# Verificação da implementação

Verificado localmente em 21/10/2026, com Python 3.12 e as dependências fixadas em requirements.txt.

## Modelo

- Teste de equivalência contra as células originais do notebook para a grade 24 × 24: aprovado.
- Comparação em grades menores com carga e parâmetros alterados, trajetória mista e carga zero: aprovada.
- Comparação explícita dos valores padrão contra a célula original de parâmetros: aprovada.
- Balanços de água, atendimento à carga, volumes, engolimentos, capacidades e custo terminal nas oito trajetórias possíveis: aprovados.
- Validações de entradas inválidas e casos sem geração: aprovados.

As comparações usam tolerâncias numéricas explícitas: custos da grade com rtol=1e-8 e atol=R$ 0,10; saídas de despacho com rtol=1e-7 e atol=1e-4. A estrutura matemática e o solver foram mantidos. Empates podem produzir alocações hidráulicas diferentes em outro ambiente ou versão de solver.

## Interface

O teste inicial encontrou um erro de replay do elemento de progresso no cache do Streamlit. A barra foi movida para dentro da função cacheada. Os testes da interface passaram após essa correção.

- Recálculo automático ao alterar carga.
- Modo manual sem apresentar resultados antigos como se fossem atuais.
- Reutilização da política ao alterar armazenamento inicial.
- Mensagem de validação para afluências inconsistentes.

Resultado do último ciclo curto: **20 passed, 1 deselected**. O teste excluído é a comparação completa de 24 níveis, já aprovada no ciclo anterior; o módulo do modelo não foi alterado depois dela. Total: **21 testes aprovados**, considerando os dois ciclos. O workflow no GitHub executa todos juntos.

## Valores observados na prévia padrão

Valores arredondados exibidos para a trajetória mínimo/mínimo/mínimo e a grade original:

| Indicador | R$ milhões |
|---|---:|
| Custo esperado inicial | 19,13 |
| Realizado com custo futuro | 22,14 |
| Realizado com despachos isolados | 72,41 |
| Isolados menos planejado | 50,27 |

Esses valores são saídas do modelo didático para seus parâmetros, não estimativas de operação real.

## Rastreabilidade

SHA-256 de reference/original.ipynb:

`FA308371A36BCCE7AAFBF111A0D692DC5AE470D83C30758137A7AB2B8D10DB07`

O notebook original foi copiado integralmente. Os testes executam somente as células 4, 6, 8 e 10, cujo código foi inspecionado; não executam comandos de instalação.

## Limite da verificação

A execução foi verificada localmente em Windows. O teste em Linux está configurado no GitHub Actions; não foi executado remotamente. A publicação e a execução efetiva no Streamlit Community Cloud dependem do envio ao repositório GitHub e do deploy posterior.

## Inspeção visual e exportação

Verificados no navegador local: indicadores legíveis, gráficos de geração, mapa de calor e superfície 3D com os eixos e unidades esperados, manutenção da aba selecionada ao mudar a visualização e download do ZIP de resultados. A superfície 3D renderizou com WebGL e não houve erros reportados pelo console na inspeção do componente.
