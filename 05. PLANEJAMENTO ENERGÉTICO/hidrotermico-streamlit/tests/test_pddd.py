import pytest

from modelo_arvore import cortes_da_continuacao, estudo_arvore
from pddd_model import caso_de_sistema, pddd
from pddd_passos import gerar_passos
from pl_model import pl_unico_det, sistema_colab


def test_pddd_igual_ao_pl_unico_registrado():
    r = pddd(caso_de_sistema(sistema_colab(), 1))
    assert r["convergiu"] and r["zsup"] == pytest.approx(pl_unico_det(sistema_colab(), 1)["custo_total"], abs=1.)
    assert r["zsup"] == pytest.approx(22138227.68, abs=1.)


def test_pddd_passo_a_passo_reproduz_o_slide():
    passos = gerar_passos()
    f1 = [p["tabela"][p["estagio"]] for p in passos if p["iteracao"] == 1 and p["fase"] == "forward"]
    assert [round(r["vf"], 2) for r in f1] == [35.37, 20.0, 20.0]
    assert [round(r["imediato"], 2) for r in f1] == [0.0, 208.75, 5775.0]
    ultimo = passos[-1]
    assert ultimo["fase"] == "convergiu"
    assert ultimo["historico"][-1]["zinf"] == pytest.approx(652.5, abs=.01)
    assert ultimo["historico"][-1]["zsup"] == pytest.approx(652.5, abs=.01)
