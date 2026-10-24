// Formato do JSON gerado pelo pipeline (src/agent/pipeline.py, nó de relatório).
// Só os campos que a tela usa; o resto do JSON é ignorado.

export interface Alternativa {
  codigo: string;
  descricao: string;
  vl_total?: number;
}

export interface Evidencia {
  inicio: number;
  fim: number;
}

export interface CodigoSigtap {
  codigo: string;
  descricao: string;
  origem?: string; // termo buscado, ou "[regra ...]" quando veio de regra
  nivel?: string; // nivel0..nivel4, regra_documento, regra_texto, regra_texto_confirmada
  confianca?: string; // alta | media | baixa
  vl_total?: number;
  alternativas?: Alternativa[];
  pistas_regra?: string[];
  evidencias?: Evidencia[]; // posições no texto, quando o pipeline as grava
}

export interface Candidato {
  codigo: string;
  descricao: string;
  vl_total?: number;
  score?: number;
  limiar?: number;
  pistas?: string[];
  motivo?: string;
}

export interface NaoRealizado {
  texto: string;
  categoria?: string;
  motivo?: string;
}

export interface CodigoGabarito {
  codigo: string;
  descricao?: string;
}

export interface Relatorio {
  prontuario_id: string;
  // Só nos arquivos montados a partir da avaliação: o que o anotador marcou.
  codigos_gabarito?: CodigoGabarito[];
  anotador?: string;
  texto_prontuario?: string;
  modelo_utilizado?: string;
  falha_extracao?: string;
  codigos_sigtap?: CodigoSigtap[];
  candidatos_regra?: Candidato[];
  termos_nao_realizados?: (NaoRealizado | string)[];
  termos_nao_encontrados?: string[];
  termos_ambiguos?: string[];
}

export type Decisao = "pendente" | "aceito" | "recusado";

export type TipoOrigem = "documento" | "regra" | "regra_ia" | "ia" | "revisao" | "manual";

// Um código na tela, venha ele das sugestões, da lista de revisão ou do faturista.
export interface Item {
  id: string;
  codigo: string;
  descricao: string;
  tipo: TipoOrigem;
  detalhe: string; // de onde veio, em linguagem simples
  confianca?: string;
  valor?: number;
  motivo?: string;
  alternativas?: Alternativa[];
  trechos: Evidencia[]; // onde está a evidência no texto
  foraEscopo?: boolean; // exames, medicamentos, materiais etc., fora do que o estudo avalia
  exame?: boolean; // fora do escopo e do grupo 02 do SIGTAP (procedimentos com finalidade diagnóstica)
}

export interface Manual {
  id: string;
  codigo: string;
  descricao: string;
  inicio: number;
  fim: number;
}

export interface Estado {
  relatorios: Relatorio[];
  atual: number;
  decisoes: Record<string, Record<string, Decisao>>; // prontuario_id -> item id -> decisão
  manuais: Record<string, Manual[]>; // prontuario_id -> códigos incluídos à mão
}
