#!/usr/bin/env python3
"""
Etapa 5 - Os pesos das regras de texto importam? Manuais x iguais x aprendidos.

Uso (a partir da raiz do projeto):
    python src/analise/etapa5_pesos_regras.py data/data-completo.xlsx

Usa as MESMAS pistas de src/agent/regras_texto.py e a MESMA divisão por paciente
da etapa 3 (semente 42, 30% dos pacientes no teste). Para cada código compara
três formas de pontuar:

  manual     os pesos escritos à mão em regras_texto.py (3, 2, 1, negativos)
  iguais     toda pista positiva vale 1 e toda pista negativa vale -1
  aprendido  regressão logística treinada só nos pacientes de treino; cada pista
             é uma variável (1 se aparece no texto, 0 se não) e o modelo calcula
             o peso de cada uma

Nas três, o ponto de corte (limiar do score ou da probabilidade) é escolhido só
no treino, pelo maior F1, e a medição é feita só no teste.

Saída: reports/analise-gabarito/etapa5_pesos.txt (só números agregados).
"""
import argparse
import importlib.util
import math
import random
import re
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "reports" / "analise-gabarito"
SEMENTE = 42
FRACAO_TESTE = 0.30

_spec = importlib.util.spec_from_file_location(
    "regras_texto", RAIZ / "src" / "agent" / "regras_texto.py")
regras_texto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regras_texto)

SAIDA = []


def log(txt=""):
    print(txt)
    SAIDA.append(str(txt))


def secao(titulo):
    log()
    log("=" * 96)
    log(titulo)
    log("=" * 96)


def parse_codigos(valor) -> set:
    if pd.isna(valor):
        return set()
    return {re.sub(r"\D", "", p) for p in str(valor).split(";") if re.sub(r"\D", "", p)}


def metricas(ouro, pred):
    tp = sum(1 for o, p in zip(ouro, pred) if o and p)
    fp = sum(1 for o, p in zip(ouro, pred) if not o and p)
    fn = sum(1 for o, p in zip(ouro, pred) if o and not p)
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if tp else 0.0
    return tp, fp, fn, prec, rec, f1


def fmt(x):
    return "  -  " if isinstance(x, float) and math.isnan(x) else f"{x:5.2f}"


def melhor_corte(scores, ouro):
    """Corte que maximiza o F1 no treino; empate fica com o corte mais alto."""
    candidatos = sorted(set(scores)) + [max(scores) + 1]
    return max(candidatos, key=lambda c: (metricas(ouro, [s >= c for s in scores])[5], c))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    args = ap.parse_args()

    df = pd.read_excel(args.planilha, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df["_cod"] = df["codigos_sigtap"].apply(parse_codigos)
    df["_txt"] = df["evolucoes"].fillna("").apply(regras_texto.normalizar)

    pacientes = sorted(df["prontuario_hash"].unique())
    random.Random(SEMENTE).shuffle(pacientes)
    teste_pac = set(pacientes[:round(len(pacientes) * FRACAO_TESTE)])
    df["split"] = df["prontuario_hash"].apply(lambda h: "teste" if h in teste_pac else "treino")
    tr, te = df[df["split"] == "treino"], df[df["split"] == "teste"]

    secao("ETAPA 5 - PESOS DAS REGRAS DE TEXTO: MANUAIS x IGUAIS x APRENDIDOS")
    log(f"Treino: {tr['prontuario_hash'].nunique()} pacientes, {len(tr)} evoluções. "
        f"Teste: {te['prontuario_hash'].nunique()} pacientes, {len(te)} evoluções.")
    log("Corte escolhido só no treino (maior F1). Métricas abaixo são do TESTE.")

    totais = {m: [0, 0, 0] for m in ("manual", "iguais", "aprendido")}
    linhas_pesos = []

    secao("1. RESULTADO NO TESTE POR CÓDIGO")
    log(f"{'código':16s}{'nome':27s}{'n':>4s} | {'manual':^17s} | {'iguais':^17s} | {'aprendido':^17s}")
    log(f"{'':16s}{'':27s}{'':>4s} | {'prec  rec   F1':^17s} | {'prec  rec   F1':^17s} | {'prec  rec   F1':^17s}")

    for codigo, regra in regras_texto.REGRAS.items():
        dig = regras_texto.so_digitos(codigo)
        pistas = regra["pistas"]
        nomes = [p[0] for p in pistas]

        def matriz(sub):
            return [[1 if re.search(rx, t) else 0 for _, rx, _ in pistas] for t in sub["_txt"]]

        X_tr, X_te = matriz(tr), matriz(te)
        y_tr = [dig in s for s in tr["_cod"]]
        y_te = [dig in s for s in te["_cod"]]

        pesos = {
            "manual": [p[2] for p in pistas],
            "iguais": [1 if p[2] > 0 else -1 for p in pistas],
        }
        res = {}
        for nome_m, w in pesos.items():
            s_tr = [sum(a * b for a, b in zip(x, w)) for x in X_tr]
            s_te = [sum(a * b for a, b in zip(x, w)) for x in X_te]
            corte = melhor_corte(s_tr, y_tr)
            res[nome_m] = metricas(y_te, [s >= corte for s in s_te])

        modelo = LogisticRegression(max_iter=1000, C=1.0)
        modelo.fit(X_tr, y_tr)
        p_tr = [round(p, 6) for p in modelo.predict_proba(X_tr)[:, 1]]
        p_te = [round(p, 6) for p in modelo.predict_proba(X_te)[:, 1]]
        corte = melhor_corte(p_tr, y_tr)
        res["aprendido"] = metricas(y_te, [p >= corte for p in p_te])

        for m in totais:
            for i in range(3):
                totais[m][i] += res[m][i]

        celulas = " | ".join(f"{fmt(res[m][3])} {fmt(res[m][4])} {fmt(res[m][5])}"
                             for m in ("manual", "iguais", "aprendido"))
        log(f"{codigo:16s}{regra['rotulo'][:26]:27s}{sum(y_te):4d} | {celulas}")

        linhas_pesos.append((codigo, regra["rotulo"],
                             list(zip(nomes, pesos["manual"], modelo.coef_[0]))))

    secao("2. MICRO-MÉDIA NO TESTE (6 códigos)")
    log(f"{'pesos':12s}{'TP':>5s}{'FP':>5s}{'FN':>5s}   {'prec':>6s}{'rec':>6s}{'F1':>6s}")
    for m, (tp, fp, fn) in totais.items():
        p = tp / (tp + fp) if tp + fp else float("nan")
        r = tp / (tp + fn) if tp + fn else float("nan")
        f = 2 * p * r / (p + r) if tp else 0.0
        log(f"{m:12s}{tp:5d}{fp:5d}{fn:5d}   {fmt(p)} {fmt(r)} {fmt(f)}")

    secao("3. PESOS: MANUAL x APRENDIDO PELA REGRESSÃO (coeficientes, escala própria)")
    log("O coeficiente aprendido não está na mesma escala do peso manual; compare o sinal")
    log("e a ordem entre as pistas do mesmo código. Coeficiente perto de zero = pista que")
    log("não ajuda a prever o código no treino.")
    for codigo, rotulo, itens in linhas_pesos:
        log()
        log(f"{codigo} {rotulo}")
        for nome, w_man, w_apr in itens:
            log(f"   {nome:32s} manual {w_man:3d}   aprendido {w_apr:6.2f}")

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / "etapa5_pesos.txt"
    log()
    log(f"Relatório gravado em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()
