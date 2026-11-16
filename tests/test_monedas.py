"""Acciones de otras bolsas: se operan en su moneda y se convierten a USD con el cambio de ese día."""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from conciliador import api, precios


def yahoo_falso(url):
    if "search?q=WEGE3" in url:
        return {"quotes": [{"symbol": "WEGE3.SA", "quoteType": "EQUITY"}, {"symbol": "WEGE3.BA", "quoteType": "EQUITY"}]}
    if "chart/WEGE3.SA" in url:
        return {"chart": {"result": [{"meta": {"currency": "BRL", "regularMarketPrice": 60}}]}}
    if "chart/WEGE3?" in url:
        raise OSError("404")  # Así no existe en Yahoo.
    if "chart/BRLUSD%3DX?range" in url or "chart/BRLUSD=X?range" in url:
        return {"chart": {"result": [{"meta": {"currency": "USD", "regularMarketPrice": 0.25}}]}}
    if "chart/BRLUSD=X?period1" in url:
        return {"chart": {"result": [{"indicators": {"quote": [{"close": [0.19, None, 0.2]}]}}]}}
    if "chart/VOD.L" in url:
        return {"chart": {"result": [{"meta": {"currency": "GBp", "regularMarketPrice": 70}}]}}
    if "chart/GBPUSD" in url:
        return {"chart": {"result": [{"meta": {"currency": "USD", "regularMarketPrice": 1.3}}]}}
    raise AssertionError(url)


def test_una_accion_de_brasil_se_busca_y_se_pasa_a_dolares():
    assert precios.accion("WEGE3", yahoo_falso) == Decimal("15.00")  # 60 reales × 0,25.


def test_londres_cotiza_en_peniques():
    assert precios.accion("VOD.L", yahoo_falso) == Decimal("0.910")  # 70 peniques = 0,70 libras × 1,3.


def test_el_cambio_es_el_ultimo_cierre_hasta_ese_dia():
    assert precios.cambio("BRL", date(2026, 11, 4), yahoo_falso) == Decimal("0.2")
    assert precios.cambio("USD", date(2026, 11, 4), yahoo_falso) == 1


def test_una_compra_en_reales_cuesta_en_dolares_lo_de_ese_dia(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "p.db", traer_precio=yahoo_falso))
    compra = {"fecha": "2026-11-04", "activo": "WEGE3", "tipo_activo": "accion", "lado": "compra",
              "cantidad": "100", "precio": "50", "moneda": "brl"}
    assert cliente.post("/api/operaciones", json=compra).status_code == 201
    assert cliente.post("/api/precios").json() == {"actualizados": 1, "errores": []}
    datos = cliente.get("/api/inversiones/2026-11").json()
    assert datos["invertido_centavos"] == 100_000  # 100 × 50 reales × 0,20 = USD 1.000.
    assert datos["cartera_centavos"] == 150_000  # 100 × 60 reales × 0,25 = USD 1.500.
    (operacion,) = datos["operaciones"]
    assert (operacion["precio"], operacion["moneda"]) == ("50", "BRL")  # Se muestra como se operó.


def test_una_moneda_rara_da_422(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "p.db", traer_precio=yahoo_falso))
    compra = {"fecha": "2026-11-04", "activo": "X", "tipo_activo": "accion", "lado": "compra",
              "cantidad": "1", "precio": "1", "moneda": "reales"}
    assert cliente.post("/api/operaciones", json=compra).status_code == 422
