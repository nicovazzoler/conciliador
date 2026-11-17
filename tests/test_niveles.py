"""Stop loss, take profit y la cartera a lo largo del tiempo. Yahoo y Binance son falsos."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from conciliador import api, inversiones, precios

HOY = date.today()


def segundos(dia):
    return int(datetime.combine(dia, datetime.min.time(), timezone.utc).timestamp())


def mercado(bajo=30, alto=34, precio=32.5):
    def traer(url):
        if "ticker/price" in url:
            return {"price": "100"}
        if "ticker/24hr" in url:
            return {"lowPrice": "90", "highPrice": "110"}
        if "klines" in url:
            return [[segundos(HOY - timedelta(days=d)) * 1000, "0", "0", "0", str(100 - d)] for d in (3, 2, 1, 0)]
        if "chart/EWZ?range=1d" in url:
            return {"chart": {"result": [{"meta": {"currency": "USD", "regularMarketPrice": precio,
                                                    "regularMarketDayLow": bajo, "regularMarketDayHigh": alto}}]}}
        if "chart/EWZ?period1" in url:
            dias = [HOY - timedelta(days=d) for d in (3, 2, 1, 0)]
            return {"chart": {"result": [{"meta": {"currency": "USD"}, "timestamp": [segundos(d) for d in dias],
                                          "indicators": {"quote": [{"close": [30, None, 31, 32]}]}}]}}
        raise AssertionError(url)
    return traer


def compra(cliente, activo="EWZ", tipo="accion", cantidad="10", precio="33", dias=3):
    datos = {"fecha": (HOY - timedelta(days=dias)).isoformat(), "activo": activo, "tipo_activo": tipo,
             "lado": "compra", "cantidad": cantidad, "precio": precio}
    assert cliente.post("/api/operaciones", json=datos).status_code == 201


def test_si_toca_el_stop_loss_avisa_y_al_confirmar_carga_la_venta(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "p.db", traer_precio=mercado(bajo=30.5)))
    compra(cliente)
    assert cliente.put("/api/niveles/ewz", json={"stop_loss": "31", "take_profit": "40"}).status_code == 204
    cliente.post("/api/precios")
    datos = cliente.get(f"/api/inversiones/{HOY:%Y-%m}").json()
    (aviso,) = datos["niveles_tocados"]
    assert (aviso["activo"], aviso["tipo"], aviso["nivel"], aviso["cantidad"]) == ("EWZ", "stop_loss", "31", "10")
    assert cliente.post("/api/niveles/EWZ/cerrar").status_code == 201
    datos = cliente.get(f"/api/inversiones/{HOY:%Y-%m}").json()
    assert datos["posiciones"] == [] and datos["niveles_tocados"] == []
    assert datos["realizado_mes_centavos"] == -2000  # 10 × (31 − 33).


def test_si_no_se_cerro_se_descarta_el_aviso(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "p.db", traer_precio=mercado(alto=41)))
    compra(cliente)
    cliente.put("/api/niveles/EWZ", json={"stop_loss": "", "take_profit": "40,5"})
    cliente.post("/api/precios")
    assert cliente.get(f"/api/inversiones/{HOY:%Y-%m}").json()["niveles_tocados"][0]["tipo"] == "take_profit"
    assert cliente.post("/api/niveles/EWZ/descartar").status_code == 204
    datos = cliente.get(f"/api/inversiones/{HOY:%Y-%m}").json()
    assert datos["niveles_tocados"] == []
    assert (datos["posiciones"][0]["stop_loss"], datos["posiciones"][0]["take_profit"]) == (None, "40.5")


def test_sin_tocar_no_avisa_y_los_niveles_se_validan(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "p.db", traer_precio=mercado()))
    compra(cliente)
    assert cliente.put("/api/niveles/EWZ", json={"stop_loss": "40", "take_profit": "35"}).status_code == 422
    cliente.put("/api/niveles/EWZ", json={"stop_loss": "29", "take_profit": "35"})
    cliente.post("/api/precios")
    assert cliente.get(f"/api/inversiones/{HOY:%Y-%m}").json()["niveles_tocados"] == []
    assert cliente.post("/api/niveles/EWZ/cerrar").status_code == 404


def test_la_cartera_dia_por_dia(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "p.db", traer_precio=mercado()))
    compra(cliente, dias=3)  # 10 EWZ a 33.
    compra(cliente, activo="BTC", tipo="cripto", cantidad="1", precio="95", dias=1)
    historia = cliente.get("/api/historia-inversiones").json()
    assert historia["sin_precio"] == []
    puntos = {p["fecha"]: p for p in historia["puntos"]}
    primero = puntos[(HOY - timedelta(days=3)).isoformat()]
    assert (primero["valor_centavos"], primero["invertido_centavos"]) == (30000, 33000)
    segundo = puntos[(HOY - timedelta(days=2)).isoformat()]  # Sin cierre ese día: usa el anterior.
    assert segundo["valor_centavos"] == 30000
    hoy = puntos[HOY.isoformat()]
    assert (hoy["valor_centavos"], hoy["invertido_centavos"]) == (32000 + 10000, 33000 + 9500)


def test_ultimo_usa_el_dia_anterior():
    serie = {date(2026, 11, 13): Decimal(1), date(2026, 11, 16): Decimal(2)}
    assert precios.ultimo(serie, date(2026, 11, 15)) == 1
    assert precios.ultimo(serie, date(2026, 11, 12)) is None
    assert inversiones.historia([], {}, date(2026, 11, 1), date(2026, 11, 2)) == []
