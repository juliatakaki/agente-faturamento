"""
gerar_relatorio.py

Lê o JSON com os prontuários já processados pelo pipeline (lista de
relatórios por prontuário) e gera um relatório de faturamento consolidado
em dois formatos: Markdown (.md) e PDF.

O relatório, por prontuário, lista cada procedimento faturável encontrado
com seus três componentes de valor (SH, SA, SP) e o total, soma o valor do
prontuário, e ao final do prontuário inclui uma NOTA listando os termos
clínicos que foram identificados no prontuário mas não puderam ser
vinculados a um código SIGTAP (ex: "coagulograma"), sinalizando que
precisam de conferência manual.

Uso:
    python gerar_relatorio.py entrada.json
    python gerar_relatorio.py entrada.json --saida relatorio_sus

Gera: <saida>.md e <saida>.pdf  (padrão: relatorio_faturamento.md/.pdf)
"""

import sys
import json
import argparse
from datetime import datetime


def formatar_reais(valor: float) -> str:
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    inteiro, centavos = f"{valor:.2f}".split(".")
    # insere separador de milhar (ponto)
    inteiro_com_milhar = ""
    while len(inteiro) > 3:
        inteiro_com_milhar = "." + inteiro[-3:] + inteiro_com_milhar
        inteiro = inteiro[:-3]
    inteiro_com_milhar = inteiro + inteiro_com_milhar
    return f"R$ {inteiro_com_milhar},{centavos}"


def gerar_markdown(prontuarios: list[dict]) -> str:
    """Monta o conteúdo do relatório em Markdown."""
    linhas = []
    linhas.append("# Relatório de Faturamento SUS - SIGTAP")
    linhas.append("")
    data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")
    linhas.append(f"**Data de geração:** {data_geracao}  ")
    linhas.append(f"**Total de prontuários processados:** {len(prontuarios)}")
    linhas.append("")

    total_geral = 0.0
    total_procedimentos = 0
    total_nao_encontrados = 0

    for pront in prontuarios:
        pront_id = pront.get("prontuario_id", "(sem identificação)")
        codigos = pront.get("codigos_sigtap", [])
        nao_encontrados = pront.get("termos_nao_encontrados", [])

        linhas.append("---")
        linhas.append("")
        linhas.append(f"## Prontuário: {pront_id}")
        linhas.append("")

        if codigos:
            # Cabeçalho da tabela
            linhas.append("| Código SIGTAP | Procedimento | SH | SA | SP | Total |")
            linhas.append("|---|---|---:|---:|---:|---:|")

            subtotal = 0.0
            for c in codigos:
                vl_sh = c.get("vl_sh", 0.0)
                vl_sa = c.get("vl_sa", 0.0)
                vl_sp = c.get("vl_sp", 0.0)
                vl_total = c.get("vl_total", vl_sh + vl_sa + vl_sp)
                subtotal += vl_total
                total_procedimentos += 1

                # escapa o pipe em descrições, se houver, para nao quebrar a tabela
                descricao = str(c.get("descricao", "")).replace("|", "/")
                linhas.append(
                    f"| {c.get('codigo', '')} | {descricao} | "
                    f"{formatar_reais(vl_sh)} | {formatar_reais(vl_sa)} | "
                    f"{formatar_reais(vl_sp)} | {formatar_reais(vl_total)} |"
                )

            linhas.append("")
            linhas.append(f"**Subtotal do prontuário {pront_id}: {formatar_reais(subtotal)}**")
            linhas.append("")
            total_geral += subtotal
        else:
            linhas.append("_Nenhum procedimento faturável foi vinculado a este prontuário._")
            linhas.append("")

        # Nota de termos não encontrados (verificação manual)
        if nao_encontrados:
            total_nao_encontrados += len(nao_encontrados)
            linhas.append("> **Nota - verificação manual necessária:**  ")
            linhas.append(
                "> Os seguintes termos clínicos foram identificados no prontuário, "
                "mas não puderam ser vinculados automaticamente a um código SIGTAP. "
                "Recomenda-se conferência manual por um faturista:"
            )
            linhas.append(">")
            for termo in nao_encontrados:
                linhas.append(f"> - {termo}")
            linhas.append("")

    # Resumo consolidado no fim
    linhas.append("---")
    linhas.append("")
    linhas.append("## Resumo Consolidado")
    linhas.append("")
    linhas.append(f"- **Prontuários processados:** {len(prontuarios)}")
    linhas.append(f"- **Total de procedimentos faturáveis:** {total_procedimentos}")
    linhas.append(f"- **Termos pendentes de verificação manual:** {total_nao_encontrados}")
    linhas.append(f"- **VALOR TOTAL A FATURAR:** {formatar_reais(total_geral)}")
    linhas.append("")
    linhas.append(
        "_SH = Serviço Hospitalar, SA = Serviço Ambulatorial, "
        "SP = Serviço Profissional. Valores conforme tabela SIGTAP/DATASUS._"
    )
    linhas.append("")

    return "\n".join(linhas)


def _normalizar_basico(texto: str) -> str:
    """Remove acentos e coloca em minúsculas, PRESERVANDO o comprimento do
    texto (cada caractere original vira exatamente um caractere), para que
    os índices calculados sobre o texto normalizado sejam válidos também
    sobre o texto original. Compara de forma tolerante a acentuação/caixa
    (ex: 'intubação' no texto vs. 'intubacao' extraído)."""
    import unicodedata
    saida = []
    for ch in texto:
        # decompõe o caractere e mantém apenas o primeiro componente base,
        # descartando os diacríticos, sem alterar a contagem de caracteres
        base = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in base if not unicodedata.combining(c))
        # se a decomposição resultar em vazio ou múltiplos, mantém o original
        saida.append(base[0].lower() if len(base) >= 1 else ch.lower())
    return "".join(saida)


def _destacar_termos_html(texto: str, termos: list[str]) -> str:
    """
    Retorna o texto do prontuário com os termos extraídos destacados (em
    negrito e com fundo amarelo), no formato de marcação aceito pelo
    Paragraph do reportlab.

    O casamento é tolerante a acentos e maiúsculas: procura cada termo no
    texto ignorando essas diferenças, mas preserva o trecho original no
    destaque. Termos que não forem localizados são simplesmente ignorados,
    sem quebrar a geração.
    """
    import re

    if not texto:
        return ""

    # escapa caracteres especiais de XML/HTML do texto base
    def escapar(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    texto_norm = _normalizar_basico(texto)

    # coleta os intervalos (início, fim) a destacar, a partir dos termos
    intervalos = []
    for termo in termos:
        termo = (termo or "").strip()
        if not termo:
            continue
        termo_norm = _normalizar_basico(termo)
        inicio = 0
        while True:
            pos = texto_norm.find(termo_norm, inicio)
            if pos == -1:
                break
            intervalos.append((pos, pos + len(termo_norm)))
            inicio = pos + len(termo_norm)

    if not intervalos:
        return escapar(texto)

    # ordena e funde intervalos sobrepostos, para não aninhar destaques
    intervalos.sort()
    fundidos = [intervalos[0]]
    for ini, fim in intervalos[1:]:
        ult_ini, ult_fim = fundidos[-1]
        if ini <= ult_fim:
            fundidos[-1] = (ult_ini, max(ult_fim, fim))
        else:
            fundidos.append((ini, fim))

    # remonta o texto intercalando trechos normais e destacados,
    # usando os índices sobre o texto ORIGINAL (mesma indexação do normalizado)
    partes = []
    cursor = 0
    for ini, fim in fundidos:
        partes.append(escapar(texto[cursor:ini]))
        trecho = escapar(texto[ini:fim])
        partes.append(f'<b><font backColor="#fff2a8">{trecho}</font></b>')
        cursor = fim
    partes.append(escapar(texto[cursor:]))
    return "".join(partes)


def gerar_pdf(prontuarios: list[dict], caminho_pdf: str) -> None:
    """Gera o relatório em PDF usando reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloRel", parent=styles["Title"], fontSize=16, spaceAfter=6
    )
    estilo_pront = ParagraphStyle(
        "Pront", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4
    )
    estilo_normal = styles["Normal"]
    estilo_nota = ParagraphStyle(
        "Nota", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#8a6d00"),
        leftIndent=6, spaceBefore=4,
    )
    estilo_subtotal = ParagraphStyle(
        "Subtotal", parent=styles["Normal"], fontSize=10, alignment=2,  # direita
        spaceBefore=4, spaceAfter=8,
    )
    estilo_texto_pep = ParagraphStyle(
        "TextoPEP", parent=styles["Normal"], fontSize=8.5, leading=12,
        backColor=colors.HexColor("#f7f9fb"), borderColor=colors.HexColor("#d5dde5"),
        borderWidth=0.5, borderPadding=6, spaceBefore=2, spaceAfter=8,
    )
    estilo_rotulo = ParagraphStyle(
        "Rotulo", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#555555"),
        spaceBefore=2, spaceAfter=2,
    )

    doc = SimpleDocTemplate(
        caminho_pdf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    story = []

    story.append(Paragraph("Relatório de Faturamento SUS - SIGTAP", estilo_titulo))
    data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")
    story.append(Paragraph(f"Data de geração: {data_geracao}", estilo_normal))
    story.append(Paragraph(f"Total de prontuários processados: {len(prontuarios)}", estilo_normal))
    story.append(Spacer(1, 10))

    total_geral = 0.0
    total_procedimentos = 0
    total_nao_encontrados = 0

    for pront in prontuarios:
        pront_id = pront.get("prontuario_id", "(sem identificação)")
        codigos = pront.get("codigos_sigtap", [])
        nao_encontrados = pront.get("termos_nao_encontrados", [])
        texto_pep = pront.get("texto_prontuario", "")
        entidades = pront.get("entidades_extraidas", [])

        bloco = [Paragraph(f"Prontuário: {pront_id}", estilo_pront)]

        # Texto original do prontuário, com os termos extraídos destacados,
        # exibido antes da tabela para evidenciar a origem dos procedimentos.
        if texto_pep:
            bloco.append(Paragraph("Texto do prontuário (termos extraídos destacados):", estilo_rotulo))
            bloco.append(Spacer(1, 12))
            texto_destacado = _destacar_termos_html(texto_pep, entidades)
            bloco.append(Paragraph(texto_destacado, estilo_texto_pep))

        if codigos:
            dados = [["Código", "Procedimento", "SH", "SA", "SP", "Total"]]
            subtotal = 0.0
            for c in codigos:
                vl_sh = c.get("vl_sh", 0.0)
                vl_sa = c.get("vl_sa", 0.0)
                vl_sp = c.get("vl_sp", 0.0)
                vl_total = c.get("vl_total", vl_sh + vl_sa + vl_sp)
                subtotal += vl_total
                total_procedimentos += 1
                dados.append([
                    c.get("codigo", ""),
                    Paragraph(str(c.get("descricao", "")), estilo_normal),
                    formatar_reais(vl_sh),
                    formatar_reais(vl_sa),
                    formatar_reais(vl_sp),
                    formatar_reais(vl_total),
                ])

            tabela = Table(dados, colWidths=[2.4*cm, 6.0*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.4*cm])
            tabela.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            bloco.append(tabela)
            bloco.append(Paragraph(
                f"Subtotal do prontuário {pront_id}: <b>{formatar_reais(subtotal)}</b>",
                estilo_subtotal
            ))
            total_geral += subtotal
        else:
            bloco.append(Paragraph(
                "Nenhum procedimento faturável foi vinculado a este prontuário.",
                estilo_normal
            ))

        if nao_encontrados:
            total_nao_encontrados += len(nao_encontrados)
            bloco.append(Paragraph(
                "<b>Nota - verificação manual necessária:</b> os seguintes termos "
                "foram identificados no prontuário mas não puderam ser vinculados "
                "a um código SIGTAP automaticamente. Recomenda-se conferência manual:",
                estilo_nota
            ))
            for termo in nao_encontrados:
                bloco.append(Paragraph(f"• {termo}", estilo_nota))

        # KeepTogether tenta nao quebrar o bloco do prontuario entre paginas
        story.append(KeepTogether(bloco))
        story.append(Spacer(1, 8))

    # Resumo consolidado
    story.append(Spacer(1, 10))
    story.append(Paragraph("Resumo Consolidado", estilo_pront))
    resumo = [
        ["Prontuários processados", str(len(prontuarios))],
        ["Total de procedimentos faturáveis", str(total_procedimentos)],
        ["Termos pendentes de verificação manual", str(total_nao_encontrados)],
        ["VALOR TOTAL A FATURAR", formatar_reais(total_geral)],
    ]
    tabela_resumo = Table(resumo, colWidths=[10*cm, 7*cm])
    tabela_resumo.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tabela_resumo)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "SH = Serviço Hospitalar, SA = Serviço Ambulatorial, SP = Serviço "
        "Profissional. Valores conforme tabela SIGTAP/DATASUS.",
        ParagraphStyle("rodape", parent=estilo_normal, fontSize=8,
                       textColor=colors.HexColor("#666666"))
    ))

    doc.build(story)


def main():
    parser = argparse.ArgumentParser(
        description="Gera relatório de faturamento SUS (.md e .pdf) a partir do JSON do pipeline"
    )
    parser.add_argument("entrada", help="Arquivo JSON com a lista de prontuários processados")
    parser.add_argument(
        "--saida", default="relatorio_faturamento",
        help="Nome base dos arquivos de saída (sem extensão). Padrão: relatorio_faturamento"
    )
    args = parser.parse_args()

    with open(args.entrada, encoding="utf-8") as f:
        prontuarios = json.load(f)

    if not isinstance(prontuarios, list):
        # aceita tanto uma lista quanto um único prontuário (dict)
        prontuarios = [prontuarios]

    # Markdown
    md = gerar_markdown(prontuarios)
    caminho_md = f"{args.saida}.md"
    with open(caminho_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Gerado: {caminho_md}")

    # PDF
    caminho_pdf = f"{args.saida}.pdf"
    gerar_pdf(prontuarios, caminho_pdf)
    print(f"Gerado: {caminho_pdf}")


if __name__ == "__main__":
    main()