"""Comando para categorizar los gastos grandes sin regla."""
import re
from collections.abc import Callable

from conciliador import base
from conciliador.manual import importe

PREFIJO = re.compile(r"^(Transferencia enviada|Pago de servicio|Pago con QR|Pago)\s+")


def texto_sugerido(descripcion: str) -> str:
    """Saca el comienzo genérico: una regla 'Transferencia enviada' categorizaría de más."""
    return PREFIJO.sub("", descripcion).strip()


def revisar(
    motor: base.Engine,
    preguntar: Callable[[str], str] = input,
    mostrar: Callable[[str], None] = print,
) -> None:
    salteados: set[int] = set()
    while True:
        lista = [p for p in base.pendientes(motor) if p.id not in salteados]
        if not lista:
            mostrar("No quedan gastos para revisar.")
            return

        gasto = lista[0]
        monto = ("-" if gasto.monto_centavos < 0 else "") + importe(gasto.monto_centavos)
        mostrar(f"{gasto.fecha:%d/%m/%Y}  {gasto.moneda} {monto}  {gasto.descripcion}")
        categoria = preguntar("Categoría, 'cambio' si no es un gasto, o Enter para saltear: ").strip()
        if not categoria:
            salteados.add(gasto.id)
            continue
        if categoria.lower() == "cambio":
            base.marcar_cambio(motor, gasto.id)
            mostrar("Marcado como cambio: no suma como gasto.")
            continue

        sugerido = texto_sugerido(gasto.descripcion)
        respuesta = preguntar(f"Texto de la regla [{sugerido}], o 'no' para no guardarla: ").strip()
        texto = None if respuesta.lower() == "no" else respuesta or sugerido
        base.resolver_pendiente(motor, gasto.id, categoria, texto)
