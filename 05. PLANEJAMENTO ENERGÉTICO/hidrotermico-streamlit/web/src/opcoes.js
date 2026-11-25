// Configurações dos gráficos (ECharts). Cada função recebe os dados da API e devolve um objeto de opções.
export const COR = { agua: '#4f8df0', termicas: ['#ff8a3d', '#ffc247', '#ff5e7a', '#c084fc'], perigo: '#ff4d5e', carga: '#14283a', texto: 'rgba(20,40,58,.75)', grade: 'rgba(20,50,80,.1)' }

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
  tooltip: { trigger: 'axis', backgroundColor: 'rgba(255,255,255,.96)', borderColor: 'rgba(20,50,80,.2)', textStyle: { color: '#14283a' } },
}
const par = (x, y) => x.map((h, i) => [h, y[i]])
export const rotuloHora = h => `Dia ${Math.floor(h / 24) + 1} · ${String(Math.floor(h % 24)).padStart(2, '0')}:${h % 1 ? '30' : '00'}`
const dica = formatos => ps => `${rotuloHora(ps[0].value[0])}<br/>` + ps.map(p => `${p.marker} ${p.seriesName}: <b>${formatos(p.value[1], p.seriesName)}</b>`).join('<br/>')

const FIXAS = new Set(['hora', 'carga', 'UHE', 'q', 'vert', 'volume', 'déficit', 'cmo', 'cma', 'cma_mwh'])
export const termicasDe = meia => Object.keys(meia).filter(k => !FIXAS.has(k))

export function despacho(meia) {
  const h = meia.hora
  // Camadas empilhadas "à mão": cada área é desenhada do zero até a soma acumulada, da maior (atrás) para a menor (na frente).
  // O ECharts empilha errado quando os dois eixos são numéricos (soma também o eixo x), por isso não usamos `stack`.
  const camadas = [['Hidrelétrica (Batalha)', meia.UHE, COR.agua], ...termicasDe(meia).map((n, i) => [n, meia[n], COR.termicas[i % 4]]), ['Déficit', meia['déficit'], COR.perigo]]
  let acum = h.map(() => 0)
  const series = camadas.map(([nome, y, cor], k) => {
    acum = acum.map((a, i) => a + (y[i] || 0))
    const dados = h.map((x, i) => [x, acum[i], y[i] || 0])   // [hora, topo da camada, valor da camada]
    return { name: nome, type: 'line', showSymbol: false, step: 'end', areaStyle: { opacity: 1 }, lineStyle: { width: 0 }, color: cor, data: dados, z: camadas.length - k, encode: { x: 0, y: 1 } }
  })
  return {
    ...base,
    tooltip: { ...base.tooltip, formatter: ps => `${rotuloHora(ps[0].value[0])}<br/>` + ps.map(p => `${p.marker} ${p.seriesName}: <b>${Number(p.value.length > 2 ? p.value[2] : p.value[1]).toFixed(1)} MW</b>`).join('<br/>') },
    xAxis: eixoDias, yAxis: eixoY('MW'),
    series: [...series, { name: 'Carga', type: 'line', showSymbol: false, step: 'end', lineStyle: { color: COR.carga, width: 2 }, color: COR.carga, data: par(h, meia.carga), z: 20 }],
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
      markLine: { symbol: 'none', silent: true, lineStyle: { color: 'rgba(20,50,80,.45)', type: 'dashed' }, label: { color: COR.texto, formatter: 'início' }, data: [{ yAxis: vi }] } }],
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
      no.itemStyle = { color: COR.termicas[0], borderColor: '#fff', borderWidth: 2, shadowBlur: 8, shadowColor: COR.termicas[0] }
      no.label = { position: 'right', distance: 10, color: '#7c2d0a', backgroundColor: 'rgba(255,138,61,.2)', borderColor: 'rgba(255,138,61,.65)', borderWidth: 1, borderRadius: 6, padding: [3, 7], fontSize: 12, fontWeight: 600,
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
      tooltip: { backgroundColor: 'rgba(255,255,255,.96)', borderColor: 'rgba(20,50,80,.2)', textStyle: { color: '#14283a' },
        formatter: p => { const n = p.data; return `<b>Mês ${n.mes} · ${n.id}</b><br/>Probabilidade: ${(n.probabilidade * 100).toFixed(2)}%<br/>Afluência: ${n.afluencia_m3s.map(v => v.toFixed(0)).join(' / ')} m³/s<br/>Volume final: ${n.volume_final.map(v => v.toFixed(1)).join(' / ')} hm³<br/>Déficit: ${n.deficit.toFixed(1)} MW` } },
      series: [{ type: 'tree', data: [raiz], orient: 'LR', left: 40, right: 270, top: 20, bottom: 20, roam: true, initialTreeDepth: -1, expandAndCollapse: false,
        symbolSize: 9, itemStyle: { color: COR.agua, borderColor: '#fff' }, edgeShape: 'polyline',
        lineStyle: { color: 'rgba(79,141,240,.55)', width: 1.6 },
        label: { color: '#14283a', fontSize: 11, position: 'top', distance: 6, formatter: p => `M${p.data.mes}` } }],
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

// ---------- PDE Didática e PL Único (gráficos por mês) ----------
const eixoMes = meses => ({ type: 'category', data: meses, axisLabel: { color: COR.texto, formatter: v => (v === 'Inicial' ? v : v.includes('ciclo') ? v.slice(0, 3) + '/' + v.split(' ').pop() : meses.length > 6 ? v.slice(0, 3) : v) }, axisLine: { lineStyle: { color: COR.grade } } })
const CORES_GERACAO = [COR.agua, '#8fb8ff', COR.termicas[0], COR.termicas[1], COR.perigo, '#c084fc']

// nomes: séries empilhadas (UHEs, térmicas, déficit); dados[i][mes]; carga: linha tracejada
export function geracaoMensal(meses, nomes, dados, carga) {
  return {
    ...base, tooltip: { ...base.tooltip, valueFormatter: v => Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' MW' },
    xAxis: eixoMes(meses), yAxis: eixoY('MW médios', { min: 0, max: Math.max(1, Math.max(...carga) * 1.15) }),
    series: [
      ...nomes.map((n, i) => ({ name: n, type: 'bar', stack: 'g', barMaxWidth: 60, color: CORES_GERACAO[i % 6], data: dados[i], itemStyle: { opacity: .88 } })),
      { name: 'Carga', type: 'line', symbol: 'none', data: carga, lineStyle: { color: COR.carga, type: 'dashed', width: 2 }, color: COR.carga },
    ],
  }
}

export function armazenamentoMensal(meses, series) {
  return {
    ...base, tooltip: { ...base.tooltip, valueFormatter: v => v.toFixed(1) + ' %' },
    xAxis: { ...eixoMes(['Inicial', ...meses]), boundaryGap: false }, yAxis: eixoY('Volume útil (%)', { min: 0, max: 100 }),
    series: series.map((s, i) => ({ name: s.nome, type: 'line', symbolSize: 7, color: s.cor || [COR.agua, COR.termicas[0]][i % 2], lineStyle: { width: 3, type: s.tracejada ? 'dashed' : 'solid' }, data: s.dados })),
  }
}

export function custosMensais(meses, series, nomeY = 'Custo imediato (R$ milhões)') {
  return {
    ...base, tooltip: { ...base.tooltip, valueFormatter: v => Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 2 }) },
    xAxis: eixoMes(meses), yAxis: eixoY(nomeY),
    series: series.map((s, i) => ({ name: s.nome, type: 'bar', barMaxWidth: 50, color: [COR.agua, COR.termicas[0]][i % 2], data: s.dados, itemStyle: { borderRadius: [4, 4, 0, 0] } })),
  }
}

// Mapa de calor do custo futuro: z[i][j], i = % útil de Batalha (x), j = % útil de Serra (y), em R$ milhões
export function custoFuturo(niveis, z) {
  const rot = niveis.map(v => v.toFixed(0))
  const todos = z.flat(), min = Math.min(...todos), max = Math.max(...todos)
  return {
    backgroundColor: 'transparent', textStyle: { color: COR.texto },
    tooltip: { confine: true, backgroundColor: 'rgba(255,255,255,.96)', borderColor: 'rgba(20,50,80,.2)', textStyle: { color: '#14283a' },
      formatter: p => `Batalha: ${rot[p.data[0]]}% útil<br/>Serra: ${rot[p.data[1]]}% útil<br/>Custo: <b>R$ ${Number(p.data[2]).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mi</b>` },
    grid: { top: 20, left: 70, right: 30, bottom: 100 },
    xAxis: { type: 'category', data: rot, name: 'VI Batalha (% útil)', nameLocation: 'middle', nameGap: 30, axisLabel: { color: COR.texto } },
    yAxis: { type: 'category', data: rot, name: 'VI Serra (% útil)', nameLocation: 'middle', nameGap: 45, axisLabel: { color: COR.texto } },
    visualMap: { min, max: max > min ? max : min + 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, text: ['Maior custo', 'Menor custo'], textStyle: { color: COR.texto }, inRange: { color: ['#e3f4f1', '#7cc7d3', '#4f8df0', '#1f3f7a'] } },
    series: [{ type: 'heatmap', data: z.flatMap((linha, i) => linha.map((v, j) => [i, j, v])), emphasis: { itemStyle: { borderColor: '#14283a', borderWidth: 1 } } }],
  }
}
