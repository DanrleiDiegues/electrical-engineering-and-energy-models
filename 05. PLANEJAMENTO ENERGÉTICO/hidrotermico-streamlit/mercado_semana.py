"""Análises do DESSEM semanal que só usam pandas (sem Streamlit): resumo diário, ordem de mérito e sua explicação."""
import pandas as pd
from modelo_semana import CDEF, HIDRO


def resumo_diario(meia):
    dia = (meia.hora // 24).astype(int) + 1
    g = meia.groupby(dia)
    return pd.DataFrame({"Carga média (MW)": g["carga"].mean().round(1),
                         "CMO mín. (R$/MWh)": g["cmo"].min().round(2),
                         "CMO médio (R$/MWh)": g["cmo"].mean().round(2),
                         "CMO máx. (R$/MWh)": g["cmo"].max().round(2),
                         "CMA médio (R$/hm³)": g["cma"].mean().round(0)}).rename_axis("Dia").reset_index()


def ordem_merito(r, usinas):
    meia, estados = r["meia"], r["estados"]
    linhas = [{"Fonte": nome, "Tipo": "Térmica", "Custo (R$/MWh)": d["cvu"], "Capacidade (MW)": d["Pmax"],
               "Energia na semana (MWh)": meia[nome].sum() * 0.5,
               "Horas ligada": int(estados.loc[estados.unidade == nome, "ligada"].sum())}
              for nome, d in usinas.items()]
    linhas.append({"Fonte": "Água de Batalha (CMA)", "Tipo": "Hidrelétrica", "Custo (R$/MWh)": float(meia.cma_mwh.mean()),
                   "Capacidade (MW)": HIDRO["rho"] * HIDRO["Qmax"], "Energia na semana (MWh)": meia.UHE.sum() * 0.5,
                   "Horas ligada": None})
    linhas.append({"Fonte": "Déficit", "Tipo": "Penalidade", "Custo (R$/MWh)": CDEF, "Capacidade (MW)": None,
                   "Energia na semana (MWh)": meia["déficit"].sum() * 0.5, "Horas ligada": None})
    return pd.DataFrame(linhas).sort_values("Custo (R$/MWh)").reset_index(drop=True)


def explicacao_merito(tabela, custo_futuro):
    agua = tabela[tabela.Tipo == "Hidrelétrica"].iloc[0]["Custo (R$/MWh)"]
    termicas = tabela[tabela.Tipo == "Térmica"]
    if not custo_futuro or agua <= 1e-6:
        return ("Com o custo futuro desligado a água não tem valor de oportunidade: o CMA é zero e o modelo a usa antes de "
                "qualquer térmica, até o limite de turbinamento. As térmicas só complementam a carga e só ficam ligadas "
                "quando compensam os custos de partida e os tempos mínimos.")
    baratas = termicas[termicas["Custo (R$/MWh)"] < agua]
    caras = termicas[termicas["Custo (R$/MWh)"] >= agua]
    texto = [f"Gastar a água de Batalha agora custa, em oportunidade, **R$ {agua:,.2f}/MWh** (o CMA médio): é o valor que o "
             "corte do custo futuro atribui ao volume que deixa de ficar guardado."]
    if len(baratas):
        nomes = ", ".join(f"{n} (R$ {c:,.2f}/MWh)" for n, c in zip(baratas.Fonte, baratas["Custo (R$/MWh)"]))
        texto.append(f"{nomes} custa menos que a água. Por isso o modelo mantém essa térmica no máximo sempre que ela está "
                     "ligada e usa a hidráulica só para completar a carga, poupando água.")
    if len(caras):
        nomes = ", ".join(f"{n} (R$ {c:,.2f}/MWh)" for n, c in zip(caras.Fonte, caras["Custo (R$/MWh)"]))
        texto.append(f"{nomes} custa mais que a água. Só entra quando a hidráulica e as térmicas mais baratas não bastam, "
                     "como nos picos de carga.")
    texto.append("Desligar o custo futuro, na lateral, mostra a outra face: sem valor para a água, a hidráulica passa a "
                 "substituir as térmicas.")
    return " ".join(texto)
