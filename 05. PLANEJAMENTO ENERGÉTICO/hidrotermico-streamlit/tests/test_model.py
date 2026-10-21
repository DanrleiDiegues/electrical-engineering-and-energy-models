"""Regressão independente contra as células auditadas do notebook original."""
import json
from dataclasses import replace
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pyscipopt import Model, quicksum

from model import FATOR_VOLUME, HORAS, Parameters, avaliar, despacho_hidrotermico, planejamento, simular


def original(p):
    nb = json.loads((Path(__file__).resolve().parents[1]/"reference"/"original.ipynb").read_text(encoding="utf-8"))
    scope = {"np": np, "pd": pd, "Model": Model, "quicksum": quicksum, "product": product}
    # Apenas parâmetros e funções do modelo; sem células de instalação ou gráficos.
    for index in (4, 6, 8, 10):
        exec(compile("".join(nb["cells"][index]["source"]), f"notebook_cell_{index}", "exec"), scope)
    scope.update(MESES=list(p.meses), CARGA=p.carga, NR_DISC=p.nr_disc, CENARIO_TRAJETORIA=list(p.trajetoria),
                 AFL_MAX=np.array(p.afl_max), AFL_MIN=np.array(p.afl_min), CENARIOS=p.cenarios,
                 VMIN=np.array(p.vmin), VMAX=np.array(p.vmax), VI_INICIAL=p.vi,
                 ro=p.ro, ENGOL=np.array(p.engolimento)*FATOR_VOLUME,
                 GTMAX1=p.gtmax[0], GTMAX2=p.gtmax[1], CT1=p.custo_termico[0]*HORAS,
                 CT2=p.custo_termico[1]*HORAS, CDEF=p.custo_deficit*HORAS)
    return scope


def test_default_parameters_match_original_cell():
    nb = json.loads((Path(__file__).resolve().parents[1]/"reference"/"original.ipynb").read_text(encoding="utf-8"))
    scope = {"np": np}
    exec("".join(nb["cells"][4]["source"]), scope)
    p = Parameters(n_meses=3)
    for actual, name in ((p.carga, "CARGA"), (p.nr_disc, "NR_DISC"), (p.vmin, "VMIN"),
                         (p.vmax, "VMAX"), (p.vi, "VI_INICIAL"), (p.ro, "ro"),
                         (np.array(p.engolimento)*FATOR_VOLUME, "ENGOL"), (p.afl_max, "AFL_MAX"),
                         (p.afl_min, "AFL_MIN"), (p.trajetoria, "CENARIO_TRAJETORIA"),
                         (p.gtmax[0], "GTMAX1"), (p.gtmax[1], "GTMAX2"),
                         (p.custo_termico[0]*HORAS, "CT1"), (p.custo_termico[1]*HORAS, "CT2"),
                         (p.custo_deficit*HORAS, "CDEF")):
        np.testing.assert_allclose(actual, scope[name], rtol=1e-14, atol=1e-12)


@pytest.mark.parametrize("p", [
    replace(Parameters(n_meses=3), nr_disc=4),
    replace(Parameters(n_meses=3), nr_disc=4, carga=190, inicial=(25, 70), trajetoria=(0, 1, 0),
            afl_max=((45, 80), (50, 110), (60, 190)), gtmax=(12, 20), custo_termico=(900, 150)),
    replace(Parameters(n_meses=3), nr_disc=3, carga=0),
    Parameters(n_meses=12, nr_disc=3),
    Parameters(n_meses=1, nr_disc=3),
])
def test_equivalence_to_notebook(p):
    compare_notebook(p)


def compare_notebook(p):
    ref = original(p)
    g0, e0, c0 = ref["planejamento"]()
    g, e, c = planejamento(p)
    np.testing.assert_allclose(e, e0)
    for expected, actual in zip(c0[:-1], c[:-1]):
        np.testing.assert_allclose(actual, expected, rtol=1e-8, atol=0.1)
    for future in (True, False):
        expected = ref["simular"](e0, c0, considerar_futuro=future)
        actual = simular(p, e, c, considerar_futuro=future)
        for a, b in zip(actual, expected):
            for key in ("fob", "ci", "alpha", "vf", "vt", "vv", "gt1", "gt2", "def"):
                np.testing.assert_allclose(a[key], b[key], rtol=1e-7, atol=1e-4, err_msg=key)


@pytest.mark.full
def test_original_24_level_grid():
    compare_notebook(Parameters(n_meses=3))


def test_all_eight_trajectories_obey_physical_constraints():
    base = replace(Parameters(n_meses=3), nr_disc=4)
    _, states, curves = planejamento(base)
    for trajectory in product((0, 1), repeat=3):
        p = replace(base, trajetoria=trajectory)
        r = avaliar(p, states, curves)
        for name in ("planejada", "isolada"):
            previous = p.vi
            for row in r[name]:
                np.testing.assert_allclose(row["VI"], previous, atol=1e-7)
                np.testing.assert_allclose(row["vf"][0], row["VI"][0]+row["AFL"][0]-row["vt"][0]-row["vv"][0], atol=1e-6)
                np.testing.assert_allclose(row["vf"][1], row["VI"][1]+row["AFL"][1]+row["vt"][0]+row["vv"][0]-row["vt"][1]-row["vv"][1], atol=1e-6)
                assert np.dot(p.ro, row["vt"])+row["gt1"]+row["gt2"]+row["def"] == pytest.approx(p.carga, abs=1e-6)
                assert np.all(row["vf"] >= np.array(p.vmin)-1e-6)
                assert np.all(row["vf"] <= np.array(p.vmax)+1e-6)
                assert np.all(row["vt"] >= -1e-6) and np.all(row["vv"] >= -1e-6)
                assert np.all(row["vt"] <= np.array(p.engolimento)*FATOR_VOLUME+1e-6)
                assert row["gt1"] <= p.gtmax[0]+1e-6 and row["gt2"] <= p.gtmax[1]+1e-6
                assert row["vt"][1]*p.ro[1] <= p.potencia_serra+1e-6
                assert row["fob"] == pytest.approx(row["ci"]+row["alpha"], abs=1e-4)
                previous = row["vf"]
            assert r[name][-1]["alpha"] == pytest.approx(0)


def test_editable_nominal_capacity_and_no_generation():
    p = replace(Parameters(n_meses=3), nr_disc=2, potencia_serra=1)
    r = despacho_hidrotermico(p, p.vi, p.cenarios[0][0])
    assert p.ro[1]*r["vt"][1] <= 1+1e-7
    p = replace(p, engolimento=(0, 0), gtmax=(0, 0))
    r = despacho_hidrotermico(p, p.vi, p.cenarios[0][0])
    assert r["def"] == pytest.approx(p.carga)


@pytest.mark.parametrize("change", [
    {"carga": float("nan")}, {"carga": -1}, {"nr_disc": 1}, {"nr_disc": 2.5},
    {"vmin": (1800, 1752)}, {"inicial": (101, 10)}, {"trajetoria": (2, 1, 1)},
    {"afl_min": ((31, 24), (25, 29), (30, 20))}, {"afl_max": ((1, 2),)},
    {"custo_termico": (-1, 5)}, {"produtividade": (float("inf"), 0.6)},
])
def test_invalid_inputs(change):
    with pytest.raises(ValueError):
        replace(Parameters(n_meses=3), **change).validate()


def test_parameters_roundtrip_and_policy_key():
    p = Parameters.from_dict(json.loads(json.dumps(Parameters(n_meses=3).to_dict())))
    assert p == Parameters(n_meses=3)
    assert replace(p, inicial=(0, 100), trajetoria=(0, 0, 0)).policy_parameters() == p.policy_parameters()
    assert replace(p, carga=100).policy_parameters() != p.policy_parameters()


@pytest.mark.parametrize("n", [1, 2, 12, 18, 24])
def test_variable_horizon_and_terminal_cost(n):
    p = Parameters(n_meses=n, nr_disc=3)
    _, states, curves = planejamento(p)
    result = avaliar(p, states, curves)
    assert len(curves) == n+1 and curves[-1] is None
    assert len(p.meses) == len(set(p.meses)) == n
    for name in ("planejada", "isolada"):
        assert len(result[name]) == n
        assert result[name][-1]["alpha"] == pytest.approx(0)
        for row in result[name]:
            assert np.dot(p.ro, row["vt"])+row["gt1"]+row["gt2"]+row["def"] == pytest.approx(p.carga, abs=1e-6)


def test_twelve_month_defaults_and_explicit_resize():
    p = Parameters()
    p.validate()
    assert p.n_meses == len(p.afl_max) == len(p.afl_min) == len(p.trajetoria) == 12
    assert p.afl_max[3:] == (p.afl_max[2],)*9
    changed = replace(p, afl_max=p.afl_max[:5] + ((80, 200),) + p.afl_max[6:])
    longer = changed.with_horizon(18)
    assert longer.afl_max[:12] == changed.afl_max
    assert longer.afl_max[12:] == (changed.afl_max[-1],)*6
    assert longer.with_horizon(1).afl_max == changed.afl_max[:1]
    longer.validate()


@pytest.mark.parametrize("n", [0, -1, 1.5, True])
def test_invalid_horizon(n):
    with pytest.raises(ValueError):
        Parameters(n_meses=n)


def test_legacy_json_infers_horizon():
    data = Parameters(n_meses=3).to_dict()
    del data["n_meses"]
    assert Parameters.from_dict(data) == Parameters(n_meses=3)
