import type { Decisao, Evidencia, Item, Manual, NaoRealizado, Relatorio } from "../types";
import { procedimento } from "./sigtap";

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

// Códigos que o estudo avalia: os 11 extraíveis do texto, os processos e a
// oxigenoterapia. O resto (exames de laboratório e imagem, medicamentos,
// materiais) aparece separado, porque o anotador quase nunca marca esses códigos.
export const CODIGOS_DO_ESCOPO = new Set([
  "0309010047", "0401010015", "0211080020", "0302040021", "0302050027", "0301100071",
  "0305010131", "0301100055", "0309010101", "0211020036", "0214010015",
  "0802010083", "0301010170", "0301010048", "0201020041", "0301100144",
]);

export function noEscopo(codigo: string): boolean {
  return CODIGOS_DO_ESCOPO.has(soDigitos(codigo));
}

/**
 * Exame fora do escopo: grupo 02 do SIGTAP (laboratório, imagem, métodos
 * gráficos). Gasometria, ECG e glicemia são do grupo 02, mas estão no escopo.
 */
export function ehExame(codigo: string): boolean {
  const d = soDigitos(codigo);
  return d.startsWith("02") && !CODIGOS_DO_ESCOPO.has(d);
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

/**
 * Posições de um termo (sem acento, sem diferença de maiúsculas), só como
 * palavra inteira: "sódio" não pode casar dentro de "episódios".
 */
function buscarTermo(textoNorm: string, termo: string): Evidencia[] {
  const t = normalizar(termo.trim());
  if (t.length < 2) return [];
  const escapado = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return buscarRegex(textoNorm, new RegExp(`(?<![a-z0-9])${escapado}(?![a-z0-9])`, "g"));
}

/** Primeira linha com conteúdo: é o cabeçalho que a regra de documento lê. */
function cabecalho(texto: string): Evidencia[] {
  const m = /\S[^\n]*/.exec(texto);
  return m ? [{ inicio: m.index, fim: m.index + m[0].length }] : [];
}

// Palavras genéricas demais para localizar um termo sozinhas.
const PALAVRAS_VAZIAS = new Set([
  "dosagem", "exame", "exames", "pesquisa", "determinacao", "contagem", "avaliacao", "paciente", "pacientes",
  "procedimento", "tratamento", "outros", "outras", "sangue", "serico", "serica", "total", "para", "com", "sem",
]);

function evidencias(texto: string, textoNorm: string, codigo: string, origem: string, nivel: string): Evidencia[] {
  if (nivel === "regra_documento") return cabecalho(texto);
  const porRegra = TERMOS_REGRA[soDigitos(codigo)];
  if (nivel.startsWith("regra_texto") && porRegra) return buscarRegex(textoNorm, porRegra);
  if (origem && !origem.startsWith("[")) {
    const achados = buscarTermo(textoNorm, origem);
    if (achados.length) return achados;
    // A IA às vezes devolve o termo reescrito ("dosagem de potássio" para
    // "potássio 3,8"). Tenta as palavras principais do termo, da mais longa
    // para a mais curta, e fica com a primeira que aparecer no texto.
    const palavras = normalizar(origem)
      .split(/[^a-z0-9]+/)
      .filter((w) => w.length >= 4 && !PALAVRAS_VAZIAS.has(w))
      .sort((x, y) => y.length - x.length);
    for (const w of palavras) {
      const porPalavra = buscarTermo(textoNorm, w);
      if (porPalavra.length) return porPalavra;
    }
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

const SEM_DESCRICAO = "(descrição não disponível)";

/** Descrição do relatório; se faltar, a da tabela do SIGTAP. */
export function descricaoDe(codigo: string, descricao?: string): string {
  if (descricao && descricao !== SEM_DESCRICAO) return descricao;
  return procedimento(soDigitos(codigo))?.n || descricao || SEM_DESCRICAO;
}

/**
 * Valor do relatório; se vier vazio ou zerado, o da tabela do SIGTAP. Os
 * arquivos montados da avaliação (etapa 4) não guardam valor.
 */
function valorDe(codigo: string, valor?: number): number | undefined {
  if (valor) return valor;
  return procedimento(soDigitos(codigo))?.v ?? valor;
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
      descricao: descricaoDe(c.codigo, c.descricao),
      tipo,
      detalhe: tipo === "ia" && origem ? `IA encontrou "${origem}"` : DETALHE[tipo],
      confianca: c.confianca,
      valor: valorDe(c.codigo, c.vl_total),
      alternativas: c.alternativas,
      trechos: c.evidencias?.length ? c.evidencias : evidencias(texto, textoNorm, c.codigo, origem, nivel),
      foraEscopo: !noEscopo(c.codigo),
      exame: ehExame(c.codigo),
    };
  });

  const revisao: Item[] = (rel.candidatos_regra || []).map((c, i) => ({
    id: `r${i}-${soDigitos(c.codigo)}`,
    codigo: c.codigo,
    descricao: descricaoDe(c.codigo, c.descricao),
    tipo: "revisao",
    detalhe: DETALHE.revisao,
    motivo: c.motivo || "A regra de texto encontrou indícios, mas a IA não confirmou que foi feito neste dia.",
    valor: valorDe(c.codigo, c.vl_total),
    trechos: evidencias(texto, textoNorm, c.codigo, "", "regra_texto"),
  }));

  for (const m of manuais) {
    sugeridos.push({
      id: m.id,
      codigo: m.codigo,
      descricao: m.descricao,
      tipo: "manual",
      detalhe: DETALHE.manual,
      valor: valorDe(m.codigo),
      trechos: [{ inicio: m.inicio, fim: m.fim }],
    });
  }

  return { sugeridos, revisao };
}

/**
 * Compara o que o sistema sugeriu com o que o anotador marcou, só nos códigos
 * do escopo. Usa a saída do sistema como veio, sem as decisões da conferência.
 * "Para conferir" não conta como sugestão, porque fica fora do valor.
 */
export function compararGabarito(rel: Relatorio): { acertos: number; aMais: number; faltaram: number } | null {
  if (!rel.codigos_gabarito) return null;
  const sistema = new Set(
    (rel.codigos_sigtap || []).map((c) => soDigitos(c.codigo)).filter((c) => CODIGOS_DO_ESCOPO.has(c)),
  );
  const anotador = new Set(
    rel.codigos_gabarito.map((g) => soDigitos(g.codigo)).filter((c) => CODIGOS_DO_ESCOPO.has(c)),
  );
  let acertos = 0;
  sistema.forEach((c) => {
    if (anotador.has(c)) acertos++;
  });
  return { acertos, aMais: sistema.size - acertos, faltaram: anotador.size - acertos };
}

export interface Metricas {
  acertos: number;
  aMais: number;
  faltaram: number;
  precisao: number | null; // do que o sistema sugeriu, quanto estava certo
  recall: number | null; // do que o anotador marcou, quanto o sistema achou
  f1: number | null;
}

export function metricas(c: { acertos: number; aMais: number; faltaram: number }): Metricas {
  const sugeridos = c.acertos + c.aMais;
  const marcados = c.acertos + c.faltaram;
  const precisao = sugeridos ? c.acertos / sugeridos : null;
  const recall = marcados ? c.acertos / marcados : null;
  const f1 = precisao !== null && recall !== null && precisao + recall > 0 ? (2 * precisao * recall) / (precisao + recall) : null;
  return { ...c, precisao, recall, f1 };
}

/** Métricas somando as evoluções abertas que têm gabarito. Null se nenhuma tem. */
export function metricasDoConjunto(relatorios: Relatorio[]): (Metricas & { evolucoes: number }) | null {
  const t = { acertos: 0, aMais: 0, faltaram: 0 };
  let evolucoes = 0;
  for (const r of relatorios) {
    const c = compararGabarito(r);
    if (!c) continue;
    t.acertos += c.acertos;
    t.aMais += c.aMais;
    t.faltaram += c.faltaram;
    evolucoes++;
  }
  return evolucoes ? { ...metricas(t), evolucoes } : null;
}

export function formatarPct(v: number | null): string {
  return v === null ? "sem dado" : `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`;
}

export const ROTULO_DECISAO: Record<string, string> = {
  pendente: "A conferir",
  aceito: "Confirmado",
  recusado: "Recusado",
  incluido: "Incluído na conferência",
};

export interface LinhaConta {
  item: Item;
  decisao: "pendente" | "aceito" | "recusado" | "incluido";
  entra: boolean; // entra no valor
}

/**
 * Itens do escopo de uma evolução com a decisão de cada um, e quantos e quanto
 * entram na conta. Sugestões entram a não ser que sejam recusadas; itens "para
 * conferir" só entram se forem incluídos; os incluídos à mão sempre entram.
 */
export function resumoEvolucao(rel: Relatorio, manuais: Manual[], dec: Record<string, Decisao>) {
  const { sugeridos, revisao } = montarItens(rel, manuais);
  const linhas: LinhaConta[] = [...sugeridos.filter((i) => !i.foraEscopo), ...revisao].map((item) => {
    const d = item.tipo === "manual" ? "incluido" : dec[item.id] || "pendente";
    const entra = item.tipo === "revisao" ? d === "aceito" : d !== "recusado";
    return { item, decisao: d, entra };
  });
  const naConta = linhas.filter((l) => l.entra);
  return {
    linhas,
    quantidade: naConta.length,
    valor: naConta.reduce((s, l) => s + (l.item.valor || 0), 0),
  };
}

/** Exames fora do escopo de uma evolução, com a decisão de cada um. */
export function examesEvolucao(rel: Relatorio, dec: Record<string, Decisao>) {
  const { sugeridos } = montarItens(rel, []);
  return sugeridos
    .filter((i) => i.exame)
    .map((item) => {
      const d = dec[item.id] || "pendente";
      return { item, decisao: d, entra: d !== "recusado" };
    });
}

export function naoRealizados(rel: Relatorio): NaoRealizado[] {
  return (rel.termos_nao_realizados || []).map((t) => (typeof t === "string" ? { texto: t } : t));
}

export function formatarReais(valor?: number): string {
  if (valor === undefined || valor === null) return "";
  return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
