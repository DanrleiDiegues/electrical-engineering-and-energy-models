import numpy as np
from streamlit_echarts import JsCode, st_echarts
import streamlit as st

from charts import base
from modelo_semana import HIDRO
from modelo_arvore import rotulo

VERMELHO = "#CF202D"


def despacho(df, eixo, fontes, chave, carga=None):
    semanal = carga is not None
    series = []
    for nome in fontes:
        serie = {"name": "Batalha" if nome == "UHE" else nome.capitalize() if nome.lower() == "déficit" else nome,
                 "type": "line" if semanal else "bar", "stack": "oferta", "data": df[nome].tolist()}
        if semanal:
            serie.update(step="end", symbol="none", areaStyle={"opacity": 0.9}, lineStyle={"width": 0})
        if nome.lower() == "déficit":
            serie["itemStyle"] = {"color": VERMELHO}
            serie["areaStyle"] = {"color": VERMELHO, "opacity": 1}
        series.append(serie)
    x = df[eixo].tolist()
    if semanal:
        series.append({"type": "line", "name": "Carga", "step": "end", "symbol": "none",
                       "itemStyle": {"color": "#263442"}, "lineStyle": {"width": 1.5}, "data": list(carga)})
        x.append(x[-1] + 0.5)
        for serie in series:
            serie["data"].append(serie["data"][-1])
    op = base()
    op.update(xAxis={"type": "category", "data": x, "boundaryGap": not semanal},
              yAxis={"type": "value", "name": "MW"}, series=series)
    st_echarts(op, height="380px", key=chave)


def graficos_semana(r, usinas):
    df, estados = r["meia"], r["estados"]
    st.subheader("Atendimento à carga")
    despacho(df, "hora", ["UHE", *usinas, "déficit"], "uct_ger", df.carga)
    st.subheader("Estado horário das térmicas")
    nomes = list(usinas)
    horas = sorted(estados.hora.unique().tolist())
    valores = [[int(row.hora), nomes.index(row.unidade), int(row.ligada)] for row in estados.itertuples()]
    op = base()
    op.update(grid={"left": 10, "right": 28, "top": 20, "bottom": 80, "containLabel": True},
              tooltip={"position":"top","formatter": JsCode("p => p.data[3] + ' · hora ' + p.data[0] + ' · ' + (p.data[2] ? 'Ligada' : 'Desligada')")},
              visualMap={"type": "piecewise", "dimension": 2, "orient": "horizontal", "bottom": 8,
                         "left": "center", "pieces": [{"value": 0, "label": "OFF · desligada", "color": "#DEE3E7"},
                                                      {"value": 1, "label": "ON · ligada", "color": "#167579"}]},
              xAxis={"type": "category", "data": horas, "name": "Hora", "nameLocation":"middle", "nameGap":25},
              yAxis={"type": "category", "data": nomes},
              series=[{"type": "heatmap", "data": [v+[nomes[v[1]]] for v in valores]}])
    st_echarts(op, height="225px", key="uct_on_off")
    st.subheader("Volume armazenado em Batalha")
    op = base()
    pontos = [[0, HIDRO["VI"]], *[[h+0.5, v] for h,v in zip(df.hora, df.volume)]]
    op.update(xAxis={"type": "value", "name": "Hora", "interval": 24, "max": 168},
              yAxis={"type": "value", "name": "hm³", "scale": True},
              series=[{"type":"line", "name":"Volume", "showSymbol":False, "data":pontos}])
    st_echarts(op, height="310px", key="uct_vol")


def grafico_carga(base_mw, ajustada_mw, capacidade, chave):
    """Perfil horário da carga da semana, com a capacidade instalada como referência."""
    fim = len(base_mw)
    pontos = lambda v: [[h, float(x)] for h, x in enumerate(v)] + [[fim, float(v[-1])]]
    ajustada = not np.allclose(base_mw, ajustada_mw)
    series = [{"name": "Carga ajustada" if ajustada else "Carga base", "type": "line", "step": "end",
               "symbol": "none", "data": pontos(ajustada_mw), "itemStyle": {"color": "#176B87"},
               "lineStyle": {"width": 2}, "areaStyle": {"opacity": 0.18},
               "markLine": {"symbol": "none", "silent": True, "lineStyle": {"color": VERMELHO, "type": "dashed"},
                            "label": {"formatter": f"Capacidade instalada · {capacidade:,.1f} MW", "position": "insideEndTop"},
                            "data": [{"yAxis": float(capacidade)}]}}]
    if ajustada:
        series.insert(0, {"name": "Carga base", "type": "line", "step": "end", "symbol": "none",
                          "data": pontos(base_mw), "itemStyle": {"color": "#839AA1"},
                          "lineStyle": {"width": 1.5, "type": "dashed"}})
    op = base()
    op.update(xAxis={"type": "value", "name": "Hora", "interval": 24, "min": 0, "max": fim},
              yAxis={"type": "value", "name": "MW", "min": 0, "max": float(max(capacidade, max(ajustada_mw), max(base_mw)) * 1.12)},
              series=series)
    st_echarts(op, height="300px", key=chave)


def _degrau(meia, coluna):
    """Pontos [hora, valor] de uma grandeza constante em cada meia hora, com o último degrau fechado."""
    pontos = [[float(h), float(v)] for h, v in zip(meia.hora, meia[coluna])]
    pontos.append([float(meia.hora.iloc[-1]) + 0.5, pontos[-1][1]])
    return pontos


def grafico_cmo(meia, chave):
    """CMO a cada meia hora e média de cada dia, em R$/MWh."""
    dia = (meia.hora // 24).astype(int)
    media = meia.assign(media_dia=meia.groupby(dia)["cmo"].transform("mean"))
    series = [{"name": "CMO a cada meia hora", "type": "line", "step": "end", "symbol": "none",
               "data": _degrau(meia, "cmo"), "lineStyle": {"width": 1.6}, "areaStyle": {"opacity": 0.12}},
              {"name": "Média do dia", "type": "line", "step": "end", "symbol": "none",
               "data": _degrau(media, "media_dia"), "itemStyle": {"color": "#D69B35"},
               "lineStyle": {"width": 2.2, "type": "dashed"}}]
    op = base()
    op.update(xAxis={"type": "value", "name": "Hora da semana", "interval": 24, "min": 0, "max": 168},
              yAxis={"type": "value", "name": "R$/MWh", "min": 0}, series=series)
    st_echarts(op, height="330px", key=chave)


def grafico_cma(meia, mwh_por_hm3, chave):
    """CMA a cada meia hora em R$/hm³, com o equivalente em R$/MWh no eixo da direita."""
    maximo = max(float(meia.cma.max()) * 1.15, 1.)
    op = base()
    op.update(xAxis={"type": "value", "name": "Hora da semana", "interval": 24, "min": 0, "max": 168},
              yAxis=[{"type": "value", "name": "R$/hm³", "min": 0, "max": maximo},
                     {"type": "value", "name": "R$/MWh equivalente", "min": 0, "max": maximo / mwh_por_hm3,
                      "splitLine": {"show": False}}],
              series=[{"name": "CMA", "type": "line", "step": "end", "symbol": "none", "data": _degrau(meia, "cma"),
                       "itemStyle": {"color": "#176B87"}, "lineStyle": {"width": 2}, "areaStyle": {"opacity": 0.12}}])
    st_echarts(op, height="300px", key=chave)


def grafico_custos(fontes, chave):
    """Custo de cada fonte em R$/MWh, da mais barata para a mais cara. `fontes`: lista de (nome, custo, cor)."""
    fontes = sorted(fontes, key=lambda f: f[1])
    op = base()
    op.update(grid={"top": 20, "left": 10, "right": 40, "bottom": 40, "containLabel": True},
              legend={"show": False}, tooltip={"trigger": "item"},
              xAxis={"type": "value", "name": "R$/MWh"},
              yAxis={"type": "category", "data": [f[0] for f in fontes], "inverse": True},
              series=[{"type": "bar", "barMaxWidth": 34,
                       "data": [{"value": float(c), "itemStyle": {"color": cor}} for _, c, cor in fontes],
                       "label": {"show": True, "position": "right",
                                 "formatter": JsCode("p => p.value.toLocaleString('pt-BR', {maximumFractionDigits: 2})")}}])
    st_echarts(op, height=f"{max(150, 56 * len(fontes) + 60)}px", key=chave)


def grafico_volumes(casos, chave):
    """Volume de Batalha ao longo da semana para um ou mais casos. `casos`: lista de (nome, resultado)."""
    series = []
    for nome, r in casos:
        pontos = [[0, HIDRO["VI"]], *[[h + 0.5, v] for h, v in zip(r["meia"].hora, r["meia"].volume)]]
        series.append({"name": nome, "type": "line", "showSymbol": False, "data": pontos})
    op = base()
    op.update(xAxis={"type": "value", "name": "Hora", "interval": 24, "max": 168},
              yAxis={"type": "value", "name": "hm³", "scale": True}, series=series)
    st_echarts(op, height="300px", key=chave)


def dados_arvore(caso, arv, sol, conversao):
    nos = {}
    for n, r in arv.items():
        afl = " / ".join(f"{v/conversao:g}" for v in r["afl"])
        vf = " / ".join(f"{v:.1f}" for v in sol[n]["v"])
        nos[n] = {"name": rotulo(n), "mes":len(n), "prob":f"{100*r['prob']:g}%",
                  "afl":afl, "vf":vf, "children":[]}
        if r["pai"] is not None:
            nos[r["pai"]]["children"].append(nos[n])
    for no in nos.values():
        if not no["children"]:
            no["folha"] = True
            no["symbolSize"] = 16
            no["itemStyle"] = {"color": "#C2410C", "borderColor": "#FFFFFF", "borderWidth": 2}
            no["label"] = {"position": "right", "distance": 10, "fontSize": 12, "fontWeight": "bold", "color": "#7C2D12",
                           "backgroundColor": "#FFEDD5", "borderColor": "#FDBA74", "borderWidth": 1, "borderRadius": 4,
                           "padding": [3, 6], "formatter": f"{no['name']} · {no['prob']}\nVF {no['vf']}"}
    return next(iter(nos.values()))


def tabela_folhas(raiz):
    """Folhas da árvore: uma linha por trajetória final."""
    linhas, pilha = [], [raiz]
    while pilha:
        no = pilha.pop()
        if no.get("folha"):
            linhas.append({"Trajetória": no["name"], "Probabilidade": no["prob"],
                           "AFL no último mês": no["afl"], "Volume final": no["vf"]})
        pilha.extend(reversed(no["children"]))
    return linhas


def mostrar_arvore(raiz, meses, chave):
    folhas = 2**(meses-1)
    op = {"tooltip":{"trigger":"item","formatter":JsCode("p => 'Mês ' + p.data.mes + ' · ' + p.data.name + '<br>Probabilidade: ' + p.data.prob + '<br>AFL: ' + p.data.afl + '<br>Volume final: ' + p.data.vf + ' hm³'")},
          "series":[{"type":"tree","data":[raiz],"orient":"LR","left":50,"right":210,"top":20,"bottom":20,
                     "initialTreeDepth":-1,"expandAndCollapse":False,"roam":True,"symbolSize":8,"itemStyle":{"color":"#2F6F7E"},
                     "edgeShape":"polyline","lineStyle":{"color":"#839AA1"},
                     "label":{"position":"inside","fontSize":10,"backgroundColor":"#F2F7F8","borderRadius":4,
                              "padding":[3,4],"formatter":JsCode("p => p.data.name+' · '+p.data.prob+'\\nAFL '+p.data.afl+'\\nVF '+p.data.vf")}}]}
    st_echarts(op, height=f"{max(420, folhas*44)}px", key=chave)

