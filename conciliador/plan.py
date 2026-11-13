"""Lee plan.csv, el archivo con los fijos y las cuotas planificados."""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

ARCHIVO = "plan.csv"
COLUMNAS = ("tipo", "concepto", "texto", "monto", "moneda", "dia", "cuotas", "primer_mes")
MES = re.compile(r"^\d{4}-\d{2}$")


@dataclass(frozen=True)
class FijoPlan:
    concepto: str
    texto: str
    monto_centavos: int
    moneda: str
    dia: int | None


@dataclass(frozen=True)
class CuotaPlan:
    concepto: str
    texto: str
    monto_centavos: int
    moneda: str
    cantidad: int
    primer_mes: str


@dataclass
class PlanLeido:
    fijos: list[FijoPlan] = field(default_factory=list)
    cuotas: list[CuotaPlan] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def leer(ruta: Path) -> PlanLeido:
    plan = PlanLeido()
    contenido = _texto(ruta)
    primera = contenido.split("\n", 1)[0]
    separador = ";" if ";" in primera else ","
    filas = csv.DictReader(contenido.splitlines(), delimiter=separador)
    faltantes = set(COLUMNAS) - set(filas.fieldnames or [])
    if faltantes:
        plan.errores.append(f"faltan columnas: {', '.join(sorted(faltantes))}")
        return plan

    conceptos: set[str] = set()
    for numero, fila in enumerate(filas, start=2):
        try:
            concepto = (fila["concepto"] or "").strip()
            if concepto in conceptos:
                raise ValueError(f"concepto repetido: {concepto!r}")
            _agregar(fila, plan)
            conceptos.add(concepto)
        except (ValueError, ArithmeticError) as error:
            plan.errores.append(f"fila {numero}: {error}")
    return plan


def monto_a_centavos(texto: str) -> int:
    """Acepta 1234,56, 1.234,56 y 1234.56, porque Excel puede guardar cualquiera."""
    limpio = texto.strip()
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif re.search(r"\.\d{3}(\.|$)", limpio):
        limpio = limpio.replace(".", "")
    entero, _, decimales = limpio.partition(".")
    if not re.fullmatch(r"\d+", entero) or not re.fullmatch(r"\d{0,2}", decimales):
        raise ValueError(f"monto inválido: {texto!r}")
    return int(entero) * 100 + int(decimales.ljust(2, "0") or 0)


def _texto(ruta: Path) -> str:
    try:
        return ruta.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return ruta.read_text(encoding="latin-1")


def _agregar(fila: dict, plan: PlanLeido) -> None:
    tipo = fila["tipo"].strip().lower()
    concepto = fila["concepto"].strip()
    texto = fila["texto"].strip()
    moneda = fila["moneda"].strip().upper()
    if not concepto or not texto:
        raise ValueError("concepto y texto son obligatorios")
    if moneda not in ("ARS", "USD"):
        raise ValueError(f"moneda inválida: {moneda!r}")
    monto = monto_a_centavos(fila["monto"])

    if tipo == "fijo":
        dia = fila["dia"].strip()
        plan.fijos.append(FijoPlan(concepto, texto, monto, moneda, int(dia) if dia else None))
    elif tipo == "cuota":
        primer_mes = fila["primer_mes"].strip()
        if not MES.match(primer_mes):
            raise ValueError(f"primer_mes inválido: {primer_mes!r}")
        plan.cuotas.append(
            CuotaPlan(concepto, texto, monto, moneda, int(fila["cuotas"]), primer_mes)
        )
    else:
        raise ValueError(f"tipo inválido: {tipo!r}")
