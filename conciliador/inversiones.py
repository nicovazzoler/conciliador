"""Posiciones y ganancias de las inversiones, con precio promedio. Todo en USD y con Decimal.

Las cantidades y los precios no son centavos: 0,0412 BTC a U$D 94.120,55 no entra en un entero.
Se calcula con Decimal y se redondea a centavos solo al final, para mostrar.
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TIPOS_ACTIVO = ("cripto", "accion")
LADOS = ("compra", "venta")


@dataclass(frozen=True)
class Operacion:
    id: int
    fecha_hora: datetime
    activo: str
    tipo_activo: str
    lado: str
    cantidad: Decimal
    precio: Decimal  # USD por unidad.
    comision: Decimal  # USD.
    fuente: str = "manual"


@dataclass
class Posicion:
    activo: str
    tipo_activo: str
    cantidad: Decimal = Decimal(0)
    costo: Decimal = Decimal(0)  # Lo invertido en lo que todavía se tiene, comisiones incluidas.
    precio: Decimal | None = None

    @property
    def costo_promedio(self) -> Decimal:
        return self.costo / self.cantidad if self.cantidad else Decimal(0)

    @property
    def valor(self) -> Decimal | None:
        return None if self.precio is None else self.cantidad * self.precio

    @property
    def no_realizado(self) -> Decimal | None:
        return None if self.valor is None else self.valor - self.costo


@dataclass
class Resultado:
    posiciones: list[Posicion]
    realizado: dict[int, Decimal]  # Ganancia de cada venta, por id de operación.
    avisos: list[str] = field(default_factory=list)


def calcular(operaciones: list[Operacion], precios: dict[str, Decimal]) -> Resultado:
    """Recorre las operaciones en orden. Una venta gana contra el costo promedio de lo que se tenía."""
    posiciones: dict[str, Posicion] = {}
    realizado: dict[int, Decimal] = {}
    avisos: list[str] = []
    for op in sorted(operaciones, key=lambda o: (o.fecha_hora, o.id)):
        pos = posiciones.setdefault(op.activo, Posicion(op.activo, op.tipo_activo))
        if op.lado == "compra":
            pos.cantidad += op.cantidad
            pos.costo += op.cantidad * op.precio + op.comision
            continue
        vendido = op.cantidad
        if vendido > pos.cantidad:
            # Vender más de lo que había: falta cargar una compra, o es una posición en corto.
            avisos.append(
                f"{op.activo}: el {op.fecha_hora:%d/%m/%Y} se vendió {formato(op.cantidad)} y había "
                f"{formato(pos.cantidad)}. Falta alguna compra; la ganancia de esa venta no es confiable."
            )
            vendido = pos.cantidad
        costo_vendido = vendido * pos.costo_promedio
        realizado[op.id] = op.cantidad * op.precio - op.comision - costo_vendido
        pos.costo -= costo_vendido
        pos.cantidad -= vendido
    abiertas = [p for p in posiciones.values() if p.cantidad > 0]
    for p in abiertas:
        p.precio = precios.get(p.activo)
    return Resultado(sorted(abiertas, key=lambda p: -(p.valor or p.costo)), realizado, avisos)


def a_centavos(valor: Decimal | None) -> int | None:
    if valor is None:
        return None
    return int((valor * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def decimal_desde(texto: str, que: str) -> Decimal:
    """Acepta 0,0412 o 0.0412, y 94.120,55 o 94120.55. Nunca pasa por float."""
    limpio = texto.strip().replace(" ", "")
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpio):
        limpio = limpio.replace(".", "")  # 90.000 es noventa mil, como se escribe acá.
    try:
        valor = Decimal(limpio)
    except InvalidOperation:
        raise ValueError(f"{que} inválido: {texto!r}")
    if not valor.is_finite() or valor < 0:
        raise ValueError(f"{que} inválido: {texto!r}")
    return valor


def formato(valor: Decimal) -> str:
    """Decimal sin ceros de más: 0.04120000 → '0.0412'."""
    texto = format(valor.normalize(), "f")
    return texto


def por_mes(operaciones: list[Operacion]) -> dict[str, list[Operacion]]:
    meses: dict[str, list[Operacion]] = defaultdict(list)
    for op in operaciones:
        meses[op.fecha_hora.strftime("%Y-%m")].append(op)
    return meses
