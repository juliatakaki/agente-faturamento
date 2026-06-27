"""
Testa buscar_procedimento com varios termos reais, baseados nos padrões
de PROCEDIMENTO e EXAME já usados no extractor.py (NER). O objetivo é
medir cobertura (quantos termos encontram pelo menos 1 resultado) e
detectar resultados suspeitos (que não parecem ter relação com o termo).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))

from sigtap_server import buscar_procedimento

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

sem_resultado = []
com_resultado = []

for termo in TERMOS:
    resultados = buscar_procedimento(termo)
    if resultados:
        com_resultado.append(termo)
        principal = resultados[0]
        print(f"[OK]    {termo!r:45} -> {principal['descricao']} ({principal['codigo']})")
        if len(resultados) > 1:
            for extra in resultados[1:]:
                print(f"                                              ...tambem: {extra['descricao']}")
    else:
        sem_resultado.append(termo)
        print(f"[VAZIO] {termo!r:45} -> nenhum resultado")

print(f"\n{'='*70}")
print(f"Cobertura: {len(com_resultado)}/{len(TERMOS)} termos encontraram resultado "
      f"({100*len(com_resultado)/len(TERMOS):.0f}%)")
if sem_resultado:
    print(f"\nSem resultado:")
    for t in sem_resultado:
        print(f"  - {t}")