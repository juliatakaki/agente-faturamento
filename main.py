"""
main.py — Ponto de entrada único do protótipo.

Executa o fluxo completo de faturamento SUS de ponta a ponta:

    prontuários (JSON)
        -> NER (spaCy)
        -> refinamento LLM + consulta SIGTAP (MCP)
        -> consolidação (JSON de relatórios)
        -> geração do relatório final (.md e .pdf)

Uso:
    python main.py                          # usa os caminhos padrão
    python main.py --entrada dados.json     # outro arquivo de entrada
    python main.py --saida-relatorio rel    # outro nome de relatório

Padrões (relativos à raiz do projeto, onde este arquivo está):
    entrada          -> data/prontuarios.json
    json intermediário -> reports/relatorios_processados.json
    relatório final  -> reports/relatorio_sus(.md/.pdf)
"""

import os
import sys
import asyncio
import argparse

# Garante que a pasta src/ esteja no path para importar os módulos internos,
# independentemente do diretório de onde o script é chamado.
RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "src"))

from agent.pipeline import processar_lote
from agent import gerar_relatorio


def _caminhos_padrao():
    """Monta os caminhos padrão relativos à raiz do projeto."""
    return {
        "entrada": os.path.join(RAIZ, "data", "prontuarios.json"),
        "json_intermediario": os.path.join(RAIZ, "reports", "relatorios_processados.json"),
        "saida_relatorio": os.path.join(RAIZ, "reports", "relatorio_sus"),
    }


def _parse_args():
    padroes = _caminhos_padrao()
    parser = argparse.ArgumentParser(
        description="Executa o pipeline completo de faturamento SUS (NER -> LLM/MCP -> relatório)."
    )
    parser.add_argument(
        "--entrada", default=padroes["entrada"],
        help="JSON de prontuários de entrada (padrão: data/prontuarios.json)"
    )
    parser.add_argument(
        "--json-intermediario", default=padroes["json_intermediario"],
        help="Onde salvar o JSON de relatórios processados "
             "(padrão: reports/relatorios_processados.json)"
    )
    parser.add_argument(
        "--saida-relatorio", default=padroes["saida_relatorio"],
        help="Nome base (sem extensão) do relatório final .md/.pdf "
             "(padrão: reports/relatorio_sus)"
    )
    parser.add_argument(
        "--sem-pdf", action="store_true",
        help="Gera apenas o .md, pulando o PDF (útil se o reportlab não estiver instalado)."
    )
    return parser.parse_args()


async def executar(entrada, json_intermediario, saida_relatorio, gerar_pdf=True):
    """Roda o fluxo completo e retorna o caminho dos arquivos gerados."""

    # ── Etapa 1: pipeline (NER -> LLM/MCP -> JSON consolidado) ──────────────
    print("=" * 60)
    print("ETAPA 1/2 — Processando prontuários (NER + LLM + SIGTAP)")
    print("=" * 60)

    if not os.path.exists(entrada):
        raise FileNotFoundError(
            f"Arquivo de entrada não encontrado: {entrada}\n"
            f"Verifique se os prontuários estão em data/prontuarios.json "
            f"ou informe outro caminho com --entrada."
        )

    os.makedirs(os.path.dirname(json_intermediario), exist_ok=True)
    relatorios = await processar_lote(entrada, json_intermediario)

    # ── Etapa 2: geração do relatório final (.md e .pdf) ───────────────────
    print()
    print("=" * 60)
    print("ETAPA 2/2 — Gerando relatório de faturamento")
    print("=" * 60)

    os.makedirs(os.path.dirname(saida_relatorio), exist_ok=True)

    # Markdown (sempre)
    md = gerar_relatorio.gerar_markdown(relatorios)
    caminho_md = f"{saida_relatorio}.md"
    with open(caminho_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Gerado: {caminho_md}")

    # PDF (opcional — depende do reportlab)
    caminho_pdf = None
    if gerar_pdf:
        try:
            caminho_pdf = f"{saida_relatorio}.pdf"
            gerar_relatorio.gerar_pdf(relatorios, caminho_pdf)
            print(f"Gerado: {caminho_pdf}")
        except ImportError:
            print("AVISO: reportlab não instalado — PDF não gerado. "
                  "Instale com 'pip install reportlab' ou use --sem-pdf. "
                  "O relatório .md foi gerado normalmente.")
            caminho_pdf = None

    return caminho_md, caminho_pdf


def main():
    args = _parse_args()

    caminho_md, caminho_pdf = asyncio.run(
        executar(
            entrada=args.entrada,
            json_intermediario=args.json_intermediario,
            saida_relatorio=args.saida_relatorio,
            gerar_pdf=not args.sem_pdf,
        )
    )

    print()
    print("=" * 60)
    print("CONCLUÍDO")
    print("=" * 60)
    print(f"Relatório Markdown: {caminho_md}")
    if caminho_pdf:
        print(f"Relatório PDF:      {caminho_pdf}")
    print(f"JSON processado:    {args.json_intermediario}")


if __name__ == "__main__":
    main()