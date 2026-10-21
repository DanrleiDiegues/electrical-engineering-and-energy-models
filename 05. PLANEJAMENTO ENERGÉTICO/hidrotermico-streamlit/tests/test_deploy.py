from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_cloud_root_entrypoint_loads_real_app():
    repo = Path(__file__).resolve().parents[3]
    app = AppTest.from_file(str(repo / "streamlit_app.py"), default_timeout=120)
    app.session_state["input_nr_disc"] = 2
    app.run()
    assert not app.exception
    assert len(app.metric) == 4
    assert app.session_state["parameters"].n_meses == 12
    assert len(app.session_state["solution"]["planejada"]) == 12
    assert any(x.value == "Simulador - Planejamento Energético" for x in app.title)
