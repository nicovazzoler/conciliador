"""Dólar oficial: lo trae de internet y lo aplica a los movimientos."""
import bisect
import json
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from urllib.request import Request, urlopen

ORIGEN = "argentinadatos"
URL = "https://api.argentinadatos.com/v1/cotizaciones/dolares/oficial"


@dataclass(frozen=True)
class CotizacionLeida:
    fecha: date
    compra_centavos: int
    venta_centavos: int


def traer() -> list[CotizacionLeida]:
    pedido = Request(URL, headers={"User-Agent": "conciliador"})
    with urlopen(pedido, timeout=20) as respuesta:
        return parsear(json.load(respuesta))


def parsear(datos: list[dict]) -> list[CotizacionLeida]:
    return [
        CotizacionLeida(
            fecha=date.fromisoformat(fila["fecha"]),
            compra_centavos=int(Decimal(str(fila["compra"])) * 100),
            venta_centavos=int(Decimal(str(fila["venta"])) * 100),
        )
        for fila in datos
    ]


def elegir(guardadas: list[tuple[date, int]], fecha: date) -> int | None:
    """Usa la cotización de ese día o la última anterior, como en un fin de semana o feriado.

    Una fecha posterior a la última publicada queda sin cotización: nunca se inventa.
    """
    if not guardadas or fecha > guardadas[-1][0]:
        return None
    indice = bisect.bisect_right(guardadas, fecha, key=lambda fila: fila[0]) - 1
    return guardadas[indice][1] if indice >= 0 else None


def a_usd(monto_centavos: int, moneda: str, cotizacion_centavos: int) -> int:
    if moneda == "USD":
        return monto_centavos
    usd = Decimal(monto_centavos) * 100 / cotizacion_centavos
    return int(usd.quantize(Decimal(1), rounding=ROUND_HALF_UP))
