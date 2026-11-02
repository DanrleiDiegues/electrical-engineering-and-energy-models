import struct
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import linprog

PASTA = Path(__file__).parent
sys.path.insert(0, str(PASTA))
from leitores_exemplo import obter_arquivos_exemplo, sistema_dos_leitores
from modelo_pl_unico import pl_unico_det


def test_leitura_cadastro_e_vazoes_contra_binario():
    pasta = obter_arquivos_exemplo(PASTA / 'dados_pysddp')
    s, cadastro, vazoes = sistema_dos_leitores(pasta)
    bruto = (pasta / 'HIDR.DAT').read_bytes()
    for i, codigo in enumerate((20, 21)):
        vmin, vmax = struct.unpack_from('<ff', bruto, (codigo-1)*792 + 40)
        assert s['UHE'][i]['Vmin'] == vmin and s['UHE'][i]['Vmax'] == vmax
    vazao_bruta = np.fromfile(pasta / 'VAZOES.DAT', dtype='<i4').reshape(88, 12, 320)
    np.testing.assert_array_equal(vazoes.iloc[:, 1], vazao_bruta[2017-1931, 8:11, 21])
    np.testing.assert_array_equal(vazoes.iloc[:, 2], vazao_bruta[2017-1931, 8:11, 250])
    np.testing.assert_array_equal(vazoes.iloc[:, 4], [7., 6., 25.])
    assert s['UHE'][0]['Jusante'] == 1 and s['UHE'][1]['Jusante'] is None


def test_resultado_leitores_contra_highs_e_balanços():
    s, _, _ = sistema_dos_leitores(PASTA / 'dados_pysddp')
    r = pl_unico_det(s, 0)
    # Formulação matricial independente, resolvida com HiGHS, para conferir o ótimo.
    n = len(s['DGer']['Meses'])
    custo = np.zeros(n*9)
    eq, rhs, bounds = [], [], []
    for t in range(n):
        h = s['UHE']
        offset = t*9
        custo[offset+4:offset+9] = [.01, .01, s['UTE'][0]['Custo'], s['UTE'][1]['Custo'], s['DGer']['CDef']]
        bounds += [(u['Vmin'], u['Vmax']) for u in h]
        bounds += [(0., min(u['Engol'], u['Potencia']/u['Prod'])) for u in h]
        bounds += [(0., None), (0., None)] + [(0., u['Capac']) for u in s['UTE']] + [(0., None)]
        for i in range(2):
            linha = np.zeros(n*9)
            linha[offset+i] = 1.
            linha[offset+2+i] = 1.
            linha[offset+4+i] = 1.
            if i == 1:
                linha[offset+2] = -1.
                linha[offset+4] = -1.
            if t:
                linha[(t-1)*9+i] = -1.
            eq.append(linha)
            rhs.append(h[i]['Afl'][t][0] + (h[i]['VI'] if t == 0 else 0.))
        linha = np.zeros(n*9)
        linha[offset+2:offset+4] = [u['Prod'] for u in h]
        linha[offset+6:offset+9] = 1.
        eq.append(linha)
        rhs.append(s['DGer']['Carga'][t])
    outro = linprog(custo/1e6, A_eq=eq, b_eq=rhs, bounds=bounds, method='highs',
                    options={'dual_feasibility_tolerance': 1e-10})
    assert outro.success
    assert r['custo_total'] == pytest.approx(outro.fun*1e6, abs=.05)
    assert r['custo_total'] == pytest.approx(3257660.9382788953, abs=.05)
    anterior = np.array([u['VI'] for u in s['UHE']])
    for t, row in enumerate(r['trajetoria']):
        np.testing.assert_allclose(row['VI'], anterior, atol=1e-6)
        esperado = row['VI'] + row['AFL'] - row['vt'] - row['vv'] + [0., row['vt'][0]+row['vv'][0]]
        np.testing.assert_allclose(row['vf'], esperado, atol=1e-6)
        assert sum(u['Prod']*row['vt'][i] for i, u in enumerate(s['UHE'])) + sum(row['gt']) + row['def'] == pytest.approx(250., abs=1e-6)
        anterior = row['vf']


def test_periodo_fora_do_historico_rejeitado():
    with pytest.raises(ValueError, match='fora do histórico'):
        sistema_dos_leitores(PASTA / 'dados_pysddp', ano=2026)
