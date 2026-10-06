#!/usr/bin/env python3
"""
Etapa 4 - Avaliação do pipeline completo no grupo de teste.

Uso (a partir da raiz do projeto):
    python src/analise/etapa4_avaliar_pipeline.py data/data-completo.xlsx --rotulo spacy --limite 3
    python src/analise/etapa4_avaliar_pipeline.py data/data-completo.xlsx --rotulo spacy
    python src/analise/etapa4_avaliar_pipeline.py data/data-completo.xlsx --rotulo spacy --so-avaliar

  --rotulo      nome da configuração (ex.: spacy, ollama). Cada rótulo tem seu
                próprio arquivo de resultados e de relatório.
  --limite N    processa no máximo N evoluções novas nesta execução (teste rápido).
  --so-avaliar  não roda o pipeline; só recalcula as métricas do que já foi processado.

O que faz
1. Refaz a MESMA divisão por paciente da etapa 3 (semente 42, 30% no teste) e
   confere as contagens (45 pacientes, 142 evoluções). Se não bater, para.
2. Grava em data/avaliacao/ dois arquivos separados:
     teste_entrada.json   só id e texto (o único que o pipeline lê)
     teste_gabarito.json  códigos e anotador (só a comparação abre)
3. Roda o pipeline (src/agent/pipeline.py), uma evolução por vez, e grava cada
   resultado assim que termina em data/avaliacao/resultados_<rotulo>.jsonl.
   Se parar no meio, a próxima execução continua de onde parou. A configuração
   do .env usada fica registrada; se ela mudar, o script recusa misturar.
4. Compara com o gabarito e grava as métricas agregadas em
   reports/analise-gabarito/etapa4_<rotulo>.txt.

Com as regras ligadas, uma única execução mede o resultado COM e SEM regras:
"sem regras" = códigos que não vieram de regra + os resultados da busca que a
regra substituiu (campo substituidos_por_regra do relatório).

data/avaliacao/ tem texto real de evolução: precisa estar no .gitignore.
"""
import argparse
import asyncio
import importlib.util
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "data" / "avaliacao"
PASTA_REL = RAIZ / "reports" / "analise-gabarito"

SEMENTE = 42
FRACAO_TESTE = 0.30
ESPERADO_PACIENTES_TESTE = 45
ESPERADO_EVOLUCOES_TESTE = 142
MIN_SUPORTE = 20  # códigos com >= 20 evoluções na planilha inteira entram na tabela por código

VARS_CONFIG = (
    "EXTRATOR_ATIVO", "PROVEDOR_LLM", "MODELO_LOCAL", "PROVEDOR_API", "MODELO_API",
    "USAR_LLM_FALLBACK", "USAR_BUSCA_SEMANTICA", "USAR_REGRAS_DOCUMENTO",
    "USAR_REGRAS_TEXTO", "MAX_TOKENS_LLM", "ORQUESTRACAO_POR_LLM",
    "OLLAMA_NUM_CTX", "TIMEOUT_LLM_SEGUNDOS",
)

SAIDA = []


def log(txt=""):
    print(txt)
    SAIDA.append(str(txt))


def secao(titulo):
    log()
    log("=" * 90)
    log(titulo)
    log("=" * 90)


def so_digitos(c) -> str:
    return re.sub(r"\D", "", str(c or ""))


def formatar_codigo(c: str) -> str:
    return f"{c[0:2]}.{c[2:4]}.{c[4:6]}.{c[6:9]}-{c[9]}" if len(c) == 10 else c


def parse_codigos(valor) -> list[str]:
    if pd.isna(valor):
        return []
    return sorted({so_digitos(p) for p in str(valor).split(";") if so_digitos(p)})


# ── 1 e 2: divisão e arquivos de entrada/gabarito ──────────────────────────

def preparar(caminho_planilha: Path) -> tuple[list[dict], dict, dict]:
    df = pd.read_excel(caminho_planilha, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # Mesma divisão da etapa 3: pacientes ordenados, embaralhados com a
    # semente, os primeiros 30% vão para o teste.
    pacientes = sorted(df["prontuario_hash"].unique())
    random.Random(SEMENTE).shuffle(pacientes)
    n_teste = round(len(pacientes) * FRACAO_TESTE)
    teste_pac = set(pacientes[:n_teste])
    teste = df[df["prontuario_hash"].isin(teste_pac)]

    if len(teste_pac) != ESPERADO_PACIENTES_TESTE or len(teste) != ESPERADO_EVOLUCOES_TESTE:
        sys.exit(f"Divisão diferente da etapa 3: {len(teste_pac)} pacientes e {len(teste)} "
                 f"evoluções (esperado {ESPERADO_PACIENTES_TESTE} e {ESPERADO_EVOLUCOES_TESTE}). "
                 f"A planilha mudou? Avaliação interrompida.")

    entrada = [{"id": str(r.source_row_id), "texto": "" if pd.isna(r.evolucoes) else str(r.evolucoes)}
               for r in teste.itertuples()]
    gabarito = {str(r.source_row_id): {"codigos": parse_codigos(r.codigos_sigtap),
                                       "anotador": str(r.annotation_group)}
                for r in teste.itertuples()}

    # Códigos frequentes e descrições, calculados na planilha inteira
    cont = Counter(c for v in df["codigos_sigtap"] for c in parse_codigos(v))
    descricoes = {}
    for v in df["itens_faturaveis"].dropna():
        for linha in str(v).splitlines():
            m = re.match(r"\s*(\d{2}\.\d{2}\.\d{2}\.\d{3}-\d)\s*-\s*(.+)", linha)
            if m:
                descricoes.setdefault(so_digitos(m.group(1)), m.group(2).strip())
    info = {"frequentes": [c for c, q in cont.most_common() if q >= MIN_SUPORTE],
            "descricoes": descricoes}

    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    (PASTA_DADOS / "teste_entrada.json").write_text(
        json.dumps(entrada, ensure_ascii=False, indent=1), encoding="utf-8")
    (PASTA_DADOS / "teste_gabarito.json").write_text(
        json.dumps(gabarito, ensure_ascii=False, indent=1), encoding="utf-8")
    return entrada, gabarito, info


# ── 3: execução com retomada ───────────────────────────────────────────────

def carregar_pipeline():
    """Importa src/agent/pipeline.py pelo caminho. Ele lê o .env na importação."""
    spec = importlib.util.spec_from_file_location(
        "pipeline", RAIZ / "src" / "agent" / "pipeline.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def config_atual() -> dict:
    return {v: os.getenv(v, "") for v in VARS_CONFIG}


def resumir_relatorio(rel: dict) -> dict:
    """Só o que a avaliação precisa, para o arquivo de resultados não crescer à toa."""
    return {
        "codigos": [{"codigo": c.get("codigo", ""), "nivel": c.get("nivel", ""),
                     "origem": c.get("origem", ""), "confianca": c.get("confianca", "")}
                    for c in rel.get("codigos_sigtap", [])],
        "candidatos": [c.get("codigo", "") for c in rel.get("candidatos_regra", [])],
        "substituidos": rel.get("substituidos_por_regra", []),
        "falha": rel.get("falha_extracao", ""),
        "n_entidades": len(rel.get("entidades_extraidas", [])),
        "n_nao_realizados": len(rel.get("termos_nao_realizados", [])),
        "ambiguos": rel.get("termos_ambiguos", []),
    }


def ler_resultados(arquivo: Path) -> dict:
    feitos = {}
    if arquivo.exists():
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                r = json.loads(linha)
                feitos[r["id"]] = r
    return feitos


async def executar(entrada: list[dict], rotulo: str, limite: int | None) -> None:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")

    arq_res = PASTA_DADOS / f"resultados_{rotulo}.jsonl"
    arq_cfg = PASTA_DADOS / f"config_{rotulo}.json"
    cfg = config_atual()
    if arq_cfg.exists():
        anterior = json.loads(arq_cfg.read_text(encoding="utf-8"))
        if anterior != cfg:
            difs = [f"{k}: antes '{anterior.get(k, '')}', agora '{cfg.get(k, '')}'"
                    for k in sorted(set(anterior) | set(cfg)) if anterior.get(k) != cfg.get(k)]
            sys.exit("A configuração do .env mudou desde o início do rótulo "
                     f"'{rotulo}':\n  " + "\n  ".join(difs) +
                     "\nVolte a configuração ou use outro --rotulo. Nada foi processado.")
    else:
        arq_cfg.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

    feitos = ler_resultados(arq_res)
    pendentes = [p for p in entrada if p["id"] not in feitos]
    if limite is not None:
        pendentes = pendentes[:limite]
    print(f"[AVALIACAO] Rótulo '{rotulo}': {len(feitos)} já processadas, "
          f"{len(pendentes)} a processar nesta execução.")
    print(f"[AVALIACAO] Configuração: {cfg}")
    if not pendentes:
        return

    pipeline = carregar_pipeline()
    await pipeline.iniciar_sessao_mcp()
    duracoes = []
    try:
        for i, p in enumerate(pendentes, start=1):
            print(f"\n[AVALIACAO {i}/{len(pendentes)}] evolução {p['id']}")
            t0 = time.monotonic()
            try:
                rel = await pipeline.processar_prontuario(p)
                registro = {"id": p["id"], **resumir_relatorio(rel)}
            except RuntimeError as e:
                # Cota esgotada (429) e afins: parar sem gravar esta evolução,
                # para ela ser refeita na próxima execução.
                if "Cota" in str(e) or "rate limit" in str(e).lower():
                    print(f"[AVALIACAO] Interrompido por limite do provedor. Rode de novo "
                          f"depois para continuar de onde parou.\n  {str(e)[:200]}")
                    break
                registro = {"id": p["id"], "erro": f"{type(e).__name__}: {str(e)[:300]}"}
            except Exception as e:
                registro = {"id": p["id"], "erro": f"{type(e).__name__}: {str(e)[:300]}"}
            registro["segundos"] = round(time.monotonic() - t0, 1)
            duracoes.append(registro["segundos"])
            with open(arq_res, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            media = sum(duracoes) / len(duracoes)
            restante = media * (len(pendentes) - i) / 60
            print(f"[AVALIACAO] {registro['segundos']:.0f}s nesta evolução; média "
                  f"{media:.0f}s; estimativa para terminar as desta execução: {restante:.0f} min")
    finally:
        await pipeline.fechar_sessao_mcp()


# ── 4: comparação com o gabarito ───────────────────────────────────────────

def metricas(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if tp else 0.0
    return p, r, f


def fmt(x):
    return "  -  " if x != x else f"{x:5.2f}"


def categoria_origem(nivel: str) -> str:
    if nivel == "regra_documento":
        return "regra de documento"
    if nivel in ("regra_texto", "regra_texto_confirmada"):
        return "regra de texto" if nivel == "regra_texto" else "regra de texto confirmada"
    return "busca textual"


def avaliar(rotulo: str, gabarito: dict, info: dict) -> None:
    arq_res = PASTA_DADOS / f"resultados_{rotulo}.jsonl"
    arq_cfg = PASTA_DADOS / f"config_{rotulo}.json"
    feitos = ler_resultados(arq_res)
    validos = {i: r for i, r in feitos.items() if "erro" not in r and i in gabarito}
    erros = [r for r in feitos.values() if "erro" in r]

    secao(f"ETAPA 4 - AVALIAÇÃO DO PIPELINE NO TESTE - rótulo '{rotulo}'")
    if arq_cfg.exists():
        log("Configuração usada:")
        for k, v in json.loads(arq_cfg.read_text(encoding="utf-8")).items():
            log(f"  {k:24s} {v}")
    log()
    log(f"Evoluções no teste: {len(gabarito)}")
    log(f"Processadas sem erro: {len(validos)}   com erro de execução: {len(erros)}   "
        f"faltando: {len(gabarito) - len(feitos)}")
    tempos = [r["segundos"] for r in validos.values() if "segundos" in r]
    if tempos:
        log(f"Tempo por evolução: média {sum(tempos) / len(tempos):.0f}s, "
            f"máximo {max(tempos):.0f}s, total {sum(tempos) / 60:.0f} min")
    falhas = sum(1 for r in validos.values() if r.get("falha"))
    log(f"Com falha de extração (contam como avaliadas, com o que as regras deram): {falhas}")
    if erros:
        for k, q in Counter(r["erro"].split(":")[0] for r in erros).most_common():
            log(f"  erro {k}: {q}")
    if not validos:
        log("\nNada para avaliar ainda.")
        return
    if len(validos) < len(gabarito):
        log("\nATENÇÃO: avaliação parcial. Os números abaixo valem só para as evoluções já processadas.")

    def pred_com(r):
        return {so_digitos(c["codigo"]) for c in r["codigos"] if c.get("codigo")}

    def pred_sem(r):
        base = {so_digitos(c["codigo"]) for c in r["codigos"]
                if c.get("codigo") and not str(c.get("nivel", "")).startswith("regra_")}
        return base | {so_digitos(s.get("codigo")) for s in r.get("substituidos", []) if s.get("codigo")}

    secao("1. RESULTADO GERAL (micro-média sobre todos os códigos)")
    log(f"{'cenário':28s}{'TP':>6s}{'FP':>6s}{'FN':>6s}   {'prec':>6s}{'rec':>6s}{'F1':>6s}")
    for nome, fpred in [("sem regras", pred_sem), ("com regras", pred_com)]:
        tp = fp = fn = 0
        for i, r in validos.items():
            ouro, pred = set(gabarito[i]["codigos"]), fpred(r)
            tp += len(ouro & pred); fp += len(pred - ouro); fn += len(ouro - pred)
        p, rr, f = metricas(tp, fp, fn)
        log(f"{nome:28s}{tp:6d}{fp:6d}{fn:6d}   {fmt(p)} {fmt(rr)} {fmt(f)}")

    secao("2. DE ONDE VÊM OS ACERTOS E OS ERROS (com regras)")
    por_origem = defaultdict(lambda: [0, 0])
    for i, r in validos.items():
        ouro = set(gabarito[i]["codigos"])
        vistos = set()
        for c in r["codigos"]:
            cod = so_digitos(c.get("codigo"))
            if not cod or cod in vistos:
                continue
            vistos.add(cod)
            por_origem[categoria_origem(c.get("nivel", ""))][0 if cod in ouro else 1] += 1
    log(f"{'origem do código':28s}{'certos':>8s}{'errados':>9s}   {'precisão':>9s}")
    for origem, (certos, errados) in sorted(por_origem.items(), key=lambda x: -sum(x[1])):
        log(f"{origem:28s}{certos:8d}{errados:9d}   {fmt(certos / (certos + errados)):>9s}")

    cand_certos = cand_errados = 0
    for i, r in validos.items():
        ouro = set(gabarito[i]["codigos"])
        for c in r.get("candidatos", []):
            if so_digitos(c) in ouro:
                cand_certos += 1
            else:
                cand_errados += 1
    log()
    log(f"Candidatos de regra sem confirmação (fora do valor): {cand_certos + cand_errados} "
        f"no total, {cand_certos} estavam no gabarito e {cand_errados} não.")

    secao(f"3. POR CÓDIGO (códigos com >= {MIN_SUPORTE} evoluções na planilha)")
    log(f"{'código':16s}{'nome':34s}{'n':>4s} | {'prec':>6s}{'rec':>6s} sem regras | "
        f"{'prec':>6s}{'rec':>6s} com regras")
    for cod in info["frequentes"]:
        linha = []
        n = sum(1 for i in validos if cod in gabarito[i]["codigos"])
        for fpred in (pred_sem, pred_com):
            tp = fp = fn = 0
            for i, r in validos.items():
                o, p = cod in gabarito[i]["codigos"], cod in fpred(r)
                tp += o and p; fp += (not o) and p; fn += o and not p
            pr, rc, _ = metricas(tp, fp, fn)
            linha.append(f"{fmt(pr)} {fmt(rc)}")
        log(f"{formatar_codigo(cod):16s}{info['descricoes'].get(cod, '?')[:33]:34s}{n:4d} | "
            f"{linha[0]}            | {linha[1]}")

    secao("4. POR ANOTADOR (com regras)")
    grupos = sorted({g["anotador"] for g in gabarito.values()})
    log(f"{'anotador':10s}{'evoluções':>10s}{'TP':>6s}{'FP':>6s}{'FN':>6s}   {'prec':>6s}{'rec':>6s}{'F1':>6s}")
    for g in grupos:
        ids = [i for i in validos if gabarito[i]["anotador"] == g]
        tp = fp = fn = 0
        for i in ids:
            ouro, pred = set(gabarito[i]["codigos"]), pred_com(validos[i])
            tp += len(ouro & pred); fp += len(pred - ouro); fn += len(ouro - pred)
        p, rr, f = metricas(tp, fp, fn)
        log(f"{g:10s}{len(ids):10d}{tp:6d}{fp:6d}{fn:6d}   {fmt(p)} {fmt(rr)} {fmt(f)}")

    PASTA_REL.mkdir(parents=True, exist_ok=True)
    destino = PASTA_REL / f"etapa4_{rotulo}.txt"
    log()
    log(f"Relatório gravado em {destino}")
    destino.write_text("\n".join(SAIDA), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    ap.add_argument("--rotulo", required=True,
                    help="nome da configuração, ex.: spacy, ollama (só letras, números, - e _)")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--so-avaliar", action="store_true")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.rotulo):
        sys.exit("--rotulo só pode ter letras, números, '-' e '_'.")

    entrada, gabarito, info = preparar(Path(args.planilha))
    if not args.so_avaliar:
        asyncio.run(executar(entrada, args.rotulo, args.limite))
    avaliar(args.rotulo, gabarito, info)


if __name__ == "__main__":
    main()