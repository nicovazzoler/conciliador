"""Historial por fuente, por categoría y por fijo, con la demo."""
from fastapi.testclient import TestClient

from conciliador import api
from conciliador.importar import importar_carpeta
from conciliador import base
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent / "demo"


def cliente(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    importar_carpeta(DEMO, motor)
    return TestClient(api.crear_app(tmp_path / "p.db", traer_cotizaciones=lambda: []))


def test_el_historial_parte_lo_gastado_por_fuente(tmp_path):
    octubre, noviembre = cliente(tmp_path).get("/api/historial/2026-11?meses=3").json()[-2:]
    assert {f["fuente"] for f in octubre["fuentes"]} == {"mercado_pago"}
    fuentes = {f["fuente"]: f["pesos_centavos"] for f in noviembre["fuentes"]}
    assert {"tarjeta_comafi", "tarjeta_nacion"} <= set(fuentes)  # Los resúmenes vencen en noviembre: mes vencido.
    assert sum(fuentes.values()) == noviembre["pesos_centavos"]


def test_historial_de_una_categoria(tmp_path):
    c = cliente(tmp_path)
    meses = c.get("/api/historial/2026-10/categoria", params={"nombre": "Servicios", "meses": 3}).json()
    assert [m["mes"] for m in meses] == ["2026-08", "2026-09", "2026-10"]
    assert meses[-1]["movimientos"] >= 1 and meses[0]["movimientos"] == 0
    assert c.get("/api/historial/2026-13/categoria", params={"nombre": "x"}).status_code == 422


def test_historial_de_un_fijo(tmp_path):
    c = cliente(tmp_path)
    meses = c.get("/api/historial/2026-10/fijo", params={"concepto": "Internet", "meses": 2}).json()
    assert [m["mes"] for m in meses] == ["2026-09", "2026-10"]
    assert meses[0]["estado"] == "sin datos"  # Sin el Mercado Pago de septiembre no se sabe.
    assert meses[-1]["estado"] in ("bien", "más caro", "más barato") and meses[-1]["pagos"] == 1


def test_reimportar_un_resumen_lo_pasa_a_mes_vencido(tmp_path):
    """Las bases de antes guardaban la compra en un pago en el mes de la compra. Reimportar lo corrige."""
    from sqlalchemy import text

    motor = base.conectar(tmp_path / "p.db")
    importar_carpeta(DEMO, motor)
    with motor.begin() as conexion:
        conexion.execute(text("UPDATE movimientos SET mes = '2026-10' WHERE fuente = 'tarjeta_comafi' AND cuota IS NULL"))
    importar_carpeta(DEMO, motor)
    with motor.connect() as conexion:
        meses = {fila[0] for fila in conexion.execute(text("SELECT mes FROM movimientos WHERE fuente = 'tarjeta_comafi' AND tipo != 'pago'"))}
    assert meses == {"2026-11"}
