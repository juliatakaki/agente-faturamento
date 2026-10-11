"""
Regra de data: um item que a IA marcou como realizado, mas cujas menções no
texto têm todas uma data anterior à da evolução, é histórico e não deve ser
faturado nesta evolução.

ORIGEM
Medida por src/analise/etapa8_datas.py na planilha de gabarito do HUB, com a
configuração escolhida só no grupo de treino (out/2026). No teste, sobre os
itens medidos (gasometria, ECG, hemodiálise, TC de crânio, RX de tórax), a
regra tirou 32 sugestões erradas e perdeu 2 certas. Funciona melhor nos exames
copiados do histórico (TC de crânio, ECG), e quase não muda a gasometria,
porque valores transcritos raramente vêm com data ao lado.

COMO FUNCIONA
1. Data da evolução: vem do sistema (campo data_evolucao do prontuário). Se não
   vier, usa a primeira data dd/mm(/aa) do cabeçalho do texto.
2. Para cada menção do termo no texto, procura a data mais próxima até
   JANELA_DEPOIS caracteres depois ou JANELA_ANTES caracteres antes, sem
   atravessar um '#' de seção.
3. A menção é antiga se essa data for anterior à da evolução.
4. O pipeline só aplica a regra a EXAME e PROCEDIMENTO (as categorias medidas).
   Em medicamento e material a data costuma ser de início de uso.
5. O item só é considerado histórico se TODAS as menções forem antigas. Menção
   sem data por perto conta como atual. Se o termo não for achado no texto,
   nada é decidido.

Os valores abaixo têm de ser os mesmos da etapa 8. Se mudar aqui, rode a etapa
8 de novo.

Este módulo não chama LLM nem MCP, para poder ser testado isoladamente.
"""

import re
import unicodedata
from datetime import date, timedelta

JANELA_DEPOIS = 40      # caracteres depois do termo
JANELA_ANTES = 80       # caracteres antes do termo
TOLERANCIA_DIAS = 0
CABECALHO_CHARS = 300

# Não pega frequências e frações como "12/12h", "ml/12h" ou "200ml/12h"
RX_DATA = re.compile(r"(?<![\d/a-z])(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?(?![\d/a-z])")

# A IA costuma devolver o termo por extenso ("eletrocardiograma") quando o
# texto usa a sigla ("ECG"). Para os itens medidos na etapa 8, o termo é
# procurado no texto por todas as formas abaixo.
SINONIMOS = [
    r"\b(gasometria|gaso|gasa)\b",
    r"\b(ecg|eletrocardiograma)\b",
    r"\b(hd|hemodialise|dialise)\b",
    r"\b(tc|tomografia)( computadorizada)? (de |do )?cranio\b",
    r"\b(rx|raio x|radiografia)( de| do)? torax\b",
]


def leve(texto) -> str:
    """Minúsculas, sem acento, sem tags [ANONIMIZACAO]. Mantém '/', '#' e pontuação."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"\[[^\]]*\]", " ", t)
    return re.sub(r"[ \t]+", " ", t)


def para_data(valor):
    """'2025-10-14 22:30:00', '2025-10-14' ou '14/10/2025' -> date. None se não der."""
    s = str(valor or "").strip()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    try:
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", s)
        if m:
            ano = int(m.group(3))
            return date(ano + 2000 if ano < 100 else ano, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    return None


def data_do_cabecalho(texto_leve: str):
    for m in RX_DATA.finditer(texto_leve[:CABECALHO_CHARS]):
        d, mes, a = int(m.group(1)), int(m.group(2)), m.group(3)
        if a is None:
            continue  # sem ano, não dá para fixar a data da nota
        ano = int(a) + 2000 if int(a) < 100 else int(a)
        try:
            return date(ano, mes, d)
        except ValueError:
            continue
    return None


def datas_no_texto(t: str, nota: date):
    """Lista (inicio, fim, date) das datas válidas no texto, com o ano inferido."""
    saida = []
    for m in RX_DATA.finditer(t):
        d, mes, a = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= d <= 31 and 1 <= mes <= 12):
            continue
        ano = (int(a) + 2000 if int(a) < 100 else int(a)) if a else nota.year
        try:
            dt = date(ano, mes, d)
        except ValueError:
            continue
        # sem ano escrito e "no futuro": é do ano anterior (ex. nota 05/01, data 28/12)
        if a is None and dt > nota + timedelta(days=1):
            try:
                dt = date(ano - 1, mes, d)
            except ValueError:
                continue
        saida.append((m.start(), m.end(), dt))
    return saida


def data_da_mencao(t, ini, fim, datas):
    """Data mais próxima da menção, dentro da janela e sem cruzar '#'. None se não houver."""
    melhor = None
    for di, df, dt in datas:
        if fim <= di <= fim + JANELA_DEPOIS and "#" not in t[fim:di]:
            dist = di - fim
        elif ini - JANELA_ANTES <= df <= ini and "#" not in t[df:ini]:
            dist = ini - df
        else:
            continue
        if melhor is None or dist < melhor[0]:
            melhor = (dist, dt)
    return melhor[1] if melhor else None


def _padroes(termo_leve: str) -> list[str]:
    """Regex usadas para achar o termo no texto: o próprio termo e, se ele for um
    dos itens medidos, todos os sinônimos do item."""
    padroes = [r"\b" + re.escape(termo_leve.strip()) + r"\b"]
    for rx in SINONIMOS:
        if re.search(rx, termo_leve):
            padroes.append(rx)
    return padroes


def data_anterior(texto: str, termo: str, data_evolucao=None):
    """
    Devolve a data (dd/mm/aaaa) que torna o item histórico, ou None.
    None quando: não há data da evolução, o termo não aparece no texto, ou
    alguma menção não tem data anterior.
    """
    t = leve(texto)
    nota = para_data(data_evolucao) if data_evolucao else None
    nota = nota or data_do_cabecalho(t)
    termo_leve = leve(termo).strip()
    if not nota or not termo_leve:
        return None

    mencoes = set()
    for rx in _padroes(termo_leve):
        mencoes.update((m.start(), m.end()) for m in re.finditer(rx, t))
    if not mencoes:
        return None

    datas = datas_no_texto(t, nota)
    limite = nota - timedelta(days=TOLERANCIA_DIAS)
    mais_recente = None
    for ini, fim in mencoes:
        dt = data_da_mencao(t, ini, fim, datas)
        if dt is None or dt >= limite:
            return None
        mais_recente = dt if mais_recente is None or dt > mais_recente else mais_recente
    return mais_recente.strftime("%d/%m/%Y")


if __name__ == "__main__":
    # Teste rápido: python src/agent/regras_datas.py
    exemplo = ("EVOLUÇÃO MÉDICA NOTURNA - UTI 14/10/25\n# Exames: ECG (16/09/25): ritmo "
               "sinusal. TC de crânio sem contraste em 07/10: sem alterações. 29/01 VDRL: NR "
               "/ Anti HIV: NR\n# Condutas: gasometria com K 2,5. HD 12/12h")
    for termo in ("eletrocardiograma", "tomografia de crânio", "Anti HIV", "gasometria",
                  "hemodiálise", "ressonância"):
        print(f"{termo:22s} -> {data_anterior(exemplo, termo) or 'atual / sem decisão'}")