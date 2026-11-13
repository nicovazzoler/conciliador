"""Alembic corre esto: aplica las migraciones sobre la conexión que le pasa base.py."""
import os

from alembic import context
from sqlalchemy import create_engine

from conciliador.base import Base


def correr(conexion):
    # render_as_batch: SQLite no modifica columnas, así que Alembic copia la tabla.
    context.configure(connection=conexion, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


conexion = context.config.attributes.get("connection")
if conexion is not None:
    correr(conexion)
else:  # Desde la terminal, con `alembic revision --autogenerate`.
    ruta = os.environ.get("CONCILIADOR_DB", "conciliador.db")
    with create_engine(f"sqlite:///{ruta}").connect() as conexion:
        correr(conexion)
