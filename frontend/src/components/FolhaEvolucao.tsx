import { useMemo, useRef } from "react";
import type { Decisao, Item } from "../types";

interface Props {
  texto: string;
  itens: Item[];
  decisoes: Record<string, Decisao>;
  selecionado: string | null;
  onSelecionar: (id: string) => void;
  onSelecaoTexto: (sel: { inicio: number; fim: number; trecho: string } | null) => void;
}

interface Segmento {
  inicio: number;
  fim: number;
  ids: string[];
}

/** Divide o texto em pedaços contíguos com o mesmo conjunto de itens grifados. */
function segmentar(texto: string, itens: Item[]): Segmento[] {
  const cobertura: string[][] = Array.from({ length: texto.length }, () => []);
  for (const item of itens) {
    for (const t of item.trechos) {
      for (let i = Math.max(0, t.inicio); i < Math.min(texto.length, t.fim); i++) {
        cobertura[i].push(item.id);
      }
    }
  }
  const segs: Segmento[] = [];
  let ini = 0;
  for (let i = 1; i <= texto.length; i++) {
    if (i === texto.length || cobertura[i].join("|") !== cobertura[ini].join("|")) {
      segs.push({ inicio: ini, fim: i, ids: cobertura[ini] });
      ini = i;
    }
  }
  return segs;
}

export function FolhaEvolucao({ texto, itens, decisoes, selecionado, onSelecionar, onSelecaoTexto }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const segmentos = useMemo(() => segmentar(texto, itens), [texto, itens]);
  const porId = useMemo(() => Object.fromEntries(itens.map((i) => [i.id, i])), [itens]);

  function classe(ids: string[]): string {
    if (!ids.length) return "";
    if (selecionado && ids.includes(selecionado)) return "grifo grifo-ativo";
    const vivos = ids.filter((id) => decisoes[id] !== "recusado");
    if (!vivos.length) return "grifo grifo-recusado";
    if (vivos.every((id) => porId[id]?.tipo === "revisao" && decisoes[id] !== "aceito")) {
      return "grifo grifo-revisao";
    }
    return "grifo";
  }

  // Converte a seleção do usuário em posições no texto original, usando o
  // data-inicio de cada pedaço.
  function aoSoltar() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !ref.current) {
      onSelecaoTexto(null);
      return;
    }
    const pos = (no: Node | null, deslocamento: number): number | null => {
      const el = no?.nodeType === Node.TEXT_NODE ? no.parentElement : (no as HTMLElement | null);
      const span = el?.closest<HTMLElement>("[data-inicio]");
      if (!span || !ref.current?.contains(span)) return null;
      return Number(span.dataset.inicio) + deslocamento;
    };
    const a = pos(sel.anchorNode, sel.anchorOffset);
    const b = pos(sel.focusNode, sel.focusOffset);
    if (a === null || b === null || a === b) {
      onSelecaoTexto(null);
      return;
    }
    const inicio = Math.min(a, b);
    const fim = Math.max(a, b);
    onSelecaoTexto({ inicio, fim, trecho: texto.slice(inicio, fim) });
  }

  if (!texto) {
    return <p className="folha-vazia">Este relatório não traz o texto da evolução.</p>;
  }

  return (
    <div className="folha" ref={ref} onMouseUp={aoSoltar} onKeyUp={aoSoltar}>
      {segmentos.map((s) => {
        const pedaco = texto.slice(s.inicio, s.fim);
        if (!s.ids.length) {
          return (
            <span key={s.inicio} data-inicio={s.inicio}>
              {pedaco}
            </span>
          );
        }
        const nomes = s.ids.map((id) => porId[id]?.descricao).filter(Boolean).join("; ");
        return (
          <mark
            key={s.inicio}
            data-inicio={s.inicio}
            className={classe(s.ids)}
            title={nomes}
            onClick={() => {
              // clicar de novo no mesmo trecho passa para o próximo código dele
              const atual = selecionado ? s.ids.indexOf(selecionado) : -1;
              onSelecionar(s.ids[(atual + 1) % s.ids.length]);
            }}
          >
            {pedaco}
          </mark>
        );
      })}
    </div>
  );
}
