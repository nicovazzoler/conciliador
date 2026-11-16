"""Leer operaciones de inversión desde capturas de pantalla (Quantfury, Binance) con Claude.

Las capturas viajan a la API de Anthropic. Lo que se lee no se guarda: vuelve como propuesta, la
persona la revisa en la página y recién ahí se carga cada operación.
"""
import base64
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

MODELO = "claude-opus-5-5"
TIPOS_DE_IMAGEN = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAXIMO_CAPTURAS = 10
MAXIMO_BYTES = 5 * 1024 * 1024  # Lo que acepta la API por imagen.

INSTRUCCIONES = """\
Vas a recibir capturas de pantalla de apps de inversión (sobre todo Quantfury, a veces Binance).
Extraé cada operación ejecutada que se vea: una compra o una venta de un activo.

Reglas:
- Una fila por ejecución. Si una posición se abrió y se cerró, son dos operaciones: la apertura y el cierre.
- Una posición en corto (short) se abre con una venta y se cierra con una compra; anotalo en "nota".
- fecha en formato AAAA-MM-DD. Hoy es {hoy}. Si la captura dice "hoy", "ayer" o no muestra el año,
  usá la fecha pasada más reciente que corresponda.
- activo: el símbolo, en mayúsculas y sin el par contra el dólar (BTC, no BTCUSDT; NVDA, no NVDA.US).
- tipo_activo: "cripto" o "accion".
- fuente: "quantfury" o "binance" según la app de la captura; "otra" si no la reconocés.
- moneda: el código de la moneda del precio tal como se ve (USD, BRL, EUR). Las acciones de Brasil, como
  WEGE3, suelen verse en reales (R$): BRL. No conviertas el precio a dólares.
- cantidad, precio (por unidad, en esa moneda) y comision (en dólares, "0" si no se ve) como números con punto
  decimal y sin separador de miles: 94125.5, 0.0412.
- numero_operacion: el identificador de la operación si la captura lo muestra; si no, null.
- Copiá los números tal cual se ven: no los calcules ni los redondees. Si un dato no se lee bien, dejá la
  operación igual y explicalo en "nota".
- Ordenes pendientes, canceladas o que no se ejecutaron no son operaciones: no las incluyas.
- En "avisos" contá lo que no pudiste leer o lo que convenga revisar. Si no hay operaciones, devolvé la lista vacía.
"""


class OperacionLeida(BaseModel):
    fecha: str = Field(description="AAAA-MM-DD")
    activo: str
    tipo_activo: Literal["cripto", "accion"]
    lado: Literal["compra", "venta"]
    fuente: Literal["quantfury", "binance", "otra"]
    moneda: str
    cantidad: str
    precio: str
    comision: str
    numero_operacion: str | None
    nota: str | None


class Lectura(BaseModel):
    operaciones: list[OperacionLeida]
    avisos: list[str]


class CapturaError(Exception):
    """Algo que se le puede decir a la persona tal cual."""


def revisar_captura(contenido: bytes, tipo: str | None) -> None:
    if tipo not in TIPOS_DE_IMAGEN:
        raise CapturaError("solo se pueden leer imágenes PNG, JPG, WEBP o GIF")
    if len(contenido) > MAXIMO_BYTES:
        raise CapturaError("cada captura puede pesar hasta 5 MB")


def leer(capturas: list[tuple[bytes, str]], clave: str, hoy: date | None = None) -> dict:
    """Manda las capturas a Claude y devuelve las operaciones que leyó, sin guardarlas."""
    if not clave:
        raise CapturaError("falta la clave de Anthropic: agregá ANTHROPIC_API_KEY al archivo .env y reiniciá el servidor")
    contenido: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": tipo, "data": base64.standard_b64encode(datos).decode()}}
        for datos, tipo in capturas
    ]
    contenido.append({"type": "text", "text": "Extraé las operaciones de estas capturas."})
    cliente = anthropic.Anthropic(api_key=clave)
    try:
        respuesta = cliente.beta.messages.parse(
            model=MODELO,
            max_tokens=16000,
            # Si el modelo se negara a responder, la API reintenta con otro, sin que haya que hacer nada.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=INSTRUCCIONES.format(hoy=(hoy or date.today()).isoformat()),
            messages=[{"role": "user", "content": contenido}],
            output_format=Lectura,
        )
    except anthropic.AuthenticationError:
        raise CapturaError("la clave de Anthropic no es válida: revisá ANTHROPIC_API_KEY en .env")
    except anthropic.PermissionDeniedError:
        raise CapturaError("la clave de Anthropic no tiene permiso para usar el modelo")
    except anthropic.RateLimitError:
        raise CapturaError("Anthropic pidió esperar un poco: probá de nuevo en un minuto")
    except anthropic.BadRequestError as error:
        raise CapturaError(f"Anthropic no aceptó las capturas: {error.message}")
    except anthropic.APIStatusError as error:
        raise CapturaError(f"Anthropic respondió con un error ({error.status_code}): probá de nuevo más tarde")
    except anthropic.APIConnectionError:
        raise CapturaError("no se pudo conectar con Anthropic: revisá la conexión")
    if respuesta.stop_reason == "refusal" or respuesta.parsed_output is None:
        raise CapturaError("no se pudieron leer las capturas")
    return limpiar(respuesta.parsed_output)


def limpiar(lectura: Lectura) -> dict:
    """Valida lo leído y lo deja listo para la página: números con coma decimal, como se cargan a mano."""
    operaciones, avisos = [], list(lectura.avisos)
    for op in lectura.operaciones:
        try:
            fecha = date.fromisoformat(op.fecha)
            numeros = [Decimal(op.cantidad), Decimal(op.precio), Decimal(op.comision or "0")]
        except (ValueError, InvalidOperation):
            avisos.append(f"Una operación de {op.activo or '?'} no se pudo leer bien y quedó afuera.")
            continue
        cantidad, precio, comision = (abs(n) for n in numeros)
        operaciones.append(
            {
                "fecha": fecha,
                "activo": op.activo.strip().upper(),
                "tipo_activo": op.tipo_activo,
                "lado": op.lado,
                "fuente": "captura" if op.fuente == "otra" else op.fuente,
                "moneda": (op.moneda or "USD").strip().upper()[:3],
                "cantidad": con_coma(cantidad),
                "precio": con_coma(precio),
                "comision": con_coma(comision),
                "numero_operacion": (op.numero_operacion or "").strip() or None,
                "nota": op.nota,
            }
        )
    return {"operaciones": operaciones, "avisos": avisos}


def con_coma(numero: Decimal) -> str:
    # Con coma decimal y sin separador de miles, como se escribe a mano.
    return format(numero.normalize(), "f").replace(".", ",")
