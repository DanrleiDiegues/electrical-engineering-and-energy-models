"""Formato dos dados que entram e saem da API (Pydantic valida as entradas automaticamente)."""
from pydantic import BaseModel, Field


class AjustesUnidade(BaseModel):
    """Valores que substituem os do cadastro DESSEM. Campo omitido = valor do cadastro."""
    Ton: int | None = Field(None, ge=1, description="Tempo mínimo ligada (h)")
    Toff: int | None = Field(None, ge=1, description="Tempo mínimo desligada (h)")
    Pmin: float | None = Field(None, ge=0, description="Potência mínima (MW)")
    Pmax: float | None = Field(None, gt=0, description="Potência máxima (MW)")
    subida: float | None = Field(None, gt=0, description="Rampa de subida (MW/h)")
    descida: float | None = Field(None, gt=0, description="Rampa de descida (MW/h)")
    cvu: float | None = Field(None, ge=0, description="Custo variável (R$/MWh)")
    partida: float | None = Field(None, ge=0, description="Custo de partida (R$)")


class UnidadeEscolhida(BaseModel):
    nome: str = Field(description='Chave do catálogo, por exemplo "BBF BALIZA · UG 1". Veja GET /catalogo.')
    ajustes: AjustesUnidade = AjustesUnidade()


class PedidoSemana(BaseModel):
    unidades: list[UnidadeEscolhida] = Field(min_length=1, max_length=4)
    percentual_carga: float = Field(100, gt=0, description="Carga em % do caso-base")
    custo_futuro: bool = Field(True, description="Aplicar a função de custo futuro (cortes)")
    hora_impacto: int | None = Field(None, ge=0, le=167, description="Hora para o teste de impacto (opcional)")
    delta_impacto: float = Field(1.0, gt=0, description="Acréscimo de carga (MW) no teste de impacto")


class ParametrosUHE(BaseModel):
    vmin: float = Field(description="Volume mínimo (hm³)")
    vmax: float = Field(description="Volume máximo (hm³)")
    vi: float = Field(ge=0, le=100, description="Volume inicial (% do volume útil)")
    qmax: float = Field(ge=0, description="Engolimento máximo (m³/s)")
    prod: float = Field(ge=0, description="Produtibilidade (MW por m³/s)")


class ParametrosTermica(BaseModel):
    nome: str
    pmax: float = Field(ge=0, description="Potência máxima (MW)")
    cvu: float = Field(ge=0, description="CVU (R$/MWh)")


class PedidoArvore(BaseModel):
    meses: int = Field(3, ge=3, le=8)
    carga: float | None = Field(None, ge=0, description="Carga mensal (MW médios). Omitido = padrão do estudo")
    cdef: float | None = Field(None, ge=0, description="Custo do déficit (R$/MWh)")
    afl: float = Field(100, gt=0, description="Escala das afluências (%)")
    uhes: list[ParametrosUHE] | None = Field(None, description="Batalha e Serra do Facão, nessa ordem. Omitido = padrão")
    termicas: list[ParametrosTermica] | None = Field(None, description="Omitido = Baliza UG 1 e Candeias UG 1 com dados do estudo")
