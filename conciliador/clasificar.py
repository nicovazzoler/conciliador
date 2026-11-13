"""Reglas de negocio sin base de datos: qué es cada movimiento y en qué categoría va."""
import re
import unicodedata

SIN_REGLA = "Gastos varios"
GASTO_GRANDE_CENTAVOS = 5_000_000
TOPE_DIARIO_CENTAVOS = 20_000_000  # $200.000 por día; el reporte lo pasa como :tope.
TIPOS_DE_GASTO = ("consumo", "cuota", "impuesto")

TRANSFERENCIA = re.compile(r"^Transferencia (?:enviada|recibida) (.+)$")
DEVOLUCION = re.compile(r"devoluci|reembolso", re.IGNORECASE)


def normalizar(texto: str) -> str:
    """Compara sin distinguir mayúsculas, acentos ni espacios de más."""
    sin_acentos = unicodedata.normalize("NFKD", texto)
    limpio = "".join(c for c in sin_acentos if not unicodedata.combining(c) and c != "'")
    return " ".join(limpio.casefold().split())


def coincide(buscado: str, descripcion: str) -> bool:
    """Busca desde el inicio de una palabra: 'CIO' no coincide con 'servicio'.

    No exige el final, porque los bancos pegan palabras, como en 'TiendaPremium'.
    """
    patron = rf"(?<!\w){re.escape(normalizar(buscado))}"
    return re.search(patron, normalizar(descripcion)) is not None


def es_titular(nombre: str, titular: str) -> bool:
    """El orden de los nombres cambia según el banco. El apellido solo no alcanza."""
    return sorted(normalizar(nombre).split()) == sorted(normalizar(titular).split())


def tipo_mercado_pago(descripcion: str, monto_centavos: int, titular: str) -> str:
    transferencia = TRANSFERENCIA.match(descripcion)
    if descripcion.startswith("Ingreso de dinero"):
        return "transferencia_propia"
    if transferencia and es_titular(transferencia[1], titular):
        return "transferencia_propia"
    if DEVOLUCION.search(descripcion):
        return "devolucion"
    return "ingreso" if monto_centavos > 0 else "consumo"


def categoria_por_regla(descripcion: str, reglas: list[tuple[str, str]]) -> str | None:
    """Si coinciden varias reglas de texto, gana la más larga, que es la más específica."""
    coincidencias = [r for r in reglas if coincide(r[0], descripcion)]
    if not coincidencias:
        return None
    return max(coincidencias, key=lambda r: len(normalizar(r[0])))[1]


def ultimo_mes_de_cuota(primer_mes: str, cantidad: int) -> str:
    anio, mes = map(int, primer_mes.split("-"))
    total = anio * 12 + (mes - 1) + cantidad - 1
    return f"{total // 12}-{total % 12 + 1:02d}"


def candidatos(gasto, fijos, cuotas) -> list:
    """Fijos con el mismo texto, y cuotas con el mismo texto vigentes en el mes del gasto."""
    return [f for f in fijos if coincide(f.texto, gasto.descripcion)] + [
        c
        for c in cuotas
        if coincide(c.texto, gasto.descripcion)
        and c.primer_mes <= gasto.mes <= ultimo_mes_de_cuota(c.primer_mes, c.cantidad)
    ]


def del_plan(gasto, fijos, cuotas) -> str | None:
    """Concepto del plan al que corresponde el gasto: primero la misma moneda, después el monto
    más cercano. Varios gastos pueden ir al mismo concepto: así un pago doble se ve en el reporte."""
    opciones = candidatos(gasto, fijos, cuotas)
    if not opciones:
        return None
    elegido = min(
        opciones,
        key=lambda p: (p.moneda != gasto.moneda, abs(-gasto.monto_centavos - p.monto_centavos)),
    )
    return elegido.concepto


def en_pesos(gasto) -> int | None:
    """Los dólares se comparan contra el umbral en pesos. Sin cotización no se sabe."""
    if gasto.moneda == "ARS":
        return gasto.monto_centavos
    if gasto.cotizacion_centavos is None:
        return None
    return gasto.monto_centavos * gasto.cotizacion_centavos // 100


def decidir(gasto, reglas, fijos, cuotas) -> tuple[str, bool]:
    """Devuelve (categoría, queda para revisar)."""
    categoria = categoria_por_regla(gasto.descripcion, reglas)
    if categoria is not None:
        return categoria, False
    pesos = en_pesos(gasto)
    if pesos is None or -pesos < GASTO_GRANDE_CENTAVOS:
        return SIN_REGLA, False
    return SIN_REGLA, del_plan(gasto, fijos, cuotas) is None
