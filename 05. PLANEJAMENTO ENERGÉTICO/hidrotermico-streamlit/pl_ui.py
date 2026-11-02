"""Interface independente para o PL Único determinístico do notebook."""
import io
import json
import zipfile
from copy import deepcopy

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

import pl_charts as charts
from pl_model import pl_unico_det, sistema_colab, tabela_det, validar_sistema_det

CALENDARIO = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
              'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']


@st.cache_data(show_spinner=False, max_entries=12)
def calcular_pl(sistema):
    return pl_unico_det(sistema, cenario=0)


def reset_pl(keep_profile=False):
    perfil = st.session_state.get('pl_input_profile', 'Exemplo do Colab (3 meses)') if keep_profile else 'Exemplo do Colab (3 meses)'
    versao = st.session_state.get('pl_editor_version', 0) + 1
    for key in list(st.session_state):
        if key.startswith('pl_'):
            del st.session_state[key]
    anual = perfil.startswith('Anual')
    # Valores explícitos também atualizam os controles que já estão no navegador.
    st.session_state.update({
        'pl_input_profile': perfil, 'pl_input_n': 12 if anual else 3,
        'pl_input_inicio': 'Janeiro' if anual else 'Setembro',
        'pl_input_load_mode': 'Constante', 'pl_input_carga': 250.,
        'pl_input_constant_afl': anual, 'pl_input_afl_b': 220. if anual else 20.,
        'pl_input_afl_s': 350. if anual else 24., 'pl_input_vi_0': 39.7,
        'pl_input_vi_1': 50.2, 'pl_input_cdef': 4000., 'pl_input_auto': True,
        'pl_input_serra': 212.58, 'pl_editor_version': versao,
    })


def trocar_perfil():
    reset_pl(keep_profile=True)


def br(valor, casas=2):
    return f'{valor:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def gerar_meses(n, inicio):
    return [CALENDARIO[(inicio + t) % 12] if n <= 12 else
            f'{CALENDARIO[(inicio + t) % 12]} · ciclo {1 + (inicio + t) // 12}' for t in range(n)]


def mostrar_pl():
    base = sistema_colab()
    with st.sidebar:
        st.markdown('### PL Único · controles')
        perfil = st.selectbox('Cenário de partida', ['Exemplo do Colab (3 meses)', 'Anual (janeiro a dezembro)'],
                              key='pl_input_profile', on_change=trocar_perfil)
        anual = perfil.startswith('Anual')
        n = int(st.number_input('Número de meses', min_value=1, max_value=60,
                                value=12 if anual else 3, step=1, key='pl_input_n'))
        if n == 12:
            inicio = 0
            st.caption('Horizonte anual: janeiro a dezembro.')
        else:
            primeiro = st.selectbox('Mês inicial', CALENDARIO, index=0 if anual else 8, key='pl_input_inicio')
            inicio = CALENDARIO.index(primeiro)
        modo_carga = st.radio('Modo da carga', ['Constante', 'Por mês'], horizontal=True, key='pl_input_load_mode')
        carga = float(st.number_input('Carga constante (MW médios)', min_value=0., value=250., step=10.,
                                      key='pl_input_carga'))
        constantes = st.toggle('Afluências constantes', value=anual, key='pl_input_constant_afl')
        qb = float(st.number_input('Batalha · AFL (m³/s)', min_value=0., value=220. if anual else 20.,
                                   step=1., key='pl_input_afl_b'))
        qs = float(st.number_input('Serra · AFL local (m³/s)', min_value=0., value=350. if anual else 24.,
                                   step=1., key='pl_input_afl_s'))
        if not constantes:
            st.caption('Edite as afluências de cada mês na tabela principal.')
        with st.expander('Armazenamento inicial'):
            inicial = [float(st.number_input(f"{u['Nome']} (% útil)", min_value=0., max_value=100.,
                                             value=v, step=1., key=f'pl_input_vi_{i}'))
                       for i, (u, v) in enumerate(zip(base['UHE'], (39.7, 50.2)))]
        cdef = float(st.number_input('Custo do déficit (R$/MWh)', min_value=0., value=4000., step=100., key='pl_input_cdef'))
        auto = st.toggle('Recalcular automaticamente', value=True, key='pl_input_auto')
        calcular = st.button('Resolver PL Único', type='primary', width='stretch', key='pl_resolve')
        st.button('Restaurar PL Único', on_click=reset_pl, width='stretch', key='pl_reset')
        st.caption('Um único PL para todos os meses. A trajetória de afluências é conhecida; não há discretização dos volumes.')

    meses = gerar_meses(n, inicio)
    versao = st.session_state.get('pl_editor_version', 0)
    sufixo = f'_v{versao}' if versao else ''
    st.subheader('PL Único · planejamento determinístico')
    st.caption('Mesma formulação do Colab, resolvida com SCIP. O exemplo de três meses reproduz suas entradas; o perfil anual usa afluências demonstrativas editáveis.')
    linhas = deepcopy(st.session_state.get('pl_saved_monthly', []))
    if not linhas:
        linhas = [[220., 350., 250.]] * 12 if anual else [
            [20., 24., 250.], [25., 29., 250.], [30., 20., 250.]]
    while len(linhas) < n:
        linhas.append(linhas[-1].copy())
    dados = pd.DataFrame(linhas[:n], columns=['Batalha · AFL (m³/s)', 'Serra · AFL local (m³/s)', 'Carga (MW médios)'])
    if constantes:
        dados.iloc[:, 0], dados.iloc[:, 1] = qb, qs
    if modo_carga == 'Constante':
        dados.iloc[:, 2] = carga
    dados.insert(0, 'Mês', meses)
    chave = f'pl_editor_monthly_{n}_{inicio}_{modo_carga}_{constantes}{sufixo}'
    if chave not in st.session_state:
        st.session_state['pl_monthly_seed'] = dados.copy()
    else:
        # Campos desabilitados acompanham os controles laterais, mesmo com o editor já aberto.
        seed = st.session_state['pl_monthly_seed'].copy()
        if constantes:
            seed.iloc[:, 1], seed.iloc[:, 2] = qb, qs
        if modo_carga == 'Constante':
            seed.iloc[:, 3] = carga
        st.session_state['pl_monthly_seed'] = seed
    disabled = ['Mês']
    if constantes:
        disabled += list(dados.columns[1:3])
    if modo_carga == 'Constante':
        disabled += ['Carga (MW médios)']
    st.markdown('#### Entradas mensais')
    frame = st.data_editor(st.session_state['pl_monthly_seed'], hide_index=True, width='stretch',
                           disabled=disabled, key=chave,
                           column_config={c: st.column_config.NumberColumn(min_value=0., required=True, format='%.2f')
                                          for c in dados.columns if c != 'Mês'})
    for t in range(n):
        if not constantes:
            linhas[t][0:2] = frame.iloc[t, 1:3].tolist()
        if modo_carga == 'Por mês':
            linhas[t][2] = frame.iloc[t, 3]
    st.session_state['pl_saved_monthly'] = linhas
    # A entrada efetiva usa os controles constantes ou os valores mensais, conforme o modo.
    efetivos = frame.iloc[:, 1:].to_numpy(dtype=float, copy=True)
    if constantes:
        efetivos[:, 0], efetivos[:, 1] = qb, qs
    if modo_carga == 'Constante':
        efetivos[:, 2] = carga

    with st.expander('Parâmetros das usinas'):
        hyd = pd.DataFrame({
            'Usina': [u['Nome'] for u in base['UHE']],
            'Volume mínimo (hm³)': [u['Vmin'] for u in base['UHE']],
            'Volume máximo (hm³)': [u['Vmax'] for u in base['UHE']],
            'Engolimento (m³/s)': [u['Engol']/2.592 for u in base['UHE']],
            'Produtibilidade (MW/(m³/s))': [u['Prod']*2.592 for u in base['UHE']],
        })
        hyd = st.data_editor(st.session_state.get('pl_saved_hyd', hyd), disabled=['Usina'],
                             hide_index=True, width='stretch', key=f'pl_editor_hyd{sufixo}',
                             column_config={c: st.column_config.NumberColumn(min_value=0., required=True, format='%.6f') for c in hyd.columns if c != 'Usina'})
        st.session_state['pl_saved_hyd'] = hyd.copy()
        potencia_serra = float(st.number_input('Potência nominal de Serra (MW)', min_value=0., value=212.58, step=1., key='pl_input_serra'))
        term = pd.DataFrame({'Usina': [u['Nome'] for u in base['UTE']],
                             'Potência máxima (MW)': [u['Capac'] for u in base['UTE']],
                             'Custo (R$/MWh)': [u['Custo']/720 for u in base['UTE']]})
        term = st.data_editor(st.session_state.get('pl_saved_thermal', term), disabled=['Usina'],
                              hide_index=True, width='stretch', key=f'pl_editor_thermal{sufixo}',
                              column_config={c: st.column_config.NumberColumn(min_value=0., required=True, format='%.2f') for c in term.columns if c != 'Usina'})
        st.session_state['pl_saved_thermal'] = term.copy()
    try:
        sistema = deepcopy(base)
        sistema['DGer'].update(Meses=meses, Carga=efetivos[:, 2].tolist(), CDef=cdef*720)
        for i, u in enumerate(sistema['UHE']):
            u.update(Vmin=float(hyd.iloc[i, 1]), Vmax=float(hyd.iloc[i, 2]),
                     Engol=float(hyd.iloc[i, 3])*2.592, Prod=float(hyd.iloc[i, 4])/2.592,
                     Afl=[[float(v)*2.592] for v in efetivos[:, i]])
            u['VI'] = u['Vmin'] + inicial[i]/100*(u['Vmax'] - u['Vmin'])
        sistema['UHE'][1]['Potencia'] = potencia_serra
        for i, u in enumerate(sistema['UTE']):
            u.update(Capac=float(term.iloc[i, 1]), Custo=float(term.iloc[i, 2])*720)
        validar_sistema_det(sistema, 0)
        assinatura = json.dumps(sistema, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError) as exc:
        st.error(f'Revise as entradas do PL Único: {exc}')
        return
    mudou = st.session_state.get('pl_parameters') != assinatura
    if calcular or (auto and mudou):
        try:
            st.session_state['pl_solution'] = calcular_pl(sistema)
            st.session_state['pl_parameters'] = assinatura
        except (ValueError, RuntimeError) as exc:
            st.error(f'Não foi possível resolver o PL Único: {exc}')
            return
    if st.session_state.get('pl_parameters') != assinatura:
        st.info('Entradas alteradas. Clique em Resolver PL Único para atualizar os resultados e os gráficos.')
        return
    r = st.session_state['pl_solution']
    traj = r['trajetoria']
    deficit = sum(max(0., x['def']) for x in traj)*720
    a, b, c, d = st.columns(4)
    a.metric('Custo total · PL Único', f"R$ {br(r['custo_total']/1e6)} mi")
    b.metric('Déficit', f'{br(deficit)} MWh')
    c.metric('Geração térmica', f"{br(sum(sum(x['gt']) for x in traj)*720)} MWh")
    d.metric('Horizonte', f'{n} meses')
    st.caption(f"Solução ótima do PL contínuo · tempo de resolução: {br(r['segundos'], 3)} s (reutilizado enquanto as entradas não mudam) · afluências conhecidas para todo o horizonte.")
    if deficit > 1e-4:
        st.warning('Há déficit nesta trajetória. Consulte os valores mensais nos resultados.')
    operacao, tabelas, modelo = st.tabs(['Operação do PL Único', 'Resultados e exportação', 'Modelo do PL Único'], key='pl_result_tabs', on_change='rerun')
    with operacao:
        st.subheader('Atendimento à carga')
        st_echarts(charts.pl_generation(sistema, r), height='390px', key='pl_gen')
        st.subheader('Armazenamento')
        st_echarts(charts.pl_storage(sistema, r), height='350px', key='pl_storage')
        st.subheader('Custo imediato por mês')
        st_echarts(charts.pl_costs(sistema, r), height='330px', key='pl_costs')
    with tabelas:
        tabela = tabela_det(sistema, r)
        st.dataframe(tabela.style.format(precision=3, decimal=',', thousands='.', subset=tabela.select_dtypes('number').columns),
                     hide_index=True, width='stretch')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('parametros_pl_unico.json', json.dumps(sistema, ensure_ascii=False, indent=2, allow_nan=False))
            z.writestr('resultados_pl_unico.csv', tabela.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig'))
            z.writestr('LEIA-ME.txt', 'PL Único determinístico. Custo total = soma dos custos imediatos.\nVazões locais conhecidas; 720 h por estágio; custo terminal zero.\n')
        st.download_button('Baixar resultados do PL Único (.zip)', buf.getvalue(), file_name='resultados_pl_unico.zip', mime='application/zip', key='pl_download')
    with modelo:
        st.markdown('''
- **Decisão conjunta:** todos os volumes, turbinamentos, vertimentos, gerações térmicas e déficits são escolhidos em um único PL.
- **Acoplamento:** o volume final de cada mês é o inicial do próximo; a descarga de Batalha chega a Serra no mesmo estágio.
- **Informação:** a trajetória inteira de afluências e cargas é conhecida. O custo é determinístico, diferente do custo esperado da PDE.
- **Hipóteses mantidas:** 720 horas por mês, produtibilidade constante, limites das usinas, penalidade de vertimento e custo terminal zero.
- **Solver:** SCIP via PySCIPOpt, com a mesma função `pl_unico_det` do Colab.
''')
        st.latex(r'\min\;\sum_t CustoImediato_t')
        st.latex(r'V^i_{t+1}=V^f_t')
