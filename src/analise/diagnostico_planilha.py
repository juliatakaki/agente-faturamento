#!/usr/bin/env python3
"""
Etapa 1 - Diagnóstico da planilha de gabarito (evoluções x códigos SIGTAP).

Uso:
    python diagnostico_planilha.py caminho/da/planilha.xlsx
    python diagnostico_planilha.py caminho/da/planilha.csv   (separador detectado: tab, ; ou ,)

Imprime só estatísticas agregadas (nenhum texto de prontuário) e grava
a mesma saída em reports/analise-gabarito/diagnostico_saida.txt.
"""
import argparse
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

import pandas as pd

# Raiz do projeto (este arquivo fica em src/analise/), para a saída sempre ir
# para reports/analise-gabarito/, não importa de onde o script seja executado.
RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "reports" / "analise-gabarito"

COLUNAS_ESPERADAS = [
    "source_row_id", "prontuario_hash", "evolucoes", "anamneses", "itens_faturaveis",
    "codigos_sigtap", "qtde_itens_sigtap", "annotation_group", "annotation_group_row",
    "unidades_funcionais", "dthr_evolucao_dt", "dthr_anamnese_dt", "ano_evolucao",
    "mes_evolucao", "idade_na_evolucao", "dias_anamnese_ate_evolucao", "label",
]

RE_ITEM = re.compile(r"(\d{2}\.\d{2}\.\d{2}\.\d{3}-\d)\s*-\s*(.+)")

SAIDA = []


def log(txt=""):
    print(txt)
    SAIDA.append(str(txt))


def secao(titulo):
    log()
    log("=" * 70)
    log(titulo)
    log("=" * 70)


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


def parse_codigos(valor) -> frozenset:
    if pd.isna(valor):
        return frozenset()
    partes = (re.sub(r"\D", "", p) for p in str(valor).split(";"))
    return frozenset(p for p in partes if p)


def parse_itens(valor) -> dict:
    """Devolve {codigo_so_digitos: descricao} a partir de itens_faturaveis."""
    if pd.isna(valor):
        return {}
    out = {}
    for linha in str(valor).splitlines():
        m = RE_ITEM.search(linha.strip())
        if m:
            out[re.sub(r"\D", "", m.group(1))] = m.group(2).strip()
    return out


def jaccard(a: frozenset, b: frozenset) -> float:
    uniao = a | b
    return len(a & b) / len(uniao) if uniao else 1.0


def formatar_codigo(c: str) -> str:
    if len(c) == 10:
        return f"{c[0:2]}.{c[2:4]}.{c[4:6]}.{c[6:9]}-{c[9]}"
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    args = ap.parse_args()

    df = carregar(Path(args.planilha))
    df.columns = [c.strip() for c in df.columns]

    # ------------------------------------------------------------------
    secao("1. ESTRUTURA")
    log(f"Linhas: {len(df)}")
    log(f"Colunas ({len(df.columns)}): {list(df.columns)}")
    faltando = [c for c in COLUNAS_ESPERADAS if c not in df.columns]
    extras = [c for c in df.columns if c not in COLUNAS_ESPERADAS]
    log(f"Colunas esperadas ausentes: {faltando}")
    log(f"Colunas extras: {extras}")
    log()
    log("Taxa de nulos/vazios por coluna:")
    for c in df.columns:
        vazio = df[c].isna() | (df[c].astype(str).str.strip() == "")
        log(f"  {c:32s} {vazio.mean():6.1%}")

    # ------------------------------------------------------------------
    secao("2. CONSISTÊNCIA DO GABARITO")
    df["_cod"] = df["codigos_sigtap"].apply(parse_codigos)
    df["_itens"] = df["itens_faturaveis"].apply(parse_itens)
    df["_n"] = df["_cod"].apply(len)

    qtde = pd.to_numeric(df.get("qtde_itens_sigtap"), errors="coerce")
    log(f"qtde_itens_sigtap == nº de códigos em codigos_sigtap: {(qtde == df['_n']).mean():.1%}")
    bate = df.apply(lambda r: set(r["_itens"].keys()) == set(r["_cod"]), axis=1)
    log(f"códigos de itens_faturaveis == codigos_sigtap:        {bate.mean():.1%}")
    log(f"Linhas sem nenhum código: {(df['_n'] == 0).sum()}")
    log()
    log("Distribuição de nº de códigos por linha:")
    for n, q in df["_n"].value_counts().sort_index().items():
        log(f"  {n:2d} códigos: {q:5d} linhas ({q / len(df):.1%})")

    # ------------------------------------------------------------------
    secao("3. FREQUÊNCIA DE CADA CÓDIGO (nº de linhas em que aparece)")
    descricoes = {}
    for d in df["_itens"]:
        for k, v in d.items():
            descricoes.setdefault(k, v)
    cont = Counter(c for s in df["_cod"] for c in s)
    log(f"Códigos distintos: {len(cont)}")
    log(f"Códigos com >= 20 linhas: {sum(1 for v in cont.values() if v >= 20)}")
    log(f"Códigos com >= 50 linhas: {sum(1 for v in cont.values() if v >= 50)}")
    log()
    for c, q in cont.most_common():
        desc = descricoes.get(c, "?")[:70]
        log(f"  {formatar_codigo(c)}  {q:5d}  ({q / len(df):5.1%})  {desc}")

    # ------------------------------------------------------------------
    secao("4. PACIENTES E REPETIÇÃO")
    por_pac = df.groupby("prontuario_hash").size()
    log(f"prontuario_hash distintos: {por_pac.size}")
    log(f"Linhas por paciente: média {por_pac.mean():.2f}, mediana {por_pac.median():.0f}, máx {por_pac.max()}")
    faixas = pd.cut(por_pac, bins=[0, 1, 2, 3, 5, 10, 10**6],
                    labels=["1", "2", "3", "4-5", "6-10", ">10"])
    for faixa, q in faixas.value_counts().sort_index().items():
        log(f"  {faixa:>5s} linha(s): {q} pacientes")
    log()
    ev = df["evolucoes"].fillna("").str.strip()
    an = df["anamneses"].fillna("").str.strip()
    log(f"Evoluções vazias: {(ev == '').sum()}")
    log(f"Textos de evolução duplicados exatamente (linhas extras): {ev[ev != ''].duplicated().sum()}")
    log(f"Linhas em que evolucoes == anamneses: {((ev == an) & (ev != '')).sum()}")
    tam = ev.str.len()
    log(f"Tamanho da evolução (caracteres): mediana {tam.median():.0f}, p90 {tam.quantile(.9):.0f}, máx {tam.max()}")

    # ------------------------------------------------------------------
    secao("5. TESTE DA HIPÓTESE 'GABARITO É DO DIA, NÃO DA NOTA'")
    df["_dt"] = pd.to_datetime(df["dthr_evolucao_dt"], errors="coerce")
    df["_dia"] = df["_dt"].dt.date
    log(f"Datas de evolução inválidas: {df['_dt'].isna().sum()}")
    validos = df.dropna(subset=["_dia"])

    grupos_dia = [g for _, g in validos.groupby(["prontuario_hash", "_dia"]) if len(g) > 1]
    log(f"Pares (paciente, dia) com mais de uma linha: {len(grupos_dia)}")
    if grupos_dia:
        iguais, textos_dif, jacs = 0, 0, []
        for g in grupos_dia:
            sets = list(g["_cod"])
            if all(s == sets[0] for s in sets):
                iguais += 1
            if g["evolucoes"].fillna("").str.strip().nunique() > 1:
                textos_dif += 1
            jacs.extend(jaccard(a, b) for a, b in combinations(sets, 2))
        log(f"  ... com textos de evolução diferentes entre si: {textos_dif}")
        log(f"  ... em que TODAS as linhas têm o mesmo conjunto de códigos: {iguais} ({iguais / len(grupos_dia):.1%})")
        log(f"  Jaccard médio entre linhas do mesmo dia: {sum(jacs) / len(jacs):.3f}")

    jacs_base = []
    for _, g in validos.sort_values("_dt").groupby("prontuario_hash"):
        por_dia = g.groupby("_dia")["_cod"].first().tolist()
        jacs_base.extend(jaccard(a, b) for a, b in zip(por_dia, por_dia[1:]))
    if jacs_base:
        log(f"Base de comparação, mesmo paciente em dias consecutivos distintos: "
            f"{len(jacs_base)} pares, Jaccard médio {sum(jacs_base) / len(jacs_base):.3f}")
    log("(Jaccard do mesmo dia bem maior que o de dias distintos, com textos diferentes,")
    log(" indica que o gabarito é do dia/conta e não da nota individual.)")

    # ------------------------------------------------------------------
    secao("6. COLUNAS DE AGRUPAMENTO E LABEL")
    for col in ["annotation_group", "unidades_funcionais", "ano_evolucao", "mes_evolucao"]:
        if col in df.columns:
            log(f"{col}:")
            for v, q in df[col].value_counts(dropna=False).head(20).items():
                log(f"  {str(v)[:60]:60s} {q}")
    if "annotation_group" in df.columns and "annotation_group_row" in df.columns:
        agr = pd.to_numeric(df["annotation_group_row"], errors="coerce")
        log()
        log("annotation_group_row por grupo (min, máx, nº linhas):")
        for grp, s in agr.groupby(df["annotation_group"]):
            log(f"  grupo {grp}: {s.min():.0f} a {s.max():.0f}, {len(s)} linhas")

    if "label" in df.columns:
        log()
        lab = df["label"]
        log(f"label: {lab.nunique(dropna=False)} valores distintos, nulos {lab.isna().mean():.1%}")
        for v, q in lab.value_counts(dropna=False).head(20).items():
            log(f"  {str(v)[:80]:80s} {q}")
        if lab.nunique() <= 20:
            log()
            log("Nº médio de códigos por valor de label:")
            for v, m in df.groupby("label")["_n"].mean().items():
                log(f"  {str(v)[:60]:60s} {m:.2f}")
            log()
            log("Código mais frequente por valor de label (top 3):")
            for v, g in df.groupby("label"):
                top = Counter(c for s in g["_cod"] for c in s).most_common(3)
                log(f"  {str(v)[:40]:40s} " + ", ".join(f"{formatar_codigo(c)}({q})" for c, q in top))
    else:
        log("Coluna 'label' não encontrada.")

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / "diagnostico_saida.txt"
    log()
    log(f"Saída gravada em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()