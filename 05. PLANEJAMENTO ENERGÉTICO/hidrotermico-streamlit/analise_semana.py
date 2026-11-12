"""Seções de análise do DESSEM semanal: arquivos de entrada, CMO, CMA, ordem de mérito, impacto da carga e custo futuro."""
import numpy as np
import pandas as pd
import streamlit as st

from catalogo_dessem import diagnostico_catalogo, registros_unidade
from charts import COLORS
from graficos_trabalhos import grafico_cma, grafico_cmo, grafico_custos, grafico_volumes
from modelo_semana import CDEF, HIDRO, demanda_semana, impacto_carga

ARQUIVOS = pd.DataFrame([
    ("termdat.dat", "CADUSIT", "Nome da usina e quantas unidades ela tem.", "Identificação da unidade."),
    ("termdat.dat", "CADUNIDT", "Pot, PotMin, On, Of, CCold, RUp, RDown", "Pmax, Pmin, Ton, Toff, custo de partida e rampas de subida e descida."),
    ("operut.dat", "INIT", "st, GerInic, tempo, MH, A/D", "Estado inicial (ligada ou não), geração inicial e tempo já cumprido nesse estado."),
    ("operut.dat", "OPER", "Custo (e Gmin/Gmax horários)", "CVU em R$/MWh. Unidades com Gmin ou Gmax horário ficam fora do modelo."),
    ("rampas.dat", "RAMP", "T (A ou D), Potencia, Tempo, FlagMeiaHora", "Curva de partida (A) e de desligamento (D), em meias horas, e potência de cada ponto."),
], columns=["Arquivo", "Bloco", "Campos lidos", "O que vira no modelo"])


@st.cache_data(show_spinner=False)
def diagnostico():
    return diagnostico_catalogo()


@st.cache_data(show_spinner=False)
def registros(codigo, ug):
    return registros_unidade(codigo, ug)


def arquivos_de_entrada(usinas):
    with st.expander("Arquivos de entrada do DESSEM · PySDDP"):
        st.markdown("O DESSEM descreve cada usina térmica em três arquivos. O PySDDP lê os arquivos de `dados_dessem/` "
                    "e o app monta, para cada unidade, os parâmetros que aparecem na lateral.")
        st.dataframe(ARQUIVOS, hide_index=True)
        total, tabela = diagnostico()
        st.markdown(f"O `termdat.dat` traz **{total} unidades**; o modelo semanal aceita **{int(tabela.iloc[0]['Unidades'])}**. "
                    "As demais não têm os dados completos de que o compromisso horário precisa:")
        st.dataframe(tabela, hide_index=True)
        st.markdown("**Registros lidos para as unidades selecionadas**")
        abas = st.tabs(list(usinas))
        for aba, (nome, d) in zip(abas, usinas.items()):
            with aba:
                for titulo, df in registros(d["codigo"], d["ug"]).items():
                    st.caption(titulo)
                    st.dataframe(df, hide_index=True)


def resumo_diario(meia):
    dia = (meia.hora // 24).astype(int) + 1
    g = meia.groupby(dia)
    return pd.DataFrame({"Carga média (MW)": g["carga"].mean().round(1),
                         "CMO mín. (R$/MWh)": g["cmo"].min().round(2),
                         "CMO médio (R$/MWh)": g["cmo"].mean().round(2),
                         "CMO máx. (R$/MWh)": g["cmo"].max().round(2),
                         "CMA médio (R$/hm³)": g["cma"].mean().round(0)}).rename_axis("Dia").reset_index()


def marginais(r):
    meia = r["meia"]
    if "cmo" not in meia:
        st.info("Os custos marginais não puderam ser calculados para este caso.")
        return
    st.subheader("Custo marginal da operação (CMO)")
    st.caption("O CMO é o custo de atender 1 MWh a mais em cada meia hora. Vem do problema linear que resulta de fixar "
               "os estados de liga e desliga da solução ótima: é o multiplicador do balanço de carga. Custos de partida "
               "e tempos mínimos não entram nele.")
    c = st.columns(3)
    c[0].metric("CMO médio (R$/MWh)", f"{meia.cmo.mean():,.2f}")
    c[1].metric("CMO mínimo (R$/MWh)", f"{meia.cmo.min():,.2f}")
    c[2].metric("CMO máximo (R$/MWh)", f"{meia.cmo.max():,.2f}")
    grafico_cmo(meia, "uct_cmo")
    st.dataframe(resumo_diario(meia), hide_index=True)
    if not r.get("marginais", True):
        st.caption("Atenção: o custo do problema linear com estados fixos difere do custo do SCIP; leia os marginais com cautela.")
    st.subheader("Custo marginal da água (CMA)")
    mwh = r["mwh_por_hm3"]
    st.caption(f"O CMA é quanto vale ter 1 hm³ a mais em Batalha: o multiplicador do balanço hídrico. Um hm³ turbinado rende "
               f"cerca de {mwh:,.1f} MWh, o que permite ler o CMA também em R$/MWh (eixo da direita). Aqui o CMA vem do corte "
               "do custo futuro que limita o volume final. Sem custo futuro, a água não tem valor de oportunidade e o CMA é zero.")
    c = st.columns(2)
    c[0].metric("CMA médio (R$/hm³)", f"{meia.cma.mean():,.0f}")
    c[1].metric("CMA médio (R$/MWh)", f"{meia.cma_mwh.mean():,.2f}")
    grafico_cma(meia, mwh, "uct_cma")


def ordem_merito(r, usinas):
    meia, estados = r["meia"], r["estados"]
    linhas = [{"Fonte": nome, "Tipo": "Térmica", "Custo (R$/MWh)": d["cvu"], "Capacidade (MW)": d["Pmax"],
               "Energia na semana (MWh)": meia[nome].sum() * 0.5,
               "Horas ligada": int(estados.loc[estados.unidade == nome, "ligada"].sum())}
              for nome, d in usinas.items()]
    linhas.append({"Fonte": "Água de Batalha (CMA)", "Tipo": "Hidrelétrica", "Custo (R$/MWh)": float(meia.cma_mwh.mean()),
                   "Capacidade (MW)": HIDRO["rho"] * HIDRO["Qmax"], "Energia na semana (MWh)": meia.UHE.sum() * 0.5,
                   "Horas ligada": None})
    linhas.append({"Fonte": "Déficit", "Tipo": "Penalidade", "Custo (R$/MWh)": CDEF, "Capacidade (MW)": None,
                   "Energia na semana (MWh)": meia["déficit"].sum() * 0.5, "Horas ligada": None})
    return pd.DataFrame(linhas).sort_values("Custo (R$/MWh)").reset_index(drop=True)


def explicacao_merito(tabela, custo_futuro):
    agua = tabela[tabela.Tipo == "Hidrelétrica"].iloc[0]["Custo (R$/MWh)"]
    termicas = tabela[tabela.Tipo == "Térmica"]
    if not custo_futuro or agua <= 1e-6:
        return ("Com o custo futuro desligado a água não tem valor de oportunidade: o CMA é zero e o modelo a usa antes de "
                "qualquer térmica, até o limite de turbinamento. As térmicas só complementam a carga e só ficam ligadas "
                "quando compensam os custos de partida e os tempos mínimos.")
    baratas = termicas[termicas["Custo (R$/MWh)"] < agua]
    caras = termicas[termicas["Custo (R$/MWh)"] >= agua]
    texto = [f"Gastar a água de Batalha agora custa, em oportunidade, **R$ {agua:,.2f}/MWh** (o CMA médio): é o valor que o "
             "corte do custo futuro atribui ao volume que deixa de ficar guardado."]
    if len(baratas):
        nomes = ", ".join(f"{n} (R$ {c:,.2f}/MWh)" for n, c in zip(baratas.Fonte, baratas["Custo (R$/MWh)"]))
        texto.append(f"{nomes} custa menos que a água. Por isso o modelo mantém essa térmica no máximo sempre que ela está "
                     "ligada e usa a hidráulica só para completar a carga, poupando água.")
    if len(caras):
        nomes = ", ".join(f"{n} (R$ {c:,.2f}/MWh)" for n, c in zip(caras.Fonte, caras["Custo (R$/MWh)"]))
        texto.append(f"{nomes} custa mais que a água. Só entra quando a hidráulica e as térmicas mais baratas não bastam, "
                     "como nos picos de carga.")
    texto.append("Desligar o custo futuro, na lateral, mostra a outra face: sem valor para a água, a hidráulica passa a "
                 "substituir as térmicas.")
    return " ".join(texto)


def merito(r, entradas):
    usinas, _, custo_futuro = entradas
    if "cma_mwh" not in r["meia"]:
        return
    st.subheader("Por que a térmica entra antes da água?")
    tabela = ordem_merito(r, usinas)
    fontes = [("Água de Batalha (CMA)", float(r["meia"].cma_mwh.mean()), COLORS[0])]
    fontes += [(nome, d["cvu"], COLORS[1 + i % (len(COLORS) - 1)]) for i, (nome, d) in enumerate(usinas.items())]
    grafico_custos(fontes, "uct_merito")
    st.markdown(explicacao_merito(tabela, custo_futuro))
    st.dataframe(tabela.round(2), hide_index=True)
    st.caption(f"O déficit custa R$ {CDEF:,.0f}/MWh e fica fora do gráfico por causa da escala.")


@st.cache_data(max_entries=48, show_spinner="Reotimizando com a carga acrescida…")
def reotimizar(unidades, percentual, custo_futuro, hora, delta):
    return impacto_carga(unidades, demanda_semana * percentual / 100, custo_futuro, hora, delta)


def impacto_da_carga(r, entradas):
    usinas, percentual, custo_futuro = entradas
    meia = r["meia"]
    if "cmo" not in meia:
        return
    st.subheader("Impacto de elevar a carga em uma hora")
    st.caption("Soma um acréscimo de carga a uma hora e reotimiza a semana. O custo previsto pelo CMO é o acréscimo vezes o CMO "
               "das duas meias horas; o custo real inclui a mudança do compromisso das térmicas.")
    c1, c2 = st.columns(2)
    hora = c1.slider("Hora da semana", 0, 167, 20, key="semana_imp_hora")
    delta = c2.number_input("Acréscimo de carga (MW)", min_value=0.5, max_value=50.0, value=1.0, step=0.5, key="semana_imp_delta")
    previsto = delta * 0.5 * (meia.cmo[2 * hora] + meia.cmo[2 * hora + 1])
    try:
        real = reotimizar(usinas, percentual, custo_futuro, hora, delta) - r["total"]
    except RuntimeError as exc:
        st.warning(f"Não foi possível reotimizar com a carga acrescida: {exc}")
        return
    c = st.columns(4)
    c[0].metric("Hora", f"Dia {hora // 24 + 1} · {hora % 24:02d}h")
    c[1].metric("Previsto pelo CMO (R$)", f"{previsto:,.2f}")
    c[2].metric("Custo real adicional (R$)", f"{real:,.2f}")
    c[3].metric("Diferença (R$)", f"{real - previsto:,.2f}")
    if abs(real - previsto) <= 0.01 * max(abs(previsto), 1.):
        st.caption("O CMO descreve bem este acréscimo: o compromisso das térmicas não mudou.")
    else:
        st.caption("O custo real fugiu do previsto. Com mais carga, o compromisso pode mudar (nova partida, falta de folga de "
                   "rampa ou de capacidade), e o CMO, calculado com liga e desliga fixos, não enxerga esses degraus.")


def indicadores(r, nomes):
    meia, estados = r["meia"], r["estados"]
    termica = meia[nomes].sum().sum() * 0.5
    linhas = {"Custo total (R$)": f"{r['total']:,.2f}", "Custo futuro (R$)": f"{r['futuro']:,.2f}",
              "Déficit (MWh)": f"{meia['déficit'].sum() * 0.5:,.1f}", "Geração hidrelétrica (MWh)": f"{meia['UHE'].sum() * 0.5:,.1f}",
              "Geração térmica (MWh)": f"{termica:,.1f}", "Volume final de Batalha (hm³)": f"{meia['volume'].iloc[-1]:,.1f}",
              "Partidas térmicas": f"{int(estados['partida'].sum())}"}
    if "cmo" in meia:
        linhas.update({"CMO médio (R$/MWh)": f"{meia.cmo.mean():,.2f}", "CMA médio (R$/MWh)": f"{meia.cma_mwh.mean():,.2f}"})
    return linhas


def com_e_sem_custo_futuro(r, entradas, resolver, nomes):
    usinas, percentual, custo_futuro = entradas
    atual, outro = ("Com custo futuro", "Sem custo futuro") if custo_futuro else ("Sem custo futuro", "Com custo futuro")
    st.subheader("Efeito do custo futuro")
    if not st.toggle(f"Comparar com o caso \"{outro.lower()}\"", key="semana_comparar"):
        return
    try:
        alternativo = resolver(usinas, percentual, not custo_futuro)
    except RuntimeError as exc:
        st.warning(f"Não foi possível resolver o caso alternativo: {exc}")
        return
    a, b = indicadores(r, nomes), indicadores(alternativo, nomes)
    st.dataframe(pd.DataFrame({atual: a, outro: {k: b.get(k, "—") for k in a}}))
    grafico_volumes([(atual, r), (outro, alternativo)], "uct_vol_comparacao")
    st.caption("O custo futuro dá valor à água que fica no reservatório no fim da semana. Sem ele, o modelo gasta água livremente "
               "e deixa de comprar geração térmica; o custo total cai porque o benefício de guardar água para a semana seguinte "
               "deixa de ser contabilizado.")
