#!/usr/bin/env python3
"""
Etapa 2 - Tipo de nota x código SIGTAP, unidade e anotador.

Uso (a partir da raiz do projeto):
    python src/analise/etapa2_tipo_documento.py data/data-completo.xlsx

Classifica cada evolução pelo cabeçalho (e, se não achar, por marcadores no corpo)
e cruza o tipo com os códigos frequentes, com a unidade e com o annotation_group.
Imprime só estatísticas agregadas e grava a saída em reports/analise-gabarito/diagnostico_etapa2.txt.
"""
import argparse
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd

# Raiz do projeto (este arquivo fica em src/analise/), para a saída sempre ir
# para reports/analise-gabarito/, não importa de onde o script seja executado.
RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "reports" / "analise-gabarito"

MIN_SUPORTE = 20  # códigos com pelo menos esse nº de linhas entram nas tabelas

RE_ITEM = re.compile(r"(\d{2}\.\d{2}\.\d{2}\.\d{3}-\d)\s*-\s*(.+)")
RE_SEPARADOR = re.compile(r"^[=_\-\s#*.~]+$")

# Ordem importa: a primeira regra que casar define o tipo.
REGRAS_CABECALHO = [
    ("psicologia", r"PSICOLOG"),
    ("fisioterapia", r"FISIOTERAP"),
    ("fonoaudiologia", r"FONOAUD"),
    ("nutricao", r"EVOLUCAO\s+(DA\s+|DE\s+)?NUTRI|SERVICO DE NUTRI|NUTRICIONIS"),
    ("servico_social", r"SERVICO SOCIAL|ASSISTENTE SOCIAL"),
    ("enfermagem", r"ENFERMAGEM"),
    ("medica", r"\bMEDIC"),
]

REGRAS_CORPO = [
    ("psicologia", r"ATENDIMENTO PSICOLOGICO|EXAME PSIQUICO"),
    ("enfermagem", r"INTERVENCOES DE ENFERMAGEM|CUIDADOS DE ENFERMAGEM"),
    ("fisioterapia", r"FISIOTERAPIA (RESPIRATORIA|MOTORA)\s*:"),
    ("medica", r"LISTA DE PROBLEMAS|HIPOTESES DIAGNOSTICAS|\bSTAFF\b|\bM?R[1-3]\b"),
]

COD_NS = "0301010048"        # consulta de nível superior (exceto médico)
COD_INTERNADO = "0301010170"  # consulta/avaliação em paciente internado

SAIDA = []


def log(txt=""):
    print(txt)
    SAIDA.append(str(txt))


def secao(titulo):
    log()
    log("=" * 90)
    log(titulo)
    log("=" * 90)


def carregar(caminho: Path) -> pd.DataFrame:
    ext = caminho.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(caminho, dtype=str)
    if ext == ".tsv":
        return pd.read_csv(caminho, sep="\t", dtype=str, encoding="utf-8-sig")
    with open(caminho, encoding="utf-8-sig", errors="replace") as f:
        primeira_linha = f.readline()
    sep = max(["\t", ";", ","], key=primeira_linha.count)
    return pd.read_csv(caminho, sep=sep, dtype=str, encoding="utf-8-sig")


def normalizar(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.upper()


def cabecalho(texto, n_linhas=3) -> str:
    linhas = []
    for linha in str(texto).splitlines():
        s = linha.strip()
        if not s or RE_SEPARADOR.match(s):
            continue
        linhas.append(s)
        if len(linhas) == n_linhas:
            break
    return " | ".join(linhas)


def classificar(texto):
    if pd.isna(texto) or not str(texto).strip():
        return "vazia", "-"
    cab = normalizar(cabecalho(texto))
    for tipo, rx in REGRAS_CABECALHO:
        if re.search(rx, cab):
            return tipo, "cabecalho"
    corpo = normalizar(texto)
    for tipo, rx in REGRAS_CORPO:
        if re.search(rx, corpo):
            return tipo, "corpo"
    return "nao_identificado", "-"


def parse_codigos(valor) -> frozenset:
    if pd.isna(valor):
        return frozenset()
    partes = (re.sub(r"\D", "", p) for p in str(valor).split(";"))
    return frozenset(p for p in partes if p)


def parse_itens(valor) -> dict:
    if pd.isna(valor):
        return {}
    out = {}
    for linha in str(valor).splitlines():
        m = RE_ITEM.search(linha.strip())
        if m:
            out[re.sub(r"\D", "", m.group(1))] = m.group(2).strip()
    return out


def formatar_codigo(c: str) -> str:
    if len(c) == 10:
        return f"{c[0:2]}.{c[2:4]}.{c[4:6]}.{c[6:9]}-{c[9]}"
    return c


def tabela_por(df, coluna, codigos, descricoes, ordem=None):
    """% de linhas de cada valor de `coluna` que contêm cada código."""
    valores = ordem if ordem is not None else df[coluna].value_counts().index.tolist()
    linhas = []
    for c in codigos:
        linha = {"codigo": f"{formatar_codigo(c)} {descricoes.get(c, '?')[:26]}"}
        for v in valores:
            sub = df[df[coluna] == v]
            if len(sub):
                linha[f"{v} (n={len(sub)})"] = round(100 * sub["_cod"].apply(lambda s: c in s).mean())
        linhas.append(linha)
    return pd.DataFrame(linhas).set_index("codigo")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    args = ap.parse_args()

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", 40)

    df = carregar(Path(args.planilha))
    df.columns = [c.strip() for c in df.columns]
    df["_cod"] = df["codigos_sigtap"].apply(parse_codigos)
    df["_n"] = df["_cod"].apply(len)

    descricoes = {}
    for d in df["itens_faturaveis"].apply(parse_itens):
        for k, v in d.items():
            descricoes.setdefault(k, v)

    cont = Counter(c for s in df["_cod"] for c in s)
    frequentes = [c for c, q in cont.most_common() if q >= MIN_SUPORTE]

    classif = df["evolucoes"].apply(classificar)
    df["tipo"] = classif.apply(lambda x: x[0])
    df["metodo"] = classif.apply(lambda x: x[1])
    ordem_tipos = df["tipo"].value_counts().index.tolist()

    # ------------------------------------------------------------------
    secao("1. TIPO DE NOTA (classificação por regex)")
    tab = pd.crosstab(df["tipo"], df["metodo"], margins=True, margins_name="total")
    log(tab.loc[ordem_tipos + ["total"]].to_string())

    nao_id = df[df["tipo"] == "nao_identificado"]
    if len(nao_id):
        log()
        log(f"Primeira linha das {len(nao_id)} evoluções não identificadas (dígitos trocados por #):")
        primeiras = nao_id["evolucoes"].apply(
            lambda t: re.sub(r"\d", "#", normalizar(cabecalho(t, 1)))[:70]
        )
        for linha, q in primeiras.value_counts().head(25).items():
            log(f"  {q:3d}x  {linha}")

    # ------------------------------------------------------------------
    secao("2. CONFERÊNCIAS")
    tem_ns = df["_cod"].apply(lambda s: COD_NS in s)
    tem_int = df["_cod"].apply(lambda s: COD_INTERNADO in s)
    label_1 = df["label"].astype(str).str.strip() == "1"
    log(f"label == 1 exatamente quando tem 03.01.01.004-8: {(label_1 == tem_ns).all()} "
        f"(divergências: {(label_1 != tem_ns).sum()})")
    log(f"Linhas com 004-8 E 017-0 juntos: {(tem_ns & tem_int).sum()}")
    log(f"Linhas sem código, por tipo de nota:")
    for t in ordem_tipos:
        sub = df[df["tipo"] == t]
        log(f"  {t:18s} {(sub['_n'] == 0).sum():3d} de {len(sub)}")

    # ------------------------------------------------------------------
    secao(f"3. CÓDIGO x TIPO DE NOTA  (% das notas daquele tipo que têm o código; códigos com >= {MIN_SUPORTE} linhas)")
    log(tabela_por(df, "tipo", frequentes, descricoes, ordem_tipos).to_string())

    # ------------------------------------------------------------------
    secao("4. CÓDIGO x UNIDADE  (% das notas da unidade que têm o código)")
    codigos_unid = frequentes + [c for c in ["0802010210"] if c in cont and c not in frequentes]
    log(tabela_por(df, "unidades_funcionais", codigos_unid, descricoes).to_string())
    log()
    log("Tipo de nota x unidade (nº de linhas):")
    log(pd.crosstab(df["tipo"], df["unidades_funcionais"]).loc[ordem_tipos].to_string())

    # ------------------------------------------------------------------
    secao("5. ANOTADORES (annotation_group)")
    grupos = sorted(df["annotation_group"].unique(), key=lambda x: str(x))
    resumo = []
    for g in grupos:
        sub = df[df["annotation_group"] == g]
        resumo.append({
            "grupo": g,
            "linhas": len(sub),
            "pacientes": sub["prontuario_hash"].nunique(),
            "media_codigos": round(sub["_n"].mean(), 2),
            "%_sem_codigo": round(100 * (sub["_n"] == 0).mean(), 1),
            "%_UTI_coronariana": round(100 * (sub["unidades_funcionais"] == "UTI CORONARIANA").mean(), 1),
        })
    log(pd.DataFrame(resumo).set_index("grupo").to_string())

    pac_multi = (df.groupby("prontuario_hash")["annotation_group"].nunique() > 1).sum()
    log()
    log(f"Pacientes com evoluções em mais de um anotador: {pac_multi} de {df['prontuario_hash'].nunique()}")

    log()
    log("Mistura de tipos de nota por anotador (% das linhas do grupo):")
    mix = pd.crosstab(df["annotation_group"], df["tipo"], normalize="index").mul(100).round(0)
    log(mix[[t for t in ordem_tipos if t in mix.columns]].to_string())

    log()
    log("Código x anotador (% das linhas do grupo que têm o código):")
    log(tabela_por(df, "annotation_group", frequentes, descricoes, grupos).to_string())

    log()
    log("Mesmo recorte, só notas de ENFERMAGEM e só notas MÉDICAS (isola o efeito do tipo de nota):")
    for t in ["enfermagem", "medica"]:
        sub = df[df["tipo"] == t]
        if len(sub):
            log()
            log(f"-- {t} --")
            log(tabela_por(sub, "annotation_group", frequentes, descricoes, grupos).to_string())

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / "diagnostico_etapa2.txt"
    log()
    log(f"Saída gravada em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()