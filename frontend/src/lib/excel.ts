import type { Decisao, Manual, Relatorio } from "../types";
import { examesEvolucao, compararGabarito, metricas, metricasDoConjunto, resumoEvolucao, rotuloTipo, ROTULO_DECISAO, soDigitos } from "./itens";

/**
 * Planilha da conferência com as abas Sintético (uma linha por evolução),
 * Itens (uma linha por código, com o número da evolução) e, quando o arquivo
 * traz gabarito, Métricas. Gera tudo no navegador.
 */
export async function exportarExcel(
  relatorios: Relatorio[],
  decisoes: Record<string, Record<string, Decisao>>,
  manuais: Record<string, Manual[]>,
) {
  const XLSX = await import("xlsx");
  const temGabarito = relatorios.some((r) => r.codigos_gabarito);

  const sintetico: (string | number)[][] = [["Evolução", "Itens identificados", "Valor (R$)"]];
  const itens: (string | number)[][] = [
    ["Evolução", "Código", "Procedimento", "Origem", "Decisão", "Entra no valor", "Valor (R$)"].concat(
      temGabarito ? ["Marcado pelo anotador"] : [],
    ),
  ];
  let qtdTotal = 0;
  let valorTotal = 0;

  for (const r of relatorios) {
    const id = r.prontuario_id;
    const res = resumoEvolucao(r, manuais[id] || [], decisoes[id] || {});
    const gab = r.codigos_gabarito ? new Set(r.codigos_gabarito.map((g) => soDigitos(g.codigo))) : null;
    sintetico.push([id, res.quantidade, round2(res.valor)]);
    qtdTotal += res.quantidade;
    valorTotal += res.valor;
    for (const l of res.linhas) {
      const linha: (string | number)[] = [
        id,
        l.item.codigo,
        l.item.descricao,
        rotuloTipo(l.item.tipo),
        ROTULO_DECISAO[l.decisao],
        l.entra ? "Sim" : "Não",
        round2(l.item.valor || 0),
      ];
      if (gab) linha.push(gab.has(soDigitos(l.item.codigo)) ? "Sim" : "Não");
      else if (temGabarito) linha.push("");
      itens.push(linha);
    }
  }
  sintetico.push(["Total", qtdTotal, round2(valorTotal)]);

  const livro = XLSX.utils.book_new();
  const abaSint = XLSX.utils.aoa_to_sheet(sintetico);
  abaSint["!cols"] = [{ wch: 12 }, { wch: 20 }, { wch: 14 }];
  XLSX.utils.book_append_sheet(livro, abaSint, "Sintético");

  const abaItens = XLSX.utils.aoa_to_sheet(itens);
  abaItens["!cols"] = [{ wch: 10 }, { wch: 15 }, { wch: 60 }, { wch: 34 }, { wch: 22 }, { wch: 14 }, { wch: 12 }, { wch: 22 }];
  abaItens["!autofilter"] = { ref: `A1:${temGabarito ? "H" : "G"}${itens.length}` };
  XLSX.utils.book_append_sheet(livro, abaItens, "Itens");

  const exames: (string | number)[][] = [["Evolução", "Código", "Exame", "Decisão", "Valor (R$)"]];
  for (const r of relatorios) {
    for (const l of examesEvolucao(r, decisoes[r.prontuario_id] || {})) {
      exames.push([r.prontuario_id, l.item.codigo, l.item.descricao, ROTULO_DECISAO[l.decisao], round2(l.item.valor || 0)]);
    }
  }
  const abaExames = XLSX.utils.aoa_to_sheet(exames);
  abaExames["!cols"] = [{ wch: 10 }, { wch: 15 }, { wch: 60 }, { wch: 14 }, { wch: 12 }];
  abaExames["!autofilter"] = { ref: `A1:E${exames.length}` };
  for (let lin = 2; lin <= exames.length; lin++) {
    const cel = abaExames[`E${lin}`];
    if (cel && typeof cel.v === "number") cel.z = '"R$" #,##0.00';
  }
  XLSX.utils.book_append_sheet(livro, abaExames, "Exames");

  if (temGabarito) {
    const met: (string | number)[][] = [["Evolução", "Acertos", "Sugeridos a mais", "Não encontrados", "Sugestões certas", "Itens encontrados", "Nota geral"]];
    for (const r of relatorios) {
      const c = compararGabarito(r);
      if (!c) continue;
      const m = metricas(c);
      met.push([r.prontuario_id, m.acertos, m.aMais, m.faltaram, pct(m.precisao), pct(m.recall), pct(m.f1)]);
    }
    const t = metricasDoConjunto(relatorios);
    if (t) met.push(["Total", t.acertos, t.aMais, t.faltaram, pct(t.precisao), pct(t.recall), pct(t.f1)]);
    met.push([]);
    met.push(["Compara o que o sistema sugeriu com o gabarito (os códigos marcados por quem conferiu a evolução), só nos códigos avaliados no estudo."]);
    met.push(["Acertos: o sistema sugeriu e estava no gabarito. Sugeridos a mais: o sistema sugeriu e não estava. Não encontrados: estava no gabarito e o sistema não sugeriu."]);
    met.push(["Sugestões certas: de tudo que o sistema sugeriu, quanto estava no gabarito."]);
    met.push(["Itens encontrados: de tudo que estava no gabarito, quanto o sistema achou."]);
    met.push(["Nota geral: equilíbrio entre as duas porcentagens (média harmônica, F1)."]);
    met.push(["As decisões tomadas na tela de conferência não mudam esses números."]);
    const abaMet = XLSX.utils.aoa_to_sheet(met);
    abaMet["!cols"] = [{ wch: 12 }, { wch: 9 }, { wch: 17 }, { wch: 16 }, { wch: 17 }, { wch: 18 }, { wch: 12 }];
    // percentuais como número, formatados
    for (let lin = 1; lin < met.length; lin++) {
      for (const col of ["E", "F", "G"]) {
        const cel = abaMet[`${col}${lin + 1}`];
        if (cel && typeof cel.v === "number") cel.z = "0%";
      }
    }
    XLSX.utils.book_append_sheet(livro, abaMet, "Métricas");
  }

  // valores em reais com duas casas
  for (const [aba, col] of [[abaSint, "C"], [abaItens, "G"]] as const) {
    const linhas = aba === abaSint ? sintetico.length : itens.length;
    for (let lin = 2; lin <= linhas; lin++) {
      const cel = aba[`${col}${lin}`];
      if (cel && typeof cel.v === "number") cel.z = '"R$" #,##0.00';
    }
  }

  XLSX.writeFile(livro, "conferencia_faturamento.xlsx");
}

function round2(v: number): number {
  return Math.round(v * 100) / 100;
}

function pct(v: number | null): number | string {
  return v === null ? "" : Math.round(v * 1000) / 1000;
}
