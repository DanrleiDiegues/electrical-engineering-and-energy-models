"""Cálculos da API, em Python puro (sem FastAPI e sem Streamlit).

Cada função recebe dados simples e devolve dicionários prontos para virar JSON.
A matemática está nos módulos da pasta acima (modelo_semana, modelo_arvore, analise_semana);
aqui só se monta a entrada e se formata a saída.
"""
import numpy as np

from mercado_semana import ordem_merito, explicacao_merito, resumo_diario
from catalogo_dessem import carregar_catalogo
from modelo_arvore import disciplina, fator, estudo_arvore, rotulo
from modelo_semana import HIDRO, CDEF, demanda_semana, despachar_semana, impacto_carga

CAMPOS = ("Ton", "Toff", "Pmin", "Pmax", "subida", "descida", "cvu", "partida")


class ErroDeEntrada(ValueError):
    """Entrada inválida (nome de usina desconhecido, etc.)."""


def limpa(x):
    """Converte numpy/NaN para tipos que o JSON aceita."""
    if isinstance(x, dict):
        return {str(k): limpa(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpa(v) for v in x]
    if isinstance(x, np.ndarray):
        return limpa(x.tolist())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if x != x else float(x)
    return x


# ---------- Catálogo (usinas lidas pelo PySDDP) ----------

def catalogo():
    """Usinas que o modelo aceita, com os valores de cadastro de cada uma."""
    return [{"nome": nome, "codigo": d["codigo"], "ug": d["ug"], "cadastro": {c: d[c] for c in CAMPOS},
             "piso_pmax": max(max(d["A"] + d["D"]), 0.1)}
            for nome, d in carregar_catalogo().items()]


# ---------- DESSEM semanal ----------

def montar_unidades(escolhas):
    """Cadastro + ajustes do usuário, com as mesmas regras do app: Pmax não desce abaixo das
    trajetórias de partida/parada e Pmin não passa de Pmax."""
    base = carregar_catalogo()
    unidades = {}
    for e in escolhas:
        if e["nome"] not in base:
            raise ErroDeEntrada(f'Usina "{e["nome"]}" não está no catálogo.')
        d = dict(base[e["nome"]])
        for campo, valor in (e.get("ajustes") or {}).items():
            if valor is not None:
                d[campo] = valor
        d["Pmax"] = max(d["Pmax"], max(d["A"] + d["D"]), 0.1)
        d["Pmin"] = min(d["Pmin"], d["Pmax"])
        unidades[e["nome"]] = d
    return unidades


def calcular_semana(escolhas, percentual_carga=100., custo_futuro=True, hora_impacto=None, delta_impacto=1.):
    unidades = montar_unidades(escolhas)
    carga = demanda_semana * percentual_carga / 100
    r = despachar_semana(unidades, carga, custo_futuro)
    meia, estados = r["meia"], r["estados"]
    nomes = list(unidades)
    saida = {
        "resumo": {"custo_total": r["total"], "custo_imediato": r["imediato"], "custo_futuro": r["futuro"],
                   "deficit_mwh": meia["déficit"].sum() * 0.5, "volume_final": meia["volume"].iloc[-1],
                   "volume_inicial": HIDRO["VI"], "partidas": int(estados["partida"].sum()),
                   "uhe_mwh": meia["UHE"].sum() * 0.5, "termica_mwh": meia[nomes].sum().sum() * 0.5,
                   "status": r["status"], "gap": r["gap"], "segundos": r["segundos"]},
        "unidades": {n: {c: d[c] for c in CAMPOS} for n, d in unidades.items()},
        "meia_hora": meia.round(6).to_dict(orient="list"),   # colunas: hora, carga, UHE, volume, cmo, cma, ...
        "estados": estados.to_dict(orient="records"),
        "diario": resumo_diario(meia).to_dict(orient="records") if "cmo" in meia else None,
        "capacidade": sum(d["Pmax"] for d in unidades.values()) + HIDRO["rho"] * HIDRO["Qmax"],
    }
    if "cma_mwh" in meia:
        tabela = ordem_merito(r, unidades)
        saida["merito"] = {"tabela": tabela.to_dict(orient="records"),
                           "explicacao": explicacao_merito(tabela, custo_futuro)}
    if hora_impacto is not None and "cmo" in meia:
        previsto = delta_impacto * 0.5 * (meia.cmo[2 * hora_impacto] + meia.cmo[2 * hora_impacto + 1])
        real = impacto_carga(unidades, carga, custo_futuro, hora_impacto, delta_impacto) - r["total"]
        saida["impacto"] = {"hora": hora_impacto, "delta_mw": delta_impacto, "previsto": previsto,
                            "real": real, "diferenca": real - previsto}
    return limpa(saida)


# ---------- PL Único em árvore ----------

def padroes_arvore():
    """Parâmetros iniciais do estudo (os mesmos que o app Streamlit mostra)."""
    uhes = []
    for i in range(2):
        util = disciplina["vmax"][i] - disciplina["vmin"][i]
        uhes.append(dict(vmin=disciplina["vmin"][i], vmax=disciplina["vmax"][i],
                         vi=round(100 * (disciplina["vi"][i] - disciplina["vmin"][i]) / util, 1),
                         qmax=round(disciplina["qmax"][i] / fator, 2), prod=round(disciplina["prod"][i] * fator, 6)))
    return limpa({"carga": 250., "cdef": 4000., "afl": 100., "nomes_uhe": disciplina["nomes"], "uhes": uhes,
                   "termicas": _termicas_padrao()})


def _termicas_padrao():
    """Baliza UG 1 e Candeias UG 1, com potência e CVU do estudo mensal."""
    cat = carregar_catalogo()
    termicas = []
    for i, nome in enumerate(["BBF BALIZA · UG 1", "ERB CANDEIAS · UG 1"]):
        if nome not in cat:
            raise ErroDeEntrada(f"Térmica padrão ausente do catálogo: {nome}")
        termicas.append(dict(nome=nome, pmax=float(disciplina["gtmax"][i]), cvu=float(disciplina["cvu"][i])))
    return termicas


def calcular_arvore(meses=3, carga=None, cdef=None, afl=100., uhes=None, termicas=None):
    padrao = padroes_arvore()
    termicas = termicas or _termicas_padrao()
    uhes = uhes or padrao["uhes"]
    p = dict(carga=padrao["carga"] if carga is None else carga, cdef=padrao["cdef"] if cdef is None else cdef, afl=afl,
             uhes=[(u["vmin"], u["vmax"], u["vi"], u["qmax"], u["prod"]) for u in uhes],
             termicas=[(t["nome"], t["pmax"], t["cvu"]) for t in termicas])
    custo, caso, arv, sol = estudo_arvore([t["nome"] for t in termicas], meses, p)
    nos = []
    for no, b in sol.items():
        nos.append({"id": rotulo(no), "pai": rotulo(arv[no]["pai"]) if arv[no]["pai"] is not None else None,
                    "mes": len(no), "probabilidade": arv[no]["prob"],
                    "afluencia_m3s": [v / fator for v in arv[no]["afl"]],
                    "volume_final": list(b["v"]), "geracao_uhe": list(caso["prod"] * b["q"]),
                    "geracao_termica": list(b["g"]), "deficit": b["d"],
                    "custo_imediato": b["ci"], "custo_futuro": b["alpha"], "folha": not any(arv[o]["pai"] == no for o in arv)})
    return limpa({"custo_esperado": custo, "meses": meses, "uhes": caso["nomes"],
                   "termicas": [t["nome"] for t in termicas], "nos": nos})
