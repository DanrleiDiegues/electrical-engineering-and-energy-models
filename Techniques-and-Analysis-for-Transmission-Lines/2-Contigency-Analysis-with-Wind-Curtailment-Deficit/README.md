# IEEE 118 DC-OPF com Geração Eólica e Análise de Contingência N-1

Este repositório contém dois arquivos principais:

- `ieee118.py`: dados do sistema IEEE 118 barras, incluindo barras, linhas, geradores convencionais, geradores fictícios para déficit de carga, geradores eólicos e parâmetros de cenários.
- `OPF_linprog_Final_MinPerdasWWind_CTG.py`: implementação do modelo DC-OPF linear com cenários estocásticos de carga e geração eólica, resolução via `scipy.optimize.linprog` e análise de contingência N-1 em linhas de transmissão.

## Objetivo do projeto

O projeto avalia o comportamento do sistema IEEE 118 sob:

- variação estocástica de demanda
- variação estocástica de geração eólica
- contingências N-1 em linhas de transmissão
- minimização de custo proxy de operação com penalização de:
  - geração convencional
  - corte de vento
  - déficit de carga

## Estrutura dos arquivos

### 1. `ieee118.py`
Responsável por definir os dados de entrada do sistema:

- `bars`: dados das 118 barras
- `lines`: dados das linhas de transmissão
- `generators`: geradores convencionais + geradores fictícios de corte de carga
- `wind_generators`: geradores eólicos
- `SCENARIO_CONFIG`: configuração dos cenários estocásticos
- `dict_to_matrices(...)`: conversão das listas de dicionários para matrizes NumPy (`DBAR`, `DLIN`, `DGER`, `DGW`)

### 2. `OPF_linprog_Final_MinPerdasWWind_CTG.py`
Responsável por:

- preparar os dados do sistema
- gerar cenários de carga e vento
- montar o modelo linear do OPF
- resolver o problema com `linprog`
- calcular fluxos, perdas e custos
- aplicar contingências em linhas
- consolidar rankings e relatórios
- exportar resultados para Excel
- gerar gráficos com Plotly

## Formulação resumida

### Função objetivo
O modelo considera:

- custo unitário da geração convencional
- penalização de corte de vento
- penalização elevada para déficit de carga

Na implementação atual, a função objetivo é equivalente a:

- geração convencional: custo `1`
- corte de vento: custo `60`
- déficit de carga: custo `400`

## Principais funções

### Dados e preparação
- `inpdat_opf(...)`: converte os dados do sistema para a estrutura usada pelo modelo
- `print_system_overview(...)`: resumo do sistema

### Cenários
- `generate_load_scenario(...)`: gera cenários estocásticos de carga
- `generate_wind_scenario(...)`: gera cenários estocásticos de vento

### Modelo e solução
- `build_model_scenario(...)`: monta a função objetivo, restrições e limites
- `solve_opf_scenario(...)`: resolve o OPF de um cenário

### Contingência
- `validate_ctg_line_order(...)`: valida a lista de linhas para contingência
- `apply_line_contingency(...)`: retira uma linha do sistema
- `restore_line_contingency(...)`: restaura a linha retirada
- `run_contingency_study(...)`: executa o estudo N-1 completo

### Exportação e apoio
- `export_study_to_excel(...)`: exporta resultados de um estudo para Excel
- `export_contingency_study_to_excel(...)`: exporta consolidado das contingências

## Dados do caso estudado

### Sistema base
- 118 barras
- 186 linhas
- 54 geradores convencionais reais
- 91 geradores fictícios para déficit de carga
- 3 geradores eólicos

### Geração eólica instalada
- barra 9: 250 MW
- barra 33: 350 MW
- barra 35: 500 MW

Potência eólica total instalada: **1100 MW**

## Modelagem estocástica

### Demanda
A carga é modelada por distribuição Normal com:

- componente global
- componente local por barra
- limites de truncamento para evitar cenários extremos inviáveis

### Geração eólica
A disponibilidade eólica é modelada por distribuição Weibull e limitada ao intervalo `[0, 1]`, sendo multiplicada pela potência máxima instalada de cada unidade.

## Saídas geradas

O script principal pode gerar:

- resumo do sistema
- consolidação das contingências
- rankings por:
  - corte de carga
  - curtailment
  - MVu
  - MVd
- arquivos Excel com:
  - cenários
  - resumo
  - matrizes do modelo
  - rankings
- gráficos interativos com Plotly

## Como executar

### 1. Instale as dependências
```bash
pip install -r requirements.txt
```

### 2. Execute o script principal
```bash
python OPF_linprog_Final_MinPerdasWWind_CTG.py
```

## Configurações principais

As principais configurações estão em `ieee118.py`, dentro de `SCENARIO_CONFIG`:

- `num_scenarios`
- `base_power_MW`
- `load_distribution`
- `wind_distribution`
- `weibull_scale`
- `weibull_shape`
- `custo_corte_carga`
- `custo_corte_vento`
- `num_real_generators`
- `num_fict_generators`

Além disso, no arquivo principal, a lista de contingências 3 CTG principais pode ser ajustada em:

```python
CTG_LINE_ORDER = [96, 37, 103]
```

## Observações importantes

- O modelo usa aproximação **DC-OPF**, portanto não representa potência reativa nem magnitude de tensão na otimização.
- As perdas são calculadas em pós-processamento a partir dos ângulos de barra.
- O déficit de carga é modelado como geradores fictícios de alto custo.
- O corte de vento é modelado por variáveis explícitas de curtailment.

## Estrutura esperada do diretório

```text
.
├── ieee118.py
├── OPF_linprog_Final_MinPerdasWWind_CTG.py
├── requirements.txt
└── data/
```

## Licença

Uso acadêmico / educacional.
