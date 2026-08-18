"""
auditar_nao_faturaveis.py

Confere, contra a tabela SIGTAP real, cada termo marcado como
"não faturável separadamente" no sinonimos_sigtap.json.

POR QUE ESTE SCRIPT EXISTE
--------------------------
A lista `nao_faturavel` do dicionário afirma que certos itens NÃO têm código
próprio no SIGTAP -- e o relatório repassa isso ao faturista como fato. Mas
boa parte dessas entradas foi criada por INFERÊNCIA, a partir de termos que
simplesmente não apareceram nas buscas automáticas, e não por consulta à
tabela ou ao setor de faturamento.

"A busca não achou pelo nome" e "não é faturável" são coisas diferentes. O
SIGTAP usa a nomenclatura oficial de fármacos (DCB), então adrenalina pode
estar como EPINEFRINA, noradrenalina como NOREPINEFRINA, e assim por diante.
Uma marcação errada faz o sistema afirmar, com aparência de certeza, que um
item não é faturável quando ele é -- ou seja, faz o hospital deixar de
cobrar algo a que tem direito.

O validar_sinonimos.py NÃO pega esses casos: ele usa a mesma busca do
pipeline, então um termo que a busca não acha continua parecendo ausente.
Este script busca por SUBSTRING (ILIKE) na tabela inteira, sem filtro de
grupo e sem os limiares da busca, e testa também sinônimos farmacológicos
conhecidos -- é deliberadamente mais permissivo, porque aqui o objetivo é
encontrar qualquer indício de que a marcação esteja errada.

Uso:
    python auditar_nao_faturaveis.py

Coloque na mesma pasta do sigtap_server.py (src/mcp/).

IMPORTANTE: nem a ausência de resultados aqui prova que um item não é
faturável. Só o setor de faturamento do HUB pode confirmar isso. Este script
serve para separar o que precisa ser corrigido AGORA do que precisa ser
levado à validação.
"""
import json
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import psycopg2

# ── Sinônimos farmacológicos e de nomenclatura ─────────────────────────────
#
# O prontuário usa o nome de uso corrente; o SIGTAP usa a Denominação Comum
# Brasileira. Para cada termo marcado como não faturável, também procuramos
# as variantes abaixo antes de aceitar a marcação como correta.
SINONIMOS_BUSCA = {
    "adrenalina": ["adrenalina", "epinefrina"],
    "noradrenalina": ["noradrenalina", "norepinefrina"],
    "solucao salina": ["cloreto de sodio", "salina", "soro fisiologico"],
    "bicarbonato de sodio": ["bicarbonato"],
    "cloreto de potassio": ["cloreto de potassio", "potassio"],
    "heparina": ["heparina"],
    "protamina": ["protamina"],
    "vancomicina": ["vancomicina"],
    "manitol": ["manitol"],
    "oseltamivir": ["oseltamivir", "fosfato de oseltamivir"],
    "azitromicina": ["azitromicina"],
    "sulfadiazina de prata": ["sulfadiazina", "prata"],
    "intubacao orotraqueal": ["intubacao", "orotraqueal", "traqueal"],
    "sedoanalgesia": ["sedacao", "analgesia", "anestesia"],
    "monitor cardiaco": ["monitorizacao", "monitor"],
    "monitorizacao cardiaca": ["monitorizacao"],
    "reposicao volemica": ["reposicao", "volemia", "hidratacao"],
    "cateter de swan ganz": ["swan", "ganz", "cateter de termodiluicao",
                             "cateter pulmonar"],
    "cateter nasal de oxigenio": ["cateter nasal", "cateter de oxigenio",
                                  "oxigenoterapia"],
    "sonda nasoenteral": ["nasoenteral", "nasogastrica", "sonda enteral"],
    "dreno abdominal": ["dreno"],
    "drenos mediastinais": ["dreno mediastinal", "mediastinal"],
    "mascara facial total": ["mascara"],
}


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acentos, sem hífens (mesma normalização do servidor)."""
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.replace("-", " ")


def conectar():
    return psycopg2.connect(
        host=os.getenv("SIGTAP_DB_HOST", "localhost"),
        port=os.getenv("SIGTAP_DB_PORT", "5432"),
        dbname=os.getenv("SIGTAP_DB_NAME", "sigtap"),
        user=os.getenv("SIGTAP_DB_USER", "sigtap"),
        password=os.getenv("SIGTAP_DB_PASSWORD", "sigtap"),
        connect_timeout=5,
    )


def carregar_nao_faturaveis(caminho: str) -> dict[str, str]:
    """Devolve {termo normalizado: seção do JSON}."""
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    saida = {}
    for secao, termos in (dados.get("nao_faturavel") or {}).items():
        if secao.startswith("_") or not isinstance(termos, list):
            continue
        for termo in termos:
            saida[_normalizar(termo)] = secao
    return saida


def buscar_na_tabela(cur, padrao: str) -> list[tuple[str, str]]:
    """
    Busca por substring, sem acento e sem filtro de grupo. Usa unaccent
    manual via translate para não depender da extensão unaccent do Postgres.
    """
    cur.execute(
        """
        SELECT co_procedimento, no_procedimento
          FROM tb_procedimento
         WHERE translate(
                   lower(no_procedimento),
                   'áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                   'aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC'
               ) LIKE %s
         ORDER BY co_procedimento
         LIMIT 8
        """,
        (f"%{padrao}%",),
    )
    return cur.fetchall()


def main():
    caminho = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sinonimos_sigtap.json"
    )
    if not os.path.exists(caminho):
        print(f"Não encontrei {caminho}")
        sys.exit(1)

    nao_faturaveis = carregar_nao_faturaveis(caminho)

    print("=" * 78)
    print("AUDITORIA DAS MARCAÇÕES DE 'NÃO FATURÁVEL'")
    print("=" * 78)
    print(f"Arquivo: {caminho}")
    print(f"Termos marcados como não faturáveis: {len(nao_faturaveis)}\n")
    print("Busca por SUBSTRING na tabela inteira, incluindo sinônimos")
    print("farmacológicos. Qualquer resultado abaixo indica que a marcação")
    print("PRECISA ser revista antes de o relatório afirmar que o item não é")
    print("faturável.\n")

    conn = conectar()
    cur = conn.cursor()

    suspeitos = []
    sem_indicio = []

    for termo, secao in sorted(nao_faturaveis.items()):
        padroes = SINONIMOS_BUSCA.get(termo, [termo])
        achados = []
        vistos = set()
        for padrao in padroes:
            for codigo, nome in buscar_na_tabela(cur, _normalizar(padrao)):
                if codigo not in vistos:
                    vistos.add(codigo)
                    achados.append((codigo, nome, padrao))

        if achados:
            suspeitos.append((termo, secao, achados))
            print(f"[REVER ] {termo}  ({secao})")
            for codigo, nome, padrao in achados[:6]:
                grupo = codigo[:2]
                print(f"           {codigo}  [g{grupo}]  {nome[:58]}")
                print(f"                     ^ encontrado buscando '{padrao}'")
            if len(achados) > 6:
                print(f"           ... e mais {len(achados) - 6} resultado(s)")
            print()
        else:
            sem_indicio.append((termo, secao))
            print(f"[ok    ] {termo}  ({secao}) — nenhum indício na tabela")

    conn.close()

    print("\n" + "=" * 78)
    print("RESUMO")
    print("=" * 78)
    print(f"  Marcações com indício de erro (REVER): {len(suspeitos)}")
    print(f"  Marcações sem indício na tabela:       {len(sem_indicio)}")

    if suspeitos:
        print("\nTERMOS A REVER — o SIGTAP tem procedimentos cujo nome contém")
        print("o termo (ou um sinônimo). Confira cada um: se algum for de fato")
        print("o item do prontuário, remova a entrada de 'nao_faturavel' no")
        print("JSON e, se necessário, crie um sinônimo apontando para ele.\n")
        for termo, secao, achados in suspeitos:
            print(f"  {termo:<28} {len(achados)} candidato(s)")

    print("\nATENÇÃO: 'nenhum indício na tabela' NÃO prova que o item não é")
    print("faturável -- prova apenas que não há procedimento com esse nome.")
    print("A marcação de não faturável é uma afirmação sobre as regras de")
    print("faturamento do SUS e só o setor de faturamento do HUB pode")
    print("confirmá-la. Até lá, o relatório deve apresentá-la como uma")
    print("marcação do sistema pendente de validação, não como fato.")


if __name__ == "__main__":
    main()