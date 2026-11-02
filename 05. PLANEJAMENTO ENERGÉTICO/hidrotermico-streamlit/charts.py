"""Opções Apache ECharts; gráficos não participam da interpolação do solver."""
import numpy as np
from streamlit_echarts import JsCode

COLORS = ["#176B87", "#49B3B1", "#D69B35", "#8B6A53", "#CB5360"]


def base():
    return {
        "color": COLORS, "animationDuration": 350,
        "textStyle": {"fontFamily": "sans-serif", "color": "#374956"},
        "tooltip": {"trigger": "axis", "confine": True,
                    "valueFormatter": JsCode("v => Number(v).toLocaleString('pt-BR', {maximumFractionDigits: 2})")},
        "legend": {"top": 0, "type": "scroll"},
        "grid": {"top": 65, "left": 65, "right": 25, "bottom": 50, "containLabel": True},
        "toolbox": {"right": 0, "bottom": 0, "feature": {"saveAsImage": {"title": "Salvar imagem", "pixelRatio": 2}}},
    }


def pl_generation(sistema, resultado):
    o = base()
    nomes = [u['Nome'] for u in sistema['UHE']] + [u['Nome'] for u in sistema['UTE']] + ['Déficit']
    rows = [[u['Prod']*r['vt'][i] for i, u in enumerate(sistema['UHE'])] +
            r['gt'].tolist() + [max(0., r['def'])] for r in resultado['trajetoria']]
    o.update({'xAxis': {'type': 'category', 'data': sistema['DGer']['Meses']},
              'yAxis': {'type': 'value', 'name': 'MW médios', 'min': 0,
                        'max': max(1., max(sistema['DGer']['Carga'])*1.15)},
              'series': [{'name': nome, 'type': 'bar', 'stack': 'geracao',
                          'data': [float(row[i]) for row in rows]} for i, nome in enumerate(nomes)]})
    o['series'].append({'name': 'Carga', 'type': 'line', 'symbol': 'none',
                        'data': sistema['DGer']['Carga'], 'lineStyle': {'type': 'dashed', 'color': '#344454'}})
    return o


def pl_storage(sistema, resultado):
    o = base()
    o.update({'xAxis': {'type': 'category', 'data': ['Inicial', *sistema['DGer']['Meses']]},
              'yAxis': {'type': 'value', 'name': 'Volume útil (%)', 'min': 0, 'max': 100}, 'series': []})
    for i, u in enumerate(sistema['UHE']):
        volumes = np.array([u['VI']] + [r['vf'][i] for r in resultado['trajetoria']])
        o['series'].append({'name': u['Nome'], 'type': 'line', 'symbolSize': 7,
                            'data': (100*(volumes-u['Vmin'])/(u['Vmax']-u['Vmin'])).tolist()})
    return o


def pl_costs(sistema, resultado):
    o = base()
    o.update({'xAxis': {'type': 'category', 'data': sistema['DGer']['Meses']},
              'yAxis': {'type': 'value', 'name': 'Custo imediato (R$ milhões)', 'min': 0},
              'series': [{'name': 'PL Único', 'type': 'bar',
                          'data': [r['ci']/1e6 for r in resultado['trajetoria']]}]})
    return o


def generation(p, trajectory):
    o = base()
    names = ["Batalha", "Serra do Facão", "BBF Baliza", "ERB Candeias", "Déficit"]
    rows = [[p.ro[0]*r["vt"][0], p.ro[1]*r["vt"][1], r["gt1"], r["gt2"], max(0, r["def"])] for r in trajectory]
    o.update({"xAxis": {"type": "category", "data": list(p.meses)},
              "yAxis": {"type": "value", "name": "MW médios", "min": 0, "max": max(float(p.cargas.max())*1.15, 1)},
              "series": [{"name": name, "type": "bar", "stack": "geracao", "barMaxWidth": 74,
                          "data": [float(r[i]) for r in rows],
                          "label": {"show": p.n_meses <= 6, "position": "inside", "color": "#fff",
                                    "formatter": JsCode("p => p.value > 0.05 ? p.value.toLocaleString('pt-BR', {maximumFractionDigits: 1}) : ''")}}
                         for i, name in enumerate(names)]})
    if p.n_meses > 6:
        o["xAxis"]["axisLabel"] = {"formatter": JsCode("v => v.slice(0, 3) + (v.includes('ciclo') ? '/' + v.split(' ').pop() : '')")}
    o["series"].append({"name": "Carga", "type": "line", "symbol": "none", "data": p.cargas.tolist(),
                        "lineStyle": {"color": "#344454", "type": "dashed", "width": 1.5}, "itemStyle": {"color": "#344454"}})
    return o


def storage(p, planned, isolated, i):
    o = base()
    o.update({"xAxis": {"type": "category", "data": ["Inicial", *p.meses], "boundaryGap": False},
              "yAxis": {"type": "value", "name": "Volume útil (%)", "min": 0, "max": 100}, "series": []})
    for traj, name, style in ((planned, "Com custo futuro", "solid"), (isolated, "Isolados", "dashed")):
        v = np.array([p.vi[i]] + [r["vf"][i] for r in traj])
        o["series"].append({"name": name, "type": "line", "symbolSize": 8,
                            "lineStyle": {"type": style, "width": 3},
                            "data": (100*(v-p.vmin[i])/(p.vmax[i]-p.vmin[i])).tolist()})
    return o


def costs(p, planned, isolated):
    o = base()
    o.update({"xAxis": {"type": "category", "data": list(p.meses)},
              "yAxis": {"type": "value", "name": "Custo imediato (R$ milhões)"},
              "series": [{"name": name, "type": "bar", "barMaxWidth": 60,
                          "data": [r["ci"]/1e6 for r in traj]}
                         for name, traj in (("Com custo futuro", planned), ("Isolados", isolated))]})
    return o


def future_cost(p, curve, surface=False):
    levels = np.linspace(0, 100, p.nr_disc)
    z = curve.reshape(p.nr_disc, p.nr_disc)/1e6
    visual = {"min": float(z.min()), "max": float(z.max()) if z.max() > z.min() else float(z.min()+1),
              "calculable": True, "orient": "horizontal", "left": "center", "bottom": 0,
              "text": ["Maior custo", "Menor custo"], "inRange": {"color": ["#E3F4F1", "#5CBDB5", "#237D98", "#183A63"]}}
    if surface:
        return {"tooltip": {"confine": True}, "visualMap": {**visual, "dimension": 2},
                "xAxis3D": {"type": "value", "name": "Batalha (% útil)", "min": 0, "max": 100},
                "yAxis3D": {"type": "value", "name": "Serra (% útil)", "min": 0, "max": 100},
                "zAxis3D": {"type": "value", "name": "R$ milhões"},
                "grid3D": {"boxWidth": 100, "boxDepth": 100, "viewControl": {"projection": "perspective"}},
                "series": [{"type": "surface", "shading": "color", "wireframe": {"show": False},
                            "data": [[float(x), float(y), float(z[i, j])] for i, x in enumerate(levels) for j, y in enumerate(levels)]}]}
    labels = [f"{v:.1f}" for v in levels]
    return {"tooltip": {"position": "top", "confine": True,
                        "formatter": JsCode("p => 'Batalha: ' + p.name + '% útil<br>Serra: ' + p.data[3] + '% útil<br>R$ ' + p.data[2].toLocaleString('pt-BR', {maximumFractionDigits: 3}) + ' milhões'")},
            "grid": {"top": 25, "left": 90, "right": 35, "bottom": 115},
            "xAxis": {"type": "category", "data": labels, "name": "VI Batalha (% útil)", "nameLocation": "middle", "nameGap": 35},
            "yAxis": {"type": "category", "data": labels, "name": "VI Serra (% útil)", "nameLocation": "middle", "nameGap": 60},
            "visualMap": {**visual, "dimension": 2},
            "series": [{"type": "heatmap", "data": [[i, j, float(z[i, j]), labels[j]] for i in range(p.nr_disc) for j in range(p.nr_disc)],
                        "emphasis": {"itemStyle": {"borderColor": "#172B3A", "borderWidth": 1}}}]}
