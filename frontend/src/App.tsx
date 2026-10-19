import { useEffect, useMemo, useState } from "react";
import type { Decisao, Estado, Manual, Relatorio } from "./types";
import { montarItens, naoRealizados, soDigitos } from "./lib/itens";
import { FolhaEvolucao } from "./components/FolhaEvolucao";
import { PainelCodigos } from "./components/PainelCodigos";

// Só as decisões ficam guardadas no navegador. O texto das evoluções não é
// guardado: ao recarregar a página, os relatórios precisam ser abertos de novo.
const CHAVE = "conferencia-faturamento-v1";

function lerDecisoes(): Pick<Estado, "decisoes" | "manuais"> {
  try {
    const bruto = localStorage.getItem(CHAVE);
    if (bruto) return JSON.parse(bruto);
  } catch {
    /* navegador sem armazenamento: começa vazio */
  }
  return { decisoes: {}, manuais: {} };
}

function lerArquivo(arquivo: File): Promise<Relatorio[]> {
  return arquivo.text().then((t) => {
    const dado = JSON.parse(t);
    const lista = Array.isArray(dado) ? dado : [dado];
    return lista.filter((r) => r && typeof r === "object" && "prontuario_id" in r) as Relatorio[];
  });
}

export default function App() {
  const [relatorios, setRelatorios] = useState<Relatorio[]>([]);
  const [atual, setAtual] = useState(0);
  const [{ decisoes, manuais }, setSalvo] = useState(lerDecisoes);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [selecaoTexto, setSelecaoTexto] = useState<{ inicio: number; fim: number; trecho: string } | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    try {
      localStorage.setItem(CHAVE, JSON.stringify({ decisoes, manuais }));
    } catch {
      /* sem armazenamento: as decisões valem só nesta aba */
    }
  }, [decisoes, manuais]);

  const rel = relatorios[atual];
  const id = rel?.prontuario_id || "";
  const decisoesAtuais = decisoes[id] || {};
  const { sugeridos, revisao } = useMemo(
    () => (rel ? montarItens(rel, manuais[id] || []) : { sugeridos: [], revisao: [] }),
    [rel, manuais, id],
  );

  function abrir(lista: Relatorio[]) {
    if (!lista.length) {
      setErro("O arquivo não tem relatórios do pipeline. Abra o JSON de saída, por exemplo reports/relatorios_processados.json.");
      return;
    }
    setErro("");
    setRelatorios(lista);
    setAtual(0);
    setSelecionado(null);
    setSelecaoTexto(null);
  }

  async function aoEscolherArquivos(e: React.ChangeEvent<HTMLInputElement>) {
    const arquivos = Array.from(e.target.files || []);
    e.target.value = "";
    try {
      const listas = await Promise.all(arquivos.map(lerArquivo));
      abrir(listas.flat());
    } catch {
      setErro("Não foi possível ler o arquivo. Confira se é o JSON gerado pelo pipeline.");
    }
  }

  async function abrirExemplo() {
    const r = await fetch(`${import.meta.env.BASE_URL}exemplo.json`);
    abrir(await r.json());
  }

  function irPara(i: number) {
    setAtual(i);
    setSelecionado(null);
    setSelecaoTexto(null);
  }

  function decidir(itemId: string, d: Decisao) {
    setSalvo((s) => {
      const doProntuario = { ...(s.decisoes[id] || {}) };
      if (d === "pendente") delete doProntuario[itemId];
      else doProntuario[itemId] = d;
      return { ...s, decisoes: { ...s.decisoes, [id]: doProntuario } };
    });
  }

  function incluirManual(codigo: string, descricao: string) {
    if (!selecaoTexto) return;
    const novo: Manual = {
      id: `m${Date.now()}`,
      codigo,
      descricao,
      inicio: selecaoTexto.inicio,
      fim: selecaoTexto.fim,
    };
    setSalvo((s) => ({ ...s, manuais: { ...s.manuais, [id]: [...(s.manuais[id] || []), novo] } }));
    setSelecionado(novo.id);
    setSelecaoTexto(null);
    window.getSelection()?.removeAllRanges();
  }

  function removerManual(itemId: string) {
    setSalvo((s) => ({ ...s, manuais: { ...s.manuais, [id]: (s.manuais[id] || []).filter((m) => m.id !== itemId) } }));
    if (selecionado === itemId) setSelecionado(null);
  }

  // Exporta as decisões de todos os prontuários abertos, para comparar com o sistema.
  function exportar() {
    const saida = relatorios.map((r) => {
      const { sugeridos: s, revisao: v } = montarItens(r, manuais[r.prontuario_id] || []);
      const dec = decisoes[r.prontuario_id] || {};
      const linha = (i: (typeof s)[number]) => ({
        codigo: i.codigo,
        codigo_digitos: soDigitos(i.codigo),
        descricao: i.descricao,
        origem: i.tipo,
        decisao: i.tipo === "manual" ? "incluido" : dec[i.id] || "pendente",
      });
      return {
        prontuario_id: r.prontuario_id,
        sugeridos: s.filter((i) => i.tipo !== "manual").map(linha),
        para_conferir: v.map(linha),
        incluidos_na_conferencia: s.filter((i) => i.tipo === "manual").map(linha),
      };
    });
    const blob = new Blob([JSON.stringify({ exportado_em: new Date().toISOString(), prontuarios: saida }, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "conferencia_faturamento.json";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="app">
      <header className="topo">
        <div className="topo-titulo">
          <h1>Conferência de faturamento</h1>
          <p>Evoluções de UTI com os códigos SIGTAP sugeridos e a evidência no texto.</p>
        </div>
        <div className="topo-acoes">
          <label className="botao-principal">
            Abrir relatórios
            <input type="file" accept=".json,application/json" multiple onChange={aoEscolherArquivos} hidden />
          </label>
          {relatorios.length > 0 && (
            <button className="botao" onClick={exportar}>
              Exportar decisões
            </button>
          )}
        </div>
      </header>

      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      {!rel ? (
        <main className="inicio">
          <h2>Abra o JSON gerado pelo pipeline</h2>
          <p>
            Cada evolução aparece como uma folha, com os trechos que justificam cada código grifados. Confirme ou recuse
            as sugestões, inclua os itens da lista de conferência e selecione trechos para incluir códigos que faltaram.
          </p>
          <p>
            O arquivo fica só no seu navegador e não é enviado para lugar nenhum.
          </p>
          <button className="botao" onClick={abrirExemplo}>
            Ver com uma evolução de exemplo
          </button>
        </main>
      ) : (
        <>
          <nav className="navegacao" aria-label="Prontuários abertos">
            <button className="botao" onClick={() => irPara(atual - 1)} disabled={atual === 0}>
              Anterior
            </button>
            <select value={atual} onChange={(e) => irPara(Number(e.target.value))} aria-label="Escolher prontuário">
              {relatorios.map((r, i) => (
                <option key={r.prontuario_id + i} value={i}>
                  Evolução {r.prontuario_id}
                </option>
              ))}
            </select>
            <span className="navegacao-pos">
              {atual + 1} de {relatorios.length}
            </span>
            <button className="botao" onClick={() => irPara(atual + 1)} disabled={atual === relatorios.length - 1}>
              Próxima
            </button>
          </nav>

          <main className="mesa">
            <section className="coluna-folha" aria-label="Texto da evolução">
              {rel.falha_extracao && (
                <p className="aviso-falha">
                  A IA não conseguiu analisar esta evolução ({rel.falha_extracao}). Os códigos vêm só das regras, então
                  leia o texto inteiro.
                </p>
              )}
              <div className="legenda">
                <span className="leg leg-sugerido">Código sugerido</span>
                <span className="leg leg-revisao">Para conferir</span>
                <span className="leg leg-ativo">Código selecionado</span>
              </div>
              <FolhaEvolucao
                texto={rel.texto_prontuario || ""}
                itens={[...sugeridos, ...revisao]}
                decisoes={decisoesAtuais}
                selecionado={selecionado}
                onSelecionar={setSelecionado}
                onSelecaoTexto={setSelecaoTexto}
              />
            </section>
            <PainelCodigos
              sugeridos={sugeridos}
              revisao={revisao}
              naoRealizados={naoRealizados(rel)}
              decisoes={decisoesAtuais}
              selecionado={selecionado}
              selecaoTexto={selecaoTexto}
              onSelecionar={(i) => setSelecionado(i === selecionado ? null : i)}
              onDecidir={decidir}
              onIncluirManual={incluirManual}
              onRemoverManual={removerManual}
            />
          </main>
        </>
      )}
    </div>
  );
}
