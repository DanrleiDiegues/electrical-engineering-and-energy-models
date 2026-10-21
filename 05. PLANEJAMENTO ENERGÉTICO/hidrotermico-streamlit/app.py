"""Aplicativo Streamlit para o planejamento hidrotérmico de três estágios."""
import io
import json
import time
import zipfile
from dataclasses import replace

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

import charts
from model import MESES, UHES, Parameters, avaliar, planejamento, tabela_resultados

st.set_page_config(page_title="Planejamento hidrotérmico", page_icon="💧", layout="wide")
st.markdown("""<style>
.block-container{padding:4.5rem 2.5rem 3rem;max-width:1550px}
h1{letter-spacing:-.04em!important} h2,h3{letter-spacing:-.02em!important}
[data-testid="stMetric"]{background:#F0F6F7;padding:18px 20px;border-radius:12px;border:1px solid #DCE9EC}
[data-testid="stMetricLabel"]{color:#526B76}
[data-testid="stMetricValue"]{font-size:clamp(1.15rem,1.6vw,1.65rem)}
[data-testid="stMetricLabel"] p{font-size:13px;white-space:normal}
.eyebrow{color:#247B8B;letter-spacing:.16em;font-size:12px;font-weight:700}
.intro{color:#5D7280;font-size:17px;margin-bottom:1.6rem}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=6)
def cached_policy(p):
    # O elemento nasce no escopo do cache para permitir replay seguro no Streamlit.
    bar = st.progress(0, text="Preparando a política de operação…")
    try:
        return planejamento(p, lambda done, total, month: bar.progress(
            done/total, text=f"{month}: {done:,}/{total:,} despachos na grade"))
    finally:
        bar.empty()


def reset():
    for k in list(st.session_state):
        if k.startswith("input_") or k in ("solution", "parameters"):
            del st.session_state[k]


def num(label, value, key, minimum=0.0, maximum=None, step=1.0, fmt=None, help=None):
    kwargs = {"min_value": float(minimum), "value": float(value), "step": float(step), "key": "input_"+key, "help": help}
    if maximum is not None:
        kwargs["max_value"] = float(maximum)
    if fmt:
        kwargs["format"] = fmt
    return st.number_input(label, **kwargs)


defaults = Parameters()
with st.sidebar:
    st.markdown("### Controle da simulação")
    st.caption("3 estágios · 2 UHEs em cascata · 2 UTEs")
    carga = num("Carga constante (MW médios)", defaults.carga, "carga", step=10.0)
    nr_disc = st.number_input("Níveis de volume por UHE", min_value=2, max_value=40, value=24, step=1, key="input_nr_disc",
                              help="O notebook usa 24 níveis: 576 pares e 3.456 despachos no planejamento. O limite de 40 é apenas da interface.")
    st.caption(f"{nr_disc**2:,} pares de volumes · {6*nr_disc**2:,} otimizações na grade".replace(",", "."))
    if nr_disc > 24:
        st.info("Grades maiores exigem mais tempo de cálculo. Cada despacho também terá mais pesos de interpolação.")
    st.markdown("#### Armazenamento inicial")
    inicial = tuple(num(f"{u} (% útil)", defaults.inicial[i], f"inicial_{i}", maximum=100, step=1) for i, u in enumerate(UHES))
    st.markdown("#### Trajetória realizada")
    st.caption("Cada seleção vale conjuntamente para as duas UHEs.")
    trajetoria = tuple(st.selectbox(m, options=[0, 1], index=1, format_func=lambda s: "Máximo" if s == 0 else "Mínimo", key=f"input_traj_{i}") for i, m in enumerate(MESES))
    automatic = st.toggle("Recalcular automaticamente", value=True, key="input_auto")
    calculate = st.button("Recalcular agora", type="primary", width="stretch")
    st.button("Restaurar valores do notebook", on_click=reset, width="stretch")
    st.caption("Os valores são aplicados ao confirmar a edição de um campo. Sem recálculo automático, use o botão acima.")

st.markdown('<div class="eyebrow">LABORATÓRIO DE PLANEJAMENTO ENERGÉTICO</div>', unsafe_allow_html=True)
st.title("Água hoje. Energia amanhã.")
st.markdown('<div class="intro">Planejamento hidrotérmico · Batalha → Serra do Facão<br>Explore o efeito das entradas sobre a geração, o armazenamento e o custo de operação.</div>', unsafe_allow_html=True)

with st.expander("Editar afluências e parâmetros das usinas", expanded=False, key="input_details", on_change="rerun"):
    st.markdown("#### Afluências locais (m³/s)")
    st.caption("Máximo e mínimo formam dois cenários conjuntos equiprováveis. A afluência de Serra aqui é apenas a contribuição local.")
    afl = pd.DataFrame({"Mês": MESES, "Batalha · máximo": np.array(defaults.afl_max)[:, 0],
                        "Batalha · mínimo": np.array(defaults.afl_min)[:, 0],
                        "Serra · máximo": np.array(defaults.afl_max)[:, 1], "Serra · mínimo": np.array(defaults.afl_min)[:, 1]})
    afl = st.data_editor(afl, hide_index=True, disabled=["Mês"], key="input_afl", width="stretch",
                         column_config={c: st.column_config.NumberColumn(c, min_value=0.0, format="%.2f", required=True) for c in afl.columns if c != "Mês"})
    st.markdown("#### Hidrelétricas")
    hyd = pd.DataFrame({"Usina": UHES, "Volume mínimo (hm³)": defaults.vmin, "Volume máximo (hm³)": defaults.vmax,
                        "Engolimento (m³/s)": defaults.engolimento, "Produtibilidade (MW/(m³/s))": defaults.produtividade})
    hyd = st.data_editor(hyd, hide_index=True, disabled=["Usina"], key="input_hyd", width="stretch",
                         column_config={c: st.column_config.NumberColumn(c, min_value=0.0, format="%.6f", required=True) for c in hyd.columns if c != "Usina"})
    st.markdown("#### Termelétricas")
    thermal = pd.DataFrame({"Usina": ["BBF Baliza", "ERB Candeias"], "Potência máxima (MW)": defaults.gtmax, "Custo (R$/MWh)": defaults.custo_termico})
    thermal = st.data_editor(thermal, hide_index=True, disabled=["Usina"], key="input_thermal", width="stretch",
                             column_config={c: st.column_config.NumberColumn(c, min_value=0.0, format="%.2f", required=True) for c in thermal.columns if c != "Usina"})
    c1, c2 = st.columns(2)
    with c1:
        deficit_cost = num("Custo do déficit (R$/MWh)", defaults.custo_deficit, "cdef", step=100)
    with c2:
        serra_power = num("Potência nominal de Serra (MW)", defaults.potencia_serra, "serra", step=1)
    st.caption("Mantidos: meses de 720 horas, produtibilidade fixa, transferência integral no mesmo mês, custo terminal zero e penalização de vertimento de R$ 0,01/hm³.")

try:
    p = replace(defaults, carga=carga, nr_disc=int(nr_disc), inicial=inicial, trajetoria=trajetoria,
                vmin=tuple(hyd.iloc[:, 1]), vmax=tuple(hyd.iloc[:, 2]), engolimento=tuple(hyd.iloc[:, 3]), produtividade=tuple(hyd.iloc[:, 4]),
                gtmax=tuple(thermal.iloc[:, 1]), custo_termico=tuple(thermal.iloc[:, 2]), custo_deficit=deficit_cost, potencia_serra=serra_power,
                afl_max=tuple(map(tuple, afl.iloc[:, [1, 3]].to_numpy(dtype=float))),
                afl_min=tuple(map(tuple, afl.iloc[:, [2, 4]].to_numpy(dtype=float))))
    p.validate()
except (ValueError, TypeError) as exc:
    st.error(f"Revise as entradas: {exc}")
    st.stop()

changed = st.session_state.get("parameters") != p
if calculate or (automatic and changed):
    started = time.perf_counter()
    try:
        grades, estados, curvas = cached_policy(p.policy_parameters())
        results = avaliar(p, estados, curvas)
        st.session_state.solution = {**results, "grades": grades, "estados": estados, "curvas": curvas, "seconds": time.perf_counter()-started}
        st.session_state.parameters = p
    except (RuntimeError, ValueError) as exc:
        st.error(f"Não foi possível concluir a otimização: {exc}")
        st.stop()

if st.session_state.get("parameters") != p:
    st.info("Entradas alteradas. Clique em **Recalcular agora** para atualizar os resultados e os gráficos.")
    st.stop()

r = st.session_state.solution
planned, isolated = r["planejada"], r["isolada"]
cp, ci = sum(x["ci"] for x in planned), sum(x["ci"] for x in isolated)
expected = sum(r["custos_iniciais"])/2
def br(v, digits=2):
    return f"{v:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")

a, b, c, d = st.columns(4)
a.metric("Esperado inicial", f"R$ {br(expected/1e6)} mi", help="Média dos custos totais dos dois cenários no volume inicial real, incluindo custo futuro.")
b.metric("Realizado · planejado", f"R$ {br(cp/1e6)} mi", help="Soma dos custos imediatos da trajetória selecionada.")
c.metric("Realizado · isolados", f"R$ {br(ci/1e6)} mi")
d.metric("Isolados − planejado", f"R$ {br((ci-cp)/1e6)} mi", help="Diferença na trajetória realizada. Não há garantia de economia em toda trajetória individual.")
st.caption(f"Entradas calculadas · grade {p.nr_disc} × {p.nr_disc} · {br(r['seconds'], 1)} s nesta execução (pode incluir reutilização da política em cache).")

overview, future, tables, methodology = st.tabs(["Operação e armazenamento", "Custos futuros", "Dados e exportação", "Modelo e hipóteses"], key="main_tabs", on_change="rerun")
with overview:
    st.subheader("Atendimento à carga")
    left, right = st.columns(2)
    with left:
        st.markdown("**Com custo futuro**")
        st_echarts(charts.generation(p, planned), height="390px", key="gen_planned")
    with right:
        st.markdown("**Despachos isolados**")
        st_echarts(charts.generation(p, isolated), height="390px", key="gen_isolated")
    st.subheader("Água armazenada ao longo dos meses")
    left, right = st.columns(2)
    for i, col in enumerate((left, right)):
        with col:
            st.markdown(f"**{UHES[i]}**")
            st_echarts(charts.storage(p, planned, isolated, i), height="340px", key=f"storage_{i}")
    st.subheader("Custo imediato por mês")
    st_echarts(charts.costs(planned, isolated), height="340px", key="costs")
    if any(x["def"] > 1e-5 for x in planned):
        st.warning("Há déficit na trajetória planejada. Consulte os valores mensais na tabela de resultados.")
with future:
    st.subheader("Custo esperado por par de volumes iniciais")
    st.caption("Cada ponto representa o custo desde o mês indicado até novembro. A grade é usada pelo otimizador; a visualização não modifica sua interpolação convexa.")
    st.caption("Cores e altura da superfície: custo em R$ milhões. Eixos horizontais: volume útil inicial de cada UHE (%).")
    month = st.selectbox("Custo desde", range(3), format_func=lambda i: MESES[i], key="view_month")
    mode = st.radio("Visualização", ["Mapa de calor", "Superfície 3D"], horizontal=True, key="view_surface")
    st_echarts(charts.future_cost(p, r["curvas"][month], surface=mode == "Superfície 3D"), height="560px", key="future")
    if mode == "Superfície 3D":
        st.caption("Arraste para girar; use a roda do mouse para aproximar. Requer WebGL; o mapa de calor apresenta os mesmos dados.")
with tables:
    st.subheader("Resultados da trajetória selecionada")
    frames = {"planejada": tabela_resultados(p, planned), "isolada": tabela_resultados(p, isolated)}
    for label, frame in frames.items():
        st.markdown("**" + ("Com custo futuro" if label == "planejada" else "Despachos isolados") + "**")
        st.dataframe(frame.style.format(precision=3, decimal=",", thousands=".", subset=frame.select_dtypes("number").columns), hide_index=True, width="stretch")
    st.caption("Os custos realizados somam apenas custos imediatos. Somar FOB contaria custos futuros repetidamente.")
    initial_df = pd.DataFrame({"Cenário inicial": ["Máximo", "Mínimo"], "Custo total (R$ mi)": np.array(r["custos_iniciais"])/1e6})
    st.markdown("**Custos no volume inicial real**")
    st.dataframe(initial_df, hide_index=True, width="stretch")
    curve_df = pd.DataFrame(r["estados"], columns=["VI Batalha (hm³)", "VI Serra (hm³)"])
    for i, month_name in enumerate(MESES):
        curve_df[f"Custo desde {month_name} (R$)"] = r["curvas"][i]
    params_json = json.dumps(p.to_dict(), ensure_ascii=False, indent=2, allow_nan=False)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("parametros.json", params_json)
        for name, frame in {**frames, "custos_na_grade": curve_df, "custos_iniciais": initial_df}.items():
            z.writestr(name+".csv", frame.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"))
        z.writestr("LEIA-ME.txt", "Custos realizados = soma dos custos imediatos. Não somar FOB.\nCustos iniciais: dois cenários com 50% cada.\nParâmetros e tabelas pertencem à mesma execução.\n")
    c1, c2 = st.columns(2)
    c1.download_button("Baixar resultados completos (.zip)", buf.getvalue(), file_name="resultados_hidrotermicos.zip", mime="application/zip", width="stretch")
    c2.download_button("Baixar parâmetros (.json)", params_json, file_name="parametros.json", mime="application/json", width="stretch")
with methodology:
    st.subheader("A formulação do notebook, preservada")
    st.markdown("""
O planejamento percorre **novembro → outubro → setembro**. Para cada par de volumes iniciais, resolve os cenários máximo e mínimo e guarda a média dos dois custos ótimos. A simulação percorre os meses na ordem cronológica usando a política calculada.

- **Cascata:** Serra recebe sua afluência local, o turbinamento e o vertimento de Batalha no mesmo mês.
- **Cenários:** ambas as UHEs no máximo ou ambas no mínimo, com 50% cada e independência entre meses.
- **Custo futuro:** combinação convexa de todos os pares da grade, com pesos escolhidos pelo solver. Esses pesos não são probabilidades de afluência nem interpolação bilinear.
- **Despacho:** minimiza custo térmico, custo do déficit, R$ 0,01 por hm³ vertido e custo futuro. Solver SCIP via PySCIPOpt, tolerância dual de 1e-9, custos internos em R$ milhões.
- **Hipóteses:** três meses de 30 dias, produtividade constante, sem evaporação, sem vazão mínima obrigatória e custo futuro terminal zero.
- **Limites:** volumes mínimo/máximo, engolimentos, capacidades térmicas e limite nominal de Serra. Batalha mantém somente o limite de engolimento, como no notebook.

O custo esperado inicial considera os dois cenários; o custo realizado depende da trajetória escolhida. Políticas ótimas em expectativa podem não ser as mais baratas para toda trajetória individual. Soluções hidráulicas equivalentes podem variar entre versões do solver.
""")
    st.latex(r"V^f_B = V^i_B + A_B - V^t_B - V^v_B")
    st.latex(r"V^f_S = V^i_S + A_S + V^t_B + V^v_B - V^t_S - V^v_S")
    st.latex(r"\rho_B V^t_B + \rho_S V^t_S + G_1 + G_2 + D = Carga")
    st.caption("Fonte: planejamento_hidrotermico_3_estágios_2_UHE.ipynb. O notebook original está preservado em reference/original.ipynb.")

st.divider()
st.caption("Planejamento hidrotérmico · Apache ECharts · SCIP / PySCIPOpt · Valores padrão do notebook original")
