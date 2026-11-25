import { useEffect, useMemo, useState } from 'react'
import { api, DEMO } from './api.js'
import Painel, { Kpi, Campo, Numero, Clima, useGraficos, SeletorGraficos, fmt, brl } from './componentes/Painel.jsx'
import Grafico from './componentes/Grafico.jsx'
import { arvoreGrafico, volumesFolhas } from './opcoes.js'

export default function Arvore() {
  const [padroes, setPadroes] = useState(null)
  const [p, setP] = useState(null)               // parâmetros em edição
  const [meses, setMeses] = useState(4)
  const [r, setR] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const g = useGraficos()
  const [erro, setErro] = useState(null)
  const [uheVista, setUheVista] = useState(0)

  async function resolver(parametros = p, m = meses) {
    setCarregando(true); setErro(null)
    try { setR(await api.arvore({ meses: m, ...parametros })) }
    catch (e) { setErro(e.message) }
    finally { setCarregando(false) }
  }
  useEffect(() => {
    api.arvorePadroes().then(d => { setPadroes(d); const ini = { carga: d.carga, cdef: d.cdef, afl: d.afl, uhes: d.uhes, termicas: d.termicas }; setP(ini); resolver(ini, 4) })
      .catch(e => setErro(e.message))
  }, [])  // eslint-disable-line

  const setUhe = (i, campo, v) => setP(q => ({ ...q, uhes: q.uhes.map((u, j) => (j === i ? { ...u, [campo]: v } : u)) }))
  const setTer = (i, campo, v) => setP(q => ({ ...q, termicas: q.termicas.map((t, j) => (j === i ? { ...t, [campo]: v } : t)) }))
  const grafico = useMemo(() => (r ? arvoreGrafico(r.nos, uheVista) : null), [r, uheVista])
  const opVolumes = useMemo(() => (r ? volumesFolhas(r.nos, r.uhes) : null), [r])
  const folhas = r ? r.nos.filter(n => n.folha).sort((a, b) => b.probabilidade - a.probabilidade) : []

  return (
    <div className="grade">
      <Painel titulo="Parâmetros do estudo" tag="PL único" className="sticky">
        {!p ? <div className="aviso info">Carregando…</div> : (
          <>
            <Campo rotulo={`Horizonte: ${meses} meses · ${2 ** meses - 1} nós · ${2 ** (meses - 1)} folhas`}>
              <input type="range" min="3" max="8" value={meses} onChange={e => setMeses(+e.target.value)} />
            </Campo>
            <div className="dupla">
              <Numero rotulo="Carga (MW médios)" valor={p.carga} min={0} passo={10} onChange={v => setP(q => ({ ...q, carga: v }))} />
              <Numero rotulo="Déficit (R$/MWh)" valor={p.cdef} min={0} passo={100} onChange={v => setP(q => ({ ...q, cdef: v }))} />
            </div>
            <Numero rotulo="Escala das afluências (%)" valor={p.afl} min={1} passo={5} onChange={v => setP(q => ({ ...q, afl: v }))} />
            {p.uhes.map((u, i) => (
              <details key={i}>
                <summary>{padroes.nomes_uhe[i]}</summary>
                <div className="dupla" style={{ marginTop: 10 }}>
                  <Numero rotulo="Vmin (hm³)" valor={u.vmin} passo={10} onChange={v => setUhe(i, 'vmin', v)} />
                  <Numero rotulo="Vmax (hm³)" valor={u.vmax} passo={10} onChange={v => setUhe(i, 'vmax', v)} />
                  <Numero rotulo="Vol. inicial (%)" valor={u.vi} min={0} max={100} passo={0.5} onChange={v => setUhe(i, 'vi', v)} />
                  <Numero rotulo="Engolimento (m³/s)" valor={u.qmax} passo={5} onChange={v => setUhe(i, 'qmax', v)} />
                  <Numero rotulo="Produtibilidade" valor={u.prod} passo={0.01} onChange={v => setUhe(i, 'prod', v)} />
                </div>
              </details>
            ))}
            {p.termicas.map((t, i) => (
              <details key={t.nome}>
                <summary>{t.nome.split(' · ')[0]}</summary>
                <div className="dupla" style={{ marginTop: 10 }}>
                  <Numero rotulo="Pmax (MW)" valor={t.pmax} passo={1} min={0} onChange={v => setTer(i, 'pmax', v)} />
                  <Numero rotulo="CVU (R$/MWh)" valor={t.cvu} passo={1} min={0} onChange={v => setTer(i, 'cvu', v)} />
                </div>
              </details>
            ))}
            <button className="botao laranja" disabled={carregando} onClick={() => resolver()}>{carregando ? 'Resolvendo…' : 'Resolver árvore'}</button>
            <button className="botao fantasma" onClick={() => { const ini = { carga: padroes.carga, cdef: padroes.cdef, afl: padroes.afl, uhes: padroes.uhes, termicas: padroes.termicas }; setP(ini) }}>Restaurar parâmetros</button>
          </>
        )}
      </Painel>

      <div className="coluna">
        {erro && <div className="aviso">{erro}</div>}
        {!r && !erro && <div className="painel vazio"><Clima grande texto="Resolvendo a árvore no SCIP…" /></div>}
        {r && (
          <>
            <div className="linha l4">
              <Kpi rotulo="Custo esperado" valor={fmt(r.custo_esperado / 1e6, 2)} unidade="R$ milhões" />
              <Kpi rotulo="Nós" valor={r.nos.length} nota={`${r.meses} meses`} />
              <Kpi rotulo="Trajetórias finais" valor={folhas.length} nota="cada folha é um cenário completo" />
              <Kpi rotulo="Maior probabilidade" valor={fmt(100 * folhas[0].probabilidade, 1)} unidade="%" nota={folhas[0].id} />
            </div>
            <SeletorGraficos g={g} lista={[['arvore', 'Árvore de cenários'], ['volumes', 'Volume final por trajetória']]} />
            {g.mostra('arvore') && <Painel titulo="Árvore de cenários" tag={`volume final de ${r.uhes[uheVista]} nas folhas`} carregando={carregando}>
              <p className="sub">Cada nó é um mês com duas aberturas de afluência. As folhas (laranja) mostram a probabilidade e o volume final da trajetória. Arraste e use o zoom para explorar.</p>
              <div className="dupla" style={{ maxWidth: 360, marginBottom: 6 }}>
                {r.uhes.map((n, i) => <button key={n} className={`botao ${i === uheVista ? '' : 'fantasma'}`} onClick={() => setUheVista(i)}>{n}</button>)}
              </div>
              <Grafico opcao={grafico.opcao} altura={grafico.altura} />
            </Painel>}
            <div className="linha l2b">
              {g.mostra('volumes') && <Painel titulo="Volume final por trajetória" tag="hm³">
                <Grafico opcao={opVolumes} altura={300} />
              </Painel>}
              <Painel titulo="Folhas mais prováveis">
                <div className="rolagem"><table>
                  <thead><tr><th>Trajetória</th><th>Prob.</th>{r.uhes.map(n => <th key={n}>{n} (hm³)</th>)}</tr></thead>
                  <tbody>{folhas.slice(0, 8).map(f => <tr key={f.id}><td>{f.id}</td><td className="num">{fmt(100 * f.probabilidade, 2)}%</td>{f.volume_final.map((v, i) => <td key={i} className="num">{fmt(v, 1)}</td>)}</tr>)}</tbody>
                </table></div>
              </Painel>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
