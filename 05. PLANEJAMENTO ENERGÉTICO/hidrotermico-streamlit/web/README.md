# Interface React (Planejamento Energético)

Interface em React (Vite + ECharts) que consome a API Python da pasta `../api`.
A matemática continua toda em Python; o React só desenha e envia parâmetros.

## Rodar (dois terminais)

```bash
# 1) API, na pasta hidrotermico-streamlit
python -m uvicorn api.main:app --reload

# 2) Interface, nesta pasta (web)
npm install
npm run dev          # abre em http://localhost:5173
```

As chamadas a `/api/...` são repassadas à porta 8000 pelo `vite.config.js`.

## Sem a API (demonstração)

`demo.html` é a interface inteira em um único arquivo, com dados de exemplo salvos em `src/demo/`.
Dê dois cliques nele para abrir no navegador. Para regerar: `npm run build:arquivo` (saída em `dist/index.html`).
Em desenvolvimento, `http://localhost:5173/?demo` faz o mesmo.

## Onde mexer

| Arquivo | Conteúdo |
|---|---|
| `src/api.js` | chamadas HTTP à API |
| `src/PDE.jsx` | aba PDE Didática: grade de volumes, operação, custos futuros, exportação |
| `src/PL.jsx` | aba PL Único: entradas mensais, operação, resultados |
| `src/Semana.jsx` | aba DESSEM semanal: controles, KPIs, medidores, gráficos, mérito, impacto |
| `src/Arvore.jsx` | aba PL em árvore: parâmetros, árvore, folhas |
| `src/opcoes.js` | configuração de todos os gráficos (ECharts) |
| `src/componentes/Cenario.jsx` e `src/estilo.css` | imagem de fundo (`public/fundo.jpg` ou a URL da Acciona) |
| `src/estilo.css` | tema de vidro, cores e layout |
