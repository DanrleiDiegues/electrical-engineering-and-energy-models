"""PDDE (1dtoy, Batalha, cascata), dados do COBRE e as abas novas do app."""
from pathlib import Path

import numpy as np
from streamlit.testing.v1 import AppTest

import cobre_dados as cd
import pdde_model as pm

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_pdde_uma_abertura_igual_ao_pl():
    # Com uma abertura por estágio a PDDE vira PDDD: Zinf tem de igualar o ótimo exato (PL da trajetória).
    caso = pm.caso_1dtoy()
    ab = [np.array([[40.]])] * 4
    r = pm.pdde(caso, ab, n_forward=1, max_iter=6)
    assert abs(r["historico"][-1]["zinf"] - pm.equivalente_deterministico(caso, ab)) < 1.


def test_pdde_1dtoy_converge_para_o_otimo_por_baixo():
    caso, ab = pm.caso_1dtoy(), cd.aberturas_cobre("professor")
    r = pm.pdde(caso, ab, n_forward=10, max_iter=15)
    otimo = pm.equivalente_deterministico(caso, ab)
    assert r["historico"][-1]["zinf"] <= otimo + 1.
    assert r["historico"][-1]["zinf"] >= .999 * otimo


def test_dados_cobre_pareados():
    p = cd.comparacao_pareada(cd.teste_cobre("original"), cd.carregar_nosso("original")["teste"])
    assert p["n"] == 2000 and abs(p["dif"]) < 100.
    assert np.allclose(cd.cenarios_teste()[:, :, 0], cd.teste_cobre("professor").inflow_m3s.to_numpy().reshape(2000, 4))


def test_batalha_um_uhe():
    caso = pm.caso_pysddp(("Batalha",), vi_pct=(5.,))
    ab, rot = pm.aberturas_historicas(caso, 4)
    r = pm.pdde(caso, ab, n_forward=2, max_iter=3)
    assert len(caso["uhes"]) == 1 and len(rot[0]) == 4 and r["historico"][-1]["zinf"] > 0


def _abrir(aba):
    app = AppTest.from_file(APP, default_timeout=300)
    app.session_state["metodo"] = aba
    app.run()
    assert not app.exception, app.exception
    return app


def test_abas_novas_abrem():
    _abrir("Benders na árvore")
    app = _abrir("COBRE × PDDE (1dtoy)")
    assert any("Zinf COBRE" in m.label for m in app.metric)
    app = _abrir("PDDE")
    app.button(key="pdde_rodar").click().run()
    assert not app.exception, app.exception


def test_toy_da_documentacao():
    # Página toy-single-reservoir do novomodelo: ótimo 17000/27 e corte do estágio 3 θ ≥ 500 − 100/3·v.
    caso, ab = pm.caso_toy_documentacao(), pm.aberturas_toy()
    assert abs(pm.equivalente_deterministico(caso, ab) - 17000 / 27) < 1e-6
    r = pm.pdde(caso, ab, n_forward=1, max_iter=1, sequencias=[[1, 1, 1, 1]])
    pi, b = r["cortes"][2][0]
    assert abs(b - 500) < 1e-6 and abs(pi[0] + 100 / 3) < 1e-6
    assert abs(pm.pdde(caso, ab, n_forward=1, max_iter=20)["historico"][-1]["zinf"] - 17000 / 27) < 1e-4


def test_passo_a_passo_registra_o_mesmo_algoritmo():
    # O registro não altera o resultado e tem forward, backward e limites em cada iteração.
    caso, ab = pm.caso_toy_documentacao(), pm.aberturas_toy()
    reg = []
    r1 = pm.pdde(caso, ab, n_forward=1, max_iter=3, registro=reg)
    r2 = pm.pdde(caso, ab, n_forward=1, max_iter=3)
    assert r1["historico"][-1]["zinf"] == r2["historico"][-1]["zinf"]
    assert [e["tipo"] for e in reg[:8]] == ["forward"] * 4 + ["backward"] * 3 + ["limites"]
