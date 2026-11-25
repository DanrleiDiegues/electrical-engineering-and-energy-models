"""COBRE × nossa PDDE no 1dtoy: leitura dos resultados do novomodelo e cálculo (ou leitura) dos nossos.

O binário do novomodelo (Rust, glibc ≥ 2.38) não roda no Streamlit Cloud nem no Colab, por isso os resultados
do COBRE foram gerados fora (v0.22.0, HiGHS 1.13.1) e ficam em dados_cobre/:
- resumo_<config>.json: limites, tempos, aberturas sorteadas pelo COBRE;
- convergencia_<config>.csv: Zinf e Zsup por iteração;
- teste_<config>.csv.gz: a política do COBRE simulada em 2000 cenários FORA DA AMOSTRA (semente 777).
Os mesmos 2000 cenários servem para as duas configurações e para a nossa PDDE: comparação pareada.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import pdde_model as pm

PASTA = Path(__file__).with_name("dados_cobre")

# Configurações do estudo: a do exemplo oficial do COBRE e a do trabalho de PDDE da disciplina (3 aberturas, 10 forwards).
CONFIGS = {"original": dict(rotulo="Exemplo oficial do 1dtoy", aberturas=10, forwards=1, iteracoes=128),
           "professor": dict(rotulo="Configuração do trabalho de PDDE", aberturas=3, forwards=10, iteracoes=50)}


def resumo_cobre(config):
    return json.loads((PASTA / f"resumo_{config}.json").read_text())


def convergencia_cobre(config):
    return pd.read_csv(PASTA / f"convergencia_{config}.csv")


def teste_cobre(config):
    """Simulação da política do COBRE no conjunto de teste (uma linha por cenário e estágio)."""
    return pd.read_csv(PASTA / f"teste_{config}.csv.gz")


def aberturas_cobre(config):
    """As aberturas (m³/s) que o COBRE sorteou: usamos AS MESMAS no cálculo da política da PDDE UFJF, para isolar o método."""
    return [np.array(a, float).reshape(-1, 1) for a in resumo_cobre(config)["aberturas_m3s"]]


def cenarios_teste():
    """Afluências dos 2000 cenários de teste, matriz (S, T, 1). São idênticas nas duas configurações."""
    t = teste_cobre("original").sort_values(["scenario_id", "stage_id"])
    S, T = t.scenario_id.nunique(), t.stage_id.nunique()
    return t.inflow_m3s.to_numpy().reshape(S, T, 1)


def calcular_nosso(config, progresso=None, n_teste=None):
    """Calcula a política da PDDE UFJF com as aberturas do COBRE e a simula nos cenários de teste."""
    c = CONFIGS[config]
    caso = pm.caso_1dtoy()
    ab = aberturas_cobre(config)
    treino = pm.pdde(caso, ab, n_forward=c["forwards"], max_iter=c["iteracoes"], semente=42, progresso=progresso)
    cen = cenarios_teste()[:n_teste]
    custos, traj = pm.simular(caso, treino["cortes"], cen)

    # Ótimo exato da árvore de aberturas (equivalente determinístico): é o valor para onde Zinf deve convergir.
    otimo = pm.equivalente_deterministico(caso, ab)
    linhas = []
    for s, tr in enumerate(traj):
        for t, r in enumerate(tr):
            linhas.append(dict(scenario_id=s, stage_id=t, inflow_m3s=float(r["afl"][0]), storage_initial_hm3=float(r["vi"][0]),
                               storage_final_hm3=float(r["v"][0]), turbined_m3s=float(r["q"][0]), spillage_m3s=float(r["s"][0]),
                               ute1_mw=float(r["g"][0]), ute2_mw=float(r["g"][1]), deficit_mw=float(r["d"]),
                               spot_price=float(r["cmo"]), water_value_per_hm3=float(r["pi"][0]),
                               discounted_immediate_cost=float(custos[s])))
    hist = pd.DataFrame(treino["historico"])
    return dict(historico=hist, teste=pd.DataFrame(linhas), segundos=treino["segundos"], otimo=otimo,
                cortes=treino["cortes"])


def salvar_nosso(config, r):
    r["historico"].to_csv(PASTA / f"nosso_convergencia_{config}.csv", index=False)
    r["teste"].to_csv(PASTA / f"nosso_teste_{config}.csv.gz", index=False, float_format="%.6f")
    cortes = [[(list(map(float, a)), float(b)) for a, b in ct] for ct in r["cortes"]]
    (PASTA / f"nosso_resumo_{config}.json").write_text(json.dumps(dict(segundos=r["segundos"], otimo=r["otimo"],
                                                                         cortes=cortes), indent=1))


def carregar_nosso(config):
    """Resultados pré-calculados da nossa PDDE (gerados por `python cobre_dados.py`)."""
    res = json.loads((PASTA / f"nosso_resumo_{config}.json").read_text())
    return dict(historico=pd.read_csv(PASTA / f"nosso_convergencia_{config}.csv"),
                teste=pd.read_csv(PASTA / f"nosso_teste_{config}.csv.gz"), segundos=res["segundos"], otimo=res["otimo"],
                cortes=[[(np.array(a), b) for a, b in ct] for ct in res["cortes"]])


def custos_por_cenario(teste):
    return teste.groupby("scenario_id").discounted_immediate_cost.first().to_numpy()


def comparacao_pareada(cobre, nosso):
    """Diferença de custo cenário a cenário (nosso − COBRE): média, IC95% e em quantos cenários cada um ganha."""
    a, b = custos_por_cenario(cobre), custos_por_cenario(nosso)
    n = min(len(a), len(b))
    d = b[:n] - a[:n]
    return dict(n=n, media_cobre=a[:n].mean(), media_nosso=b[:n].mean(), dif=d.mean(),
                ic95=1.96 * d.std(ddof=1) / np.sqrt(n), iguais=float(np.mean(np.abs(d) <= 1.)),
                nosso_menor=float(np.mean(d < -1.)), cobre_menor=float(np.mean(d > 1.)))


def medias_estagio(teste, meses=("Jan", "Fev", "Mar", "Abr")):
    g = teste.groupby("stage_id")
    df = pd.DataFrame({"Estágio": list(meses),
                       "Volume final (hm³)": g.storage_final_hm3.mean(), "Turbinado (m³/s)": g.turbined_m3s.mean(),
                       "Vertido (m³/s)": g.spillage_m3s.mean(), "UTE1 (MW)": g.ute1_mw.mean(), "UTE2 (MW)": g.ute2_mw.mean(),
                       "Déficit (MW)": g.deficit_mw.mean(), "P(déficit)": g.deficit_mw.apply(lambda x: (x > 1e-6).mean()),
                       "CMO (R$/MWh)": g.spot_price.mean(),
                       # O COBRE publica o valor da água com sinal negativo (dual do balanço); mostramos |·|.
                       "Valor da água (R$/hm³)": g.water_value_per_hm3.apply(lambda x: x.abs().mean())})
    return df.reset_index(drop=True)


if __name__ == "__main__":
    for cfg in CONFIGS:
        r = calcular_nosso(cfg)
        salvar_nosso(cfg, r)
        print(cfg, r["historico"].iloc[-1].to_dict(), "ótimo", r["otimo"], custos_por_cenario(r["teste"]).mean())
