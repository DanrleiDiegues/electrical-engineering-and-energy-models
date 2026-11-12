from copy import deepcopy

import pandas as pd
import streamlit as st
from graficos_trabalhos import despacho, graficos_semana, dados_arvore, mostrar_arvore
from formulacao_trabalhos import formulacao_semana, formulacao_arvore

from catalogo_dessem import carregar_catalogo
from modelo_arvore import disciplina, quadro, fator, construir_arvore, cortes_da_continuacao, resolver_arvore, rotulo
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


@st.cache_data(max_entries=24, show_spinner="Resolvendo o compromisso térmico semanal no SCIP…")
def resolver_semana(unidades, percentual, custo_futuro):
    return despachar_semana(unidades, demanda_semana * percentual / 100, custo_futuro)


def semana():
    st.header("Compromisso térmico semanal")
    st.caption("Batalha e duas unidades térmicas • 168 horas • despacho a cada meia hora")
    formulacao_semana()
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
    graficos_semana(r, usinas)
    with st.expander("Despacho e estados por unidade"):
        st.dataframe(r["meia"])
        st.dataframe(r["estados"])


def ampliar_horizonte(caso, meses):
    for campo in ("carga", "aberturas"):
        ultimo = caso[campo][-1]
        caso[campo].extend(deepcopy(ultimo) for _ in range(meses-len(caso[campo])))


@st.cache_data(show_spinner=False)
def arvore_quadro(meses):
    caso = deepcopy(quadro)
    ampliar_horizonte(caso, meses)
    arv = construir_arvore(caso["aberturas"])
    _, sol = resolver_arvore(caso, arv, cortes_da_continuacao(caso))
    return dados_arvore(caso, arv, sol, 1.)


@st.cache_data(max_entries=24, show_spinner=False)
def resolver_pl(usinas, meses):
    caso = deepcopy(disciplina)
    nomes = list(usinas)
    for j, (nome, d) in enumerate(usinas.items()):
        # As duas UTEs que constam no estudo mensal mantêm os dados desse estudo.
        referencia = {322: 0, 106: 1}.get(d["codigo"]) if d["ug"] == 1 else None
        caso["gtmax"][j] = disciplina["gtmax"][referencia] if referencia is not None else d["Pmax"]
        caso["cvu"][j] = disciplina["cvu"][referencia] if referencia is not None else d["cvu"]
    caso["termicas"] = nomes
    ampliar_horizonte(caso, meses)
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
    return custo, pd.DataFrame(linhas), cadastro, dados_arvore(caso, arv, resultado, fator)


def arvore():
    st.header("PL Único em árvore de cenários")
    formulacao_arvore()
    meses = st.sidebar.slider("Horizonte da árvore (meses)", 3, 6, 3, key="arvore_meses")
    st.caption(f"{meses} meses · {2**meses-1} nós · {2**(meses-1)} trajetórias finais")
    if meses > 3:
        st.caption("Nos meses adicionais, cada nó repete a carga e as duas aberturas de afluência do mês 3, com 50% de probabilidade por ramo. Os cortes passam às folhas do novo horizonte.")
    usinas = selecionar("arvore", [322, 106])
    custo, df, cadastro, raiz = resolver_pl(usinas, meses)
    st.dataframe(cadastro, hide_index=True)
    st.caption("Baliza UG 1 e Candeias UG 1 usam potência e CVU do estudo mensal do Colab. As demais unidades usam o cadastro DESSEM lido pelo PySDDP.")
    st.metric("Custo esperado (R$)", f"{custo:,.2f}")
    st.subheader("Árvores de cenários")
    caso_real, caso_quadro = st.tabs(["Batalha e Serra do Facão", "Exemplo do quadro"])
    with caso_real:
        st.caption("Em cada nó, os valores aparecem na ordem Batalha / Serra do Facão. AFL é a afluência local em m³/s e VF é o volume final em hm³. Arraste ou use o zoom para explorar.")
        mostrar_arvore(raiz, meses, "arv_real")
    with caso_quadro:
        st.caption("Caso didático do Colab com uma UHE e duas térmicas de referência. AFL é dada em hm³ por estágio e VF em hm³. Os seletores de térmicas se aplicam ao caso Batalha e Serra do Facão.")
        mostrar_arvore(arvore_quadro(meses), meses, "arv_quadro")
    st.subheader("Atendimento à carga por nó")
    despacho(df, "Nó", [*disciplina["nomes"], *usinas, "Déficit"], "arvore_ger")
    st.dataframe(df, hide_index=True)


