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


def dados_arvore(caso, arv, sol, conversao):
    nos = {}
    for n, r in arv.items():
        afl = " / ".join(f"{v/conversao:g}" for v in r["afl"])
        vf = " / ".join(f"{v:.1f}" for v in sol[n]["v"])
        nos[n] = {"name": rotulo(n), "mes":len(n), "prob":f"{100*r['prob']:g}%",
                  "afl":afl, "vf":vf, "children":[]}
        if r["pai"] is not None:
            nos[r["pai"]]["children"].append(nos[n])
    return next(iter(nos.values()))


def mostrar_arvore(raiz, meses, chave):
    folhas = 2**(meses-1)
    op = {"tooltip":{"trigger":"item","formatter":JsCode("p => 'Mês ' + p.data.mes + ' · ' + p.data.name + '<br>Probabilidade: ' + p.data.prob + '<br>AFL: ' + p.data.afl + '<br>Volume final: ' + p.data.vf + ' hm³'")},
          "series":[{"type":"tree","data":[raiz],"orient":"LR","left":65,"right":65,"top":20,"bottom":20,
                     "initialTreeDepth":-1,"expandAndCollapse":False,"roam":True,"symbolSize":6,
                     "edgeShape":"polyline","lineStyle":{"color":"#839AA1"},
                     "label":{"position":"inside","fontSize":10,"backgroundColor":"#F2F7F8","borderRadius":4,
                              "padding":[3,4],"formatter":JsCode("p => p.data.name+' · '+p.data.prob+'\\nAFL '+p.data.afl+'\\nVF '+p.data.vf")}}]}
    st_echarts(op, height=f"{max(290,folhas*62)}px", key=chave)

