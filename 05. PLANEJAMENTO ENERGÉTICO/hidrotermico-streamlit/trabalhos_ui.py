from copy import deepcopy

import numpy as np
import pandas as pd
import streamlit as st
from graficos_trabalhos import despacho, graficos_semana, grafico_carga, dados_arvore, mostrar_arvore, tabela_folhas
from formulacao_trabalhos import formulacao_semana, formulacao_arvore

from analise_semana import (arquivos_de_entrada, com_e_sem_custo_futuro, com_e_sem_hidro_flat, impacto_da_carga, marginais, merito)
from catalogo_dessem import carregar_catalogo
from modelo_arvore import disciplina, quadro, fator, construir_arvore, cortes_da_continuacao, resolver_arvore, rotulo, ampliar_horizonte, estudo_arvore, caso_pysddp
import dados_pysddp as dp
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
def resolver_semana(unidades, percentual, custo_futuro, hidro_flat=True):
    return despachar_semana(unidades, demanda_semana * percentual / 100, custo_futuro, hidro_flat=hidro_flat)


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
    from metodologia import mostrar_algoritmo
    mostrar_algoritmo(st, '7.')
    with st.expander("Por que a hidrelétrica não fica flat? (onde isso está no código)"):
        from metodologia import BLOCOS
        inicio = next(i for i, b in enumerate(BLOCOS) if b[0] == "h2" and b[1].startswith("7.3"))
        fim = next(i for i, b in enumerate(BLOCOS) if b[0] == "h1" and b[1].startswith("8."))
        for b in BLOCOS[inicio + 1:fim]:
            if b[0] == "p":
                st.markdown(b[1])
            elif b[0] == "eq":
                st.latex(b[1] + r"\tag{" + b[2] + "}")
            elif b[0] == "tabela":
                st.dataframe(pd.DataFrame(b[2], columns=b[1]), hide_index=True)
        st.caption("Os trechos estão marcados com [POR QUE NÃO É FLAT] em modelo_semana.py. Texto completo na aba Metodologia, seção 7.")
    n_termicas = st.sidebar.number_input("Número de térmicas", 1, 4, 2, key="semana_n_termicas",
                                         help="As unidades vêm do cadastro DESSEM (PySDDP). Veja quais o modelo aceita no painel de arquivos de entrada.")
    usinas = selecionar("semana", [106, 322, None, None][:n_termicas])
    cadastro = {nome: dict(d) for nome, d in usinas.items()}
    for nome, d in usinas.items():
        with st.sidebar.expander(nome):
            parametros_unidade(nome, d, cadastro[nome])
    percentual = st.sidebar.number_input("Carga semanal (% do caso-base)", min_value=1, value=100, key="semana_carga")
    carga = demanda_semana * percentual / 100
    st.sidebar.caption(f"Carga base: média {demanda_semana.mean():.1f} MW · pico {demanda_semana.max():.1f} MW. "
                       f"Carga aplicada: média {carga.mean():.1f} MW · pico {carga.max():.1f} MW.")
    custo_futuro = st.sidebar.checkbox("Aplicar custo futuro", True, key="semana_fcf")
    hidro_flat = st.sidebar.checkbox("Hidrelétrica flat (vazão constante)", True, key="semana_flat",
                                     help="Batalha turbina a mesma vazão em todas as meias horas; o modelo escolhe esse valor. "
                                          "Desmarque para deixar a vazão livre a cada meia hora (a hidro passa a seguir a carga).")
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
    arquivos_de_entrada(usinas)

    assinatura = repr((usinas, percentual, custo_futuro, hidro_flat))
    if calcular or "semana_assinatura" not in st.session_state or (auto and st.session_state["semana_assinatura"] != assinatura):
        try:
            resultado, erro = resolver_semana(usinas, percentual, custo_futuro, hidro_flat), None
        except RuntimeError as exc:
            resultado, erro = None, str(exc)
        st.session_state.update(semana_resultado=resultado, semana_erro=erro,
                                semana_assinatura=assinatura, semana_usinas=list(usinas),
                                semana_entradas=(usinas, percentual, custo_futuro, hidro_flat))
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
    entradas = st.session_state["semana_entradas"]
    marginais(r)
    merito(r, entradas)
    impacto_da_carga(r, entradas)
    com_e_sem_custo_futuro(r, entradas, resolver_semana, nomes)
    com_e_sem_hidro_flat(r, entradas, resolver_semana, nomes)
    with st.expander("Despacho e estados por unidade"):
        st.dataframe(meia)
        st.dataframe(estados)
        st.download_button("Baixar despacho em meia hora (CSV)", meia.to_csv(index=False).encode("utf-8"),
                           "despacho_semanal.csv", "text/csv", key="semana_csv")


@st.cache_data(show_spinner=False)
def arvore_quadro(meses):
    caso = deepcopy(quadro)
    ampliar_horizonte(caso, meses)
    arv = construir_arvore(caso["aberturas"])
    _, sol = resolver_arvore(caso, arv, cortes_da_continuacao(caso))
    return dados_arvore(caso, arv, sol, 1.)


@st.cache_data(show_spinner=False)
def base_arvore(fonte, mes_inicial):
    """Caso-base da árvore: lido ao vivo pelo PySDDP ou o caso fixo do Colab."""
    return caso_pysddp(mes_inicial) if fonte == "pysddp" else deepcopy(disciplina)


def termica_padrao(d, fonte="colab"):
    """Potência máxima e CVU por padrão. Com dados do PySDDP valem os do deck DESSEM; no caso do Colab,
    as duas UTEs do estudo mensal mantêm os dados desse estudo."""
    if fonte == "pysddp":
        return float(d["Pmax"]), float(d["cvu"])
    referencia = {322: 0, 106: 1}.get(d["codigo"]) if d["ug"] == 1 else None
    if referencia is not None:
        return float(disciplina["gtmax"][referencia]), float(disciplina["cvu"][referencia])
    return float(d["Pmax"]), float(d["cvu"])


def restaurar_arvore():
    for chave in [k for k in st.session_state if k.startswith("arvore_p_")]:
        del st.session_state[chave]


def parametros_arvore(usinas, base, fonte="colab"):
    """Controles laterais do PL em árvore. Retorna os parâmetros em estruturas imutáveis, para o cache."""
    # A fonte entra na chave: trocar de fonte recarrega os padrões daquela fonte.
    chave = lambda nome: f"arvore_p_{fonte}_{nome}"
    padroes = {"carga": 250., "cdef": 4000., "afl": 100.}
    for i in range(2):
        util = float(base["vmax"][i] - base["vmin"][i])
        padroes.update({f"vi{i}": round(100 * float(base["vi"][i] - base["vmin"][i]) / util, 1),
                        f"vmin{i}": float(base["vmin"][i]), f"vmax{i}": float(base["vmax"][i]),
                        f"qmax{i}": round(float(base["qmax"][i]) / fator, 2),
                        f"prod{i}": round(float(base["prod"][i]) * fator, 6)})
    for nome, d in usinas.items():
        padroes[f"pmax_{nome}"], padroes[f"cvu_{nome}"] = termica_padrao(d, fonte)
    for k, v in padroes.items():
        st.session_state.setdefault(chave(k), v)
    with st.sidebar.expander("Parâmetros do estudo"):
        st.caption("Sistema")
        carga = st.number_input("Carga mensal (MW médios)", min_value=0., step=10., key=chave("carga"))
        cdef = st.number_input("Custo do déficit (R$/MWh)", min_value=0., step=100., key=chave("cdef"))
        afl = st.number_input("Escala das afluências (%)", min_value=1., step=5., key=chave("afl"),
                              help="Multiplica todas as aberturas de afluência da árvore.")
        uhes = []
        for i, nome in enumerate(disciplina["nomes"]):
            st.caption(nome)
            vmax = st.number_input("Volume máximo (hm³)", min_value=1., step=10., key=chave(f"vmax{i}"))
            if st.session_state[chave(f"vmin{i}")] > vmax:
                st.session_state[chave(f"vmin{i}")] = vmax
            vmin = st.number_input("Volume mínimo (hm³)", min_value=0., max_value=vmax, step=10., key=chave(f"vmin{i}"))
            vi = st.slider("Volume inicial (% do útil)", 0., 100., step=0.5, key=chave(f"vi{i}"))
            qmax = st.number_input("Engolimento (m³/s)", min_value=0., step=5., key=chave(f"qmax{i}"))
            prod = st.number_input("Produtibilidade (MW/(m³/s))", min_value=0., step=0.01, format="%.4f", key=chave(f"prod{i}"))
            uhes.append((vmin, vmax, vi, qmax, prod))
        termicas = []
        for nome, d in usinas.items():
            st.caption(nome)
            pmax = st.number_input("Potência máxima (MW)", min_value=0., step=1., key=chave(f"pmax_{nome}"))
            cvu = st.number_input("CVU (R$/MWh)", min_value=0., step=1., key=chave(f"cvu_{nome}"))
            termicas.append((nome, pmax, cvu))
        st.button("Restaurar parâmetros", key="arvore_restaurar", on_click=restaurar_arvore, width="stretch")
    return dict(carga=carga, cdef=cdef, afl=afl, uhes=tuple(uhes), termicas=tuple(termicas))


@st.cache_data(max_entries=24, show_spinner="Resolvendo o PL em árvore no SCIP…")
def resolver_pl(usinas, meses, parametros, fonte="colab", mes_inicial=9):
    custo, caso, arv, resultado = estudo_arvore(list(usinas), meses, parametros, base_arvore(fonte, mes_inicial))
    nomes = list(usinas)
    linhas = []
    for no, b in resultado.items():
        linhas.append({"Nó": rotulo(no), "Mês": len(no), "Probabilidade": arv[no]["prob"],
                       **dict(zip(caso["nomes"], caso["prod"] * b["q"])),
                       **dict(zip(nomes, b["g"])), "Déficit": b["d"], "Custo imediato (R$)": b["ci"],
                       "Custo futuro (R$)": b["alpha"],
                       **{f"Volume {n} (hm³)": v for n,v in zip(caso["nomes"],b["v"])}})
    cadastro = pd.DataFrame({"Unidade": nomes, "Máx. (MW)": caso["gtmax"], "CVU (R$/MWh)": caso["cvu"]})
    return custo, pd.DataFrame(linhas), cadastro, dados_arvore(caso, arv, resultado, fator), caso["nomes"]


def arvore():
    st.header("PL Único em árvore de cenários")
    formulacao_arvore()
    meses = st.sidebar.slider("Horizonte da árvore (meses)", 3, 8, 3, key="arvore_meses")
    st.caption(f"{meses} meses · {2**meses-1} nós · {2**(meses-1)} trajetórias finais")
    if meses > 3:
        st.caption("Nos meses adicionais, cada nó repete a carga e as duas aberturas de afluência do mês 3, com 50% de probabilidade por ramo. Os cortes passam às folhas do novo horizonte.")
    fonte = st.sidebar.radio("Dados das usinas", ["pysddp", "colab"], key="arvore_fonte",
                             format_func=lambda f: "PySDDP ao vivo (HIDR.DAT, VAZOES.DAT, DESSEM)" if f == "pysddp"
                             else "Caso da disciplina (Colab)")
    mes_inicial = 9
    if fonte == "pysddp":
        mes_inicial = st.sidebar.selectbox("Mês inicial", range(1, 13), 8, key="arvore_mes",
                                           format_func=lambda m: dp.MESES[m - 1])
        st.caption("Dados ao vivo: cadastro de Batalha e Serra do Facão do HIDR.DAT e aberturas do VAZOES.DAT (mês 1 = média "
                   "histórica; depois, média dos anos secos e dos úmidos de cada mês, 50% cada). Térmicas do deck DESSEM.")
    usinas = selecionar("arvore", [322, 106])
    base = base_arvore(fonte, mes_inicial)
    parametros = parametros_arvore(usinas, base, fonte)
    try:
        custo, df, cadastro, raiz, nomes_uhe = resolver_pl(usinas, meses, parametros, fonte, mes_inicial)
    except RuntimeError as exc:
        st.warning(f"O PL ficou inviável ou não convergiu com estes parâmetros ({exc}). Confira volumes, engolimento e carga.")
        return
    st.dataframe(cadastro, hide_index=True)
    if fonte == "pysddp":
        st.caption("Potência e CVU de todas as térmicas vêm do cadastro DESSEM lido pelo PySDDP. Todos os valores podem ser alterados em Parâmetros do estudo.")
    else:
        st.caption("Baliza UG 1 e Candeias UG 1 partem da potência e do CVU do estudo mensal do Colab. As demais unidades partem do cadastro DESSEM lido pelo PySDDP. Todos os valores podem ser alterados em Parâmetros do estudo.")
    st.metric("Custo esperado (R$)", f"{custo:,.2f}")
    st.subheader("Árvores de cenários")
    caso_real, caso_quadro = st.tabs(["Batalha e Serra do Facão", "Cenário Base"])
    with caso_real:
        st.caption("Em cada nó, os valores aparecem na ordem Batalha / Serra do Facão. AFL é a afluência local em m³/s e VF é o volume final em hm³. As folhas aparecem em laranja, com rótulo próprio. Arraste ou use o zoom para explorar.")
        mostrar_arvore(raiz, meses, "arv_real")
        with st.expander("Folhas da árvore (trajetórias finais)"):
            st.dataframe(pd.DataFrame(tabela_folhas(raiz)), hide_index=True)
    with caso_quadro:
        st.caption("Caso didático do Colab com uma UHE e duas térmicas de referência. AFL é dada em hm³ por estágio e VF em hm³. Os seletores de térmicas se aplicam ao caso Batalha e Serra do Facão.")
        mostrar_arvore(arvore_quadro(meses), meses, "arv_quadro")
    fontes = [*disciplina["nomes"], *usinas, "Déficit"]
    st.subheader("Atendimento à carga por mês (valor esperado dos nós)")
    # Em cada mês as probabilidades dos nós somam 1: a média ponderada é o valor esperado daquele mês.
    # Com aberturas equiprováveis, coincide com a média simples dos nós do mês.
    colunas = [*fontes, "Custo imediato (R$)", "Custo futuro (R$)", *[c for c in df.columns if c.startswith("Volume ")]]
    por_mes = (df[colunas].mul(df["Probabilidade"], axis=0).groupby(df["Mês"]).sum()
               .div(df.groupby("Mês")["Probabilidade"].sum(), axis=0).reset_index())
    por_mes["Mês"] = [f"Mês {m}" for m in por_mes["Mês"]]
    despacho(por_mes, "Mês", fontes, "arvore_ger_mes")
    st.dataframe(por_mes, hide_index=True)
    st.subheader("Atendimento à carga por nó")
    despacho(df, "Nó", fontes, "arvore_ger")
    st.dataframe(df, hide_index=True)


