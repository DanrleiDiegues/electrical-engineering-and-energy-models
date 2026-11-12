// Medidor circular no estilo de painel de controle. `valor` e `max` definem o arco preenchido.
export default function Medidor({ valor, max, rotulo, unidade, cor, tamanho = 170 }) {
  const r = tamanho / 2 - 14
  const c = tamanho / 2
  const inicio = 135, varredura = 270
  const ponto = ang => [c + r * Math.cos((ang * Math.PI) / 180), c + r * Math.sin((ang * Math.PI) / 180)]
  const arco = (a, b) => {
    const [x1, y1] = ponto(a), [x2, y2] = ponto(b)
    return `M${x1} ${y1} A${r} ${r} 0 ${b - a > 180 ? 1 : 0} 1 ${x2} ${y2}`
  }
  const frac = Math.max(0, Math.min(1, max > 0 ? valor / max : 0))
  const marcas = Array.from({ length: 41 }, (_, i) => inicio + (varredura * i) / 40)
  return (
    <div className="medidor">
      <svg width={tamanho} height={tamanho * 0.9} viewBox={`0 0 ${tamanho} ${tamanho * 0.95}`}>
        <circle cx={c} cy={c} r={c - 2} fill="rgba(6,20,32,.55)" stroke="rgba(255,255,255,.12)" />
        {marcas.map((a, i) => {
          const [x1, y1] = [c + (r + 8) * Math.cos((a * Math.PI) / 180), c + (r + 8) * Math.sin((a * Math.PI) / 180)]
          const [x2, y2] = [c + (r + (i % 5 ? 4 : 1)) * Math.cos((a * Math.PI) / 180), c + (r + (i % 5 ? 4 : 1)) * Math.sin((a * Math.PI) / 180)]
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(255,255,255,.28)" strokeWidth="1" />
        })}
        <path d={arco(inicio, inicio + varredura)} stroke="rgba(255,255,255,.12)" strokeWidth="9" fill="none" strokeLinecap="round" />
        {frac > 0.003 && <path d={arco(inicio, inicio + varredura * frac)} stroke={cor} strokeWidth="9" fill="none" strokeLinecap="round" style={{ filter: `drop-shadow(0 0 6px ${cor})` }} />}
        <text x={c} y={c + 2} textAnchor="middle" fill="#fff" fontSize={tamanho * 0.17} fontWeight="600" className="num">
          {Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 0 })}
        </text>
        <text x={c} y={c + tamanho * 0.15} textAnchor="middle" fill="rgba(255,255,255,.6)" fontSize="11">{unidade}</text>
      </svg>
      <div className="legenda">{rotulo}</div>
    </div>
  )
}
