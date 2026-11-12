from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from modelo_semana import HIDRO, demanda_semana

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def nova_semana():
    app = AppTest.from_file(APP, default_timeout=300)
    app.session_state["metodo"] = "DESSEM semanal"
    return app.run()


def metricas(app):
    return {m.label: m.value for m in app.metric}


def chave(app, campo, posicao=0):
    return [x.key for x in app.number_input if x.key.endswith(f"_{campo}")][posicao]


def test_semana_mostra_carga_base_parametros_e_resultados():
    app = nova_semana()
    assert not app.exception
    m = metricas(app)
    assert m["Carga média (MW)"] == f"{demanda_semana.mean():.1f}"
    assert m["Pico (MW)"] == f"{demanda_semana.max():.1f}"
    assert m["Energia semanal (MWh)"] == f"{demanda_semana.sum():,.0f}"
    assert "Custo total (R$)" in m and "Déficit (MWh)" in m
    for campo in ("Pmin", "Pmax", "subida", "descida", "cvu", "partida"):
        assert len([x for x in app.number_input if x.key.endswith(f"_{campo}")]) == 2
    assert len([s for s in app.slider if s.key.endswith(("_Ton", "_Toff"))]) == 4
    assert app.dataframe[0].value["Alterado em relação ao cadastro"].tolist() == ["—", "—"]
    assert any("Carga base: média" in c.value for c in app.sidebar.caption)


def test_carga_ajustada_aparece_e_altera_o_resultado():
    app = nova_semana()
    custo = app.session_state["semana_resultado"]["total"]
    app.number_input(key="semana_carga").set_value(110).run()
    assert not app.exception
    m = metricas(app)
    assert m["Pico (MW)"] == f"{demanda_semana.max() * 1.1:.1f}"
    assert app.session_state["semana_resultado"]["total"] > custo


def test_parametro_alterado_e_marcado_e_restaurado():
    app = nova_semana()
    cvu = chave(app, "cvu")
    padrao = app.number_input(key=cvu).value
    custo = app.session_state["semana_resultado"]["total"]
    app.number_input(key=cvu).set_value(padrao + 100).run()
    assert not app.exception
    assert app.dataframe[0].value["Alterado em relação ao cadastro"].tolist()[0] == "CVU"
    assert app.session_state["semana_resultado"]["total"] != custo
    next(b for b in app.button if b.key.endswith("_restaurar")).click().run()
    assert app.number_input(key=cvu).value == padrao
    assert app.session_state["semana_resultado"]["total"] == pytest.approx(custo)
    assert app.dataframe[0].value["Alterado em relação ao cadastro"].tolist()[0] == "—"


def test_pmin_acompanha_pmax_e_pmax_respeita_trajetorias():
    app = nova_semana()
    pmin, pmax = chave(app, "Pmin"), chave(app, "Pmax")
    campo = app.number_input(key=pmax)
    assert campo.min >= 0.1
    app.number_input(key=pmax).set_value(campo.min).run()
    assert not app.exception
    assert app.number_input(key=pmin).value <= app.number_input(key=pmax).value


def test_recalculo_manual_nao_mostra_resultado_desatualizado():
    app = nova_semana()
    custo = app.session_state["semana_resultado"]["total"]
    app.toggle(key="semana_auto").set_value(False).run()
    cvu = chave(app, "cvu")
    app.number_input(key=cvu).set_value(app.number_input(key=cvu).value + 100).run()
    assert any("Entradas alteradas" in i.value for i in app.info)
    assert app.session_state["semana_resultado"]["total"] == custo
    next(b for b in app.button if b.key == "semana_calcular").click().run()
    assert not any("Entradas alteradas" in i.value for i in app.info)
    assert app.session_state["semana_resultado"]["total"] != custo


def test_grafico_da_carga_inclui_base_ajustada_e_capacidade():
    from graficos_trabalhos import grafico_carga
    import graficos_trabalhos as g
    capturado = {}
    g.st_echarts = lambda op, **kw: capturado.update(op=op, **kw)
    capacidade = 16.79 + 9.8 + HIDRO["rho"] * HIDRO["Qmax"]
    grafico_carga(demanda_semana, demanda_semana, capacidade, "k")
    assert [s["name"] for s in capturado["op"]["series"]] == ["Carga base"]
    grafico_carga(demanda_semana, demanda_semana * 1.2, capacidade, "k")
    series = capturado["op"]["series"]
    assert [s["name"] for s in series] == ["Carga base", "Carga ajustada"]
    assert all(len(s["data"]) == 169 for s in series)
    assert series[-1]["markLine"]["data"] == [{"yAxis": capacidade}]
    assert np.isclose(series[-1]["data"][0][1], demanda_semana[0] * 1.2)


def test_marginais_e_catalogo():
    from catalogo_dessem import diagnostico_catalogo
    app = nova_semana()
    assert not app.exception
    total, tabela = diagnostico_catalogo()
    assert total == 390 and int(tabela["Unidades"].iloc[0]) == 5
    assert "CMO médio (R$/MWh)" in metricas(app) and "CMA médio (R$/hm³)" in metricas(app)


def nova_arvore():
    app = AppTest.from_file(APP, default_timeout=600)
    app.session_state["metodo"] = "PL Único em árvore"
    return app.run()


def test_arvore_oito_meses_e_parametros():
    app = nova_arvore()
    assert not app.exception
    base = metricas(app)["Custo esperado (R$)"]
    app.slider(key="arvore_meses").set_value(8).run()
    assert not app.exception
    app.number_input(key="arvore_p_carga").set_value(300.).run()
    assert not app.exception
    assert metricas(app)["Custo esperado (R$)"] != base
