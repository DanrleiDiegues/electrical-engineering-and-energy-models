// Cartão de vidro usado em toda a interface.
export default function Painel({ titulo, tag, children, className = '', carregando = false }) {
  return (
    <section className={`painel ${className} ${carregando ? 'carregando' : ''}`}>
      {titulo && <h3>{titulo}{tag && <span className="tag">{tag}</span>}</h3>}
      {children}
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
      <thead><tr><th /> {colunas.map(c => <th key={c}>{c}</th>)}</tr></thead>
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
