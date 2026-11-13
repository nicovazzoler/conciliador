import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from conciliador import base


def test_una_base_nueva_queda_en_la_ultima_version(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    assert base.version(motor) == base.ultima_version()
    assert inspect(motor).has_table("movimientos")


def test_los_modelos_coinciden_con_las_migraciones(tmp_path):
    """Si cambia un modelo y falta su migración, este test falla."""
    motor = base.conectar(tmp_path / "p.db")
    with motor.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), base.Base.metadata)
    assert diferencias == []


def test_una_base_anterior_a_alembic_se_marca_como_0001(tmp_path):
    ruta = tmp_path / "vieja.db"
    with create_engine(f"sqlite:///{ruta}").begin() as conexion:  # Estructura de la 0001, sin versión.
        command.upgrade(base._config(conexion), "0001")
        conexion.exec_driver_sql("DROP TABLE alembic_version")

    with pytest.raises(base.BaseDesactualizada):
        base.conectar(ruta)
    base.migrar(ruta)
    assert base.version(base.conectar(ruta)) == base.ultima_version()


def test_migrar_una_base_al_dia_no_hace_nada(tmp_path):
    ruta = tmp_path / "p.db"
    base.conectar(ruta)
    assert base.migrar(ruta) is None
    assert list(tmp_path.iterdir()) == [ruta]


def test_migrar_desde_una_version_vieja_hace_respaldo(tmp_path):
    ruta = tmp_path / "p.db"
    motor = create_engine(f"sqlite:///{ruta}")
    with motor.begin() as conexion:
        command.upgrade(base._config(conexion), "0001")

    respaldo = base.migrar(ruta)
    assert respaldo == tmp_path / f"p-antes-de-{base.ultima_version()}.db"
    assert base.version(create_engine(f"sqlite:///{respaldo}")) == "0001"
    assert base.version(base.conectar(ruta)) == base.ultima_version()
