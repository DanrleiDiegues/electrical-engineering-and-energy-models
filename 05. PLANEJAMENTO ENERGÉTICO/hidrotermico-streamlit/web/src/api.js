// Cliente da API Python. Com ?demo na URL, usa dados de exemplo salvos em src/demo/ (não precisa da API).
export const DEMO = import.meta.env.MODE === 'arquivo' || new URLSearchParams(location.search).has('demo')
const BASE = '/api'

async function chamar(caminho, corpo) {
  const opcoes = corpo ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) } : undefined
  let r
  try { r = await fetch(BASE + caminho, opcoes) }
  catch { throw new Error('Não foi possível falar com a API. Ela está rodando? (uvicorn api.main:app --reload)') }
  if (!r.ok) {
    const e = await r.json().catch(() => ({}))
    throw new Error(typeof e.detail === 'string' ? e.detail : r.statusText)
  }
  return r.json()
}

const exemplo = nome => import(`./demo/${nome}.json`).then(m => m.default)

export const api = {
  catalogo: () => (DEMO ? exemplo('catalogo') : chamar('/catalogo')),
  semana: pedido => (DEMO ? exemplo('semana') : chamar('/semana', pedido)),
  arvorePadroes: () => (DEMO ? exemplo('arvore_padroes') : chamar('/arvore/padroes')),
  arvore: pedido => (DEMO ? exemplo('arvore') : chamar('/arvore', pedido)),
}
