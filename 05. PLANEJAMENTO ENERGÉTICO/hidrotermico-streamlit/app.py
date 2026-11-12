"""Abas independentes de PDE Didática e PL Único."""
from pathlib import Path
import runpy

import streamlit as st

st.set_page_config(page_title="Simulador - Planejamento Energético", page_icon="💧", layout="wide")
st.markdown("""<style>
.block-container{padding:4.5rem 2.5rem 3rem;max-width:1550px}
h1{letter-spacing:-.04em!important;font-size:clamp(1.65rem,3vw,2.75rem)!important;line-height:1.18!important} h2,h3{letter-spacing:-.02em!important}
[data-testid="stMetric"]{background:#F0F6F7;padding:18px 20px;border-radius:12px;border:1px solid #DCE9EC}
[data-testid="stMetricLabel"]{color:#526B76}
[data-testid="stMetricValue"]{font-size:clamp(1.15rem,1.6vw,1.65rem)}
[data-testid="stMetricLabel"] p{font-size:13px;white-space:normal}
.eyebrow{color:#247B8B;letter-spacing:.16em;font-size:12px;font-weight:700}
.intro{color:#5D7280;font-size:17px;margin-bottom:1.6rem}
@media(max-width:1100px){
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]){flex-wrap:wrap!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"])>[data-testid="stColumn"]{flex:1 1 calc(50% - .5rem)!important;width:calc(50% - .5rem)!important;min-width:0!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stBidiComponentRegular"]){flex-wrap:wrap!important}
[data-testid="stHorizontalBlock"]:has([data-testid="stBidiComponentRegular"])>[data-testid="stColumn"]{flex:1 1 100%!important;width:100%!important;min-width:0!important}
}
@media(max-width:640px){
[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"])>[data-testid="stColumn"]{flex-basis:100%!important;width:100%!important}
}

</style>""", unsafe_allow_html=True)


# Interrompe a limpeza dos widgets escalares ao trocar de método.
# Editores guardam seus valores em DataFrames próprios; não se reatribui seu estado interno.
for key in list(st.session_state):
    escalar = key.startswith(('input_', 'pl_input_', 'view_')) or key in ('main_tabs', 'pl_result_tabs')
    editor = key in ('input_hyd', 'input_thermal') or key.startswith('input_load_editor_')
    if escalar and not editor:
        st.session_state[key] = st.session_state[key]

st.markdown('<div class="eyebrow">LABORATÓRIO DE PLANEJAMENTO ENERGÉTICO</div>', unsafe_allow_html=True)
st.title("Simulador - Planejamento Energético")
st.markdown('<div class="intro">Planejamento hidrotérmico · Batalha → Serra do Facão<br>Explore o efeito das entradas sobre a geração, o armazenamento e o custo de operação.</div>', unsafe_allow_html=True)

pde, plu, uct, arv = st.tabs(['PDE Didática', 'PL Único', 'DESSEM semanal', 'PL Único em árvore'], key='metodo', on_change='rerun', bind='query-params')
if pde.open:
    with pde:
        runpy.run_path(str(Path(__file__).with_name('pde_app.py')), run_name='__main__')
if plu.open:
    with plu:
        from pl_ui import mostrar_pl
        mostrar_pl()
if uct.open:
    with uct:
        from trabalhos_ui import semana
        semana()
if arv.open:
    with arv:
        from trabalhos_ui import arvore
        arvore()
