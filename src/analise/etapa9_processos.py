#!/usr/bin/env python3
"""
Etapa 9 - Como os anotadores marcam os códigos de processo (diária, consultas,
coleta, oxigenoterapia)? Análise descritiva para desenhar regras.

Uso (a partir da raiz do projeto, com o venv ativado):
    python src/analise/etapa9_processos.py data/data-completo.xlsx

Não usa LLM. Só no grupo de TREINO (mesma divisão da etapa 3), porque as regras
desenhadas a partir daqui serão medidas depois no teste.

Seções
  1. Quanto cada código é marcado por tipo de nota (médica, enfermagem, ...).
  2. Quanto cada anotador marca, no total e no tipo de nota em que o código é
     mais comum.
  3. Por paciente e dia: quando há várias notas no mesmo dia, o código aparece
     em uma só ou em todas? E em qual tipo de nota?
  4. Termos candidatos (coleta, oxigenoterapia): aparecem mais nas notas
     marcadas do que nas não marcadas?

Saída: reports/analise-gabarito/etapa9_processos.txt (só números agregados).
"""
import argparse
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "reports" / "analise-gabarito"
SEMENTE = 42
FRACAO_TESTE = 0.30

PROCESSOS = [
    ("0802010083", "DIARIA UTI II"),
    ("0301010170", "CONSULTA PAC. INTERNADO"),
    ("0301010048", "CONSULTA NIVEL SUPERIOR"),
    ("0201020041", "COLETA P/ EXAME"),
    ("0301100144", "OXIGENOTERAPIA"),
]

# Tipo de nota pelo cabeçalho (primeiras linhas). A ordem importa.
TIPOS = [
    ("fisioterapia", r"fisioterap"),
    ("enfermagem", r"enfermag"),
    ("nutricao", r"nutri"),
    ("fonoaudiologia", r"fono"),
    ("psicologia", r"psicolog"),
    ("servico social", r"servico social|assistente social"),
    ("farmacia", r"farmac"),
    ("medica", r"medic|clinica medica|plantao"),
]

TERMOS = {
    "0201020041": [
        ("coletado/colhido", r"\b(colet|colhid)\w*"),
        ("exames de rotina", r"\bexames? (de )?rotina\b"),
        ("hemocultura", r"\bhemocultura"),
        ("gasometria", r"\bgasometria|\bgaso\b"),
        ("laboratorio/labs", r"\blaborat\w*|\blabs?\b"),
        ("hb/leuco/plaq", r"\b(hb|leuco\w*|plaq\w*)\b"),
        ("solicito exames", r"\bsolicit\w* (de )?exames"),
    ],
    "0301100144": [
        ("cateter nasal / cn", r"\bcateter nasal\b|\bcn\b|\bcnaf\b"),
        ("o2 / oxigenio", r"\bo2\b|\boxigeni\w*"),
        ("mascara / venturi", r"\bmascara\b|\bventuri\b|\bmacronebuliz\w*"),
        ("vm / ventilacao mecanica", r"\bvm\b|\bventilacao mecanica\b"),
        ("tot / tqt", r"\btot\b|\btqt\b"),
        ("vni / bipap / cpap", r"\bvni\b|\bbipap\b|\bcpap\b"),
        ("fio2", r"\bfio2\b"),
        ("ar ambiente / aa", r"\bar ambiente\b|\baa\b"),
        ("l/min", r"\bl ?/ ?min\b|\blpm\b"),
    ],
}

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


def normalizar(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"[^a-z0-9:/ \n]+", " ", t)
    return re.sub(r"[ \t]+", " ", t)


def tipo_nota(texto_norm: str) -> str:
    linhas = [l.strip() for l in texto_norm.splitlines() if re.search(r"[a-z]", l)][:3]
    cab = " ".join(linhas)
    for nome, rx in TIPOS:
        if re.search(rx, cab):
            return nome
    return "outro"


def para_data(valor):
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(valor or ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def pct(n, d):
    return f"{n / d:5.0%}" if d else "   - "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    args = ap.parse_args()

    df = carregar(Path(args.planilha))
    df.columns = [c.strip() for c in df.columns]
    df["_cod"] = df["codigos_sigtap"].apply(parse_codigos)
    df["_txt"] = df["evolucoes"].fillna("").apply(normalizar)
    df["_tipo"] = df["_txt"].apply(tipo_nota)
    df["_dia"] = df["dthr_evolucao_dt"].apply(para_data) if "dthr_evolucao_dt" in df.columns else None
    df["_anot"] = df["annotation_group"].astype(str)

    pacientes = sorted(df["prontuario_hash"].unique())
    random.Random(SEMENTE).shuffle(pacientes)
    teste_pac = set(pacientes[:round(len(pacientes) * FRACAO_TESTE)])
    tr = df[~df["prontuario_hash"].isin(teste_pac)].copy()

    secao("ETAPA 9 - CÓDIGOS DE PROCESSO (só TREINO)")
    log(f"{len(tr)} evoluções, {tr['prontuario_hash'].nunique()} pacientes.")
    log("Tipos de nota (pelo cabeçalho): " + ", ".join(
        f"{t} {q}" for t, q in Counter(tr["_tipo"]).most_common()))
    diarias = Counter(c for s in tr["_cod"] for c in s if c.startswith("0802"))
    if diarias:
        log("Códigos de diária (08.02) no treino: " + ", ".join(f"{c} ({q})" for c, q in diarias.most_common()))

    tipos = [t for t, _ in Counter(tr["_tipo"]).most_common()]
    anots = sorted(tr["_anot"].unique())

    # ── 1. por tipo de nota ──────────────────────────────────────────────
    secao("1. % DAS NOTAS MARCADAS, POR TIPO DE NOTA")
    cab = "".join(f"{t[:11]:>13s}" for t in tipos)
    log(f"{'código':26s}{'total':>7s}{cab}")
    log(f"{'(n notas)':26s}{len(tr):7d}" + "".join(f"{(tr['_tipo'] == t).sum():13d}" for t in tipos))
    tipo_dom = {}
    for cod, nome in PROCESSOS:
        marc = tr["_cod"].apply(lambda s: cod in s)
        celulas = []
        melhor = (-1, None)
        for t in tipos:
            sub = marc[tr["_tipo"] == t]
            celulas.append(pct(sub.sum(), len(sub)))
            if len(sub) >= 5 and sub.mean() > melhor[0]:
                melhor = (sub.mean(), t)
        tipo_dom[cod] = melhor[1]
        log(f"{nome:26s}{pct(marc.sum(), len(tr)):>7s}" + "".join(f"{c:>13s}" for c in celulas))

    # ── 2. por anotador ──────────────────────────────────────────────────
    secao("2. % MARCADAS POR ANOTADOR (total / só no tipo de nota em que o código é mais comum)")
    log(f"{'código':26s}{'tipo dominante':>16s}" + "".join(f"{'anot ' + a:>16s}" for a in anots))
    for cod, nome in PROCESSOS:
        t = tipo_dom[cod]
        celulas = []
        for a in anots:
            sub = tr[tr["_anot"] == a]
            m_tot = sub["_cod"].apply(lambda s: cod in s)
            sub_t = sub[sub["_tipo"] == t]
            m_t = sub_t["_cod"].apply(lambda s: cod in s)
            celulas.append(f"{pct(m_tot.sum(), len(sub)).strip()}/{pct(m_t.sum(), len(sub_t)).strip()}"
                           f" ({len(sub_t)})")
        log(f"{nome:26s}{str(t):>16s}" + "".join(f"{c:>16s}" for c in celulas))

    # ── 3. por paciente-dia ──────────────────────────────────────────────
    secao("3. POR PACIENTE E DIA (dthr_evolucao_dt)")
    com_dia = tr[tr["_dia"].notna()]
    grupos = com_dia.groupby(["prontuario_hash", "_dia"])
    tamanhos = Counter(len(g) for _, g in grupos)
    log(f"Paciente-dias: {len(grupos)}. Notas por paciente-dia: " +
        ", ".join(f"{k} nota(s): {v}" for k, v in sorted(tamanhos.items())))
    mesmo_anot = sum(1 for _, g in grupos if len(g) > 1 and g["_anot"].nunique() == 1)
    multi = sum(1 for _, g in grupos if len(g) > 1)
    log(f"Paciente-dias com 2+ notas em que todas têm o mesmo anotador: {mesmo_anot} de {multi}")
    log()
    log("Nos paciente-dias com 2+ notas, em quantas notas do dia o código aparece:")
    log(f"{'código':26s}{'nenhuma':>9s}{'só uma':>9s}{'algumas':>9s}{'todas':>9s}   tipo da nota marcada quando é só uma")
    for cod, nome in PROCESSOS:
        cont = Counter()
        tipo_unica = Counter()
        for _, g in grupos:
            if len(g) < 2:
                continue
            marc = g["_cod"].apply(lambda s: cod in s)
            k = int(marc.sum())
            if k == 0:
                cont["nenhuma"] += 1
            elif k == 1:
                cont["só uma"] += 1
                tipo_unica[g[marc]["_tipo"].iloc[0]] += 1
            elif k == len(g):
                cont["todas"] += 1
            else:
                cont["algumas"] += 1
        tipos_txt = ", ".join(f"{t} {q}" for t, q in tipo_unica.most_common(3)) or "-"
        log(f"{nome:26s}" + "".join(f"{cont[c]:9d}" for c in ("nenhuma", "só uma", "algumas", "todas"))
            + f"   {tipos_txt}")
    log()
    log("Paciente-dias com pelo menos uma nota marcada, por anotador do dia (só dias de um anotador):")
    log(f"{'código':26s}" + "".join(f"{'anot ' + a:>12s}" for a in anots))
    for cod, nome in PROCESSOS:
        celulas = []
        for a in anots:
            dias = [g for _, g in grupos if g["_anot"].nunique() == 1 and g["_anot"].iloc[0] == a]
            k = sum(1 for g in dias if g["_cod"].apply(lambda s: cod in s).any())
            celulas.append(f"{pct(k, len(dias)).strip()} ({len(dias)})")
        log(f"{nome:26s}" + "".join(f"{c:>12s}" for c in celulas))

    # ── 4. termos candidatos ─────────────────────────────────────────────
    secao("4. TERMOS CANDIDATOS: % DAS NOTAS COM O TERMO (marcadas x não marcadas)")
    for cod, nome in PROCESSOS:
        if cod not in TERMOS:
            continue
        t = tipo_dom[cod]
        log()
        log(f"{nome}  (todas as notas  |  só notas {t})")
        marc = tr["_cod"].apply(lambda s: cod in s)
        sub_t = tr["_tipo"] == t
        log(f"   {'termo':26s}{'marcadas':>10s}{'não marc.':>10s}   |{'marcadas':>10s}{'não marc.':>10s}")
        log(f"   {'(n)':26s}{int(marc.sum()):10d}{int((~marc).sum()):10d}   |"
            f"{int((marc & sub_t).sum()):10d}{int((~marc & sub_t).sum()):10d}")
        for rot, rx in TERMOS[cod]:
            tem = tr["_txt"].apply(lambda x: bool(re.search(rx, x)))
            log(f"   {rot:26s}{pct((tem & marc).sum(), marc.sum()):>10s}"
                f"{pct((tem & ~marc).sum(), (~marc).sum()):>10s}   |"
                f"{pct((tem & marc & sub_t).sum(), (marc & sub_t).sum()):>10s}"
                f"{pct((tem & ~marc & sub_t).sum(), (~marc & sub_t).sum()):>10s}")

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / "etapa9_processos.txt"
    log()
    log(f"Relatório gravado em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()
