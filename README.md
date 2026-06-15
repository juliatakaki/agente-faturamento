# Protótipo de Agente de IA para Extração de Procedimentos Clínicos e Associação com Códigos SIGTAP

## Sobre o projeto

Este projeto consiste no desenvolvimento de um protótipo funcional de um agente baseado em Inteligência Artificial Generativa para auxiliar na identificação automática de procedimentos clínicos descritos em prontuários eletrônicos e sua associação com códigos da tabela SIGTAP (Sistema de Gerenciamento da Tabela de Procedimentos, Medicamentos e OPM do SUS).

O protótipo foi desenvolvido como parte do Trabalho de Conclusão de Curso (TCC), com o objetivo de validar a viabilidade técnica de uma arquitetura baseada em:

- Processamento de Linguagem Natural (PLN);
- Reconhecimento de Entidades Nomeadas (NER);
- Modelos de Linguagem de Grande Escala (LLMs);
- Model Context Protocol (MCP);
- Orquestração de agentes utilizando LangGraph.

O sistema recebe como entrada um prontuário clínico em formato textual, realiza a extração de entidades relevantes, utiliza um modelo de linguagem para refinamento das informações e consulta uma base SIGTAP por meio de ferramentas disponibilizadas via MCP. Como resultado, é gerado um relatório estruturado contendo os procedimentos identificados e seus respectivos códigos.

---

# Arquitetura do protótipo

O fluxo geral do sistema é representado por:

```
Prontuário eletrônico
          |
          v
+----------------+
|      NER       |
|     spaCy      |
+----------------+
          |
          v
Entidades clínicas extraídas
          |
          v
+----------------+
|      LLM       |
| Ollama + Llama |
| ou Qwen        |
+----------------+
          |
          v
+----------------+
|  MCP Server    |
|    SIGTAP      |
+----------------+
          |
          v
Códigos SIGTAP encontrados
          |
          v
Relatório estruturado
```

---

# Funcionamento do pipeline

## 1. Extração de entidades clínicas (NER)

A primeira etapa do pipeline consiste na análise do texto do prontuário utilizando técnicas de Processamento de Linguagem Natural.

O módulo NER é responsável por identificar entidades clínicas relevantes, classificando-as em categorias como:

- PROCEDIMENTO;
- EXAME;
- MEDICAMENTO;
- MATERIAL.

Atualmente, o protótipo utiliza o componente `EntityRuler` do spaCy, baseado em regras linguísticas definidas para o domínio hospitalar.

Exemplo:

Entrada:

```
Paciente submetido à intubação orotraqueal.
Realizado hemograma completo e instalado cateter venoso central.
```

Saída:

```json
[
  {
    "texto": "intubação orotraqueal",
    "categoria": "PROCEDIMENTO"
  },
  {
    "texto": "hemograma completo",
    "categoria": "EXAME"
  },
  {
    "texto": "cateter venoso central",
    "categoria": "MATERIAL"
  }
]
```

---

## 2. Refinamento utilizando modelo de linguagem (LLM)

Após a extração das entidades, as informações são encaminhadas para um modelo de linguagem.

O LLM atua como agente de raciocínio, sendo responsável por:

- analisar as entidades extraídas;
- identificar quais informações possuem relação com procedimentos faturáveis;
- decidir quais consultas devem ser realizadas na base SIGTAP;
- utilizar as ferramentas disponibilizadas pelo servidor MCP.

Para garantir privacidade dos dados clínicos, o protótipo utiliza modelos executados localmente por meio do Ollama.

Modelos compatíveis:

- Llama;
- Qwen;
- outros modelos locais com suporte a ferramentas.

---

## 3. Consulta à tabela SIGTAP utilizando MCP

O acesso à tabela SIGTAP é realizado através de um servidor MCP (Model Context Protocol).

O MCP funciona como uma camada intermediária entre o agente de IA e fontes externas de informação, permitindo que o modelo utilize ferramentas especializadas durante a execução.

O servidor disponibiliza ferramentas como:

### buscar_procedimento()

Realiza uma busca textual por procedimentos.

Exemplo:

Entrada:

```
intubação orotraqueal
```

Saída:

```json
{
  "codigo": "03.01.01.007-2",
  "descricao": "INTUBACAO OROTRAQUEAL"
}
```

---

### buscar_por_codigo()

Realiza uma consulta direta utilizando um código SIGTAP.

Exemplo:

Entrada:

```
03.01.01.007-2
```

Saída:

```json
{
  "descricao": "INTUBACAO OROTRAQUEAL"
}
```

---

## 4. Geração do relatório

Após a etapa de consulta, o sistema consolida os resultados em um relatório estruturado no formato JSON.

Exemplo:

```json
{
  "prontuario_id": "PEP001",
  "total_entidades_extraidas": 10,
  "total_codigos_sigtap": 5,
  "procedimentos": [
    {
      "codigo": "03.01.01.007-2",
      "descricao": "INTUBACAO OROTRAQUEAL"
    }
  ]
}
```

---

# Estrutura do projeto

```
prototipo/
│
├── main.py
│
├── requirements.txt
│
├── data/
│   ├── prontuarios.json
│   └── sigtap_mock.csv
│
├── reports/
│   └── relatórios gerados
│
└── src/
    │
    ├── ner/
    │   └── extractor.py
    │
    ├── mcp/
    │   └── sigtap_server.py
    │
    └── agent/
        └── pipeline.py
```

---

# Descrição dos arquivos

## main.py

Arquivo principal de execução do protótipo.

Responsável por:

- carregar os prontuários;
- iniciar o pipeline de processamento;
- executar o agente;
- salvar os relatórios gerados.

Execução:

```bash
python main.py
```

---

## data/prontuarios.json

Dataset contendo prontuários clínicos sintéticos utilizados para validação do protótipo.

Os registros simulam evoluções hospitalares contendo:

- procedimentos;
- exames;
- medicamentos;
- materiais hospitalares.

---

## data/sigtap_mock.csv

Versão reduzida da tabela SIGTAP utilizada durante o desenvolvimento.

Contém informações como:

- código do procedimento;
- descrição;
- grupo.

Em versões futuras do projeto, essa base será substituída pela tabela SIGTAP completa disponibilizada pelo DATASUS.

---

## src/ner/extractor.py

Responsável pelo módulo de Reconhecimento de Entidades Nomeadas.

Principais funções:

- criação do pipeline spaCy;
- carregamento das regras clínicas;
- processamento dos textos;
- extração das entidades.

---

## src/mcp/sigtap_server.py

Implementa o servidor MCP responsável pelo acesso à base SIGTAP.

Responsabilidades:

- carregar a tabela;
- normalizar termos de busca;
- encontrar correspondências;
- disponibilizar ferramentas para o agente.

---

## src/agent/pipeline.py

Representa o núcleo do agente inteligente.

Utiliza LangGraph para orquestrar as etapas:

1. Extração das entidades pelo NER;
2. Refinamento utilizando LLM;
3. Consulta ao servidor MCP;
4. Geração do relatório final.

---

# Tecnologias utilizadas

## Linguagem

- Python 3.13

## Processamento de Linguagem Natural

- spaCy

## Inteligência Artificial Generativa

- Ollama;
- Llama;
- Qwen.

## Frameworks de agentes

- LangChain;
- LangGraph.

## Integração de ferramentas

- Model Context Protocol (MCP).

## Manipulação de dados

- Pandas;
- JSON.

---

# Instalação

## 1. Clonar o repositório

```bash
git clone https://github.com/juliatakaki/agente-faturamento

```

---

## 2. Criar ambiente virtual

```bash
python -m venv venv
```

Ativação no Windows:

```bash
venv\Scripts\activate
```

Ativação no Linux/Mac:

```bash
source venv/bin/activate
```

---

## 3. Instalar dependências

```bash
pip install -r requirements.txt
```

---

## 4. Instalar modelo spaCy

```bash
python -m spacy download pt_core_news_sm
```

---

## 5. Instalar Ollama

Download:

https://ollama.com/download

Após a instalação, baixar um modelo:

```bash
ollama pull llama3.2
```

ou:

```bash
ollama pull qwen2.5:7b
```

---

# Execução

Para executar o protótipo:

```bash
python main.py
```

Durante a execução será exibido:

```
Iniciando processamento de 10 prontuários...

Processando PEP001...
[NER] 10 entidades extraídas.
[LLM+MCP] Refinando entidades e consultando SIGTAP.

Processamento concluído.
```

Os relatórios gerados serão armazenados no diretório:

```
reports/
```

---

# Limitações atuais

Por se tratar de um protótipo inicial, existem algumas limitações:

- utilização de dados sintéticos;
- utilização de uma versão reduzida da tabela SIGTAP;
- NER baseado em regras;
- ausência de treinamento supervisionado;
- avaliação quantitativa limitada.

Essas limitações serão trabalhadas nas próximas etapas do projeto, incluindo:

- utilização de prontuários reais anonimizados;
- evolução do modelo NER;
- comparação entre diferentes modelos de linguagem;
- avaliação utilizando métricas como precisão, recall e F1-score.

---

# Trabalhos futuros

Como evolução do projeto, pretende-se:

- substituir regras manuais por modelos NER especializados;
- utilizar a tabela SIGTAP completa;
- comparar modelos locais e modelos via API;
- avaliar desempenho, custo e privacidade;
- aprimorar mecanismos de recuperação dos procedimentos;
- desenvolver uma solução mais próxima do ambiente hospitalar real.

---

# Autora

**Júlia Takaki Neves**

Projeto desenvolvido como parte do Trabalho de Conclusão de Curso em Engenharia de Software.
