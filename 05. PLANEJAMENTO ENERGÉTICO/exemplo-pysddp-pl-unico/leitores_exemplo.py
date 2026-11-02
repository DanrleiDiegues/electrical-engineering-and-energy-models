"""Leitura real de HIDR.DAT e VAZOES.DAT; adaptação didática para um PL Único."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd
from PySDDP.newave.script.hidr import Hidr
from PySDDP.newave.script.vazoes import Vazoes

COMMIT_DADOS = 'dd8931084696f5652211f1fe342c18d132a61dcf'
URL_DADOS = f'https://raw.githubusercontent.com/AndreMarcato/PySDDP/{COMMIT_DADOS}/PySDDP/pmo'
HASHES_DADOS = {
    'HIDR.DAT': '13d932a62a6a6d10fbe77d9d1714f1eca66f27d5a0020afaeaa884cdeaab9d76',
    'VAZOES.DAT': '090a182a7fb2df2c827a00d2a61b2653673a61187dc5b935c1982916737ca910',
}


def obter_arquivos_exemplo(pasta='dados_pysddp'):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, esperado in HASHES_DADOS.items():
        arquivo = pasta / nome
        if not arquivo.exists():
            with urlopen(f'{URL_DADOS}/{nome}', timeout=60) as resposta:
                conteudo = resposta.read()
            if hashlib.sha256(conteudo).hexdigest() != esperado:
                raise ValueError(f'Hash inesperado no download de {nome}.')
            arquivo.write_bytes(conteudo)
        elif hashlib.sha256(arquivo.read_bytes()).hexdigest() != esperado:
            raise ValueError(f'{nome} difere da amostra fixada; não será sobrescrito. Use outra pasta para o exemplo.')
    return pasta


def sistema_dos_leitores(pasta, ano=2017, mes_inicial=9, n_meses=3,
                         cargas=None, inicial=(39.7, 50.2), nr_postos=320, ano_base=1931):
    # Estes dois leitores não resolvem o despacho: apenas interpretam os arquivos.
    if type(n_meses) is not int or n_meses < 1 or type(mes_inicial) is not int or not 1 <= mes_inicial <= 12:
        raise ValueError('Informe horizonte positivo e mês inicial de 1 a 12.')
    if type(nr_postos) is not int or nr_postos < 1:
        raise ValueError('Informe o número de postos do arquivo.')
    if len(inicial) != 2 or not np.all(np.isfinite(inicial)) or min(inicial) < 0 or max(inicial) > 100:
        raise ValueError('Informe dois armazenamentos iniciais entre 0 e 100%.')
    pasta = Path(pasta)
    if (pasta / 'VAZOES.DAT').stat().st_size % (4*12*nr_postos):
        raise ValueError('Tamanho de VAZOES.DAT incompatível com o número de postos.')
    cadastro = Hidr()
    cadastro.ler(str(pasta / 'HIDR.DAT'))
    historico = Vazoes()
    historico.ler(str(pasta / 'VAZOES.DAT'), nr_postos)
    codigos = [20, 21]
    registros = [cadastro.get(c) for c in codigos]
    if any(r is None for r in registros):
        raise ValueError('Batalha (20) e Serra do Facão (21) não estão no cadastro informado.')
    esperados = ['BATALHA', 'SERRA FACAO']
    if [r['nome'].strip() for r in registros] != esperados:
        raise ValueError('Os códigos não correspondem às duas usinas esperadas neste exemplo.')
    if any(not 1 <= r['posto'] <= nr_postos for r in registros):
        raise ValueError('Posto hidrológico fora das colunas de VAZOES.DAT.')
    datas = [(ano + (mes_inicial-1+t)//12, (mes_inicial-1+t)%12+1) for t in range(n_meses)]
    if any(not 0 <= a-ano_base < historico.vaz_nat.shape[0] for a, _ in datas):
        raise ValueError('Período solicitado fora do histórico disponível.')
    naturais = np.array([[historico.vaz_nat[a-ano_base, m-1, r['posto']-1]
                           for r in registros] for a, m in datas], dtype=float)
    locais = naturais.copy()
    # O arquivo contém vazões NATURAIS. Subtrai a contribuição de Batalha em Serra.
    # O balanço do PL voltará a somar a descarga operada de Batalha no mesmo mês.
    for i, codigo in enumerate(codigos):
        for j, registro in enumerate(registros):
            if registro['jusante'] == codigo:
                locais[:, i] -= naturais[:, j]
    if not np.all(np.isfinite(locais)) or np.any(locais < 0):
        raise ValueError('As vazões incrementais ficaram negativas; revise os dados e o período, sem truncá-las a zero.')
    calendario = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    meses = [f'{calendario[m-1]}/{a}' for a, m in datas]
    horas, fator = 720, 2.592
    uhes, cadastro_resumo = [], []
    for i, r in enumerate(registros):
        conjuntos = int(r['num_conj_maq'])
        maquinas = np.array(r['maq_por_conj'][:conjuntos], dtype=float)
        q_conj = maquinas * np.array(r['vaz_efet_conj'][:conjuntos], dtype=float)
        q_nominal = float(q_conj.sum())
        potencia = float(maquinas @ np.array(r['pef_por_conj'][:conjuntos], dtype=float))
        if q_nominal <= 0:
            raise ValueError('Cadastro sem vazão nominal positiva para a aproximação didática.')
        queda = float(q_conj @ np.array(r['alt_efet_conj'][:conjuntos], dtype=float) / q_nominal)
        if r['tipo_perda'] == 2:
            queda_liquida = queda - r['perda_hid']
        elif r['tipo_perda'] == 1:
            queda_liquida = queda * (1-r['perda_hid']/100)
        else:
            raise ValueError('Tipo de perda hidráulica não suportado no exemplo.')
        rho = float(r['prod_esp'] * queda_liquida)
        if rho < 0 or not np.isfinite(rho):
            raise ValueError('Produtibilidade inválida após aplicar a hipótese de queda constante.')
        nome = 'Batalha' if i == 0 else 'Serra do Facão'
        jusante = codigos.index(r['jusante']) if r['jusante'] in codigos else None
        uhes.append({'Nome': nome, 'Vmin': float(r['vol_min']), 'Vmax': float(r['vol_max']),
                     'VI': float(r['vol_min'] + inicial[i]/100*(r['vol_max']-r['vol_min'])),
                     'Prod': rho/fator, 'Engol': q_nominal*fator, 'Potencia': potencia,
                     'Jusante': jusante, 'Afl': [[float(q)*fator] for q in locais[:, i]]})
        cadastro_resumo.append({'Usina': nome, 'Código HIDR': r['codigo'], 'Posto': r['posto'],
                                'Volume mínimo (hm³)': r['vol_min'], 'Volume máximo (hm³)': r['vol_max'],
                                'Potência nominal (MW)': potencia, 'Vazão nominal adotada (m³/s)': q_nominal,
                                'Produtibilidade constante (MW/(m³/s))': rho})
    demanda = [250.]*n_meses if cargas is None else list(cargas)
    sistema = {'DGer': {'Meses': meses, 'Carga': demanda, 'Horas': horas,
                         'CDef': 4000.*horas, 'Nr_Disc': 5}, 'UHE': uhes,
               'UTE': [{'Nome': 'BBF Baliza', 'Capac': 10., 'Custo': 882.76*horas},
                       {'Nome': 'ERB Candeias', 'Capac': 17., 'Custo': 118.93*horas}]}
    vazoes = pd.DataFrame({'Mês': meses, 'Batalha natural (m³/s)': naturais[:, 0],
                           'Serra natural (m³/s)': naturais[:, 1], 'Batalha local (m³/s)': locais[:, 0],
                           'Serra incremental (m³/s)': locais[:, 1]})
    return sistema, pd.DataFrame(cadastro_resumo), vazoes
