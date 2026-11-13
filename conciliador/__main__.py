"""Comandos: python -m conciliador importar [carpeta] | revisar | migrar | gasto | pago | manuales | borrar | reporte"""
import argparse
import os
from datetime import date
from pathlib import Path

from conciliador import base, manual, reporte
from conciliador.importar import actualizar_cotizaciones, importar_carpeta
from conciliador.revisar import revisar


def clave_nacion(ruta_env: Path = Path(".env")) -> str:
    """La clave del PDF de Nación se lee de .env y nunca se muestra."""
    if "BNA_PDF_CLAVE" in os.environ:
        return os.environ["BNA_PDF_CLAVE"]
    if ruta_env.exists():
        for linea in ruta_env.read_text(encoding="utf-8").splitlines():
            if linea.startswith("BNA_PDF_CLAVE="):
                return linea.split("=", 1)[1]
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(prog="conciliador")
    comandos = parser.add_subparsers(dest="comando", required=True)
    importar = comandos.add_parser("importar", help="importa los archivos de una carpeta")
    importar.add_argument("carpeta", nargs="?", type=Path, default=Path("entrada"))
    comandos.add_parser("revisar", help="categoriza los gastos grandes sin regla")
    comandos.add_parser("migrar", help="respalda la base y la actualiza")
    gasto = comandos.add_parser("gasto", help="registra un gasto que no viene en un PDF")
    gasto.add_argument("monto", help="por ejemplo 15000 o 1.234,56")
    gasto.add_argument("descripcion", help="se cruza con las reglas y el plan, como un PDF")
    gasto.add_argument("--fecha", default=date.today().isoformat())
    gasto.add_argument("--usd", action="store_true", help="el monto está en dólares")
    gasto.add_argument("--medio", choices=manual.MEDIOS, default="efectivo")
    pago = comandos.add_parser("pago", help="avisa que pagaste un resumen de tarjeta")
    pago.add_argument("tarjeta", choices=manual.TARJETAS)
    pago.add_argument("monto")
    pago.add_argument("--fecha", default=date.today().isoformat())
    pago.add_argument("--usd", action="store_true", help="la parte del resumen pagada en dólares")
    comandos.add_parser("manuales", help="lista los últimos gastos y pagos cargados a mano")
    borrar = comandos.add_parser("borrar", help="borra un gasto o pago cargado a mano")
    borrar.add_argument("id", type=int, help="el número que muestra `manuales`")
    del_mes = comandos.add_parser("reporte", help="el reporte del mes")
    del_mes.add_argument("mes", help="por ejemplo 2026-11")
    argumentos = parser.parse_args()

    ruta = Path(os.environ.get("CONCILIADOR_DB", "conciliador.db"))
    if argumentos.comando == "migrar":
        respaldo = base.migrar(ruta)
        print(f"Base actualizada. Respaldo: {respaldo}" if respaldo else "La base ya estaba al día.")
        return
    try:
        motor = base.conectar(ruta)
    except base.BaseDesactualizada as error:
        raise SystemExit(str(error))
    if argumentos.comando == "revisar":
        revisar(motor)
        return
    try:
        if argumentos.comando == "gasto":
            manual.registrar_gasto(
                motor,
                argumentos.monto,
                argumentos.descripcion,
                manual.leer_fecha(argumentos.fecha),
                "USD" if argumentos.usd else "ARS",
                argumentos.medio,
            )
            return
        if argumentos.comando == "reporte":
            print(reporte.texto(reporte.armar(motor, argumentos.mes)))
            return
        if argumentos.comando == "manuales":
            manual.listar(motor)
            return
        if argumentos.comando == "borrar":
            manual.borrar(motor, argumentos.id)
            return
        if argumentos.comando == "pago":
            manual.registrar_pago(
                motor,
                argumentos.tarjeta,
                argumentos.monto,
                manual.leer_fecha(argumentos.fecha),
                "USD" if argumentos.usd else "ARS",
            )
            return
    except ValueError as error:
        raise SystemExit(f"Error: {error}")

    for informe in importar_carpeta(argumentos.carpeta, motor, clave_nacion()):
        if not informe.reconocido:
            print(f"{informe.archivo}: no reconocido o con clave incorrecta, no se importó")
            continue
        print(
            f"{informe.archivo}: {informe.nuevas} nuevas, {informe.repetidas} repetidas, "
            f"{len(informe.errores)} con error"
        )
        for detalle in [*informe.errores, *informe.problemas]:
            print(f"  AVISO: {detalle}")
    aviso = actualizar_cotizaciones(motor)
    if aviso:
        print(f"AVISO: {aviso}")
    print(f"Gastos para revisar: {len(base.pendientes(motor))}")
    print(f"Movimientos sin USD: {base.contar_sin_usd(motor)}")


if __name__ == "__main__":
    main()
