"""Tela do passo a passo da PDDD: avança e volta pelos estágios do forward e do backward, como nos slides da aula."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from pddd_passos import EXEMPLO, gerar_passos

ORDINAIS = ["Primeira", "Segunda", "Terceira", "Quarta", "Quinta", "Sexta", "Sétima", "Oitava", "Nona", "Décima"]
AZUL, VERMELHO, CINZA = "#1f3fbf", "#d62728", "#9aa5ad"


@st.cache_data(show_spinner="Executando a PDDD do exemplo…")
def passos(cenario):
    return gerar_passos(EXEMPLO, cenario)


def _cabecalho(p, T):
    """Caixas Est 1 → Est 2 → Est 3 com o VI de cada estágio; a seta muda de sentido no backward."""
    seta = "⟸" if p["fase"] == "backward" else "⟹"
    caixas = []
    for t in range(T):
        r = p["tabela"][t]
        vi = f"VI={r['vi']:.2f} hm³" if r else "VI = ?"
        ativo = t == p["estagio"]
        estilo = ("border:2px solid #d62728;background:#fff4f4" if ativo else "border:1.5px solid #222;background:#fff")
        caixas.append(f'<span style="{estilo};padding:6px 12px;font-size:15px;white-space:nowrap">Est {t + 1} - '
                      f'<span style="color:{AZUL};font-style:italic;font-size:12px">{vi}</span></span>')
    corpo = f' <span style="font-size:24px;color:#555">{seta}</span> '.join(caixas)
    st.markdown(f'<div style="display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;margin:8px 0 14px">{corpo}</div>',
                unsafe_allow_html=True)


def _cartao(p, t):
    """Tabela de um estágio com os mesmos campos do slide."""
    r = p["tabela"][t]
    afl = EXEMPLO["afl"][st.session_state["pddd_passo_cen"]][t]
    if r is None:
        return (f'<div style="border:1px solid #333;padding:8px;text-align:center;color:{CINZA}">'
                f'<b style="color:#222">Estágio {t + 1}</b><br><i style="color:{AZUL}">AFL = {afl:g} hm³</i><br><br>'
                f'aguardando o forward chegar a este estágio</div>')
    antigo = p["fase"] == "backward" and t < p["estagio"]
    cor = CINZA if antigo else AZUL
    destaque = "box-shadow:0 0 0 2px #d62728 inset;" if t == p["estagio"] else ""
    nota = f'<div style="color:{CINZA};font-size:11px">valores do forward (ainda não resolvido no backward)</div>' if antigo else ""
    f = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"""<div style="border:1px solid #333;padding:8px 10px;{destaque}font-family:'CMU Serif','Latin Modern Roman',serif">
<div style="text-align:center"><b>Estágio {t + 1}</b><br><i style="color:{AZUL}">AFL = {afl:g} hm³</i></div>{nota}
<div style="display:grid;grid-template-columns:1fr auto;color:{cor};font-size:14px;margin:6px 0">
<span>VI = {f(r['vi'])} hm³</span><span>v<sub>t</sub> = {f(r['vt'])}</span>
<span>vf = {f(r['vf'])} hm³</span><span>v<sub>v</sub> = {f(r['vv'])}</span>
<span></span><span>g<sub>t</sub> = {f(r['gt'])}</span></div>
<div style="text-align:center;color:{cor};font-size:14px">def = {f(r['deficit'])}<br>fut = ${f(r['fut'])}<br>
<span style="color:{VERMELHO if not antigo else CINZA}">imediato = ${f(r['imediato'])}</span><br>tot = ${f(r['tot'])}</div></div>"""


def _grafico(p, t, ymax):
    """Cortes do estágio t (planos de Q_t em função do volume que ele recebe) e a região viável de α."""
    u = EXEMPLO["uhe"]
    x = np.linspace(u["vmin"], u["vmax"], 161)
    cortes = p["graficos"][t]
    fig = go.Figure()
    envelope = np.zeros_like(x)
    for k, c in enumerate(cortes):
        envelope = np.maximum(envelope, c["a"] * x + c["b"])

    # Região viável de α: tudo o que fica ACIMA do maior corte (e de zero). Cada novo corte recorta a região.
    fig.add_scatter(x=np.r_[x, x[::-1]], y=np.r_[envelope, np.full_like(x, ymax)], fill="toself",
                    fillcolor="rgba(230,120,110,.35)", line=dict(width=0), name="região viável de α", hoverinfo="skip")
    for k, c in enumerate(cortes):
        novo = p["novo"] == t and k == len(cortes) - 1
        fig.add_scatter(x=x, y=c["a"] * x + c["b"], mode="lines", name=f"corte it. {c['iteracao']}",
                        line=dict(color=VERMELHO if novo else "#7a5a5a", width=3 if novo else 1.4,
                                  dash="solid" if novo else "dot"))
        fig.add_scatter(x=[c["x"]], y=[c["y"]], mode="markers+text", text=[f"({c['x']:.2f}; {c['y']:,.2f})"],
                        textposition="top right", marker=dict(color=AZUL, size=8), showlegend=False)
    fig.add_scatter(x=x, y=envelope, mode="lines", line=dict(color="#b03020", width=2.5), name="FCF aproximada")
    rotulo = "Volume inicial do estágio 1 (hm³)" if t == 0 else f"Vol. final do estágio {t} = VI do estágio {t + 1} (hm³)"
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=36, b=10), template="plotly_white", showlegend=False,
                      title=dict(text=("Q₁(VI): custo do estágio 1" if t == 0 else f"α do estágio {t} (cortes vindos do {t + 1})"),
                                 font=dict(size=13)),
                      xaxis=dict(title=rotulo, range=[u["vmin"], u["vmax"]]), yaxis=dict(title="α ($)", range=[0, ymax]))
    return fig


def passo_a_passo():
    st.subheader("PDDD passo a passo — exemplo da aula")
    st.caption("Uma UHE (20 a 100 hm³, VI = 65 hm³, ρ = 0,95, engolimento 60 hm³), GT 1 (15 MWmed, \\$10) e GT 2 (10 MWmed, \\$25), "
               "déficit \\$500, carga de 50 MWmed em 3 estágios. Cada clique resolve um estágio do forward ou do backward.")
    cenario = st.radio("Afluências", list(EXEMPLO["afl"]), horizontal=True, key="pddd_passo_cen")
    lista = passos(cenario)
    n = len(lista)
    chave = f"pddd_passo_{cenario}"
    st.session_state.setdefault(chave, 0)

    def mover(delta=None, para=None):
        st.session_state[chave] = para if para is not None else min(max(st.session_state[chave] + delta, 0), n - 1)

    b = st.columns([1, 1, 1, 1, 3])
    b[0].button("⏮ Início", on_click=mover, kwargs=dict(para=0), width="stretch", key="pp_ini")
    b[1].button("◀ Voltar", on_click=mover, kwargs=dict(delta=-1), width="stretch", key="pp_vol",
                disabled=st.session_state[chave] == 0)
    b[2].button("Avançar ▶", on_click=mover, kwargs=dict(delta=1), width="stretch", key="pp_ava", type="primary",
                disabled=st.session_state[chave] == n - 1)
    b[3].button("Fim ⏭", on_click=mover, kwargs=dict(para=n - 1), width="stretch", key="pp_fim")
    b[4].markdown(f"**Passo {st.session_state[chave] + 1} de {n}**")

    p = lista[st.session_state[chave]]
    T = len(p["tabela"])
    fase = {"forward": "Forward", "backward": "Backward", "convergiu": "Forward (convergência)"}[p["fase"]]
    st.markdown(f'<div style="background:#2b3aa8;color:#fff;padding:8px 14px;font-size:22px;border-radius:4px">'
                f'PDDD - Exemplo - {fase} - {ORDINAIS[p["iteracao"] - 1]} Iteração</div>', unsafe_allow_html=True)
    _cabecalho(p, T)

    # Escala comum dos gráficos: o maior custo visto em todo o exemplo.
    ymax = 1.1 * max(c["y"] for q in lista for g in q["graficos"] for c in g) if any(lista[-1]["graficos"]) else 100.
    colunas = st.columns(T)
    for t, col in enumerate(colunas):
        col.markdown(_cartao(p, t), unsafe_allow_html=True)
        col.plotly_chart(_grafico(p, t, ymax), width="stretch", key=f"pp_g{t}")

    # "$" sozinho abriria uma fórmula no Markdown do Streamlit: escapa-se o cifrão de moeda.
    (st.success if p["fase"] == "convergiu" else st.info)(p["texto"].replace("$", "\\$"))
    if p["historico"]:
        h = p["historico"]
        fig = go.Figure()
        fig.add_scatter(x=[x["iteracao"] for x in h], y=[x["zsup"] for x in h], mode="lines+markers", name="Zsup", line_color=VERMELHO)
        fig.add_scatter(x=[x["iteracao"] for x in h], y=[x["zinf"] for x in h], mode="lines+markers", name="Zinf", line_color=AZUL)
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10), template="plotly_white",
                          title="Evolução de Zinf e Zsup até este passo", xaxis=dict(title="Iteração", dtick=1), yaxis_title="$")
        st.plotly_chart(fig, width="stretch", key="pp_hist")
    st.caption("Leitura: no forward, cada estágio recebe o vf do anterior como VI e usa os cortes que já existem. No backward, "
               "cada estágio é resolvido de novo no volume visitado; o dual do balanço hídrico dá a inclinação π e o custo dá o ponto "
               "(v̄; Q). O corte α ≥ π·v + (Q − π·v̄) passa a valer para o estágio anterior e recorta a região viável de α (área sombreada). "
               "O PL tem soluções ótimas alternativas: a divisão entre custo imediato e futuro pode diferir do slide, mas o custo total "
               "(tot) e os cortes são os mesmos.")
