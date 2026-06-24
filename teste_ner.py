"""
2. Processa os textos dos prontuários
Script para testar a extração de entidades dos prontuários.
Lê os textos dos pacientes e exibe as entidades médicas
identificadas pelo modelo NER.
"""

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
        print(f"  [{e['categoria']}] {e['texto']}")# Esse script pega os prontuários de teste e mostra quais entidades
# (procedimentos, exames, etc.) o spaCy conseguiu identificar em cada um.

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