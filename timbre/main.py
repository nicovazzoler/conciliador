"""Timbre: recibe los webhooks de Mercado Pago, valida la firma y guarda solo de qué se avisó.

El aviso no trae montos ni nombres (solo tipo, acción e id). El detalle lo pide el conciliador a la
API con su token, desde la máquina del usuario. Acá no hay token de Mercado Pago.
"""
import hashlib
import hmac
import json
import logging
import os
from collections import deque
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request, Response

app = FastAPI(title="timbre", docs_url=None, redoc_url=None, openapi_url=None)
# El logger de uvicorn sale sin buffer en los logs de Railway; un print a stdout puede quedar retenido.
log = logging.getLogger("uvicorn.error")

# En memoria: se pierde al reiniciar. Alcanza para probar; los logs de Railway quedan igual.
avisos: deque[dict] = deque(maxlen=200)


def iguales(a: str, b: str) -> bool:
    """Comparación en tiempo constante. En bytes, porque con str no-ASCII compare_digest tira TypeError."""
    return hmac.compare_digest(a.encode(), b.encode())


def firma_valida(secreto: str, x_signature: str, request_id: str, data_id: str) -> bool:
    """x-signature es "ts=...,v1=..."; v1 es el HMAC-SHA256 de "id:...;request-id:...;ts:...;"."""
    partes = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    # Según Mercado Pago, lo que no vino en el aviso se saca del manifiesto en vez de ir vacío.
    manifiesto = "".join(
        f"{clave}:{valor};" for clave, valor in (("id", data_id), ("request-id", request_id), ("ts", ts)) if valor
    )
    return iguales(hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest(), v1)


@app.get("/")
def salud() -> dict:
    return {"ok": True}


@app.post("/webhook")
async def recibir(
    request: Request,
    x_signature: str = Header(default=""),
    x_request_id: str = Header(default=""),
) -> Response:
    secreto = os.environ.get("MP_WEBHOOK_SECRET", "")
    if not secreto:
        log.warning("AVISO rechazado: falta MP_WEBHOOK_SECRET")
        raise HTTPException(503, "falta configurar MP_WEBHOOK_SECRET")
    try:
        cuerpo = json.loads(await request.body() or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "el cuerpo no es JSON")
    if not isinstance(cuerpo, dict):
        raise HTTPException(400, "el cuerpo no es un objeto JSON")
    data = cuerpo.get("data") if isinstance(cuerpo.get("data"), dict) else {}
    # Mercado Pago manda data.id en la URL y en el cuerpo; la firma usa el de la URL, en minúsculas.
    data_id = str(request.query_params.get("data.id") or data.get("id") or "").lower()
    if not firma_valida(secreto, x_signature, x_request_id, data_id):
        log.warning("AVISO rechazado: firma inválida (data.id=%s)", data_id or "-")
        raise HTTPException(401, "firma inválida")

    aviso = {
        "recibido": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tipo": cuerpo.get("type") or request.query_params.get("type"),
        "accion": cuerpo.get("action"),
        "id": data_id,
        "real": cuerpo.get("live_mode"),  # False en las notificaciones simuladas y de prueba.
        "request_id": x_request_id,  # Si se repite, es un reintento del mismo aviso.
    }
    avisos.append(aviso)
    log.info("AVISO %s %s id=%s real=%s", aviso["tipo"], aviso["accion"], aviso["id"], aviso["real"])
    return Response(status_code=200)


@app.get("/avisos")
def listar(authorization: str = Header(default="")) -> list[dict]:
    """Los últimos avisos, del más nuevo al más viejo. Pide la clave de TIMBRE_CLAVE como Bearer."""
    clave = os.environ.get("TIMBRE_CLAVE", "")
    if not clave or not iguales(authorization, f"Bearer {clave}"):
        raise HTTPException(401, "clave incorrecta")
    return list(reversed(avisos))


if __name__ == "__main__":
    # Railway pasa el puerto en PORT y hay que escuchar en todas las interfaces, no solo en localhost.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
