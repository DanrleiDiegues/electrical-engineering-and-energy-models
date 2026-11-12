"""PDE Didática: política por programação dinâmica na grade de volumes (aba "PDE Didática").

O cálculo é longo (milhares de despachos no SCIP), então roda em segundo plano:
`iniciar` devolve um número de tarefa e `consultar` informa o andamento e, no fim, o resultado.
"""
import threading
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from time import perf_counter

import numpy as np

from model import UHES, Parameters, avaliar, planejamento, tabela_resultados

_executor = ThreadPoolExecutor(max_workers=1)   # uma política por vez
_tarefas = OrderedDict()
_politicas = OrderedDict()                      # reaproveita a política quando só a trajetória ou o volume inicial mudam
_trava = threading.Lock()


def padroes(n_meses=12):
    p = Parameters(n_meses=n_meses)
    return {
        'n_meses': n_meses, 'carga': p.carga, 'nr_disc': 24, 'inicial': list(p.inicial), 'trajetoria': list(p.trajetoria),
        'afl_max': [list(a) for a in p.afl_max], 'afl_min': [list(a) for a in p.afl_min],
        'uhes': [{'nome': UHES[i], 'vmin': p.vmin[i], 'vmax': p.vmax[i], 'engolimento': p.engolimento[i],
                  'produtividade': p.produtividade[i]} for i in range(2)],
        'termicas': [{'nome': n, 'gtmax': p.gtmax[i], 'custo': p.custo_termico[i]} for i, n in enumerate(['BBF Baliza', 'ERB Candeias'])],
        'custo_deficit': p.custo_deficit, 'potencia_serra': p.potencia_serra, 'meses': list(p.meses),
    }


def montar_parametros(d):
    """Pedido de tela -> Parameters do modelo (a mesma validação do app Streamlit)."""
    n = d['n_meses']
    cargas = d.get('cargas_mensais')
    p = Parameters(
        n_meses=n, carga=float(d['carga']), cargas_mensais=tuple(map(float, cargas)) if cargas else None,
        nr_disc=int(d['nr_disc']), inicial=tuple(d['inicial']), trajetoria=tuple(int(t) for t in d['trajetoria']),
        vmin=tuple(u['vmin'] for u in d['uhes']), vmax=tuple(u['vmax'] for u in d['uhes']),
        engolimento=tuple(u['engolimento'] for u in d['uhes']), produtividade=tuple(u['produtividade'] for u in d['uhes']),
        gtmax=tuple(t['gtmax'] for t in d['termicas']), custo_termico=tuple(t['custo'] for t in d['termicas']),
        custo_deficit=d['custo_deficit'], potencia_serra=d['potencia_serra'],
        afl_max=tuple(map(tuple, d['afl_max'])), afl_min=tuple(map(tuple, d['afl_min'])))
    p.validate()
    return p


def iniciar(pedido):
    p = montar_parametros(pedido)          # erros de validação aparecem já aqui (ValueError)
    tarefa = {'id': uuid.uuid4().hex[:12], 'estado': 'fila', 'feito': 0, 'total': p.n_meses * p.nr_disc ** 2 * 2,
              'mes': '', 'resultado': None, 'erro': None}
    with _trava:
        _tarefas[tarefa['id']] = tarefa
        while len(_tarefas) > 8:
            _tarefas.popitem(last=False)
    _executor.submit(_executar, tarefa, p)
    return tarefa['id']


def consultar(tarefa_id):
    t = _tarefas.get(tarefa_id)
    if t is None:
        return None
    return {k: t[k] for k in ('id', 'estado', 'feito', 'total', 'mes', 'resultado', 'erro')}


def _executar(t, p):
    try:
        inicio = perf_counter()
        t['estado'] = 'calculando'
        chave = p.policy_parameters()
        if chave not in _politicas:
            def progresso(feito, total, mes):
                t['feito'], t['mes'] = feito, mes
            _politicas[chave] = planejamento(chave, progresso)
            while len(_politicas) > 4:
                _politicas.popitem(last=False)
        grades, estados, curvas = _politicas[chave]
        t['mes'] = 'simulando trajetórias'
        t['resultado'] = formatar(p, avaliar(p, estados, curvas), estados, curvas, perf_counter() - inicio)
        t['feito'], t['estado'] = t['total'], 'pronto'
    except Exception as exc:   # o erro vai para a tela, não derruba a API
        t['estado'], t['erro'] = 'erro', str(exc)


def _linhas(p, trajetoria):
    tabela = tabela_resultados(p, trajetoria)
    return tabela.to_dict(orient='records')


def formatar(p, r, estados, curvas, segundos):
    planejada, isolada = r['planejada'], r['isolada']
    cp, ci = sum(x['ci'] for x in planejada), sum(x['ci'] for x in isolada)
    capacidade = p.produtividade[0] * p.engolimento[0] + min(p.produtividade[1] * p.engolimento[1], p.potencia_serra) + sum(p.gtmax)
    pct = lambda traj, i: [100 * (v - p.vmin[i]) / (p.vmax[i] - p.vmin[i]) for v in [p.vi[i]] + [x['vf'][i] for x in traj]]
    n = p.nr_disc
    return {
        'meses': list(p.meses), 'carga': p.cargas.tolist(), 'nomes_uhe': list(UHES), 'nr_disc': n,
        'resumo': {'esperado_inicial': sum(r['custos_iniciais']) / 2, 'custo_planejado': cp, 'custo_isolado': ci,
                   'deficit_mwh': sum(x['def'] for x in planejada) * 720, 'meses_com_deficit': sum(x['def'] > 1e-5 for x in planejada),
                   'capacidade': capacidade, 'meses_acima_capacidade': int(np.sum(p.cargas > capacidade + 1e-6)), 'segundos': segundos},
        'custos_iniciais': [c / 1e6 for c in r['custos_iniciais']],
        'planejada': _linhas(p, planejada), 'isolada': _linhas(p, isolada),
        'armazenamento': {'planejada': [pct(planejada, i) for i in range(2)], 'isolada': [pct(isolada, i) for i in range(2)]},
        'niveis': np.linspace(0, 100, n).tolist(),
        # custo futuro desde cada mês, em R$ milhões: matriz [Batalha][Serra] com n × n pontos
        'futuro': [(np.asarray(c) / 1e6).reshape(n, n).tolist() for c in curvas[:p.n_meses]],
        'parametros': p.to_dict(),
    }
