"""A API deve devolver os mesmos números que os módulos de modelagem e o app Streamlit."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.main import app
from modelo_semana import demanda_semana, despachar_semana
from api import servicos

cliente = TestClient(app)
CANDEIAS, BALIZA = "ERB CANDEIAS · UG 1", "BBF BALIZA · UG 1"


def test_catalogo():
    r = cliente.get("/catalogo")
    assert r.status_code == 200
    nomes = [u["nome"] for u in r.json()]
    assert len(nomes) == 5 and CANDEIAS in nomes


def test_semana_igual_ao_modelo():
    escolhas = [{"nome": CANDEIAS}, {"nome": BALIZA}]
    r = cliente.post("/semana", json={"unidades": escolhas, "hora_impacto": 20})
    assert r.status_code == 200
    d = r.json()
    direto = despachar_semana(servicos.montar_unidades(escolhas), demanda_semana, True)
    assert d["resumo"]["custo_total"] == pytest.approx(direto["total"])
    assert len(d["meia_hora"]["cmo"]) == 336
    assert d["impacto"]["previsto"] == pytest.approx(502.713, abs=0.01)
    assert d["merito"]["tabela"][0]["Fonte"] == CANDEIAS


def test_semana_com_ajuste_e_sem_custo_futuro():
    base = cliente.post("/semana", json={"unidades": [{"nome": CANDEIAS}]}).json()
    caro = cliente.post("/semana", json={"unidades": [{"nome": CANDEIAS, "ajustes": {"cvu": 900}}],
                                         "custo_futuro": False}).json()
    assert caro["unidades"][CANDEIAS]["cvu"] == 900
    assert caro["resumo"]["custo_futuro"] == 0 and base["resumo"]["custo_futuro"] > 0


def test_entrada_invalida():
    assert cliente.post("/semana", json={"unidades": [{"nome": "NAO EXISTE"}]}).status_code == 422
    assert cliente.post("/arvore", json={"meses": 9}).status_code == 422


def test_arvore_igual_ao_streamlit():
    d = cliente.post("/arvore", json={"meses": 3}).json()
    assert d["custo_esperado"] == pytest.approx(211218080.69, abs=0.01)   # valor do app Streamlit
    assert len(d["nos"]) == 7 and sum(n["folha"] for n in d["nos"]) == 4
    d8 = cliente.post("/arvore", json={"meses": 8, "carga": 300}).json()
    assert len(d8["nos"]) == 255 and sum(n["folha"] for n in d8["nos"]) == 128
