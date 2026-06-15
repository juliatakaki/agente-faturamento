import json, sys
sys.path.insert(0, "src")
from ner.extractor import construir_ner, extrair_entidades

nlp = construir_ner()

with open("data/prontuarios.json", encoding="utf-8") as f:
    prontuarios = json.load(f)

for p in prontuarios:
    entidades = extrair_entidades(p["texto"], nlp)
    print(f"\n[{p['id']}] {len(entidades)} entidades:")
    for e in entidades:
        print(f"  [{e['categoria']}] {e['texto']}")