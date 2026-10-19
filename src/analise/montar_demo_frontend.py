#!/usr/bin/env python3
"""
Monta, a partir de uma rodada da etapa 4 já gravada, o arquivo que a tela de
conferência (frontend/) abre. Não roda o pipeline, não usa LLM nem o banco do
SIGTAP: junta o texto da evolução (teste_entrada.json), o que o pipeline sugeriu
(resultados_<rotulo>.jsonl) e o que o anotador marcou (teste_gabarito.json).

Uso (a partir da raiz do projeto, com o venv ativado):
    python src/analise/montar_demo_frontend.py data/data-completo.xlsx --rotulo gemma27_v3
    python src/analise/montar_demo_frontend.py data/data-completo.xlsx --rotulo gemma27_v3 --ids 7405,22494
    python src/analise/montar_demo_frontend.py data/data-completo.xlsx --rotulo gemma27_v3 --n 8

Sem --ids, sorteia --n evoluções do grupo de teste (semente fixa, para não
escolher a dedo as que deram certo).

Saída: data/avaliacao/demo_frontend_<rotulo>.json. Tem texto real de evolução:
fica em data/avaliacao/ (fora do git) e não deve ir para a pasta frontend/.

Limitações em relação ao JSON gerado pelo pipeline: o arquivo de resultados da
etapa 4 não guarda valores (R$), alternativas da busca nem o motivo de cada
candidato. A descrição dos códigos vem da coluna itens_faturaveis da planilha;
códigos que nunca aparecem lá ficam sem descrição.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "data" / "avaliacao"


def so_digitos(c) -> str:
    return re.sub(r"\D", "", str(c or ""))


def formatar(c: str) -> str:
    d = so_digitos(c)
    return f"{d[0:2]}.{d[2:4]}.{d[4:6]}.{d[6:9]}-{d[9]}" if len(d) == 10 else str(c)


def descricoes_da_planilha(caminho: Path) -> dict:
    df = pd.read_excel(caminho, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    saida = {}
    for v in df.get("itens_faturaveis", pd.Series(dtype=str)).dropna():
        for linha in str(v).splitlines():
            m = re.match(r"\s*(\d{2}\.\d{2}\.\d{2}\.\d{3}-\d)\s*-\s*(.+)", linha)
            if m:
                saida.setdefault(so_digitos(m.group(1)), m.group(2).strip())
    return saida


def ler_json(nome: str):
    arq = PASTA_DADOS / nome
    if not arq.exists():
        sys.exit(f"Não encontrei {arq}. Rode antes a etapa 4.")
    return json.loads(arq.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha")
    ap.add_argument("--rotulo", required=True)
    ap.add_argument("--ids", default="", help="ids separados por vírgula")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--semente", type=int, default=7)
    args = ap.parse_args()

    entrada = {p["id"]: p for p in ler_json("teste_entrada.json")}
    gabarito = ler_json("teste_gabarito.json")
    arq_res = PASTA_DADOS / f"resultados_{args.rotulo}.jsonl"
    if not arq_res.exists():
        sys.exit(f"Não encontrei {arq_res}.")
    resultados = {}
    for linha in arq_res.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            r = json.loads(linha)
            if "erro" not in r and r["id"] in entrada:
                resultados[r["id"]] = r

    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
        faltando = [i for i in ids if i not in resultados]
        if faltando:
            sys.exit(f"Ids sem resultado na rodada '{args.rotulo}': {', '.join(faltando)}")
    else:
        ids = sorted(resultados)
        random.Random(args.semente).shuffle(ids)
        ids = sorted(ids[: args.n])

    desc = descricoes_da_planilha(Path(args.planilha))

    relatorios = []
    for i in ids:
        r = resultados[i]
        vistos = set()
        codigos = []
        for c in r.get("codigos", []):
            d = so_digitos(c.get("codigo"))
            if not d or d in vistos:
                continue
            vistos.add(d)
            codigos.append({
                "codigo": formatar(d),
                "descricao": desc.get(d, "(descrição não disponível)"),
                "origem": c.get("origem", ""),
                "nivel": c.get("nivel", ""),
                "confianca": c.get("confianca", ""),
            })
        candidatos = [
            {"codigo": formatar(c), "descricao": desc.get(so_digitos(c), "(descrição não disponível)")}
            for c in dict.fromkeys(r.get("candidatos", []))
            if so_digitos(c) not in vistos
        ]
        nao_realizados = [
            {"texto": t, "motivo": "data anterior à evolução"} for t in r.get("data_anterior", [])
        ]
        g = gabarito.get(i, {})
        relatorios.append({
            "prontuario_id": i,
            "texto_prontuario": entrada[i].get("texto", ""),
            "modelo_utilizado": args.rotulo,
            "falha_extracao": r.get("falha", ""),
            "codigos_sigtap": codigos,
            "candidatos_regra": candidatos,
            "termos_nao_realizados": nao_realizados,
            "codigos_gabarito": [
                {"codigo": formatar(c), "descricao": desc.get(so_digitos(c), "")} for c in g.get("codigos", [])
            ],
            "anotador": g.get("anotador", ""),
        })

    destino = PASTA_DADOS / f"demo_frontend_{args.rotulo}.json"
    destino.write_text(json.dumps(relatorios, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(relatorios)} evoluções gravadas em {destino}")
    print("Ids: " + ", ".join(ids))


if __name__ == "__main__":
    main()
