"""
Teste isolado da extração por LLM de UM prontuário.
Uso (de dentro da pasta do projeto): python src/test/teste_extracao.py HUB010
"""
import sys
import json
import asyncio
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from pipeline import extrair_entidades_llm


async def main():
    if len(sys.argv) < 2:
        print("Uso: python src/test/teste_extracao.py <ID_DO_PRONTUARIO>")
        return

    alvo = sys.argv[1]

    caminho = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "prontuarios_hub.json"
    )
    with open(caminho, encoding="utf-8") as f:
        prontuarios = json.load(f)

    pront = next((p for p in prontuarios if p.get("id") == alvo), None)
    if pront is None:
        print(f"Prontuário {alvo} não encontrado em {caminho}.")
        return

    print(f"Testando extração do {alvo} "
          f"({len(pront['texto'])} caracteres de texto)...\n")

    entidades = await extrair_entidades_llm(pront["texto"])

    print(f"\n{len(entidades)} entidades extraídas:")
    for e in entidades:
        print(f"  [{e['categoria']}] {e['texto']} ({e['status']})")


if __name__ == "__main__":
    asyncio.run(main())