"""Único módulo que accede a la base. Ver la decisión D3 en PLAN.md."""
import shutil
from types import SimpleNamespace
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import (
    Date, String, UniqueConstraint, create_engine, delete, func, inspect, select, text,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from conciliador import clasificar, cotizaciones
from conciliador.lectores import FilaLeida
from conciliador.lectores.tarjetas import ResumenTarjeta
from conciliador.plan import PlanLeido


class Base(DeclarativeBase):
    pass


class Movimiento(Base):
    __tablename__ = "movimientos"
    __table_args__ = (UniqueConstraint("fuente", "numero_operacion"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente: Mapped[str] = mapped_column(String(30))
    numero_operacion: Mapped[str] = mapped_column(String(80))
    fecha: Mapped[date] = mapped_column(Date)
    descripcion: Mapped[str] = mapped_column(String(200))
    monto_centavos: Mapped[int]
    moneda: Mapped[str] = mapped_column(String(3))
    tipo: Mapped[str] = mapped_column(String(20))
    mes: Mapped[str] = mapped_column(String(7))
    cuota: Mapped[str | None] = mapped_column(String(5))
    categoria: Mapped[str | None] = mapped_column(String(60))
    categoria_manual: Mapped[bool] = mapped_column(default=False)
    pendiente: Mapped[bool] = mapped_column(default=False)
    fecha_cotizacion: Mapped[date] = mapped_column(Date)
    cotizacion_centavos: Mapped[int | None]
    usd_centavos: Mapped[int | None]
    plan_concepto: Mapped[str | None] = mapped_column(String(60))  # Fijo o cuota del plan.
    medio: Mapped[str | None] = mapped_column(String(15))  # Solo en lo cargado a mano.
    tarjeta: Mapped[str | None] = mapped_column(String(30))  # Solo en los pagos de tarjeta.


class Resumen(Base):
    __tablename__ = "resumenes"
    __table_args__ = (UniqueConstraint("tarjeta", "numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tarjeta: Mapped[str] = mapped_column(String(30))
    numero: Mapped[str] = mapped_column(String(30))
    cierre: Mapped[date] = mapped_column(Date)
    vencimiento: Mapped[date] = mapped_column(Date)
    total_pesos_centavos: Mapped[int]
    total_dolares_centavos: Mapped[int]
    percepcion_centavos: Mapped[int]


class Cotizacion(Base):
    __tablename__ = "cotizaciones"

    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    compra_centavos: Mapped[int]
    venta_centavos: Mapped[int]
    origen: Mapped[str] = mapped_column(String(30))


class Regla(Base):
    __tablename__ = "reglas"
    __table_args__ = (UniqueConstraint("tipo", "valor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10), default="texto")
    valor: Mapped[str] = mapped_column(String(100))
    categoria: Mapped[str] = mapped_column(String(60))


class Fijo(Base):
    __tablename__ = "fijos"

    id: Mapped[int] = mapped_column(primary_key=True)
    concepto: Mapped[str] = mapped_column(String(60))
    texto: Mapped[str] = mapped_column(String(100))
    monto_centavos: Mapped[int]
    moneda: Mapped[str] = mapped_column(String(3))
    dia: Mapped[int | None]


class Cuota(Base):
    __tablename__ = "cuotas"

    id: Mapped[int] = mapped_column(primary_key=True)
    concepto: Mapped[str] = mapped_column(String(60))
    texto: Mapped[str] = mapped_column(String(100))
    monto_centavos: Mapped[int]
    moneda: Mapped[str] = mapped_column(String(3))
    cantidad: Mapped[int]
    primer_mes: Mapped[str] = mapped_column(String(7))


@dataclass(frozen=True)
class Pendiente:
    id: int
    fecha: date
    descripcion: str
    monto_centavos: int
    moneda: str


MIGRACIONES = Path(__file__).parent / "migraciones"
CONSULTAS = Path(__file__).parent / "consultas"
PRIMERA_VERSION = "0001"


class BaseDesactualizada(Exception):
    """La base está en una versión vieja: hay que correr `conciliador migrar`."""


def conectar(ruta: Path) -> Engine:
    """Una base nueva se crea con las migraciones. Una existente y vieja no se toca sola."""
    nueva = not ruta.exists() or ruta.stat().st_size == 0
    motor = create_engine(f"sqlite:///{ruta}")
    if nueva:
        _actualizar(motor)
    elif version(motor) != ultima_version():
        raise BaseDesactualizada(
            f"La base está en la versión {version(motor)} y el código espera la "
            f"{ultima_version()}: corré `conciliador migrar`."
        )
    return motor


def migrar(ruta: Path) -> Path | None:
    """Respalda la base y la lleva a la última versión. Devuelve el respaldo, si hubo cambios."""
    motor = create_engine(f"sqlite:///{ruta}")
    if version(motor) is None and inspect(motor).has_table("movimientos"):
        _marcar(motor, PRIMERA_VERSION)  # Creada antes de Alembic: ya tiene la estructura de la 0001.
    if version(motor) == ultima_version():
        return None
    respaldo = ruta.with_name(f"{ruta.stem}-antes-de-{ultima_version()}.db")
    shutil.copy(ruta, respaldo)
    _actualizar(motor)
    return respaldo


def version(motor: Engine) -> str | None:
    with motor.connect() as conexion:
        return MigrationContext.configure(conexion).get_current_revision()


def ultima_version() -> str:
    return ScriptDirectory.from_config(_config()).get_current_head()


def _config(conexion=None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRACIONES))
    config.attributes["connection"] = conexion
    return config


def _actualizar(motor: Engine) -> None:
    with motor.begin() as conexion:
        command.upgrade(_config(conexion), "head")


def _marcar(motor: Engine, revision: str) -> None:
    with motor.begin() as conexion:
        command.stamp(_config(conexion), revision)


def guardar_movimientos(motor: Engine, fuente: str, filas: Iterable[FilaLeida]) -> tuple[int, int]:
    """Guarda las filas y devuelve (nuevas, repetidas). La base es quien detecta los repetidos."""
    nuevas = repetidas = 0
    with Session(motor) as sesion, sesion.begin():
        for fila in filas:
            orden = (
                insert(Movimiento)
                .values(
                    fuente=fuente,
                    numero_operacion=fila.numero_operacion,
                    fecha=fila.fecha,
                    descripcion=fila.descripcion,
                    monto_centavos=fila.monto_centavos,
                    moneda=fila.moneda,
                    tipo=fila.tipo,
                    mes=fila.mes or fila.fecha.strftime("%Y-%m"),
                    cuota=fila.cuota,
                    fecha_cotizacion=fila.fecha_cotizacion or fila.fecha,
                )
                .on_conflict_do_nothing(index_elements=["fuente", "numero_operacion"])
            )
            if sesion.execute(orden).rowcount:
                nuevas += 1
            else:
                repetidas += 1
    return nuevas, repetidas


def guardar_resumen(motor: Engine, resumen: ResumenTarjeta) -> None:
    orden = (
        insert(Resumen)
        .values(
            tarjeta=resumen.fuente,
            numero=resumen.numero,
            cierre=resumen.cierre,
            vencimiento=resumen.vencimiento,
            total_pesos_centavos=resumen.total_pesos,
            total_dolares_centavos=resumen.total_dolares,
            percepcion_centavos=resumen.percepcion,
        )
        .on_conflict_do_nothing(index_elements=["tarjeta", "numero"])
    )
    with Session(motor) as sesion, sesion.begin():
        sesion.execute(orden)


def reemplazar_plan(motor: Engine, plan: PlanLeido) -> None:
    """El plan es el archivo: cada importación reemplaza lo anterior."""
    with Session(motor) as sesion, sesion.begin():
        sesion.execute(delete(Fijo))
        sesion.execute(delete(Cuota))
        sesion.add_all(
            Fijo(
                concepto=f.concepto,
                texto=f.texto,
                monto_centavos=f.monto_centavos,
                moneda=f.moneda,
                dia=f.dia,
            )
            for f in plan.fijos
        )
        sesion.add_all(
            Cuota(
                concepto=c.concepto,
                texto=c.texto,
                monto_centavos=c.monto_centavos,
                moneda=c.moneda,
                cantidad=c.cantidad,
                primer_mes=c.primer_mes,
            )
            for c in plan.cuotas
        )


def aplicar_reglas(motor: Engine) -> None:
    """Categoriza los gastos sin categoría real. Nunca pisa una categoría puesta a mano."""
    with Session(motor) as sesion, sesion.begin():
        reglas = [(r.valor, r.categoria) for r in sesion.scalars(select(Regla))]
        fijos = sesion.scalars(select(Fijo)).all()
        cuotas = sesion.scalars(select(Cuota)).all()
        gastos = sesion.scalars(
            select(Movimiento).where(Movimiento.tipo.in_(clasificar.TIPOS_DE_GASTO))
        ).all()
        for gasto in gastos:
            # Derivado del plan y del movimiento: se recalcula entero, porque el plan pudo cambiar.
            gasto.plan_concepto = clasificar.del_plan(gasto, fijos, cuotas)
            if not gasto.categoria_manual and gasto.categoria in (None, clasificar.SIN_REGLA):
                gasto.categoria, gasto.pendiente = clasificar.decidir(gasto, reglas, fijos, cuotas)


def pendientes(motor: Engine) -> list[Pendiente]:
    with Session(motor) as sesion:
        filas = sesion.scalars(
            select(Movimiento).where(Movimiento.pendiente.is_(True)).order_by(Movimiento.fecha)
        )
        return [
            Pendiente(f.id, f.fecha, f.descripcion, f.monto_centavos, f.moneda) for f in filas
        ]


def resolver_pendiente(
    motor: Engine, movimiento_id: int, categoria: str, texto_regla: str | None
) -> None:
    """Pone la categoría a mano y, si hay texto, la guarda como regla para lo que venga."""
    with Session(motor) as sesion, sesion.begin():
        gasto = sesion.get_one(Movimiento, movimiento_id)
        gasto.categoria = categoria
        gasto.categoria_manual = True
        gasto.pendiente = False
        if texto_regla:
            sesion.execute(
                insert(Regla)
                .values(tipo="texto", valor=texto_regla, categoria=categoria)
                .on_conflict_do_nothing(index_elements=["tipo", "valor"])
            )
    aplicar_reglas(motor)


def consultar(motor: Engine, nombre: str, **parametros) -> list[dict]:
    """Corre consultas/<nombre>.sql. Los valores van como parámetros, nunca pegados al texto."""
    lineas = (CONSULTAS / f"{nombre}.sql").read_text(encoding="utf-8").splitlines()
    # Sin comentarios: text() tomaría un ":mes" escrito en un comentario como otro parámetro.
    sql = "\n".join(l for l in lineas if not l.lstrip().startswith("--"))
    with motor.connect() as conexion:
        return [dict(fila) for fila in conexion.execute(text(sql), parametros).mappings()]


FUENTE_MANUAL = "manual"


def guardar_manual(
    motor: Engine,
    fila: FilaLeida,
    medio: str | None = None,
    tarjeta: str | None = None,
    categoria: str | None = None,
) -> tuple[str | None, str | None]:
    """Guarda lo cargado a mano y lo procesa como una importación. Devuelve (categoría, plan)."""
    with Session(motor) as sesion, sesion.begin():
        movimiento = Movimiento(
            fuente=FUENTE_MANUAL,
            numero_operacion=fila.numero_operacion,
            fecha=fila.fecha,
            descripcion=fila.descripcion,
            monto_centavos=fila.monto_centavos,
            moneda=fila.moneda,
            tipo=fila.tipo,
            mes=fila.mes or fila.fecha.strftime("%Y-%m"),
            fecha_cotizacion=fila.fecha,
            categoria=categoria,
            categoria_manual=categoria is not None,
            pendiente=False,
            medio=medio,
            tarjeta=tarjeta,
        )
        sesion.add(movimiento)
        sesion.flush()
        movimiento_id = movimiento.id
    asignar_cotizaciones(motor)
    aplicar_reglas(motor)
    with Session(motor) as sesion:
        guardado = sesion.get_one(Movimiento, movimiento_id)
        return guardado.categoria, guardado.plan_concepto


def ultimo_manual(motor: Engine) -> tuple[date, int, str] | None:
    """Fecha, monto y descripción del último gasto cargado a mano."""
    with Session(motor) as sesion:
        ultimo = sesion.scalar(
            select(Movimiento)
            .where(Movimiento.fuente == FUENTE_MANUAL, Movimiento.tipo == "consumo")
            .order_by(Movimiento.id.desc())
            .limit(1)
        )
        return None if ultimo is None else (ultimo.fecha, ultimo.monto_centavos, ultimo.descripcion)


@dataclass(frozen=True)
class Evaluacion:
    grande_sin_anticipar: bool
    previsto: tuple[str, int, str] | None  # Concepto, monto y moneda del fijo o cuota del plan.


def evaluar(motor: Engine, fila: FilaLeida) -> Evaluacion:
    """Lo que pasaría al guardar la fila, con las reglas, el plan y la cotización guardados."""
    with Session(motor) as sesion:
        reglas = [(r.valor, r.categoria) for r in sesion.scalars(select(Regla))]
        fijos = sesion.scalars(select(Fijo)).all()
        cuotas = sesion.scalars(select(Cuota)).all()
        guardadas = sesion.execute(
            select(Cotizacion.fecha, Cotizacion.venta_centavos).order_by(Cotizacion.fecha)
        ).all()
        gasto = SimpleNamespace(
            descripcion=fila.descripcion,
            monto_centavos=fila.monto_centavos,
            moneda=fila.moneda,
            mes=fila.mes or fila.fecha.strftime("%Y-%m"),
            cotizacion_centavos=cotizaciones.elegir(guardadas, fila.fecha),
        )
        concepto = clasificar.del_plan(gasto, fijos, cuotas)
        previsto = next(
            ((p.concepto, p.monto_centavos, p.moneda) for p in [*fijos, *cuotas] if p.concepto == concepto),
            None,
        )
        return Evaluacion(clasificar.decidir(gasto, reglas, fijos, cuotas)[1], previsto)


def manuales(motor: Engine, cantidad: int = 10) -> list[dict]:
    """Los últimos cargados a mano, del más nuevo al más viejo."""
    with Session(motor) as sesion:
        filas = sesion.scalars(
            select(Movimiento)
            .where(Movimiento.fuente == FUENTE_MANUAL)
            .order_by(Movimiento.id.desc())
            .limit(cantidad)
        )
        return [_manual_como_dict(f) for f in filas]


def manual(motor: Engine, movimiento_id: int) -> dict | None:
    """Un movimiento cargado a mano, o None si no existe o vino de un PDF."""
    with Session(motor) as sesion:
        fila = sesion.get(Movimiento, movimiento_id)
        return _manual_como_dict(fila) if fila and fila.fuente == FUENTE_MANUAL else None


def borrar_manual(motor: Engine, movimiento_id: int) -> bool:
    """Borra un movimiento cargado a mano. Los de un PDF no: el PDF los volvería a traer."""
    with Session(motor) as sesion, sesion.begin():
        borradas = sesion.execute(
            delete(Movimiento).where(
                Movimiento.id == movimiento_id, Movimiento.fuente == FUENTE_MANUAL
            )
        ).rowcount
    return borradas == 1


def _manual_como_dict(fila: Movimiento) -> dict:
    return {
        "id": fila.id,
        "fecha": fila.fecha,
        "descripcion": fila.descripcion,
        "monto_centavos": fila.monto_centavos,
        "moneda": fila.moneda,
        "tipo": fila.tipo,
        "medio": fila.medio,
        "tarjeta": fila.tarjeta,
        "categoria": fila.categoria,
        "plan_concepto": fila.plan_concepto,
    }


def marcar_cambio(motor: Engine, movimiento_id: int) -> None:
    """La plata cambió de forma (USDT, efectivo) pero no se gastó: deja de sumar."""
    with Session(motor) as sesion, sesion.begin():
        movimiento = sesion.get_one(Movimiento, movimiento_id)
        movimiento.tipo = "cambio"
        movimiento.categoria = None
        movimiento.pendiente = False
        movimiento.plan_concepto = None


def guardar_cotizaciones(motor: Engine, filas: Iterable[cotizaciones.CotizacionLeida]) -> None:
    """No pisa una fecha ya guardada, para que un reporte viejo no cambie."""
    valores = [
        {
            "fecha": f.fecha,
            "compra_centavos": f.compra_centavos,
            "venta_centavos": f.venta_centavos,
            "origen": cotizaciones.ORIGEN,
        }
        for f in filas
    ]
    if valores:
        with Session(motor) as sesion, sesion.begin():
            sesion.execute(insert(Cotizacion).on_conflict_do_nothing(), valores)


def asignar_cotizaciones(motor: Engine) -> None:
    """Completa los movimientos sin cotización. Los que ya tienen una no cambian."""
    with Session(motor) as sesion, sesion.begin():
        guardadas = sesion.execute(
            select(Cotizacion.fecha, Cotizacion.venta_centavos).order_by(Cotizacion.fecha)
        ).all()
        faltantes = sesion.scalars(
            select(Movimiento).where(Movimiento.cotizacion_centavos.is_(None))
        )
        for movimiento in faltantes:
            cotizacion = cotizaciones.elegir(guardadas, movimiento.fecha_cotizacion)
            if cotizacion is not None:
                movimiento.cotizacion_centavos = cotizacion
                movimiento.usd_centavos = cotizaciones.a_usd(
                    movimiento.monto_centavos, movimiento.moneda, cotizacion
                )


def contar_sin_usd(motor: Engine) -> int:
    with Session(motor) as sesion:
        return sesion.scalar(
            select(func.count())
            .select_from(Movimiento)
            .where(Movimiento.usd_centavos.is_(None))
        )
