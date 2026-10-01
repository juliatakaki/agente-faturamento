"""
Calcula o recall do sistema contra o gabarito (padrão-ouro).

Recall = dos códigos que o gabarito diz que deveriam ser faturados,
quantos o sistema encontrou.

Mede em duas variações:
  - top-1: conta acerto quando o código do gabarito é o candidato ESCOLHIDO
           pelo sistema (a 1ª opção de algum termo).
  - top-3: conta acerto quando o código do gabarito é o escolhido OU uma das
           alternativas ranqueadas daquele termo (2ª/3ª). Mede o quanto o
           ranqueamento ajuda o faturista, que vê as 3 opções.

Uso:
    python calcular_recall.py gabarito.json relatorios_processados.json
"""
import sys
import json


def normalizar_codigo(codigo: str) -> str:
    """Deixa só os dígitos, para comparar sem depender da formatação."""
    return "".join(c for c in str(codigo) if c.isdigit())


def codigos_do_sistema(relatorio_pront: dict):
    """
    Retorna dois conjuntos de códigos (normalizados) para um prontuário:
      - escolhidos: os códigos que o sistema selecionou (top-1)
      - com_alternativas: os escolhidos MAIS as alternativas (top-3)
    """
    escolhidos = set()
    com_alternativas = set()
    for c in relatorio_pront.get("codigos_sigtap", []):
        cod = normalizar_codigo(c.get("codigo", ""))
        if cod:
            escolhidos.add(cod)
            com_alternativas.add(cod)
        for alt in c.get("alternativas", []):
            cod_alt = normalizar_codigo(alt.get("codigo", ""))
            if cod_alt:
                com_alternativas.add(cod_alt)
    return escolhidos, com_alternativas


def main():
    if len(sys.argv) < 3:
        print("Uso: python calcular_recall.py <gabarito.json> <relatorios_processados.json>")
        return

    with open(sys.argv[1], encoding="utf-8") as f:
        gab = json.load(f)
    with open(sys.argv[2], encoding="utf-8") as f:
        rel = json.load(f)

    # indexa a saída do sistema por prontuário
    if isinstance(rel, dict):
        rel = [rel]
    sistema_por_id = {r.get("prontuario_id"): r for r in rel}

    gabarito = gab.get("gabarito", gab if isinstance(gab, list) else [])

    total_gab = 0
    total_top1 = 0
    total_top3 = 0

    print(f"{'Prontuário':<12} {'Gab':>4} {'Top-1':>6} {'Top-3':>6}   Códigos do gabarito não achados (top-3)")
    print("-" * 90)

    for item in gabarito:
        pid = item.get("prontuario_id")
        cods_gab = [normalizar_codigo(c["codigo"]) for c in item.get("codigos", [])]
        n_gab = len(cods_gab)
        total_gab += n_gab

        rel_pront = sistema_por_id.get(pid)
        if rel_pront is None:
            print(f"{pid:<12} {n_gab:>4} {'—':>6} {'—':>6}   (prontuário ausente na saída do sistema)")
            continue

        escolhidos, com_alt = codigos_do_sistema(rel_pront)

        achados_top1 = [c for c in cods_gab if c in escolhidos]
        achados_top3 = [c for c in cods_gab if c in com_alt]
        nao_achados = [c for c in cods_gab if c not in com_alt]

        total_top1 += len(achados_top1)
        total_top3 += len(achados_top3)

        # descrições dos não achados, para leitura
        desc_nao = []
        for c in item.get("codigos", []):
            if normalizar_codigo(c["codigo"]) in nao_achados:
                desc_nao.append(c.get("descricao", c["codigo"])[:35])

        print(f"{pid:<12} {n_gab:>4} {len(achados_top1):>6} {len(achados_top3):>6}   "
              + "; ".join(desc_nao))

    print("-" * 90)
    r1 = total_top1 / total_gab if total_gab else 0
    r3 = total_top3 / total_gab if total_gab else 0
    print(f"\nTOTAL de códigos no gabarito: {total_gab}")
    print(f"Recall top-1 (código escolhido):     {total_top1}/{total_gab} = {r1:.1%}")
    print(f"Recall top-3 (escolhido + alternativas): {total_top3}/{total_gab} = {r3:.1%}")
    print(f"\nGanho do ranqueamento (top-3 - top-1): {(r3-r1):.1%}")


if __name__ == "__main__":
    main()
