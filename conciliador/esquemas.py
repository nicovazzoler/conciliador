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


class MesHistorial(BaseModel):
    mes: str
    pesos_centavos: int
    dolares_centavos: int
    total_usd_centavos: int


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


# Lo que recibe la API.


class GastoNuevo(BaseModel):
    monto: str  # Texto, como "9.832,83": un número viajaría como float.
    descripcion: str
    fecha: date | None = None  # Sin fecha: hoy.
    moneda: Literal["ARS", "USD"] = "ARS"
    medio: Literal["efectivo", "debito", "transferencia"] = "efectivo"
    confirmado: bool = False  # La página lo manda después de mostrar los avisos.
    categoria: str | None = None


class PagoNuevo(BaseModel):
    tarjeta: Literal["tarjeta_comafi", "tarjeta_nacion"]
    monto: str
    fecha: date | None = None
    moneda: Literal["ARS", "USD"] = "ARS"


# Lo que devuelve.


class Aviso(BaseModel):
    codigo: Literal["igual_al_anterior", "lejos_de_lo_previsto", "grande_sin_anticipar"]
    mensaje: str


class Avisos(BaseModel):
    avisos: list[Aviso]


class Guardado(BaseModel):
    id: int
    categoria: str | None = None
    plan_concepto: str | None = None


class Manual(BaseModel):
    id: int
    fecha: date
    descripcion: str
    monto_centavos: int
    moneda: str
    tipo: str
    medio: str | None
    tarjeta: str | None
    categoria: str | None
    plan_concepto: str | None


# Revisar.


class Pendiente(BaseModel):
    id: int
    fecha: date
    descripcion: str
    monto_centavos: int
    moneda: str
    sugerido: str  # El texto que se propone para la regla.


class Resolucion(BaseModel):
    """O una categoría (con regla opcional), o `cambio: true` si no fue un gasto."""

    categoria: str | None = None
    regla: str | None = None
    cambio: bool = False


class GrupoVarios(BaseModel):
    texto: str
    moneda: str
    movimientos: int
    total_centavos: int
    ejemplo: str
    plan_concepto: str | None  # Si el grupo es de un fijo o una cuota del plan.


class ReglaNueva(BaseModel):
    texto: str
    categoria: str


class ReglaGuardada(BaseModel):
    categorizados: int


# Importar.


class InformeArchivo(BaseModel):
    archivo: str
    reconocido: bool
    nuevas: int
    repetidas: int
    errores: list[str]
    problemas: list[str]  # Lo que no cerró al verificar: saldos o totales.


class Importacion(BaseModel):
    informes: list[InformeArchivo]
    aviso_cotizaciones: str | None
    pendientes: int
    sin_usd: int
