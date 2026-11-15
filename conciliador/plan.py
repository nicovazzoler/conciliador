"""Lee plan.csv, el archivo con los fijos y las cuotas planificados."""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

ARCHIVO = "plan.csv"
COLUMNAS = ("tipo", "concepto", "texto", "monto", "moneda", "dia", "cuotas", "primer_mes")
# Opcional: un plan.csv sin esta columna sigue funcionando, y lo suyo queda sin categoría.
CATEGORIA = "categoria"
MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")  # 2026-13 no es un mes.


@dataclass(frozen=True)
class FijoPlan:
    concepto: str
    texto: str
    monto_centavos: int
    moneda: str
    dia: int | None
    categoria: str | None = None


@dataclass(frozen=True)
class CuotaPlan:
    concepto: str
    texto: str
    monto_centavos: int
    moneda: str
    cantidad: int
    primer_mes: str
    categoria: str | None = None


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
    categoria = (fila.get(CATEGORIA) or "").strip() or None

    if tipo == "fijo":
        dia = fila["dia"].strip()
        plan.fijos.append(FijoPlan(concepto, texto, monto, moneda, int(dia) if dia else None, categoria))
    elif tipo == "cuota":
        primer_mes = fila["primer_mes"].strip()
        if not MES.match(primer_mes):
            raise ValueError(f"primer_mes inválido: {primer_mes!r}")
        plan.cuotas.append(
            CuotaPlan(concepto, texto, monto, moneda, int(fila["cuotas"]), primer_mes, categoria)
        )
    else:
        raise ValueError(f"tipo inválido: {tipo!r}")


def fijo_desde(concepto: str, texto: str, monto: str, moneda: str, dia: int | None, categoria: str | None) -> FijoPlan:
    """Valida un fijo cargado desde la app, con las mismas reglas que una fila de plan.csv."""
    concepto, texto, moneda = concepto.strip(), texto.strip(), moneda.strip().upper()
    _validar_comunes(concepto, texto, moneda)
    if dia is not None and not 1 <= dia <= 31:
        raise ValueError("el día tiene que estar entre 1 y 31")
    return FijoPlan(concepto, texto, _monto_positivo(monto), moneda, dia, (categoria or "").strip() or None)


def cuota_desde(
    concepto: str, texto: str, monto: str, moneda: str, cantidad: int, primer_mes: str, categoria: str | None
) -> CuotaPlan:
    """Valida una cuota cargada desde la app, con las mismas reglas que una fila de plan.csv."""
    concepto, texto, moneda, primer_mes = concepto.strip(), texto.strip(), moneda.strip().upper(), primer_mes.strip()
    _validar_comunes(concepto, texto, moneda)
    if not 1 <= cantidad <= 120:
        raise ValueError("la cantidad de cuotas tiene que estar entre 1 y 120")
    if not MES.match(primer_mes):
        raise ValueError(f"primer mes inválido: {primer_mes!r}. Usá AAAA-MM")
    return CuotaPlan(concepto, texto, _monto_positivo(monto), moneda, cantidad, primer_mes, (categoria or "").strip() or None)


def a_csv(fijos: list[FijoPlan], cuotas: list[CuotaPlan]) -> str:
    """El plan como plan.csv, para guardarlo o editarlo en Excel."""
    filas = [";".join([*COLUMNAS, CATEGORIA])]
    for f in fijos:
        filas.append(";".join(["fijo", f.concepto, f.texto, _monto_texto(f.monto_centavos), f.moneda,
                               "" if f.dia is None else str(f.dia), "", "", f.categoria or ""]))
    for c in cuotas:
        filas.append(";".join(["cuota", c.concepto, c.texto, _monto_texto(c.monto_centavos), c.moneda,
                               "", str(c.cantidad), c.primer_mes, c.categoria or ""]))
    return "\n".join(filas) + "\n"


def _validar_comunes(concepto: str, texto: str, moneda: str) -> None:
    if not concepto or not texto:
        raise ValueError("el concepto y el texto que se busca son obligatorios")
    if ";" in concepto or ";" in texto:
        raise ValueError("el concepto y el texto no pueden tener punto y coma")
    if moneda not in ("ARS", "USD"):
        raise ValueError(f"moneda inválida: {moneda!r}")


def _monto_positivo(texto: str) -> int:
    centavos = monto_a_centavos(texto)
    if centavos <= 0:
        raise ValueError("el monto tiene que ser mayor que 0")
    return centavos


def _monto_texto(centavos: int) -> str:
    return f"{centavos // 100},{centavos % 100:02d}"
