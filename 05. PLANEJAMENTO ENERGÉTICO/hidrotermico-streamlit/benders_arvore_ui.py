"""Aba "Benders na árvore": a decomposição da PDDD aplicada a uma árvore de cenários (Benders aninhado).

Não é o que o professor pediu na PDDD (lá é uma trajetória). É o degrau entre a PDDD e a PDDE: mostra que cortes
funcionam com incerteza, mas também por que a árvore inteira não escala — o problema que a PDDE resolve.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modelo_arvore import cortes_da_continuacao, disciplina, estudo_arvore, fator
from pddd_model import pddd

CORES = ["#1B6B82", "#4B9999", "#C18523", "#7F6A55", "#B74B74", "#5B6CB0"]


@st.cache_data(max_entries=8, show_spinner="Resolvendo o PL em árvore e o Benders aninhado na mesma árvore…")
def comparar_arvore(meses):
    """PL Único em árvore × Benders aninhado visitando todos os nós da mesma árvore (caso da disciplina)."""
    util = disciplina["vmax"] - disciplina["vmin"]
    p = dict(carga=250., cdef=4000., afl=100.,
             uhes=[(disciplina["vmin"][i], disciplina["vmax"][i], 100 * (disciplina["vi"][i] - disciplina["vmin"][i]) / util[i],
                    disciplina["qmax"][i] / fator, disciplina["prod"][i] * fator) for i in range(2)],
             termicas=[("BBF Baliza", 10., 882.76), ("ERB Candeias", 17., 118.93)])
    custo, caso, arv, _ = estudo_arvore(["BBF Baliza", "ERB Candeias"], meses, p)

    # Mesmo código da PDDD; a única diferença é passar a árvore: o forward visita TODOS os nós e o backward
    # gera um corte médio por nó pai (média ponderada pelas probabilidades dos filhos).
    r = pddd(caso, cortes_da_continuacao(caso), arvore=arv)
    nos = sum(len(n) for n in arv) if isinstance(arv, (list, tuple)) else None
    return custo, r["zsup"], r["zinf"], r["iteracoes"], pd.DataFrame(r["historico"]), nos, r["segundos"]


def benders_arvore():
    st.header("Benders aninhado na árvore — o degrau entre a PDDD e a PDDE")
    st.markdown(
        "Na aba **PDDD** a comparação é a que o professor pediu: **uma trajetória** de afluências, PDDD = PL Único. "
        "Aqui a mesma decomposição roda numa **árvore de cenários** (o caso da aba *PL Único em árvore*). "
        "O nome correto é **Benders aninhado** (*nested Benders*): não é a PDDD do trabalho, e por isso ficou separada.")
    c = st.columns(3)
    c[0].markdown("**PDDD (trajetória)**  \n1 nó por mês. Forward e backward passam pelo mesmo caminho. "
                  "Corte = dual do único filho.")
    c[1].markdown("**Benders aninhado (árvore)**  \nTodos os nós no forward. Cada nó pai recebe um corte **médio** "
                  "dos filhos. Exato, mas o número de nós cresce como $n^T$.")
    c[2].markdown("**PDDE (próxima aba)**  \nIndependência entre estágios: **um** conjunto de cortes por estágio, "
                  "forward **amostrado**. Escala para muitos meses, mas o $Z_{sup}$ vira estimativa.")

    m = st.slider("Meses da árvore", 3, 7, 3, key="benders_arv_meses",
                  help="Árvore binária (seco/úmido) a partir do 2º mês: 2^(T−1) cenários.")
    custo, zsup, zinf, it, hist, _, seg = comparar_arvore(m)
    k = st.columns(4)
    k[0].metric("PL Único em árvore (R$)", f"{custo:,.2f}")
    k[1].metric("Benders aninhado · Zsup (R$)", f"{zsup:,.2f}")
    k[2].metric("Diferença (R$)", f"{abs(zsup - custo):,.4f}")
    k[3].metric("Iterações", it)
    fig = go.Figure()
    fig.add_scatter(x=hist.iteracao, y=hist.zsup / 1e6, name="Zsup", mode="lines+markers", line_color=CORES[4])
    fig.add_scatter(x=hist.iteracao, y=hist.zinf / 1e6, name="Zinf", mode="lines+markers", line_color=CORES[0])
    fig.add_hline(y=custo / 1e6, line_dash="dot", line_color="#41464D", annotation_text="PL em árvore")
    fig.update_layout(title="Evolução de Zinf e Zsup na árvore", height=340, template="plotly_white",
                      margin=dict(l=10, r=10, t=50, b=10), yaxis_title="R$ milhões", xaxis_title="Iteração",
                      legend=dict(orientation="h", y=-0.25), hovermode="x unified")
    st.plotly_chart(fig, width="stretch", key="benders_arv_conv")

    cen = 2 ** (m - 1)
    st.markdown(
        f"Com {m} meses a árvore tem **{cen} cenários**; com 12 meses seriam {2 ** 11:,}, e com 10 aberturas por mês "
        f"(como no 1dtoy) 10¹¹. Aqui $Z_{{sup}}$ é **exato** (soma ponderada de todos os nós), por isso o gap fecha como na PDDD. "
        "Na PDDE o forward só sorteia alguns cenários, e $Z_{sup}$ passa a ter intervalo de confiança.")
    with st.expander("O que cada estágio recebe e entrega aqui"):
        st.markdown(
            "- **Forward, nó do mês t:** recebe o volume final do **nó pai** e a afluência do próprio nó; entrega o seu volume final "
            "a cada filho.\n"
            "- **Backward, nó do mês t:** recebe os cortes que **seus** filhos deixaram; resolve cada filho e entrega ao pai um corte "
            "médio $\\alpha \\ge \\sum_k p_k (b_k + \\pi_k^\\top V^F)$.\n"
            "- **Diferença para a PDDE:** lá o corte é do **estágio** (vale para todos os nós do mês), porque as aberturas de um mês "
            "não dependem do mês anterior.")
