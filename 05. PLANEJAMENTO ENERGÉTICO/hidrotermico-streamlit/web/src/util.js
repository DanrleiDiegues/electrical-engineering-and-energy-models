// Funções de apoio compartilhadas pelas telas.
export const CALENDARIO = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

export const gerarMeses = (n, inicio = 0) =>
  Array.from({ length: n }, (_, t) => (n <= 12 ? CALENDARIO[(inicio + t) % 12] : `${CALENDARIO[(inicio + t) % 12]} · ciclo ${1 + Math.floor((inicio + t) / 12)}`))

// Ajusta o tamanho de uma lista, repetindo o último valor (como o app Streamlit faz ao mudar o horizonte).
export const ajusta = (lista, n) => Array.from({ length: n }, (_, i) => (i < lista.length ? lista[i] : lista[lista.length - 1]))

export function baixar(nome, conteudo, tipo = 'text/plain') {
  const url = URL.createObjectURL(new Blob([conteudo], { type: tipo + ';charset=utf-8' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: nome })
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
}

// Lista de objetos -> CSV com ponto e vírgula e vírgula decimal (abre direto no Excel em português).
export function paraCsv(linhas) {
  if (!linhas.length) return ''
  const cols = Object.keys(linhas[0])
  const cel = v => (typeof v === 'number' ? String(v).replace('.', ',') : `"${String(v).replace(/"/g, '""')}"`)
  return '﻿' + [cols.join(';'), ...linhas.map(l => cols.map(c => cel(l[c])).join(';'))].join('\n')
}
