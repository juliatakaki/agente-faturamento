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

import os
import json
import unicodedata
import pandas as pd
import psycopg2
from rapidfuzz import fuzz
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

# ── Inicialização ──────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": os.getenv("SIGTAP_DB_HOST", "localhost"),
    "port": os.getenv("SIGTAP_DB_PORT", "5432"),
    "dbname": os.getenv("SIGTAP_DB_NAME", "sigtap"),
    "user": os.getenv("SIGTAP_DB_USER", "sigtap"),
    "password": os.getenv("SIGTAP_DB_PASSWORD", "sigtap"),
}

# Modelo usado no nível 4 (fallback via LLM). Mesmo modelo já usado no
# restante do pipeline (pipeline.py), para manter consistência.
MODELO_LLM_FALLBACK = os.getenv("SIGTAP_LLM_FALLBACK_MODEL", "llama3.2")

# Query que junta procedimento + descrição longa + grupo (derivado do código).
# LEFT JOIN porque nem todo procedimento tem uma linha em tb_descricao,
# e perder a linha do procedimento so' por faltar a descricao longa
# reduziria a cobertura de busca sem necessidade.
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

QUERY_GRUPOS = """
    SELECT co_grupo, no_grupo FROM tb_grupo
"""

mcp = FastMCP("sigtap-server")

# Carrega a tabela uma única vez na inicialização
_tabela: pd.DataFrame | None = None


def _normalizar(texto: str) -> str:
    """
    Normaliza um texto para comparação:
    - converte para minúsculas
    - remove acentos (tórax → torax, intubação → intubacao)
    - remove hífens (raio-x → raio x)
    """
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace("-", " ")
    return texto


def _formatar_codigo(codigo_str: str) -> str:
    """
    Formata o código do SIGTAP no padrão oficial com pontos e hífen.
    Ex: '0202020380' -> '02.02.02.038-0'
    """
    codigo_str = str(codigo_str).strip().zfill(10)
    return (
        f"{codigo_str[0:2]}.{codigo_str[2:4]}.{codigo_str[4:6]}."
        f"{codigo_str[6:9]}-{codigo_str[9]}"
    )


def _carregar_do_postgres() -> pd.DataFrame:
    """Conecta no Postgres e monta o DataFrame combinando
    tb_procedimento + tb_descricao + tb_grupo (este último via o código
    derivado, ja' que nao ha' FK direta entre as duas primeiras tabelas)."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        procedimentos = pd.read_sql_query(QUERY_SIGTAP, conn)
        grupos = pd.read_sql_query(QUERY_GRUPOS, conn)
    finally:
        conn.close()

    procedimentos = procedimentos.merge(
        grupos,
        left_on="co_grupo_derivado",
        right_on="co_grupo",
        how="left",
    )

    return procedimentos


def _get_tabela() -> pd.DataFrame:
    global _tabela
    if _tabela is None:
        bruta = _carregar_do_postgres()

        tabela = pd.DataFrame()
        tabela["codigo_bruto"] = bruta["codigo_bruto"]
        tabela["codigo"] = tabela["codigo_bruto"].apply(_formatar_codigo)

        # Descrição usada na busca: apenas o nome curto (no_procedimento),
        # igual ao comportamento da tabela reduzida anterior. A descrição
        # longa (ds_procedimento) e' mantida na tabela como contexto extra,
        # mas NAO participa da busca textual: ela costuma ser um texto
        # narrativo extenso (protocolos clinicos completos) que pode citar
        # de passagem outros exames/procedimentos (ex: a descricao de um
        # protocolo de transplante menciona "HEMOGRAMA COMPLETO" dentro de
        # uma lista de 30+ exames do protocolo), gerando falsos positivos
        # se usada com o mesmo peso do nome curto na busca.
        tabela["descricao"] = bruta["nome_curto"]
        tabela["descricao_longa"] = bruta["descricao_longa"]

        tabela["grupo"] = bruta["no_grupo"].fillna("Não classificado")
        tabela["descricao_norm"] = tabela["descricao"].apply(_normalizar)

        # Valores faturáveis: o SIGTAP armazena em centavos (inteiros),
        # então dividimos por 100 para obter reais. Os três componentes:
        #   vl_sh -> Serviço Hospitalar
        #   vl_sa -> Serviço Ambulatorial
        #   vl_sp -> Serviço Profissional
        # O valor total do procedimento é a soma dos três.
        tabela["vl_sh"] = (bruta["vl_sh"].fillna(0).astype(float) / 100.0).round(2)
        tabela["vl_sa"] = (bruta["vl_sa"].fillna(0).astype(float) / 100.0).round(2)
        tabela["vl_sp"] = (bruta["vl_sp"].fillna(0).astype(float) / 100.0).round(2)
        tabela["vl_total"] = (tabela["vl_sh"] + tabela["vl_sa"] + tabela["vl_sp"]).round(2)

        _tabela = tabela

    return _tabela


# ── Ferramentas MCP ────────────────────────────────────────────────────────

def _buscar_com_nivel(termo: str) -> tuple[pd.DataFrame, str]:
    """
    Lógica interna de busca em níveis. Retorna os resultados (DataFrame)
    e uma string indicando qual nível resolveu a busca:
      "nivel1"  -> busca exata (todas as palavras presentes)
      "nivel2"  -> busca parcial (ao menos uma palavra presente)
      "nivel3"  -> fuzzy matching (rapidfuzz, limiar alto, alta confiança)
      "nivel4"  -> fallback via LLM (traducao semantica termo clinico -> SIGTAP)
      "vazio"   -> nenhum nível encontrou resultado

    Extraído como função separada (em vez de embutido em buscar_procedimento)
    para permitir medir, em testes, qual nível resolve cada termo sem
    alterar a assinatura nem o comportamento da ferramenta MCP pública.
    """
    tabela = _get_tabela()
    termo_norm = _normalizar(termo)

    palavras = [p for p in termo_norm.split() if len(p) > 2]
    if not palavras:
        palavras = [termo_norm]

    # Nível 1 — busca exata: todas as palavras do termo aparecem na descrição
    mascara = tabela["descricao_norm"].apply(
        lambda desc: all(p in desc for p in palavras)
    )
    resultados = tabela[mascara]
    if not resultados.empty:
        return resultados, "nivel1"

    # Nível 2 — busca parcial: ao menos uma palavra aparece na descrição
    for palavra in palavras:
        mascara_parcial = tabela["descricao_norm"].str.contains(palavra, na=False)
        resultados = tabela[mascara_parcial]
        if not resultados.empty:
            return resultados, "nivel2"

    # Nível 3 — busca por similaridade (rapidfuzz): cobre erros de digitação
    # e variações que a busca por substring não captura (ex: "sor" vs "soro").
    USAR_FUZZY = True
    SCORE_MINIMO = 87
    if USAR_FUZZY:
        scores = tabela["descricao_norm"].apply(
            lambda desc: fuzz.partial_ratio(termo_norm, desc)
        )
        candidatos = tabela[scores >= SCORE_MINIMO].copy()
        if not candidatos.empty:
            candidatos["_score"] = scores[scores >= SCORE_MINIMO]
            resultados = candidatos.sort_values("_score", ascending=False)
            return resultados, "nivel3"

    # Nível 4 — fallback via LLM: cobre casos em que o termo clínico (ex:
    # "coagulograma") não tem correspondência textual direta com o nome
    # administrativo do SIGTAP (ex: "DETERMINAÇÃO DE TEMPO DE COAGULAÇÃO").
    #
    # DESATIVADO nesta versão (USAR_LLM_FALLBACK = False). Em testes com o
    # modelo local llama3.2, o nível 4 mostrou julgamento clínico instável:
    # ora aceitava correspondências erradas (ex: "reanimação cardiopulmonar"
    # -> "prova de função pulmonar"), ora rejeitava correspondências corretas.
    # A reativação está planejada como trabalho futuro, com modelos mais
    # capazes (ex: APIs pagas), bastando voltar a flag para True. O código
    # das duas etapas (_etapa_escolha / _etapa_verificacao) permanece pronto.
    USAR_LLM_FALLBACK = False
    if USAR_LLM_FALLBACK:
        candidato_ou_none = _fallback_llm(termo, termo_norm, tabela)
        if candidato_ou_none is not None:
            return candidato_ou_none, "nivel4"

    # Nenhum nível encontrou correspondência: registra o termo para
    # verificação manual posterior (sem duplicatas) e retorna vazio.
    _registrar_termo_nao_encontrado(termo)
    return tabela.iloc[0:0], "vazio"  # DataFrame vazio com as mesmas colunas


def _registrar_termo_nao_encontrado(termo: str) -> None:
    """
    Registra um termo que não teve correspondência em nenhum nível, num
    arquivo de log de texto simples (uma linha por termo), para revisão
    manual posterior. Evita duplicatas: se o termo já foi registrado antes
    (comparação case-insensitive, ignorando espaços nas pontas), não
    registra de novo.

    O caminho do arquivo pode ser configurado via a variável de ambiente
    SIGTAP_LOG_NAO_ENCONTRADOS; o padrão é "termos_nao_encontrados.txt"
    no diretório de trabalho atual.
    """
    caminho_log = os.getenv("SIGTAP_LOG_NAO_ENCONTRADOS", "termos_nao_encontrados.txt")
    termo_limpo = termo.strip()
    if not termo_limpo:
        return

    chave = termo_limpo.lower()

    # Lê os termos já registrados (se o arquivo existir) para evitar duplicatas.
    try:
        if os.path.exists(caminho_log):
            with open(caminho_log, "r", encoding="utf-8") as f:
                ja_registrados = {linha.strip().lower() for linha in f if linha.strip()}
            if chave in ja_registrados:
                return
    except OSError:
        # Se não for possível ler o log, segue para tentar gravar mesmo assim;
        # no pior caso, gera uma duplicata, o que é preferível a perder o registro.
        pass

    try:
        with open(caminho_log, "a", encoding="utf-8") as f:
            f.write(termo_limpo + "\n")
    except OSError:
        # Falha ao gravar o log nao deve interromper a busca; apenas ignora.
        pass


def _etapa_escolha(termo: str, candidatos: pd.DataFrame) -> int | None:
    """
    Etapa 1 do nível 4: pede ao LLM para escolher o índice do melhor
    candidato da lista (ou null). Retorna o índice (int) ou None.
    Aqui NÃO se pede confiança -- a validação fica a cargo da etapa 2,
    que avalia o candidato escolhido de forma isolada.
    """
    lista_para_llm = "\n".join(
        f"{i}: {row['descricao']}" for i, row in candidatos.iterrows()
    )

    prompt = f"""Você é um especialista em faturamento hospitalar brasileiro (tabela SIGTAP).

Um termo clínico foi extraído de um prontuário: "{termo}"

Abaixo está uma lista de procedimentos SIGTAP candidatos (numerados). Escolha
o ÍNDICE do procedimento que melhor corresponde clinicamente ao termo, ou null
se nenhum corresponder.

Responda APENAS com um JSON no formato exato: {{"indice": N ou null}}
- NUNCA invente um índice fora da lista.
- NUNCA inclua texto fora do JSON.

Candidatos:
{lista_para_llm}
"""

    llm = ChatOllama(model=MODELO_LLM_FALLBACK, temperature=0)
    resposta = llm.invoke(prompt)
    conteudo = resposta.content.strip()

    if conteudo.startswith("```"):
        conteudo = conteudo.strip("`")
        conteudo = conteudo.replace("json", "", 1).strip()

    dados = json.loads(conteudo)
    indice = dados.get("indice")

    if not isinstance(indice, int) or indice < 0 or indice >= len(candidatos):
        return None
    return indice


def _etapa_verificacao(termo: str, descricao_candidato: str) -> bool:
    """
    Etapa 2 do nível 4: verifica, de forma ISOLADA e binária, se o
    candidato escolhido na etapa 1 é de fato o mesmo ato clínico que o
    termo buscado. Tirar o candidato da lista (onde competia com dezenas
    de outros) e julgá-lo sozinho tende a dar respostas mais precisas em
    modelos pequenos do que pedir auto-avaliação de confiança.

    Retorna True somente se o LLM responder SIM de forma inequívoca.
    """
    prompt = f"""Você é um auditor de faturamento hospitalar (tabela SIGTAP).

Termo clínico extraído de um prontuário: "{termo}"
Procedimento SIGTAP candidato: "{descricao_candidato}"

Pergunta: esses dois se referem ao MESMO ato clínico, de modo que um auditor
aceitaria este procedimento SIGTAP como correspondente a este termo?

Considere que compartilhar uma palavra ou ser da mesma área do corpo NÃO basta
-- precisa ser efetivamente o mesmo procedimento/exame. Na dúvida, responda NÃO.

Responda APENAS com uma única palavra: SIM ou NÃO."""

    llm = ChatOllama(model=MODELO_LLM_FALLBACK, temperature=0)
    resposta = llm.invoke(prompt)
    conteudo = resposta.content.strip().upper()

    # Normaliza para detectar SIM de forma robusta (remove acentos/pontuação),
    # exigindo que a resposta comece com "SIM" para evitar aceitar textos como
    # "NÃO, isso não é o mesmo" que por acaso contenham "sim" em "assim" etc.
    conteudo_norm = _normalizar(conteudo).strip().strip(".!,").upper()
    return conteudo_norm.startswith("SIM")


def _fallback_llm(termo: str, termo_norm: str, tabela: pd.DataFrame) -> pd.DataFrame | None:
    """
    Nível 4: busca por correspondência semântica via LLM, em duas etapas:
      Etapa 1 (_etapa_escolha):     o LLM escolhe o melhor candidato da lista.
      Etapa 2 (_etapa_verificacao): o candidato escolhido é verificado de
                                    forma isolada (SIM/NÃO).
    Só retorna um resultado se a etapa 2 confirmar. Caso contrário, None.

    Os candidatos são pré-filtrados por fuzzy frouxo (limiar baixo) só para
    reduzir a tabela (~5000 linhas) a poucas dezenas, sem aceitar nada
    automaticamente -- a decisão final é sempre do LLM nas duas etapas.
    """
    SCORE_MINIMO_CANDIDATOS = 50
    MAX_CANDIDATOS = 30

    scores = tabela["descricao_norm"].apply(
        lambda desc: fuzz.token_set_ratio(termo_norm, desc)
    )
    candidatos = tabela[scores >= SCORE_MINIMO_CANDIDATOS].copy()
    if candidatos.empty:
        return None

    candidatos["_score"] = scores[scores >= SCORE_MINIMO_CANDIDATOS]
    candidatos = candidatos.sort_values("_score", ascending=False).head(MAX_CANDIDATOS)
    candidatos = candidatos.reset_index(drop=True)

    try:
        # Etapa 1: escolha
        indice = _etapa_escolha(termo, candidatos)
        if indice is None:
            return None

        descricao_escolhida = candidatos.iloc[indice]["descricao"]

        # Etapa 2: verificação isolada do candidato escolhido
        if not _etapa_verificacao(termo, descricao_escolhida):
            return None

        return candidatos.iloc[[indice]]

    except Exception:
        # Qualquer falha (Ollama fora do ar, JSON malformado, etc) deve
        # degradar graciosamente para "sem resultado", nao quebrar a busca.
        return None


@mcp.tool()
def buscar_procedimento(termo: str) -> list[dict]:
    """
    Busca procedimentos na tabela SIGTAP pelo nome ou descrição.

    Args:
        termo: Texto a buscar (ex: 'intubacao orotraqueal', 'hemograma').

    Returns:
        Lista de até 3 procedimentos, cada um com codigo, descricao, grupo,
        os valores faturáveis em reais (vl_sh, vl_sa, vl_sp, vl_total) e o
        nível da busca que o encontrou (nivel1 a nivel3).
    """
    resultados, nivel = _buscar_com_nivel(termo)
    colunas = ["codigo", "descricao", "grupo", "vl_sh", "vl_sa", "vl_sp", "vl_total"]
    registros = resultados[colunas].head(3).to_dict("records")
    # anexa o nível da busca a cada registro, para que o pipeline e o
    # relatório possam exibir em qual camada o procedimento foi encontrado.
    for r in registros:
        r["nivel"] = nivel
    return registros


@mcp.tool()
def buscar_por_codigo(codigo: str) -> dict | None:
    """
    Retorna o procedimento SIGTAP pelo código exato.

    Args:
        codigo: Código SIGTAP no formato oficial (ex: '02.02.02.038-0').

    Returns:
        Dicionário com codigo, descricao, grupo e os valores faturáveis em
        reais (vl_sh, vl_sa, vl_sp, vl_total), ou None se não encontrado.
    """
    tabela = _get_tabela()
    resultado = tabela[tabela["codigo"] == codigo]
    if resultado.empty:
        return None
    colunas = ["codigo", "descricao", "grupo", "vl_sh", "vl_sa", "vl_sp", "vl_total"]
    return resultado[colunas].iloc[0].to_dict()


# ── Ponto de entrada ───────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")