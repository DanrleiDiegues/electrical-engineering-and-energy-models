#//////////////////////////////////////////////////////////////////////
#             UNIVERSIDADE FEDERAL DE JUIZ DE FORA
#               FACULDADE DE ENGENHARIA ELÉTRICA
#         OTIMIZAÇÃO DE SISTEMAS ELETRICOS DE POTENCIA
#//////////////////////////////////////////////////////////////////////

#
#      Programa de Otimização - Parte A
#      Despacho econômico com perdas na transmissão
#

#      Variáveis de otimização:
#      x = [PG_1 ... PG_NGER  theta_1 ... theta_NBAR]
#
#      Função objetivo:
#      min  sum_g Cg * PG_g
#
#      Restrições de igualdade:
#      1) Balanço de potência nodal
#      2) Ângulo de referência
#
#      Restrições de desigualdade:
#      1) Limites de fluxo nas linhas
#
#      Restrições de canalização:
#      0 <= PG_g <= PGmax_g
#      -pi <= theta_i <= pi
#
#      Observação:
#      As perdas dependem de (theta_i - theta_j)^2, então são calculadas
#      fora do solver e inseridas iterativamente no vetor BX e nos limites Bi.
#
#//////////////////////////////////////////////////////////////////////

import numpy as np
from scipy.optimize import linprog
#from B3_slide import DBAR, DLIN, DGER
from B6L8 import DBAR, DLIN, DGER

#-------------------------------------------------------------
#------------ Subrotina para entrada de dados ----------------
#-------------------------------------------------------------
def inpdat_parteA(DBAR, DLIN, DGER, PB=100.0):
    # barra
    # linha
    # gerador
    # constantes gerais

    #----------Dados das barras----------

    NBAR, AUX = DBAR.shape
    BUSID = DBAR[:, 0].astype(int)
    TIPO = DBAR[:, 1].astype(int)

    # Coluna 10 no MATLAB -> índice 9 no Python
    PLOAD = DBAR[:, 9] / PB

    # Barra de referência (tipo = 2)
    BREF = None
    for i in range(NBAR):
        if TIPO[i] == 2:
            BREF = i
            break

    if BREF is None:
        raise ValueError("Nenhuma barra de referência (tipo 2) foi encontrada em DBAR.")

    #----------Dados das linhas----------

    NLIN, AUX = DLIN.shape
    bus_to_pos = {bus_id: pos for pos, bus_id in enumerate(BUSID)}

    SB = np.zeros(NLIN, dtype=int)
    EB = np.zeros(NLIN, dtype=int)
    r = np.zeros(NLIN, dtype=float)
    x = np.zeros(NLIN, dtype=float)
    G = np.zeros(NLIN, dtype=float)
    B = np.zeros(NLIN, dtype=float)
    Bor = np.zeros(NLIN, dtype=float)
    FLIM = np.zeros(NLIN, dtype=float)

    for i in range(NLIN):
        de_bus = int(DLIN[i, 0])
        para_bus = int(DLIN[i, 1])

        SB[i] = bus_to_pos[de_bus]              # índice interno da barra DE
        EB[i] = bus_to_pos[para_bus]            # índice interno da barra PARA

        r[i] = DLIN[i, 2] / 100.0               # resistência série
        x[i] = DLIN[i, 3] / 100.0               # reatância série

        denom = r[i] ** 2 + x[i] ** 2
        G[i] = r[i] / denom                     # condutância série
        B[i] = x[i] / denom                     # susceptância (módulo)

        Bor[i] = 1.0 / x[i]                     # gamma = 1/x
        FLIM[i] = DLIN[i, 9] / PB              # limite de fluxo em pu

    #----------Dados dos geradores----------

    NGER, AUX = DGER.shape
    BARPG = np.zeros(NGER, dtype=int)
    PGMIN = np.zeros(NGER, dtype=float)
    PGMAX = np.zeros(NGER, dtype=float)
    CPG = np.zeros(NGER, dtype=float)

    for i in range(NGER):
        ger_bus = int(DGER[i, 0])
        BARPG[i] = bus_to_pos[ger_bus]          # índice interno da barra do gerador
        PGMIN[i] = DGER[i, 1] / PB
        PGMAX[i] = DGER[i, 2] / PB
        CPG[i] = DGER[i, 3]

    #----------Inicializando variáveis----------

    # x = [PG_1 ... PG_NGER  theta_1 ... theta_NBAR]
    NVAR = NGER + NBAR

    return {
        "NBAR": NBAR,
        "BUSID": BUSID,
        "TIPO": TIPO,
        "PLOAD": PLOAD,
        "BREF": BREF,
        "NLIN": NLIN,
        "SB": SB,
        "EB": EB,
        "r": r,
        "x": x,
        "G": G,
        "B": B,
        "Bor": Bor,
        "FLIM": FLIM,
        "NGER": NGER,
        "BARPG": BARPG,
        "PGMIN": PGMIN,
        "PGMAX": PGMAX,
        "CPG": CPG,
        "NVAR": NVAR,
    }


#-------------------------------------------------------------
#------------ Cálculo de perdas e fluxos ---------------------
#-------------------------------------------------------------
def calc_losses_and_flows_partA(theta, G, Bor, SB, EB):
    """
    Calcula:
    - perdas por linha: Pperda_ij = G_ij * (theta_i - theta_j)^2
    - fluxo líquido DC: f_ij = gamma_ij * (theta_i - theta_j)
    """

    delta_theta = theta[SB] - theta[EB]
    perdas_linha = G * (delta_theta ** 2)
    fluxo = Bor * delta_theta

    return perdas_linha, fluxo


#-------------------------------------------------------------
#------------ Montagem do modelo da Parte A ------------------
#-------------------------------------------------------------
def build_model_partA(DBAR, DLIN, DGER, PB=100.0, theta_prev=None):
    """
    This function builds the optimization model for the economic dispatch problem with transmission losses (Part A).
    This includes the objective function, equality constraints (power balance and reference angle), inequality constraints (line flow limits), and variable bounds.
    The losses are calculated based on the previous iteration's angles and are included in the constraints iteratively.
    Args:
        DBAR (_type_): _description_
        DLIN (_type_): _description_
        DGER (_type_): _description_
        PB (float, optional): _description_. Defaults to 100.0.
        theta_prev (_type_, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    dados = inpdat_parteA(DBAR, DLIN, DGER, PB=PB)

    NBAR = dados["NBAR"]
    BUSID = dados["BUSID"]
    TIPO = dados["TIPO"]
    PLOAD = dados["PLOAD"]
    BREF = dados["BREF"]

    NLIN = dados["NLIN"]
    SB = dados["SB"]
    EB = dados["EB"]
    r = dados["r"]
    x = dados["x"]
    G = dados["G"]
    B = dados["B"]
    Bor = dados["Bor"]
    FLIM = dados["FLIM"]

    NGER = dados["NGER"]
    BARPG = dados["BARPG"]
    PGMIN = dados["PGMIN"]
    PGMAX = dados["PGMAX"]
    CPG = dados["CPG"]

    NVAR = dados["NVAR"]

    #---------------------------------------------------------
    #----------Indexação das variáveis------------------------
    #---------------------------------------------------------
    #
    # x = [PG_1 ... PG_NGER  theta_1 ... theta_NBAR]
    #
    i_pg_ini = 0
    i_pg_fim = NGER

    i_theta_ini = i_pg_fim
    i_theta_fim = i_theta_ini + NBAR

    idx = {
        "pg": slice(i_pg_ini, i_pg_fim),
        "theta": slice(i_theta_ini, i_theta_fim),
    }

    #---------------------------------------------------------
    #----------Chute inicial para perdas----------------------
    #---------------------------------------------------------
    if theta_prev is None:
        theta_prev = np.zeros(NBAR, dtype=float)

    perdas_linha_prev, fluxo_prev = calc_losses_and_flows_partA(
        theta_prev, G, Bor, SB, EB
    )

    #---------------------------------------------------------
    #----------Montagem da CX--------------------------------
    #---------------------------------------------------------
    #
    # min sum_g Cg * PG_g + 0 * theta
    #
    CX = np.zeros(NVAR, dtype=float)

    for g in range(NGER):
        CX[i_pg_ini + g] = CPG[g]

    #---------------------------------------------------------
    #----------Montagem da AX e BX---------------------------
    #---------------------------------------------------------
    #
    # Equações:
    # 1) balanço nodal: NBAR
    # 2) ângulo de referência: 1
    #
    NEQ = NBAR + 1
    AX = np.zeros((NEQ, NVAR), dtype=float)
    BX = np.zeros(NEQ, dtype=float)

    #---------------------------------------------------------
    #----------1) Balanço de potência nodal-------------------
    #---------------------------------------------------------
    #
    # PG_i - sum_j gamma_ij * (theta_i - theta_j)
    #     = PLOAD_i + DeltaPperda_i
    #
    # As perdas são inseridas como meia perda em cada extremidade
    # da linha, usando o valor calculado na iteração anterior.
    #
    PINJ = np.zeros(NBAR, dtype=float)

    for j in range(NLIN):
        PINJ[SB[j]] += perdas_linha_prev[j] / 2.0
        PINJ[EB[j]] += perdas_linha_prev[j] / 2.0

    # incidência dos geradores
    for g in range(NGER):
        barra_g = BARPG[g]
        AX[barra_g, i_pg_ini + g] = 1.0

    # montagem da matriz Bbus
    Bbus = np.zeros((NBAR, NBAR), dtype=float)

    for j in range(NLIN):
        de = SB[j]
        para = EB[j]
        gama = Bor[j]

        Bbus[de, de] += gama
        Bbus[para, para] += gama
        Bbus[de, para] -= gama
        Bbus[para, de] -= gama

    # termo angular entra com sinal negativo: PG - Bbus*theta = carga + perdas
    AX[0:NBAR, i_theta_ini:i_theta_fim] = -Bbus
    BX[0:NBAR] = PLOAD + PINJ

    #---------------------------------------------------------
    #----------2) Ângulo de referência------------------------
    #---------------------------------------------------------
    #
    # theta_ref = 0
    #
    row_ref = NBAR
    AX[row_ref, i_theta_ini + BREF] = 1.0
    BX[row_ref] = 0.0

    #---------------------------------------------------------
    #----------Montagem da Ai e Bi----------------------------
    #---------------------------------------------------------
    #
    # Limite de fluxo nas linhas:
    # f_ij <= L_ij - Pperda_ij/2
    #
    # Como o fluxo pode mudar de direção, usamos o sinal do fluxo
    # da iteração anterior para montar a desigualdade ativa.
    #
    Ai = np.zeros((NLIN, NVAR), dtype=float)
    Bi = np.zeros(NLIN, dtype=float)

    for j in range(NLIN):
        de = SB[j]
        para = EB[j]

        # limite corrigido pela perda da linha
        Bi[j] = FLIM[j] - perdas_linha_prev[j] / 2.0

        # se o fluxo anterior foi positivo, usa gamma*(theta_de - theta_para)
        if fluxo_prev[j] >= 0:
            Ai[j, i_theta_ini + de] = +Bor[j]
            Ai[j, i_theta_ini + para] = -Bor[j]

        # se o fluxo anterior foi negativo, inverte o sentido
        else:
            Ai[j, i_theta_ini + de] = -Bor[j]
            Ai[j, i_theta_ini + para] = +Bor[j]

    #---------------------------------------------------------
    #----------Restrições de canalização----------------------
    #---------------------------------------------------------
    Vlb = np.zeros(NVAR, dtype=float)
    Vub = np.zeros(NVAR, dtype=float)

    # PG
    Vlb[idx["pg"]] = PGMIN
    Vub[idx["pg"]] = PGMAX

    # theta
    Vlb[idx["theta"]] = -np.pi
    Vub[idx["theta"]] = +np.pi

    bounds = [(Vlb[k], Vub[k]) for k in range(NVAR)]

    return {
        "CX": CX,
        "AX": AX,
        "BX": BX,
        "Ai": Ai,
        "Bi": Bi,
        "Vlb": Vlb,
        "Vub": Vub,
        "bounds": bounds,
        "dados": dados,
        "idx": idx,
        "theta_prev": theta_prev,
        "perdas_linha_prev": perdas_linha_prev,
        "fluxo_prev": fluxo_prev,
    }


#-------------------------------------------------------------
#------------ Programa principal - Parte A -------------------
#-------------------------------------------------------------
def OPF_ParteA(
    DBAR,
    DLIN,
    DGER,
    PB=100.0,
    tol=1e-8,
    max_iter=50,
    verbose=True
):
    #----------Dados fixos----------

    dados = inpdat_parteA(DBAR, DLIN, DGER, PB=PB)
    NBAR = dados["NBAR"]
    BUSID = dados["BUSID"]
    TIPO = dados["TIPO"]
    PLOAD = dados["PLOAD"]
    BREF = dados["BREF"]

    NLIN = dados["NLIN"]
    SB = dados["SB"]
    EB = dados["EB"]
    r = dados["r"]
    x = dados["x"]
    G = dados["G"]
    B = dados["B"]
    Bor = dados["Bor"]
    FLIM = dados["FLIM"]

    NGER = dados["NGER"]
    BARPG = dados["BARPG"]
    PGMIN = dados["PGMIN"]
    PGMAX = dados["PGMAX"]
    CPG = dados["CPG"]

    # chute inicial para os ângulos
    theta_prev = np.zeros(NBAR, dtype=float)

    historico = []
    theta_old = None
    resultado_iter = None

    #---------------------------------------------------------
    #----------Processo iterativo para perdas-----------------
    #---------------------------------------------------------
    for k in range(max_iter):
        model = build_model_partA(
            DBAR=DBAR,
            DLIN=DLIN,
            DGER=DGER,
            PB=PB,
            theta_prev=theta_prev
        )

        CX = model["CX"]
        AX = model["AX"]
        BX = model["BX"]
        Ai = model["Ai"]
        Bi = model["Bi"]
        Vlb = model["Vlb"]
        Vub = model["Vub"]
        bounds = model["bounds"]
        idx = model["idx"]

        #-----------------------chamada do PL-----------------------
        res = linprog(
            c=CX,
            A_ub=Ai,
            b_ub=Bi,
            A_eq=AX,
            b_eq=BX,
            bounds=bounds,
            method="highs"
        )

        if not res.success:
            raise RuntimeError(f"O solver não convergiu. Status: {res.status} | {res.message}")

        Vp = res.x
        FOB = res.fun

        # decodificação
        PG = Vp[idx["pg"]]
        THETA = Vp[idx["theta"]]

        perdas_linha, fluxo = calc_losses_and_flows_partA(THETA, G, Bor, SB, EB)
        perdas_totais = np.sum(perdas_linha)

        # critério de convergência: variação máxima angular
        if theta_old is None:
            erro = np.inf
        else:
            erro = np.max(np.abs(THETA - theta_old))

        historico.append({
            "iter": k + 1,
            "FOB": FOB,
            "theta": THETA.copy(),
            "pg": PG.copy(),
            "perdas_linha_pu": perdas_linha.copy(),
            "perdas_linha_MW": perdas_linha * PB,
            "perdas_totais_pu": perdas_totais,
            "perdas_totais_MW": perdas_totais * PB,
            "fluxo_pu": fluxo.copy(),
            "fluxo_MW": fluxo * PB,
            "erro": erro,
        })

        if verbose:
            print("\n" + "=" * 60)
            print(f" ITERAÇÃO {k+1} - PARTE A")
            print("=" * 60)
            print(f"FOB = {FOB:.10f}")
            print(f"Perdas totais = {perdas_totais:.10f} pu  ({perdas_totais * PB:.6f} MW)")
            print(f"Erro angular = {erro}")

        if erro < tol:
            resultado_iter = {
                "res": res,
                "model": model,
                "PG": PG,
                "THETA": THETA,
                "perdas_linha": perdas_linha,
                "fluxo": fluxo,
                "perdas_totais": perdas_totais,
            }
            break

        theta_old = THETA.copy()
        theta_prev = THETA.copy()

    else:
        raise RuntimeError(f"O processo iterativo não convergiu em {max_iter} iterações.")

    #---------------------------------------------------------
    #----------Extração das variáveis duais-------------------
    #---------------------------------------------------------
    lbd_BUS = None
    lbd_EQ = None
    lbd_CV = None
    pilo = None
    piup = None

    res = resultado_iter["res"]
    model = resultado_iter["model"]
    idx = model["idx"]

    if hasattr(res, "eqlin") and res.eqlin is not None and res.eqlin.marginals is not None:
        lbd_EQ = -np.array(res.eqlin.marginals)
        lbd_BUS = -np.array(res.eqlin.marginals[0:NBAR])

    if hasattr(res, "ineqlin") and res.ineqlin is not None and res.ineqlin.marginals is not None:
        lbd_CV = -np.array(res.ineqlin.marginals)

    if hasattr(res, "lower") and res.lower is not None and res.lower.marginals is not None:
        pilo = -np.array(res.lower.marginals)

    if hasattr(res, "upper") and res.upper is not None and res.upper.marginals is not None:
        piup = -np.array(res.upper.marginals)

    #---------------------------------------------------------
    #----------Decodificação da solução final-----------------
    #---------------------------------------------------------
    PG = resultado_iter["PG"]
    THETA = resultado_iter["THETA"]
    perdas_linha = resultado_iter["perdas_linha"]
    fluxo = resultado_iter["fluxo"]
    perdas_totais = resultado_iter["perdas_totais"]

    THETA_GRAUS = THETA * 180.0 / np.pi
    PG_MW = PG * PB
    FLUXO_MW = fluxo * PB
    PERDAS_LINHA_MW = perdas_linha * PB
    PERDAS_TOTAIS_MW = perdas_totais * PB

    #---------------------------------------------------------
    #----------Impressão das saídas---------------------------
    #---------------------------------------------------------
    if verbose:
        print("\n" + "=" * 60)
        print(" DADOS PROCESSADOS PARA OTIMIZAÇÃO - PARTE A")
        print("=" * 60)
        print(f"NBAR: {NBAR}")
        print(f"BUSID: {BUSID}")
        print(f"PLOAD: {PLOAD}")
        print(f"TIPO: {TIPO}")
        print(f"BREF: {BREF}")
        print(f"NLIN: {NLIN}")
        print(f"SB: {SB}")
        print(f"EB: {EB}")
        print(f"r: {r}")
        print(f"x: {x}")
        print(f"G: {G}")
        print(f"B: {B}")
        print(f"Bor: {Bor}")
        print(f"FLIM: {FLIM}")
        print(f"NGER: {NGER}")
        print(f"BARPG: {BARPG}")
        print(f"PGMIN: {PGMIN}")
        print(f"PGMAX: {PGMAX}")
        print(f"NVAR: {dados['NVAR']}")

        print("\n" + "=" * 60)
        print(" MATRIZES DO PROBLEMA DE OTIMIZAÇÃO - PARTE A")
        print(" Problema CONSIDERANDO perdas e limites de fluxo:")
        print("=" * 60)
        print(f"CX (coeficientes da função objetivo):\n{model['CX']}\n")
        print(f"AX (coeficientes das igualdades):\n{model['AX']}\n")
        print(f"BX (termos independentes das igualdades):\n{model['BX']}\n")
        print(f"Ai (coeficientes das desigualdades de fluxo):\n{model['Ai']}\n")
        print(f"Bi (termos independentes das desigualdades de fluxo):\n{model['Bi']}\n")
        print(f"Vlb (limite inferior das variáveis):\n{model['Vlb']}\n")
        print(f"Vub (limite superior das variáveis):\n{model['Vub']}\n")

        print("--------- RESULTADOS DA OTIMIZAÇÃO - PARTE A ---------")
        print(f"Status da otimização (exitflag): {res.status}")
        print(f"Valor ótimo da função objetivo (fval): {res.fun}")
        print(f"Solução ótima (Vp): {res.x}\n")

        print(f"Função objetivo: FOB = {res.fun}")
        print(f"Perdas totais: {PERDAS_TOTAIS_MW:.6f} MW")

        print("\n----------DADOS DOS GERADORES-----------")
        print("   Gerador    Barra    PG(MW)")
        print(np.column_stack([np.arange(1, NGER + 1), BUSID[BARPG], PG_MW]))

        print("\n------------DADOS DAS LINHAS------------")
        print("   Linha    De    Para   Fluxo(MW)   Limite(MW)   Perda(MW)")
        print(np.column_stack([
            np.arange(1, NLIN + 1),
            BUSID[SB],
            BUSID[EB],
            FLUXO_MW,
            FLIM * PB,
            PERDAS_LINHA_MW
        ]))

        print("\n----------DADOS DAS BARRAS------------")
        print("   Barra    Teta(rad)    Teta(graus)    Lambda")
        if lbd_BUS is not None:
            print(np.column_stack([BUSID, THETA, THETA_GRAUS, lbd_BUS]))
        else:
            print(np.column_stack([BUSID, THETA, THETA_GRAUS]))

        if lbd_CV is not None:
            print("\nSensibilidade das linhas (duais das desigualdades)")
            print("   Linha    Lambda_linha")
            print(np.column_stack([np.arange(1, NLIN + 1), lbd_CV]))

        print("\n" + "=" * 60)
        print(" RELATÓRIO RESUMIDO - PARTE A")
        print("=" * 60)

        print("\nÂngulos:")
        for i in range(NBAR):
            print(f"  barra {BUSID[i]}: {THETA[i] + 0.0:.6f} rad  ({THETA_GRAUS[i] + 0.0:.6f} graus)")

        print("\nGeração:")
        for g in range(NGER):
            print(f"  G{g+1} (barra {BUSID[BARPG[g]]}): {PG_MW[g]:.6f} MW")

        print("\nFluxos nas linhas:")
        for j in range(NLIN):
            de = BUSID[SB[j]]
            para = BUSID[EB[j]]
            print(
                f"  L{j+1} ({de}->{para}): fluxo={FLUXO_MW[j] + 0.0:.6f} MW  "
                f"(limite={FLIM[j] * PB:.6f} MW)  perda={PERDAS_LINHA_MW[j] + 0.0:.6f} MW"
            )

        print("\nPreços nodais / Lambda das barras:")
        if lbd_BUS is not None:
            for i in range(NBAR):
                print(f"  barra {BUSID[i]}: {lbd_BUS[i] + 0.0:.6f}")

        print("\nDual da barra de referência:")
        if lbd_EQ is not None:
            print(f"  {lbd_EQ[-1] + 0.0:.6f}")

    return {
        "CX": model["CX"],
        "AX": model["AX"],
        "BX": model["BX"],
        "Ai": model["Ai"],
        "Bi": model["Bi"],
        "Vlb": model["Vlb"],
        "Vub": model["Vub"],
        "bounds": model["bounds"],
        "solution": res.x,
        "FOB": res.fun,
        "theta_rad": THETA,
        "theta_deg": THETA_GRAUS,
        "pg_pu": PG,
        "pg_MW": PG_MW,
        "fluxo_pu": fluxo,
        "fluxo_MW": FLUXO_MW,
        "perdas_linha_pu": perdas_linha,
        "perdas_linha_MW": PERDAS_LINHA_MW,
        "perdas_totais_pu": perdas_totais,
        "perdas_totais_MW": PERDAS_TOTAIS_MW,
        "lbd_BUS": lbd_BUS,
        "lbd_EQ": lbd_EQ,
        "lbd_CV": lbd_CV,
        "pilo": pilo,
        "piup": piup,
        "dados": dados,
        "idx": idx,
        "historico_iteracoes": historico,
        "solver_result": res,
        "DBAR": DBAR,
        "DLIN": DLIN,
        "DGER": DGER,
    }


#-------------------------------------------------------------
#------------ Exemplo de uso ---------------------------------
#-------------------------------------------------------------
if __name__ == "__main__":
    # Exemplo:
    # from B3 import DBAR, DLIN, DGER

    resultado = OPF_ParteA(
        DBAR,
        DLIN,
        DGER,
        PB=100.0,
        tol=1e-8,
        max_iter=50,
        verbose=True
    )