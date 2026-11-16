from pathlib import Path

from conciliador.__main__ import RAIZ


def test_las_rutas_por_defecto_son_las_del_proyecto_y_no_las_de_la_terminal():
    # Correr el comando desde web/ creaba una base vacía ahí. La raíz es la carpeta del proyecto.
    assert (RAIZ / "conciliador" / "__main__.py").exists()
    assert RAIZ == Path(__file__).resolve().parent.parent
