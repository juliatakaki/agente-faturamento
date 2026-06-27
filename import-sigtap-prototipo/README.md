# Importação SIGTAP para PostgreSQL

Scripts para gerar o schema do banco e importar os arquivos de dados em
largura fixa (fixed-width) do SIGTAP/DATASUS para o PostgreSQL.

## O que tem aqui

- `docker-compose.yml` — sobe um PostgreSQL 16 do zero
- `gerar_ddl.py` — lê os arquivos de layout e gera `schema.sql` + `layouts.json`
- `importar.py` — lê os arquivos de dados (largura fixa) e carrega no Postgres
- `requirements.txt` — dependências Python

## Passo 1 — Organize os arquivos

Coloque **na mesma pasta**:

- O `layout.txt` mestre (se você tiver)
- Os arquivos de layout individuais, ex: `rl_procedimento_incremento_layout.txt`,
  `tb_descricao_layout.txt`, etc (se existirem soltos, eles têm prioridade
  sobre o que estiver no `layout.txt` mestre, caso haja divergência)
- Todos os arquivos de **dados** (ex: `tb_procedimento.txt`,
  `rl_procedimento_cid.txt`, etc.) — um arquivo de dados por tabela,
  com o nome do arquivo igual ao nome da tabela.

Essa pasta pode ser a mesma onde estão `docker-compose.py`, `gerar_ddl.py`
etc, ou uma pasta separada — você passa o caminho como argumento.

## Passo 2 — Suba o Postgres

```bash
docker compose up -d
```

Isso cria o banco `sigtap`, usuário `sigtap`, senha `sigtap`, na porta `5432`.
Pra mudar essas credenciais, edite o `docker-compose.yml` antes de subir.

Espere alguns segundos e confirme que está saudável:

```bash
docker compose ps
```

## Passo 3 — Instale as dependências Python

```bash
pip install -r requirements.txt
```

## Passo 4 — Gere o schema (DDL)

```bash
python gerar_ddl.py /caminho/para/sua/pasta/com/layouts
```

Isso vai:
1. Imprimir a lista de tabelas encontradas (confirme que bateu com as suas 48)
2. Gerar `schema.sql` (os `CREATE TABLE`) dentro dessa mesma pasta
3. Gerar `layouts.json` (usado no próximo passo)

**Se a contagem de tabelas não bater com as 48 que você tem**, me avisa —
provavelmente há algum arquivo de layout com nome ou formato diferente do
padrão `<nome_tabela>_layout.txt`, e eu ajusto o parser.

## Passo 5 — Crie as tabelas no Postgres

```bash
psql -h localhost -U sigtap -d sigtap -f /caminho/para/sua/pasta/schema.sql
```

Vai pedir a senha (`sigtap`, se você não mudou). Se não tiver o `psql`
instalado localmente, dá pra rodar de dentro do container:

```bash
docker compose exec -T postgres psql -U sigtap -d sigtap < /caminho/para/sua/pasta/schema.sql
```

## Passo 6 — Importe os dados

```bash
python importar.py /caminho/para/sua/pasta/com/dados \
    --host localhost --port 5432 --db sigtap --user sigtap --password sigtap
```

O script:
- Detecta automaticamente se cada arquivo é UTF-8 ou Latin-1 (o padrão do
  SIGTAP é Latin-1/ISO-8859-1, então se a detecção falhar ele assume isso)
- Corta cada linha nas posições exatas definidas no layout
- Converte campos `NUMBER` para número e os demais para texto
- Usa `COPY` (rápido, mesmo para tabelas com muitas linhas, como
  `rl_procedimento_compativel` que costuma ter milhões)

### Testar com uma tabela só primeiro

Recomendo validar com uma tabela pequena antes de rodar tudo:

```bash
python importar.py /caminho/para/sua/pasta --apenas tb_financiamento \
    --host localhost --port 5432 --db sigtap --user sigtap --password sigtap
```

Depois confira no banco:

```bash
docker compose exec postgres psql -U sigtap -d sigtap -c "SELECT * FROM tb_financiamento LIMIT 5;"
```

Se os acentos estiverem corretos (ex: "Atenção Básica" e não algo
corrompido como "AtenÔÇÆo BÔÇísica"), pode rodar para todas as tabelas.

### Forçar um encoding específico

Se a detecção automática errar para algum arquivo específico:

```bash
python importar.py /caminho/para/sua/pasta --encoding latin-1 ...
```

## Passo 7 — Aplique as foreign keys (opcional)

O `schema.sql` gerado cria só as colunas, sem constraints de FK — isso é
proposital, porque criar as FKs antes de popular os dados pode falhar caso
a ordem de carga não respeite as dependências (ex: `rl_procedimento_cid`
referencia `tb_procedimento` e `tb_cid`).

Depois que TODAS as 48 tabelas estiverem carregadas, você pode adicionar as
FKs manualmente baseado nos seus arquivos de relacionamento. Se quiser, me
manda 2-3 exemplos dos arquivos de relacionamento (os 34 que você mencionou)
e eu gero um script automático de `ALTER TABLE ... ADD FOREIGN KEY` também,
do mesmo jeito que fiz para o DDL.

## Notas técnicas

- Os campos `DT_COMPETENCIA` (e similares tipados como `CHAR` no SIGTAP)
  foram mapeados para `VARCHAR`, não `DATE`, porque vêm no formato `AAAAMM`
  (ex: `202401`), que não é uma data válida sozinha (falta o dia). Se quiser,
  depois dá para converter para `DATE` fazendo `TO_DATE(dt_competencia || '01', 'YYYYMMDD')`.
- Os campos `NUMBER` foram mapeados para `NUMERIC` sem precisão fixa, porque
  o layout fornecido não especifica quantas casas decimais cada campo tem
  (ex: `VL_SH`, valores monetários, provavelmente têm 2 decimais, mas isso
  não está no layout — me avise se você tiver essa informação em algum outro
  lugar e eu ajusto).
- `CREATE TABLE IF NOT EXISTS` — rodar o `schema.sql` de novo não dá erro,
  mas também não atualiza uma tabela já existente. Se mudar o layout, dropar
  a tabela antes (`DROP TABLE tb_x;`) ou rodar `docker compose down -v` para
  resetar o banco do zero.
