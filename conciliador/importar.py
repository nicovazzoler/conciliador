"""Importa los archivos de una carpeta e informa qué pasó con cada uno."""
from dataclasses import dataclass, field, replace
from pathlib import Path

from conciliador import base, cotizaciones, plan
from conciliador.lectores import mercado_pago, tarjeta_comafi, tarjeta_nacion, tarjetas


@dataclass
class Informe:
    archivo: str
    reconocido: bool = False
    nuevas: int = 0
    repetidas: int = 0
    errores: list[str] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)


def importar_carpeta(carpeta: Path, motor: base.Engine, clave_nacion: str = "") -> list[Informe]:
    archivos = sorted(p for p in carpeta.iterdir() if p.is_file() and not p.name.startswith("."))
    informes = [importar_archivo(archivo, motor, clave_nacion) for archivo in archivos]
    base.aplicar_reglas(motor)
    return informes


def actualizar_cotizaciones(motor: base.Engine, traer=cotizaciones.traer) -> str | None:
    """Trae el dólar y completa los USD. Sin conexión sigue con lo guardado y devuelve un aviso."""
    aviso = None
    try:
        base.guardar_cotizaciones(motor, traer())
    except (OSError, ValueError, KeyError) as error:
        aviso = f"no se pudieron traer las cotizaciones ({type(error).__name__})"
    base.asignar_cotizaciones(motor)
    base.aplicar_reglas(motor)
    return aviso


def importar_archivo(ruta: Path, motor: base.Engine, clave_nacion: str = "") -> Informe:
    informe = Informe(ruta.name)
    if ruta.name == plan.ARCHIVO:
        leido = plan.leer(ruta)
        base.reemplazar_plan(motor, leido)
        informe.reconocido = True
        informe.nuevas = len(leido.fijos) + len(leido.cuotas)
        informe.errores = leido.errores
        return informe
    if ruta.suffix.lower() != ".pdf":
        return informe

    cuenta = mercado_pago.leer(ruta)
    if cuenta is not None:
        informe.reconocido = True
        informe.errores = cuenta.errores
        informe.problemas = mercado_pago.verificar(cuenta)
        informe.nuevas, informe.repetidas = base.guardar_movimientos(
            motor, mercado_pago.FUENTE, (f.fila for f in cuenta.filas)
        )
        return informe

    tarjeta = tarjeta_comafi.leer(ruta) or tarjeta_nacion.leer(ruta, clave_nacion)
    if tarjeta is not None:
        informe.reconocido = True
        informe.errores = tarjeta.errores
        informe.problemas = tarjetas.verificar(tarjeta)
        informe.nuevas, informe.repetidas = base.guardar_movimientos(
            motor, tarjeta.fuente, _con_signo_de_cuenta(tarjeta.filas)
        )
        base.guardar_resumen(motor, tarjeta)
    return informe


def _con_signo_de_cuenta(filas):
    """En la base, negativo es plata que sale. Los resúmenes de tarjeta usan el signo opuesto."""
    return [replace(f, monto_centavos=-f.monto_centavos) for f in filas]
