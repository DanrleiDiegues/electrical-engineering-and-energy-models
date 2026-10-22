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


def test_invalid_monthly_load_shows_validation_without_results():
    app = AppTest.from_file(APP, default_timeout=180)
    app.session_state["input_nr_disc"] = 2
    app.session_state["input_load_mode"] = "Por mês"
    app.run()
    app.session_state["input_load_editor_12"] = {"edited_rows": {0: {"Carga (MW médios)": -1}}, "added_rows": [], "deleted_rows": []}
    app.run()
    assert not app.exception
    assert app.error and len(app.metric) == 0


def test_horizon_resize_preserves_inputs_and_updates_graph_data():
    import charts
    app = AppTest.from_file(APP, default_timeout=180)
    app.session_state["input_nr_disc"] = 2
    app.run()
    assert not app.exception
    assert any(x.value == "Simulador - Planejamento Energético" for x in app.title)
    assert app.session_state["parameters"].n_meses == 12
    app.radio(key="input_afl_mode").set_value("Mês a mês").run()
    app.selectbox(key="input_afl_month_12").set_value(8).run()
    app.slider(key="input_afl_month_b_8").set_value((30.0,260.0)).run()
    app.selectbox(key="input_trajectory_mode").set_value("Personalizada").run()
    app.selectbox(key="input_traj_8").set_value(1).run()
    assert app.session_state["parameters"].afl_max[8][0] == 260
    app.number_input(key="input_n_meses").set_value(2).run()
    assert not app.exception
    assert len(app.session_state["solution"]["planejada"]) == 2
    app.number_input(key="input_n_meses").set_value(15).run()
    assert not app.exception
    p = app.session_state["parameters"]
    assert p.n_meses == 15 and p.afl_max[8][0] == 260 and p.trajetoria[8] == 1
    planned = app.session_state["solution"]["planejada"]
    isolated = app.session_state["solution"]["isolada"]
    for options in (charts.generation(p, planned), charts.costs(p, planned, isolated)):
        assert len(options["xAxis"]["data"]) == 15
        assert all(len(series["data"]) == 15 for series in options["series"])
    assert len(charts.storage(p, planned, isolated, 0)["series"][0]["data"]) == 16
    app.selectbox(key="view_month_15").set_value(14).run()
    app.number_input(key="input_n_meses").set_value(1).run()
    assert not app.exception
    assert len(app.session_state["solution"]["planejada"]) == 1



def test_sidebar_ranges_trajectory_shortcuts_and_monthly_load():
    import charts
    app = AppTest.from_file(APP, default_timeout=180)
    app.session_state["input_nr_disc"] = 2
    app.run()
    assert not app.exception
    p = app.session_state["parameters"]
    assert p.meses[0] == "Janeiro" and p.meses[-1] == "Dezembro"
    assert p.afl_max[0] == (220,350) and p.trajetoria == (0,)*12
    assert max(x["def"] for x in app.session_state["solution"]["planejada"]) < 1e-5
    app.slider(key="input_afl_uniform_b").set_value((40.0,270.0)).run()
    app.slider(key="input_afl_uniform_s").set_value((60.0,420.0)).run()
    assert not app.exception
    p = app.session_state["parameters"]
    assert p.afl_max == ((270,420),)*12 and p.afl_min == ((40,60),)*12
    app.selectbox(key="input_trajectory_mode").set_value("Todas mínimas").run()
    assert app.session_state["parameters"].trajetoria == (1,)*12
    app.radio(key="input_load_mode").set_value("Por mês").run()
    app.session_state["input_load_editor_12"] = {"edited_rows": {0: {"Carga (MW médios)": 180}, 1: {"Carga (MW médios)": 300}, 2: {"Carga (MW médios)": 0}}, "added_rows": [], "deleted_rows": []}
    app.run()
    assert not app.exception
    p = app.session_state["parameters"]
    assert p.cargas_mensais[:3] == (180,300,0)
    series = charts.generation(p,app.session_state["solution"]["planejada"])["series"][-1]
    assert series["data"][:3] == [180,300,0]
    app.number_input(key="input_n_meses").set_value(2).run()
    app.number_input(key="input_n_meses").set_value(15).run()
    assert not app.exception
    assert app.session_state["parameters"].cargas_mensais[:3] == (180,300,0)
    app.radio(key="input_load_mode").set_value("Constante").run()
    assert app.session_state["parameters"].cargas_mensais is None
    app.radio(key="input_load_mode").set_value("Por mês").run()
    assert not app.exception
    assert app.session_state["parameters"].cargas_mensais[:3] == (180,300,0)
