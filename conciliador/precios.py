"""Precios actuales: cripto desde Binance y acciones desde Yahoo Finance. Nunca se inventa uno.

Binance tiene una API pública. Yahoo no tiene API oficial: su endpoint de gráficos es el que usan
casi todas las herramientas gratuitas, pero puede cambiar. Si falla, el activo queda sin precio.
"""
import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
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


YAHOO = "https://query1.finance.yahoo.com"


def _cotizacion(simbolo: str, traer: Callable[[str], dict]) -> tuple[Decimal, str]:
    datos = traer(f"{YAHOO}/v8/finance/chart/{urllib.parse.quote(simbolo)}?range=1d&interval=1d")
    meta = datos["chart"]["result"][0]["meta"]
    return Decimal(str(meta["regularMarketPrice"])), meta["currency"]


def _buscar(activo: str, traer: Callable[[str], dict]) -> str:
    """WEGE3 no existe en Yahoo como tal: es WEGE3.SA, en la bolsa de San Pablo. Se busca el símbolo."""
    datos = traer(f"{YAHOO}/v1/finance/search?q={urllib.parse.quote(activo)}&quotesCount=5&newsCount=0")
    for cotizacion in datos.get("quotes", []):
        simbolo = cotizacion.get("symbol", "")
        if cotizacion.get("quoteType") in ("EQUITY", "ETF") and simbolo.split(".")[0] == activo:
            return simbolo
    raise ValueError(f"{activo} no aparece en Yahoo")


def a_dolares(precio: Decimal, moneda: str, traer: Callable[[str], dict]) -> Decimal:
    """Convierte con el cambio de hoy. Londres cotiza en peniques (GBp): se pasa a libras."""
    if moneda == "GBp":
        precio, moneda = precio / 100, "GBP"
    if moneda == "USD":
        return precio
    cambio, _ = _cotizacion(f"{moneda}USD=X", traer)
    return precio * cambio


def accion(activo: str, traer: Callable[[str], dict] = _json) -> Decimal:
    """El precio en USD. Si cotiza en otra moneda, se convierte con el cambio de hoy."""
    activo = activo.upper()
    try:
        precio, moneda = _cotizacion(activo, traer)
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        precio, moneda = _cotizacion(_buscar(activo, traer), traer)
    return a_dolares(precio, moneda, traer)


def cambio(moneda: str, dia: date, traer: Callable[[str], dict] = _json) -> Decimal:
    """Cuántos USD valía una unidad de `moneda` ese día: el último cierre hasta esa fecha."""
    if moneda == "USD":
        return Decimal(1)
    desde = int(datetime.combine(dia - timedelta(days=7), datetime.min.time(), timezone.utc).timestamp())
    hasta = int(datetime.combine(dia + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp())
    datos = traer(f"{YAHOO}/v8/finance/chart/{moneda}USD=X?period1={desde}&period2={hasta}&interval=1d")
    resultado = datos["chart"]["result"][0]
    cierres = [c for c in resultado["indicators"]["quote"][0]["close"] if c is not None]
    if not cierres:
        raise ValueError(f"no hay cambio de {moneda} para {dia}")
    return Decimal(str(cierres[-1]))


def actualizar(activos: dict[str, str], traer: Callable[[str], dict] = _json) -> tuple[dict[str, Decimal], list[str]]:
    """Recibe {activo: tipo} y devuelve ({activo: precio}, errores). Uno que falla no frena a los demás."""
    precios, errores = {}, []
    for activo, tipo in activos.items():
        try:
            precios[activo] = (cripto if tipo == "cripto" else accion)(activo, traer)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
            errores.append(f"{activo}: sin precio ({type(error).__name__})")
    return precios, errores
