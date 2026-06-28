"""
Testa o nível 4 (fallback via LLM em DUAS etapas) isoladamente, mockando
ChatOllama. A etapa 1 (escolha) retorna um JSON com indice; a etapa 2
(verificacao) retorna SIM ou NAO. O mock distingue as duas etapas pelo
conteudo do prompt (a etapa 2 pergunta "MESMO ato clinico").
"""
import sys
sys.path.insert(0, "/home/claude/mcp_update")

import pandas as pd
import sigtap_server as srv


def fake_carregar_do_postgres():
    procedimentos = pd.DataFrame([
        {"codigo_bruto": "0202010992", "nome_curto": "Prova de retracao do coagulo",
         "descricao_longa": "", "co_grupo_derivado": "02"},
        {"codigo_bruto": "0202010990", "nome_curto": "Determinacao de tempo de coagulacao",
         "descricao_longa": "", "co_grupo_derivado": "02"},
        {"codigo_bruto": "0202010991", "nome_curto": "Dosagem de anticoagulante circulante",
         "descricao_longa": "", "co_grupo_derivado": "02"},
    ])
    grupos = pd.DataFrame([{"co_grupo": "02", "no_grupo": "Diagnostico"}])
    procedimentos = procedimentos.merge(grupos, left_on="co_grupo_derivado", right_on="co_grupo", how="left")
    return procedimentos


srv._carregar_do_postgres = fake_carregar_do_postgres


class FakeResposta:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    """
    Mock de ChatOllama que distingue as duas etapas pelo conteudo do prompt:
    - etapa de verificacao: o prompt contem "MESMO ato" -> retorna resp_verif
    - etapa de escolha: caso contrario -> retorna resp_escolha
    """
    def __init__(self, resp_escolha, resp_verif):
        self._resp_escolha = resp_escolha
        self._resp_verif = resp_verif

    def invoke(self, prompt):
        if "MESMO ato" in prompt:
            return FakeResposta(self._resp_verif)
        return FakeResposta(self._resp_escolha)


def rodar_com_mock(resp_escolha, resp_verif, termo="coagulograma"):
    original = srv.ChatOllama
    srv.ChatOllama = lambda model, temperature: FakeLLM(resp_escolha, resp_verif)
    try:
        resultados, nivel = srv._buscar_com_nivel(termo)
    finally:
        srv.ChatOllama = original
    return resultados, nivel


print("=== Caso 1: escolha valida + verificacao SIM -> aceito ===")
resultados, nivel = rodar_com_mock('{"indice": 0}', "SIM")
print(f"nivel={nivel}, resultado={resultados['descricao'].tolist() if not resultados.empty else 'vazio'}")
assert nivel == "nivel4"
assert resultados.iloc[0]["descricao"] == "Prova de retracao do coagulo"
print("OK\n")

print("=== Caso 2: escolha valida + verificacao NAO -> rejeitado (caso central) ===")
resultados, nivel = rodar_com_mock('{"indice": 0}', "NÃO")
print(f"nivel={nivel}, resultados vazio={resultados.empty}")
assert nivel == "vazio", "verificacao NAO deveria barrar o resultado"
print("OK: verificacao isolada barrou o candidato\n")

print("=== Caso 3: escolha retorna null -> nem chega na verificacao ===")
resultados, nivel = rodar_com_mock('{"indice": null}', "SIM")
print(f"nivel={nivel}, resultados vazio={resultados.empty}")
assert nivel == "vazio"
print("OK\n")

print("=== Caso 4: escolha com indice fora do range -> rejeitado ===")
resultados, nivel = rodar_com_mock('{"indice": 999}', "SIM")
print(f"nivel={nivel}, resultados vazio={resultados.empty}")
assert nivel == "vazio"
print("OK\n")

print("=== Caso 5: escolha com JSON malformado -> degradacao graciosa ===")
resultados, nivel = rodar_com_mock('nao sei dizer', "SIM")
print(f"nivel={nivel}, resultados vazio={resultados.empty}")
assert nivel == "vazio"
print("OK\n")

print("=== Caso 6: escolha com cercas de codigo (markdown) -> parseado ok ===")
resultados, nivel = rodar_com_mock('```json\n{"indice": 0}\n```', "SIM")
print(f"nivel={nivel}")
assert nivel == "nivel4"
print("OK\n")

print("=== Caso 7: verificacao responde 'SIM, ...' (com texto extra) -> aceito ===")
resultados, nivel = rodar_com_mock('{"indice": 0}', "SIM, sao o mesmo exame")
print(f"nivel={nivel}")
assert nivel == "nivel4", "Deveria aceitar resposta que comeca com SIM"
print("OK\n")

print("=== Caso 8: verificacao responde 'NAO, ...' (com texto extra) -> rejeitado ===")
resultados, nivel = rodar_com_mock('{"indice": 0}', "NAO, sao procedimentos diferentes")
print(f"nivel={nivel}, resultados vazio={resultados.empty}")
assert nivel == "vazio", "Resposta que comeca com NAO deve barrar"
print("OK\n")

print("=== Caso 9: verificacao com 'sim' minusculo -> aceito ===")
resultados, nivel = rodar_com_mock('{"indice": 0}', "sim")
print(f"nivel={nivel}")
assert nivel == "nivel4", "Deveria normalizar maiusculas/minusculas"
print("OK\n")

print("=== Caso 10: termo sem candidatos -> nem chama LLM ===")
resultados, nivel = rodar_com_mock('{"indice": 0}', "SIM", termo="xyz999nadaaver")
print(f"nivel={nivel}")
assert nivel == "vazio"
print("OK\n")

print("Todos os testes do nivel 4 (2 etapas) passaram.")