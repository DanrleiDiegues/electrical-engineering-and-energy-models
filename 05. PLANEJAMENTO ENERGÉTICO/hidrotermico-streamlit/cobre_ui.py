"""Aba COBRE × PDDE: o 1dtoy do Novo Modelo (ONS/CCEE/EPE, derivado do Cobre) lado a lado com a PDDE UFJF.

Objetivo da apresentação: não é provar que dão igual, e sim entender, com os mesmos dados, onde os métodos diferem
(implementação, solver, sorteio, estimativa do Zsup, custo computacional) e se essas diferenças mudam a política e o custo.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import cobre_dados as cd

AZUL, OCRE, CINZA, VERDE = "#2a78d6", "#eb6834", "#41464D", "#1baf7a"
COBRE, UFJF = "COBRE (Novo Modelo)", "PDDE UFJF"


def _layout(fig, titulo, y, altura=340):
    fig.update_layout(title=titulo, height=altura, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
                      yaxis_title=y, legend=dict(orientation="h", y=-0.25), hovermode="x unified")
    return fig


def _barras(categorias, v1, v2, titulo, y, fmt="%{y:,.2f}", altura=300, log=False):
    """Barras agrupadas COBRE × PDDE UFJF com o valor escrito em cada barra."""
    fig = go.Figure()
    fig.add_bar(x=categorias, y=v1, name=COBRE, marker_color=OCRE, texttemplate=fmt, textposition="outside")
    fig.add_bar(x=categorias, y=v2, name=UFJF, marker_color=AZUL, texttemplate=fmt, textposition="outside")
    fig = _layout(fig, titulo, y, altura).update_layout(barmode="group", hovermode="closest", uniformtext_minsize=9)
    if log:
        fig.update_yaxes(type="log")
    else:
        topo = max(max(np.abs(v1)), max(np.abs(v2)))
        fig.update_yaxes(range=[0, topo * 1.2 if topo > 0 else 1])
    return fig


@st.cache_data(show_spinner="Lendo os resultados do COBRE e da PDDE UFJF…")
def carregar(config):
    return dict(resumo=cd.resumo_cobre(config), conv=cd.convergencia_cobre(config), teste=cd.teste_cobre(config),
                nosso=cd.carregar_nosso(config))


DADOS = pd.DataFrame([
    ("Estágios", "4 meses: Jan–Abr/2024 (744, 696, 744 e 720 h)"),
    ("UHE1", "0–1000 hm³, VI 83,222 hm³, turbinado e defluência ≤ 50 m³/s, ρ = 1 MW/(m³/s), ≤ 50 MW"),
    ("Térmicas", "UTE1 15 MW a R$ 5/MWh · UTE2 15 MW a R$ 10/MWh"),
    ("Carga", "75 MW médios em todos os estágios"),
    ("Afluência", "Normal(40; 10) m³/s, independente entre estágios"),
    ("Penalidades", "Déficit R$ 7.500/MWh · excesso R$ 100/MWh · vertimento 0,01 e turbinamento 0,05 R$/(m³/s·h)"),
    ("Desconto", "12% ao ano → β = 1,12^(−horas/8766) por estágio"),
], columns=["Dado", "Valor (idêntico nos dois)"])

METODO = pd.DataFrame([
    ("Linguagem / solver", "Rust · HiGHS 1.13.1", "Python · SCIP (PySCIPOpt)"),
    ("Aberturas", "Sorteadas pelo próprio COBRE da Normal(40; 10), semente 42", "As MESMAS do COBRE, lidas da saída dele"),
    ("Sorteio do forward", "Gerador interno do COBRE", "numpy default_rng(42): outra sequência de cenários"),
    ("Corte", "Média das aberturas (um corte por volume visitado)", "Média das aberturas (um corte por volume visitado)"),
    ("Gestão de cortes", "Mantém todos os cortes; reaproveita a solução anterior (warm start)",
     "Descarta cortes repetidos; monta um LP novo a cada resolução"),
    ("Zsup", "Média dos custos do forward", "Média dos custos do forward + IC95%"),
    ("Parada", "Limite de iterações", "Limite de iterações"),
    ("Simulação final", "2000 cenários fora da amostra (semente 777)", "Os MESMOS 2000 cenários, lidos da saída do COBRE"),
], columns=["Aspecto", COBRE, UFJF])


def cobre_aba():
    st.header("COBRE × PDDE UFJF — caso 1dtoy")
    st.markdown(
        "O **Novo Modelo** (ONS, CCEE e EPE, derivado do projeto aberto **Cobre**) traz o caso **1dtoy**: uma UHE, duas térmicas, "
        "quatro meses. Rodamos o mesmo caso na **PDDE UFJF**, a nossa implementação independente, alinhada com a formulação da "
        "disciplina. **A meta não é dar igual**, e sim ver lado a lado o que muda no método e se isso muda o resultado.")
    st.success(
        "**Conclusões principais**  \n"
        "1. Os dois chegam à **mesma política**: nos mesmos 2000 cenários, a diferença de custo é de poucos reais por cenário.  \n"
        "2. Os dois estão **corretos**: o Zinf de ambos converge por baixo para o ótimo exato da árvore.  \n"
        "3. A **configuração pesa mais que o código**: com 3 aberturas a política custa ≈ R\\$ 600 mil a mais.  \n"
        "4. O COBRE é **dezenas de vezes mais rápido** resolvendo o mesmo número de PLs.")

    st.caption("Dados do caso")
    st.dataframe(DADOS, hide_index=True, width="stretch")
    st.caption("Diferenças de método")
    st.dataframe(METODO, hide_index=True, width="stretch")
    st.info("**Ponto crítico: por que usar as mesmas aberturas?** As aberturas definem a árvore que a PDDE otimiza. Com "
            "aberturas diferentes, cada código resolveria outro problema e o ruído do sorteio (centenas de milhares de reais) "
            "esconderia a diferença de método (poucos reais).")

    config = st.radio("Configuração usada para calcular a política", list(cd.CONFIGS), horizontal=True, key="cobre_cfg",
                      format_func=lambda k: f"{cd.CONFIGS[k]['rotulo']}: {cd.CONFIGS[k]['aberturas']} aberturas, "
                                            f"{cd.CONFIGS[k]['forwards']} forward(s), {cd.CONFIGS[k]['iteracoes']} iterações")
    d = carregar(config)
    if st.toggle("Recalcular agora a política da PDDE UFJF (≈ 1 min)", key="cobre_recalc",
                 help="Por padrão a tela usa os resultados já calculados (python cobre_dados.py)."):
        barra = st.progress(0., "Calculando a política…")
        d = dict(d, nosso=cd.calcular_nosso(config, progresso=lambda h, n: barra.progress(h["iteracao"] / n,
                                                                                         f"Iteração {h['iteracao']}/{n}")))
        barra.empty()
    res, conv, nosso = d["resumo"], d["conv"], d["nosso"]
    hist = nosso["historico"]
    _limites(res, conv, nosso, hist)
    _custo_computacional(res, conv, nosso, hist, config)
    _teste(d, nosso)
    _configuracoes()


def _limites(res, conv, nosso, hist):
    st.subheader("1. Cálculo da política: Zinf e Zsup")
    k = st.columns(3)
    k[0].metric(f"Zinf {COBRE} (R$)", f"{res['zinf_final']:,.2f}",
                f"{100 * (res['zinf_final'] / nosso['otimo'] - 1):+.4f}% do ótimo", delta_color="off")
    k[1].metric(f"Zinf {UFJF} (R$)", f"{hist.zinf.iloc[-1]:,.2f}",
                f"{100 * (hist.zinf.iloc[-1] / nosso['otimo'] - 1):+.4f}% do ótimo", delta_color="off")
    k[2].metric("Ótimo exato da árvore (R$)", f"{nosso['otimo']:,.2f}", "equivalente determinístico", delta_color="off")

    a, b = st.columns(2)
    fig = go.Figure()
    fig.add_scatter(x=conv.iteration + 1, y=conv.lower_bound / 1e6, name=f"Zinf {COBRE}", line_color=OCRE, mode="lines")
    fig.add_scatter(x=hist.iteracao, y=hist.zinf / 1e6, name=f"Zinf {UFJF}", line=dict(color=AZUL, dash="dash"))
    fig.add_hline(y=nosso["otimo"] / 1e6, line_dash="dot", line_color=CINZA, annotation_text="ótimo exato")
    lo = min(conv.lower_bound.iloc[min(3, len(conv) - 1)], hist.zinf.iloc[min(3, len(hist) - 1)]) / 1e6
    a.plotly_chart(_layout(fig, "Zinf por iteração (só sobe)", "R$ milhões").update_yaxes(range=[lo, nosso["otimo"] / 1e6 * 1.003])
                   .update_xaxes(title="Iteração"), width="stretch", key="cobre_conv")
    fig = go.Figure()
    fig.add_scatter(x=conv.iteration + 1, y=conv.upper_bound / 1e6, name=f"Zsup {COBRE}", mode="markers",
                    marker=dict(color=OCRE, size=6))
    fig.add_scatter(x=hist.iteracao, y=hist.zsup / 1e6, name=f"Zsup {UFJF}", mode="markers",
                    marker=dict(color=AZUL, size=6, symbol="diamond"))
    fig.add_hline(y=nosso["otimo"] / 1e6, line_dash="dot", line_color=CINZA, annotation_text="ótimo exato")
    b.plotly_chart(_layout(fig, "Zsup por iteração (escala log)", "R$ milhões").update_yaxes(type="log")
                   .update_xaxes(title="Iteração"), width="stretch", key="cobre_zsup")
    st.info(
        "**Ponto crítico: como ler os dois gráficos.**  \n"
        "• **Zinf** é exato: o valor do 1º mês com os cortes atuais. Só sobe e para logo abaixo do ótimo nos dois códigos. "
        "As curvas não coincidem iteração a iteração porque cada código sorteia outros caminhos no forward.  \n"
        f"• **Zsup** é o custo médio dos cenários do forward. Com {res['forwards']} forward(s) por iteração ele salta entre meses "
        "sem déficit (≈ R\\$ 0,6 mi) e meses secos com déficit (dezenas a centenas de milhões). Não converge e não serve para "
        "parar: os dois códigos param pelo limite de iterações. Como os caminhos sorteados são diferentes, os pontos de "
        "Zsup do COBRE e da PDDE UFJF não precisam coincidir.")


def _custo_computacional(res, conv, nosso, hist, config):
    st.subheader("2. Custo computacional")
    c = cd.CONFIGS[config]
    lps = len(conv) * (c["forwards"] * 4 + 3 * c["forwards"] * c["aberturas"] + c["aberturas"])
    t_cobre = res["segundos_treino"]
    t_ufjf = float(nosso["segundos"])
    cortes_ufjf = int(hist.cortes.iloc[-1])
    k = st.columns(4)
    k[0].metric("Tempo total", f"{t_cobre:.2f} s × {t_ufjf:.1f} s", f"COBRE {t_ufjf / t_cobre:.0f}× mais rápido", delta_color="off")
    k[1].metric("PLs resolvidos (os mesmos nos dois)", f"{lps:,}", f"COBRE registrou {int(conv.lp_solves.sum()):,}", delta_color="off")
    k[2].metric("Tempo por PL", f"{1e3 * t_cobre / lps:.3f} ms × {1e3 * t_ufjf / lps:.2f} ms", delta_color="off")
    k[3].metric("Cortes guardados no fim", f"{int(conv.cuts_active.iloc[-1])} × {cortes_ufjf}",
                "UFJF descarta cortes repetidos", delta_color="off")
    a, b = st.columns(2)
    a.plotly_chart(_barras(["Tempo total (s)", "Tempo por iteração (ms)"],
                           [t_cobre, 1e3 * t_cobre / len(conv)], [t_ufjf, 1e3 * t_ufjf / len(hist)],
                           "Tempo para calcular a política (escala log)", "", log=True), width="stretch", key="cobre_tempo")
    fig = go.Figure()
    fig.add_scatter(x=conv.iteration + 1, y=conv.time_total_ms.cumsum() / 1e3, name=COBRE, line_color=OCRE)
    fig.add_scatter(x=hist.iteracao, y=hist.segundos, name=UFJF, line=dict(color=AZUL, dash="dash"))
    b.plotly_chart(_layout(fig, "Tempo acumulado por iteração (escala log)", "segundos", 300).update_yaxes(type="log")
                   .update_xaxes(title="Iteração"), width="stretch", key="cobre_tempo_acum")
    st.info("**Ponto crítico: a diferença de tempo é de engenharia, não de matemática.** Os dois resolvem exatamente o mesmo "
            "número de PLs. O COBRE é compilado (Rust), usa o HiGHS e reaproveita a solução de um PL no seguinte (warm start); "
            "a PDDE UFJF é Python e monta cada PL do zero no SCIP. Para o 1dtoy isso é irrelevante; para o SIN, com centenas de "
            "usinas e milhares de cenários, é o que torna o cálculo viável.")


def _teste(d, nosso):
    st.subheader("3. A política nos mesmos 2000 cenários fora da amostra")
    p = cd.comparacao_pareada(d["teste"], nosso["teste"])
    k = st.columns(4)
    k[0].metric(f"Custo esperado {COBRE} (R$)", f"{p['media_cobre']:,.0f}")
    k[1].metric(f"Custo esperado {UFJF} (R$)", f"{p['media_nosso']:,.0f}")
    k[2].metric("Diferença por cenário (R$)", f"{p['dif']:,.2f}", f"IC95% ± {p['ic95']:,.2f}", delta_color="off")
    k[3].metric("Cenários com custo igual (±R$ 1)", f"{100 * p['iguais']:.1f}%",
                f"UFJF menor {100 * p['nosso_menor']:.0f}% · COBRE menor {100 * p['cobre_menor']:.0f}%", delta_color="off")
    custos = cd.custos_por_cenario(d["teste"])
    ic_media = 1.96 * custos.std(ddof=1) / np.sqrt(len(custos))
    st.info(
        "**Ponto crítico: por que comparar cenário a cenário.** O custo de um cenário varia de R\\$ 0,5 mi (sem déficit) a "
        f"R\\$ 200 mi (com déficit), então a média de 2000 cenários tem incerteza de ± R\\$ {ic_media / 1e6:.1f} mi. "
        "Comparando as duas políticas **no mesmo cenário**, essa variação se cancela e sobra só a diferença de política: "
        f"R\\$ {p['dif']:,.2f} ± {p['ic95']:,.2f} por cenário.")
    dif = cd.custos_por_cenario(nosso["teste"])[:p["n"]] - custos[:p["n"]]
    fig = go.Figure(go.Histogram(x=dif, nbinsx=60, marker_color=AZUL))
    st.plotly_chart(_layout(fig, f"Diferença de custo por cenário ({UFJF} − {COBRE})", "cenários", 280).update_xaxes(title="R$"),
                    width="stretch", key="cobre_dif")

    e1, e2 = cd.medias_estagio(d["teste"]), cd.medias_estagio(nosso["teste"])
    figs = [("Volume final (hm³)", "Volume final médio", "%{y:.1f}"), ("Déficit (MW)", "Déficit médio", "%{y:.2f}"),
            ("P(déficit)", "Probabilidade de déficit", "%{y:.1%}"), ("CMO (R$/MWh)", "CMO médio", "%{y:,.0f}")]
    cols = st.columns(2)
    for j, (col, tit, fmt) in enumerate(figs):
        cols[j % 2].plotly_chart(_barras(e1["Estágio"], e1[col], e2[col], tit, col, fmt), width="stretch", key=f"cobre_est_{j}")
    st.caption("O CMO pode diferir em alguns cenários mesmo com o despacho idêntico: quando o PL tem mais de um dual ótimo, "
               "HiGHS e SCIP escolhem valores diferentes. O custo e as decisões não mudam.")
    with st.expander("Tabelas por estágio (inclui turbinado, vertido, térmicas e valor da água)"):
        st.caption(COBRE)
        st.dataframe(e1.style.format(precision=2), hide_index=True, width="stretch")
        st.caption(UFJF)
        st.dataframe(e2.style.format(precision=2), hide_index=True, width="stretch")


def _configuracoes():
    st.subheader("4. Quantas aberturas? Exemplo oficial × trabalho de PDDE")
    o, pr = carregar("original"), carregar("professor")
    co, cp = cd.custos_por_cenario(o["teste"]), cd.custos_por_cenario(pr["teste"])
    ic = lambda x: 1.96 * x.std(ddof=1) / np.sqrt(len(x))
    st.plotly_chart(_barras(["Zinf (ótimo da própria árvore)", "Custo no teste (mundo real)"],
                            [o["resumo"]["zinf_final"] / 1e6, co.mean() / 1e6],
                            [pr["resumo"]["zinf_final"] / 1e6, cp.mean() / 1e6],
                            "COBRE com 10 aberturas (laranja) × 3 aberturas (azul)", "R$ milhões", "%{y:.2f}")
                    .update_traces(selector=dict(name=COBRE), name="10 aberturas × 1 forward × 128 it.")
                    .update_traces(selector=dict(name=UFJF), name="3 aberturas × 10 forwards × 50 it."),
                    width="stretch", key="cobre_cfgs")
    tab = pd.DataFrame([
        ("Aberturas × forwards × iterações", "10 × 1 × 128", "3 × 10 × 50"),
        ("Zinf final (R$)", f"{o['resumo']['zinf_final']:,.0f}", f"{pr['resumo']['zinf_final']:,.0f}"),
        ("Custo no conjunto de teste (R$)", f"{co.mean():,.0f} ± {ic(co):,.0f}", f"{cp.mean():,.0f} ± {ic(cp):,.0f}"),
    ], columns=["", "Exemplo oficial", "Trabalho de PDDE"])
    st.dataframe(tab, hide_index=True, width="stretch")
    dd = cp - co
    st.info(
        "**Ponto crítico: o Zinf depende da árvore.**  \n"
        "• As aberturas do COBRE têm média 40 e desvio 10 nas duas configurações, mas com 3 pontos o mês seco (≈ 26 m³/s) tem "
        "probabilidade 1/3, contra ≈ 11% na Normal real. Como o déficit é caro, a árvore de 3 pontos fica mais cara: o ótimo dela é "
        f"R\\$ {(pr['resumo']['zinf_final'] - o['resumo']['zinf_final']) / 1e6:.2f} mi maior.  \n"
        f"• Nos mesmos cenários de teste, a política de 3 aberturas custa **R\\$ {dd.mean():,.0f}** a mais "
        f"(IC95% ± {ic(dd):,.0f}): diferença real, medida cenário a cenário.  \n"
        f"• Já a comparação entre cada Zinf e o custo de teste não permite conclusão: a média de teste tem incerteza de "
        f"± R\\$ {ic(co) / 1e6:.1f} mi, maior que a distância entre eles. Por isso o Zinf de uma árvore pequena não deve ser lido "
        "como limite inferior do problema real; a teoria só garante isso na média sobre muitas árvores sorteadas.  \n"
        "• Nas duas configurações, COBRE e PDDE UFJF chegam ao mesmo ótimo: a diferença vem da **amostragem**, não do código.")
