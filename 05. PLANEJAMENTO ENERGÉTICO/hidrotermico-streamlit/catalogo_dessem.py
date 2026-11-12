"""Leitores PySDDP 0.0.90 e seleção de unidades representáveis pelo modelo semanal."""
from pathlib import Path
from PySDDP.dessem.script.cadterm import CadTerm
from PySDDP.dessem.script.operut import Operut
from PySDDP.dessem.script.rampas import Rampas

DADOS = Path(__file__).with_name("dados_dessem")


def perfil(curvas, sentido):
    valores = []
    for linha in curvas.loc[curvas["T"].str.strip() == sentido].itertuples(index=False):
        fim = 2 * int(linha.Tempo) + int(linha.FlagMeiaHora)
        if fim <= len(valores):
            raise ValueError("Duração incompatível")
        valores.extend([float(linha.Potencia)] * (fim - len(valores)))
    if not valores or len(valores) % 2:
        raise ValueError("Trajetória incompleta para compromisso horário")
    return tuple(valores)


def carregar_catalogo():
    cad, op, ramp = CadTerm(), Operut(), Rampas()
    for leitor, arquivo in [(cad, "termdat.dat"), (op, "operut.dat"), (ramp, "rampas.dat")]:
        leitor.ler(str(DADOS / arquivo))
    nomes = {int(r.num_usi): r.nome.strip() for r in cad.cadusit_df.itertuples()}
    combinadas = set(cad.cadconf_df.num_usi.astype(int))

    def grupos(df, us, ug):
        return dict(tuple(df.groupby([df[us].str.strip(), df[ug].str.strip()])))

    iniciais = grupos(op.condicoes_iniciais_df, "us", "ug")
    limites = grupos(op.limites_condicoes_df, "us", "un")
    curvas = grupos(ramp.rampas_df, "us", "uni")
    catalogo = {}
    for r in cad.cadunidt_df.itertuples():
        chave = r.num_usi.strip(), r.ind_ger.strip()
        codigo, ug = map(int, chave)
        if codigo in combinadas or not all(chave in g for g in (iniciais, limites, curvas)):
            continue
        ini, oper, curva = iniciais[chave], limites[chave], curvas[chave]
        if len(ini) != 1 or len(oper) != 1 or set(curva["C"].str.strip()) != {"S"}:
            continue
        i, o = ini.iloc[0], oper.iloc[0]
        if i["A/D"].strip() != "0" or o.Gmax.strip() or o.Gmin.strip():
            continue
        try:
            d = dict(codigo=codigo, ug=ug, Pmin=float(r.ger_min), Pmax=float(r.pot),
                     Ton=int(r.temp_on), Toff=int(r.temp_off), subida=float(r.ramp_tom),
                     descida=float(r.ramp_alivio), cvu=float(o.Custo),
                     partida=float(r.custo_frio.strip() or 0), u0=int(i.st), p0=float(i.GerInic),
                     idade=float(i.tempo) + .5 * int(i.MH.strip() or 0),
                     A=perfil(curva, "A"), D=perfil(curva, "D"))
        except ValueError:
            continue
        if min(d["Ton"], d["Toff"], d["subida"], d["descida"]) <= 0:
            continue
        if not (0 <= d["Pmin"] <= d["Pmax"] and min(d["A"] + d["D"]) >= 0
                and max(d["A"] + d["D"]) <= d["Pmax"] and d["u0"] in (0, 1)):
            continue
        catalogo[f"{nomes[codigo]} · UG {ug}"] = d
    return catalogo
