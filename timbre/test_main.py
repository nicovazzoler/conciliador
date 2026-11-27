import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

import main as timbre

SECRETO = "secreto-de-prueba"


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("MP_WEBHOOK_SECRET", SECRETO)
    monkeypatch.setenv("TIMBRE_CLAVE", "clave")
    timbre.avisos.clear()
    return TestClient(timbre.app)


def firmar(data_id: str, request_id: str, ts: str = "1764250000", secreto: str = SECRETO) -> str:
    manifiesto = f"id:{data_id};request-id:{request_id};ts:{ts};"
    return f"ts={ts},v1={hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()}"


def avisar(cliente, data_id="123456", firma=None, request_id="req-1"):
    return cliente.post(
        f"/webhook?data.id={data_id}&type=payment",
        json={"type": "payment", "action": "payment.created", "data": {"id": data_id}, "live_mode": True},
        headers={"x-signature": firma or firmar(data_id, request_id), "x-request-id": request_id},
    )


def test_un_aviso_bien_firmado_se_guarda(cliente):
    assert avisar(cliente).status_code == 200
    (aviso,) = cliente.get("/avisos", headers={"Authorization": "Bearer clave"}).json()
    assert (aviso["tipo"], aviso["accion"], aviso["id"], aviso["real"]) == ("payment", "payment.created", "123456", True)


def test_con_otro_secreto_se_rechaza_y_no_se_guarda(cliente):
    assert avisar(cliente, firma=firmar("123456", "req-1", secreto="otro")).status_code == 401
    assert avisar(cliente, firma="basura").status_code == 401
    assert cliente.get("/avisos", headers={"Authorization": "Bearer clave"}).json() == []


def test_la_firma_cubre_el_id(cliente):
    """Una firma válida para un pago no sirve para avisar de otro."""
    assert avisar(cliente, data_id="999", firma=firmar("123456", "req-1")).status_code == 401


def test_el_id_alfanumerico_se_firma_en_minusculas(cliente):
    assert avisar(cliente, data_id="ORDABC", firma=firmar("ordabc", "req-1")).status_code == 200


def test_sin_request_id_el_manifiesto_lo_omite():
    manifiesto = "id:5;ts:1;"
    v1 = hmac.new(SECRETO.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    assert timbre.firma_valida(SECRETO, f"ts=1,v1={v1}", "", "5")


def test_los_avisos_piden_clave(cliente):
    avisar(cliente)
    assert cliente.get("/avisos").status_code == 401
    assert cliente.get("/avisos", headers={"Authorization": "Bearer otra"}).status_code == 401


def test_sin_secreto_configurado_no_acepta_nada(cliente, monkeypatch):
    monkeypatch.delenv("MP_WEBHOOK_SECRET")
    assert avisar(cliente).status_code == 503


def test_cuerpos_raros_no_rompen_el_servidor(cliente):
    """Un 400 o 401, nunca un 500: la URL es pública y cualquiera puede mandar cualquier cosa."""
    assert cliente.post("/webhook", content=b"[1, 2]").status_code == 400
    assert cliente.post("/webhook", content=b"\xff\xfe").status_code == 400
    assert cliente.post("/webhook", json={"data": "texto"}).status_code == 401
    assert cliente.post("/webhook", json={}, headers={"x-signature": "ts=1,v1=ñ".encode("latin-1")}).status_code == 401
    assert cliente.get("/avisos", headers={"Authorization": "Bearer ñ".encode("latin-1")}).status_code == 401


def test_no_publica_la_documentacion(cliente):
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404
