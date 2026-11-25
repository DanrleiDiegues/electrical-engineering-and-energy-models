"""Rotas HTTP. Cada rota só valida a entrada e chama uma função de servicos.py.

Para rodar (na pasta hidrotermico-streamlit):
    uvicorn api.main:app --reload
Documentação interativa: http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import servicos, servicos_pde, servicos_pl
from .esquemas import PedidoArvore, PedidoPDE, PedidoPL, PedidoSemana

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
                    custo_futuro=pedido.custo_futuro, hidro_flat=pedido.hidro_flat, hora_impacto=pedido.hora_impacto, delta_impacto=pedido.delta_impacto)


@app.get("/arvore/padroes")
def padroes_arvore():
    return servicos.padroes_arvore()


@app.post("/arvore")
def arvore(pedido: PedidoArvore):
    """PL único em árvore de cenários, de 3 a 8 meses."""
    dados = pedido.model_dump()
    return _executa(servicos.calcular_arvore, **dados)


# ---------- PL Único determinístico ----------
@app.get("/pl/padroes")
def pl_padroes(perfil: str = "colab"):
    """Valores iniciais: perfil "colab" (3 meses) ou "anual" (12 meses)."""
    return servicos.limpa(servicos_pl.padroes(perfil))


@app.post("/pl")
def pl(pedido: PedidoPL):
    """PL Único: um único problema linear para todos os meses, com a trajetória de afluências conhecida."""
    try:
        return servicos.limpa(servicos_pl.calcular(pedido.model_dump()))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, f"O otimizador não encontrou solução: {exc}")


# ---------- PDE Didática (cálculo em segundo plano) ----------
@app.get("/pde/padroes")
def pde_padroes(n_meses: int = 12):
    return servicos.limpa(servicos_pde.padroes(n_meses))


@app.post("/pde")
def pde_iniciar(pedido: PedidoPDE):
    """Inicia o cálculo e devolve o número da tarefa. Consulte o andamento em GET /pde/{id}."""
    try:
        return {"id": servicos_pde.iniciar(pedido.model_dump())}
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/pde/{tarefa_id}")
def pde_consultar(tarefa_id: str):
    """estado: fila, calculando, pronto ou erro; `resultado` só vem quando pronto."""
    t = servicos_pde.consultar(tarefa_id)
    if t is None:
        raise HTTPException(404, "Tarefa desconhecida (a API pode ter sido reiniciada).")
    return servicos.limpa(t)
