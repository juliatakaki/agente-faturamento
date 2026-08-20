"""
medir_generalizacao.py

Compara o comportamento do agente em DOIS conjuntos de prontuários:

  CALIBRAÇÃO  os 10 prontuários a partir dos quais o dicionário, os limiares
              e os padrões do NER foram construídos
  VALIDAÇÃO   prontuários que o sistema nunca "viu" durante o desenvolvimento

POR QUE ISTO EXISTE
-------------------
Todo o vocabulário do sistema veio de um único conjunto de 10 prontuários
sintéticos: as 31 entradas do dicionário, os limiares (0.80 semântico, 0.55
de cobertura IDF, 93 de fuzzy) e os padrões do NER por regras. Medir o
desempenho nesse mesmo conjunto não diz nada sobre prontuários reais -- diz
apenas que a calibração funcionou onde foi calibrada.

A diferença entre os dois conjuntos É a medida do quanto o sistema depende
dos dados em que foi construído. Um resultado honesto aqui vale mais, na
banca, do que um número alto obtido no conjunto de origem.

O QUE ESTE SCRIPT MEDE (e o que NÃO mede)
------------------------------------------
MEDE, sem precisar de gabarito:
  - taxa de extração do NER (quantas entidades por prontuário)
  - quanto do resultado vem do dicionário curado (Nível 0) e quanto das
    buscas genéricas
  - taxa de termos sem correspondência
  - taxa de correspondências de baixa confiança
  - cobertura do dicionário sobre os termos que apareceram

NÃO MEDE se as correspondências estão CERTAS -- isso exige o gabarito
(gerar_gabarito.py) preenchido por quem entende de faturamento. Um sistema
pode atribuir código a 100% dos termos e errar em todos.

COMO USAR
---------
1) Processe cada conjunto num arquivo separado:

   python main.py --entrada data/prontuarios.json ^
       --json-intermediario reports/proc_calibracao.json --sem-pdf --sem-menu

   python main.py --entrada data/prontuarios_validacao.json ^
       --json-intermediario reports/proc_validacao.json --sem-pdf --sem-menu

   (--sem-menu usa o modelo do .env, garantindo que os dois lotes rodem com
   o MESMO modelo; se preferir escolher no menu, escolha a mesma opção nas
   duas execuções, ou a comparação mistura duas variáveis.)

2) Compare:

   python medir_generalizacao.py reports/proc_calibracao.json reports/proc_validacao.json

Coloque este arquivo na raiz do projeto, junto do main.py.
"""

import json
import os
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.abspath(__file__))
CAMINHO_DICIONARIO = os.path.join(RAIZ, "src", "mcp", "sinonimos_sigtap.json")

# Níveis considerados "conhecimento curado": vieram do dicionário escrito à
# mão a partir do conjunto de calibração. É a fração que NÃO deve transferir
# para prontuários novos -- e é justamente por isso que ela é a métrica
# central deste script.
NIVEIS_CURADOS = {"nivel0"}

ROTULO_NIVEL = {
    "nivel0": "Dicionário (curado)",
    "nivel1": "Exata",
    "nivel2": "Parcial (IDF)",
    "nivel_semantico": "Semântica",
    "nivel3": "Similaridade",
    "nivel4": "Agente",
}


def _normalizar(texto: str) -> str:
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.replace("-", " ").strip()


def carregar_relatorios(caminho: str) -> list[dict]:
    if not os.path.exists(caminho):
        print(f"Não encontrei {caminho}.")
        print("Veja as instruções no cabeçalho deste arquivo para gerá-lo.")
        sys.exit(1)
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    return dados if isinstance(dados, list) else [dados]


def carregar_chaves_dicionario() -> set[str]:
    """Todas as chaves do dicionário (sinônimos + não faturáveis)."""
    if not os.path.exists(CAMINHO_DICIONARIO):
        return set()
    with open(CAMINHO_DICIONARIO, encoding="utf-8") as f:
        dados = json.load(f)

    chaves = set()
    for chave in (dados.get("sinonimos") or {}):
        if not chave.startswith("_"):
            chaves.add(_normalizar(chave))
    for secao, termos in (dados.get("nao_faturavel") or {}).items():
        if secao.startswith("_") or not isinstance(termos, list):
            continue
        for termo in termos:
            chaves.add(_normalizar(termo))
    return chaves


def resumir(relatorios: list[dict], chaves_dicionario: set[str]) -> dict:
    """Consolida as métricas de um conjunto de prontuários."""
    r = {
        "prontuarios": len(relatorios),
        "entidades": 0,
        "com_codigo": 0,
        "nao_faturavel": 0,
        "sem_correspondencia": 0,
        "por_nivel": {},
        "por_confianca": {"alta": 0, "media": 0, "baixa": 0},
        "termos_no_dicionario": 0,
        "termos_totais": 0,
        "valor": 0.0,
        "modelo": "não informado",
        "orquestracao": "",
    }

    for p in relatorios:
        r["modelo"] = p.get("modelo_utilizado") or r["modelo"]
        r["orquestracao"] = p.get("orquestracao") or r["orquestracao"]
        r["entidades"] += len(p.get("entidades_extraidas", []))

        termos_do_prontuario = set()

        for c in p.get("codigos_sigtap", []):
            r["com_codigo"] += 1
            r["valor"] += c.get("vl_total", 0.0) or 0.0
            nivel = c.get("nivel", "?")
            r["por_nivel"][nivel] = r["por_nivel"].get(nivel, 0) + 1
            conf = c.get("confianca", "")
            if conf in r["por_confianca"]:
                r["por_confianca"][conf] += 1
            if c.get("origem"):
                termos_do_prontuario.add(_normalizar(c["origem"]))

        for t in p.get("termos_nao_faturaveis", []):
            r["nao_faturavel"] += 1
            termos_do_prontuario.add(_normalizar(t))

        for t in p.get("termos_nao_encontrados", []):
            r["sem_correspondencia"] += 1
            termos_do_prontuario.add(_normalizar(t))

        r["termos_totais"] += len(termos_do_prontuario)
        r["termos_no_dicionario"] += len(termos_do_prontuario & chaves_dicionario)

    r["valor"] = round(r["valor"], 2)
    return r


def _pct(parte: int, total: int) -> str:
    return f"{parte / total:.0%}" if total else "—"


def _linha(rotulo: str, a: str, b: str) -> str:
    return f"  {rotulo:<38} {a:>14} {b:>14}"


def comparar(cal: dict, val: dict) -> None:
    print("=" * 70)
    print("MEDIÇÃO DE GENERALIZAÇÃO")
    print("=" * 70)

    if cal["modelo"] != val["modelo"]:
        print("\nATENÇÃO: os dois conjuntos rodaram com MODELOS DIFERENTES")
        print(f"  calibração: {cal['modelo']}")
        print(f"  validação:  {val['modelo']}")
        print("A comparação mistura duas variáveis. Rode os dois com o mesmo")
        print("modelo (use --sem-menu) antes de tirar conclusões.\n")
    else:
        print(f"\nModelo: {cal['modelo']}")
        if cal["orquestracao"]:
            print(f"Orquestração: {cal['orquestracao']}")

    print()
    print(_linha("", "CALIBRAÇÃO", "VALIDAÇÃO"))
    print("  " + "-" * 66)
    print(_linha("Prontuários", str(cal["prontuarios"]), str(val["prontuarios"])))

    # ── Extração (teto do NER) ────────────────────────────────────────────
    print()
    print("  EXTRAÇÃO DE ENTIDADES (teto do NER)")
    media_cal = cal["entidades"] / cal["prontuarios"] if cal["prontuarios"] else 0
    media_val = val["entidades"] / val["prontuarios"] if val["prontuarios"] else 0
    print(_linha("Entidades extraídas", str(cal["entidades"]), str(val["entidades"])))
    print(_linha("Média por prontuário", f"{media_cal:.1f}", f"{media_val:.1f}"))

    # ── Desfecho de cada termo ────────────────────────────────────────────
    print()
    print("  DESFECHO DOS TERMOS BUSCADOS")
    for chave, rotulo in (
        ("com_codigo", "Com código atribuído"),
        ("nao_faturavel", "Marcados sem código próprio"),
        ("sem_correspondencia", "Sem correspondência"),
    ):
        tot_c = cal["termos_totais"]
        tot_v = val["termos_totais"]
        print(_linha(
            rotulo,
            f"{cal[chave]} ({_pct(cal[chave], tot_c)})",
            f"{val[chave]} ({_pct(val[chave], tot_v)})",
        ))

    # ── A métrica central ─────────────────────────────────────────────────
    print()
    print("  DEPENDÊNCIA DO CONHECIMENTO CURADO")
    print("  (o dicionário foi escrito a partir do conjunto de calibração;")
    print("   quanto maior a queda aqui, mais o sistema depende dele)")
    cur_c = sum(n for niv, n in cal["por_nivel"].items() if niv in NIVEIS_CURADOS)
    cur_v = sum(n for niv, n in val["por_nivel"].items() if niv in NIVEIS_CURADOS)
    print(_linha(
        "Códigos vindos do dicionário",
        f"{cur_c} ({_pct(cur_c, cal['com_codigo'])})",
        f"{cur_v} ({_pct(cur_v, val['com_codigo'])})",
    ))
    print(_linha(
        "Termos presentes no dicionário",
        f"{cal['termos_no_dicionario']} ({_pct(cal['termos_no_dicionario'], cal['termos_totais'])})",
        f"{val['termos_no_dicionario']} ({_pct(val['termos_no_dicionario'], val['termos_totais'])})",
    ))

    # ── Distribuição por nível ────────────────────────────────────────────
    print()
    print("  DISTRIBUIÇÃO POR NÍVEL DE BUSCA")
    for nivel in ("nivel0", "nivel1", "nivel2", "nivel_semantico", "nivel3", "nivel4"):
        c = cal["por_nivel"].get(nivel, 0)
        v = val["por_nivel"].get(nivel, 0)
        if c or v:
            print(_linha(
                "  " + ROTULO_NIVEL.get(nivel, nivel),
                f"{c} ({_pct(c, cal['com_codigo'])})",
                f"{v} ({_pct(v, val['com_codigo'])})",
            ))

    # ── Confiança ─────────────────────────────────────────────────────────
    print()
    print("  CONFIANÇA DAS CORRESPONDÊNCIAS")
    for conf in ("alta", "media", "baixa"):
        c = cal["por_confianca"][conf]
        v = val["por_confianca"][conf]
        print(_linha(
            "  " + conf.capitalize(),
            f"{c} ({_pct(c, cal['com_codigo'])})",
            f"{v} ({_pct(v, val['com_codigo'])})",
        ))

    # ── Leitura do resultado ──────────────────────────────────────────────
    print()
    print("=" * 70)
    print("COMO LER ESTE RESULTADO")
    print("=" * 70)

    queda_dic = 0.0
    if cal["com_codigo"] and val["com_codigo"]:
        queda_dic = (cur_c / cal["com_codigo"]) - (cur_v / val["com_codigo"])

    sem_c = cal["sem_correspondencia"] / cal["termos_totais"] if cal["termos_totais"] else 0
    sem_v = val["sem_correspondencia"] / val["termos_totais"] if val["termos_totais"] else 0

    print(f"\nQueda na participação do dicionário: {queda_dic:+.0%}")
    print(f"Variação dos termos sem correspondência: {sem_v - sem_c:+.0%}")

    print("\nO esperado é que o dicionário caia e as lacunas subam -- ele foi")
    print("escrito para o conjunto de calibração. A questão é o TAMANHO da")
    print("diferença, e o que sobra funcionando sem ele: os níveis 1 a 4 são")
    print("estruturais e deveriam se manter estáveis entre os dois conjuntos.")
    print("\nSe a média de entidades extraídas cair muito, o gargalo é o NER")
    print("por regras, que só enxerga padrões previamente cadastrados -- e")
    print("nesse caso o problema está ANTES da busca: os termos sequer chegam")
    print("a ser procurados. Compare com EXTRATOR_ATIVO=llm.")
    print("\nNenhum destes números diz se as correspondências estão CERTAS.")
    print("Para isso é preciso o gabarito preenchido (gerar_gabarito.py).")


def main():
    if len(sys.argv) < 3:
        print("Uso: python medir_generalizacao.py <calibracao.json> <validacao.json>")
        print("\nVeja o cabeçalho deste arquivo para gerar os dois JSONs.")
        sys.exit(1)

    chaves = carregar_chaves_dicionario()
    if not chaves:
        print(f"AVISO: não consegui ler o dicionário em {CAMINHO_DICIONARIO}.")
        print("As métricas de cobertura do dicionário sairão zeradas.\n")

    cal = resumir(carregar_relatorios(sys.argv[1]), chaves)
    val = resumir(carregar_relatorios(sys.argv[2]), chaves)
    comparar(cal, val)


if __name__ == "__main__":
    main()