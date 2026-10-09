#!/usr/bin/env python3
"""
Etapa 6 - Em que contexto aparecem os termos dos códigos candidatos quando a regra
ACERTA e quando ela ERRA?

Uso (a partir da raiz do projeto, com o venv ativado):
    python src/analise/etapa6_contexto_erros.py data/data-completo.xlsx

Não usa LLM. Usa só o grupo de TREINO (mesma divisão por paciente da etapa 3,
semente 42), para as pistas novas saírem do treino e serem avaliadas depois no teste.

Para cada código candidato de src/agent/regras_texto.py:
  acerto  = evolução em que a regra dispara e o código está no gabarito
  erro    = evolução em que a regra dispara e o código NÃO está no gabarito
Em cada evolução, acha as ocorrências do termo principal (ex. "gasometria", "sne")
e olha uma janela de texto em volta delas. Depois compara acerto x erro em:
  1. famílias de contexto definidas aqui (histórico, plano/pedido, ato do dia,
     data, valor numérico de exame)
  2. palavras e pares de palavras da janela que mais separam acerto de erro
     (só termos que aparecem em pelo menos 5 evoluções de 5 pacientes)

Saída: reports/analise-gabarito/etapa6_contexto_erros.txt (só números agregados
e termos curtos, nenhum trecho de evolução).
"""
import argparse
import importlib.util
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "reports" / "analise-gabarito"

_spec = importlib.util.spec_from_file_location(
    "regras_texto", RAIZ / "src" / "agent" / "regras_texto.py")
regras_texto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regras_texto)

SEMENTE = 42
FRACAO_TESTE = 0.30
JANELA = 80          # caracteres antes e depois do termo
MIN_EVOL = 5
MIN_PAC = 5

# Termo principal de cada código candidato, para ancorar a janela de contexto.
# Escrito sobre o texto em minúsculas e sem acento, com pontuação mantida.
ANCORAS = {
    "0211080020": r"\b(gasometria|gaso|gasa|ph|pao2|po2|paco2|pco2|hco3|bic)\b",
    "0305010131": r"\b(hemodialise|dialise|hd|cdl|trs|nefro\w*)\b",
    "0301100071": r"\b(tqt|traqueostomi\w*)\b",
    "0309010047": r"\b(sne|gtt|enteral|dieta)\b",
}

FAMILIAS = [
    ("histórico", r"\b(em uso|uso de|mant(em|ido|ida|enho|ida)|segue|seguindo|permanece|"
                  r"previ[ao]s?|anterior|ontem|admiss\w*|desde|cronic\w*|ja )"),
    ("plano/pedido", r"\b(program\w*|solicit\w*|aguard\w*|avaliar|se necessario|discutir|"
                     r"prescrev\w*|suspen\w*|retirad\w*|sem indicacao|nao realiz\w*)"),
    ("ato do dia", r"\b(realiz\w*|colhid\w*|coletad\w*|hoje|passad\w*|instalad\w*|"
                   r"iniciad\w*|feit[oa]s?|procedid\w*|trocad\w*|troca de)"),
    ("data dd/mm", r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b"),
    ("valor decimal", r"\b\d+[.,]\d+\b"),
]

STOP = set("""a o as os e de da do das dos em no na nos nas com sem para por pelo pela um uma
ao aos que se ou mas como mais menos ja nao sim foi ser esta estao seu sua ele ela lhe isso
este esse essa entre ate apos sob sobre h x""".split())

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
    log("=" * 90)
    log(titulo)
    log("=" * 90)


def carregar(caminho: Path) -> pd.DataFrame:
    ext = caminho.suffix.lower()
    if ext in (".xlsx", ".xls"):
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
    """Minúsculas, sem acento, sem tags [ANONIMIZACAO]. Mantém pontuação e '/'."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"\[[^\]]*\]", " ", t)
    return re.sub(r"\s+", " ", t)


def janelas(texto_leve: str, ancora: str) -> str:
    """Junta as janelas em volta de todas as ocorrências do termo principal."""
    partes = []
    for m in re.finditer(ancora, texto_leve):
        ini, fim = max(0, m.start() - JANELA), m.end() + JANELA
        partes.append(texto_leve[ini:m.start()] + " # " + texto_leve[m.end():fim])
    return " | ".join(partes)


def termos(jan: str) -> set:
    s = set()
    for trecho in re.split(r"[|#]", jan):
        tok = [w for w in re.findall(r"[a-z][a-z0-9]+", trecho)]
        for n in (1, 2):
            for i in range(len(tok) - n + 1):
                g = tok[i:i + n]
                if g[0] in STOP or g[-1] in STOP:
                    continue
                s.add(" ".join(g))
    return s


def pct(n, d):
    return f"{n / d:4.0%}" if d else "  - "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    args = ap.parse_args()

    df = carregar(Path(args.planilha))
    df.columns = [c.strip() for c in df.columns]
    df["_cod"] = df["codigos_sigtap"].apply(parse_codigos)
    df["_norm"] = df["evolucoes"].fillna("").apply(regras_texto.normalizar)
    df["_leve"] = df["evolucoes"].fillna("").apply(leve)

    pacientes = sorted(df["prontuario_hash"].unique())
    random.Random(SEMENTE).shuffle(pacientes)
    teste_pac = set(pacientes[:round(len(pacientes) * FRACAO_TESTE)])
    treino = df[~df["prontuario_hash"].isin(teste_pac)]

    secao("CONTEXTO DOS ACERTOS E ERROS DAS REGRAS CANDIDATAS (só TREINO)")
    log(f"Treino: {treino['prontuario_hash'].nunique()} pacientes, {len(treino)} evoluções. "
        f"Janela de {JANELA} caracteres antes e depois do termo principal.")
    log("Acerto = regra dispara e o código está no gabarito. Erro = regra dispara e não está.")

    for cod, regra in CANDIDATOS.items():
        if cod not in ANCORAS:
            log(f"\n{regra['rotulo']}: sem termo principal definido em ANCORAS, pulei.")
            continue
        dispara = treino["_norm"].apply(
            lambda t: regras_texto.pontuar(t, regra["pistas"])[0] >= regra["limiar"])
        ouro = treino["_cod"].apply(lambda s: cod in s)
        grupos = {"acerto": treino[dispara & ouro], "erro": treino[dispara & ~ouro]}
        jan = {g: [janelas(t, ANCORAS[cod]) for t in sub["_leve"]] for g, sub in grupos.items()}
        na, ne = len(grupos["acerto"]), len(grupos["erro"])

        secao(f"{regra['rotulo']}  (acertos {na}, erros {ne}, limiar {regra['limiar']})")
        sem = {g: sum(1 for j in jan[g] if not j) for g in jan}
        if sem["acerto"] or sem["erro"]:
            log(f"Evoluções sem o termo principal (regra disparou por outras pistas): "
                f"acerto {sem['acerto']}, erro {sem['erro']}")

        log()
        log("1. Famílias de contexto perto do termo (% das evoluções)")
        log(f"   {'família':16s}{'acerto':>8s}{'erro':>8s}")
        for nome, rx in FAMILIAS:
            a = sum(1 for j in jan["acerto"] if re.search(rx, j))
            e = sum(1 for j in jan["erro"] if re.search(rx, j))
            log(f"   {nome:16s}{pct(a, na):>8s}{pct(e, ne):>8s}")

        # termos da janela que mais separam acerto de erro
        cont = {g: Counter() for g in jan}
        pac = defaultdict(set)
        for g, sub in grupos.items():
            for h, j in zip(sub["prontuario_hash"], jan[g]):
                for t in termos(j):
                    cont[g][t] += 1
                    pac[t].add(h)
        linhas = []
        for t in set(cont["acerto"]) | set(cont["erro"]):
            a, e = cont["acerto"][t], cont["erro"][t]
            if a + e < MIN_EVOL or len(pac[t]) < MIN_PAC or re.search(ANCORAS[cod], t):
                continue
            pa, pe = (a / na if na else 0), (e / ne if ne else 0)
            linhas.append((pe - pa, t, pa, pe))
        linhas.sort()
        log()
        log("2. Termos perto do termo principal que indicam ERRO (mais comuns no erro)")
        top = [x for x in reversed(linhas) if x[0] > 0][:10]
        for _, t, pa, pe in top:
            log(f"   {t:28s} acerto {pa:4.0%}   erro {pe:4.0%}")
        if not top:
            log("   nenhum termo passa no critério")
        log("3. Termos perto do termo principal que indicam ACERTO (mais comuns no acerto)")
        top = [x for x in linhas if x[0] < 0][:10]
        for _, t, pa, pe in top:
            log(f"   {t:28s} acerto {pa:4.0%}   erro {pe:4.0%}")
        if not top:
            log("   nenhum termo passa no critério")

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / "etapa6_contexto_erros.txt"
    log()
    log(f"Relatório gravado em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


if __name__ == "__main__":
    main()
