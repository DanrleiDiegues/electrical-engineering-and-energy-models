# API do planejamento hidrotérmico

Expõe em HTTP os mesmos cálculos do app Streamlit, para uma interface React consumir.
A matemática **não foi duplicada**: a API chama os módulos da pasta acima.

## Onde olhar (do mais didático ao mais técnico)

| Arquivo | O que tem |
|---|---|
| `../modelo_semana.py` | MILP do compromisso térmico semanal (SCIP), CMO e CMA por duais |
| `../modelo_arvore.py` | PL único em árvore de cenários (`estudo_arvore` é o ponto de entrada) |
| `../mercado_semana.py` | resumo diário, ordem de mérito e sua explicação (só pandas) |
| `servicos.py` | DESSEM semanal e árvore: monta a entrada, chama o modelo, devolve dicionários/JSON |
| `servicos_pl.py` | PL Único determinístico (`../pl_model.py`) |
| `servicos_pde.py` | PDE Didática (`../model.py`), com cálculo em segundo plano |
| `esquemas.py` | formato e limites das entradas (Pydantic) |
| `main.py` | as rotas HTTP, bem curtas |

## Rodar localmente

```bash
pip install -r requirements-dev.txt -r requirements-api.txt
uvicorn api.main:app --reload        # na pasta hidrotermico-streamlit
```

Abra http://127.0.0.1:8000/docs: dá para testar cada rota pelo navegador.

## Rotas

- `GET /catalogo`: usinas aceitas e valores de cadastro.
- `POST /semana`: despacho, CMO, CMA, mérito e impacto de carga. Exemplo de corpo:
  `{"unidades": [{"nome": "ERB CANDEIAS · UG 1", "ajustes": {"cvu": 150}}], "percentual_carga": 100, "custo_futuro": true, "hora_impacto": 20}`
- `GET /arvore/padroes` e `POST /arvore`: PL em árvore, de 3 a 8 meses, com parâmetros opcionais.

- `GET /pl/padroes?perfil=colab|anual` e `POST /pl`: PL Único determinístico (resposta imediata).
- `GET /pde/padroes`, `POST /pde` e `GET /pde/{id}`: PDE Didática. O cálculo leva de segundos a minutos (milhares de despachos no SCIP), então `POST /pde` devolve um `id` e `GET /pde/{id}` informa `estado` (fila, calculando, pronto, erro), `feito/total` e, no fim, o `resultado`.

Erros: `422` entrada inválida, `409` o otimizador não achou solução viável.

## Testes

`pytest tests/test_api.py` confere que a API devolve os mesmos números do modelo e do app Streamlit.

## Usar a API direto do Python

```python
from api.servicos import calcular_semana
r = calcular_semana([{"nome": "ERB CANDEIAS · UG 1"}], custo_futuro=False)
```
