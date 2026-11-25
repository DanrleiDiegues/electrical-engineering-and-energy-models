"""PDDE passo a passo: cada clique mostra um estágio do forward, do backward ou o cálculo de Zinf e Zsup.

Os passos não são simulados à parte: vêm do registro da própria função pdde() de pdde_model.py, a mesma usada
nas abas PDDE e COBRE × PDDE. O que aparece aqui é, portanto, exatamente o que o código faz.
"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

import pdde_model as pm

AZUL, LARANJA, VERDE, CINZA, ROSA = "#2a78d6", "#eb6834", "#1baf7a", "#898781", "#B74B74"
MESES = ["Jan", "Fev", "Mar", "Abr"]
CASOS = {
    "toy": dict(rotulo="Toy da documentação do COBRE (3 aberturas, contas à mão)", media=30., desvio=10., iteracoes=6,
                vmax_plot=100., unidade="$", escala=1.),
    "1dtoy": dict(rotulo="1dtoy do COBRE (10 aberturas, as mesmas do novomodelo)", media=40., desvio=10., iteracoes=8,
                  vmax_plot=250., unidade="R$ mil", escala=1e3),
}


@st.cache_data(show_spinner="Calculando a política e registrando cada passo…")
def gerar(chave):
    """Roda a pdde() com registro e devolve (eventos, cortes finais, caso, aberturas)."""
    c = CASOS[chave]
    if chave == "toy":
        caso, ab, seq = pm.caso_toy_documentacao(), pm.aberturas_toy(), [[1, 1, 1, 1], [2, 1, 1, 1]]
    else:
        import cobre_dados as cd
        caso, ab, seq = pm.caso_1dtoy(), cd.aberturas_cobre("original"), None
    reg = []
    r = pm.pdde(caso, ab, n_forward=1, max_iter=c["iteracoes"], semente=42, sequencias=seq, registro=reg)
    otimo = pm.equivalente_deterministico(caso, ab)
    return reg, r["cortes"], r["caso"], [np.asarray(a)[:, 0] for a in ab], otimo


def _fmt(x, c):
    return f"{x / c['escala']:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cabecalho(ev, n_it):
    if ev is None:
        titulo, cor = "Estado inicial — a política ainda não sabe nada (α = 0)", CINZA
    elif ev["tipo"] == "forward":
        titulo, cor = f"Iteração {ev['it']} de {n_it} · Forward · estágio {ev['t'] + 1} ({MESES[ev['t']]})", AZUL
    elif ev["tipo"] == "backward":
        titulo, cor = (f"Iteração {ev['it']} de {n_it} · Backward · estágio {ev['t'] + 1} ({MESES[ev['t']]}) "
                       f"→ corte para {MESES[ev['t'] - 1]}"), LARANJA
    else:
        titulo, cor = f"Iteração {ev['it']} de {n_it} · Zinf e Zsup", VERDE
    st.markdown(f'<div style="background:{cor};color:#fff;padding:8px 14px;font-size:20px;border-radius:4px;margin:6px 0">'
                f'{titulo}</div>', unsafe_allow_html=True)


def _caminho(eventos, i):
    """Aberturas escolhidas no forward da iteração do passo i, até o passo i."""
    ev = eventos[i]
    return {e["t"]: e for e in eventos[:i + 1] if e["tipo"] == "forward" and e["it"] == ev["it"]}


def _arvore(ev, eventos, i, ab):
    """As aberturas de cada mês (pontos) e o caminho que o forward sorteou nesta iteração (linha azul)."""
    fig = go.Figure()
    for t, a in enumerate(ab):
        cor = [CINZA] * len(a)
        if ev is not None and ev["tipo"] == "backward" and ev["t"] == t:
            cor = [LARANJA] * len(a)
        fig.add_scatter(x=[MESES[t]] * len(a), y=a, mode="markers", marker=dict(size=10, color=cor), showlegend=False,
                        hovertemplate="%{y:.1f} m³/s<extra></extra>")
    if ev is not None and ev["tipo"] in ("forward", "limites", "backward"):
        cam = _caminho(eventos, i) if ev["tipo"] == "forward" else {
            e["t"]: e for e in eventos if e["tipo"] == "forward" and e["it"] == ev["it"]}
        ts = sorted(cam)
        fig.add_scatter(x=[MESES[t] for t in ts], y=[float(cam[t]["afl"][0]) for t in ts], mode="lines+markers",
                        line=dict(color=AZUL, width=3), marker=dict(size=14, color=AZUL), name="caminho do forward",
                        hovertemplate="%{y:.1f} m³/s<extra></extra>")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), template="plotly_white", showlegend=False,
                      title="Aberturas de cada mês e o caminho sorteado", yaxis_title="Afluência (m³/s)")
    return fig


def _normal(ev, ab, c):
    """De onde vêm as aberturas: pontos da Normal, cada um com probabilidade 1/n. O forward sorteia um deles."""
    t = ev["t"] if ev is not None and ev["tipo"] in ("forward", "backward") else 0
    x = np.linspace(c["media"] - 4 * c["desvio"], c["media"] + 4 * c["desvio"], 300)
    dens = np.exp(-.5 * ((x - c["media"]) / c["desvio"]) ** 2) / (c["desvio"] * np.sqrt(2 * np.pi))
    fig = go.Figure()
    fig.add_scatter(x=x, y=dens, mode="lines", line=dict(color=CINZA), fill="tozeroy", fillcolor="rgba(137,135,129,.12)",
                    hoverinfo="skip")
    a = ab[t]
    topo = dens.max() * 1.15
    cores = [CINZA] * len(a)
    if ev is not None and ev["tipo"] == "forward":
        cores[ev["w"]] = AZUL
    elif ev is not None and ev["tipo"] == "backward":
        cores = [LARANJA] * len(a)
    for xi, ci in zip(a, cores):
        fig.add_scatter(x=[xi, xi], y=[0, topo * .55], mode="lines", line=dict(color=ci, width=3 if ci != CINZA else 1.5),
                        hoverinfo="skip")
    fig.add_scatter(x=a, y=[topo * .55] * len(a), mode="markers+text", marker=dict(size=9, color=cores),
                    text=[f"{v:.0f}" for v in a], textposition="top center", hovertemplate="%{x:.1f} m³/s · prob. 1/" + str(len(a)) + "<extra></extra>")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), template="plotly_white", showlegend=False,
                      title=f"Normal({c['media']:.0f}; {c['desvio']:.0f}) e as {len(a)} aberturas de {MESES[t]}",
                      xaxis_title="Afluência (m³/s)", yaxis=dict(showticklabels=False, range=[0, topo]))
    return fig


def _fcf(ev, cortes, caso, c, eventos, i):
    """A política: α_t(VF) = máximo dos cortes de cada mês até este passo. O corte novo aparece em laranja."""
    n = [0, 0, 0, 0] if ev is None else ev["n_cortes"]
    x = np.linspace(caso["uhes"][0]["vmin"], c["vmax_plot"], 200)
    figs = []
    novo = (ev["t"] - 1) if ev is not None and ev["tipo"] == "backward" and ev["novo"] else None
    for t in range(3):
        fig = go.Figure()
        cs = cortes[t][:n[t]]
        for j, (pi, b) in enumerate(cs):
            cor = LARANJA if (t == novo and j == len(cs) - 1) else "rgba(137,135,129,.45)"
            fig.add_scatter(x=x, y=(b + pi[0] * x) / c["escala"], mode="lines", line=dict(color=cor, width=3 if cor == LARANJA else 1),
                            hoverinfo="skip")
        env = np.maximum(np.max([b + pi[0] * x for pi, b in cs], axis=0), 0) if cs else 0 * x
        fig.add_scatter(x=x, y=env / c["escala"], mode="lines", line=dict(color=ROSA, width=3), hovertemplate="VF %{x:.0f} · α %{y:,.1f}<extra></extra>")
        # Onde o forward desta iteração deixou o reservatório no fim deste mês.
        cam = {e["t"]: e for e in eventos[:i + 1] if e["tipo"] == "forward" and ev is not None and e["it"] == ev["it"]}
        if t in cam:
            vf = float(cam[t]["r"]["v"][0])
            fig.add_vline(x=vf, line_dash="dot", line_color=AZUL)
        topo = max(float(env.max()) / c["escala"] * 1.1, 1.)
        fig.update_layout(height=230, margin=dict(l=10, r=10, t=36, b=10), template="plotly_white", showlegend=False,
                          title=f"α após {MESES[t]} · {len(cs)} corte(s)", xaxis_title="VF (hm³)",
                          yaxis=dict(title=c["unidade"], range=[0, topo]))
        figs.append(fig)
    return figs


def _texto(ev, caso, c, ab):
    if ev is None:
        return ("Sem cortes, α = 0 em todos os meses: para a política, a água guardada não vale nada no futuro. "
                "No primeiro forward ela tende a gastar a água cedo. Cada iteração acrescenta cortes que ensinam o valor da água.")
    if ev["tipo"] == "forward":
        r = ev["r"]
        return (f"**Recebe** VI = {ev['vi'][0]:.1f} hm³ (o VF do mês anterior) e a afluência sorteada "
                f"**{ev['afl'][0]:.1f} m³/s** (abertura {ev['w'] + 1} de {len(ab[ev['t']])}, " + ("fixada como na documentação" if caso.get('fator_volume') and ev['it'] <= 2 else "sorteada com probabilidade igual") + "). "
                f"Resolve min custo imediato + β·α usando os cortes **atuais** de {MESES[ev['t']]}. "
                f"**Entrega** VF = {r['v'][0]:.1f} hm³ ao próximo mês. "
                f"Custo imediato {_fmt(r['ci'], c)} {c['unidade']}, custo futuro estimado α = {_fmt(r['alpha'], c)} {c['unidade']}.")
    if ev["tipo"] == "backward":
        pi, b = ev["corte"]
        return (f"**Recebe** v̄ = {ev['v_barra'][0]:.1f} hm³ (o volume que o forward deixou no fim de {MESES[ev['t'] - 1]}). "
                f"Resolve {MESES[ev['t']]} para **todas** as {len(ev['abertas'])} aberturas com esse mesmo v̄ e tira a média: "
                f"inclinação π̄ = {pi[0] / c['escala']:,.3f} {c['unidade']}/hm³ (o valor da água) e custo médio. "
                f"**Entrega** a {MESES[ev['t'] - 1]} o corte α ≥ {_fmt(b, c)} {pi[0] / c['escala']:+,.3f}·VF "
                + ("(novo)." if ev["novo"] else "(igual a um corte que já existia, por isso descartado)."))
    return (f"**Zinf** = média, nas aberturas de Jan, do objetivo com o VI real: {_fmt(ev['zinf'], c)} {c['unidade']}. "
            f"Só sobe, porque cada corte novo só pode aumentar o custo futuro estimado. **Zsup** = custo do cenário do forward: "
            f"{_fmt(ev['zsup'], c)} {c['unidade']}. Com 1 forward é um único cenário, por isso oscila e não serve para parar.")


def passo_a_passo():
    st.subheader("PDDE passo a passo")
    st.caption("Cada clique mostra um estágio do forward, um estágio do backward ou o cálculo de Zinf e Zsup. Os passos são "
               "registrados pela própria função pdde() usada nas outras abas, com 1 forward por iteração.")
    chave = st.radio("Caso", list(CASOS), format_func=lambda k: CASOS[k]["rotulo"], horizontal=True, key="pdde_pp_caso")
    c = CASOS[chave]
    eventos, cortes, caso, ab, otimo = gerar(chave)
    passos = [None] + eventos
    n = len(passos)
    k = f"pdde_pp_{chave}"
    st.session_state.setdefault(k, 0)

    def mover(delta=None, para=None):
        st.session_state[k] = para if para is not None else min(max(st.session_state[k] + delta, 0), n - 1)

    b = st.columns([1, 1, 1, 1, 3])
    b[0].button("⏮ Início", on_click=mover, kwargs=dict(para=0), width="stretch", key="pdde_pp_ini")
    b[1].button("◀ Voltar", on_click=mover, kwargs=dict(delta=-1), width="stretch", key="pdde_pp_vol",
                disabled=st.session_state[k] == 0)
    b[2].button("Avançar ▶", on_click=mover, kwargs=dict(delta=1), width="stretch", key="pdde_pp_ava", type="primary",
                disabled=st.session_state[k] == n - 1)
    b[3].button("Fim ⏭", on_click=mover, kwargs=dict(para=n - 1), width="stretch", key="pdde_pp_fim")
    b[4].markdown(f"**Passo {st.session_state[k] + 1} de {n}**")
    st.select_slider("Ir para a iteração", list(range(1, c["iteracoes"] + 1)), key=f"pdde_pp_it_{chave}",
                     on_change=lambda: mover(para=next(j for j, p in enumerate(passos) if p is not None
                                                       and p["it"] == st.session_state[f"pdde_pp_it_{chave}"])))

    i = st.session_state[k]
    ev = passos[i]
    _cabecalho(ev, c["iteracoes"])
    st.info(_texto(ev, caso, c, ab).replace("$", "\\$"))

    col = st.columns(2)
    col[0].plotly_chart(_arvore(ev, eventos, max(i - 1, 0), ab), width="stretch", key="pdde_pp_arv")
    col[1].plotly_chart(_normal(ev, ab, c), width="stretch", key="pdde_pp_normal")
    st.caption("A Normal só é usada para **criar** as aberturas (pontos da curva, cada um com probabilidade 1/n). No forward o código "
               "sorteia o **índice** da abertura de forma uniforme, `w = rng.integers(n)`; no backward usa **todas**. "
               "No toy as aberturas {20, 30, 40} representam a Normal(30; 10) com 3 pontos.")

    if ev is not None and ev["tipo"] == "forward":
        r = ev["r"]
        m = st.columns(6)
        m[0].metric("VI (hm³)", f"{ev['vi'][0]:.1f}")
        m[1].metric("Afluência (m³/s)", f"{ev['afl'][0]:.1f}")
        m[2].metric("Turbinado (m³/s)", f"{r['q'][0]:.1f}")
        m[3].metric("Térmicas (MW)", f"{r['g'].sum():.1f}")
        m[4].metric("Déficit (MW)", f"{r['d']:.1f}")
        m[5].metric("VF (hm³)", f"{r['v'][0]:.1f}")
    elif ev is not None and ev["tipo"] == "backward":
        import pandas as pd
        st.dataframe(pd.DataFrame([{"Abertura (m³/s)": a["afl"][0], "VF (hm³)": a["v"][0], "Déficit (MW)": a["d"],
                                    f"Custo total Q ({c['unidade']})": a["obj"] / c["escala"],
                                    f"π = ∂Q/∂v̄ ({c['unidade']}/hm³)": a["pi"][0] / c["escala"]} for a in ev["abertas"]])
                     .style.format(precision=2), hide_index=True)

    st.markdown("**A política (FCF) de cada mês até este passo** — linha rosa = α(VF) = máximo dos cortes; "
                "laranja = corte criado neste passo; pontilhado azul = VF do forward desta iteração.")
    cols = st.columns(3)
    for t, fig in enumerate(_fcf(ev, cortes, caso, c, eventos, max(i - 1, 0))):
        cols[t].plotly_chart(fig, width="stretch", key=f"pdde_pp_fcf{t}")
    st.caption("Abril não tem corte: depois do horizonte o custo futuro é zero. Cada backward manda um corte para o mês anterior.")

    lim = [e for e in eventos[:max(i - 1, 0) + 1] if e["tipo"] == "limites"] if ev is not None else []
    if lim:
        fig = go.Figure()
        fig.add_scatter(x=[e["it"] for e in lim], y=[e["zsup"] / c["escala"] for e in lim], mode="markers", name="Zsup",
                        marker=dict(color=CINZA, size=9))
        fig.add_scatter(x=[e["it"] for e in lim], y=[e["zinf"] / c["escala"] for e in lim], mode="lines+markers", name="Zinf",
                        line_color=VERDE)
        fig.add_hline(y=otimo / c["escala"], line_dash="dot", line_color="#41464D", annotation_text="ótimo da árvore")
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=36, b=10), template="plotly_white",
                          title="Zinf e Zsup até este passo", xaxis=dict(title="Iteração", dtick=1), yaxis_title=c["unidade"],
                          legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, width="stretch", key="pdde_pp_lim")
