import numpy as np
# Criando os dados de barras, linhas e geradores como listas de dicionários:

bars = [
    { "barra": 1, "tipo": 2, "G": 1, "VT": 1.0, "angle": 0.0, "PG": 1.0, "QG": 6.9, "QMIN": -9999.0, "QMAX": 9999.0, "PLOAD": 0.0, "QLOAD": 0.0, "QBAR": 0.0 },
    { "barra": 2,"tipo": 0, "G": 0,  "VT": 1.0, "angle": -4.98, "PG": 0.0, "QG": 0.0, "QMIN": 0.0,   "QMAX": 0.0,    "PLOAD": 20.0, "QLOAD": 8.5, "QBAR": 0.0 },
    { "barra": 3, "tipo": 1, "G": 1, "VT": 1.05, "angle": -12.72, "PG": 0.0, "QG": 0.0, "QMIN": -200.0, "QMAX": 250.0, "PLOAD": 40.0, "QLOAD": 17.0, "QBAR": 0.0},
    { "barra": 4, "tipo": 1, "G": 1, "VT": 1.0, "angle": 0.0, "PG": 0.0, "QG": 0.0, "QMIN": -200.0, "QMAX": 250.0, "PLOAD": 30.0, "QLOAD": 4.0, "QBAR": 0.0 },
    { "barra": 5, "tipo": 0, "G": 0, "VT": 1.0, "angle": -4.98, "PG": 0.0, "QG": 0.0, "QMIN": 0.0, "QMAX": 0.0, "PLOAD": 30.0, "QLOAD": 12.7, "QBAR": 0.0 },
    { "barra": 6, "tipo": 0, "G": 0, "VT": 1.0, "angle": -12.72, "PG": 0.0, "QG": 0.0, "QMIN": 0.0, "QMAX": 0.0, "PLOAD": 40.0, "QLOAD": 17.3, "QBAR": 0.0 },
]

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

generators = [
    {"barra": 1, "pmin": 0.0, "pmax": 50.0, "custo": 10.0},
    {"barra": 3, "pmin": 0.0, "pmax": 70.0, "custo": 20.0},
    {"barra": 4, "pmin": 0.0, "pmax": 60.0, "custo": 30.0},
]

# Dados de limite de fluxo para cada linha
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

# Dados de tensão para cada tipo de barra
DTEN = [
    {"tipo": 0, "Vmin": 0.80, "Vmax": 1.20},
    {"tipo": 1, "Vmin": 1.00, "Vmax": 1.01},
]

# Flags e parâmetros do caso
FLG_LIM = 1
OBJF = 2   # 1 = custo operacional mínimo | 2 = perdas mínimas
R_BAR = 1
R_GER = 1
R_LIN = 1


# Esta função converte as listas de dicionários em matrizes NumPy no formato esperado.
def dict_to_matrices(bars, lines, generators):
    #-------------------------
    # Dados das barras
    # colunas:
    # [barra, tipo, G, VT, angle, PG, QG, QMIN, QMAX, PLOAD, QLOAD, QBAR]
    #-------------------------
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

    #-------------------------
    # Dados das linhas
    # colunas:
    # [de, para, R, X, 0, 0, 0, 0, 0, cap, custo]
    # cap é o limite de fluxo
    # custo é o custo associado à linha
    #-------------------------
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

    #-------------------------
    # Dados dos geradores
    # colunas:
    # [barra, pmin, pmax, custo]
    #-------------------------
    DGER = np.array([
        [g["barra"], g["pmin"], g["pmax"], g["custo"]]
        for g in generators
    ], dtype=float)

    return DBAR, DLIN, DGER


# Convertendo os dados do B6L8.py para as matrizes DBAR, DLIN e DGER
DBAR, DLIN, DGER = dict_to_matrices(bars, lines, generators)

if __name__ == "__main__":
    print(f"DBAR:\n{DBAR}\n")
    print(f"DLIN:\n{DLIN}\n")
    print(f"DGER:\n{DGER}\n")
    print(f"DVIO:\n{DVIO}\n")
    print(f"DTEN:\n{DTEN}\n")