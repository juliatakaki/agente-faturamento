"""
Servidor MCP para consulta à tabela SIGTAP.
Expõe duas ferramentas:
  - buscar_procedimento: busca por texto livre no SIGTAP
  - buscar_por_codigo:   busca pelo código exato
"""

import os
import unicodedata
import pandas as pd
from mcp.server.fastmcp import FastMCP

# ── Inicialização ──────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SIGTAP_PATH = os.path.join(BASE_DIR, "data", "sigtap_mock.csv")

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
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace("-", " ")
    return texto


def _get_tabela() -> pd.DataFrame:
    global _tabela
    if _tabela is None:
        _tabela = pd.read_csv(SIGTAP_PATH, dtype=str)
        # Cria coluna normalizada para busca
        _tabela["descricao_norm"] = _tabela["descricao"].apply(_normalizar)
    return _tabela


# ── Ferramentas MCP ────────────────────────────────────────────────────────

@mcp.tool()
def buscar_procedimento(termo: str) -> list[dict]:
    """
    Busca procedimentos na tabela SIGTAP pelo nome ou descrição.

    Args:
        termo: Texto a buscar (ex: 'intubacao orotraqueal', 'hemograma').

    Returns:
        Lista de até 3 procedimentos com codigo, descricao e grupo.
    """
    tabela = _get_tabela()
    termo_norm = _normalizar(termo)

    # Busca por cada palavra do termo normalizado (AND: todas devem aparecer)
    palavras = [p for p in termo_norm.split() if len(p) > 2]
    if not palavras:
        palavras = [termo_norm]

    mascara = tabela["descricao_norm"].apply(
        lambda desc: all(p in desc for p in palavras)
    )
    resultados = tabela[mascara]

    # Se não encontrou com AND, tenta com cada palavra isolada (OR parcial)
    if resultados.empty:
        for palavra in palavras:
            mascara_parcial = tabela["descricao_norm"].str.contains(
                palavra, na=False
            )
            resultados = tabela[mascara_parcial]
            if not resultados.empty:
                break

    return resultados[["codigo", "descricao", "grupo"]].head(3).to_dict("records")


@mcp.tool()
def buscar_por_codigo(codigo: str) -> dict | None:
    """
    Retorna o procedimento SIGTAP pelo código exato.

    Args:
        codigo: Código SIGTAP (ex: '04.01.01.004-3').

    Returns:
        Dicionário com codigo, descricao e grupo, ou None se não encontrado.
    """
    tabela = _get_tabela()
    resultado = tabela[tabela["codigo"] == codigo]
    if resultado.empty:
        return None
    return resultado[["codigo", "descricao", "grupo"]].iloc[0].to_dict()


# ── Ponto de entrada ───────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")