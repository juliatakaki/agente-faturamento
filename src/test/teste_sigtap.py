"""
3. Consulta os procedimentos na tabela SIGTAP
Script para testar a busca de procedimentos na tabela SIGTAP.
Envia os termos identificados e exibe os códigos e descrições
dos procedimentos encontrados.
"""

import sys
import os

# Adiciona a pasta src/mcp ao path, para poder importar sigtap_server
# mesmo estando dentro de src/test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))

from sigtap_server import buscar_procedimento, buscar_por_codigo

print("=== Busca por texto ===")
print(buscar_procedimento("hemograma"))

print("\n=== Busca por código (troque por um código real do seu banco) ===")
print(buscar_por_codigo("02.02.02.038-0"))