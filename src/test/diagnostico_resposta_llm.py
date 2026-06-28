"""
Diagnóstico do nível 4: chama o LLM de verdade (Ollama) para um termo e
mostra a resposta CRUA (JSON completo, incluindo confianca), sem aplicar
o filtro de aceitação do sigtap_server.py. Usado para investigar se o
modelo está seguindo a instrução de confiança corretamente.

Uso:
    python diagnostico_resposta_llm.py "coagulograma"
    python diagnostico_resposta_llm.py "reanimacao cardiopulmonar"
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))

from rapidfuzz import fuzz
import sigtap_server as srv
from langchain_ollama import ChatOllama

SCORE_MINIMO_CANDIDATOS = 50
MAX_CANDIDATOS = 30


def diagnosticar(termo: str):
    tabela = srv._get_tabela()
    termo_norm = srv._normalizar(termo)

    scores = tabela["descricao_norm"].apply(
        lambda desc: fuzz.token_set_ratio(termo_norm, desc)
    )
    candidatos = tabela[scores >= SCORE_MINIMO_CANDIDATOS].copy()
    if candidatos.empty:
        print(f"Nenhum candidato para {termo!r} -- LLM nem seria chamado.")
        return

    candidatos["_score"] = scores[scores >= SCORE_MINIMO_CANDIDATOS]
    candidatos = candidatos.sort_values("_score", ascending=False).head(MAX_CANDIDATOS)
    candidatos = candidatos.reset_index(drop=True)

    lista_para_llm = "\n".join(
        f"{i}: {row['descricao']}" for i, row in candidatos.iterrows()
    )

    # Mesmo prompt usado em sigtap_server.py (copiado aqui para diagnostico)
    prompt = f"""Você é um especialista em faturamento hospitalar brasileiro (tabela SIGTAP).

Um termo clínico foi extraído de um prontuário: "{termo}"

Abaixo está uma lista de procedimentos SIGTAP candidatos (numerados), gerada
por similaridade de texto. ATENÇÃO: similaridade de texto não significa
correspondência clínica real. Duas palavras em comum não bastam -- o
procedimento escolhido precisa ser efetivamente o mesmo ato clínico descrito
no termo, não apenas um procedimento da mesma área ou que compartilha uma
palavra.

Exemplos do que é e não é uma correspondência válida:
- Termo "coagulograma" + candidato "PROVA DE RETRAÇÃO DO COÁGULO"
  -> VÁLIDO: ambos avaliam a coagulação sanguínea, é o mesmo exame clínico,
     mesmo o nome sendo bem diferente do termo buscado.
- Termo "reanimação cardiopulmonar" + candidato "PROVA DE FUNÇÃO PULMONAR SIMPLES"
  -> INVÁLIDO: um é um procedimento de emergência (massagem cardíaca e
     ventilação), o outro é um exame diagnóstico de rotina. Compartilhar a
     palavra "pulmonar" não os torna o mesmo procedimento.
- Termo "intubação orotraqueal" + candidato "PUNÇÃO DE TRAQUEIA C/ ASPIRAÇÃO"
  -> INVÁLIDO: são procedimentos diferentes na via aérea, não o mesmo ato.

Para cada candidato, pergunte-se: "um auditor de faturamento hospitalar
aceitaria este código para este termo clínico?" Se a resposta for não, ou se
você tiver qualquer dúvida razoável, a resposta correta é null.

Responda APENAS com um JSON no formato exato:
{{"indice": N ou null, "confianca": "alta" ou "baixa"}}

Regras OBRIGATÓRIAS:
- "confianca" deve ser "alta" SOMENTE se você tem certeza de que é o mesmo
  procedimento clínico, não apenas um procedimento parecido ou da mesma área.
- Se "confianca" for "baixa", "indice" DEVE ser null.
- Use "indice": null sempre que nenhum candidato for uma correspondência
  clínica real, mesmo que algum pareça "o menos ruim" da lista.
- NUNCA invente um índice fora da lista abaixo.
- NUNCA inclua texto fora do JSON.

Candidatos:
{lista_para_llm}
"""

    print(f"\n{'='*70}")
    print(f"TERMO: {termo!r}")
    print(f"{'='*70}")
    print(f"\nCandidatos enviados ao LLM ({len(candidatos)}):")
    print(lista_para_llm)

    llm = ChatOllama(model=srv.MODELO_LLM_FALLBACK, temperature=0)
    resposta = llm.invoke(prompt)

    print(f"\n--- RESPOSTA CRUA DO LLM ---")
    print(repr(resposta.content))
    print(f"-----------------------------\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python diagnostico_resposta_llm.py "termo a investigar"')
        sys.exit(1)
    diagnosticar(sys.argv[1])