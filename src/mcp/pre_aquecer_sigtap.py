"""
Pré-aquecimento do cache de embeddings do SIGTAP.

Roda a carga do Postgres + o cálculo dos embeddings de TODAS as descrições
do SIGTAP uma única vez, em primeiro plano, com progresso visível no
terminal -- ao contrário de quando isso acontece "escondido" dentro do
subprocesso MCP na primeira busca semântica do pipeline.

Depois de rodar este script uma vez, o arquivo
.cache_embeddings_sigtap.npy fica populado e as próximas execuções do
pipeline (via MCP) reaproveitam esse cache, sem pagar o custo de
baixar/calcular os embeddings de novo.

Uso:
    python pre_aquecer_sigtap.py

Coloque este arquivo na mesma pasta do sigtap_server.py (src/mcp/) para
que o import funcione sem ajustes.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Pré-aquecimento do SIGTAP (Postgres + embeddings)")
print("=" * 60)

print("\n[1/3] Carregando tabela do Postgres...")
t0 = time.time()
import sigtap_server as sv  # noqa: E402  (import depois do sys.path.insert de propósito)
tabela = sv._get_tabela()
print(f"      OK - {len(tabela)} procedimentos carregados em {time.time() - t0:.1f}s")

print(f"\n[2/3] Carregando modelo de embeddings "
      f"'{sv._MODELO_EMBEDDINGS_NOME}' (baixa da internet se ainda não "
      "estiver em cache local)...")
t0 = time.time()
sv._carregar_modelo_embeddings()
print(f"      OK - modelo carregado em {time.time() - t0:.1f}s")

print(f"\n[3/3] Calculando embeddings para {len(tabela)} descrições "
      "(pode levar alguns minutos na primeira vez)...")
t0 = time.time()
embeddings = sv._obter_embeddings_tabela(tabela)
print(f"      OK - {embeddings.shape[0]} embeddings calculados em "
      f"{time.time() - t0:.1f}s")
print(f"      Salvo em: {sv._CACHE_EMBEDDINGS_PATH}")

print("\nPronto! As próximas execuções do pipeline vão reaproveitar esse cache.")