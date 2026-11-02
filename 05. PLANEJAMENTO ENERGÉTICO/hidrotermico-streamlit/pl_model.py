"""PL Único determinístico: mesma formulação e funções do notebook da disciplina."""
from copy import deepcopy
from time import perf_counter

import numpy as np
import pandas as pd
from pyscipopt import Model, quicksum, SCIP_PARAMSETTING

escala_det = 1_000_000.0


def validar_sistema_det(sistema, cenario):
    geral, uhes, utes = sistema['DGer'], sistema['UHE'], sistema['UTE']
    n = len(geral['Meses'])
    carga = np.asarray(geral['Carga'], dtype=float)
    if n < 1 or carga.shape != (n,) or not np.all(np.isfinite(carga)) or np.any(carga < 0):
        raise ValueError('Informe um mês e uma carga finita não negativa por estágio.')
    if not uhes or not np.isfinite(geral['CDef']) or geral['CDef'] < 0:
        raise ValueError('Informe UHEs e custo de déficit não negativo.')
    if not np.isfinite(geral['Horas']) or geral['Horas'] <= 0:
        raise ValueError('A duração de cada estágio deve ser positiva.')
    if isinstance(cenario, (int, np.integer)) and not isinstance(cenario, bool):
        cenarios = [int(cenario)] * n
    else:
        try:
            cenarios = list(cenario)
        except TypeError as exc:
            raise ValueError('Escolha um cenário inteiro ou uma sequência por mês.') from exc
    if len(cenarios) != n or any(type(c) not in (int, np.int64, np.int32) or c < 0 for c in cenarios):
        raise ValueError('Informe um índice de cenário inteiro não negativo por estágio.')
    for i, u in enumerate(uhes):
        valores = [u[k] for k in ('Vmin', 'Vmax', 'VI', 'Prod', 'Engol')]
        if not np.all(np.isfinite(valores)) or not (0 <= u['Vmin'] < u['Vmax']) or not (u['Vmin'] <= u['VI'] <= u['Vmax']):
            raise ValueError(f"Volumes inválidos em {u['Nome']}.")
        if u['Prod'] < 0 or u['Engol'] < 0 or (u.get('Potencia') is not None and (not np.isfinite(u['Potencia']) or u['Potencia'] < 0)):
            raise ValueError('Produtibilidade, engolimento e potência devem ser não negativos.')
        jusante = u.get('Jusante')
        if jusante is not None and (type(jusante) is not int or not i < jusante < len(uhes)):
            raise ValueError('Ordene as UHEs de montante para jusante, sem ciclos.')
        if len(u['Afl']) != n:
            raise ValueError('Informe afluências locais para todos os estágios.')
        for t, c in enumerate(cenarios):
            vazoes = np.asarray(u['Afl'][t], dtype=float)
            if vazoes.ndim != 1 or c >= len(vazoes) or not np.all(np.isfinite(vazoes)) or np.any(vazoes < 0):
                raise ValueError('Afluência ou cenário inválido.')
    for u in utes:
        if not np.all(np.isfinite([u['Capac'], u['Custo']])) or min(u['Capac'], u['Custo']) < 0:
            raise ValueError('Capacidade e custo térmico devem ser não negativos.')
    return np.array([[u['Afl'][t][c] for u in uhes] for t, c in enumerate(cenarios)])


def empacotar_det(sistema, metodo, trajetoria, segundos, **extras):
    return {'metodo': metodo, 'trajetoria': trajetoria,
            'custo_total': float(sum(r['ci'] for r in trajetoria)),
            'segundos': segundos, **extras}


def tabela_det(sistema, resultado):
    linhas = []
    for r in resultado['trajetoria']:
        linha = {'Mês': sistema['DGer']['Meses'][r['t']],
                 'Carga (MWm)': sistema['DGer']['Carga'][r['t']]}
        for i, u in enumerate(sistema['UHE']):
            linha[f"{u['Nome']} (MWm)"] = u['Prod'] * r['vt'][i]
            linha[f"VF {u['Nome']} (hm³)"] = r['vf'][i]
        for i, u in enumerate(sistema['UTE']):
            linha[f"{u['Nome']} (MWm)"] = r['gt'][i]
        linha.update({'Déficit (MWm)': r['def'], 'Custo imediato (R$)': r['ci']})
        linhas.append(linha)
    return pd.DataFrame(linhas)


def criar_modelo_det(nome, duais=False):
    modelo = Model(nome)
    modelo.hideOutput()
    modelo.setRealParam('numerics/dualfeastol', 1e-9)
    modelo.setRealParam('numerics/feastol', 1e-9)
    if duais:
        # Recomendação do PySCIPOpt para consultar duais do PL original.
        modelo.setPresolve(SCIP_PARAMSETTING.OFF)
        modelo.setHeuristics(SCIP_PARAMSETTING.OFF)
        modelo.disablePropagation()
        modelo.setBoolParam('lp/alwaysgetduals', True)
    return modelo


def limite_turbinado_det(uhe):
    limite = uhe['Engol']
    if uhe.get('Potencia') is not None and uhe['Prod'] > 0:
        limite = min(limite, uhe['Potencia'] / uhe['Prod'])
    return float(limite)


def pl_unico_det(sistema, cenario=1):
    inicio = perf_counter()
    afluencias = validar_sistema_det(sistema, cenario)
    geral, uhes, utes = sistema['DGer'], sistema['UHE'], sistema['UTE']
    n = len(geral['Meses'])
    modelo = criar_modelo_det('PL Único')
    try:
        vf = [[modelo.addVar(f'VF_{i}_{t}', lb=u['Vmin'], ub=u['Vmax']) for t in range(n)] for i, u in enumerate(uhes)]
        vt = [[modelo.addVar(f'VT_{i}_{t}', lb=0, ub=limite_turbinado_det(u)) for t in range(n)] for i, u in enumerate(uhes)]
        vv = [[modelo.addVar(f'VV_{i}_{t}', lb=0) for t in range(n)] for i in range(len(uhes))]
        gt = [[modelo.addVar(f'GT_{j}_{t}', lb=0, ub=u['Capac']) for t in range(n)] for j, u in enumerate(utes)]
        deficit = [modelo.addVar(f'DEF_{t}', lb=0) for t in range(n)]
        custos = []
        for t in range(n):
            for i, u in enumerate(uhes):
                vi = float(u['VI']) if t == 0 else vf[i][t - 1]
                recebimento = quicksum(vt[j][t] + vv[j][t] for j, montante in enumerate(uhes) if montante.get('Jusante') == i)
                modelo.addCons(vf[i][t] + vt[i][t] + vv[i][t] - recebimento == vi + float(afluencias[t, i]))
            modelo.addCons(quicksum(u['Prod'] * vt[i][t] for i, u in enumerate(uhes)) +
                           quicksum(g[t] for g in gt) + deficit[t] == float(geral['Carga'][t]))
            custos.append(quicksum(u['Custo'] * gt[j][t] for j, u in enumerate(utes)) +
                          geral['CDef'] * deficit[t] + 0.01 * quicksum(v[t] for v in vv))
        modelo.setObjective(quicksum(custos) / escala_det, sense='minimize')
        modelo.optimize()
        if modelo.getStatus() != 'optimal':
            raise RuntimeError(f'PL Único: {modelo.getStatus()}.')
        trajetoria = []
        for t in range(n):
            trajetoria.append({'t': t,
                'VI': np.array([u['VI'] if t == 0 else modelo.getVal(vf[i][t - 1]) for i, u in enumerate(uhes)]),
                'AFL': afluencias[t].copy(), 'vf': np.array([modelo.getVal(v[t]) for v in vf]),
                'vt': np.array([modelo.getVal(v[t]) for v in vt]), 'vv': np.array([modelo.getVal(v[t]) for v in vv]),
                'gt': np.array([modelo.getVal(g[t]) for g in gt]), 'def': modelo.getVal(deficit[t]),
                'ci': modelo.getVal(custos[t])})
        return empacotar_det(sistema, 'PL Único', trajetoria, perf_counter() - inicio,
                            objetivo_solver=modelo.getObjVal() * escala_det)
    finally:
        modelo.freeProb()

SISTEMA_COLAB = {'DGer': {'Meses': ['Setembro', 'Outubro', 'Novembro'],
          'Carga': [250.0, 250.0, 250.0],
          'Horas': 720,
          'CDef': 2880000.0,
          'Nr_Disc': 5},
 'UHE': [{'Nome': 'Batalha',
          'Vmin': 430.049988,
          'Vmax': 1781.609985,
          'VI': 966.619306809,
          'Prod': 0.12708815586419753,
          'Engol': 381.07584,
          'Potencia': None,
          'Jusante': 1,
          'Afl': [[77.76, 51.84], [90.72, 64.8], [103.68, 77.76]]},
         {'Nome': 'Serra do Facão',
          'Vmin': 1752.0,
          'Vmax': 5199.0,
          'VI': 3482.3940000000002,
          'Prod': 0.23753858024691357,
          'Engol': 811.296,
          'Potencia': 212.58,
          'Jusante': None,
          'Afl': [[181.44, 62.208], [241.056, 75.168], [456.192, 51.84]]}],
 'UTE': [{'Nome': 'BBF Baliza', 'Capac': 10.0, 'Custo': 635587.2},
         {'Nome': 'ERB Candeias', 'Capac': 17.0, 'Custo': 85629.6}]}


def sistema_colab():
    return deepcopy(SISTEMA_COLAB)
