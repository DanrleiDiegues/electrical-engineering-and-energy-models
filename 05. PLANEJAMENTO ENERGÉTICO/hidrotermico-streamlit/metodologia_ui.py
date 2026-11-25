"""Aba Metodologia: descrição dos métodos, com opção de imprimir ou salvar em PDF."""
import json

import streamlit as st

from metodologia import desenhar, documento_html


def metodologia():
    st.header("Metodologia — modelo, métodos e algoritmos")
    st.caption("Este texto acompanha a evolução do código. A mesma fonte gera a página abaixo e o documento para impressão.")
    doc = documento_html()
    c1, c2 = st.columns([1, 1])
    with c1:
        # O botão abre o documento numa janela própria e chama a impressão do navegador
        # ("Salvar como PDF" gera o arquivo). O documento usa KaTeX, com fórmulas em Computer Modern.
        st.iframe(f"""
<button id="b" style="width:100%;padding:.55rem 1rem;border-radius:.5rem;border:1px solid #1B6B82;background:#1B6B82;
color:#fff;font:600 14px sans-serif;cursor:pointer">Imprimir ou salvar em PDF</button>
<script>
const doc = {json.dumps(doc)};
document.getElementById('b').onclick = () => {{
  const w = window.open('', '_blank');
  if (!w) {{ alert('Permita janelas pop-up para imprimir.'); return; }}
  w.document.open(); w.document.write(doc); w.document.close();
  const pronto = () => w.document.body && w.document.body.dataset.pronto ? setTimeout(() => w.print(), 300) : setTimeout(pronto, 200);
  pronto();
}};
</script>""", height=48)
    with c2:
        st.download_button("Baixar como página (HTML)", doc.encode("utf-8"), "planejamento_energetico_metodos.html",
                           "text/html", key="metodologia_html", width="stretch")
    st.divider()
    desenhar(st)
