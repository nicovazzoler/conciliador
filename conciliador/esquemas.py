"""La forma del JSON de la API. FastAPI valida cada respuesta contra esto y lo publica en /docs."""
from datetime import date
from typing import Literal

from pydantic import BaseModel


class Totales(BaseModel):
    movimientos: int
    pesos_centavos: int
    dolares_centavos: int
    total_usd_centavos: int
    sin_usd: int


class Categoria(BaseModel):
    categoria: str | None
    movimientos: int
    total_usd_centavos: int | None  # Sin cotización no hay USD: ver sin_usd.
    porcentaje: float | None
    sin_usd: int


class Fijo(BaseModel):
    concepto: str
    moneda: str
    anotado_centavos: int
    pagos: int
    cobrado_centavos: int
    estado: Literal["sin datos", "sin debitar", "más caro", "más barato", "bien"]


class Cuota(BaseModel):
    concepto: str
    esperada: str | None  # "03/06"; vacía en las que llegaron sin plan.
    llegaron: str | None
    cobros: int
    monto_centavos: int
    estado: Literal["sin datos", "falta", "sin plan", "repetida", "otro número", "bien"]


class Dia(BaseModel):
    fecha: date
    movimientos: int
    pesos_centavos: int
    detalle: str


class Resumen(BaseModel):
    tarjeta: str
    numero: str
    cierre: date
    vencimiento: date
    a_pagar_pesos: int
    a_pagar_usd: int
    falta_pesos: int
    falta_usd: int
    estado: Literal["nada que pagar", "confirmado", "avisado", "parcial", "impago"]


class Importado(BaseModel):
    mercado_pago: bool
    resumenes: str | None


class Reporte(BaseModel):
    mes: str
    totales: Totales
    categorias: list[Categoria]
    fijos: list[Fijo]
    cuotas: list[Cuota]
    dias_sobre_tope: list[Dia]
    resumenes: list[Resumen]
    pendientes: int
    importado: Importado
