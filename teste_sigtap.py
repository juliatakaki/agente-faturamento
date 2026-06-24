"""
3. Consulta os procedimentos na tabela SIGTAP
Script para testar a busca de procedimentos na tabela SIGTAP.
Envia os termos identificados e exibe os códigos e descrições
dos procedimentos encontrados.
"""

import unicodedata, pandas as pd

def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace("-", " ")
    return texto

tabela = pd.read_csv("data/sigtap_mock.csv", dtype=str)
tabela["descricao_norm"] = tabela["descricao"].apply(normalizar)

termos = [
    "intubação orotraqueal",
    "raio-x de tórax",
    "hemograma completo",
    "cateter venoso central",
    "hemodiálise",
]

for termo in termos:
    termo_norm = normalizar(termo)
    palavras = [p for p in termo_norm.split() if len(p) > 2]
    mascara = tabela["descricao_norm"].apply(
        lambda d: all(p in d for p in palavras)
    )
    resultado = tabela[mascara]
    if not resultado.empty:
        r = resultado.iloc[0]
        print(f"✓ {termo} → {r['codigo']} | {r['descricao']}")
    else:
        print(f"✗ {termo} → não encontrado")