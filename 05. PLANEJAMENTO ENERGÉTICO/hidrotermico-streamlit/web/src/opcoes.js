// Configurações dos gráficos (ECharts). Cada função recebe os dados da API e devolve um objeto de opções.
export const COR = { agua: '#5ec4ff', termicas: ['#ff8a3d', '#ffc247', '#ff5e7a', '#c084fc'], perigo: '#ff4d5e', carga: '#ffffff', texto: 'rgba(255,255,255,.72)', grade: 'rgba(255,255,255,.09)' }

const eixoDias = {
  type: 'value', min: 0, max: 168, interval: 24, axisLabel: { color: COR.texto, formatter: v => (v >= 168 ? '' : `Dia ${v / 24 + 1}`) },
  axisLine: { lineStyle: { color: COR.grade } }, splitLine: { show: true, lineStyle: { color: COR.grade } },
}
const eixoY = (nome, extra = {}) => ({
  type: 'value', name: nome, nameTextStyle: { color: COR.texto }, axisLabel: { color: COR.texto },
  splitLine: { lineStyle: { color: COR.grade } }, ...extra,
})
const base = {
  backgroundColor: 'transparent', textStyle: { color: COR.texto },
  grid: { left: 54, right: 24, top: 42, bottom: 30 },
  legend: { top: 0, textStyle: { color: COR.texto }, icon: 'roundRect', itemHeight: 8 },
  tooltip: { trigger: 'axis', backgroundColor: 'rgba(7,20,32,.92)', borderColor: 'rgba(255,255,255,.2)', textStyle: { color: '#fff' } },
}
const par = (x, y) => x.map((h, i) => [h, y[i]])
export const rotuloHora = h => `Dia ${Math.floor(h / 24) + 1} · ${String(Math.floor(h % 24)).padStart(2, '0')}:${h % 1 ? '30' : '00'}`
const dica = formatos => ps => `${rotuloHora(ps[0].value[0])}<br/>` + ps.map(p => `${p.marker} ${p.seriesName}: <b>${formatos(p.value[1], p.seriesName)}</b>`).join('<br/>')

const FIXAS = new Set(['hora', 'carga', 'UHE', 'q', 'vert', 'volume', 'déficit', 'cmo', 'cma', 'cma_mwh'])
export const termicasDe = meia => Object.keys(meia).filter(k => !FIXAS.has(k))

export function despacho(meia) {
  const h = meia.hora
  const area = (nome, y, cor, topo) => ({ name: nome, type: 'line', stack: 'g', showSymbol: false, step: 'end', areaStyle: { opacity: .72 }, lineStyle: { width: 0 }, color: cor, data: par(h, y), z: topo })
  return {
    ...base,
    tooltip: { ...base.tooltip, formatter: dica(v => v.toFixed(1) + ' MW') },
    xAxis: eixoDias, yAxis: eixoY('MW'),
    series: [
      area('Hidrelétrica (Batalha)', meia.UHE, COR.agua, 1),
      ...termicasDe(meia).map((n, i) => area(n, meia[n], COR.termicas[i % 4], 2)),
      area('Déficit', meia['déficit'], COR.perigo, 3),
      { name: 'Carga', type: 'line', showSymbol: false, step: 'end', lineStyle: { color: COR.carga, width: 2 }, color: COR.carga, data: par(h, meia.carga), z: 9 },
    ],
  }
}

export function marginais(meia) {
  const h = meia.hora
  return {
    ...base,
    tooltip: { ...base.tooltip, formatter: dica((v, n) => (n.startsWith('CMO') ? v.toFixed(1) + ' R$/MWh' : v.toFixed(1) + ' R$/MWh')) },
    xAxis: eixoDias, yAxis: eixoY('R$/MWh'),
    series: [
      { name: 'CMO', type: 'line', showSymbol: false, step: 'end', color: COR.termicas[0], lineStyle: { width: 2 }, areaStyle: { opacity: .15 }, data: par(h, meia.cmo) },
      { name: 'CMA (equivalente em R$/MWh)', type: 'line', showSymbol: false, color: COR.agua, lineStyle: { width: 2, type: 'dashed' }, data: par(h, meia.cma_mwh) },
    ],
  }
}

export function volume(meia, vi) {
  return {
    ...base, legend: { show: false },
    tooltip: { ...base.tooltip, formatter: dica(v => v.toFixed(1) + ' hm³') },
    xAxis: eixoDias, yAxis: eixoY('hm³', { scale: true }),
    series: [{ name: 'Volume de Batalha', type: 'line', showSymbol: false, color: COR.agua, lineStyle: { width: 2 }, areaStyle: { opacity: .18 }, data: par(meia.hora, meia.volume),
      markLine: { symbol: 'none', silent: true, lineStyle: { color: 'rgba(255,255,255,.4)', type: 'dashed' }, label: { color: COR.texto, formatter: 'início' }, data: [{ yAxis: vi }] } }],
  }
}

// ---------- PL em árvore ----------
export function arvoreGrafico(nos, uhe = 0) {
  const porId = Object.fromEntries(nos.map(n => [n.id, { ...n, children: [] }]))
  let raiz = null
  nos.forEach(n => { n.pai ? porId[n.pai].children.push(porId[n.id]) : (raiz = porId[n.id]) })
  const pinta = no => {
    no.name = no.id
    no.value = no.volume_final[uhe]
    if (no.folha) {
      no.symbolSize = 15
      no.itemStyle = { color: COR.termicas[0], borderColor: '#fff', borderWidth: 2, shadowBlur: 14, shadowColor: COR.termicas[0] }
      no.label = { position: 'right', distance: 10, color: '#ffe7d1', backgroundColor: 'rgba(255,138,61,.22)', borderColor: 'rgba(255,138,61,.6)', borderWidth: 1, borderRadius: 6, padding: [3, 7], fontSize: 12, fontWeight: 600,
        formatter: () => `${no.id}  ·  ${(no.probabilidade * 100).toFixed(1)}%  ·  ${no.volume_final[uhe].toFixed(0)} hm³` }
    }
    no.children.forEach(pinta)
  }
  pinta(raiz)
  const folhas = nos.filter(n => n.folha).length
  return {
    altura: Math.max(440, folhas * 42),
    opcao: {
      backgroundColor: 'transparent', textStyle: { color: COR.texto },
      tooltip: { backgroundColor: 'rgba(7,20,32,.92)', borderColor: 'rgba(255,255,255,.2)', textStyle: { color: '#fff' },
        formatter: p => { const n = p.data; return `<b>Mês ${n.mes} · ${n.id}</b><br/>Probabilidade: ${(n.probabilidade * 100).toFixed(2)}%<br/>Afluência: ${n.afluencia_m3s.map(v => v.toFixed(0)).join(' / ')} m³/s<br/>Volume final: ${n.volume_final.map(v => v.toFixed(1)).join(' / ')} hm³<br/>Déficit: ${n.deficit.toFixed(1)} MW` } },
      series: [{ type: 'tree', data: [raiz], orient: 'LR', left: 40, right: 270, top: 20, bottom: 20, roam: true, initialTreeDepth: -1, expandAndCollapse: false,
        symbolSize: 9, itemStyle: { color: COR.agua, borderColor: 'rgba(255,255,255,.7)' }, edgeShape: 'polyline',
        lineStyle: { color: 'rgba(94,196,255,.45)', width: 1.6 },
        label: { color: '#fff', fontSize: 11, position: 'top', distance: 6, formatter: p => `M${p.data.mes}` } }],
    },
  }
}

export function volumesFolhas(nos, nomes) {
  const folhas = nos.filter(n => n.folha).sort((a, b) => a.id.localeCompare(b.id))
  return {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 54, right: 20, top: 42, bottom: 40 },
    xAxis: { type: 'category', data: folhas.map(f => f.id), axisLabel: { color: COR.texto, rotate: folhas.length > 16 ? 60 : 0, fontSize: 10, interval: folhas.length > 40 ? 'auto' : 0 }, axisLine: { lineStyle: { color: COR.grade } } },
    yAxis: eixoY('hm³ no fim'),
    series: nomes.map((n, i) => ({ name: n, type: 'bar', color: i ? COR.termicas[1] : COR.agua, data: folhas.map(f => +f.volume_final[i].toFixed(1)), barMaxWidth: 16, itemStyle: { borderRadius: [4, 4, 0, 0] } })),
  }
}
