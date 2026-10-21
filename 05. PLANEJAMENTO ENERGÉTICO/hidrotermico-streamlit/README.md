# Planejamento hidrotérmico — Batalha → Serra do Facão

Aplicativo Streamlit com Apache ECharts e o mesmo modelo de programação dinâmica/SCIP do notebook `planejamento_hidrotermico_3_estágios_2_UHE.ipynb`.

## Executar no computador

Use Python 3.12. No terminal, dentro desta pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

No Linux/macOS, substitua `.\.venv\Scripts\python.exe` por `.venv/bin/python`.

## Usar

- Ajuste carga, discretização, armazenamento inicial e trajetória na barra lateral.
- Abra **Editar afluências e parâmetros das usinas** para editar as tabelas. Confirme a célula com Enter ou clicando fora.
- O recálculo automático vem ativado. Desative para fazer várias mudanças e então clique em **Recalcular agora**.
- A política na grade é reutilizada quando apenas o volume inicial ou a trajetória muda. As trajetórias e os custos iniciais são recalculados.
- As abas mostram geração, armazenamento, custos imediatos, mapa de calor/superfície 3D, tabelas e hipóteses.
- Em **Dados e exportação**, baixe os parâmetros em JSON ou um ZIP com parâmetros e tabelas CSV (separador `;`, decimal `,`, UTF-8 com BOM).
- **Restaurar valores do notebook** recupera todos os dados originais.

A interface aceita de 2 a 40 níveis por UHE; o padrão original é 24. O limite de 40 é uma proteção de uso da interface, não uma alteração da formulação. O módulo do modelo aceita qualquer inteiro a partir de 2. Existem `6 × NR_DISC²` despachos na recursão, e cada despacho não terminal usa até `NR_DISC²` pesos. Grades maiores podem levar minutos no Streamlit Cloud. A barra de progresso acompanha o processamento. O cache mantém até seis políticas e é compartilhado entre sessões com parâmetros iguais, sem compartilhar entradas de interface.

## Fidelidade ao notebook

`model.py` mantém as variáveis, restrições, ordem dos cenários, recursão, objetivo e solver. A adaptação troca variáveis globais por parâmetros explícitos, adiciona validações, cache na interface e libera o solver mesmo quando há falha.

- Três meses: setembro, outubro, novembro, **todos com 720 horas**.
- Dois cenários **conjuntos**: as duas UHEs no máximo ou as duas no mínimo; 50% cada, independentes entre meses.
- Balanço em cascata com transferência integral no mesmo estágio.
- Produtibilidade fixa, sem evaporação e sem vazão mínima obrigatória.
- Custo futuro terminal zero.
- Interpolação por combinação convexa de **todos** os pares de volumes da grade; pesos endógenos, não probabilidades de afluência nem interpolação bilinear.
- Déficit não negativo e sem teto; custos térmicos e do déficit multiplicados por 720 horas.
- Penalização de vertimento de **R$ 0,01/hm³**, custos internos em R$ milhões, tolerância dual `1e-9`.
- Limite nominal de Serra (212,58 MW por padrão). Nenhum novo limite nominal para Batalha.
- Os valores padrão dos volumes, custos, afluências e capacidades são os do notebook.

**Custo esperado inicial** é a média dos custos totais nos dois cenários para o volume inicial real. **Custo realizado** é a soma dos custos imediatos na trajetória escolhida. Não se deve somar FOB. A operação planejada não é garantidamente mais barata em toda trajetória individual, e empates hidráulicos podem resultar em decisões diferentes entre versões de solver.

O notebook original está em `reference/original.ipynb`, preservado para rastreabilidade e regressão. O app não executa esse arquivo em produção e não depende do Google Drive, de credenciais ou de arquivos externos ao repositório. Os testes executam somente as células auditadas de parâmetros e funções do notebook; não executam instalação ou gráficos.

## Subir para o GitHub

Este aplicativo usa o repositório existente [DanrleiDiegues/electrical-engineering-and-energy-models](https://github.com/DanrleiDiegues/electrical-engineering-and-energy-models), na branch `main`. O `.git` está na pasta `02   Electrical Engineering Master   UFJF`.

O código está em `05. PLANEJAMENTO ENERGÉTICO/hidrotermico-streamlit/`. Não crie outro repositório dentro dessa subpasta. Ao publicar alterações, adicione somente os arquivos do aplicativo e as configurações correspondentes, pois a pasta do mestrado contém outros materiais locais.

O workflow de testes está na raiz do repositório, em `.github/workflows/hidrotermico.yml`. O tema usado pelo Streamlit Cloud está em `.streamlit/config.toml`, também na raiz. A cópia de configuração nesta subpasta permite executar o aplicativo localmente a partir daqui.

## Publicar no Streamlit Community Cloud

1. Entre em https://share.streamlit.io e conecte a conta GitHub.
2. Selecione **Create app** e o repositório `DanrleiDiegues/electrical-engineering-and-energy-models`.
3. Selecione a branch `main` e o arquivo principal `05. PLANEJAMENTO ENERGÉTICO/hidrotermico-streamlit/app.py`.
4. Em **Advanced settings**, escolha **Python 3.12**.
5. Clique em **Deploy**.

O `requirements.txt` instala as dependências, incluindo a distribuição binária de PySCIPOpt com SCIP. Não há secrets a configurar, serviços pagos ou banco de dados necessários. Para repositório privado, a integração Streamlit/GitHub precisa ter acesso a ele. O aplicativo precisa de um servidor Python; GitHub Pages não executa Streamlit.

Referências oficiais: [Deploy no Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [dependências](https://docs.streamlit.io/deploy/concepts/dependencies), [instalação do PySCIPOpt](https://pyscipopt.readthedocs.io/en/stable/install.html), [componente ECharts](https://github.com/andfanilo/streamlit-echarts).

## Verificação

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

A suíte cobre regressão contra o notebook (inclusive grade 24 × 24), balanços nas oito trajetórias possíveis, capacidades, validação das entradas e atualização da interface. Para um ciclo curto, use `python -m pytest -q -m "not full"`. As versões das dependências diretas estão fixadas. A execução real no Streamlit Cloud só poderá ser verificada depois de publicar o repositório.

## Arquivos

- `app.py`: interface e recálculo.
- `model.py`: modelo de otimização parametrizado.
- `charts.py`: gráficos Apache ECharts e ECharts GL.
- `requirements.txt`: dependências de produção.
- `.streamlit/config.toml`: tema e execução.
- `tests/`: verificações automatizadas.
- `reference/original.ipynb`: referência original.

Para o deploy neste repositório, o Cloud encontra `requirements.txt` junto ao arquivo principal e lê `.streamlit/config.toml` a partir da raiz do repositório. Para reproduzir esse modo localmente, execute a partir da pasta que contém o `.git`:

```powershell
python -m streamlit run "05. PLANEJAMENTO ENERGÉTICO/hidrotermico-streamlit/app.py"
```
