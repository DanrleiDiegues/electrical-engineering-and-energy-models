"""PL Único determinístico (aba "PL Único"): monta o sistema, resolve e formata o resultado."""
import numpy as np

from pl_model import pl_unico_det, sistema_colab, validar_sistema_det

CALENDARIO = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
              'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
M3S_PARA_HM3 = 2.592   # 720 h × 3600 s / 1e6: converte m³/s médios do mês em hm³


def gerar_meses(n, inicio):
    return [CALENDARIO[(inicio + t) % 12] if n <= 12 else
            f'{CALENDARIO[(inicio + t) % 12]} · ciclo {1 + (inicio + t) // 12}' for t in range(n)]


def padroes(perfil='colab'):
    """Valores iniciais de cada perfil, os mesmos que o app Streamlit usa."""
    base = sistema_colab()
    anual = perfil == 'anual'
    n = 12 if anual else 3
    return {
        'perfil': perfil, 'n': n, 'inicio': 0 if anual else 8,
        'afl_b': [220.] * n if anual else [20., 25., 30.],
        'afl_s': [350.] * n if anual else [24., 29., 20.],
        'carga': [250.] * n, 'vi': [39.7, 50.2], 'cdef': 4000., 'potencia_serra': 212.58,
        'uhes': [{'nome': u['Nome'], 'vmin': u['Vmin'], 'vmax': u['Vmax'],
                  'engol': u['Engol'] / M3S_PARA_HM3, 'prod': u['Prod'] * M3S_PARA_HM3} for u in base['UHE']],
        'termicas': [{'nome': u['Nome'], 'capac': u['Capac'], 'custo': u['Custo'] / 720} for u in base['UTE']],
    }


def montar_sistema(p):
    """Traduz o pedido (unidades de tela: m³/s, R$/MWh) para o dicionário do notebook (hm³, R$/mês)."""
    n = len(p['carga'])
    if not (len(p['afl_b']) == len(p['afl_s']) == n >= 1):
        raise ValueError('Carga e afluências precisam ter o mesmo número de meses.')
    sistema = sistema_colab()
    sistema['DGer'].update(Meses=gerar_meses(n, p['inicio']), Carga=[float(c) for c in p['carga']], CDef=p['cdef'] * 720)
    for i, (u, d) in enumerate(zip(sistema['UHE'], p['uhes'])):
        afl = p['afl_b'] if i == 0 else p['afl_s']
        u.update(Vmin=d['vmin'], Vmax=d['vmax'], Engol=d['engol'] * M3S_PARA_HM3, Prod=d['prod'] / M3S_PARA_HM3,
                 Afl=[[float(v) * M3S_PARA_HM3] for v in afl])
        u['VI'] = d['vmin'] + p['vi'][i] / 100 * (d['vmax'] - d['vmin'])
    sistema['UHE'][1]['Potencia'] = p['potencia_serra']
    for u, d in zip(sistema['UTE'], p['termicas']):
        u.update(Capac=d['capac'], Custo=d['custo'] * 720)
    validar_sistema_det(sistema, 0)
    return sistema


def calcular(pedido):
    sistema = montar_sistema(pedido)
    r = pl_unico_det(sistema, cenario=0)
    uhes, utes, traj = sistema['UHE'], sistema['UTE'], r['trajetoria']
    linhas = [{'mes': sistema['DGer']['Meses'][x['t']], 'carga': sistema['DGer']['Carga'][x['t']],
               'uhe': [u['Prod'] * x['vt'][i] for i, u in enumerate(uhes)], 'ute': x['gt'].tolist(),
               'deficit': max(0., x['def']), 'vi': x['VI'].tolist(), 'vf': x['vf'].tolist(),
               'vt': x['vt'].tolist(), 'vv': x['vv'].tolist(), 'afl': (x['AFL'] / M3S_PARA_HM3).tolist(), 'ci': x['ci']}
              for x in traj]
    pct = lambda v, u: 100 * (v - u['Vmin']) / (u['Vmax'] - u['Vmin'])
    return {
        'meses': sistema['DGer']['Meses'], 'nomes_uhe': [u['Nome'] for u in uhes], 'nomes_ute': [u['Nome'] for u in utes],
        'resumo': {'custo_total': r['custo_total'], 'deficit_mwh': sum(x['deficit'] for x in linhas) * 720,
                   'termica_mwh': sum(sum(x['ute']) for x in linhas) * 720, 'segundos': r['segundos']},
        'linhas': linhas,
        'armazenamento': [[pct(u['VI'], u)] + [pct(x['vf'][i], u) for x in traj] for i, u in enumerate(uhes)],
    }
