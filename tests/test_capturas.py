"""Lectura de capturas: la API de Anthropic se reemplaza por una falsa; nunca se llama de verdad."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from conciliador import api, capturas

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def lectura_falsa(imagenes):
    assert imagenes and all(tipo == "image/png" for _, tipo in imagenes)
    return capturas.limpiar(capturas.Lectura(
        operaciones=[
            capturas.OperacionLeida(fecha="2026-10-02", activo="btc", tipo_activo="cripto", lado="compra",
                                    fuente="quantfury", cantidad="0.05", precio="60000", comision="0",
                                    numero_operacion=None, nota=None),
            capturas.OperacionLeida(fecha="2026-10-09", activo="NVDA", tipo_activo="accion", lado="venta",
                                    fuente="otra", cantidad="3", precio="94.125", comision="0.5",
                                    numero_operacion="Q-123", nota="short"),
            capturas.OperacionLeida(fecha="ayer", activo="ETH", tipo_activo="cripto", lado="compra",
                                    fuente="binance", cantidad="1", precio="3000", comision="0",
                                    numero_operacion=None, nota=None),
        ],
        avisos=[],
    ))


@pytest.fixture
def cliente(tmp_path):
    return TestClient(api.crear_app(tmp_path / "prueba.db", tmp_path, leer_capturas=lectura_falsa))


def test_lee_las_capturas_sin_guardar_nada(cliente):
    respuesta = cliente.post("/api/operaciones/leer", files=[("archivos", ("a.png", PNG, "image/png"))])
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert [o["activo"] for o in datos["operaciones"]] == ["BTC", "NVDA"]
    nvda = datos["operaciones"][1]
    # Con coma y sin miles: "94.125" se leería como noventa y cuatro mil al cargarlo.
    assert (nvda["precio"], nvda["comision"], nvda["fuente"]) == ("94,125", "0,5", "captura")
    assert len(datos["avisos"]) == 1  # La de fecha ilegible queda afuera, con aviso.
    assert cliente.get("/api/inversiones/2026-10").json()["operaciones"] == []


def test_solo_acepta_imagenes(cliente):
    respuesta = cliente.post("/api/operaciones/leer", files=[("archivos", ("a.pdf", b"%PDF", "application/pdf"))])
    assert respuesta.status_code == 422


def test_lo_leido_no_se_carga_dos_veces(cliente):
    leida = cliente.post("/api/operaciones/leer", files=[("archivos", ("a.png", PNG, "image/png"))]).json()
    btc = {k: v for k, v in leida["operaciones"][0].items() if k != "nota"}
    assert cliente.post("/api/operaciones", json=btc).status_code == 201
    assert cliente.post("/api/operaciones", json=btc).status_code == 409
    nvda = {k: v for k, v in leida["operaciones"][1].items() if k != "nota"}
    nvda["fecha"] = "2026-10-09"
    assert cliente.post("/api/operaciones", json=nvda).status_code == 201
    assert cliente.post("/api/operaciones", json=nvda).status_code == 409
    precio = cliente.get("/api/inversiones/2026-10").json()["operaciones"]
    assert {o["precio"] for o in precio} >= {"94.125"}


def test_sin_clave_avisa_que_hay_que_ponerla(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "prueba.db", tmp_path))
    respuesta = cliente.post("/api/operaciones/leer", files=[("archivos", ("a.png", PNG, "image/png"))])
    assert respuesta.status_code == 502
    assert "ANTHROPIC_API_KEY" in respuesta.json()["detail"]


def test_la_carga_manual_sigue_sin_numero(cliente):
    manual = {"fecha": "2026-10-02", "activo": "BTC", "tipo_activo": "cripto", "lado": "compra",
              "cantidad": "0,01", "precio": "60000"}
    assert cliente.post("/api/operaciones", json=manual).status_code == 201
    assert cliente.post("/api/operaciones", json=manual).status_code == 201


def test_las_instrucciones_dicen_la_fecha_de_hoy():
    assert "2026-11-16" in capturas.INSTRUCCIONES.format(hoy=date(2026, 11, 16).isoformat())
