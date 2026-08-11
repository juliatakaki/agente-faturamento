"""
Gabarito de avaliação: monta a planilha de referência e calcula as métricas.

POR QUE ISTO EXISTE: sem um gabarito -- a resposta correta para cada termo,
decidida por quem entende de faturamento -- não há como dizer se o agente
acerta. Contar quantos termos "receberam um código" mede atividade, não
qualidade: na rodada anterior, 'manitol' recebia PIELOSTOMIA e isso contava
como sucesso. O gabarito é o que separa acerto de ruído e sustenta o capítulo
de resultados.

FLUXO DE USO
------------
1) Gerar a planilha pré-preenchida com o que o agente produziu:
       python gerar_gabarito.py
   Cria reports/gabarito.csv com uma linha por termo buscado, já com o
   código que o agente retornou.

2) Preencher a coluna 'veredito' (e as demais quando fizer sentido).
   Abra no Excel/LibreOffice. Vale a pena fazer isso junto com a enfermeira
   do setor de faturamento -- é justamente o tipo de julgamento que o
   sistema não pode fazer sozinho.

       veredito         significado
       ---------------  --------------------------------------------------
       correto          o código retornado é o que seria faturado
       incorreto        o agente retornou um código, mas é o errado
                        -> preencha 'codigo_correto' com o certo
       incompleto       o código está certo mas faltaram outros (painel)
                        -> liste os que faltaram em 'codigo_correto'
       lacuna           o agente não achou, mas EXISTE código no SIGTAP
                        -> preencha 'codigo_correto'
       ausente_ok       o agente não achou e realmente NÃO há código
                        (acerto: reconhecer a ausência é resposta correta)

3) Calcular as métricas sobre a planilha preenchida:
       python gerar_gabarito.py --avaliar

A planilha é reescrita preservando o que você já preencheu: rodar o passo 1
de novo depois de mudar o agente atualiza a coluna do que ele retornou e
mantém seus vereditos, para você ver o que melhorou e o que quebrou.

Coloque este arquivo na raiz do projeto (junto do main.py).
"""
import csv
import json
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_RELATORIOS = os.path.join(BASE, "reports", "relatorios_processados.json")
CAMINHO_GABARITO = os.path.join(BASE, "reports", "gabarito.csv")

COLUNAS = [
    # preenchidas automaticamente a partir da execução do agente
    "prontuario", "termo", "categoria", "nivel", "confianca",
    "codigo_retornado", "descricao_retornada", "valor_retornado",
    # preenchidas por você (e preservadas entre execuções)
    "veredito", "codigo_correto", "observacao",
]

VEREDITOS_VALIDOS = {
    "correto", "incorreto", "incompleto", "lacuna", "ausente_ok"
}


def carregar_relatorios() -> list[dict]:
    if not os.path.exists(CAMINHO_RELATORIOS):
        print(f"Não encontrei {CAMINHO_RELATORIOS}.")
        print("Rode 'python main.py' antes para gerar os relatórios.")
        sys.exit(1)
    with open(CAMINHO_RELATORIOS, encoding="utf-8") as f:
        dados = json.load(f)
    return dados if isinstance(dados, list) else [dados]


def linhas_do_agente(relatorios: list[dict]) -> list[dict]:
    """
    Converte os relatórios numa linha por termo buscado, cobrindo os três
    desfechos possíveis: com código, sem correspondência e não faturável.
    Um termo de painel gera uma linha por código, porque cada código é uma
    decisão de faturamento separada e pode estar certa ou errada por si.
    """
    linhas = []
    for rel in relatorios:
        pid = rel.get("prontuario_id", "?")

        for c in rel.get("codigos_sigtap", []):
            linhas.append({
                "prontuario": pid,
                "termo": c.get("origem", ""),
                "categoria": c.get("categoria", ""),
                "nivel": c.get("nivel", ""),
                "confianca": c.get("confianca", ""),
                "codigo_retornado": c.get("codigo", ""),
                "descricao_retornada": c.get("descricao", ""),
                "valor_retornado": c.get("vl_total", 0.0),
            })

        for termo in rel.get("termos_nao_encontrados", []):
            linhas.append({
                "prontuario": pid, "termo": termo, "categoria": "",
                "nivel": "vazio", "confianca": "",
                "codigo_retornado": "", "descricao_retornada": "",
                "valor_retornado": 0.0,
            })

        for termo in rel.get("termos_nao_faturaveis", []):
            linhas.append({
                "prontuario": pid, "termo": termo, "categoria": "",
                "nivel": "nao_faturavel", "confianca": "",
                "codigo_retornado": "", "descricao_retornada": "",
                "valor_retornado": 0.0,
            })

    return linhas


def carregar_vereditos_existentes() -> dict[tuple[str, str], dict]:
    """
    Lê os vereditos já preenchidos, indexados por (prontuário, termo), para
    que regerar a planilha depois de mexer no agente não apague o trabalho
    manual. A chave ignora o código retornado de propósito: se o agente
    mudou de código para o mesmo termo, o veredito antigo precisa ser
    revisto -- e é sinalizado como tal na coluna 'observacao'.
    """
    if not os.path.exists(CAMINHO_GABARITO):
        return {}

    existentes = {}
    with open(CAMINHO_GABARITO, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            chave = (linha.get("prontuario", ""), linha.get("termo", ""))
            if linha.get("veredito", "").strip():
                existentes[chave] = linha
    return existentes


def gerar():
    relatorios = carregar_relatorios()
    linhas = linhas_do_agente(relatorios)
    anteriores = carregar_vereditos_existentes()

    preservados = 0
    revisar = 0
    for linha in linhas:
        chave = (linha["prontuario"], linha["termo"])
        antigo = anteriores.get(chave)
        if not antigo:
            linha.update({"veredito": "", "codigo_correto": "", "observacao": ""})
            continue

        linha["veredito"] = antigo.get("veredito", "")
        linha["codigo_correto"] = antigo.get("codigo_correto", "")
        linha["observacao"] = antigo.get("observacao", "")
        preservados += 1

        # O agente mudou de resposta para um termo já julgado: o veredito
        # anterior não vale mais automaticamente.
        if antigo.get("codigo_retornado", "") != linha["codigo_retornado"]:
            linha["observacao"] = (
                f"REVISAR: antes retornava "
                f"'{antigo.get('codigo_retornado', '(nada)') or '(nada)'}'. "
                + linha["observacao"]
            ).strip()
            revisar += 1

    os.makedirs(os.path.dirname(CAMINHO_GABARITO), exist_ok=True)
    with open(CAMINHO_GABARITO, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)

    pendentes = sum(1 for l in linhas if not l["veredito"])
    print(f"Gabarito gravado em: {CAMINHO_GABARITO}")
    print(f"  {len(linhas)} linha(s) no total")
    print(f"  {preservados} veredito(s) preservado(s) de execuções anteriores")
    if revisar:
        print(f"  {revisar} linha(s) marcada(s) como REVISAR (o agente mudou "
              f"de resposta)")
    print(f"  {pendentes} linha(s) aguardando veredito")
    print("\nPreencha a coluna 'veredito' e rode:")
    print("  python gerar_gabarito.py --avaliar")


def avaliar():
    if not os.path.exists(CAMINHO_GABARITO):
        print(f"Não encontrei {CAMINHO_GABARITO}. Rode sem --avaliar primeiro.")
        sys.exit(1)

    with open(CAMINHO_GABARITO, encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))

    julgadas = [l for l in linhas if l.get("veredito", "").strip()]
    pendentes = len(linhas) - len(julgadas)

    invalidos = {
        l["veredito"].strip() for l in julgadas
        if l["veredito"].strip() not in VEREDITOS_VALIDOS
    }
    if invalidos:
        print(f"Vereditos não reconhecidos: {', '.join(sorted(invalidos))}")
        print(f"Use apenas: {', '.join(sorted(VEREDITOS_VALIDOS))}")
        sys.exit(1)

    if not julgadas:
        print("Nenhuma linha julgada ainda. Preencha a coluna 'veredito'.")
        sys.exit(1)

    contagem = Counter(l["veredito"].strip() for l in julgadas)
    n = len(julgadas)

    # O agente RESPONDEU quando devolveu um código; ABSTEVE-SE quando não
    # devolveu (vazio ou não faturável).
    respondeu = [l for l in julgadas if l.get("codigo_retornado", "").strip()]
    absteve = [l for l in julgadas if not l.get("codigo_retornado", "").strip()]

    corretas = contagem["correto"]
    incorretas = contagem["incorreto"]
    incompletas = contagem["incompleto"]
    lacunas = contagem["lacuna"]
    ausencias_ok = contagem["ausente_ok"]

    print("=" * 70)
    print("MÉTRICAS DE AVALIAÇÃO")
    print("=" * 70)
    print(f"Linhas julgadas: {n}" + (f"  ({pendentes} pendentes)" if pendentes else ""))
    print()
    for veredito in sorted(VEREDITOS_VALIDOS):
        print(f"  {veredito:<14} {contagem[veredito]:>4}")

    print("\n" + "-" * 70)
    if respondeu:
        # Precisão: dos códigos que o agente propôs, quantos um auditor
        # aceitaria. É a métrica que importa para faturamento -- um código
        # errado proposto custa glosa.
        precisao = corretas / len(respondeu)
        print(f"Precisão (dos {len(respondeu)} códigos propostos): {precisao:.1%}")

    # Cobertura: dos termos que TÊM código no SIGTAP, quantos o agente achou
    # e acertou. 'ausente_ok' fica fora do denominador: não havia o que achar.
    com_codigo_existente = corretas + incorretas + incompletas + lacunas
    if com_codigo_existente:
        cobertura = corretas / com_codigo_existente
        print(f"Cobertura (dos {com_codigo_existente} termos com código no "
              f"SIGTAP): {cobertura:.1%}")

    if absteve:
        # Quando o agente se absteve, ele acertou ao se abster?
        acerto_abstencao = ausencias_ok / len(absteve)
        print(f"Abstenção correta (das {len(absteve)} abstenções): "
              f"{acerto_abstencao:.1%}")

    print("\n" + "-" * 70)
    print("DESEMPENHO POR NÍVEL DE BUSCA")
    print("-" * 70)
    por_nivel: dict[str, Counter] = {}
    for l in julgadas:
        por_nivel.setdefault(l.get("nivel", "?"), Counter())[l["veredito"].strip()] += 1
    for nivel, cont in sorted(por_nivel.items(), key=lambda x: -sum(x[1].values())):
        total = sum(cont.values())
        acertos = cont["correto"] + cont["ausente_ok"]
        print(f"  {nivel:<18} {acertos:>3}/{total:<3} acertos  "
              f"({acertos / total:.0%})")

    print("\n" + "-" * 70)
    print("DESEMPENHO POR CONFIANÇA DECLARADA")
    print("-" * 70)
    print("Se a confiança for útil, 'alta' deve errar menos que 'baixa'.")
    por_conf: dict[str, Counter] = {}
    for l in respondeu:
        chave = l.get("confianca", "") or "(sem)"
        por_conf.setdefault(chave, Counter())[l["veredito"].strip()] += 1
    for conf in ("alta", "media", "baixa", "(sem)"):
        cont = por_conf.get(conf)
        if not cont:
            continue
        total = sum(cont.values())
        print(f"  {conf:<8} {cont['correto']:>3}/{total:<3} corretos  "
              f"({cont['correto'] / total:.0%})")

    erros = [l for l in julgadas if l["veredito"].strip() in ("incorreto", "lacuna")]
    if erros:
        print("\n" + "-" * 70)
        print(f"ERROS A INVESTIGAR ({len(erros)})")
        print("-" * 70)
        for l in erros:
            alvo = l.get("codigo_correto", "") or "(não informado)"
            print(f"  [{l['veredito']:<9}] {l['termo'][:34]:<34} "
                  f"retornou {l.get('codigo_retornado') or '(nada)':<16} "
                  f"correto: {alvo}")


if __name__ == "__main__":
    if "--avaliar" in sys.argv:
        avaliar()
    else:
        gerar()