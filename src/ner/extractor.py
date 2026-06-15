"""
Módulo de extração de entidades clínicas (NER).
Usa spaCy com EntityRuler baseado em padrões clínicos em português.
Categorias reconhecidas: PROCEDIMENTO, EXAME, MEDICAMENTO, MATERIAL.
"""

import spacy # bib de NLP. faz a tokenização do prontuário e reconhece as entidades clínicas com base em padrões pré-definidos.
from spacy.pipeline import EntityRuler


# ── Padrões de entidades clínicas ──────────────────────────────────────────

PADROES = [

    # PROCEDIMENTOS
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "intubacao"}, {"LOWER": "orotraqueal"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "intubação"}, {"LOWER": "orotraqueal"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "ventilacao"}, {"LOWER": "mecanica"}, {"LOWER": "invasiva"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "ventilação"}, {"LOWER": "mecânica"}, {"LOWER": "invasiva"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "ventilacao"}, {"LOWER": "nao"}, {"LOWER": "invasiva"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "ventilação"}, {"LOWER": "não"}, {"LOWER": "invasiva"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "sedoanalgesia"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "reanimacao"}, {"LOWER": "cardiopulmonar"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "reanimação"}, {"LOWER": "cardiopulmonar"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "laparotomia"}, {"LOWER": "exploradora"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "drenagem"}, {"LOWER": "de"}, {"LOWER": "abscesso"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "hemodialise"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "hemodiálise"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "enxertia"}, {"LOWER": "de"}, {"LOWER": "pele"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "curativo"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "fisioterapia"}, {"LOWER": "respiratoria"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "fisioterapia"}, {"LOWER": "respiratória"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "fisioterapia"}, {"LOWER": "motora"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "fisioterapia"}, {"LOWER": "neurologica"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "fisioterapia"}, {"LOWER": "neurológica"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "hemotransfusao"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "hemotransfusão"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "nutricao"}, {"LOWER": "parenteral"}, {"LOWER": "total"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "nutrição"}, {"LOWER": "parenteral"}, {"LOWER": "total"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "nebulizacao"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "nebulização"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "reposicao"}, {"LOWER": "volêmica"}]},
    {"label": "PROCEDIMENTO", "pattern": [{"LOWER": "reposição"}, {"LOWER": "volêmica"}]},

    # EXAMES
    {"label": "EXAME", "pattern": [{"LOWER": "hemograma"}, {"LOWER": "completo"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "hemocultura"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "gasometria"}, {"LOWER": "arterial"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "gasometria"}, {"LOWER": "venosa"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "raio-x"}, {"LOWER": "de"}, {"LOWER": "torax"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "raio-x"}, {"LOWER": "de"}, {"LOWER": "tórax"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "raio"}, {"LOWER": "x"}, {"LOWER": "de"}, {"LOWER": "tórax"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "raio"}, {"LOWER": "x"}, {"LOWER": "de"}, {"LOWER": "torax"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "eletrocardiograma"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "troponina"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "ck-mb"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "ecocardiograma"}, {"LOWER": "a"}, {"LOWER": "beira"}, {"LOWER": "leito"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "ecocardiograma"}, {"LOWER": "à"}, {"LOWER": "beira"}, {"LOWER": "leito"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "ecocardiograma"}, {"LOWER": "transesofagico"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "ecocardiograma"}, {"LOWER": "transesofágico"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "tomografia"}, {"LOWER": "computadorizada"}, {"LOWER": "de"}, {"LOWER": "cranio"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "tomografia"}, {"LOWER": "computadorizada"}, {"LOWER": "de"}, {"LOWER": "crânio"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "tomografia"}, {"LOWER": "computadorizada"}, {"LOWER": "de"}, {"LOWER": "torax"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "tomografia"}, {"LOWER": "computadorizada"}, {"LOWER": "de"}, {"LOWER": "tórax"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "tomografia"}, {"LOWER": "de"}, {"LOWER": "tórax"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "tomografia"}, {"LOWER": "de"}, {"LOWER": "cranio"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "tomografia"}, {"LOWER": "de"}, {"LOWER": "crânio"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "angiotomografia"}, {"LOWER": "de"}, {"LOWER": "vasos"}, {"LOWER": "cerebrais"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "lactato"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "pcr"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "proteina"}, {"LOWER": "c"}, {"LOWER": "reativa"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "proteína"}, {"LOWER": "c"}, {"LOWER": "reativa"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "procalcitonina"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "ultrassom"}, {"LOWER": "abdominal"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "ultrassom"}, {"LOWER": "renal"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "liquido"}, {"LOWER": "cefalorraquidiano"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "líquido"}, {"LOWER": "cefalorraquidiano"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "eletroencefalograma"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "ureia"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "uréia"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "creatinina"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "albumina"}, {"LOWER": "serica"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "albumina"}, {"LOWER": "sérica"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "cultura"}, {"LOWER": "de"}, {"LOWER": "ferida"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "doppler"}, {"LOWER": "transcraniano"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "glicemia"}, {"LOWER": "capilar"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "cetonemia"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "coagulograma"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "perfil"}, {"LOWER": "lipidico"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "perfil"}, {"LOWER": "lipídico"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "painel"}, {"LOWER": "viral"}, {"LOWER": "respiratorio"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "painel"}, {"LOWER": "viral"}, {"LOWER": "respiratório"}]},
    {"label": "EXAME", "pattern": [{"LOWER": "swab"}, {"LOWER": "de"}, {"LOWER": "queimadura"}]},

    # MEDICAMENTOS
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "midazolam"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "fentanil"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "piperacilina"}, {"LOWER": "tazobactam"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "piperacilina-tazobactam"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "adrenalina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "noradrenalina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "vancomicina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "meropenem"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "meropenen"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "manitol"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "dexametasona"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "morfina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "sulfadiazina"}, {"LOWER": "de"}, {"LOWER": "prata"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "alteplase"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "insulina"}, {"LOWER": "regular"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "cloreto"}, {"LOWER": "de"}, {"LOWER": "potassio"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "cloreto"}, {"LOWER": "de"}, {"LOWER": "potássio"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "bicarbonato"}, {"LOWER": "de"}, {"LOWER": "sodio"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "bicarbonato"}, {"LOWER": "de"}, {"LOWER": "sódio"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "solucao"}, {"LOWER": "salina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "solução"}, {"LOWER": "salina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "protamina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "heparina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "oseltamivir"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "azitromicina"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "metilprednisolona"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "albumina"}, {"LOWER": "humana"}]},
    {"label": "MEDICAMENTO", "pattern": [{"LOWER": "broncodilatador"}]},

    # MATERIAIS / DISPOSITIVOS
    {"label": "MATERIAL", "pattern": [{"LOWER": "cateter"}, {"LOWER": "venoso"}, {"LOWER": "central"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "cateter"}, {"LOWER": "arterial"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "cateter"}, {"LOWER": "de"}, {"LOWER": "duplo"}, {"LOWER": "lumen"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "cateter"}, {"LOWER": "de"}, {"LOWER": "duplo"}, {"LOWER": "lúmen"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "cateter"}, {"LOWER": "de"}, {"LOWER": "swan-ganz"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "sonda"}, {"LOWER": "vesical"}, {"LOWER": "de"}, {"LOWER": "demora"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "sondagem"}, {"LOWER": "vesical"}, {"LOWER": "de"}, {"LOWER": "demora"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "sonda"}, {"LOWER": "nasoenteral"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "dreno"}, {"LOWER": "abdominal"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "drenos"}, {"LOWER": "mediastinais"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "monitor"}, {"LOWER": "cardiaco"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "monitor"}, {"LOWER": "cardíaco"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "cateter"}, {"LOWER": "nasal"}, {"LOWER": "de"}, {"LOWER": "oxigenio"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "cateter"}, {"LOWER": "nasal"}, {"LOWER": "de"}, {"LOWER": "oxigênio"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "mascara"}, {"LOWER": "facial"}, {"LOWER": "total"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "máscara"}, {"LOWER": "facial"}, {"LOWER": "total"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "bomba"}, {"LOWER": "de"}, {"LOWER": "infusao"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "bomba"}, {"LOWER": "de"}, {"LOWER": "infusão"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "concentrado"}, {"LOWER": "de"}, {"LOWER": "hemacias"}]},
    {"label": "MATERIAL", "pattern": [{"LOWER": "concentrado"}, {"LOWER": "de"}, {"LOWER": "hemácias"}]},
]


def construir_ner() -> spacy.Language:
    """Constrói e retorna o pipeline spaCy com EntityRuler configurado."""
    nlp = spacy.blank("pt") # cria um modelo spaCy vazio em português
    ruler = nlp.add_pipe(
        "entity_ruler", 
        config={"overwrite_ents": True}
    ) 
    ruler.add_patterns(PADROES)
    return nlp

def extrair_entidades(texto: str, nlp: spacy.Language) -> list[dict]:
    """
    Extrai entidades clínicas de um texto de prontuário.

    Args:
        texto: Texto livre do prontuário.
        nlp:   Pipeline spaCy já configurado.

    Returns:
        Lista de dicionários com 'texto' e 'categoria' de cada entidade.
    """
    doc = nlp(texto)
    entidades = []
    vistos = set()

    for ent in doc.ents:
        chave = (ent.text.lower(), ent.label_)
        if chave not in vistos:
            vistos.add(chave)
            entidades.append({
                "texto": ent.text,
                "categoria": ent.label_
            })

    return entidades

# ── Execução standalone para teste rápido ─────────────────────────────────

if __name__ == "__main__":
    import json

    nlp = construir_ner()

    with open("../../data/prontuarios.json", encoding="utf-8") as f:
        prontuarios = json.load(f)

    for p in prontuarios[:3]:
        print(f"\n{'='*60}")
        print(f"Prontuário: {p['id']}")
        print(f"{'='*60}")
        entidades = extrair_entidades(p["texto"], nlp)
        for e in entidades:
            print(f"  [{e['categoria']}] {e['texto']}")