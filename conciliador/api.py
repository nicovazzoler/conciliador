"""API HTTP. Solo traduce: cada endpoint llama a las mismas funciones que la terminal."""
from dataclasses import asdict
from datetime import date
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse

from conciliador import base, esquemas, manual, reporte

HOST = "127.0.0.1"  # Sin login: solo esta máquina puede entrar.
PUERTO = 8000


def crear_app(ruta_db: Path) -> FastAPI:
    """Una app por base: los tests usan una temporal y el comando `web`, la real."""
    motor = base.conectar(ruta_db)  # Si la base está desactualizada, falla al arrancar.
    app = FastAPI(title="Conciliador")

    @app.get("/api/reporte/{mes}", response_model=esquemas.Reporte)
    def ver_reporte(mes: str):
        try:
            return asdict(reporte.armar(motor, mes))
        except ValueError as error:  # Un mes mal escrito es un error de quien llama.
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

    return app


def servir(ruta_db: Path) -> None:
    uvicorn.run(crear_app(ruta_db), host=HOST, port=PUERTO)
