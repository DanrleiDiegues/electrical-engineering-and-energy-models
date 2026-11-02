from pathlib import Path

from leitores_exemplo import obter_arquivos_exemplo, sistema_dos_leitores
from modelo_pl_unico import pl_unico_det, tabela_det

if __name__ == '__main__':
    pasta = obter_arquivos_exemplo(Path(__file__).with_name('dados_pysddp'))
    sistema, cadastro, vazoes = sistema_dos_leitores(pasta)
    resultado = pl_unico_det(sistema, cenario=0)
    print(cadastro.to_string(index=False))
    print(vazoes.to_string(index=False))
    print(tabela_det(sistema, resultado).to_string(index=False))
    print(f"Custo total do PL Único: R$ {resultado['custo_total']:,.2f}")
