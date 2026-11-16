from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from conciliador import api, inversiones, precios
from conciliador.inversiones import Operacion


def op(id, dia, lado, cantidad, precio, comision="0", activo="BTC"):
    return Operacion(id, datetime(2026, 11, dia), activo, "cripto", lado, Decimal(cantidad), Decimal(precio), Decimal(comision))


def test_precio_promedio_y_ganancia_realizada():
    """Dos compras a 90.000 y 100.000: promedio 95.000. Vender medio a 110.000 gana 7.500."""
    r = inversiones.calcular(
        [op(1, 1, "compra", "1", "90000"), op(2, 2, "compra", "1", "100000"), op(3, 3, "venta", "0.5", "110000")],
        {"BTC": Decimal("120000")},
    )
    assert r.realizado == {3: Decimal("7500")}
    (btc,) = r.posiciones
    assert (btc.cantidad, btc.costo_promedio, btc.costo) == (Decimal("1.5"), Decimal("95000"), Decimal("142500"))
    assert btc.no_realizado == Decimal("37500")  # 1,5 × 120.000 − 142.500.


def test_las_comisiones_suben_el_costo_y_bajan_la_ganancia():
    r = inversiones.calcular([op(1, 1, "compra", "1", "100", "1"), op(2, 2, "venta", "1", "110", "1")], {})
    assert r.realizado == {2: Decimal("8")}  # 110 − 1 de comisión − 101 de costo.
    assert r.posiciones == []


def test_el_orden_es_por_fecha_aunque_se_carguen_desordenadas():
    r = inversiones.calcular([op(2, 5, "venta", "1", "120"), op(1, 1, "compra", "1", "100")], {})
    assert r.realizado == {2: Decimal("20")}


def test_vender_mas_de_lo_que_hay_avisa():
    r = inversiones.calcular([op(1, 1, "compra", "1", "100"), op(2, 2, "venta", "2", "110")], {})
    assert "Falta alguna compra" in r.avisos[0]


def test_sin_precio_no_se_inventa_el_valor():
    (btc,) = inversiones.calcular([op(1, 1, "compra", "1", "100")], {}).posiciones
    assert (btc.valor, btc.no_realizado) == (None, None)


def test_decimales_con_coma_o_punto_y_nunca_float():
    assert inversiones.decimal_desde("0,0412", "cantidad") == Decimal("0.0412")
    assert inversiones.decimal_desde("94.120,55", "precio") == Decimal("94120.55")
    assert inversiones.decimal_desde("94120.55", "precio") == Decimal("94120.55")
    assert inversiones.decimal_desde("251.75", "precio") == Decimal("251.75")  # Punto o coma: los dos son decimal.
    assert inversiones.decimal_desde("94,120.55", "precio") == Decimal("94120.55")
    assert inversiones.decimal_desde("1.234.567", "cantidad") == Decimal("1234567")
    assert inversiones.decimal_desde("1.5", "cantidad") == Decimal("1.5")
    for malo in ("abc", "-1", "NaN"):
        with pytest.raises(ValueError):
            inversiones.decimal_desde(malo, "cantidad")


def respuesta_falsa(url):
    if "binance" in url:
        return {"symbol": "BTCUSDT", "price": "120000.50"}
    if "FALLA" in url:
        raise OSError("sin red")
    return {"chart": {"result": [{"meta": {"currency": "USD", "regularMarketPrice": 140.25}}]}}


def test_precios_por_tipo_y_uno_que_falla_no_frena_a_los_demas():
    nuevos, errores = precios.actualizar({"BTC": "cripto", "NVDA": "accion", "FALLA": "accion", "USDT": "cripto"},
                                         respuesta_falsa)
    assert nuevos == {"BTC": Decimal("120000.50"), "NVDA": Decimal("140.25"), "USDT": Decimal(1)}
    assert errores == ["FALLA: sin precio (OSError)"]


def test_cargar_operaciones_y_ver_la_cartera_por_la_api(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "p.db", traer_precio=respuesta_falsa))
    for operacion in (
        {"fecha": "2026-11-01", "activo": "btc", "tipo_activo": "cripto", "lado": "compra", "cantidad": "0,5", "precio": "90000"},
        {"fecha": "2026-11-02", "activo": "BTC", "tipo_activo": "cripto", "lado": "venta", "cantidad": "0,1", "precio": "110000", "comision": "1"},
    ):
        assert cliente.post("/api/operaciones", json=operacion).status_code == 201

    sin_precio = cliente.get("/api/inversiones/2026-11").json()
    assert sin_precio["sin_precio"] == ["BTC"]
    assert sin_precio["cartera_centavos"] == 0

    assert cliente.post("/api/precios").json() == {"actualizados": 1, "errores": []}
    datos = cliente.get("/api/inversiones/2026-11").json()
    assert datos["realizado_mes_centavos"] == 199_900  # 0,1 × (110.000 − 90.000) − 1.
    assert datos["invertido_centavos"] == 3_600_000  # 0,4 × 90.000.
    assert datos["cartera_centavos"] == 4_800_020  # 0,4 × 120.000,50.
    venta, compra = datos["operaciones"]
    assert (venta["lado"], venta["resultado_centavos"]) == ("venta", 199_900)
    assert (compra["abierta"], compra["resultado_centavos"]) == (True, None)


def test_una_operacion_invalida_da_422(tmp_path):
    cliente = TestClient(api.crear_app(tmp_path / "p.db"))
    base = {"fecha": "2026-11-01", "activo": "BTC", "tipo_activo": "cripto", "lado": "compra", "cantidad": "1", "precio": "100"}
    for malo in ({"cantidad": "0"}, {"precio": "abc"}, {"fecha": "2999-01-01"}, {"activo": " "}):
        assert cliente.post("/api/operaciones", json={**base, **malo}).status_code == 422, malo
