"""Lectura de la API de Mercado Pago con el access token de la cuenta. Solo pedidos GET.

El token sale de MP_ACCESS_TOKEN (entorno o .env) y nunca se muestra ni se guarda.
Los montos llegan como Decimal (parse_float) y se pasan a centavos sin tocar float.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from conciliador.manual import importe

API = "https://api.mercadopago.com"
ARGENTINA = timezone(timedelta(hours=-3))  # La API devuelve las fechas en GMT-04.
POR_PAGINA = 50
MAXIMO = 1000  # Por rol. Para una prueba sobra; si se llega, se avisa.

Pedir = Callable[[str, dict], dict]


class ErrorMP(Exception):
    """La API respondió con error. El mensaje es para mostrar y nunca incluye el token."""


@dataclass(frozen=True)
class PagoLeido:
    id: str
    fecha: datetime  # Creación del pago, en hora argentina.
    rol: str  # "cobrado" (la cuenta es collector) o "pagado" (la cuenta es payer).
    estado: str
    tipo: str  # operation_type/payment_type_id, por ejemplo money_transfer/account_money.
    monto_centavos: int  # Positivo si entra, negativo si sale.
    moneda: str
    detalle: str


def pedidor(token: str) -> Pedir:
    """Una función que hace GET a la API con el token en el header."""

    def pedir(ruta: str, parametros: dict) -> dict:
        url = f"{API}{ruta}" + (f"?{urllib.parse.urlencode(parametros)}" if parametros else "")
        pedido = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": "conciliador"})
        try:
            with urllib.request.urlopen(pedido, timeout=20) as respuesta:
                return json.load(respuesta, parse_float=Decimal)
        except urllib.error.HTTPError as error:
            raise ErrorMP(_explicar(error.code, error.read())) from None
        except urllib.error.URLError as error:
            raise ErrorMP(f"no se pudo conectar con Mercado Pago ({error.reason})") from None

    return pedir


def _explicar(codigo: int, cuerpo: bytes) -> str:
    try:
        mensaje = str(json.loads(cuerpo).get("message", ""))
    except (ValueError, AttributeError):
        mensaje = ""
    if codigo == 401:
        return "Mercado Pago no aceptó el token (401). Tiene que ser el access token de producción."
    return f"Mercado Pago respondió {codigo}. {mensaje}".strip()


def pagos_recientes(pedir: Pedir, dias: int) -> tuple[str, list[PagoLeido], list[dict]]:
    """Lo cobrado y lo pagado en los últimos `dias`, del más nuevo al más viejo.

    Devuelve el id de la cuenta, los pagos leídos y las respuestas crudas, para guardarlas si se pide.
    Una transferencia a uno mismo puede aparecer dos veces: como cobrada y como pagada.
    """
    if not 1 <= dias <= 364:
        raise ValueError("se pueden pedir entre 1 y 364 días: la API no acepta rangos de un año o más")
    cuenta = str(pedir("/users/me", {})["id"])
    filtros = {"range": "date_created", "begin_date": f"NOW-{dias}DAYS", "end_date": "NOW",
               "sort": "date_created", "criteria": "desc"}
    pagos, crudos = [], []
    for rol, filtro in (("cobrado", "collector.id"), ("pagado", "payer.id")):
        for crudo in _buscar(pedir, {**filtros, filtro: cuenta}):
            crudos.append({"rol": rol, **crudo})
            pagos.append(_leer(crudo, rol))
    return cuenta, sorted(pagos, key=lambda p: p.fecha, reverse=True), crudos


def _buscar(pedir: Pedir, filtros: dict) -> list[dict]:
    resultados: list[dict] = []
    while len(resultados) < MAXIMO:
        pagina = pedir("/v1/payments/search", {**filtros, "limit": POR_PAGINA, "offset": len(resultados)})
        lote = pagina.get("results") or []
        resultados += lote
        if len(lote) < POR_PAGINA or len(resultados) >= (pagina.get("paging") or {}).get("total", 0):
            break
    return resultados


def _leer(crudo: dict, rol: str) -> PagoLeido:
    monto = int((Decimal(crudo.get("transaction_amount") or 0) * 100).quantize(Decimal(1), ROUND_HALF_UP))
    return PagoLeido(
        id=str(crudo["id"]),
        fecha=datetime.fromisoformat(crudo["date_created"]).astimezone(ARGENTINA),
        rol=rol,
        estado=crudo.get("status") or "?",
        tipo=f"{crudo.get('operation_type') or '?'}/{crudo.get('payment_type_id') or '?'}",
        monto_centavos=monto if rol == "cobrado" else -monto,
        moneda=crudo.get("currency_id") or "?",
        detalle=_detalle(crudo, rol),
    )


def _detalle(crudo: dict, rol: str) -> str:
    """Quién mandó, si es un cobro; si no, la descripción que trae el pago."""
    descripcion = crudo.get("description") or ""
    if rol == "pagado":
        return descripcion
    payer = crudo.get("payer") or {}
    documento = payer.get("identification") or {}
    quien = " ".join(filter(None, (payer.get("first_name"), payer.get("last_name"))))
    quien = quien or " ".join(filter(None, (documento.get("type"), documento.get("number"))))
    return " · ".join(filter(None, (f"de {quien}" if quien else "", descripcion)))


def texto(cuenta: str, pagos: list[PagoLeido], dias: int, en_base: set[str] | None) -> str:
    """Solo presentación. `en_base` son los números de operación de Mercado Pago ya importados del PDF."""
    periodo = "el último día" if dias == 1 else f"los últimos {dias} días"
    lineas = [f"Cuenta {cuenta}: {len(pagos)} pagos creados en {periodo}.", ""]
    if not pagos:
        lineas.append("La API no devolvió nada. Lo que no aparece acá no se puede seguir con esta búsqueda.")
    for p in pagos:
        simbolo = "U$D" if p.moneda == "USD" else "$"
        linea = (
            f"{p.fecha:%d/%m %H:%M}  {p.id:>13}  {p.rol:<7}  {p.estado:<9}  {p.tipo:<32} "
            f"{'+' if p.monto_centavos > 0 else '-'} {simbolo} {importe(p.monto_centavos):>11}  {p.detalle}"
        )
        if en_base is not None:
            linea += "  [en la base]" if p.id in en_base else "  [no está en la base]"
        lineas.append(linea.rstrip())
    if pagos:
        por_tipo = Counter(f"{p.rol} {p.tipo}" for p in pagos)
        lineas += ["", "Por tipo:", *(f"  {cantidad:>3}  {tipo}" for tipo, cantidad in por_tipo.most_common())]
    if any(cantidad >= MAXIMO for cantidad in Counter(p.rol for p in pagos).values()):
        lineas.append(f"\nAVISO: se cortó en {MAXIMO} pagos por rol. Pedí menos días.")
    return "\n".join(lineas)
