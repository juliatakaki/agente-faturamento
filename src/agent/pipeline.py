"""
Pipeline principal do agente de IA.
Fluxo: NER → refinamento LLM + consulta MCP/SIGTAP → geração do relatório.
Orquestrado com LangGraph.
"""

import os
import json
import sys
import asyncio
from datetime import datetime
from typing import TypedDict

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ner.extractor import construir_ner, extrair_entidades

load_dotenv()

# ── Tipos ──────────────────────────────────────────────────────────────────

class EstadoPipeline(TypedDict):
    prontuario_id: str
    texto: str
    entidades_brutas: list[dict]       # saída do NER
    entidades_refinadas: list[dict]    # saída do LLM (normalização)
    resultados_sigtap: list[dict]      # saída da consulta MCP
    termos_nao_encontrados: list[str]  # termos buscados sem correspondência
    relatorio: dict                    # relatório final


# ── Configuração ───────────────────────────────────────────────────────────

# Usa sys.executable (caminho do Python em uso) em vez de "python3" fixo,
# pois "python3" não existe no Windows -- isso causava o erro
# "Connection closed" ao iniciar o subprocesso do servidor MCP.
MCP_CONFIG = {
    "sigtap": {
        "command": sys.executable,
        "args": [
            os.path.join(os.path.dirname(__file__), "../mcp/sigtap_server.py")
        ],
        "transport": "stdio",
    }
}

NLP = construir_ner()


# ── Nós do grafo ───────────────────────────────────────────────────────────

def no_ner(estado: EstadoPipeline) -> EstadoPipeline:
    """Extrai entidades clínicas do texto com spaCy."""
    print(f"  [NER] Processando {estado['prontuario_id']}...")
    entidades = extrair_entidades(estado["texto"], NLP)
    print(f"  [NER] {len(entidades)} entidades extraídas.")
    return {**estado, "entidades_brutas": entidades}


def _limpar_texto(texto: str) -> str:
    """
    Corrige texto que veio com sequências unicode escapadas de forma literal
    (ex: a string contém os 6 caracteres '\\u00e3' em vez do caractere 'ã').
    Isso acontece quando o LLM gera esses escapes no meio do termo.

    Se a decodificação falhar, devolve o texto original sem quebrar.
    """
    if not isinstance(texto, str):
        return texto
    # só tenta decodificar se houver a marca de escape literal "\\u"
    if "\\u" in texto:
        try:
            return texto.encode("latin-1", "backslashreplace").decode("unicode_escape")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return texto
    return texto


def _expandir_termos(termo_bruto: str) -> list[str]:
    """
    Recebe o argumento 'termo' que o LLM passou para buscar_procedimento e
    devolve uma lista de termos individuais a buscar.

    Trata o caso (observado com llama3.2) em que o modelo agrupa vários
    termos num único argumento, em vez de chamar a ferramenta uma vez por
    termo. Exemplos que viram múltiplos termos:
        "[laparotomia exploradora, drenagem de abscesso, curativo]"
        "laparotomia exploradora, drenagem de abscesso, curativo"
    Um termo normal (sem vírgula) é devolvido como lista de um elemento.

    Também remove colchetes nas pontas e espaços extras de cada termo.
    """
    if not isinstance(termo_bruto, str):
        return []

    texto = termo_bruto.strip()
    if not texto:
        return []

    # remove colchetes externos, se o modelo formatou como lista "[...]"
    if texto.startswith("[") and texto.endswith("]"):
        texto = texto[1:-1].strip()

    # se houver vírgulas, trata como vários termos; senão, é um termo só
    if "," in texto:
        partes = [p.strip() for p in texto.split(",")]
    else:
        partes = [texto]

    # limpa cada termo e descarta vazios/duplicados, preservando a ordem
    vistos = set()
    termos = []
    for p in partes:
        limpo = _limpar_texto(p.strip().strip("[]").strip())
        if limpo and limpo.lower() not in vistos:
            vistos.add(limpo.lower())
            termos.append(limpo)

    return termos


def _rotulo_nivel_log(nivel: str) -> str:
    """Converte o código do nível (ex: 'nivel2') no rótulo usado no log."""
    nomes = {
        "nivel1": "Nível 1 - Exata",
        "nivel2": "Nível 2 - Parcial",
        "nivel3": "Nível 3 - Similaridade",
        "nivel4": "Nível 4 - LLM",
    }
    return nomes.get(nivel, nivel or "Nível ?")


def _normalizar_resultado_mcp(resultado_busca) -> list[dict]:
    """
    Normaliza a resposta da ferramenta MCP 'buscar_procedimento' para uma
    lista de dicionários (cada um com codigo, descricao, grupo, valores...).

    Formato real observado com langchain_mcp_adapters: uma LISTA de
    "envelopes", cada um no formato:
        {'type': 'text', 'text': '<json do procedimento>', 'id': '...'}
    onde o procedimento de verdade está dentro do campo 'text' como STRING
    JSON. Pode haver vários envelopes (até 3 resultados da busca).

    Também trata, por robustez: lista já de dicts-de-dados, string JSON
    pura, e mensagens de erro da ferramenta (que viram lista vazia).

    Sempre retorna uma lista (possivelmente vazia), nunca quebra.
    """
    if not resultado_busca:
        return []

    itens = resultado_busca if isinstance(resultado_busca, list) else [resultado_busca]

    saida = []
    for item in itens:
        # Envelope {'type': 'text', 'text': '<json>'} -> extrai e parseia o 'text'
        if isinstance(item, dict) and "text" in item and "codigo" not in item:
            texto = item.get("text", "")
            # ignora mensagens de erro da ferramenta (ex: "Error executing tool...")
            if isinstance(texto, str) and texto.lstrip().startswith("{"):
                parseado = _tentar_json(texto)
                saida.extend(parseado)
            continue

        # Já é o dict-de-dados (tem 'codigo') -> usa direto
        if isinstance(item, dict) and "codigo" in item:
            saida.append(item)
            continue

        # String JSON solta
        if isinstance(item, str):
            saida.extend(_tentar_json(item))
            continue

        # Objeto com atributo .text (content block tipado)
        texto_attr = getattr(item, "text", None)
        if isinstance(texto_attr, str) and texto_attr.lstrip().startswith("{"):
            saida.extend(_tentar_json(texto_attr))

    return saida


def _tentar_json(texto: str) -> list[dict]:
    """Tenta desserializar uma string JSON em lista de dicts. Retorna [] se falhar."""
    try:
        dados = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(dados, dict):
        return [dados]
    if isinstance(dados, list):
        return [d for d in dados if isinstance(d, dict)]
    return []


async def no_refinamento_e_sigtap(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Usa o LLM para normalizar entidades e o MCP para consultar o SIGTAP.
    Combina refinamento e consulta numa única chamada ao agente LLM com ferramentas.
    """
    print("  [LLM+MCP] Refinando entidades e consultando SIGTAP...")

    llm = ChatOllama(model="llama3.2", temperature=0)

    client = MultiServerMCPClient(MCP_CONFIG)
    ferramentas = await client.get_tools()
    llm_com_ferramentas = llm.bind_tools(ferramentas)

    entidades_json = json.dumps(
        estado["entidades_brutas"], ensure_ascii=False, indent=2
    )

    # IMPORTANTE: não usamos ChatPromptTemplate.format_messages() aqui.
    # O texto das entidades é um JSON, cheio de chaves { }, e o motor de
    # template do LangChain interpreta { } como marcadores de variável,
    # o que causa "KeyError" ao encontrar as chaves do JSON. Montamos as
    # mensagens diretamente (SystemMessage/HumanMessage), assim o conteúdo
    # dinâmico é tratado como texto literal, sem reprocessamento de chaves.
    sistema = """Você é um assistente especializado em faturamento hospitalar brasileiro.
Sua tarefa é:
1. Receber uma lista de entidades clínicas extraídas de um prontuário eletrônico.
2. Para cada entidade do tipo PROCEDIMENTO, EXAME ou MATERIAL, usar a ferramenta
   'buscar_procedimento' para encontrar o código SIGTAP correspondente.
3. Retornar um JSON com a lista de correspondências encontradas.

REGRAS IMPORTANTES:
- Foque apenas em PROCEDIMENTOS, EXAMES e MATERIAIS. Ignore MEDICAMENTOS.
- Use EXATAMENTE o campo "texto" da entidade como argumento da busca,
  sem traduzir, reformular ou abreviar. Por exemplo: se a entidade é
  "raio-x de tórax", chame buscar_procedimento(termo="raio-x de tórax").
- Se não encontrar correspondência, tente apenas com a palavra principal
  do texto (ex: "hemograma" ao invés de "hemograma completo").
- Nunca invente termos que não estejam no campo "texto" da entidade."""

    humano = f"""Prontuário: {estado['prontuario_id']}

Entidades extraídas:
{entidades_json}

Consulte o SIGTAP para cada entidade relevante e retorne as correspondências."""

    mensagens = [SystemMessage(content=sistema), HumanMessage(content=humano)]
    resposta = await llm_com_ferramentas.ainvoke(mensagens)

    # Processa chamadas de ferramentas, rastreando TANTO os termos que
    # retornaram correspondência quanto os que NÃO retornaram. Antes, os
    # termos sem resultado simplesmente eram descartados (o "if resultado_busca"
    # ignorava); agora eles são guardados em 'termos_nao_encontrados' para
    # alimentar a nota de verificação manual no relatório final.
    resultados = []
    nao_encontrados = []
    if hasattr(resposta, "tool_calls") and resposta.tool_calls:
        # ferramenta de busca (resolvida uma vez fora do loop)
        ferramenta_busca = next(
            (f for f in ferramentas if f.name == "buscar_procedimento"), None
        )

        for tool_call in resposta.tool_calls:
            if tool_call["name"] != "buscar_procedimento" or ferramenta_busca is None:
                continue

            termo_bruto = tool_call["args"].get("termo", "")

            # O llama3.2 às vezes desobedece a instrução e manda VÁRIOS termos
            # de uma vez, agrupados como uma "lista" num único argumento
            # (ex: "[laparotomia exploradora, drenagem de abscesso, ...]").
            # Isso fazia a ferramenta falhar e perder todos esses termos.
            # _expandir_termos detecta esse caso e quebra em termos individuais,
            # para que cada um seja buscado separadamente.
            for termo in _expandir_termos(termo_bruto):
                resultado_busca = await ferramenta_busca.ainvoke({"termo": termo})
                # A resposta vem como lista de envelopes {'type':'text','text': <json>}.
                correspondencias = _normalizar_resultado_mcp(resultado_busca)

                if correspondencias:
                    # buscar_procedimento retorna ate 3 candidatos ordenados por
                    # relevancia. Para o faturamento, consideramos apenas o
                    # primeiro (mais relevante) -- os demais sao alternativas
                    # que NAO foram necessariamente realizadas, e soma-las
                    # inflaria o valor com procedimentos que nao aconteceram.
                    melhor = correspondencias[0]
                    # log de diagnóstico: mostra em qual nível (camada de busca)
                    # o termo foi resolvido e a que procedimento SIGTAP foi ligado.
                    rotulo = _rotulo_nivel_log(melhor.get("nivel", ""))
                    print(f"    [{rotulo}] '{termo}' -> "
                          f"{melhor.get('descricao', '')} ({melhor.get('codigo', '')})")
                    resultados.append({
                        "termo_buscado": termo,
                        "correspondencias": [melhor],
                        # guarda as alternativas (sem entrar no total) para
                        # eventual conferencia manual, sem perder a informacao
                        "alternativas": correspondencias[1:],
                    })
                else:
                    print(f"    [Sem resultado] '{termo}'")
                    if termo and termo not in nao_encontrados:
                        nao_encontrados.append(termo)

    print(f"  [LLM+MCP] {len(resultados)} consultas SIGTAP realizadas, "
          f"{len(nao_encontrados)} termo(s) sem correspondência.")
    return {
        **estado,
        "resultados_sigtap": resultados,
        "termos_nao_encontrados": nao_encontrados,
    }


def no_relatorio(estado: EstadoPipeline) -> EstadoPipeline:
    """Consolida os resultados num relatório estruturado."""
    print("  [RELATÓRIO] Gerando relatório...")

    # Deduplica códigos encontrados, propagando também os valores faturáveis
    # (vl_sh, vl_sa, vl_sp, vl_total) que o MCP agora retorna para cada
    # correspondência. Antes, só codigo/descricao/grupo/origem eram guardados.
    codigos_encontrados = {}
    for resultado in estado["resultados_sigtap"]:
        for correspondencia in resultado.get("correspondencias", []):
            # segurança: ignora qualquer item que não seja um dict com 'codigo'
            if not isinstance(correspondencia, dict) or "codigo" not in correspondencia:
                continue
            codigo = correspondencia["codigo"]
            if codigo not in codigos_encontrados:
                codigos_encontrados[codigo] = {
                    "codigo": codigo,
                    "descricao": correspondencia["descricao"],
                    "grupo": correspondencia["grupo"],
                    "origem": resultado["termo_buscado"],
                    # valores em reais (o MCP já converte de centavos);
                    # usa .get com 0.0 como padrão por robustez, caso algum
                    # resultado venha sem os campos de valor.
                    "vl_sh": correspondencia.get("vl_sh", 0.0),
                    "vl_sa": correspondencia.get("vl_sa", 0.0),
                    "vl_sp": correspondencia.get("vl_sp", 0.0),
                    "vl_total": correspondencia.get("vl_total", 0.0),
                    # nível da busca que encontrou este código (nivel1 a nivel3)
                    "nivel": correspondencia.get("nivel", ""),
                }

    relatorio = {
        "prontuario_id": estado["prontuario_id"],
        "data_processamento": datetime.now().isoformat(),
        # texto original do prontuário e as entidades extraídas pelo NER,
        # usados pelo relatório para exibir a fonte com os termos destacados.
        "texto_prontuario": estado.get("texto", ""),
        "entidades_extraidas": [e.get("texto", "") for e in estado["entidades_brutas"]],
        "resumo": {
            "total_entidades_extraidas": len(estado["entidades_brutas"]),
            "total_codigos_sigtap": len(codigos_encontrados),
            "total_nao_encontrados": len(estado.get("termos_nao_encontrados", [])),
        },
        "entidades_por_categoria": _agrupar_por_categoria(estado["entidades_brutas"]),
        "codigos_sigtap": list(codigos_encontrados.values()),
        # lista de termos sem correspondência, usada pela nota do relatório
        "termos_nao_encontrados": estado.get("termos_nao_encontrados", []),
    }

    return {**estado, "relatorio": relatorio}


def _agrupar_por_categoria(entidades: list[dict]) -> dict:
    grupos: dict[str, list[str]] = {}
    for e in entidades:
        cat = e["categoria"]
        grupos.setdefault(cat, []).append(e["texto"])
    return grupos


# ── Construção do grafo ────────────────────────────────────────────────────

def construir_grafo() -> StateGraph:
    grafo = StateGraph(EstadoPipeline)
    grafo.add_node("ner", no_ner)
    grafo.add_node("refinamento_sigtap", no_refinamento_e_sigtap)
    grafo.add_node("relatorio", no_relatorio)

    grafo.set_entry_point("ner")
    grafo.add_edge("ner", "refinamento_sigtap")
    grafo.add_edge("refinamento_sigtap", "relatorio")
    grafo.add_edge("relatorio", END)

    return grafo.compile()


# ── Execução ───────────────────────────────────────────────────────────────

async def processar_prontuario(prontuario: dict) -> dict:
    """Processa um prontuário e retorna o relatório de faturamento."""
    grafo = construir_grafo()

    estado_inicial: EstadoPipeline = {
        "prontuario_id": prontuario["id"],
        "texto": prontuario["texto"],
        "entidades_brutas": [],
        "entidades_refinadas": [],
        "resultados_sigtap": [],
        "termos_nao_encontrados": [],
        "relatorio": {},
    }

    estado_final = await grafo.ainvoke(estado_inicial)
    return estado_final["relatorio"]


async def processar_lote(caminho_entrada: str, caminho_saida: str) -> list[dict]:
    """
    Processa todos os prontuários de um arquivo JSON de entrada e salva a
    lista consolidada de relatórios num arquivo JSON de saída -- que é
    exatamente o formato consumido por gerar_relatorio.py.

    Args:
        caminho_entrada: JSON com a lista de prontuários ({id, texto, ...}).
        caminho_saida:   onde gravar a lista de relatórios processados.

    Returns:
        A lista de relatórios (também gravada em caminho_saida).
    """
    with open(caminho_entrada, encoding="utf-8") as f:
        prontuarios = json.load(f)

    if isinstance(prontuarios, dict):
        prontuarios = [prontuarios]

    relatorios = []
    for i, prontuario in enumerate(prontuarios, start=1):
        print(f"\n[{i}/{len(prontuarios)}] Prontuário {prontuario.get('id', '?')}")
        relatorio = await processar_prontuario(prontuario)
        relatorios.append(relatorio)

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

    # garante que a pasta de saída existe
    os.makedirs(os.path.dirname(saida), exist_ok=True)

    asyncio.run(processar_lote(entrada, saida))