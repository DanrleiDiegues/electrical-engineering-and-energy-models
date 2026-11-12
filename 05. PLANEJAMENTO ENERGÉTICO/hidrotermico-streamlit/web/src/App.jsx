import { useEffect, useState } from 'react'
import Cenario from './componentes/Cenario.jsx'
import Semana from './Semana.jsx'
import Arvore from './Arvore.jsx'
import { api, DEMO } from './api.js'

const Icone = ({ d }) => <svg viewBox="0 0 24 24"><path d={d} /></svg>
const ICONES = {
  semana: 'M3 12h4l3-8 4 16 3-8h4',
  arvore: 'M12 3v6M12 9l-6 5M12 9l6 5M6 14v7M18 14v7',
}

export default function App() {
  const [aba, setAba] = useState(() => (location.hash === '#arvore' ? 'arvore' : 'semana'))
  const [online, setOnline] = useState(DEMO)
  useEffect(() => { DEMO || api.catalogo().then(() => setOnline(true)).catch(() => setOnline(false)) }, [])
  const ir = a => { setAba(a); location.hash = a === 'arvore' ? 'arvore' : '' }
  return (
    <>
      <Cenario />
      <nav className="lateral">
        {Object.entries(ICONES).map(([k, d]) => <button key={k} className={aba === k ? 'ativa' : ''} title={k === 'semana' ? 'DESSEM semanal' : 'PL em árvore'} onClick={() => ir(k)}><Icone d={d} /></button>)}
      </nav>
      <main className="app">
        <header className="topo">
          <div className="marca">
            <svg width="38" height="38" viewBox="0 0 40 40" fill="none" stroke="#4f8df0" strokeWidth="2.2" strokeLinecap="round"><path d="M6 24c5-6 9 6 14 0s9 6 14 0" /><path d="M6 31c5-6 9 6 14 0s9 6 14 0" opacity=".6" /><path d="M20 4v13M14 9l6 8 6-8" stroke="#ff8a3d" /></svg>
            <div>Planejamento Energético<small>Hidrotérmico · UFJF</small></div>
          </div>
          <div className="abas">
            <button className={aba === 'semana' ? 'ativa' : ''} onClick={() => ir('semana')}>DESSEM semanal</button>
            <button className={aba === 'arvore' ? 'ativa' : ''} onClick={() => ir('arvore')}>PL em árvore</button>
          </div>
          <div className="pilula"><span className={`ponto ${online ? '' : 'off'}`} />{DEMO ? 'Dados de demonstração' : online ? 'API conectada' : 'API offline'}</div>
        </header>
        {aba === 'semana' ? <Semana /> : <Arvore />}
      </main>
    </>
  )
}
