"""
Regras de texto (regex + scoring) para códigos SIGTAP com pista textual forte.

ORIGEM DAS REGRAS
-----------------
As pistas vêm da mineração de termos distintivos sobre a planilha de gabarito
do HUB (data/data-completo.xlsx, 420 evoluções de 150 pacientes, 5 anotadores),
documentada em reports/analise-gabarito/. Os limiares e o modo de cada código
foram decididos SÓ no grupo de treino (105 pacientes, semente 42) e conferidos
no grupo de teste (45 pacientes) por src/analise/etapa3_regras_regex.py.

COMO FUNCIONA
-------------
Cada código tem uma lista de pistas (regex com peso). O score de um texto é a
soma dos pesos das pistas que aparecem nele; peso negativo é pista contra o
código. O código dispara quando o score atinge o limiar.

MODO DE CADA CÓDIGO
-------------------
Critério fixado antes de olhar o teste: precisão no treino >= PRECISAO_MINIMA_DIRETA.
  - "direta":    o código entra na lista de faturamento sugerida.
  - "candidato": o regex só levanta a suspeita. O código precisa ser confirmado
                 por outra fonte (no pipeline, o extrator ter encontrado o item
                 como REALIZADO); sem confirmação, vai para revisão do faturista.

Precisão e recall medidos (etapa 3, semente 42):
  código           treino prec  teste prec  teste rec   modo
  03.02.04.002-1      0,80        0,81        0,95     direta
  04.01.01.001-5      0,71        0,75        0,87     direta
  03.02.05.002-7      0,69        0,88        0,96     direta
  02.11.08.002-0      0,54        0,42        0,61     candidato   (limiar 6, out/2026)
  03.01.10.007-1      0,38        0,17        0,71     candidato
  03.05.01.013-1      0,30        0,32        0,69     candidato
  03.09.01.004-7      0,37        0,37        0,86     candidato   (limiar 1, out/2026)

Cateterismo vesical, passagem de SNE e glicemia capilar também foram testados
(out/2026) e ficaram de fora. No treino não há termo que separe as evoluções com
esses códigos das sem eles, e no teste os casos de cateterismo e de passagem de SNE
vêm todos de um único anotador. A marcação parece seguir o hábito do anotador
(ex. paciente com SVD ou com dieta enteral), não algo escrito na evolução.

O eletrocardiograma também foi testado (precisão 0,19 no treino e no teste, 13
de 16 alertas falsos no teste) e ficou de fora, porque só poluiria a lista de
revisão do faturista. O ECG de admissão fica copiado no histórico das evoluções.

Nos candidatos, os falsos positivos disparam as mesmas pistas dos acertos: a
palavra está no texto (valor de gaso transcrito, "HD" no histórico, TQT já
instalada), mas o procedimento não foi feito naquela evolução.

PISTAS DE PROXIMIDADE (out/2026)
A etapa 6 (src/analise/etapa6_contexto_erros.py, só no treino) mostrou que o que
separa acerto de erro nos candidatos é a parte da nota em que o termo aparece.
Ex.: gasometria perto de FiO2/SatO2 costuma ser acerto, e perto de "exame físico",
"FC" ou "bpm" (sinais vitais) costuma ser erro. Essas pistas usam perto(a, b), que
dispara quando os dois termos estão a até JANELA_PALAVRAS palavras um do outro.
Com elas, a etapa 3 derivou novos limiares no treino: gasometria 6 e nutrição
enteral 1 (basta "SNE"). No teste, gasometria foi de F1 0,49 para 0,50 (precisão
0,35 para 0,42) e nutrição enteral de F1 0,40 para 0,51 (recall 0,43 para 0,86).
Também foram testadas pistas de proximidade para hemodiálise ("HD" perto de
"prescrevo"/"conduta", contra "choque séptico") e TQT ("TQT" perto de "PEEP"/"modo",
contra "CDL"). Não melhoraram o teste e ficaram de fora.

Este módulo não chama LLM nem MCP, para poder ser testado isoladamente.
"""

import re
import unicodedata

PRECISAO_MINIMA_DIRETA = 0.60

MODO_DIRETA = "direta"
MODO_CANDIDATO = "candidato"

# Distância máxima, em palavras, para as pistas de proximidade
JANELA_PALAVRAS = 12


def perto(a: str, b: str, n: int = JANELA_PALAVRAS) -> str:
    """Regex que dispara quando o termo a e o termo b estão a até n palavras um do
    outro, em qualquer ordem. a e b são alternativas de regex, ex. 'hd|hemodialise'."""
    ra, rb = rf"\b(?:{a})\b", rf"\b(?:{b})\b"
    meio = rf"(?:\s+\S+){{0,{n}}}?\s+"
    return rf"{ra}{meio}{rb}|{rb}{meio}{ra}"


# Termos principais usados nas pistas de proximidade
_GASO = r"gasometria|gas[ao]|ph|pao2|po2|paco2|pco2"
_SNE = r"sne|gtt|enteral|dieta"

# Códigos verdes sem pista no texto (etapa 7, out/2026): o procedimento quase
# nunca está descrito na evolução e a marcação depende do anotador. O pipeline
# tira esses códigos das sugestões quando as regras de texto estão ligadas.
CODIGOS_SEM_PISTA_NO_TEXTO = (
    "03.01.10.005-5",  # cateterismo vesical de demora
    "03.09.01.010-1",  # passagem de sonda nasoentérica
    "02.14.01.001-5",  # glicemia capilar
)

# Cada pista: (nome legível, regex sobre o texto normalizado, peso)
REGRAS = {
    "04.01.01.001-5": {
        "nome": "CURATIVO GRAU II C/ OU S/ DEBRIDAMENTO",
        "rotulo": "CURATIVO GRAU II",
        "modo": MODO_DIRETA,
        "limiar": 2,
        "pistas": [
            ("realizo/realizado curativo", r"\brealiz\w*\s+(a\s+)?(troca\s+de\s+)?curativo", 3),
            ("bloco curativos",            r"\bcurativos\b", 2),
            ("curativo",                   r"\bcurativo\b", 1),
            ("limpeza com sf",             r"\blimpeza\s+com\s+sf", 1),
            ("clorexidina",                r"\bclorexidina\b", 1),
            ("ocluo/oclusao",              r"\b(ocluo|ocluido|oclusao)\b", 1),
            ("cobertura especial",         r"\b(alginato|hidrogel|hidrocoloide|espuma|alevyn|aguacel)\b", 1),
            ("so mantenho curativo",       r"\bmantenho\s+curativo", -1),
        ],
    },
    "03.02.04.002-1": {
        "nome": "ATENDIMENTO FISIOTERAPEUTICO EM PACIENTE COM TRANSTORNO RESPIRATORIO",
        "rotulo": "FISIOTERAPIA RESPIRATORIA",
        "modo": MODO_DIRETA,
        "limiar": 2,
        "pistas": [
            ("secao fisio respiratoria",   r"\bfisioterapia\s+respiratoria\s*:", 3),
            ("cabecalho fisioterapia",     r"\bevolucao\s+(de\s+|da\s+)?fisioterapia", 2),
            ("monitorizacao ventilatoria", r"\bmonitorizacao\s+ventilatoria\b", 1),
            ("aparelho locomotor",         r"\baparelho\s+locomotor\b", 1),
        ],
    },
    "03.02.05.002-7": {
        "nome": "ATENDIMENTO FISIOTERAPEUTICO NAS ALTERACOES MOTORAS",
        "rotulo": "FISIOTERAPIA MOTORA",
        "modo": MODO_DIRETA,
        "limiar": 2,
        "pistas": [
            ("secao fisio motora",         r"\bfisioterapia\s+motora\s*:", 3),
            ("cabecalho fisioterapia",     r"\bevolucao\s+(de\s+|da\s+)?fisioterapia", 2),
            ("aparelho locomotor",         r"\baparelho\s+locomotor\b", 1),
            ("cinesioterapia/sedestacao",  r"\b(cinesioterapia|sedestacao|ortostatismo|mobilizacao)\b", 1),
        ],
    },
    "02.11.08.002-0": {
        "nome": "GASOMETRIA",
        "rotulo": "GASOMETRIA",
        "modo": MODO_CANDIDATO,
        "limiar": 6,
        "pistas": [
            ("realizado/coletado gasometria", r"\b(realiz|colet)\w*\s+(a\s+)?gasometria", 3),
            ("gasometria",                    r"\bgasometria\b", 1),
            ("gasa/gaso",                     r"\bgas[ao]\b", 1),
            ("ph",                            r"\bph\b", 1),
            ("pao2/po2",                      r"\b(pao2|po2)\b", 1),
            ("paco2/pco2",                    r"\b(paco2|pco2)\b", 1),
            ("hco3/bic/be",                   r"\b(hco3|bic|be)\b", 1),
            # proximidade (etapa 6)
            ("gaso perto de fio2/sato2",      perto(_GASO, r"fio2|sato2|sao2"), 1),
            ("gaso no exame fisico",          perto(_GASO, r"exame fisico|fc|bpm"), -1),
        ],
        # Termos que, extraídos como REALIZADO, confirmam o candidato.
        "confirmacao": ("gasometria", "gaso", "gasa"),
    },
    "03.05.01.013-1": {
        "nome": "HEMODIALISE P/ PACIENTES RENAIS AGUDOS / CRONICOS AGUDIZADOS",
        "rotulo": "HEMODIALISE",
        "modo": MODO_CANDIDATO,
        "limiar": 4,
        "pistas": [
            ("hd",                  r"\bhd\b", 2),
            ("hemodialise/dialise", r"\b(hemo)?dialise\b", 2),
            ("uf",                  r"\buf\b", 2),
            ("trs",                 r"\btrs\b", 1),
            ("nefrologia",          r"\bnefro(logia)?\b", 1),
            ("cdl",                 r"\bcdl\b", 1),
        ],
        "confirmacao": ("hemodialise", "dialise", "hd", "terapia renal substitutiva"),
    },
    "03.01.10.007-1": {
        "nome": "CUIDADOS C/ TRAQUEOSTOMIA",
        "rotulo": "CUIDADOS C/ TRAQUEOSTOMIA",
        "modo": MODO_CANDIDATO,
        "limiar": 3,
        "pistas": [
            ("tqt",              r"\btqt\b", 2),
            ("traqueostomia",    r"\btraqueostomi\w*", 2),
            ("cuff",             r"\bcuff\b", 1),
            ("acoplado/via tqt", r"\b(via|em|sob|por|acoplad\w*\s+a)\s+tqt\b", 1),
            ("programar tqt",    r"\b(programar|programo|indicacao\s+de|aguarda\w*)\s+tqt\b", -2),
        ],
        "confirmacao": ("traqueostomia", "tqt"),
    },
    # Acrescentado em out/2026. Pistas escolhidas pela mineração SÓ no grupo de
    # treino (etapa 3). Limiar e modo definidos depois, pela etapa 3, no treino.
    "03.09.01.004-7": {
        "nome": "NUTRICAO ENTERAL EM ADULTO",
        "rotulo": "NUTRICAO ENTERAL",
        "modo": MODO_CANDIDATO,
        "limiar": 1,
        "pistas": [
            ("dieta por/via SNE ou GTT", r"\bdieta\s+(enteral\s+)?(por|via|em|pela)\s+(sne|gtt|sng|cne)\b", 3),
            ("dieta enteral",            r"\bdieta\s+enteral\b", 2),
            ("TNE/terapia nutricional",  r"\btne\b|\bterapia\s+nutricional\b", 2),
            ("gtt",                      r"\bgtt\b", 1),
            ("sne",                      r"\bsne\b", 1),
            ("dieta zero",               r"\bdieta\s+zero\b", -1),
            ("sne fechada",              r"\bsne\s+fechada\b", -1),
            # proximidade (etapa 6)
            ("sne perto de termo de nutricao", perto(_SNE, r"calorica|kcal|nasoenterica|gastrostomia"), 1),
        ],
        "confirmacao": ("nutricao enteral", "dieta enteral", "tne", "terapia nutricional enteral"),
    },
}


def normalizar(texto) -> str:
    """Minúsculas, sem acentos, sem tags [ANONIMIZACAO], espaços colapsados. Mantém ':'."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = t.replace("²", "2")
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"[^a-z0-9:]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def so_digitos(codigo: str) -> str:
    """'04.01.01.001-5' -> '0401010015' (formato da coluna codigos_sigtap)."""
    return re.sub(r"\D", "", codigo)


def pontuar(texto_normalizado: str, pistas) -> tuple[int, list[str]]:
    """Devolve (score, nomes das pistas que dispararam) para um texto já normalizado."""
    score, disparadas = 0, []
    for nome, rx, peso in pistas:
        if re.search(rx, texto_normalizado):
            score += peso
            disparadas.append(nome)
    return score, disparadas


def aplicar_regras_texto(texto: str) -> list[dict]:
    """
    Aplica todas as regras a um texto de evolução e devolve os códigos que
    dispararam, cada um como dict:
      codigo, nome, modo ('direta' | 'candidato'), score, limiar, pistas
    """
    t = normalizar(texto)
    disparos = []
    for codigo, regra in REGRAS.items():
        score, pistas = pontuar(t, regra["pistas"])
        if score >= regra["limiar"]:
            disparos.append({
                "codigo": codigo,
                "nome": regra["nome"],
                "modo": regra["modo"],
                "score": score,
                "limiar": regra["limiar"],
                "pistas": pistas,
            })
    return disparos


if __name__ == "__main__":
    # Teste rápido: python src/agent/regras_texto.py
    exemplo = ("EVOLUÇÃO DE ENFERMAGEM. Realizo curativo em CVC. Limpeza com SF 0,9% "
               "e antissepsia com clorexidina alcoólica. Ocluo com gaze e filme. "
               "Em VM por TQT. Realizado gasometria arterial.")
    for d in aplicar_regras_texto(exemplo):
        print(f"{d['codigo']}  {d['modo']:9s}  score {d['score']} (limiar {d['limiar']})  "
              f"{d['nome']}  <- {', '.join(d['pistas'])}")