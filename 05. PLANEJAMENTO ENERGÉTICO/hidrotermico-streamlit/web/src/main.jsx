import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './estilo.css'

// Se algo quebrar, mostra o erro na tela em vez de deixar a página em branco.
class Limite extends React.Component {
  state = { erro: null }
  static getDerivedStateFromError(erro) { return { erro } }
  render() {
    return this.state.erro
      ? <pre style={{ color: '#ffb4b4', padding: 24, whiteSpace: 'pre-wrap' }}>Erro na interface:{'\n'}{String(this.state.erro.stack || this.state.erro)}</pre>
      : this.props.children
  }
}

createRoot(document.getElementById('root')).render(<Limite><App /></Limite>)
