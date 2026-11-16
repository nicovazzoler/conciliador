"""La forma del JSON de la API. FastAPI valida cada respuesta contra esto y lo publica en /docs."""
from datetime import date, datetime
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
    fuente: str  # mercado_pago, tarjeta_comafi, tarjeta_nacion o manual.
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
    fuentes: list[str]  # De dónde vienen los movimientos del grupo.


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


# Plan.


class FijoEntrada(BaseModel):
    concepto: str
    texto: str  # Lo que se busca en la descripción de los movimientos.
    monto: str  # Texto, como en Cargar: nunca float.
    moneda: Literal["ARS", "USD"] = "ARS"
    dia: int | None = None
    categoria: str | None = None


class CuotaEntrada(BaseModel):
    concepto: str
    texto: str
    monto: str
    moneda: Literal["ARS", "USD"] = "ARS"
    cantidad: int
    primer_mes: str  # AAAA-MM
    categoria: str | None = None


class FijoPlan(BaseModel):
    id: int
    concepto: str
    texto: str
    monto_centavos: int
    moneda: str
    dia: int | None
    categoria: str | None


class CuotaPlan(BaseModel):
    id: int
    concepto: str
    texto: str
    monto_centavos: int
    moneda: str
    cantidad: int
    primer_mes: str
    categoria: str | None


class Plan(BaseModel):
    fijos: list[FijoPlan]
    cuotas: list[CuotaPlan]


# Inversiones.


class OperacionNueva(BaseModel):
    fecha: date
    activo: str
    tipo_activo: Literal["cripto", "accion"]
    lado: Literal["compra", "venta"]
    cantidad: str  # Texto decimal: 0,0412. Nunca float.
    precio: str  # USD por unidad.
    comision: str = "0"
    # Lo leído de una captura dice de dónde viene. Con número, una operación no se carga dos veces.
    fuente: Literal["manual", "quantfury", "binance", "captura"] = "manual"
    numero_operacion: str | None = None


class OperacionLeida(BaseModel):
    """Una operación leída de una captura: todavía no está guardada."""

    fecha: date
    activo: str
    tipo_activo: Literal["cripto", "accion"]
    lado: Literal["compra", "venta"]
    fuente: Literal["quantfury", "binance", "captura"]
    cantidad: str  # Con coma decimal y sin miles, como se carga a mano.
    precio: str
    comision: str
    numero_operacion: str | None
    nota: str | None  # Lo que convenga revisar de esta operación.


class LecturaCapturas(BaseModel):
    operaciones: list[OperacionLeida]
    avisos: list[str]


class PosicionInversion(BaseModel):
    activo: str
    tipo_activo: str
    cantidad: str
    costo_promedio: str
    invertido_centavos: int
    precio: str | None
    valor_centavos: int | None
    no_realizado_centavos: int | None


class OperacionInversion(BaseModel):
    id: int
    fecha: date
    activo: str
    tipo_activo: str
    lado: str
    cantidad: str
    precio: str
    comision_centavos: int
    resultado_centavos: int | None  # Solo las ventas: la ganancia o pérdida realizada.
    abierta: bool  # Una compra de un activo que todavía se tiene.


class Inversiones(BaseModel):
    mes: str
    cartera_centavos: int
    invertido_centavos: int
    no_realizado_centavos: int
    realizado_mes_centavos: int
    comisiones_mes_centavos: int
    operaciones_mes: int
    sin_precio: list[str]
    precios_al: datetime | None
    avisos: list[str]
    posiciones: list[PosicionInversion]
    operaciones: list[OperacionInversion]


class PreciosActualizados(BaseModel):
    actualizados: int
    errores: list[str]


# Movimientos y categorías.


class MovimientoDelMes(BaseModel):
    id: int
    fecha: date
    descripcion: str
    fuente: str
    tipo: str
    categoria: str | None
    categoria_manual: bool
    plan_concepto: str | None
    monto_centavos: int
    moneda: str
    usd_centavos: int | None
    cuota: str | None
    medio: str | None


class MovimientosDelMes(BaseModel):
    mes: str
    entro_centavos: int  # Ingresos en pesos.
    salio_centavos: int  # Gastos en pesos: consumos, cuotas e impuestos.
    movimientos: list[MovimientoDelMes]


class CategoriaElegida(BaseModel):
    categoria: str | None  # Sin categoría: vuelve a la automática.


class CategoriaDetalle(BaseModel):
    nombre: str
    movimientos: int
    reglas: int
    en_plan: int


class Renombre(BaseModel):
    de: str
    a: str


class Renombrada(BaseModel):
    movimientos: int


class ReglaDetalle(BaseModel):
    id: int
    texto: str
    categoria: str


class ReglaEditada(BaseModel):
    texto: str
    categoria: str
