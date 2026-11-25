import { useState } from 'react'

// Cartão de vidro usado em toda a interface.
export default function Painel({ titulo, tag, children, className = '', carregando = false }) {
  return (
    <section className={`painel ${className} ${carregando ? 'carregando' : ''}`}>
      {titulo && <h3>{titulo}{tag && <span className="tag">{tag}</span>}</h3>}
      {children}
      {carregando && <div className="veu"><Clima texto="Resolvendo no SCIP…" /></div>}
    </section>
  )
}

export function Kpi({ rotulo, valor, unidade, nota, alerta }) {
  return (
    <section className={`painel kpi ${alerta ? 'alerta' : ''}`}>
      <div className="rot">{rotulo}</div>
      <div className="val num">{valor}{unidade && <small>{unidade}</small>}</div>
      {nota && <div className="nota">{nota}</div>}
    </section>
  )
}

export function Campo({ rotulo, children }) {
  return <label className="campo"><span>{rotulo}</span>{children}</label>
}

export function Numero({ rotulo, valor, onChange, min, max, passo = 1 }) {
  return (
    <Campo rotulo={rotulo}>
      <input type="number" value={valor} min={min} max={max} step={passo}
        onChange={e => e.target.value !== '' && onChange(Number(e.target.value))} />
    </Campo>
  )
}

export function Chave({ rotulo, valor, onChange }) {
  return (
    <label className="chave"><span>{rotulo}</span>
      <input type="checkbox" checked={valor} onChange={e => onChange(e.target.checked)} /><i />
    </label>
  )
}

// Formatação em português
export const fmt = (v, d = 0) => Number(v).toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })
export const brl = (v, d = 0) => 'R$ ' + fmt(v, d)

// Tabela de números editáveis. valores[i][j]: linha i, coluna j; `travada(i, j)` bloqueia células.
export function TabelaNumeros({ colunas, rotulos, valores, onChange, travada = () => false, passo = 1 }) {
  return (
    <div className="rolagem"><table className="editavel">
      <thead><tr><th />{colunas.map(c => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{valores.map((linha, i) => (
        <tr key={i}><td>{rotulos[i]}</td>
          {linha.map((v, j) => (
            <td key={j}><input type="number" value={v} step={passo} min={0} disabled={travada(i, j)}
              onChange={e => e.target.value !== '' && onChange(i, j, Number(e.target.value))} /></td>
          ))}
        </tr>))}
      </tbody>
    </table></div>
  )
}

export function SubAbas({ abas, valor, onChange }) {
  return <div className="subabas">{abas.map(a => <button key={a} className={a === valor ? 'ativa' : ''} onClick={() => onChange(a)}>{a}</button>)}</div>
}

export function Progresso({ feito, total, texto }) {
  const pct = total ? Math.round((100 * feito) / total) : 0
  return (
    <div className="painel"><h3>Calculando a política de operação</h3>
      <div className="trilho grande"><div className="preench" style={{ width: `${pct}%`, background: 'var(--agua-2)' }} /></div>
      <p className="sub" style={{ marginTop: 8 }}>{texto} · {feito.toLocaleString('pt-BR')} de {total.toLocaleString('pt-BR')} despachos ({pct}%)</p>
    </div>
  )
}

// Indicador de carregamento: um sol que gira, nuvem e chuvinha.
export function Clima({ texto = 'Carregando o cenário…', grande = false }) {
  return (
    <div className={`clima ${grande ? 'grande' : ''}`} role="status" aria-live="polite">
      <div className="ceu">
        <svg className="sol" viewBox="0 0 100 100" aria-hidden="true">
          <g className="raios">{Array.from({ length: 12 }, (_, i) => <line key={i} x1="50" y1="6" x2="50" y2="20" transform={`rotate(${i * 30} 50 50)`} />)}</g>
          <circle cx="50" cy="50" r="19" />
        </svg>
        <svg className="nuvem" viewBox="0 0 80 40" aria-hidden="true"><path d="M20 34a12 12 0 0 1-1-24 16 16 0 0 1 30-3 13 13 0 0 1 13 12 11 11 0 0 1-2 15z" /></svg>
        <div className="chuva" aria-hidden="true">{Array.from({ length: 7 }, (_, i) => <i key={i} style={{ left: `${10 + i * 12}%`, animationDelay: `${(i * 0.23) % 1.1}s` }} />)}</div>
      </div>
      <div className="texto-clima">{texto}</div>
    </div>
  )
}

// Seletor de gráficos: todos visíveis por padrão; cada botão liga ou desliga um gráfico.
export function useGraficos() {
  const [ocultos, setOcultos] = useState(() => new Set())
  const alternar = id => setOcultos(o => { const n = new Set(o); n.has(id) ? n.delete(id) : n.add(id); return n })
  const mostrarTodos = () => setOcultos(new Set())
  return { mostra: id => !ocultos.has(id), alternar, mostrarTodos, ocultos }
}

export function SeletorGraficos({ lista, g }) {
  return (
    <div className="seletor" role="group" aria-label="Gráficos visíveis">
      <span className="rotulo">Gráficos</span>
      {lista.map(([id, nome]) => (
        <button key={id} className={g.mostra(id) ? 'ativa' : ''} aria-pressed={g.mostra(id)} onClick={() => g.alternar(id)}>
          <i />{nome}
        </button>
      ))}
      {g.ocultos.size > 0 && <button className="todos" onClick={g.mostrarTodos}>Mostrar todos</button>}
    </div>
  )
}
