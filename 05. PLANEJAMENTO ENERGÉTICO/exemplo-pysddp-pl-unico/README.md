# Exemplo — Leitores PySDDP e PL Único

- Lê Batalha e Serra do Facão com `Hidr`, e vazões naturais com `Vazoes`.
- Converte a vazão de Serra em contribuição incremental e alimenta o PL Único.
- Resolve com PySCIPOpt/SCIP; o PySDDP participa somente da leitura dos arquivos.

Abra **Exemplo - Leitores PySDDP e PL Único.ipynb** no Colab e execute as células em ordem. O notebook é independente e baixa os dois arquivos públicos se eles não existirem na pasta de execução.

Para executar o script, instale `requirements.txt` desta pasta e rode `python executar_exemplo.py`. Os testes usam `python -m pytest test_leitores.py -q`.

## Dados e hipóteses

Os arquivos em `dados_pysddp/` vêm da amostra pública do [PySDDP, commit dd8931084696f5652211f1fe342c18d132a61dcf](https://github.com/AndreMarcato/PySDDP/tree/dd8931084696f5652211f1fe342c18d132a61dcf/PySDDP/pmo). Os hashes são conferidos pelo código e a licença original acompanha os arquivos. Esta amostra não é uma exportação do caso 103 da plataforma.

O exemplo usa setembro a novembro de 2017, 320 postos e ano-base 1931. O cadastro informa os postos 22 (Batalha) e 251 (Serra). As vazões naturais de Batalha são 11, 9 e 43 m³/s; as de Serra, 18, 15 e 68 m³/s. As contribuições incrementais adotadas em Serra são 7, 6 e 25 m³/s.

Adota-se a vazão nominal total como limite constante de turbinamento e uma produtibilidade constante calculada com a queda nominal e a perda hidráulica cadastradas. Essa aproximação não reproduz as curvas completas do NEWAVE. As térmicas, CVUs, carga de 250 MW médios e percentuais iniciais 39,7%/50,2% continuam sendo entradas do exercício, não campos lidos desses dois arquivos. Cada mês mantém 720 horas e o custo terminal é zero.

O custo verificado do exemplo é aproximadamente **R$ 3.257.660,94**, com déficit numericamente zero. Ele difere do exemplo original do Colab porque os dados de entrada são diferentes.

Os testes conferem os campos contra os bytes dos arquivos, os balanços da cascata e o ótimo do SCIP contra uma formulação matricial independente resolvida pelo HiGHS. Para utilizar outro deck, chame `sistema_dos_leitores` com a pasta, período, número de postos e ano-base correspondentes; não use o verificador de hashes da amostra para um arquivo diferente.
