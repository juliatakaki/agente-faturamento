"""
Calibração dos limiares de busca do SIGTAP.

Roda os termos do seu conjunto de teste contra a tabela real e imprime os
NÚMEROS que sustentam a escolha dos limiares -- em vez de você chutar
valores. Serve tanto para ajustar o protótipo quanto para justificar os
limiares no TCC com evidência empírica.

Mostra três coisas:
  1. IDF das palavras dos termos -- quais são fortes e quais são fracas
     como evidência de correspondência (base do nível 2).
  2. Similaridade semântica máxima de cada termo dentro do grupo correto
     do SIGTAP -- para escolher LIMIAR_SIMILARIDADE_SEMANTICA.
  3. O que cada termo retorna hoje, com nível, score e confiança.

Uso:
    python calibrar_sigtap.py                 # usa a lista de exemplo abaixo
    python calibrar_sigtap.py termos.txt      # um "termo|CATEGORIA" por linha

Coloque na mesma pasta do sigtap_server.py (src/mcp/).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sigtap_server as sv  # noqa: E402

# Termos observados nos testes do protótipo, com a categoria vinda do NER.
# Inclui deliberadamente os casos que davam falso positivo, para você ver o
# efeito das mudanças.
TERMOS_PADRAO = [
    ("intubação orotraqueal", "PROCEDIMENTO"),
    ("ventilação mecânica invasiva", "PROCEDIMENTO"),
    ("sedoanalgesia", "PROCEDIMENTO"),
    ("hemograma completo", "EXAME"),
    ("raio-x de tórax", "EXAME"),
    ("PCR", "EXAME"),
    ("coagulograma", "EXAME"),
    ("procalcitonina", "EXAME"),
    ("cetonemia", "EXAME"),
    ("CK-MB", "EXAME"),
    ("gasometria arterial", "EXAME"),
    ("líquido cefalorraquidiano", "EXAME"),
    ("perfil lipídico", "EXAME"),
    ("cateter venoso central", "MATERIAL"),
    ("cateter de Swan-Ganz", "MATERIAL"),
    ("cateter nasal de oxigênio", "MATERIAL"),
    ("sonda nasoenteral", "MATERIAL"),
    ("dreno abdominal", "MATERIAL"),
    ("máscara facial total", "MATERIAL"),
    ("heparina", "MEDICAMENTO"),
    ("protamina", "MEDICAMENTO"),
    ("manitol", "MEDICAMENTO"),
    ("oseltamivir", "MEDICAMENTO"),
    ("azitromicina", "MEDICAMENTO"),
    ("vancomicina", "MEDICAMENTO"),
    ("noradrenalina", "MEDICAMENTO"),
    ("sulfadiazina de prata", "MEDICAMENTO"),
    ("solução salina", "MEDICAMENTO"),
]


def carregar_termos(caminho: str | None):
    if not caminho:
        return TERMOS_PADRAO
    termos = []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            if "|" in linha:
                termo, categoria = linha.split("|", 1)
                termos.append((termo.strip(), categoria.strip().upper()))
            else:
                termos.append((linha, ""))
    return termos


termos = carregar_termos(sys.argv[1] if len(sys.argv) > 1 else None)

print("=" * 78)
print("CALIBRAÇÃO DA BUSCA SIGTAP")
print("=" * 78)

tabela = sv._get_tabela()
print(f"Tabela: {len(tabela)} procedimentos")
print(f"Limiar semântico atual:  {sv._LIMIAR_SIMILARIDADE_SEMANTICA}")
print(f"Limiar cobertura IDF:    {sv._LIMIAR_COBERTURA_IDF}")

# ── 1. IDF das palavras ────────────────────────────────────────────────────
print("\n" + "=" * 78)
print("1. IDF DAS PALAVRAS (maior = mais discriminativa)")
print("=" * 78)
print("Palavras com IDF baixo aparecem em muitas descrições e não deveriam,")
print("sozinhas, decidir uma correspondência de faturamento.\n")

vistas = {}
for termo, _ in termos:
    for palavra in sv._normalizar(termo).split():
        if len(palavra) > 2 and palavra not in vistas:
            vistas[palavra] = sv._idf_palavra(palavra)

for palavra, idf in sorted(vistas.items(), key=lambda x: x[1]):
    n_desc = sum(
        1 for d in tabela["descricao_norm"] if sv._contem_palavra(d, palavra)
    )
    marca = "FRACA " if idf < 4.5 else "      "
    print(f"  {marca}{palavra:<28} idf={idf:5.2f}  ({n_desc} descrições)")

# ── 2. Similaridade semântica ──────────────────────────────────────────────
print("\n" + "=" * 78)
print("2. SIMILARIDADE SEMÂNTICA MÁXIMA (dentro do grupo da categoria)")
print("=" * 78)
print("Escolha o limiar acima do maior score dos casos ERRADOS e abaixo do")
print("menor score dos casos CERTOS. Se não houver essa separação, o modelo")
print("de embeddings não distingue esses termos -- e o limiar deve ser alto.\n")

for termo, categoria in termos:
    termo_norm = sv._normalizar(termo)
    candidatos = sv._filtrar_por_categoria(tabela, categoria)
    if candidatos.empty:
        print(f"  {termo:<32} (sem candidatos no grupo)")
        continue
    try:
        resultado, score = sv._buscar_semantico(termo_norm, candidatos)
        # _buscar_semantico devolve vazio abaixo do limiar; para calibrar
        # queremos o score independentemente disso, então recalculamos o topo
        modelo = sv._carregar_modelo_embeddings()
        emb_tab = sv._obter_embeddings_tabela(tabela)
        import numpy as np
        pos = candidatos.index.to_numpy()
        emb_termo = modelo.encode([termo_norm], normalize_embeddings=True)[0]
        sims = emb_tab[pos] @ emb_termo.astype(emb_tab.dtype)
        melhor = int(np.argmax(sims))
        score = float(sims[melhor])
        desc = candidatos.iloc[melhor]["descricao"][:44]
        passa = "PASSA" if score >= sv._LIMIAR_SIMILARIDADE_SEMANTICA else "corta"
        print(f"  {termo:<32} {score:.3f} [{passa}] -> {desc}")
    except ImportError:
        print("  (sentence-transformers não instalado)")
        break

# ── 3. Resultado atual ─────────────────────────────────────────────────────
print("\n" + "=" * 78)
print("3. RESULTADO ATUAL DA BUSCA COMPLETA")
print("=" * 78)

contagem: dict[str, int] = {}
for termo, categoria in termos:
    resultados, nivel, score = sv._buscar_com_nivel(termo, categoria)
    contagem[nivel] = contagem.get(nivel, 0) + 1
    confianca = sv._confianca(nivel, score)
    if resultados.empty:
        print(f"  {termo:<32} [{nivel}] SEM CORRESPONDÊNCIA")
    else:
        desc = resultados.iloc[0]["descricao"][:44]
        print(f"  {termo:<32} [{nivel}/{confianca}] {score:.2f} -> {desc}")

print("\nDistribuição por nível:")
for nivel, n in sorted(contagem.items(), key=lambda x: -x[1]):
    print(f"  {nivel:<20} {n}")

print("\nAjuste os limiares no .env (LIMIAR_SIMILARIDADE_SEMANTICA, "
      "LIMIAR_COBERTURA_IDF) e rode de novo para comparar.")