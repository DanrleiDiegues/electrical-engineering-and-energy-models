import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import Painel, { Kpi, Campo, Numero, Chave, TabelaNumeros, SubAbas, Clima, useGraficos, SeletorGraficos, fmt, brl } from './componentes/Painel.jsx'
import Grafico from './componentes/Grafico.jsx'
import { geracaoMensal, armazenamentoMensal, custosMensais } from './opcoes.js'
import { CALENDARIO, gerarMeses, ajusta, baixar, paraCsv } from './util.js'

// Aba "PL Único": um único problema linear para todos os meses, com a trajetória de afluências conhecida.
export default function PL() {
  const [perfil, setPerfil] = useState('colab')
  const [p, setP] = useState(null)                 // parâmetros em edição (mesmo formato do pedido à API)
  const [modoCarga, setModoCarga] = useState('Constante')
  const [constantes, setConstantes] = useState(false)
  const [cargaConst, setCargaConst] = useState(250)
  const [qb, setQb] = useState(220)
  const [qs, setQs] = useState(350)
  const [r, setR] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState(null)
  const [aba, setAba] = useState('Operação do PL Único')

  async function carregarPerfil(nome) {
    const d = await api.plPadroes(nome)
    setPerfil(nome); setP(d); setCargaConst(d.carga[0]); setQb(d.afl_b[0]); setQs(d.afl_s[0]); setConstantes(nome === 'anual'); setModoCarga('Constante')
    return d
  }
  async function resolver(pedido) {
    setCarregando(true); setErro(null)
    try { setR(await api.pl(pedido)) } catch (e) { setErro(e.message) } finally { setCarregando(false) }
  }
  useEffect(() => { carregarPerfil('colab').then(resolver).catch(e => setErro(e.message)) }, [])  // eslint-disable-line

  // Entradas efetivas: os controles "constantes" sobrepõem a tabela mensal, como no app Streamlit.
  const efetivo = useMemo(() => p && ({
    ...p,
    afl_b: constantes ? p.afl_b.map(() => qb) : p.afl_b,
    afl_s: constantes ? p.afl_s.map(() => qs) : p.afl_s,
    carga: modoCarga === 'Constante' ? p.carga.map(() => cargaConst) : p.carga,
  }), [p, constantes, qb, qs, modoCarga, cargaConst])

  if (!p) return <div className="painel vazio">{erro || <Clima grande texto="Carregando o cenário…" />}</div>
  const n = p.carga.length
  const meses = gerarMeses(n, p.inicio)
  const mudarN = novo => setP(q => ({ ...q, afl_b: ajusta(q.afl_b, novo), afl_s: ajusta(q.afl_s, novo), carga: ajusta(q.carga, novo), inicio: novo === 12 ? 0 : q.inicio }))
  const editarMes = (i, j, v) => setP(q => {
    const campo = ['afl_b', 'afl_s', 'carga'][j]
    return { ...q, [campo]: q[campo].map((x, k) => (k === i ? v : x)) }
  })
  const editarUhe = (i, j, v) => setP(q => ({ ...q, uhes: q.uhes.map((u, k) => (k === i ? { ...u, [['vmin', 'vmax', 'engol', 'prod'][j]]: v } : u)) }))
  const editarUte = (i, j, v) => setP(q => ({ ...q, termicas: q.termicas.map((u, k) => (k === i ? { ...u, [['capac', 'custo'][j]]: v } : u)) }))
  const pedido = () => ({ inicio: p.inicio, afl_b: efetivo.afl_b, afl_s: efetivo.afl_s, carga: efetivo.carga, vi: p.vi, cdef: p.cdef,
    potencia_serra: p.potencia_serra, uhes: p.uhes.map(({ nome, ...u }) => u), termicas: p.termicas.map(({ nome, ...u }) => u) })

  return (
    <div className="grade">
      <Painel titulo="Controles" tag="PL Único" className="sticky">
        <p className="sub">Um único PL para todos os meses. A trajetória de afluências é conhecida e não há discretização dos volumes.</p>
        <Campo rotulo="Cenário de partida">
          <select value={perfil} onChange={e => carregarPerfil(e.target.value)}>
            <option value="colab">Exemplo do Colab (3 meses)</option><option value="anual">Anual (janeiro a dezembro)</option>
          </select>
        </Campo>
        <div className="dupla">
          <Numero rotulo="Número de meses" valor={n} min={1} max={60} onChange={v => mudarN(Math.max(1, Math.min(60, Math.round(v))))} />
          {n !== 12 ? (
            <Campo rotulo="Mês inicial">
              <select value={p.inicio} onChange={e => setP(q => ({ ...q, inicio: +e.target.value }))}>{CALENDARIO.map((m, i) => <option key={m} value={i}>{m}</option>)}</select>
            </Campo>
          ) : <Campo rotulo="Mês inicial"><span className="sub">janeiro a dezembro</span></Campo>}
        </div>
        <div className="seg">{['Constante', 'Por mês'].map(m => <button key={m} className={modoCarga === m ? 'ativa' : ''} onClick={() => setModoCarga(m)}>Carga {m.toLowerCase()}</button>)}</div>
        {modoCarga === 'Constante' && <Numero rotulo="Carga (MW médios)" valor={cargaConst} min={0} passo={10} onChange={setCargaConst} />}
        <Chave rotulo="Afluências constantes" valor={constantes} onChange={setConstantes} />
        {constantes && (
          <div className="dupla">
            <Numero rotulo="Batalha · AFL (m³/s)" valor={qb} onChange={setQb} />
            <Numero rotulo="Serra · AFL local (m³/s)" valor={qs} onChange={setQs} />
          </div>
        )}
        <h4>Armazenamento inicial (% útil)</h4>
        <div className="dupla">
          {p.uhes.map((u, i) => <Numero key={i} rotulo={u.nome || `UHE ${i + 1}`} valor={p.vi[i]} min={0} max={100} passo={1} onChange={v => setP(q => ({ ...q, vi: q.vi.map((x, k) => (k === i ? v : x)) }))} />)}
        </div>
        <div className="dupla">
          <Numero rotulo="Déficit (R$/MWh)" valor={p.cdef} min={0} passo={100} onChange={v => setP(q => ({ ...q, cdef: v }))} />
          <Numero rotulo="Serra nominal (MW)" valor={p.potencia_serra} min={0} onChange={v => setP(q => ({ ...q, potencia_serra: v }))} />
        </div>
        <button className="botao laranja" disabled={carregando} onClick={() => resolver(pedido())}>{carregando ? 'Resolvendo…' : 'Resolver PL Único'}</button>
        <button className="botao fantasma" onClick={() => carregarPerfil(perfil).then(resolver)}>Restaurar PL Único</button>
      </Painel>

      <div className="coluna">
        {erro && <div className="aviso">{erro}</div>}
        <Painel titulo="Entradas mensais" tag="editável">
          <TabelaNumeros colunas={['Batalha · AFL (m³/s)', 'Serra · AFL local (m³/s)', 'Carga (MW médios)']} rotulos={meses}
            valores={meses.map((_, i) => [efetivo.afl_b[i], efetivo.afl_s[i], efetivo.carga[i]])} onChange={editarMes}
            travada={(i, j) => (j < 2 ? constantes : modoCarga === 'Constante')} passo={1} />
          <details>
            <summary>Parâmetros das usinas</summary>
            <h4>Hidrelétricas</h4>
            <TabelaNumeros colunas={['Vmin (hm³)', 'Vmax (hm³)', 'Engolimento (m³/s)', 'Produtibilidade']} rotulos={p.uhes.map(u => u.nome)}
              valores={p.uhes.map(u => [u.vmin, u.vmax, u.engol, u.prod])} onChange={editarUhe} passo={0.01} />
            <h4>Termelétricas</h4>
            <TabelaNumeros colunas={['Potência máxima (MW)', 'Custo (R$/MWh)']} rotulos={p.termicas.map(u => u.nome)}
              valores={p.termicas.map(u => [u.capac, u.custo])} onChange={editarUte} passo={0.01} />
          </details>
        </Painel>

        {r && (
          <>
            <div className="linha l4">
              <Kpi rotulo="Custo total · PL Único" valor={fmt(r.resumo.custo_total / 1e6, 2)} unidade="R$ milhões" />
              <Kpi rotulo="Déficit" valor={fmt(r.resumo.deficit_mwh, 1)} unidade="MWh" alerta={r.resumo.deficit_mwh > 1e-4} />
              <Kpi rotulo="Geração térmica" valor={fmt(r.resumo.termica_mwh, 0)} unidade="MWh" />
              <Kpi rotulo="Horizonte" valor={r.meses.length} unidade="meses" nota={`resolvido em ${fmt(r.resumo.segundos, 3)} s`} />
            </div>
            <SubAbas abas={['Operação do PL Único', 'Resultados e exportação', 'Modelo do PL Único']} valor={aba} onChange={setAba} />
            {aba === 'Operação do PL Único' && <Operacao r={r} carregando={carregando} />}
            {aba === 'Resultados e exportação' && <Resultados r={r} pedido={pedido()} />}
            {aba === 'Modelo do PL Único' && (
              <Painel titulo="Modelo do PL Único">
                <ul className="texto-longo">
                  <li><b>Decisão conjunta:</b> volumes, turbinamentos, vertimentos, gerações térmicas e déficits são escolhidos em um único PL.</li>
                  <li><b>Acoplamento:</b> o volume final de cada mês é o inicial do próximo; a descarga de Batalha chega a Serra no mesmo estágio.</li>
                  <li><b>Informação:</b> a trajetória inteira de afluências e cargas é conhecida. O custo é determinístico, diferente do custo esperado da PDE.</li>
                  <li><b>Hipóteses mantidas:</b> 720 horas por mês, produtibilidade constante, limites das usinas, penalidade de vertimento e custo terminal zero.</li>
                  <li><b>Solver:</b> SCIP via PySCIPOpt, com a mesma função <code>pl_unico_det</code> do Colab.</li>
                </ul>
              </Painel>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function Operacao({ r, carregando }) {
  const g = useGraficos()
  const nomes = [...r.nomes_uhe, ...r.nomes_ute, 'Déficit']
  const dados = nomes.map((_, k) => r.linhas.map(l => (k < r.nomes_uhe.length ? l.uhe[k] : k < nomes.length - 1 ? l.ute[k - r.nomes_uhe.length] : l.deficit)))
  const opG = useMemo(() => geracaoMensal(r.meses, nomes, dados, r.linhas.map(l => l.carga)), [r])   // eslint-disable-line
  const opA = useMemo(() => armazenamentoMensal(r.meses, r.nomes_uhe.map((n, i) => ({ nome: n, dados: r.armazenamento[i] }))), [r])
  const opC = useMemo(() => custosMensais(r.meses, [{ nome: 'PL Único', dados: r.linhas.map(l => l.ci / 1e6) }]), [r])
  return (
    <>
      <SeletorGraficos g={g} lista={[['carga', 'Atendimento à carga'], ['armaz', 'Armazenamento'], ['custo', 'Custo imediato']]} />
      {g.mostra('carga') && <Painel titulo="Atendimento à carga" carregando={carregando}><Grafico opcao={opG} altura={360} /></Painel>}
      {(g.mostra('armaz') || g.mostra('custo')) && <div className="linha l2b">
        {g.mostra('armaz') && <Painel titulo="Armazenamento" tag="% do volume útil"><Grafico opcao={opA} altura={320} /></Painel>}
        {g.mostra('custo') && <Painel titulo="Custo imediato por mês" tag="R$ milhões"><Grafico opcao={opC} altura={320} /></Painel>}
      </div>}
    </>
  )
}

function Resultados({ r, pedido }) {
  const linhas = r.linhas.map(l => ({
    'Mês': l.mes, 'Carga (MWm)': l.carga,
    ...Object.fromEntries(r.nomes_uhe.map((n, i) => [`${n} (MWm)`, l.uhe[i]])),
    ...Object.fromEntries(r.nomes_uhe.map((n, i) => [`VF ${n} (hm³)`, l.vf[i]])),
    ...Object.fromEntries(r.nomes_ute.map((n, i) => [`${n} (MWm)`, l.ute[i]])),
    'Déficit (MWm)': l.deficit, 'Custo imediato (R$)': l.ci,
  }))
  const cols = Object.keys(linhas[0])
  return (
    <Painel titulo="Resultados da trajetória">
      <div className="rolagem"><table>
        <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{linhas.map((l, i) => <tr key={i}>{cols.map(c => <td key={c} className="num">{typeof l[c] === 'number' ? fmt(l[c], 2) : l[c]}</td>)}</tr>)}</tbody>
      </table></div>
      <div className="dupla" style={{ marginTop: 14, maxWidth: 520 }}>
        <button className="botao" onClick={() => baixar('resultados_pl_unico.csv', paraCsv(linhas), 'text/csv')}>Baixar resultados (.csv)</button>
        <button className="botao fantasma" onClick={() => baixar('parametros_pl_unico.json', JSON.stringify(pedido, null, 2), 'application/json')}>Baixar parâmetros (.json)</button>
      </div>
      <p className="sub" style={{ marginTop: 10 }}>Custo total = soma dos custos imediatos. Vazões locais conhecidas; 720 h por estágio; custo terminal zero.</p>
    </Painel>
  )
}
