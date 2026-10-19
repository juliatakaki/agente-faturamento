# Conferência de faturamento (front-end)

Tela para o faturista conferir os códigos SIGTAP sugeridos pelo pipeline. Mostra a
evolução com os trechos que justificam cada código grifados, e permite confirmar,
recusar, incluir itens da lista de conferência e incluir códigos novos a partir de
um trecho selecionado. As decisões podem ser exportadas em JSON.

A tela lê o JSON de saída do pipeline (`python src/agent/pipeline.py entrada.json saida.json`).
Não chama o pipeline nem nenhum servidor. O arquivo é aberto e processado só no navegador.

## Como rodar

Precisa do Node.js 18 ou mais novo.

    cd frontend
    npm install
    npm run dev

Abra http://localhost:5173 e clique em "Abrir relatórios", ou em "Ver com uma evolução
de exemplo" (texto fictício, em `public/exemplo.json`).

## Dados

- O texto das evoluções não é salvo no navegador. Só as decisões ficam guardadas
  (localStorage), associadas ao id do prontuário.
- O exemplo em `public/exemplo.json` é inventado. Não coloque JSON com evoluções
  reais dentro da pasta `frontend/`, para não irem para o git.

## Limitação atual

Para códigos que vêm de regra, o pipeline ainda não grava a posição exata da pista no
texto. A tela procura os termos principais da regra (em `src/lib/itens.ts`) e grifa o que
achar. Se o JSON trouxer o campo `evidencias` (início e fim) em cada código, a tela usa
essas posições no lugar.
