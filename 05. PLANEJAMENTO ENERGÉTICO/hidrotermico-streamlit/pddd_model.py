"""PDDD — Programação Dinâmica Dual (decomposição de Benders aninhada).

Uma única função atende os dois casos do curso:
- trajetória conhecida (cada mês tem uma só afluência): é a PDDD determinística, que deve igualar o PL Único;
- árvore de cenários (cada mês tem várias aberturas): visitando todos os nós, a PDDD deve igualar o PL Único em árvore.

O despacho de cada nó usa o mesmo `bloco_fisico` do PL em árvore, então a física é idêntica nos três métodos.
"""
from time import perf_counter

import numpy as np
from pyscipopt import Model, SCIP_PARAMSETTING, quicksum

from modelo_arvore import bloco_fisico, construir_arvore, rotulo
from pl_model import limite_turbinado_det


def caso_de_sistema(sistema, cenario=0):
    """Converte o `sistema` do PL Único no `caso` usado pela árvore e pela PDDD (uma abertura por mês)."""
    geral, uhes, utes = sistema["DGer"], sistema["UHE"], sistema["UTE"]
    n = len(geral["Meses"])
    return dict(
        nomes=[u["Nome"] for u in uhes],
        vmin=np.array([u["Vmin"] for u in uhes], float), vmax=np.array([u["Vmax"] for u in uhes], float),
        vi=np.array([u["VI"] for u in uhes], float),
        prod=np.array([u["Prod"] for u in uhes], float),
        # O limite de potência (Serra: 212,58 MW) entra como teto do turbinamento, igual ao PL Único.
        qmax=np.array([limite_turbinado_det(u) for u in uhes], float),
        mont=[[j for j, m in enumerate(uhes) if m.get("Jusante") == i] for i in range(len(uhes))],
        termicas=[u["Nome"] for u in utes], gtmax=[u["Capac"] for u in utes],
        # Os dicionários do PL guardam custos já multiplicados pelas horas do mês: aqui voltamos a R$/MWh.
        cvu=[u["Custo"] / geral["Horas"] for u in utes], cdef=geral["CDef"] / geral["Horas"],
        horas=float(geral["Horas"]), escala=1e6, carga=[float(c) for c in geral["Carga"]], unidade="R$",
        aberturas=[[(1., np.array([u["Afl"][t][cenario] for u in uhes], float))] for t in range(n)],
        meses=list(geral["Meses"]))


def _resolver_no(caso, vi, afl, carga, cortes, duais):
    """Despacho de UM nó: min C_t + α, sujeito ao balanço e aos cortes de custo futuro do nó."""
    m = Model("PDDD - estágio")
    try:
        m.hideOutput()
        m.setRealParam("numerics/feastol", 1e-9)
        m.setRealParam("numerics/dualfeastol", 1e-9)
        if duais:
            # Para ler os duais do PL ORIGINAL o SCIP não pode pré-processar nem propagar o modelo.
            m.setPresolve(SCIP_PARAMSETTING.OFF)
            m.setHeuristics(SCIP_PARAMSETTING.OFF)
            m.disablePropagation()
            m.setBoolParam("lp/alwaysgetduals", True)

        # VI entra como NÚMERO (lado direito do balanço). É isso que faz o dual medir ∂custo/∂VI.
        b = bloco_fisico(m, caso, [float(x) for x in vi], afl, carga, "no")

        # α ≥ 0: os custos são não negativos, então zero já é um limite inferior válido do futuro.
        alpha = m.addVar(lb=0, name="alpha")

        # Cada corte é um plano  α ≥ b + a·VF  (em R$); divide-se pela escala como no objetivo.
        for a, intercepto in cortes:
            m.addCons(alpha >= (intercepto + quicksum(float(k) * v for k, v in zip(a, b["v"]))) / caso["escala"])

        m.setObjective(b["ci"] / caso["escala"] + alpha, "minimize")
        m.optimize()
        if m.getStatus() != "optimal":
            raise RuntimeError(f"PDDD: estágio com status {m.getStatus()}")
        r = dict(v=np.array([m.getVal(x) for x in b["v"]]), q=np.array([m.getVal(x) for x in b["q"]]),
                 s=np.array([m.getVal(x) for x in b["s"]]), g=np.array([m.getVal(x) for x in b["g"]]),
                 d=m.getVal(b["d"]), ci=m.getVal(b["ci"]), alpha=m.getVal(alpha) * caso["escala"],
                 obj=m.getObjVal() * caso["escala"])
        if duais:
            # Dual do balanço hídrico = sensibilidade do custo ao volume inicial (R$/hm³).
            # O objetivo foi dividido por 10⁶; multiplicar de volta deixa o corte em reais.
            r["pi"] = np.array([m.getDualsolLinear(c) * caso["escala"] for c in b["bh"]])

            # CMA (custo marginal da água, R$/hm³): quanto o custo CAI com 1 hm³ a mais no reservatório = −π.
            r["cma"] = -r["pi"]

            # CMO (R$/MWh): dual do atendimento à carga (R$ por MW médio no mês) dividido pelas horas do mês.
            r["cmo"] = m.getDualsolLinear(b["atendimento"]) * caso["escala"] / caso["horas"]
        return r
    finally:
        m.freeProb()


def pddd(caso, cortes_terminais=(), max_iter=100, tol_abs=1., tol_rel=1e-8, arvore=None, progresso=None):
    """Forward/backward até Zsup − Zinf ≤ tol_abs + tol_rel·|Zsup|.

    caso: dicionário do PL em árvore (carga e aberturas por mês).
    cortes_terminais: cortes (a, b) aplicados ao α das folhas; vazio = custo após o horizonte nulo.
    Devolve trajetória/nós do melhor forward, histórico de Zinf/Zsup e os cortes de cada nó.
    """
    inicio = perf_counter()
    arvore = arvore or construir_arvore(caso["aberturas"])
    T = len(caso["carga"])
    por_estagio = [[no for no, r in arvore.items() if r["t"] == t] for t in range(T)]
    filhos = {no: [] for no in arvore}
    for no, r in arvore.items():
        if r["pai"] is not None:
            filhos[r["pai"]].append(no)

    # Cortes de cada nó: aproximam o custo dos meses SEGUINTES em função do volume final do nó.
    cortes = {no: (list(cortes_terminais) if not filhos[no] else []) for no in arvore}
    zsup, zinf, historico, melhor = np.inf, -np.inf, [], None

    for it in range(1, max_iter + 1):
        # ---------- FORWARD: percorre a árvore do primeiro ao último mês com os cortes atuais ----------
        sol = {}
        for t in range(T):
            for no in por_estagio[t]:
                r = arvore[no]
                vi = caso["vi"] if r["pai"] is None else sol[r["pai"]]["v"]
                # duais=True também no forward: assim cada mês sai com CMO e CMA (dados de saída do despacho).
                sol[no] = _resolver_no(caso, vi, r["afl"], caso["carga"][t], cortes[no], duais=True)

        # Zsup: custo esperado REALIZADO pela política. Soma-se só o custo imediato (somar α contaria o futuro
        # duas vezes). Nas folhas o α é o custo após o horizonte, que também faz parte do objetivo do PL.
        custo = sum(arvore[no]["prob"] * (s["ci"] + (s["alpha"] if not filhos[no] else 0.)) for no, s in sol.items())
        raiz = por_estagio[0][0]
        # Zinf: objetivo do primeiro mês = custo imediato + aproximação (por baixo) do futuro.
        zinf = max(zinf, sol[raiz]["obj"])
        if custo < zsup:
            zsup, melhor = custo, sol
        gap = zsup - zinf
        historico.append(dict(iteracao=it, zinf=zinf, zsup=zsup, custo_forward=custo, gap=gap,
                              cortes=sum(len(c) for c in cortes.values())))
        if progresso:
            progresso(it, zinf, zsup)
        if gap <= tol_abs + tol_rel * max(1., abs(zsup)):
            break
        if it == max_iter:
            break

        # ---------- BACKWARD: do último mês para o segundo, um corte para cada nó pai ----------
        for t in range(T - 1, 0, -1):
            for pai in por_estagio[t - 1]:
                v_barra = sol[pai]["v"]
                a, b = np.zeros(len(v_barra)), 0.
                for filho in filhos[pai]:
                    # O filho é resolvido a partir do volume que o pai visitou no forward.
                    r = _resolver_no(caso, v_barra, arvore[filho]["afl"], caso["carga"][t], cortes[filho], duais=True)
                    p = arvore[filho]["prob"] / arvore[pai]["prob"]
                    # Corte agregado (média ponderada dos filhos):  α ≥ Σ p·[Q + π·(VF − v̄)].
                    a += p * r["pi"]
                    b += p * (r["obj"] - r["pi"] @ v_barra)
                cortes[pai].append((a, b))

    return dict(sol=melhor, arvore=arvore, cortes=cortes, historico=historico, zinf=zinf, zsup=zsup,
                convergiu=zsup - zinf <= tol_abs + tol_rel * max(1., abs(zsup)),
                iteracoes=len(historico), segundos=perf_counter() - inicio,
                por_estagio=por_estagio)


def trajetoria(resultado):
    """Lista de meses (para o caso determinístico): o caminho único da raiz até a folha."""
    return [resultado["sol"][nos[0]] for nos in resultado["por_estagio"]]


def custo_futuro_superficie(cortes, caso, n=25):
    """α(VF) = max(0, max dos cortes) numa grade de volumes finais das duas UHEs, em R$ milhões."""
    eixos = [np.linspace(caso["vmin"][i], caso["vmax"][i], n) for i in range(2)]
    X, Y = np.meshgrid(*eixos, indexing="ij")
    Z = np.zeros_like(X)
    for a, b in cortes:
        Z = np.maximum(Z, b + a[0] * X + a[1] * Y)
    return eixos[0], eixos[1], Z / 1e6


def tabela_saida(resultado, caso):
    """Dados de saída do despacho determinístico, mês a mês (lista de dicionários)."""
    linhas = []
    for t, r in enumerate(trajetoria(resultado)):
        linha = {"Mês": caso.get("meses", [f"Mês {i + 1}" for i in range(len(caso["carga"]))])[t],
                 "Carga (MWm)": caso["carga"][t]}
        for i, n in enumerate(caso["nomes"]):
            linha[f"VF {n} (hm³)"] = r["v"][i]
            linha[f"Turbinado {n} (hm³)"] = r["q"][i]
            linha[f"Vertido {n} (hm³)"] = r["s"][i]
            linha[f"Geração {n} (MWm)"] = caso["prod"][i] * r["q"][i]
            linha[f"CMA {n} (R$/hm³)"] = r["cma"][i]
        for j, n in enumerate(caso["termicas"]):
            linha[f"{n} (MWm)"] = r["g"][j]
        linha.update({"Déficit (MWm)": r["d"], "CMO (R$/MWh)": r["cmo"], "Custo imediato (R$)": r["ci"],
                      "Custo futuro α (R$)": r["alpha"]})
        linhas.append(linha)
    return linhas


def rotulos(resultado):
    return {no: rotulo(no) for no in resultado["arvore"]}
