"""
main.py — Ponto de entrada único do protótipo.

Executa o fluxo completo de faturamento SUS de ponta a ponta:

    prontuários (JSON)
        -> NER (spaCy)
        -> refinamento LLM + consulta SIGTAP (MCP)
        -> consolidação (JSON de relatórios)
        -> geração do relatório final (.md e .pdf)

Uso:
    python main.py                          # usa os caminhos padrão
    python main.py --entrada dados.json     # outro arquivo de entrada
    python main.py --saida-relatorio rel    # outro nome de relatório

Padrões (relativos à raiz do projeto, onde este arquivo está):
    entrada          -> data/prontuarios.json
    json intermediário -> reports/relatorios_processados.json
    relatório final  -> reports/relatorio_sus(.md/.pdf)
"""

import os
import sys
import asyncio
import argparse

# Garante que a pasta src/ esteja no path para importar os módulos internos,
# independentemente do diretório de onde o script é chamado.
RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "src"))

from agent.pipeline import processar_lote
from agent import gerar_relatorio


# ── Seleção interativa do modelo ────────────────────────────────────────────
#
# Apresenta um pequeno console para escolher, antes de rodar o pipeline, qual
# "cérebro" o agente vai usar. A escolha define as variáveis de ambiente
# (PROVEDOR_LLM, MODELO_LOCAL / PROVEDOR_API / MODELO_API) que o pipeline.py
# lê em criar_llm() -- e que o pipeline repassa EXPLICITAMENTE ao subprocesso
# do servidor MCP, para que o agente do nível 4 use o mesmo modelo.
#
# ATENÇÃO -- MODELOS DE API SAEM DE CATÁLOGO SEM AVISO: em agosto/2026 o
# modelo 'llama-3.3-70b-versatile' foi descontinuado pela Groq no meio dos
# testes, e todas as chamadas passaram a retornar 404. Se uma opção aqui
# parar de funcionar, liste os modelos disponíveis na sua conta antes de
# chutar um substituto:
#
#   python -c "import os,urllib.request,json;from dotenv import load_dotenv;\
#   load_dotenv();req=urllib.request.Request(\
#   'https://api.groq.com/openai/v1/models',headers={'Authorization':\
#   'Bearer '+os.getenv('GROQ_API_KEY','')});\
#   [print(m['id']) for m in json.load(urllib.request.urlopen(req))['data']]"
#
# Para o TCC, anote SEMPRE o nome exato do modelo e a data de cada execução:
# um resultado obtido com um modelo que saiu do ar não é reproduzível.
#
# Os nomes também podem ser sobrescritos por variável de ambiente, sem mexer
# no código -- útil quando um provedor renomeia um modelo:
#   MODELO_GROQ=openai/gpt-oss-20b python main.py
MODELO_OLLAMA_PADRAO = os.getenv("MODELO_OLLAMA", "llama3.2")
MODELO_GROQ_PADRAO = os.getenv("MODELO_GROQ", "openai/gpt-oss-120b")
MODELO_GOOGLE_PADRAO = os.getenv("MODELO_GOOGLE", "gemini-3.5-flash")

# Cada opção: (rótulo exibido, provedor, modelo, é_api)
OPCOES_MODELO = [
    (f"Local — Ollama ({MODELO_OLLAMA_PADRAO})",
     "local", MODELO_OLLAMA_PADRAO, False),
    (f"API — Groq ({MODELO_GROQ_PADRAO})",
     "groq", MODELO_GROQ_PADRAO, True),
    (f"API — Google ({MODELO_GOOGLE_PADRAO})",
     "google", MODELO_GOOGLE_PADRAO, True),
]

CHAVE_ENV_POR_PROVEDOR = {
    "google": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
}


def selecionar_modelo_interativo():
    """
    Mostra um console com as opções de modelo disponíveis e aplica a escolha
    às variáveis de ambiente que o pipeline usa (criar_llm() em pipeline.py).

    Retorna uma descrição curta da escolha, para exibir no resumo final.
    Se a entrada não for interativa (ex.: rodando em script/CI), mantém o
    que já estiver definido no .env sem perguntar nada.
    """
    if not sys.stdin.isatty():
        # Ambiente não interativo: respeita o .env como estava, sem perguntar.
        return "definido pelo .env (execução não interativa)"

    print("=" * 60)
    print("Selecione o modelo de linguagem do agente")
    print("=" * 60)
    for i, (rotulo, *_ ) in enumerate(OPCOES_MODELO, start=1):
        print(f"  [{i}] {rotulo}")
    print()

    escolha = None
    while escolha is None:
        bruto = input(f"Digite o número da opção [1-{len(OPCOES_MODELO)}]: ").strip()
        if bruto.isdigit() and 1 <= int(bruto) <= len(OPCOES_MODELO):
            escolha = int(bruto) - 1
        else:
            print("Opção inválida, tente novamente.")

    rotulo, provedor, modelo, e_api = OPCOES_MODELO[escolha]

    if not e_api:
        os.environ["PROVEDOR_LLM"] = "local"
        os.environ["MODELO_LOCAL"] = modelo
        # Limpa a configuração de API para que o subprocesso MCP não herde
        # um provedor antigo do .env e acabe rodando o nível 4 com um modelo
        # diferente do escolhido aqui.
        os.environ.pop("PROVEDOR_API", None)
        os.environ.pop("MODELO_API", None)
        print(f"\n-> Usando modelo local: {modelo}\n")
        return rotulo

    chave_env = CHAVE_ENV_POR_PROVEDOR[provedor]
    if not os.getenv(chave_env):
        print(
            f"\nAVISO: a variável {chave_env} não está definida no .env. "
            f"A chamada à API deve falhar até que ela seja configurada."
        )

    os.environ["PROVEDOR_LLM"] = "api"
    os.environ["PROVEDOR_API"] = provedor
    os.environ["MODELO_API"] = modelo
    print(f"\n-> Usando modelo via API ({provedor}): {modelo}\n")
    return f"{provedor} — {modelo}"


def _caminhos_padrao():
    """Monta os caminhos padrão relativos à raiz do projeto."""
    return {
        "entrada": os.path.join(RAIZ, "data", "prontuarios.json"),
        "json_intermediario": os.path.join(RAIZ, "reports", "relatorios_processados.json"),
        "saida_relatorio": os.path.join(RAIZ, "reports", "relatorio_sus"),
    }


def _parse_args():
    padroes = _caminhos_padrao()
    parser = argparse.ArgumentParser(
        description="Executa o pipeline completo de faturamento SUS (NER -> LLM/MCP -> relatório)."
    )
    parser.add_argument(
        "--entrada", default=padroes["entrada"],
        help="JSON de prontuários de entrada (padrão: data/prontuarios.json)"
    )
    parser.add_argument(
        "--json-intermediario", default=padroes["json_intermediario"],
        help="Onde salvar o JSON de relatórios processados "
             "(padrão: reports/relatorios_processados.json)"
    )
    parser.add_argument(
        "--saida-relatorio", default=padroes["saida_relatorio"],
        help="Nome base (sem extensão) do relatório final .md/.pdf "
             "(padrão: reports/relatorio_sus)"
    )
    parser.add_argument(
        "--sem-pdf", action="store_true",
        help="Gera apenas o .md, pulando o PDF (útil se o reportlab não estiver instalado)."
    )
    parser.add_argument(
        "--sem-menu", action="store_true",
        help="Pula o console de seleção de modelo e usa o que já estiver configurado no .env."
    )
    return parser.parse_args()


async def executar(entrada, json_intermediario, saida_relatorio, gerar_pdf=True):
    """Roda o fluxo completo e retorna o caminho dos arquivos gerados."""

    # ── Etapa 1: pipeline (NER -> LLM/MCP -> JSON consolidado) ──────────────
    print("=" * 60)
    print("ETAPA 1/2 — Processando prontuários (NER + LLM + SIGTAP)")
    print("=" * 60)

    if not os.path.exists(entrada):
        raise FileNotFoundError(
            f"Arquivo de entrada não encontrado: {entrada}\n"
            f"Verifique se os prontuários estão em data/prontuarios.json "
            f"ou informe outro caminho com --entrada."
        )

    os.makedirs(os.path.dirname(json_intermediario), exist_ok=True)
    relatorios = await processar_lote(entrada, json_intermediario)

    # ── Etapa 2: geração do relatório final (.md e .pdf) ───────────────────
    print()
    print("=" * 60)
    print("ETAPA 2/2 — Gerando relatório de faturamento")
    print("=" * 60)

    os.makedirs(os.path.dirname(saida_relatorio), exist_ok=True)

    # Markdown (sempre)
    md = gerar_relatorio.gerar_markdown(relatorios)
    caminho_md = f"{saida_relatorio}.md"
    with open(caminho_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Gerado: {caminho_md}")

    # PDF (opcional — depende do reportlab)
    caminho_pdf = None
    if gerar_pdf:
        try:
            caminho_pdf = f"{saida_relatorio}.pdf"
            gerar_relatorio.gerar_pdf(relatorios, caminho_pdf)
            print(f"Gerado: {caminho_pdf}")
        except ImportError:
            print("AVISO: reportlab não instalado — PDF não gerado. "
                  "Instale com 'pip install reportlab' ou use --sem-pdf. "
                  "O relatório .md foi gerado normalmente.")
            caminho_pdf = None

    return caminho_md, caminho_pdf


def main():
    args = _parse_args()

    if args.sem_menu:
        descricao_modelo = "definido pelo .env (--sem-menu)"
    else:
        descricao_modelo = selecionar_modelo_interativo()

    caminho_md, caminho_pdf = asyncio.run(
        executar(
            entrada=args.entrada,
            json_intermediario=args.json_intermediario,
            saida_relatorio=args.saida_relatorio,
            gerar_pdf=not args.sem_pdf,
        )
    )

    print()
    print("=" * 60)
    print("CONCLUÍDO")
    print("=" * 60)
    print(f"Modelo utilizado:   {descricao_modelo}")
    print(f"Relatório Markdown: {caminho_md}")
    if caminho_pdf:
        print(f"Relatório PDF:      {caminho_pdf}")
    print(f"JSON processado:    {args.json_intermediario}")


if __name__ == "__main__":
    main()