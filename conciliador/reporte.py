"""El reporte del mes: `armar` junta los datos y `texto` los presenta. La API usa `armar`."""
import re
from dataclasses import dataclass

from conciliador import base, clasificar
from conciliador.manual import importe

MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
SIN_AVISO = ("bien", "sin datos")
NOMBRES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


@dataclass
class Reporte:
    mes: str
    totales: dict
    categorias: list[dict]
    fijos: list[dict]
    cuotas: list[dict]
    dias_sobre_tope: list[dict]
    resumenes: list[dict]
    pendientes: int
    importado: dict


def armar(motor: base.Engine, mes: str) -> Reporte:
    """Corre todas las consultas del mes. El mes llega como parámetro, nunca pegado al SQL."""
    if not MES.match(mes):
        raise ValueError(f"mes inválido: {mes!r}. Usá AAAA-MM, por ejemplo 2026-11")
    (totales,) = base.consultar(motor, "totales", mes=mes)
    return Reporte(
        mes=mes,
        totales=totales,
        categorias=base.consultar(motor, "categorias", mes=mes),
        fijos=base.consultar(motor, "fijos", mes=mes),
        cuotas=base.consultar(motor, "cuotas", mes=mes),
        dias_sobre_tope=base.consultar(
            motor, "tope", mes=mes, tope=clasificar.TOPE_DIARIO_CENTAVOS
        ),
        resumenes=base.consultar(motor, "resumenes", mes=mes),
        pendientes=len(base.pendientes(motor)),
        importado=base.consultar(motor, "importado", mes=mes)[0],
    )


def texto(reporte: Reporte) -> str:
    """Solo presentación: no consulta nada. Lo que está bien no se muestra, para no tapar lo que no."""
    anio, mes = reporte.mes.split("-")
    t = reporte.totales
    importado = reporte.importado
    lineas = [
        f"{NOMBRES[int(mes) - 1].upper()} {anio}",
        "Importado: Mercado Pago "
        + ("sí" if importado["mercado_pago"] else "no (los fijos no se controlan)")
        + "; resúmenes que vencen este mes: "
        + (importado["resumenes"] or "ninguno (las cuotas no se controlan)"),
        f"Gastado: $ {importe(t['pesos_centavos'])} en pesos y U$D {importe(t['dolares_centavos'])} "
        f"en dólares; en total, U$D {importe(t['total_usd_centavos'])}",
    ]

    lineas += _seccion("Por categoría (USD)", [
        f"{c['categoria']:<30} {importe(c['total_usd_centavos'] or 0):>10}  "
        f"{f'{c['porcentaje'] or 0:.1f}'.replace('.', ','):>5}%"
        for c in reporte.categorias
    ])
    lineas += _seccion("Fijos", [
        f"{f['estado']:<12} {f['concepto']:<30} anotado {_plata(f['anotado_centavos'], f['moneda'])}"
        + (f"   cobrado {_plata(f['cobrado_centavos'], f['moneda'])} ({_pagos(f['pagos'])})"
           if f["pagos"] else "")
        for f in reporte.fijos
        if f["estado"] not in SIN_AVISO
    ])
    lineas += _seccion("Cuotas", [
        f"{c['estado']:<12} {c['concepto']:<40} {c['esperada'] or c['llegaron'] or '':>6}  "
        f"{importe(c['monto_centavos'])}"
        for c in reporte.cuotas
        if c["estado"] not in SIN_AVISO
    ])
    tope = importe(clasificar.TOPE_DIARIO_CENTAVOS).split(",")[0]
    lineas += _seccion(f"Días sobre el tope de $ {tope}", [
        f"{d['fecha'][8:10]}/{d['fecha'][5:7]}   $ {importe(d['pesos_centavos']):>12}   {d['movimientos']} gastos"
        for d in reporte.dias_sobre_tope
    ])
    lineas += _seccion("Resúmenes de tarjeta", [
        f"{r['estado']:<15} {r['tarjeta']:<15} vence {r['vencimiento'][8:10]}/{r['vencimiento'][5:7]}"
        + (f"   falta $ {importe(r['falta_pesos'])} y U$D {importe(r['falta_usd'])}"
           if r["falta_pesos"] or r["falta_usd"] else "")
        for r in reporte.resumenes
    ])
    lineas += ["", f"Avisos: {reporte.pendientes} gastos para revisar, {t['sin_usd']} movimientos sin USD"]
    return "\n".join(lineas)


def _plata(centavos: int, moneda: str) -> str:
    return f"{'U$D' if moneda == 'USD' else '$'} {importe(centavos)}"


def _pagos(cantidad: int) -> str:
    return f"{cantidad} pago" if cantidad == 1 else f"{cantidad} pagos"


def _seccion(titulo: str, filas: list[str]) -> list[str]:
    return ["", titulo, *(f"  {f}" for f in filas or ["(nada que avisar)"])]
