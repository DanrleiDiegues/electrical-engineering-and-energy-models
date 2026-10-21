# Simulador - Planejamento Energético

Aplicativo Streamlit com Apache ECharts, programação dinâmica e SCIP, baseado no notebook `planejamento_hidrotermico_3_estágios_2_UHE.ipynb`.

## Horizonte e dados

O padrão é **12 meses**, começando em setembro. O controle **Número de meses** aceita de **1 a 60** na interface; o modelo aceita qualquer inteiro positivo. Para horizontes acima de 12 meses, os rótulos identificam os ciclos anuais.

Setembro, outubro e novembro mantêm as afluências do notebook. Os meses adicionais iniciam com as afluências de novembro apenas como **exemplo editável**, não como dados históricos ou previsão hidrológica. Edite a tabela de afluências para representar seu cenário. Afluências e escolhas da trajetória já editadas são preservadas ao reduzir e depois ampliar o horizonte na mesma sessão.

O recálculo automático vem ativado. Desative-o para editar vários campos antes de clicar em **Recalcular agora**. O padrão de discretização continua em 24 níveis por UHE. O planejamento resolve `2 × número de meses × NR_DISC²` despachos: são **13.824** para 12 meses com 24 níveis. A primeira execução pode levar vários minutos, dependendo da máquina. A política é reutilizada quando apenas o volume inicial ou a trajetória muda.

## Executar a partir da raiz do repositório

O `.git` existente está em `02   Electrical Engineering Master   UFJF`. Dentro dessa pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

No Linux/macOS, use `.venv/bin/python` em lugar de `.\.venv\Scripts\python.exe`.

O código permanece em `05. PLANEJAMENTO ENERGÉTICO/hidrotermico-streamlit/`. A entrada `streamlit_app.py` na raiz carrega essa implementação sem duplicá-la.

## Publicar no Streamlit Community Cloud

Repositório: [DanrleiDiegues/electrical-engineering-and-energy-models](https://github.com/DanrleiDiegues/electrical-engineering-and-energy-models).

| Campo | Valor |
|---|---|
| Repository | `DanrleiDiegues/electrical-engineering-and-energy-models` |
| Branch | `main` |
| Main file path recomendado | `streamlit_app.py` |
| Advanced settings → Python | `3.12` |
| Secrets | Não são necessários |

Os requisitos de produção estão em **requirements.txt na raiz do repositório**. O arquivo foi retirado da subpasta cujo nome contém espaços, para evitar a falha de instalação mostrada no Cloud. A configuração do tema continua em `.streamlit/config.toml` na raiz. Deploys existentes que apontem para o arquivo antigo na subpasta também encontram as dependências na raiz.

Em uma nova publicação, entre em [Streamlit Community Cloud](https://share.streamlit.io/), clique em **Create app**, preencha os campos acima e clique em **Deploy**. Para um app já publicado, o Cloud acompanha as alterações da branch. Caso o estado de erro permaneça, use **Manage app → Reboot app** para refazer a inicialização.

## Usar e exportar

- Barra lateral: horizonte, carga, discretização, armazenamento inicial e trajetória mensal.
- **Editar afluências e parâmetros das usinas**: afluências locais, limites, produtibilidades, capacidades térmicas e custos.
- **Operação e armazenamento**: geração, déficit, volumes e custos imediatos para o horizonte inteiro.
- **Custos futuros**: mapa de calor ou superfície 3D em qualquer mês selecionado.
- **Dados e exportação**: tabelas mensais, parâmetros JSON e ZIP com todos os resultados.
- **Restaurar cenário padrão**: recupera os 12 meses e os valores iniciais de exemplo.

Os CSVs usam separador `;`, vírgula decimal e UTF-8 com BOM. Os parâmetros exportados incluem `n_meses`, afluências e trajetória completas. JSONs antigos de três meses têm seu horizonte inferido a partir das afluências.

## Fidelidade matemática

A extensão altera o número de estágios e as dimensões das entradas. A formulação de cada despacho é preservada:

- Dois cenários conjuntos equiprováveis: ambas as UHEs no máximo ou ambas no mínimo, independentes entre meses.
- Transferência integral do turbinamento e vertimento de Batalha para Serra no mesmo estágio.
- Estágios de 30 dias e 720 horas, inclusive meses com outra duração no calendário.
- Produtibilidade fixa, sem evaporação ou vazão mínima obrigatória.
- Custo futuro terminal zero no último mês escolhido.
- Interpolação por combinação convexa de todos os pares da grade; pesos escolhidos pelo solver, não probabilidades de afluência ou interpolação bilinear.
- Limites dos volumes, engolimentos, capacidades térmicas e potência nominal de Serra; nenhum limite nominal novo para Batalha.
- Custo térmico e do déficit multiplicados por 720 horas, penalização de vertimento de R$ 0,01/hm³, custos internos em R$ milhões e tolerância dual de 1e-9.

O custo esperado inicial é a média dos custos totais dos dois cenários. O custo realizado soma os custos imediatos da trajetória escolhida. Não se deve somar FOB, pois isso repetiria os custos futuros. A política ótima em expectativa não garante menor custo em toda trajetória individual.

O notebook original está preservado em `reference/original.ipynb`. Para reproduzir suas entradas, selecione três meses. Os testes comparam diretamente as células auditadas do notebook com o modelo, inclusive após ampliar a lista de meses.

## Testes

A partir da raiz do repositório:

```powershell
python -m pip install -r "05. PLANEJAMENTO ENERGÉTICO/hidrotermico-streamlit/requirements-dev.txt"
python -m pytest -c "05. PLANEJAMENTO ENERGÉTICO/hidrotermico-streamlit/pytest.ini" "05. PLANEJAMENTO ENERGÉTICO/hidrotermico-streamlit/tests" -q
```

O workflow `.github/workflows/hidrotermico.yml` executa a suíte em Linux/Python 3.12. Há verificações de equivalência com o notebook, horizonte de um mês, horizontes de 12 meses e superiores, balanços, custo terminal, validação, preservação das edições e recálculo da interface.

Referências oficiais: [organização no Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization), [dependências](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), [PySCIPOpt](https://pyscipopt.readthedocs.io/en/stable/install.html), [ECharts para Streamlit](https://github.com/andfanilo/streamlit-echarts).
