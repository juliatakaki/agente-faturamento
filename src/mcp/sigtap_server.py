"""
Servidor MCP para consulta à tabela SIGTAP.
Expõe duas ferramentas:
  - buscar_procedimento: busca por texto livre no SIGTAP
  - buscar_por_codigo:   busca pelo código exato

Fonte de dados: tabela SIGTAP real (DATASUS), reduzida com descrições.
Colunas relevantes usadas: codigo_procedimento, no_procedimento, no_grupo.
"""

import os
import unicodedata
import pandas as pd
from rapidfuzz import fuzz
from mcp.server.fastmcp import FastMCP

# ── Inicialização ──────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SIGTAP_PATH = os.path.join(BASE_DIR, "data", "sigtap.csv")

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


def _formatar_codigo(codigo_int: int) -> str:
    """
    Formata o código numérico do SIGTAP no padrão oficial com pontos e hífen.
    Ex: 202020380 -> 02.02.02.038-0
    """
    codigo_str = str(int(codigo_int)).zfill(10)
    return (
        f"{codigo_str[0:2]}.{codigo_str[2:4]}.{codigo_str[4:6]}."
        f"{codigo_str[6:9]}-{codigo_str[9]}"
    )


def _get_tabela() -> pd.DataFrame:
    global _tabela
    if _tabela is None:
        bruta = pd.read_csv(SIGTAP_PATH, dtype={"codigo_procedimento": "Int64"})

        # Seleciona e renomeia apenas as colunas relevantes para a busca,
        # mantendo a mesma interface usada no restante do pipeline.
        tabela = bruta[["codigo_procedimento", "no_procedimento", "no_grupo"]].copy()
        tabela = tabela.rename(columns={
            "codigo_procedimento": "codigo_bruto",
            "no_procedimento": "descricao",
            "no_grupo": "grupo",
        })

        tabela["codigo"] = tabela["codigo_bruto"].apply(_formatar_codigo)
        tabela["descricao_norm"] = tabela["descricao"].apply(_normalizar)

        _tabela = tabela

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

    # Nível 1 — busca exata: todas as palavras do termo aparecem na descrição
    mascara = tabela["descricao_norm"].apply(
        lambda desc: all(p in desc for p in palavras)
    )
    resultados = tabela[mascara]

    # Nível 2 — busca parcial: ao menos uma palavra aparece na descrição
    if resultados.empty:
        for palavra in palavras:
            mascara_parcial = tabela["descricao_norm"].str.contains(
                palavra, na=False
            )
            resultados = tabela[mascara_parcial]
            if not resultados.empty:
                break

    # Nível 3 — busca por similaridade (rapidfuzz): cobre erros de digitação
    # e variações que a busca por substring não captura (ex: "sor" vs "soro").
    #
    # NOTA: desativado nesta versão de demonstração. A tabela SIGTAP utilizada
    # é um recorte reduzido (909 procedimentos) e não contém diversos itens
    # comuns em UTI (ex: intubação, ventilação mecânica, hemotransfusão).
    # Nessas condições, fuzz.partial_ratio tende a aproximar substrings sem
    # relação semântica real com o termo buscado (ex: "reposição volêmica"
    # casando com "molde auricular (reposição)"), o que produziria
    # correspondências incorretas na demonstração. Reativar quando a tabela
    # SIGTAP completa estiver disponível, no TCC 2.
    USAR_FUZZY = False
    if resultados.empty and USAR_FUZZY:
        scores = tabela["descricao_norm"].apply(
            lambda desc: fuzz.partial_ratio(termo_norm, desc)
        )
        SCORE_MINIMO = 87  # limiar mais estrito: evita falsos positivos quando a
                            # tabela (reduzida) não contém o procedimento procurado
        candidatos = tabela[scores >= SCORE_MINIMO].copy()
        if not candidatos.empty:
            candidatos["_score"] = scores[scores >= SCORE_MINIMO]
            resultados = candidatos.sort_values("_score", ascending=False)

    return resultados[["codigo", "descricao", "grupo"]].head(3).to_dict("records")


@mcp.tool()
def buscar_por_codigo(codigo: str) -> dict | None:
    """
    Retorna o procedimento SIGTAP pelo código exato.

    Args:
        codigo: Código SIGTAP no formato oficial (ex: '02.02.02.038-0').

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