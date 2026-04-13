#//////////////////////////////////////////////////////////////////////
#             UNIVERSIDADE FEDERAL DE JUIZ DE FORA
#               FACULDADE DE ENGENHARIA ELÉTRICA
#         OTIMIZAÇÃO DE SISTEMAS ELETRICOS DE POTENCIA
#//////////////////////////////////////////////////////////////////////
#
#      Programa de Otimização - Parte C
#      Despacho econômico + minimização de investimento
#
#      Variáveis de otimização:
#      x = [theta_1 ... theta_NBAR
#           fdir_1  ... fdir_NLIN
#           frev_1  ... frev_NLIN
#           PG_1    ... PG_NGER]
#
#      Função objetivo:
#      min  sum_j Cj * (fdir_j + frev_j) + sum_g penalidade_pg * PG_g
#
#      Restrições de igualdade:
#      1) Balanço de potência nodal
#      2) Fluxo nas linhas (Lei de Ohm DC)
#      3) Ângulo de referência
#
#      Restrições de canalização:
#      -pi <= theta_i <= pi
#      0 <= fdir_j <= Lj
#      0 <= frev_j <= Lj
#      PGmin_g <= PG_g <= PGmax_g
#
#//////////////////////////////////////////////////////////////////////

import numpy as np
from scipy.optimize import linprog
from save_result import save_opf_results
from plots_panel import run_big_dashboard
import matplotlib.pyplot as plt
#from B3 import DBAR, DLIN, DGER
#from B3_aula import DBAR, DLIN, DGER
from B3_slide import DBAR, DLIN, DGER # Slide do Glaucio.
#from B6L8 import DBAR, DLIN, DGER
#from ieee118 import DBAR, DLIN, DGER
#-------------------------------------------------------------
#------------ Subrotina para entrada de dados ----------------
#-------------------------------------------------------------
def inpdat_final(DBAR, DLIN, DGER, PB=100.0, line_costs=None):
    # barra
    # linha
    # gerador
    # constantes gerais

    #----------Dados das barras----------

    NBAR, AUX = DBAR.shape
    BUSID = DBAR[:, 0].astype(int)
    TIPO = DBAR[:, 1].astype(int)

    # Coluna 10 no MATLAB -> índice 9 no Python
    # Funciona tanto para o B3 enxuto quanto para casos maiores
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
    CLINE = np.zeros(NLIN, dtype=float)

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

        # custo da linha:
        # 1) se o usuário passar line_costs, usa esse vetor
        # 2) se DLIN tiver a coluna 11, usa como custo
        # 3) senão, usa a própria capacidade como fallback
        if line_costs is not None:
            CLINE[i] = line_costs[i]
        elif DLIN.shape[1] >= 11:
            CLINE[i] = DLIN[i, 10]
        else:
            CLINE[i] = DLIN[i, 9]

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
    # theta + fdir + frev + PG
    NVAR = NBAR + NLIN + NLIN + NGER

    return {
        "NBAR": NBAR, "BUSID": BUSID, "TIPO": TIPO, "PLOAD": PLOAD, "BREF": BREF,
        "NLIN": NLIN, "SB": SB, "EB": EB, "r": r, "x": x, "G": G, "B": B, "Bor": Bor,
        "FLIM": FLIM, "CLINE": CLINE, "NGER": NGER, "BARPG": BARPG, "PGMIN": PGMIN,
        "PGMAX": PGMAX, "CPG": CPG, "NVAR": NVAR,
    }


#-------------------------------------------------------------
#------------ Programa principal - Parte C -------------------
#-------------------------------------------------------------

# Perdas totais:
def calc_total_losses_pu(theta, G, SB, EB):
    """
    Calcula a perda total do sistema em pu:
        Pperda_total = sum_j G_j * (theta_de - theta_para)^2
    """
    delta_theta = theta[SB] - theta[EB]
    perdas_linha = G * (delta_theta ** 2)
    perda_total = np.sum(perdas_linha)
    
    # Print das matrizes de perdas:
    print(" 🟢 Perdas por linha (MW):")
    for j in range(len(SB)):
        print(f"  Linha {j+1} (de {SB[j]+1} para {EB[j]+1}): {perdas_linha[j]:.10f} pu")
    print(f"  Total: {perda_total:.10f} pu") 
    
    return perda_total, perdas_linha

def OPF_Final(
    DBAR, DLIN, DGER,
    PB=100.0,
    penalidade_pg=0.001,
    line_costs=None,
    PLOAD_override=None,
    verbose=True
):
    # barra
    # linha
    # gerador
    # constantes gerais
    # PL

    #----------Input Dados----------

    dados = inpdat_final(DBAR, DLIN, DGER, PB=PB, line_costs=line_costs)

    NBAR = dados["NBAR"]
    BUSID = dados["BUSID"]
    TIPO = dados["TIPO"]
    
    # PLOAD é carregado a partir de dados, mas pode ser sobrescrito por um vetor fornecido pelo usuário. 
    # Se PLOAD_override for None, usa o PLOAD original dos dados; caso contrário, 
    # converte PLOAD_override para um array NumPy e o utiliza como o vetor de carga.
    PLOAD_base = dados["PLOAD"].copy()

    if PLOAD_override is None:
        PLOAD = PLOAD_base.copy()
    else:
        PLOAD = np.array(PLOAD_override, dtype=float).copy()
    
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
    CLINE = dados["CLINE"]

    NGER = dados["NGER"]
    BARPG = dados["BARPG"]
    PGMIN = dados["PGMIN"]
    PGMAX = dados["PGMAX"]
    CPG = dados["CPG"]

    NVAR = dados["NVAR"]

    #---------------------------------------------------------
    #----------Indexação das variáveis------------------------
    #---------------------------------------------------------
    i_theta_ini = 0
    i_theta_fim = NBAR

    i_fdir_ini = i_theta_fim
    i_fdir_fim = i_fdir_ini + NLIN

    i_frev_ini = i_fdir_fim
    i_frev_fim = i_frev_ini + NLIN

    i_pg_ini = i_frev_fim
    i_pg_fim = i_pg_ini + NGER

    idx = {
        "theta": slice(i_theta_ini, i_theta_fim),
        "fdir": slice(i_fdir_ini, i_fdir_fim),
        "frev": slice(i_frev_ini, i_frev_fim),
        "pg": slice(i_pg_ini, i_pg_fim),
    }

    #---------------------------------------------------------
    #----------Montagem da CX--------------------------------
    #---------------------------------------------------------
    #
    # min sum_j Cj*(fdir_j + frev_j) + sum_g penalidade_pg*PG_g
    #
    CX = np.zeros(NVAR, dtype=float)

    # theta -> custo zero
    # fdir  -> custo da linha
    # frev  -> custo da linha
    # PG    -> penalização pequena

    for j in range(NLIN):
        CX[i_fdir_ini + j] = CLINE[j]
        CX[i_frev_ini + j] = CLINE[j]

    for g in range(NGER):
        CX[i_pg_ini + g] = penalidade_pg

    #---------------------------------------------------------
    #----------Montagem da AX e BX---------------------------
    #---------------------------------------------------------
    #
    # Equações:
    # 1) balanço nodal: NBAR
    # 2) fluxo nas linhas: NLIN
    # 3) ângulo de referência: 1
    #
    NEQ = NBAR + NLIN + 1

    AX = np.zeros((NEQ, NVAR), dtype=float)
    BX = np.zeros(NEQ, dtype=float)

    #---------------------------------------------------------
    #----------1) Balanço de potência nodal-------------------
    #---------------------------------------------------------
    #
    # Equação adotada:
    #
    # (sum f_saindo - sum f_entrando) - PG = -PLOAD
    #
    # Para cada linha j orientada de SB -> EB:
    #
    # na barra SB:
    #   +fdir_j - frev_j
    #
    # na barra EB:
    #   -fdir_j + frev_j
    #
    for i in range(NBAR):
        # contribuição das linhas
        for j in range(NLIN):
            if SB[j] == i:
                AX[i, i_fdir_ini + j] += 1.0
                AX[i, i_frev_ini + j] += -1.0

            if EB[j] == i:
                AX[i, i_fdir_ini + j] += -1.0
                AX[i, i_frev_ini + j] += 1.0

        # contribuição dos geradores
        for g in range(NGER):
            if BARPG[g] == i:
                AX[i, i_pg_ini + g] += -1.0

        BX[i] = -PLOAD[i]

    #---------------------------------------------------------
    #----------2) Fluxo nas linhas (Lei de Ohm DC)------------
    #---------------------------------------------------------
    #
    # (fdir_j - frev_j) - gamma_j*(theta_SB - theta_EB) = 0
    #
    for j in range(NLIN):
        row = NBAR + j

        de = SB[j]
        para = EB[j]
        gama = Bor[j]

        AX[row, i_theta_ini + de] += -gama
        AX[row, i_theta_ini + para] += +gama
        AX[row, i_fdir_ini + j] += +1.0
        AX[row, i_frev_ini + j] += -1.0

        BX[row] = 0.0

    #---------------------------------------------------------
    #----------3) Ângulo de referência------------------------
    #---------------------------------------------------------
    #
    # theta_ref = 0
    #
    row_ref = NBAR + NLIN
    AX[row_ref, i_theta_ini + BREF] = 1.0
    BX[row_ref] = 0.0

    #---------------------------------------------------------
    #----------Restrições de canalização----------------------
    #---------------------------------------------------------
    Vlb = np.zeros(NVAR, dtype=float)
    Vub = np.zeros(NVAR, dtype=float)

    # theta
    Vlb[idx["theta"]] = -np.pi
    Vub[idx["theta"]] = +np.pi

    # fdir
    Vlb[idx["fdir"]] = 0.0
    Vub[idx["fdir"]] = FLIM

    # frev
    Vlb[idx["frev"]] = 0.0
    Vub[idx["frev"]] = FLIM

    # PG
    Vlb[idx["pg"]] = PGMIN
    Vub[idx["pg"]] = PGMAX

    bounds = [(Vlb[k], Vub[k]) for k in range(NVAR)]

    #---------------------------------------------------------
    #----------Chamada do PL---------------------------------
    #---------------------------------------------------------
    res = linprog(
        c=CX,
        A_ub=None,
        b_ub=None,
        A_eq=AX,
        b_eq=BX,
        bounds=bounds,
        method="highs"
    )

    if not res.success:
        raise RuntimeError(f"O solver não convergiu. Status: {res.status} | {res.message}")

    Vp = res.x
    FOB = res.fun
    exitflag = res.status
    fval = res.fun

    #---------------------------------------------------------
    #----------Extração das variáveis duais-------------------
    #---------------------------------------------------------
    lbd_BUS = None
    lbd_EQ = None
    pilo = None
    piup = None

    if hasattr(res, "eqlin") and res.eqlin is not None and res.eqlin.marginals is not None:
        lbd_EQ = -np.array(res.eqlin.marginals) # Multiplicadores das igualdades (balanço de potência, fluxo nas linhas, ângulo de referência)
        lbd_BUS = -np.array(res.eqlin.marginals[0:NBAR]) # Multiplicadores específicos das igualdades de balanço de potência, que podem ser interpretados como os preços nodais de energia (lambdas) em cada barra.
        
    if hasattr(res, "lower") and res.lower is not None and res.lower.marginals is not None:
        pilo = -np.array(res.lower.marginals) # Multiplicadores dos limites inferiores das variáveis, que indicam o quanto a função objetivo aumentaria se o limite inferior de uma variável fosse relaxado.

    if hasattr(res, "upper") and res.upper is not None and res.upper.marginals is not None:
        piup = -np.array(res.upper.marginals) # Multiplicadores dos limites superiores das variáveis, que indicam o quanto a função objetivo aumentaria se o limite superior de uma variável fosse relaxado. No contexto das linhas, esses multiplicadores estão relacionados à sensibilidade do custo em relação aos limites de fluxo nas linhas, e podem ser usados para avaliar o benefício de investir em reforços na capacidade das linhas.

    #print(f"Multiplicadores das igualdades (lbd_EQ):\n{lbd_EQ}\n")
    #print(f"Multiplicadores específicos das igualdades de balanço de potência (lbd_BUS):\n{lbd_BUS}\n")
    #print(f"Multiplicadores dos limites inferiores (pilo):\n{pilo}\n")
    #print(f"Multiplicadores dos limites superiores (piup):\n{piup}\n")

    #---------------------------------------------------------
    #----------Decodificação da solução-----------------------
    #---------------------------------------------------------
    THETA = Vp[idx["theta"]]
    FDIR = Vp[idx["fdir"]]
    FREV = Vp[idx["frev"]]
    PG = Vp[idx["pg"]]

    THETA_GRAUS = THETA * 180.0 / np.pi
    FLIQ = FDIR - FREV

    # Converter para MW
    FDIR_MW = FDIR * PB
    FREV_MW = FREV * PB
    FLIQ_MW = FLIQ * PB
    PG_MW = PG * PB

    #---------------------------------------------------------
    #----------Sensibilidade das linhas-----------------------
    #---------------------------------------------------------
    #
    # Como o limite da linha foi modelado em Vub de fdir e frev,
    # a sensibilidade das linhas vem dos multiplicadores dos
    # limites superiores dessas variáveis.
    
    #---------------------------------------------------------
    #----------Sensibilidade das linhas-----------------------
    #---------------------------------------------------------
    sens_fdir = None
    sens_frev = None
    sens_linha = None
    indice_invest = None

    if piup is not None:
        sens_fdir = piup[idx["fdir"]]
        sens_frev = piup[idx["frev"]]
        
        # sensibilidade agregada por linha
        sens_linha = np.maximum(sens_fdir, sens_frev)
        
        # índice benefício/custo
        indice_invest = sens_linha / CLINE

    #---------------------------------------------------------
    #---------- IMPRIME AS SAÍDAS DE DADOS --------------------------------
    #---------------------------------------------------------
    if verbose:
        print("\n" + "="*50)
        print(" DADOS PROCESSADOS PARA OTIMIZAÇÃO")
        print("="*50)
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
        print(f"CLINE: {CLINE}")
        print(f"NGER: {NGER}")
        print(f"BARPG: {BARPG}")
        print(f"PGMIN: {PGMIN}")
        print(f"PGMAX: {PGMAX}")
        print(f"NVAR: {NVAR}")
        
        # ----------------------------------------------------------------------------------------------------------------
        # -------------------------------- IMPRIME MATRIZES DO PROBLEMA DE OTIMIZAÇÃO --------------------------------------
        # ----------------------------------------------------------------------------------------------------------------
        print("\n" + "="*50)
        print(" MATRIZES DO PROBLEMA DE OTIMIZAÇÃO")
        print(" Problema CONSIDERANDO PERDAS E LIMITES DE FLUXO:")
        print("="*50)
        
        print(f"CX (coeficientes da função objetivo):\n{CX}\n")
        print(f"AX (coeficientes das igualdades de balanço de potência):\n{AX}\n")
        print(f"BX (termos independentes das igualdades de balanço de potência):\n{BX}\n")
        #print(f"Ai (coeficientes das desigualdades de fluxo):\n{Ai}\n")
        #print(f"Bi (termos independentes das desigualdades de fluxo):\n{Bi}\n")
        print(f"Vlb (limite inferior das variáveis):\n{Vlb}\n")
        print(f"Vub (limite superior das variáveis):\n{Vub}\n")
        print("")
        print("--------- RESULTADOS DA OTIMIZAÇÃO ---------")
        print(f"Status da otimização (exitflag): {exitflag}")
        print(f"Valor ótimo da função objetivo (fval): {fval}")
        print(f"Solução ótima (Vp): {Vp}")
        print("\n -------------- // -------------- \n")
        print(f"Função objetivo: FOB = {FOB}")
        print(" ")
        print("----------DADOS DOS GERADORES-----------")
        print("    Barra    Geração(MW)")
        print(np.column_stack([BUSID[BARPG], PG_MW]))
        print(" ")
        print("------------DADOS DAS LINHAS------------")
        print(" ")
        print("   Linha    De    Para   fdir(MW)   frev(MW)   fliq(MW)   Limite(MW)")
        print(np.column_stack([
            np.arange(1, NLIN + 1), BUSID[SB], BUSID[EB], FDIR_MW, FREV_MW, FLIQ_MW, FLIM * PB
        ]))
        print(" ")
        print("----------DADOS DAS BARRAS------------")
        print("   Barra    Teta(rad)    Teta(graus)    Lambda")
        if lbd_BUS is not None:
            print(np.column_stack([BUSID, THETA, THETA_GRAUS, lbd_BUS]))
        else:
            print(np.column_stack([BUSID, THETA, THETA_GRAUS]))

        if sens_linha is not None:
            print(" ")
            print("Sensibilidade de investimento das linhas")
            print("   Linha    mu_fdir    mu_frev    sens_linha    custo    indice")
            print(np.column_stack([
                    np.arange(1, NLIN + 1), sens_fdir, sens_frev, sens_linha, CLINE, indice_invest
                ]))
        
        #---------------------------------------------------------
        #----------Impressão Visual dos Multiplicadores-----------
        #---------------------------------------------------------
        if verbose:
            print("\n" + "="*50)
            print(" RELATÓRIO DE PREÇOS-SOMBRA E MULTIPLICADORES")
            print("="*50)
            
            # Angulos:
            print("\nÂngulos:")
            for i in range(NBAR):
                print(f"  ang{i+1}: {THETA[i] + 0.0:.4f} rad  ({THETA_GRAUS[i] + 0.0:.2f} graus)")
            
            # Fluxos nas linhas e seus limites:
            print("\nFluxos nas linhas (MW):")
            for j in range(NLIN):
                de = BUSID[SB[j]]
                para = BUSID[EB[j]]
                print(f"  L{j+1} ({de}->{para}): fdir={FDIR[j] + 0.0:.4f}  frev={FREV[j] + 0.0:.4f}  fluxo={FLIQ[j] + 0.0:.4f}  (limite: +/-{FLIM[j]*PB:.1f} MW / {FLIM[j]:.4f} p.u.)")
           
            # Geração dos geradores:
            print("\nGeração dos geradores (MW):")
            for g in range(NGER):
                barra = BUSID[BARPG[g]]
                print(f"  G{g+1} (barra {barra}): {PG_MW[g]:.6f} MW")
            
            # FOB:
            print(f"\nFunção objetivo (FOB): {FOB:.6f}")
            
            # Perdas por linha:
            perda_total_pu, perdas_linha_pu = calc_total_losses_pu(THETA, G, SB, EB)
            print("Perdas por linha (MW):")
            for j in range(NLIN):
                de = BUSID[SB[j]]
                para = BUSID[EB[j]]
                print(f"  L{j+1} ({de}->{para}): {perdas_linha_pu[j] + 0.0:.6f} p.u.   ({perdas_linha_pu[j]*PB + 0.0:.4f} MW)")
                print(f"  Total: {perda_total_pu + 0.0:.6f} p.u.   ({perda_total_pu*PB + 0.0:.4f} MW)")
            
            print("\nAlocacao de perdas por barra (MW):")
            for i in range(NBAR):
                carga_orig = PLOAD_base[i] * PB
                carga_corr = PLOAD[i] * PB
                perda_aloc = carga_corr - carga_orig
                print(f"  barra {BUSID[i]}: carga={carga_orig + 0.0:.4f} MW  + perdas={perda_aloc + 0.0:.4f} MW  = carga corrigida={carga_corr + 0.0:.4f} MW")
            
            
            if lbd_BUS is not None:
                print("\nPreços nodais / LMP ($/MWh):")
                for i in range(NBAR):
                    # Usamos + 0.0 para evitar imprimir "-0.000000"
                    print(f"  barra {BUSID[i]}: {lbd_BUS[i] + 0.0:.6f}")

            if lbd_EQ is not None:
                print("\nDual das equações de fluxo:")
                for j in range(NLIN):
                    de = BUSID[SB[j]]
                    para = BUSID[EB[j]]
                    # Os duals de fluxo começam após as NBAR equações de balanço nodal
                    val_fluxo = lbd_EQ[NBAR + j] + 0.000000 # Ajuste para evitar "-0.000000"
                    print(f"  L{j+1} ({de}->{para}): {val_fluxo:.6f}")

                print(f"\nDual da barra de referência: {lbd_EQ[-1] + 0.0:.6f}")

            if piup is not None and pilo is not None:
                print("\nPreço-sombra do limite de capacidade das linhas:")
                for j in range(NLIN):
                    de = BUSID[SB[j]]
                    para = BUSID[EB[j]]
                    v_fdir = sens_fdir[j] + 0.0 if sens_fdir is not None else 0.0
                    v_frev = sens_frev[j] + 0.0 if sens_frev is not None else 0.0
                    s_linha = sens_linha[j] + 0.0 if sens_linha is not None else 0.0
                    print(f"  L{j+1} ({de}->{para}): {s_linha:.6f}  (fdir={v_fdir:.6f} / frev={v_frev:.6f})")

                print("\nPreços-sombra dos limites dos geradores:")
                for g in range(NGER):
                    barra = BUSID[BARPG[g]]
                    val_min = pilo[idx["pg"]][g] + 0.0
                    val_max = piup[idx["pg"]][g] + 0.0
                    print(f"  G{g+1} (barra {barra}): min={val_min:.6f}  max={val_max:.6f}")
                    
            if indice_invest is not None:
                print("\nÍndice benefício/custo (indice_invest):")
                for j in range(NLIN):
                    de = BUSID[SB[j]]
                    para = BUSID[EB[j]]
                    print(f"  L{j+1} ({de}->{para}): {indice_invest[j] + 0.0:.6f}")

    return {
        "CX": CX, "AX": AX, "BX": BX, "Vlb": Vlb, "Vub": Vub, "bounds": bounds,
        "solution": Vp, "FOB": FOB, "theta_rad": THETA, "theta_deg": THETA_GRAUS,
        "fdir_pu": FDIR, "frev_pu": FREV, "fliq_pu": FLIQ, "fdir_MW": FDIR_MW,
        "frev_MW": FREV_MW, "fliq_MW": FLIQ_MW, "pg_pu": PG, "pg_MW": PG_MW,
        "lbd_BUS": lbd_BUS, "lbd_EQ": lbd_EQ, "pilo": pilo, "piup": piup,
        "sens_fdir": sens_fdir, "sens_frev": sens_frev, "sens_linha": sens_linha,
        "indice_invest": indice_invest, "dados": dados, "idx": idx, "solver_result": res,
        "PLOAD_usado_pu": PLOAD, "PLOAD_usado_MW": PLOAD * PB,
    }


def OPF_Final_com_perdas_distribuidas(
    DBAR, DLIN, DGER, 
    PB=100.0, 
    penalidade_pg=0.001, 
    line_costs=None, 
    tol=1e-8, max_iter=50, verbose=True
):
    """
    Resolve a Parte C com perdas totais iterativas:
    - resolve o LP
    - calcula Pperda_total fora do solver
    - adiciona a perda apenas na barra de referência
    - repete até convergência
    """
    # dados fixos do sistema
    dados = inpdat_final(DBAR, DLIN, DGER, PB=PB, line_costs=line_costs)
    PLOAD_base = dados["PLOAD"].copy()
    G = dados["G"]
    SB = dados["SB"]
    EB = dados["EB"]
    NLIN = dados["NLIN"]

    # chute inicial: sem perdas
    PLOAD_eff = PLOAD_base.copy()
    historico = []
    perda_total_anterior = None
    resultado = None

    
    # ==================================================
    # ========== PROCESSO ITERATIVO DE PERDAS ==========
    # ==================================================
    # processo iterativo com inclusão de perdas
    for k in range(max_iter):
        # resolve o LP com a carga efetiva desta iteração
        resultado = OPF_Final(
            DBAR,
            DLIN,
            DGER,
            PB=PB,
            penalidade_pg=penalidade_pg,
            line_costs=line_costs,
            PLOAD_override=PLOAD_eff,
            verbose=False
        )

        theta = resultado["theta_rad"]

        # calcula perdas totais com base nos ângulos atuais
        perda_total_pu, perdas_linha_pu = calc_total_losses_pu(theta, G, SB, EB)

        # monta a carga da próxima iteração
        PLOAD_novo = PLOAD_base.copy()
        #PLOAD_novo[BREF] += perda_total_pu

        # ==========================================================
        # DISTRIBUI AS PERDAS (Metade em cada extremidade da linha)
        # ==========================================================
        for j in range(NLIN):
            metade_perda = perdas_linha_pu[j] / 2.0
            PLOAD_novo[SB[j]] += metade_perda # Adiciona metade da perda na barra de origem da linha
            PLOAD_novo[EB[j]] += metade_perda # Adiciona metade da perda na barra de destino da linha

        if perda_total_anterior is None:
            erro = np.inf
        else:
            erro = abs(perda_total_pu - perda_total_anterior)
        
        # critério de convergência
        if perda_total_anterior is None:
            erro = np.inf
        else:
            erro = abs(perda_total_pu - perda_total_anterior)

        historico.append({
            "iter": k + 1,
            "perda_total_pu": perda_total_pu,
            "perda_total_MW": perda_total_pu * PB,
            "perdas_linha_pu": perdas_linha_pu.copy(),
            "perdas_linha_MW": perdas_linha_pu * PB,
            "PLOAD_eff_pu": PLOAD_novo.copy(),
            "PLOAD_eff_MW": PLOAD_novo * PB,
            "erro": erro,
        })

        if verbose:
            print(f"\nIteração {k+1}")
            print(f"Perda total = {perda_total_pu:.10f} pu = {perda_total_pu * PB:.6f} MW")
            print(f"Erro = {erro}")

        if erro < tol:
            PLOAD_eff = PLOAD_novo
            break

        PLOAD_eff = PLOAD_novo
        perda_total_anterior = perda_total_pu

    else:
        raise RuntimeError(
            f"O processo iterativo de perdas não convergiu em {max_iter} iterações."
        )

    # resolve uma última vez com a carga convergida
    resultado_final = OPF_Final(
        DBAR,
        DLIN,
        DGER,
        PB=PB,
        penalidade_pg=penalidade_pg,
        line_costs=line_costs,
        PLOAD_override=PLOAD_eff,
        verbose=verbose
    )

    # recalcula perdas com a solução final
    theta_final = resultado_final["theta_rad"]
    perda_total_pu, perdas_linha_pu = calc_total_losses_pu(theta_final, G, SB, EB)

    resultado_final["perda_total_pu"] = perda_total_pu
    resultado_final["perda_total_MW"] = perda_total_pu * PB
    resultado_final["perdas_linha_pu"] = perdas_linha_pu
    resultado_final["perdas_linha_MW"] = perdas_linha_pu * PB
    resultado_final["PLOAD_base_pu"] = PLOAD_base
    resultado_final["PLOAD_base_MW"] = PLOAD_base * PB
    resultado_final["PLOAD_eff_pu"] = PLOAD_eff
    resultado_final["PLOAD_eff_MW"] = PLOAD_eff * PB
    resultado_final["historico_iteracoes"] = historico

    if verbose:
        print("\n========== RESULTADOS FINAIS DO OPF COM PERDAS DISTRIBUÍDAS ==========")
        print("Carga original total (MW):", np.sum(resultado_final["PLOAD_base_MW"]))
        print("Carga efetiva total (MW):", np.sum(resultado_final["PLOAD_eff_MW"]))
        print("Geração total (MW):", np.sum(resultado_final["pg_MW"]))
        print(f"Perda total do sistema: {perda_total_pu:.10f} pu")
        print(f"Perda total do sistema: {perda_total_pu * PB:.6f} MW")
        print("Perdas por linha (MW):")
        print(perdas_linha_pu * PB)
        print(f"Convergiu em {len(resultado_final['historico_iteracoes'])} iterações.")
        print("==================================================================")
        
    return resultado_final

#-------------------------------------------------------------
#------------ Exemplo de uso com o sistema B3 ---------------
#-------------------------------------------------------------
if __name__ == "__main__":
    #---------------- Rodar o OPF com os dados do B3 ----------------
    # OPF (Optimization Power Flow) é um problema de otimização que busca determinar a melhor forma de operar um sistema elétrico de potência, minimizando custos ou perdas, enquanto satisfaz as restrições físicas e operacionais do sistema. 
    # O código abaixo executa o OPF usando a função definida acima, com os dados do sistema em questão.
    resultado = OPF_Final_com_perdas_distribuidas(
        DBAR,
        DLIN,
        DGER,
        PB=100.0,
        penalidade_pg=0.001,
        tol=1e-8,
        max_iter=50,
        verbose=True
    )
    
    # PLOTS:
    # run_all_essential_plots(resultado)
    run_big_dashboard(resultado, pb=100.0)
    #pasta_saida = save_opf_results(resultado, output_dir="opf_results", case_name="b6l8")
    #print("Resultados salvos em:", pasta_saida)