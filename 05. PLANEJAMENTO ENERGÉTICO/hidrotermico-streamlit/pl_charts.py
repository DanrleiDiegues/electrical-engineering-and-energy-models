"""Gráficos Apache ECharts do PL Único, separados da PDE Didática."""
import numpy as np

from charts import base


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
