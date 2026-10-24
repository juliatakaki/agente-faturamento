import { normalizar } from "./itens";

// Tabela do SIGTAP para a tela (public/sigtap.json, gerado por
// src/analise/gerar_sigtap_frontend.py). Serve para buscar procedimentos na
// inclusão manual e para completar descrição e valor quando o relatório não traz.

export interface Procedimento {
  c: string; // código só com dígitos
  n: string; // nome
  v: number; // valor total (SH + SA + SP), em R$
}

interface Indexado extends Procedimento {
  busca: string; // nome normalizado
}

let tabela: Indexado[] = [];
let porCodigo = new Map<string, Indexado>();

export async function carregarSigtap(): Promise<boolean> {
  try {
    const r = await fetch(`${import.meta.env.BASE_URL}sigtap.json`);
    if (!r.ok) return false;
    const dados: Procedimento[] = await r.json();
    tabela = dados.map((p) => ({ ...p, busca: normalizar(p.n) }));
    porCodigo = new Map(tabela.map((p) => [p.c, p]));
    return tabela.length > 0;
  } catch {
    return false;
  }
}

export function procedimento(digitos: string): Procedimento | undefined {
  return porCodigo.get(digitos);
}

export function formatarCodigo(digitos: string): string {
  return digitos.length === 10
    ? `${digitos.slice(0, 2)}.${digitos.slice(2, 4)}.${digitos.slice(4, 6)}.${digitos.slice(6, 9)}-${digitos[9]}`
    : digitos;
}

/**
 * O termo aparece no nome? Um caractere estragado no arquivo (o "�" de
 * acento perdido) vale como qualquer letra, para "avaliacao" achar "AVALIA��O".
 */
function contem(nome: string, termo: string): boolean {
  if (!nome.includes("�")) return nome.includes(termo);
  for (let i = 0; i + termo.length <= nome.length; i++) {
    let ok = true;
    for (let k = 0; k < termo.length; k++) {
      const ch = nome[i + k];
      if (ch !== termo[k] && ch !== "�") {
        ok = false;
        break;
      }
    }
    if (ok) return true;
  }
  return false;
}

/**
 * Busca por código (com ou sem pontos, inteiro ou o começo) ou por palavras do
 * nome, em qualquer ordem. Nomes que começam com o termo vêm primeiro.
 */
export function buscarProcedimentos(consulta: string, limite = 30): Procedimento[] {
  const q = normalizar(consulta.trim());
  if (!q) return [];
  const digitos = q.replace(/[\s.\-/]/g, "");
  if (/^\d+$/.test(digitos)) {
    return tabela.filter((p) => p.c.startsWith(digitos)).slice(0, limite);
  }
  const termos = q.split(/\s+/).filter(Boolean);
  const achados = tabela.filter((p) => termos.every((t) => contem(p.busca, t)));
  achados.sort((a, b) => Number(!a.busca.startsWith(termos[0])) - Number(!b.busca.startsWith(termos[0])));
  return achados.slice(0, limite);
}
