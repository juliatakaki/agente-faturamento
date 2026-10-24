#!/usr/bin/env python3
"""
Gera frontend/public/sigtap.json a partir da Tabela Unificada do SIGTAP
(DATASUS). A tela de conferência usa esse arquivo para buscar procedimentos na
inclusão manual e para mostrar descrição e valor de cada código, sem depender do
Postgres da VM. A tabela é pública, então o JSON pode ir para o git.

Uso (a partir da raiz do projeto):
    python src/analise/gerar_sigtap_frontend.py TabelaUnificada_202606_v2606.zip
    python src/analise/gerar_sigtap_frontend.py caminho/tb_procedimento.txt

Prefira passar o .zip baixado do site do SIGTAP: o script lê tb_procedimento.txt
e tb_procedimento_layout.txt de dentro dele, na codificação original (latin-1).
Abrir e salvar o .txt num editor costuma estragar os acentos.

Com o .txt solto, o layout é lido de tb_procedimento_layout.txt na mesma pasta;
se não existir, usa o layout padrão do SIGTAP.

Saída: lista de {"c": código só com dígitos, "n": nome, "v": valor total em R$}.
O valor total é SH + SA + SP (os campos vêm em centavos).
"""
import io
import json
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "frontend" / "public" / "sigtap.json"

# Layout padrão (tb_procedimento_layout.txt), posições começando em 1.
LAYOUT_PADRAO = {
    "CO_PROCEDIMENTO": (1, 10),
    "NO_PROCEDIMENTO": (11, 260),
    "VL_SH": (283, 294),
    "VL_SA": (295, 306),
    "VL_SP": (307, 318),
    "DT_COMPETENCIA": (331, 336),
}


def decodificar(dados: bytes) -> str:
    """O DATASUS publica em latin-1. Aceita também um arquivo já convertido para UTF-8."""
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("latin-1")


def ler_layout(texto: str) -> dict:
    layout = {}
    for linha in texto.splitlines()[1:]:
        partes = [p.strip() for p in linha.split(",")]
        if len(partes) >= 4 and partes[2].isdigit() and partes[3].isdigit():
            layout[partes[0]] = (int(partes[2]), int(partes[3]))
    faltando = [c for c in LAYOUT_PADRAO if c not in layout]
    if faltando:
        sys.exit(f"Layout sem as colunas {', '.join(faltando)}.")
    return layout


def abrir(caminho: Path) -> tuple[str, dict]:
    if caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as z:
            nomes = {Path(n).name.lower(): n for n in z.namelist()}
            if "tb_procedimento.txt" not in nomes:
                sys.exit("O zip não tem tb_procedimento.txt.")
            texto = decodificar(z.read(nomes["tb_procedimento.txt"]))
            lay = nomes.get("tb_procedimento_layout.txt")
            layout = ler_layout(decodificar(z.read(lay))) if lay else LAYOUT_PADRAO
        return texto, layout
    texto = decodificar(caminho.read_bytes())
    arq_layout = caminho.with_name("tb_procedimento_layout.txt")
    layout = ler_layout(decodificar(arq_layout.read_bytes())) if arq_layout.exists() else LAYOUT_PADRAO
    return texto, layout


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    caminho = Path(sys.argv[1])
    if not caminho.exists():
        sys.exit(f"Não encontrei {caminho}.")
    texto, layout = abrir(caminho)

    def campo(linha: str, nome: str) -> str:
        ini, fim = layout[nome]
        return linha[ini - 1 : fim]

    def centavos(linha: str, nome: str) -> int:
        v = campo(linha, nome).strip()
        return int(v) if v.isdigit() else 0

    saida = []
    competencias = set()
    estragados = 0
    for linha in texto.splitlines():
        if len(linha) < layout["VL_SP"][1]:
            continue
        codigo = campo(linha, "CO_PROCEDIMENTO").strip()
        if not codigo.isdigit():
            continue
        nome = " ".join(campo(linha, "NO_PROCEDIMENTO").split())
        if "�" in nome:
            estragados += 1
        total = centavos(linha, "VL_SH") + centavos(linha, "VL_SA") + centavos(linha, "VL_SP")
        saida.append({"c": codigo, "n": nome, "v": round(total / 100, 2)})
        competencias.add(campo(linha, "DT_COMPETENCIA").strip())

    if not saida:
        sys.exit("Nenhum procedimento lido. Confira se o arquivo é o tb_procedimento.txt.")

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    comp = ", ".join(sorted(c for c in competencias if c))
    print(f"{len(saida)} procedimentos gravados em {DESTINO} (competência {comp}).")
    if estragados:
        print(f"AVISO: {estragados} nomes com acentos estragados (o arquivo foi salvo numa codificação errada).")
        print("A busca continua funcionando, mas os nomes aparecem com '�'. Rode de novo com o .zip original.")


if __name__ == "__main__":
    main()
