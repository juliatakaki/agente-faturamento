"""
Diagnóstico do nível 4 (fallback LLM): mostra a lista de candidatos que
SERIA enviada ao LLM para um termo, sem de fato chamar o LLM. Usado para
investigar se um candidato correto estava disponível na lista quando o
LLM escolheu uma resposta errada.

Uso:
    python diagnostico_candidatos.py "intubacao orotraqueal"
    python diagnostico_candidatos.py "reanimacao cardiopulmonar"
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))

from rapidfuzz import fuzz
import sigtap_server as srv

SCORE_MINIMO_CANDIDATOS = 50
MAX_CANDIDATOS = 30


def mostrar_candidatos(termo: str):
    tabela = srv._get_tabela()
    termo_norm = srv._normalizar(termo)

    scores = tabela["descricao_norm"].apply(
        lambda desc: fuzz.token_set_ratio(termo_norm, desc)
    )
    candidatos = tabela[scores >= SCORE_MINIMO_CANDIDATOS].copy()

    if candidatos.empty:
        print(f"Nenhum candidato encontrado para {termo!r} (nem o nível 4 teria opções).")
        return

    candidatos["_score"] = scores[scores >= SCORE_MINIMO_CANDIDATOS]
    candidatos = candidatos.sort_values("_score", ascending=False).head(MAX_CANDIDATOS)
    candidatos = candidatos.reset_index(drop=True)

    print(f"\nTermo buscado: {termo!r}")
    print(f"Total de candidatos (score >= {SCORE_MINIMO_CANDIDATOS}): {len(candidatos)}\n")
    print(f"{'idx':>4}  {'score':>6}  descricao")
    print("-" * 90)
    for i, row in candidatos.iterrows():
        print(f"{i:>4}  {row['_score']:>6.1f}  {row['descricao']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python diagnostico_candidatos.py "termo a investigar"')
        sys.exit(1)

    termo = sys.argv[1]
    mostrar_candidatos(termo)