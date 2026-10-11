#!/usr/bin/env python3
"""
Etapa 8 - Regra de data: descartar menções de procedimento/exame cuja data
escrita no texto é anterior à data da própria evolução.

Uso (a partir da raiz do projeto, com o venv ativado):
    python src/analise/etapa8_datas.py data/data-completo.xlsx

Não usa LLM. Mesma divisão por paciente da etapa 3 (semente 42, 30% teste).
A configuração da regra é escolhida SÓ no treino e depois medida no teste.

Como a regra funciona
  1. Data da nota = coluna dthr_evolucao_dt da planilha (no uso real, vem do
     sistema do hospital junto com o texto). Se estiver vazia, usa a primeira
     data dd/mm(/aa) do cabeçalho do texto.
  2. Para cada menção do termo (ex. "ECG"), procura a data mais próxima numa
     janela logo depois ("ECG (16/09/25)", "TC de crânio em 07/10") ou logo
     antes ("29/01 VDRL / Anti HIV"), sem atravessar um '#' de seção.
  3. A menção é ANTIGA se essa data for anterior à data de referência. Duas
     referências são testadas: a data da evolução (com tolerância de 0 ou 1
     dia, porque notas noturnas citam exames do dia anterior) e a data da
     anamnese (coluna dthr_anamnese_dt, admissão), mais conservadora.
  4. O código é descartado na evolução só se TODAS as menções forem antigas.
     Menção sem data perto conta como atual.

Como é medida (sem IA)
  Simula um extrator que sugere o código sempre que o termo aparece no texto
  ("menção"), e compara com o mesmo extrator depois da regra ("menção + data").
  O que interessa é quanto a regra tira de erro sem tirar acerto.

Saída: reports/analise-gabarito/etapa8_datas.txt (só números agregados).
"""
import argparse
import random
import re
import unicodedata
from datetime import date, timedelta
from itertools import product
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "reports" / "analise-gabarito"

SEMENTE = 42
FRACAO_TESTE = 0.30
CABECALHO_CHARS = 300

# Configurações testadas no treino
JANELAS_DEPOIS = (0, 20, 40)        # caracteres depois do termo
JANELAS_ANTES = (0, 40, 80, 120)    # caracteres antes do termo
TOLERANCIAS = (0, 1)                # dias de tolerância (só para a referência evolução)
REFERENCIAS = ("evolucao", "anamnese")

# (nome, códigos que contam como acerto, regex do termo no texto leve)
ITENS = [
    ("GASOMETRIA",        {"0211080020"}, r"\b(gasometria|gaso|gasa)\b"),
    ("ELETROCARDIOGRAMA", {"0211020036"}, r"\b(ecg|eletrocardiograma)\b"),
    ("HEMODIALISE",       {"0305010131", "0305010042"}, r"\b(hd|hemodialise|dialise)\b"),
    ("TC DE CRANIO",      {"0206010079"},
     r"\b(tc|tomografia)( computadorizada)? (de |do )?cranio\b"),
    ("RX DE TORAX",       {"0204030170", "0204030153"},
     r"\b(rx|raio x|radiografia)( de| do)? torax\b"),
    ("HEMOGRAMA",         {"0202020380"}, r"\bhemograma\b"),
]

# Não pega frequências e frações como "12/12h", "ml/12h" ou "200ml/12h"
RX_DATA = re.compile(r"(?<![\d/a-z])(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?(?![\d/a-z])")

SAIDA = []


def log(txt=""):
    print(txt)
    SAIDA.append(str(txt))


def secao(titulo):
    log()
    log("=" * 96)
    log(titulo)
    log("=" * 96)


def carregar(caminho: Path) -> pd.DataFrame:
    if caminho.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(caminho, dtype=str)
    with open(caminho, encoding="utf-8-sig", errors="replace") as f:
        primeira = f.readline()
    sep = max(["\t", ";", ","], key=primeira.count)
    return pd.read_csv(caminho, sep=sep, dtype=str, encoding="utf-8-sig")


def parse_codigos(valor) -> frozenset:
    if pd.isna(valor):
        return frozenset()
    return frozenset(p for p in (re.sub(r"\D", "", x) for x in str(valor).split(";")) if p)


def leve(texto) -> str:
    """Minúsculas, sem acento, sem tags [ANONIMIZACAO]. Mantém '/', '#' e pontuação."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"\[[^\]]*\]", " ", t)
    return re.sub(r"[ \t]+", " ", t)


def _ano(a, ref_ano):
    if a is None:
        return None
    a = int(a)
    return a + 2000 if a < 100 else a


def data_da_nota(t: str):
    for m in RX_DATA.finditer(t[:CABECALHO_CHARS]):
        d, mes, a = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= d <= 31 and 1 <= mes <= 12:
            ano = _ano(a, None) or 2025
            try:
                return date(ano, mes, d)
            except ValueError:
                continue
    return None


def datas_no_texto(t: str, nota: date):
    """Lista (inicio, fim, date) de datas válidas no texto, com o ano inferido."""
    saida = []
    for m in RX_DATA.finditer(t):
        d, mes, a = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= d <= 31 and 1 <= mes <= 12):
            continue
        ano = _ano(a, nota.year) or nota.year
        try:
            dt = date(ano, mes, d)
        except ValueError:
            continue
        # sem ano escrito e "no futuro": é do ano anterior (ex. nota 05/01, data 28/12)
        if a is None and dt > nota + timedelta(days=1):
            try:
                dt = date(ano - 1, mes, d)
            except ValueError:
                continue
        saida.append((m.start(), m.end(), dt))
    return saida


def para_data(valor):
    """Converte o valor da coluna de data/hora da planilha em date, ou None."""
    if valor is None or (isinstance(valor, float) and valor != valor) or str(valor).strip() == "":
        return None
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dt = pd.to_datetime(str(valor).strip(), errors="coerce", dayfirst=True)
    return None if pd.isna(dt) else dt.date()


def mencao_antiga(t, ini, fim, datas, nota, depois, antes, tol) -> bool:
    """A data mais próxima da menção, dentro da janela e sem cruzar '#', é anterior à referência?"""
    melhor = None
    for di, df, dt in datas:
        if depois and fim <= di <= fim + depois and "#" not in t[fim:di]:
            dist = di - fim
        elif antes and ini - antes <= df <= ini and "#" not in t[df:ini]:
            dist = ini - df
        else:
            continue
        if melhor is None or dist < melhor[0]:
            melhor = (dist, dt)
    if melhor is None:
        return False
    return melhor[1] < nota - timedelta(days=tol)


def avaliar(df, item_rx, cods, depois, antes, tol, ref="evolucao"):
    """Devolve (tp, fp, fn) de 'menção' e de 'menção + data' para um item."""
    base = [0, 0, 0]
    filt = [0, 0, 0]
    col_ref = "_nota" if ref == "evolucao" else "_anam"
    if ref == "anamnese":
        tol = 0
    for t, nota, datas, ouro_set in zip(df["_leve"], df[col_ref], df["_datas"], df["_cod"]):
        if nota is not None and nota != nota:
            nota = None
        ouro = bool(ouro_set & cods)
        mencoes = [(m.start(), m.end()) for m in re.finditer(item_rx, t)]
        pred_base = bool(mencoes)
        pred_filt = pred_base
        if pred_base and nota is not None and (depois or antes):
            pred_filt = not all(
                mencao_antiga(t, i, f, datas, nota, depois, antes, tol) for i, f in mencoes)
        for acc, p in ((base, pred_base), (filt, pred_filt)):
            acc[0] += ouro and p
            acc[1] += (not ouro) and p
            acc[2] += ouro and not p
    return base, filt


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if tp else 0.0
    return p, r, f


def fmt(x):
    return "  -  " if x != x else f"{x:5.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    args = ap.parse_args()

    df = carregar(Path(args.planilha))
    df.columns = [c.strip() for c in df.columns]
    df["_cod"] = df["codigos_sigtap"].apply(parse_codigos)
    df["_leve"] = df["evolucoes"].fillna("").apply(leve)
    df["_nota_cab"] = df["_leve"].apply(data_da_nota)
    tem_col = "dthr_evolucao_dt" in df.columns
    tem_anam = "dthr_anamnese_dt" in df.columns
    df["_nota_col"] = df["dthr_evolucao_dt"].apply(para_data) if tem_col else None
    df["_nota"] = [c if c is not None else h for c, h in zip(df["_nota_col"], df["_nota_cab"])]
    df["_anam"] = df["dthr_anamnese_dt"].apply(para_data) if tem_anam else None
    df["_datas"] = [datas_no_texto(t, n) if n else [] for t, n in zip(df["_leve"], df["_nota"])]

    pacientes = sorted(df["prontuario_hash"].unique())
    random.Random(SEMENTE).shuffle(pacientes)
    teste_pac = set(pacientes[:round(len(pacientes) * FRACAO_TESTE)])
    treino = df[~df["prontuario_hash"].isin(teste_pac)]
    teste = df[df["prontuario_hash"].isin(teste_pac)]

    secao("ETAPA 8 - REGRA DE DATA")
    for nome, sub in (("treino", treino), ("teste", teste)):
        n = len(sub)
        n_col = sum(1 for x in sub["_nota_col"] if x is not None)
        n_cab = sum(1 for x in sub["_nota_cab"] if x is not None)
        n_nota = sum(1 for x in sub["_nota"] if x is not None)
        n_anam = sum(1 for x in sub["_anam"] if x is not None)
        log(f"{nome:7s} {n} evoluções. Data da evolução pela coluna {n_col} ({n_col / n:.0%}), "
            f"pelo cabeçalho {n_cab} ({n_cab / n:.0%}), usada {n_nota} ({n_nota / n:.0%}). "
            f"Data da anamnese {n_anam} ({n_anam / n:.0%}).")
    ambos = [(c, h) for c, h in zip(df["_nota_col"], df["_nota_cab"]) if c and h]
    if ambos:
        igual = sum(1 for c, h in ambos if c == h)
        perto = sum(1 for c, h in ambos if abs((c - h).days) <= 1)
        log(f"Conferência coluna x cabeçalho ({len(ambos)} com as duas): mesma data {igual} "
            f"({igual / len(ambos):.0%}), até 1 dia de diferença {perto} ({perto / len(ambos):.0%}).")

    # ── 1. escolha da configuração no treino ─────────────────────────────
    secao("1. CONFIGURAÇÃO ESCOLHIDA NO TREINO (micro-média dos itens)")
    resultados = []
    for ref, depois, antes, tol in product(REFERENCIAS, JANELAS_DEPOIS, JANELAS_ANTES, TOLERANCIAS):
        if (not depois and not antes) or (ref == "anamnese" and tol):
            continue
        tot_b, tot_f = [0, 0, 0], [0, 0, 0]
        for _, cods, rx in ITENS:
            b, f = avaliar(treino, rx, cods, depois, antes, tol, ref)
            tot_b = [x + y for x, y in zip(tot_b, b)]
            tot_f = [x + y for x, y in zip(tot_f, f)]
        resultados.append((prf(*tot_f)[2], depois, antes, tol, tot_b, tot_f, ref))
    resultados.sort(key=lambda x: (-x[0], x[1] + x[2], x[3]))

    tot_b = resultados[0][4]
    p, r, f = prf(*tot_b)
    log(f"{'configuração':40s}{'TP':>5s}{'FP':>5s}{'FN':>5s}   {'prec':>6s}{'rec':>6s}{'F1':>6s}")
    log(f"{'só menção (sem regra)':40s}{tot_b[0]:5d}{tot_b[1]:5d}{tot_b[2]:5d}   "
        f"{fmt(p)} {fmt(r)} {fmt(f)}")
    def rotulo(ref, depois, antes, tol):
        r = "evolução" if ref == "evolucao" else "anamnese"
        return f"{r}, depois {depois}, antes {antes}" + (f", tol {tol}d" if ref == "evolucao" else "")

    for f1, depois, antes, tol, _, tf, ref in resultados[:6]:
        p, r, f = prf(*tf)
        log(f"{rotulo(ref, depois, antes, tol):40s}{tf[0]:5d}{tf[1]:5d}{tf[2]:5d}   {fmt(p)} {fmt(r)} {fmt(f)}")
    melhor_anam = next((x for x in resultados if x[6] == "anamnese"), None)
    if melhor_anam and melhor_anam not in resultados[:6]:
        f1, depois, antes, tol, _, tf, ref = melhor_anam
        p, r, f = prf(*tf)
        log(f"{rotulo(ref, depois, antes, tol):40s}{tf[0]:5d}{tf[1]:5d}{tf[2]:5d}   {fmt(p)} {fmt(r)} {fmt(f)}"
            f"   (melhor com anamnese)")
    _, D, A, T, _, _, REF = resultados[0]
    log()
    log(f"Escolhida: referência {'evolução' if REF == 'evolucao' else 'anamnese'}, janela depois "
        f"{D} caracteres, antes {A} caracteres, tolerância {T} dia(s).")

    # ── 2. por item, treino e teste ──────────────────────────────────────
    secao("2. POR ITEM, COM A CONFIGURAÇÃO ESCOLHIDA (prec / rec)")
    log(f"{'item':20s}{'grupo':>7s}{'n':>5s} | {'só menção':>13s} | {'menção + data':>13s} | "
        f"{'erros tirados':>13s}{'acertos perdidos':>18s}")
    tot = {"treino": [[0, 0, 0], [0, 0, 0]], "teste": [[0, 0, 0], [0, 0, 0]]}
    for nome, cods, rx in ITENS:
        for g, sub in (("treino", treino), ("teste", teste)):
            b, f = avaliar(sub, rx, cods, D, A, T, REF)
            tot[g][0] = [x + y for x, y in zip(tot[g][0], b)]
            tot[g][1] = [x + y for x, y in zip(tot[g][1], f)]
            pb, rb, _ = prf(*b)
            pf, rf, _ = prf(*f)
            n = b[0] + b[2]
            log(f"{nome:20s}{g:>7s}{n:5d} | {fmt(pb)} / {fmt(rb)} | {fmt(pf)} / {fmt(rf)} | "
                f"{b[1] - f[1]:13d}{b[0] - f[0]:18d}")
    log()
    for g in ("treino", "teste"):
        b, f = tot[g]
        pb, rb, fb = prf(*b)
        pf, rf, ff = prf(*f)
        log(f"Total {g:7s} só menção prec {pb:.2f} rec {rb:.2f} F1 {fb:.2f}  |  "
            f"menção + data prec {pf:.2f} rec {rf:.2f} F1 {ff:.2f}  |  "
            f"erros tirados {b[1] - f[1]}, acertos perdidos {b[0] - f[0]}")

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / "etapa8_datas.txt"
    log()
    log(f"Relatório gravado em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()