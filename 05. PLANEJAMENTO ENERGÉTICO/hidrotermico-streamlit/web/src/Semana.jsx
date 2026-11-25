import { useEffect, useMemo, useState } from 'react'
import { api, DEMO } from './api.js'
import Painel, { Kpi, Campo, Numero, Chave, Clima, useGraficos, SeletorGraficos, fmt, brl } from './componentes/Painel.jsx'
import Grafico from './componentes/Grafico.jsx'
import Medidor from './componentes/Medidor.jsx'
import { despacho, marginais, volume, COR } from './opcoes.js'

const CAMPOS = [['Ton', 'Ton (h)', 1], ['Toff', 'Toff (h)', 1], ['Pmin', 'Mín. (MW)', 1], ['Pmax', 'Máx. (MW)', 1],
  ['subida', 'Subida (MW/h)', 1], ['descida', 'Descida (MW/h)', 1], ['cvu', 'CVU (R$/MWh)', 1], ['partida', 'Partida (R$)', 100]]

// **negrito** do texto vindo da API
const comNegrito = t => t.split('**').map((p, i) => (i % 2 ? <b key={i}>{p}</b> : p))

export default function Semana() {
  const [catalogo, setCatalogo] = useState(null)
  const [escolhas, setEscolhas] = useState([])          // nomes das usinas selecionadas
  const [ajustes, setAjustes] = useState({})            // { nome: { campo: valor } } só do que foi alterado
  const [percentual, setPercentual] = useState(100)
  const [fcf, setFcf] = useState(true)
  const [flat, setFlat] = useState(true)   // hidrelétrica com vazão constante na semana
  const [r, setR] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const g = useGraficos()
  const [erro, setErro] = useState(null)
  const [hora, setHora] = useState(20)
  const [delta, setDelta] = useState(1)
  const [impactoCarregando, setImpactoCarregando] = useState(false)

  const cadastro = useMemo(() => Object.fromEntries((catalogo || []).map(u => [u.nome, u])), [catalogo])

  const pedido = (extra = {}) => ({
    unidades: escolhas.map(nome => ({ nome, ajustes: ajustes[nome] || {} })),
    percentual_carga: percentual, custo_futuro: fcf, hidro_flat: flat, ...extra,
  })

  async function calcular(extra = {}) {
    setCarregando(true); setErro(null)
    try { setR(await api.semana(pedido(extra))) }
    catch (e) { setErro(e.message) }
    finally { setCarregando(false) }
  }

  async function testarImpacto() {
    setImpactoCarregando(true)
    try { const novo = await api.semana(pedido({ hora_impacto: hora, delta_impacto: delta })); setR(r => ({ ...r, impacto: novo.impacto })) }
    catch (e) { setErro(e.message) }
    finally { setImpactoCarregando(false) }
  }

  useEffect(() => {
    api.catalogo().then(c => {
      setCatalogo(c)
      const acha = t => c.find(u => u.nome.includes(t))?.nome
      setEscolhas([acha('CANDEIAS'), acha('BALIZA')].filter(Boolean))
    }).catch(e => setErro(e.message))
  }, [])
  useEffect(() => { if (escolhas.length && !r && !carregando) calcular({ hora_impacto: 20 }) }, [escolhas])  // eslint-disable-line

  const trocar = (i, nome) => setEscolhas(es => es.map((e, j) => (j === i ? nome : e)))
  const mudar = (nome, campo, v) => setAjustes(a => {
    const atual = { ...(a[nome] || {}), [campo]: v }
    if (atual[campo] === cadastro[nome].cadastro[campo]) delete atual[campo]
    return { ...a, [nome]: atual }
  })
  const valor = (nome, campo) => ajustes[nome]?.[campo] ?? cadastro[nome].cadastro[campo]
  const codigos = new Set(escolhas.map(n => cadastro[n]?.codigo))

  const m = r?.meia_hora
  const resumo = r?.resumo
  const cmoMax = m ? Math.max(...m.cmo, 1) * 1.08 : 1
  // Hooks sempre no topo, nunca dentro de condições (o React exige a mesma ordem a cada renderização).
  const opDespacho = useMemo(() => (m ? despacho(m) : null), [r])          // eslint-disable-line
  const opVolume = useMemo(() => (m ? volume(m, resumo.volume_inicial) : null), [r])  // eslint-disable-line
  const opMarginais = useMemo(() => (m ? marginais(m) : null), [r])        // eslint-disable-line

  return (
    <div className="grade">
      {/* ---------- controles ---------- */}
      <Painel titulo="Controles" tag="DESSEM" className="sticky">
        <p className="sub">Batalha com até 4 térmicas do cadastro DESSEM (PySDDP) · 168 h em passos de meia hora.</p>
        {!catalogo && <div className="aviso info">Carregando catálogo…</div>}
        {catalogo && escolhas.map((nome, i) => (
          <div key={i}>
            <Campo rotulo={`Térmica ${i + 1}`}>
              <select value={nome} onChange={e => trocar(i, e.target.value)}>
                {catalogo.filter(u => u.nome === nome || !codigos.has(u.codigo)).map(u => <option key={u.nome}>{u.nome}</option>)}
              </select>
            </Campo>
            <details>
              <summary>Parâmetros de {nome.split(' · ')[0]}{Object.keys(ajustes[nome] || {}).length ? ' •' : ''}</summary>
              <div className="dupla" style={{ marginTop: 10 }}>
                {CAMPOS.map(([c, rot, passo]) => (
                  <Numero key={c} rotulo={rot} valor={valor(nome, c)} passo={passo} min={c === 'Pmax' ? cadastro[nome].piso_pmax : 0}
                    onChange={v => mudar(nome, c, v)} />
                ))}
              </div>
              <button className="botao fantasma" onClick={() => setAjustes(a => ({ ...a, [nome]: {} }))}>Restaurar cadastro</button>
            </details>
          </div>
        ))}
        {catalogo && (
          <div className="dupla" style={{ margin: '4px 0 10px' }}>
            <button className="botao fantasma" disabled={escolhas.length >= 4} onClick={() => {
              const livre = catalogo.find(u => !codigos.has(u.codigo)); livre && setEscolhas(e => [...e, livre.nome])
            }}>+ Térmica</button>
            <button className="botao fantasma" disabled={escolhas.length <= 1} onClick={() => setEscolhas(e => e.slice(0, -1))}>− Térmica</button>
          </div>
        )}
        <Campo rotulo={`Carga semanal: ${percentual}% do caso-base`}>
          <input type="range" min="50" max="150" value={percentual} onChange={e => setPercentual(+e.target.value)} />
        </Campo>
        <Chave rotulo="Aplicar custo futuro" valor={fcf} onChange={setFcf} />
        <Chave rotulo="Hidrelétrica flat (vazão constante)" valor={flat} onChange={setFlat} />
        <button className="botao laranja" disabled={carregando || !escolhas.length} onClick={() => calcular()}>
          {carregando ? 'Resolvendo…' : 'Calcular'}
        </button>
      </Painel>

      {/* ---------- resultados ---------- */}
      <div className="coluna">
        {erro && <div className="aviso">{erro}{DEMO ? '' : ' Verifique a API ou os parâmetros (despacho inviável com carga alta demais).'}</div>}
        {!r && !erro && <div className="painel vazio"><Clima grande texto="Resolvendo o compromisso térmico semanal…" /></div>}
        {r && (
          <>
            <div className="linha l4">
              <Kpi rotulo="Custo total" valor={brl(resumo.custo_total / 1000, 1)} unidade="mil" nota={`imediato ${brl(resumo.custo_imediato / 1000, 1)} mil · futuro ${brl(resumo.custo_futuro / 1000, 1)} mil`} />
              <Kpi rotulo="Déficit" valor={fmt(resumo.deficit_mwh, 1)} unidade="MWh" alerta={resumo.deficit_mwh > 0.01} nota={resumo.deficit_mwh > 0.01 ? 'carga acima da capacidade' : 'carga atendida'} />
              <Kpi rotulo="Volume final de Batalha" valor={fmt(resumo.volume_final, 1)} unidade="hm³" nota={`${resumo.volume_final - resumo.volume_inicial >= 0 ? '+' : ''}${fmt(resumo.volume_final - resumo.volume_inicial, 1)} hm³ na semana`} />
              <Kpi rotulo="Partidas térmicas" valor={resumo.partidas} nota={`hidro ${fmt(resumo.uhe_mwh / 1000, 2)} GWh · térmica ${fmt(resumo.termica_mwh / 1000, 2)} GWh`} />
            </div>

            <SeletorGraficos g={g} lista={[['cmo', 'Medidores de CMO'], ['despacho', 'Despacho'], ['volume', 'Volume de Batalha'], ['marginais', 'CMO e CMA']]} />

            {g.mostra('cmo') && <Painel titulo="Custo marginal da operação (CMO)" tag="R$/MWh" carregando={carregando}>
              <p className="sub">Custo de atender 1 MWh a mais em cada meia hora, obtido do problema linear com liga/desliga fixos. Mesma escala nos três medidores.</p>
              <div className="medidores">
                <Medidor valor={Math.min(...m.cmo)} max={cmoMax} rotulo="Mínimo" unidade="R$/MWh" cor={COR.agua} />
                <Medidor valor={m.cmo.reduce((a, b) => a + b, 0) / m.cmo.length} max={cmoMax} rotulo="Médio" unidade="R$/MWh" cor={COR.termicas[1]} tamanho={190} />
                <Medidor valor={Math.max(...m.cmo)} max={cmoMax} rotulo="Máximo" unidade="R$/MWh" cor={COR.perigo} />
                <Medidor valor={m.cma_mwh.reduce((a, b) => a + b, 0) / m.cma_mwh.length} max={cmoMax} rotulo="CMA médio (água)" unidade="R$/MWh" cor="#7c9cff" />
              </div>
            </Painel>}

            {(g.mostra('despacho') || g.mostra('volume')) && <div className="linha l2" >
              {g.mostra('despacho') && <Painel titulo="Despacho" tag="MW · meia hora" carregando={carregando}>
                <Grafico opcao={opDespacho} altura={330} />
              </Painel>}
              {g.mostra('volume') && <Painel titulo="Volume de Batalha" tag="hm³" carregando={carregando}>
                <Grafico opcao={opVolume} altura={330} />
              </Painel>}
            </div>}

            {g.mostra('marginais') && <Painel titulo="CMO e CMA ao longo da semana" carregando={carregando}>
              <Grafico opcao={opMarginais} altura={280} />
            </Painel>}

            <div className="linha l2b">
              {r.merito && (
                <Painel titulo="Por que a térmica entra antes da água?" tag="ordem de mérito">
                  {(() => {
                    const lista = r.merito.tabela.filter(l => l.Tipo !== 'Penalidade')
                    const topo = Math.max(...lista.map(l => l['Custo (R$/MWh)']))
                    return lista.map(l => (
                      <div className="barra" key={l.Fonte}>
                        <span>{l.Fonte.replace('Água de Batalha (CMA)', 'Água (CMA)')}</span>
                        <div className="trilho"><div className="preench" style={{ width: `${(100 * l['Custo (R$/MWh)']) / topo}%`, background: l.Tipo === 'Hidrelétrica' ? COR.agua : COR.termicas[0] }} /></div>
                        <span className="v num">{fmt(l['Custo (R$/MWh)'], 2)}</span>
                      </div>
                    ))
                  })()}
                  <p className="texto-longo">{comNegrito(r.merito.explicacao)}</p>
                </Painel>
              )}
              <Painel titulo="Impacto de elevar a carga" tag="reotimiza a semana">
                <p className="sub">Soma um acréscimo de carga a uma hora e reotimiza. O CMO prevê o custo; a diferença vem de partidas, rampas e capacidade.</p>
                <Campo rotulo={`Hora da semana: dia ${Math.floor(hora / 24) + 1} · ${String(hora % 24).padStart(2, '0')}h`}>
                  <input type="range" min="0" max="167" value={hora} onChange={e => setHora(+e.target.value)} />
                </Campo>
                <Numero rotulo="Acréscimo (MW)" valor={delta} min={0.5} max={50} passo={0.5} onChange={setDelta} />
                <button className="botao" disabled={impactoCarregando || DEMO} onClick={testarImpacto}>{impactoCarregando ? 'Reotimizando…' : 'Testar impacto'}</button>
                {r.impacto && (() => {
                  const { previsto, real, diferenca } = r.impacto
                  const topo = Math.max(Math.abs(previsto), Math.abs(real), 1)
                  return (
                    <div style={{ marginTop: 14 }}>
                      <div className="sub" style={{ marginBottom: 2 }}>Resultado para o dia {Math.floor(r.impacto.hora / 24) + 1}, {String(r.impacto.hora % 24).padStart(2, '0')}h (+{r.impacto.delta_mw} MW)</div>
                      {[['Previsto pelo CMO', previsto, COR.agua], ['Custo real', real, COR.termicas[0]]].map(([n, v, c]) => (
                        <div className="barra" key={n} style={{ gridTemplateColumns: '120px 1fr 90px' }}><span>{n}</span>
                          <div className="trilho"><div className="preench" style={{ width: `${(100 * Math.abs(v)) / topo}%`, background: c }} /></div>
                          <span className="v num">{brl(v, 2)}</span></div>
                      ))}
                      <p className="texto-longo">{Math.abs(diferenca) <= 0.01 * Math.max(Math.abs(previsto), 1)
                        ? 'O CMO descreve bem este acréscimo: o compromisso das térmicas não mudou.'
                        : `Diferença de ${brl(diferenca, 2)}: com mais carga o compromisso pode mudar (nova partida, falta de rampa ou capacidade), e o CMO não enxerga esses degraus.`}</p>
                    </div>
                  )
                })()}
              </Painel>
            </div>

            <Painel titulo="Resumo por dia">
              <div className="rolagem"><table>
                <thead><tr>{Object.keys(r.diario[0]).map(k => <th key={k}>{k}</th>)}</tr></thead>
                <tbody>{r.diario.map(l => <tr key={l.Dia}>{Object.values(l).map((v, i) => <td key={i} className="num">{fmt(v, i === 0 ? 0 : 1)}</td>)}</tr>)}</tbody>
              </table></div>
              <p className="sub" style={{ marginTop: 10 }}>SCIP · {resumo.status} · gap {(resumo.gap * 100).toFixed(2)}% · {resumo.segundos.toFixed(1)} s</p>
            </Painel>
          </>
        )}
      </div>
    </div>
  )
}
