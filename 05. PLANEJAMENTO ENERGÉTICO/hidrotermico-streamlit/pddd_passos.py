"""PDDD passo a passo: o exemplo da aula (1 UHE, 2 UTEs, 3 estágios) gravado a cada solução de estágio.

Cada passo guarda o que o slide mostra: a fase (forward ou backward), o estágio resolvido, a tabela de
cada estágio e os cortes de cada estágio até aquele momento. A tela só percorre a lista de passos.
"""
from copy import deepcopy

import numpy as np
from pyscipopt import Model, SCIP_PARAMSETTING, quicksum

# Dados do notebook de referência (Aulas 3, 4 e 5): custos em $/MWmed, volumes em hm³, sem horas no custo.
EXEMPLO = dict(
    uhe=dict(nome="UHE do Marcato", vmin=20., vmax=100., vi=65., prod=.95, engol=60.),
    utes=[dict(nome="GT 1", capac=15., custo=10.), dict(nome="GT 2", capac=10., custo=25.)],
    cdef=500., carga=[50., 50., 50.],
    afl={"Cenário 1 (úmido)": [23., 19., 15.], "Cenário 2 (seco)": [16., 14., 11.]},
)


def resolver_estagio(caso, t, vi, afl, cortes):
    """min Σ c·gt + c_def·def + 0,01·vv + α, com α ≥ cortes do estágio t. Devolve a tabela do slide e o dual."""
    u = caso["uhe"]
    m = Model("estágio")
    try:
        m.hideOutput()
        # Duais do PL original: sem pré-processamento, heurísticas ou propagação.
        m.setPresolve(SCIP_PARAMSETTING.OFF)
        m.setHeuristics(SCIP_PARAMSETTING.OFF)
        m.disablePropagation()
        m.setBoolParam("lp/alwaysgetduals", True)

        vf = m.addVar(lb=u["vmin"], ub=u["vmax"])
        vt = m.addVar(lb=0, ub=u["engol"])
        vv = m.addVar(lb=0)
        gt = [m.addVar(lb=0, ub=g["capac"]) for g in caso["utes"]]
        d = m.addVar(lb=0)
        alpha = m.addVar(lb=0)

        # Balanço com VI do lado direito: o dual é ∂custo/∂VI, a inclinação do corte.
        balanco = m.addCons(vf + vt + vv == vi + afl)
        m.addCons(u["prod"] * vt + quicksum(gt) + d == caso["carga"][t])

        # Cada corte limita α por baixo: a região viável de α é o que fica ACIMA de todos os planos.
        for a, b in cortes[t]:
            m.addCons(alpha >= a * vf + b)

        imediato = quicksum(g["custo"] * x for g, x in zip(caso["utes"], gt)) + caso["cdef"] * d + .01 * vv
        m.setObjective(imediato + alpha, "minimize")
        m.optimize()
        if m.getStatus() != "optimal":
            raise RuntimeError(m.getStatus())
        return dict(vi=vi, afl=afl, vf=m.getVal(vf), vt=m.getVal(vt), vv=m.getVal(vv),
                    gt=sum(m.getVal(x) for x in gt), gts=[m.getVal(x) for x in gt], deficit=m.getVal(d),
                    fut=m.getVal(alpha), imediato=m.getVal(imediato), tot=m.getObjVal(),
                    pi=m.getDualsolLinear(balanco))
    finally:
        m.freeProb()


def gerar_passos(caso=EXEMPLO, cenario="Cenário 1 (úmido)", tol=.01, max_iter=10):
    """Executa a PDDD e grava um passo a cada estágio resolvido (forward e backward)."""
    afl = caso["afl"][cenario]
    T = len(caso["carga"])
    cortes = [[] for _ in range(T)]       # cortes[t]: limitam o α do estágio t (custo dos estágios t+1…)
    graficos = [[] for _ in range(T)]     # cortes desenhados no gráfico do estágio t (gerados ao resolvê-lo)
    passos, historico = [], []
    tabela = [None] * T
    for it in range(1, max_iter + 1):
        # ---------------- FORWARD: o estágio t recebe VI = vf do estágio t−1 ----------------
        vi = caso["uhe"]["vi"]
        tabela = [None] * T
        for t in range(T):
            r = resolver_estagio(caso, t, vi, afl[t], cortes)
            tabela[t] = r
            passos.append(dict(iteracao=it, fase="forward", estagio=t, tabela=deepcopy(tabela),
                               graficos=deepcopy(graficos), novo=None, historico=list(historico),
                               texto=f"Forward {it}: o estágio {t + 1} recebe VI = {vi:.2f} hm³ "
                                     + ("(volume inicial do estudo)" if t == 0 else f"(vf do estágio {t})")
                                     + f" e entrega vf = {r['vf']:.2f} hm³ ao estágio {t + 2}." if t < T - 1 else
                                     f"Forward {it}: o estágio {t + 1} recebe VI = {vi:.2f} hm³ (vf do estágio {t}). Último estágio: α = 0."))
            vi = r["vf"]
        visitados = [r["vi"] for r in tabela]

        # Zsup soma só os custos imediatos; Zinf é o custo total do estágio 1 (imediato + α).
        zsup = sum(r["imediato"] for r in tabela)
        zinf = tabela[0]["tot"]
        historico.append(dict(iteracao=it, zinf=zinf, zsup=zsup))
        convergiu = abs(zsup - zinf) <= tol
        passos[-1]["historico"] = list(historico)
        passos[-1]["texto"] += (f" Zsup = Σ imediatos = ${zsup:,.2f}; Zinf = tot do estágio 1 = ${zinf:,.2f}."
                                + (" Gap ≤ tolerância: CONVERGIU." if convergiu else " Gap acima da tolerância: começa o backward."))
        if convergiu:
            passos[-1]["fase"] = "convergiu"
            break

        # ---------------- BACKWARD: do último estágio para o primeiro ----------------
        tab_b = deepcopy(tabela)
        for t in range(T - 1, -1, -1):
            r = resolver_estagio(caso, t, visitados[t], afl[t], cortes)
            tab_b[t] = r

            # Corte gerado no ponto visitado: Q(v̄) + π·(v − v̄), com π = dual do balanço hídrico.
            a, b = r["pi"], r["tot"] - r["pi"] * visitados[t]
            graficos[t].append(dict(a=a, b=b, x=visitados[t], y=r["tot"], iteracao=it))
            if t > 0:
                # O corte vira restrição do α do estágio ANTERIOR (função do vf do estágio t−1).
                cortes[t - 1].append((a, b))
                texto = (f"Backward {it}: o estágio {t + 1} recebe v̄ = {visitados[t]:.2f} hm³ (vf do estágio {t} no forward) "
                         f"e os cortes atuais. Custo ${r['tot']:,.2f}, π = {a:,.2f} $/hm³ → novo corte entregue ao estágio {t}: "
                         f"α ≥ {a:,.2f}·vf + {b:,.2f}.")
            else:
                texto = (f"Backward {it}: o estágio 1 é resolvido de novo com VI = {visitados[0]:.2f} hm³ e os novos cortes. "
                         f"Custo total ${r['tot']:,.2f}: este é o novo limite inferior (Zinf).")
            passos.append(dict(iteracao=it, fase="backward", estagio=t, tabela=deepcopy(tab_b),
                               graficos=deepcopy(graficos), novo=t, historico=list(historico), texto=texto))
    return passos
