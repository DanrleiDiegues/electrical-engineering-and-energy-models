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


def test_pl_unico_igual_ao_modelo():
    from pl_model import pl_unico_det, sistema_colab
    padroes = cliente.get("/pl/padroes").json()
    r = cliente.post("/pl", json=padroes)
    assert r.status_code == 200
    d = r.json()
    colab = sistema_colab()
    colab["UHE"][1]["Potencia"] = 212.58      # potência nominal de Serra; cenário 1 = afluências mínimas do Colab (20, 25, 30 e 24, 29, 20 m³/s)
    assert d["resumo"]["custo_total"] == pytest.approx(pl_unico_det(colab, 1)["custo_total"], rel=1e-6)
    assert d["meses"] == ["Setembro", "Outubro", "Novembro"] and len(d["armazenamento"][0]) == 4
    padroes["carga"] = [250.] * 2
    assert cliente.post("/pl", json=padroes).status_code == 422     # meses incoerentes
    anual = cliente.get("/pl/padroes", params={"perfil": "anual"}).json()
    assert len(cliente.post("/pl", json=anual).json()["linhas"]) == 12


def _aguarda(tarefa):
    import time
    for _ in range(300):
        t = cliente.get(f"/pde/{tarefa}").json()
        if t["estado"] in ("pronto", "erro"):
            return t
        time.sleep(0.1)
    raise AssertionError("PDE não terminou")


def test_pde_igual_ao_modelo():
    from model import Parameters, planejamento, avaliar
    pedido = cliente.get("/pde/padroes", params={"n_meses": 2}).json()
    pedido["nr_disc"] = 4
    t = _aguarda(cliente.post("/pde", json=pedido).json()["id"])
    assert t["estado"] == "pronto", t["erro"]
    d = t["resultado"]
    p = Parameters(n_meses=2, nr_disc=4)
    _, estados, curvas = planejamento(p.policy_parameters())
    direto = avaliar(p, estados, curvas)
    assert d["resumo"]["custo_planejado"] == pytest.approx(sum(x["ci"] for x in direto["planejada"]), rel=1e-6)
    assert len(d["futuro"]) == 2 and len(d["futuro"][0]) == 4 and len(d["armazenamento"]["planejada"][0]) == 3


def test_pde_entrada_invalida():
    pedido = cliente.get("/pde/padroes", params={"n_meses": 2}).json()
    pedido["nr_disc"] = 3
    pedido["trajetoria"] = [0]            # tamanho errado
    assert cliente.post("/pde", json=pedido).status_code == 422
    assert cliente.get("/pde/naoexiste").status_code == 404
