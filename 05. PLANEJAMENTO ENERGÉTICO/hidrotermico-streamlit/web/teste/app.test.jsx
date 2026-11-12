// @vitest-environment jsdom
// @vitest-environment-options {"url":"http://localhost/?demo"}
import { describe, it, expect, vi } from 'vitest'
import React from 'react'
import { createRoot } from 'react-dom/client'
import { act } from 'react'

vi.mock('../src/componentes/Grafico.jsx', () => ({ default: () => <div data-grafico /> }))
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const espera = ms => new Promise(r => setTimeout(r, ms))
async function ate(raiz, texto) { for (let i = 0; i < 60 && !raiz.textContent.includes(texto); i++) await act(async () => { await espera(250) }) }

describe('interface em modo demonstração', () => {
  it('renderiza as duas abas sem quebrar', async () => {
    const App = (await import('../src/App.jsx')).default
    const raiz = document.createElement('div'); document.body.appendChild(raiz)
    await act(async () => { createRoot(raiz).render(<App />) })
    await ate(raiz, 'Custo total')
    expect(raiz.textContent).toContain('Custo total')
    expect(raiz.textContent).toContain('Por que a térmica entra antes da água?')
    expect(raiz.querySelectorAll('[data-grafico]').length).toBe(3)
    await act(async () => { [...raiz.querySelectorAll('.abas button')].find(b => b.textContent.includes('árvore')).click() })
    await ate(raiz, 'Folhas mais prováveis')
    expect(raiz.textContent).toContain('Trajetórias finais')
    expect(raiz.textContent).toContain('Folhas mais prováveis')
  })
})
