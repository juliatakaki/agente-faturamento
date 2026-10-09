#!/usr/bin/env python3
"""
Etapa 4 (simulação) - E se os códigos candidatos exigissem IA E regex ao mesmo tempo?

Uso (a partir da raiz do projeto, com o venv ativado):
    python src/analise/etapa4_simular_exigente.py --rotulo gemma27

Não roda o pipeline e não usa LLM. Lê o que a etapa 4 já gravou em data/avaliacao/
(teste_entrada.json, teste_gabarito.json e resultados_<rotulo>.jsonl) e recalcula as
métricas dos 11 códigos de texto em três cenários:

  atual      o que o pipeline sugeriu na rodada.
  exigente   igual ao atual, mas os códigos CANDIDATOS de src/agent/regras_texto.py
             (gasometria, hemodiálise, traqueostomia, nutrição enteral) só ficam se a
             regra de regex também disparar no texto da evolução. Ou seja, a busca
             textual sozinha não basta mais para esses códigos.
  só regex   referência: o atual mais todos os candidatos em que o regex disparou,
             com ou sem a IA. Mostra o teto de recall das regras.

Os demais códigos de texto (curativo, fisioterapias, etc.) não mudam entre cenários.

O regex é recalculado agora, com a versão atual de regras_texto.py. Se as regras
mudaram depois da rodada, a simulação reflete as regras de hoje.

Saída: reports/analise-gabarito/etapa4_exigente_<rotulo>.txt (só números agregados).
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "data" / "avaliacao"
PASTA_REL = RAIZ / "reports" / "analise-gabarito"

_spec = importlib.util.spec_from_file_location(
    "regras_texto", RAIZ / "src" / "agent" / "regras_texto.py")
regras_texto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regras_texto)

# Os 11 códigos de TEXTO da aba "Estratégia" (linhas verdes), só dígitos
CODIGOS_TEXTO = {
    "0309010047": "NUTRIÇÃO ENTERAL EM ADULTO",
    "0401010015": "CURATIVO GRAU II",
    "0211080020": "GASOMETRIA",
    "0302040021": "FISIOTERAPIA RESPIRATÓRIA",
    "0302050027": "FISIOTERAPIA MOTORA",
    "0301100071": "CUIDADOS C/ TRAQUEOSTOMIA",
    "0305010131": "HEMODIÁLISE",
    "0301100055": "CATETERISMO VESICAL DE DEMORA",
    "0309010101": "PASSAGEM DE SONDA NASOENTÉRICA",
    "0211020036": "ELETROCARDIOGRAMA",
    "0214010015": "GLICEMIA CAPILAR",
}

# Candidatos = regras em modo "candidato" em regras_texto.py
CANDIDATOS = {
    regras_texto.so_digitos(c): r for c, r in regras_texto.REGRAS.items()
    if r["modo"] == regras_texto.MODO_CANDIDATO
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


def so_digitos(c) -> str:
    return re.sub(r"\D", "", str(c or ""))


def fmt(x):
    return "  -  " if x != x else f"{x:5.2f}"


def metricas(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if tp else 0.0
    return p, r, f


def ler_json(nome):
    arq = PASTA_DADOS / nome
    if not arq.exists():
        sys.exit(f"Não encontrei {arq}. Rode antes a etapa 4.")
    return json.loads(arq.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotulo", required=True)
    args = ap.parse_args()

    textos = {p["id"]: p["texto"] for p in ler_json("teste_entrada.json")}
    gabarito = ler_json("teste_gabarito.json")
    arq_res = PASTA_DADOS / f"resultados_{args.rotulo}.jsonl"
    if not arq_res.exists():
        sys.exit(f"Não encontrei {arq_res}.")
    resultados = {}
    for linha in arq_res.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            r = json.loads(linha)
            if "erro" not in r and r["id"] in gabarito:
                resultados[r["id"]] = r

    verdes = set(CODIGOS_TEXTO)
    ouro = {i: set(g["codigos"]) & verdes for i, g in gabarito.items()}

    # Quais candidatos o regex dispara em cada evolução (com as regras de hoje)
    dispara = {}
    for i in resultados:
        t = regras_texto.normalizar(textos.get(i, ""))
        dispara[i] = {
            cod for cod, regra in CANDIDATOS.items()
            if regras_texto.pontuar(t, regra["pistas"])[0] >= regra["limiar"]
        }

    def atual(i):
        return {so_digitos(c.get("codigo")) for c in resultados[i].get("codigos", [])} & verdes

    def exigente(i):
        return {c for c in atual(i) if c not in CANDIDATOS or c in dispara[i]}

    def so_regex(i):
        return atual(i) | (dispara[i] & verdes)

    cenarios = [("atual", atual), ("exigente", exigente), ("só regex", so_regex)]

    secao(f"SIMULAÇÃO - CANDIDATOS EXIGINDO IA E REGEX - rótulo '{args.rotulo}'")
    log(f"Evoluções avaliadas: {len(resultados)} de {len(gabarito)}. "
        f"Códigos de texto no gabarito: {sum(len(s) for s in ouro.values())}.")
    log("Candidatos considerados: " + ", ".join(
        f"{r['rotulo']}"
        for c, r in CANDIDATOS.items()))

    secao("1. CÓDIGOS DE TEXTO, MICRO-MÉDIA")
    log(f"{'cenário':12s}{'TP':>5s}{'FP':>5s}{'FN':>5s}   {'prec':>6s}{'rec':>6s}{'F1':>6s}")
    for nome, f in cenarios:
        tp = fp = fn = 0
        for i in resultados:
            p = f(i)
            tp += len(ouro[i] & p); fp += len(p - ouro[i]); fn += len(ouro[i] - p)
        pr, rc, f1 = metricas(tp, fp, fn)
        log(f"{nome:12s}{tp:5d}{fp:5d}{fn:5d}   {fmt(pr)} {fmt(rc)} {fmt(f1)}")

    secao("2. SÓ OS CÓDIGOS CANDIDATOS, POR CÓDIGO (precisão / recall)")
    log(f"{'código':28s}{'n':>4s}" + "".join(f"{nome:>16s}" for nome, _ in cenarios))
    for cod, regra in CANDIDATOS.items():
        n = sum(1 for s in ouro.values() if cod in s)
        celulas = []
        for _, f in cenarios:
            tp = fp = fn = 0
            for i in resultados:
                o, p = cod in ouro[i], cod in f(i)
                tp += o and p; fp += (not o) and p; fn += o and not p
            pr, rc, _ = metricas(tp, fp, fn)
            celulas.append(f"{fmt(pr).strip()} / {fmt(rc).strip()}")
        log(f"{regra['rotulo'][:27]:28s}{n:4d}" + "".join(f"{c:>16s}" for c in celulas))

    PASTA_REL.mkdir(parents=True, exist_ok=True)
    destino = PASTA_REL / f"etapa4_exigente_{args.rotulo}.txt"
    log()
    log(f"Relatório gravado em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()
