"""
Validação do dicionário clínico -> SIGTAP.

Confere que cada alvo declarado em sinonimos_sigtap.json realmente resolve
para algum procedimento da tabela SIGTAP. É o que impede o dicionário de
apodrecer em silêncio: um alvo escrito com o nome errado (ou que sumiu numa
nova competência do SIGTAP) apareceria como "sem correspondência" no
relatório, sem nenhuma pista de que a causa está no dicionário.

ATENÇÃO -- O QUE ESTE SCRIPT NÃO FAZ: ele confirma que o alvo RESOLVE, não
que resolve CERTO. Alvos genéricos resolvem para o primeiro específico da
tabela ('radiografia' -> RADIOGRAFIA DE LARINGE), o que é tecnicamente um
sucesso e clinicamente um erro. Confira sempre a coluna do procedimento
retornado: se ele for mais específico do que o termo pedia, o alvo precisa
ser reescrito ou a entrada removida.

RODE SEMPRE depois de editar o sinonimos_sigtap.json.

Uso:
    python validar_sinonimos.py

Coloque na mesma pasta do sigtap_server.py (src/mcp/).
Código de saída 1 se houver algum alvo não resolvido (útil em CI).
"""
import os
import sys

# Desliga a busca semântica ANTES de importar o servidor: a validação do
# dicionário é sobre correspondência TEXTUAL. Deixar o nível semântico ativo
# faria um alvo errado "resolver" por proximidade de embeddings, mascarando
# justamente o erro que queremos encontrar -- além de carregar o modelo
# (~10s) e poluir a saída.
os.environ["USAR_BUSCA_SEMANTICA"] = "false"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sigtap_server as sv  # noqa: E402

# Cada seção de 'nao_faturavel' corresponde a uma categoria de entidade e,
# portanto, a um recorte de grupos do SIGTAP. Sem isso a verificação busca na
# tabela inteira e dá falso alarme: 'bicarbonato de sódio' (medicamento)
# casava com GASOMETRIA porque a palavra aparece na descrição do exame, e
# 'dreno abdominal' (material) casava com RETIRADA DE DRENO TUBULAR TORÁCICO,
# que é o ato de retirar, não o insumo.
_CATEGORIA_DA_SECAO = {
    "medicamentos_uso_hospitalar": "MEDICAMENTO",
    "materiais_descartaveis": "MATERIAL",
    "procedimentos_embutidos": "PROCEDIMENTO",
    "exames_nao_cobertos": "EXAME",
}

print("=" * 78)
print("VALIDAÇÃO DO DICIONÁRIO CLÍNICO -> SIGTAP")
print("=" * 78)
print(f"Arquivo: {sv._CAMINHO_SINONIMOS}\n")

tabela = sv._get_tabela()
sinonimos, nao_faturavel = sv._carregar_dicionario()

if not sinonimos and not nao_faturavel:
    print("Nenhuma entrada carregada. Verifique o caminho e a sintaxe do JSON.")
    sys.exit(1)

# ── 1. Alvos dos sinônimos ─────────────────────────────────────────────────
print("=" * 78)
print(f"1. SINÔNIMOS ({len(sinonimos)} entradas)")
print("=" * 78)
print("Confira se o procedimento retornado é MAIS ESPECÍFICO do que o termo")
print("pedia -- nesse caso o alvo está genérico demais e precisa ser revisto.\n")

falhas = []
paineis = []

for termo, alvos in sorted(sinonimos.items()):
    linhas = []
    houve_falha = False
    for alvo in alvos:
        resultado, nivel, _ = sv._buscar_niveis_texto(alvo, tabela)
        if resultado.empty:
            falhas.append((termo, alvo))
            houve_falha = True
            linhas.append(f"      ALVO NÃO RESOLVIDO: '{alvo}'")
        else:
            linha = resultado.iloc[0]
            linhas.append(
                f"      '{alvo}' -> {linha['descricao'][:52]} "
                f"({linha['codigo']}) [{nivel}]"
            )
    print(f"  [{'FALHA' if houve_falha else '  ok '}] {termo}")
    for l in linhas:
        print(l)
    if len(alvos) > 1:
        paineis.append((termo, len(alvos)))

# ── 2. Termos marcados como não faturáveis ─────────────────────────────────
print("\n" + "=" * 78)
print(f"2. NÃO FATURÁVEIS ({len(nao_faturavel)} entradas)")
print("=" * 78)
print("Conferindo, DENTRO DO GRUPO da categoria, se algum deles na verdade")
print("existe no SIGTAP -- nesse caso a marcação está errada.\n")

marcados_indevidamente = []
for termo, secao in sorted(nao_faturavel.items()):
    categoria = _CATEGORIA_DA_SECAO.get(secao, "")
    candidatos = sv._filtrar_por_categoria(tabela, categoria)
    resultado, nivel, _ = sv._buscar_niveis_texto(termo, candidatos)

    if not resultado.empty and nivel in ("nivel1", "nivel2"):
        linha = resultado.iloc[0]
        marcados_indevidamente.append(
            (termo, categoria, linha["descricao"], linha["codigo"])
        )
        print(f"  [REVER] {termo:<28} existe no grupo de {categoria}: "
              f"{linha['descricao'][:38]} ({linha['codigo']})")
    else:
        print(f"  [  ok ] {termo:<28} ({secao})")

# ── 3. Chaves duplicadas entre as duas seções ──────────────────────────────
conflitos = set(sinonimos) & set(nao_faturavel)

# ── Resumo ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 78)
print("RESUMO")
print("=" * 78)
print(f"  Sinônimos válidos:        {len(sinonimos) - len({t for t, _ in falhas})}")
print(f"  Alvos não resolvidos:     {len(falhas)}")
print(f"  Painéis (>1 código):      {len(paineis)}")
print(f"  Não faturáveis a rever:   {len(marcados_indevidamente)}")
print(f"  Conflitos entre seções:   {len(conflitos)}")

if falhas:
    print("\nALVOS NÃO RESOLVIDOS -- corrija o nome no JSON para bater com a")
    print("nomenclatura real do SIGTAP. Para descobrir o nome exato:")
    print("  SELECT no_procedimento FROM tb_procedimento")
    print("   WHERE no_procedimento ILIKE '%trecho%';")
    for termo, alvo in falhas:
        print(f"  {termo:<28} -> '{alvo}'")

if marcados_indevidamente:
    print("\nMARCADOS COMO NÃO FATURÁVEIS MAS PRESENTES NO GRUPO CORRETO --")
    print("remova da lista 'nao_faturavel' para que a busca encontre o código:")
    for termo, categoria, desc, codigo in marcados_indevidamente:
        print(f"  {termo:<28} [{categoria}] {desc[:36]} ({codigo})")

if conflitos:
    print("\nTERMOS EM AMBAS AS SEÇÕES (a marcação de não faturável vence e o")
    print("sinônimo nunca é usado) -- mantenha em apenas uma:")
    for termo in sorted(conflitos):
        print(f"  {termo}")

if paineis:
    print("\nPAINÉIS (um termo clínico -> vários códigos faturáveis):")
    for termo, n in paineis:
        print(f"  {termo:<28} {n} códigos")

print("\nLembrete: este dicionário PRECISA ser validado pelo setor de")
print("faturamento do HUB antes de qualquer uso com dados reais.")

sys.exit(1 if (falhas or conflitos) else 0)