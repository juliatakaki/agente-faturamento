"""
Servidor MCP para consulta à tabela SIGTAP.
Expõe duas ferramentas:
  - buscar_procedimento: busca por texto livre no SIGTAP
  - buscar_por_codigo:   busca pelo código exato

Fonte de dados: Postgres (tabela SIGTAP completa, importada do DATASUS).
Tabelas usadas: tb_procedimento, tb_descricao, tb_grupo.

NOTA SOBRE O GRUPO: tb_procedimento não tem uma coluna co_grupo (FK direta).
No layout oficial do SIGTAP, o código do procedimento já contém o grupo,
subgrupo e forma de organização embutidos nos 6 primeiros dígitos
(GG.SS.FF.AAA-V). Por isso o grupo é derivado a partir dos 2 primeiros
dígitos de co_procedimento, sem precisar de uma coluna extra.
"""

import math
import os
import json
import re
import sys
import threading
import time
import unicodedata
from datetime import datetime

# ── Modo offline do Hugging Face ────────────────────────────────────────────
# DEVE vir ANTES de qualquer import de sentence_transformers/transformers,
# porque essas bibliotecas leem estas variáveis no momento do import. Sem
# isso, mesmo com o modelo já em cache local, o SentenceTransformer dispara
# mais de uma dezena de requisições HTTP ao Hugging Face Hub só para
# revalidar arquivos -- lento sempre, e travando de vez atrás de proxy.
# Para trocar de modelo, rode pre_aquecer_sigtap.py com HF_SIGTAP_OFFLINE=false.
if os.getenv("HF_SIGTAP_OFFLINE", "true").lower() == "true":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np
import pandas as pd
import psycopg2
from rapidfuzz import fuzz
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

load_dotenv()

# ── Log garantido (arquivo + stderr) ────────────────────────────────────────
# Este servidor roda como SUBPROCESSO do pipeline (stdio); mensagens em
# stderr podem não chegar ao terminal, fazendo etapas lentas parecerem
# travamento. _log() escreve em stderr E num arquivo em disco.
#   PowerShell: Get-Content src\mcp\sigtap_server.log -Wait
#   Linux/Mac:  tail -f src/mcp/sigtap_server.log
#
# O log é também onde o CICLO DO AGENTE (nível 4) fica registrado turno a
# turno -- é a evidência de que as decisões partiram do modelo, e não de um
# roteiro fixo. Vale guardar esse arquivo junto dos resultados do TCC.

CAMINHO_LOG_SERVIDOR = os.getenv(
    "SIGTAP_LOG_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "sigtap_server.log"),
)


def _log(mensagem: str) -> None:
    linha = f"[{datetime.now().strftime('%H:%M:%S')}] {mensagem}"
    print(linha, file=sys.stderr, flush=True)
    try:
        with open(CAMINHO_LOG_SERVIDOR, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass


# ── Inicialização ──────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": os.getenv("SIGTAP_DB_HOST", "localhost"),
    "port": os.getenv("SIGTAP_DB_PORT", "5432"),
    "dbname": os.getenv("SIGTAP_DB_NAME", "sigtap"),
    "user": os.getenv("SIGTAP_DB_USER", "sigtap"),
    "password": os.getenv("SIGTAP_DB_PASSWORD", "sigtap"),
}

SIGTAP_DB_CONNECT_TIMEOUT = int(os.getenv("SIGTAP_DB_CONNECT_TIMEOUT", "5"))

QUERY_SIGTAP = """
    SELECT
        p.co_procedimento AS codigo_bruto,
        p.no_procedimento AS nome_curto,
        COALESCE(d.ds_procedimento, '') AS descricao_longa,
        LEFT(p.co_procedimento, 2) AS co_grupo_derivado,
        COALESCE(p.vl_sh, 0) AS vl_sh,
        COALESCE(p.vl_sa, 0) AS vl_sa,
        COALESCE(p.vl_sp, 0) AS vl_sp
    FROM tb_procedimento p
    LEFT JOIN tb_descricao d ON d.co_procedimento = p.co_procedimento
"""

QUERY_GRUPOS = "SELECT co_grupo, no_grupo FROM tb_grupo"

mcp = FastMCP("sigtap-server")

_tabela: pd.DataFrame | None = None
_idf: dict[str, float] | None = None

# Protege o carregamento preguiçoso de tabela/modelo/embeddings.
_lock_carga = threading.RLock()


# ── Dicionário clínico -> SIGTAP (Nível 0) ─────────────────────────────────
#
# A calibração mostrou que os erros restantes da busca são de VOCABULÁRIO, e
# não de algoritmo: o prontuário usa o nome clínico e o SIGTAP usa o
# administrativo ("raio-x de tórax" x "RADIOGRAFIA DE TÓRAX"; "CK-MB" x
# "CREATINOFOSFOQUINASE FRAÇÃO MB"). Nenhum limiar resolve isso -- o modelo
# de embeddings genérico não conhece esse vocabulário e o fuzzy confunde
# analitos parecidos (procalcitonina x calcitonina, substâncias diferentes).
#
# O dicionário fica num JSON externo, editável sem tocar no código, e aponta
# para TEXTOS do SIGTAP, nunca para códigos: assim cada alvo é validado
# contra a tabela real (validar_sinonimos.py), e um alvo inexistente aparece
# como erro de validação em vez de virar código errado no relatório.
_CAMINHO_SINONIMOS = os.getenv(
    "SIGTAP_SINONIMOS",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "sinonimos_sigtap.json"),
)

# Similaridade mínima para casar um termo com uma CHAVE do dicionário quando
# não há correspondência exata. Ver _resolver_chave_dicionario().
_LIMIAR_CHAVE_DICIONARIO = int(os.getenv("LIMIAR_CHAVE_DICIONARIO", "92"))

_sinonimos: dict[str, list[str]] | None = None
_nao_faturavel: dict[str, str] | None = None


def _carregar_dicionario() -> tuple[dict[str, list[str]], dict[str, str]]:
    """
    Carrega o dicionário do JSON externo. Devolve:
      - sinonimos: termo normalizado -> lista de termos de busca no SIGTAP
      - nao_faturavel: termo normalizado -> motivo (chave da categoria no JSON)

    Se o arquivo não existir ou estiver malformado, o servidor segue
    funcionando sem o Nível 0 (degradação graciosa) e registra o aviso.
    """
    global _sinonimos, _nao_faturavel
    if _sinonimos is not None and _nao_faturavel is not None:
        return _sinonimos, _nao_faturavel

    _sinonimos, _nao_faturavel = {}, {}
    try:
        with open(_CAMINHO_SINONIMOS, encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        _log(f"[NIVEL0] AVISO: dicionário não encontrado em "
             f"{_CAMINHO_SINONIMOS} — Nível 0 desativado.")
        return _sinonimos, _nao_faturavel
    except json.JSONDecodeError as e:
        _log(f"[NIVEL0] ERRO de sintaxe no dicionário ({e}) — Nível 0 desativado.")
        return _sinonimos, _nao_faturavel

    for chave, alvos in (dados.get("sinonimos") or {}).items():
        if chave.startswith("_") or not isinstance(alvos, list):
            continue
        _sinonimos[_normalizar(chave)] = [_normalizar(a) for a in alvos]

    for motivo, termos in (dados.get("nao_faturavel") or {}).items():
        if motivo.startswith("_") or not isinstance(termos, list):
            continue
        for termo in termos:
            _nao_faturavel[_normalizar(termo)] = motivo

    _log(f"[NIVEL0] Dicionário carregado: {len(_sinonimos)} sinônimo(s), "
         f"{len(_nao_faturavel)} termo(s) não faturável(is).")
    return _sinonimos, _nao_faturavel


def _resolver_chave_dicionario(
    termo_norm: str,
    sinonimos: dict[str, list[str]],
    nao_faturavel: dict[str, str],
) -> str:
    """
    Devolve a chave do dicionário correspondente ao termo, aceitando pequenas
    corrupções de grafia.

    POR QUE ISTO EXISTE: o LLM às vezes altera o termo ao repassá-lo para a
    ferramenta, mesmo instruído a copiar o texto exato. Foram observados
    'oxigânio' por 'oxigênio', 'intubáção' e até 'intubãão' por 'intubação',
    'volémica' por 'volêmica'. A remoção de acentos absorve a variante
    lusitana, mas não a troca ou perda de letra -- e como o dicionário é
    casado por chave exata, um caractere trocado anulava toda a curadoria.
    """
    if termo_norm in sinonimos or termo_norm in nao_faturavel:
        return termo_norm

    chaves = list(sinonimos) + list(nao_faturavel)
    if not chaves:
        return termo_norm

    melhor = max(chaves, key=lambda k: fuzz.ratio(termo_norm, k))
    score = fuzz.ratio(termo_norm, melhor)
    if score >= _LIMIAR_CHAVE_DICIONARIO:
        _log(f"[NIVEL0] '{termo_norm}' casado com a chave '{melhor}' "
             f"(similaridade {score:.0f}; provável corrupção do termo pelo LLM).")
        return melhor
    return termo_norm


# ── Filtro por grupo do SIGTAP conforme a categoria da entidade ────────────
#
# Cada categoria de entidade só pode, por construção, corresponder a alguns
# grupos do SIGTAP (os 2 primeiros dígitos do código). Sem esse filtro, a
# busca varre os 4.994 procedimentos e produz falsos positivos absurdos:
# "manitol" (medicamento) casando com PIELOSTOMIA (cirurgia), "heparina" com
# HEPATORRAFIA -- casamentos por semelhança de subpalavras, não de sentido.
#
# Grupos oficiais:
#   01 Promoção e prevenção   02 Diagnóstica          03 Clínicos
#   04 Cirúrgicos             05 Transplantes         06 Medicamentos
#   07 OPME                   08 Ações complementares
_MAPA_CATEGORIA_GRUPOS = {
    "MEDICAMENTO": {"06"},
    "MATERIAL": {"07"},
    "EXAME": {"02"},
    "PROCEDIMENTO": {"03", "04", "05"},
}

# Quando a busca restrita ao grupo não encontra nada, o padrão é reportar
# lacuna em vez de reabrir a busca para a tabela toda: em faturamento, uma
# lacuna sinalizada é preferível a um código de grupo errado, que gera glosa.
RETENTAR_SEM_FILTRO = os.getenv("SIGTAP_RETENTAR_SEM_FILTRO", "false").lower() == "true"


# ── Busca semântica (embeddings) ────────────────────────────────────────────
#
# LIMITAÇÃO MEDIDA: o modelo multilíngue genérico não conhece boa parte do
# vocabulário clínico raro (fármacos, epônimos). Para esses termos ele
# recorre à semelhança de SUBPALAVRAS, não de sentido -- daí "heparina" ->
# "hepatite", "sulfadiazina" -> "sulfassalazina". Por isso o limiar é alto e
# a busca devolve VAZIO quando nada o ultrapassa.
_MODELO_EMBEDDINGS_NOME = os.getenv(
    "MODELO_EMBEDDINGS", "paraphrase-multilingual-MiniLM-L12-v2"
)
_CACHE_EMBEDDINGS_PATH = os.path.join(
    os.path.dirname(__file__), ".cache_embeddings_sigtap.npy"
)
_LIMIAR_SIMILARIDADE_SEMANTICA = float(
    os.getenv("LIMIAR_SIMILARIDADE_SEMANTICA", "0.80")
)

# Cobertura mínima de informação (IDF) exigida no nível 2. Subido de 0.45
# para 0.55 após a calibração: em 0.45, "perfil lipídico" era aceito por
# casar apenas "perfil" (cobertura 0.46) com PERFIL DE PRESSÃO URETRAL.
_LIMIAR_COBERTURA_IDF = float(os.getenv("LIMIAR_COBERTURA_IDF", "0.55"))

# Limiar do nível 3 (fuzzy). Subido de 87 para 93 após a calibração:
# "procalcitonina" casava com DOSAGEM DE CALCITONINA a 88 -- substâncias
# diferentes, apenas com grafia parecida.
_SCORE_MINIMO_FUZZY = int(os.getenv("SCORE_MINIMO_FUZZY", "93"))

_modelo_embeddings = None
_embeddings_tabela: np.ndarray | None = None


def _carregar_modelo_embeddings():
    """Carrega o modelo de embeddings (uma vez por processo)."""
    global _modelo_embeddings
    with _lock_carga:
        if _modelo_embeddings is None:
            _log(f"[SEMANTICO] Carregando modelo '{_MODELO_EMBEDDINGS_NOME}' "
                 f"(HF_HUB_OFFLINE={os.environ.get('HF_HUB_OFFLINE', 'n/d')})...")
            t0 = time.time()
            from sentence_transformers import SentenceTransformer
            _modelo_embeddings = SentenceTransformer(_MODELO_EMBEDDINGS_NOME)
            _log(f"[SEMANTICO] Modelo carregado em {time.time() - t0:.1f}s.")
        return _modelo_embeddings


def _obter_embeddings_tabela(tabela: pd.DataFrame) -> np.ndarray:
    """
    Embeddings de TODAS as descrições (tabela completa, ordem posicional
    original), com cache em memória e em disco.

    ATENÇÃO: quando o cache em disco está válido, esta função retorna SEM
    carregar o modelo -- ela só precisa dos vetores já calculados. Por isso
    ela NÃO serve sozinha como aquecimento. Ver _aquecer().
    """
    global _embeddings_tabela
    with _lock_carga:
        if _embeddings_tabela is not None and len(_embeddings_tabela) == len(tabela):
            return _embeddings_tabela

        if os.path.exists(_CACHE_EMBEDDINGS_PATH):
            cache = np.load(_CACHE_EMBEDDINGS_PATH)
            if len(cache) == len(tabela):
                _log(f"[SEMANTICO] Cache reaproveitado ({len(cache)} linhas).")
                _embeddings_tabela = cache
                return _embeddings_tabela
            _log("[SEMANTICO] Cache desatualizado (tabela mudou) — recalculando...")

        modelo = _carregar_modelo_embeddings()
        _log(f"[SEMANTICO] Calculando embeddings para {len(tabela)} descrições "
             f"(rode pre_aquecer_sigtap.py para evitar isso no pipeline)...")
        t0 = time.time()
        embeddings = np.asarray(
            modelo.encode(
                tabela["descricao_norm"].tolist(), batch_size=64,
                show_progress_bar=False, normalize_embeddings=True,
            ),
            dtype=np.float32,
        )
        _log(f"[SEMANTICO] {len(tabela)} embeddings em {time.time() - t0:.1f}s.")

        np.save(_CACHE_EMBEDDINGS_PATH, embeddings)
        _embeddings_tabela = embeddings
        return _embeddings_tabela


def _aquecer() -> None:
    """
    Carrega dicionário, tabela, embeddings E O MODELO antes de o servidor
    aceitar conexões.

    POR QUE SÍNCRONO: aquecer numa thread de fundo perdia a corrida -- o
    cliente MCP ficava pronto em ~10s, o LLM respondia em ~2s, e a primeira
    busca chegava com o carregamento em andamento, ficava bloqueada no lock e
    estourava o timeout do cliente.

    POR QUE O ENCODE DE TESTE: chamar só _obter_embeddings_tabela() encontra
    o cache em disco e RETORNA SEM CARREGAR O MODELO -- aquecia a parte
    barata e deixava a cara para a primeira busca semântica, que seguia
    estourando o timeout ('midazolam', 180s).
    """
    t0 = time.time()
    try:
        _carregar_dicionario()
        tabela = _get_tabela()

        if os.getenv("USAR_BUSCA_SEMANTICA", "true").lower() == "true":
            _obter_embeddings_tabela(tabela)
            modelo = _carregar_modelo_embeddings()
            t1 = time.time()
            modelo.encode(["aquecimento"], normalize_embeddings=True)
            _log(f"[AQUECIMENTO] Primeiro encode em {time.time() - t1:.1f}s.")

        _log(f"[AQUECIMENTO] Concluído em {time.time() - t0:.1f}s — as buscas "
             f"já respondem sem atraso inicial.")
    except Exception as e:
        _log(f"[AQUECIMENTO] AVISO: falhou ({type(e).__name__}: {e}). "
             f"O carregamento ocorrerá sob demanda, na primeira busca.")


def _buscar_semantico(
    termo_norm: str, candidatos: pd.DataFrame
) -> tuple[pd.DataFrame, float]:
    """
    Busca por similaridade de SIGNIFICADO dentro do recorte `candidatos`.
    Retorna (resultado, melhor_score); resultado VAZIO quando nada ultrapassa
    o limiar. Embeddings normalizados => cosseno vira produto escalar.
    """
    tabela_completa = _get_tabela()
    modelo = _carregar_modelo_embeddings()
    embeddings_tabela = _obter_embeddings_tabela(tabela_completa)

    posicoes = candidatos.index.to_numpy()
    if len(posicoes) == 0:
        return candidatos, 0.0

    embedding_termo = modelo.encode(
        [termo_norm], normalize_embeddings=True
    )[0].astype(np.float32)

    similaridades = embeddings_tabela[posicoes] @ embedding_termo
    melhor_local = int(np.argmax(similaridades))
    melhor_score = float(similaridades[melhor_local])
    linha = candidatos.iloc[[melhor_local]]

    _log(f"[SEMANTICO] '{termo_norm}': {melhor_score:.3f} "
         f"(limiar {_LIMIAR_SIMILARIDADE_SEMANTICA}) -> "
         f"{linha.iloc[0]['descricao'][:60]}")

    if melhor_score < _LIMIAR_SIMILARIDADE_SEMANTICA:
        return candidatos.iloc[0:0], melhor_score
    return linha, melhor_score


def _normalizar(texto: str) -> str:
    """
    Minúsculas, sem acentos (tórax → torax), sem hífens (raio-x → raio x).
    Trocas de letra, que os acentos não cobrem, são tratadas em
    _resolver_chave_dicionario().
    """
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.replace("-", " ")


def _formatar_codigo(codigo_str: str) -> str:
    """'0202020380' -> '02.02.02.038-0'."""
    codigo_str = str(codigo_str).strip().zfill(10)
    return (
        f"{codigo_str[0:2]}.{codigo_str[2:4]}.{codigo_str[4:6]}."
        f"{codigo_str[6:9]}-{codigo_str[9]}"
    )


def _carregar_do_postgres() -> pd.DataFrame:
    """
    Conecta no Postgres e monta o DataFrame (tb_procedimento + tb_descricao +
    tb_grupo via código derivado). Usa SQLAlchemy quando disponível (evita o
    UserWarning do pandas); cai para psycopg2 direto se não estiver instalado.
    """
    _log(f"[SIGTAP] Conectando ao Postgres em "
         f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']} "
         f"(timeout={SIGTAP_DB_CONNECT_TIMEOUT}s)...")
    t0 = time.time()

    try:
        from sqlalchemy import create_engine
        url = (
            f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
        )
        engine = create_engine(
            url, connect_args={"connect_timeout": SIGTAP_DB_CONNECT_TIMEOUT}
        )
        with engine.connect() as conn:
            procedimentos = pd.read_sql_query(QUERY_SIGTAP, conn)
            grupos = pd.read_sql_query(QUERY_GRUPOS, conn)
        engine.dispose()
    except ImportError:
        _log("[SIGTAP] SQLAlchemy não instalado — usando psycopg2 direto.")
        try:
            conn = psycopg2.connect(
                **DB_CONFIG, connect_timeout=SIGTAP_DB_CONNECT_TIMEOUT
            )
        except psycopg2.OperationalError as e:
            _log(f"[SIGTAP] ERRO ao conectar no Postgres: {e}")
            raise
        try:
            procedimentos = pd.read_sql_query(QUERY_SIGTAP, conn)
            grupos = pd.read_sql_query(QUERY_GRUPOS, conn)
        finally:
            conn.close()

    _log(f"[SIGTAP] Tabela carregada: {len(procedimentos)} procedimentos, "
         f"{len(grupos)} grupos, em {time.time() - t0:.1f}s.")

    return procedimentos.merge(
        grupos, left_on="co_grupo_derivado", right_on="co_grupo", how="left"
    )


def _calcular_idf(tabela: pd.DataFrame) -> dict[str, float]:
    """
    IDF de cada palavra do vocabulário: idf(p) = ln(N / df(p)).

    PARA QUE SERVE: pesar a evidência de cada palavra que casa na busca
    parcial. Palavras em centenas de descrições ("total", "abdominal")
    quase não distinguem nada; palavras raras ("gasometria", "troponina")
    praticamente identificam o procedimento.
    """
    n_docs = len(tabela)
    freq: dict[str, int] = {}
    for desc in tabela["descricao_norm"]:
        for palavra in set(desc.split()):
            freq[palavra] = freq.get(palavra, 0) + 1
    return {p: math.log(n_docs / df) for p, df in freq.items()}


def _idf_palavra(palavra: str) -> float:
    """
    IDF de uma palavra. Ausentes do vocabulário do SIGTAP recebem o IDF
    máximo (ln N): são maximamente discriminativas por definição.
    """
    global _idf
    if _idf is None:
        _idf = _calcular_idf(_get_tabela())
    return _idf.get(palavra, math.log(len(_get_tabela())))


def _get_tabela() -> pd.DataFrame:
    global _tabela
    with _lock_carga:
        if _tabela is not None:
            return _tabela

        bruta = _carregar_do_postgres()

        tabela = pd.DataFrame()
        tabela["codigo_bruto"] = bruta["codigo_bruto"]
        tabela["codigo"] = tabela["codigo_bruto"].apply(_formatar_codigo)
        tabela["co_grupo"] = bruta["co_grupo_derivado"]

        # Descrição usada na busca: apenas o nome curto. A descrição longa é
        # mantida como contexto, mas NÃO participa da busca textual: costuma
        # ser um protocolo narrativo que cita de passagem outros exames.
        tabela["descricao"] = bruta["nome_curto"]
        tabela["descricao_longa"] = bruta["descricao_longa"]

        tabela["grupo"] = bruta["no_grupo"].fillna("Não classificado")
        tabela["descricao_norm"] = tabela["descricao"].apply(_normalizar)
        tabela["n_palavras_desc"] = tabela["descricao_norm"].apply(
            lambda d: max(len([p for p in d.split() if len(p) > 2]), 1)
        )

        # O SIGTAP armazena valores em centavos. vl_sh = Serviço Hospitalar,
        # vl_sa = Ambulatorial, vl_sp = Profissional; total = soma dos três.
        tabela["vl_sh"] = (bruta["vl_sh"].fillna(0).astype(float) / 100.0).round(2)
        tabela["vl_sa"] = (bruta["vl_sa"].fillna(0).astype(float) / 100.0).round(2)
        tabela["vl_sp"] = (bruta["vl_sp"].fillna(0).astype(float) / 100.0).round(2)
        tabela["vl_total"] = (tabela["vl_sh"] + tabela["vl_sa"] + tabela["vl_sp"]).round(2)

        _tabela = tabela.reset_index(drop=True)
        return _tabela


# ── Busca em níveis ────────────────────────────────────────────────────────

# Palavras de negação: quando uma delas precede um termo buscado na descrição
# e o termo de busca NÃO contém a mesma negação, o candidato é descartado --
# evita que "ventilação mecânica invasiva" retorne "ventilação mecânica NÃO
# invasiva", de sentido clínico oposto.
_PALAVRAS_NEGACAO = ("nao", "sem")


def _tem_negacao_indevida(desc_norm: str, palavras_termo: list[str]) -> bool:
    """Verifica se a descrição nega indevidamente uma das palavras buscadas."""
    if any(neg in palavras_termo for neg in _PALAVRAS_NEGACAO):
        return False  # o termo já fala de negação (ex: "ventilação não invasiva")

    tokens = desc_norm.split()
    for i, tok in enumerate(tokens):
        if tok in _PALAVRAS_NEGACAO:
            if any(p in tokens[i + 1 : i + 3] for p in palavras_termo):
                return True
    return False


def _contem_palavra(desc: str, palavra: str) -> bool:
    """
    `palavra` aparece em `desc` como PALAVRA INTEIRA, não como substring.
    Sem isso, "dreno" é achada em "aDRENOcorticotrófico" e "monitor" em
    "MONITORamento".
    """
    return re.search(rf"\b{re.escape(palavra)}\b", desc) is not None


def _filtrar_por_categoria(tabela: pd.DataFrame, categoria: str) -> pd.DataFrame:
    """Recorta a tabela aos grupos compatíveis com a categoria da entidade."""
    grupos = _MAPA_CATEGORIA_GRUPOS.get((categoria or "").strip().upper())
    return tabela if not grupos else tabela[tabela["co_grupo"].isin(grupos)]


def _confianca(nivel: str, score: float) -> str:
    """
    Classifica a confiança, para o relatório destacar o que precisa de
    conferência humana. Limiares deliberadamente conservadores: superestimar
    a confiança de uma correspondência errada custa mais, em faturamento, do
    que sinalizar uma correta para revisão.
    """
    if nivel == "nivel0":
        # Tradução curada manualmente e validada contra a tabela real.
        return "alta"
    if nivel == "nivel1":
        return "alta" if score >= 0.60 else "media"
    if nivel == "nivel2":
        return "media" if score >= 0.55 else "baixa"
    if nivel == "nivel_semantico":
        return "media" if score >= 0.88 else "baixa"
    if nivel == "nivel3":
        # Fuzzy quase perfeito indica diferença só de grafia/acentuação
        # ("Doppler transcraniano" x "ECODOPPLER TRANSCRANIANO").
        return "media" if score >= 0.97 else "baixa"
    if nivel == "nivel4":
        # Correspondência proposta pelo agente: SEMPRE baixa. É o nível com
        # menos garantia formal, e o objetivo dele é resgatar lacunas para
        # conferência humana, não fechar faturamento sozinho.
        return "baixa"
    return "baixa"


def _buscar_niveis_texto(
    termo_norm: str, candidatos: pd.DataFrame
) -> tuple[pd.DataFrame, str, float]:
    """
    Níveis 1 a 3 (exata, parcial ponderada por IDF, semântica, fuzzy) sobre o
    recorte `candidatos`. Separado de _buscar_com_nivel para que os níveis 0
    e 4 possam reaproveitá-lo, sem recursão.
    """
    palavras = [p for p in termo_norm.split() if len(p) > 2] or [termo_norm]
    idf_total = sum(_idf_palavra(p) for p in palavras) or 1.0

    # ── Nível 1 — exata, com DESEMPATE POR DENSIDADE. Quando várias
    # descrições contêm todas as palavras, a mais curta costuma ser a certa:
    # a mais longa normalmente é um procedimento MAIS ESPECÍFICO que apenas
    # contém o termo (ex: "ventilação mecânica invasiva" casando com o
    # acompanhamento DOMICILIAR).
    #
    # LIMITAÇÃO CONHECIDA: o critério é de tamanho, não clínico. Para
    # medicamentos ele escolhe a apresentação de nome mais curto ("MORFINA
    # 10 MG (POR COMPRIMIDO)" em vez de "MORFINA 10 MG/ML (POR AMPOLA)").
    mascara = candidatos["descricao_norm"].apply(
        lambda desc: all(_contem_palavra(desc, p) for p in palavras)
        and not _tem_negacao_indevida(desc, palavras)
    )
    resultados = candidatos[mascara]
    if not resultados.empty:
        resultados = resultados.copy()
        resultados["_score"] = len(palavras) / resultados["n_palavras_desc"]
        resultados = resultados.sort_values("_score", ascending=False)
        return resultados, "nivel1", float(resultados.iloc[0]["_score"])

    # ── Nível 2 — parcial ponderada por IDF. Só aceita quando as palavras
    # que casaram respondem por uma fração mínima da informação do termo,
    # rejeitando casamentos por palavra fraca ("máscara facial TOTAL" x
    # "DOSAGEM DE BILIRRUBINA TOTAL").
    def _score_nivel2(desc: str) -> float:
        casadas = [p for p in palavras if _contem_palavra(desc, p)]
        if not casadas or _tem_negacao_indevida(desc, casadas):
            return 0.0
        return sum(_idf_palavra(p) for p in casadas) / idf_total

    scores2 = candidatos["descricao_norm"].apply(_score_nivel2)
    aceitos = candidatos[scores2 >= _LIMIAR_COBERTURA_IDF]
    if not aceitos.empty:
        aceitos = aceitos.copy()
        cobertura = scores2[scores2 >= _LIMIAR_COBERTURA_IDF]
        densidade = len(palavras) / aceitos["n_palavras_desc"]
        # 70% cobertura do termo + 30% densidade: prefere descrições curtas
        # e específicas entre as aceitas
        aceitos["_score"] = 0.7 * cobertura + 0.3 * densidade
        aceitos = aceitos.sort_values("_score", ascending=False)
        return aceitos, "nivel2", float(cobertura.max())

    # ── Nível semântico — significado via embeddings, dentro do recorte.
    if os.getenv("USAR_BUSCA_SEMANTICA", "true").lower() == "true" and not candidatos.empty:
        try:
            resultados, score_sem = _buscar_semantico(termo_norm, candidatos)
            if not resultados.empty:
                return resultados, "nivel_semantico", score_sem
        except ImportError:
            _log("[SEMANTICO] AVISO: 'sentence-transformers' não instalado.")

    # ── Nível 3 — fuzzy, com limiar alto. Nomes de analitos diferem por
    # prefixos curtos e o fuzzy os confunde (procalcitonina x calcitonina).
    if not candidatos.empty:
        scores = candidatos["descricao_norm"].apply(
            lambda desc: fuzz.partial_ratio(termo_norm, desc)
        )
        fuzzy = candidatos[scores >= _SCORE_MINIMO_FUZZY]
        if not fuzzy.empty:
            fuzzy = fuzzy.copy()
            fuzzy["_score"] = scores[scores >= _SCORE_MINIMO_FUZZY]
            fuzzy = fuzzy.sort_values("_score", ascending=False)
            return fuzzy, "nivel3", float(fuzzy.iloc[0]["_score"]) / 100.0

    return candidatos.iloc[0:0], "vazio", 0.0


# ══════════════════════════════════════════════════════════════════════════
# NÍVEL 4 — CICLO AGÊNTICO
# ══════════════════════════════════════════════════════════════════════════
#
# É AQUI que o sistema deixa de ser uma esteira de passos fixos e passa a ter
# um agente. A diferença não está em usar um LLM (os outros níveis também
# poderiam usar), e sim em QUEM CONTROLA O LAÇO:
#
#   - Nos níveis 0 a 3, o código decide tudo: a ordem das tentativas, quantas
#     são, e quando parar. O LLM não participa.
#   - No nível 4, o código não sabe de antemão quantas tentativas haverá nem
#     quais termos serão buscados. O modelo propõe um termo, VÊ O RESULTADO
#     REAL da busca no SIGTAP, e decide a partir dele: aceitar um candidato,
#     tentar outro termo, ou declarar que não existe código. O número de
#     voltas varia de termo para termo, na mesma execução -- na primeira
#     rodada, de 2 voltas ('midazolam') a 4 ('cultura de ferida').
#
# Esse ciclo (agir -> observar -> decidir) é o que caracteriza um agente, e é
# a razão de a arquitetura ser agêntica em vez de um pipeline linear: a
# distância entre a linguagem clínica do prontuário e a administrativa do
# SIGTAP não é previsível o suficiente para caber numa sequência fixa.
#
# ── TRÊS TRAVAS DE SEGURANÇA ────────────────────────────────────────────────
#
# Faturamento indevido gera glosa, então a autonomia é deliberadamente limitada:
#
# 1. O MODELO NUNCA ESCREVE UM CÓDIGO. Ele só propõe TERMOS DE BUSCA (texto)
#    e escolhe candidatos POR ÍNDICE numa lista que o Python montou a partir
#    da tabela real. Se alucinar um nome de exame inexistente, a busca não
#    encontra nada -- vira lacuna, não vira código errado.
#
# 2. TETO DE TENTATIVAS. O laço é do modelo, mas dentro de um limite. O teto
#    é um limite de custo e de terminação, não um roteiro: dentro dele, quem
#    decide é o modelo.
#
# 3. FALHA VIRA DESISTÊNCIA. Resposta malformada, JSON inválido, índice fora
#    da lista, API fora do ar -- qualquer imprevisto encerra o ciclo sem
#    resultado. O sistema nunca "chuta" para não voltar de mãos vazias.
#
# Toda correspondência do nível 4 recebe confiança BAIXA e vai para a lista
# de conferência humana no relatório.
#
# ── RESULTADO DA PRIMEIRA RODADA (ago/2026, Groq llama-3.3-70b) ────────────
#
# 11 termos entraram no ciclo, nenhum foi resgatado, e as recusas foram
# clinicamente corretas -- o agente rejeitou DOSAGEM DE PROLACTINA para
# 'procalcitonina' ("prolactina é um hormônio diferente"), DOSAGEM DE
# ALUMÍNIO para 'albumina sérica', e insulinas análogas para 'insulina
# regular'. São exatamente os falsos positivos que os níveis 2 e 3
# aceitavam. A autonomia foi usada para reconhecer ausência, não para
# preencher lacunas com códigos plausíveis.

USAR_LLM_FALLBACK = os.getenv("USAR_LLM_FALLBACK", "true").lower() == "true"

# Teto subido de 4 para 6 após a primeira rodada: 'cultura de ferida'
# esbarrou no limite ainda progredindo (na 3ª volta já tinha achado
# candidatos plausíveis e ia refinar). O teto existe para garantir
# terminação e conter custo, não para interromper raciocínio em andamento.
NIVEL4_MAX_TENTATIVAS = int(os.getenv("SIGTAP_NIVEL4_MAX_TENTATIVAS", "6"))
NIVEL4_MAX_CANDIDATOS = int(os.getenv("SIGTAP_NIVEL4_MAX_CANDIDATOS", "5"))

_llm_nivel4 = None


def _criar_llm_nivel4():
    """
    Cria o modelo usado pelo agente do nível 4, lendo as MESMAS variáveis de
    ambiente do pipeline (PROVEDOR_LLM, PROVEDOR_API, MODELO_API,
    MODELO_LOCAL). Como o servidor MCP roda como subprocesso do pipeline, ele
    herda o ambiente -- então a escolha feita no menu do main.py vale aqui
    também, e o experimento de comparação entre modelos cobre este nível.
    """
    global _llm_nivel4
    if _llm_nivel4 is not None:
        return _llm_nivel4

    provedor = os.getenv("PROVEDOR_LLM", "local").strip().lower()

    if provedor == "api":
        provedor_api = os.getenv("PROVEDOR_API", "").strip().lower()
        modelo = os.getenv("MODELO_API", "")
        _log(f"[NIVEL4] Agente usando API ({provedor_api}): {modelo}")

        if provedor_api == "openai":
            from langchain_openai import ChatOpenAI
            _llm_nivel4 = ChatOpenAI(model=modelo, temperature=0)
        elif provedor_api == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            _llm_nivel4 = ChatGoogleGenerativeAI(model=modelo, temperature=0)
        elif provedor_api == "anthropic":
            from langchain_anthropic import ChatAnthropic
            _llm_nivel4 = ChatAnthropic(model=modelo, temperature=0)
        elif provedor_api == "groq":
            # A Groq expõe API compatível com a da OpenAI.
            from langchain_openai import ChatOpenAI
            _llm_nivel4 = ChatOpenAI(
                model=modelo, temperature=0,
                api_key=os.getenv("GROQ_API_KEY", ""),
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            raise ValueError(f"PROVEDOR_API não suportado: '{provedor_api}'")
    else:
        from langchain_ollama import ChatOllama
        modelo = os.getenv("MODELO_LOCAL", "llama3.2")
        _log(f"[NIVEL4] Agente usando modelo LOCAL via Ollama: {modelo}")
        _llm_nivel4 = ChatOllama(model=modelo, temperature=0)

    return _llm_nivel4


_NIVEL4_SISTEMA = """Você é um especialista em faturamento hospitalar do SUS.

Um termo clínico foi extraído de um prontuário e NÃO foi encontrado na tabela
SIGTAP pelas buscas automáticas. Sua tarefa é descobrir se existe um
procedimento SIGTAP correspondente, propondo termos de busca alternativos.

CONTEXTO IMPORTANTE: o prontuário usa linguagem clínica e o SIGTAP usa
linguagem administrativa. Exemplos reais dessa diferença:
- "raio-x de tórax" no SIGTAP é "RADIOGRAFIA DE TORAX"
- "CK-MB" no SIGTAP é "DOSAGEM DE CREATINOFOSFOQUINASE FRACAO MB"
- exames laboratoriais costumam começar com "DOSAGEM DE" ou "PESQUISA DE"

A BUSCA IGNORA MAIÚSCULAS, ACENTOS E HÍFENS. Propor o mesmo termo com outra
grafia, em caixa alta ou sem hífen NÃO muda nada e desperdiça uma tentativa.
Para mudar o resultado, mude as PALAVRAS: use o sinônimo administrativo, o
nome técnico do analito, ou o termo mais amplo da família do procedimento.

IGUALMENTE IMPORTANTE: muitos itens do prontuário simplesmente NÃO TÊM código
próprio no SIGTAP. Medicamentos de uso hospitalar rotineiro, insumos
descartáveis e atos incluídos em outro procedimento não são faturáveis
separadamente. Nesses casos, a resposta CORRETA é desistir. Não force uma
correspondência: um código errado gera glosa, uma lacuna sinalizada não.

A cada rodada, responda APENAS com um JSON, sem texto fora dele e sem blocos
de código markdown. Use uma destas três formas:

{"acao": "buscar", "termo": "termo alternativo a buscar", "motivo": "por quê"}
{"acao": "aceitar", "indice": N, "motivo": "por quê este é o mesmo ato clínico"}
{"acao": "desistir", "motivo": "por que não existe código correspondente"}

REGRAS:
- "aceitar" só é permitido para um índice da lista de candidatos que acabei
  de mostrar. NUNCA invente códigos ou índices fora da lista.
- Só aceite se for efetivamente o MESMO exame/procedimento. Compartilhar uma
  palavra, ser da mesma área do corpo ou ter grafia parecida NÃO basta.
  Atenção a diferenças de material biológico (sangue x urina), de via de
  administração e de forma farmacêutica.
- Na dúvida, prefira desistir."""


def _extrair_json_llm(texto: str) -> dict | None:
    """
    Extrai o JSON da resposta do modelo, tolerando blocos markdown e texto
    em volta. Devolve None se não for possível interpretar -- e no ciclo do
    agente, None significa desistir (nunca chutar).
    """
    bruto = (texto or "").strip()
    if bruto.startswith("```"):
        bruto = re.sub(r"^```[a-zA-Z]*\n?", "", bruto)
        bruto = re.sub(r"\n?```$", "", bruto).strip()

    try:
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else None
    except json.JSONDecodeError:
        pass

    # Alguns modelos escrevem uma frase antes do JSON; tenta o primeiro
    # objeto que aparecer no texto.
    m = re.search(r"\{.*\}", bruto, re.DOTALL)
    if m:
        try:
            dados = json.loads(m.group(0))
            return dados if isinstance(dados, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _indice_valido(valor, tamanho: int) -> int | None:
    """
    Converte o índice devolvido pelo modelo, aceitando inteiro ou string
    numérica ("0" além de 0) -- alguns modelos entregam o número entre
    aspas, e recusar por causa disso descartaria uma escolha válida.
    Devolve None quando não é um índice utilizável da lista.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        indice = valor
    elif isinstance(valor, str) and valor.strip().isdigit():
        indice = int(valor.strip())
    else:
        return None
    return indice if 0 <= indice < tamanho else None


def _fallback_llm_agente(
    termo: str, categoria: str, candidatos_base: pd.DataFrame
) -> tuple[pd.DataFrame, int] | None:
    """
    Nível 4: ciclo agêntico de resgate de termos sem correspondência.

    Fluxo de cada volta:
      1. O modelo propõe um termo de busca (ou desiste).
      2. O CÓDIGO executa esse termo nos níveis determinísticos 1 a 3,
         dentro do recorte da categoria -- ou seja, a proposta do modelo é
         validada contra a tabela real, não aceita de véu.
      3. O resultado (até NIVEL4_MAX_CANDIDATOS descrições reais) VOLTA para
         o modelo, que decide a próxima ação vendo o que de fato existe.

    MEMÓRIA DE TENTATIVAS: o ciclo guarda os termos já buscados (na forma
    normalizada) e avisa o modelo quando ele repete um. Na primeira rodada,
    metade dos ciclos gastou a volta inicial rebuscando o termo original com
    outra grafia ('midazolam' -> 'midazolam', 'fentanil' -> 'FENTANIL'),
    porque o modelo não sabia o que já havia sido tentado. Repetições agora
    não consomem busca e são respondidas na hora.

    Retorna (linha_do_dataframe, numero_de_tentativas) ou None se o agente
    desistiu, estourou o teto ou algo falhou.
    """
    try:
        llm = _criar_llm_nivel4()
    except Exception as e:
        _log(f"[NIVEL4] Não foi possível criar o modelo ({type(e).__name__}: {e}) "
             f"— nível 4 pulado.")
        return None

    termo_norm_original = _normalizar(termo).strip()
    tentados: set[str] = {termo_norm_original}

    _log(f"[NIVEL4] ===== Iniciando ciclo para '{termo}' "
         f"(categoria={categoria or 'não informada'}, "
         f"teto de {NIVEL4_MAX_TENTATIVAS} tentativas) =====")

    historico = [
        SystemMessage(content=_NIVEL4_SISTEMA),
        HumanMessage(content=(
            f'Termo do prontuário: "{termo}"\n'
            f'Categoria: {categoria or "não informada"}\n'
            f'Espaço de busca: {len(candidatos_base)} procedimentos do SIGTAP '
            f'compatíveis com essa categoria.\n\n'
            f'JÁ FOI TENTADO, sem resultado: "{termo_norm_original}" — nas '
            f'buscas exata, parcial, semântica e por similaridade. Repetir '
            f'esse mesmo termo (mesmo em caixa alta, com acento ou sem hífen) '
            f'daria exatamente o mesmo resultado.\n\n'
            f'Proponha um termo com PALAVRAS DIFERENTES, ou desista se '
            f'entender que não existe código próprio no SIGTAP para isso.'
        )),
    ]

    ultima_lista: pd.DataFrame | None = None

    for tentativa in range(1, NIVEL4_MAX_TENTATIVAS + 1):
        try:
            resposta = llm.invoke(historico)
        except Exception as e:
            _log(f"[NIVEL4] Falha ao chamar o modelo ({type(e).__name__}: {e}) "
                 f"— encerrando ciclo.")
            return None

        conteudo = getattr(resposta, "content", "") or ""
        decisao = _extrair_json_llm(conteudo)

        if not decisao:
            _log(f"[NIVEL4] Tentativa {tentativa}: resposta não interpretável "
                 f"como JSON — desistindo. Resposta: {conteudo[:120]!r}")
            return None

        acao = str(decisao.get("acao", "")).strip().lower()
        motivo = str(decisao.get("motivo", ""))[:160]

        # ── Ação: desistir ────────────────────────────────────────────────
        if acao == "desistir":
            _log(f"[NIVEL4] Tentativa {tentativa}: DESISTIR — {motivo}")
            _log(f"[NIVEL4] ===== Ciclo de '{termo}' encerrado sem "
                 f"correspondência ({tentativa} tentativa(s)) =====")
            return None

        # ── Ação: aceitar um candidato mostrado na rodada anterior ────────
        if acao == "aceitar":
            if ultima_lista is None or ultima_lista.empty:
                _log(f"[NIVEL4] Tentativa {tentativa}: tentou ACEITAR sem "
                     f"lista de candidatos — desistindo.")
                return None

            indice = _indice_valido(decisao.get("indice"), len(ultima_lista))
            if indice is None:
                _log(f"[NIVEL4] Tentativa {tentativa}: índice inválido "
                     f"({decisao.get('indice')!r}) — desistindo.")
                return None

            escolhido = ultima_lista.iloc[[indice]]
            _log(f"[NIVEL4] Tentativa {tentativa}: ACEITAR índice {indice} -> "
                 f"{escolhido.iloc[0]['descricao'][:60]} "
                 f"({escolhido.iloc[0]['codigo']}) — {motivo}")
            _log(f"[NIVEL4] ===== Ciclo de '{termo}' resolvido em "
                 f"{tentativa} tentativa(s) =====")
            return escolhido, tentativa

        # ── Ação: buscar um termo alternativo ─────────────────────────────
        if acao != "buscar":
            _log(f"[NIVEL4] Tentativa {tentativa}: ação desconhecida "
                 f"({acao!r}) — desistindo.")
            return None

        termo_sugerido = str(decisao.get("termo", "")).strip()
        if not termo_sugerido:
            _log(f"[NIVEL4] Tentativa {tentativa}: BUSCAR sem termo — desistindo.")
            return None

        termo_sugerido_norm = _normalizar(termo_sugerido).strip()

        # Repetição de um termo já tentado: responde na hora, sem gastar
        # busca. A normalização é a mesma que a busca aplica, então dois
        # termos com a mesma forma normalizada dariam resultados idênticos.
        if termo_sugerido_norm in tentados:
            _log(f"[NIVEL4] Tentativa {tentativa}: BUSCAR '{termo_sugerido}' "
                 f"— JÁ TENTADO, avisando o modelo sem repetir a busca.")
            historico.append(AIMessage(content=conteudo))
            historico.append(HumanMessage(content=(
                f'O termo "{termo_sugerido}" já foi tentado nesta sessão e '
                f'tem a mesma forma normalizada de uma busca anterior — a '
                f'busca ignora maiúsculas, acentos e hífens, então o '
                f'resultado seria idêntico.\n\n'
                f'Já tentados: {", ".join(sorted(tentados))}\n\n'
                f'Proponha um termo com palavras DIFERENTES, ou desista.'
            )))
            continue

        tentados.add(termo_sugerido_norm)
        _log(f"[NIVEL4] Tentativa {tentativa}: BUSCAR '{termo_sugerido}' — {motivo}")

        # O código executa a proposta do modelo contra a tabela real.
        resultados, nivel_interno, _ = _buscar_niveis_texto(
            termo_sugerido_norm, candidatos_base
        )

        if resultados.empty:
            ultima_lista = None
            _log(f"[NIVEL4]   -> nada encontrado para '{termo_sugerido}'")
            observacao = (
                f'A busca por "{termo_sugerido}" não encontrou nenhum '
                f'procedimento no SIGTAP.\n\n'
                f'Já tentados: {", ".join(sorted(tentados))}\n\n'
                f'Quer tentar outro termo (com palavras diferentes) ou desistir?'
            )
        else:
            ultima_lista = resultados.head(NIVEL4_MAX_CANDIDATOS).reset_index(drop=True)
            linhas = "\n".join(
                f"{i}: {row['descricao']}"
                for i, row in ultima_lista.iterrows()
            )
            _log(f"[NIVEL4]   -> {len(ultima_lista)} candidato(s) via "
                 f"{nivel_interno}: {ultima_lista.iloc[0]['descricao'][:60]}")
            observacao = (
                f'A busca por "{termo_sugerido}" encontrou estes procedimentos '
                f'reais do SIGTAP:\n\n{linhas}\n\n'
                f'Algum deles é o MESMO ato clínico que "{termo}"? '
                f'Se sim, aceite pelo índice. Se não, tente outro termo ou '
                f'desista.\n\n'
                f'Já tentados: {", ".join(sorted(tentados))}'
            )

        historico.append(AIMessage(content=conteudo))
        historico.append(HumanMessage(content=observacao))

    _log(f"[NIVEL4] ===== Teto de {NIVEL4_MAX_TENTATIVAS} tentativas atingido "
         f"para '{termo}' sem conclusão =====")
    return None


def _buscar_com_nivel(
    termo: str, categoria: str = ""
) -> tuple[pd.DataFrame, str, float]:
    """
    Busca completa, restrita aos grupos compatíveis com `categoria`.
    Retorna (resultados, nivel, score).

    Níveis:
      "nao_faturavel"    -> termo sem código próprio no SIGTAP (dicionário)
      "nivel0"           -> tradução pelo dicionário clínico->SIGTAP
      "nivel1"           -> exata, com desempate por densidade
      "nivel2"           -> parcial ponderada por IDF
      "nivel_semantico"  -> significado via embeddings, limiar alto
      "nivel3"           -> fuzzy (limiar alto)
      "nivel4"           -> ciclo agêntico de resgate (confiança baixa)
      "vazio"            -> nenhuma correspondência
    """
    tabela = _get_tabela()
    sinonimos, nao_faturavel = _carregar_dicionario()

    termo_norm = _normalizar(termo).strip()
    # Tolera pequenas corrupções de grafia introduzidas pelo LLM ao repassar
    # o termo (ver _resolver_chave_dicionario).
    termo_norm = _resolver_chave_dicionario(termo_norm, sinonimos, nao_faturavel)

    # ── Não faturável: o termo existe no prontuário mas não tem código
    # próprio no SIGTAP. Retorna vazio com nível PRÓPRIO, para o relatório
    # distinguir "não encontrado" (revisar) de "não faturável" (normal).
    # Tem precedência sobre TUDO, inclusive sobre o agente do nível 4: é
    # curadoria humana e não deve ser reaberta por um modelo.
    if termo_norm in nao_faturavel:
        _log(f"[NIVEL0] '{termo}' marcado como não faturável separadamente "
             f"({nao_faturavel[termo_norm]}).")
        return tabela.iloc[0:0], "nao_faturavel", 0.0

    # ── Nível 0: tradução pelo dicionário, buscada na TABELA INTEIRA e não
    # no recorte da categoria. O dicionário é curadoria humana e vale mais
    # que a categoria inferida pelo NER, que erra: "sondagem vesical de
    # demora" foi classificada como MATERIAL (grupo 07), mas o procedimento
    # correspondente está no grupo 03. Vários alvos significam um PAINEL.
    if termo_norm in sinonimos:
        alvos = sinonimos[termo_norm]
        _log(f"[NIVEL0] '{termo}' -> {alvos}")
        partes = []
        for alvo in alvos:
            parcial, _, _ = _buscar_niveis_texto(alvo, tabela)
            if not parcial.empty:
                partes.append(parcial.head(1))
            else:
                _log(f"[NIVEL0] AVISO: alvo '{alvo}' não resolveu no SIGTAP "
                     f"(rode validar_sinonimos.py).")
        if partes:
            return pd.concat(partes), "nivel0", 1.0

    candidatos = _filtrar_por_categoria(tabela, categoria)
    if len(candidatos) < len(tabela):
        _log(f"[SIGTAP] '{termo}' (cat={categoria}): busca restrita a "
             f"{len(candidatos)} de {len(tabela)} procedimentos.")

    resultados, nivel, score = _buscar_niveis_texto(termo_norm, candidatos)
    if nivel != "vazio":
        return resultados, nivel, score

    # ── Nível 4 — ciclo agêntico. Só chega aqui o que TODOS os níveis
    # determinísticos deixaram passar, então o custo fica contido na fração
    # de termos realmente difíceis.
    if USAR_LLM_FALLBACK and not candidatos.empty:
        try:
            resultado_agente = _fallback_llm_agente(termo, categoria, candidatos)
            if resultado_agente is not None:
                linha, tentativas = resultado_agente
                # score guarda o número de tentativas do ciclo, útil para
                # analisar depois quanto esforço o agente gastou por termo.
                return linha, "nivel4", float(tentativas)
        except Exception as e:
            _log(f"[NIVEL4] Erro inesperado no ciclo ({type(e).__name__}: {e}) "
                 f"— tratando como sem correspondência.")

    # Nada encontrado. Por padrão NÃO reabrimos a busca sem o filtro de
    # grupo: uma lacuna sinalizada é preferível a um código de grupo errado.
    if RETENTAR_SEM_FILTRO and categoria:
        _log(f"[SIGTAP] '{termo}' sem correspondência no grupo — retentando "
             f"sem filtro (confiança baixa).")
        resultados, nivel, _ = _buscar_niveis_texto(termo_norm, tabela)
        if nivel != "vazio":
            return resultados, nivel, 0.0

    _registrar_termo_nao_encontrado(termo)
    return candidatos.iloc[0:0], "vazio", 0.0


def _registrar_termo_nao_encontrado(termo: str) -> None:
    """
    Registra um termo sem correspondência num arquivo de texto (uma linha por
    termo), para revisão manual e para alimentar o dicionário do Nível 0.
    Evita duplicatas. Caminho configurável via SIGTAP_LOG_NAO_ENCONTRADOS.
    """
    caminho_log = os.getenv("SIGTAP_LOG_NAO_ENCONTRADOS", "termos_nao_encontrados.txt")
    termo_limpo = termo.strip()
    if not termo_limpo:
        return

    try:
        if os.path.exists(caminho_log):
            with open(caminho_log, encoding="utf-8") as f:
                if termo_limpo.lower() in {l.strip().lower() for l in f if l.strip()}:
                    return
    except OSError:
        pass

    try:
        with open(caminho_log, "a", encoding="utf-8") as f:
            f.write(termo_limpo + "\n")
    except OSError:
        pass


# ── Ferramentas MCP ────────────────────────────────────────────────────────

@mcp.tool()
def buscar_procedimento(termo: str, categoria: str = "") -> list[dict]:
    """
    Busca procedimentos na tabela SIGTAP pelo nome ou descrição.

    Args:
        termo: Texto a buscar (ex: 'intubacao orotraqueal', 'hemograma').
        categoria: Categoria da entidade, para restringir a busca aos grupos
            corretos do SIGTAP. Um de: PROCEDIMENTO, EXAME, MATERIAL,
            MEDICAMENTO. Vazio busca na tabela inteira.

    Returns:
        Lista de até 3 procedimentos com codigo, descricao, grupo, valores em
        reais (vl_sh, vl_sa, vl_sp, vl_total), o nível que os encontrou, o
        score e a confiança. Quando o termo é um painel (nivel0 com vários
        alvos), todos os itens vêm marcados com painel=True. Quando o termo
        não tem código próprio no SIGTAP, retorna um único marcador com
        nivel='nao_faturavel'.
    """
    t0 = time.time()
    resultados, nivel, score = _buscar_com_nivel(termo, categoria)
    confianca = _confianca(nivel, score)

    if resultados.empty:
        _log(f"[TOOL] '{termo}' (cat={categoria or '-'}) -> {nivel}, "
             f"{time.time() - t0:.2f}s")
        # Marcador explícito para que o pipeline distinga "não faturável
        # separadamente" (informação normal) de "não encontrado" (revisar).
        if nivel == "nao_faturavel":
            return [{"nivel": "nao_faturavel", "termo": termo}]
        return []

    painel = nivel == "nivel0" and len(resultados) > 1
    _log(f"[TOOL] '{termo}' (cat={categoria or '-'}) -> {nivel}, "
         f"score={score:.3f}, confianca={confianca}, painel={painel}, "
         f"{len(resultados)} resultado(s), {time.time() - t0:.2f}s")

    colunas = ["codigo", "descricao", "grupo", "vl_sh", "vl_sa", "vl_sp", "vl_total"]
    registros = resultados[colunas].head(3).to_dict("records")
    for r in registros:
        r["nivel"] = nivel
        r["score"] = round(score, 3)
        r["confianca"] = confianca
        r["painel"] = painel
        # No nível 4, o score é o número de voltas que o agente deu até
        # concluir -- registrado para análise do esforço por termo.
        if nivel == "nivel4":
            r["tentativas_agente"] = int(score)
    return registros


@mcp.tool()
def buscar_por_codigo(codigo: str) -> dict | None:
    """
    Retorna o procedimento SIGTAP pelo código exato.

    Args:
        codigo: Código SIGTAP no formato oficial (ex: '02.02.02.038-0').

    Returns:
        Dicionário com codigo, descricao, grupo e valores em reais, ou None.
    """
    tabela = _get_tabela()
    resultado = tabela[tabela["codigo"] == codigo]
    if resultado.empty:
        return None
    colunas = ["codigo", "descricao", "grupo", "vl_sh", "vl_sa", "vl_sp", "vl_total"]
    return resultado[colunas].iloc[0].to_dict()


# ── Ponto de entrada ───────────────────────────────────────────────────────

if __name__ == "__main__":
    _log("[SIGTAP] Iniciando servidor MCP...")
    # Aquecimento SÍNCRONO e COMPLETO (inclui carregar o modelo de embeddings
    # e fazer um encode de teste): nenhuma busca chega antes de tudo pronto.
    _aquecer()
    _log(f"[SIGTAP] Nível 4 (agente): "
         f"{'ATIVO' if USAR_LLM_FALLBACK else 'desativado'}, "
         f"teto de {NIVEL4_MAX_TENTATIVAS} tentativas por termo.")
    _log("[SIGTAP] Pronto, aguardando conexão via stdio...")
    mcp.run(transport="stdio")