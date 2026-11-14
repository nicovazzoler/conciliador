import json
from dataclasses import asdict
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from conciliador import api, base, reporte
from conciliador.importar import importar_carpeta

DEMO = Path(__file__).parent.parent / "demo"


def cliente_con_demo(tmp_path):
    ruta = tmp_path / "demo.db"
    importar_carpeta(DEMO, base.conectar(ruta))
    return TestClient(api.crear_app(ruta)), ruta


def test_el_reporte_de_la_api_es_el_mismo_que_el_de_la_terminal(tmp_path):
    """La condición de 'lista' de la etapa 2: la página y la terminal dan los mismos números."""
    cliente, ruta = cliente_con_demo(tmp_path)
    for mes in ("2026-10", "2026-11"):
        respuesta = cliente.get(f"/api/reporte/{mes}")
        assert respuesta.status_code == 200
        terminal = json.loads(json.dumps(asdict(reporte.armar(base.conectar(ruta), mes)), default=str))
        terminal["importado"]["mercado_pago"] = bool(terminal["importado"]["mercado_pago"])
        assert respuesta.json() == terminal


def test_un_mes_mal_escrito_da_422(tmp_path):
    cliente, _ = cliente_con_demo(tmp_path)
    respuesta = cliente.get("/api/reporte/2026-13")
    assert respuesta.status_code == 422
    assert "mes inválido" in respuesta.json()["detail"]


def test_la_api_escucha_solo_en_127_0_0_1(tmp_path, monkeypatch):
    """Sin login, abrirla a la red dejaría ver tus gastos a cualquiera en tu Wi-Fi."""
    llamada = {}
    monkeypatch.setattr(api.uvicorn, "run", lambda app, **opciones: llamada.update(opciones))
    api.servir(tmp_path / "p.db")
    assert llamada["host"] == "127.0.0.1"


DIA = "2026-10-20"


def test_un_gasto_normal_se_guarda_de_una(tmp_path):
    cliente, _ = cliente_con_demo(tmp_path)
    respuesta = cliente.post("/api/gastos", json={"monto": "3.500", "descripcion": "Café Demo", "fecha": DIA})
    assert respuesta.status_code == 201
    assert respuesta.json()["id"] > 0


def test_un_gasto_grande_pide_confirmacion_y_despues_se_guarda(tmp_path):
    cliente, _ = cliente_con_demo(tmp_path)
    gasto = {"monto": "200000", "descripcion": "Mueble Demo", "fecha": DIA}
    primera = cliente.post("/api/gastos", json=gasto)
    assert primera.status_code == 409
    assert [a["codigo"] for a in primera.json()["avisos"]] == ["grande_sin_anticipar"]
    assert cliente.get("/api/manuales").json() == []  # Sin confirmar no se guarda.

    segunda = cliente.post("/api/gastos", json={**gasto, "confirmado": True, "categoria": "Hogar"})
    assert segunda.status_code == 201
    assert segunda.json()["categoria"] == "Hogar"


def test_un_monto_invalido_o_una_fecha_futura_dan_422(tmp_path):
    cliente, _ = cliente_con_demo(tmp_path)
    for gasto in (
        {"monto": "abc", "descripcion": "Café Demo", "fecha": DIA},
        {"monto": "0", "descripcion": "Café Demo", "fecha": DIA},
        {"monto": "100", "descripcion": "Café Demo", "fecha": "2999-01-01"},
        {"monto": "100", "descripcion": "Café Demo", "fecha": DIA, "medio": "cheque"},
    ):
        assert cliente.post("/api/gastos", json=gasto).status_code == 422, gasto


def test_un_pago_aparece_en_manuales(tmp_path):
    cliente, _ = cliente_con_demo(tmp_path)
    respuesta = cliente.post("/api/pagos", json={"tarjeta": "tarjeta_comafi", "monto": "1000", "fecha": DIA})
    assert respuesta.status_code == 201
    (pago,) = cliente.get("/api/manuales").json()
    assert (pago["tipo"], pago["tarjeta"], pago["monto_centavos"]) == ("pago_tarjeta", "tarjeta_comafi", -100_000)


def test_borrar_un_manual_y_despues_da_404(tmp_path):
    cliente, _ = cliente_con_demo(tmp_path)
    nuevo = cliente.post("/api/gastos", json={"monto": "3500", "descripcion": "Café Demo", "fecha": DIA}).json()
    assert cliente.delete(f"/api/manuales/{nuevo['id']}").status_code == 204
    assert cliente.delete(f"/api/manuales/{nuevo['id']}").status_code == 404


def test_no_se_puede_borrar_un_movimiento_de_un_pdf_por_la_api(tmp_path):
    cliente, ruta = cliente_con_demo(tmp_path)
    with base.Session(base.conectar(ruta)) as sesion:
        de_un_pdf = sesion.scalar(select(base.Movimiento.id).limit(1))
    assert cliente.delete(f"/api/manuales/{de_un_pdf}").status_code == 404
