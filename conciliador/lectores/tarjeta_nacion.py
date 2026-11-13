"""Lee el resumen en PDF de la tarjeta de Banco Nación, que viene con clave."""
import re
from datetime import date
from pathlib import Path

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from conciliador.lectores import FilaLeida, a_centavos
from conciliador.lectores.tarjetas import (
    ResumenTarjeta,
    clave_detalle,
    limite_entre_columnas,
    mes_de,
    tipo_de_consumo,
)

FUENTE = "tarjeta_nacion"

MESES = "Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split()
MONTO = r"-?[\d.,]+"
FECHA = r"\d{2}-[A-Z][a-z]{2}-\d{2}"
EMPIEZA_CON_FECHA = re.compile(rf"^{FECHA}\s")
CONSUMO = re.compile(rf"^({FECHA}) (.+?)(?: (\d{{2}}/\d{{2}}))? (\d{{5,}}) ({MONTO})$")


def leer(ruta: Path, clave: str = "") -> ResumenTarjeta | None:
    """Devuelve el resumen, o None si el archivo no es de Nación o no abre con esa clave."""
    try:
        with pdfplumber.open(ruta, password=clave) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
            if "DETALLES DEL MES" not in texto or "CUIT Entidad 30-50001091-2" not in texto:
                return None
            resumen = _encabezado(texto)
            _leer_filas(pdf, resumen)
            return resumen
    except PdfminerException:
        return None


def _encabezado(texto: str) -> ResumenTarjeta:
    pendiente = re.search(rf"^SALDO PENDIENTE ({MONTO}) ({MONTO})$", texto, re.MULTILINE)
    actual = re.search(rf"^SALDO ACTUAL ({MONTO}) ({MONTO})$", texto, re.MULTILINE)
    if pendiente is None or actual is None:
        raise ValueError("Formato inesperado en el resumen de Nación: faltan los saldos")
    return ResumenTarjeta(
        fuente=FUENTE,
        numero=_buscar(r"N° de Resumen (\d+)", texto),
        cierre=_fecha(_buscar(rf"Estado de cuenta al : ({FECHA})", texto)),
        vencimiento=_fecha(_buscar(rf"Vencimiento actual : ({FECHA})", texto)),
        total_pesos=a_centavos(actual[1]),
        total_dolares=a_centavos(actual[2]),
        saldo_anterior_pesos=a_centavos(pendiente[1]),
        saldo_anterior_dolares=a_centavos(pendiente[2]),
    )


def _buscar(patron: str, texto: str) -> str:
    encontrado = re.search(patron, texto)
    if encontrado is None:
        raise ValueError(f"Formato inesperado en el resumen de Nación: {patron}")
    return encontrado[1]


def _fecha(texto: str) -> date:
    dia, mes, anio = texto.split("-")
    return date(2000 + int(anio), MESES.index(mes) + 1, int(dia))


def _leer_filas(pdf, resumen: ResumenTarjeta) -> None:
    dentro = False
    limite = 0.0
    for pagina in pdf.pages:
        for linea in pagina.extract_text_lines():
            texto = linea["text"].strip()
            if texto.startswith("DETALLES DEL MES"):
                dentro = True
                limite = limite_entre_columnas(pagina, linea["top"], "PESOS", "DOLAR")
            elif texto.startswith("TOTAL TITULAR"):
                dentro = False
            elif dentro and EMPIEZA_CON_FECHA.match(texto):
                _leer_consumo(texto, linea["x1"] > limite, resumen)


def _leer_consumo(texto: str, en_dolares: bool, resumen: ResumenTarjeta) -> None:
    fila = CONSUMO.match(texto)
    if fila is None:
        resumen.errores.append(f"fila ilegible: {texto}")
        return
    fecha, cuota, monto = _fecha(fila[1]), fila[3], a_centavos(fila[5])
    resumen.filas.append(
        FilaLeida(
            numero_operacion=clave_detalle(fila[4], cuota, fecha),
            fecha=fecha,
            descripcion=fila[2],
            monto_centavos=monto,
            moneda="USD" if en_dolares else "ARS",
            tipo=tipo_de_consumo(monto, cuota is not None),
            mes=mes_de(resumen.vencimiento) if cuota else mes_de(fecha),
            cuota=cuota,
            fecha_cotizacion=resumen.vencimiento if cuota else None,
        )
    )
