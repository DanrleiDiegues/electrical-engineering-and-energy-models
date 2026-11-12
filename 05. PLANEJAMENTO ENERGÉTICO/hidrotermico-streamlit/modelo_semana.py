import numpy as np
import pandas as pd
from pyscipopt import Model, quicksum, SCIP_PARAMSETTING
HIDRO = {"Vmin":430.049988, "Vmax":1781.609985, "Qmax":147.02, "rho":0.009025*(37.70-1.20)}
HIDRO["VI"] = HIDRO["Vmin"]+0.397*(HIDRO["Vmax"]-HIDRO["Vmin"])
AFLUENCIA = 70.0  # m³/s, afluência constante de estudo
CDEF = 4000.0  # R$/MWh
CORTES = [(HIDRO["VI"]-6,12500.),(HIDRO["VI"]-12,46000.)]  # alvo hm³, inclinação em módulo R$/hm³
horas_semana = np.arange(168)
perfil_dia = np.array([35,33,32,31,32,35,40,47,52,55,57,56,
                       54,53,54,57,60,65,69,70,67,60,49,40],dtype=float)
demanda_semana = np.tile(perfil_dia,7) + np.repeat([0,1,0,2,0,-5,-7],24)
from math import ceil
from copy import deepcopy

def despachar_semana(unidades, demanda, usar_fcf=True, limite_s=120, fixos=None):
    """Resolve o compromisso semanal. Com `fixos`, resolve o LP com estados e eventos fixos e devolve os duais (CMO e CMA)."""
    horas = range(len(demanda))
    passos = range(2*len(demanda))
    dt, fator = 0.5, 0.0018  # meia hora e hm³ por m³/s a cada meia hora
    m = Model("UCT semanal com trajetórias de meia hora")
    m.hideOutput()
    m.setRealParam("numerics/feastol",1e-8)
    m.setRealParam("limits/time",float(limite_s))
    if fixos is not None:
        # Com os binários fixos o problema é linear: os duais do balanço de carga e do balanço hídrico são os custos marginais.
        m.setPresolve(SCIP_PARAMSETTING.OFF); m.setHeuristics(SCIP_PARAMSETTING.OFF)
        m.disablePropagation(); m.setBoolParam("lp/alwaysgetduals", True)

    def binaria(grupo, nome_var, chave):
        if fixos is None:
            return m.addVar(vtype="B", name=nome_var)
        valor = float(fixos[grupo][chave])
        return m.addVar(lb=valor, ub=valor, name=nome_var)

    u, ligar, desligar, p, normal = {}, {}, {}, {}, {}
    for nome, d in unidades.items():
        ton, toff = d["Ton"], d["Toff"]
        if min(ton,toff) < 1 or int(ton)!=ton or int(toff)!=toff:
            raise ValueError("Ton e Toff devem ser números inteiros positivos de horas.")
        for h in horas:
            u[nome,h] = binaria("u", f"ligada_{nome}_{h}", (nome,h))
            ligar[nome,h] = binaria("ligar", f"partida_{nome}_{h}", (nome,h))
            desligar[nome,h] = binaria("desligar", f"desligamento_{nome}_{h}", (nome,h))
        for h in horas:
            anterior = u[nome,h-1] if h else d["u0"]
            y, w = ligar[nome,h], desligar[nome,h]
            m.addCons(u[nome,h]-anterior == y-w)
            m.addCons(y <= u[nome,h])
            m.addCons(y <= 1-anterior)
            m.addCons(quicksum(ligar[nome,i] for i in range(max(0,h-ton+1),h+1)) <= u[nome,h])
            m.addCons(quicksum(desligar[nome,i] for i in range(max(0,h-toff+1),h+1)) <= 1-u[nome,h])
            if h < max(0,ceil((ton if d["u0"] else toff)-d["idade"])):
                m.addCons(u[nome,h] == d["u0"])
            # A semana termina com todas as novas obrigações cumpridas.
            if h+max(ton,len(d["A"])//2)>len(demanda): m.addCons(y==0)
            if h+toff>len(demanda) or 2*h<len(d["D"]): m.addCons(w==0)
        for k in passos:
            h = k//2
            eventos = []
            for j,valor in enumerate(d["A"]):
                inicio=k-j
                if inicio>=0 and inicio%2==0:
                    eventos.append((ligar[nome,inicio//2],valor))
            for j,valor in enumerate(d["D"]):
                fim=k+len(d["D"])-j
                if fim%2==0 and fim//2<len(demanda):
                    eventos.append((desligar[nome,fim//2],valor))
            ocupada = quicksum(evento for evento,valor in eventos)
            alvo = quicksum(valor*evento for evento,valor in eventos)
            normal[nome,k]=u[nome,h]-ocupada
            m.addCons(normal[nome,k]>=0)  # impede sobreposição entre duas trajetórias
            g=p[nome,k]=m.addVar(lb=0,ub=d["Pmax"])
            m.addCons(g>=d["Pmin"]*normal[nome,k]+alvo)
            m.addCons(g<=d["Pmax"]*normal[nome,k]+alvo)
            g0=p[nome,k-1] if k else d["p0"]
            n0=normal[nome,k-1] if k else d["u0"]
            relax=d["Pmax"]*(2-normal[nome,k]-n0)
            m.addCons(g-g0<=dt*d["subida"]+relax)
            m.addCons(g0-g<=dt*d["descida"]+relax)
            # Chegada ao regime livre e preparação para entrar na curva de parada.
            apos=k-len(d["A"])
            if apos>=0 and apos%2==0:
                m.addCons(g<=d["Pmin"]+dt*d["subida"]+d["Pmax"]*(1-ligar[nome,apos//2]))
            fim=k+1+len(d["D"])
            if fim%2==0 and fim//2<len(demanda):
                m.addCons(g<=d["Pmin"]+d["Pmax"]*(1-desligar[nome,fim//2]))
    vol, vazao, vert, deficit, cons_agua, cons_carga = {}, {}, {}, {}, {}, {}
    for k in passos:
        vol[k]=m.addVar(lb=HIDRO["Vmin"],ub=HIDRO["Vmax"])
        vazao[k]=m.addVar(lb=0,ub=HIDRO["Qmax"])
        vert[k]=m.addVar(lb=0)
        deficit[k]=m.addVar(lb=0)
        vi=vol[k-1] if k else HIDRO["VI"]
        cons_agua[k]=m.addCons(vol[k]==vi+fator*(AFLUENCIA-vazao[k]-vert[k]))
        cons_carga[k]=m.addCons(HIDRO["rho"]*vazao[k]+quicksum(p[n,k] for n in unidades)+deficit[k]==demanda[k//2])
    futuro=m.addVar(lb=0,ub=None if usar_fcf else 0)
    if usar_fcf:
        for alvo, valor in CORTES:
            m.addCons(futuro>=valor*(alvo-vol[passos[-1]]))
    imediato=quicksum(dt*(quicksum(d["cvu"]*p[n,k] for n,d in unidades.items())+CDEF*deficit[k])
                      +0.01*fator*vert[k] for k in passos)
    partida=quicksum(d["partida"]*ligar[n,h] for n,d in unidades.items() for h in horas)
    m.setObjective((imediato+partida+futuro)/1e6,"minimize")
    try:
        m.optimize()
        if not m.getNSols(): raise RuntimeError(f"SCIP sem solução viável: {m.getStatus()}")
        if fixos is not None:
            # CMO em R$/MWh e CMA em R$/hm³; o objetivo foi dividido por 1e6 e o intervalo dura dt horas.
            return dict(cmo=[m.getDualsolLinear(cons_carga[k])*1e6/dt for k in passos],
                        cma=[-m.getDualsolLinear(cons_agua[k])*1e6 for k in passos],
                        total=m.getObjVal()*1e6)
        melhor=m.getBestSol()
        val=lambda x: m.getSolVal(melhor,x)
        for variaveis in (u,ligar,desligar):
            if any(abs(val(x)-round(val(x)))>1e-6 for x in variaveis.values()):
                raise RuntimeError("Solução com estado ou evento fracionário.")
        meia=pd.DataFrame([{"hora":k/2,"carga":demanda[k//2],"UHE":HIDRO["rho"]*val(vazao[k]),
                            "q":val(vazao[k]),"vert":val(vert[k]),"volume":val(vol[k]),"déficit":val(deficit[k]),
                            **{n:val(p[n,k]) for n in unidades}} for k in passos])
        estados=pd.DataFrame([{ "hora":h, "unidade":n, "ligada":round(val(u[n,h])),
                         "partida":round(val(ligar[n,h])), "desligada":round(val(desligar[n,h]))}
                         for n in unidades for h in horas])
        resultado = dict(meia=meia, estados=estados, status=str(m.getStatus()),gap=m.getGap(),
                         imediato=val(imediato)+val(partida),futuro=val(futuro),total=m.getObjVal()*1e6,
                         inferior=m.getDualbound()*1e6, segundos=m.getSolvingTime(),
                         mwh_por_hm3=HIDRO["rho"]*dt/fator, marginais=False)
        fixados = {"u": {(n,h): round(val(u[n,h])) for n in unidades for h in horas},
                   "ligar": {(n,h): round(val(ligar[n,h])) for n in unidades for h in horas},
                   "desligar": {(n,h): round(val(desligar[n,h])) for n in unidades for h in horas}}
    finally:
        m.freeProb()
    try:
        lp = despachar_semana(unidades, demanda, usar_fcf, limite_s, fixos=fixados)
        meia = resultado["meia"]
        meia["cmo"], meia["cma"] = lp["cmo"], lp["cma"]
        meia["cma_mwh"] = meia["cma"] / resultado["mwh_por_hm3"]
        resultado["marginais"] = abs(lp["total"] - resultado["total"]) <= 1e-3 * max(1., abs(resultado["total"]))
    except RuntimeError:
        pass
    return resultado


def impacto_carga(unidades, demanda, usar_fcf, hora, delta):
    """Variação do custo total ao somar `delta` MW à carga de uma hora, com o compromisso reotimizado."""
    nova = np.array(demanda, dtype=float)
    nova[hora] += delta
    return despachar_semana(unidades, nova, usar_fcf)["total"]
