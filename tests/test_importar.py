from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conciliador import base
from conciliador.importar import importar_carpeta
from conciliador.lectores import FilaLeida

RAIZ = Path(__file__).parent.parent
DEMO = RAIZ / "demo"


def contar(motor):
    with Session(motor) as sesion:
        return sesion.scalar(select(func.count()).select_from(base.Movimiento))


def importar_demo(motor):
    return [i for i in importar_carpeta(DEMO, motor) if i.archivo.endswith(".pdf")]


def test_importa_las_tres_fuentes(tmp_path):
    motor = base.conectar(tmp_path / "prueba.db")
    informes = importar_demo(motor)
    assert [(i.nuevas, i.repetidas) for i in informes] == [(20, 0), (11, 0), (5, 0)]
    assert all(i.problemas == [] for i in informes)
    assert contar(motor) == 36


def test_reimportar_no_agrega_movimientos(tmp_path):
    motor = base.conectar(tmp_path / "prueba.db")
    importar_demo(motor)
    informes = importar_demo(motor)
    assert [(i.nuevas, i.repetidas) for i in informes] == [(0, 20), (0, 11), (0, 5)]
    assert contar(motor) == 36


def test_dos_gastos_iguales_con_distinto_numero_son_distintos(tmp_path):
    motor = base.conectar(tmp_path / "prueba.db")
    fila = dict(fecha=date(2026, 10, 1), descripcion="Pago SUBE", monto_centavos=-100)
    filas = [FilaLeida("1", **fila), FilaLeida("2", **fila)]
    assert base.guardar_movimientos(motor, "mercado_pago", filas) == (2, 0)


def test_el_mismo_numero_en_otra_fuente_no_es_repetido(tmp_path):
    motor = base.conectar(tmp_path / "prueba.db")
    fila = FilaLeida("1", date(2026, 10, 1), "Pago", -100)
    base.guardar_movimientos(motor, "mercado_pago", [fila])
    assert base.guardar_movimientos(motor, "otra_fuente", [fila]) == (1, 0)


def test_los_archivos_ajenos_se_informan(tmp_path):
    carpeta = tmp_path / "entrada"
    carpeta.mkdir()
    (carpeta / "notas.txt").write_text("nada")
    motor = base.conectar(tmp_path / "prueba.db")
    assert [i.reconocido for i in importar_carpeta(carpeta, motor)] == [False]


def test_solo_base_toca_la_base():
    conflictivos = [
        p.relative_to(RAIZ).as_posix()
        for p in (RAIZ / "conciliador").rglob("*.py")
        if p.name != "base.py"
        and "migraciones" not in p.parts
        and "sqlalchemy" in p.read_text(encoding="utf-8")
    ]
    assert conflictivos == []
