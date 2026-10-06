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
import importlib.util
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

# Regras de texto (regex + scoring), em src/agent/regras_texto.py. Carregado
# pelo caminho do arquivo para funcionar tanto rodando este arquivo direto
# quanto importando-o a partir do main.py, sem depender de como o pacote
# 'agent' está montado. É o MESMO módulo que src/analise/etapa3_regras_regex.py
# avalia, para o que é medido e o que roda nunca divergirem.
_spec_regras = importlib.util.spec_from_file_location(
    "regras_texto", os.path.join(os.path.dirname(os.path.abspath(__file__)), "regras_texto.py")
)
regras_texto = importlib.util.module_from_spec(_spec_regras)
_spec_regras.loader.exec_module(regras_texto)

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

# Marcadores textuais de que o item NÃO foi realizado NESTA evolução. Usados
# como rede de segurança sobre a classificação do LLM: se o modelo disser
# REALIZADO mas o texto ao redor do termo contiver um destes, o item é
# rebaixado. A assimetria é deliberada -- em faturamento, errar para menos
# custa receita, errar para mais custa glosa e credibilidade.
#
# Duas categorias, por direção temporal: (1) o item ainda vai acontecer
# (futuro/pendente) e (2) o item já aconteceu ANTES desta nota, geralmente
# em outra internação ou etapa cirúrgica anterior (histórico/pós-operatório).
# A categoria (2) foi adicionada depois de um caso real: "1)POI - Laparotomia
# exploradora..." no diagnóstico clínico de uma evolução -- POI (pós-operatório
# imediato) sinaliza que a cirurgia já ocorreu, mas sem esse marcador o item
# era classificado como realizado NESTA data, inflando o relatório com um
# procedimento cirúrgico de alto valor que não aconteceu na internação atual.
_MARCADORES_NAO_REALIZADO = (
    # -- futuro / pendente --
    "nao realizado", "nao realizada", "nao foi realizado", "nao foi realizada",
    "nao realizou", "sem realizar",
    "cancelado", "cancelada", "suspenso", "suspensa",
    "adiado", "adiada", "postergado", "postergada",
    "programado", "programada", "agendado", "agendada",
    "solicitado", "solicitada", "aguarda", "aguardando",
    "a realizar", "sera realizado", "sera realizada",
    "previsto", "prevista", "indicado", "indicada",
    # -- histórico / já ocorreu antes desta nota --
    "poi",  # pós-operatório imediato
)


# Termos extraídos que, sozinhos, não carregam contexto suficiente para
# apontar UM código SIGTAP com confiança -- mesmo problema documentado como
# "regra de ouro" em sinonimos_sigtap.json, mas do lado da extração: aqui o
# termo em si (não um alvo de dicionário) é curto demais para diferenciar
# entre códigos próximos.
#
# Caso que motivou a lista: "curativo" sozinho resolve no nível 1 para
# CURATIVO SIMPLES (03.01.10.028-4) por pontuação F1 -- a descrição mais
# curta natural vence contra CURATIVO GRAU II C/ OU S/ DEBRIDAMENTO
# (04.01.01.001-5), mesmo quando o texto ao redor descreve lesão com
# debridamento/exsudato que indicaria o grau maior. Em vez de arriscar o
# código errado (ou fixar um mapeamento não validado pelo faturamento),
# o termo é desviado da busca inteiramente e cai para revisão manual.
#
# Exceção (out/2026): com USAR_REGRAS_TEXTO=true, se a regra de texto do
# curativo grau II disparar, o "curativo" sai desta lista de revisão, porque o
# código já foi atribuído pela regra. Base: nas 420 evoluções do gabarito do
# HUB, o curativo simples não aparece nenhuma vez; todo curativo faturado em
# UTI foi grau II. Quando a regra não dispara, o comportamento acima continua.
#
# Só adicionar aqui com evidência de ambiguidade real observada nos dados --
# mesmo critério do arquivo de sinônimos: é melhor cair em revisão manual do
# que resolver automaticamente para um código plausível e errado.
_TERMOS_GENERICOS_REVISAR = frozenset({
    "curativo",
})


# ── Tipos ──────────────────────────────────────────────────────────────────

class EstadoPipeline(TypedDict):
    prontuario_id: str
    texto: str
    entidades_brutas: list[dict]       # saída do NER
    entidades_refinadas: list[dict]    # saída do LLM (normalização)
    resultados_sigtap: list[dict]      # saída da consulta MCP
    termos_nao_encontrados: list[str]  # buscados sem correspondência (REVISAR)
    termos_nao_faturaveis: list[str]   # sem código próprio no SIGTAP
    termos_ambiguos: list[str]         # genéricos demais, desviados da busca (REVISAR)
    termos_nao_realizados: list[dict]  # mencionados mas não executados
    candidatos_regra: list[dict]       # regra de texto disparou mas não foi confirmada (REVISAR)
    substituidos_por_regra: list[dict] # resultados da busca trocados pela regra (para avaliação)
    falha_extracao: str                # motivo, se o extrator falhou; "" se não falhou
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
        return (f"api/{os.getenv('PROVEDOR_API', '?')} - "
                f"{os.getenv('MODELO_API', '?')}")
    return f"local/ollama - {os.getenv('MODELO_LOCAL', 'llama3.2')}"


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

# Limite de tokens da resposta do LLM. Ver _criar_llm_api().
MAX_TOKENS_LLM = int(os.getenv("MAX_TOKENS_LLM", "8192"))


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

    max_tokens generoso em todos os provedores: prontuários grandes geram
    listas longas de entidades, e modelos que "raciocinam" (ex.: gpt-oss)
    consomem parte do limite de saída com raciocínio interno. Sem folga, a
    resposta é cortada no meio (finish_reason='length') e o JSON fica
    inválido -- foi o que truncava a extração dos prontuários mais extensos.

    O valor vem de MAX_TOKENS_LLM no .env (padrão 8192). Motivo (out/2026): no
    plano gratuito do Groq o limite caiu para 8.000 tokens por minuto, e o
    HUB004 passou a ser recusado com erro 413 (pedido de 11.669 tokens). Um
    max_tokens menor reduz o tamanho do pedido, ao custo de mais risco de
    resposta cortada nos prontuários com muitos itens.
    """
    max_tokens = MAX_TOKENS_LLM
    if provedor_api == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=modelo, temperature=0, max_tokens=max_tokens)

    if provedor_api == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=modelo, temperature=0, max_output_tokens=max_tokens
        )

    if provedor_api == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=modelo, temperature=0, max_tokens=max_tokens)

    if provedor_api == "groq":
        # A Groq expõe API compatível com a da OpenAI.
        from langchain_openai import ChatOpenAI
        chave_groq = os.getenv("GROQ_API_KEY", "")
        if not chave_groq:
            raise ValueError("PROVEDOR_API=groq requer GROQ_API_KEY no .env.")
        return ChatOpenAI(
            model=modelo, temperature=0, api_key=chave_groq,
            base_url="https://api.groq.com/openai/v1",
            max_tokens=max_tokens,
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

CATEGORIA - uma destas quatro:
- PROCEDIMENTO: procedimentos clínicos, cirúrgicos, terapêuticos e de
  reabilitação (ex: "intubação orotraqueal", "laparotomia exploradora",
  "fisioterapia respiratória", "fisioterapia motora", "nutrição enteral",
  "hemodiálise", "transfusão de hemácias")
- EXAME: exames laboratoriais ou de imagem
  (ex: "hemograma completo", "raio-x de tórax")
- MATERIAL: materiais e insumos
  (ex: "cateter venoso central", "sonda vesical")
- MEDICAMENTO: medicamentos administrados
  (ex: "midazolam", "piperacilina-tazobactam")

ATO vs. DISPOSITIVO: quando o texto menciona uma terapia administrada por
meio de um dispositivo, registre AMBOS separadamente, pois os dois podem ser
faturáveis. Ex: "dieta por sonda nasoenteral" gera tanto "nutrição enteral"
(o procedimento) quanto "sonda nasoenteral" (o material); "oxigênio por
cateter nasal" gera a oxigenoterapia e o cateter. Não registre apenas o
dispositivo, esquecendo o procedimento associado.

STATUS - esta é a parte mais importante. Prontuário registra tanto o que foi
FEITO quanto o que foi apenas cogitado. Só o que foi realizado pode ser
faturado; cobrar um exame que não aconteceu é irregularidade grave.
- REALIZADO: o item foi efetivamente executado
  ("realizada laparotomia", "coletado hemograma", "administrado midazolam")
- NAO_REALIZADO: o item foi mencionado mas NÃO executado - solicitado e
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

    return any(
        re.search(rf"\b{re.escape(marcador)}\b", alvo)
        for marcador in _MARCADORES_NAO_REALIZADO
    )

def _e_pedido_grande_demais(excecao: Exception) -> bool:
    """
    Detecta o erro 413 (pedido maior que o limite de tokens por minuto do
    plano). Precisa ser testado ANTES de _e_erro_de_cota: a resposta do Groq
    para o 413 traz o código 'rate_limit_exceeded' no corpo, e seria tratada
    como cota esgotada, interrompendo o lote inteiro. Caso real: no HUB004,
    um único prontuário grande derrubava os 10.

    Diferente da cota, o 413 não se resolve esperando: o mesmo pedido vai
    falhar de novo. Por isso vira falha só daquele prontuário.
    """
    if getattr(excecao, "status_code", None) == 413:
        return True
    texto = str(excecao).lower()
    return "error code: 413" in texto or "request too large" in texto


def _e_erro_de_cota(excecao: Exception) -> bool:
    """
    Detecta se a exceção é um estouro de cota / rate limit da API, de forma
    robusta a qual provedor está em uso (a Groq usa a lib da OpenAI, o Google
    tem a sua). Checa tanto o tipo da exceção quanto o texto da mensagem,
    porque nem todo provedor expõe uma classe própria acessível aqui.
    """
    # Tenta reconhecer pela classe da OpenAI (usada por OpenAI e Groq),
    # com import defensivo para não exigir o pacote quando se usa só Ollama.
    try:
        from openai import RateLimitError
        if isinstance(excecao, RateLimitError):
            return True
    except ImportError:
        pass

    # Fallback pelo conteúdo da mensagem -- cobre outros provedores e o
    # código HTTP 429, que é o padrão para "rate limit".
    texto = str(excecao).lower()
    return (
        "rate limit" in texto
        or "rate_limit" in texto
        or "429" in texto
        or "quota" in texto
        or "tokens per day" in texto
        or "tpd" in texto
    )


async def extrair_entidades_llm(texto_prontuario: str) -> list[dict]:
    """
    Versão que devolve só a lista de entidades, mantida para quem já chama
    esta função. O pipeline usa _extrair_entidades_llm_com_status, que diz
    também se a extração falhou.
    """
    entidades, _ = await _extrair_entidades_llm_com_status(texto_prontuario)
    return entidades


async def _extrair_entidades_llm_com_status(texto_prontuario: str) -> tuple[list[dict], str]:
    """
    Devolve (entidades, motivo_da_falha). motivo_da_falha é "" quando a
    extração funcionou, inclusive quando o prontuário não tem nenhum item.

    POR QUE DISTINGUIR: antes, falha e prontuário sem itens devolviam a mesma
    lista vazia. No HUB006 o LLM deu timeout e dois erros de conexão, e o
    relatório saiu como se a evolução estivesse quase vazia, sem nenhum aviso
    para quem confere.

    Extrai entidades clínicas faturáveis direto do texto bruto, via LLM, em
    vez do NER por regras. Retorna dicts com texto, categoria e status.

    É AQUI, e não na orquestração, que faz sentido comparar modelos: ler um
    texto narrativo e decidir o que é item faturável -- e se foi realizado --
    é trabalho cognitivo real, com espaço amplo para os modelos divergirem.

    A chamada ao LLM é repetida em caso de falha transitória (resposta vazia
    ou timeout), com espera crescente entre tentativas. Já o estouro de cota
    da API (rate limit) não é transitório dentro da execução -- a cota é por
    minuto/dia --, então interrompe o lote com uma mensagem clara, em vez de
    insistir à toa ou explodir com um traceback.
    """
    llm = criar_llm()
    mensagens = [
        SystemMessage(content=EXTRATOR_LLM_SISTEMA),
        HumanMessage(content=f"Texto do prontuário:\n\n{texto_prontuario}"),
    ]

    MAX_TENTATIVAS = 3
    ESPERA_ENTRE_TENTATIVAS = [2, 4]  # segundos, backoff crescente

    conteudo = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resposta = await asyncio.wait_for(
                llm.ainvoke(mensagens), timeout=TIMEOUT_LLM_CHAMADA
            )
        except asyncio.TimeoutError:
            print(f"  [EXTRATOR-LLM] TIMEOUT ({TIMEOUT_LLM_CHAMADA}s) na "
                  f"tentativa {tentativa}/{MAX_TENTATIVAS}.")
            resposta = None
        except Exception as e:
            if _e_pedido_grande_demais(e):
                print(f"  [EXTRATOR-LLM] pedido grande demais para o limite por minuto "
                      f"do provedor (413). Sem nova tentativa: o mesmo pedido falharia "
                      f"de novo. Detalhe: {str(e)[:200]}")
                return [], (
                    "o texto é grande demais para o limite de tokens por minuto do "
                    "provedor (erro 413); reduzir MAX_TOKENS_LLM no .env, usar "
                    "outro provedor ou ler manualmente"
                )
            if _e_erro_de_cota(e):
                raise RuntimeError(
                    "Cota da API do modelo esgotada (rate limit). O lote foi "
                    "interrompido. Opções: aguardar o reset da cota, trocar de "
                    "provedor no menu (ex.: Ollama local, sem cota) ou usar "
                    "outra chave/plano. Detalhe do provedor: "
                    f"{str(e)[:300]}"
                ) from e
            print(f"  [EXTRATOR-LLM] erro na chamada ({type(e).__name__}) na "
                  f"tentativa {tentativa}/{MAX_TENTATIVAS}: {str(e)[:150]}")
            resposta = None

        if resposta is not None:
            # Normaliza o conteúdo para string. Alguns provedores (Gemini via
            # LangChain) devolvem resposta.content como LISTA de blocos.
            bruto = resposta.content
            if isinstance(bruto, list):
                partes = []
                for parte in bruto:
                    if isinstance(parte, str):
                        partes.append(parte)
                    elif isinstance(parte, dict):
                        partes.append(parte.get("text", "") or parte.get("content", ""))
                    else:
                        partes.append(str(parte))
                bruto = "".join(partes)
            elif not isinstance(bruto, str):
                bruto = str(bruto)

            if bruto.strip():
                conteudo = bruto
                break
            print(f"  [EXTRATOR-LLM] resposta vazia na tentativa "
                  f"{tentativa}/{MAX_TENTATIVAS}.")

        if tentativa < MAX_TENTATIVAS:
            espera = ESPERA_ENTRE_TENTATIVAS[tentativa - 1]
            print(f"  [EXTRATOR-LLM] repetindo em {espera}s...")
            await asyncio.sleep(espera)

    if not conteudo:
        print(f"  [EXTRATOR-LLM] falhou após {MAX_TENTATIVAS} tentativa(s) "
              f"(resposta vazia ou timeout). Prontuário sem entidades.")
        return [], (f"o modelo não respondeu após {MAX_TENTATIVAS} tentativas "
                    f"(timeout, erro de conexão ou resposta vazia)")

    try:
        entidades = _extrair_json_da_resposta(conteudo)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  [EXTRATOR-LLM] AVISO: resposta não interpretável como JSON ({e}).")
        return [], "a resposta do modelo não era um JSON válido"

    if not isinstance(entidades, list):
        print("  [EXTRATOR-LLM] AVISO: resposta não é uma lista. Ignorada.")
        return [], "a resposta do modelo não era uma lista de itens"

    validas = []
    rebaixadas = []
    for e in entidades:
        if not isinstance(e, dict):
            continue
        texto = str(e.get("texto", "")).strip()
        categoria = str(e.get("categoria", "")).strip().upper()
        if not texto or categoria not in CATEGORIAS_BUSCAVEIS:
            continue

        status = str(e.get("status", "")).strip().upper()
        if status != STATUS_NAO_REALIZADO:
            status = STATUS_REALIZADO

        if status == STATUS_REALIZADO and _verificar_status_no_texto(
            texto, texto_prontuario
        ):
            status = STATUS_NAO_REALIZADO
            rebaixadas.append(texto)

        validas.append({"texto": texto, "categoria": categoria, "status": status})

    if rebaixadas:
        print(f"  [EXTRATOR-LLM] {len(rebaixadas)} item(ns) rebaixado(s) para "
              f"NÃO REALIZADO pelo contexto do texto: {', '.join(rebaixadas)}")
    return validas, ""

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
    falha = ""

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
        entidades, falha = await _extrair_entidades_llm_com_status(estado["texto"])
    else:
        raise ValueError(f"EXTRATOR_ATIVO inválido: '{extrator}'. Use 'regras' ou 'llm'.")

    n_realizadas = sum(
        1 for e in entidades if e.get("status", STATUS_REALIZADO) == STATUS_REALIZADO
    )
    print(f"  [NER] ({extrator}) {len(entidades)} entidades extraídas "
          f"({n_realizadas} realizadas, {len(entidades) - n_realizadas} não realizadas).")
    if falha:
        print(f"  [NER] ATENÇÃO: extração falhou ({falha}). O relatório deste "
              f"prontuário vai sinalizar a falha.")
    return {**estado, "entidades_brutas": entidades, "falha_extracao": falha}


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
        "regra_documento": "Regra de documento",
        "regra_texto": "Regra de texto",
        "regra_texto_confirmada": "Regra de texto confirmada",
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
# CONSULTA AO SIGTAP - laço determinístico
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
              f"- marcado como sem código próprio no SIGTAP")
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
) -> tuple[list[dict], list[str], list[str], list[str]]:
    """
    Laço determinístico: uma busca por entidade, na ordem em que o extrator
    as devolveu. Devolve (resultados, nao_encontrados, nao_faturaveis,
    termos_ambiguos).

    A categoria vem direto da entidade (fonte determinística), sem passar
    pelo LLM -- eliminando a chance de o modelo trocá-la.
    """
    resultados: list[dict] = []
    nao_encontrados: list[str] = []
    nao_faturaveis: list[str] = []
    termos_ambiguos: list[str] = []

    for entidade in entidades:
        termo = _limpar_texto(str(entidade.get("texto", "")).strip())
        if not termo:
            continue
        categoria = str(entidade.get("categoria", "")).strip().upper()

        # Termo genérico demais para confiar numa correspondência automática
        # -- ver comentário de _TERMOS_GENERICOS_REVISAR. Nem chega a
        # consultar o SIGTAP: cai direto para revisão manual.
        if termo.lower() in _TERMOS_GENERICOS_REVISAR:
            print(f"    [Genérico - revisar] '{termo}' ({categoria or 'sem categoria'}) "
                  f"- termo curto demais para diferenciar entre códigos próximos")
            if termo not in termos_ambiguos:
                termos_ambiguos.append(termo)
            continue

        correspondencias, duracao = await _buscar_um_termo(
            ferramenta_busca, termo, categoria
        )
        _registrar_resultado(
            termo, categoria, correspondencias, duracao,
            resultados, nao_encontrados, nao_faturaveis,
        )

    return resultados, nao_encontrados, nao_faturaveis, termos_ambiguos


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

# ── Regras de faturamento por tipo de documento ─────────────────────────────
# Códigos que vêm do TIPO do documento, não de ação no texto. Etapa
# DESLIGÁVEL por USAR_REGRAS_DOCUMENTO, para comparar desempenho com/sem.
USAR_REGRAS_DOCUMENTO = os.getenv("USAR_REGRAS_DOCUMENTO", "false").strip().lower() == "true"

_COD_CONSULTA_NAO_MEDICO = "03.01.01.004-8"
_COD_CONSULTA_MEDICO = "03.01.01.017-0"
_COD_DIARIA_UTI = "08.02.01.008-3"

# Marcadores procurados SÓ NO CABEÇALHO (primeiras linhas com conteúdo).
# Antes a busca era no texto inteiro, e uma nota de enfermagem que citasse a
# "evolução médica" no corpo podia ser classificada como médica. Os não
# médicos são testados primeiro porque o cabeçalho tem um tipo só.
# "fisioterapia" sozinho cobre cabeçalhos reais como "EVOLUÇÃO FISIOTERAPIA
# – NOITE", que não casavam com "evolucao de fisioterapia".
_MARCADORES_NAO_MEDICO = [
    "evolucao de enfermagem",
    "enfermagem",
    "psicologia",
    "fisioterapia",
    "fonoaudiologia",
]
_MARCADORES_MEDICO = [
    "evolucao medica",
    "medica",
    "evolucao uti",
    "evolucao clinica",
]

# Modelo da evolução de fisioterapia no CORPO do texto. Caso real da planilha
# do HUB: uma evolução com cabeçalho "EVOLUÇÃO DIURNA" era de fisioterapia, e
# a regra genérica abaixo a classificava como médica.
_RX_MODELO_FISIOTERAPIA = re.compile(r"fisioterapia\s+(respiratoria|motora)\s*:")

# Estrutura típica da evolução médica no CORPO, para notas cujo cabeçalho não
# diz o tipo (ex.: começa com o nome do hospital ou com "# Lista de problemas").
# Na planilha do HUB, 45 evoluções sem tipo no cabeçalho tinham perfil de nota
# médica no gabarito (consulta de paciente internado em 56%, diária em 60%).
_RX_ESTRUTURA_MEDICA = re.compile(
    r"lista de problemas|hipoteses diagnosticas|\bstaff\b|\bm?r[1-3]\b|"
    r"sob orientacao|sob supervisao d[oa] dr"
)

_N_LINHAS_CABECALHO = 5
_RX_LINHA_SEPARADORA = re.compile(r"^[=_\-\s#*.~]+$")


def _cabecalho(texto: str, n_linhas: int = _N_LINHAS_CABECALHO) -> str:
    """Primeiras linhas com conteúdo, ignorando linhas só de ====, ____ etc."""
    linhas = []
    for linha in str(texto).splitlines():
        s = linha.strip()
        if not s or _RX_LINHA_SEPARADORA.match(s):
            continue
        linhas.append(s)
        if len(linhas) == n_linhas:
            break
    return " | ".join(linhas)


def _detectar_tipo_evolucao(texto_prontuario: str) -> str | None:
    """
    Decide o tipo de documento: 'medico', 'nao_medico' ou None.

    Ordem: (1) marcadores não médicos no cabeçalho; (2) marcadores médicos no
    cabeçalho; (3) modelo de fisioterapia no corpo; (4) cabeçalho genérico com
    "evolucao" conta como médico; (5) estrutura de nota médica no corpo.
    """
    cab = _normalizar_texto_simples(_cabecalho(texto_prontuario))
    corpo = _normalizar_texto_simples(texto_prontuario)
    for m in _MARCADORES_NAO_MEDICO:
        if re.search(rf"\b{re.escape(m)}\b", cab):
            return "nao_medico"
    for m in _MARCADORES_MEDICO:
        if re.search(rf"\b{re.escape(m)}\b", cab):
            return "medico"
    if _RX_MODELO_FISIOTERAPIA.search(corpo):
        return "nao_medico"
    if "evolucao" in cab:
        return "medico"
    if _RX_ESTRUTURA_MEDICA.search(corpo):
        return "medico"
    return None


async def _buscar_codigo_exato(ferramenta_busca_codigo, codigo: str) -> dict | None:
    """Chama buscar_por_codigo (MCP) para obter descrição e valores de um código."""
    if ferramenta_busca_codigo is None:
        return None
    try:
        resposta = await ferramenta_busca_codigo.ainvoke({"codigo": codigo})
    except Exception as e:
        print(f"  [REGRA] falha ao buscar valores do código {codigo}: {e}")
        return None
    if isinstance(resposta, list):
        normalizados = _normalizar_resultado_mcp(resposta)
        return normalizados[0] if normalizados else None
    try:
        dados = json.loads(resposta) if isinstance(resposta, str) else resposta
    except (json.JSONDecodeError, TypeError):
        return None
    return dados if isinstance(dados, dict) else None


async def _aplicar_regras_documento(ferramenta_busca_codigo, texto_prontuario: str) -> list[dict]:
    """
    Gera os códigos que vêm do TIPO do documento (consulta e diária), com os
    valores buscados na tabela. Retorna correspondências no mesmo formato da
    busca textual, marcadas com nivel='regra_documento'.
    """
    tipo = _detectar_tipo_evolucao(texto_prontuario)
    if tipo is None:
        return []
    if tipo == "nao_medico":
        codigos = [_COD_CONSULTA_NAO_MEDICO]
    else:
        codigos = [_COD_CONSULTA_MEDICO, _COD_DIARIA_UTI]

    resultados = []
    for codigo in codigos:
        dados = await _buscar_codigo_exato(ferramenta_busca_codigo, codigo)
        if dados:
            dados["nivel"] = "regra_documento"
            dados["score"] = 1.0
            dados["confianca"] = "alta"
            resultados.append({
                "termo_buscado": f"[regra: {tipo}]",
                "categoria": "PROCEDIMENTO",
                "correspondencias": [dados],
                "alternativas": [],
                "painel": False,
            })
    return resultados


# ── Regras de texto (regex + scoring) ──────────────────────────────────────
# Códigos com pista textual forte, definidos em src/agent/regras_texto.py e
# avaliados em src/analise/etapa3_regras_regex.py. Etapa DESLIGÁVEL por
# USAR_REGRAS_TEXTO, para comparar desempenho com/sem.
#
#  - modo "direta": o código entra no relatório (precisão no treino >= 0,60).
#  - modo "candidato": só entra se o extrator também tiver encontrado o item
#    como REALIZADO. Sem essa confirmação, vai para candidatos_regra, uma
#    lista de revisão. Motivo: nesses códigos a palavra aparece em evoluções
#    em que o procedimento não foi feito naquele dia (gaso transcrita, "HD"
#    no histórico, TQT já instalada), e o regex não distingue isso. Quem lê
#    o contexto é o extrator.
USAR_REGRAS_TEXTO = os.getenv("USAR_REGRAS_TEXTO", "false").strip().lower() == "true"

_COD_CURATIVO_GRAU_II = "04.01.01.001-5"
# Quando a regra de texto atribui o curativo grau II, resultados da busca
# textual que descrevem o mesmo ato saem do relatório, porque o ato já está
# coberto pela regra e a busca costuma errar o código.
#
# A remoção é pelo TERMO buscado (contém a palavra "curativo"), e não por uma
# lista de códigos. A primeira versão removia só o CURATIVO SIMPLES
# (03.01.10.028-4), que resolveu o HUB008 ("troca de curativo"), mas no
# HUB001 o extrator devolveu "curativo de ferida" e a busca levou para
# TRATAMENTO DE FERIDAS COM FITOTERÁPICO, que escapou da lista. Pelo termo,
# qualquer variação é coberta. Base: nas 420 evoluções de UTI do gabarito do
# HUB, todo curativo faturado foi grau II.
_RX_TERMO_CURATIVO = re.compile(r"\bcurativos?\b")


def _remover_curativo_textual(resultados: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Tira os resultados da busca textual cujo termo é um curativo. Resultados
    de regra (termo entre colchetes) nunca são removidos. Devolve
    (restantes, resultados removidos).
    """
    restantes, removidos = [], []
    for r in resultados:
        termo = str(r.get("termo_buscado", ""))
        if not termo.startswith("[") and _RX_TERMO_CURATIVO.search(regras_texto.normalizar(termo)):
            removidos.append(r)
        else:
            restantes.append(r)
    return restantes, removidos


def _codigos_ja_encontrados(resultados: list[dict]) -> set[str]:
    """Códigos (só dígitos) presentes nos resultados até aqui."""
    return {
        regras_texto.so_digitos(str(c.get("codigo", "")))
        for r in resultados
        for c in r.get("correspondencias", [])
        if isinstance(c, dict) and c.get("codigo")
    }


# Só ato confirma ato. MATERIAL fica de fora porque indica que o dispositivo
# existe, não que o procedimento foi feito: no HUB004, "tubo de traqueostomia"
# (MATERIAL) confirmava "cuidados com traqueostomia", e TQT já instalada era
# justamente a principal origem de falso positivo do regex.
_CATEGORIAS_QUE_CONFIRMAM = {"PROCEDIMENTO", "EXAME"}


def _entidade_confirma(disparo: dict, entidades_realizadas: list[dict]) -> str | None:
    """
    Devolve o texto da entidade REALIZADA que confirma um candidato, ou None.
    Só entidades de PROCEDIMENTO ou EXAME confirmam. A comparação é por
    palavra inteira, no texto normalizado da entidade.

    Limitação: a confirmação herda o status dado pelo extrator. Se ele marcar
    como realizado um procedimento histórico (ex.: TQT feita semanas antes),
    o candidato é confirmado indevidamente.
    """
    termos = regras_texto.REGRAS[disparo["codigo"]].get("confirmacao", ())
    for e in entidades_realizadas:
        if str(e.get("categoria", "")).strip().upper() not in _CATEGORIAS_QUE_CONFIRMAM:
            continue
        texto_ent = regras_texto.normalizar(e.get("texto", ""))
        for termo in termos:
            if re.search(rf"\b{re.escape(termo)}\b", texto_ent):
                return e.get("texto", "")
    return None


async def _correspondencia_de_regra(ferramenta_busca_codigo, disparo: dict, nivel: str) -> dict:
    """
    Monta a correspondência de um código vindo de regra de texto, com
    descrição e valores da tabela. Se a busca por código falhar, usa os dados
    do módulo de regras com valores zerados, para o código não sumir do
    relatório (o faturista vê o código e confere o valor).
    """
    dados = await _buscar_codigo_exato(ferramenta_busca_codigo, disparo["codigo"])
    if not dados:
        print(f"  [REGRA-TEXTO] AVISO: sem dados da tabela para {disparo['codigo']}; "
              f"incluído com valores zerados.")
        dados = {
            "codigo": disparo["codigo"], "descricao": disparo["nome"], "grupo": "",
            "vl_sh": 0.0, "vl_sa": 0.0, "vl_sp": 0.0, "vl_total": 0.0,
        }
    dados.setdefault("grupo", "")
    dados["nivel"] = nivel
    dados["score"] = 1.0
    # Precisão medida entre 0,69 e 0,88: boa, mas 1 em cada 4 a 5 sugestões
    # pode estar errada. "media" sinaliza que o faturista deve conferir.
    dados["confianca"] = "media"
    dados["pistas_regra"] = disparo["pistas"]
    dados["score_regra"] = disparo["score"]
    return dados


async def _aplicar_regras_texto(
    ferramenta_busca_codigo,
    texto_prontuario: str,
    entidades_realizadas: list[dict],
    codigos_existentes: set[str],
) -> tuple[list[dict], list[dict], bool]:
    """
    Aplica as regras de texto. Devolve (resultados, candidatos_nao_confirmados,
    curativo_por_regra).

    Códigos que a busca textual já encontrou não são repetidos: a deduplicação
    do relatório manteria só o primeiro, e um candidato já encontrado não
    precisa de revisão.
    """
    resultados: list[dict] = []
    candidatos: list[dict] = []
    curativo_por_regra = False

    for disparo in regras_texto.aplicar_regras_texto(texto_prontuario):
        codigo = disparo["codigo"]
        if regras_texto.so_digitos(codigo) in codigos_existentes:
            continue

        if disparo["modo"] == regras_texto.MODO_DIRETA:
            dados = await _correspondencia_de_regra(ferramenta_busca_codigo, disparo, "regra_texto")
            resultados.append({
                "termo_buscado": f"[regra de texto: {', '.join(disparo['pistas'])}]",
                "categoria": "PROCEDIMENTO",
                "correspondencias": [dados],
                "alternativas": [],
                "painel": False,
            })
            if codigo == _COD_CURATIVO_GRAU_II:
                curativo_por_regra = True
            continue

        confirmadora = _entidade_confirma(disparo, entidades_realizadas)
        if confirmadora:
            dados = await _correspondencia_de_regra(
                ferramenta_busca_codigo, disparo, "regra_texto_confirmada"
            )
            resultados.append({
                "termo_buscado": (f"[regra de texto confirmada por '{confirmadora}': "
                                  f"{', '.join(disparo['pistas'])}]"),
                "categoria": "PROCEDIMENTO",
                "correspondencias": [dados],
                "alternativas": [],
                "painel": False,
            })
        else:
            candidatos.append({
                "codigo": codigo,
                "descricao": disparo["nome"],
                "score": disparo["score"],
                "limiar": disparo["limiar"],
                "pistas": disparo["pistas"],
            })

    return resultados, candidatos, curativo_por_regra


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

    # Ferramenta de busca por código exato, usada pelas regras de documento
    # e de texto para obter descrição e valores.
    ferramenta_busca_codigo = next(
        (f for f in ferramentas if f.name == "buscar_por_codigo"), None
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
        termos_ambiguos: list[str] = []
    else:
        resultados, nao_encontrados, nao_faturaveis, termos_ambiguos = await _consultar_sigtap(
            entidades_buscaveis, ferramenta_busca
        )

    # Regras de documento (se ligadas): consulta e diária pelo tipo da nota.
    if USAR_REGRAS_DOCUMENTO:
        resultados_regra = await _aplicar_regras_documento(
            ferramenta_busca_codigo, estado.get("texto", "")
        )
        if resultados_regra:
            nomes = [r["correspondencias"][0].get("descricao", "") for r in resultados_regra]
            print(f"  [REGRA-DOC] {len(resultados_regra)} código(s) por regra de "
                  f"documento: {', '.join(nomes)}")
            resultados = resultados + resultados_regra

    # Regras de texto (se ligadas): regex + scoring sobre o texto da evolução.
    candidatos_regra: list[dict] = []
    substituidos_por_regra: list[dict] = []
    if USAR_REGRAS_TEXTO:
        resultados_texto, candidatos_regra, curativo_por_regra = await _aplicar_regras_texto(
            ferramenta_busca_codigo,
            estado.get("texto", ""),
            entidades_buscaveis,
            _codigos_ja_encontrados(resultados),
        )
        for r in resultados_texto:
            c = r["correspondencias"][0]
            print(f"    [{_rotulo_nivel_log(c.get('nivel', ''))}] [{c.get('confianca')}] "
                  f"{c.get('descricao', '')} ({c.get('codigo', '')}) "
                  f"<- {', '.join(c.get('pistas_regra', []))}")
        for cand in candidatos_regra:
            print(f"    [Regra de texto - candidato] {cand['descricao']} ({cand['codigo']}) "
                  f"score {cand['score']}/{cand['limiar']} sem confirmação do extrator "
                  f"<- {', '.join(cand['pistas'])}")
        # O código do curativo já foi atribuído pela regra: o termo genérico
        # "curativo" sai da revisão e o curativo simples da busca textual sai
        # do relatório, para o mesmo ato não aparecer duas vezes.
        if curativo_por_regra:
            termos_ambiguos = [t for t in termos_ambiguos if t.lower() != "curativo"]
            resultados, removidos = _remover_curativo_textual(resultados)
            if removidos:
                print(f"    [Regra de texto] curativo da busca textual substituído "
                      f"pelo grau II da regra: "
                      f"{', '.join(r.get('termo_buscado', '') for r in removidos)}")
                # Guardados para a avaliação poder reconstruir o resultado
                # "sem regras" a partir da mesma execução. Não vão para a
                # tabela nem para o valor do relatório.
                substituidos_por_regra = [
                    {
                        "termo": r.get("termo_buscado", ""),
                        "codigo": c.get("codigo", ""),
                        "descricao": c.get("descricao", ""),
                        "nivel": c.get("nivel", ""),
                    }
                    for r in removidos
                    for c in r.get("correspondencias", []) if isinstance(c, dict)
                ]

        resultados = resultados + resultados_texto

    baixa_confianca = [
        r["termo_buscado"] for r in resultados
        if any(c.get("confianca") == "baixa" for c in r["correspondencias"])
    ]
    print(f"  [SIGTAP] {len(resultados)} termo(s) com correspondência, "
          f"{len(nao_faturaveis)} sem código próprio, "
          f"{len(nao_encontrados)} sem correspondência, "
          f"{len(termos_ambiguos)} genérico(s) desviado(s) para revisão, "
          f"{len(candidatos_regra)} candidato(s) de regra sem confirmação, "
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
        "termos_ambiguos": termos_ambiguos,
        "candidatos_regra": candidatos_regra,
        "substituidos_por_regra": substituidos_por_regra,
        "entidades_descartadas": entidades_descartadas,
    }

def no_relatorio(estado: EstadoPipeline) -> EstadoPipeline:
    """Consolida os resultados num relatório estruturado."""
    print("  [RELATÓRIO] Gerando relatório...")

    codigos_encontrados = {}
    for resultado in estado["resultados_sigtap"]:
        # As alternativas são do RESULTADO (irmãs de "correspondencias"),
        # não de cada correspondência. Ficam penduradas no código principal
        # apenas como informação para conferência: não passam pela
        # deduplicação nem entram no valor faturado.
        alternativas = resultado.get("alternativas", [])
        for correspondencia in resultado.get("correspondencias", []):
            if not isinstance(correspondencia, dict) or "codigo" not in correspondencia:
                continue
            codigo = correspondencia["codigo"]
            if codigo not in codigos_encontrados:
                codigos_encontrados[codigo] = {
                    "codigo": codigo,
                    "descricao": correspondencia.get("descricao", ""),
                    "grupo": correspondencia.get("grupo", ""),
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
                    # Pistas da regra de texto que geraram o código (vazio se
                    # o código veio da busca textual ou da regra de documento).
                    "pistas_regra": correspondencia.get("pistas_regra", []),
                    # Outras hipóteses ranqueadas para o mesmo termo (2º, 3º
                    # candidatos), para o faturista escolher. Só informativas.
                    "alternativas": [
                        {
                            "codigo": a.get("codigo", ""),
                            "descricao": a.get("descricao", ""),
                            "vl_total": a.get("vl_total", 0.0),
                            "nivel": a.get("nivel", ""),
                            "confianca": a.get("confianca", ""),
                        }
                        for a in alternativas
                        if isinstance(a, dict) and a.get("codigo")
                    ],
                }

    codigos = list(codigos_encontrados.values())
    nao_realizados = estado.get("termos_nao_realizados", [])
    candidatos_regra = estado.get("candidatos_regra", [])

    relatorio = {
        "prontuario_id": estado["prontuario_id"],
        "data_processamento": datetime.now().isoformat(),
        # registra o modelo, o extrator e o modo de orquestração: um
        # resultado obtido com um modelo que depois sai de catálogo não é
        # reproduzível sem essa informação
        "modelo_utilizado": _descrever_modelo_atual(),
        "extrator": os.getenv("EXTRATOR_ATIVO", "regras").strip().lower(),
        "orquestracao": "llm" if ORQUESTRACAO_POR_LLM else "deterministica",
        "regras_documento": USAR_REGRAS_DOCUMENTO,
        "regras_texto": USAR_REGRAS_TEXTO,
        # Motivo da falha do extrator ("" se não falhou). Com falha, os
        # códigos do relatório vêm só das regras e a evolução precisa de
        # leitura manual.
        "falha_extracao": estado.get("falha_extracao", ""),
        "texto_prontuario": estado.get("texto", ""),
        "entidades_extraidas": [e.get("texto", "") for e in estado["entidades_brutas"]],
        "resumo": {
            "total_entidades_extraidas": len(estado["entidades_brutas"]),
            "total_codigos_sigtap": len(codigos),
            "total_nao_encontrados": len(estado.get("termos_nao_encontrados", [])),
            "total_nao_faturaveis": len(estado.get("termos_nao_faturaveis", [])),
            "total_nao_realizados": len(nao_realizados),
            "total_ambiguos": len(estado.get("termos_ambiguos", [])),
            "total_candidatos_regra": len(candidatos_regra),
            "total_baixa_confianca": sum(
                1 for c in codigos if c.get("confianca") == "baixa"
            ),
            "valor_total": round(sum(c.get("vl_total", 0.0) for c in codigos), 2),
        },
        "entidades_por_categoria": _agrupar_por_categoria(estado["entidades_brutas"]),
        "codigos_sigtap": codigos,
        # Cinco listas com significados distintos para quem confere:
        #  - nao_encontrados: a busca falhou, pode haver receita a cobrar
        #  - nao_faturaveis: o dicionário marcou como sem código próprio
        #  - nao_realizados: mencionados no prontuário mas não executados
        #  - ambiguos: termo genérico demais para diferenciar entre códigos
        #    próximos (ex: "curativo" sozinho); a busca nem chegou a rodar
        #  - candidatos_regra: a regra de texto achou indício do código, mas o
        #    extrator não confirmou que foi realizado; não entra no valor
        "termos_nao_encontrados": estado.get("termos_nao_encontrados", []),
        "termos_nao_faturaveis": estado.get("termos_nao_faturaveis", []),
        "termos_nao_realizados": nao_realizados,
        "termos_ambiguos": estado.get("termos_ambiguos", []),
        "candidatos_regra": candidatos_regra,
        # Resultados da busca textual trocados por uma regra (hoje, só o
        # curativo). Fora do valor; existem para a avaliação comparar o
        # resultado com e sem regras numa única execução.
        "substituidos_por_regra": estado.get("substituidos_por_regra", []),
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
        "termos_ambiguos": [],
        "candidatos_regra": [],
        "substituidos_por_regra": [],
        "falha_extracao": "",
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

    print(f"[CONFIG] Regras de documento: {'ligadas' if USAR_REGRAS_DOCUMENTO else 'desligadas'}; "
          f"regras de texto: {'ligadas' if USAR_REGRAS_TEXTO else 'desligadas'}.")

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