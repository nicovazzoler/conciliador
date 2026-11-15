"""Precios actuales: cripto desde Binance y acciones desde Yahoo Finance. Nunca se inventa uno.

Binance tiene una API pública. Yahoo no tiene API oficial: su endpoint de gráficos es el que usan
casi todas las herramientas gratuitas, pero puede cambiar. Si falla, el activo queda sin precio.
"""
import json
import urllib.request
from collections.abc import Callable
from decimal import Decimal

AGENTE = "conciliador"


def _json(url: str) -> dict:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=15) as respuesta:
        return json.load(respuesta)


def cripto(activo: str, traer: Callable[[str], dict] = _json) -> Decimal:
    """BTC → precio de BTCUSDT. USDT vale 1 por definición."""
    if activo.upper() in ("USDT", "USDC", "USD"):
        return Decimal(1)
    datos = traer(f"https://api.binance.com/api/v3/ticker/price?symbol={activo.upper()}USDT")
    return Decimal(datos["price"])


def accion(activo: str, traer: Callable[[str], dict] = _json) -> Decimal:
    datos = traer(f"https://query1.finance.yahoo.com/v8/finance/chart/{activo.upper()}?range=1d&interval=1d")
    meta = datos["chart"]["result"][0]["meta"]
    if meta.get("currency") != "USD":
        raise ValueError(f"{activo} cotiza en {meta.get('currency')}, no en USD")
    return Decimal(str(meta["regularMarketPrice"]))


def actualizar(activos: dict[str, str], traer: Callable[[str], dict] = _json) -> tuple[dict[str, Decimal], list[str]]:
    """Recibe {activo: tipo} y devuelve ({activo: precio}, errores). Uno que falla no frena a los demás."""
    precios, errores = {}, []
    for activo, tipo in activos.items():
        try:
            precios[activo] = (cripto if tipo == "cripto" else accion)(activo, traer)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
            errores.append(f"{activo}: sin precio ({type(error).__name__})")
    return precios, errores
