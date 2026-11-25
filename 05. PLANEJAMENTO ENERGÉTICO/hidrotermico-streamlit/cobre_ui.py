"""Aba COBRE × PDDE: o 1dtoy do novomodelo (ONS/CCEE/EPE) lado a lado com a nossa PDDE.

Objetivo da apresentação: não é provar que dão igual, e sim entender, com os mesmos dados, onde os métodos diferem
(implementação, solver, sorteio, estimativa do Zsup) e se essas diferenças mudam a política e o custo.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import cobre_dados as cd

AZUL, ROSA, CINZA, OCRE = "#1B6B82", "#B74B74", "#41464D", "#C18523"


def _layout(fig, titulo, y, altura=340):
    fig.update_layout(title=titulo, height=altura, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
                      yaxis_title=y, legend=dict(orientation="h", y=-0.25), hovermode="x unified")
    return fig


@st.cache_data(show_spinner="Lendo os resultados do COBRE e da nossa PDDE…")
def carregar(config):
    return dict(resumo=cd.resumo_cobre(config), conv=cd.convergencia_cobre(config), teste=cd.teste_cobre(config),
                nosso=cd.carregar_nosso(config))


DADOS = pd.DataFrame([
    ("Estágios", "4 meses: Jan–Abr/2024 (744, 696, 744 e 720 h)"),
    ("UHE1", "0–1000 hm³, VI 83,222 hm³, turbinado e defluência ≤ 50 m³/s, ρ = 1 MW/(m³/s), ≤ 50 MW"),
    ("Térmicas", "UTE1 15 MW a R$ 5/MWh · UTE2 15 MW a R$ 10/MWh"),
    ("Carga", "75 MW médios em todos os estágios"),
    ("Afluência", "Normal(40; 10) m³/s, ruído branco (independente entre estágios)"),
    ("Penalidades", "Déficit R$ 7.500/MWh · excesso R$ 100/MWh · vertimento 0,01 e turbinamento 0,05 R$/(m³/s·h)"),
    ("Desconto", "12% ao ano → β = 1,12^(−horas/8766) por estágio"),
], columns=["Dado", "Valor (idêntico nos dois)"])

METODO = pd.DataFrame([
    ("Linguagem / solver", "Rust · HiGHS 1.13.1", "Python · SCIP (PySCIPOpt)"),
    ("Aberturas", "Sorteadas pelo próprio COBRE (semente 42)", "As MESMAS do COBRE, lidas da saída dele"),
    ("Sorteio do forward", "Gerador interno do COBRE", "numpy default_rng(42): outra sequência de cenários"),
    ("Corte", "Média das aberturas (single-cut)", "Média das aberturas (single-cut)"),
    ("Gestão de cortes", "Seleção de cortes ativos, warm start entre LPs", "Todos os cortes; descarta só duplicados; LP novo a cada solve"),
    ("Zsup", "Média dos custos do forward (estatístico)", "Média dos forwards + IC95% (estatístico)"),
    ("Parada", "Limite de iterações", "Limite de iterações"),
    ("Simulação final", "2000 cenários fora da amostra (semente 777)", "Os MESMOS 2000 cenários, lidos da saída do COBRE"),
], columns=["Aspecto", "COBRE (novomodelo 0.22.0)", "Nossa PDDE"])


def cobre_aba():
    st.header("COBRE × nossa PDDE — caso 1dtoy")
    st.markdown(
        "O **COBRE** (novomodelo, desenvolvido por ONS, CCEE e EPE) traz o caso **1dtoy**: uma UHE, duas térmicas, quatro meses. "
        "Rodamos o mesmo caso na nossa PDDE para avaliar como o COBRE se comporta diante de uma implementação independente, "
        "alinhada com a formulação da disciplina. **A meta não é dar igual**, e sim ver lado a lado o que muda no método e se isso "
        "muda o resultado.")
    c = st.columns(2)
    c[0].caption("Dados do caso")
    c[0].dataframe(DADOS, hide_index=True)
    c[1].caption("Diferenças de método")
    c[1].dataframe(METODO, hide_index=True)

    config = st.radio("Configuração do treino", list(cd.CONFIGS), horizontal=True, key="cobre_cfg",
                      format_func=lambda k: f"{cd.CONFIGS[k]['rotulo']}: {cd.CONFIGS[k]['aberturas']} aberturas, "
                                            f"{cd.CONFIGS[k]['forwards']} forward(s), {cd.CONFIGS[k]['iteracoes']} iterações")
    d = carregar(config)
    if st.toggle("Recalcular a nossa PDDE agora (≈ 1 min)", key="cobre_recalc",
                 help="Por padrão a tela usa os resultados pré-calculados (python cobre_dados.py)."):
        barra = st.progress(0., "Treinando…")
        d = dict(d, nosso=cd.calcular_nosso(config, progresso=lambda h, n: barra.progress(h["iteracao"] / n,
                                                                                         f"Iteração {h['iteracao']}/{n}")))
        barra.empty()
    res, conv, nosso = d["resumo"], d["conv"], d["nosso"]
    hist = nosso["historico"]

    # ---------------- treino ----------------
    st.subheader("1. Treino: limite inferior")
    k = st.columns(4)
    k[0].metric("Zinf COBRE (R$)", f"{res['zinf_final']:,.2f}")
    k[1].metric("Zinf nosso (R$)", f"{hist.zinf.iloc[-1]:,.2f}",
                f"{100 * (hist.zinf.iloc[-1] / res['zinf_final'] - 1):+.4f}% vs COBRE", delta_color="off")
    k[2].metric("Ótimo exato da árvore (R$)", f"{nosso['otimo']:,.2f}",
                f"COBRE {100 * (res['zinf_final'] / nosso['otimo'] - 1):+.4f}% · nosso {100 * (hist.zinf.iloc[-1] / nosso['otimo'] - 1):+.4f}%",
                delta_color="off")
    k[3].metric("Tempo de treino", f"{res['segundos_treino']:.2f} s × {nosso['segundos']:.0f} s",
                f"{res['lp_treino']:,} LPs no COBRE", delta_color="off")
    fig = go.Figure()
    fig.add_scatter(x=conv.iteration + 1, y=conv.lower_bound / 1e6, name="Zinf COBRE", line_color=OCRE, mode="lines")
    fig.add_scatter(x=hist.iteracao, y=hist.zinf / 1e6, name="Zinf nosso", line=dict(color=AZUL, dash="dash"))
    fig.add_hline(y=nosso["otimo"] / 1e6, line_dash="dot", line_color=CINZA, annotation_text="ótimo exato (equivalente determinístico)")
    lo = min(conv.lower_bound.iloc[min(3, len(conv) - 1)], hist.zinf.iloc[min(3, len(hist) - 1)]) / 1e6
    st.plotly_chart(_layout(fig, "Zinf por iteração", "R$ milhões").update_yaxes(range=[lo, nosso["otimo"] / 1e6 * 1.003])
                    .update_xaxes(title="Iteração"), width="stretch", key="cobre_conv")
    st.markdown(
        "- O **ótimo exato** é o PL de toda a árvore de aberturas (o \"PL Único em árvore\" do 1dtoy, "
        f"{sum(np.cumprod([len(a) for a in res['aberturas_m3s']])):,} nós). Zinf de qualquer PDDE correta converge **por baixo** "
        "para ele: é a validação independente dos dois códigos.\n"
        "- As curvas não coincidem iteração a iteração porque **os forwards sorteiam cenários diferentes**: os cortes nascem em "
        "volumes diferentes. O valor final converge para o mesmo ponto.\n"
        "- O **Zsup** com 1 forward é o custo de um único cenário (o COBRE reporta "
        f"R\\$ {res['zsup_final']:,.0f}), por isso não serve como critério de parada no exemplo oficial.")

    # ---------------- teste ----------------
    st.subheader("2. Política avaliada no mesmo conjunto de teste (2000 cenários fora da amostra)")
    p = cd.comparacao_pareada(d["teste"], nosso["teste"])
    k = st.columns(4)
    k[0].metric("Custo esperado COBRE (R$)", f"{p['media_cobre']:,.0f}")
    k[1].metric("Custo esperado nosso (R$)", f"{p['media_nosso']:,.0f}")
    k[2].metric("Diferença pareada (R$)", f"{p['dif']:,.2f}", f"IC95% ± {p['ic95']:,.2f}", delta_color="off")
    k[3].metric("Cenários com custo igual (±R$ 1)", f"{100 * p['iguais']:.1f}%",
                f"nosso menor {100 * p['nosso_menor']:.0f}% · COBRE menor {100 * p['cobre_menor']:.0f}%", delta_color="off")
    dif = cd.custos_por_cenario(nosso["teste"])[:p["n"]] - cd.custos_por_cenario(d["teste"])[:p["n"]]
    fig = go.Figure(go.Histogram(x=dif, nbinsx=60, marker_color=AZUL))
    st.plotly_chart(_layout(fig, "Diferença de custo por cenário (nosso − COBRE)", "cenários", 300).update_xaxes(title="R$"),
                    width="stretch", key="cobre_dif")
    st.caption("Comparação **pareada**: cada cenário de afluência é o mesmo para as duas políticas, então a variância das "
               "afluências (desvio de dezenas de milhões) se cancela e sobra só a diferença de política.")

    e1, e2 = cd.medias_estagio(d["teste"]), cd.medias_estagio(nosso["teste"])
    figs = [("Volume final (hm³)", "Volume final médio"), ("CMO (R$/MWh)", "CMO médio"),
            ("Valor da água (R$/hm³)", "Valor da água médio"), ("P(déficit)", "Probabilidade de déficit")]
    cols = st.columns(2)
    for j, (col, tit) in enumerate(figs):
        fig = go.Figure()
        fig.add_bar(x=e1["Estágio"], y=e1[col], name="COBRE", marker_color=OCRE)
        fig.add_bar(x=e2["Estágio"], y=e2[col], name="Nosso", marker_color=AZUL)
        cols[j % 2].plotly_chart(_layout(fig, tit, col, 300), width="stretch", key=f"cobre_est_{j}")
    with st.expander("Tabelas por estágio"):
        st.caption("COBRE")
        st.dataframe(e1.style.format(precision=2), hide_index=True)
        st.caption("Nossa PDDE")
        st.dataframe(e2.style.format(precision=2), hide_index=True)
    st.caption("O CMO e o valor da água podem diferir em alguns cenários mesmo com o despacho idêntico: quando o LP é degenerado, "
               "há mais de um dual ótimo e HiGHS e SCIP escolhem vértices diferentes. O custo e as decisões não mudam.")

    # ---------------- configurações ----------------
    st.subheader("3. Quantas aberturas? Exemplo oficial × configuração da aula")
    o, pr = carregar("original"), carregar("professor")
    co, cp = cd.custos_por_cenario(o["teste"]), cd.custos_por_cenario(pr["teste"])
    tab = pd.DataFrame([
        ("Aberturas × forwards × iterações", "10 × 1 × 128", "3 × 10 × 50"),
        ("Zinf final (R$)", f"{o['resumo']['zinf_final']:,.0f}", f"{pr['resumo']['zinf_final']:,.0f}"),
        ("Custo no conjunto de teste (R$)", f"{co.mean():,.0f}", f"{cp.mean():,.0f}"),
        ("Zinf − custo de teste (R$)", f"{o['resumo']['zinf_final'] - co.mean():,.0f}", f"{pr['resumo']['zinf_final'] - cp.mean():,.0f}"),
    ], columns=["", "Exemplo oficial", "Configuração da aula"])
    st.dataframe(tab, hide_index=True)
    dd = cp - co
    st.markdown(
        f"- Com **3 aberturas** a política custa em média **R\\$ {dd.mean():,.0f}** a mais no mundo de teste "
        f"(IC95% ± {1.96 * dd.std(ddof=1) / np.sqrt(len(dd)):,.0f}): a árvore com 3 pontos representa mal a Normal(40; 10).\n"
        "- O Zinf de cada configuração é o ótimo da **sua** árvore, não do mundo real. Com 3 aberturas ele chega a ficar "
        "**acima** do custo de teste, então não pode ser lido como limite inferior do problema verdadeiro.\n"
        "- Nas duas configurações, COBRE e nossa PDDE chegam ao mesmo ótimo: a diferença vem da **amostragem**, não do código.")
