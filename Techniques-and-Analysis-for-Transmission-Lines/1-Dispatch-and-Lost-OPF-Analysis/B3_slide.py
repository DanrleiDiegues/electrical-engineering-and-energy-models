import numpy as np

# Criando os dados de barras, linhas e geradores como listas de dicionários:
bars = [
    {"barra": 1, "tipo": 2, "carga": 0.0},
    {"barra": 2, "tipo": 0, "carga": 0.0},
    {"barra": 3, "tipo": 0, "carga": 10.0},
]


lines = [
    {"de": 1, "para": 2, "R": 10.0, "X": 100.0, "cap": 2.0},
    {"de": 1, "para": 3, "R": 15.0, "X": 100.0, "cap": 6.0},
    {"de": 2, "para": 3, "R": 5.0,  "X": 50.0,  "cap": 10.0},
]

'''
lines = [
    {"de": 1, "para": 2, "R": 20.0, "X": 100.0, "cap": 2.0},
    {"de": 1, "para": 3, "R": 20.0, "X": 100.0, "cap": 6.0},
    {"de": 2, "para": 3, "R": 10.0,  "X": 50.0,  "cap": 10.0},
]
'''

generators = [
    {"barra": 1, "pmin": 0.0, "pmax": 15.0, "custo": 10.0},
    {"barra": 2, "pmin": 0.0, "pmax": 15.0, "custo": 20.0},
]



# Esta função converte as listas de dicionários em matrizes NumPy no formato esperado pela função inpdat.
def dict_to_matrices(bars, lines, generators):
    #-------------------------
    # Dados das barras
    # colunas:
    # [barra, tipo, 0, 0, 0, 0, 0, 0, 0, carga]
    #-------------------------
    DBAR = np.array([
        [b["barra"], b["tipo"], 0, 0, 0, 0, 0, 0, 0, b["carga"]]
        for b in bars
    ], dtype=float)

    #-------------------------
    # Dados das linhas
    # colunas:
    # [de, para, R, X, 0, 0, 0, 0, 0, cap]
    # cap é o limite de fluxo em pu-MW
    #-------------------------
    DLIN = np.array([
        [l["de"], l["para"], l["R"], l["X"], 0, 0, 0, 0, 0, l["cap"]]
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

# Convertendo os dados do B3.py para as matrizes DBAR, DLIN e DGER
DBAR, DLIN, DGER = dict_to_matrices(bars, lines, generators)

if __name__ == "__main__":
    print(f"DBAR:\n{DBAR}\n")
    print(f"DLIN:\n{DLIN}\n")
    print(f"DGER:\n{DGER}\n")