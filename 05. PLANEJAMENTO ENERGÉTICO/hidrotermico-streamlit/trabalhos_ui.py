from copy import deepcopy

import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from catalogo_dessem import carregar_catalogo
from charts import base
from modelo_arvore import disciplina, construir_arvore, cortes_da_continuacao, resolver_arvore, rotulo
from modelo_semana import demanda_semana, despachar_semana


@st.cache_data(show_spinner=False)
def catalogo():
    return carregar_catalogo()


def selecionar(prefixo, padroes):
    dados = catalogo()
    escolhidas = {}
    for pos, codigo in enumerate(padroes):
        opcoes = [k for k, d in dados.items() if d["codigo"] not in
                  {u["codigo"] for u in escolhidas.values()}]
        padrao = next((k for k in opcoes if dados[k]["codigo"] == codigo and dados[k]["ug"] == 1), opcoes[0])
        nome = st.sidebar.selectbox(f"Térmica {pos + 1}", opcoes, index=opcoes.index(padrao),
                                    key=f"{prefixo}_ute_{pos}")
        escolhidas[nome] = dados[nome]
    return escolhidas


def grafico(df, eixo, colunas, chave):
    op = base()
    op.update(xAxis={"type": "category", "data": df[eixo].tolist()},
              yAxis={"type": "value", "name": "MW"},
              series=[{"type": "bar", "stack": "oferta", "name": c, "data": df[c].tolist()}
                      for c in colunas])
    st_echarts(options=op, height="380px", key=chave)


@st.cache_data(max_entries=24, show_spinner="Resolvendo o compromisso térmico semanal no SCIP…")
def resolver_semana(unidades, percentual, custo_futuro):
    return despachar_semana(unidades, demanda_semana * percentual / 100, custo_futuro)


def semana():
    st.header("Compromisso térmico semanal")
    st.caption("Batalha e duas unidades térmicas • 168 horas • despacho a cada meia hora")
    usinas = selecionar("semana", [106, 322])
    for nome, d in usinas.items():
        with st.sidebar.expander(nome):
            for campo in ("Ton", "Toff"):
                d[campo] = st.slider(f"{campo} (h)", 1, max(48, d[campo]), d[campo],
                                     key=f"semana_{nome}_{campo}")
    percentual = st.sidebar.number_input("Carga semanal (% do caso-base)", min_value=1, value=100, key="semana_carga")
    custo_futuro = st.sidebar.checkbox("Aplicar custo futuro", True, key="semana_fcf")
    st.dataframe(pd.DataFrame(usinas).T[["Pmin","Pmax","Ton","Toff","subida","descida","cvu","p0"]]
                 .rename(columns={"Pmin":"Mín. (MW)", "Pmax":"Máx. (MW)", "Ton":"Ton (h)",
                                  "Toff":"Toff (h)", "subida":"Subida (MW/h)", "descida":"Descida (MW/h)",
                                  "cvu":"CVU (R$/MWh)", "p0":"Geração inicial (MW)"}))
    try:
        r = resolver_semana(usinas, percentual, custo_futuro)
    except RuntimeError as exc:
        if "infeasible" in str(exc):
            st.warning("Despacho inviável. Confira a geração inicial, os mínimos técnicos e a carga semanal. Unidades de maior porte podem exigir uma carga maior.")
        else:
            st.warning(str(exc))
        return
    st.metric("Custo total (R$)", f"{r['total']:,.2f}")
    st.caption(f"SCIP · {r['status']} · gap {r['gap']:.2%}")
    grafico(r["meia"], "hora", ["UHE", *usinas, "déficit"], "uct_ger")
    with st.expander("Despacho e estados por unidade"):
        st.dataframe(r["meia"])
        st.dataframe(r["estados"])


@st.cache_data(max_entries=24, show_spinner=False)
def resolver_pl(usinas):
    caso = deepcopy(disciplina)
    nomes = list(usinas)
    for j, (nome, d) in enumerate(usinas.items()):
        # As duas UTEs que constam no estudo mensal mantêm os dados desse estudo.
        referencia = {322: 0, 106: 1}.get(d["codigo"]) if d["ug"] == 1 else None
        caso["gtmax"][j] = disciplina["gtmax"][referencia] if referencia is not None else d["Pmax"]
        caso["cvu"][j] = disciplina["cvu"][referencia] if referencia is not None else d["cvu"]
    caso["termicas"] = nomes
    arv = construir_arvore(caso["aberturas"])
    custo, resultado = resolver_arvore(caso, arv, cortes_da_continuacao(caso))
    linhas = []
    for no, b in resultado.items():
        linhas.append({"Nó": rotulo(no), "Mês": len(no), "Probabilidade": arv[no]["prob"],
                       **dict(zip(caso["nomes"], caso["prod"] * b["q"])),
                       **dict(zip(nomes, b["g"])), "Déficit": b["d"], "Custo imediato (R$)": b["ci"],
                       "Custo futuro (R$)": b["alpha"],
                       **{f"Volume {n} (hm³)": v for n,v in zip(caso["nomes"],b["v"])}})
    cadastro = pd.DataFrame({"Unidade": nomes, "Máx. (MW)": caso["gtmax"], "CVU (R$/MWh)": caso["cvu"]})
    return custo, pd.DataFrame(linhas), cadastro


def arvore():
    st.header("PL Único em árvore de cenários")
    st.caption("Batalha e Serra do Facão • três meses • sete nós • cortes de custo futuro nas folhas")
    usinas = selecionar("arvore", [322, 106])
    custo, df, cadastro = resolver_pl(usinas)
    st.dataframe(cadastro, hide_index=True)
    st.caption("Baliza UG 1 e Candeias UG 1 usam potência e CVU do estudo mensal do Colab. As demais unidades usam o cadastro DESSEM lido pelo PySDDP.")
    st.metric("Custo esperado (R$)", f"{custo:,.2f}")
    grafico(df, "Nó", [*disciplina["nomes"], *usinas, "Déficit"], "arvore_ger")
    st.dataframe(df, hide_index=True)


