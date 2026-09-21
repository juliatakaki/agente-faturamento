# Relatório de Faturamento SUS - SIGTAP

**Data de geração:** 21/09/2026 às 10:07  
**Total de prontuários processados:** 10  
**Modelo utilizado:** api/groq - openai/gpt-oss-120b  
**Consulta ao SIGTAP:** laço determinístico

> **Relatório de apoio ao faturamento.** As correspondências são sugestões da busca automática e devem ser verificadas antes do envio, com prioridade para as de confiança **BAIXA**. O dicionário de termos usado pelo sistema ainda não foi validado pelo setor de faturamento.

---

## Prontuário: HUB001

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |

**Subtotal do prontuário HUB001: R$ 0,00**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - cateter vesical
> - solução fisiológica
> - clorexidina alcoólica
> - gaze
> - filme transparente
> - banho no leito

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - sonda nasoenteral

---

## Prontuário: HUB002

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 04.06.01.010-2 | CARDIORRAFIA | consulta de cardiologia | Semântica | Média | R$ 1.175,18 | R$ 0,00 | R$ 693,36 | R$ 1.868,54 |
| 04.06.03.001-4 | ANGIOPLASTIA CORONARIANA | angioplastia | Exata | **BAIXA** | R$ 988,48 | R$ 1.081,48 | R$ 587,24 | R$ 2.657,20 |
| 03.01.08.017-8 | ATENDIMENTO INDIVIDUAL EM PSICOTERAPIA | atendimento psicológico | Semântica | **BAIXA** | R$ 0,00 | R$ 2,55 | R$ 0,00 | R$ 2,55 |

**Subtotal do prontuário HUB002: R$ 4.528,29**

_Outras hipóteses para conferência:_

- **angioplastia** → 2ª: ANGIOPLASTIA CORONARIANA PRIMÁRIA (04.06.03.004-9, R$ 2.581,19) · 3ª: ANGIOPLASTIA EM ENXERTO CORONARIANO (04.06.03.006-5, R$ 1.986,20)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - dobutamina
> - cateter de oxigênio
> - exame psíquico

---

## Prontuário: HUB003

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 07.01.07.007-2 | PLACA OCLUSAL | placa de alevyn | Semântica | Média | R$ 0,00 | R$ 23,54 | R$ 0,00 | R$ 23,54 |
| 06.04.05.007-0 | MORFINA 10 MG (POR COMPRIMIDO) | morfina | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |

**Subtotal do prontuário HUB003: R$ 23,54**

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
> - compressa estéril

---

## Prontuário: HUB004

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.02.02.038-0 | HEMOGRAMA COMPLETO | hemograma completo | Exata | Alta | R$ 0,00 | R$ 4,11 | R$ 0,00 | R$ 4,11 |
| 02.11.08.002-0 | GASOMETRIA | gasometria | Exata | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |
| 02.11.02.003-6 | ELETROCARDIOGRAMA | ECG | Dicionário | Alta | R$ 0,00 | R$ 5,15 | R$ 0,00 | R$ 5,15 |
| 02.06.01.007-9 | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | tomografia computadorizada de crânio sem contraste | Parcial | Média | R$ 97,44 | R$ 97,44 | R$ 0,00 | R$ 194,88 |
| 02.06.01.001-0 | TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE | tomografia computadorizada de abdome sem contraste | Parcial | **BAIXA** | R$ 86,76 | R$ 86,76 | R$ 0,00 | R$ 173,52 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia computadorizada de tórax sem contraste | Parcial | Média | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.02.03.029-6 | PESQUISA DE ANTICORPOS ANTI-HIV-1 (WESTERN BLOT/IMUNOBLOT) | anti HIV | Exata | **BAIXA** | R$ 0,00 | R$ 85,00 | R$ 0,00 | R$ 85,00 |
| 02.02.03.078-4 | PESQUISA DE ANTICORPOS IGG E IGM CONTRA ANTIGENO CENTRAL DO VIRUS DA HEPATITE B (ANTI-HBC-TOTAL) | anti HBC total | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.063-6 | PESQUISA DE ANTICORPOS CONTRA ANTIGENO DE SUPERFICIE DO VIRUS DA HEPATITE B (ANTI-HBS) | anti HBS | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.144-6 | PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) PARA POPULAÇÃO GERAL (EXCETO GESTANTE, PARCEIRO OU PARCERIA) | HBsAg | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.147-0 | PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) PARA POPULAÇÃO GERAL (EXCETO GESTANTE, PARCEIRO OU PARCERIA) | anti HCV | Similaridade | Média | R$ 0,00 | R$ 18,55 | R$ 0,00 | R$ 18,55 |
| 02.02.03.077-6 | PESQUISA DE ANTICORPOS IGG ANTITRYPANOSOMA CRUZI | sorologia Chagas | Agente | **BAIXA** | R$ 0,00 | R$ 9,25 | R$ 0,00 | R$ 9,25 |
| 02.14.01.027-9 | TESTE RÁPIDO PARA DETECÇÃO DE ANTICORPOS ANTI-HIV EM GESTANTE | teste rápido HIV | Exata | **BAIXA** | R$ 1,00 | R$ 1,00 | R$ 0,00 | R$ 2,00 |
| 02.14.01.014-7 | TESTE RÁPIDO DE DENGUE NS1 | teste rápido NS1 | Exata | Média | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.02.08.015-3 | HEMOCULTURA | hemocultura | Exata | Alta | R$ 0,00 | R$ 11,49 | R$ 0,00 | R$ 11,49 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 03.01.10.005-5 | CATETERISMO VESICAL DE DEMORA | sonda vesical de demora | Dicionário | Alta | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 06.04.05.007-0 | MORFINA 10 MG (POR COMPRIMIDO) | morfina | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 06.03.01.001-6 | METILPREDNISOLONA 500 MG INJENTAVEL (POR AMPOLA) | prednisolona | Similaridade | Média | R$ 20,96 | R$ 0,00 | R$ 0,00 | R$ 20,96 |

**Subtotal do prontuário HUB004: R$ 1.073,53**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)
- **tomografia computadorizada de crânio sem contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **tomografia computadorizada de abdome sem contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA LOMBO-SACRA C/ OU S/ CONTRASTE (02.06.01.002-8, R$ 202,20)
- **tomografia computadorizada de tórax sem contraste** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA CERVICAL C/ OU S/ CONTRASTE (02.06.01.001-0, R$ 173,52) · 3ª: TOMOGRAFIA COMPUTADORIZADA DE COLUNA TORACICA C/ OU S/ CONTRASTE (02.06.01.003-6, R$ 173,52)
- **anti HIV** → 2ª: PESQUISA LABORATORIAL DE ANTÍGENOS DE HIV OU ANTICORPOS ANTI-HIV-1 OU ANTI-HIV-2 EM GESTANTE (02.02.03.151-9, R$ 10,00)
- **HBsAg** → 2ª: PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) EM GESTANTE (02.02.03.145-4, R$ 18,55) · 3ª: PESQUISA LABORATORIAL DE ANTÍGENO DE SUPERFÍCIE DO VÍRUS DA HEPATITE B (HBSAG) EM PARCEIRO OU PARCERIA DE GESTANTE (02.02.03.146-2, R$ 18,55)
- **anti HCV** → 2ª: PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) EM GESTANTE (02.02.03.148-9, R$ 18,55) · 3ª: PESQUISA LABORATORIAL DE ANTICORPOS CONTRA O VÍRUS DA HEPATITE C (ANTI-HCV) EM PARCEIRO OU PARCERIA DE GESTANTE (02.02.03.149-7, R$ 18,55)
- **teste rápido HIV** → 2ª: TESTE RÁPIDO PARA DETECÇÃO DE ANTICORPOS ANTI-HIV EM PARCEIRO OU PARCERIA DE GESTANTE (02.14.01.028-7, R$ 2,00)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)
- **morfina** → 2ª: MORFINA 30 MG (POR COMPRIMIDO) (06.04.05.008-9, R$ 0,00)
- **prednisolona** → 2ª: METILPREDNISOLONA 500MG INJETAVEL P/TRANSPLANTE(POR FRASCO AMPOLA) (06.03.08.012-0, R$ 20,96) · 3ª: METILPREDNISOLONA 500 MG INJETAVEL (POR AMPOLA) (06.04.28.010-6, R$ 0,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - VDRL
> - painel viral
> - urocultura
> - tubo de traqueostomia
> - sonda nasogástrica
> - amitriptilina
> - glicazida
> - metformina
> - atenolol
> - dipirona
> - torgena
> - aztreonam
> - amicacina
> - linezolida
> - micafungina
> - meropenem
> - polimixina B
> - unasyn
> - tazocin
> - ceftriaxona
> - aciclovir
> - levofloxacino
> - precedex
> - fentanil
> - potássio
> - gluconato de cálcio

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - intubação orotraqueal
> - vancomicina
> - noradrenalina

---

## Prontuário: HUB005

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |

**Subtotal do prontuário HUB005: R$ 2,78**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - cistoprostatectomia radical
> - urostomia à Bricker
> - midazolam
> - fentanil

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - noradrenalina

---

## Prontuário: HUB006

_Nenhum código SIGTAP foi vinculado a este prontuário._

---

## Prontuário: HUB007

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 03.01.05.017-1 | AVALIAÇÃO DO PACIENTE EM VENTILAÇÃO MECÂNICA INVASIVADOMICILIAR | ventilação mecânica | Exata | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |
| 07.02.05.005-9 | CATETER BALAO P/ EMBOLECTOMIA ARTERIAL / VENOSA | cateter arterial | Exata | **BAIXA** | R$ 96,20 | R$ 0,00 | R$ 0,00 | R$ 96,20 |
| 02.11.08.002-0 | GASOMETRIA | gasometria arterial | Dicionário | Alta | R$ 0,00 | R$ 2,78 | R$ 0,00 | R$ 2,78 |

**Subtotal do prontuário HUB007: R$ 316,35**

_Outras hipóteses para conferência:_

- **ventilação mecânica** → 2ª: INSTALAÇÃO / MANUTENÇÃO DE VENTILAÇÃO MECÂNICA NÃO INVASIVA DOMICILIAR (03.01.05.006-6, R$ 27,50)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)

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
| 03.01.10.028-4 | CURATIVO SIMPLES | troca de curativo | Parcial | **BAIXA** | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |

**Subtotal do prontuário HUB008: R$ 0,00**

_Outras hipóteses para conferência:_

- **troca de curativo** → 2ª: CURATIVO ESPECIAL (03.01.10.027-6, R$ 0,00)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - expressão manual de fístula
> - solução fisiológica 0,9%
> - clorexidina alcoólica
> - compressa estéril
> - filme transparente

---

## Prontuário: HUB009

| Código SIGTAP | Procedimento | Origem | Nível | Confiança | SH | SA | SP | Total |
|---|---|---|---|---|---:|---:|---:|---:|
| 06.04.41.001-8 | METADONA 5 MG (POR COMPRIMIDO) | Metadona | Exata | Média | R$ 0,00 | R$ 0,00 | R$ 0,00 | R$ 0,00 |
| 02.06.03.001-0 | TOMOGRAFIA COMPUTADORIZADA DE ABDOMEN SUPERIOR | tomografia computadorizada de abdome | Parcial | Alta | R$ 138,63 | R$ 138,63 | R$ 0,00 | R$ 277,26 |
| 02.06.02.003-1 | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia computadorizada de tórax | Exata | Alta | R$ 136,41 | R$ 136,41 | R$ 0,00 | R$ 272,82 |
| 02.06.01.007-9 | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | tomografia computadorizada de crânio | Exata | Alta | R$ 97,44 | R$ 97,44 | R$ 0,00 | R$ 194,88 |
| 02.06.01.009-5 | TOMOGRAFIA POR EMISSÃO DE PÓSITRONS (PET-CT) | PET-CT | Similaridade | Média | R$ 0,00 | R$ 2.107,22 | R$ 0,00 | R$ 2.107,22 |
| 02.02.08.010-2 | CULTURA P/ HERPESVIRUS | cultura de sangue | Parcial | **BAIXA** | R$ 0,00 | R$ 4,33 | R$ 0,00 | R$ 4,33 |
| 07.02.04.015-0 | CATETER VENOSO CENTRAL DUPLO LUMEN | cateter venoso central | Exata | Média | R$ 119,89 | R$ 97,48 | R$ 0,00 | R$ 217,37 |

**Subtotal do prontuário HUB009: R$ 3.073,88**

_Outras hipóteses para conferência:_

- **Metadona** → 2ª: METADONA 10 MG (POR COMPRIMIDO) (06.04.41.002-6, R$ 0,00)
- **tomografia computadorizada de abdome** → 2ª: TOMOGRAFIA COMPUTADORIZADA DE PELVE / BACIA / ABDOMEN INFERIOR (02.06.03.003-7, R$ 277,26) · 3ª: TOMOGRAFIA COMPUTADORIZADA DO CRANIO (02.06.01.007-9, R$ 194,88)
- **cultura de sangue** → 2ª: PROCESSAMENTO DE SANGUE (02.12.02.006-4, R$ 10,15)
- **cateter venoso central** → 2ª: CATETER VENOSO CENTRAL MONO LUMEN (07.02.05.081-4, R$ 0,00) · 3ª: CATETER DE ACESSO VENOSO CENTRAL POR INSERÇÃO PERIFÉRICA (PICC) (07.02.04.011-8, R$ 243,52)

> **Sem correspondência - verificação manual**  
> Estes termos foram identificados no prontuário mas não puderam ser vinculados a um código SIGTAP pela busca automática. Podem representar receita não faturada.
>
> - Unasyn
> - Tigeciclina
> - Poli B
> - Meropenem
> - Cefepime
> - Tazocin
> - Potássio
> - Magnésio
> - angiotomografia de tórax
> - cultura de swab

> **Marcados pelo sistema como sem código próprio no SIGTAP**  
> O dicionário do sistema registra estes itens como não faturáveis separadamente (embutidos em outro procedimento ou fora do rol da tabela). Essa marcação NÃO foi validada pelo setor de faturamento e já se mostrou incorreta em auditoria - conferir antes de descartar.
>
> - Azitromicina
> - Vancomicina

---

## Prontuário: HUB010

_Nenhum código SIGTAP foi vinculado a este prontuário._

---

## Resumo Consolidado

- **Prontuários processados:** 10
- **Códigos SIGTAP atribuídos:** 40
- **Códigos com valor maior que zero:** 30
- **Correspondências de confiança BAIXA (conferir):** 15
- **Termos sem correspondência (verificar):** 69
- **Termos marcados como sem código próprio (conferir marcação):** 9
- **VALOR TOTAL SUGERIDO:** R$ 9.018,37

_SH = Serviço Hospitalar, SA = Serviço Ambulatorial, SP = Serviço Profissional. Valores conforme tabela SIGTAP/DATASUS._
