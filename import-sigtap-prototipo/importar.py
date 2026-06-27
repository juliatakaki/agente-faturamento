#!/usr/bin/env python3
"""
importar.py

Le os arquivos de DADOS do SIGTAP (largura fixa, um por tabela) e carrega
no Postgres, usando o layouts.json gerado pelo gerar_ddl.py para saber
onde cortar cada campo.

Encoding: o SIGTAP normalmente vem em Latin-1 (ISO-8859-1). Este script
tenta ler cada arquivo como UTF-8 primeiro; se falhar, usa Latin-1
automaticamente (que aceita qualquer byte e nao falha nunca).

Uso:
    python importar.py <diretorio_com_layouts_e_dados> \
        --host localhost --port 5432 --db sigtap --user sigtap --password sigtap

    Por padrao, o script procura por um arquivo de dados com o mesmo nome
    da tabela (case-insensitive) e extensao .txt dentro do diretorio
    informado. Ex: para a tabela "tb_procedimento", procura por
    "tb_procedimento.txt" (ou .TXT).
"""

import argparse
import json
import os
import sys
import io
import glob

import psycopg2


def detectar_encoding(path):
    """Tenta decodificar o arquivo como UTF-8 primeiro (se nao tiver erro,
    e' UTF-8). Caso contrario, usa latin-1, que e' o encoding padrao real
    dos arquivos de dados do SIGTAP/DATASUS e aceita qualquer byte (nunca
    falha), evitando falsos positivos de bibliotecas de deteccao automatica
    em textos curtos/repetitivos (que tendem a "advinhar" encodings exoticos
    como hp_roman8)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            f.read()
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def encontrar_arquivo_dados(diretorio, nome_tabela):
    """Procura um arquivo de dados correspondente ao nome da tabela,
    ignorando case e aceitando .txt/.TXT. Evita pegar arquivos de layout."""
    candidatos = glob.glob(os.path.join(diretorio, "*"))
    nome_tabela_lower = nome_tabela.lower()

    for caminho in candidatos:
        base = os.path.basename(caminho).lower()
        if "_layout" in base:
            continue
        nome_sem_ext, ext = os.path.splitext(base)
        if nome_sem_ext == nome_tabela_lower and ext == ".txt":
            return caminho

    return None


def converter_valor(valor_raw, tipo):
    """Converte o valor lido (string fixed-width, ja sem padding de espacos)
    para o tipo apropriado. Strings vazias viram NULL."""
    valor = valor_raw.strip()
    if valor == "":
        return None

    if tipo.upper() == "NUMBER":
        # Alguns campos NUMBER no SIGTAP podem ter zeros a esquerda
        # ou estar vazios (espacos). Tentamos converter; se falhar,
        # mantemos como NULL para nao quebrar a carga.
        try:
            if "." in valor or "," in valor:
                return float(valor.replace(",", "."))
            return int(valor)
        except ValueError:
            return None

    return valor


def importar_tabela(conn, diretorio, tabela_def, encoding_forcado=None):
    nome_tabela = tabela_def["tabela"]
    campos = tabela_def["campos"]

    caminho_dados = encontrar_arquivo_dados(diretorio, nome_tabela)
    if caminho_dados is None:
        print(f"  [PULADO] Nenhum arquivo de dados encontrado para '{nome_tabela}'")
        return 0

    encoding = encoding_forcado or detectar_encoding(caminho_dados)

    nomes_colunas = [c["nome"].lower() for c in campos]

    linhas_convertidas = []
    with open(caminho_dados, "r", encoding=encoding, errors="replace") as f:
        for num_linha, linha in enumerate(f, start=1):
            linha = linha.rstrip("\n").rstrip("\r")
            if linha.strip() == "":
                continue

            valores = []
            for campo in campos:
                # posicoes no layout sao 1-indexed e inclusivas
                inicio = campo["inicio"] - 1
                fim = campo["fim"]
                bruto = linha[inicio:fim] if len(linha) >= inicio else ""
                valores.append(converter_valor(bruto, campo["tipo"]))
            linhas_convertidas.append(valores)

    if not linhas_convertidas:
        print(f"  [VAZIO] {nome_tabela}: arquivo de dados sem linhas")
        return 0

    cur = conn.cursor()

    # usa COPY via buffer em memoria (rapido, mesmo para tabelas grandes)
    buffer = io.StringIO()
    for valores in linhas_convertidas:
        partes = []
        for v in valores:
            if v is None:
                partes.append("\\N")
            else:
                # escapa caracteres especiais do formato COPY (tab, backslash, newline)
                texto = str(v).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
                partes.append(texto)
        buffer.write("\t".join(partes))
        buffer.write("\n")
    buffer.seek(0)

    colunas_sql = ", ".join(nomes_colunas)
    cur.copy_expert(
        f"COPY {nome_tabela} ({colunas_sql}) FROM STDIN WITH (FORMAT text, NULL '\\N')",
        buffer,
    )
    conn.commit()
    cur.close()

    print(f"  [OK] {nome_tabela}: {len(linhas_convertidas)} linhas importadas (encoding={encoding})")
    return len(linhas_convertidas)


def main():
    parser = argparse.ArgumentParser(description="Importa dados fixed-width do SIGTAP para o Postgres")
    parser.add_argument("diretorio", help="Diretorio com layouts.json e os arquivos de dados (.txt)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default="5432")
    parser.add_argument("--db", default="sigtap")
    parser.add_argument("--user", default="sigtap")
    parser.add_argument("--password", default="sigtap")
    parser.add_argument("--encoding", default=None,
                         help="Forcar um encoding especifico (ex: latin-1) em vez de detectar automaticamente")
    parser.add_argument("--apenas", default=None,
                         help="Importar apenas esta tabela (nome exato, p/ testes)")
    args = parser.parse_args()

    caminho_layouts = os.path.join(args.diretorio, "layouts.json")
    if not os.path.isfile(caminho_layouts):
        print(f"Arquivo layouts.json nao encontrado em {args.diretorio}.")
        print("Rode primeiro: python gerar_ddl.py <diretorio>")
        sys.exit(1)

    with open(caminho_layouts, "r", encoding="utf-8") as f:
        tabelas = json.load(f)

    if args.apenas:
        tabelas = [t for t in tabelas if t["tabela"].lower() == args.apenas.lower()]
        if not tabelas:
            print(f"Tabela '{args.apenas}' nao encontrada em layouts.json")
            sys.exit(1)

    conn = psycopg2.connect(
        host=args.host, port=args.port, dbname=args.db,
        user=args.user, password=args.password,
    )

    total_linhas = 0
    total_tabelas_importadas = 0
    print(f"Importando {len(tabelas)} tabelas...\n")
    for tabela_def in tabelas:
        n = importar_tabela(conn, args.diretorio, tabela_def, encoding_forcado=args.encoding)
        if n > 0:
            total_tabelas_importadas += 1
        total_linhas += n

    conn.close()
    print(f"\nConcluido: {total_tabelas_importadas}/{len(tabelas)} tabelas, {total_linhas} linhas no total.")


if __name__ == "__main__":
    main()
