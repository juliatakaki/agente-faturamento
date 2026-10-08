#!/usr/bin/env python3
"""
Etapa 4 (recorte) - Avaliação só dos códigos de TEXTO (os verdes da aba "Estratégia").

Uso (a partir da raiz do projeto):
    python src/analise/etapa4_texto.py --rotulo spacy
    python src/analise/etapa4_texto.py --rotulo spacy openai      (compara rótulos lado a lado)

Não roda o pipeline e não usa LLM. Lê o que a etapa 4 já gravou:
    data/avaliacao/teste_gabarito.json
    data/avaliacao/resultados_<rotulo>.jsonl

Os códigos de PROCESSO (diária, consultas, coleta, oxigenoterapia) ficam de fora,
porque não têm evidência no texto e dependem de regra de faturamento. Aqui, tanto o
gabarito quanto as sugestões do sistema são filtrados para os 11 códigos de texto:
um código de processo sugerido pelo sistema não conta como erro nem como acerto.

"Sem regras" = só o que veio da busca textual (sem regra de documento nem de texto),
mais os resultados da busca que a regra de curativo substituiu.

Saída: reports/analise-gabarito/etapa4_texto_<rotulos>.txt (só números agregados).
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "data" / "avaliacao"
PASTA_REL = RAIZ / "reports" / "analise-gabarito"

# Os 11 códigos de TEXTO da aba "Estratégia" (linhas verdes)
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


def formatar_codigo(c: str) -> str:
    return f"{c[0:2]}.{c[2:4]}.{c[4:6]}.{c[6:9]}-{c[9]}" if len(c) == 10 else c


def fmt(x):
    return "  -  " if x != x else f"{x:5.2f}"


def metricas(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if tp else 0.0
    return p, r, f


def carregar(rotulo: str) -> dict:
    arq = PASTA_DADOS / f"resultados_{rotulo}.jsonl"
    if not arq.exists():
        sys.exit(f"Não encontrei {arq}. Rode antes a etapa 4 com --rotulo {rotulo}.")
    feitos = {}
    for linha in arq.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            r = json.loads(linha)
            feitos[r["id"]] = r
    return feitos


def pred_com(r) -> set:
    return {so_digitos(c.get("codigo")) for c in r.get("codigos", [])} & set(CODIGOS_TEXTO)


def pred_sem(r) -> set:
    base = {so_digitos(c.get("codigo")) for c in r.get("codigos", [])
            if not str(c.get("nivel", "")).startswith("regra_")}
    base |= {so_digitos(s.get("codigo")) for s in r.get("substituidos", [])}
    return base & set(CODIGOS_TEXTO)


def origem(nivel: str) -> str:
    if nivel in ("regra_texto", "regra_texto_confirmada"):
        return "regra de texto"
    if nivel == "regra_documento":
        return "regra de documento"
    return "busca textual"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotulo", nargs="+", required=True)
    args = ap.parse_args()

    arq_gab = PASTA_DADOS / "teste_gabarito.json"
    if not arq_gab.exists():
        sys.exit(f"Não encontrei {arq_gab}. Rode antes a etapa 4.")
    gabarito = json.loads(arq_gab.read_text(encoding="utf-8"))
    ouro = {i: set(g["codigos"]) & set(CODIGOS_TEXTO) for i, g in gabarito.items()}

    resultados = {}
    for rot in args.rotulo:
        feitos = carregar(rot)
        resultados[rot] = {i: r for i, r in feitos.items() if "erro" not in r and i in gabarito}

    secao("ETAPA 4 - SÓ CÓDIGOS DE TEXTO (os 11 verdes da aba Estratégia)")
    log(f"Códigos de texto no gabarito do teste: {sum(len(s) for s in ouro.values())}, "
        f"em {sum(1 for s in ouro.values() if s)} das {len(ouro)} evoluções.")
    for rot, res in resultados.items():
        aviso = "" if len(res) == len(gabarito) else "   (PARCIAL)"
        log(f"Rótulo '{rot}': {len(res)} de {len(gabarito)} evoluções avaliadas{aviso}")

    secao("1. RESULTADO GERAL NOS CÓDIGOS DE TEXTO (micro-média)")
    log(f"{'rótulo':12s}{'cenário':14s}{'TP':>5s}{'FP':>5s}{'FN':>5s}   {'prec':>6s}{'rec':>6s}{'F1':>6s}")
    for rot, res in resultados.items():
        for nome, fpred in (("sem regras", pred_sem), ("com regras", pred_com)):
            tp = fp = fn = 0
            for i, r in res.items():
                o, p = ouro[i], fpred(r)
                tp += len(o & p); fp += len(p - o); fn += len(o - p)
            pr, rc, f1 = metricas(tp, fp, fn)
            log(f"{rot:12s}{nome:14s}{tp:5d}{fp:5d}{fn:5d}   {fmt(pr)} {fmt(rc)} {fmt(f1)}")

    secao("2. POR CÓDIGO, COM REGRAS (precisão / recall)")
    cab = "".join(f"{rot:>18s}" for rot in resultados)
    log(f"{'código':16s}{'nome':32s}{'n':>4s}{cab}")
    for cod, nome in CODIGOS_TEXTO.items():
        n = sum(1 for s in ouro.values() if cod in s)
        celulas = []
        for rot, res in resultados.items():
            tp = fp = fn = 0
            for i, r in res.items():
                o, p = cod in ouro[i], cod in pred_com(r)
                tp += o and p; fp += (not o) and p; fn += o and not p
            pr, rc, _ = metricas(tp, fp, fn)
            celulas.append(f"{fmt(pr).strip()} / {fmt(rc).strip()}")
        log(f"{formatar_codigo(cod):16s}{nome[:31]:32s}{n:4d}" + "".join(f"{c:>18s}" for c in celulas))

    secao("3. DE ONDE VÊM OS ACERTOS E ERROS NOS CÓDIGOS DE TEXTO (com regras)")
    for rot, res in resultados.items():
        contagem = defaultdict(lambda: [0, 0])
        for i, r in res.items():
            vistos = set()
            for c in r.get("codigos", []):
                cod = so_digitos(c.get("codigo"))
                if cod not in CODIGOS_TEXTO or cod in vistos:
                    continue
                vistos.add(cod)
                contagem[origem(c.get("nivel", ""))][0 if cod in ouro[i] else 1] += 1
        cand_certos = sum(1 for i, r in res.items() for c in r.get("candidatos", [])
                          if so_digitos(c) in ouro[i])
        cand_total = sum(len(r.get("candidatos", [])) for r in res.values())
        log(f"Rótulo '{rot}'")
        log(f"   {'origem':26s}{'certos':>8s}{'errados':>9s}   {'precisão':>9s}")
        for orig, (c, e) in sorted(contagem.items(), key=lambda x: -sum(x[1])):
            log(f"   {orig:26s}{c:8d}{e:9d}   {fmt(c / (c + e)):>9s}")
        log(f"   Candidatos sem confirmação (fora do valor): {cand_total}, "
            f"dos quais {cand_certos} estavam no gabarito.")
        log()

    PASTA_REL.mkdir(parents=True, exist_ok=True)
    destino = PASTA_REL / f"etapa4_texto_{'_'.join(args.rotulo)}.txt"
    log(f"Relatório gravado em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()
