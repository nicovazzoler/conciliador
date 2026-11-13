"""Lee el resumen en PDF de la tarjeta de Comafi."""
import re
from datetime import date, datetime
from pathlib import Path

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from conciliador.lectores import FilaLeida, a_centavos
from conciliador.lectores.tarjetas import (
    ResumenTarjeta,
    clave_cargo,
    clave_detalle,
    limite_entre_columnas,
    mes_de,
    tipo_de_cargo,
    tipo_de_consumo,
)

FUENTE = "tarjeta_comafi"

MONTO = r"-?[\d.,]+"
EMPIEZA_CON_FECHA = re.compile(r"^\d{2}/\d{2}/\d{4}\s")
CARGO = re.compile(rf"^(\d{{2}}/\d{{2}}/\d{{4}}) (.+?) ({MONTO}|-) ({MONTO}|-)$")
CONSUMO = re.compile(
    rf"^(\d{{2}}/\d{{2}}/\d{{4}}) (.+?)(?: C\.(\d{{2}}/\d{{2}}))? (\d{{4,}}) ({MONTO})$"
)
FIN_DE_CONSUMOS = re.compile(r"Total Consumos de")


def leer(ruta: Path) -> ResumenTarjeta | None:
    """Devuelve el resumen, o None si el archivo no es de la tarjeta de Comafi."""
    try:
        with pdfplumber.open(ruta) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
            if "TARJETA DE CRÉDITO MASTERCARD" not in texto or "BANCO COMAFI" not in texto:
                return None
            resumen = _encabezado(texto)
            _leer_filas(pdf, resumen)
            return resumen
    except PdfminerException:
        return None


def _encabezado(texto: str) -> ResumenTarjeta:
    return ResumenTarjeta(
        fuente=FUENTE,
        numero=_buscar(rf"Resumen Nro\.:(\d+)", texto),
        cierre=_fecha(_buscar(r"\bCierre: (\S+)", texto)),
        vencimiento=_fecha(_buscar(r"\bVencimiento: (\S+)", texto)),
        total_pesos=a_centavos(_buscar(rf"^\$ Total a pagar: ({MONTO})", texto)),
        total_dolares=a_centavos(_buscar(rf"^U\$D Total a pagar: ({MONTO})", texto)),
        saldo_anterior_pesos=a_centavos(_buscar(rf"^\$ ({MONTO}) \$ {MONTO}$", texto)),
        saldo_anterior_dolares=a_centavos(_buscar(rf"^U\$D ({MONTO}) U\$D {MONTO}$", texto)),
    )


def _buscar(patron: str, texto: str) -> str:
    encontrado = re.search(patron, texto, re.MULTILINE)
    if encontrado is None:
        raise ValueError(f"Formato inesperado en el resumen de Comafi: {patron}")
    return encontrado[1]


def _fecha(texto: str) -> date:
    return datetime.strptime(texto, "%d/%m/%Y").date()


def _leer_filas(pdf, resumen: ResumenTarjeta) -> None:
    seccion = None
    limite = 0.0
    for pagina in pdf.pages:
        for linea in pagina.extract_text_lines():
            texto = linea["text"].strip()
            if texto == "Consolidado":
                seccion = "consolidado"
            elif texto.startswith("Detalle de consumo"):
                seccion = "detalle"
            elif seccion == "detalle" and texto.startswith("Fecha Detalle"):
                limite = limite_entre_columnas(pagina, linea["top"], "Pesos", "Dólares")
            elif FIN_DE_CONSUMOS.search(texto):
                seccion = None
            elif seccion and EMPIEZA_CON_FECHA.match(texto):
                if seccion == "consolidado":
                    _leer_cargo(texto, resumen)
                else:
                    _leer_consumo(texto, linea["x1"] > limite, resumen)


def _leer_cargo(texto: str, resumen: ResumenTarjeta) -> None:
    fila = CARGO.match(texto)
    if fila is None:
        resumen.errores.append(f"fila ilegible: {texto}")
        return
    fecha, concepto, pesos, dolares = _fecha(fila[1]), fila[2], fila[3], fila[4]
    tipo = tipo_de_cargo(concepto)
    mes = mes_de(fecha) if tipo == "pago" else mes_de(resumen.vencimiento)
    for moneda, importe in (("ARS", pesos), ("USD", dolares)):
        if importe != "-":
            resumen.filas.append(
                FilaLeida(
                    numero_operacion=clave_cargo(resumen.numero, len(resumen.filas), concepto),
                    fecha=fecha,
                    descripcion=concepto,
                    monto_centavos=a_centavos(importe),
                    moneda=moneda,
                    tipo=tipo,
                    mes=mes,
                )
            )


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
