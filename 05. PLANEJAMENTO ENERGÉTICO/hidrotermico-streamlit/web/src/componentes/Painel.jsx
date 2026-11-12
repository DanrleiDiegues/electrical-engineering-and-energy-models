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
