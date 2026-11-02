# Verificação — PDE Didática e PL Único

Verificado em 02/11/2026, com Python 3.12 e as dependências fixadas no requirements.txt da raiz.

## Resultado

**52 testes aprovados em 207,50 segundos**, executados com `python -m pytest -q` na cópia de trabalho da versão a publicar, em Windows. Os 44 testes existentes da PDE foram mantidos; oito testes cobrem o PL e sua interface.

O PL reproduziu o custo de referência do Colab: **R$ 22.138.227,67668162**, sem déficit. Foram conferidos balanços físicos, carga variável, calendário anual, validação das entradas, recálculo manual sem resultados desatualizados, persistência das edições e independência dos controles ao alternar os métodos. As funções de modelagem foram extraídas do notebook, mantendo suas restrições e objetivo em PySCIPOpt/SCIP.

O exemplo separado `../exemplo-pysddp-pl-unico/` passou em **três testes adicionais**: leitura dos arquivos públicos com hashes fixos, conferência dos balanços e comparação com um PL montado independentemente no SciPy/HiGHS. O problema é resolvido com SCIP; o HiGHS é usado somente como verificação. Custo do exemplo: **R$ 3.257.660,9382788953**, sem déficit. A amostra pública do PySDDP (setembro a novembro de 2017) não é uma exportação do caso 103. Hipóteses de conversão estão documentadas no exemplo.

Os dois notebooks foram executados integralmente. O notebook principal preserva as células anteriores e os gráficos comparativos, acrescentando gráficos individuais de despacho, armazenamento e custo para cada método, além da convergência da PDDD.

A suíte inclui:

- Regressão contra o notebook original, incluindo os três estágios originais na grade 24 × 24.
- Comparação da recursão com demanda variável por estágio com as funções originais, alterando apenas a entrada de carga de cada estágio.
- Equivalência entre demanda constante e vetor mensal constante.
- Carga mensal zero, picos acima da capacidade, valores inválidos e exportação da demanda efetiva.
- Balanços hídricos e energéticos, limites das usinas, custo terminal e horizontes ajustáveis.
- Janeiro a dezembro no horizonte anual e identificação de ciclos acima de 12 meses.
- Barras laterais de afluência mínima/máxima globais e por mês, e seleção de trajetórias.
- Preservação das edições ao alternar modos de carga, modos de afluência e tamanho do horizonte.
- Recálculo automático e manual, gráficos e entrada pela raiz streamlit_app.py.

No cenário demonstrativo de 12 meses, carga constante de 250 MW médios, trajetória de máximas (220 m³/s em Batalha e 350 m³/s em Serra) e grade 4 × 4, a simulação planejada apresentou **zero déficit em todos os meses**, com custo realizado de aproximadamente R$ 17,55 milhões. O resultado se refere a essas entradas e à discretização indicada; cargas e afluências diferentes podem produzir déficit.

## Fidelidade e limites

A carga mensal substitui somente a demanda do estágio no balanço energético. As variáveis, demais restrições, objetivo, probabilidades dos dois cenários, interpolação e solver foram preservados. O modelo mantém estágios de 30 dias/720 horas mesmo com rótulos de meses civis.

Os limites físicos das usinas permanecem os mesmos. Com os parâmetros padrão, a capacidade máxima do conjunto é aproximadamente 268,14 MW médios. Aumentar afluências não elimina déficit obrigatório quando a carga ultrapassa essa capacidade.

As novas faixas de afluência são entradas demonstrativas editáveis, não observações históricas ou previsões. A política ainda considera os dois cenários conjuntos equiprováveis; a trajetória selecionada determina apenas o cenário realizado em cada estágio.

## Publicação

O GitHub Actions está configurado para repetir a suíte em Linux/Python 3.12. A confirmação da execução no Cloud e o commit publicado são registrados no relatório de publicação entregue ao usuário.

## Rastreabilidade

O notebook original foi preservado sem modificações em reference/original.ipynb.

SHA-256: FA308371A36BCCE7AAFBF111A0D692DC5AE470D83C30758137A7AB2B8D10DB07.

Tolerâncias da regressão: custos na grade com rtol=1e-8 e atol=R$ 0,10; saídas de despacho com rtol=1e-7 e atol=1e-4. As soluções podem ter alocações equivalentes diferentes entre versões de solver.
