from datetime import datetime
import numpy as np
from scipy.optimize import linprog
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# Arquivo de dados no novo formato:
# - DGER: geradores reais + fictícios no mesmo bloco [barra, pmin, pmax, custo]
# - DGW : geradores eólicos com custo [barra, pgwmin, pgwmax, custo]
from B6L8_wWind import DBAR, DLIN, DGER, DGW, SCENARIO_CONFIG
#from ieee118 import DBAR, DLIN, DGER, DGW, SCENARIO_CONFIG

# ============================================================
# CONFIGURAÇÕES DOS CENÁRIOS
# Variáveis GLOBAIS para controle de cenários, extraídas do SCENARIO_CONFIG
# ============================================================
NC = SCENARIO_CONFIG["num_scenarios"]
PB = SCENARIO_CONFIG["base_power_MW"]

# Eólica: distribuição Weibull. :contentReference[oaicite:7]{index=7}
WEIBULL_SCALE = SCENARIO_CONFIG["weibull_scale"]
WEIBULL_SHAPE = SCENARIO_CONFIG["weibull_shape"]

# Custos
CUSTO_CORTE_VENTO = SCENARIO_CONFIG["custo_corte_vento"]
TOL = SCENARIO_CONFIG["tol"]
MAX_ITER = SCENARIO_CONFIG["max_iter"]

# Quantos geradores reais existem no início de DGER
# Para o B6L8 discutido, são 3 reais e o restante fictícios
NGER_REAIS = SCENARIO_CONFIG["num_real_generators"]
NGER_FICT = SCENARIO_CONFIG["num_fict_generators"]


# ============================================================
# INPUTDATA ADAPTADO
# ============================================================
def inpdat_opf(DBAR, DLIN, DGER, DGW, PB=100.0):
    NBAR, _ = DBAR.shape
    NLIN, _ = DLIN.shape
    NGER, _ = DGER.shape
    NGW, _ = DGW.shape if DGW.size > 0 else (0, 0)

    BUSID = DBAR[:, 0].astype(int)
    TIPO = DBAR[:, 1].astype(int)

    bus_to_pos = {bus_id: pos for pos, bus_id in enumerate(BUSID)}

    # --------------------------------------------------
    # LEITURA DAS CARGAS A PARTIR DE DBAR
    # Equivalente ao slide de modificação do inpdat
    # PLOAD(i) = DBAR(i,10)/PB
    # QLOAD(i) = DBAR(i,11)/PB
    # QBAR(i)  = DBAR(i,12)/PB
    # QLOAD(i) = QLOAD(i) - QBAR(i)
    # PLOAD_b = PLOAD
    # QLOAD_b = QLOAD
    # --------------------------------------------------
    PLOAD = DBAR[:, 9] / PB
    QLOAD = DBAR[:, 10] / PB
    QBAR  = DBAR[:, 11] / PB

    QLOAD = QLOAD - QBAR

    PLOAD_b = PLOAD.copy()
    QLOAD_b = QLOAD.copy()

    # barra de referência
    BREF = None
    for i in range(NBAR):
        if TIPO[i] == 2:
            BREF = i
            break
    if BREF is None:
        raise ValueError("Nenhuma barra slack/tipo 2 encontrada.")

    # linhas
    SB = np.zeros(NLIN, dtype=int)
    EB = np.zeros(NLIN, dtype=int)
    r = np.zeros(NLIN)
    x = np.zeros(NLIN)
    G = np.zeros(NLIN)
    Bor = np.zeros(NLIN)
    FLIM = np.zeros(NLIN)

    for i in range(NLIN):
        de_bus = int(DLIN[i, 0])
        para_bus = int(DLIN[i, 1])

        SB[i] = bus_to_pos[de_bus]
        EB[i] = bus_to_pos[para_bus]

        r[i] = DLIN[i, 2] / 100.0
        x[i] = DLIN[i, 3] / 100.0

        denom = r[i] ** 2 + x[i] ** 2
        G[i] = r[i] / denom
        Bor[i] = 1.0 / x[i]
        FLIM[i] = DLIN[i, 9] / PB

    # geradores convencionais / fictícios
    BARPG = np.zeros(NGER, dtype=int)
    PGMIN = np.zeros(NGER)
    PGMAX = np.zeros(NGER)
    CPG = np.zeros(NGER)

    for i in range(NGER):
        ger_bus = int(DGER[i, 0])
        BARPG[i] = bus_to_pos[ger_bus]
        PGMIN[i] = DGER[i, 1] / PB
        PGMAX[i] = DGER[i, 2] / PB
        CPG[i] = DGER[i, 3]

    # eólicos
    # Novo formato esperado:
    # DGW = [barra, pgwmin, pgwmax, custo]
    # Para robustez, também aceitamos o formato antigo com 3 colunas.
    NOGW = np.zeros(NGW, dtype=int)
    PGWMIN = np.zeros(NGW)
    PGWMAX = np.zeros(NGW)
    CPGW = np.zeros(NGW)

    for i in range(NGW):
        w_bus = int(DGW[i, 0])
        NOGW[i] = bus_to_pos[w_bus]
        PGWMIN[i] = DGW[i, 1] / PB
        PGWMAX[i] = DGW[i, 2] / PB
        CPGW[i] = DGW[i, 3] if DGW.shape[1] >= 4 else SCENARIO_CONFIG.get("custo_eolica", 0.0)

    return {
        "NBAR": NBAR,
        "NLIN": NLIN,
        "NGER": NGER,
        "NGW": NGW,
        "BUSID": BUSID,
        "TIPO": TIPO,
        "BREF": BREF,
        "PLOAD_b": PLOAD_b,
        "QLOAD_b": QLOAD_b,
        "SB": SB,
        "EB": EB,
        "r": r,
        "x": x,
        "G": G,
        "Bor": Bor,
        "FLIM": FLIM,
        "BARPG": BARPG,
        "PGMIN": PGMIN,
        "PGMAX": PGMAX,
        "CPG": CPG,
        "NOGW": NOGW,
        "PGWMIN": PGWMIN,
        "PGWMAX": PGWMAX,
        "CPGW": CPGW,
    }


def print_system_overview(data):
    PLOAD_base = data["PLOAD_b"]
    PGMIN = data["PGMIN"]
    PGMAX = data["PGMAX"]

    NG = data["NGER"]
    NGW = data["NGW"]
    NB = data["NBAR"]
    NL = data["NLIN"]

    total_load = float(np.sum(PLOAD_base))

    total_pg_min = float(np.sum(PGMIN[:NGER_REAIS]))
    total_pg_max = float(np.sum(PGMAX[:NGER_REAIS]))

    total_deficit_max = float(np.sum(PGMAX[NGER_REAIS:])) if NG > NGER_REAIS else 0.0

    total_wind_max = float(np.sum(data["PGWMAX"])) if NGW > 0 else 0.0

    print("\n================ SYSTEM OVERVIEW ================")

    print(f"Barras: {NB}")
    print(f"Linhas: {NL}")

    print("\nCarga:")
    print(f"Total carga base [MW]: {PB*total_load:.2f}")

    print("\nGeração convencional:")
    print(f"Geração mínima total [MW]: {PB*total_pg_min:.2f}")
    print(f"Geração máxima total [MW]: {PB*total_pg_max:.2f}")

    print("\nGeração eólica:")
    print(f"Capacidade eólica instalada [MW]: {PB*total_wind_max:.2f}")

    print("\nDéficit (corte de carga):")
    print(f"Déficit máximo permitido [MW]: {PB*total_deficit_max:.2f}")

    print("\nCapacidade total possível:")
    print(f"Convencional + eólica [MW]: {PB*total_pg_max + PB*total_wind_max:.2f}")

    margem = total_pg_max + total_wind_max - total_load

    print("\nMargem de atendimento:")
    print(f"Margem de potência [MW]: {PB*margem:.2f}")

    if margem < 0:
        print("⚠ Sistema pode precisar de corte de carga")

    print("=================================================\n")

# ============================================================
# CÁLCULO DE PERDAS E FLUXOS
# ============================================================
def calc_losses_and_flows(theta, G, Bor, SB, EB):
    delta_theta = theta[SB] - theta[EB]
    perdas_linha = G * (delta_theta ** 2)
    fluxo = Bor * delta_theta
    return perdas_linha, fluxo


# ============================================================
# GERAÇÃO DE CENÁRIOS
# ============================================================
def generate_load_scenario(PLOAD_b, QLOAD_b, rng, mode=None, config=None):
    if config is None:
        config = SCENARIO_CONFIG

    if mode is None:
        mode = config.get("load_distribution", "normal")

    nbus = len(PLOAD_b)

    fator_min = config.get("fator_min", 0.70)
    fator_max = config.get("fator_max", 1.30)

    if mode == "uniform":
        ag = config["ag"]
        bg = config["bg"]
        ac = config["ac"]
        bc = config["bc"]

        # versão mais física: global escalar
        rg = ag + (bg - ag) * rng.random()
        rc = ac + (bc - ac) * rng.random(nbus)

        r = rg + rc

    elif mode == "normal":
        mu_geral = config["mu_geral"]
        sigma_geral = config["sigma_geral"]
        mu_local = config["mu_local"]
        sigma_local = config["sigma_local"]

        fg = rng.normal(mu_geral, sigma_geral)
        fl = rng.normal(mu_local, sigma_local, size=nbus)

        r = (1.0 + fg) * (1.0 + fl)
    else:
        raise ValueError(f"Distribuição de carga inválida: {mode}")

    r = np.clip(r, fator_min, fator_max)

    PLOAD = PLOAD_b * r
    QLOAD = QLOAD_b * r

    return PLOAD, QLOAD, r

def generate_wind_scenario(PGWMAX, rng, config=None):
    """
    Geração eólica com Weibull:
    PGW = R * PGWmax, com R gerado por Weibull.
    """
    if config is None:
        config = SCENARIO_CONFIG
        
    if len(PGWMAX) == 0:
        return np.zeros(0)

    WEIBULL_SCALE = config["weibull_scale"]
    WEIBULL_SHAPE = config["weibull_shape"]

    R = WEIBULL_SCALE * rng.weibull(WEIBULL_SHAPE, size=len(PGWMAX))

    R = np.clip(R, 0.0, 1.0)

    PGW = R * PGWMAX

    return PGW


# ============================================================
# MONTAGEM DO MODELO OPF COM CENÁRIOS E PCW
# ============================================================
def build_model_scenario(data, PLOAD_scn, PGW_scn, theta_prev=None):
    """_summary_
    This function builds the linear programming model for the OPF problem considering a specific load scenario (PLOAD_scn) and 
    a specific wind generation scenario (PGW_scn). 
    It also takes into account the previous voltage angles (theta_prev) to calculate losses and flows, 
    which are used in the constraints of the model.
    
    # Implementação da Equação nodal com eólica:
    # PG + Deficit - Bbus*theta - PCW = PLOAD - PGW
    # onde:
    # - Deficit é modelado por geradores fictícios de alto custo
    # - PGW reduz a carga líquida da barra
    # - PCW é variável de curtailment com custo intermediário
    
    Args:
        data (_type_): _description_
        PLOAD_scn (_type_): _description_
        PGW_scn (_type_): _description_
        theta_prev (_type_, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    NBAR = data["NBAR"]
    NLIN = data["NLIN"]
    NGER = data["NGER"]
    NGW = data["NGW"]

    BREF = data["BREF"]
    SB = data["SB"]
    EB = data["EB"]
    G = data["G"]
    Bor = data["Bor"]
    FLIM = data["FLIM"]

    BARPG = data["BARPG"]
    PGMIN = data["PGMIN"]
    PGMAX = data["PGMAX"]
    # CPG = data["CPG"]

    NOGW = data["NOGW"]
    # CPGW = data["CPGW"]

    if theta_prev is None:
        theta_prev = np.zeros(NBAR)

    # Mantemos o cálculo de perdas e fluxos apenas para análise posterior e
    # acompanhamento iterativo. Porém, a formulação do PL abaixo segue de forma
    # mais fiel o slide: balanço nodal sem termo explícito de perdas no lado
    # direito e FOB baseada em hierarquia de custos.
    perdas_prev, fluxo_prev = calc_losses_and_flows(theta_prev, G, Bor, SB, EB)

    # carga líquida = carga do cenário - geração eólica disponível
    PNET = PLOAD_scn.copy()
    for i in range(NGW):
        PNET[NOGW[i]] -= PGW_scn[i] # É a mesma coisa que PNET[NOGW[i]] = PNET[NOGW[i]] - PGW_scn[i]

    # índices
    i_pg_ini = 0
    i_pg_fim = NGER

    i_theta_ini = i_pg_fim
    i_theta_fim = i_theta_ini + NBAR

    i_pcw_ini = i_theta_fim
    i_pcw_fim = i_pcw_ini + NGW

    NVAR = NGER + NBAR + NGW

    idx = {
        "pg": slice(i_pg_ini, i_pg_fim), # inclui geradores reais + fictícios
        "theta": slice(i_theta_ini, i_theta_fim), # ângulos de todas as barras
        "pcw": slice(i_pcw_ini, i_pcw_fim), # variáveis de corte de vento para cada gerador eólico
    }

    # ============================================================
    # FUNÇÃO OBJETIVO - HIERARQUIA DE CUSTOS DO SLIDE
    # min Σ(C_PG * PG) + Σ(C_PCW * PCW)
    #
    # Como os geradores fictícios já estão inseridos em DGER com custo alto,
    # o termo Σ(C_Deficit * Deficit) é naturalmente representado pelo subconjunto
    # dos PG fictícios.
    # ============================================================
    """
    MINIMIZAÇÃO DE CUSTOS:
    CX = np.zeros(NVAR)

    # 1) Toda geração em DGER entra com seu custo próprio
    #    - reais: custo baixo/moderado
    #    - fictícios (deficit): custo alto
    CX[idx["pg"]] = CPG

    # 2) Corte de vento: custo intermediário
    if NGW > 0:
        if len(CPGW) == NGW:
            CX[idx["pcw"]] = CPGW
        else:
            CX[idx["pcw"]] = CUSTO_CORTE_VENTO
    """
    """MININIZAÇÃO DE PERDAS:
    """
    
    # ============================================================
    # FUNÇÃO OBJETIVO
    # min Σ(1 * PG_real) + Σ(400 * PG_fict) + Σ(60 * PCW)
    # ------------------------------------------------------------
    # PG_real  = geração convencional real
    # PG_fict  = geradores fictícios que representam corte de carga
    # PCW      = corte de vento
    # ============================================================
    CX = np.zeros(NVAR)

    custos_pg = np.ones(NGER, dtype=float)       # O que faz: gera custo 1 para os geradores reais

    # geradores fictícios de corte de carga
    if NGER > NGER_REAIS:
        custos_pg[NGER_REAIS:] = 400.0           # O que faz: gera custo 400 para os geradores fictícios de déficit

    CX[idx["pg"]] = custos_pg

    # corte de vento
    if NGW > 0:
        CX[idx["pcw"]] = 60.0                     # O que faz: gera custo 60 para o corte de vento, conforme sugerido no slide
    
    # ============================================================
    # RESTRIÇÕES DE IGUALDADE
    # Balanço nodal com eólica e corte de vento:
    # PG + Deficit - Bbus*theta - PCW = PLOAD - PG
    # onde:
    # - Deficit é modelado por geradores fictícios de alto custo
    # - PGW reduz a carga líquida da barra (já incorporado em PNET)
    # - PCW é variável de curtailment com custo intermediário
    # ============================================================
    NEQ = NBAR + 1
    AX = np.zeros((NEQ, NVAR))
    BX = np.zeros(NEQ)

    # geradores + déficit (fictícios)
    for g in range(NGER):
        barra_g = BARPG[g]
        AX[barra_g, i_pg_ini + g] = 1.0                                       # O que faz: adiciona o termo de geração do gerador g à barra correspondente (barra_g) na matriz de coeficientes AX. Isso representa a contribuição do gerador g para o balanço de potência na barra barra_g.
        # Isso é o mesmo que: AX[barra_g, i_pg_ini + g]

    # matriz Bbus
    Bbus = np.zeros((NBAR, NBAR))
    for j in range(NLIN):
        de = SB[j]
        para = EB[j]
        gama = Bor[j]
        Bbus[de, de] += gama                                                  # O que faz: adiciona o termo de susceptância da linha à barra de origem (de)
        Bbus[para, para] += gama                                              # Isso é o mesmo que: Bbus[para, para] = Bbus[para, para] + gama
        Bbus[de, para] -= gama
        Bbus[para, de] -= gama

    # termo de ângulo
    AX[0:NBAR, idx["theta"]] = -Bbus
    
    # ============= CARGA LÍQUIDA (CENÁRIO DE CARGA - GERAÇÃO EÓLICA) ====   
    BX[0:NBAR] = PNET

    # ============= CORTE DE VENTO =======================================
    for i in range(NGW):
        bus = NOGW[i]
        AX[bus, i_pcw_ini + i] = -1.0

    # barra de referência
    AX[NBAR, i_theta_ini + BREF] = 1.0
    BX[NBAR] = 0.0
    
    # ============================================================
    # RESTRIÇÕES DE DESIGUALDADE
    # Fluxo limitado por FLIM: -FLIM <= f_ij <= FLIM, com f_ij = Bor*(theta_de - theta_para)
    # Para cada linha, isso gera duas desigualdades:
    # 1) +f_ij <= FLIM  <=>  Bor*(theta_de - theta_para) <= FLIM
    # 2) -f_ij <= FLIM  <=>  Bor*(theta_para - theta_de) <= FLIM
    # ============================================================

    Ai = np.zeros((2 * NLIN, NVAR))
    Bi = np.zeros(2 * NLIN)
    
    # Para cada linha, adicionamos as duas desigualdades correspondentes ao fluxo limitado,
    # porque o fluxo pode ser positivo ou negativo, e ambos os casos precisam ser considerados para 
    # garantir que o fluxo em cada linha não exceda o limite FLIM em nenhuma direção.
    for j in range(NLIN):
        de = SB[j]
        para = EB[j]

        # +f_ij <= FLIM
        Ai[2 * j, i_theta_ini + de] = +Bor[j] 
        Ai[2 * j, i_theta_ini + para] = -Bor[j]
        Bi[2 * j] = FLIM[j]

        # -f_ij <= FLIM  <=>  f_ij >= -FLIM
        Ai[2 * j + 1, i_theta_ini + de] = -Bor[j]
        Ai[2 * j + 1, i_theta_ini + para] = +Bor[j]
        Bi[2 * j + 1] = FLIM[j]

    # bounds
    Vlb = np.zeros(NVAR)
    Vub = np.zeros(NVAR)

    # PG
    Vlb[idx["pg"]] = PGMIN
    Vub[idx["pg"]] = PGMAX

    # theta
    Vlb[idx["theta"]] = -np.pi
    Vub[idx["theta"]] = +np.pi

    # PCW: 0 <= PCW <= PGW_disponível
    if NGW > 0:
        Vlb[idx["pcw"]] = 0.0
        Vub[idx["pcw"]] = PGW_scn

    bounds = [(Vlb[k], Vub[k]) for k in range(NVAR)]

    return {
        "CX": CX,
        "AX": AX,
        "BX": BX,
        "Ai": Ai,
        "Bi": Bi,
        "bounds": bounds,
        "idx": idx,
        "theta_prev": theta_prev,
        "PNET": PNET,
        "PGW_scn": PGW_scn,
        "perdas_prev": perdas_prev,
        "fluxo_prev": fluxo_prev,
        "Bbus": Bbus,
    }


# ============================================================
# RESOLUÇÃO DO OPF DE UM CENÁRIO
# ============================================================
def solve_opf_scenario(data, PLOAD_scn, PGW_scn, tol=1e-8, max_iter=50):
    theta_prev = np.zeros(data["NBAR"])
    theta_old = None
    final = None

    for k in range(max_iter):
        model = build_model_scenario(data, PLOAD_scn, PGW_scn, theta_prev)

        res = linprog(
            c=model["CX"],
            A_ub=model["Ai"],
            b_ub=model["Bi"],
            A_eq=model["AX"],
            b_eq=model["BX"],
            bounds=model["bounds"],
            method="highs"
        )

        if not res.success:
            raise RuntimeError(f"linprog falhou: status={res.status} | {res.message}")

        idx = model["idx"]
        x = res.x

        PG = x[idx["pg"]] # geração real + fictícia (corte de carga), importante para análise de quanto cada tipo de geração contribui para o atendimento da carga em cada cenário
        THETA = x[idx["theta"]] # ângulos de todas as barras, importantes para análise de como a tensão se distribui no sistema e onde ocorrem os maiores desvios angulares
        PCW = x[idx["pcw"]] # variáveis de corte de vento, importantes para análise de quanto vento foi cortado em cada cenário

        perdas_linha, fluxo = calc_losses_and_flows(
            THETA, data["G"], data["Bor"], data["SB"], data["EB"]
        )
        perdas_totais = np.sum(perdas_linha)

        if theta_old is None:
            erro = np.inf
        else:
            erro = np.max(np.abs(THETA - theta_old))
        
        # ADICIONAIS PARA ANÁLISE DETALHADA DE CUSTOS E PERDAS
        # cálculo de custos detalhado para análise posterior
        # separa geradores reais e fictícios
        idx_real = np.arange(NGER_REAIS)
        idx_fict = np.arange(NGER_REAIS, data["NGER"])

        # custo da geração real: $ = custo_unitário_real (1 $/MW) * quantidade_geração_real (MW)
        custo_pg_real = float(np.sum(PG[idx_real] * 1.0))

        # Custo em unidade: $ = custo_unitário_corte_carga (400 $/MW) * quantidade_corte_carga (MW)
        custo_corte_carga = (
            float(np.sum(PG[idx_fict] * 400.0))
            if len(idx_fict) > 0 else 0.0
        )
        
        # Custo em unidade: $ = custo_unitário_corte_vento (60 $/MW) * quantidade_corte_vento (MW)
        custo_corte_vento = (
            float(np.sum(PCW * 60.0))
            if len(PCW) > 0 else 0.0
        )

        # custo_pg agora representa apenas geração convencional
        custo_pg = custo_pg_real
        # custo associado ao corte de vento (mantido para compatibilidade)
        custo_pcw = custo_corte_vento   
        
        final = {
            "res": res,
            "PG": PG,
            "THETA": THETA,
            "PCW": PCW,
            "perdas_linha": perdas_linha, # perdas por linha, importante para análise de onde ocorrem as perdas no sistema
            "fluxo": fluxo,
            "perdas_totais": perdas_totais, # perdas totais do sistema, indicador chave de eficiência
            "erro": erro,
            "model": model,
            "custo_pg": custo_pg,
            "custo_pcw": custo_pcw,
            "custo_total": float(res.fun),
            
            "custo_pg_real": custo_pg_real,
            "custo_corte_carga": custo_corte_carga,
            "custo_corte_vento": custo_corte_vento,
        }

        if erro < tol:
            break

        theta_old = THETA.copy()
        theta_prev = THETA.copy()

    if final is None:
        raise RuntimeError("Nenhuma solução foi produzida.")

    # Cálculo de variáveis duais (lambda) para análise posterior
    lbd_bus = None
    lbd_cv = None

    res = final["res"]
    if hasattr(res, "eqlin") and res.eqlin is not None and res.eqlin.marginals is not None:
        lbd_bus = -np.array(res.eqlin.marginals[:data["NBAR"]])

    if hasattr(res, "ineqlin") and res.ineqlin is not None and res.ineqlin.marginals is not None:
        marg = -np.array(res.ineqlin.marginals)
        if len(marg) == 2 * data["NLIN"]:
            lbd_cv = np.maximum(np.abs(marg[0::2]), np.abs(marg[1::2]))
        else:
            lbd_cv = marg

    final["lbd_bus"] = lbd_bus
    final["lbd_cv"] = lbd_cv

    return final


# ============================================================
# LOOP DE CENÁRIOS + ANÁLISE
# ============================================================
def run_scenario_study(DBAR, DLIN, DGER, DGW, PB=100.0, Nc=1000, seed=123):
    """
    This function runs a scenario study for the OPF problem with wind generation. 
    It generates multiple load and wind scenarios, solves the OPF for each scenario, 
    and collects results such as costs, losses, load shedding, wind curtailment, line flows, and dual variables. 
    Finally, it summarizes the results across all scenarios.
    Args:
        DBAR: Data for buses
        DLIN: Data for lines
        DGER: Data for generators
        DGW: Data for wind generators
        PB: Base power for per unit normalization
        Nc: Number of scenarios
        seed: Random seed for reproducibility    
    """
    data = inpdat_opf(DBAR, DLIN, DGER, DGW, PB=PB)
    rng = np.random.default_rng(seed)

    NBAR = data["NBAR"]
    NLIN = data["NLIN"]
    NGER = data["NGER"]
    NGW = data["NGW"]

    idx_real = np.arange(NGER_REAIS)
    idx_fict = np.arange(NGER_REAIS, NGER)

    results = []

    MVu = np.zeros(len(idx_real))
    MVd = np.zeros(len(idx_real))
    PG_ant_real = None

    all_fob = []
    all_losses = []
    all_corte_carga = []
    all_corte_vento = []
    all_fluxos = []
    all_lambda_linhas = []
    all_pg_real = []
    all_custo_pg_real = []
    all_custo_corte_carga = []
    all_custo_corte_vento = []

    for ic in range(Nc):
        # Cenário de carga
        PLOAD_scn, QLOAD_scn, fator_carga = generate_load_scenario(
            data["PLOAD_b"], 
            data["QLOAD_b"], 
            rng, 
            config=SCENARIO_CONFIG
        )

        # Cenário eólico
        PGW_scn = generate_wind_scenario(
            data["PGWMAX"], 
            rng, 
            config=SCENARIO_CONFIG
        )
        # =========================================
        # RESOLVENDO O OPF PARA O CENÁRIO GERADO
        # =========================================
        sol = solve_opf_scenario(
            data, 
            PLOAD_scn, 
            PGW_scn, 
            tol=TOL, 
            max_iter=MAX_ITER
        )

        # EXTRAÇÃO DE VARIÁVEIS PARA ANÁLISE
        # Nesta parte, extraímos as variáveis de interesse da solução do OPF para análise detalhada.

        PG = sol["PG"]
        PG_real = PG[idx_real] # Geração Real
        PG_fict = PG[idx_fict] if len(idx_fict) > 0 else np.zeros(0) # Corte de Carga (Geração Fictícia)
        
        corte_carga = np.sum(PG_fict) * PB
        corte_vento = np.sum(sol["PCW"]) * PB
        fob = sol["res"].fun
        perdas_mw = sol["perdas_totais"] * PB # perdas totais em MW são as perdas que ocorrem no sistema, calculadas a partir dos ângulos de tensão e da matriz Bbus. Elas representam a energia dissipada nas linhas devido à resistência, e são um indicador importante da eficiência do sistema.
        fluxo_mw = sol["fluxo"] * PB

        # ====================================================
        # ============= RAMPAS DE GERADORES REAIS ============
        # ====================================================
        if PG_ant_real is None:
            ramp_up = np.zeros(len(idx_real))
            ramp_down = np.zeros(len(idx_real))
        else:
            dif = (PG_real - PG_ant_real) * PB
            ramp_up = np.maximum(dif, 0.0)
            ramp_down = np.maximum(-dif, 0.0)

            MVu = np.maximum(MVu, ramp_up)
            MVd = np.maximum(MVd, ramp_down)

        PG_ant_real = PG_real.copy()

        all_fob.append(fob)
        all_losses.append(perdas_mw)
        all_corte_carga.append(corte_carga)
        all_corte_vento.append(corte_vento)
        all_fluxos.append(fluxo_mw)
        all_pg_real.append(PG_real * PB)
        all_custo_pg_real.append(sol.get("custo_pg_real", 0.0))
        all_custo_corte_carga.append(sol.get("custo_corte_carga", 0.0))
        all_custo_corte_vento.append(sol.get("custo_corte_vento", 0.0))

        if sol["lbd_cv"] is not None:
            all_lambda_linhas.append(sol["lbd_cv"])
        else:
            all_lambda_linhas.append(np.zeros(NLIN))

        results.append({
            "cenario": ic + 1,
            "fator_carga": fator_carga,
            "PLOAD_scn_MW": PLOAD_scn * PB,
            "QLOAD_scn_MVAr": QLOAD_scn * PB,
            "PGW_scn_MW": PGW_scn * PB,
            "PG_real_MW": PG_real * PB,
            "PG_total_MW": PG * PB,
            "PCW_MW": sol["PCW"] * PB,
            "corte_carga_MW": corte_carga,
            "corte_vento_MW": corte_vento,
            "FOB": fob,
            "custo_pg": sol.get("custo_pg"),
            "custo_pcw": sol.get("custo_pcw"),
            "custo_pg_real": sol.get("custo_pg_real"),
            "custo_corte_carga": sol.get("custo_corte_carga"),
            "custo_corte_vento": sol.get("custo_corte_vento"),
            "perdas_MW": perdas_mw,
            "fluxo_MW": fluxo_mw,
            "theta_rad": sol["THETA"],
            "theta_deg": sol["THETA"] * 180.0 / np.pi,
            "lambda_bus": sol["lbd_bus"],
            "lambda_linhas": sol["lbd_cv"],
            "ramp_up_MW": ramp_up,
            "ramp_down_MW": ramp_down,
            "model_inputs": sol["model"],     
        })
        

    # consolidação
    all_fluxos = np.array(all_fluxos)
    all_lambda_linhas = np.array(all_lambda_linhas)
    all_pg_real = np.array(all_pg_real)

    limite_mw = data["FLIM"] * PB
    violacoes = np.abs(all_fluxos) > (limite_mw + 1e-6)
    freq_violacao = violacoes.mean(axis=0)
    max_fluxo_abs = np.max(np.abs(all_fluxos), axis=0)
    lambda_medio_linhas = np.mean(all_lambda_linhas, axis=0)

    summary = {
        "FOB_media": float(np.mean(all_fob)),
        "FOB_std": float(np.std(all_fob)),
        "perdas_medias_MW": float(np.mean(all_losses)),
        "custo_pg_real_medio": float(np.mean(all_custo_pg_real)),
        "custo_corte_carga_medio": float(np.mean(all_custo_corte_carga)),
        "custo_corte_vento_medio": float(np.mean(all_custo_corte_vento)),
        "corte_carga_medio_MW": float(np.mean(all_corte_carga)),
        "corte_vento_medio_MW": float(np.mean(all_corte_vento)),
        "MVu_MW": MVu,
        "MVd_MW": MVd,
        "lambda_medio_linhas": lambda_medio_linhas,
        "freq_violacao_linhas": freq_violacao,
        "max_fluxo_abs_MW": max_fluxo_abs,
        "linha_mais_onerosa": int(np.argmax(lambda_medio_linhas) + 1),
        "linha_mais_violada": int(np.argmax(freq_violacao) + 1),
        "linha_maior_fluxo_abs": int(np.argmax(max_fluxo_abs) + 1),
        "limites_MW": limite_mw,
    }

    return {
        "data": data, # dados de entrada processados
        "results": results, # resultados detalhados de cada cenário
        "summary": summary, # resumo consolidado dos resultados
    }


# ============================================================
# RELATÓRIO
# ============================================================
def print_summary(study):
    summary = study["summary"]

    print("\n" + "=" * 70)
    print("RESUMO FINAL DO ESTUDO DE CENÁRIOS")
    print("=" * 70)
    print(f"FOB média                  : {summary['FOB_media']:.6f}")
    print(f"FOB desvio padrão          : {summary['FOB_std']:.6f}")
    print(f"Custo médio geração real   : {summary['custo_pg_real_medio']:.6f}")
    print(f"Custo médio corte carga    : {summary['custo_corte_carga_medio']:.6f}")
    print(f"Custo médio corte vento    : {summary['custo_corte_vento_medio']:.6f}")
    print(f"Corte de carga médio (MW)  : {summary['corte_carga_medio_MW']:.6f}")
    print(f"Corte de vento médio (MW)  : {summary['corte_vento_medio_MW']:.6f}")
    print(f"Perdas médias (MW)         : {summary['perdas_medias_MW']:.6f}")
    print(f"Linha mais onerosa         : {summary['linha_mais_onerosa']}")
    print(f"Linha mais violada         : {summary['linha_mais_violada']}")
    print(f"Linha com maior fluxo abs  : {summary['linha_maior_fluxo_abs']}")

    print("\nMVu por gerador real (MW):")
    print("  (Máxima rampa de subida observada para cada gerador real ao longo dos cenários)")
    for i, v in enumerate(summary["MVu_MW"], start=1):
        print(f"  G{i}: {v:.6f}")

    print("\nMVd por gerador real (MW):")
    print("  (Máxima rampa de descida observada para cada gerador real ao longo dos cenários)")
    for i, v in enumerate(summary["MVd_MW"], start=1):
        print(f"  G{i}: {v:.6f}")

    print("\nECONÔMICO = Ranking econômico das linhas (lambda médio) / (Linha mais Onerosa):")
    ranking_lambda = np.argsort(-summary["lambda_medio_linhas"])
    for pos in ranking_lambda:
        print(f"  Linha {pos+1}: {summary['lambda_medio_linhas'][pos]:.6f}")

    print("\nFÍSICO = Frequência de violação por linha (Linha mais Severa):")
    ranking_viol = np.argsort(-summary["freq_violacao_linhas"])
    for pos in ranking_viol:
        print(f"  Linha {pos+1}: {summary['freq_violacao_linhas'][pos]*100:.2f}%")

    print("\nMaior fluxo absoluto por linha (MW):")
    for i, val in enumerate(summary["max_fluxo_abs_MW"], start=1):
        print(f"  Linha {i}: {val:.6f} / limite {summary['limites_MW'][i-1]:.6f}")


def serialize_array(x):
    if x is None:
        return None
    return np.array(x).tolist()

def export_study_to_excel(study, filename="opf_scenarios_withWind_results.xlsx", save_first_model_only=False):
    results = study["results"]
    summary = study["summary"]

    # =========================================================
    # ABA 1: cenários
    # =========================================================
    rows = []
    for r in results:
        row = {
            "cenario": r["cenario"],
            "FOB": r["FOB"],
            "custo_pg_real": r.get("custo_pg_real"),
            "custo_corte_carga": r.get("custo_corte_carga"),
            "custo_corte_vento": r.get("custo_corte_vento"),
            "corte_carga_MW": r["corte_carga_MW"],
            "corte_vento_MW": r["corte_vento_MW"],
            "perdas_MW": r["perdas_MW"],
            "PLOAD_total_MW": float(np.sum(r["PLOAD_scn_MW"])),
            "QLOAD_total_MVAr": float(np.sum(r["QLOAD_scn_MVAr"])),
            "PGW_total_MW": float(np.sum(r["PGW_scn_MW"])),
            "PG_real_total_MW": float(np.sum(r["PG_real_MW"])),
            "PG_total_MW": float(np.sum(r["PG_total_MW"])),
            "fluxo_max_abs_MW": float(np.max(np.abs(r["fluxo_MW"]))),
            "ramp_up_max_MW": float(np.max(r.get("ramp_up_MW", np.zeros(1)))),
            "ramp_down_max_MW": float(np.max(r.get("ramp_down_MW", np.zeros(1)))),
            "fator_carga": serialize_array(r["fator_carga"]),
            "PCW_MW": serialize_array(r["PCW_MW"]),
            "lambda_bus": serialize_array(r["lambda_bus"]),
            "lambda_linhas": serialize_array(r["lambda_linhas"]),
        }
        rows.append(row)

    df_results = pd.DataFrame(rows)

    # =========================================================
    # ABA 2: resumo
    # =========================================================
    df_summary = pd.DataFrame({
        "metric": list(summary.keys()),
        "value": [serialize_array(v) if isinstance(v, (np.ndarray, list)) else v for v in summary.values()]
    })

    # =========================================================
    # ABA 3: inputs do modelo para TODOS os cenários
    # =========================================================
    model_rows = []
    targets = [results[0]] if save_first_model_only else results

    for r in targets:
        model = r.get("model_inputs", None)
        if model is None:
            continue

        model_rows.append({
            "cenario": r["cenario"],
            "nvar": len(model["CX"]) if model.get("CX") is not None else None,
            "neq": model["AX"].shape[0] if model.get("AX") is not None else None,
            "nineq": model["Ai"].shape[0] if model.get("Ai") is not None else None,
            "CX": serialize_array(model.get("CX")),
            "AX": serialize_array(model.get("AX")),
            "BX": serialize_array(model.get("BX")),
            "Ai": serialize_array(model.get("Ai")),
            "Bi": serialize_array(model.get("Bi")),
            "bounds": serialize_array(model.get("bounds")),
            "PNET": serialize_array(model.get("PNET")),
            "PGW_scn": serialize_array(model.get("PGW_scn")),
            "theta_prev": serialize_array(model.get("theta_prev")),
            "perdas_prev": serialize_array(model.get("perdas_prev")),
            "fluxo_prev": serialize_array(model.get("fluxo_prev")),
        })

    df_model = pd.DataFrame(model_rows)
    df_rank_linhas = build_line_violation_ranking_table(study)
    df_rampas = build_top_ramps_table(study, top_n=10)
    
    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df_results.to_excel(writer, sheet_name="cenarios", index=False)
        df_summary.to_excel(writer, sheet_name="summary", index=False)
        df_model.to_excel(writer, sheet_name="linprog_inputs", index=False)
        df_rank_linhas.to_excel(writer, sheet_name="ranking_linhas", index=False)
        df_rampas.to_excel(writer, sheet_name="rampas_top10", index=False)

    print(f"Arquivo Excel salvo com sucesso: {filename}")

# =============================================
# ============ DASHBOARDS DE RESULTADOS =======
# =============================================
def print_top_line_rankings(study, top_n=5):
    summary = study["summary"]

    lambda_med = np.array(summary["lambda_medio_linhas"])
    freq_viol = np.array(summary["freq_violacao_linhas"])
    max_flux = np.array(summary["max_fluxo_abs_MW"])
    limits = np.array(summary["limites_MW"])

    ranking = np.argsort(-lambda_med)[:top_n]

    print("\n" + "=" * 80)
    print(f"TOP {top_n} LINHAS - RANKING ECONÔMICO E FÍSICO")
    print("=" * 80)
    print(f"{'Linha':>8} {'Lambda Médio':>15} {'Freq Viol (%)':>15} {'Fluxo Máx (MW)':>15} {'Limite (MW)':>15}")
    for i in ranking:
        print(f"{i+1:>8} {lambda_med[i]:>15.6f} {100*freq_viol[i]:>15.2f} {max_flux[i]:>15.4f} {limits[i]:>15.4f}")
        
def plot_line_ranking_by_lambda(study):
    summary = study["summary"]

    lambda_med = np.array(summary["lambda_medio_linhas"])
    freq_viol = np.array(summary["freq_violacao_linhas"])
    max_flux = np.array(summary["max_fluxo_abs_MW"])
    limits = np.array(summary["limites_MW"])

    df_rank = pd.DataFrame({
        "linha": [f"Linha {i}" for i in range(1, len(lambda_med) + 1)],
        "lambda_medio": lambda_med,
        "freq_violacao_pct": freq_viol * 100.0,
        "fluxo_max_abs_MW": max_flux,
        "limite_MW": limits,
    }).sort_values("lambda_medio", ascending=True)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_rank["lambda_medio"],
        y=df_rank["linha"],
        orientation="h",
        customdata=np.stack([
            df_rank["freq_violacao_pct"],
            df_rank["fluxo_max_abs_MW"],
            df_rank["limite_MW"]
        ], axis=1),
        hovertemplate=(
            "Linha: %{y}<br>"
            "Lambda médio: %{x:.6f}<br>"
            "Freq. violação: %{customdata[0]:.2f}%<br>"
            "Fluxo máx abs: %{customdata[1]:.4f} MW<br>"
            "Limite: %{customdata[2]:.4f} MW<extra></extra>"
        ),
        name="Lambda médio"
    ))

    fig.update_layout(
        title="Ranking das Linhas por Coeficiente de Lagrange Médio",
        xaxis_title="Lambda Médio",
        yaxis_title="Linha",
        template="plotly_white",
        height=800,
        width=1800
    )

    fig.show()      

def build_line_violation_ranking_table(study):
    """Constrói um DataFrame com o ranking das linhas baseado no lambda médio, frequência de violação e fluxo máximo observado.
    """
    
    summary = study["summary"]

    lambda_med = np.array(summary["lambda_medio_linhas"])
    freq_viol = np.array(summary["freq_violacao_linhas"])
    max_flux = np.array(summary["max_fluxo_abs_MW"])
    limits = np.array(summary["limites_MW"])

    df_rank = pd.DataFrame({
        "linha": np.arange(1, len(lambda_med) + 1),
        "lambda_medio": lambda_med,
        "freq_violacao_pct": freq_viol * 100.0,
        "fluxo_max_abs_MW": max_flux,
        "limite_MW": limits,
        "excesso_max_MW": np.maximum(max_flux - limits, 0.0),
    })

    df_rank = df_rank.sort_values(by="lambda_medio", ascending=False).reset_index(drop=True)
    df_rank["ranking"] = np.arange(1, len(df_rank) + 1)

    return df_rank[[
        "ranking",
        "linha",
        "lambda_medio",
        "freq_violacao_pct",
        "fluxo_max_abs_MW",
        "limite_MW",
        "excesso_max_MW"
    ]]    

def print_scenario_extremes(study, top_n=10):
    results = study["results"]

    cortes = sorted(results, key=lambda r: r["corte_carga_MW"], reverse=True)[:top_n]
    ventos = sorted(results, key=lambda r: r["corte_vento_MW"], reverse=True)[:top_n]

    print("\n" + "=" * 80)
    print(f"TOP {top_n} CENÁRIOS COM MAIOR CORTE DE CARGA")
    print("=" * 80)
    for r in cortes:
        print(f"Cenário {r['cenario']:>4} | Corte carga = {r['corte_carga_MW']:>10.4f} MW | FOB = {r['FOB']:>12.6f}")

    print("\n" + "=" * 80)
    print(f"TOP {top_n} CENÁRIOS COM MAIOR CURTAILMENT")
    print("=" * 80)
    for r in ventos:
        print(f"Cenário {r['cenario']:>4} | Curtailment = {r['corte_vento_MW']:>10.4f} MW | FOB = {r['FOB']:>12.6f}")


def plot_load_shedding_and_curtailment(study):
    results = study["results"]

    cenarios = [r["cenario"] for r in results]
    corte_carga = [r["corte_carga_MW"] for r in results]
    corte_vento = [r["corte_vento_MW"] for r in results]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=cenarios,
        y=corte_carga,
        name="Corte de Carga (MW)",
        hovertemplate="Cenário: %{x}<br>Corte de carga: %{y:.4f} MW<extra></extra>"
    ))

    fig.add_trace(go.Bar(
        x=cenarios,
        y=corte_vento,
        name="Curtailment Eólico (MW)",
        hovertemplate="Cenário: %{x}<br>Curtailment: %{y:.4f} MW<extra></extra>"
    ))

    fig.update_layout(
        title="Corte de Carga e Curtailment por Cenário",
        xaxis_title="Cenário",
        yaxis_title="Potência (MW)",
        barmode="group",
        template="plotly_white",
        height=800,
        width=1800
    )

    fig.show()

def print_top_ramps_per_generator(study, top_n=10):
    results = study["results"]

    if len(results) == 0 or "ramp_up_MW" not in results[0]:
        print("\nRamps por cenário ainda não foram armazenadas em results.")
        return

    nger = len(results[0]["ramp_up_MW"])

    for g in range(nger):
        ramps_up = [(r["cenario"], r["ramp_up_MW"][g]) for r in results]
        ramps_down = [(r["cenario"], r["ramp_down_MW"][g]) for r in results]

        top_up = sorted(ramps_up, key=lambda x: x[1], reverse=True)[:top_n]
        top_down = sorted(ramps_down, key=lambda x: x[1], reverse=True)[:top_n]

        print("\n" + "=" * 80)
        print(f"GERADOR G{g+1} - TOP {top_n} RAMPAS UP")
        print("=" * 80)
        for cen, val in top_up:
            print(f"Cenário {cen:>4} | Ramp Up = {val:>10.4f} MW")

        print("\n" + "=" * 80)
        print(f"GERADOR G{g+1} - TOP {top_n} RAMPAS DOWN")
        print("=" * 80)
        for cen, val in top_down:
            print(f"Cenário {cen:>4} | Ramp Down = {val:>10.4f} MW")

def plot_top_ramps_combined(study, top_n=10):
    results = study["results"]

    if len(results) == 0 or "ramp_up_MW" not in results[0]:
        print("Ramps por cenário ainda não foram armazenadas em results.")
        return

    nger = len(results[0]["ramp_up_MW"])

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            f"Top {top_n} Rampas de Subida",
            f"Top {top_n} Rampas de Descida"
        ),
        vertical_spacing=0.12
    )

    for g in range(nger):
        # UP
        ramps_up = [(r["cenario"], r["ramp_up_MW"][g]) for r in results]
        top_up = sorted(ramps_up, key=lambda x: x[1], reverse=True)[:top_n]

        rank_up = list(range(1, len(top_up) + 1))
        val_up = [x[1] for x in top_up]
        cen_up = [x[0] for x in top_up]

        fig.add_trace(
            go.Bar(
                x=rank_up,
                y=val_up,
                name=f"G{g+1}",
                customdata=cen_up,
                hovertemplate=(
                    f"Gerador: G{g+1}<br>"
                    "Ranking: %{x}<br>"
                    "Cenário: %{customdata}<br>"
                    "Ramp Up: %{y:.4f} MW<extra></extra>"
                ),
                legendgroup=f"G{g+1}"
            ),
            row=1, col=1
        )

        # DOWN
        ramps_down = [(r["cenario"], r["ramp_down_MW"][g]) for r in results]
        top_down = sorted(ramps_down, key=lambda x: x[1], reverse=True)[:top_n]

        rank_down = list(range(1, len(top_down) + 1))
        val_down = [x[1] for x in top_down]
        cen_down = [x[0] for x in top_down]

        fig.add_trace(
            go.Bar(
                x=rank_down,
                y=val_down,
                name=f"G{g+1}",
                customdata=cen_down,
                hovertemplate=(
                    f"Gerador: G{g+1}<br>"
                    "Ranking: %{x}<br>"
                    "Cenário: %{customdata}<br>"
                    "Ramp Down: %{y:.4f} MW<extra></extra>"
                ),
                legendgroup=f"G{g+1}",
                showlegend=False
            ),
            row=2, col=1
        )

    fig.update_layout(
        title="Ranking das Maiores Rampas por Gerador",
        template="plotly_white",
        barmode="group",
        height=900,
        width=1800,
        legend_title="Geradores"
    )

    fig.update_xaxes(title_text="Ranking", row=1, col=1)
    fig.update_xaxes(title_text="Ranking", row=2, col=1)
    fig.update_yaxes(title_text="Ramp Up (MW)", row=1, col=1)
    fig.update_yaxes(title_text="Ramp Down (MW)", row=2, col=1)

    fig.show()


def plot_ramps_by_scenario(study, mode="up"):
    results = study["results"]

    if len(results) == 0 or "ramp_up_MW" not in results[0]:
        print("Ramps por cenário ainda não foram armazenadas em results.")
        return

    nger = len(results[0]["ramp_up_MW"])
    cenarios = [r["cenario"] for r in results]

    fig = go.Figure()

    for g in range(nger):
        if mode == "up":
            y = [r["ramp_up_MW"][g] for r in results]
            titulo = "Rampas de Subida por Cenário"
            ylab = "Ramp Up (MW)"
        else:
            y = [r["ramp_down_MW"][g] for r in results]
            titulo = "Rampas de Descida por Cenário"
            ylab = "Ramp Down (MW)"

        fig.add_trace(
            go.Scatter(
                x=cenarios,
                y=y,
                mode="lines+markers",
                name=f"G{g+1}",
                hovertemplate=(
                "Gerador: G" + str(g+1) + "<br>"
                "Cenário: %{x}<br>"
                + ylab + ": %{y:.4f} MW"
                "<extra></extra>"
            )
            )
        )

    fig.update_layout(
        title=titulo,
        xaxis_title="Cenário",
        yaxis_title=ylab,
        template="plotly_white",
        height=900,
        width=1800
    )

    fig.show()

def build_top_ramps_table(study, top_n=10):
    results = study["results"]
    nger = len(results[0]["ramp_up_MW"])

    rows = []
    for g in range(nger):
        ramps_up = [(r["cenario"], r["ramp_up_MW"][g], "up") for r in results]
        ramps_down = [(r["cenario"], r["ramp_down_MW"][g], "down") for r in results]

        top_up = sorted(ramps_up, key=lambda x: x[1], reverse=True)[:top_n]
        top_down = sorted(ramps_down, key=lambda x: x[1], reverse=True)[:top_n]

        for cen, val, tipo in top_up + top_down:
            rows.append({
                "gerador": f"G{g+1}",
                "tipo_rampa": tipo,
                "cenario": cen,
                "valor_MW": val
            })

    df = pd.DataFrame(rows)
    return df.sort_values(by=["gerador", "tipo_rampa", "valor_MW"], ascending=[True, True, False])

def print_results_dashboard(study):
    results = study["results"]

    fob = np.array([r["FOB"] for r in results])
    perdas = np.array([r["perdas_MW"] for r in results])
    corte_carga = np.array([r["corte_carga_MW"] for r in results])
    corte_vento = np.array([r["corte_vento_MW"] for r in results])
    custo_pg_real = np.array([r.get("custo_pg_real", 0.0) for r in results])
    custo_corte_carga = np.array([r.get("custo_corte_carga", 0.0) for r in results])
    custo_corte_vento = np.array([r.get("custo_corte_vento", 0.0) for r in results])

    print("\n" + "=" * 80)
    print("DASHBOARD RÁPIDO DOS RESULTS")
    print("=" * 80)
    print(f"FOB    | min={fob.min():.6f} | média={fob.mean():.6f} | max={fob.max():.6f}")
    print(f"Perdas | min={perdas.min():.6f} | média={perdas.mean():.6f} | max={perdas.max():.6f}")
    print(f"Carga  | min={corte_carga.min():.6f} | média={corte_carga.mean():.6f} | max={corte_carga.max():.6f}")
    print(f"Vento  | min={corte_vento.min():.6f} | média={corte_vento.mean():.6f} | max={corte_vento.max():.6f}")
    print(f"Custo PG real   | min={custo_pg_real.min():.6f} | média={custo_pg_real.mean():.6f} | max={custo_pg_real.max():.6f}")
    print(f"Corte carga $   | min={custo_corte_carga.min():.6f} | média={custo_corte_carga.mean():.6f} | max={custo_corte_carga.max():.6f}")
    print(f"Corte vento $   | min={custo_corte_vento.min():.6f} | média={custo_corte_vento.mean():.6f} | max={custo_corte_vento.max():.6f}")

    p95_fob = np.percentile(fob, 95)
    p95_perdas = np.percentile(perdas, 95)

    print(f"\nPercentil 95 FOB    : {p95_fob:.6f}")
    print(f"Percentil 95 Perdas : {p95_perdas:.6f}")

def plot_load_vs_generation(study):
    results = study["results"]

    cenarios = np.array([r["cenario"] for r in results])
    carga_total = np.array([np.sum(r["PLOAD_scn_MW"]) for r in results])
    geracao_real = np.array([np.sum(r["PG_real_MW"]) for r in results])
    geracao_total = np.array([np.sum(r["PG_total_MW"]) for r in results])
    eolica_disponivel = np.array([np.sum(r["PGW_scn_MW"]) for r in results])
    curtailment = np.array([r["corte_vento_MW"] for r in results])
    eolica_utilizada = eolica_disponivel - curtailment

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=cenarios, y=carga_total,
        mode="lines+markers",
        name="Carga Total (MW)"
    ))

    fig.add_trace(go.Scatter(
        x=cenarios, y=geracao_real,
        mode="lines+markers",
        name="Geração Convencional Real (MW)"
    ))

    fig.add_trace(go.Scatter(
        x=cenarios, y=eolica_disponivel,
        mode="lines+markers",
        name="Eólica Disponível (MW)"
    ))

    fig.add_trace(go.Scatter(
        x=cenarios, y=eolica_utilizada,
        mode="lines+markers",
        name="Eólica Utilizada (MW)"
    ))

    fig.add_trace(go.Scatter(
        x=cenarios, y=geracao_total,
        mode="lines+markers",
        name="Geração Total do Modelo (MW)"
    ))

    fig.update_layout(
        title="Carga e Geração por Cenário",
        xaxis_title="Cenário",
        yaxis_title="Potência (MW)",
        template="plotly_white",
        height=900,
        width=1800
    )

    fig.show()
    

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("Iniciando estudo de cenários para OPF com eólica...")
    print("""
          A formulação abaixo segue a hierarquia de custos dos slides: 
          custo da geração convencional <= custo de corte de vento <= custo de déficit/corte de carga. 
          Os limites de fluxo foram impostos de forma simétrica em ambos os sentidos da linha,
          e as perdas elétricas são recalculadas a posteriori para análise dos cenários.
          """)
    
    data = inpdat_opf(DBAR, DLIN, DGER, DGW, PB=PB)
    print_system_overview(data)
    
    study = run_scenario_study(
        DBAR=DBAR,
        DLIN=DLIN,
        DGER=DGER,
        DGW=DGW,
        PB=PB,
        Nc=NC,
        seed=123
    )

    # Print the summary of the study
    print_summary(study)   
    print_top_line_rankings(study, top_n=5)
    print_scenario_extremes(study, top_n=10)
    print_results_dashboard(study)
    print_top_ramps_per_generator(study, top_n=10)
    
    # Tabela ranking linhas
    df_rank_linhas = build_line_violation_ranking_table(study)
    print("\nRanking das linhas por lambda médio:")
    print(df_rank_linhas.to_string(index=False))

    # Gráficos
    plot_top_ramps_combined(study, top_n=10)
    plot_ramps_by_scenario(study, mode="up")
    plot_ramps_by_scenario(study, mode="down")
    plot_load_shedding_and_curtailment(study)
    plot_load_vs_generation(study)
    plot_line_ranking_by_lambda(study)
    


    # Excel com todos os cenários na 3ª aba
    # Filename com nome da configuração do sistema 
    # Total Load, Total Generation, Wind Penetration, etc.,
    # e timestamp para garantir unicidade e rastreabilidade dos arquivos gerados.
    filename = f"opf_scenarios_withWind_results_{sum(study['data']['PLOAD_b']):.0f}MW_{sum(study['data']['PGWMAX']):.0f}MW_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    
    export_study_to_excel(
        study,
        filename=filename,
        save_first_model_only=False #True: Salva apenas primeiro scenário, False: Salva modelo de todos os cenários (pode gerar arquivos grandes)
    )