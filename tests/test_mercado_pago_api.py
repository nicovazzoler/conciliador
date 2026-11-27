import io
import json
import urllib.error
from datetime import date
from decimal import Decimal

import pytest

from conciliador import base, mercado_pago_api
from conciliador.__main__ import main
from conciliador.lectores import FilaLeida

CUENTA = 555
TOKEN = "token-de-mentira"  # No tiene la forma de una credencial real a propósito.


def pago(id, rol, monto="10.5", fecha="2026-11-27T14:03:12.000-04:00", **extra):
    """Un pago con la forma de /v1/payments/search. Los montos llegan como Decimal, como con parse_float."""
    return {
        "id": id, "date_created": fecha, "status": "approved", "transaction_amount": Decimal(monto),
        "currency_id": "ARS", "operation_type": "money_transfer", "payment_type_id": "account_money",
        "collector_id": CUENTA if rol == "cobrado" else 999, **extra,
    }


def api_falsa(cobrados, pagados, pedidos=None):
    """Responde /users/me y /v1/payments/search paginando como la API."""
    def pedir(ruta, parametros):
        if pedidos is not None:
            pedidos.append((ruta, parametros))
        if ruta == "/users/me":
            return {"id": CUENTA}
        todos = cobrados if "collector.id" in parametros else pagados
        inicio = parametros["offset"]
        return {"paging": {"total": len(todos)}, "results": todos[inicio:inicio + parametros["limit"]]}
    return pedir


def test_lee_cobros_y_pagos_con_signo_hora_argentina_y_centavos():
    cobro = pago(1, "cobrado", "10.5", payer={"first_name": "Ana", "last_name": "Demo"})
    compra = pago(2, "pagado", "1234.56", fecha="2026-11-27T10:00:00.000-04:00", description="Kiosco demo",
                  operation_type="regular_payment")
    cuenta, pagos, crudos = mercado_pago_api.pagos_recientes(api_falsa([cobro], [compra]), 1)
    assert cuenta == "555"
    primero, segundo = pagos  # Del más nuevo al más viejo.
    assert (primero.id, primero.rol, primero.monto_centavos, primero.detalle) == ("1", "cobrado", 1050, "de Ana Demo")
    assert f"{primero.fecha:%H:%M}" == "15:03"  # 14:03 en GMT-04 son las 15:03 en Argentina.
    assert (segundo.monto_centavos, segundo.tipo, segundo.detalle) == (-123456, "regular_payment/account_money", "Kiosco demo")
    assert [c["rol"] for c in crudos] == ["cobrado", "pagado"]


def test_pide_los_ultimos_dias_como_cobrador_y_como_pagador():
    pedidos = []
    mercado_pago_api.pagos_recientes(api_falsa([], [], pedidos), 3)
    busquedas = [p for r, p in pedidos if r == "/v1/payments/search"]
    assert [("collector.id" in p, "payer.id" in p) for p in busquedas] == [(True, False), (False, True)]
    assert {p["begin_date"] for p in busquedas} == {"NOW-3DAYS"}


def test_pagina_hasta_traer_todo():
    cobrados = [pago(i, "cobrado") for i in range(120)]
    pedidos = []
    _, pagos, _ = mercado_pago_api.pagos_recientes(api_falsa(cobrados, [], pedidos), 1)
    assert len(pagos) == 120
    assert [p["offset"] for r, p in pedidos if "collector.id" in p] == [0, 50, 100]


def test_un_rango_de_un_anio_o_mas_es_un_error():
    for dias in (0, 365):
        with pytest.raises(ValueError, match="entre 1 y 364"):
            mercado_pago_api.pagos_recientes(api_falsa([], []), dias)


def test_un_token_rechazado_se_explica_sin_mostrar_el_token(monkeypatch):
    def rechazar(pedido, timeout):
        raise urllib.error.HTTPError(pedido.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"message":"invalid token"}'))
    monkeypatch.setattr(mercado_pago_api.urllib.request, "urlopen", rechazar)
    with pytest.raises(mercado_pago_api.ErrorMP) as error:
        mercado_pago_api.pedidor(TOKEN)("/users/me", {})
    assert "401" in str(error.value) and TOKEN not in str(error.value)


def test_el_token_va_en_el_header_y_los_montos_llegan_como_decimal(monkeypatch):
    vistos = []
    def responder(pedido, timeout):
        vistos.append(pedido)
        return io.BytesIO(json.dumps({"results": [{"transaction_amount": 0.1}]}).encode())
    monkeypatch.setattr(mercado_pago_api.urllib.request, "urlopen", responder)
    datos = mercado_pago_api.pedidor(TOKEN)("/v1/payments/search", {"limit": 1})
    assert vistos[0].get_header("Authorization") == f"Bearer {TOKEN}"
    assert datos["results"][0]["transaction_amount"] == Decimal("0.1")


def test_el_texto_marca_que_esta_en_la_base_y_resume_por_tipo():
    _, pagos, _ = mercado_pago_api.pagos_recientes(api_falsa([pago(1, "cobrado"), pago(2, "cobrado")], []), 1)
    salida = mercado_pago_api.texto("555", pagos, 1, en_base={"1"})
    assert "[en la base]" in salida and "[no está en la base]" in salida
    assert "2  cobrado money_transfer/account_money" in salida
    assert "+ $       10,50" in salida


def test_sin_pagos_lo_dice():
    assert "La API no devolvió nada" in mercado_pago_api.texto("555", [], 1, None)


def test_numeros_de_operacion_de_una_fuente(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    base.guardar_movimientos(motor, "mercado_pago", [FilaLeida("777", date(2026, 11, 1), "DEMO", -100, tipo="consumo")])
    assert base.numeros_de_operacion(motor, "mercado_pago") == {"777"}
    assert base.numeros_de_operacion(motor, "tarjeta_comafi") == set()


def test_sin_token_el_comando_explica_de_donde_sacarlo(monkeypatch):
    monkeypatch.setenv("MP_ACCESS_TOKEN", "")
    monkeypatch.setattr("sys.argv", ["conciliador", "mp-probar"])
    with pytest.raises(SystemExit, match="Credenciales de producción"):
        main()
