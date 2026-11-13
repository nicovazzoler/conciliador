"""API HTTP. Solo traduce: cada endpoint llama a las mismas funciones que la terminal."""
from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException

from conciliador import base, esquemas, reporte

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

    return app


def servir(ruta_db: Path) -> None:
    uvicorn.run(crear_app(ruta_db), host=HOST, port=PUERTO)
