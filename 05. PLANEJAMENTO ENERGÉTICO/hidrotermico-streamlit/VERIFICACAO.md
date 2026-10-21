# Verificação — horizonte ajustável e correção do Cloud

Verificado em 21/10/2026, com Python 3.12 e as dependências fixadas no requirements.txt da raiz.

## Resultado

**36 testes aprovados em 133,64 segundos**, executados no repositório real com `python -m pytest -q` a partir da pasta do aplicativo.

A suíte inclui:

- Regressão contra o notebook original, incluindo os três meses originais na grade 24 × 24.
- Comparação com as funções originais para horizontes de um e 12 meses, adaptando apenas a lista de meses e as entradas fornecidas à referência.
- Horizontes de 1, 2, 12, 18 e 24 meses, terminal sem custo futuro e atendimento à carga.
- Balanços hídricos e limites nas oito trajetórias do caso original.
- Horizonte inválido, dados inconsistentes, carga zero e ausência de geração.
- Preservação de afluências e escolhas da trajetória ao reduzir e ampliar o horizonte.
- Gráficos com a mesma quantidade de meses das trajetórias; armazenamento inclui o ponto inicial.
- Recálculo automático e manual sem exibir resultados antigos como atuais.
- Entrada `streamlit_app.py` na raiz, carregando a implementação real e calculando os 12 meses.

A comparação da AST (estrutura sintática) de `despacho_hidrotermico` com a versão anterior foi idêntica: variáveis, balanços, objetivo, restrições e parâmetros do solver não foram alterados.

## Dados para os meses adicionais

Setembro a novembro usam os dados do notebook. Os demais meses iniciam com os valores de novembro como preenchimento editável. Esses valores não são séries históricas nem previsão dos meses adicionados. A interface e a documentação informam essa hipótese.

## Correção de instalação

A imagem fornecida mostra falha de instalação do requirements.txt em um caminho com espaços. O arquivo de dependências foi movido para a raiz do repositório, e foi criada a entrada curta `streamlit_app.py`. O caminho original da implementação permanece disponível e também pode encontrar os requisitos na raiz. A configuração e o workflow foram adaptados para esse arranjo.

A execução no Cloud deve ser acompanhada após o envio deste commit. Os testes descritos acima foram executados localmente em Windows. O GitHub Actions está configurado para repetir a suíte em Linux/Python 3.12.

## Rastreabilidade

O notebook original foi preservado sem modificações em reference/original.ipynb.

SHA-256: `FA308371A36BCCE7AAFBF111A0D692DC5AE470D83C30758137A7AB2B8D10DB07`.

Tolerâncias da regressão: custos na grade com rtol=1e-8 e atol=R$ 0,10; saídas de despacho com rtol=1e-7 e atol=1e-4. As soluções podem ter alocações equivalentes diferentes entre versões de solver.
