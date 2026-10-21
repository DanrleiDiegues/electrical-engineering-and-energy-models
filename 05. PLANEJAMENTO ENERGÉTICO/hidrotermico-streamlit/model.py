"""Modelo do notebook, parametrizado sem alterar sua formulação matemática."""
from dataclasses import asdict, dataclass, replace
from itertools import product
from typing import Callable

import numpy as np
import pandas as pd
from pyscipopt import Model, quicksum

MESES = ("Setembro", "Outubro", "Novembro")
CALENDARIO = ("Setembro", "Outubro", "Novembro", "Dezembro", "Janeiro", "Fevereiro",
              "Março", "Abril", "Maio", "Junho", "Julho", "Agosto")
AFL_MAX_ORIGINAL = ((30.0, 70.0), (35.0, 93.0), (40.0, 176.0))
AFL_MIN_ORIGINAL = ((20.0, 24.0), (25.0, 29.0), (30.0, 20.0))
UHES = ("Batalha", "Serra do Facão")
HORAS = 30 * 24
FATOR_VOLUME = HORAS * 3600 / 1_000_000
ESCALA_CUSTO = 1_000_000


@dataclass(frozen=True)
class Parameters:
    n_meses: int = 12
    carga: float = 250.0
    nr_disc: int = 24
    vmin: tuple = (430.049988, 1752.0)
    vmax: tuple = (1781.609985, 5199.0)
    inicial: tuple = (39.7, 50.2)  # % do volume útil
    produtividade: tuple = (0.009025 * (37.70 - 1.20), 0.6157)  # MW/(m³/s)
    engolimento: tuple = (147.02, 313.0)  # m³/s
    potencia_serra: float = 212.58
    gtmax: tuple = (10.0, 17.0)
    custo_termico: tuple = (882.76, 118.93)  # R$/MWh
    custo_deficit: float = 4000.0
    afl_max: tuple | None = None
    afl_min: tuple | None = None
    trajetoria: tuple | None = None

    def __post_init__(self):
        if type(self.n_meses) is not int or self.n_meses < 1:
            raise ValueError("O horizonte deve ser um inteiro maior ou igual a 1 mês.")
        for name, original in (("afl_max", AFL_MAX_ORIGINAL), ("afl_min", AFL_MIN_ORIGINAL)):
            if getattr(self, name) is None:
                values = original[:self.n_meses] + (original[-1],) * max(0, self.n_meses-len(original))
                object.__setattr__(self, name, values)
        if self.trajetoria is None:
            object.__setattr__(self, "trajetoria", (1,) * self.n_meses)

    @property
    def meses(self):
        return tuple(CALENDARIO[i % 12] if self.n_meses <= 12 else
                     f"{CALENDARIO[i % 12]} · ciclo {i // 12 + 1}" for i in range(self.n_meses))

    def with_horizon(self, n_meses):
        """Preserva meses existentes e preenche novos com a última afluência."""
        if type(n_meses) is not int or n_meses < 1:
            raise ValueError("O horizonte deve ser um inteiro maior ou igual a 1 mês.")
        def resize(values):
            return values[:n_meses] + (values[-1],) * max(0, n_meses-len(values))
        return replace(self, n_meses=n_meses, afl_max=resize(self.afl_max),
                       afl_min=resize(self.afl_min), trajetoria=resize(self.trajetoria))

    @property
    def vi(self):
        return np.array(self.vmin) + np.array(self.inicial) / 100 * (np.array(self.vmax) - self.vmin)

    @property
    def ro(self):
        return np.array(self.produtividade) / FATOR_VOLUME

    @property
    def cenarios(self):
        return [np.array(self.afl_max) * FATOR_VOLUME, np.array(self.afl_min) * FATOR_VOLUME]

    def policy_parameters(self):
        """Volume inicial e trajetória não alteram a recursão na grade."""
        return replace(self, inicial=(39.7, 50.2), trajetoria=(1,) * self.n_meses)

    def validate(self):
        if type(self.nr_disc) is not int or self.nr_disc < 2:
            raise ValueError("A discretização deve ser um inteiro maior ou igual a 2.")
        for field in ("vmin", "vmax", "inicial", "produtividade", "engolimento", "gtmax", "custo_termico"):
            a = np.asarray(getattr(self, field), dtype=float)
            if a.shape != (2,) or not np.all(np.isfinite(a)):
                raise ValueError(f"{field}: informe dois números finitos.")
        for field in ("carga", "potencia_serra", "custo_deficit"):
            value = getattr(self, field)
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{field}: informe um número finito não negativo.")
        if np.any(np.array(self.vmax) <= self.vmin) or np.any(np.array(self.vmin) < 0):
            raise ValueError("Os volumes devem respeitar 0 ≤ mínimo < máximo em cada UHE.")
        if np.any(np.array(self.inicial) < 0) or np.any(np.array(self.inicial) > 100):
            raise ValueError("O armazenamento inicial deve estar entre 0 e 100% do volume útil.")
        for field in ("produtividade", "engolimento", "gtmax", "custo_termico"):
            if np.any(np.array(getattr(self, field)) < 0):
                raise ValueError(f"{field}: valores negativos não são permitidos.")
        hi, lo = np.array(self.afl_max, dtype=float), np.array(self.afl_min, dtype=float)
        if hi.shape != (self.n_meses, 2) or lo.shape != (self.n_meses, 2) or not np.all(np.isfinite([hi, lo])):
            raise ValueError(f"Informe afluências finitas para os {self.n_meses} meses e as duas UHEs.")
        if np.any(lo < 0) or np.any(hi < lo):
            raise ValueError("As afluências devem respeitar 0 ≤ mínima ≤ máxima.")
        if len(self.trajetoria) != self.n_meses or any(type(s) is not int or s not in (0, 1) for s in self.trajetoria):
            raise ValueError("Escolha máximo (0) ou mínimo (1) em cada mês da trajetória.")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("O cenário JSON deve ser um objeto.")
        data = dict(data)
        if "n_meses" not in data and isinstance(data.get("afl_max"), (list, tuple)):
            data["n_meses"] = len(data["afl_max"])
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError("Parâmetros desconhecidos: " + ", ".join(sorted(unknown)))
        def tuples(v):
            return tuple(tuples(x) for x in v) if isinstance(v, list) else v
        try:
            p = cls(**{k: tuples(v) for k, v in data.items()})
            p.validate()
        except (TypeError, OverflowError) as exc:
            raise ValueError("Tipos de parâmetros inválidos no cenário.") from exc
        return p


def despacho_hidrotermico(p, VI, AFL, estados=None, custos_futuros=None):
    """Mesmas variáveis, restrições, pesos e objetivo da célula 6 do notebook."""
    modelo = Model("despacho_hidrotermico")
    modelo.hideOutput()
    modelo.setRealParam("numerics/dualfeastol", 1e-9)
    try:
        vf = [modelo.addVar(f"vf{i+1}", lb=float(p.vmin[i]), ub=float(p.vmax[i])) for i in range(2)]
        vt = [modelo.addVar(f"vt{i+1}", lb=0, ub=float(p.engolimento[i] * FATOR_VOLUME)) for i in range(2)]
        vv = [modelo.addVar(f"vv{i+1}", lb=0) for i in range(2)]
        gt1 = modelo.addVar("gt1", lb=0, ub=p.gtmax[0])
        gt2 = modelo.addVar("gt2", lb=0, ub=p.gtmax[1])
        deficit = modelo.addVar("def", lb=0)
        alpha = modelo.addVar("alpha", lb=0)

        modelo.addCons(vf[0] == float(VI[0] + AFL[0]) - vt[0] - vv[0])
        modelo.addCons(vf[1] == float(VI[1] + AFL[1]) + vt[0] + vv[0] - vt[1] - vv[1])
        modelo.addCons(float(p.ro[0])*vt[0] + float(p.ro[1])*vt[1] + gt1 + gt2 + deficit == p.carga)
        modelo.addCons(float(p.ro[1])*vt[1] <= p.potencia_serra)

        if custos_futuros is None:
            modelo.addCons(alpha == 0)
        else:
            pesos = [modelo.addVar(lb=0) for _ in estados]
            modelo.addCons(quicksum(pesos) == 1)
            for i in range(2):
                modelo.addCons(vf[i] == quicksum(float(v[i])*w for v, w in zip(estados, pesos)))
            modelo.addCons(alpha == quicksum(float(c/ESCALA_CUSTO)*w for c, w in zip(custos_futuros, pesos)))

        custo_imediato = p.custo_termico[0]*HORAS*gt1 + p.custo_termico[1]*HORAS*gt2 + p.custo_deficit*HORAS*deficit + 0.01*quicksum(vv)
        modelo.setObjective(custo_imediato/ESCALA_CUSTO + alpha, sense="minimize")
        modelo.optimize()
        if modelo.getStatus() != "optimal":
            raise RuntimeError(f"Solução não ótima: {modelo.getStatus()}")
        return {"fob": modelo.getObjVal()*ESCALA_CUSTO, "ci": modelo.getVal(custo_imediato),
                "alpha": modelo.getVal(alpha)*ESCALA_CUSTO,
                "vf": np.array([modelo.getVal(v) for v in vf]),
                "vt": np.array([modelo.getVal(v) for v in vt]),
                "vv": np.array([modelo.getVal(v) for v in vv]),
                "gt1": modelo.getVal(gt1), "gt2": modelo.getVal(gt2), "def": modelo.getVal(deficit)}
    finally:
        modelo.freeProb()


def planejamento(p: Parameters, progress: Callable | None = None):
    p.validate()
    grades = [np.linspace(p.vmin[i], p.vmax[i], p.nr_disc) for i in range(2)]
    estados = np.array(list(product(*grades)))
    curvas = [None] * (p.n_meses + 1)
    done, total = 0, p.n_meses * len(estados) * 2
    for t in range(p.n_meses-1, -1, -1):
        custos = []
        for VI in estados:
            resultados = []
            for cenario in p.cenarios:
                r = despacho_hidrotermico(p, VI, cenario[t], estados, curvas[t+1])
                resultados.append(r["fob"])
                done += 1
            custos.append(sum(resultados) / 2)
            if progress and (done % 40 == 0 or done == total):
                progress(done, total, p.meses[t])
        curvas[t] = np.array(custos)
    return grades, estados, curvas


def simular(p, estados, curvas, considerar_futuro=True):
    VI, trajetoria = p.vi.copy(), []
    for t, mes in enumerate(p.meses):
        AFL = p.cenarios[p.trajetoria[t]][t]
        futuro = curvas[t+1] if considerar_futuro else None
        r = despacho_hidrotermico(p, VI, AFL, estados, futuro)
        trajetoria.append({"mes": mes, "VI": VI.copy(), "AFL": AFL.copy(), **r})
        VI = r["vf"].copy()
    return trajetoria


def avaliar(p, estados, curvas):
    p.validate()
    planejada = simular(p, estados, curvas)
    isolada = simular(p, estados, curvas, considerar_futuro=False)
    iniciais = [despacho_hidrotermico(p, p.vi, c[0], estados, curvas[1])["fob"] for c in p.cenarios]
    return {"planejada": planejada, "isolada": isolada, "custos_iniciais": iniciais}


def tabela_resultados(p, trajetoria):
    return pd.DataFrame([{
        "Mês": r["mes"], "Batalha (MWm)": p.ro[0]*r["vt"][0],
        "Serra (MWm)": p.ro[1]*r["vt"][1], "Baliza (MWm)": r["gt1"],
        "Candeias (MWm)": r["gt2"], "Déficit (MWm)": r["def"],
        "VI Batalha (hm³)": r["VI"][0], "VI Serra (hm³)": r["VI"][1],
        "VF Batalha (hm³)": r["vf"][0], "VF Serra (hm³)": r["vf"][1],
        "Turbinado Batalha (hm³)": r["vt"][0], "Turbinado Serra (hm³)": r["vt"][1],
        "Vertido Batalha (hm³)": r["vv"][0], "Vertido Serra (hm³)": r["vv"][1],
        "Afluência local Batalha (m³/s)": r["AFL"][0]/FATOR_VOLUME,
        "Afluência local Serra (m³/s)": r["AFL"][1]/FATOR_VOLUME,
        "Custo imediato (R$ mi)": r["ci"]/1e6, "Custo futuro (R$ mi)": r["alpha"]/1e6,
        "FOB (R$ mi)": r["fob"]/1e6,
    } for r in trajetoria])
