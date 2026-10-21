from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_app_recalculates_and_never_shows_stale_results():
    app = AppTest.from_file(APP, default_timeout=180)
    app.session_state["input_nr_disc"] = 3
    app.run()
    assert not app.exception
    assert len(app.metric) == 4
    initial = app.session_state["solution"]["custos_iniciais"][0]
    app.number_input(key="input_carga").set_value(300).run()
    assert not app.exception
    assert app.session_state["parameters"].carga == 300
    assert app.session_state["solution"]["custos_iniciais"][0] > initial
    app.toggle(key="input_auto").set_value(False).run()
    app.number_input(key="input_carga").set_value(150).run()
    assert len(app.metric) == 0
    assert any("Entradas alteradas" in x.value for x in app.info)
    next(b for b in app.button if b.label == "Recalcular agora").click().run()
    assert not app.exception
    assert app.session_state["parameters"].carga == 150
    assert len(app.metric) == 4
    app.number_input(key="input_inicial_0").set_value(80).run()
    next(b for b in app.button if b.label == "Recalcular agora").click().run()
    assert not app.exception
    assert app.session_state["parameters"].inicial[0] == 80


def test_invalid_inflow_shows_validation_without_results():
    app = AppTest.from_file(APP, default_timeout=180)
    app.session_state["input_nr_disc"] = 2
    app.run()
    app.session_state["input_afl"] = {"edited_rows": {0: {"Batalha · mínimo": 999}}, "added_rows": [], "deleted_rows": []}
    app.run()
    assert not app.exception
    assert app.error
    assert len(app.metric) == 0
