"""PDDE — Programação Dinâmica Dual Estocástica (SDDP), com afluências independentes entre estágios.

Uma só implementação atende três casos:
- 1dtoy do COBRE: 1 UHE, 2 UTEs, 4 estágios, afluência Normal(40; 10) m³/s, desconto de 12% ao ano;
- Batalha (1 UHE) com dados do PySDDP: o caso "semelhante ao 1dtoy" no nosso sistema;
- Batalha + Serra do Facão (2 UHEs em cascata) com dados do PySDDP: o trabalho do professor.

Unidades: vazões em m³/s, volumes em hm³, potências em MW médios, custos em R$/MWh (as horas de cada
estágio entram dentro do modelo). O custo realizado de uma trajetória é descontado: Σ D_t · C_t.
"""
from itertools import product
from time import perf_counter

import numpy as np
from pyscipopt import Model, SCIP_PARAMSETTING, quicksum

# 365,25 dias × 24 h: é o ano que o novomodelo usa para converter a taxa anual de desconto em fator por estágio.
HORAS_ANO = 8766.


# ----------------------------------------------------------------------------- casos
def caso_1dtoy():
    """Dados do exemplo oficial examples/1dtoy do novomodelo (ONS, CCEE, EPE), v0.22.0."""
    horas = [744, 696, 744, 720]   # jan, fev (2024 é bissexto), mar e abr de 2024
    return dict(
        nome="1dtoy (COBRE)",
        uhes=[dict(nome="UHE1", vmin=0., vmax=1000., qmax=50., prod=1., gmax=50., defluencia_max=50., montante=[])],
        utes=[dict(nome="UTE1", gmax=15., custo=5.), dict(nome="UTE2", gmax=15., custo=10.)],
        carga=[75.] * 4, horas=horas, meses=["Jan/2024", "Fev/2024", "Mar/2024", "Abr/2024"],
        cdef=7500., custo_excesso=100.,

        # No novomodelo as penalidades hídricas são em R$/(m³/s·h). 1 m³/s durante 1 h = 0,0036 hm³,
        # então dividir por 0,0036 converte para R$/hm³, a unidade do nosso balanço hídrico.
        custo_vert=.01 / .0036, custo_turb=.05 / .0036,
        v0=[83.222], escala=1e6, taxa_anual=.12,
        afluencia=dict(media=[40.] * 4, desvio=[10.] * 4))


def caso_toy_documentacao():
    """Exemplo resolvido à mão na documentação do novomodelo ("toy-single-reservoir", modelossetoreletrico.org.br).

    1 UHE (ρ = 1, ζ = 1, 0–100, v₀ = 30), 1 térmica sem limite a 50/MW, carga 40, déficit 1000, sem desconto,
    afluência Normal(30; 10) com 3 aberturas {20, 30, 40}. A página dá Zinf = 5000/9 na 1ª iteração,
    16000/27 na 2ª e o ótimo 17000/27 ≈ 629,63: serve de teste à mão do nosso código.
    """
    return dict(nome="Toy da documentação do COBRE",
                uhes=[dict(nome="UHE", vmin=0., vmax=100., qmax=None, prod=1., montante=[])],
                utes=[dict(nome="Térmica", gmax=None, custo=50.)], carga=[40.] * 4, horas=[1.] * 4,
                meses=["t1", "t2", "t3", "t4"], cdef=1000., custo_vert=0., fator_volume=1., v0=[30.], escala=1.,
                taxa_anual=0.)


def aberturas_toy():
    return [np.array([[20.], [30.], [40.]]) for _ in range(4)]


def caso_pysddp(usinas=("Batalha",), mes_inicial=1, n_meses=4, carga=None, vi_pct=(39.7, 50.2), cdef=4000.,
                taxa_anual=0., termicas=None):
    """Caso com dados ao vivo do PySDDP (HIDR.DAT, VAZOES.DAT e deck DESSEM).

    usinas=("Batalha",) é o caso de 1 UHE, comparável ao 1dtoy; ("Batalha", "Serra do Facão") é a cascata.
    Sem carga informada, usa-se a carga que dá a mesma "folga" do 1dtoy (ver carga_como_1dtoy).
    """
    import dados_pysddp as dp
    cad = dp.cadastro_uhes()
    termicas = termicas or dp.termicas_dessem()
    uhes = []
    for i, nome in enumerate(usinas):
        u = cad[nome]

        # Só Serra recebe a descarga de Batalha; com 1 UHE, Batalha não tem montante.
        montante = [0] if (nome == "Serra do Facão" and "Batalha" in usinas) else []
        uhes.append(dict(nome=nome, vmin=u["vmin"], vmax=u["vmax"], qmax=u["qmax"], prod=u["prod"], gmax=u["potencia"],
                         montante=montante))
    v0 = [u["vmin"] + p / 100 * (u["vmax"] - u["vmin"]) for u, p in zip(uhes, vi_pct)]
    meses = [f"{dp.MESES[(mes_inicial - 1 + t) % 12][:3]}" for t in range(n_meses)]
    caso = dict(nome=" + ".join(usinas) + " (PySDDP)", uhes=uhes,
                utes=[dict(nome=t["Nome"], gmax=t["Pmax"], custo=t["CVU"]) for t in termicas],
                horas=[720] * n_meses, meses=meses, cdef=cdef, custo_vert=.01, v0=v0,

                # Escala 1e3 (e não 1e6): com 1e6 a penalidade de vertimento ficaria abaixo da tolerância do SCIP.
                escala=1e3, taxa_anual=taxa_anual, mes_inicial=mes_inicial, usinas=tuple(usinas))
    caso["carga"] = [float(carga)] * n_meses if carga is not None else [carga_como_1dtoy(caso)] * n_meses
    return caso


def carga_como_1dtoy(caso):
    """Carga que reproduz a folga do 1dtoy: carga = energia hidráulica média + 35/30 da capacidade térmica.

    No 1dtoy a hidro média gera 40 MW, as térmicas somam 30 MW e a carga é 75 MW: faltam 35 MW além da hidro,
    isto é, 117% da capacidade térmica. O armazenamento e o déficit fecham a diferença. Esse aperto é o que torna
    o caso interessante (o valor da água é alto e há risco de déficit).
    """
    import dados_pysddp as dp
    _, locais = dp.historico_local()
    idx = [list(dp.CODIGOS).index(n) for n in caso["usinas"]]
    meses = [(caso["mes_inicial"] - 1 + t) % 12 for t in range(len(caso["horas"]))]
    energia = 0.
    for k, (i, u) in enumerate(zip(idx, caso["uhes"])):
        # Energia de uma UHE = ρ × (vazão local + a que vem de montante), limitada ao engolimento.
        vazao = locais[:, meses, i] + sum(locais[:, meses, idx[j]] for j in u["montante"])
        energia += u["prod"] * float(np.minimum(vazao, u["qmax"]).mean())
    termica = sum(t["gmax"] for t in caso["utes"])
    return round(energia + 35 / 30 * termica, 1)


# ----------------------------------------------------------------------------- aberturas
def aberturas_normal(caso, n, semente=42):
    """n aberturas por estágio sorteadas de Normal(média, desvio): é como o COBRE gera a árvore do 1dtoy."""
    rng = np.random.default_rng(semente)
    a = caso["afluencia"]
    return [rng.normal(a["media"][t], a["desvio"][t], (n, len(caso["uhes"]))) for t in range(len(caso["carga"]))]


def aberturas_historicas(caso, n, semente=42):
    """n aberturas por mês: anos sorteados (sem repetição) do VAZOES.DAT para aquele mês do calendário.

    É a abordagem da aula: cada abertura é um ano histórico, e as duas UHEs usam o MESMO ano (afluências conjuntas).
    Devolve as aberturas (m³/s) e os rótulos "Mês/ano" de cada uma.
    """
    import dados_pysddp as dp
    anos, locais = dp.historico_local()
    idx = [list(dp.CODIGOS).index(nm) for nm in caso["usinas"]]
    rng = np.random.default_rng(semente)
    ab, rot = [], []
    for t in range(len(caso["carga"])):
        m = (caso["mes_inicial"] - 1 + t) % 12
        escolhidos = rng.choice(len(anos), n, replace=False)
        ab.append(locais[escolhidos][:, m, :][:, idx])
        rot.append([f"{dp.MESES[m][:3]}/{anos[i]}" for i in escolhidos])
    return ab, rot


def descontos(horas, taxa_anual):
    """β_t: desconto de UM estágio (multiplica α_t). D_t: fator acumulado que multiplica o custo do estágio t."""
    beta = np.array([(1 + taxa_anual) ** (-h / HORAS_ANO) for h in horas])
    acumulado = np.concatenate([[1.], np.cumprod(beta[:-1])])
    return beta, acumulado


# ----------------------------------------------------------------------------- estágio
def resolver_estagio(caso, t, v0, afl, cortes, duais=False):
    """Despacho de um estágio: min C_t + β_t·α_t, sujeito a balanço, carga e aos cortes do estágio t.

    O estágio t RECEBE v0 (o volume final do estágio t−1) e a afluência da abertura; ENTREGA o volume final.
    """
    # Um volume que sai do SCIP 1e-9 abaixo do mínimo (tolerância) é trazido de volta à caixa:
    # sem isso, o estágio seguinte pode ficar inviável por um erro de arredondamento.
    v0 = np.clip(np.asarray(v0, float), [u["vmin"] for u in caso["uhes"]], [u["vmax"] for u in caso["uhes"]])
    try:
        return _estagio(caso, t, v0, afl, cortes, duais, 1e-8)
    except Exception:
        # Raramente o LP acusa dificuldade numérica com tolerâncias apertadas: repete com as padrão do SCIP.
        return _estagio(caso, t, v0, afl, cortes, duais, None)


def _estagio(caso, t, v0, afl, cortes, duais, tol):
    uhes, utes = caso["uhes"], caso["utes"]
    horas = caso["horas"][t]

    # k converte vazão média do estágio (m³/s) em volume (hm³): 1 m³/s × horas × 3600 s / 10⁶.
    # No exemplo à mão da documentação do COBRE tudo está na mesma unidade (ζ = 1), e o caso informa k diretamente.
    k = caso.get("fator_volume", horas * 3600 / 1e6)
    m = Model("PDDE - estágio")
    try:
        m.hideOutput()
        if tol:
            m.setRealParam("numerics/feastol", tol)
            m.setRealParam("numerics/dualfeastol", tol)
        if duais:
            # Duais do PL ORIGINAL: o SCIP não pode pré-processar, usar heurísticas nem propagar.
            m.setPresolve(SCIP_PARAMSETTING.OFF)
            m.setHeuristics(SCIP_PARAMSETTING.OFF)
            m.disablePropagation()
            m.setBoolParam("lp/alwaysgetduals", True)

        v = [m.addVar(lb=u["vmin"], ub=u["vmax"]) for u in uhes]
        q = [m.addVar(lb=0, ub=u["qmax"]) for u in uhes]
        s = [m.addVar(lb=0) for _ in uhes]
        g = [m.addVar(lb=0, ub=u["gmax"]) for u in utes]
        d = m.addVar(lb=0)

        # Excesso (geração sem consumo) só existe no 1dtoy, que o penaliza; no nosso caso não há essa variável.
        e = m.addVar(lb=0) if caso.get("custo_excesso") is not None else 0.

        balancos = []
        for i, u in enumerate(uhes):
            recebe = quicksum(q[j] + s[j] for j in u["montante"])

            # Balanço hídrico com v0 no LADO DIREITO: o dual desta restrição é ∂custo/∂v0 (R$/hm³),
            # exatamente a inclinação π do corte que o backward entrega ao estágio anterior.
            balancos.append(m.addCons(v[i] + k * (q[i] + s[i] - recebe) == float(v0[i]) + k * float(afl[i])))

            # Defluência máxima (turbinada + vertida): o 1dtoy limita a 50 m³/s.
            if u.get("defluencia_max") is not None:
                m.addCons(q[i] + s[i] <= u["defluencia_max"])

            # Potência máxima da usina: ρ·q ≤ Pmax.
            if u.get("gmax") is not None:
                m.addCons(u["prod"] * q[i] <= u["gmax"])

        # Atendimento à carga em MW médios; o dual dividido pelas horas é o CMO (R$/MWh).
        carga = m.addCons(quicksum(u["prod"] * q[i] for i, u in enumerate(uhes)) + quicksum(g) + d - e == caso["carga"][t])

        # Custo imediato em R$: térmica, déficit e excesso em R$/MWh × horas; vertimento e turbinamento em R$/hm³.
        imediato = horas * (quicksum(u["custo"] * g[j] for j, u in enumerate(utes)) + caso["cdef"] * d
                            + (caso["custo_excesso"] * e if caso.get("custo_excesso") is not None else 0.))
        imediato += k * (caso.get("custo_vert", .01) * quicksum(s) + caso.get("custo_turb", 0.) * quicksum(q))

        # α_t ≥ cada corte: aproxima POR BAIXO o custo esperado dos estágios seguintes, em função do volume final.
        alpha = m.addVar(lb=0)
        for a, b in cortes[t]:
            m.addCons(alpha >= (b + quicksum(float(ai) * vi for ai, vi in zip(a, v))) / caso["escala"])

        # β_t desconta o futuro em um estágio; o objetivo é dividido pela escala para o SCIP trabalhar com números ~1.
        beta = caso["beta"][t]
        m.setObjective(imediato / caso["escala"] + beta * alpha, "minimize")
        m.optimize()
        if m.getStatus() != "optimal":
            raise RuntimeError(f"Estágio {t + 1}: {m.getStatus()}")
        r = dict(v=np.array([m.getVal(x) for x in v]), q=np.array([m.getVal(x) for x in q]),
                 s=np.array([m.getVal(x) for x in s]), g=np.array([m.getVal(x) for x in g]),
                 d=m.getVal(d), ci=m.getVal(imediato), alpha=m.getVal(alpha) * caso["escala"],
                 obj=m.getObjVal() * caso["escala"])
        if duais:
            r["pi"] = np.array([m.getDualsolLinear(c) * caso["escala"] for c in balancos])
            r["cmo"] = m.getDualsolLinear(carga) * caso["escala"] / horas
        return r
    finally:
        m.freeProb()


# ----------------------------------------------------------------------------- algoritmo
def preparar(caso):
    """Calcula os fatores de desconto e devolve o caso pronto para o algoritmo."""
    caso = dict(caso)
    caso["beta"], caso["D"] = descontos(caso["horas"], caso.get("taxa_anual", 0.))
    return caso


def pdde(caso, aberturas, n_forward=10, max_iter=50, semente=42, progresso=None, sequencias=None):
    """Treina a política: forward amostrado (Monte Carlo) + backward em TODAS as aberturas de cada estágio.

    aberturas[t]: matriz (n_aberturas, n_uhes) em m³/s, equiprováveis e independentes entre estágios.
    sequencias (opcional): índices das aberturas do forward em cada iteração, ex. [[1,1,1,1], [2,1,1,1]] para
    reproduzir à mão o exemplo da documentação; sem ela, o forward é sorteado (Monte Carlo).
    Devolve os cortes de cada estágio e o histórico de Zinf e Zsup por iteração.
    """
    caso = preparar(caso)
    inicio = perf_counter()
    T = len(caso["carga"])
    rng = np.random.default_rng(semente)

    # cortes[t]: aproximação de E[custo dos estágios t+1…T | VF_t]. Um único conjunto por estágio vale para qualquer
    # nó daquele estágio — é a independência entre estágios que permite isso (e é o que diferencia a PDDE do Benders na árvore).
    cortes = [[] for _ in range(T)]
    historico = []
    for it in range(1, max_iter + 1):
        # ---------------- FORWARD: n_forward sequências sorteadas entre as aberturas ----------------
        estados, custos = [], []
        for f in range(n_forward):
            v, custo, visitados = np.array(caso["v0"], float), 0., []
            for t in range(T):
                # Sorteio de Monte Carlo: uma das aberturas do estágio t (ou a sequência dada, no exemplo à mão).
                w = sequencias[it - 1][t] if sequencias and it <= len(sequencias) else rng.integers(len(aberturas[t]))

                # O estágio t RECEBE v (o VF do estágio t−1 nesta sequência) e usa os cortes atuais.
                r = resolver_estagio(caso, t, v, aberturas[t][w], cortes)
                visitados.append(v)

                # Custo REALIZADO: só o imediato, descontado. Somar α contaria o futuro duas vezes.
                custo += caso["D"][t] * r["ci"]
                v = r["v"]
            estados.append(visitados)
            custos.append(custo)

        # ---------------- BACKWARD: do último estágio para o segundo ----------------
        for t in range(T - 1, 0, -1):
            for visitados in estados:
                # O estágio t RECEBE v̄ = VF do estágio t−1 visitado no forward, e é resolvido para TODAS as aberturas.
                v_barra = visitados[t]
                rs = [resolver_estagio(caso, t, v_barra, afl, cortes, duais=True) for afl in aberturas[t]]

                # Corte médio (aberturas equiprováveis): π̄ = média dos duais; b̄ = média de Q − π̄·v̄.
                pi = np.mean([r["pi"] for r in rs], axis=0)
                b = np.mean([r["obj"] for r in rs]) - pi @ v_barra

                # O estágio t ENTREGA o corte ao estágio t−1: α_{t−1}(VF) ≥ b̄ + π̄·VF.
                # Cortes repetidos não acrescentam informação e degradam o LP, por isso são descartados.
                if not any(np.allclose(pi, a, rtol=1e-9, atol=1e-6) and abs(b - c) <= 1e-6 * max(1., abs(b))
                           for a, c in cortes[t - 1]):
                    cortes[t - 1].append((pi, b))

        # ---------------- LIMITES ----------------
        # Zinf: valor esperado do 1º estágio (média nas suas aberturas, com o VI real). Cresce a cada iteração.
        zinf = float(np.mean([resolver_estagio(caso, 0, caso["v0"], afl, cortes)["obj"] for afl in aberturas[0]]))

        # Zsup: média dos custos dos forwards. É uma ESTIMATIVA, com intervalo de confiança de 95%.
        media = float(np.mean(custos))
        dp_ = float(np.std(custos, ddof=1)) if n_forward > 1 else 0.
        meia = 1.96 * dp_ / np.sqrt(n_forward)
        historico.append(dict(iteracao=it, zinf=zinf, zsup=media, zsup_inf=media - meia, zsup_sup=media + meia,
                              cortes=sum(len(c) for c in cortes), segundos=perf_counter() - inicio))
        if progresso:
            progresso(historico[-1], max_iter)
    return dict(cortes=cortes, historico=historico, segundos=perf_counter() - inicio, caso=caso)


def simular(caso, cortes, cenarios, duais=True):
    """Aplica a política (os cortes) a cenários de afluência (S × T × n_uhes) e devolve custos e trajetórias."""
    caso = preparar(caso)
    custos, trajetorias = [], []
    for cen in cenarios:
        v, custo, traj = np.array(caso["v0"], float), 0., []
        for t, afl in enumerate(cen):
            r = resolver_estagio(caso, t, v, afl, cortes, duais=duais)
            r["vi"], r["afl"] = v, np.asarray(afl)
            traj.append(r)
            custo += caso["D"][t] * r["ci"]
            v = r["v"]
        custos.append(custo)
        trajetorias.append(traj)
    return np.array(custos), trajetorias


def equivalente_deterministico(caso, aberturas):
    """Ótimo EXATO da árvore de aberturas: todos os nós num único PL (o "PL Único em árvore" da PDDE).

    Só é viável para árvores pequenas (o número de nós cresce como nᵀ). Serve de referência: o Zinf de qualquer
    implementação converge para este valor por baixo.
    """
    caso = preparar(caso)
    T, nh = len(caso["carga"]), len(caso["uhes"])
    m = Model("equivalente determinístico")
    try:
        m.hideOutput()
        objetivo = []
        pais = {(): np.array(caso["v0"], float)}
        for t in range(T):
            n = len(aberturas[t])
            k = caso.get("fator_volume", caso["horas"][t] * 3600 / 1e6)
            novos = {}
            for caminho, vi in pais.items():
                for w in range(n):
                    afl = aberturas[t][w]
                    v = [m.addVar(lb=u["vmin"], ub=u["vmax"]) for u in caso["uhes"]]
                    q = [m.addVar(lb=0, ub=u["qmax"]) for u in caso["uhes"]]
                    s = [m.addVar(lb=0) for _ in caso["uhes"]]
                    g = [m.addVar(lb=0, ub=u["gmax"]) for u in caso["utes"]]
                    d = m.addVar(lb=0)
                    e = m.addVar(lb=0) if caso.get("custo_excesso") is not None else 0.
                    for i, u in enumerate(caso["uhes"]):
                        # O nó RECEBE o volume final do nó pai (variável) — na raiz, o v0 (número).
                        m.addCons(v[i] + k * (q[i] + s[i] - quicksum(q[j] + s[j] for j in u["montante"]))
                                  == vi[i] + k * float(afl[i]))
                        if u.get("defluencia_max") is not None:
                            m.addCons(q[i] + s[i] <= u["defluencia_max"])
                        if u.get("gmax") is not None:
                            m.addCons(u["prod"] * q[i] <= u["gmax"])
                    m.addCons(quicksum(u["prod"] * q[i] for i, u in enumerate(caso["uhes"])) + quicksum(g) + d - e
                              == caso["carga"][t])
                    ci = caso["horas"][t] * (quicksum(u["custo"] * g[j] for j, u in enumerate(caso["utes"]))
                                             + caso["cdef"] * d
                                             + (caso["custo_excesso"] * e if caso.get("custo_excesso") is not None else 0.))
                    ci += k * (caso.get("custo_vert", .01) * quicksum(s) + caso.get("custo_turb", 0.) * quicksum(q))

                    # Probabilidade do caminho = 1/nᵗ⁺¹ (aberturas equiprováveis); custo descontado por D_t.
                    prob = 1. / np.prod([len(aberturas[i]) for i in range(t + 1)])
                    objetivo.append(prob * caso["D"][t] * ci / caso["escala"])
                    novos[caminho + (w,)] = v
            pais = novos
        m.setObjective(quicksum(objetivo), "minimize")
        m.optimize()
        if m.getStatus() != "optimal":
            raise RuntimeError(m.getStatus())
        return float(m.getObjVal() * caso["escala"])
    finally:
        m.freeProb()


def resumo_estagios(trajetorias, caso):
    """Médias por estágio de uma simulação (para comparar com o COBRE)."""
    T = len(trajetorias[0])
    linhas = []
    for t in range(T):
        rs = [tr[t] for tr in trajetorias]
        linhas.append({"Estágio": caso.get("meses", [f"{i + 1}" for i in range(T)])[t],
                       "Volume final médio (hm³)": np.mean([r["v"].sum() for r in rs]),
                       "Turbinado médio (m³/s)": np.mean([r["q"].sum() for r in rs]),
                       "Vertido médio (m³/s)": np.mean([r["s"].sum() for r in rs]),
                       "Térmica média (MW)": np.mean([r["g"].sum() for r in rs]),
                       "Déficit médio (MW)": np.mean([r["d"] for r in rs]),
                       "P(déficit > 0)": np.mean([r["d"] > 1e-6 for r in rs]),
                       "CMO médio (R$/MWh)": np.mean([r.get("cmo", np.nan) for r in rs]),
                       "Valor da água médio (R$/hm³)": np.mean([-r.get("pi", np.full(1, np.nan)).sum() for r in rs])})
    return linhas
