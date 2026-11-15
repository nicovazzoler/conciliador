"""API HTTP. Solo traduce: cada endpoint llama a las mismas funciones que la terminal."""
import shutil
import tempfile
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from conciliador import base, cotizaciones, esquemas, importar, manual, plan, reporte, revisar

MAXIMO_ARCHIVO = 20 * 1024 * 1024  # 20 MB: un resumen pesa menos de 1.
MINIMO_REGLA = 3  # Una regla "Pa" alcanzaría a Pago, Pasaje, Panadería...

HOST = "127.0.0.1"  # Sin login: solo esta máquina puede entrar.
PUERTO = 8000
PAGINA = Path(__file__).parent.parent / "web" / "dist"


def crear_app(
    ruta_db: Path,
    entrada: Path = Path("entrada"),
    clave_nacion: str = "",
    traer_cotizaciones=cotizaciones.traer,
) -> FastAPI:
    """Una app por base: los tests usan una temporal y el comando `web`, la real.

    La clave del PDF de Nación la recibe el servidor al arrancar y nunca viaja a la página.
    """
    motor = base.conectar(ruta_db)  # Si la base está desactualizada, falla al arrancar.
    app = FastAPI(title="Conciliador")

    @app.get("/api/reporte/{mes}", response_model=esquemas.Reporte)
    def ver_reporte(mes: str):
        try:
            return asdict(reporte.armar(motor, mes))
        except ValueError as error:  # Un mes mal escrito es un error de quien llama.
            raise HTTPException(status_code=422, detail=str(error))

    @app.get("/api/historial/{mes}", response_model=list[esquemas.MesHistorial])
    def ver_historial(mes: str, meses: int = 6):
        try:
            return reporte.historial(motor, mes, meses)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))

    @app.post(
        "/api/gastos",
        status_code=201,
        response_model=esquemas.Guardado,
        responses={409: {"model": esquemas.Avisos, "description": "Hay avisos: falta confirmar"}},
    )
    def cargar_gasto(gasto: esquemas.GastoNuevo):
        try:
            fecha = manual.leer_fecha((gasto.fecha or date.today()).isoformat())
            fila = manual.preparar_gasto(gasto.monto, gasto.descripcion, fecha, gasto.moneda, gasto.medio)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        avisos = manual.evaluar_gasto(motor, fila)
        if avisos and not gasto.confirmado:
            return JSONResponse(
                status_code=409,
                content={"avisos": [{"codigo": a.codigo, "mensaje": a.mensaje} for a in avisos]},
            )
        movimiento_id, categoria, plan_concepto = manual.guardar_gasto(
            motor, fila, gasto.medio, gasto.categoria
        )
        return {"id": movimiento_id, "categoria": categoria, "plan_concepto": plan_concepto}

    @app.post("/api/pagos", status_code=201, response_model=esquemas.Guardado)
    def cargar_pago(pago: esquemas.PagoNuevo):
        try:
            fecha = manual.leer_fecha((pago.fecha or date.today()).isoformat())
            return {"id": manual.guardar_pago(motor, pago.tarjeta, pago.monto, fecha, pago.moneda)}
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))

    @app.get("/api/manuales", response_model=list[esquemas.Manual])
    def ver_manuales(cantidad: int = 10):
        return base.manuales(motor, cantidad)

    @app.delete("/api/manuales/{movimiento_id}", status_code=204)
    def borrar_manual(movimiento_id: int):
        if not base.borrar_manual(motor, movimiento_id):
            raise HTTPException(status_code=404, detail="no hay un gasto o pago cargado a mano con ese número")
        return Response(status_code=204)

    @app.get("/api/pendientes", response_model=list[esquemas.Pendiente])
    def ver_pendientes():
        return [
            {**vars(p), "sugerido": revisar.texto_sugerido(p.descripcion)} for p in base.pendientes(motor)
        ]

    @app.post("/api/pendientes/{movimiento_id}", status_code=204)
    def resolver(movimiento_id: int, resolucion: esquemas.Resolucion):
        if not base.es_pendiente(motor, movimiento_id):
            raise HTTPException(status_code=404, detail="ese movimiento no está para revisar")
        if resolucion.cambio:
            base.marcar_cambio(motor, movimiento_id)
            return Response(status_code=204)
        categoria = (resolucion.categoria or "").strip()
        if not categoria:
            raise HTTPException(status_code=422, detail="falta la categoría, o marcarlo como cambio")
        regla = (resolucion.regla or "").strip() or None
        if regla is not None and len(regla) < MINIMO_REGLA:
            raise HTTPException(status_code=422, detail=f"la regla necesita al menos {MINIMO_REGLA} letras")
        base.resolver_pendiente(motor, movimiento_id, categoria, regla)
        return Response(status_code=204)

    @app.get("/api/plan", response_model=esquemas.Plan)
    def ver_plan():
        return base.plan_con_ids(motor)

    @app.get("/api/plan.csv", response_class=PlainTextResponse)
    def exportar_plan():
        leido = base.leer_plan(motor)
        return PlainTextResponse(
            plan.a_csv(leido.fijos, leido.cuotas),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="plan.csv"'},
        )

    def _guardar(tabla: str, item_id: int | None, construir):
        try:
            item = construir()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        try:
            guardado = base.guardar_del_plan(motor, tabla, item, item_id)
        except base.ConceptoRepetido as error:
            raise HTTPException(status_code=409, detail=str(error))
        if guardado is None:
            raise HTTPException(status_code=404, detail="no existe en el plan")
        return {"id": guardado}

    def _fijo(e: esquemas.FijoEntrada):
        return lambda: plan.fijo_desde(e.concepto, e.texto, e.monto, e.moneda, e.dia, e.categoria)

    def _cuota(e: esquemas.CuotaEntrada):
        return lambda: plan.cuota_desde(e.concepto, e.texto, e.monto, e.moneda, e.cantidad, e.primer_mes, e.categoria)

    @app.post("/api/plan/fijos", status_code=201, response_model=esquemas.Guardado)
    def crear_fijo(entrada: esquemas.FijoEntrada):
        return _guardar("fijos", None, _fijo(entrada))

    @app.put("/api/plan/fijos/{item_id}", response_model=esquemas.Guardado)
    def editar_fijo(item_id: int, entrada: esquemas.FijoEntrada):
        return _guardar("fijos", item_id, _fijo(entrada))

    @app.post("/api/plan/cuotas", status_code=201, response_model=esquemas.Guardado)
    def crear_cuota(entrada: esquemas.CuotaEntrada):
        return _guardar("cuotas", None, _cuota(entrada))

    @app.put("/api/plan/cuotas/{item_id}", response_model=esquemas.Guardado)
    def editar_cuota(item_id: int, entrada: esquemas.CuotaEntrada):
        return _guardar("cuotas", item_id, _cuota(entrada))

    @app.delete("/api/plan/{tabla}/{item_id}", status_code=204)
    def borrar_del_plan(tabla: Literal["fijos", "cuotas"], item_id: int):
        if not base.borrar_del_plan(motor, tabla, item_id):
            raise HTTPException(status_code=404, detail="no existe en el plan")
        return Response(status_code=204)

    @app.get("/api/categorias", response_model=list[str])
    def ver_categorias():
        return base.categorias(motor)

    @app.get("/api/varios", response_model=list[esquemas.GrupoVarios])
    def ver_varios():
        return revisar.agrupar_varios(motor)

    @app.post("/api/reglas", status_code=201, response_model=esquemas.ReglaGuardada)
    def crear_regla(regla: esquemas.ReglaNueva):
        texto, categoria = regla.texto.strip(), regla.categoria.strip()
        if len(texto) < MINIMO_REGLA or not categoria:
            raise HTTPException(
                status_code=422, detail=f"la regla necesita al menos {MINIMO_REGLA} letras y una categoría"
            )
        try:
            return {"categorizados": base.agregar_regla(motor, texto, categoria)}
        except base.ReglaRepetida as error:
            raise HTTPException(status_code=409, detail=str(error))

    @app.post("/api/importar", response_model=esquemas.Importacion)
    def importar_archivos(archivos: list[UploadFile]):
        informes = [_importar_uno(archivo, motor, entrada, clave_nacion) for archivo in archivos]
        base.aplicar_reglas(motor)
        aviso = importar.actualizar_cotizaciones(motor, traer_cotizaciones)
        return {
            "informes": informes,
            "aviso_cotizaciones": aviso,
            "pendientes": len(base.pendientes(motor)),
            "sin_usd": base.contar_sin_usd(motor),
        }

    # La página ya armada (`npm run build`). Va al final para que /api/... no caiga acá.
    if PAGINA.is_dir():
        app.mount("/", StaticFiles(directory=PAGINA, html=True), name="pagina")

    return app


def esquema_openapi() -> dict:
    """El esquema de la API, para generar los tipos de TypeScript. Usa una base descartable."""
    with tempfile.TemporaryDirectory() as carpeta:
        return crear_app(Path(carpeta) / "esquema.db").openapi()


def nombre_seguro(nombre: str | None) -> str | None:
    """Solo el nombre final, sin carpetas: '../../x.pdf' queda 'x.pdf'. None si no se acepta."""
    final = Path((nombre or "").replace("\\", "/")).name
    if not final or final.startswith("."):
        return None
    if final != plan.ARCHIVO and Path(final).suffix.lower() != ".pdf":
        return None
    return final


def _importar_uno(archivo: UploadFile, motor: base.Engine, entrada: Path, clave_nacion: str) -> dict:
    nombre = nombre_seguro(archivo.filename)
    if nombre is None:
        return _rechazado(archivo.filename or "(sin nombre)", "solo se aceptan PDF o plan.csv")
    contenido = archivo.file.read(MAXIMO_ARCHIVO + 1)
    if len(contenido) > MAXIMO_ARCHIVO:
        return _rechazado(nombre, "pesa más de 20 MB")

    # Se importa desde una carpeta temporal: si no se reconoce, no pisa un archivo bueno de entrada/.
    with tempfile.TemporaryDirectory() as carpeta:
        temporal = Path(carpeta) / nombre
        temporal.write_bytes(contenido)
        informe = importar.importar_archivo(temporal, motor, clave_nacion)
        if informe.reconocido:
            entrada.mkdir(exist_ok=True)
            shutil.move(temporal, entrada / nombre)
    return asdict(informe)


def _rechazado(nombre: str, motivo: str) -> dict:
    return asdict(importar.Informe(nombre, errores=[motivo]))


def servir(ruta_db: Path, entrada: Path = Path("entrada"), clave_nacion: str = "") -> None:
    uvicorn.run(crear_app(ruta_db, entrada, clave_nacion), host=HOST, port=PUERTO)
