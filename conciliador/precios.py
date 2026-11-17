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


FALLAS = (OSError, ValueError, KeyError, IndexError, TypeError)


def _grafico(activo: str, consulta: str, traer: Callable[[str], dict]) -> dict:
    """El gráfico de Yahoo del activo; si no existe tal cual, el del símbolo que encuentra la búsqueda."""
    try:
        return traer(f"{YAHOO}/v8/finance/chart/{urllib.parse.quote(activo)}?{consulta}")["chart"]["result"][0]
    except FALLAS:
        simbolo = _buscar(activo, traer)
        return traer(f"{YAHOO}/v8/finance/chart/{urllib.parse.quote(simbolo)}?{consulta}")["chart"]["result"][0]


def accion(activo: str, traer: Callable[[str], dict] = _json) -> Decimal:
    """El precio en USD. Si cotiza en otra moneda, se convierte con el cambio de hoy."""
    meta = _grafico(activo.upper(), "range=1d&interval=1d", traer)["meta"]
    return a_dolares(Decimal(str(meta["regularMarketPrice"])), meta["currency"], traer)


def extremos(activo: str, tipo: str, traer: Callable[[str], dict] = _json) -> tuple[Decimal, Decimal, str]:
    """El mínimo y el máximo de hoy, en la moneda en que cotiza: para saber si tocó un stop loss o un take profit."""
    activo = activo.upper()
    if tipo == "cripto":
        datos = traer(f"https://api.binance.com/api/v3/ticker/24hr?symbol={activo}USDT")
        return Decimal(datos["lowPrice"]), Decimal(datos["highPrice"]), "USD"
    meta = _grafico(activo, "range=1d&interval=1d", traer)["meta"]
    bajo, alto, moneda = Decimal(str(meta["regularMarketDayLow"])), Decimal(str(meta["regularMarketDayHigh"])), meta["currency"]
    if moneda == "GBp":
        bajo, alto, moneda = bajo / 100, alto / 100, "GBP"
    return bajo, alto, moneda


def _segundos(dia: date) -> int:
    return int(datetime.combine(dia, datetime.min.time(), timezone.utc).timestamp())


def _serie(resultado: dict) -> dict[date, Decimal]:
    fechas = [datetime.fromtimestamp(t, timezone.utc).date() for t in resultado.get("timestamp", [])]
    cierres = resultado["indicators"]["quote"][0]["close"]
    return {f: Decimal(str(c)) for f, c in zip(fechas, cierres) if c is not None}


def cierres(activo: str, tipo: str, desde: date, traer: Callable[[str], dict] = _json) -> dict[date, Decimal]:
    """El cierre de cada día desde `desde`, en USD. Lo que cotiza en otra moneda se convierte día por día."""
    activo = activo.upper()
    if tipo == "cripto":
        if activo in ("USDT", "USDC", "USD"):
            return {desde: Decimal(1)}
        velas = traer(f"https://api.binance.com/api/v3/klines?symbol={activo}USDT&interval=1d"
                      f"&startTime={_segundos(desde) * 1000}&limit=1000")
        return {datetime.fromtimestamp(v[0] / 1000, timezone.utc).date(): Decimal(str(v[4])) for v in velas}
    consulta = f"period1={_segundos(desde)}&period2={_segundos(date.today() + timedelta(days=1))}&interval=1d"
    resultado = _grafico(activo, consulta, traer)
    serie, moneda = _serie(resultado), resultado["meta"]["currency"]
    if moneda == "GBp":
        serie, moneda = {f: c / 100 for f, c in serie.items()}, "GBP"
    if moneda == "USD":
        return serie
    cambio = _serie(traer(f"{YAHOO}/v8/finance/chart/{moneda}USD=X?{consulta}")["chart"]["result"][0])
    return {f: c * v for f, c in serie.items() if (v := ultimo(cambio, f)) is not None}


def ultimo(serie: dict[date, Decimal], dia: date) -> Decimal | None:
    """El valor de ese día o el último anterior: un fin de semana usa el viernes."""
    anteriores = [f for f in serie if f <= dia]
    return serie[max(anteriores)] if anteriores else None


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
