"""Lectores de cada fuente. Todos devuelven filas en el mismo formato."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class FilaLeida:
    numero_operacion: str
    fecha: date
    descripcion: str
    monto_centavos: int
    moneda: str = "ARS"
    tipo: str = "sin_clasificar"
    mes: str | None = None  # Mes en que cuenta. Si falta, es el de la fecha.
    cuota: str | None = None
    fecha_cotizacion: date | None = None  # Si falta, es la fecha del movimiento.


def a_centavos(texto: str) -> int:
    """Convierte '-1.234,56' en -123456, sin pasar por float."""
    return int(Decimal(texto.replace(".", "").replace(",", ".")) * 100)
