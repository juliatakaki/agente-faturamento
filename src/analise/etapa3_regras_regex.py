#!/usr/bin/env python3
"""
Etapa 3 - Regras de regex/scoring para códigos com pista textual forte,
avaliadas em pacientes separados (treino x teste).

Uso (a partir da raiz do projeto):
    python src/analise/etapa3_regras_regex.py data/data-completo.xlsx

O que faz
1. Divide os PACIENTES (prontuario_hash) em treino (70%) e teste (30%), com semente fixa.
   Evoluções do mesmo paciente nunca ficam nos dois grupos.
2. Refaz a mineração de termos distintivos só no treino, para conferir que as pistas
   usadas nas regras aparecem sem olhar o teste.
3. Para cada código, soma os pesos das pistas encontradas no texto (score) e escolhe,
   só no treino, o limiar de score que maximiza o F1.
4. Mede precisão, recall e F1 no teste, no total e por anotador.

Saídas em reports/analise-gabarito/
- etapa3_regras.txt       relatório agregado
- etapa3_predicoes.csv    uma linha por evolução (só source_row_id, grupo, split, scores e
                          predições, sem texto), para inspecionar os erros depois
"""
import argparse
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "reports" / "analise-gabarito"

SEMENTE = 42
FRACAO_TESTE = 0.30

# ----------------------------------------------------------------------
# Regras. Cada código tem uma lista de (nome, regex, peso). O texto é
# normalizado antes (minúsculas, sem acentos, tags de anonimização removidas).
# Peso negativo = pista contra o código.
# ----------------------------------------------------------------------
REGRAS = {
    "0401010015": ("CURATIVO GRAU II", [
        ("realizo/realizado curativo", r"\brealiz\w*\s+(a\s+)?(troca\s+de\s+)?curativo", 3),
        ("bloco curativos",            r"\bcurativos\b", 2),
        ("curativo",                   r"\bcurativo\b", 1),
        ("limpeza com sf",             r"\blimpeza\s+com\s+sf", 1),
        ("clorexidina",                r"\bclorexidina\b", 1),
        ("ocluo/oclusao",              r"\b(ocluo|ocluido|oclusao)\b", 1),
        ("cobertura especial",         r"\b(alginato|hidrogel|hidrocoloide|espuma|alevyn|aguacel)\b", 1),
        ("so mantenho curativo",       r"\bmantenho\s+curativo", -1),
    ]),
    "0211080020": ("GASOMETRIA", [
        ("realizado/coletado gasometria", r"\b(realiz|colet)\w*\s+(a\s+)?gasometria", 3),
        ("gasometria",                    r"\bgasometria\b", 1),
        ("gasa/gaso",                     r"\bgas[ao]\b", 1),
        ("ph",                            r"\bph\b", 1),
        ("pao2/po2",                      r"\b(pao2|po2)\b", 1),
        ("paco2/pco2",                    r"\b(paco2|pco2)\b", 1),
        ("hco3/bic/be",                   r"\b(hco3|bic|be)\b", 1),
    ]),
    "0305010131": ("HEMODIALISE", [
        ("hd",                  r"\bhd\b", 2),
        ("hemodialise/dialise", r"\b(hemo)?dialise\b", 2),
        ("uf",                  r"\buf\b", 2),
        ("trs",                 r"\btrs\b", 1),
        ("nefrologia",          r"\bnefro(logia)?\b", 1),
        ("cdl",                 r"\bcdl\b", 1),
    ]),
    "0301100071": ("CUIDADOS C/ TRAQUEOSTOMIA", [
        ("tqt",                 r"\btqt\b", 2),
        ("traqueostomia",       r"\btraqueostomi\w*", 2),
        ("cuff",                r"\bcuff\b", 1),
        ("acoplado/via tqt",    r"\b(via|em|sob|por|acoplad\w*\s+a)\s+tqt\b", 1),
        ("programar tqt",       r"\b(programar|programo|indicacao\s+de|aguarda\w*)\s+tqt\b", -2),
    ]),
    "0302040021": ("FISIOTERAPIA RESPIRATORIA", [
        ("secao fisio respiratoria", r"\bfisioterapia\s+respiratoria\s*:", 3),
        ("cabecalho fisioterapia",   r"\bevolucao\s+(de\s+|da\s+)?fisioterapia", 2),
        ("monitorizacao ventilatoria", r"\bmonitorizacao\s+ventilatoria\b", 1),
        ("aparelho locomotor",       r"\baparelho\s+locomotor\b", 1),
    ]),
    "0302050027": ("FISIOTERAPIA MOTORA", [
        ("secao fisio motora",       r"\bfisioterapia\s+motora\s*:", 3),
        ("cabecalho fisioterapia",   r"\bevolucao\s+(de\s+|da\s+)?fisioterapia", 2),
        ("aparelho locomotor",       r"\baparelho\s+locomotor\b", 1),
        ("cinesioterapia/sedestacao", r"\b(cinesioterapia|sedestacao|ortostatismo|mobilizacao)\b", 1),
    ]),
}

STOP = set("""a o as os e de da do das dos em no na nos nas com sem para por pelo pela pelos pelas um uma uns
umas ao aos que se ou mas como mais menos muito ja nao sim foi ser esta estao seu sua seus suas ele ela eles
elas lhe isso este esse essa entre ate apos sob sobre the h x""".split())

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
    """Minúsculas, sem acentos, sem tags [ANONIMIZACAO], espaços colapsados. Mantém ':'."""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = t.replace("²", "2")
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"[^a-z0-9:]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def ngramas(texto_norm: str) -> set:
    tok = [w for w in texto_norm.replace(":", " ").split() if re.search(r"[a-z]", w) and len(w) >= 2]
    s = set()
    for n in (1, 2, 3):
        for i in range(len(tok) - n + 1):
            g = tok[i:i + n]
            if g[0] in STOP or g[-1] in STOP:
                continue
            s.add(" ".join(g))
    return s


def parse_codigos(valor) -> frozenset:
    if pd.isna(valor):
        return frozenset()
    partes = (re.sub(r"\D", "", p) for p in str(valor).split(";"))
    return frozenset(p for p in partes if p)


def formatar_codigo(c: str) -> str:
    return f"{c[0:2]}.{c[2:4]}.{c[4:6]}.{c[6:9]}-{c[9]}" if len(c) == 10 else c


def score(texto_norm: str, regras) -> int:
    return sum(peso for _, rx, peso in regras if re.search(rx, texto_norm))


def metricas(ouro, pred):
    tp = sum(1 for o, p in zip(ouro, pred) if o and p)
    fp = sum(1 for o, p in zip(ouro, pred) if not o and p)
    fn = sum(1 for o, p in zip(ouro, pred) if o and not p)
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if tp else 0.0
    return dict(tp=tp, fp=fp, fn=fn, prec=prec, rec=rec, f1=f1)


def fmt(x):
    return "  -  " if isinstance(x, float) and math.isnan(x) else f"{x:5.2f}"


def minerar_treino(treino: pd.DataFrame, codigo: str, k=6):
    """Mesmo critério da aba 'Padrões no texto', aplicado só no treino."""
    N = len(treino)
    dfw = Counter(g for s in treino["_ng"] for g in s)
    mask = treino["_cod"].apply(lambda s: codigo in s)
    A, B = treino[mask], treino[~mask]
    nA, nB = len(A), len(B)
    if nA < 5:
        return []
    yA = Counter(g for s in A["_ng"] for g in s)
    yB = Counter(g for s in B["_ng"] for g in s)
    pac = defaultdict(set)
    for h, s in zip(A["prontuario_hash"], A["_ng"]):
        for g in s:
            pac[g].add(h)
    linhas = []
    for g, ya in yA.items():
        if dfw[g] < 5:
            continue
        yb = yB.get(g, 0)
        pA, pB = ya / nA, yb / nB
        if pA < 0.25 or len(pac[g]) < 5 or (pB and pA / pB < 3):
            continue
        p = dfw[g] / N
        a, b = 10 * p, 10 * (1 - p)
        d = math.log((ya + a) / (nA - ya + b)) - math.log((yb + a) / (nB - yb + b))
        v = 1 / (ya + a) + 1 / (nA - ya + b) + 1 / (yb + a) + 1 / (nB - yb + b)
        linhas.append((d / math.sqrt(v), g, pA, pB))
    linhas.sort(reverse=True)
    escolhidos = []
    for z, g, pA, pB in linhas:
        if any(g in e or e in g for e, _, _ in escolhidos):
            continue
        escolhidos.append((g, pA, pB))
        if len(escolhidos) == k:
            break
    return escolhidos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    args = ap.parse_args()

    df = carregar(Path(args.planilha))
    df.columns = [c.strip() for c in df.columns]
    df["_cod"] = df["codigos_sigtap"].apply(parse_codigos)
    df["_txt"] = df["evolucoes"].fillna("").apply(normalizar)
    df["_ng"] = df["_txt"].apply(ngramas)

    # --- divisão por paciente ---
    pacientes = sorted(df["prontuario_hash"].unique())
    random.Random(SEMENTE).shuffle(pacientes)
    n_teste = round(len(pacientes) * FRACAO_TESTE)
    teste_pac = set(pacientes[:n_teste])
    df["split"] = df["prontuario_hash"].apply(lambda h: "teste" if h in teste_pac else "treino")
    treino, teste = df[df["split"] == "treino"], df[df["split"] == "teste"]

    secao("1. DIVISÃO POR PACIENTE")
    log(f"Semente {SEMENTE}, {FRACAO_TESTE:.0%} dos pacientes no teste")
    log(f"Treino: {treino['prontuario_hash'].nunique()} pacientes, {len(treino)} evoluções")
    log(f"Teste:  {teste['prontuario_hash'].nunique()} pacientes, {len(teste)} evoluções")
    log()
    log("Evoluções com cada código (treino / teste):")
    for c, (nome, _) in REGRAS.items():
        ntr = treino["_cod"].apply(lambda s: c in s).sum()
        nte = teste["_cod"].apply(lambda s: c in s).sum()
        log(f"  {formatar_codigo(c)} {nome:28s} {ntr:4d} / {nte:3d}")

    secao("2. PISTAS MINERADAS SÓ NO TREINO (conferência, mesmo critério da aba 2)")
    for c, (nome, _) in REGRAS.items():
        pistas = minerar_treino(treino, c)
        txt = "; ".join(f"{g} ({pA:.0%} vs {pB:.0%})" for g, pA, pB in pistas) or "nenhum termo passa no critério"
        log(f"{formatar_codigo(c)} {nome}")
        log(f"   {txt}")

    secao("3. LIMIAR ESCOLHIDO NO TREINO E RESULTADO NO TESTE")
    resultados = {}
    for c, (nome, regras) in REGRAS.items():
        df[f"score_{c}"] = df["_txt"].apply(lambda t: score(t, regras))
        df[f"ouro_{c}"] = df["_cod"].apply(lambda s: c in s)
        tr = df[df["split"] == "treino"]
        candidatos = sorted(set(tr[f"score_{c}"]) | {max(tr[f"score_{c}"]) + 1})
        melhor = max(candidatos, key=lambda L: (metricas(tr[f"ouro_{c}"], tr[f"score_{c}"] >= L)["f1"], -L))
        df[f"pred_{c}"] = df[f"score_{c}"] >= melhor
        tr = df[df["split"] == "treino"]
        te = df[df["split"] == "teste"]
        m_tr = metricas(tr[f"ouro_{c}"], tr[f"pred_{c}"])
        m_te = metricas(te[f"ouro_{c}"], te[f"pred_{c}"])
        resultados[c] = (nome, melhor, m_tr, m_te)

    log(f"{'código':16s}{'nome':28s}{'limiar':>7s} | {'F1 treino':>9s} | {'TP':>4s}{'FP':>4s}{'FN':>4s} {'prec':>6s}{'rec':>6s}{'F1':>6s}  (teste)")
    for c, (nome, L, mtr, mte) in resultados.items():
        log(f"{formatar_codigo(c):16s}{nome:28s}{L:7d} | {fmt(mtr['f1']):>9s} | "
            f"{mte['tp']:4d}{mte['fp']:4d}{mte['fn']:4d} {fmt(mte['prec'])} {fmt(mte['rec'])} {fmt(mte['f1'])}")

    tp = sum(r[3]["tp"] for r in resultados.values())
    fp = sum(r[3]["fp"] for r in resultados.values())
    fn = sum(r[3]["fn"] for r in resultados.values())
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    log()
    log(f"Micro-média no teste (6 códigos): TP {tp}, FP {fp}, FN {fn}, precisão {p:.2f}, recall {r:.2f}, "
        f"F1 {2 * p * r / (p + r):.2f}")

    secao("4. TESTE POR ANOTADOR (precisão / recall; '-' = sem casos)")
    te = df[df["split"] == "teste"]
    grupos = sorted(te["annotation_group"].unique(), key=str)
    cab = "".join(f"{'anot ' + str(g):>16s}" for g in grupos)
    log(f"{'código':16s}{'nome':28s}{cab}")
    for c, (nome, *_rest) in resultados.items():
        celulas = []
        for g in grupos:
            sub = te[te["annotation_group"] == g]
            m = metricas(sub[f"ouro_{c}"], sub[f"pred_{c}"])
            celulas.append(f"{fmt(m['prec']).strip()}/{fmt(m['rec']).strip()} (n={m['tp'] + m['fn']})")
        log(f"{formatar_codigo(c):16s}{nome:28s}" + "".join(f"{x:>16s}" for x in celulas))

    secao("5. QUAIS PISTAS DISPARAM NOS ERROS DO TESTE (contagem de evoluções)")
    for c, (nome, regras) in REGRAS.items():
        fpm = te[te[f"pred_{c}"] & ~te[f"ouro_{c}"]]
        fnm = te[~te[f"pred_{c}"] & te[f"ouro_{c}"]]
        log(f"{formatar_codigo(c)} {nome}  (FP={len(fpm)}, FN={len(fnm)})")
        for rot, sub in [("FP", fpm), ("FN", fnm)]:
            if not len(sub):
                continue
            cont = Counter(n for t in sub["_txt"] for n, rx, _ in regras if re.search(rx, t))
            txt = ", ".join(f"{n} {q}" for n, q in cont.most_common()) or "nenhuma pista no texto"
            log(f"   {rot}: {txt}")

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    cols = ["source_row_id", "annotation_group", "split"] + [
        f"{p}_{c}" for c in REGRAS for p in ("ouro", "score", "pred")]
    destino_csv = PASTA_SAIDA / "etapa3_predicoes.csv"
    df[cols].to_csv(destino_csv, index=False, encoding="utf-8")
    destino = PASTA_SAIDA / "etapa3_regras.txt"
    log()
    log(f"Relatório gravado em {destino}")
    log(f"Predições gravadas em {destino_csv}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()