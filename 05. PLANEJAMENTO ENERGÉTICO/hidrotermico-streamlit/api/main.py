"""Rotas HTTP. Cada rota só valida a entrada e chama uma função de servicos.py.

Para rodar (na pasta hidrotermico-streamlit):
    uvicorn api.main:app --reload
Documentação interativa: http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import servicos
from .esquemas import PedidoArvore, PedidoSemana

app = FastAPI(title="Planejamento hidrotérmico UFJF", version="0.1")
# Permite que a interface React (em outra porta, no desenvolvimento local) chame a API.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def _executa(funcao, **kwargs):
    try:
        return funcao(**kwargs)
    except servicos.ErroDeEntrada as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:   # SCIP sem solução viável
        raise HTTPException(409, f"O otimizador não encontrou solução: {exc}")


@app.get("/saude")
def saude():
    return {"ok": True}


@app.get("/catalogo")
def catalogo():
    """Usinas térmicas aceitas pelo modelo, lidas pelo PySDDP."""
    return _executa(servicos.catalogo)


@app.post("/semana")
def semana(pedido: PedidoSemana):
    """Compromisso térmico semanal: despacho, CMO, CMA, mérito e (opcional) impacto de carga."""
    return _executa(servicos.calcular_semana,
                    escolhas=[u.model_dump() for u in pedido.unidades], percentual_carga=pedido.percentual_carga,
                    custo_futuro=pedido.custo_futuro, hora_impacto=pedido.hora_impacto, delta_impacto=pedido.delta_impacto)


@app.get("/arvore/padroes")
def padroes_arvore():
    return servicos.padroes_arvore()


@app.post("/arvore")
def arvore(pedido: PedidoArvore):
    """PL único em árvore de cenários, de 3 a 8 meses."""
    dados = pedido.model_dump()
    return _executa(servicos.calcular_arvore, **dados)
