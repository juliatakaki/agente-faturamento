"""
Pipeline principal do agente de IA.
Fluxo: NER → consulta MCP/SIGTAP → geração do relatório.
Orquestrado com LangGraph.

ONDE ESTÁ O AGENTE NESTA ARQUITETURA
------------------------------------
A etapa de correspondência (percorrer as entidades e consultar o SIGTAP) é
DETERMINÍSTICA, feita por um laço em Python. A autonomia do modelo está
concentrada no Nível 4 do servidor MCP, onde há decisão real a tomar:
propor um termo alternativo, observar o que a busca devolveu e decidir
entre aceitar, tentar de novo ou declarar que não existe código.

Essa divisão veio de evidência, não de preferência. Ver o comentário de
_consultar_sigtap() para o histórico.
"""

import os
import json
import re
import sys
import asyncio
from contextlib import AsyncExitStack
from datetime import datetime
from typing import TypedDict

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ner.extractor import construir_ner, extrair_entidades

load_dotenv()

# ── Timeouts ─────────────────────────────────────────────────────────────
# Cada await que depende de algo externo tem timeout explícito. Sem isso,
# qualquer travamento externo trava o pipeline em silêncio; com ele, o
# pipeline falha dizendo ONDE e DEPOIS DE QUANTO TEMPO travou.
TIMEOUT_MCP_TOOLS = int(os.getenv("TIMEOUT_MCP_TOOLS_SEGUNDOS", "180"))
TIMEOUT_LLM_CHAMADA = int(os.getenv("TIMEOUT_LLM_SEGUNDOS", "90"))
TIMEOUT_SIGTAP_TOOL = int(os.getenv("TIMEOUT_SIGTAP_TOOL_SEGUNDOS", "180"))

CATEGORIAS_BUSCAVEIS = {"PROCEDIMENTO", "EXAME", "MATERIAL", "MEDICAMENTO"}

# Permite reproduzir o comportamento antigo (orquestração pelo LLM) para
# fins de comparação no TCC 2. Ver _consultar_sigtap_via_llm().
ORQUESTRACAO_POR_LLM = os.getenv("ORQUESTRACAO_POR_LLM", "false").lower() == "true"


# ── Tipos ──────────────────────────────────────────────────────────────────

class EstadoPipeline(TypedDict):
    prontuario_id: str
    texto: str
    entidades_brutas: list[dict]       # saída do NER
    entidades_refinadas: list[dict]    # saída do LLM (normalização)
    resultados_sigtap: list[dict]      # saída da consulta MCP
    termos_nao_encontrados: list[str]  # buscados sem correspondência (REVISAR)
    termos_nao_faturaveis: list[str]   # sem código próprio no SIGTAP (normal)
    entidades_descartadas: list[str]   # fora das categorias faturáveis
    relatorio: dict                    # relatório final


# ── Configuração do subprocesso MCP ────────────────────────────────────────
#
# Usa sys.executable (caminho do Python em uso) em vez de "python3" fixo,
# pois "python3" não existe no Windows -- isso causava "Connection closed"
# ao iniciar o subprocesso do servidor MCP.
#
# AMBIENTE EXPLÍCITO: as variáveis que definem o modelo (PROVEDOR_LLM,
# PROVEDOR_API, MODELO_API, MODELO_LOCAL) são montadas na hora de abrir a
# sessão e passadas ao subprocesso.
#
# POR QUE ISSO É NECESSÁRIO: o menu do main.py escreve a escolha em
# os.environ do processo PAI. Variável de ambiente é copiada para o filho no
# momento em que ele nasce -- e o servidor MCP lê essas variáveis para criar
# o modelo do agente do nível 4. Sem passar explicitamente, o subprocesso
# poderia herdar um ambiente diferente do escolhido no menu: em agosto/2026
# isso fez o nível 4 rodar com Groq (do .env) enquanto o resto do pipeline
# rodava com Gemini (do menu) -- e como o modelo Groq havia saído do
# catálogo, os 11 ciclos do agente falharam com 404 sem que nada aparecesse
# no terminal.

_VARS_MODELO = (
    "PROVEDOR_LLM", "PROVEDOR_API", "MODELO_API", "MODELO_LOCAL",
    "OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY",
    "USAR_LLM_FALLBACK", "USAR_BUSCA_SEMANTICA",
)


def _montar_config_mcp() -> dict:
    """
    Monta a configuração do servidor MCP com o ambiente atual do processo,
    resolvido no momento da chamada (e não no import), para que a escolha
    feita no menu do main.py chegue ao subprocesso.
    """
    ambiente = dict(os.environ)
    for var in _VARS_MODELO:
        valor = os.environ.get(var)
        if valor is not None:
            ambiente[var] = valor

    return {
        "sigtap": {
            "command": sys.executable,
            "args": [
                os.path.join(os.path.dirname(__file__), "../mcp/sigtap_server.py")
            ],
            "transport": "stdio",
            "env": ambiente,
        }
    }


def _descrever_modelo_atual() -> str:
    """Descrição curta do modelo configurado, para conferência nos logs."""
    if os.getenv("PROVEDOR_LLM", "local").strip().lower() == "api":
        return (f"api/{os.getenv('PROVEDOR_API', '?')} — "
                f"{os.getenv('MODELO_API', '?')}")
    return f"local/ollama — {os.getenv('MODELO_LOCAL', 'llama3.2')}"


# ── Sessão MCP persistente ─────────────────────────────────────────────────
#
# PROBLEMA QUE ISTO RESOLVE: com client.get_tools() sem manter uma sessão
# aberta, o adaptador abre e fecha uma sessão stdio A CADA chamada de
# ferramenta -- um subprocesso NOVO do sigtap_server.py por busca. Como o
# servidor carrega a tabela do Postgres (~10s) e o modelo de embeddings
# (~20s) na inicialização, esse custo era pago de novo em toda busca.
#
# SOLUÇÃO: abrir UMA sessão e mantê-la viva durante todo o lote.
#
# IMPORTANTE: abrir e fechar na MESMA task. O LangGraph executa cada nó do
# grafo numa task própria; abrir a sessão dentro de um nó e fechá-la em
# processar_lote faz o anyio acusar "Attempted to exit cancel scope in a
# different task than it was entered in".

_pilha_mcp: AsyncExitStack | None = None
_ferramentas_mcp: list | None = None


async def iniciar_sessao_mcp() -> list:
    """
    Abre a sessão MCP e carrega as ferramentas. Chamar na task principal,
    antes de processar os prontuários. Idempotente.
    """
    global _pilha_mcp, _ferramentas_mcp

    if _ferramentas_mcp is not None:
        return _ferramentas_mcp

    print(f"[MCP] Iniciando servidor SIGTAP -- carrega a tabela uma vez e "
          f"fica de pé durante todo o lote (timeout {TIMEOUT_MCP_TOOLS}s).")
    print(f"[MCP] Modelo repassado ao subprocesso: {_descrever_modelo_atual()}")
    t0 = datetime.now()

    _pilha_mcp = AsyncExitStack()
    client = MultiServerMCPClient(_montar_config_mcp())
    try:
        sessao = await asyncio.wait_for(
            _pilha_mcp.enter_async_context(client.session("sigtap")),
            timeout=TIMEOUT_MCP_TOOLS,
        )
        _ferramentas_mcp = await asyncio.wait_for(
            load_mcp_tools(sessao), timeout=TIMEOUT_MCP_TOOLS
        )
    except asyncio.TimeoutError:
        await fechar_sessao_mcp()
        raise RuntimeError(
            f"Timeout de {TIMEOUT_MCP_TOOLS}s iniciando o MCP do SIGTAP. "
            "Causas comuns: Postgres fora do ar, ou primeira carga do modelo "
            "de embeddings com disco frio. Rode "
            "'python src/mcp/sigtap_server.py' direto para ver o erro real, "
            "e confira sigtap_server.log na pasta do servidor."
        )

    print(f"[MCP] Pronto em {(datetime.now() - t0).total_seconds():.1f}s, "
          f"{len(_ferramentas_mcp)} ferramenta(s).")
    return _ferramentas_mcp


async def fechar_sessao_mcp() -> None:
    """Fecha a sessão e encerra o subprocesso. Chamar na MESMA task que abriu."""
    global _pilha_mcp, _ferramentas_mcp
    if _pilha_mcp is not None:
        try:
            await _pilha_mcp.aclose()
        except Exception as e:
            print(f"[MCP] Aviso ao fechar a sessão: {e}")
    _pilha_mcp = None
    _ferramentas_mcp = None


def obter_ferramentas_mcp() -> list:
    """Devolve as ferramentas já carregadas (a sessão precisa ter sido iniciada)."""
    if _ferramentas_mcp is None:
        raise RuntimeError(
            "Sessão MCP não iniciada. Chame 'await iniciar_sessao_mcp()' "
            "antes de processar prontuários."
        )
    return _ferramentas_mcp


# ── Seleção do modelo de linguagem ─────────────────────────────────────────
#
# O agente pode rodar com dois tipos de "cérebro":
#   - local:  modelo na própria máquina via Ollama. Não envia dados p/ fora.
#   - api:    provedor externo (OpenAI, Google, Anthropic, Groq). Melhor
#             desempenho, porém envia os dados para fora.
#
# IMPORTANTE: o modo "api" envia o conteúdo processado a servidores externos.
# Usar apenas com dados sintéticos ou conforme o protocolo de ética aprovado.

# O LLM é criado UMA vez e reaproveitado entre prontuários.
_llm_cache = None


def criar_llm():
    """
    Cria (ou devolve, se já criado) o modelo de linguagem conforme o ambiente.

    Variáveis lidas:
      PROVEDOR_LLM  -> "local" (padrão) ou "api"
      MODELO_LOCAL  -> nome do modelo no Ollama (padrão: "llama3.2")
      MODELO_API    -> nome do modelo do provedor
      PROVEDOR_API  -> "openai" | "google" | "anthropic" | "groq"
    """
    global _llm_cache
    if _llm_cache is not None:
        return _llm_cache

    provedor = os.getenv("PROVEDOR_LLM", "local").strip().lower()

    if provedor == "local":
        modelo = os.getenv("MODELO_LOCAL", "llama3.2")
        print(f"  [LLM] Usando modelo LOCAL via Ollama: {modelo}")
        _llm_cache = ChatOllama(model=modelo, temperature=0)
        return _llm_cache

    if provedor == "api":
        modelo = os.getenv("MODELO_API", "")
        provedor_api = os.getenv("PROVEDOR_API", "").strip().lower()
        if not modelo or not provedor_api:
            raise ValueError(
                "Para usar PROVEDOR_LLM=api, defina MODELO_API e PROVEDOR_API "
                "no .env. Ex: PROVEDOR_API=groq, MODELO_API=openai/gpt-oss-120b."
            )
        print(f"  [LLM] Usando modelo via API ({provedor_api}): {modelo}")
        _llm_cache = _criar_llm_api(provedor_api, modelo)
        return _llm_cache

    raise ValueError(f"PROVEDOR_LLM inválido: '{provedor}'. Use 'local' ou 'api'.")


def _criar_llm_api(provedor_api: str, modelo: str):
    """
    Instancia o cliente do provedor escolhido. Imports tardios para que o
    agente rode em modo local sem ter todos os pacotes de API instalados.
    A chave é lida da variável padrão de cada provedor.
    """
    if provedor_api == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=modelo, temperature=0)

    if provedor_api == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=modelo, temperature=0)

    if provedor_api == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=modelo, temperature=0)

    if provedor_api == "groq":
        # A Groq expõe API compatível com a da OpenAI, então reutilizamos o
        # ChatOpenAI apontando para o endpoint da Groq com a chave dela.
        from langchain_openai import ChatOpenAI
        chave_groq = os.getenv("GROQ_API_KEY", "")
        if not chave_groq:
            raise ValueError("PROVEDOR_API=groq requer GROQ_API_KEY no .env.")
        return ChatOpenAI(
            model=modelo, temperature=0, api_key=chave_groq,
            base_url="https://api.groq.com/openai/v1",
        )

    raise ValueError(
        f"PROVEDOR_API não suportado: '{provedor_api}'. "
        "Use 'openai', 'google', 'anthropic' ou 'groq'."
    )


NLP = construir_ner()


# ── Nós do grafo ───────────────────────────────────────────────────────────

def _extrair_json_da_resposta(texto: str):
    """
    Extrai JSON de uma resposta de LLM, tolerando blocos markdown
    (```json ... ```) mesmo quando instruído a não usá-los.
    """
    bruto = texto.strip()
    if bruto.startswith("```"):
        bruto = re.sub(r"^```[a-zA-Z]*\n?", "", bruto)
        bruto = re.sub(r"\n?```$", "", bruto)
    return json.loads(bruto.strip())


EXTRATOR_LLM_SISTEMA = """Você é um assistente especializado em análise de prontuários clínicos.
Sua tarefa é ler o texto de um prontuário eletrônico e identificar todos os
itens passíveis de faturamento hospitalar mencionados nele.

Cada item deve ser classificado em UMA das categorias:
- PROCEDIMENTO: procedimentos clínicos e cirúrgicos realizados
  (ex: "intubação orotraqueal", "laparotomia exploradora")
- EXAME: exames laboratoriais ou de imagem realizados
  (ex: "hemograma completo", "raio-x de tórax")
- MATERIAL: materiais e insumos utilizados
  (ex: "cateter venoso central", "sonda vesical")
- MEDICAMENTO: medicamentos administrados
  (ex: "midazolam", "piperacilina-tazobactam")

REGRAS IMPORTANTES:
- Extraia o texto EXATAMENTE como aparece no prontuário, sem traduzir,
  reformular, resumir ou corrigir a grafia.
- Não invente itens que não estão explicitamente mencionados no texto.
- Não inclua dados administrativos, sinais vitais isolados ou comentários
  gerais que não sejam procedimentos, exames, materiais ou medicamentos.
- Responda APENAS com um array JSON, sem nenhum texto antes ou depois,
  sem blocos de código markdown. Formato exato:
  [{"texto": "termo exatamente como no prontuário", "categoria": "PROCEDIMENTO"}, ...]
- Se nenhum item for identificado, responda com um array vazio: []
"""


async def extrair_entidades_llm(texto_prontuario: str) -> list[dict]:
    """
    Extrai entidades clínicas faturáveis direto do texto bruto, via LLM, em
    vez do NER por regras. Retorna no MESMO formato (texto/categoria).

    É AQUI, e não na orquestração, que faz sentido comparar modelos: ler um
    texto narrativo e decidir o que é item faturável é trabalho cognitivo
    real, com espaço amplo para os modelos divergirem.
    """
    llm = criar_llm()
    mensagens = [
        SystemMessage(content=EXTRATOR_LLM_SISTEMA),
        HumanMessage(content=f"Texto do prontuário:\n\n{texto_prontuario}"),
    ]

    try:
        resposta = await asyncio.wait_for(
            llm.ainvoke(mensagens), timeout=TIMEOUT_LLM_CHAMADA
        )
    except asyncio.TimeoutError:
        print(f"  [EXTRATOR-LLM] TIMEOUT ({TIMEOUT_LLM_CHAMADA}s). "
              f"Verifique a chave de API e a rede.")
        return []

    try:
        entidades = _extrair_json_da_resposta(resposta.content)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [EXTRATOR-LLM] AVISO: resposta não interpretável como JSON ({e}).")
        return []

    if not isinstance(entidades, list):
        print("  [EXTRATOR-LLM] AVISO: resposta não é uma lista. Ignorada.")
        return []

    validas = []
    for e in entidades:
        if not isinstance(e, dict):
            continue
        texto = str(e.get("texto", "")).strip()
        categoria = str(e.get("categoria", "")).strip().upper()
        if texto and categoria in CATEGORIAS_BUSCAVEIS:
            validas.append({"texto": texto, "categoria": categoria})
    return validas


async def no_ner(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Extrai entidades clínicas do prontuário. O método é escolhido por
    EXTRATOR_ATIVO:
      "regras" (padrão) -> NER por regras (spaCy EntityRuler).
      "llm"              -> extração via LLM.
    """
    print(f"  [NER] Processando {estado['prontuario_id']}...")
    extrator = os.getenv("EXTRATOR_ATIVO", "regras").strip().lower()

    if extrator == "regras":
        entidades = extrair_entidades(estado["texto"], NLP)
    elif extrator == "llm":
        entidades = await extrair_entidades_llm(estado["texto"])
    else:
        raise ValueError(f"EXTRATOR_ATIVO inválido: '{extrator}'. Use 'regras' ou 'llm'.")

    print(f"  [NER] ({extrator}) {len(entidades)} entidades extraídas.")
    return {**estado, "entidades_brutas": entidades}


def _limpar_texto(texto: str) -> str:
    """
    Corrige texto com sequências unicode escapadas literalmente (ex: a string
    contém os 6 caracteres '\\u00e3' em vez do caractere 'ã').
    """
    if not isinstance(texto, str):
        return texto
    if "\\u" in texto:
        try:
            return texto.encode("latin-1", "backslashreplace").decode("unicode_escape")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return texto
    return texto


def _expandir_termos(termo_bruto: str) -> list[str]:
    """
    Devolve os termos individuais do argumento que o LLM passou, tratando o
    caso em que o modelo agrupa vários termos num único argumento
    (ex: "[laparotomia, drenagem de abscesso, curativo]").

    Usado apenas no modo ORQUESTRACAO_POR_LLM; o laço determinístico usa o
    texto da entidade direto, sem essa ambiguidade.
    """
    if not isinstance(termo_bruto, str):
        return []

    texto = termo_bruto.strip()
    if not texto:
        return []

    if texto.startswith("[") and texto.endswith("]"):
        texto = texto[1:-1].strip()

    partes = [p.strip() for p in texto.split(",")] if "," in texto else [texto]

    vistos = set()
    termos = []
    for p in partes:
        limpo = _limpar_texto(p.strip().strip("[]").strip())
        if limpo and limpo.lower() not in vistos:
            vistos.add(limpo.lower())
            termos.append(limpo)
    return termos


def _rotulo_nivel_log(nivel: str) -> str:
    """Converte o código do nível no rótulo usado no log."""
    return {
        "nivel0": "Nível 0 - Dicionário",
        "nivel1": "Nível 1 - Exata",
        "nivel2": "Nível 2 - Parcial",
        "nivel_semantico": "Nível Semântico",
        "nivel3": "Nível 3 - Similaridade",
        "nivel4": "Nível 4 - Agente",
    }.get(nivel, nivel or "Nível ?")


def _normalizar_resultado_mcp(resultado_busca) -> list[dict]:
    """Normaliza a resposta da ferramenta MCP para uma lista de dicionários."""
    if not resultado_busca:
        return []

    itens = resultado_busca if isinstance(resultado_busca, list) else [resultado_busca]

    saida = []
    for item in itens:
        if isinstance(item, dict) and "text" in item and "codigo" not in item:
            texto = item.get("text", "")
            if isinstance(texto, str) and texto.lstrip().startswith("{"):
                saida.extend(_tentar_json(texto))
            continue

        if isinstance(item, dict) and ("codigo" in item or "nivel" in item):
            saida.append(item)
            continue

        if isinstance(item, str):
            saida.extend(_tentar_json(item))
            continue

        texto_attr = getattr(item, "text", None)
        if isinstance(texto_attr, str) and texto_attr.lstrip().startswith("{"):
            saida.extend(_tentar_json(texto_attr))

    return saida


def _tentar_json(texto: str) -> list[dict]:
    """Desserializa uma string JSON em lista de dicts. Retorna [] se falhar."""
    try:
        dados = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(dados, dict):
        return [dados]
    if isinstance(dados, list):
        return [d for d in dados if isinstance(d, dict)]
    return []


# ══════════════════════════════════════════════════════════════════════════
# CONSULTA AO SIGTAP — laço determinístico
# ══════════════════════════════════════════════════════════════════════════
#
# POR QUE UM LAÇO EM PYTHON, E NÃO O LLM ORQUESTRANDO
# ----------------------------------------------------
# Até agosto/2026 esta etapa era conduzida pelo LLM: o modelo recebia a lista
# de entidades e decidia quais chamadas de ferramenta fazer. Os testes
# mostraram que essa decisão não é dele para tomar -- e que o resultado
# depende inteiramente de qual modelo está por trás:
#
#   modelo                 chamadas para 10 entidades
#   ---------------------  --------------------------
#   llama-3.3-70b          10   (emite chamadas em paralelo)
#   gemini-3.5-flash       10   (idem)
#   openai/gpt-oss-120b     1   (tool calling sequencial)
#   qwen/qwen3.6-27b        1   (idem)
#
# Mesmo prompt, mesma ferramenta, mesmo pipeline. Modelos de tool calling
# sequencial emitem UMA chamada, esperam o resultado e só então decidem a
# próxima -- e como o código coletava as tool_calls de uma única resposta,
# 9 de 10 entidades nunca eram buscadas. O pipeline dependia, sem saber, do
# comportamento paralelo de dois modelos específicos.
#
# Havia outros sintomas do mesmo problema: o llama-3.3-70b chegou a fazer
# 7 chamadas para 10 entidades, e corrompia a grafia dos termos ao repassá-
# los ('intubãão', 'oxigânio', 'volémica'), a ponto de ser preciso escrever
# um casamento por similaridade só para consertar isso.
#
# Percorrer uma lista não é uma decisão: é uma iteração. Com o laço, são
# sempre N chamadas para N entidades, em qualquer modelo, sem custo de API
# nesta etapa e sem corrupção de termo.
#
# ISSO NÃO REMOVE O AGENTE. A autonomia do modelo está no Nível 4 do
# servidor MCP, onde existe decisão real: propor um termo alternativo,
# observar o que a busca devolveu e decidir entre aceitar, tentar de novo ou
# declarar que não há código. Lá o número de passos varia por termo e não é
# escrito de antemão -- que é o que caracteriza um agente. Aqui, só se
# percorre uma lista.
#
# Como efeito colateral, o experimento de comparação entre modelos fica mais
# limpo: com a correspondência determinística, a diferença entre modelos
# passa a medir extração e ciclo agêntico, e não estilo de tool calling.
#
# O comportamento antigo continua disponível com ORQUESTRACAO_POR_LLM=true,
# para reproduzir a comparação no TCC 2.


async def _buscar_um_termo(
    ferramenta_busca, termo: str, categoria: str
) -> tuple[list[dict], float]:
    """
    Executa uma busca no SIGTAP e devolve (correspondências, duração).
    Timeout vira lista vazia -- o termo entra como pendência de revisão.
    """
    t0 = datetime.now()
    try:
        resultado = await asyncio.wait_for(
            ferramenta_busca.ainvoke({"termo": termo, "categoria": categoria}),
            timeout=TIMEOUT_SIGTAP_TOOL,
        )
    except asyncio.TimeoutError:
        print(f"    [SIGTAP] TIMEOUT ({TIMEOUT_SIGTAP_TOOL}s) em '{termo}' "
              f"-- confira sigtap_server.log.")
        return [], (datetime.now() - t0).total_seconds()

    return (
        _normalizar_resultado_mcp(resultado),
        (datetime.now() - t0).total_seconds(),
    )


def _registrar_resultado(
    termo: str,
    categoria: str,
    correspondencias: list[dict],
    duracao: float,
    resultados: list[dict],
    nao_encontrados: list[str],
    nao_faturaveis: list[str],
) -> None:
    """
    Classifica o resultado de uma busca em um dos três desfechos e o acumula
    nas listas correspondentes. Compartilhado pelos dois modos de consulta.
    """
    # ── Desfecho 1: termo sem código próprio no SIGTAP. Não é falha da
    # busca -- é característica do SIGTAP (medicação de uso hospitalar
    # embutida na diária, insumo descartável fora do rol de OPME, ato
    # incluído em outro procedimento). Vai para uma lista PRÓPRIA, separada
    # dos "não encontrados", porque o significado para quem confere é
    # oposto: um é informação normal, o outro é pendência de revisão.
    if correspondencias and correspondencias[0].get("nivel") == "nao_faturavel":
        print(f"    [Não faturável] '{termo}' ({categoria or 'sem categoria'}) "
              f"— sem código próprio no SIGTAP")
        if termo and termo not in nao_faturaveis:
            nao_faturaveis.append(termo)
        return

    # ── Desfecho 2: nenhuma correspondência -> pendência de revisão.
    if not correspondencias:
        print(f"    [Sem resultado] '{termo}' "
              f"({categoria or 'sem categoria'}, {duracao:.1f}s)")
        if termo and termo not in nao_encontrados:
            nao_encontrados.append(termo)
        return

    # ── Desfecho 3: correspondência encontrada.
    # PAINEL: quando o termo clínico corresponde a vários códigos faturáveis
    # (ex: "coagulograma" = TP + TTPA), TODOS entram no faturamento -- foram
    # exames distintos efetivamente realizados. Fora do painel, considera-se
    # apenas o primeiro candidato: os demais são alternativas que NÃO foram
    # necessariamente realizadas, e somá-las inflaria o valor.
    melhor = correspondencias[0]
    if melhor.get("painel"):
        selecionadas = correspondencias
        alternativas = []
    else:
        selecionadas = [melhor]
        alternativas = correspondencias[1:]

    rotulo = _rotulo_nivel_log(melhor.get("nivel", ""))
    for c in selecionadas:
        extra = ""
        if c.get("nivel") == "nivel4":
            extra = f" [{c.get('tentativas_agente', '?')} tentativa(s) do agente]"
        print(f"    [{rotulo}] [{c.get('confianca', '?')}] '{termo}' "
              f"({categoria or 'sem categoria'}) -> "
              f"{c.get('descricao', '')} ({c.get('codigo', '')}) "
              f"em {duracao:.1f}s{extra}")

    resultados.append({
        "termo_buscado": termo,
        "categoria": categoria,
        "correspondencias": selecionadas,
        "alternativas": alternativas,
        "painel": bool(melhor.get("painel")),
    })


async def _consultar_sigtap(
    entidades: list[dict], ferramenta_busca
) -> tuple[list[dict], list[str], list[str]]:
    """
    Laço determinístico: uma busca por entidade, na ordem em que o NER as
    extraiu. Devolve (resultados, nao_encontrados, nao_faturaveis).

    A categoria vem direto da entidade (fonte determinística do NER), sem
    passar pelo LLM -- eliminando também a chance de o modelo trocá-la.
    """
    resultados: list[dict] = []
    nao_encontrados: list[str] = []
    nao_faturaveis: list[str] = []

    for entidade in entidades:
        termo = _limpar_texto(str(entidade.get("texto", "")).strip())
        if not termo:
            continue
        categoria = str(entidade.get("categoria", "")).strip().upper()

        correspondencias, duracao = await _buscar_um_termo(
            ferramenta_busca, termo, categoria
        )
        _registrar_resultado(
            termo, categoria, correspondencias, duracao,
            resultados, nao_encontrados, nao_faturaveis,
        )

    return resultados, nao_encontrados, nao_faturaveis


async def _consultar_sigtap_via_llm(
    entidades: list[dict], ferramentas: list, ferramenta_busca
) -> tuple[list[dict], list[str], list[str]]:
    """
    Modo alternativo (ORQUESTRACAO_POR_LLM=true): o LLM decide quais buscas
    fazer, como era antes de agosto/2026.

    Mantido para reproduzir a comparação no TCC 2 -- é o braço experimental
    que mostra a variação entre modelos na etapa de correspondência. NÃO é
    o modo recomendado: modelos de tool calling sequencial emitem uma única
    chamada e deixam a maior parte das entidades sem buscar.
    """
    llm = criar_llm()
    llm_com_ferramentas = llm.bind_tools(ferramentas)

    entidades_json = json.dumps(entidades, ensure_ascii=False, indent=2)
    mapa_categorias = {
        str(e.get("texto", "")).strip().lower(): e.get("categoria", "").upper()
        for e in entidades if e.get("texto")
    }

    # IMPORTANTE: não usamos ChatPromptTemplate.format_messages() aqui. O
    # texto das entidades é um JSON cheio de chaves { }, que o motor de
    # template do LangChain interpreta como marcadores de variável, causando
    # KeyError. Montamos as mensagens diretamente.
    sistema = """Você é um assistente especializado em faturamento hospitalar brasileiro.
Sua tarefa é:
1. Receber uma lista de itens clínicos passíveis de faturamento (procedimentos,
   exames, materiais e medicamentos) extraídos de um prontuário eletrônico.
2. Para cada item, usar a ferramenta 'buscar_procedimento' para
   encontrar o código SIGTAP correspondente.
3. Retornar um JSON com a lista de correspondências encontradas.

REGRAS IMPORTANTES:
- Use EXATAMENTE o campo "texto" da entidade como argumento 'termo',
  sem traduzir, reformular ou abreviar.
- Passe SEMPRE o campo "categoria" da entidade no argumento 'categoria'.
- Chame a ferramenta UMA VEZ POR ENTIDADE, para TODAS as entidades da lista.
- Nunca invente termos que não estejam no campo "texto" da entidade."""

    humano = (f"Entidades extraídas:\n{entidades_json}\n\n"
              f"Consulte o SIGTAP para cada entidade e retorne as correspondências.")

    t0 = datetime.now()
    try:
        resposta = await asyncio.wait_for(
            llm_com_ferramentas.ainvoke(
                [SystemMessage(content=sistema), HumanMessage(content=humano)]
            ),
            timeout=TIMEOUT_LLM_CHAMADA,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"Timeout de {TIMEOUT_LLM_CHAMADA}s aguardando o LLM orquestrador."
        )

    chamadas = getattr(resposta, "tool_calls", []) or []
    print(f"  [LLM+MCP] LLM respondeu em {(datetime.now() - t0).total_seconds():.1f}s, "
          f"{len(chamadas)} chamada(s) para {len(entidades)} entidade(s).")
    if len(chamadas) < len(entidades):
        print(f"  [LLM+MCP] AVISO: o modelo não buscou "
              f"{len(entidades) - len(chamadas)} entidade(s). Comportamento "
              f"típico de modelos com tool calling sequencial.")

    resultados: list[dict] = []
    nao_encontrados: list[str] = []
    nao_faturaveis: list[str] = []

    for tool_call in chamadas:
        if tool_call["name"] != "buscar_procedimento":
            continue

        categoria_llm = str(tool_call["args"].get("categoria", "")).strip().upper()
        for termo in _expandir_termos(tool_call["args"].get("termo", "")):
            chave = termo.strip().lower()
            categoria = mapa_categorias.get(chave, "")
            if not categoria:
                for texto_ent, cat in mapa_categorias.items():
                    if chave in texto_ent or texto_ent in chave:
                        categoria = cat
                        break
            categoria = categoria or categoria_llm

            correspondencias, duracao = await _buscar_um_termo(
                ferramenta_busca, termo, categoria
            )
            _registrar_resultado(
                termo, categoria, correspondencias, duracao,
                resultados, nao_encontrados, nao_faturaveis,
            )

    return resultados, nao_encontrados, nao_faturaveis


async def no_consulta_sigtap(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Consulta o SIGTAP para cada entidade faturável extraída do prontuário.
    """
    ferramentas = obter_ferramentas_mcp()
    ferramenta_busca = next(
        (f for f in ferramentas if f.name == "buscar_procedimento"), None
    )
    if ferramenta_busca is None:
        raise RuntimeError(
            "Ferramenta 'buscar_procedimento' não encontrada no servidor MCP."
        )

    # Filtro por categoria feito no CÓDIGO (determinístico). Busca as quatro
    # categorias faturáveis -- a tabela SIGTAP cobre todas elas.
    entidades_buscaveis = [
        e for e in estado["entidades_brutas"]
        if e.get("categoria", "").upper() in CATEGORIAS_BUSCAVEIS
    ]
    entidades_descartadas = [
        e.get("texto", "") for e in estado["entidades_brutas"]
        if e.get("categoria", "").upper() not in CATEGORIAS_BUSCAVEIS
    ]

    modo = "LLM orquestrando" if ORQUESTRACAO_POR_LLM else "laço determinístico"
    print(f"  [SIGTAP] Consultando {len(entidades_buscaveis)} entidade(s) "
          f"({modo}), {len(entidades_descartadas)} descartada(s).")

    if ORQUESTRACAO_POR_LLM:
        resultados, nao_encontrados, nao_faturaveis = await _consultar_sigtap_via_llm(
            entidades_buscaveis, ferramentas, ferramenta_busca
        )
    else:
        resultados, nao_encontrados, nao_faturaveis = await _consultar_sigtap(
            entidades_buscaveis, ferramenta_busca
        )

    baixa_confianca = [
        r["termo_buscado"] for r in resultados
        if any(c.get("confianca") == "baixa" for c in r["correspondencias"])
    ]
    print(f"  [SIGTAP] {len(resultados)} termo(s) com correspondência, "
          f"{len(nao_faturaveis)} não faturável(is), "
          f"{len(nao_encontrados)} sem correspondência, "
          f"{len(baixa_confianca)} de baixa confiança.")
    if baixa_confianca:
        print(f"  [SIGTAP] Conferir manualmente: {', '.join(baixa_confianca)}")
    if entidades_descartadas:
        print(f"  [SIGTAP] Descartadas: {', '.join(entidades_descartadas)}")

    return {
        **estado,
        "resultados_sigtap": resultados,
        "termos_nao_encontrados": nao_encontrados,
        "termos_nao_faturaveis": nao_faturaveis,
        "entidades_descartadas": entidades_descartadas,
    }


def no_relatorio(estado: EstadoPipeline) -> EstadoPipeline:
    """Consolida os resultados num relatório estruturado."""
    print("  [RELATÓRIO] Gerando relatório...")

    codigos_encontrados = {}
    for resultado in estado["resultados_sigtap"]:
        for correspondencia in resultado.get("correspondencias", []):
            if not isinstance(correspondencia, dict) or "codigo" not in correspondencia:
                continue
            codigo = correspondencia["codigo"]
            if codigo not in codigos_encontrados:
                codigos_encontrados[codigo] = {
                    "codigo": codigo,
                    "descricao": correspondencia["descricao"],
                    "grupo": correspondencia["grupo"],
                    "origem": resultado["termo_buscado"],
                    "categoria": resultado.get("categoria", ""),
                    "vl_sh": correspondencia.get("vl_sh", 0.0),
                    "vl_sa": correspondencia.get("vl_sa", 0.0),
                    "vl_sp": correspondencia.get("vl_sp", 0.0),
                    "vl_total": correspondencia.get("vl_total", 0.0),
                    "nivel": correspondencia.get("nivel", ""),
                    # score e confiança, para o relatório destacar o que
                    # precisa de conferência humana
                    "score": correspondencia.get("score", 0.0),
                    "confianca": correspondencia.get("confianca", ""),
                    "painel": bool(resultado.get("painel")),
                    # quantas voltas o agente do nível 4 deu até concluir
                    "tentativas_agente": correspondencia.get("tentativas_agente"),
                }

    codigos = list(codigos_encontrados.values())
    relatorio = {
        "prontuario_id": estado["prontuario_id"],
        "data_processamento": datetime.now().isoformat(),
        # registra o modelo e o modo de orquestração: um resultado obtido
        # com um modelo que depois sai de catálogo não é reproduzível sem
        # essa informação
        "modelo_utilizado": _descrever_modelo_atual(),
        "orquestracao": "llm" if ORQUESTRACAO_POR_LLM else "deterministica",
        "texto_prontuario": estado.get("texto", ""),
        "entidades_extraidas": [e.get("texto", "") for e in estado["entidades_brutas"]],
        "resumo": {
            "total_entidades_extraidas": len(estado["entidades_brutas"]),
            "total_codigos_sigtap": len(codigos),
            "total_nao_encontrados": len(estado.get("termos_nao_encontrados", [])),
            "total_nao_faturaveis": len(estado.get("termos_nao_faturaveis", [])),
            "total_baixa_confianca": sum(
                1 for c in codigos if c.get("confianca") == "baixa"
            ),
            "valor_total": round(sum(c.get("vl_total", 0.0) for c in codigos), 2),
        },
        "entidades_por_categoria": _agrupar_por_categoria(estado["entidades_brutas"]),
        "codigos_sigtap": codigos,
        # DUAS listas com significados opostos para quem confere:
        #  - nao_encontrados: pendência, exige revisão manual
        #  - nao_faturaveis: informação normal, o SIGTAP não tem código próprio
        "termos_nao_encontrados": estado.get("termos_nao_encontrados", []),
        "termos_nao_faturaveis": estado.get("termos_nao_faturaveis", []),
        "entidades_descartadas": estado.get("entidades_descartadas", []),
    }

    return {**estado, "relatorio": relatorio}


def _agrupar_por_categoria(entidades: list[dict]) -> dict:
    grupos: dict[str, list[str]] = {}
    for e in entidades:
        grupos.setdefault(e["categoria"], []).append(e["texto"])
    return grupos


# ── Construção do grafo ────────────────────────────────────────────────────

# O grafo é compilado uma vez e reaproveitado entre prontuários.
_grafo_cache = None


def construir_grafo() -> StateGraph:
    global _grafo_cache
    if _grafo_cache is not None:
        return _grafo_cache

    grafo = StateGraph(EstadoPipeline)
    grafo.add_node("ner", no_ner)
    grafo.add_node("consulta_sigtap", no_consulta_sigtap)
    grafo.add_node("relatorio", no_relatorio)

    grafo.set_entry_point("ner")
    grafo.add_edge("ner", "consulta_sigtap")
    grafo.add_edge("consulta_sigtap", "relatorio")
    grafo.add_edge("relatorio", END)

    _grafo_cache = grafo.compile()
    return _grafo_cache


# ── Execução ───────────────────────────────────────────────────────────────

async def processar_prontuario(prontuario: dict) -> dict:
    """
    Processa um prontuário e retorna o relatório de faturamento.
    Requer que a sessão MCP já esteja aberta (iniciar_sessao_mcp).
    """
    grafo = construir_grafo()

    estado_inicial: EstadoPipeline = {
        "prontuario_id": prontuario["id"],
        "texto": prontuario["texto"],
        "entidades_brutas": [],
        "entidades_refinadas": [],
        "resultados_sigtap": [],
        "termos_nao_encontrados": [],
        "termos_nao_faturaveis": [],
        "entidades_descartadas": [],
        "relatorio": {},
    }

    estado_final = await grafo.ainvoke(estado_inicial)
    return estado_final["relatorio"]


async def processar_lote(caminho_entrada: str, caminho_saida: str) -> list[dict]:
    """
    Processa todos os prontuários de um JSON de entrada e salva a lista
    consolidada de relatórios no JSON de saída -- o formato consumido por
    gerar_relatorio.py.

    A sessão MCP é aberta e fechada AQUI, na task principal, para que o
    subprocesso do servidor SIGTAP fique de pé durante todo o processamento e
    o encerramento não cruze fronteiras de task (anyio cancel scope).
    """
    with open(caminho_entrada, encoding="utf-8") as f:
        prontuarios = json.load(f)

    if isinstance(prontuarios, dict):
        prontuarios = [prontuarios]

    relatorios = []
    await iniciar_sessao_mcp()
    try:
        for i, prontuario in enumerate(prontuarios, start=1):
            print(f"\n[{i}/{len(prontuarios)}] Prontuário {prontuario.get('id', '?')}")
            relatorios.append(await processar_prontuario(prontuario))
    finally:
        await fechar_sessao_mcp()

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(relatorios, f, ensure_ascii=False, indent=2)

    print(f"\nConcluído: {len(relatorios)} prontuários processados.")
    print(f"JSON de saída salvo em: {caminho_saida}")
    return relatorios


# ── Ponto de entrada para rodar o lote completo ────────────────────────────

if __name__ == "__main__":
    # Caminhos padrão relativos a este arquivo (src/agent/pipeline.py):
    #   entrada: data/prontuarios.json
    #   saida:   reports/relatorios_processados.json
    base = os.path.dirname(__file__)
    entrada_padrao = os.path.join(base, "..", "..", "data", "prontuarios.json")
    saida_padrao = os.path.join(base, "..", "..", "reports", "relatorios_processados.json")

    entrada = sys.argv[1] if len(sys.argv) > 1 else entrada_padrao
    saida = sys.argv[2] if len(sys.argv) > 2 else saida_padrao

    os.makedirs(os.path.dirname(saida), exist_ok=True)

    asyncio.run(processar_lote(entrada, saida))