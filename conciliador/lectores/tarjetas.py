"""Lo que comparten los lectores de resúmenes de tarjeta."""
import re
from dataclasses import dataclass, field
from datetime import date

from conciliador.lectores import FilaLeida

PERCEPCION = re.compile(r"RG\.? ?5617")


@dataclass
class ResumenTarjeta:
    fuente: str
    numero: str
    cierre: date
    vencimiento: date
    total_pesos: int
    total_dolares: int
    saldo_anterior_pesos: int
    saldo_anterior_dolares: int
    filas: list[FilaLeida] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def percepcion(self) -> int:
        """Percepción cobrada en este resumen. Si se paga en dólares, se devuelve en el siguiente."""
        return sum(
            f.monto_centavos
            for f in self.filas
            if f.tipo == "percepcion" and f.moneda == "ARS" and f.monto_centavos > 0
        )


def verificar(resumen: ResumenTarjeta) -> list[str]:
    """El saldo anterior más todas las filas tiene que dar el total del resumen."""
    problemas = []
    controles = (
        ("ARS", resumen.saldo_anterior_pesos, resumen.total_pesos),
        ("USD", resumen.saldo_anterior_dolares, resumen.total_dolares),
    )
    for moneda, saldo_anterior, total in controles:
        suma = sum(f.monto_centavos for f in resumen.filas if f.moneda == moneda)
        if saldo_anterior + suma != total:
            problemas.append(f"las filas en {moneda} no coinciden con el total del resumen")
    return problemas


def clave_detalle(comprobante: str, cuota: str | None, fecha: date) -> str:
    """El comprobante se repite en cada cuota y entre comercios, por eso no alcanza solo."""
    return f"{comprobante}|{cuota or '-'}|{fecha.isoformat()}"


def clave_cargo(numero_resumen: str, indice: int, concepto: str) -> str:
    """Los impuestos y pagos no traen comprobante. El índice separa dos filas iguales."""
    return f"{numero_resumen}|{indice}|{concepto}"[:80]


def tipo_de_cargo(concepto: str) -> str:
    if concepto.startswith("SU PAGO"):
        return "pago"
    if PERCEPCION.search(concepto):
        return "percepcion"
    return "impuesto"


def tipo_de_consumo(monto_centavos: int, es_cuota: bool) -> str:
    if monto_centavos < 0:
        return "devolucion"
    return "cuota" if es_cuota else "consumo"


def mes_de(fecha: date) -> str:
    return fecha.strftime("%Y-%m")


def limite_entre_columnas(pagina, top: float, izquierda: str, derecha: str) -> float:
    """Un importe solo no dice su moneda: la da la columna en la que está."""
    bordes = {p["text"]: p["x1"] for p in pagina.extract_words() if abs(p["top"] - top) < 3}
    return (bordes[izquierda] + bordes[derecha]) / 2
