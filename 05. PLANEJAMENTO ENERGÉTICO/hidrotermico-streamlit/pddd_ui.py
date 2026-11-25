"""Aba PDDD: decomposição dual com cortes numa única trajetória, validada contra o PL Único (o que o professor pediu).

A versão em árvore (Benders aninhado) ficou na aba própria, benders_arvore_ui.py, como degrau antes da PDDE.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import dados_pysddp as dp
from pddd_model import caso_de_sistema, custo_futuro_superficie, pddd, tabela_saida, trajetoria
from pl_model import pl_unico_det, sistema_colab

CORES = ["#1B6B82", "#4B9999", "#C18523", "#7F6A55", "#B74B74", "#5B6CB0"]


def _layout(fig, titulo, y, altura=340):
    fig.update_layout(title=titulo, height=altura, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
                      yaxis_title=y, legend=dict(orientation="h", y=-0.2), hovermode="x unified")
    return fig


@st.cache_data(max_entries=16, show_spinner="Resolvendo o PL Único e a PDDD no SCIP…")
def resolver(fonte, ano, mes, n_meses, extras, carga, vi_b, vi_s, max_iter):
    """Monta o caso, resolve PL Único e PDDD no horizonte estendido e devolve tudo pronto para a tela."""
    if fonte == "pysddp":
        sistema = dp.sistema_pysddp(ano=ano, mes_inicial=mes, n_meses=n_meses + extras, carga=carga,
                                    vi_pct=(vi_b, vi_s))
        cenario = 0
    else:
        sistema, cenario = sistema_colab(), 1
    pl = pl_unico_det(sistema, cenario)
    caso = caso_de_sistema(sistema, cenario)
    r = pddd(caso, max_iter=max_iter)
    traj = trajetoria(r)
    estagios = [r["por_estagio"][t][0] for t in range(len(traj))]
    superficies = [custo_futuro_superficie(r["cortes"][no], caso) for no in estagios]
    return dict(pl=pl["custo_total"], zsup=r["zsup"], zinf=r["zinf"], convergiu=r["convergiu"],
                iteracoes=r["iteracoes"], segundos=r["segundos"], historico=pd.DataFrame(r["historico"]),
                saida=pd.DataFrame(tabela_saida(r, caso)), superficies=superficies,
                vf=[x["v"] for x in traj], ncortes=[len(r["cortes"][no]) for no in estagios],
                nomes=caso["nomes"], termicas=caso["termicas"], meses=caso["meses"],
                vmin=caso["vmin"], vmax=caso["vmax"])


def formulacao():
    with st.expander("Formulação da PDDD (resumo)", expanded=False):
        st.markdown("Cada mês resolve $\\min\\, C_t(x_t)+\\alpha_t$ com as mesmas restrições do PL Único. O custo futuro $\\alpha_t$ é "
                    "limitado por **cortes** gerados no *backward* a partir dos duais do balanço hídrico:")
        st.latex(r"\alpha_t \ge b_t^\ell + (\pi_t^\ell)^\top V^F_t,\qquad \pi_t=\partial Q_{t+1}(\bar v)/\partial v,\qquad b_t=Q_{t+1}(\bar v)-\pi_t^\top\bar v")
        st.markdown("O *forward* fornece $Z_{sup}$ (soma dos custos **imediatos** da trajetória) e o primeiro mês fornece $Z_{inf}$ "
                    "(custo imediato + $\\alpha_1$). Para no critério:")
        st.latex(r"Z_{sup}-Z_{inf}\le \tau_a+\tau_r\max(1,|Z_{sup}|),\qquad \tau_a=\text{R\$ }1,\ \tau_r=10^{-8}")
        st.markdown("Com a trajetória conhecida e o gap fechado, $Z_{PDDD}=Z_{PL}$. O **CMO** é o dual do atendimento à carga "
                    "(R\\$/MWh) e o **CMA** é o dual do balanço hídrico com sinal trocado (R\\$/hm³).")


def pddd_aba():
    st.header("PDDD — Programação Dinâmica Dual Determinística")
    estudo, passo = st.tabs(["Estudo: PL Único × PDDD", "Passo a passo (exemplo da aula)"], key="pddd_sub",
                            on_change="rerun")
    if passo.open:
        with passo:
            from pddd_passos_ui import passo_a_passo
            passo_a_passo()
    if estudo.open:
        with estudo:
            _estudo()


def _estudo():
    formulacao()
    from metodologia import mostrar_algoritmo
    mostrar_algoritmo(st, '5.')
    fonte = st.sidebar.radio("Dados das usinas", ["pysddp", "colab"], key="pddd_fonte",
                             format_func=lambda f: "PySDDP ao vivo (HIDR.DAT, VAZOES.DAT, DESSEM)" if f == "pysddp"
                             else "Caso da disciplina (Colab, Set–Nov)")
    a0, a1 = dp.anos_disponiveis()
    if fonte == "pysddp":
        ano = st.sidebar.number_input("Ano inicial do histórico", a0, a1 - 1, 2015, key="pddd_ano")
        mes = st.sidebar.selectbox("Mês inicial", range(1, 13), 8, key="pddd_mes", format_func=lambda m: dp.MESES[m - 1])
        n_meses = st.sidebar.slider("Horizonte (meses)", 2, 60, 24, key="pddd_meses")
        extras = st.sidebar.number_input("Estágios pós-horizonte (ex.: 13º estágio)", 0, 24, 0, key="pddd_extras",
                                         help="Meses adicionais, com as vazões históricas seguintes, resolvidos junto e "
                                              "descartados da apresentação. Evitam que o modelo esvazie os reservatórios "
                                              "no último mês só porque o custo após o horizonte é zero.")
        carga = st.sidebar.number_input("Carga (MW médios)", 0., 400., 100., 10., key="pddd_carga")
        vi_b = st.sidebar.slider("Volume inicial Batalha (% útil)", 0., 100., 39.7, .5, key="pddd_vib")
        vi_s = st.sidebar.slider("Volume inicial Serra (% útil)", 0., 100., 50.2, .5, key="pddd_vis")
        fim = (ano + (mes - 1 + n_meses + extras - 1) // 12)
        if fim > a1:
            st.warning(f"O horizonte com os estágios extras passa de {a1}, o último ano do VAZOES.DAT. Reduza o horizonte ou o ano.")
            return
    else:
        ano = mes = carga = vi_b = vi_s = None
        n_meses, extras = 3, 0
    max_iter = st.sidebar.number_input("Máximo de iterações", 1, 300, 100, key="pddd_iter")
    try:
        r = resolver(fonte, ano, mes, n_meses, extras, carga, vi_b, vi_s, int(max_iter))
    except (ValueError, RuntimeError) as exc:
        st.warning(str(exc))
        return

    if fonte == "pysddp":
        with st.expander("Dados lidos pelo PySDDP", expanded=False):
            st.dataframe(dp.tabela_cadastro().round(4), hide_index=True)
            st.dataframe(pd.DataFrame(dp.termicas_dessem()), hide_index=True)
            st.caption("UHEs: HIDR.DAT (cadastro) e VAZOES.DAT (vazões naturais; em Serra usa-se a incremental). "
                       "Térmicas: termdat.dat/operut.dat do deck DESSEM. Tudo lido pelos leitores do PySDDP a cada execução.")

    # ---------------- validação ----------------
    st.subheader("Validação: PL Único × PDDD")
    c = st.columns(5)
    c[0].metric("PL Único (R$)", f"{r['pl']:,.2f}")
    c[1].metric("PDDD · Zsup (R$)", f"{r['zsup']:,.2f}")
    c[2].metric("PDDD · Zinf (R$)", f"{r['zinf']:,.2f}")
    c[3].metric("|Zsup − PL| (R$)", f"{abs(r['zsup'] - r['pl']):,.4f}")
    c[4].metric("Iterações", r["iteracoes"], help=f"{r['segundos']:.1f} s")
    if r["convergiu"] and abs(r["zsup"] - r["pl"]) <= 1 + 1e-6 * abs(r["pl"]):
        st.success("Gap fechado e custo igual ao do PL Único: a PDDD recuperou o ótimo determinístico.")
    else:
        st.warning("A PDDD não fechou o gap ou o custo difere do PL Único. Aumente o número de iterações.")
    if extras:
        st.caption(f"Os custos acima incluem os {extras} estágio(s) pós-horizonte. As tabelas e gráficos mostram só os {n_meses} meses do estudo.")

    h = r["historico"]
    fig = go.Figure()
    fig.add_scatter(x=h.iteracao, y=h.zsup / 1e6, name="Zsup", mode="lines+markers", line_color=CORES[4])
    fig.add_scatter(x=h.iteracao, y=h.zinf / 1e6, name="Zinf", mode="lines+markers", line_color=CORES[0])
    fig.add_hline(y=r["pl"] / 1e6, line_dash="dot", line_color="#41464D", annotation_text="PL Único")
    st.plotly_chart(_layout(fig, "Convergência: Zinf e Zsup por iteração", "R$ milhões").update_xaxes(title="Iteração"),
                    width="stretch", key="pddd_conv")

    # ---------------- dados de saída ----------------
    st.subheader("Dados de saída por estágio")
    df = r["saida"].iloc[:n_meses]
    meses = df["Mês"]
    nomes, termicas = r["nomes"], r["termicas"]

    c = st.columns(3)
    c[0].metric("Custo total do período (R$)", f"{df['Custo imediato (R$)'].sum():,.2f}")
    c[1].metric("Déficit total (MWh)", f"{df['Déficit (MWm)'].sum() * dp.HORAS:,.1f}")
    c[2].metric("CMO médio (R$/MWh)", f"{df['CMO (R$/MWh)'].mean():,.2f}")

    abas = st.tabs(["Atendimento à carga", "Volumes", "Turbinado e vertido", "CMO e CMA", "Custos", "Tabela"])
    with abas[0]:
        fig = go.Figure()
        series = [(f"Geração {n} (MWm)", n) for n in nomes] + [(f"{n} (MWm)", n) for n in termicas] + [("Déficit (MWm)", "Déficit")]
        for k, (col, nome) in enumerate(series):
            fig.add_bar(x=meses, y=df[col].clip(lower=0), name=nome, marker_color=CORES[k % len(CORES)])
        fig.add_scatter(x=meses, y=df["Carga (MWm)"], name="Carga", mode="lines+markers", line=dict(color="#41464D", dash="dash"))
        st.plotly_chart(_layout(fig.update_layout(barmode="stack"), "Geração hidráulica, térmica e déficit", "MW médios"),
                        width="stretch", key="pddd_ger")
    with abas[1]:
        fig = go.Figure()
        for i, n in enumerate(nomes):
            fig.add_scatter(x=meses, y=df[f"VF {n} (hm³)"], name=n, mode="lines+markers", line_color=CORES[i])
        st.plotly_chart(_layout(fig, "Volume final ótimo", "hm³"), width="stretch", key="pddd_vol")
    with abas[2]:
        fig = go.Figure()
        for i, n in enumerate(nomes):
            fig.add_bar(x=meses, y=df[f"Turbinado {n} (hm³)"], name=f"Turbinado {n}", marker_color=CORES[i])
            fig.add_bar(x=meses, y=df[f"Vertido {n} (hm³)"], name=f"Vertido {n}", marker_color=CORES[i + 2])
        st.plotly_chart(_layout(fig, "Volumes turbinado e vertido", "hm³/mês"), width="stretch", key="pddd_tv")
    with abas[3]:
        fig = go.Figure()
        fig.add_scatter(x=meses, y=df["CMO (R$/MWh)"], name="CMO", mode="lines+markers", line_color=CORES[4])
        st.plotly_chart(_layout(fig, "Custo marginal de operação (CMO)", "R$/MWh"), width="stretch", key="pddd_cmo")
        fig = go.Figure()
        for i, n in enumerate(nomes):
            fig.add_scatter(x=meses, y=df[f"CMA {n} (R$/hm³)"], name=n, mode="lines+markers", line_color=CORES[i])
        st.plotly_chart(_layout(fig, "Custo marginal da água (CMA) de cada UHE", "R$/hm³"), width="stretch", key="pddd_cma")
        st.caption("CMO: dual do atendimento à carga dividido pelas horas do mês. CMA: dual do balanço hídrico com sinal trocado, "
                   "ou seja, quanto o custo total cai com 1 hm³ a mais no reservatório no início do mês.")
    with abas[4]:
        fig = go.Figure()
        fig.add_bar(x=meses, y=df["Custo imediato (R$)"] / 1e6, name="Custo imediato", marker_color=CORES[0])
        fig.add_scatter(x=meses, y=df["Custo futuro α (R$)"] / 1e6, name="Custo futuro α", mode="lines+markers", line_color=CORES[2])
        st.plotly_chart(_layout(fig, "Custo por estágio", "R$ milhões"), width="stretch", key="pddd_custos")
    with abas[5]:
        st.dataframe(df.round(4), hide_index=True)
        st.download_button("Baixar dados de saída (CSV)", df.to_csv(index=False).encode("utf-8"), "pddd_saida.csv",
                           "text/csv", key="pddd_csv")

    # ---------------- função de custo futuro em 3D ----------------
    st.subheader("Função de custo futuro em 3D, mês a mês")
    t = st.select_slider("Mês", options=list(range(n_meses)), format_func=lambda i: meses.iloc[i], key="pddd_mes3d")
    x, y, z = r["superficies"][t]
    vf = r["vf"][t]
    fig = go.Figure(go.Surface(x=x, y=y, z=z.T, colorscale="Tealrose", showscale=True,
                               colorbar=dict(title="R$ mi")))
    xi, yi = np.argmin(abs(x - vf[0])), np.argmin(abs(y - vf[1]))
    fig.add_scatter3d(x=[vf[0]], y=[vf[1]], z=[z[xi, yi]], mode="markers", marker=dict(size=6, color="#B74B74"),
                      name="VF ótimo")
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=30, b=0), template="plotly_white",
                      scene=dict(xaxis_title=f"VF {nomes[0]} (hm³)", yaxis_title=f"VF {nomes[1]} (hm³)", zaxis_title="α (R$ mi)"))
    st.plotly_chart(fig, width="stretch", key="pddd_3d")
    st.caption(f"{r['ncortes'][t]} corte(s) no fim de {meses.iloc[t]}. A superfície é max(0, max dos planos): cada corte é um "
               "plano tangente ao custo futuro no volume visitado. Onde não há cortes, o custo futuro aproximado é zero.")
