import json
from dataclasses import asdict
from pathlib import Path

from fastapi.testclient import TestClient

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
