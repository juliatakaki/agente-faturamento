"""
Ponto de entrada do protótipo.
Processa todos os prontuários e salva os relatórios em reports/.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from agent.pipeline import processar_prontuario

BASE_DIR = os.path.dirname(__file__)
PRONTUARIOS_PATH = os.path.join(BASE_DIR, "data", "prontuarios.json")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


async def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)

    with open(PRONTUARIOS_PATH, encoding="utf-8") as f:
        prontuarios = json.load(f)

    print(f"Iniciando processamento de {len(prontuarios)} prontuários...\n")

    relatorios = []

    for prontuario in prontuarios:
        print(f"Processando {prontuario['id']}...")
        relatorio = await processar_prontuario(prontuario)
        relatorios.append(relatorio)

        # Salva relatório individual
        path_individual = os.path.join(REPORTS_DIR, f"{prontuario['id']}.json")
        with open(path_individual, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)

        print(f"  ✓ {relatorio['resumo']['total_codigos_sigtap']} códigos SIGTAP identificados\n")

    # Salva relatório consolidado
    path_consolidado = os.path.join(REPORTS_DIR, "relatorio_consolidado.json")
    with open(path_consolidado, "w", encoding="utf-8") as f:
        json.dump(relatorios, f, ensure_ascii=False, indent=2)

    print(f"\nProcessamento concluído.")
    print(f"Relatórios salvos em: {REPORTS_DIR}/")
    print(f"Relatório consolidado: {path_consolidado}")


if __name__ == "__main__":
    asyncio.run(main())