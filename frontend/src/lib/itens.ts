import type { Evidencia, Item, Manual, NaoRealizado, Relatorio } from "../types";

/**
 * Minúsculas e sem acento, mantendo o mesmo comprimento do texto original,
 * para que as posições encontradas valham também no texto exibido.
 */
export function normalizar(texto: string): string {
  let saida = "";
  for (const ch of texto) {
    const base = ch.normalize("NFKD").replace(/[̀-ͯ]/g, "") || ch;
    // um caractere vira exatamente um (ex.: "ß" ficaria com 2; corta)
    saida += base[0].toLowerCase()[0];
  }
  return saida;
}

/** Remove a pontuação do código para comparar ("04.01.01.001-5" -> "0401010015"). */
export function soDigitos(codigo: string): string {
  return (codigo || "").replace(/\D/g, "");
}

// Termos procurados no texto para cada código que vem de regra. O pipeline ainda
// não grava a posição exata da pista, então a tela procura os termos principais
// da regra (os mesmos de src/agent/regras_texto.py) e grifa o que achar.
const TERMOS_REGRA: Record<string, RegExp> = {
  "0401010015": /\bcurativos?\b|\bclorexidina\b|\boclu(o|sao|ido)\b/g,
  "0302040021": /\bfisioterapia respiratoria\b|\bmonitorizacao ventilatoria\b/g,
  "0302050027": /\bfisioterapia motora\b|\bcinesioterapia\b|\bsedestacao\b|\bmobilizacao\b/g,
  "0211080020": /\bgasometria\b|\bgas[ao]\b|\bpao2\b|\bpaco2\b|\bhco3\b/g,
  "0305010131": /\bhd\b|\b(hemo)?dialise\b|\buf\b|\btrs\b/g,
  "0301100071": /\btqt\b|\btraqueostomi\w*/g,
  "0309010047": /\bsne\b|\bgtt\b|\bdieta enteral\b|\btne\b|\bterapia nutricional\b/g,
  "0301100144": /\bvm\b|\bventilacao mecanica\b|\bfio2\b|\bcateter nasal\b|\btot\b|\btqt\b/g,
};

/** Posições de todas as ocorrências de uma regex no texto normalizado. */
function buscarRegex(textoNorm: string, rx: RegExp): Evidencia[] {
  const saida: Evidencia[] = [];
  const re = new RegExp(rx.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(textoNorm)) !== null) {
    if (m[0].length === 0) {
      re.lastIndex++;
      continue;
    }
    saida.push({ inicio: m.index, fim: m.index + m[0].length });
  }
  return saida;
}

/** Posições de um termo literal (sem acento, sem diferença de maiúsculas). */
function buscarTermo(textoNorm: string, termo: string): Evidencia[] {
  const t = normalizar(termo.trim());
  if (t.length < 2) return [];
  const saida: Evidencia[] = [];
  let i = textoNorm.indexOf(t);
  while (i !== -1) {
    saida.push({ inicio: i, fim: i + t.length });
    i = textoNorm.indexOf(t, i + t.length);
  }
  return saida;
}

/** Primeira linha com conteúdo: é o cabeçalho que a regra de documento lê. */
function cabecalho(texto: string): Evidencia[] {
  const m = /\S[^\n]*/.exec(texto);
  return m ? [{ inicio: m.index, fim: m.index + m[0].length }] : [];
}

function evidencias(texto: string, textoNorm: string, codigo: string, origem: string, nivel: string): Evidencia[] {
  if (nivel === "regra_documento") return cabecalho(texto);
  const porRegra = TERMOS_REGRA[soDigitos(codigo)];
  if (nivel.startsWith("regra_texto") && porRegra) return buscarRegex(textoNorm, porRegra);
  if (origem && !origem.startsWith("[")) {
    const achados = buscarTermo(textoNorm, origem);
    if (achados.length) return achados;
  }
  return porRegra ? buscarRegex(textoNorm, porRegra) : [];
}

function tipoPorNivel(nivel: string): Item["tipo"] {
  if (nivel === "regra_documento") return "documento";
  if (nivel === "regra_texto_confirmada") return "regra_ia";
  if (nivel === "regra_texto") return "regra";
  return "ia";
}

const DETALHE: Record<Item["tipo"], string> = {
  documento: "Regra do tipo de nota",
  regra: "Regra de texto",
  regra_ia: "Regra de texto confirmada pela IA",
  ia: "Encontrado pela IA na busca do SIGTAP",
  revisao: "Para conferir",
  manual: "Incluído na conferência",
};

export function rotuloTipo(tipo: Item["tipo"]): string {
  return DETALHE[tipo];
}

/** Monta os itens da tela a partir do relatório do pipeline e dos códigos incluídos à mão. */
export function montarItens(rel: Relatorio, manuais: Manual[]): { sugeridos: Item[]; revisao: Item[] } {
  const texto = rel.texto_prontuario || "";
  const textoNorm = normalizar(texto);

  const sugeridos: Item[] = (rel.codigos_sigtap || []).map((c, i) => {
    const nivel = c.nivel || "";
    const tipo = tipoPorNivel(nivel);
    const origem = c.origem || "";
    return {
      id: `s${i}-${soDigitos(c.codigo)}`,
      codigo: c.codigo,
      descricao: c.descricao,
      tipo,
      detalhe: tipo === "ia" && origem ? `IA encontrou "${origem}"` : DETALHE[tipo],
      confianca: c.confianca,
      valor: c.vl_total,
      alternativas: c.alternativas,
      trechos: c.evidencias?.length ? c.evidencias : evidencias(texto, textoNorm, c.codigo, origem, nivel),
    };
  });

  const revisao: Item[] = (rel.candidatos_regra || []).map((c, i) => ({
    id: `r${i}-${soDigitos(c.codigo)}`,
    codigo: c.codigo,
    descricao: c.descricao,
    tipo: "revisao",
    detalhe: DETALHE.revisao,
    motivo: c.motivo || "A regra de texto encontrou indícios, mas a IA não confirmou que foi feito neste dia.",
    trechos: evidencias(texto, textoNorm, c.codigo, "", "regra_texto"),
  }));

  for (const m of manuais) {
    sugeridos.push({
      id: m.id,
      codigo: m.codigo,
      descricao: m.descricao,
      tipo: "manual",
      detalhe: DETALHE.manual,
      trechos: [{ inicio: m.inicio, fim: m.fim }],
    });
  }

  return { sugeridos, revisao };
}

export function naoRealizados(rel: Relatorio): NaoRealizado[] {
  return (rel.termos_nao_realizados || []).map((t) => (typeof t === "string" ? { texto: t } : t));
}

export function formatarReais(valor?: number): string {
  if (valor === undefined || valor === null) return "";
  return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
