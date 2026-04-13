import numpy as np

# ============================================================
# DADOS DAS BARRAS
# colunas esperadas em DBAR:
# [barra, tipo, G, VT, angle, PG, QG, QMIN, QMAX, PLOAD, QLOAD, QBAR]
# ============================================================
bars = [
    {"barra": 1, "tipo": 2, "G": 1, "VT": 1.0,  "angle": 0.0,   "PG": 1.0, "QG": 6.9, "QMIN": -9999.0, "QMAX": 9999.0, "PLOAD": 0.0,  "QLOAD": 0.0,  "QBAR": 0.0},
    {"barra": 2, "tipo": 0, "G": 0, "VT": 1.0,  "angle": -4.98, "PG": 0.0, "QG": 0.0, "QMIN": 0.0,     "QMAX": 0.0,    "PLOAD": 20.0, "QLOAD": 8.5,  "QBAR": 0.0},
    {"barra": 3, "tipo": 1, "G": 1, "VT": 1.05, "angle": -12.72,"PG": 0.0, "QG": 0.0, "QMIN": -200.0,  "QMAX": 250.0,  "PLOAD": 40.0, "QLOAD": 17.0, "QBAR": 0.0},
    {"barra": 4, "tipo": 1, "G": 1, "VT": 1.0,  "angle": 0.0,   "PG": 0.0, "QG": 0.0, "QMIN": -200.0,  "QMAX": 250.0,  "PLOAD": 30.0, "QLOAD": 4.0,  "QBAR": 0.0},
    {"barra": 5, "tipo": 0, "G": 0, "VT": 1.0,  "angle": -4.98, "PG": 0.0, "QG": 0.0, "QMIN": 0.0,     "QMAX": 0.0,    "PLOAD": 30.0, "QLOAD": 12.7, "QBAR": 0.0},
    {"barra": 6, "tipo": 0, "G": 0, "VT": 1.0,  "angle": -12.72,"PG": 0.0, "QG": 0.0, "QMIN": 0.0,     "QMAX": 0.0,    "PLOAD": 40.0, "QLOAD": 17.3, "QBAR": 0.0},
    # ------- Mudanças para Teste de aumento de CARGA:
    #{"barra": 5, "tipo": 0, "G": 0, "VT": 1.0,  "angle": -4.98, "PG": 0.0, "QG": 0.0, "QMIN": 0.0,     "QMAX": 0.0,    "PLOAD": 40.0, "QLOAD": 12.7, "QBAR": 0.0},
    #{"barra": 6, "tipo": 0, "G": 0, "VT": 1.0,  "angle": -12.72,"PG": 0.0, "QG": 0.0, "QMIN": 0.0,     "QMAX": 0.0,    "PLOAD": 50.0, "QLOAD": 17.3, "QBAR": 0.0},
    
]

# ============================================================
# DADOS DAS LINHAS
# colunas esperadas em DLIN:
# [de, para, R, X, 0, 0, 0, 0, 0, cap, custo]
# ============================================================
lines = [
    {"linha": 1, "de": 1, "para": 2, "R": 1.0, "X": 10.0, "cap": 15.0, "custo": 0.15},
    {"linha": 2, "de": 2, "para": 3, "R": 2.0, "X": 17.0, "cap": 15.0, "custo": 0.15},
    {"linha": 3, "de": 3, "para": 4, "R": 5.0, "X": 10.0, "cap": 10.0, "custo": 0.10},
    {"linha": 4, "de": 4, "para": 5, "R": 1.0, "X": 15.0, "cap": 25.0, "custo": 0.25},
    {"linha": 5, "de": 5, "para": 6, "R": 2.0, "X": 18.0, "cap": 20.0, "custo": 0.20},
    {"linha": 6, "de": 3, "para": 6, "R": 3.0, "X": 13.0, "cap": 30.0, "custo": 0.30},
    {"linha": 7, "de": 1, "para": 5, "R": 1.0, "X": 14.0, "cap": 30.0, "custo": 0.30},
    {"linha": 8, "de": 4, "para": 2, "R": 2.0, "X": 12.0, "cap": 20.0, "custo": 0.20},
]

# ============================================================
# GERADORES CONVENCIONAIS + FICTÍCIOS NO MESMO BLOCO
# colunas esperadas em DGER:
# [barra, pmin, pmax, custo]
#
# Estrutura alinhada com o ieee118.py:
# - primeiro entram os geradores convencionais reais
# - depois entram os geradores fictícios de corte de carga
# ============================================================
generators = [
    # -------------------------
    # GERADORES CONVENCIONAIS REAIS
    # -------------------------
    {"barra": 1, "pmin": 0.0, "pmax": 50.0, "custo": 10.0},
    {"barra": 3, "pmin": 0.0, "pmax": 70.0, "custo": 20.0},
    {"barra": 4, "pmin": 0.0, "pmax": 60.0, "custo": 30.0},

    # -------------------------
    # GERADORES FICTÍCIOS PARA CORTE DE CARGA
    # custo alto para só serem usados se necessário
    # -------------------------
    {"barra": 2, "pmin": 0.0, "pmax": 20.0, "custo": 400.0},
    {"barra": 3, "pmin": 0.0, "pmax": 40.0, "custo": 400.0},
    {"barra": 4, "pmin": 0.0, "pmax": 30.0, "custo": 400.0},
    {"barra": 5, "pmin": 0.0, "pmax": 30.0, "custo": 400.0},
    {"barra": 6, "pmin": 0.0, "pmax": 40.0, "custo": 400.0},
]

# ============================================================
# GERAÇÃO EÓLICA (DGW)
# colunas esperadas em DGW:
# [barra, pgwmin, pgwmax, custo]
#
# Agora a eólica também carrega custo explícito,
# igual ao padrão adotado no ieee118.py.
# ============================================================
"""
wind_generators = [
    {"barra": 5, "pgwmin": 0.0, "pgwmax": 50.0, "custo": 60.0},
    {"barra": 6, "pgwmin": 0.0, "pgwmax": 35.0, "custo": 60.0},
]
"""
wind_generators = [
    {"barra": 5, "pgwmin": 0.0, "pgwmax": 80.0, "custo": 60.0},
    {"barra": 6, "pgwmin": 0.0, "pgwmax": 50.0, "custo": 60.0},
]

# ============================================================
# LIMITES DE FLUXO
# ============================================================
DVIO = [
    {"linha": 1, "limite": 15.0},
    {"linha": 2, "limite": 15.0},
    {"linha": 3, "limite": 10.0},
    {"linha": 4, "limite": 25.0},
    {"linha": 5, "limite": 20.0},
    {"linha": 6, "limite": 30.0},
    {"linha": 7, "limite": 30.0},
    {"linha": 8, "limite": 20.0},
]

# ============================================================
# LIMITES DE TENSÃO POR TIPO DE BARRA
# ============================================================
DTEN = [
    {"tipo": 0, "Vmin": 0.80, "Vmax": 1.20},
    {"tipo": 1, "Vmin": 1.00, "Vmax": 1.01},
]

# ============================================================
# FLAGS E PARÂMETROS DO CASO
# ============================================================
FLG_LIM = 1
OBJF = 2   # 1 = custo operacional mínimo | 2 = perdas mínimas
R_BAR = 1
R_GER = 1
R_LIN = 1

# ============================================================
# PARÂMETROS DOS CENÁRIOS
# ============================================================
SCENARIO_CONFIG = {
    "num_scenarios": 100,
    "base_power_MW": 100.0,

    # carga
    "load_distribution": "normal",   # "uniform" ou "normal"

    # uniforme
    "ag": 0.95,
    "bg": 1.10,
    "ac": -0.02,
    "bc": 0.02,

    # normal
    "mu_geral": 0.00,
    "sigma_geral": 0.04,
    "mu_local": 0.00,
    "sigma_local": 0.015,

    # limites de proteção
    "fator_min": 0.70,
    "fator_max": 1.30,

    # eólica
    "wind_distribution": "weibull",
    "weibull_scale": 1.0,
    "weibull_shape": 2.5,

    # custos
    "custo_corte_carga": 400.0,
    "custo_corte_vento": 60.0,
    "custo_eolica": 60.0,
    "epsilon_pg": 1e-4,
    "tol": 1e-8,
    "max_iter": 50,

    # quantidade de geradores por tipo no vetor unificado DGER
    "num_real_generators": 3,
    "num_fict_generators": 5,
}

# ============================================================
# FUNÇÕES AUXILIARES DE CONSTRUÇÃO
# ============================================================

def dict_to_matrices(
    bars,
    lines,
    generators,
    wind_generators=None,
):
    """
    Converte listas de dicionários em matrizes NumPy.

    Retorna:
        DBAR : matriz das barras
        DLIN : matriz das linhas
        DGER : matriz de todos os geradores convencionais
               (reais + fictícios de corte de carga)
        DGW  : matriz dos geradores eólicos com custo
    """

    wind_generators = wind_generators or []

    # -------------------------
    # DBAR
    # [barra, tipo, G, VT, angle, PG, QG, QMIN, QMAX, PLOAD, QLOAD, QBAR]
    # -------------------------
    DBAR = np.array([
        [
            b["barra"],
            b["tipo"],
            b["G"],
            b["VT"],
            b["angle"],
            b["PG"],
            b["QG"],
            b["QMIN"],
            b["QMAX"],
            b["PLOAD"],
            b["QLOAD"],
            b["QBAR"],
        ]
        for b in bars
    ], dtype=float)

    # -------------------------
    # DLIN
    # [de, para, R, X, 0, 0, 0, 0, 0, cap, custo]
    # -------------------------
    DLIN = np.array([
        [
            l["de"],
            l["para"],
            l["R"],
            l["X"],
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            l["cap"],
            l["custo"],
        ]
        for l in lines
    ], dtype=float)

    # -------------------------
    # DGER
    # [barra, pmin, pmax, custo]
    # Inclui geradores reais + fictícios de corte de carga
    # -------------------------
    DGER = np.array([
        [g["barra"], g["pmin"], g["pmax"], g["custo"]]
        for g in generators
    ], dtype=float)

    # -------------------------
    # DGW
    # [barra, pgwmin, pgwmax, custo]
    # -------------------------
    if wind_generators:
        DGW = np.array([
            [w["barra"], w["pgwmin"], w["pgwmax"], w["custo"]]
            for w in wind_generators
        ], dtype=float)
    else:
        DGW = np.zeros((0, 4), dtype=float)

    return DBAR, DLIN, DGER, DGW


def build_base_load_vectors(bars):
    """
    Guarda os vetores base de carga ativa e reativa.
    Isso ajuda depois na geração dos cenários.
    """
    PLOAD_b = np.array([b["PLOAD"] for b in bars], dtype=float)
    QLOAD_b = np.array([b["QLOAD"] for b in bars], dtype=float)
    return PLOAD_b, QLOAD_b


def classify_generators(num_real_generators, num_fict_generators):
    """
    Retorna índices úteis para separar geradores reais dos fictícios
    dentro do DGER unificado.
    """
    idx_real = np.arange(0, num_real_generators)
    idx_fict = np.arange(num_real_generators, num_real_generators + num_fict_generators)
    return idx_real, idx_fict


# ============================================================
# CONSTRUÇÃO FINAL DAS MATRIZES
# ============================================================
DBAR, DLIN, DGER, DGW = dict_to_matrices(
    bars=bars,
    lines=lines,
    generators=generators,
    wind_generators=wind_generators,
)

PLOAD_b, QLOAD_b = build_base_load_vectors(bars)
idx_real_gen, idx_fict_gen = classify_generators(
    SCENARIO_CONFIG["num_real_generators"],
    SCENARIO_CONFIG["num_fict_generators"],
)

# ============================================================
# DEBUG / TESTE
# ============================================================
if __name__ == "__main__":
    print("DBAR:\n", DBAR, "\n")
    print("DLIN:\n", DLIN, "\n")
    print("DGER (reais + fictícios):\n", DGER, "\n")
    print("DGW (eólicas com custo):\n", DGW, "\n")
    print("DVIO:\n", DVIO, "\n")
    print("DTEN:\n", DTEN, "\n")
    print("PLOAD_b:\n", PLOAD_b, "\n")
    print("QLOAD_b:\n", QLOAD_b, "\n")
    print("idx_real_gen:\n", idx_real_gen, "\n")
    print("idx_fict_gen:\n", idx_fict_gen, "\n")
    print("SCENARIO_CONFIG:\n", SCENARIO_CONFIG, "\n")
