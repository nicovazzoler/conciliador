"""Gastos y pagos de tarjeta que no vienen en un PDF. Acá se valida y se pregunta; guarda base.py."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from uuid import uuid4

from conciliador import base, plan
from conciliador.lectores import FilaLeida

MEDIOS = ("efectivo", "debito", "transferencia")
TARJETAS = ("tarjeta_comafi", "tarjeta_nacion")


def importe(centavos: int) -> str:
    """-12345678 → '123.456,78'."""
    return f"{abs(centavos) / 100:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def leer_fecha(texto: str, hoy: date | None = None) -> date:
    """Acepta 2026-10-28 o 28/10/2026. Una fecha futura es un error de tipeo."""
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            fecha = datetime.strptime(texto.strip(), formato).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"fecha inválida: {texto!r}. Usá 2026-10-28 o 28/10/2026")
    if fecha > (hoy or date.today()):
        raise ValueError(f"la fecha {fecha:%d/%m/%Y} es futura")
    return fecha


def leer_monto(texto: str) -> int:
    """Los mismos formatos que plan.csv, y mayor que 0."""
    centavos = plan.monto_a_centavos(texto)
    if centavos <= 0:
        raise ValueError("el monto tiene que ser mayor que 0")
    return centavos


@dataclass(frozen=True)
class Aviso:
    """Algo que hay que confirmar antes de guardar. El mensaje es el mismo en la terminal y en la web."""

    codigo: str  # "igual_al_anterior", "lejos_de_lo_previsto" o "grande_sin_anticipar"
    mensaje: str


def preparar_gasto(
    monto: str, descripcion: str, fecha: date, moneda: str = "ARS", medio: str = "efectivo"
) -> FilaLeida:
    """Valida y arma la fila. No toca la base."""
    descripcion = descripcion.strip()
    if not descripcion:
        raise ValueError("la descripción no puede estar vacía")
    if medio not in MEDIOS:
        raise ValueError(f"medio inválido: {medio!r}. Opciones: {', '.join(MEDIOS)}")
    if moneda not in ("ARS", "USD"):
        raise ValueError(f"moneda inválida: {moneda!r}")
    return FilaLeida(uuid4().hex, fecha, descripcion, -leer_monto(monto), moneda, tipo="consumo")


def evaluar_gasto(motor: base.Engine, fila: FilaLeida) -> list[Aviso]:
    """Lo que hay que confirmar antes de guardar. No pregunta nada: eso lo decide quien llama."""
    avisos = []
    monto = f"{fila.moneda} {importe(fila.monto_centavos)}"

    # No es detección de repetidos: es un "¿seguro?" por si el mismo gasto se mandó dos veces.
    if base.ultimo_manual(motor) == (fila.fecha, fila.monto_centavos, fila.descripcion):
        avisos.append(Aviso("igual_al_anterior", "Es igual al último gasto que cargaste."))

    evaluacion = base.evaluar(motor, fila)
    if _lejos_de_lo_previsto(fila, evaluacion.previsto):
        concepto, previsto, _ = evaluacion.previsto
        avisos.append(Aviso(
            "lejos_de_lo_previsto",
            f"{concepto} está anotado en {fila.moneda} {importe(previsto)}, y cargaste {importe(fila.monto_centavos)}.",
        ))
    if evaluacion.grande_sin_anticipar:
        avisos.append(Aviso("grande_sin_anticipar", f"{monto} es un gasto grande sin anticipar."))
    return avisos


def guardar_gasto(
    motor: base.Engine, fila: FilaLeida, medio: str, categoria: str | None = None
) -> tuple[str | None, str | None]:
    """Guarda sin preguntar. Devuelve (categoría, concepto del plan)."""
    return base.guardar_manual(motor, fila, medio=medio, categoria=categoria)


def registrar_gasto(
    motor: base.Engine,
    monto: str,
    descripcion: str,
    fecha: date,
    moneda: str = "ARS",
    medio: str = "efectivo",
    preguntar: Callable[[str], str] = input,
    mostrar: Callable[[str], None] = print,
) -> bool:
    """La versión de la terminal: pregunta por cada aviso. Devuelve si se guardó."""
    fila = preparar_gasto(monto, descripcion, fecha, moneda, medio)
    avisos = evaluar_gasto(motor, fila)
    for aviso in avisos:
        if not _si(preguntar(f"{aviso.mensaje} ¿Lo guardo igual? [s/N]: ")):
            mostrar("No se guardó.")
            return False

    categoria = None
    if any(a.codigo == "grande_sin_anticipar" for a in avisos):
        categoria = preguntar("Categoría (Enter para dejarlo en revisar): ").strip() or None

    categoria, del_plan = guardar_gasto(motor, fila, medio, categoria)
    detalle = f"fijo o cuota: {del_plan}" if del_plan else (categoria or "para revisar")
    mostrar(
        f"Guardado: {fecha:%d/%m/%Y}  {moneda} {importe(fila.monto_centavos)}  {fila.descripcion}  ({detalle})"
    )
    return True


def registrar_pago(
    motor: base.Engine,
    tarjeta: str,
    monto: str,
    fecha: date,
    moneda: str = "ARS",
    mostrar: Callable[[str], None] = print,
) -> None:
    """El aviso de que pagaste un resumen. Sale plata del banco, pero no es un gasto nuevo."""
    if tarjeta not in TARJETAS:
        raise ValueError(f"tarjeta inválida: {tarjeta!r}. Opciones: {', '.join(TARJETAS)}")
    fila = FilaLeida(uuid4().hex, fecha, f"Pago {tarjeta}", -leer_monto(monto), moneda, tipo="pago_tarjeta")
    base.guardar_manual(motor, fila, tarjeta=tarjeta)
    mostrar(f"Guardado: pago de {tarjeta} por {moneda} {importe(fila.monto_centavos)}. No suma como gasto.")


def describir(movimiento: dict) -> str:
    detalle = movimiento["tarjeta"] or movimiento["plan_concepto"] or movimiento["categoria"] or ""
    return (
        f"{movimiento['id']:>5}  {movimiento['fecha']:%d/%m/%Y}  {movimiento['moneda']} "
        f"{importe(movimiento['monto_centavos']):>12}  {movimiento['descripcion']}"
        + (f"  ({detalle})" if detalle else "")
    )


def listar(motor: base.Engine, mostrar: Callable[[str], None] = print) -> None:
    movimientos = base.manuales(motor)
    if not movimientos:
        mostrar("No hay nada cargado a mano.")
    for movimiento in movimientos:
        mostrar(describir(movimiento))


def borrar(
    motor: base.Engine,
    movimiento_id: int,
    preguntar: Callable[[str], str] = input,
    mostrar: Callable[[str], None] = print,
) -> bool:
    """Devuelve si se borró. Solo lo cargado a mano: lo de un PDF se corrige reimportando."""
    movimiento = base.manual(motor, movimiento_id)
    if movimiento is None:
        raise ValueError(f"no hay un gasto o pago cargado a mano con el número {movimiento_id}")
    mostrar(describir(movimiento))
    if not _si(preguntar("¿Lo borro? [s/N]: ")):
        mostrar("No se borró.")
        return False
    base.borrar_manual(motor, movimiento_id)
    mostrar("Borrado.")
    return True


def _lejos_de_lo_previsto(fila: FilaLeida, previsto: tuple[str, int, str] | None) -> bool:
    """Más del doble o menos de la mitad de lo anotado: casi siempre es un dígito de más o de menos."""
    if previsto is None or previsto[2] != fila.moneda:
        return False
    monto = -fila.monto_centavos
    return monto > 2 * previsto[1] or 2 * monto < previsto[1]


def _si(respuesta: str) -> bool:
    return respuesta.strip().lower() in ("s", "si", "sí")
