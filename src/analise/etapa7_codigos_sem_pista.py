#!/usr/bin/env python3
"""
Etapa 7 - Os códigos cateterismo vesical, passagem de SNE e glicemia capilar estão
escritos no texto da evolução, ou dependem do hábito de cada anotador?

Uso (a partir da raiz do projeto, com o venv ativado):
    python src/analise/etapa7_codigos_sem_pista.py data/data-completo.xlsx

Não usa LLM. Usa a planilha inteira (420 evoluções), porque é uma análise
descritiva do gabarito, não escolha de regra.

Para cada código mede duas coisas:
  menção   o texto cita o dispositivo ou o exame (ex. "SVD", "SNE", "HGT")
  ato      o texto descreve o procedimento sendo feito (ex. "passada SVD",
           "repassada SNE", "realizado HGT")
Curativo grau II entra como comparação, porque é um código que está no texto.

Tabela 1  quantas evoluções marcadas com o código têm menção e ato no texto,
          comparado com as evoluções não marcadas.
Tabela 2  por anotador, quanto cada um marca o código, no total e só entre as
          evoluções que mencionam o dispositivo ou exame. Se o texto decidisse, a
          porcentagem seria parecida entre anotadores.

Saída: reports/analise-gabarito/etapa7_codigos_sem_pista.txt (só números agregados).
"""
import argparse
import importlib.util
import re
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "reports" / "analise-gabarito"

_spec = importlib.util.spec_from_file_location(
    "regras_texto", RAIZ / "src" / "agent" / "regras_texto.py")
regras_texto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regras_texto)

# (código só dígitos, nome, regex de menção, regex de ato), sobre o texto normalizado
CODIGOS = [
    ("0301100055", "CATETERISMO VESICAL DE DEMORA",
     r"\bsvd\b|\bsonda\s+vesical\b|\bcateter\s+vesical\b",
     r"\b(passad[ao]|passo|passagem\s+de|instalad[ao]|inserid[ao]|realizad[ao]|realizo|"
     r"troca\s+de|trocad[ao]|troco)\s+(a\s+|de\s+)?(nova\s+)?(svd|sonda\s+vesical|cateter\s+vesical)"
     r"|\bsvd\s+(passad|instalad|trocad)\w*|\b(sondagem|cateterismo)\s+vesical"),
    ("0309010101", "PASSAGEM DE SONDA NASOENTERICA",
     r"\bsne\b|\bsonda\s+naso\s*enterica\b",
     r"\b(passad[ao]|repassad[ao]|passo|repasso|passagem\s+de|reposicionad[ao]|"
     r"troca\s+de|trocad[ao])\s+(a\s+)?(nova\s+)?(sne|sonda\s+naso\s*enterica)"
     r"|\bsne\s+(passad|repassad|reposicionad)\w*"),
    ("0214010015", "GLICEMIA CAPILAR",
     r"\bhgt\b|\bglicemias?\s+capilar(es)?\b|\bdextro\b|\bglicemi\w*\s*:?\s*\d{2,3}\b",
     r"\b(realiz|afer|verific|colet)\w*\s+(a\s+|de\s+)?(hgt|glicemia\s+capilar|dextro)"
     r"|\bhgt\s*:?\s*\d{2,3}\b|\bglicemia\s+capilar\s*:?\s*\d{2,3}\b"),
    ("0401010015", "CURATIVO GRAU II (comparacao)",
     r"\bcurativos?\b",
     r"\brealiz\w*\s+(a\s+)?(troca\s+de\s+)?curativo"),
]

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


def pct(n, d):
    return f"{n / d:5.0%}" if d else "   - "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    args = ap.parse_args()

    df = carregar(Path(args.planilha))
    df.columns = [c.strip() for c in df.columns]
    df["_cod"] = df["codigos_sigtap"].apply(parse_codigos)
    df["_txt"] = df["evolucoes"].fillna("").apply(regras_texto.normalizar)
    anotadores = sorted(df["annotation_group"].dropna().unique(), key=str)

    secao("ETAPA 7 - CÓDIGOS SEM PISTA NO TEXTO (planilha inteira)")
    log(f"{len(df)} evoluções, {df['prontuario_hash'].nunique()} pacientes, {len(anotadores)} anotadores.")
    log("menção = cita o dispositivo ou exame.  ato = descreve o procedimento sendo feito.")

    for cod, nome, rx_mencao, rx_ato in CODIGOS:
        df[f"m_{cod}"] = df["_txt"].apply(lambda t: bool(re.search(rx_mencao, t)))
        df[f"a_{cod}"] = df["_txt"].apply(lambda t: bool(re.search(rx_ato, t)))
        df[f"o_{cod}"] = df["_cod"].apply(lambda s: cod in s)

    secao("1. O TEXTO DAS EVOLUÇÕES MARCADAS TEM O PROCEDIMENTO?")
    log(f"{'código':32s}{'marcadas':>9s} | {'com menção':>11s}{'com ato':>9s} | "
        f"{'não marc.':>10s}{'com menção':>11s}{'com ato':>9s}")
    for cod, nome, *_ in CODIGOS:
        sim = df[df[f"o_{cod}"]]
        nao = df[~df[f"o_{cod}"]]
        log(f"{nome[:31]:32s}{len(sim):9d} | {pct(sim[f'm_{cod}'].sum(), len(sim)):>11s}"
            f"{pct(sim[f'a_{cod}'].sum(), len(sim)):>9s} | {len(nao):10d}"
            f"{pct(nao[f'm_{cod}'].sum(), len(nao)):>11s}{pct(nao[f'a_{cod}'].sum(), len(nao)):>9s}")
    log()
    log("Leitura: num código que está no texto, 'com ato' é alto nas marcadas e baixo nas")
    log("não marcadas (ver curativo). Se 'com ato' é baixo nas marcadas, o anotador marcou")
    log("sem o procedimento estar descrito.")

    secao("2. QUANTO CADA ANOTADOR MARCA O CÓDIGO")
    log("Cada célula: % marcadas no total (n evoluções)  /  % marcadas entre as que têm menção (n)")
    for cod, nome, *_ in CODIGOS:
        log()
        log(nome)
        for g in anotadores:
            sub = df[df["annotation_group"] == g]
            com = sub[sub[f"m_{cod}"]]
            log(f"   anotador {str(g):4s} total {pct(sub[f'o_{cod}'].sum(), len(sub))} (n={len(sub):3d})"
                f"   com menção {pct(com[f'o_{cod}'].sum(), len(com))} (n={len(com):3d})"
                f"   marcadas {int(sub[f'o_{cod}'].sum()):3d}")
        total = int(df[f"o_{cod}"].sum())
        if total:
            maior = max(anotadores, key=lambda g: df[(df["annotation_group"] == g)][f"o_{cod}"].sum())
            n_maior = int(df[df["annotation_group"] == maior][f"o_{cod}"].sum())
            log(f"   -> anotador {maior} fez {n_maior} de {total} marcações ({n_maior / total:.0%})")

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / "etapa7_codigos_sem_pista.txt"
    log()
    log(f"Relatório gravado em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()
