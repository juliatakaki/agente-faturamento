"""
Pipeline principal do agente de IA.
Fluxo: NER → refinamento LLM + consulta MCP/SIGTAP → geração do relatório.
Orquestrado com LangGraph.
"""

import os
import json
import sys
from datetime import datetime
from typing import TypedDict

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.prompts import ChatPromptTemplate
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
    relatorio: dict                    # relatório final


# ── Configuração ───────────────────────────────────────────────────────────

MCP_CONFIG = {
    "sigtap": {
        "command": "python3",
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


async def no_refinamento_e_sigtap(estado: EstadoPipeline) -> EstadoPipeline:
    """
    Usa o LLM para normalizar entidades e o MCP para consultar o SIGTAP.
    Combina refinamento e consulta numa única chamada ao agente LLM com ferramentas.
    """
    print("  [LLM+MCP] Refinando entidades e consultando SIGTAP...")

    llm = ChatOllama(model="llama3.2", temperature=0)

    async with MultiServerMCPClient(MCP_CONFIG) as client:
        ferramentas = client.get_tools()
        llm_com_ferramentas = llm.bind_tools(ferramentas)

        entidades_json = json.dumps(
            estado["entidades_brutas"], ensure_ascii=False, indent=2
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um assistente especializado em faturamento hospitalar brasileiro.
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
- Nunca invente termos que não estejam no campo "texto" da entidade."""),
            ("human", f"""Prontuário: {estado['prontuario_id']}

Entidades extraídas:
{entidades_json}

Consulte o SIGTAP para cada entidade relevante e retorne as correspondências.""")
        ])

        mensagens = prompt.format_messages()
        resposta = await llm_com_ferramentas.ainvoke(mensagens)

        # Processa chamadas de ferramentas
        resultados = []
        if hasattr(resposta, "tool_calls") and resposta.tool_calls:
            for tool_call in resposta.tool_calls:
                if tool_call["name"] == "buscar_procedimento":
                    termo = tool_call["args"].get("termo", "")
                    # Executa a ferramenta
                    for ferramenta in ferramentas:
                        if ferramenta.name == "buscar_procedimento":
                            resultado_busca = await ferramenta.ainvoke(
                                {"termo": termo}
                            )
                            if resultado_busca:
                                resultados.append({
                                    "termo_buscado": termo,
                                    "correspondencias": resultado_busca
                                })
                            break

        print(f"  [LLM+MCP] {len(resultados)} consultas SIGTAP realizadas.")
        return {**estado, "resultados_sigtap": resultados}


def no_relatorio(estado: EstadoPipeline) -> EstadoPipeline:
    """Consolida os resultados num relatório estruturado."""
    print("  [RELATÓRIO] Gerando relatório...")

    # Deduplica códigos encontrados
    codigos_encontrados = {}
    for resultado in estado["resultados_sigtap"]:
        for correspondencia in resultado.get("correspondencias", []):
            codigo = correspondencia["codigo"]
            if codigo not in codigos_encontrados:
                codigos_encontrados[codigo] = {
                    "codigo": codigo,
                    "descricao": correspondencia["descricao"],
                    "grupo": correspondencia["grupo"],
                    "origem": resultado["termo_buscado"]
                }

    relatorio = {
        "prontuario_id": estado["prontuario_id"],
        "data_processamento": datetime.now().isoformat(),
        "resumo": {
            "total_entidades_extraídas": len(estado["entidades_brutas"]),
            "total_codigos_sigtap": len(codigos_encontrados),
        },
        "entidades_por_categoria": _agrupar_por_categoria(estado["entidades_brutas"]),
        "codigos_sigtap": list(codigos_encontrados.values()),
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
        "relatorio": {},
    }

    estado_final = await grafo.ainvoke(estado_inicial)
    return estado_final["relatorio"]