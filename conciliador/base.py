"""Único módulo que accede a la base. Ver la decisión D3 en PLAN.md."""
import shutil
from types import SimpleNamespace
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import (
    Date, DateTime, String, UniqueConstraint, create_engine, delete, func, inspect, or_, select, text, update,
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
    categoria: Mapped[str | None] = mapped_column(String(60))


class Cuota(Base):
    __tablename__ = "cuotas"

    id: Mapped[int] = mapped_column(primary_key=True)
    concepto: Mapped[str] = mapped_column(String(60))
    texto: Mapped[str] = mapped_column(String(100))
    monto_centavos: Mapped[int]
    moneda: Mapped[str] = mapped_column(String(3))
    cantidad: Mapped[int]
    primer_mes: Mapped[str] = mapped_column(String(7))
    categoria: Mapped[str | None] = mapped_column(String(60))


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


class ConceptoRepetido(Exception):
    """El concepto identifica al fijo o cuota: no puede haber dos iguales en el plan."""


def hay_plan(motor: Engine) -> bool:
    with Session(motor) as sesion:
        return sesion.scalar(select(func.count()).select_from(Fijo)) + sesion.scalar(
            select(func.count()).select_from(Cuota)
        ) > 0


def leer_plan(motor: Engine) -> PlanLeido:
    """El plan guardado, como si se hubiera leído de plan.csv."""
    from conciliador.plan import CuotaPlan, FijoPlan

    with Session(motor) as sesion:
        fijos = [FijoPlan(f.concepto, f.texto, f.monto_centavos, f.moneda, f.dia, f.categoria)
                 for f in sesion.scalars(select(Fijo).order_by(Fijo.concepto))]
        cuotas = [CuotaPlan(c.concepto, c.texto, c.monto_centavos, c.moneda, c.cantidad, c.primer_mes, c.categoria)
                  for c in sesion.scalars(select(Cuota).order_by(Cuota.primer_mes, Cuota.concepto))]
    return PlanLeido(fijos=fijos, cuotas=cuotas)


def plan_con_ids(motor: Engine) -> dict:
    """Los fijos y las cuotas con su id, para editarlos desde la app."""
    with Session(motor) as sesion:
        fijos = [{"id": f.id, "concepto": f.concepto, "texto": f.texto, "monto_centavos": f.monto_centavos,
                  "moneda": f.moneda, "dia": f.dia, "categoria": f.categoria}
                 for f in sesion.scalars(select(Fijo).order_by(Fijo.concepto))]
        cuotas = [{"id": c.id, "concepto": c.concepto, "texto": c.texto, "monto_centavos": c.monto_centavos,
                   "moneda": c.moneda, "cantidad": c.cantidad, "primer_mes": c.primer_mes, "categoria": c.categoria}
                  for c in sesion.scalars(select(Cuota).order_by(Cuota.primer_mes, Cuota.concepto))]
    return {"fijos": fijos, "cuotas": cuotas}


def guardar_del_plan(motor: Engine, tabla: str, item, item_id: int | None = None) -> int | None:
    """Crea (sin id) o modifica (con id) un fijo o una cuota. Devuelve el id, o None si no existe."""
    modelo = Fijo if tabla == "fijos" else Cuota
    with Session(motor) as sesion, sesion.begin():
        repetido = [
            *sesion.scalars(select(Fijo.id).where(Fijo.concepto == item.concepto)),
            *sesion.scalars(select(Cuota.id).where(Cuota.concepto == item.concepto)),
        ]
        propio = item_id is not None and sesion.get(modelo, item_id) is not None
        if repetido and not (propio and repetido == [item_id] and sesion.get(modelo, item_id).concepto == item.concepto):
            raise ConceptoRepetido(f"ya hay algo en el plan que se llama {item.concepto!r}")
        if item_id is None:
            fila = modelo()
            sesion.add(fila)
            anterior = None
        else:
            fila = sesion.get(modelo, item_id)
            if fila is None:
                return None
            anterior = fila.concepto
        for campo, valor in vars(item).items():
            setattr(fila, "cantidad" if campo == "cantidad" else campo, valor)
        sesion.flush()
        nuevo_id = fila.id
        _soltar_categoria_del_plan(sesion, {anterior, item.concepto})
    aplicar_reglas(motor)
    return nuevo_id


def borrar_del_plan(motor: Engine, tabla: str, item_id: int) -> bool:
    modelo = Fijo if tabla == "fijos" else Cuota
    with Session(motor) as sesion, sesion.begin():
        fila = sesion.get(modelo, item_id)
        if fila is None:
            return False
        _soltar_categoria_del_plan(sesion, {fila.concepto})
        sesion.delete(fila)
    aplicar_reglas(motor)
    return True


def _soltar_categoria_del_plan(sesion: Session, conceptos: set) -> None:
    """Lo que tomó la categoría de un fijo o cuota que cambió se vuelve a calcular desde cero.

    Sin esto, si se borra la categoría del plan, los gastos se quedarían con la vieja.
    """
    sesion.execute(
        update(Movimiento)
        .where(Movimiento.plan_concepto.in_([c for c in conceptos if c]), Movimiento.categoria_manual.is_(False))
        .values(categoria=None, pendiente=False)
    )


class OperacionInversion(Base):
    """Una compra o venta de un activo. Cantidad y precio como texto decimal: no entran en centavos."""

    __tablename__ = "operaciones"
    __table_args__ = (UniqueConstraint("fuente", "numero_operacion"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente: Mapped[str] = mapped_column(String(30))
    numero_operacion: Mapped[str] = mapped_column(String(80))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    activo: Mapped[str] = mapped_column(String(20))
    tipo_activo: Mapped[str] = mapped_column(String(10))
    lado: Mapped[str] = mapped_column(String(10))
    cantidad: Mapped[str] = mapped_column(String(40))
    precio: Mapped[str] = mapped_column(String(40))
    comision: Mapped[str] = mapped_column(String(40))


class PrecioActivo(Base):
    """El último precio conocido de cada activo, en USD, con su hora y su origen."""

    __tablename__ = "precios"

    activo: Mapped[str] = mapped_column(String(20), primary_key=True)
    precio: Mapped[str] = mapped_column(String(40))
    actualizado: Mapped[datetime] = mapped_column(DateTime)
    origen: Mapped[str] = mapped_column(String(20))


def guardar_operacion(motor: Engine, fuente: str, numero: str, op) -> bool:
    """Guarda una operación. Devuelve False si ya estaba: se reconoce por fuente y número."""
    with Session(motor) as sesion, sesion.begin():
        orden = (
            insert(OperacionInversion)
            .values(
                fuente=fuente, numero_operacion=numero, fecha_hora=op.fecha_hora, activo=op.activo,
                tipo_activo=op.tipo_activo, lado=op.lado, cantidad=str(op.cantidad), precio=str(op.precio),
                comision=str(op.comision),
            )
            .on_conflict_do_nothing(index_elements=["fuente", "numero_operacion"])
        )
        return sesion.execute(orden).rowcount == 1


def operaciones(motor: Engine) -> list:
    from conciliador.inversiones import Operacion

    with Session(motor) as sesion:
        return [
            Operacion(o.id, o.fecha_hora, o.activo, o.tipo_activo, o.lado, Decimal(o.cantidad), Decimal(o.precio),
                      Decimal(o.comision), o.fuente)
            for o in sesion.scalars(select(OperacionInversion))
        ]


def borrar_operacion(motor: Engine, operacion_id: int) -> bool:
    with Session(motor) as sesion, sesion.begin():
        return sesion.execute(delete(OperacionInversion).where(OperacionInversion.id == operacion_id)).rowcount == 1


def guardar_precios(motor: Engine, precios: dict, origen: dict[str, str], momento: datetime) -> None:
    with Session(motor) as sesion, sesion.begin():
        for activo, precio in precios.items():
            sesion.merge(PrecioActivo(activo=activo, precio=str(precio), actualizado=momento, origen=origen[activo]))


def precios(motor: Engine) -> tuple[dict, datetime | None]:
    """Los precios guardados y la hora del más viejo: lo que se muestra es tan nuevo como ese."""
    with Session(motor) as sesion:
        filas = sesion.scalars(select(PrecioActivo)).all()
    return {f.activo: Decimal(f.precio) for f in filas}, min((f.actualizado for f in filas), default=None)


def reemplazar_plan(motor: Engine, plan: PlanLeido) -> None:
    """Reemplaza el plan entero, por ejemplo al subir un plan.csv."""
    with Session(motor) as sesion, sesion.begin():
        anteriores = {*sesion.scalars(select(Fijo.concepto)), *sesion.scalars(select(Cuota.concepto))}
        _soltar_categoria_del_plan(sesion, anteriores)
        sesion.execute(delete(Fijo))
        sesion.execute(delete(Cuota))
        sesion.add_all(
            Fijo(
                concepto=f.concepto,
                texto=f.texto,
                monto_centavos=f.monto_centavos,
                moneda=f.moneda,
                dia=f.dia,
                categoria=f.categoria,
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
                categoria=c.categoria,
            )
            for c in plan.cuotas
        )


def aplicar_reglas(motor: Engine) -> None:
    """Categoriza los gastos. Gana la categoría puesta a mano, después la del fijo o cuota del plan
    al que corresponde el gasto, y después las reglas."""
    with Session(motor) as sesion, sesion.begin():
        reglas = [(r.valor, r.categoria) for r in sesion.scalars(select(Regla))]
        fijos = sesion.scalars(select(Fijo)).all()
        cuotas = sesion.scalars(select(Cuota)).all()
        gastos = sesion.scalars(
            select(Movimiento).where(Movimiento.tipo.in_(clasificar.TIPOS_DE_GASTO))
        ).all()
        del_plan = {p.concepto: p.categoria for p in [*fijos, *cuotas] if p.categoria}
        for gasto in gastos:
            # Derivado del plan y del movimiento: se recalcula entero, porque el plan pudo cambiar.
            gasto.plan_concepto = clasificar.del_plan(gasto, fijos, cuotas)
            if gasto.categoria_manual:
                continue
            if gasto.plan_concepto in del_plan:
                # Lo anotado en el plan es más específico que una regla de texto.
                gasto.categoria, gasto.pendiente = del_plan[gasto.plan_concepto], False
            elif gasto.tipo == "impuesto":
                # Los cargos de la tarjeta van juntos, sin una regla por cada sello o IVA.
                gasto.categoria, gasto.pendiente = clasificar.IMPUESTOS, False
            elif gasto.categoria in (None, clasificar.SIN_REGLA):
                gasto.categoria, gasto.pendiente = clasificar.decidir(gasto, reglas, fijos, cuotas)


def pendientes(motor: Engine) -> list[Pendiente]:
    with Session(motor) as sesion:
        filas = sesion.scalars(
            select(Movimiento).where(Movimiento.pendiente.is_(True)).order_by(Movimiento.fecha)
        )
        return [
            Pendiente(f.id, f.fecha, f.descripcion, f.monto_centavos, f.moneda) for f in filas
        ]


class ReglaRepetida(Exception):
    """Ya hay una regla con ese texto. Guardarla de nuevo no haría nada."""

    def __init__(self, categoria: str):
        super().__init__(f"ya hay una regla con ese texto, para la categoría {categoria!r}")
        self.categoria = categoria


def categorias(motor: Engine) -> list[str]:
    """Las categorías en uso, de la más usada a la menos. "Gastos varios" no es una categoría elegida."""
    with Session(motor) as sesion:
        filas = sesion.execute(
            select(Movimiento.categoria, func.count())
            .where(Movimiento.categoria.is_not(None), Movimiento.categoria != clasificar.SIN_REGLA)
            .group_by(Movimiento.categoria)
            .order_by(func.count().desc(), Movimiento.categoria)
        ).all()
        en_uso = [categoria for categoria, _ in filas]
        sin_movimientos = sesion.scalars(
            select(Regla.categoria).where(Regla.categoria.not_in(en_uso)).distinct().order_by(Regla.categoria)
        ).all()
        return en_uso + list(sin_movimientos)


def gastos_varios(motor: Engine) -> list[dict]:
    """Gastos sin categoría real y sin categoría puesta a mano: lo que una regla podría categorizar."""
    with Session(motor) as sesion:
        filas = sesion.scalars(
            select(Movimiento).where(
                Movimiento.tipo.in_(clasificar.TIPOS_DE_GASTO),
                Movimiento.categoria_manual.is_(False),
                Movimiento.categoria == clasificar.SIN_REGLA,
            )
        )
        return [
            {
                "id": f.id,
                "descripcion": f.descripcion,
                "monto_centavos": f.monto_centavos,
                "moneda": f.moneda,
                "plan_concepto": f.plan_concepto,
            }
            for f in filas
        ]


def agregar_regla(motor: Engine, texto: str, categoria: str) -> int:
    """Guarda la regla, la aplica y devuelve cuántos movimientos sin categoría real categorizó."""
    sin_categoria = (
        Movimiento.tipo.in_(clasificar.TIPOS_DE_GASTO),
        Movimiento.categoria_manual.is_(False),
        or_(Movimiento.categoria.is_(None), Movimiento.categoria == clasificar.SIN_REGLA),
    )
    with Session(motor) as sesion, sesion.begin():
        existente = sesion.scalar(select(Regla).where(Regla.tipo == "texto", Regla.valor == texto))
        if existente is not None:
            raise ReglaRepetida(existente.categoria)
        sesion.add(Regla(tipo="texto", valor=texto, categoria=categoria))
        candidatos = list(sesion.scalars(select(Movimiento.id).where(*sin_categoria)))
    aplicar_reglas(motor)
    # Se cuenta movimiento por movimiento: restar totales mezclaría otros cambios de aplicar_reglas.
    with Session(motor) as sesion:
        return sesion.scalar(
            select(func.count()).where(Movimiento.id.in_(candidatos), Movimiento.categoria == categoria)
        )


def es_pendiente(motor: Engine, movimiento_id: int) -> bool:
    with Session(motor) as sesion:
        movimiento = sesion.get(Movimiento, movimiento_id)
        return movimiento is not None and movimiento.pendiente


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
) -> tuple[int, str | None, str | None]:
    """Guarda lo cargado a mano y lo procesa como una importación. Devuelve (id, categoría, plan)."""
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
        return guardado.id, guardado.categoria, guardado.plan_concepto


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


# Movimientos y edición de categorías.


def movimientos_del_mes(motor: Engine, mes: str) -> list[dict]:
    """Todo lo del mes, del más nuevo al más viejo: gastos, ingresos, transferencias, pagos y cambios."""
    with Session(motor) as sesion:
        filas = sesion.scalars(
            select(Movimiento).where(Movimiento.mes == mes).order_by(Movimiento.fecha.desc(), Movimiento.id.desc())
        )
        return [
            {
                "id": f.id, "fecha": f.fecha, "descripcion": f.descripcion, "fuente": f.fuente, "tipo": f.tipo,
                "categoria": f.categoria, "categoria_manual": f.categoria_manual, "plan_concepto": f.plan_concepto,
                "monto_centavos": f.monto_centavos, "moneda": f.moneda, "usd_centavos": f.usd_centavos,
                "cuota": f.cuota, "medio": f.medio,
            }
            for f in filas
        ]


def poner_categoria(motor: Engine, movimiento_id: int, categoria: str | None) -> bool:
    """Con categoría, queda puesta a mano. Sin categoría, vuelve a la automática: plan, impuestos o reglas."""
    with Session(motor) as sesion, sesion.begin():
        movimiento = sesion.get(Movimiento, movimiento_id)
        if movimiento is None:
            return False
        movimiento.categoria = categoria
        movimiento.categoria_manual = categoria is not None
        movimiento.pendiente = False
    aplicar_reglas(motor)
    return True


def categorias_detalle(motor: Engine) -> list[dict]:
    """Cada categoría con cuántos movimientos, reglas y conceptos del plan la usan."""
    with Session(motor) as sesion:
        en_movimientos = dict(sesion.execute(
            select(Movimiento.categoria, func.count())
            .where(Movimiento.categoria.is_not(None), Movimiento.categoria != clasificar.SIN_REGLA)
            .group_by(Movimiento.categoria)
        ).all())
        en_reglas = dict(sesion.execute(select(Regla.categoria, func.count()).group_by(Regla.categoria)).all())
        en_plan: dict[str, int] = {}
        for modelo in (Fijo, Cuota):
            for categoria, cantidad in sesion.execute(
                select(modelo.categoria, func.count()).where(modelo.categoria.is_not(None)).group_by(modelo.categoria)
            ):
                en_plan[categoria] = en_plan.get(categoria, 0) + cantidad
    nombres = sorted({*en_movimientos, *en_reglas, *en_plan}, key=lambda n: (-en_movimientos.get(n, 0), n.lower()))
    return [
        {"nombre": n, "movimientos": en_movimientos.get(n, 0), "reglas": en_reglas.get(n, 0), "en_plan": en_plan.get(n, 0)}
        for n in nombres
    ]


def renombrar_categoria(motor: Engine, de: str, a: str) -> int:
    """Cambia el nombre en movimientos, reglas y plan. Si `a` ya existe, las dos quedan unidas."""
    with Session(motor) as sesion, sesion.begin():
        cambiados = sesion.execute(
            update(Movimiento).where(Movimiento.categoria == de).values(categoria=a)
        ).rowcount
        for modelo in (Regla, Fijo, Cuota):
            sesion.execute(update(modelo).where(modelo.categoria == de).values(categoria=a))
    return cambiados


def borrar_categoria(motor: Engine, nombre: str) -> None:
    """Saca la categoría de todos lados: borra sus reglas, la quita del plan y lo que la tenía se recalcula."""
    with Session(motor) as sesion, sesion.begin():
        sesion.execute(delete(Regla).where(Regla.categoria == nombre))
        for modelo in (Fijo, Cuota):
            sesion.execute(update(modelo).where(modelo.categoria == nombre).values(categoria=None))
        sesion.execute(
            update(Movimiento).where(Movimiento.categoria == nombre).values(categoria=None, categoria_manual=False)
        )
    aplicar_reglas(motor)


def reglas(motor: Engine) -> list[dict]:
    with Session(motor) as sesion:
        return [
            {"id": r.id, "texto": r.valor, "categoria": r.categoria}
            for r in sesion.scalars(select(Regla).order_by(Regla.categoria, Regla.valor))
        ]


def editar_regla(motor: Engine, regla_id: int, texto: str | None, categoria: str | None) -> bool:
    """Sin texto ni categoría, la borra. Lo que la regla había categorizado se recalcula."""
    with Session(motor) as sesion, sesion.begin():
        regla = sesion.get(Regla, regla_id)
        if regla is None:
            return False
        if texto is not None:
            otra = sesion.scalar(select(Regla.id).where(Regla.valor == texto, Regla.id != regla_id))
            if otra is not None:
                raise ReglaRepetida(sesion.get(Regla, otra).categoria)
        # Lo que esta regla categorizó (no puesto a mano, con su categoría y su texto) vuelve a calcularse.
        for movimiento in sesion.scalars(
            select(Movimiento).where(Movimiento.categoria == regla.categoria, Movimiento.categoria_manual.is_(False))
        ):
            if clasificar.coincide(regla.valor, movimiento.descripcion):
                movimiento.categoria = None
        if texto is None and categoria is None:
            sesion.delete(regla)
        else:
            regla.valor = texto or regla.valor
            regla.categoria = categoria or regla.categoria
    aplicar_reglas(motor)
    return True
