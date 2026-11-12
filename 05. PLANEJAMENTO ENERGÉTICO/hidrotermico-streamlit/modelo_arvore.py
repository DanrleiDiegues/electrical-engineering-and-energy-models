import numpy as np
import pandas as pd
from pyscipopt import Model, quicksum, SCIP_PARAMSETTING

# Cada abertura contém o vetor de afluências LOCAIS observado naquele nó.
# No exemplo do quadro os números de AFL são adotados em hm³/estágio.
quadro = dict(nomes=["UHE didática"], vmin=np.array([20.]), vmax=np.array([100.]),
              vi=np.array([65.]), prod=np.array([.95]), qmax=np.array([60.]), mont=[[]],
              termicas=["GT 1","GT 2"], gtmax=[15.,10.], cvu=[10.,25.], cdef=500.,
              horas=1., escala=1., carga=[50.,50.,50.], unidade="$ didáticos",
              aberturas=[[(1.,[15.])],[(.5,[16.]),(.5,[19.])],[(.5,[20.]),(.5,[25.])]],
              afl_cont=[15.], carga_cont=50.)
# No caso das nossas usinas, entradas em m³/s são convertidas para volume mensal.
fator=720*3600/1e6
minimos=np.array([430.049988,1752.])
maximos=np.array([1781.609985,5199.])
disciplina=dict(nomes=["Batalha","Serra do Facão"],vmin=minimos,vmax=maximos,
                vi=minimos+[.397,.502]*(maximos-minimos),prod=np.array([.009025*(37.70-1.20),.6157])/fator,
                qmax=np.array([147.02,min(313.,212.58/.6157)])*fator, mont=[[],[0]],
                termicas=["BBF Baliza","ERB Candeias"],gtmax=[10.,17.],cvu=[882.76,118.93],
                cdef=4000.,horas=720.,escala=1e6,carga=[250.,250.,250.],unidade="R$",
                aberturas=[[(1.,fator*np.array([20.,24.]))],
                           [(.5,fator*np.array([25.,29.])),(.5,fator*np.array([35.,93.]))],
                           [(.5,fator*np.array([30.,20.])),(.5,fator*np.array([40.,176.]))]],
                afl_cont=fator*np.array([20.,24.]),carga_cont=250.)

def construir_arvore(aberturas):
    pais=[None]
    arvore={}
    for t,opcoes in enumerate(aberturas):
        if not opcoes or not np.isclose(sum(p for p,_ in opcoes),1) or any(p<=0 for p,_ in opcoes):
            raise ValueError(f"Probabilidades condicionais inválidas no mês {t+1}.")
        if t==0 and len(opcoes)!=1: raise ValueError("O primeiro estágio deve ter uma única afluência observada.")
        filhos=[]
        for pai in pais:
            for j,(p,afl) in enumerate(opcoes):
                no=(pai or ())+(j,)
                arvore[no]=dict(t=t,pai=pai,afl=np.asarray(afl,dtype=float),
                                prob=p*(arvore[pai]["prob"] if pai is not None else 1.))
                filhos.append(no)
        pais=filhos
    return arvore

def rotulo(no):
    return "R" if len(no)==1 else "R"+"".join(str(k+1) for k in no[1:])
def bloco_fisico(m,c,vi,afl,carga,nome):
    # vi admite tanto um número conhecido como a variável VF do nó pai.
    nh=range(len(c["nomes"]))
    v=[m.addVar(lb=c["vmin"][i],ub=c["vmax"][i],name=f"VF_{nome}_{i}") for i in nh]
    q=[m.addVar(lb=0,ub=c["qmax"][i],name=f"VT_{nome}_{i}") for i in nh]
    s=[m.addVar(lb=0,name=f"VV_{nome}_{i}") for i in nh]
    g=[m.addVar(lb=0,ub=lim,name=f"GT_{nome}_{j}") for j,lim in enumerate(c["gtmax"])]
    d=m.addVar(lb=0,name=f"DEF_{nome}")
    bh=[]
    for i in nh:
        recebida=quicksum(q[j]+s[j] for j in c["mont"][i])
        bh.append(m.addCons(v[i]+q[i]+s[i]-recebida == vi[i]+afl[i]))
    m.addCons(quicksum(c["prod"][i]*q[i] for i in nh)+quicksum(g)+d == carga)
    ci=c["horas"]*(quicksum(custo*x for custo,x in zip(c["cvu"],g))+c["cdef"]*d)+.01*quicksum(s)
    return dict(v=v,q=q,s=s,g=g,d=d,ci=ci,bh=bh)

def cortes_da_continuacao(c):
    # Um mês adicional conhecido representa a continuação didática. Cada dual dá um plano de suporte.
    cortes=[]
    for fracao in (0.,.22):
        estado=c["vmin"]+fracao*(c["vmax"]-c["vmin"])
        m=Model("PL auxiliar para o corte terminal")
        try:
            m.hideOutput()
            m.setPresolve(SCIP_PARAMSETTING.OFF); m.setHeuristics(SCIP_PARAMSETTING.OFF)
            m.disablePropagation();m.setBoolParam("lp/alwaysgetduals",True)
            reg=bloco_fisico(m,c,estado,c["afl_cont"],c["carga_cont"],"continua")
            m.setObjective(reg["ci"]/c["escala"],"minimize")
            m.optimize()
            if m.getStatus()!="optimal": raise RuntimeError(m.getStatus())
            custo=m.getObjVal()*c["escala"]
            a=np.array([m.getDualsolLinear(restr)*c["escala"] for restr in reg["bh"]])
            cortes.append((a,float(custo-a@estado)))
        finally:
            m.freeProb()
    return cortes

def resolver_arvore(c,arvore,cortes=()):
    T=len(c["carga"])
    if not arvore or max(r["t"] for r in arvore.values())!=T-1:
        raise ValueError("Carga e horizonte da árvore incompatíveis.")
    m=Model("PL único com recurso multiestágio")
    try:
        m.hideOutput()
        m.setRealParam("numerics/feastol",1e-9)
        m.setRealParam("numerics/dualfeastol",1e-9)
        blocos={};objetivo=[]
        for no,r in arvore.items():
            pai=r["pai"]
            vi=c["vi"] if pai is None else blocos[pai]["v"]
            b=blocos[no]=bloco_fisico(m,c,vi,r["afl"],c["carga"][r["t"]],rotulo(no))
            alpha=None
            if r["t"]==T-1:
                alpha=m.addVar(lb=0,name="alpha_"+rotulo(no))
                for a,intercepto in cortes:
                    m.addCons(alpha >= (intercepto+quicksum(float(k)*v for k,v in zip(a,b["v"])))/c["escala"])
                if not len(cortes): m.addCons(alpha==0)
            b["alpha"]=alpha
            objetivo.append(r["prob"]*(b["ci"]/c["escala"]+(alpha if alpha is not None else 0.)))
        m.setObjective(quicksum(objetivo),"minimize")
        m.optimize()
        if m.getStatus()!="optimal": raise RuntimeError(f"SCIP: {m.getStatus()}")
        resultado={}
        for no,b in blocos.items():
            nums={k:np.array([m.getVal(x) for x in b[k]]) for k in ["v","q","s","g"]}
            resultado[no]=dict(**nums,d=m.getVal(b["d"]),ci=m.getVal(b["ci"]),
                                alpha=m.getVal(b["alpha"])*c["escala"] if b["alpha"] is not None else 0.)
        return float(m.getObjVal()*c["escala"]),resultado
    finally:
        m.freeProb()

