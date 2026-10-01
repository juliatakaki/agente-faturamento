# Relatório de Faturamento SUS - SIGTAP

**Data de geração:** 30/09/2026 às 23:58  
**Total de prontuários processados:** 10  
**Modelo utilizado:** api/groq - openai/gpt-oss-120b  
**Consulta ao SIGTAP:** laço determinístico

> **Relatório de apoio ao faturamento.** As correspondências são sugestões da busca automática e devem ser verificadas antes do envio, com prioridade para as de confiança **BAIXA**. O dicionário de termos usado pelo sistema ainda não foi validado pelo setor de faturamento.

---

## Prontuário: HUB001

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |

**Subtotal do prontuário HUB001: R$ 30,00**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)
- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - tubo orotraqueal
> - cateter vesical
> - gaze
> - filme transparente
> - clorexidina alcoólica
> - solução fisiológica

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
| 03.01.10.005-5 | CATETERISMO VESICAL DE DEMORA | cateterismo | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 04.06.03.001-4 | ANGIOPLASTIA CORONARIANA | angioplastia | Exata | **BAIXA** | R$ 988,48 | R$ 1.081,48 | R$ 587,24 | R$ 2.657,20 |

**Subtotal do prontuário HUB002: R$ 2.659,75**

_Outras hipóteses para conferência:_

- **cateterismo** → 2ª: CATETERISMO VESICAL DE ALIVIO (03.01.10.004-7, R$ 0,00) · 3ª: CATETERISMO EVACUADOR DE BEXIGA (03.09.03.001-3, R$ 1,52)
- **angioplastia** → 2ª: ANGIOPLASTIA CORONARIANA PRIMÁRIA (04.06.03.004-9, R$ 2.581,19) · 3ª: ANGIOPLASTIA EM ENXERTO CORONARIANO (04.06.03.006-5, R$ 1.986,20)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - exame psíquico
> - cateter de oxigênio
> - dobutamina

---

## Prontuário: HUB003

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 07.01.07.007-2 | PLACA OCLUSAL | placa de alevyn | Semântica | Média | R$ 0,00 | R$ 23,54 | R$ 0,00 | R$ 23,54 |
| 06.04.05.007-0 | MORFINA 10 MG (POR COMPRIMIDO) | morfina | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 07.01.04.001-7 | BENGALA ARTICULADA | compressa | Semântica | **BAIXA** | R$ 0,00 | R$ 91,91 | R$ 0,00 | R$ 91,91 |
| 04.03.01.034-9 | TREPANACAO CRANIANA PARA PROPEDEUTICA NEUROCIRURGICA / IMPLANTE PARA MONITORIZACAO PIC | monitorização | Similaridade | Média | R$ 494,83 | R$ 0,00 | R$ 107,52 | R$ 602,35 |

**Subtotal do prontuário HUB003: R$ 717,80**

_Outras hipóteses para conferência:_

- **morfina** → 2ª: MORFINA 30 MG (POR COMPRIMIDO) (06.04.05.008-9, R$ 0,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - solução fisiológica
> - clorexidina alcoólica
> - gaze
> - filme transparente
> - alginato

---

## Prontuário: HUB004

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.016-3 | ATENDIMENTO E ACOMPANHAMENTO DOMICILIAR DEPACIENTE SUBMETIDO À VENTILAÇÃO MECÂNICA INVASIVA DOMICILIAR | ventilação mecânica invasiva | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 03.01.10.003-9 | AFERIÇÃO DE PRESSÃO ARTERIAL | cateterismo arterial invasivo | Semântica | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.01.10.005-5 | CATETERISMO VESICAL DE DEMORA | cateterismo vesical | Exata | Média | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.02.02.038-0 | HEMOGRAMA COMPLETO | hemograma completo | Exata | Alta | R$ 0,00 | R$ 4,11 | R$ 0,00 | R$ 4,11 |
| 02.02.02.014-2 | DETERMINAÇÃO DE TEMPO E ATIVIDADE DA PROTROMBINA (TAP) | tempo de protrombina | Exata | **BAIXA** | R$ 0,00 | R$ 2,73 | R$ 0,00 | R$ 2,73 |
| 02.02.01.069-4 | DOSAGEM DE UREIA | ureia | Exata | Média | R$ 0,00 | R$ 1,85 | R$ 0,00 | R$ 1,85 |
| 02.02.01.031-7 | DOSAGEM DE CREATININA | creatinina | Exata | Média | R$ 0,00 | R$ 1,85 | R$ 0,00 | R$ 1,85 |
| 02.14.01.001-5 | GLICEMIA CAPILAR | glicemia | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.02.01.063-5 | DOSAGEM DE SODIO | sódio | Exata | Média | R$ 0,00 | R$ 1,85 | R$ 0,00 | R$ 1,85 |
| 02.02.01.060-0 | DOSAGEM DE POTASSIO | potássio | Exata | Média | R$ 0,00 | R$ 1,85 | R$ 0,00 | R$ 1,85 |
| 02.02.01.056-2 | DOSAGEM DE MAGNESIO | magnésio | Exata | Média | R$ 0,00 | R$ 2,01 | R$ 0,00 | R$ 2,01 |
| 02.02.01.021-0 | DOSAGEM DE CALCIO | cálcio | Exata | Média | R$ 0,00 | R$ 1,85 | R$ 0,00 | R$ 1,85 |
| 02.02.01.046-5 | DOSAGEM DE GAMA-GLUTAMIL-TRANSFERASE (GAMA GT) | GGT | Agente | **BAIXA** | R$ 0,00 | R$ 3,51 | R$ 0,00 | R$ 3,51 |
| 02.02.02.013-4 | DETERMINAÇÃO DE TEMPO DE TROMBOPLASTINA PARCIAL ATIVADA (TTP ATIVADA) | AST | Similaridade | Média | R$ 0,00 | R$ 5,77 | R$ 0,00 | R$ 5,77 |
| 02.02.09.032-9 | REAÇÃO DE RIVALTA NO LÍQUIDO SINOVIAL E DERRAMES | ALT | Similaridade | Média | R$ 0,00 | R$ 1,89 | R$ 0,00 | R$ 1,89 |
| 02.02.01.032-5 | DOSAGEM DE CREATINOFOSFOQUINASE (CPK) | CPK | Similaridade | Média | R$ 0,00 | R$ 3,68 | R$ 0,00 | R$ 3,68 |
| 02.02.01.020-1 | DOSAGEM DE BILIRRUBINA TOTAL E FRACOES | bilirrubina total | Exata | **BAIXA** | R$ 0,00 | R$ 2,01 | R$ 0,00 | R$ 2,01 |
| 02.02.03.111-0 | TESTE NÃO TREPONEMICO P/ DETECÇÃO DE SIFILIS PARA POPULAÇÃO GERAL (EXCETO GESTANTE, PARCEIRO OU PARCERIA) | VDRL | Agente | **BAIXA** | R$ 0,00 | R$ 2,83 | R$ 0,00 | R$ 2,83 |
| 02.02.03.029-6 | PESQUISA DE ANTICORPOS ANTI-HIV-1 (WESTERN BLOT/IMUNOBLOT) | anti-HIV | Exata | **BAIXA** | R$ 0,00 | R$ 85,00 | R$ 0,00 | R$ 85,00 |
| 02.02.03.078-4 | PESQUISA DE ANTICORPOS IGG E IGM CONTRA ANTIGENO CENTRAL DO VIRUS DA HEPATITE B (ANTI-HBC-TOTAL) | anti-HBc total | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.063-6 | PESQUISA DE ANTICORPOS CONTRA ANTIGENO DE SUPERFICIE DO VIRUS DA HEPATITE B (ANTI-HBS) | anti-HBs | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.144-6 | PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) PARA POPULAÇÃO GERAL (EXCETO GESTANTE, PARCEIRO OU PARCERIA) | HBsAg | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.147-0 | PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) PARA POPULAÇÃO GERAL (EXCETO GESTANTE, PARCEIRO OU PARCERIA) | anti-HCV | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |
| 02.11.02.003-6 | ELETROCARDIOGRAMA | eletrocardiograma | Exata | Alta | R$ 0,00 | R$ 5,15 | R$ 0,00 | R$ 5,15 |
| 02.06.01.007-9 | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | tomografia computadorizada de crânio sem contraste | Parcial | Média | R$ 97,44 | R$ 97,44 | R$ 0,00 | R$ 194,88 |
| 02.06.01.001-0 | TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE | tomografia computadorizada de abdome sem contraste | Parcial | **BAIXA** | R$ 86,76 | R$ 86,76 | R$ 0,00 | R$ 173,52 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia computadorizada de tórax sem contraste | Parcial | Média | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.02.08.015-3 | HEMOCULTURA | hemocultura | Exata | Alta | R$ 0,00 | R$ 11,49 | R$ 0,00 | R$ 11,49 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 07.02.05.005-9 | CATETER BALAO P/ EMBOLECTOMIA ARTERIAL / VENOSA | cateter arterial | Exata | **BAIXA** | R$ 96,20 | R$ 0,00 | R$ 0,00 | R$ 96,20 |
| 06.04.05.007-0 | MORFINA 10 MG (POR COMPRIMIDO) | morfina | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 06.03.01.001-6 | METILPREDNISOLONA 500 MG INJENTAVEL (POR AMPOLA) | prednisolona | Similaridade | Média | R$ 20,96 | R$ 0,00 | R$ 0,00 | R$ 20,96 |

**Subtotal do prontuário HUB004: R$ 1.222,16**

_Outras hipóteses para conferência:_

- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)
- **cateterismo vesical** → 2ª: CATETERISMO VESICAL DE ALIVIO (03.01.10.004-7, R$ 0,00)
- **ureia** → 2ª: CLEARANCE DE UREIA (02.02.05.004-1, R$ 3,51)
- **creatinina** → 2ª: CLEARANCE DE CREATININA (02.02.05.002-5, R$ 3,51) · 3ª: DOSAGEM DE CREATININA NO LÍQUIDO AMNIÓTICO (02.02.09.008-6, R$ 1,89)
- **cálcio** → 2ª: DOSAGEM DE CALCIO IONIZAVEL (02.02.01.022-8, R$ 3,51)
- **AST** → 2ª: RASTREIO P/ DEFICIENCIA DE ENZIMAS ERITROCITARIAS (02.02.02.051-7, R$ 2,73) · 3ª: TESTE DE ELASTASE PANCREÁTICA FECAL (02.02.04.018-6, R$ 248,00)
- **ALT** → 2ª: IDENTIFICAÇÃO DE ALTERAÇÃO CROMOSSÔNICA SUBMICROSCÓPICA POR ARRAY-CGH (02.02.10.010-3, R$ 0,00)
- **anti-HIV** → 2ª: PESQUISA LABORATORIAL DE ANTÍGENOS DE HIV OU ANTICORPOS ANTI-HIV-1 OU ANTI-HIV-2 EM GESTANTE (02.02.03.151-9, R$ 10,00)
- **HBsAg** → 2ª: PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) EM GESTANTE (02.02.03.145-4, R$ 18,55) · 3ª: PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) EM PARCEIRO OU PARCERIA DE GESTANTE (02.02.03.146-2, R$ 18,55)
- **anti-HCV** → 2ª: PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) EM GESTANTE (02.02.03.148-9, R$ 18,55) · 3ª: PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) EM PARCEIRO OU PARCERIA DE GESTANTE (02.02.03.149-7, R$ 18,55)
- **eletrocardiograma** → 2ª: TELE-ELETROCARDIOGRAMA SÍNCRONO/LAUDO (02.11.02.009-5, R$ 0,00)
- **tomografia computadorizada de crânio sem contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **tomografia computadorizada de abdome sem contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA LOMBO-SACRA C/ OU S/ CONTRASTE (02.06.01.002-8, R$ 202,20)
- **tomografia computadorizada de tórax sem contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **morfina** → 2ª: MORFINA 30 MG (POR COMPRIMIDO) (06.04.05.008-9, R$ 0,00)
- **prednisolona** → 2ª: METILPREDNISOLONA 500MG INJETAVEL P/TRANSPLANTE(POR FRASCO AMPOLA) (06.03.08.012-0, R$ 20,96) · 3ª: METILPREDNISOLONA 500 MG INJETAVEL (POR AMPOLA) (06.04.28.010-6, R$ 0,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - cateterismo venoso central
> - INR
> - bilirrubina direta
> - sorologia de Chagas
> - painel viral
> - urocultura
> - cultura de secreção traqueal
> - tubo endotraqueal
> - cateter vesical
> - amitriptilina
> - gliclazida
> - metformina
> - atenolol
> - dipirona
> - piperacilina-tazobactam
> - aztreonam
> - amikacina
> - linezolida
> - micafungina
> - meropenem
> - polimixina B
> - ampicilina-sulbactam
> - ceftriaxona
> - aciclovir
> - levofloxacino

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - intubação orotraqueal
> - sonda nasoenteral
> - vancomicina

---

## Prontuário: HUB005

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.016-3 | ATENDIMENTO E ACOMPANHAMENTO DOMICILIAR DEPACIENTE SUBMETIDO À VENTILAÇÃO MECÂNICA INVASIVA DOMICILIAR | ventilação mecânica invasiva | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.03.14.013-5 | TRATAMENTO DE OUTRAS DOENCAS DO APARELHO RESPIRATORIO | fisioterapia respiratória | Semântica | **BAIXA** | R$ 451,47 | R$ 0,00 | R$ 29,40 | R$ 480,87 |
| 03.02.05.002-7 | ATENDIMENTO FISIOTERAPÊUTICO NAS ALTERAÇÕES MOTORAS | fisioterapia motora | Semântica | **BAIXA** | R$ 0,00 | R$ 4,67 | R$ 0,00 | R$ 4,67 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |

**Subtotal do prontuário HUB005: R$ 488,32**

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - cistoprostatectomia radical
> - urostomia à Bricker
> - amicacina
> - dipirona
> - midazolam
> - fentanil

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - noradrenalina

---

## Prontuário: HUB006

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 03.01.05.016-3 | ATENDIMENTO E ACOMPANHAMENTO DOMICILIAR DEPACIENTE SUBMETIDO À VENTILAÇÃO MECÂNICA INVASIVA DOMICILIAR | ventilação mecânica invasiva | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.06.02.006-8 | TRANSFUSAO DE CONCENTRADO DE HEMACIAS | transfusão de hemácias | Exata | Média | R$ 8,39 | R$ 8,09 | R$ 0,00 | R$ 16,48 |
| 03.06.02.007-6 | TRANSFUSAO DE CONCENTRADO DE PLAQUETAS | transfusão de plaquetas | Exata | Média | R$ 8,39 | R$ 8,09 | R$ 0,00 | R$ 16,48 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 07.02.05.005-9 | CATETER BALAO P/ EMBOLECTOMIA ARTERIAL / VENOSA | cateter arterial | Exata | **BAIXA** | R$ 96,20 | R$ 0,00 | R$ 0,00 | R$ 96,20 |
| 02.02.02.038-0 | HEMOGRAMA COMPLETO | hemograma completo | Exata | Alta | R$ 0,00 | R$ 4,11 | R$ 0,00 | R$ 4,11 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |
| 02.02.08.015-3 | HEMOCULTURA | hemocultura | Exata | Alta | R$ 0,00 | R$ 11,49 | R$ 0,00 | R$ 11,49 |
| 02.02.08.010-2 | CULTURA P/ HERPESVIRUS | cultura de urina | Parcial | **BAIXA** | R$ 0,00 | R$ 4,33 | R$ 0,00 | R$ 4,33 |
| 02.14.01.015-5 | TESTE RÁPIDO DE PROTEINÚRIA | proteinúria de 24h | Parcial | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.08.02.012-8 | IMUNO-CINTILOGRAFIA (ANTICORPO MONOCLONAL) | imunofenotipagem | Semântica | **BAIXA** | R$ 1.103,26 | R$ 1.103,26 | R$ 0,00 | R$ 2.206,52 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia de tórax | Dicionário | Alta | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.06.01.004-4 | TOMOGRAFIA COMPUTADORIZADA DE FACE / SEIOS DA FACE / ARTICULACOES TEMPORO-MANDIBULARES | tomografia de seios da face | Exata | **BAIXA** | R$ 86,75 | R$ 86,75 | R$ 0,00 | R$ 173,50 |
| 02.06.01.007-9 | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | tomografia computadorizada do corpo total | Parcial | **BAIXA** | R$ 97,44 | R$ 97,44 | R$ 0,00 | R$ 194,88 |
| 02.06.03.003-7 | TOMOGRAFIA COMPUTADORIZADA DE PELVE / BACIA / ABDOMEN INFERIOR | tomografia de pelve | Exata | **BAIXA** | R$ 138,63 | R$ 138,63 | R$ 0,00 | R$ 277,26 |

**Subtotal do prontuário HUB006: R$ 3.524,22**

_Outras hipóteses para conferência:_

- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)
- **transfusão de plaquetas** → 2ª: TRANSFUSAO DE PLAQUETAS POR AFERESE (03.06.02.009-2, R$ 16,18)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **tomografia computadorizada do corpo total** → 2ª: TOMOGRAFIA COMPUTADORIZADA DO PESCOCO (02.06.01.005-2, R$ 173,50) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE TORAX (02.06.02.003-1, R$ 272,82)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - cânula endotraqueal
> - aspiração traqueal
> - angiotomografia
> - bioquímica sanguínea
> - losartana
> - furosemida
> - metoprolol
> - midazolam
> - fentanil
> - dexmedetomidina
> - vasopressina
> - meropenem
> - micafungina
> - anfotericina B
> - anidulofungina
> - amicacina
> - piperacilina-tazobactam
> - dexametasona

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - intubação orotraqueal
> - sonda nasoenteral
> - noradrenalina
> - vancomicina

---

## Prontuário: HUB007

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 04.05.05.030-5 | SUTURA DE CORNEA | sutura | Exata | **BAIXA** | R$ 0,00 | R$ 164,08 | R$ 0,00 | R$ 164,08 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 07.02.05.005-9 | CATETER BALAO P/ EMBOLECTOMIA ARTERIAL / VENOSA | cateter arterial | Exata | **BAIXA** | R$ 96,20 | R$ 0,00 | R$ 0,00 | R$ 96,20 |

**Subtotal do prontuário HUB007: R$ 480,43**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)
- **sutura** → 2ª: SUTURA DE ESCLERA (04.05.03.009-6, R$ 322,38) · 3ª: SUTURA DE CONJUNTIVA (04.05.05.029-1, R$ 82,28)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - vasopressina
> - fentanil
> - midazolam
> - clorexidina alcoólica
> - banho no leito
> - gaze
> - filme transparente
> - placa de hidropolímero

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - noradrenalina
> - monitorização cardíaca

---

## Prontuário: HUB008

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 07.02.04.011-8 | CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) | acesso venoso periférico | Parcial | **BAIXA** | R$ 243,52 | R$ 0,00 | R$ 0,00 | R$ 243,52 |

**Subtotal do prontuário HUB008: R$ 243,52**

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - solução fisiológica 0,9%
> - clorexidina alcoólica
> - compressa estéril
> - filme transparente

---

## Prontuário: HUB009

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 06.04.41.001-8 | METADONA 5 MG (POR COMPRIMIDO) | metadona | Exata | Média | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 02.02.08.010-2 | CULTURA P/ HERPESVIRUS | cultura de sangue | Parcial | **BAIXA** | R$ 0,00 | R$ 4,33 | R$ 0,00 | R$ 4,33 |
| 02.02.08.015-3 | HEMOCULTURA | cultura de HMC | Agente | **BAIXA** | R$ 0,00 | R$ 11,49 | R$ 0,00 | R$ 11,49 |
| 02.06.03.001-0 | TOMOGRAFIA COMPUTADORIZADA DE ABDOMEN SUPERIOR | tomografia computadorizada de abdômen com contraste | Parcial | Média | R$ 138,63 | R$ 138,63 | R$ 0,00 | R$ 277,26 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia computadorizada de tórax com contraste | Parcial | Média | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.06.01.007-9 | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | tomografia computadorizada de crânio com contraste | Parcial | Média | R$ 97,44 | R$ 97,44 | R$ 0,00 | R$ 194,88 |
| 02.06.01.009-5 | TOMOGRAFIA POR EMISSÃO DE PÓSITRONS (PET-CT) | PET-CT | Similaridade | Média | R$ 0,00 | R$ 2.107,22 | R$ 0,00 | R$ 2.107,22 |

**Subtotal do prontuário HUB009: R$ 3.115,37**

_Outras hipóteses para conferência:_

- **metadona** → 2ª: METADONA 10 MG (POR COMPRIMIDO) (06.04.41.002-6, R$ 0,00)
- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **cultura de sangue** → 2ª: PROCESSAMENTO DE SANGUE (02.12.02.006-4, R$ 10,15)
- **tomografia computadorizada de abdômen com contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **tomografia computadorizada de tórax com contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **tomografia computadorizada de crânio com contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - unasyn
> - tigeciclina
> - Poli B
> - mero
> - cefepime
> - tazocin
> - azitro
> - vanco
> - potássio
> - magnésio
> - swab

---

## Prontuário: HUB010

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 04.04.01.037-7 | TRAQUEOSTOMIA | traqueostomia | Exata | Alta | R$ 394,07 | R$ 0,00 | R$ 160,66 | R$ 554,73 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 04.01.01.003-1 | DRENAGEM DE ABSCESSO | drenagem torácica | Parcial | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 04.09.01.058-8 | URETEROSTOMIA CUTÂNEA | biopsia cutânea | Parcial | **BAIXA** | R$ 445,58 | R$ 0,00 | R$ 183,38 | R$ 628,96 |
| 03.09.01.004-7 | NUTRIÇÃO ENTERAL EM ADULTO | nutrição enteral | Exata | Média | R$ 30,00 | R$ 0,00 | R$ 0,00 | R$ 30,00 |
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia de tórax | Dicionário | Alta | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.06.01.004-4 | TOMOGRAFIA COMPUTADORIZADA DE FACE / SEIOS DA FACE / ARTICULACOES TEMPORO-MANDIBULARES | tomografia de seios da face | Exata | **BAIXA** | R$ 86,75 | R$ 86,75 | R$ 0,00 | R$ 173,50 |

**Subtotal do prontuário HUB010: R$ 1.877,38**

_Outras hipóteses para conferência:_

- **traqueostomia** → 2ª: CUIDADOS C/ TRAQUEOSTOMIA (03.01.10.007-1, R$ 0,00) · 3ª: TRAQUEOSTOMIA MEDIASTINAL (04.12.02.007-6, R$ 733,68)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **drenagem torácica** → 2ª: ESOFAGORRAFIA TORÁCICA (04.07.01.010-6, R$ 787,65)
- **nutrição enteral** → 2ª: NUTRIÇÃO ENTERAL EM PEDIATRIA (03.09.01.006-3, R$ 18,00) · 3ª: NUTRICAO ENTERAL EM NEONATOLOGIA (03.09.01.005-5, R$ 18,00)
- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - cateter venoso central
> - dreno torácico
> - sonda de gastrostomia
> - bactrim
> - levofloxacino
> - aciclovir
> - vancomicina oral
> - fluconazol
> - meropenem
> - linezolida
> - amicacina

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - sonda nasoenteral
> - vancomicina

---

## Resumo Consolidado

- **Prontuários processados:** 10
- **Códigos SIGTAP atribuídos:** 87
- **Códigos com valor maior que zero:** 71
- **Correspondências de confiança BAIXA (conferir):** 39
- **Termos sem correspondência (verificar):** 97
- **Termos marcados como sem código próprio (conferir marcação):** 13
- **VALOR TOTAL SUGERIDO:** R$ 14.358,95

_SH = Serviço Hospitalar, SA = Serviço Ambulatorial, SP = Serviço Profissional. Valores conforme tabela SIGTAP/DATASUS._
