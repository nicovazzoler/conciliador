"""Comando para categorizar los gastos grandes sin regla."""
import re
from collections import defaultdict
from collections.abc import Callable

from conciliador import base, clasificar
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


def agrupar_varios(motor: base.Engine) -> list[dict]:
    """"Gastos varios" agrupado por el texto que se sugeriría como regla, de mayor a menor monto.

    Una regla con ese texto categorizaría el grupo entero. Se agrupa también por moneda, porque
    sumar pesos con dólares no daría un total con sentido.
    """
    grupos: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for gasto in base.gastos_varios(motor):
        # Se agrupa como compara una regla, sin mayúsculas ni tildes: una sola regla cubre al grupo.
        clave = clasificar.normalizar(texto_sugerido(gasto["descripcion"]))
        grupos[(clave, gasto["moneda"])].append(gasto)
    resultado = [
        {
            "texto": texto_sugerido(gastos[0]["descripcion"]),
            "moneda": moneda,
            "movimientos": len(gastos),
            "total_centavos": -sum(g["monto_centavos"] for g in gastos),
            "ejemplo": gastos[0]["descripcion"],
            "plan_concepto": next((g["plan_concepto"] for g in gastos if g["plan_concepto"]), None),
            "fuentes": sorted({g["fuente"] for g in gastos}),
        }
        for (_, moneda), gastos in grupos.items()
    ]
    return sorted(resultado, key=lambda g: g["total_centavos"], reverse=True)
