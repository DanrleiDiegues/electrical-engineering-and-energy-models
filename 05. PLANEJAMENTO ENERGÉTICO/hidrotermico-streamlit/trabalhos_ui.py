from copy import deepcopy

import pandas as pd
import streamlit as st
from graficos_trabalhos import despacho, graficos_semana, grafico_carga, dados_arvore, mostrar_arvore
from formulacao_trabalhos import formulacao_semana, formulacao_arvore

from catalogo_dessem import carregar_catalogo
from modelo_arvore import disciplina, quadro, fator, construir_arvore, cortes_da_continuacao, resolver_arvore, rotulo
from modelo_semana import HIDRO, demanda_semana, despachar_semana


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


CAMPOS = ("Ton", "Toff", "Pmin", "Pmax", "subida", "descida", "cvu", "partida")
ROTULOS = {"Ton": "Ton", "Toff": "Toff", "Pmin": "Mín.", "Pmax": "Máx.", "subida": "Subida",
           "descida": "Descida", "cvu": "CVU", "partida": "Custo de partida"}


def restaurar_cadastro(nome):
    for campo in CAMPOS:
        st.session_state.pop(f"semana_{nome}_{campo}", None)


def parametros_unidade(nome, d, cadastro):
    """Controles de uma unidade. Os valores iniciais vêm do cadastro DESSEM lido pelo PySDDP."""
    chave = lambda campo: f"semana_{nome}_{campo}"
    for campo in CAMPOS:
        st.session_state.setdefault(chave(campo), int(cadastro[campo]) if campo in ("Ton", "Toff") else float(cadastro[campo]))
    st.caption("Permanência mínima")
    for campo in ("Ton", "Toff"):
        d[campo] = st.slider(f"{campo} (h)", 1, max(48, cadastro[campo]), key=chave(campo))
    st.caption("Limites de potência")
    esq, dir_ = st.columns(2)
    # A potência máxima não pode ficar abaixo das trajetórias de partida e parada cadastradas.
    d["Pmax"] = dir_.number_input("Máx. (MW)", min_value=max(max(d["A"] + d["D"]), 0.1), step=1.0, key=chave("Pmax"))
    if st.session_state[chave("Pmin")] > d["Pmax"]:
        st.session_state[chave("Pmin")] = d["Pmax"]
    d["Pmin"] = esq.number_input("Mín. (MW)", min_value=0.0, max_value=d["Pmax"], step=1.0, key=chave("Pmin"))
    st.caption("Rampas")
    esq, dir_ = st.columns(2)
    d["subida"] = esq.number_input("Subida (MW/h)", min_value=0.1, step=1.0, key=chave("subida"))
    d["descida"] = dir_.number_input("Descida (MW/h)", min_value=0.1, step=1.0, key=chave("descida"))
    st.caption("Custos")
    esq, dir_ = st.columns(2)
    d["cvu"] = esq.number_input("CVU (R$/MWh)", min_value=0.0, step=1.0, key=chave("cvu"))
    d["partida"] = dir_.number_input("Partida (R$)", min_value=0.0, step=100.0, key=chave("partida"))
    st.button("Restaurar cadastro", key=f"semana_{nome}_restaurar", on_click=restaurar_cadastro,
              args=(nome,), width="stretch")


def alteracoes(d, cadastro):
    return ", ".join(ROTULOS[c] for c in CAMPOS if d[c] != cadastro[c]) or "—"


def carga_semana(carga, percentual, capacidade):
    st.subheader("Carga da semana")
    c = st.columns(4)
    ajuste = None if percentual == 100 else f"{percentual:g}% da carga base"
    c[0].metric("Carga média (MW)", f"{carga.mean():.1f}", delta=ajuste, delta_color="off")
    c[1].metric("Pico (MW)", f"{carga.max():.1f}", help=f"Carga base: {demanda_semana.max():.1f} MW de pico e {demanda_semana.mean():.1f} MW de média.")
    c[2].metric("Energia semanal (MWh)", f"{carga.sum():,.0f}")
    c[3].metric("Folga de capacidade (MW)", f"{capacidade - carga.max():,.1f}",
                help="Capacidade instalada (térmicas selecionadas e turbinamento máximo de Batalha) menos o pico da carga. Valores negativos indicam déficit inevitável.")
    grafico_carga(demanda_semana, carga, capacidade, "uct_carga")
    st.caption("Carga horária em MW médios; a mesma carga vale para as duas meias horas de cada hora. "
               f"A linha tracejada soma o máximo das térmicas e o turbinamento máximo de Batalha ({capacidade:,.1f} MW).")


def semana():
    st.header("Compromisso térmico semanal")
    st.caption("Batalha e duas unidades térmicas • 168 horas • despacho a cada meia hora")
    formulacao_semana()
    usinas = selecionar("semana", [106, 322])
    cadastro = {nome: dict(d) for nome, d in usinas.items()}
    for nome, d in usinas.items():
        with st.sidebar.expander(nome):
            parametros_unidade(nome, d, cadastro[nome])
    percentual = st.sidebar.number_input("Carga semanal (% do caso-base)", min_value=1, value=100, key="semana_carga")
    carga = demanda_semana * percentual / 100
    st.sidebar.caption(f"Carga base: média {demanda_semana.mean():.1f} MW · pico {demanda_semana.max():.1f} MW. "
                       f"Carga aplicada: média {carga.mean():.1f} MW · pico {carga.max():.1f} MW.")
    custo_futuro = st.sidebar.checkbox("Aplicar custo futuro", True, key="semana_fcf")
    auto = st.sidebar.toggle("Recalcular automaticamente", True, key="semana_auto")
    calcular = st.sidebar.button("Recalcular agora", key="semana_calcular", disabled=auto, width="stretch")

    capacidade = sum(d["Pmax"] for d in usinas.values()) + HIDRO["rho"] * HIDRO["Qmax"]
    carga_semana(carga, percentual, capacidade)

    st.subheader("Cadastro das unidades")
    tabela = pd.DataFrame(usinas).T[["Pmin","Pmax","Ton","Toff","subida","descida","cvu","partida","p0"]]
    tabela = tabela.rename(columns={"Pmin":"Mín. (MW)", "Pmax":"Máx. (MW)", "Ton":"Ton (h)",
                                    "Toff":"Toff (h)", "subida":"Subida (MW/h)", "descida":"Descida (MW/h)",
                                    "cvu":"CVU (R$/MWh)", "partida":"Partida (R$)", "p0":"Geração inicial (MW)"})
    tabela["Alterado em relação ao cadastro"] = [alteracoes(d, cadastro[n]) for n, d in usinas.items()]
    st.dataframe(tabela)

    assinatura = repr((usinas, percentual, custo_futuro))
    if calcular or "semana_assinatura" not in st.session_state or (auto and st.session_state["semana_assinatura"] != assinatura):
        try:
            resultado, erro = resolver_semana(usinas, percentual, custo_futuro), None
        except RuntimeError as exc:
            resultado, erro = None, str(exc)
        st.session_state.update(semana_resultado=resultado, semana_erro=erro,
                                semana_assinatura=assinatura, semana_usinas=list(usinas))
    r, erro = st.session_state["semana_resultado"], st.session_state["semana_erro"]
    if st.session_state["semana_assinatura"] != assinatura:
        st.info("Entradas alteradas. Clique em Recalcular agora para atualizar os resultados e os gráficos.")
    if erro:
        if "infeasible" in erro:
            st.warning("Despacho inviável. Confira a geração inicial, os limites de potência, as rampas, os tempos mínimos e a carga semanal. Unidades de maior porte podem exigir uma carga maior.")
        else:
            st.warning(erro)
    if r is None:
        return
    nomes = st.session_state["semana_usinas"]
    meia, estados = r["meia"], r["estados"]
    st.subheader("Resultado")
    c = st.columns(4)
    c[0].metric("Custo total (R$)", f"{r['total']:,.2f}")
    c[1].metric("Custo imediato e partidas (R$)", f"{r['imediato']:,.2f}")
    c[2].metric("Custo futuro (R$)", f"{r['futuro']:,.2f}")
    c[3].metric("Déficit (MWh)", f"{meia['déficit'].sum() * 0.5:,.1f}")
    c = st.columns(4)
    volume = meia["volume"].iloc[-1]
    c[0].metric("Volume final de Batalha (hm³)", f"{volume:,.1f}", delta=f"{volume - HIDRO['VI']:+,.1f} hm³ desde o início", delta_color="off")
    c[1].metric("Partidas térmicas", int(estados["partida"].sum()))
    c[2].metric("Geração hidrelétrica (MWh)", f"{meia['UHE'].sum() * 0.5:,.1f}")
    c[3].metric("Geração térmica (MWh)", f"{meia[nomes].sum().sum() * 0.5:,.1f}")
    st.caption(f"SCIP · {r['status']} · gap {r['gap']:.2%}")
    graficos_semana(r, nomes)
    with st.expander("Despacho e estados por unidade"):
        st.dataframe(meia)
        st.dataframe(estados)
        st.download_button("Baixar despacho em meia hora (CSV)", meia.to_csv(index=False).encode("utf-8"),
                           "despacho_semanal.csv", "text/csv", key="semana_csv")


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
    caso_real, caso_quadro = st.tabs(["Batalha e Serra do Facão", "Cenário Base"])
    with caso_real:
        st.caption("Em cada nó, os valores aparecem na ordem Batalha / Serra do Facão. AFL é a afluência local em m³/s e VF é o volume final em hm³. Arraste ou use o zoom para explorar.")
        mostrar_arvore(raiz, meses, "arv_real")
    with caso_quadro:
        st.caption("Caso didático do Colab com uma UHE e duas térmicas de referência. AFL é dada em hm³ por estágio e VF em hm³. Os seletores de térmicas se aplicam ao caso Batalha e Serra do Facão.")
        mostrar_arvore(arvore_quadro(meses), meses, "arv_quadro")
    st.subheader("Atendimento à carga por nó")
    despacho(df, "Nó", [*disciplina["nomes"], *usinas, "Déficit"], "arvore_ger")
    st.dataframe(df, hide_index=True)


