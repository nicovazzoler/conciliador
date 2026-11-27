"""Comandos: python -m conciliador importar [carpeta] | revisar | migrar | gasto | pago | manuales | borrar | reporte | web | mp-probar"""
import argparse
import os
from datetime import date
from pathlib import Path

from conciliador import base, manual, reporte
from conciliador.importar import actualizar_cotizaciones, importar_carpeta
from conciliador.revisar import revisar

# La carpeta del proyecto: la base, entrada/ y .env se buscan acá aunque el comando se corra desde otra.
RAIZ = Path(__file__).resolve().parent.parent


def leer_clave(nombre: str, ruta_env: Path = RAIZ / ".env") -> str:
    """Las claves se leen del entorno o de .env y nunca se muestran."""
    if nombre in os.environ:
        return os.environ[nombre]
    if ruta_env.exists():
        for linea in ruta_env.read_text(encoding="utf-8").splitlines():
            if linea.startswith(f"{nombre}="):
                return linea.split("=", 1)[1].strip()
    return ""


def clave_nacion(ruta_env: Path = RAIZ / ".env") -> str:
    """La clave del PDF de Nación."""
    return leer_clave("BNA_PDF_CLAVE", ruta_env)


def probar_mercado_pago(dias: int, guardar: bool, ruta: Path) -> None:
    """Solo lee: no escribe en la base ni cambia nada en la cuenta de Mercado Pago."""
    import json

    from conciliador import mercado_pago_api

    token = leer_clave("MP_ACCESS_TOKEN")
    if not token:
        raise SystemExit(
            "Falta MP_ACCESS_TOKEN en .env. Está en Tus integraciones → tu aplicación → "
            "Credenciales de producción → Access token."
        )
    if token.startswith("TEST-"):
        print("AVISO: es un token de prueba. Con él no aparecen tus movimientos reales.\n")
    try:
        cuenta, pagos, crudos = mercado_pago_api.pagos_recientes(mercado_pago_api.pedidor(token), dias)
    except (mercado_pago_api.ErrorMP, ValueError) as error:
        raise SystemExit(f"Error: {error}")
    en_base = None
    if ruta.exists():  # Solo se cruza con una base que ya existe: conectar crearía una vacía.
        try:
            en_base = base.numeros_de_operacion(base.conectar(ruta), "mercado_pago")
        except base.BaseDesactualizada:
            print("AVISO: la base está desactualizada, no se cruza con lo importado. Corré `migrar`.\n")
    print(mercado_pago_api.texto(cuenta, pagos, dias, en_base))
    if guardar:
        destino = RAIZ / "entrada" / f"mp-pagos-{date.today():%Y%m%d}.json"
        destino.parent.mkdir(exist_ok=True)
        destino.write_text(json.dumps(crudos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"\nRespuestas crudas en {destino}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="conciliador")
    comandos = parser.add_subparsers(dest="comando", required=True)
    importar = comandos.add_parser("importar", help="importa los archivos de una carpeta")
    importar.add_argument("carpeta", nargs="?", type=Path, default=RAIZ / "entrada")
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
    comandos.add_parser("web", help="levanta la app web en http://127.0.0.1:8000")
    comandos.add_parser("openapi", help="imprime el esquema de la API, para los tipos del front")
    probar = comandos.add_parser("mp-probar", help="lista lo que la API de Mercado Pago ve de tu cuenta (solo lee)")
    probar.add_argument("--dias", type=int, default=1, help="cuántos días para atrás, de 1 a 364 (por defecto 1)")
    probar.add_argument("--guardar", action="store_true", help="guarda las respuestas crudas en entrada/")
    argumentos = parser.parse_args()

    if argumentos.comando == "openapi":
        import json

        from conciliador import api

        print(json.dumps(api.esquema_openapi(), ensure_ascii=False, indent=2))
        return

    ruta = Path(os.environ.get("CONCILIADOR_DB", RAIZ / "conciliador.db"))
    if argumentos.comando == "mp-probar":
        probar_mercado_pago(argumentos.dias, argumentos.guardar, ruta)
        return
    if argumentos.comando == "migrar":
        respaldo = base.migrar(ruta)
        print(f"Base actualizada. Respaldo: {respaldo}" if respaldo else "La base ya estaba al día.")
        return
    if argumentos.comando == "web":
        from conciliador import api  # Solo acá: el resto de los comandos no necesita FastAPI.

        try:
            api.servir(ruta, RAIZ / "entrada", clave_nacion(), leer_clave("ANTHROPIC_API_KEY"))
        except base.BaseDesactualizada as error:
            raise SystemExit(str(error))
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
