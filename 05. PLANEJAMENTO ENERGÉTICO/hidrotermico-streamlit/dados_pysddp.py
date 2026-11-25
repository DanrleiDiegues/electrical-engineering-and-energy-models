"""Dados "ao vivo" de Batalha e Serra do Facão, lidos dos arquivos do NEWAVE com os leitores do PySDDP.

Nada aqui é digitado à mão: volumes, máquinas, produtibilidade e vazões saem de HIDR.DAT e VAZOES.DAT
(amostra pública do repositório do PySDDP) e as térmicas saem do deck DESSEM lido em catalogo_dessem.py.
Os modelos (PL Único, PDDD, árvore, PDDE) recebem o sistema já montado por estas funções.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from PySDDP.newave.script.hidr import Hidr
from PySDDP.newave.script.vazoes import Vazoes

PASTA = Path(__file__).with_name("dados_pysddp")

# Códigos das usinas no HIDR.DAT. Batalha (20) descarrega em Serra do Facão (21).
CODIGOS = {"Batalha": 20, "Serra do Facão": 21}

# VAZOES.DAT desta amostra: 320 postos, histórico a partir de 1931.
NR_POSTOS, ANO_BASE = 320, 1931

# Uma vazão de 1 m³/s durante um mês de 720 h equivale a 2,592 hm³.
HORAS = 720
FATOR = HORAS * 3600 / 1e6

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# Térmicas da disciplina, identificadas pelo código no deck DESSEM (termdat.dat).
TERMICAS_DESSEM = {"BBF Baliza": (322, 1), "ERB Candeias": (106, 1)}


@lru_cache(maxsize=1)
def leitores(pasta=PASTA):
    """Lê HIDR.DAT (cadastro) e VAZOES.DAT (histórico de vazões naturais) com o PySDDP."""
    pasta = Path(pasta)
    cadastro = Hidr()
    cadastro.ler(str(pasta / "HIDR.DAT"))
    vazoes = Vazoes()
    vazoes.ler(str(pasta / "VAZOES.DAT"), NR_POSTOS)
    return cadastro, vazoes


def _usina(registro):
    """Converte um registro do HIDR.DAT nos parâmetros que os modelos lineares usam."""
    conjuntos = int(registro["num_conj_maq"])
    maquinas = np.array(registro["maq_por_conj"][:conjuntos], dtype=float)

    # Engolimento: soma das vazões efetivas de todas as máquinas (m³/s).
    q_conj = maquinas * np.array(registro["vaz_efet_conj"][:conjuntos], dtype=float)
    q_nominal = float(q_conj.sum())

    # Potência instalada: soma das potências efetivas (MW).
    potencia = float(maquinas @ np.array(registro["pef_por_conj"][:conjuntos], dtype=float))

    # Produtibilidade constante = produtibilidade específica × queda líquida nominal.
    # Hipótese do curso: sem polinômios cota-volume, a queda não varia com o armazenamento.
    queda = float(q_conj @ np.array(registro["alt_efet_conj"][:conjuntos], dtype=float) / q_nominal)
    perda = registro["perda_hid"]
    queda_liquida = queda - perda if registro["tipo_perda"] == 2 else queda * (1 - perda / 100)
    return dict(codigo=int(registro["codigo"]), posto=int(registro["posto"]), jusante=int(registro["jusante"]),
                vmin=float(registro["vol_min"]), vmax=float(registro["vol_max"]),
                prod=float(registro["prod_esp"] * queda_liquida), qmax=q_nominal, potencia=potencia)


@lru_cache(maxsize=1)
def cadastro_uhes():
    """Batalha e Serra do Facão como saem do HIDR.DAT (MW/(m³/s), m³/s, hm³, MW)."""
    cadastro, _ = leitores()
    usinas = {}
    for nome, codigo in CODIGOS.items():
        registro = cadastro.get(codigo)
        if registro is None:
            raise ValueError(f"{nome} (código {codigo}) não está no HIDR.DAT.")
        usinas[nome] = _usina(registro)
    return usinas


@lru_cache(maxsize=1)
def historico_local():
    """Vazões LOCAIS (m³/s) de todo o histórico: matriz [ano, mês, usina].

    O VAZOES.DAT traz vazões NATURAIS. A natural de Serra já contém a água que chega de Batalha;
    como o balanço hídrico soma a descarga de Batalha em Serra, usamos a incremental
    (natural de Serra − natural de Batalha) para não contar a mesma água duas vezes.
    """
    _, vazoes = leitores()
    usinas = cadastro_uhes()
    naturais = np.stack([vazoes.vaz_nat[:, :, u["posto"] - 1] for u in usinas.values()], axis=-1).astype(float)
    locais = naturais.copy()
    codigos = [u["codigo"] for u in usinas.values()]
    for i, codigo in enumerate(codigos):
        for j, u in enumerate(usinas.values()):
            if u["jusante"] == codigo:
                locais[..., i] -= naturais[..., j]

    # Anos sem dados (zeros no fim do arquivo) ficam de fora.
    validos = np.all(naturais > 0, axis=(1, 2))
    anos = ANO_BASE + np.flatnonzero(validos)
    return anos, np.maximum(locais[validos], 0.)


def anos_disponiveis():
    anos, _ = historico_local()
    return int(anos[0]), int(anos[-1])


def calendario(ano, mes_inicial, n_meses):
    """Lista de (ano, mês) a partir de mes_inicial (1 a 12)."""
    return [(ano + (mes_inicial - 1 + t) // 12, (mes_inicial - 1 + t) % 12 + 1) for t in range(n_meses)]


def vazoes_trajetoria(ano, mes_inicial, n_meses):
    """Vazões locais (m³/s) observadas em n_meses consecutivos do histórico. Matriz [mês, usina]."""
    anos, locais = historico_local()
    linhas = []
    for a, m in calendario(ano, mes_inicial, n_meses):
        if a not in anos:
            raise ValueError(f"{MESES[m-1]}/{a} está fora do histórico ({anos[0]}–{anos[-1]}).")
        linhas.append(locais[int(np.flatnonzero(anos == a)[0]), m - 1])
    return np.array(linhas)


def termicas_dessem():
    """Potência máxima e CVU de Baliza e Candeias lidos do deck DESSEM pelo PySDDP."""
    from catalogo_dessem import carregar_catalogo
    catalogo = carregar_catalogo()
    termicas = []
    for nome, (codigo, ug) in TERMICAS_DESSEM.items():
        d = next((d for d in catalogo.values() if d["codigo"] == codigo and d["ug"] == ug), None)
        if d is None:
            raise ValueError(f"{nome} não está no catálogo DESSEM.")
        termicas.append(dict(Nome=nome, Pmax=float(d["Pmax"]), CVU=float(d["cvu"])))
    return termicas


def sistema_pysddp(ano=2015, mes_inicial=9, n_meses=24, carga=250., vi_pct=(39.7, 50.2), cdef=4000.,
                   termicas=None):
    """Monta o dicionário `sistema` (formato do PL Único) com dados lidos ao vivo pelo PySDDP.

    Unidades internas do PL: volumes em hm³, afluência e turbinamento em hm³/mês, custos já multiplicados por 720 h.
    """
    usinas = cadastro_uhes()
    vazoes = vazoes_trajetoria(ano, mes_inicial, n_meses)
    if termicas is None:
        termicas = termicas_dessem()
    meses = [f"{MESES[m-1][:3]}/{a}" for a, m in calendario(ano, mes_inicial, n_meses)]
    uhes = []
    for i, (nome, u) in enumerate(usinas.items()):
        uhes.append({"Nome": nome, "Vmin": u["vmin"], "Vmax": u["vmax"],
                     "VI": u["vmin"] + vi_pct[i] / 100 * (u["vmax"] - u["vmin"]),
                     # Prod em MW por hm³/mês e engolimento em hm³/mês (mesma convenção do Colab).
                     "Prod": u["prod"] / FATOR, "Engol": u["qmax"] * FATOR, "Potencia": u["potencia"],
                     "Jusante": 1 if i == 0 else None,
                     # Uma única "abertura" por mês: a trajetória é conhecida (problema determinístico).
                     "Afl": [[float(q) * FATOR] for q in vazoes[:, i]]})
    utes = [{"Nome": t["Nome"], "Capac": float(t["Pmax"]), "Custo": float(t["CVU"]) * HORAS} for t in termicas]
    carga = [float(carga)] * n_meses if np.isscalar(carga) else [float(c) for c in carga]
    return {"DGer": {"Meses": meses, "Carga": carga, "Horas": HORAS, "CDef": cdef * HORAS, "Nr_Disc": 5},
            "UHE": uhes, "UTE": utes}


def tabela_cadastro():
    """Resumo do que foi lido, para mostrar na interface."""
    return pd.DataFrame([{"Usina": n, "Código HIDR": u["codigo"], "Posto": u["posto"],
                          "Volume mínimo (hm³)": u["vmin"], "Volume máximo (hm³)": u["vmax"],
                          "Engolimento (m³/s)": u["qmax"], "Potência (MW)": u["potencia"],
                          "Produtibilidade (MW/(m³/s))": u["prod"]} for n, u in cadastro_uhes().items()])


def aberturas_historicas(mes_inicial, n_meses):
    """Árvore binária a partir do histórico: em cada mês, duas aberturas equiprováveis.

    Abertura "seca" = média dos anos abaixo da mediana daquele mês; "úmida" = média dos anos acima.
    O primeiro mês é a média histórica (afluência já observada). Valores em m³/s, matriz por usina.
    """
    _, locais = historico_local()
    aberturas = []
    for t in range(n_meses):
        m = (mes_inicial - 1 + t) % 12
        serie = locais[:, m, :]
        if t == 0:
            aberturas.append([(1., serie.mean(axis=0))])
            continue
        total = serie.sum(axis=1)
        seco = total <= np.median(total)
        aberturas.append([(.5, serie[seco].mean(axis=0)), (.5, serie[~seco].mean(axis=0))])
    return aberturas
