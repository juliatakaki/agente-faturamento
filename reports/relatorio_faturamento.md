# Relatório de Faturamento SUS - SIGTAP

**Data de geração:** 06/10/2026 às 11:15  
**Total de prontuários processados:** 10  
**Modelo utilizado:** api/groq - openai/gpt-oss-120b  
**Consulta ao SIGTAP:** laço determinístico  
**Regras:** regras de documento ligadas; regras de texto ligadas

> **Relatório de apoio ao faturamento.** As correspondências são sugestões da busca automática e devem ser verificadas antes do envio, com prioridade para as de confiança **BAIXA**. O dicionário de termos usado pelo sistema ainda não foi validado pelo setor de faturamento.

---

## Prontuário: HUB001

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 03.09.05.026-0 | TRATAMENTO DE FERIDAS COM FITOTERÁPICO | curativo de ferida | Semântica | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.01.01.004-8 | CONSULTA DE PROFISSIONAIS DE NIVEL SUPERIOR NA ATENÇÃO ESPECIALIZADA (EXCETO MÉDICO) | [regra: nao_medico] | Regra de documento | Alta | R$ 0,00 | R$ 6,30 | R$ 0,00 | R$ 6,30 |
| 04.01.01.001-5 | CURATIVO GRAU II C/ OU S/ DEBRIDAMENTO | [regra de texto: realizo/realizado curativo, bloco curativos, curativo, limpeza com sf, clorexidina, ocluo/oclusao, so mantenho curativo] | Regra de texto | Média | R$ 32,40 | R$ 32,40 | R$ 0,00 | R$ 64,80 |

**Subtotal do prontuário HUB001: R$ 101,10**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)
- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - tubo orotraqueal
> - sonda vesical
> - solução fisiológica 0,9%
> - clorexidina alcoólica
> - gaze
> - filme transparente

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - sonda nasoenteral

---

## Prontuário: HUB002

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.08.017-8 | ATENDIMENTO INDIVIDUAL EM PSICOTERAPIA | atendimento psicológico | Semântica | **BAIXA** | R$ 0,00 | R$ 2,55 | R$ 0,00 | R$ 2,55 |
| 03.01.10.014-4 | OXIGENOTERAPIA POR DIA | oxigenoterapia | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 04.06.02.030-2 | PLASTIA ARTERIAL COM REMENDO (QUALQUER TÉCNICA) | cateterismo arterial | Semântica | **BAIXA** | R$ 1.082,35 | R$ 0,00 | R$ 375,26 | R$ 1.457,61 |
| 04.06.03.001-4 | ANGIOPLASTIA CORONARIANA | angioplastia coronária | Semântica | Média | R$ 988,48 | R$ 1.081,48 | R$ 587,24 | R$ 2.657,20 |
| 03.01.01.004-8 | CONSULTA DE PROFISSIONAIS DE NIVEL SUPERIOR NA ATENÇÃO ESPECIALIZADA (EXCETO MÉDICO) | [regra: nao_medico] | Regra de documento | Alta | R$ 0,00 | R$ 6,30 | R$ 0,00 | R$ 6,30 |

**Subtotal do prontuário HUB002: R$ 4.123,66**

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - dobutamina

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - cateter nasal de oxigênio

> **Classificados pelo sistema como não realizados nesta evolução**  
> O sistema classificou estes itens como mencionados mas não realizados nesta evolução (solicitados, programados, cancelados, suspensos ou anteriores a ela). Eles não foram buscados e não entram no valor. A classificação é automática e pode errar - conferir, principalmente exames e procedimentos de valor alto.
>
> - TAVI (procedimento)

---

## Prontuário: HUB003

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 06.04.05.007-0 | MORFINA 10 MG (POR COMPRIMIDO) | morfina | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 07.01.07.007-2 | PLACA OCLUSAL | placa de alevyn | Semântica | Média | R$ 0,00 | R$ 23,54 | R$ 0,00 | R$ 23,54 |
| 07.01.04.001-7 | BENGALA ARTICULADA | compressa | Semântica | **BAIXA** | R$ 0,00 | R$ 91,91 | R$ 0,00 | R$ 91,91 |
| 04.03.01.034-9 | TREPANACAO CRANIANA PARA PROPEDEUTICA NEUROCIRURGICA / IMPLANTE PARA MONITORIZACAO PIC | monitorização | Similaridade | Média | R$ 494,83 | R$ 0,00 | R$ 107,52 | R$ 602,35 |
| 03.01.01.004-8 | CONSULTA DE PROFISSIONAIS DE NIVEL SUPERIOR NA ATENÇÃO ESPECIALIZADA (EXCETO MÉDICO) | [regra: nao_medico] | Regra de documento | Alta | R$ 0,00 | R$ 6,30 | R$ 0,00 | R$ 6,30 |
| 04.01.01.001-5 | CURATIVO GRAU II C/ OU S/ DEBRIDAMENTO | [regra de texto: realizo/realizado curativo, bloco curativos, curativo, limpeza com sf, clorexidina, ocluo/oclusao, cobertura especial] | Regra de texto | Média | R$ 32,40 | R$ 32,40 | R$ 0,00 | R$ 64,80 |

**Subtotal do prontuário HUB003: R$ 788,90**

_Outras hipóteses para conferência:_

- **morfina** → 2ª: MORFINA 30 MG (POR COMPRIMIDO) (06.04.05.008-9, R$ 0,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - solução fisiológica 0,9%
> - clorexidina alcoólica
> - gaze
> - filme transparente
> - alginato
> - vigilância hemodinâmica

---

## Prontuário: HUB004

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 03.01.10.005-5 | CATETERISMO VESICAL DE DEMORA | cateterismo vesical | Exata | Média | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.02.08.015-3 | HEMOCULTURA | hemocultura | Exata | Alta | R$ 0,00 | R$ 11,49 | R$ 0,00 | R$ 11,49 |
| 02.02.02.038-0 | HEMOGRAMA COMPLETO | hemograma completo | Exata | Alta | R$ 0,00 | R$ 4,11 | R$ 0,00 | R$ 4,11 |
| 02.11.08.002-0 | GASOMETRIA | gasometria | Exata | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |
| 02.13.01.077-1 | TESTE MOLECULAR PARA A DETECÇÃO DE HIV-2 | teste de HIV | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.02.03.078-4 | PESQUISA DE ANTICORPOS IGG E IGM CONTRA ANTIGENO CENTRAL DO VIRUS DA HEPATITE B (ANTI-HBC-TOTAL) | anti-HBc total | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.063-6 | PESQUISA DE ANTICORPOS CONTRA ANTIGENO DE SUPERFICIE DO VIRUS DA HEPATITE B (ANTI-HBS) | anti-HBs | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.144-6 | PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) PARA POPULAÇÃO GERAL (EXCETO GESTANTE, PARCEIRO OU PARCERIA) | HBsAg | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.147-0 | PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) PARA POPULAÇÃO GERAL (EXCETO GESTANTE, PARCEIRO OU PARCERIA) | anti-HCV | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.077-6 | PESQUISA DE ANTICORPOS IGG ANTITRYPANOSOMA CRUZI | sorologia de Chagas | Agente | **BAIXA** | R$ 0,00 | R$ 9,25 | R$ 0,00 | R$ 9,25 |
| 02.14.01.027-9 | TESTE RÁPIDO PARA DETECÇÃO DE ANTICORPOS ANTI-HIV EM GESTANTE | teste rápido de HIV | Exata | **BAIXA** | R$ 1,00 | R$ 1,00 | R$ 0,00 | R$ 2,00 |
| 02.14.01.014-7 | TESTE RÁPIDO DE DENGUE NS1 | teste NS1 | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.11.02.003-6 | ELETROCARDIOGRAMA | eletrocardiograma | Exata | Alta | R$ 0,00 | R$ 5,15 | R$ 0,00 | R$ 5,15 |
| 02.06.01.007-9 | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | tomografia computadorizada de crânio | Exata | Alta | R$ 97,44 | R$ 97,44 | R$ 0,00 | R$ 194,88 |
| 02.06.03.001-0 | TOMOGRAFIA COMPUTADORIZADA DE ABDOMEN SUPERIOR | tomografia computadorizada de abdome | Parcial | Alta | R$ 138,63 | R$ 138,63 | R$ 0,00 | R$ 277,26 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia computadorizada de tórax | Exata | Alta | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 06.04.05.007-0 | MORFINA 10 MG (POR COMPRIMIDO) | morfina | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 06.03.01.001-6 | METILPREDNISOLONA 500 MG INJENTAVEL (POR AMPOLA) | prednisolona | Similaridade | Média | R$ 20,96 | R$ 0,00 | R$ 0,00 | R$ 20,96 |
| 03.01.01.017-0 | CONSULTA/AVALIAÇÃO EM PACIENTE INTERNADO | [regra: medico] | Regra de documento | Alta | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 08.02.01.008-3 | DIARIA DE UNIDADE DE TERAPIA INTENSIVA ADULTO (UTI II) | [regra: medico] | Regra de documento | Alta | R$ 510,00 | R$ 0,00 | R$ 90,00 | R$ 600,00 |

**Subtotal do prontuário HUB004: R$ 1.722,27**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)
- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)
- **cateterismo vesical** → 2ª: CATETERISMO VESICAL DE ALIVIO (03.01.10.004-7, R$ 0,00)
- **HBsAg** → 2ª: PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) EM GESTANTE (02.02.03.145-4, R$ 18,55) · 3ª: PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) EM PARCEIRO OU PARCERIA DE GESTANTE (02.02.03.146-2, R$ 18,55)
- **anti-HCV** → 2ª: PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) EM GESTANTE (02.02.03.148-9, R$ 18,55) · 3ª: PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) EM PARCEIRO OU PARCERIA DE GESTANTE (02.02.03.149-7, R$ 18,55)
- **teste rápido de HIV** → 2ª: TESTE RÁPIDO PARA DETECÇÃO DE ANTICORPOS ANTI-HIV EM PARCEIRO OU PARCERIA DE GESTANTE (02.14.01.028-7, R$ 2,00)
- **eletrocardiograma** → 2ª: TELE-ELETROCARDIOGRAMA SÍNCRONO/LAUDO (02.11.02.009-5, R$ 0,00)
- **tomografia computadorizada de abdome** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE PELVE / BACIA / ABDOMEN INFERIOR (02.06.03.003-7, R$ 277,26) · 3ª: TOMOGRAFIA COMPUTADORIZADA DO CRANIO (02.06.01.007-9, R$ 194,88)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **morfina** → 2ª: MORFINA 30 MG (POR COMPRIMIDO) (06.04.05.008-9, R$ 0,00)
- **prednisolona** → 2ª: METILPREDNISOLONA 500MG INJETAVEL P/TRANSPLANTE(POR FRASCO AMPOLA) (06.03.08.012-0, R$ 20,96) · 3ª: METILPREDNISOLONA 500 MG INJETAVEL (POR AMPOLA) (06.04.28.010-6, R$ 0,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - urocultura
> - cultura de secreção traqueal
> - VDRL
> - painel viral
> - sonda vesical
> - tubo endotraqueal
> - amitriptilina
> - glicazida
> - metformina
> - atenolol
> - dipirona
> - dexmedetomidina
> - fentanil
> - gluconato de cálcio
> - ceftazidima
> - aztreonam
> - linezolida
> - micafungina
> - amicacina
> - torgena

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - intubação orotraqueal
> - sonda nasoenteral
> - noradrenalina
> - cloreto de potássio

> **Indício pelas regras de texto, sem confirmação - conferir**  
> As regras de texto encontraram indício destes procedimentos, mas o extrator não confirmou que foram realizados nesta evolução. Eles NÃO entram no valor sugerido. Conferir no texto se o procedimento foi feito neste dia ou se é apenas menção (dispositivo já instalado, histórico, valor transcrito).
>
> - HEMODIALISE P/ PACIENTES RENAIS AGUDOS / CRONICOS AGUDIZADOS (03.05.01.013-1) - pistas: hd, uf, trs, cdl
> - CUIDADOS C/ TRAQUEOSTOMIA (03.01.10.007-1) - pistas: tqt, acoplado/via tqt

---

## Prontuário: HUB005

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 04.09.03.003-1 | PROSTATOVESICULECTOMIA RADICAL | cistoprostatectomia radical | Agente | **BAIXA** | R$ 575,24 | R$ 0,00 | R$ 513,16 | R$ 1.088,40 |
| 03.01.05.016-3 | ATENDIMENTO E ACOMPANHAMENTO DOMICILIAR DEPACIENTE SUBMETIDO À VENTILAÇÃO MECÂNICA INVASIVA DOMICILIAR | ventilação mecânica invasiva | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.03.14.013-5 | TRATAMENTO DE OUTRAS DOENCAS DO APARELHO RESPIRATORIO | fisioterapia respiratória | Semântica | **BAIXA** | R$ 451,47 | R$ 0,00 | R$ 29,40 | R$ 480,87 |
| 03.02.05.002-7 | ATENDIMENTO FISIOTERAPÊUTICO NAS ALTERAÇÕES MOTORAS | fisioterapia motora | Semântica | **BAIXA** | R$ 0,00 | R$ 4,67 | R$ 0,00 | R$ 4,67 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |
| 02.02.08.010-2 | CULTURA P/ HERPESVIRUS | cultura de urina | Parcial | **BAIXA** | R$ 0,00 | R$ 4,33 | R$ 0,00 | R$ 4,33 |
| 03.01.01.004-8 | CONSULTA DE PROFISSIONAIS DE NIVEL SUPERIOR NA ATENÇÃO ESPECIALIZADA (EXCETO MÉDICO) | [regra: nao_medico] | Regra de documento | Alta | R$ 0,00 | R$ 6,30 | R$ 0,00 | R$ 6,30 |
| 03.02.04.002-1 | ATENDIMENTO FISIOTERAPÊUTICO EM PACIENTE COM TRANSTORNO RESPIRATÓRIO SEM COMPLICAÇÕES SISTÊMICAS | [regra de texto: secao fisio respiratoria, monitorizacao ventilatoria, aparelho locomotor] | Regra de texto | Média | R$ 4,67 | R$ 4,67 | R$ 0,00 | R$ 9,34 |

**Subtotal do prontuário HUB005: R$ 1.596,69**

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - dreno hemovac
> - urostomia Bricker
> - amicacina
> - dipirona
> - midazolam
> - fentanil
> - filtro HME

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - noradrenalina

> **Classificados pelo sistema como não realizados nesta evolução**  
> O sistema classificou estes itens como mencionados mas não realizados nesta evolução (solicitados, programados, cancelados, suspensos ou anteriores a ela). Eles não foram buscados e não entram no valor. A classificação é automática e pode errar - conferir, principalmente exames e procedimentos de valor alto.
>
> - laparotomia exploradora (procedimento)
> - lavagem de cavidade (procedimento)
> - reimplante de ureteres (procedimento)

> **Indício pelas regras de texto, sem confirmação - conferir**  
> As regras de texto encontraram indício destes procedimentos, mas o extrator não confirmou que foram realizados nesta evolução. Eles NÃO entram no valor sugerido. Conferir no texto se o procedimento foi feito neste dia ou se é apenas menção (dispositivo já instalado, histórico, valor transcrito).
>
> - CUIDADOS C/ TRAQUEOSTOMIA (03.01.10.007-1) - pistas: tqt, cuff

---

## Prontuário: HUB006

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 04.17.01.006-0 | SEDACAO | sedação | Exata | Alta | R$ 0,00 | R$ 15,15 | R$ 15,15 | R$ 30,30 |
| 03.01.05.016-3 | ATENDIMENTO E ACOMPANHAMENTO DOMICILIAR DEPACIENTE SUBMETIDO À VENTILAÇÃO MECÂNICA INVASIVA DOMICILIAR | ventilação mecânica invasiva | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 03.06.02.006-8 | TRANSFUSAO DE CONCENTRADO DE HEMACIAS | transfusão de hemácias | Exata | Média | R$ 8,39 | R$ 8,09 | R$ 0,00 | R$ 16,48 |
| 03.06.02.007-6 | TRANSFUSAO DE CONCENTRADO DE PLAQUETAS | transfusão de plaquetas | Exata | Média | R$ 8,39 | R$ 8,09 | R$ 0,00 | R$ 16,48 |
| 04.12.01.006-2 | PUNCAO DE TRAQUEIA C/ ASPIRACAO | aspiração traqueal | Semântica | **BAIXA** | R$ 15,79 | R$ 15,79 | R$ 0,00 | R$ 31,58 |
| 02.02.08.015-3 | HEMOCULTURA | hemocultura | Exata | Alta | R$ 0,00 | R$ 11,49 | R$ 0,00 | R$ 11,49 |
| 02.05.01.003-2 | ECOCARDIOGRAFIA TRANSTORACICA | ecocardiograma | Semântica | **BAIXA** | R$ 67,86 | R$ 67,86 | R$ 0,00 | R$ 135,72 |
| 02.06.01.007-9 | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | tomografia computadorizada de corpo total | Parcial | **BAIXA** | R$ 97,44 | R$ 97,44 | R$ 0,00 | R$ 194,88 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia computadorizada de tórax | Exata | Alta | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.06.01.004-4 | TOMOGRAFIA COMPUTADORIZADA DE FACE / SEIOS DA FACE / ARTICULACOES TEMPORO-MANDIBULARES | tomografia computadorizada de seios da face | Exata | Média | R$ 86,75 | R$ 86,75 | R$ 0,00 | R$ 173,50 |
| 02.06.03.003-7 | TOMOGRAFIA COMPUTADORIZADA DE PELVE / BACIA / ABDOMEN INFERIOR | tomografia computadorizada de pelve | Exata | **BAIXA** | R$ 138,63 | R$ 138,63 | R$ 0,00 | R$ 277,26 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |
| 02.02.02.038-0 | HEMOGRAMA COMPLETO | hemograma completo | Exata | Alta | R$ 0,00 | R$ 4,11 | R$ 0,00 | R$ 4,11 |
| 02.02.09.019-1 | MIELOGRAMA | mielograma | Exata | Alta | R$ 0,00 | R$ 5,79 | R$ 0,00 | R$ 5,79 |
| 02.02.03.011-3 | DOSAGEM DE BETA-2-MICROGLOBULINA | beta-2-microglobulina | Exata | Alta | R$ 0,00 | R$ 13,55 | R$ 0,00 | R$ 13,55 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 07.02.05.005-9 | CATETER BALAO P/ EMBOLECTOMIA ARTERIAL / VENOSA | cateter arterial | Exata | **BAIXA** | R$ 96,20 | R$ 0,00 | R$ 0,00 | R$ 96,20 |
| 03.01.01.017-0 | CONSULTA/AVALIAÇÃO EM PACIENTE INTERNADO | [regra: medico] | Regra de documento | Alta | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 08.02.01.008-3 | DIARIA DE UNIDADE DE TERAPIA INTENSIVA ADULTO (UTI II) | [regra: medico] | Regra de documento | Alta | R$ 510,00 | R$ 0,00 | R$ 90,00 | R$ 600,00 |

**Subtotal do prontuário HUB006: R$ 2.130,31**

_Outras hipóteses para conferência:_

- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)
- **transfusão de plaquetas** → 2ª: TRANSFUSAO DE PLAQUETAS POR AFERESE (03.06.02.009-2, R$ 16,18)
- **tomografia computadorizada de corpo total** → 2ª: TOMOGRAFIA COMPUTADORIZADA DO PESCOCO (02.06.01.005-2, R$ 173,50) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE TORAX (02.06.02.003-1, R$ 272,82)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - losartana
> - furosemida
> - metoprolol
> - midazolam
> - fentanil
> - dexametasona
> - meropenem
> - micafungina
> - anfotericina B
> - anidulofungina
> - amicacina
> - piperacilina-tazobactam
> - angiotomografia
> - imunofixação sérica

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - vancomicina
> - intubação orotraqueal
> - sonda nasoenteral

> **Classificados pelo sistema como não realizados nesta evolução**  
> O sistema classificou estes itens como mencionados mas não realizados nesta evolução (solicitados, programados, cancelados, suspensos ou anteriores a ela). Eles não foram buscados e não entram no valor. A classificação é automática e pode errar - conferir, principalmente exames e procedimentos de valor alto.
>
> - alopurinol (medicamento)
> - ivermectina (medicamento)
> - aciclovir (medicamento)
> - bactrim (medicamento)
> - toracocentese diagnóstica (procedimento)
> - extubação (procedimento)
> - proteinúria de 24 horas (exame)
> - fundoscopia (exame)
> - baciloscopia (exame)
> - genexpert (exame)
> - IGRA (exame)
> - galactomanana (exame)

---

## Prontuário: HUB007

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 04.05.05.030-5 | SUTURA DE CORNEA | sutura | Exata | **BAIXA** | R$ 0,00 | R$ 164,08 | R$ 0,00 | R$ 164,08 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |
| 03.01.01.004-8 | CONSULTA DE PROFISSIONAIS DE NIVEL SUPERIOR NA ATENÇÃO ESPECIALIZADA (EXCETO MÉDICO) | [regra: nao_medico] | Regra de documento | Alta | R$ 0,00 | R$ 6,30 | R$ 0,00 | R$ 6,30 |
| 04.01.01.001-5 | CURATIVO GRAU II C/ OU S/ DEBRIDAMENTO | [regra de texto: realizo/realizado curativo, bloco curativos, curativo, limpeza com sf, clorexidina, ocluo/oclusao, so mantenho curativo] | Regra de texto | Média | R$ 32,40 | R$ 32,40 | R$ 0,00 | R$ 64,80 |

**Subtotal do prontuário HUB007: R$ 455,33**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **sutura** → 2ª: SUTURA DE ESCLERA (04.05.03.009-6, R$ 322,38) · 3ª: SUTURA DE CONJUNTIVA (04.05.05.029-1, R$ 82,28)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - vasopressina
> - fentanil
> - midazolam
> - solução salina 0,9%
> - clorexidina alcoólica
> - gaze
> - filme transparente
> - placa de hidropolímero
> - banho no leito

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - noradrenalina
> - monitorização cardíaca

---

## Prontuário: HUB008

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.01.004-8 | CONSULTA DE PROFISSIONAIS DE NIVEL SUPERIOR NA ATENÇÃO ESPECIALIZADA (EXCETO MÉDICO) | [regra: nao_medico] | Regra de documento | Alta | R$ 0,00 | R$ 6,30 | R$ 0,00 | R$ 6,30 |
| 04.01.01.001-5 | CURATIVO GRAU II C/ OU S/ DEBRIDAMENTO | [regra de texto: realizo/realizado curativo, bloco curativos, curativo, clorexidina, ocluo/oclusao] | Regra de texto | Média | R$ 32,40 | R$ 32,40 | R$ 0,00 | R$ 64,80 |

**Subtotal do prontuário HUB008: R$ 71,10**

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - expressão manual
> - solução fisiológica 0,9%
> - clorexidina alcoólica
> - compressa estéril
> - filme transparente

---

## Prontuário: HUB009

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 06.04.51.001-2 | RISPERIDONA 1 MG (POR COMPRIMIDO) | risperidona | Exata | Média | R$ 0,00 | R$ 0,10 | R$ 0,00 | R$ 0,10 |
| 06.04.41.001-8 | METADONA 5 MG (POR COMPRIMIDO) | metadona | Exata | Média | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 02.06.03.001-0 | TOMOGRAFIA COMPUTADORIZADA DE ABDOMEN SUPERIOR | tomografia computadorizada de abdômen com contraste | Parcial | Média | R$ 138,63 | R$ 138,63 | R$ 0,00 | R$ 277,26 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia computadorizada de tórax com contraste | Parcial | Média | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.06.01.007-9 | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | tomografia computadorizada de crânio com contraste | Parcial | Média | R$ 97,44 | R$ 97,44 | R$ 0,00 | R$ 194,88 |
| 02.06.01.009-5 | TOMOGRAFIA POR EMISSÃO DE PÓSITRONS (PET-CT) | PET-CT | Similaridade | Média | R$ 0,00 | R$ 2.107,22 | R$ 0,00 | R$ 2.107,22 |
| 02.02.08.010-2 | CULTURA P/ HERPESVIRUS | cultura de sangue | Parcial | **BAIXA** | R$ 0,00 | R$ 4,33 | R$ 0,00 | R$ 4,33 |
| 03.01.01.017-0 | CONSULTA/AVALIAÇÃO EM PACIENTE INTERNADO | [regra: medico] | Regra de documento | Alta | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 08.02.01.008-3 | DIARIA DE UNIDADE DE TERAPIA INTENSIVA ADULTO (UTI II) | [regra: medico] | Regra de documento | Alta | R$ 510,00 | R$ 0,00 | R$ 90,00 | R$ 600,00 |

**Subtotal do prontuário HUB009: R$ 3.703,98**

_Outras hipóteses para conferência:_

- **risperidona** → 2ª: RISPERIDONA 2 MG (POR COMPRIMIDO) (06.04.51.002-0, R$ 0,11) · 3ª: RISPERIDONA 3 MG (POR COMPRIMIDO) (06.04.51.003-9, R$ 0,17)
- **metadona** → 2ª: METADONA 10 MG (POR COMPRIMIDO) (06.04.41.002-6, R$ 0,00)
- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **tomografia computadorizada de abdômen com contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **tomografia computadorizada de tórax com contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **tomografia computadorizada de crânio com contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **cultura de sangue** → 2ª: PROCESSAMENTO DE SANGUE (02.12.02.006-4, R$ 10,15)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - unasyn
> - tigeciclina
> - polimixina B
> - meropenem
> - cefepime
> - piperacilina-tazobactam
> - lorazepam
> - potássio
> - magnésio
> - angiotomografia de tórax
> - cultura de swab

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - azitromicina
> - vancomicina

---

## Prontuário: HUB010

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 04.04.01.037-7 | TRAQUEOSTOMIA | traqueostomia de urgência | Parcial | **BAIXA** | R$ 394,07 | R$ 0,00 | R$ 160,66 | R$ 554,73 |
| 03.01.06.003-7 | ATENDIMENTO DE URGÊNCIA EM ATENÇÃO BÁSICA | drenagem torácica de urgência | Semântica | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 04.09.01.058-8 | URETEROSTOMIA CUTÂNEA | biópsia cutânea | Parcial | **BAIXA** | R$ 445,58 | R$ 0,00 | R$ 183,38 | R$ 628,96 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia computadorizada de tórax | Exata | Alta | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.06.01.004-4 | TOMOGRAFIA COMPUTADORIZADA DE FACE / SEIOS DA FACE / ARTICULACOES TEMPORO-MANDIBULARES | tomografia computadorizada de seios da face | Exata | Média | R$ 86,75 | R$ 86,75 | R$ 0,00 | R$ 173,50 |
| 02.14.01.021-0 | TESTE RÁPIDO CRAG PARA CRIPTOCOCOSE | teste rápido para criptococo | Parcial | Média | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.02.08.018-8 | PESQUISA DE BACILO DIFTÉRICO | baciloscopia de escarro | Semântica | **BAIXA** | R$ 0,00 | R$ 2,80 | R$ 0,00 | R$ 2,80 |
| 02.02.08.015-3 | HEMOCULTURA | hemocultura | Exata | Alta | R$ 0,00 | R$ 11,49 | R$ 0,00 | R$ 11,49 |
| 02.02.09.036-1 | TESTE MOLECULAR PARA A DETECÇÃO DO COMPLEXO MYCOBACTERIUM TUBERCULOSIS | GeneXpert | Agente | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.01.01.017-0 | CONSULTA/AVALIAÇÃO EM PACIENTE INTERNADO | [regra: medico] | Regra de documento | Alta | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 08.02.01.008-3 | DIARIA DE UNIDADE DE TERAPIA INTENSIVA ADULTO (UTI II) | [regra: medico] | Regra de documento | Alta | R$ 510,00 | R$ 0,00 | R$ 90,00 | R$ 600,00 |
| 03.01.10.007-1 | CUIDADOS C/ TRAQUEOSTOMIA | [regra de texto confirmada por 'traqueostomia de urgência': tqt, traqueostomia, acoplado/via tqt] | Regra de texto (confirmada) | Média | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |

**Subtotal do prontuário HUB010: R$ 2.491,67**

_Outras hipóteses para conferência:_

- **traqueostomia de urgência** → 2ª: CUIDADOS C/ TRAQUEOSTOMIA (03.01.10.007-1, R$ 0,00) · 3ª: TRAQUEOSTOMIA MEDIASTINAL (04.12.02.007-6, R$ 733,68)
- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)
- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **teste rápido para criptococo** → 2ª: TESTE RÁPIDO PARA MALÁRIA (02.14.01.018-0, R$ 0,00) · 3ª: TESTE RÁPIDO PARA DENGUE IGG/IGM (02.14.01.012-0, R$ 0,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - dreno torácico
> - cateter de gastrostomia
> - cultura de secreção
> - bactrim
> - levofloxacino
> - aciclovir
> - fluconazol
> - meropenem
> - linezolida
> - amicacina
> - vancomicina oral

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - sonda nasoenteral
> - vancomicina

> **Classificados pelo sistema como não realizados nesta evolução**  
> O sistema classificou estes itens como mencionados mas não realizados nesta evolução (solicitados, programados, cancelados, suspensos ou anteriores a ela). Eles não foram buscados e não entram no valor. A classificação é automática e pode errar - conferir, principalmente exames e procedimentos de valor alto.
>
> - ressonância magnética de coluna lombar (exame)
> - ressonância magnética de coluna torácica (exame)
> - eletromiografia (exame)
> - aspirado traqueal (exame)
> - ivermectina (medicamento)

---

## Resumo Consolidado

- **Prontuários processados:** 10
- **Códigos SIGTAP atribuídos:** 101
- **Códigos atribuídos por regra:** 20
- **Códigos com valor maior que zero:** 79
- **Correspondências de confiança BAIXA (conferir):** 33
- **Termos sem correspondência (verificar):** 90
- **Termos marcados como sem código próprio (conferir marcação):** 16
- **Indícios de regra sem confirmação (conferir, fora do valor):** 3
- **Termos genéricos para revisão (código a definir):** 0
- **Classificados como não realizados (conferir, fora do valor):** 21
- **VALOR TOTAL SUGERIDO:** R$ 17.185,01

_SH = Serviço Hospitalar, SA = Serviço Ambulatorial, SP = Serviço Profissional. Valores conforme tabela SIGTAP/DATASUS._
