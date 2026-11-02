from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from pl_model import pl_unico_det, sistema_colab

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def test_pl_reproduz_colab_e_balanços():
    s = sistema_colab()
    r = pl_unico_det(s, 1)
    assert r['custo_total'] == pytest.approx(22138227.67668162, abs=.1)
    np.testing.assert_allclose(r['objetivo_solver'], r['custo_total'], atol=.01)
    anterior = np.array([u['VI'] for u in s['UHE']])
    for t, row in enumerate(r['trajetoria']):
        np.testing.assert_allclose(row['VI'], anterior, atol=1e-6)
        np.testing.assert_allclose(row['vf'], row['VI'] + row['AFL'] - row['vt'] - row['vv'] +
                                   np.array([0., row['vt'][0] + row['vv'][0]]), atol=1e-6)
        geracao = sum(u['Prod']*row['vt'][i] for i, u in enumerate(s['UHE'])) + sum(row['gt']) + row['def']
        assert geracao == pytest.approx(s['DGer']['Carga'][t], abs=1e-6)
        anterior = row['vf']


def test_pl_carga_variavel_e_graficos():
    novo_pl()  # Registra o componente ECharts no runtime Streamlit.
    import pl_charts as charts
    s = sistema_colab()
    s['DGer']['Carga'] = [0., 300., 180.]
    r = pl_unico_det(s, 0)
    assert r['trajetoria'][1]['def'] > 30
    assert charts.pl_generation(s, r)['series'][-1]['data'] == [0., 300., 180.]
    assert len(charts.pl_storage(s, r)['series'][0]['data']) == 4
    assert len(charts.pl_costs(s, r)['series'][0]['data']) == 3


def novo_pl():
    app = AppTest.from_file(APP, default_timeout=180)
    app.session_state['metodo'] = 'PL Único'
    return app.run()


def test_aba_pl_independente_sem_executar_pde():
    app = novo_pl()
    assert not app.exception
    assert len(app.metric) == 4
    assert app.session_state['pl_solution']['custo_total'] == pytest.approx(22138227.67668162, abs=.1)
    assert 'solution' not in app.session_state
    assert 'parameters' not in app.session_state
    assert not any(x.key == 'input_nr_disc' for x in app.number_input)


def test_troca_metodos_preserva_entradas_e_reset_isolado():
    app = AppTest.from_file(APP, default_timeout=180)
    app.session_state['input_nr_disc'] = 2
    app.session_state['input_n_meses'] = 3
    app.run()
    app.number_input(key='input_carga').set_value(175.).run()
    assert not app.exception
    app.session_state['metodo'] = 'PL Único'
    app.run()
    assert not app.exception
    app.number_input(key='pl_input_carga').set_value(300.).run()
    assert not app.exception
    custo_pl = app.session_state['pl_solution']['custo_total']
    app.session_state['metodo'] = 'PDE Didática'
    app.run()
    assert not app.exception
    assert app.number_input(key='input_carga').value == 175
    assert app.session_state['parameters'].carga == 175
    app.session_state['metodo'] = 'PL Único'
    app.run()
    assert not app.exception
    assert app.number_input(key='pl_input_carga').value == 300
    assert app.session_state['pl_solution']['custo_total'] == custo_pl
    app.button(key='pl_reset').click().run()
    assert not app.exception
    assert app.number_input(key='pl_input_carga').value == 250
    assert app.session_state['parameters'].carga == 175


def test_pl_manual_nao_exibe_resultados_antigos():
    app = novo_pl()
    app.toggle(key='pl_input_auto').set_value(False).run()
    app.number_input(key='pl_input_carga').set_value(200.).run()
    assert not app.exception
    assert len(app.metric) == 0
    assert any('Entradas alteradas' in x.value for x in app.info)
    app.button(key='pl_resolve').click().run()
    assert not app.exception
    assert len(app.metric) == 4
    assert '200.0' in app.session_state['pl_parameters']


def test_pl_mensal_horizonte_e_modos_preservados():
    app = novo_pl()
    app.radio(key='pl_input_load_mode').set_value('Por mês').run()
    editor = 'pl_editor_monthly_3_8_Por mês_False'
    app.session_state[editor] = {'edited_rows': {0: {'Carga (MW médios)': 180., 'Batalha · AFL (m³/s)': 100.}},
                                 'added_rows': [], 'deleted_rows': []}
    app.run()
    assert not app.exception
    app.number_input(key='pl_input_n').set_value(1).run()
    app.number_input(key='pl_input_n').set_value(3).run()
    assert not app.exception
    assert app.session_state['pl_saved_monthly'][0] == [100., 24., 180.]
    app.radio(key='pl_input_load_mode').set_value('Constante').run()
    app.radio(key='pl_input_load_mode').set_value('Por mês').run()
    assert not app.exception
    assert app.session_state['pl_saved_monthly'][0][2] == 180.


def test_pl_perfil_anual_e_afluencias_constantes():
    app = novo_pl()
    app.number_input(key='pl_input_carga').set_value(300.).run()
    app.radio(key='pl_input_load_mode').set_value('Por mês').run()
    app.selectbox(key='pl_input_profile').set_value('Anual (janeiro a dezembro)').run()
    assert not app.exception
    assert app.number_input(key='pl_input_carga').value == 250.
    assert app.radio(key='pl_input_load_mode').value == 'Constante'
    assert len(app.session_state['pl_solution']['trajetoria']) == 12
    assert max(r['def'] for r in app.session_state['pl_solution']['trajetoria']) < 1e-5
    import json
    s = json.loads(app.session_state['pl_parameters'])
    assert s['DGer']['Meses'][0] == 'Janeiro' and s['DGer']['Meses'][-1] == 'Dezembro'
    app.number_input(key='pl_input_afl_b').set_value(0.).run()
    app.number_input(key='pl_input_afl_s').set_value(0.).run()
    assert not app.exception
    assert sum(r['def'] for r in app.session_state['pl_solution']['trajetoria']) > 0
    app.radio(key='pl_input_load_mode').set_value('Por mês').run()
    app.selectbox(key='pl_input_profile').set_value('Exemplo do Colab (3 meses)').run()
    assert not app.exception
    assert app.selectbox(key='pl_input_inicio').value == 'Setembro'
    assert app.number_input(key='pl_input_carga').value == 250.
    assert app.radio(key='pl_input_load_mode').value == 'Constante'
    assert app.session_state['pl_monthly_seed']['Mês'].tolist() == ['Setembro', 'Outubro', 'Novembro']
    assert app.session_state['pl_solution']['custo_total'] == pytest.approx(22138227.67668162, abs=.1)


def test_pl_validacao_sem_metricas():
    app = novo_pl()
    app.radio(key='pl_input_load_mode').set_value('Por mês').run()
    editor = 'pl_editor_monthly_3_8_Por mês_False'
    app.session_state[editor] = {'edited_rows': {0: {'Carga (MW médios)': -1.}}, 'added_rows': [], 'deleted_rows': []}
    app.run()
    assert not app.exception
    assert app.error and len(app.metric) == 0
