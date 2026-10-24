import { useState } from "react";
import type { Decisao, Item, NaoRealizado } from "../types";
import { descricaoDe, formatarReais, soDigitos } from "../lib/itens";
import { buscarProcedimentos, formatarCodigo, type Procedimento } from "../lib/sigtap";

interface Props {
  sugeridos: Item[];
  revisao: Item[];
  naoRealizados: NaoRealizado[];
  decisoes: Record<string, Decisao>;
  selecionado: string | null;
  realce: string[];
  onRealce: (ids: string[] | null) => void;
  gabarito?: { codigo: string; descricao?: string }[];
  mostrarFora: boolean;
  mostrarExames: boolean;
  onMostrarExames: (v: boolean) => void;
  onMostrarFora: (v: boolean) => void;
  selecaoTexto: { inicio: number; fim: number; trecho: string } | null;
  sigtapPronto: boolean;
  trechoAtual: number; // qual ocorrência do código selecionado está em foco no texto
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
  realcado,
  noGabarito,
  revisao,
  trechoAtual,
  onRealce,
  onSelecionar,
  onDecidir,
  onRemoverManual,
}: {
  item: Item;
  decisao: Decisao;
  ativo: boolean;
  realcado: boolean;
  noGabarito?: boolean;
  revisao: boolean;
  trechoAtual: number;
  onRealce: (ids: string[] | null) => void;
  onSelecionar: () => void;
  onDecidir: (d: Decisao) => void;
  onRemoverManual?: () => void;
}) {
  const semTrecho = item.trechos.length === 0;
  return (
    <li
      data-item={item.id}
      className={`codigo estado-${decisao} ${ativo ? "ativo" : ""} ${realcado ? "realcado" : ""} ${item.confianca === "baixa" ? "baixa" : ""}`}
      onMouseEnter={() => onRealce([item.id])}
      onMouseLeave={() => onRealce(null)}
    >
      <button
        className="codigo-corpo"
        onClick={onSelecionar}
        aria-pressed={ativo}
        title={semTrecho ? undefined : "Clique para ver no texto. Clique de novo para ir à próxima ocorrência."}
      >
        <span className="codigo-num">{item.codigo}</span>
        <span className="codigo-desc">{item.descricao}</span>
        <span className="codigo-meta">
          {item.detalhe}
          {item.confianca ? `. ${rotuloConfianca(item.confianca)}` : ""}
          {semTrecho ? ". Trecho não localizado no texto" : ""}
        </span>
        {ativo && item.trechos.length > 1 && (
          <span className="codigo-ocorrencia">
            Trecho {trechoAtual + 1} de {item.trechos.length} no texto. Clique de novo para o próximo.
          </span>
        )}
        {noGabarito !== undefined && (
          <span className={`codigo-gabarito ${noGabarito ? "sim" : "nao"}`}>
            {noGabarito ? "Também marcado pelo anotador" : "Não marcado pelo anotador"}
          </span>
        )}
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

/** Campo único que busca no SIGTAP enquanto digita (código com ou sem pontos, ou nome). */
function BuscaSigtap({ onEscolher }: { onEscolher: (p: Procedimento) => void }) {
  const [consulta, setConsulta] = useState("");
  const [ativo, setAtivo] = useState(0);
  const resultados = consulta.trim().length >= 2 ? buscarProcedimentos(consulta) : [];

  function escolher(proc: Procedimento) {
    onEscolher(proc);
    setConsulta("");
    setAtivo(0);
  }

  function tecla(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!resultados.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAtivo((a) => Math.min(a + 1, resultados.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      escolher(resultados[ativo]);
    }
  }

  return (
    <div className="busca-sigtap">
      <label>
        Procedimento do SIGTAP
        <input
          value={consulta}
          onChange={(e) => {
            setConsulta(e.target.value);
            setAtivo(0);
          }}
          onKeyDown={tecla}
          placeholder="Digite o código ou o nome, ex. curativo ou 0401010015"
          role="combobox"
          aria-expanded={resultados.length > 0}
          aria-controls="lista-sigtap"
          autoComplete="off"
          autoFocus
          onFocus={(e) => e.currentTarget.scrollIntoView({ block: "start", behavior: "smooth" })}
        />
      </label>
      {consulta.trim().length >= 2 && (
        <ul id="lista-sigtap" className="busca-lista" role="listbox">
          {resultados.length === 0 ? (
            <li className="busca-vazia">Nenhum procedimento encontrado.</li>
          ) : (
            resultados.map((r, k) => (
              <li
                key={r.c}
                role="option"
                aria-selected={k === ativo}
                className={k === ativo ? "ativo" : ""}
                onMouseEnter={() => setAtivo(k)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  escolher(r);
                }}
              >
                <span className="codigo-num">{formatarCodigo(r.c)}</span>
                <span className="busca-nome">{r.n}</span>
                <span className="busca-valor">{formatarReais(r.v)}</span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}

export function PainelCodigos(p: Props) {
  const [codigo, setCodigo] = useState("");
  const [descricao, setDescricao] = useState("");
  const [escolhido, setEscolhido] = useState<Procedimento | null>(null);
  const digitosGabarito = p.gabarito ? new Set(p.gabarito.map((g) => soDigitos(g.codigo))) : null;
  const noGabarito = (c: string) => (digitosGabarito ? digitosGabarito.has(soDigitos(c)) : undefined);
  const digitosSistema = new Set(
    [...p.sugeridos, ...p.revisao].map((i) => soDigitos(i.codigo)),
  );
  // Do gabarito, só o que o sistema não pôs na tela. O que ele achou já aparece
  // nos códigos com "Também marcado pelo anotador".
  const faltaram = (p.gabarito || []).filter((g) => !digitosSistema.has(soDigitos(g.codigo)));

  const doEscopo = p.sugeridos.filter((i) => !i.foraEscopo);
  const exames = p.sugeridos.filter((i) => i.exame);
  const fora = p.sugeridos.filter((i) => i.foraEscopo && !i.exame);
  const valorExames = exames.filter((i) => p.decisoes[i.id] !== "recusado").reduce((s, i) => s + (i.valor || 0), 0);
  const listaFora = (itens: Item[]) => (
    <ul className="lista">
      {itens.map((i) => (
        <Codigo
          key={i.id}
          item={i}
          decisao={p.decisoes[i.id] || "pendente"}
          ativo={p.selecionado === i.id}
          trechoAtual={p.trechoAtual}
          realcado={p.realce.includes(i.id)}
          noGabarito={noGabarito(i.codigo)}
          onRealce={p.onRealce}
          revisao={false}
          onSelecionar={() => p.onSelecionar(i.id)}
          onDecidir={(d) => p.onDecidir(i.id, d)}
        />
      ))}
    </ul>
  );
  const valor = [...doEscopo, ...p.revisao]
    .filter((i) => (i.tipo === "revisao" ? p.decisoes[i.id] === "aceito" : p.decisoes[i.id] !== "recusado"))
    .reduce((s, i) => s + (i.valor || 0), 0);
  const pendentes = doEscopo.filter((i) => i.tipo !== "manual" && !p.decisoes[i.id]).length;

  function incluir(e: React.FormEvent) {
    e.preventDefault();
    if (!p.selecaoTexto) return;
    if (p.sigtapPronto) {
      if (!escolhido) return;
      p.onIncluirManual(formatarCodigo(escolhido.c), escolhido.n);
      setEscolhido(null);
      return;
    }
    if (!codigo.trim()) return;
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
        {doEscopo.length === 0 ? (
          <p className="vazio">O sistema não sugeriu nenhum código do escopo para esta evolução.</p>
        ) : (
          <ul className="lista">
            {doEscopo.map((i) => (
              <Codigo
                key={i.id}
                item={i}
                decisao={p.decisoes[i.id] || "pendente"}
                ativo={p.selecionado === i.id}
                trechoAtual={p.trechoAtual}
                realcado={p.realce.includes(i.id)}
                noGabarito={noGabarito(i.codigo)}
                onRealce={p.onRealce}
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
                trechoAtual={p.trechoAtual}
                realcado={p.realce.includes(i.id)}
                noGabarito={noGabarito(i.codigo)}
                onRealce={p.onRealce}
                revisao
                onSelecionar={() => p.onSelecionar(i.id)}
                onDecidir={(d) => p.onDecidir(i.id, d)}
              />
            ))}
          </ul>
        )}
      </section>

      {exames.length > 0 && (
        <section className="bloco">
          <details open={p.mostrarExames} onToggle={(e) => p.onMostrarExames((e.target as HTMLDetailsElement).open)}>
            <summary>
              <h2>Exames encontrados ({exames.length})</h2>
              <span className="bloco-resumo"> {formatarReais(valorExames)} à parte</span>
            </summary>
            <p className="vazio nota-fora">
              Exames de laboratório, imagem e métodos gráficos citados nesta evolução. Ficam fora da avaliação do
              estudo e somam à parte, sem entrar no valor dos códigos sugeridos. Com este bloco aberto, os trechos
              deles aparecem grifados no texto.
            </p>
            {listaFora(exames)}
          </details>
        </section>
      )}

      {fora.length > 0 && (
        <section className="bloco">
          <details open={p.mostrarFora} onToggle={(e) => p.onMostrarFora((e.target as HTMLDetailsElement).open)}>
            <summary>
              <h2>Outros códigos encontrados pela busca ({fora.length})</h2>
            </summary>
            <p className="vazio nota-fora">
              Medicamentos, materiais e outros procedimentos. Ficam fora do escopo avaliado e não entram no valor
              acima. Com este bloco aberto, os trechos deles aparecem grifados no texto.
            </p>
            {listaFora(fora)}
          </details>
        </section>
      )}

      {p.gabarito && (
        <section className="bloco">
          <header className="bloco-topo">
            <h2>Marcados pelo anotador e não sugeridos</h2>
            <span className="bloco-resumo">Gabarito da planilha</span>
          </header>
          {p.gabarito.length === 0 ? (
            <p className="vazio">O anotador não marcou nenhum código nesta evolução.</p>
          ) : faltaram.length === 0 ? (
            <p className="vazio">O sistema sugeriu tudo o que o anotador marcou.</p>
          ) : (
            <ul className="lista-simples gabarito">
              {faltaram.map((g) => (
                <li key={g.codigo} className="faltou">
                  <span className="codigo-num">{g.codigo}</span> {descricaoDe(g.codigo, g.descricao)}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="bloco">
        <header className="bloco-topo">
          <h2>Incluir código pelo texto</h2>
        </header>
        {p.selecaoTexto ? (
          <form className="form-manual" onSubmit={incluir}>
            <p className="trecho-selecionado">"{p.selecaoTexto.trecho.slice(0, 160)}"</p>
            {p.sigtapPronto ? (
              escolhido ? (
                <div className="escolhido">
                  <span className="codigo-num">{formatarCodigo(escolhido.c)}</span>
                  <span className="codigo-desc">{escolhido.n}</span>
                  <span className="codigo-meta">{formatarReais(escolhido.v)}</span>
                  <button type="button" className="acao" onClick={() => setEscolhido(null)}>
                    Trocar
                  </button>
                </div>
              ) : (
                <BuscaSigtap onEscolher={setEscolhido} />
              )
            ) : (
              <>
                <p className="vazio">Tabela do SIGTAP não carregada (falta public/sigtap.json). Digite o código.</p>
                <label>
                  Código SIGTAP
                  <input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="04.01.01.001-5" required />
                </label>
                <label>
                  Procedimento
                  <input value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="Curativo grau II" />
                </label>
              </>
            )}
            <button type="submit" className="botao-principal" disabled={p.sigtapPronto && !escolhido}>
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
