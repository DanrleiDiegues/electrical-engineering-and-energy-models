// @vitest-environment jsdom
// @vitest-environment-options {"url":"http://localhost/?demo"}
import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { createRoot } from 'react-dom/client'
import { act } from 'react'

vi.mock('../src/componentes/Grafico.jsx', () => ({ default: () => <div data-grafico /> }))
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const espera = ms => new Promise(r => setTimeout(r, ms))
async function ate(raiz, texto) { for (let i = 0; i < 60 && !raiz.textContent.includes(texto); i++) await act(async () => { await espera(250) }) }

describe('interface em modo demonstração', () => {
  beforeEach(() => { location.hash = ''; document.body.innerHTML = '' })
  it('seletor de gráficos esconde e mostra cada gráfico', async () => {
    const App = (await import('../src/App.jsx')).default
    const raiz = document.createElement('div'); document.body.appendChild(raiz)
    await act(async () => { createRoot(raiz).render(<App />) })
    await ate(raiz, 'Custo total')
    const chip = nome => [...raiz.querySelectorAll('.seletor button')].find(b => b.textContent === nome)
    expect(raiz.querySelectorAll('.seletor button.ativa').length).toBe(4)   // todos ligados por padrão
    await act(async () => { chip('Despacho').click() })
    expect(raiz.querySelectorAll('[data-grafico]').length).toBe(2)
    expect(raiz.textContent).not.toContain('MW · meia hora')
    await act(async () => { chip('Mostrar todos').click() })
    expect(raiz.querySelectorAll('[data-grafico]').length).toBe(3)
  })

  it('mostra a abertura com o sol e a chuva e troca de aba com transição', async () => {
    const App = (await import('../src/App.jsx')).default
    const raiz = document.createElement('div'); document.body.appendChild(raiz)
    await act(async () => { createRoot(raiz).render(<App />) })
    expect(raiz.querySelector('.abertura .sol')).toBeTruthy()
    await act(async () => { [...raiz.querySelectorAll('.abas button')].find(b => b.textContent === 'PL Único').click() })
    expect(raiz.querySelector('.pagina.saindo')).toBeTruthy()
    await ate(raiz, 'Custo total · PL Único')
    expect(raiz.querySelector('.pagina.entrando')).toBeTruthy()
    await act(async () => { await espera(2200) })
    expect(raiz.querySelector('.abertura')).toBeNull()
  })

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

  it('renderiza PL Único e PDE Didática, com o cálculo em segundo plano simulado', async () => {
    const App = (await import('../src/App.jsx')).default
    const raiz = document.createElement('div'); document.body.appendChild(raiz)
    await act(async () => { createRoot(raiz).render(<App />) })
    const aba = nome => [...raiz.querySelectorAll('.abas button')].find(b => b.textContent === nome)
    await act(async () => { aba('PL Único').click() })
    await ate(raiz, 'Custo total · PL Único')
    expect(raiz.textContent).toContain('Atendimento à carga')
    await act(async () => { [...raiz.querySelectorAll('.subabas button')].find(b => b.textContent.includes('Resultados')).click() })
    expect(raiz.textContent).toContain('Baixar resultados (.csv)')
    await act(async () => { aba('PDE Didática').click() })
    await ate(raiz, 'Calcular')
    await act(async () => { [...raiz.querySelectorAll('button')].find(b => b.textContent === 'Calcular').click() })
    await ate(raiz, 'Esperado inicial')
    expect(raiz.textContent).toContain('Isolados − planejado')
    await act(async () => { [...raiz.querySelectorAll('.subabas button')].find(b => b.textContent.includes('Custos futuros')).click() })
    expect(raiz.textContent).toContain('Custo esperado por par de volumes iniciais')
  })
})
