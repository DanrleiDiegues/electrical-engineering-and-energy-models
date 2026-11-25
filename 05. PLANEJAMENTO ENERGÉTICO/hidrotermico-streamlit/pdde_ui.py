"""Aba PDDE: a política estocástica com um seletor de caso (1dtoy do COBRE, Batalha sozinha, Batalha + Serra)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import pdde_model as pm

CORES = ["#1B6B82", "#4B9999", "#C18523", "#7F6A55", "#B74B74", "#5B6CB0"]
CASOS = {"toy": "Toy da documentação do COBRE (resolvido à mão, 1 UHE)",
         "1dtoy": "1dtoy do COBRE (1 UHE, dados idênticos ao novomodelo)",
         "batalha": "Batalha sozinha (PySDDP) — semelhante ao 1dtoy",
         "cascata": "Batalha + Serra do Facão (PySDDP) — trabalho da disciplina"}


def _layout(fig, titulo, y, altura=360):
    fig.update_layout(title=titulo, height=altura, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
                      yaxis_title=y, legend=dict(orientation="h", y=-0.25), hovermode="x unified")
    return fig


def montar_caso(chave, p):
    """Caso e aberturas a partir das escolhas da barra lateral. Devolve (caso, aberturas, rótulos das aberturas)."""
    if chave == "toy":
        return pm.caso_toy_documentacao(), pm.aberturas_toy(), None
    if chave == "1dtoy":
        caso = pm.caso_1dtoy()
        if p["origem"] == "cobre":
            import cobre_dados as cd
            return caso, cd.aberturas_cobre("original" if p["n_ab"] == 10 else "professor"), None
        return caso, pm.aberturas_normal(caso, p["n_ab"], p["semente_ab"]), None
    usinas = ("Batalha",) if chave == "batalha" else ("Batalha", "Serra do Facão")
    caso = pm.caso_pysddp(usinas, mes_inicial=p["mes"], n_meses=p["meses"], carga=p["carga"], vi_pct=p["vi"],
                          cdef=p["cdef"], taxa_anual=p["taxa"])
    if p["economia_1dtoy"]:
        # Mesmas regras econômicas do 1dtoy: excesso penalizado, vertimento e turbinamento com custo.
        caso.update(custo_excesso=100., custo_vert=.01 / .0036, custo_turb=.05 / .0036)
    ab, rot = pm.aberturas_historicas(caso, p["n_ab"], p["semente_ab"])
    return caso, ab, rot


@st.cache_data(max_entries=12, show_spinner=False)
def treinar(chave, p, n_forward, max_iter, semente, n_sim):
    caso, ab, rot = montar_caso(chave, dict(p))
    barra = st.progress(0., "Treinando a PDDE…")
    # No toy, as duas primeiras iterações seguem o forward da documentação: ε = 0 e depois ε = (+1, 0, 0, 0).
    seq = [[1, 1, 1, 1], [2, 1, 1, 1]] if chave == "toy" and p.get("seq_doc") else None
    r = pm.pdde(caso, ab, n_forward=n_forward, max_iter=max_iter, semente=semente, sequencias=seq,
                progresso=lambda h, n: barra.progress(h["iteracao"] / n, f"Iteração {h['iteracao']}/{n} · Zinf R$ {h['zinf']:,.0f}"))
    barra.empty()

    # Simulação DENTRO da amostra: sequências sorteadas entre as mesmas aberturas usadas no treino.
    rng = np.random.default_rng(semente + 1)
    cen = np.array([[a[rng.integers(len(a))] for a in ab] for _ in range(n_sim)])
    custos, traj = pm.simular(caso, r["cortes"], cen)

    # O ótimo exato (equivalente determinístico) só cabe em árvores pequenas.
    nos = int(np.sum(np.cumprod([len(a) for a in ab])))
    otimo = pm.equivalente_deterministico(caso, ab) if nos <= 15000 else None
    return dict(historico=pd.DataFrame(r["historico"]), cortes=r["cortes"], segundos=r["segundos"], custos=custos,
                estagios=pd.DataFrame(pm.resumo_estagios(traj, r["caso"])), otimo=otimo, nos=nos,
                vol=np.array([[x["v"] for x in tr] for tr in traj]), caso=r["caso"],
                aberturas=[np.asarray(a).tolist() for a in ab], rotulos=rot)


def _barra_lateral():
    sb = st.sidebar
    chave = sb.selectbox("Caso da PDDE", list(CASOS), format_func=CASOS.get, key="pdde_caso")
    p = {}
    if chave == "toy":
        p["seq_doc"] = sb.checkbox("Forward das 2 primeiras iterações igual ao da documentação", True, key="pdde_toy_seq")
        padrao = (1, 10)
    elif chave == "1dtoy":
        p["origem"] = sb.radio("Aberturas", ["cobre", "normal"], key="pdde_origem",
                               format_func=lambda o: "As mesmas do COBRE (semente 42 do novomodelo)" if o == "cobre"
                               else "Sorteadas por nós de Normal(40; 10)")
        if p["origem"] == "cobre":
            p["n_ab"] = sb.radio("Aberturas por estágio", [10, 3], key="pdde_nab_cobre",
                                 format_func=lambda n: f"{n} ({'exemplo oficial' if n == 10 else 'configuração da aula'})")
        else:
            p["n_ab"] = sb.slider("Aberturas por estágio", 2, 30, 10, key="pdde_nab_normal")
        p["semente_ab"] = sb.number_input("Semente das aberturas", 0, 9999, 42, key="pdde_sem_ab")
        padrao = (1, 128) if p.get("n_ab") == 10 else (10, 50)
    else:
        import dados_pysddp as dp
        p["mes"] = sb.selectbox("Mês inicial", range(1, 13), 0 if chave == "batalha" else 8, key=f"pdde_mes_{chave}", format_func=lambda m: dp.MESES[m - 1])
        p["meses"] = sb.slider("Estágios (meses)", 2, 12, 4, key="pdde_meses")
        p["n_ab"] = sb.slider("Aberturas por mês (anos históricos)", 2, 20, 10, key="pdde_nab_hist")
        p["semente_ab"] = sb.number_input("Semente do sorteio dos anos", 0, 9999, 42, key="pdde_sem_hist")
        vb = sb.slider("Volume inicial Batalha (% útil)", 0., 100., 5. if chave == "batalha" else 39.7, .5, key=f"pdde_vib_{chave}")
        p["vi"] = (vb,) if chave == "batalha" else (vb, sb.slider("Volume inicial Serra (% útil)", 0., 100., 50.2, .5, key="pdde_vis"))
        auto = sb.checkbox("Carga com a mesma folga do 1dtoy", chave == "batalha", key=f"pdde_auto_{chave}",
                           help="Carga = energia hidráulica média + 117% da capacidade térmica, como 75 = 40 + 35 MW no 1dtoy.")
        p["carga"] = None if auto else sb.number_input("Carga (MW médios)", 0., 400., 75. if chave == "batalha" else 250.,
                                                       5., key=f"pdde_carga_{chave}")
        p["economia_1dtoy"] = sb.checkbox("Regras econômicas do 1dtoy", chave == "batalha", key=f"pdde_eco_{chave}",
                                          help="Déficit R$ 7.500/MWh, desconto de 12% a.a., excesso e turbinamento penalizados.")
        p["cdef"] = 7500. if p["economia_1dtoy"] else sb.number_input("Custo de déficit (R$/MWh)", 0., 20000., 4000., 100.,
                                                                      key="pdde_cdef")
        p["taxa"] = .12 if p["economia_1dtoy"] else 0.
        padrao = (5, 30)
    n_forward = sb.slider("Forwards por iteração", 1, 50, padrao[0], key=f"pdde_fw_{chave}_{p.get('n_ab')}")
    max_iter = sb.slider("Iterações", 5, 200, padrao[1], key=f"pdde_it_{chave}_{p.get('n_ab')}")
    semente = sb.number_input("Semente do forward", 0, 9999, 42, key="pdde_sem")
    n_sim = sb.slider("Cenários na simulação final", 50, 1000, 200, 50, key="pdde_sim")
    return chave, p, n_forward, max_iter, semente, n_sim


def pdde_aba():
    st.header("PDDE — Programação Dinâmica Dual Estocástica")
    st.markdown("Cortes como na PDDD, mas com **incerteza**: em cada estágio as aberturas são equiprováveis e independentes do "
                "estágio anterior. Isso permite **um** conjunto de cortes por estágio (e não por nó, como no Benders na árvore) "
                "e um forward **amostrado**. Escolha o caso na barra lateral; *Batalha sozinha* é o nosso sistema no formato do 1dtoy.")
    from metodologia import mostrar_algoritmo
    mostrar_algoritmo(st, '10.')
    chave, p, n_forward, max_iter, semente, n_sim = _barra_lateral()
    with st.expander("Dados do caso", expanded=False):
        caso, ab, rot = montar_caso(chave, p)
        c = st.columns(2)
        c[0].dataframe(pd.DataFrame([{k: u.get(k) for k in ("nome", "vmin", "vmax", "qmax", "prod", "gmax")} for u in caso["uhes"]]),
                       hide_index=True)
        c[0].dataframe(pd.DataFrame(caso["utes"]), hide_index=True)
        c[1].markdown(f"- Carga: **{caso['carga'][0]:.1f} MW** · Déficit: **R\\$ {caso['cdef']:,.0f}/MWh**  \n"
                      f"- Volume inicial: {', '.join(f'{v:.1f}' for v in caso['v0'])} hm³  \n"
                      f"- Desconto: {100 * caso.get('taxa_anual', 0):.0f}% a.a. · Estágios: {', '.join(caso['meses'])}")
        tab = pd.DataFrame({caso["meses"][t]: [f"{x:.1f}" for x in np.asarray(a).sum(axis=1)] for t, a in enumerate(ab)})
        if rot:
            tab = pd.DataFrame({caso["meses"][t]: [f"{x:.1f} ({r.split('/')[1]})" for x, r in zip(np.asarray(a).sum(axis=1), rot[t])]
                                for t, a in enumerate(ab)})
        c[1].caption("Aberturas (m³/s, soma das UHEs" + (", ano histórico" if rot else "") + ")")
        c[1].dataframe(tab, hide_index=True)

    # Só treina ao clicar: o 1dtoy com 128 iterações leva ~20 s. Os resultados ficam enquanto os parâmetros não mudarem.
    chave_treino = repr((chave, sorted(p.items()), n_forward, max_iter, semente, n_sim))
    if st.button("Treinar a PDDE", type="primary", key="pdde_rodar"):
        st.session_state["pdde_treinado"] = chave_treino
    if st.session_state.get("pdde_treinado") != chave_treino:
        st.info("Ajuste o caso e clique em **Treinar a PDDE**. O 1dtoy com 128 iterações leva cerca de 20 s.")
        return
    r = treinar(chave, p, n_forward, max_iter, semente, n_sim)
    if chave == "toy":
        mostrar_toy(r)
    mostrar_resultado(r, chave)


def mostrar_toy(r):
    """Confere o nosso código com as contas à mão da página toy-single-reservoir do novomodelo."""
    h = r["historico"]
    doc = {1: 5000 / 9, 2: 16000 / 27}
    st.markdown("**Conferência com a documentação** "
                "([toy-single-reservoir](https://modelossetoreletrico.org.br/docs/examples/toy-single-reservoir/))")
    st.dataframe(pd.DataFrame([
        {"Item": "Zinf iteração 1", "Documentação": doc[1], "Nosso": h.zinf.iloc[0]},
        {"Item": "Zinf iteração 2", "Documentação": doc[2], "Nosso": h.zinf.iloc[1] if len(h) > 1 else np.nan},
        {"Item": "Ótimo esperado (17000/27)", "Documentação": 17000 / 27, "Nosso": r["otimo"]},
        {"Item": "Zinf final", "Documentação": 17000 / 27, "Nosso": h.zinf.iloc[-1]}]).style.format(precision=2), hide_index=True)
    st.caption("O corte do estágio 3 sai igual ao da página (θ ≥ 500 − 100/3·v). Nos estágios 1 e 2 os cortes podem diferir porque, "
               "com o reservatório exatamente vazio, o LP é degenerado: o dual pode ser 50 (térmica) ou 100/3 (valor da água), e os dois "
               "são subgradientes válidos. Os caminhos de Zinf mudam, mas o ótimo 17000/27 é o mesmo.")


def mostrar_resultado(r, chave):
    h = r["historico"]
    k = st.columns(4)
    k[0].metric("Zinf final (R$)", f"{h.zinf.iloc[-1]:,.2f}")
    k[1].metric("Simulação: custo médio (R$)", f"{r['custos'].mean():,.0f}",
                f"± {1.96 * r['custos'].std(ddof=1) / np.sqrt(len(r['custos'])):,.0f} (IC95%)", delta_color="off")
    k[2].metric("Ótimo exato da árvore (R$)", f"{r['otimo']:,.2f}" if r["otimo"] else "—",
                f"Zinf − ótimo: {h.zinf.iloc[-1] - r['otimo']:,.0f}" if r["otimo"] else f"{r['nos']:,} nós: grande demais",
                delta_color="off")
    k[3].metric("Tempo de treino", f"{r['segundos']:.1f} s", f"{int(h.cortes.iloc[-1])} cortes", delta_color="off")

    fig = go.Figure()
    fig.add_scatter(x=h.iteracao, y=h.zsup_sup / 1e6, line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=h.iteracao, y=h.zsup_inf / 1e6, fill="tonexty", fillcolor="rgba(183,75,116,.15)", line=dict(width=0),
                    name="IC95% do Zsup")
    fig.add_scatter(x=h.iteracao, y=h.zsup / 1e6, name="Zsup (média dos forwards)", mode="lines", line_color=CORES[4])
    fig.add_scatter(x=h.iteracao, y=h.zinf / 1e6, name="Zinf", mode="lines+markers", line_color=CORES[0])
    if r["otimo"]:
        fig.add_hline(y=r["otimo"] / 1e6, line_dash="dot", line_color="#41464D", annotation_text="ótimo exato")
    st.plotly_chart(_layout(fig, "Evolução de Zinf e Zsup", "R$ milhões").update_xaxes(title="Iteração"), width="stretch",
                    key="pdde_conv")
    st.caption("Zinf é exato e cresce; Zsup é a média de poucos forwards (com 1 forward por iteração é o custo de um único cenário "
               "e não serve como limite). Por isso a parada usa a estabilização de Zinf ou um número fixo de iterações.")

    a, b = st.tabs(["Despacho médio por estágio", "Cortes (função de custo futuro)"], key="pdde_res")
    with a:
        st.dataframe(r["estagios"].style.format(precision=2), hide_index=True)
        caso = r["caso"]
        vol = r["vol"].sum(axis=2)
        fig = go.Figure()
        for q, op in ((5, .12), (25, .25)):
            fig.add_scatter(x=caso["meses"], y=np.percentile(vol, 100 - q, axis=0), line=dict(width=0), showlegend=False)
            fig.add_scatter(x=caso["meses"], y=np.percentile(vol, q, axis=0), fill="tonexty", line=dict(width=0),
                            fillcolor=f"rgba(27,107,130,{op})", name=f"P{q}–P{100 - q}")
        fig.add_scatter(x=caso["meses"], y=vol.mean(axis=0), name="Média", line_color=CORES[0])
        st.plotly_chart(_layout(fig, "Volume final armazenado (todas as UHEs)", "hm³"), width="stretch", key="pdde_vol")
        fig = go.Figure(go.Histogram(x=r["custos"] / 1e6, nbinsx=40, marker_color=CORES[1]))
        st.plotly_chart(_layout(fig, "Distribuição do custo total na simulação", "cenários").update_xaxes(title="R$ milhões"),
                        width="stretch", key="pdde_hist")
    with b:
        cortes, caso = r["cortes"], r["caso"]
        t = st.select_slider("Fim do estágio", caso["meses"][:-1], key="pdde_corte_t")
        i = caso["meses"].index(t)
        uhes = caso["uhes"]
        if len(uhes) == 1:
            u = uhes[0]
            x = np.linspace(u["vmin"], u["vmax"], 200)
            fig = go.Figure()
            for j, (pi, b0) in enumerate(cortes[i]):
                fig.add_scatter(x=x, y=(b0 + pi[0] * x) / 1e6, mode="lines", line=dict(width=1, color="rgba(65,70,77,.25)"),
                                showlegend=j == 0, name="cortes")
            env = np.max([[b0 + pi[0] * xx for xx in x] for pi, b0 in cortes[i]], axis=0) if cortes[i] else 0 * x
            fig.add_scatter(x=x, y=np.maximum(env, 0) / 1e6, name="α = max(cortes)", line=dict(color=CORES[4], width=3))
            fig.update_yaxes(range=[0, max(1e-6, np.max(env)) / 1e6 * 1.05])
            st.plotly_chart(_layout(fig, f"Custo futuro esperado após {t}", "α (R$ milhões)").update_xaxes(title="Volume final (hm³)"),
                            width="stretch", key="pdde_fcf2d")
        else:
            x = np.linspace(uhes[0]["vmin"], uhes[0]["vmax"], 40)
            y = np.linspace(uhes[1]["vmin"], uhes[1]["vmax"], 40)
            X, Y = np.meshgrid(x, y)
            Z = np.zeros_like(X)
            for pi, b0 in cortes[i]:
                Z = np.maximum(Z, b0 + pi[0] * X + pi[1] * Y)
            fig = go.Figure(go.Surface(x=x, y=y, z=Z / 1e6, colorscale="Tealrose"))
            fig.update_layout(height=520, margin=dict(l=0, r=0, t=30, b=0), template="plotly_white",
                              scene=dict(xaxis_title=f"VF {uhes[0]['nome']}", yaxis_title=f"VF {uhes[1]['nome']}",
                                         zaxis_title="α (R$ mi)"))
            st.plotly_chart(fig, width="stretch", key="pdde_fcf3d")
        st.caption(f"{len(cortes[i])} cortes no fim de {t}. Na PDDE eles valem para qualquer cenário do estágio (independência).")
