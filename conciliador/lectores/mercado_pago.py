"""Lee el resumen de cuenta en PDF de Mercado Pago."""
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from conciliador import clasificar
from conciliador.lectores import FilaLeida, a_centavos

FUENTE = "mercado_pago"

MONTO = r"(-?[\d.,]+)"
FILA = re.compile(
    rf"^(\d{{2}})-(\d{{2}})-(\d{{4}})\s*(.*?)\s*(\d{{10,}})\s+\$\s*{MONTO}\s+\$\s*{MONTO}$"
)
EMPIEZA_CON_FECHA = re.compile(r"^\d{2}-\d{2}-\d{4}")
PIE_DE_PAGINA = re.compile(r"^\d+/\d+$|^Fecha de generación")


@dataclass
class FilaMP:
    fila: FilaLeida
    saldo_centavos: int


@dataclass
class ResumenMP:
    titular: str
    saldo_inicial: int
    saldo_final: int
    entradas: int
    salidas: int
    filas: list[FilaMP] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def leer(ruta: Path) -> ResumenMP | None:
    """Devuelve el resumen, o None si el archivo no es de Mercado Pago."""
    try:
        with pdfplumber.open(ruta) as pdf:
            encabezado = pdf.pages[0].extract_text() or ""
            if "RESUMEN DE CUENTA EN PESOS" not in encabezado or "CVU:" not in encabezado:
                return None
            resumen = ResumenMP(
                titular=encabezado.splitlines()[1],
                saldo_inicial=_total(encabezado, "Saldo inicial"),
                saldo_final=_total(encabezado, "Saldo final"),
                entradas=_total(encabezado, "Entradas"),
                salidas=_total(encabezado, "Salidas"),
            )
            for pagina in pdf.pages:
                _leer_pagina(pagina.extract_text_lines(), resumen)
            return resumen
    except PdfminerException:
        return None


def verificar(resumen: ResumenMP) -> list[str]:
    """Compara lo leído contra los totales del PDF. Una fila perdida no da error por sí sola."""
    problemas = []
    montos = [f.fila.monto_centavos for f in resumen.filas]
    if sum(m for m in montos if m > 0) != resumen.entradas:
        problemas.append("las entradas no coinciden con el total del resumen")
    if sum(m for m in montos if m < 0) != resumen.salidas:
        problemas.append("las salidas no coinciden con el total del resumen")

    saldo = resumen.saldo_inicial
    for f in resumen.filas:
        saldo += f.fila.monto_centavos
        if saldo != f.saldo_centavos:
            problemas.append(f"el saldo no cierra en la operación {f.fila.numero_operacion}")
            saldo = f.saldo_centavos
    if saldo != resumen.saldo_final:
        problemas.append("el saldo final no coincide con el resumen")
    return problemas


def _total(texto: str, etiqueta: str) -> int:
    encontrado = re.search(rf"{etiqueta}: \$ {MONTO}", texto)
    if encontrado is None:
        raise ValueError(f"No se encontró '{etiqueta}' en el resumen")
    return a_centavos(encontrado[1])


def _leer_pagina(lineas: list[dict], resumen: ResumenMP) -> None:
    tabla = _lineas_de_la_tabla(lineas)
    anclas = [l for l in tabla if FILA.match(l["text"])]
    sueltas = []
    for linea in tabla:
        if FILA.match(linea["text"]):
            continue
        if EMPIEZA_CON_FECHA.match(linea["text"]) or not anclas:
            resumen.errores.append(f"fila ilegible: {linea['text']}")
        else:
            sueltas.append(linea)

    # Una descripción larga se parte en líneas arriba y abajo de la fila con los números.
    # Cada línea suelta pertenece a la fila que tiene más cerca.
    agregadas: dict[int, list[dict]] = {id(a): [] for a in anclas}
    for linea in sueltas:
        cercana = min(anclas, key=lambda a: abs(a["top"] - linea["top"]))
        agregadas[id(cercana)].append(linea)

    for ancla in anclas:
        dia, mes, anio, centro, numero, valor, saldo = FILA.match(ancla["text"]).groups()
        arriba = [l["text"] for l in agregadas[id(ancla)] if l["top"] < ancla["top"]]
        abajo = [l["text"] for l in agregadas[id(ancla)] if l["top"] > ancla["top"]]
        descripcion = " ".join(p for p in [*arriba, centro, *abajo] if p)
        monto = a_centavos(valor)
        resumen.filas.append(
            FilaMP(
                fila=FilaLeida(
                    numero_operacion=numero,
                    fecha=date(int(anio), int(mes), int(dia)),
                    descripcion=descripcion,
                    monto_centavos=monto,
                    tipo=clasificar.tipo_mercado_pago(descripcion, monto, resumen.titular),
                ),
                saldo_centavos=a_centavos(saldo),
            )
        )


def _lineas_de_la_tabla(lineas: list[dict]) -> list[dict]:
    """Se queda con lo que está entre el encabezado de la tabla y el pie de página."""
    tabla = []
    dentro = False
    for linea in lineas:
        texto = linea["text"].strip()
        if texto == "operación":
            dentro = True
        elif PIE_DE_PAGINA.match(texto):
            break
        elif dentro:
            tabla.append({**linea, "text": texto})
    return tabla
