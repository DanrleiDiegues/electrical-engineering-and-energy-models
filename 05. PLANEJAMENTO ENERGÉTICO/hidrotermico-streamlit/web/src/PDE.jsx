import { useEffect, useMemo, useState } from 'react'
import { api, DEMO } from './api.js'
import Painel, { Kpi, Campo, Numero, TabelaNumeros, SubAbas, Progresso, fmt } from './componentes/Painel.jsx'
import Grafico from './componentes/Grafico.jsx'
import { geracaoMensal, armazenamentoMensal, custosMensais, custoFuturo } from './opcoes.js'
import { ajusta, gerarMeses, baixar, paraCsv } from './util.js'

const UNIFORME = { bMax: 220, bMin: 30, sMax: 350, sMin: 20 }   // cenário de demonstração do app Streamlit

// Aba "PDE Didática": programação dinâmica na grade de volumes, com dois cenários de afluência por mês.
export default function PDE() {
  const [p, setP] = useState(null)
  const [modoCarga, setModoCarga] = useState('Constante')
  const [cargasMensais, setCargasMensais] = useState([])
  const [modoAfl, setModoAfl] = useState('Todos os meses')
  const [u, setU] = useState(UNIFORME)
  const [modoTraj, setModoTraj] = useState('Todas máximas')
  const [custom, setCustom] = useState([])
  const [r, setR] = useState(null)
  const [tarefa, setTarefa] = useState(null)
  const [erro, setErro] = useState(null)
  const [aba, setAba] = useState('Operação e armazenamento')
  const [mesFuturo, setMesFuturo] = useState(0)

  useEffect(() => {
    api.pdePadroes(12).then(d => { setP({ ...d, nr_disc: DEMO ? d.nr_disc : 12 }); setCargasMensais(Array(d.n_meses).fill(d.carga)); setCustom(Array(d.n_meses).fill(0)) }).catch(e => setErro(e.message))
  }, [])

  if (!p) return <div className="painel vazio">{erro || 'Carregando…'}</div>
  const n = p.n_meses
  const meses = gerarMeses(n)
  const aflMax = modoAfl === 'Todos os meses' ? Array(n).fill([u.bMax, u.sMax]) : ajusta(p.afl_max, n)
  const aflMin = modoAfl === 'Todos os meses' ? Array(n).fill([u.bMin, u.sMin]) : ajusta(p.afl_min, n)
  const trajetoria = modoTraj === 'Todas máximas' ? Array(n).fill(0) : modoTraj === 'Todas mínimas' ? Array(n).fill(1) : ajusta(custom, n)
  const pedido = () => ({
    n_meses: n, carga: p.carga, cargas_mensais: modoCarga === 'Por mês' ? ajusta(cargasMensais, n) : null, nr_disc: p.nr_disc,
    inicial: p.inicial, trajetoria, afl_max: aflMax, afl_min: aflMin,
    uhes: p.uhes.map(({ nome, ...x }) => x), termicas: p.termicas.map(({ nome, ...x }) => x),
    custo_deficit: p.custo_deficit, potencia_serra: p.potencia_serra,
  })
  async function calcular() {
    setErro(null); setR(null); setTarefa({ feito: 0, total: n * p.nr_disc ** 2 * 2, mes: 'Iniciando' })
    try { setR(await api.pde(pedido(), setTarefa)); setMesFuturo(0) } catch (e) { setErro(e.message) } finally { setTarefa(null) }
  }
  const set = (campo, v) => setP(q => ({ ...q, [campo]: v }))
  const setN = v => set('n_meses', Math.max(1, Math.min(60, Math.round(v))))
  const editarAfl = (i, j, v) => {
    const mx = ajusta(p.afl_max, n).map(l => [...l]), mn = ajusta(p.afl_min, n).map(l => [...l])
    ;[[mx, 0, 0], [mn, 0, 1], [mx, 1, 2], [mn, 1, 3]].forEach(([m, uhe, col]) => { if (col === j) m[i][uhe] = v })
    setP(q => ({ ...q, afl_max: mx, afl_min: mn }))
  }
  const editarUhe = (i, j, v) => set('uhes', p.uhes.map((x, k) => (k === i ? { ...x, [['vmin', 'vmax', 'engolimento', 'produtividade'][j]]: v } : x)))
  const editarTer = (i, j, v) => set('termicas', p.termicas.map((x, k) => (k === i ? { ...x, [['gtmax', 'custo'][j]]: v } : x)))
  const despachos = 2 * n * p.nr_disc ** 2

  return (
    <div className="grade">
      <Painel titulo="Controles" tag="PDE Didática" className="sticky">
        <p className="sub">{n} estágios · 2 UHEs em cascata · 2 UTEs. O calendário começa em janeiro; cada estágio tem 30 dias.</p>
        <Numero rotulo="Número de meses" valor={n} min={1} max={60} onChange={setN} />
        <div className="seg">{['Constante', 'Por mês'].map(m => <button key={m} className={modoCarga === m ? 'ativa' : ''} onClick={() => setModoCarga(m)}>Carga {m.toLowerCase()}</button>)}</div>
        {modoCarga === 'Constante'
          ? <Numero rotulo="Carga constante (MW médios)" valor={p.carga} min={0} passo={10} onChange={v => set('carga', v)} />
          : <p className="sub">Edite a carga mensal na tabela do painel principal.</p>}
        <Numero rotulo="Níveis de volume por UHE" valor={p.nr_disc} min={2} max={40} onChange={v => set('nr_disc', Math.max(2, Math.min(40, Math.round(v))))} />
        <p className="sub">{(p.nr_disc ** 2).toLocaleString('pt-BR')} pares de volumes · {despachos.toLocaleString('pt-BR')} otimizações na grade. {p.nr_disc > 16 ? 'Grades grandes levam vários minutos; 24 níveis é o padrão do app Streamlit.' : 'Grade rápida; suba para 24 para reproduzir o app Streamlit.'}</p>
        <h4>Afluências locais (m³/s)</h4>
        <div className="seg">{['Todos os meses', 'Mês a mês'].map(m => <button key={m} className={modoAfl === m ? 'ativa' : ''} onClick={() => setModoAfl(m)}>{m}</button>)}</div>
        {modoAfl === 'Todos os meses' ? (
          <div className="dupla">
            <Numero rotulo="Batalha · mínima" valor={u.bMin} onChange={v => setU({ ...u, bMin: v })} />
            <Numero rotulo="Batalha · máxima" valor={u.bMax} onChange={v => setU({ ...u, bMax: v })} />
            <Numero rotulo="Serra · mínima" valor={u.sMin} onChange={v => setU({ ...u, sMin: v })} />
            <Numero rotulo="Serra · máxima" valor={u.sMax} onChange={v => setU({ ...u, sMax: v })} />
          </div>
        ) : <p className="sub">Edite as afluências de cada mês no painel principal.</p>}
        <h4>Trajetória realizada</h4>
        <Campo rotulo="Trajetória de afluências">
          <select value={modoTraj} onChange={e => setModoTraj(e.target.value)}>{['Todas máximas', 'Todas mínimas', 'Personalizada'].map(m => <option key={m}>{m}</option>)}</select>
        </Campo>
        {modoTraj === 'Personalizada' && (
          <div className="chips">{meses.map((m, i) => (
            <button key={i} className={ajusta(custom, n)[i] ? 'min' : 'max'} onClick={() => setCustom(ajusta(custom, n).map((x, k) => (k === i ? 1 - x : x)))}>{m.slice(0, 3)} {ajusta(custom, n)[i] ? 'mín' : 'máx'}</button>
          ))}</div>
        )}
        <h4>Armazenamento inicial (% útil)</h4>
        <div className="dupla">{p.uhes.map((x, i) => <Numero key={i} rotulo={x.nome} valor={p.inicial[i]} min={0} max={100} passo={1} onChange={v => set('inicial', p.inicial.map((a, k) => (k === i ? v : a)))} />)}</div>
        <button className="botao laranja" disabled={!!tarefa} onClick={calcular}>{tarefa ? 'Calculando…' : 'Calcular'}</button>
        <button className="botao fantasma" onClick={() => api.pdePadroes(12).then(d => { setP({ ...d, nr_disc: DEMO ? d.nr_disc : 12 }); setU(UNIFORME); setModoAfl('Todos os meses'); setModoTraj('Todas máximas'); setModoCarga('Constante') })}>Restaurar cenário padrão</button>
      </Painel>

      <div className="coluna">
        {erro && <div className="aviso">{erro}</div>}
        {(modoCarga === 'Por mês' || modoAfl === 'Mês a mês') && (
          <Painel titulo="Entradas mensais" tag="editável">
            {modoCarga === 'Por mês' && (<>
              <h4>Carga (MW médios)</h4>
              <TabelaNumeros colunas={['Carga']} rotulos={meses} valores={ajusta(cargasMensais, n).map(c => [c])} onChange={(i, j, v) => setCargasMensais(ajusta(cargasMensais, n).map((c, k) => (k === i ? v : c)))} />
            </>)}
            {modoAfl === 'Mês a mês' && (<>
              <h4>Afluências (m³/s)</h4>
              <TabelaNumeros colunas={['Batalha · máx.', 'Batalha · mín.', 'Serra · máx.', 'Serra · mín.']} rotulos={meses}
                valores={meses.map((_, i) => [aflMax[i][0], aflMin[i][0], aflMax[i][1], aflMin[i][1]])} onChange={editarAfl} />
            </>)}
          </Painel>
        )}
        <Painel titulo="Parâmetros das usinas" tag="editável">
          <details>
            <summary>Hidrelétricas, termelétricas e déficit</summary>
            <h4>Hidrelétricas</h4>
            <TabelaNumeros colunas={['Vmin (hm³)', 'Vmax (hm³)', 'Engolimento (m³/s)', 'Produtibilidade']} rotulos={p.uhes.map(x => x.nome)}
              valores={p.uhes.map(x => [x.vmin, x.vmax, x.engolimento, x.produtividade])} onChange={editarUhe} passo={0.01} />
            <h4>Termelétricas</h4>
            <TabelaNumeros colunas={['Potência máxima (MW)', 'Custo (R$/MWh)']} rotulos={p.termicas.map(x => x.nome)}
              valores={p.termicas.map(x => [x.gtmax, x.custo])} onChange={editarTer} passo={0.01} />
            <div className="dupla" style={{ marginTop: 12, maxWidth: 420 }}>
              <Numero rotulo="Custo do déficit (R$/MWh)" valor={p.custo_deficit} min={0} passo={100} onChange={v => set('custo_deficit', v)} />
              <Numero rotulo="Serra nominal (MW)" valor={p.potencia_serra} min={0} onChange={v => set('potencia_serra', v)} />
            </div>
          </details>
        </Painel>

        {tarefa && <Progresso feito={tarefa.feito} total={tarefa.total} texto={tarefa.mes || 'Preparando'} />}
        {!r && !tarefa && !erro && <div className="painel vazio">Configure o cenário e clique em <b>Calcular</b>. Com grade {p.nr_disc} × {p.nr_disc} e {n} meses são {despachos.toLocaleString('pt-BR')} otimizações.</div>}
        {r && <Resultado r={r} aba={aba} setAba={setAba} mesFuturo={mesFuturo} setMesFuturo={setMesFuturo} />}
      </div>
    </div>
  )
}

function Resultado({ r, aba, setAba, mesFuturo, setMesFuturo }) {
  const s = r.resumo
  const mi = v => fmt(v / 1e6, 2)
  const op = useMemo(() => {
    const gen = traj => geracaoMensal(r.meses, ['Batalha', 'Serra do Facão', 'BBF Baliza', 'ERB Candeias', 'Déficit'],
      ['Batalha (MWm)', 'Serra (MWm)', 'Baliza (MWm)', 'Candeias (MWm)', 'Déficit (MWm)'].map(c => traj.map(l => Math.max(0, l[c]))), r.carga)
    const arm = i => armazenamentoMensal(r.meses, [{ nome: 'Com custo futuro', dados: r.armazenamento.planejada[i] }, { nome: 'Isolados', dados: r.armazenamento.isolada[i], tracejada: true }])
    return { gp: gen(r.planejada), gi: gen(r.isolada), a0: arm(0), a1: arm(1),
      custos: custosMensais(r.meses, [{ nome: 'Com custo futuro', dados: r.planejada.map(l => l['Custo imediato (R$ mi)']) }, { nome: 'Isolados', dados: r.isolada.map(l => l['Custo imediato (R$ mi)']) }]) }
  }, [r])
  const opFuturo = useMemo(() => custoFuturo(r.niveis, r.futuro[mesFuturo] || r.futuro[0]), [r, mesFuturo])
  return (
    <>
      <div className="linha l4">
        <Kpi rotulo="Esperado inicial" valor={mi(s.esperado_inicial)} unidade="R$ mi" nota="média dos dois cenários, com custo futuro" />
        <Kpi rotulo="Realizado · planejado" valor={mi(s.custo_planejado)} unidade="R$ mi" nota="soma dos custos imediatos" />
        <Kpi rotulo="Realizado · isolados" valor={mi(s.custo_isolado)} unidade="R$ mi" />
        <Kpi rotulo="Isolados − planejado" valor={mi(s.custo_isolado - s.custo_planejado)} unidade="R$ mi" nota="na trajetória realizada" />
      </div>
      <p className="sub" style={{ margin: '0 4px' }}>Déficit na trajetória planejada: {fmt(s.deficit_mwh, 0)} MWh · {s.meses_com_deficit} mês(es) com déficit · grade {r.nr_disc} × {r.nr_disc} · {fmt(s.segundos, 1)} s.
        {s.meses_acima_capacidade > 0 && ` A carga supera a capacidade de ${fmt(s.capacidade, 2)} MW médios em ${s.meses_acima_capacidade} mês(es).`}</p>
      <SubAbas abas={['Operação e armazenamento', 'Custos futuros', 'Dados e exportação', 'Modelo e hipóteses']} valor={aba} onChange={setAba} />

      {aba === 'Operação e armazenamento' && (<>
        <div className="linha l2b">
          <Painel titulo="Com custo futuro" tag="MW médios"><Grafico opcao={op.gp} altura={360} /></Painel>
          <Painel titulo="Despachos isolados" tag="MW médios"><Grafico opcao={op.gi} altura={360} /></Painel>
        </div>
        <div className="linha l2b">
          <Painel titulo="Batalha" tag="volume útil %"><Grafico opcao={op.a0} altura={300} /></Painel>
          <Painel titulo="Serra do Facão" tag="volume útil %"><Grafico opcao={op.a1} altura={300} /></Painel>
        </div>
        <Painel titulo="Custo imediato por mês" tag="R$ milhões"><Grafico opcao={op.custos} altura={300} /></Painel>
      </>)}

      {aba === 'Custos futuros' && (
        <Painel titulo="Custo esperado por par de volumes iniciais">
          <p className="sub">Cada ponto é o custo desde o mês escolhido até o fim do horizonte. Eixos: volume útil inicial de cada UHE (%); cor: custo em R$ milhões.</p>
          <Campo rotulo="Custo desde"><select value={mesFuturo} onChange={e => setMesFuturo(+e.target.value)}>{r.meses.map((m, i) => <option key={i} value={i}>{m}</option>)}</select></Campo>
          <Grafico opcao={opFuturo} altura={520} />
        </Painel>
      )}

      {aba === 'Dados e exportação' && (<>
        {[['Com custo futuro', r.planejada, 'planejada'], ['Despachos isolados', r.isolada, 'isolada']].map(([titulo, linhas, nome]) => (
          <Painel key={nome} titulo={titulo} tag="trajetória selecionada">
            <div className="rolagem"><table>
              <thead><tr>{Object.keys(linhas[0]).map(c => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>{linhas.map((l, i) => <tr key={i}>{Object.values(l).map((v, j) => <td key={j} className="num">{typeof v === 'number' ? fmt(v, 2) : v}</td>)}</tr>)}</tbody>
            </table></div>
            <button className="botao fantasma" style={{ maxWidth: 260, marginTop: 12 }} onClick={() => baixar(`resultados_${nome}.csv`, paraCsv(linhas), 'text/csv')}>Baixar {nome} (.csv)</button>
          </Painel>
        ))}
        <Painel titulo="Exportar">
          <p className="sub">Os custos realizados somam apenas custos imediatos. Somar FOB contaria custos futuros repetidamente.</p>
          <button className="botao" style={{ maxWidth: 260 }} onClick={() => baixar('parametros.json', JSON.stringify(r.parametros, null, 2), 'application/json')}>Baixar parâmetros (.json)</button>
        </Painel>
      </>)}

      {aba === 'Modelo e hipóteses' && (
        <Painel titulo="A formulação do notebook, preservada">
          <p className="texto-longo">O planejamento percorre o horizonte do último mês para o primeiro. Para cada par de volumes iniciais, resolve os cenários máximo e mínimo e guarda a média dos dois custos ótimos. A simulação percorre os meses em ordem cronológica.</p>
          <ul className="texto-longo">
            <li><b>Cascata:</b> Serra recebe sua afluência local, o turbinamento e o vertimento de Batalha no mesmo mês.</li>
            <li><b>Cenários:</b> ambas as UHEs no máximo ou ambas no mínimo, com 50% cada e independência entre meses.</li>
            <li><b>Custo futuro:</b> combinação convexa de todos os pares da grade, com pesos escolhidos pelo solver. Não são probabilidades nem interpolação bilinear.</li>
            <li><b>Despacho:</b> minimiza custo térmico, custo do déficit, R$ 0,01 por hm³ vertido e custo futuro. SCIP via PySCIPOpt.</li>
            <li><b>Hipóteses:</b> estágios mensais de 30 dias, produtibilidade constante, sem evaporação, sem vazão mínima e custo futuro terminal zero.</li>
          </ul>
          <p className="texto-longo"><code>V<sup>f</sup><sub>B</sub> = V<sup>i</sup><sub>B</sub> + A<sub>B</sub> − V<sup>t</sup><sub>B</sub> − V<sup>v</sup><sub>B</sub></code><br />
            <code>V<sup>f</sup><sub>S</sub> = V<sup>i</sup><sub>S</sub> + A<sub>S</sub> + V<sup>t</sup><sub>B</sub> + V<sup>v</sup><sub>B</sub> − V<sup>t</sup><sub>S</sub> − V<sup>v</sup><sub>S</sub></code><br />
            <code>ρ<sub>B</sub>V<sup>t</sup><sub>B</sub> + ρ<sub>S</sub>V<sup>t</sup><sub>S</sub> + G<sub>1</sub> + G<sub>2</sub> + D = Carga</code></p>
        </Painel>
      )}
    </>
  )
}
