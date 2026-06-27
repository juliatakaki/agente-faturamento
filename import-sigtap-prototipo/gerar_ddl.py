#!/usr/bin/env python3
"""
gerar_ddl.py

Le o layout.txt mestre do SIGTAP (varias tabelas, cada bloco comecando
com o nome da tabela, seguido do cabecalho Coluna,Tamanho,Inicio,Fim,Tipo
e das linhas de campos) e gera:

  1. Um arquivo schema.sql com os CREATE TABLE de todas as tabelas
  2. Um arquivo layouts.json com os campos/posicoes de cada tabela,
     usado depois pelo script de importacao (importar.py)

Uso:
    python gerar_ddl.py layout.txt
"""

import sys
import json
import re
import os
import glob

TIPO_MAP = {
    "VARCHAR2": "VARCHAR",
    "CHAR": "VARCHAR",   # DT_COMPETENCIA etc vem como texto (AAAAMM), nao precisa ser DATE
    "NUMBER": "NUMERIC",
}


def parse_layout_individual(path):
    """
    Le um arquivo de layout INDIVIDUAL (ex: rl_procedimento_incremento_layout.txt),
    que ja comeca direto no cabecalho 'Coluna,Tamanho,Inicio,Fim,Tipo', sem
    o nome da tabela na primeira linha. O nome da tabela e' inferido a partir
    do nome do arquivo (removendo o sufixo '_layout.txt' ou '_layout.TXT').
    """
    nome_arquivo = os.path.basename(path)
    nome_tabela = re.sub(r"_layout\.txt$", "", nome_arquivo, flags=re.IGNORECASE)

    with open(path, "r", encoding="utf-8") as f:
        linhas = [l.rstrip("\n") for l in f if l.strip() != ""]

    if not linhas or not linhas[0].strip().lower().startswith("coluna"):
        raise ValueError(
            f"Arquivo {path} nao comeca com o cabecalho 'Coluna,Tamanho,Inicio,Fim,Tipo'"
        )

    campos = []
    for linha in linhas[1:]:
        partes = [p.strip() for p in linha.split(",")]
        if len(partes) != 5:
            raise ValueError(f"Linha de campo invalida em {path}: '{linha}'")
        nome, tamanho, inicio, fim, tipo = partes
        campos.append({
            "nome": nome,
            "tamanho": int(tamanho),
            "inicio": int(inicio),
            "fim": int(fim),
            "tipo": tipo,
        })

    return {"tabela": nome_tabela, "campos": campos}


def parse_layout(path):
    """
    Retorna uma lista de dicts:
    [{"tabela": "tb_procedimento", "campos": [
        {"nome": "CO_PROCEDIMENTO", "tamanho": 10, "inicio": 1, "fim": 10, "tipo": "VARCHAR2"},
        ...
      ]},
     ...]
    """
    with open(path, "r", encoding="utf-8") as f:
        linhas = [l.rstrip("\n") for l in f]

    tabelas = []
    i = 0
    n = len(linhas)

    while i < n:
        linha = linhas[i].strip()

        # pula linhas vazias entre blocos
        if linha == "":
            i += 1
            continue

        # essa linha deve ser o nome da tabela
        nome_tabela = linha
        i += 1

        # proxima linha deve ser o cabecalho
        if i >= n or not linhas[i].strip().lower().startswith("coluna"):
            raise ValueError(
                f"Esperava cabecalho 'Coluna,Tamanho,...' apos '{nome_tabela}' "
                f"na linha {i+1}, encontrei: '{linhas[i] if i < n else 'EOF'}'"
            )
        i += 1  # pula o cabecalho

        campos = []
        while i < n and linhas[i].strip() != "":
            partes = [p.strip() for p in linhas[i].split(",")]
            if len(partes) != 5:
                raise ValueError(
                    f"Linha de campo invalida na tabela {nome_tabela}, linha {i+1}: '{linhas[i]}'"
                )
            nome, tamanho, inicio, fim, tipo = partes
            campos.append({
                "nome": nome,
                "tamanho": int(tamanho),
                "inicio": int(inicio),
                "fim": int(fim),
                "tipo": tipo,
            })
            i += 1

        tabelas.append({"tabela": nome_tabela, "campos": campos})

    return tabelas


def gerar_create_table(tabela_def):
    nome = tabela_def["tabela"]
    campos = tabela_def["campos"]

    linhas_sql = [f'CREATE TABLE IF NOT EXISTS {nome} (']
    defs = []
    for campo in campos:
        tipo_pg = TIPO_MAP.get(campo["tipo"].upper(), "VARCHAR")
        if tipo_pg == "VARCHAR":
            defs.append(f'    {campo["nome"].lower()} VARCHAR({campo["tamanho"]})')
        else:
            # NUMERIC: usamos o tamanho do campo como precisao maxima,
            # sem casas decimais fixas (o SIGTAP nao indica explicitamente
            # quantas casas decimais cada NUMBER tem no layout fornecido).
            defs.append(f'    {campo["nome"].lower()} NUMERIC')
    linhas_sql.append(",\n".join(defs))
    linhas_sql.append(");")
    return "\n".join(linhas_sql)


def main():
    if len(sys.argv) != 2:
        print("Uso: python gerar_ddl.py <diretorio_com_os_layouts>")
        print("  O diretorio deve conter o layout.txt mestre (opcional)")
        print("  e/ou arquivos individuais *_layout.txt")
        sys.exit(1)

    diretorio = sys.argv[1]

    tabelas_por_nome = {}

    # 1) Layout mestre (layout.txt), se existir
    caminho_mestre = os.path.join(diretorio, "layout.txt")
    if os.path.isfile(caminho_mestre):
        for t in parse_layout(caminho_mestre):
            tabelas_por_nome[t["tabela"].lower()] = t

    # 2) Arquivos de layout individuais (*_layout.txt), exceto o proprio layout.txt
    individuais = sorted(glob.glob(os.path.join(diretorio, "*_layout.txt")))
    individuais = [p for p in individuais if os.path.basename(p).lower() != "layout.txt"]

    for caminho in individuais:
        t = parse_layout_individual(caminho)
        # Um arquivo individual sobrescreve a versao do mestre se for diferente,
        # assumindo que o arquivo individual e' a fonte mais especifica/atualizada.
        tabelas_por_nome[t["tabela"].lower()] = t

    tabelas = list(tabelas_por_nome.values())

    if not tabelas:
        print(f"Nenhuma tabela encontrada em {diretorio}. Verifique os arquivos.")
        sys.exit(1)

    print(f"Encontradas {len(tabelas)} tabelas (mestre + individuais):\n")
    for t in sorted(tabelas, key=lambda x: x["tabela"]):
        print(f"  - {t['tabela']:35s} ({len(t['campos'])} campos)")

    # gera schema.sql
    saida_sql = os.path.join(diretorio, "schema.sql")
    with open(saida_sql, "w", encoding="utf-8") as f:
        f.write("-- Schema gerado automaticamente a partir dos layouts do SIGTAP\n")
        f.write("-- Gerado por gerar_ddl.py\n\n")
        for t in tabelas:
            f.write(gerar_create_table(t))
            f.write("\n\n")

    # gera layouts.json (usado no importar.py)
    saida_json = os.path.join(diretorio, "layouts.json")
    with open(saida_json, "w", encoding="utf-8") as f:
        json.dump(tabelas, f, ensure_ascii=False, indent=2)

    print(f"\nGerado {saida_sql} ({len(tabelas)} tabelas) e {saida_json}")


if __name__ == "__main__":
    main()
