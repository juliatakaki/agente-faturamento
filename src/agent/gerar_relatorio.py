"""
gerar_relatorio.py

Lê o JSON com os prontuários já processados pelo pipeline (lista de
relatórios por prontuário) e gera um relatório de faturamento consolidado
em dois formatos: Markdown (.md) e PDF.

O relatório, por prontuário, lista cada código SIGTAP encontrado com seus
três componentes de valor (SH, SA, SP), o total, o nível de busca que o
resolveu e a confiança da correspondência; soma o valor do prontuário; e
separa os termos que exigem atenção humana em duas listas distintas:

  - SEM CORRESPONDÊNCIA: o termo existe no prontuário, deveria ter código,
    mas a busca não achou. Pode representar receita não faturada.
  - MARCADO COMO SEM CÓDIGO PRÓPRIO: o dicionário do sistema registra que o
    item não seria faturável separadamente.

CALIBRAÇÃO DA LINGUAGEM -- LEIA ANTES DE ALTERAR OS TEXTOS
----------------------------------------------------------
A segunda lista JÁ FOI apresentada como fato ("estes itens não são
faturáveis separadamente"). Isso estava errado por dois motivos:

1. É uma afirmação sobre as REGRAS DE FATURAMENTO DO SUS, que o sistema não
   tem como verificar. Ele sabe apenas o que está escrito no seu dicionário.
2. As entradas do dicionário foram criadas por inferência a partir de termos
   que a busca não encontrou. Uma auditoria em agosto/2026 mostrou que pelo
   menos três estavam erradas -- 'cateter de Swan-Ganz' existe no SIGTAP
   como CATETER DE TERMODILUIÇÃO e 'sedoanalgesia' como SEDAÇÃO. Como essa
   lista tem precedência sobre toda a busca, as marcações erradas estavam
   impedindo ativamente que o código fosse encontrado.

Enquanto o setor de faturamento não validar o dicionário, o relatório deve
dizer "o sistema marcou" e não "não é faturável". A diferença não é de
estilo: um faturista que lê a versão afirmativa não confere, e receita
deixa de ser cobrada em silêncio.

Uso:
    python gerar_relatorio.py entrada.json
    python gerar_relatorio.py entrada.json --saida relatorio_sus

Gera: <saida>.md e <saida>.pdf  (padrão: relatorio_faturamento.md/.pdf)
"""

import sys
import json
import argparse
import unicodedata
from datetime import datetime


# ── Rótulos de apoio ───────────────────────────────────────────────────────

# Nível de busca que resolveu cada correspondência. Aparece no relatório
# porque as garantias são muito diferentes entre eles: o Nível 0 é tradução
# curada, enquanto o semântico e o do agente são aproximações.
ROTULO_NIVEL = {
    "nivel0": "Dicionário",
    "nivel1": "Exata",
    "nivel2": "Parcial",
    "nivel_semantico": "Semântica",
    "nivel3": "Similaridade",
    "nivel4": "Agente",
}

ROTULO_CONFIANCA = {
    "alta": "Alta",
    "media": "Média",
    "baixa": "BAIXA",
}

# Texto usado nas duas notas por prontuário e no resumo. Centralizado aqui
# para que a calibração descrita no cabeçalho não se perca ao editar um
# formato e esquecer o outro.
TEXTO_PENDENCIA = (
    "Estes termos foram identificados no prontuário mas não puderam ser "
    "vinculados a um código SIGTAP pela busca automática. Podem representar "
    "receita não faturada — recomenda-se conferência."
)

TEXTO_MARCADO_SEM_CODIGO = (
    "O dicionário do sistema registra estes itens como não faturáveis "
    "separadamente (embutidos em outro procedimento ou fora do rol da "
    "tabela). Essa marcação NÃO foi validada pelo setor de faturamento e "
    "já se mostrou incorreta em auditoria — conferir antes de descartar."
)


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


def _rotulo_nivel(codigo_nivel: str) -> str:
    return ROTULO_NIVEL.get(codigo_nivel or "", codigo_nivel or "—")


def _rotulo_confianca(confianca: str) -> str:
    return ROTULO_CONFIANCA.get(confianca or "", confianca or "—")


def _metadados_execucao(prontuarios: list[dict]) -> tuple[str, str]:
    """
    Extrai o modelo e o modo de orquestração usados na execução, gravados
    pelo pipeline em cada relatório.

    Registrar isso no documento não é detalhe: modelos de API saem de
    catálogo sem aviso (o llama-3.3-70b-versatile foi descontinuado pela
    Groq no meio dos testes), e um resultado sem essa informação não é
    reproduzível depois.
    """
    modelo = "não informado"
    orquestracao = ""
    for p in prontuarios:
        modelo = p.get("modelo_utilizado") or modelo
        orquestracao = p.get("orquestracao") or orquestracao
        if modelo != "não informado":
            break

    if orquestracao == "llm":
        orquestracao = "LLM orquestrando as consultas"
    elif orquestracao == "deterministica":
        orquestracao = "laço determinístico"
    return modelo, orquestracao


def _totais(prontuarios: list[dict]) -> dict:
    """
    Consolida os números do lote inteiro, separando o que é pendência do
    que o sistema marcou como sem código próprio.
    """
    t = {
        "codigos": 0,
        "codigos_com_valor": 0,
        "nao_encontrados": 0,
        "nao_faturaveis": 0,
        "baixa_confianca": 0,
        "valor": 0.0,
    }
    for p in prontuarios:
        for c in p.get("codigos_sigtap", []):
            t["codigos"] += 1
            valor = c.get("vl_total", 0.0) or 0.0
            t["valor"] += valor
            if valor > 0:
                t["codigos_com_valor"] += 1
            if c.get("confianca") == "baixa":
                t["baixa_confianca"] += 1
        t["nao_encontrados"] += len(p.get("termos_nao_encontrados", []))
        t["nao_faturaveis"] += len(p.get("termos_nao_faturaveis", []))
    t["valor"] = round(t["valor"], 2)
    return t


# ── Markdown ───────────────────────────────────────────────────────────────

def gerar_markdown(prontuarios: list[dict]) -> str:
    """Monta o conteúdo do relatório em Markdown."""
    linhas = []
    linhas.append("# Relatório de Faturamento SUS - SIGTAP")
    linhas.append("")
    data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")
    modelo, orquestracao = _metadados_execucao(prontuarios)

    linhas.append(f"**Data de geração:** {data_geracao}  ")
    linhas.append(f"**Total de prontuários processados:** {len(prontuarios)}  ")
    linhas.append(f"**Modelo utilizado:** {modelo}  ")
    if orquestracao:
        linhas.append(f"**Consulta ao SIGTAP:** {orquestracao}")
    linhas.append("")
    linhas.append(
        "> **Relatório de apoio ao faturamento — não substitui conferência "
        "humana.** As correspondências são sugestões da busca automática e "
        "devem ser verificadas antes do envio, com prioridade para as de "
        "confiança **BAIXA**. O dicionário de termos usado pelo sistema ainda "
        "não foi validado pelo setor de faturamento."
    )
    linhas.append("")

    for pront in prontuarios:
        pront_id = pront.get("prontuario_id", "(sem identificação)")
        codigos = pront.get("codigos_sigtap", [])
        nao_encontrados = pront.get("termos_nao_encontrados", [])
        nao_faturaveis = pront.get("termos_nao_faturaveis", [])

        linhas.append("---")
        linhas.append("")
        linhas.append(f"## Prontuário: {pront_id}")
        linhas.append("")

        if codigos:
            linhas.append(
                "| Código SIGTAP | Procedimento | Origem | Nível | Confiança | "
                "SH | SA | SP | Total |"
            )
            linhas.append("|---|---|---|---|---|---:|---:|---:|---:|")

            subtotal = 0.0
            for c in codigos:
                vl_sh = c.get("vl_sh", 0.0)
                vl_sa = c.get("vl_sa", 0.0)
                vl_sp = c.get("vl_sp", 0.0)
                vl_total = c.get("vl_total", vl_sh + vl_sa + vl_sp)
                subtotal += vl_total

                # escapa o pipe em descrições para nao quebrar a tabela
                descricao = str(c.get("descricao", "")).replace("|", "/")
                origem = str(c.get("origem", "")).replace("|", "/")
                if c.get("painel"):
                    origem += " (painel)"

                confianca = _rotulo_confianca(c.get("confianca"))
                if c.get("confianca") == "baixa":
                    confianca = f"**{confianca}**"

                linhas.append(
                    f"| {c.get('codigo', '')} | {descricao} | {origem} | "
                    f"{_rotulo_nivel(c.get('nivel'))} | {confianca} | "
                    f"{formatar_reais(vl_sh)} | {formatar_reais(vl_sa)} | "
                    f"{formatar_reais(vl_sp)} | {formatar_reais(vl_total)} |"
                )

            linhas.append("")
            linhas.append(
                f"**Subtotal do prontuário {pront_id}: {formatar_reais(subtotal)}**"
            )
            linhas.append("")
        else:
            linhas.append("_Nenhum código SIGTAP foi vinculado a este prontuário._")
            linhas.append("")

        # ── Pendência: a busca não encontrou ───────────────────────────────
        if nao_encontrados:
            linhas.append("> **Sem correspondência — verificação manual**  ")
            linhas.append(f"> {TEXTO_PENDENCIA}")
            linhas.append(">")
            for termo in nao_encontrados:
                linhas.append(f"> - {termo}")
            linhas.append("")

        # ── Marcação do dicionário, ainda não validada ─────────────────────
        if nao_faturaveis:
            linhas.append(
                "> **Marcados pelo sistema como sem código próprio no SIGTAP**  "
            )
            linhas.append(f"> {TEXTO_MARCADO_SEM_CODIGO}")
            linhas.append(">")
            for termo in nao_faturaveis:
                linhas.append(f"> - {termo}")
            linhas.append("")

    # ── Resumo consolidado ────────────────────────────────────────────────
    t = _totais(prontuarios)
    linhas.append("---")
    linhas.append("")
    linhas.append("## Resumo Consolidado")
    linhas.append("")
    linhas.append(f"- **Prontuários processados:** {len(prontuarios)}")
    linhas.append(f"- **Códigos SIGTAP atribuídos:** {t['codigos']}")
    linhas.append(
        f"- **Códigos com valor maior que zero:** {t['codigos_com_valor']}"
    )
    linhas.append(
        f"- **Correspondências de confiança BAIXA (conferir):** "
        f"{t['baixa_confianca']}"
    )
    linhas.append(
        f"- **Termos sem correspondência (verificar):** {t['nao_encontrados']}"
    )
    linhas.append(
        f"- **Termos marcados como sem código próprio (conferir marcação):** "
        f"{t['nao_faturaveis']}"
    )
    linhas.append(f"- **VALOR TOTAL SUGERIDO:** {formatar_reais(t['valor'])}")
    linhas.append("")
    linhas.append(
        "_SH = Serviço Hospitalar, SA = Serviço Ambulatorial, "
        "SP = Serviço Profissional. Valores conforme tabela SIGTAP/DATASUS._"
    )
    linhas.append("")

    return "\n".join(linhas)


# ── Destaque do texto do prontuário ────────────────────────────────────────

def _normalizar_basico(texto: str) -> str:
    """
    Remove acentos e coloca em minúsculas, PRESERVANDO o comprimento do
    texto (cada caractere original vira exatamente um caractere), para que
    os índices calculados sobre o texto normalizado sejam válidos também
    sobre o texto original. Compara de forma tolerante a acentuação/caixa
    (ex: 'intubação' no texto vs. 'intubacao' extraído).
    """
    saida = []
    for ch in texto:
        # decompõe o caractere e mantém apenas o primeiro componente base,
        # descartando os diacríticos, sem alterar a contagem de caracteres
        base = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in base if not unicodedata.combining(c))
        if not base:
            base = ch
        # .lower() pode devolver mais de um caractere em casos raros
        # (ex: 'İ'); mantém só o primeiro para não deslocar os índices
        saida.append(base[0].lower()[0])
    return "".join(saida)


# Cores do destaque. São QUATRO situações, não três: a versão anterior tinha
# só encontrado/não encontrado/descartada, e por isso pintava de amarelo
# ("encontrado") os termos marcados como sem código próprio -- afirmando no
# texto o oposto do que a tabela do mesmo prontuário mostrava.
COR_ENCONTRADO = "#fff2a8"       # amarelo  — código atribuído
COR_BAIXA_CONFIANCA = "#ffd9a8"  # laranja  — código atribuído, conferir
COR_NAO_ENCONTRADO = "#ffb3b3"   # vermelho — sem correspondência
COR_NAO_FATURAVEL = "#dcdcdc"    # cinza    — marcado como sem código próprio
COR_DESCARTADA = "#bcd8f5"       # azul     — fora das categorias faturáveis

# Prioridade na sobreposição: quanto maior, mais prevalece. O vermelho vence
# porque uma pendência não pode ficar escondida sob outro destaque.
PRIORIDADE_COR = {
    COR_DESCARTADA: 1,
    COR_NAO_FATURAVEL: 2,
    COR_ENCONTRADO: 3,
    COR_BAIXA_CONFIANCA: 4,
    COR_NAO_ENCONTRADO: 5,
}


def _destacar_termos_html(texto: str, grupos: list[tuple[list[str], str]]) -> str:
    """
    Retorna o texto do prontuário com os termos destacados, no formato de
    marcação aceito pelo Paragraph do reportlab.

    `grupos` é uma lista de (termos, cor), permitindo quantas categorias
    forem necessárias -- a versão anterior tinha as três categorias fixas na
    assinatura, o que foi justamente o que impediu de representar a quarta
    quando ela surgiu.

    O casamento é tolerante a acentos e maiúsculas: procura cada termo no
    texto ignorando essas diferenças, mas preserva o trecho original no
    destaque. Termos não localizados são ignorados, sem quebrar.
    """
    if not texto:
        return ""

    def escapar(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    texto_norm = _normalizar_basico(texto)

    intervalos = []
    for termos, cor in grupos:
        for termo in termos or []:
            termo = (termo or "").strip()
            if not termo:
                continue
            termo_norm = _normalizar_basico(termo)
            inicio = 0
            while True:
                pos = texto_norm.find(termo_norm, inicio)
                if pos == -1:
                    break
                intervalos.append((pos, pos + len(termo_norm), cor))
                inicio = pos + len(termo_norm)

    if not intervalos:
        return escapar(texto)

    # Resolve cada caractere para uma cor, respeitando a prioridade.
    cores = [None] * len(texto)
    for ini, fim, cor in intervalos:
        for i in range(ini, min(fim, len(texto))):
            if cores[i] is None or PRIORIDADE_COR[cor] > PRIORIDADE_COR[cores[i]]:
                cores[i] = cor

    # remonta o texto agrupando faixas contíguas de mesma cor
    partes = []
    i = 0
    n = len(texto)
    while i < n:
        cor_atual = cores[i]
        j = i
        while j < n and cores[j] == cor_atual:
            j += 1
        trecho = escapar(texto[i:j])
        if cor_atual is None:
            partes.append(trecho)
        else:
            partes.append(f'<b><font backColor="{cor_atual}">{trecho}</font></b>')
        i = j
    return "".join(partes)


def _classificar_termos(pront: dict) -> dict:
    """
    Separa os termos do prontuário nas categorias de destaque.

    CORREÇÃO IMPORTANTE: a versão anterior montava a lista de "encontrados"
    partindo de TODAS as entidades extraídas e removendo apenas as não
    encontradas. Como os termos marcados como sem código próprio não eram
    removidos, eles apareciam em AMARELO, com a legenda dizendo
    "procedimento encontrado" -- exatamente o oposto do que a tabela do
    mesmo prontuário informava. Aqui a subtração cobre todas as categorias.
    """
    entidades = [str(e).strip() for e in pront.get("entidades_extraidas", []) if str(e).strip()]
    nao_encontrados = [t for t in pront.get("termos_nao_encontrados", []) if t]
    nao_faturaveis = [t for t in pront.get("termos_nao_faturaveis", []) if t]
    descartadas = [t for t in pront.get("entidades_descartadas", []) if t]

    # Termos cuja correspondência ficou com confiança baixa: recebem cor
    # própria para que a conferência humana comece por eles.
    baixa_confianca = [
        str(c.get("origem", "")).strip()
        for c in pront.get("codigos_sigtap", [])
        if c.get("confianca") == "baixa" and c.get("origem")
    ]

    ja_classificados = {
        _normalizar_basico(t.strip())
        for t in nao_encontrados + nao_faturaveis + descartadas + baixa_confianca
    }
    encontrados = [
        e for e in entidades
        if _normalizar_basico(e) not in ja_classificados
    ]

    return {
        "encontrados": encontrados,
        "baixa_confianca": baixa_confianca,
        "nao_encontrados": nao_encontrados,
        "nao_faturaveis": nao_faturaveis,
        "descartadas": descartadas,
    }


# ── PDF ────────────────────────────────────────────────────────────────────

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
    estilo_celula = ParagraphStyle(
        "Celula", parent=styles["Normal"], fontSize=7, leading=8.5
    )
    # Pendência (vermelho): a busca não achou, pode haver receita a cobrar
    estilo_nota_pendencia = ParagraphStyle(
        "NotaPendencia", parent=styles["Normal"], fontSize=8,
        textColor=colors.HexColor("#8c2b2b"), leftIndent=6, spaceBefore=4,
    )
    # Marcação do dicionário (cinza): conferir, ainda não validada
    estilo_nota_info = ParagraphStyle(
        "NotaInfo", parent=styles["Normal"], fontSize=8,
        textColor=colors.HexColor("#555555"), leftIndent=6, spaceBefore=4,
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
        "Rotulo", parent=styles["Normal"], fontSize=7.5,
        textColor=colors.HexColor("#555555"), leading=10,
        spaceBefore=2, spaceAfter=2,
    )
    estilo_aviso = ParagraphStyle(
        "Aviso", parent=styles["Normal"], fontSize=8.5, leading=11,
        backColor=colors.HexColor("#fdf6e3"), borderColor=colors.HexColor("#e0d3a8"),
        borderWidth=0.5, borderPadding=6, spaceBefore=6, spaceAfter=10,
    )

    doc = SimpleDocTemplate(
        caminho_pdf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    story = []

    story.append(Paragraph("Relatório de Faturamento SUS - SIGTAP", estilo_titulo))
    data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")
    modelo, orquestracao = _metadados_execucao(prontuarios)
    story.append(Paragraph(f"Data de geração: {data_geracao}", estilo_normal))
    story.append(Paragraph(
        f"Total de prontuários processados: {len(prontuarios)}", estilo_normal))
    story.append(Paragraph(f"Modelo utilizado: {modelo}", estilo_normal))
    if orquestracao:
        story.append(Paragraph(
            f"Consulta ao SIGTAP: {orquestracao}", estilo_normal))

    story.append(Paragraph(
        "<b>Relatório de apoio ao faturamento — não substitui conferência "
        "humana.</b> As correspondências abaixo são sugestões da busca "
        "automática e devem ser verificadas antes do envio, com prioridade "
        "para as de confiança <b>BAIXA</b>. Os itens que o sistema marcou "
        "como sem código próprio no SIGTAP também precisam de conferência: "
        "essa marcação vem de um dicionário interno que ainda não foi "
        "validado pelo setor de faturamento.",
        estilo_aviso
    ))

    for pront in prontuarios:
        pront_id = pront.get("prontuario_id", "(sem identificação)")
        codigos = pront.get("codigos_sigtap", [])
        texto_pep = pront.get("texto_prontuario", "")
        termos = _classificar_termos(pront)

        bloco = [Paragraph(f"Prontuário: {pront_id}", estilo_pront)]

        # Texto original do prontuário com os termos destacados, exibido
        # antes da tabela para evidenciar a origem de cada código.
        if texto_pep:
            legenda = [
                ('<font backColor="%s"><b>&nbsp;amarelo&nbsp;</b></font> '
                 'código atribuído' % COR_ENCONTRADO),
                ('<font backColor="%s"><b>&nbsp;laranja&nbsp;</b></font> '
                 'código atribuído, confiança baixa' % COR_BAIXA_CONFIANCA),
                ('<font backColor="%s"><b>&nbsp;vermelho&nbsp;</b></font> '
                 'sem correspondência (verificar)' % COR_NAO_ENCONTRADO),
                ('<font backColor="%s"><b>&nbsp;cinza&nbsp;</b></font> '
                 'marcado como sem código próprio' % COR_NAO_FATURAVEL),
            ]
            if termos["descartadas"]:
                legenda.append(
                    '<font backColor="%s"><b>&nbsp;azul&nbsp;</b></font> '
                    'fora das categorias faturáveis' % COR_DESCARTADA
                )
            bloco.append(Paragraph(
                "Texto do prontuário — " + "; ".join(legenda) + ".",
                estilo_rotulo))

            texto_destacado = _destacar_termos_html(texto_pep, [
                (termos["encontrados"], COR_ENCONTRADO),
                (termos["baixa_confianca"], COR_BAIXA_CONFIANCA),
                (termos["nao_encontrados"], COR_NAO_ENCONTRADO),
                (termos["nao_faturaveis"], COR_NAO_FATURAVEL),
                (termos["descartadas"], COR_DESCARTADA),
            ])
            bloco.append(Paragraph(texto_destacado, estilo_texto_pep))

        if codigos:
            dados = [[
                "Código",
                Paragraph("<b>Procedimento</b><br/><font size=6>origem · nível</font>",
                          ParagraphStyle("CabTab", parent=estilo_celula,
                                         textColor=colors.white)),
                "Conf.", "SH", "SA", "SP", "Total",
            ]]
            linhas_baixa = []   # índices para destacar na tabela
            subtotal = 0.0

            for c in codigos:
                vl_sh = c.get("vl_sh", 0.0)
                vl_sa = c.get("vl_sa", 0.0)
                vl_sp = c.get("vl_sp", 0.0)
                vl_total = c.get("vl_total", vl_sh + vl_sa + vl_sp)
                subtotal += vl_total

                origem = str(c.get("origem", ""))
                if c.get("painel"):
                    origem += " · painel"
                rodape_celula = f"{origem} · {_rotulo_nivel(c.get('nivel'))}"
                if c.get("nivel") == "nivel4" and c.get("tentativas_agente"):
                    rodape_celula += f" ({c['tentativas_agente']} tentativas)"

                descricao = (
                    f"{c.get('descricao', '')}<br/>"
                    f'<font size=6 color="#666666">{rodape_celula}</font>'
                )

                if c.get("confianca") == "baixa":
                    linhas_baixa.append(len(dados))

                dados.append([
                    c.get("codigo", ""),
                    Paragraph(descricao, estilo_celula),
                    _rotulo_confianca(c.get("confianca")),
                    formatar_reais(vl_sh),
                    formatar_reais(vl_sa),
                    formatar_reais(vl_sp),
                    formatar_reais(vl_total),
                ])

            tabela = Table(
                dados,
                colWidths=[2.3*cm, 5.9*cm, 1.5*cm, 1.9*cm, 1.9*cm, 1.9*cm, 2.1*cm]
            )
            estilo_tabela = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#f2f6fa")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
            # destaca as linhas de baixa confiança, para que a conferência
            # comece por elas
            for idx in linhas_baixa:
                estilo_tabela.append(
                    ("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#ffe9d1"))
                )
                estilo_tabela.append(
                    ("FONTNAME", (2, idx), (2, idx), "Helvetica-Bold")
                )
            tabela.setStyle(TableStyle(estilo_tabela))

            bloco.append(tabela)
            bloco.append(Paragraph(
                f"Subtotal do prontuário {pront_id}: <b>{formatar_reais(subtotal)}</b>",
                estilo_subtotal
            ))
        else:
            bloco.append(Paragraph(
                "Nenhum código SIGTAP foi vinculado a este prontuário.",
                estilo_normal
            ))

        # ── Pendência: a busca não encontrou ───────────────────────────────
        if termos["nao_encontrados"]:
            bloco.append(Paragraph(
                f"<b>Sem correspondência — verificação manual:</b> "
                f"{TEXTO_PENDENCIA}",
                estilo_nota_pendencia
            ))
            for termo in termos["nao_encontrados"]:
                bloco.append(Paragraph(f"• {termo}", estilo_nota_pendencia))

        # ── Marcação do dicionário, ainda não validada ─────────────────────
        if termos["nao_faturaveis"]:
            bloco.append(Paragraph(
                f"<b>Marcados pelo sistema como sem código próprio no SIGTAP:"
                f"</b> {TEXTO_MARCADO_SEM_CODIGO}",
                estilo_nota_info
            ))
            for termo in termos["nao_faturaveis"]:
                bloco.append(Paragraph(f"• {termo}", estilo_nota_info))

        # KeepTogether tenta nao quebrar o bloco do prontuario entre paginas
        story.append(KeepTogether(bloco))
        story.append(Spacer(1, 12))

    # ── Resumo consolidado ────────────────────────────────────────────────
    t = _totais(prontuarios)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Resumo Consolidado", estilo_pront))
    resumo = [
        ["Prontuários processados", str(len(prontuarios))],
        ["Códigos SIGTAP atribuídos", str(t["codigos"])],
        ["Códigos com valor maior que zero", str(t["codigos_com_valor"])],
        ["Correspondências de confiança BAIXA (conferir)", str(t["baixa_confianca"])],
        ["Termos sem correspondência (verificar)", str(t["nao_encontrados"])],
        ["Marcados como sem código próprio (conferir marcação)",
         str(t["nao_faturaveis"])],
        ["VALOR TOTAL SUGERIDO", formatar_reais(t["valor"])],
    ]
    tabela_resumo = Table(resumo, colWidths=[11*cm, 6*cm])
    estilo_resumo = [
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    # realça as linhas que exigem ação humana
    if t["baixa_confianca"]:
        estilo_resumo.append(
            ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#ffe9d1")))
    if t["nao_encontrados"]:
        estilo_resumo.append(
            ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#ffe0e0")))
    tabela_resumo.setStyle(TableStyle(estilo_resumo))
    story.append(tabela_resumo)

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "SH = Serviço Hospitalar, SA = Serviço Ambulatorial, SP = Serviço "
        "Profissional. Valores conforme tabela SIGTAP/DATASUS.",
        ParagraphStyle("rodape", parent=estilo_normal, fontSize=8,
                       textColor=colors.HexColor("#666666"))
    ))
    story.append(Paragraph(
        "Níveis de busca: Dicionário (tradução curada), Exata, Parcial, "
        "Semântica, Similaridade e Agente (resgate por reformulação do "
        "termo). Os três últimos são aproximações e recebem confiança "
        "reduzida. O dicionário de termos do sistema, incluindo as marcações "
        "de itens sem código próprio, ainda não passou por validação do setor "
        "de faturamento.",
        ParagraphStyle("rodape2", parent=estilo_normal, fontSize=7.5,
                       textColor=colors.HexColor("#888888"), spaceBefore=4)
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