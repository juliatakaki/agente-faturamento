import { useState } from "react";
import type { Decisao, Item, NaoRealizado } from "../types";
import { formatarReais } from "../lib/itens";

interface Props {
  sugeridos: Item[];
  revisao: Item[];
  naoRealizados: NaoRealizado[];
  decisoes: Record<string, Decisao>;
  selecionado: string | null;
  selecaoTexto: { inicio: number; fim: number; trecho: string } | null;
  onSelecionar: (id: string) => void;
  onDecidir: (id: string, d: Decisao) => void;
  onIncluirManual: (codigo: string, descricao: string) => void;
  onRemoverManual: (id: string) => void;
}

function rotuloConfianca(c?: string) {
  if (c === "alta") return "Confiança alta";
  if (c === "media") return "Confiança média";
  if (c === "baixa") return "Confiança baixa, conferir";
  return "";
}

function Codigo({
  item,
  decisao,
  ativo,
  revisao,
  onSelecionar,
  onDecidir,
  onRemoverManual,
}: {
  item: Item;
  decisao: Decisao;
  ativo: boolean;
  revisao: boolean;
  onSelecionar: () => void;
  onDecidir: (d: Decisao) => void;
  onRemoverManual?: () => void;
}) {
  const semTrecho = item.trechos.length === 0;
  return (
    <li className={`codigo estado-${decisao} ${ativo ? "ativo" : ""} ${item.confianca === "baixa" ? "baixa" : ""}`}>
      <button className="codigo-corpo" onClick={onSelecionar} aria-pressed={ativo}>
        <span className="codigo-num">{item.codigo}</span>
        <span className="codigo-desc">{item.descricao}</span>
        <span className="codigo-meta">
          {item.detalhe}
          {item.confianca ? `. ${rotuloConfianca(item.confianca)}` : ""}
          {semTrecho ? ". Trecho não localizado no texto" : ""}
        </span>
        {item.motivo && <span className="codigo-motivo">{item.motivo}</span>}
        {ativo && item.alternativas && item.alternativas.length > 0 && (
          <span className="codigo-alt">
            Outras opções da busca:{" "}
            {item.alternativas.map((a) => `${a.descricao} (${a.codigo})`).join("; ")}
          </span>
        )}
      </button>
      <div className="codigo-lado">
        {item.valor !== undefined && <span className="codigo-valor">{formatarReais(item.valor)}</span>}
        <div className="acoes" role="group" aria-label={`Decisão sobre ${item.codigo}`}>
          {item.tipo === "manual" ? (
            <button className="acao recusar" onClick={onRemoverManual}>
              Remover
            </button>
          ) : (
            <>
              <button
                className={`acao aceitar ${decisao === "aceito" ? "marcada" : ""}`}
                onClick={() => onDecidir(decisao === "aceito" ? "pendente" : "aceito")}
              >
                {revisao ? "Incluir" : "Confirmar"}
              </button>
              <button
                className={`acao recusar ${decisao === "recusado" ? "marcada" : ""}`}
                onClick={() => onDecidir(decisao === "recusado" ? "pendente" : "recusado")}
              >
                {revisao ? "Descartar" : "Recusar"}
              </button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}

export function PainelCodigos(p: Props) {
  const [codigo, setCodigo] = useState("");
  const [descricao, setDescricao] = useState("");

  const valor = [...p.sugeridos, ...p.revisao]
    .filter((i) => (i.tipo === "revisao" ? p.decisoes[i.id] === "aceito" : p.decisoes[i.id] !== "recusado"))
    .reduce((s, i) => s + (i.valor || 0), 0);
  const pendentes = p.sugeridos.filter((i) => i.tipo !== "manual" && !p.decisoes[i.id]).length;

  function incluir(e: React.FormEvent) {
    e.preventDefault();
    if (!codigo.trim() || !p.selecaoTexto) return;
    p.onIncluirManual(codigo.trim(), descricao.trim() || "Código incluído na conferência");
    setCodigo("");
    setDescricao("");
  }

  return (
    <aside className="painel">
      <section className="bloco">
        <header className="bloco-topo">
          <h2>Códigos sugeridos</h2>
          <span className="bloco-resumo">
            {formatarReais(valor)}
            {pendentes > 0 ? `, ${pendentes} a conferir` : ", tudo conferido"}
          </span>
        </header>
        {p.sugeridos.length === 0 ? (
          <p className="vazio">O sistema não sugeriu nenhum código para esta evolução.</p>
        ) : (
          <ul className="lista">
            {p.sugeridos.map((i) => (
              <Codigo
                key={i.id}
                item={i}
                decisao={p.decisoes[i.id] || "pendente"}
                ativo={p.selecionado === i.id}
                revisao={false}
                onSelecionar={() => p.onSelecionar(i.id)}
                onDecidir={(d) => p.onDecidir(i.id, d)}
                onRemoverManual={() => p.onRemoverManual(i.id)}
              />
            ))}
          </ul>
        )}
      </section>

      <section className="bloco">
        <header className="bloco-topo">
          <h2>Para conferir</h2>
          <span className="bloco-resumo">Fora do valor até serem incluídos</span>
        </header>
        {p.revisao.length === 0 ? (
          <p className="vazio">Nenhum indício sem confirmação nesta evolução.</p>
        ) : (
          <ul className="lista">
            {p.revisao.map((i) => (
              <Codigo
                key={i.id}
                item={i}
                decisao={p.decisoes[i.id] || "pendente"}
                ativo={p.selecionado === i.id}
                revisao
                onSelecionar={() => p.onSelecionar(i.id)}
                onDecidir={(d) => p.onDecidir(i.id, d)}
              />
            ))}
          </ul>
        )}
      </section>

      <section className="bloco">
        <header className="bloco-topo">
          <h2>Incluir código pelo texto</h2>
        </header>
        {p.selecaoTexto ? (
          <form className="form-manual" onSubmit={incluir}>
            <p className="trecho-selecionado">"{p.selecaoTexto.trecho.slice(0, 160)}"</p>
            <label>
              Código SIGTAP
              <input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="04.01.01.001-5" required />
            </label>
            <label>
              Procedimento
              <input value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="Curativo grau II" />
            </label>
            <button type="submit" className="botao-principal">
              Incluir código
            </button>
          </form>
        ) : (
          <p className="vazio">Selecione um trecho da evolução para incluir um código que o sistema não sugeriu.</p>
        )}
      </section>

      {p.naoRealizados.length > 0 && (
        <section className="bloco">
          <details>
            <summary>
              <h2>Considerados não realizados ({p.naoRealizados.length})</h2>
            </summary>
            <ul className="lista-simples">
              {p.naoRealizados.map((n, k) => (
                <li key={k}>
                  {n.texto}
                  {n.categoria ? ` (${n.categoria.toLowerCase()})` : ""}
                  {n.motivo ? <span className="codigo-motivo"> {n.motivo}</span> : null}
                </li>
              ))}
            </ul>
          </details>
        </section>
      )}
    </aside>
  );
}
