"""
Testa buscar_procedimento com varios termos reais, baseados nos padrões
de PROCEDIMENTO e EXAME já usados no extractor.py (NER). O objetivo é
medir cobertura (quantos termos encontram pelo menos 1 resultado) e
detectar resultados suspeitos (que não parecem ter relação com o termo).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))

from sigtap_server import _buscar_com_nivel

# Termos baseados nos PADROES de PROCEDIMENTO e EXAME do extractor.py
TERMOS = [
    "intubacao orotraqueal",
    "ventilacao mecanica invasiva",
    "ventilacao nao invasiva",
    "sedoanalgesia",
    "reanimacao cardiopulmonar",
    "laparotomia exploradora",
    "drenagem de abscesso",
    "hemodialise",
    "enxertia de pele",
    "curativo",
    "fisioterapia respiratoria",
    "fisioterapia motora",
    "hemotransfusao",
    "nutricao parenteral total",
    "nebulizacao",
    "reposicao volemica",
    "hemograma completo",
    "hemocultura",
    "gasometria arterial",
    "raio-x de torax",
    "eletrocardiograma",
    "troponina",
    "ecocardiograma transesofagico",
    "tomografia computadorizada de cranio",
    "tomografia de torax",
    "lactato",
    "procalcitonina",
    "ultrassom abdominal",
    "eletroencefalograma",
    "creatinina",
    "coagulograma",
]

print(f"Testando {len(TERMOS)} termos...\n")

contagem_por_nivel = {"nivel1": 0, "nivel2": 0, "nivel3": 0, "nivel4": 0, "vazio": 0}
termos_por_nivel = {"nivel1": [], "nivel2": [], "nivel3": [], "nivel4": [], "vazio": []}

NOME_NIVEL = {
    "nivel1": "Nível 1 (exata)",
    "nivel2": "Nível 2 (parcial)",
    "nivel3": "Nível 3 (fuzzy)",
    "nivel4": "Nível 4 (LLM)",
    "vazio": "Sem resultado",
}

for termo in TERMOS:
    resultados, nivel = _buscar_com_nivel(termo)
    contagem_por_nivel[nivel] += 1
    termos_por_nivel[nivel].append(termo)

    if not resultados.empty:
        principal = resultados.iloc[0]
        extra = f" (+{len(resultados)-1} outro(s))" if len(resultados) > 1 else ""
        print(f"[{NOME_NIVEL[nivel]:18}] {termo!r:42} -> {principal['descricao']} ({principal['codigo']}){extra}")
    else:
        print(f"[{NOME_NIVEL[nivel]:18}] {termo!r:42} -> nenhum resultado")

total = len(TERMOS)
com_resultado = total - contagem_por_nivel["vazio"]

print(f"\n{'='*70}")
print(f"Cobertura total: {com_resultado}/{total} termos encontraram resultado "
      f"({100*com_resultado/total:.0f}%)\n")

print("Distribuição por nível (qual nível resolveu cada termo):")
for nivel in ["nivel1", "nivel2", "nivel3", "nivel4", "vazio"]:
    qtd = contagem_por_nivel[nivel]
    pct = 100 * qtd / total
    print(f"  {NOME_NIVEL[nivel]:18}: {qtd:3} termos ({pct:5.1f}%)")

if termos_por_nivel["nivel3"]:
    print(f"\nTermos resolvidos pelo fuzzy (nível 3):")
    for t in termos_por_nivel["nivel3"]:
        print(f"  - {t}")

if termos_por_nivel["nivel4"]:
    print(f"\nTermos resolvidos pelo fallback LLM (nível 4):")
    for t in termos_por_nivel["nivel4"]:
        print(f"  - {t}")

if termos_por_nivel["vazio"]:
    print(f"\nTermos sem resultado:")
    for t in termos_por_nivel["vazio"]:
        print(f"  - {t}")