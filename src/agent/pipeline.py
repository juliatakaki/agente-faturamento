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


# ── Status de execução do item no prontuário ───────────────────────────────
#
# PROBLEMA QUE ISTO RESOLVE: prontuário registra tanto o que foi FEITO
# quanto o que foi apenas cogitado -- solicitado e não realizado, cancelado,
# adiado, programado para depois, suspenso. Só o que foi efetivamente
# realizado é faturável.
#
# Até agosto/2026 o sistema não fazia essa distinção: extraía o termo e
# faturava. Nos 10 prontuários sintéticos de calibração isso nunca apareceu,
# porque tudo que era mencionado tinha sido realizado. No conjunto de
# validação (VAL006), escrito de propósito com exames solicitados,
# cancelados e programados, o sistema atribuiu código a um ecocardiograma
# que não foi feito e a uma tomografia cancelada -- ou seja, cobrança
# indevida, que em faturamento SUS significa glosa.
#
# A detecção é feita pelo EXTRATOR, não por uma etapa separada: quem lê o
# texto é quem tem o contexto ("solicitado ecocardiograma, ainda não
# realizado"). Uma verificação posterior, olhando só o termo isolado,
# perderia essa informação.
#
# Itens não realizados NÃO são descartados: vão para uma lista própria no
# relatório. O sistema mostra o que viu e classifica; não esconde. Isso
# preserva a informação para o faturista (que pode saber que o exame
# acabou sendo feito e não registrado) sem inflar o valor sugerido.
STATUS_REALIZADO = "REALIZADO"
STATUS_NAO_REALIZADO = "NAO_REALIZADO"

# Marcadores textuais de que o item NÃO foi realizado. Usados como rede de
# segurança sobre a classificação do LLM: se o modelo disser REALIZADO mas
# o texto ao redor do termo contiver um destes, o item é rebaixado. A
# assimetria é deliberada -- em faturamento, errar para menos custa receita,
# errar para mais custa glosa e credibilidade.
_MARCADORES_NAO_REALIZADO = (
    "nao realizado", "nao realizada", "nao foi realizado", "nao foi realizada",
    "nao realizou", "sem realizar",
    "cancelado", "cancelada", "suspenso", "suspensa",
    "adiado", "adiada", "postergado", "postergada",
    "programado", "programada", "agendado", "agendada",
    "solicitado", "solicitada", "aguarda", "aguardando",
    "a realizar", "sera realizado", "sera realizada",
    "previsto", "prevista", "indicado", "indicada",
)


# ── Tipos ──────────────────────────────────────────────────────────────────

class EstadoPipeline(TypedDict):
    prontuario_id: str
    texto: str
    entidades_brutas: list[dict]       # saída do NER
    entidades_refinadas: list[dict]    # saída do LLM (normalização)
    resultados_sigtap: list[dict]      # saída da consulta MCP
    termos_nao_encontrados: list[str]  # buscados sem correspondência (REVISAR)
    termos_nao_faturaveis: list[str]   # sem código próprio no SIGTAP
    termos_nao_realizados: list[dict]  # mencionados mas não executados
    entidades_descartadas: list[str]   # fora das categorias faturáveis
    relatorio: dict                    # relatório final


# ── Configuração do subprocesso MCP ────────────────────────────────────────
#
# Usa sys.executable (caminho do Python em uso) em vez de "python3" fixo,
# pois "python3" não existe no Windows -- isso causava "Connection closed"
# ao iniciar o subprocesso do servidor MCP.
#
# AMBIENTE EXPLÍCITO: as variáveis que definem o modelo são montadas na hora
# de abrir a sessão e passadas ao subprocesso. O menu do main.py escreve a
# escolha em os.environ do processo PAI, e variável de ambiente é copiada
# para o filho no momento em que ele nasce -- sem passar explicitamente, o
# subprocesso herdava um ambiente diferente do escolhido no menu.

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
#   - api:    provedor externo. Melhor desempenho, porém envia os dados p/ fora.
#
# IMPORTANTE: o modo "api" envia o conteúdo processado a servidores externos.
# Usar apenas com dados sintéticos ou conforme o protocolo de ética aprovado.

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
        # A Groq expõe API compatível com a da OpenAI.
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

Para cada item, informe TRÊS coisas: o termo, a categoria e o status.

CATEGORIA — uma destas quatro:
- PROCEDIMENTO: procedimentos clínicos e cirúrgicos
  (ex: "intubação orotraqueal", "laparotomia exploradora")
- EXAME: exames laboratoriais ou de imagem
  (ex: "hemograma completo", "raio-x de tórax")
- MATERIAL: materiais e insumos
  (ex: "cateter venoso central", "sonda vesical")
- MEDICAMENTO: medicamentos administrados
  (ex: "midazolam", "piperacilina-tazobactam")

STATUS — esta é a parte mais importante. Prontuário registra tanto o que foi
FEITO quanto o que foi apenas cogitado. Só o que foi realizado pode ser
faturado; cobrar um exame que não aconteceu é irregularidade grave.
- REALIZADO: o item foi efetivamente executado
  ("realizada laparotomia", "coletado hemograma", "administrado midazolam")
- NAO_REALIZADO: o item foi mencionado mas NÃO executado — solicitado e
  ainda pendente, cancelado, suspenso, adiado, programado para depois, ou
  explicitamente negado
  ("solicitado ecocardiograma, ainda não realizado", "tomografia cancelada",
   "não foi realizada a endoscopia", "colonoscopia programada para a
   próxima semana", "antibiótico suspenso")

Na dúvida sobre o status, responda NAO_REALIZADO. É preferível deixar de
faturar algo que aconteceu a cobrar algo que não aconteceu.

COMO ESCREVER O TERMO:
- Use o NOME DO PROCEDIMENTO, sem os detalhes ao redor. O termo será
  buscado numa tabela oficial que registra apenas o nome do ato.
- Escreva "hemodiálise", não "sessão de hemodiálise de 4 horas por fístula
  arteriovenosa". Escreva "sutura de ferimento", não "sutura de laceração em
  couro cabeludo de aproximadamente 8 cm". Escreva "radiografia de fêmur",
  não "RX de fêmur em duas incidências".
- Mantenha o que IDENTIFICA o procedimento (região anatômica, via, tipo) e
  descarte o que é circunstância (duração, quantidade, medida, lateralidade,
  motivo, quem realizou).
- Expanda abreviações que você reconheça com segurança: "HMG" vira
  "hemograma", "RX tx" vira "radiografia de tórax", "GASO" vira
  "gasometria". Se não tiver certeza do que a abreviação significa, mantenha
  como está.

REGRAS GERAIS:
- Não invente itens que não estão explicitamente mencionados no texto.
- Não inclua dados administrativos, sinais vitais isolados ou comentários
  gerais.
- Um item mencionado várias vezes aparece uma vez só.
- Responda APENAS com um array JSON, sem texto antes ou depois e sem blocos
  de código markdown. Formato exato:
  [{"texto": "hemograma completo", "categoria": "EXAME", "status": "REALIZADO"}]
- Se nenhum item for identificado, responda com um array vazio: []
"""


def _normalizar_texto_simples(texto: str) -> str:
    """Minúsculas e sem acentos, para comparação de marcadores textuais."""
    import unicodedata
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _verificar_status_no_texto(termo: str, texto_prontuario: str) -> bool:
    """
    Rede de segurança sobre a classificação do LLM: localiza a SENTENÇA em
    que o termo aparece e verifica se ela contém marcador de não realização.

    Retorna True se encontrou indício de que o item NÃO foi realizado.

    POR QUE SENTENÇA, E NÃO UMA JANELA DE CARACTERES: a primeira versão
    olhava os ~90 caracteres ao redor do termo, e isso atravessava a
    fronteira da frase. No VAL006, "Foi coletado hemograma completo" fica
    logo depois de "A tomografia de abdome programada para hoje foi
    cancelada" -- a janela pegava "programada" e "cancelada" da frase
    anterior e rebaixava o hemograma, que tinha sido realizado. A sentença é
    a unidade natural de escopo dessas marcações em português.

    Esta verificação NUNCA promove um item a realizado -- só rebaixa. Se o
    LLM disse NAO_REALIZADO, a decisão dele é mantida.
    """
    if not termo or not texto_prontuario:
        return False

    termo_norm = _normalizar_texto_simples(termo)
    sentencas = [
        s for s in re.split(r"[.;!?\n]+", _normalizar_texto_simples(texto_prontuario))
        if s.strip()
    ]

    # Procura a sentença que contém o termo completo.
    alvo = next((s for s in sentencas if termo_norm in s), None)

    # O extrator pode ter reformulado o termo (abreviação expandida, frase
    # encurtada). Nesse caso, procura pela palavra mais longa -- que tende a
    # ser a mais específica e a que sobrevive à reformulação.
    if alvo is None:
        palavras = sorted(
            (p for p in termo_norm.split() if len(p) > 4), key=len, reverse=True
        )
        for palavra in palavras:
            alvo = next((s for s in sentencas if palavra in s), None)
            if alvo is not None:
                break

    if alvo is None:
        return False

    return any(marcador in alvo for marcador in _MARCADORES_NAO_REALIZADO)


async def extrair_entidades_llm(texto_prontuario: str) -> list[dict]:
    """
    Extrai entidades clínicas faturáveis direto do texto bruto, via LLM, em
    vez do NER por regras. Retorna dicts com texto, categoria e status.

    É AQUI, e não na orquestração, que faz sentido comparar modelos: ler um
    texto narrativo e decidir o que é item faturável -- e se foi realizado --
    é trabalho cognitivo real, com espaço amplo para os modelos divergirem.
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
    rebaixadas = []
    for e in entidades:
        if not isinstance(e, dict):
            continue
        texto = str(e.get("texto", "")).strip()
        categoria = str(e.get("categoria", "")).strip().upper()
        if not texto or categoria not in CATEGORIAS_BUSCAVEIS:
            continue

        # Status vindo do modelo; ausente é tratado como REALIZADO para não
        # perder itens quando o modelo ignora o campo (o texto abaixo ainda
        # pode rebaixá-lo).
        status = str(e.get("status", "")).strip().upper()
        if status != STATUS_NAO_REALIZADO:
            status = STATUS_REALIZADO

        # Rede de segurança: o texto do prontuário pode contradizer o modelo.
        if status == STATUS_REALIZADO and _verificar_status_no_texto(
            texto, texto_prontuario
        ):
            status = STATUS_NAO_REALIZADO
            rebaixadas.append(texto)

        validas.append({"texto": texto, "categoria": categoria, "status": status})

    if rebaixadas:
        print(f"  [EXTRATOR-LLM] {len(rebaixadas)} item(ns) rebaixado(s) para "
              f"NÃO REALIZADO pelo contexto do texto: {', '.join(rebaixadas)}")
    return validas


async def no_ner(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Extrai entidades clínicas do prontuário. O método é escolhido por
    EXTRATOR_ATIVO:
      "regras" (padrão) -> NER por regras (spaCy EntityRuler).
      "llm"              -> extração via LLM.

    O extrator por regras não classifica status (não tem contexto para
    isso), então suas entidades entram como REALIZADO e passam apenas pela
    verificação textual -- que é o que dá alguma proteção nesse modo.
    """
    print(f"  [NER] Processando {estado['prontuario_id']}...")
    extrator = os.getenv("EXTRATOR_ATIVO", "regras").strip().lower()

    if extrator == "regras":
        entidades = extrair_entidades(estado["texto"], NLP)
        rebaixadas = []
        for e in entidades:
            if _verificar_status_no_texto(e.get("texto", ""), estado["texto"]):
                e["status"] = STATUS_NAO_REALIZADO
                rebaixadas.append(e.get("texto", ""))
            else:
                e["status"] = STATUS_REALIZADO
        if rebaixadas:
            print(f"  [NER] {len(rebaixadas)} item(ns) marcado(s) como NÃO "
                  f"REALIZADO pelo contexto: {', '.join(rebaixadas)}")
    elif extrator == "llm":
        entidades = await extrair_entidades_llm(estado["texto"])
    else:
        raise ValueError(f"EXTRATOR_ATIVO inválido: '{extrator}'. Use 'regras' ou 'llm'.")

    n_realizadas = sum(
        1 for e in entidades if e.get("status", STATUS_REALIZADO) == STATUS_REALIZADO
    )
    print(f"  [NER] ({extrator}) {len(entidades)} entidades extraídas "
          f"({n_realizadas} realizadas, {len(entidades) - n_realizadas} não realizadas).")
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
    caso em que o modelo agrupa vários termos num único argumento.
    Usado apenas no modo ORQUESTRACAO_POR_LLM.
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
# mostraram que o resultado depende inteiramente de qual modelo está por trás:
#
#   modelo                 chamadas para 10 entidades
#   ---------------------  --------------------------
#   llama-3.3-70b          10   (emite chamadas em paralelo)
#   gemini-3.5-flash       10   (idem)
#   openai/gpt-oss-120b     1   (tool calling sequencial)
#   qwen/qwen3.6-27b        1   (idem)
#
# Modelos de tool calling sequencial emitem UMA chamada, esperam o resultado
# e só então decidem a próxima -- e como o código coletava as tool_calls de
# uma única resposta, 84 de 94 termos nunca eram buscados.
#
# Percorrer uma lista não é uma decisão: é uma iteração. Com o laço, são
# sempre N chamadas para N entidades, em qualquer modelo.
#
# ISSO NÃO REMOVE O AGENTE. A autonomia do modelo está no Nível 4 do servidor
# MCP, onde existe decisão real: propor um termo alternativo, observar o que
# a busca devolveu e decidir entre aceitar, tentar de novo ou desistir.
#
# O comportamento antigo continua disponível com ORQUESTRACAO_POR_LLM=true.


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
    # ── Desfecho 1: termo sem código próprio no SIGTAP, conforme o
    # dicionário do sistema. Vai para uma lista PRÓPRIA, separada dos "não
    # encontrados", porque o significado para quem confere é oposto.
    if correspondencias and correspondencias[0].get("nivel") == "nao_faturavel":
        print(f"    [Não faturável] '{termo}' ({categoria or 'sem categoria'}) "
              f"— marcado como sem código próprio no SIGTAP")
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
    # PAINEL: quando o termo corresponde a vários códigos faturáveis
    # (ex: "coagulograma" = TP + TTPA), TODOS entram. Fora do painel,
    # considera-se apenas o primeiro candidato: os demais são alternativas
    # que NÃO foram necessariamente realizadas.
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
    Laço determinístico: uma busca por entidade, na ordem em que o extrator
    as devolveu. Devolve (resultados, nao_encontrados, nao_faturaveis).

    A categoria vem direto da entidade (fonte determinística), sem passar
    pelo LLM -- eliminando a chance de o modelo trocá-la.
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
    fazer, como era antes de agosto/2026. Mantido para reproduzir a
    comparação no TCC 2. NÃO é o modo recomendado.
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
    # template do LangChain interpreta como marcadores de variável.
    sistema = """Você é um assistente especializado em faturamento hospitalar brasileiro.
Sua tarefa é:
1. Receber uma lista de itens clínicos passíveis de faturamento.
2. Para cada item, usar a ferramenta 'buscar_procedimento' para
   encontrar o código SIGTAP correspondente.
3. Retornar um JSON com a lista de correspondências encontradas.

REGRAS IMPORTANTES:
- Use EXATAMENTE o campo "texto" da entidade como argumento 'termo'.
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
    Consulta o SIGTAP para cada entidade faturável REALIZADA.

    Itens marcados como não realizados são separados ANTES da busca: não
    faz sentido gastar consulta (e, no nível 4, chamadas de LLM) com algo
    que não pode ser faturado. Eles seguem para o relatório numa lista
    própria, para que o faturista veja o que o sistema encontrou e decida.
    """
    ferramentas = obter_ferramentas_mcp()
    ferramenta_busca = next(
        (f for f in ferramentas if f.name == "buscar_procedimento"), None
    )
    if ferramenta_busca is None:
        raise RuntimeError(
            "Ferramenta 'buscar_procedimento' não encontrada no servidor MCP."
        )

    # Filtro por categoria feito no CÓDIGO (determinístico).
    entidades_faturaveis = [
        e for e in estado["entidades_brutas"]
        if e.get("categoria", "").upper() in CATEGORIAS_BUSCAVEIS
    ]
    entidades_descartadas = [
        e.get("texto", "") for e in estado["entidades_brutas"]
        if e.get("categoria", "").upper() not in CATEGORIAS_BUSCAVEIS
    ]

    # Separação por status: só o realizado é buscado.
    entidades_buscaveis = [
        e for e in entidades_faturaveis
        if e.get("status", STATUS_REALIZADO) == STATUS_REALIZADO
    ]
    nao_realizadas = [
        {"texto": e.get("texto", ""), "categoria": e.get("categoria", "")}
        for e in entidades_faturaveis
        if e.get("status", STATUS_REALIZADO) != STATUS_REALIZADO
    ]

    modo = "LLM orquestrando" if ORQUESTRACAO_POR_LLM else "laço determinístico"
    print(f"  [SIGTAP] Consultando {len(entidades_buscaveis)} entidade(s) "
          f"realizada(s) ({modo}); {len(nao_realizadas)} não realizada(s), "
          f"{len(entidades_descartadas)} descartada(s).")
    if nao_realizadas:
        print(f"  [SIGTAP] Não faturados por não terem sido realizados: "
              f"{', '.join(e['texto'] for e in nao_realizadas)}")

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
          f"{len(nao_faturaveis)} sem código próprio, "
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
        "termos_nao_realizados": nao_realizadas,
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
                    "score": correspondencia.get("score", 0.0),
                    "confianca": correspondencia.get("confianca", ""),
                    "painel": bool(resultado.get("painel")),
                    "tentativas_agente": correspondencia.get("tentativas_agente"),
                }

    codigos = list(codigos_encontrados.values())
    nao_realizados = estado.get("termos_nao_realizados", [])

    relatorio = {
        "prontuario_id": estado["prontuario_id"],
        "data_processamento": datetime.now().isoformat(),
        # registra o modelo, o extrator e o modo de orquestração: um
        # resultado obtido com um modelo que depois sai de catálogo não é
        # reproduzível sem essa informação
        "modelo_utilizado": _descrever_modelo_atual(),
        "extrator": os.getenv("EXTRATOR_ATIVO", "regras").strip().lower(),
        "orquestracao": "llm" if ORQUESTRACAO_POR_LLM else "deterministica",
        "texto_prontuario": estado.get("texto", ""),
        "entidades_extraidas": [e.get("texto", "") for e in estado["entidades_brutas"]],
        "resumo": {
            "total_entidades_extraidas": len(estado["entidades_brutas"]),
            "total_codigos_sigtap": len(codigos),
            "total_nao_encontrados": len(estado.get("termos_nao_encontrados", [])),
            "total_nao_faturaveis": len(estado.get("termos_nao_faturaveis", [])),
            "total_nao_realizados": len(nao_realizados),
            "total_baixa_confianca": sum(
                1 for c in codigos if c.get("confianca") == "baixa"
            ),
            "valor_total": round(sum(c.get("vl_total", 0.0) for c in codigos), 2),
        },
        "entidades_por_categoria": _agrupar_por_categoria(estado["entidades_brutas"]),
        "codigos_sigtap": codigos,
        # Três listas com significados distintos para quem confere:
        #  - nao_encontrados: a busca falhou, pode haver receita a cobrar
        #  - nao_faturaveis: o dicionário marcou como sem código próprio
        #  - nao_realizados: mencionados no prontuário mas não executados
        "termos_nao_encontrados": estado.get("termos_nao_encontrados", []),
        "termos_nao_faturaveis": estado.get("termos_nao_faturaveis", []),
        "termos_nao_realizados": nao_realizados,
        "entidades_descartadas": estado.get("entidades_descartadas", []),
    }

    return {**estado, "relatorio": relatorio}


def _agrupar_por_categoria(entidades: list[dict]) -> dict:
    grupos: dict[str, list[str]] = {}
    for e in entidades:
        grupos.setdefault(e["categoria"], []).append(e["texto"])
    return grupos


# ── Construção do grafo ────────────────────────────────────────────────────

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
        "termos_nao_realizados": [],
        "entidades_descartadas": [],
        "relatorio": {},
    }

    estado_final = await grafo.ainvoke(estado_inicial)
    return estado_final["relatorio"]


async def processar_lote(caminho_entrada: str, caminho_saida: str) -> list[dict]:
    """
    Processa todos os prontuários de um JSON de entrada e salva a lista
    consolidada de relatórios no JSON de saída.

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
    base = os.path.dirname(__file__)
    entrada_padrao = os.path.join(base, "..", "..", "data", "prontuarios_hub.json")
    saida_padrao = os.path.join(base, "..", "..", "reports", "relatorios_processados.json")

    entrada = sys.argv[1] if len(sys.argv) > 1 else entrada_padrao
    saida = sys.argv[2] if len(sys.argv) > 2 else saida_padrao

    os.makedirs(os.path.dirname(saida), exist_ok=True)

    asyncio.run(processar_lote(entrada, saida))