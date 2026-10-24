import type { Decisao, Manual, Relatorio } from "../types";
import {
  compararGabarito,
  formatarPct,
  formatarReais,
  metricas,
  metricasDoConjunto,
  resumoEvolucao,
  rotuloTipo,
  ROTULO_DECISAO,
} from "../lib/itens";

interface Props {
  relatorios: Relatorio[];
  decisoes: Record<string, Record<string, Decisao>>;
  manuais: Record<string, Manual[]>;
}

/**
 * Relatório para papel, só com tabelas (sem o texto das evoluções). Fica
 * escondido na tela e só aparece na impressão (ver @media print em styles.css).
 */
export function Impressao({ relatorios, decisoes, manuais }: Props) {
  const data = new Date().toLocaleString("pt-BR");
  const resumos = relatorios.map((r) => ({
    rel: r,
    ...resumoEvolucao(r, manuais[r.prontuario_id] || [], decisoes[r.prontuario_id] || {}),
  }));
  const qtdTotal = resumos.reduce((s, r) => s + r.quantidade, 0);
  const valorTotal = resumos.reduce((s, r) => s + r.valor, 0);
  const conjunto = metricasDoConjunto(relatorios);

  return (
    <div className="impressao">
      <header className="imp-capa">
        <h1>Conferência de faturamento</h1>
        <p>
          {relatorios.length} evolução(ões). Gerado em {data}. Valores considerando as decisões da conferência.
        </p>
      </header>

      <h2 className="imp-titulo">Sintético</h2>
      <table className="imp-tabela imp-sintetico">
        <thead>
          <tr>
            <th>Evolução</th>
            <th className="num">Itens identificados</th>
            <th className="num">Valor</th>
          </tr>
        </thead>
        <tbody>
          {resumos.map((r) => (
            <tr key={r.rel.prontuario_id}>
              <td>{r.rel.prontuario_id}</td>
              <td className="num">{r.quantidade}</td>
              <td className="num">{formatarReais(r.valor)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Total</td>
            <td className="num">{qtdTotal}</td>
            <td className="num">{formatarReais(valorTotal)}</td>
          </tr>
        </tfoot>
      </table>

      {conjunto && (
        <>
          <h2 className="imp-titulo">Comparação com o gabarito</h2>
          <table className="imp-tabela imp-sintetico">
            <thead>
              <tr>
                <th>Evolução</th>
                <th className="num">Acertos</th>
                <th className="num">Sugeridos a mais</th>
                <th className="num">Não encontrados</th>
                <th className="num">Sugestões certas</th>
                <th className="num">Itens encontrados</th>
                <th className="num">Nota geral</th>
              </tr>
            </thead>
            <tbody>
              {relatorios.map((r) => {
                const c = compararGabarito(r);
                if (!c) return null;
                const m = metricas(c);
                return (
                  <tr key={r.prontuario_id}>
                    <td>{r.prontuario_id}</td>
                    <td className="num">{m.acertos}</td>
                    <td className="num">{m.aMais}</td>
                    <td className="num">{m.faltaram}</td>
                    <td className="num">{formatarPct(m.precisao)}</td>
                    <td className="num">{formatarPct(m.recall)}</td>
                    <td className="num">{formatarPct(m.f1)}</td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <td>Total</td>
                <td className="num">{conjunto.acertos}</td>
                <td className="num">{conjunto.aMais}</td>
                <td className="num">{conjunto.faltaram}</td>
                <td className="num">{formatarPct(conjunto.precisao)}</td>
                <td className="num">{formatarPct(conjunto.recall)}</td>
                <td className="num">{formatarPct(conjunto.f1)}</td>
              </tr>
            </tfoot>
          </table>
          <p className="imp-nota">
            Compara o que o sistema sugeriu com o gabarito (os códigos marcados por quem conferiu a evolução), só nos
            códigos avaliados no estudo. Sugestões certas é quanto do que o sistema sugeriu estava no gabarito. Itens
            encontrados é quanto do gabarito o sistema achou. Nota geral é o equilíbrio entre os dois. As decisões da
            conferência não mudam esses números.
          </p>
        </>
      )}

      <h2 className="imp-titulo">Itens por evolução</h2>
      {resumos.map((r) => (
        <section key={r.rel.prontuario_id} className="imp-evolucao">
          <h3>Evolução {r.rel.prontuario_id}</h3>
          <table className="imp-tabela">
            <thead>
              <tr>
                <th>Código</th>
                <th>Procedimento</th>
                <th>Origem</th>
                <th>Decisão</th>
                <th className="num">Valor</th>
              </tr>
            </thead>
            <tbody>
              {r.linhas.length === 0 ? (
                <tr>
                  <td colSpan={5}>Nenhum código do escopo.</td>
                </tr>
              ) : (
                r.linhas.map((l) => (
                  <tr key={l.item.id} className={l.entra ? "" : "imp-fora"}>
                    <td className="num">{l.item.codigo}</td>
                    <td>{l.item.descricao}</td>
                    <td>{rotuloTipo(l.item.tipo)}</td>
                    <td>{ROTULO_DECISAO[l.decisao]}</td>
                    <td className="num">{formatarReais(l.item.valor)}</td>
                  </tr>
                ))
              )}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4}>
                  {r.quantidade} item(ns) no valor
                </td>
                <td className="num">{formatarReais(r.valor)}</td>
              </tr>
            </tfoot>
          </table>
        </section>
      ))}
    </div>
  );
}
