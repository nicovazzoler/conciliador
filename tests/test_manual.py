from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from conciliador import base, clasificar, manual
from conciliador.importar import importar_carpeta

DEMO = Path(__file__).parent.parent / "demo"
DIA = date(2026, 10, 20)


def nunca(_):
    raise AssertionError("no tenía que preguntar")


def demo(tmp_path):
    motor = base.conectar(tmp_path / "demo.db")
    importar_carpeta(DEMO, motor)
    return motor


def manuales(motor):
    with base.Session(motor) as sesion:
        return sesion.scalars(
            select(base.Movimiento).where(base.Movimiento.fuente == base.FUENTE_MANUAL)
        ).all()


def gastado(motor, mes):
    with base.Session(motor) as sesion:
        return sesion.scalar(
            select(func.sum(base.Movimiento.monto_centavos)).where(
                base.Movimiento.tipo.in_(clasificar.TIPOS_DE_GASTO), base.Movimiento.mes == mes
            )
        )


def test_un_gasto_manual_suma_en_el_total_del_mes(tmp_path):
    motor = demo(tmp_path)
    antes = gastado(motor, "2026-10")
    assert manual.registrar_gasto(motor, "3.500", "Café Demo", DIA, preguntar=nunca, mostrar=print)
    assert gastado(motor, "2026-10") == antes - 350_000
    (cafe,) = manuales(motor)
    assert (cafe.medio, cafe.tipo, cafe.mes) == ("efectivo", "consumo", "2026-10")


def test_un_gasto_manual_se_vincula_con_su_fijo(tmp_path):
    motor = demo(tmp_path)
    manual.registrar_gasto(motor, "13000", "OBRA SOCIAL DEMO", DIA, medio="debito", preguntar=nunca)
    fijos = {f["concepto"]: f for f in base.consultar(motor, "fijos", mes="2026-10")}
    assert fijos["Obra social"]["estado"] == "bien"


def test_un_gasto_grande_sin_confirmar_no_se_guarda(tmp_path):
    motor = demo(tmp_path)
    assert not manual.registrar_gasto(motor, "200000", "Mueble Demo", DIA, preguntar=lambda _: "n")
    assert manuales(motor) == []


def test_un_gasto_grande_confirmado_guarda_la_categoria(tmp_path):
    motor = demo(tmp_path)
    respuestas = iter(["s", "Hogar"])
    manual.registrar_gasto(motor, "200000", "Mueble Demo", DIA, preguntar=lambda _: next(respuestas))
    (mueble,) = manuales(motor)
    assert (mueble.categoria, mueble.categoria_manual, mueble.pendiente) == ("Hogar", True, False)


def test_el_mismo_gasto_dos_veces_seguidas_pregunta(tmp_path):
    motor = demo(tmp_path)
    manual.registrar_gasto(motor, "3500", "Café Demo", DIA, preguntar=nunca)
    assert not manual.registrar_gasto(motor, "3500", "Café Demo", DIA, preguntar=lambda _: "n")
    assert manual.registrar_gasto(motor, "3500", "Café Demo", DIA, preguntar=lambda _: "s")
    assert len(manuales(motor)) == 2


def test_un_pago_de_tarjeta_no_suma_como_gasto(tmp_path):
    motor = demo(tmp_path)
    antes = gastado(motor, "2026-10")
    manual.registrar_pago(motor, "tarjeta_nacion", "150000", DIA, mostrar=print)
    assert gastado(motor, "2026-10") == antes
    (pago,) = manuales(motor)
    assert (pago.tipo, pago.tarjeta, pago.monto_centavos) == ("pago_tarjeta", "tarjeta_nacion", -15_000_000)


def test_fecha_futura_monto_cero_o_tarjeta_desconocida_dan_error(tmp_path):
    with pytest.raises(ValueError, match="futura"):
        manual.leer_fecha("2026-10-21", hoy=DIA)
    assert manual.leer_fecha("28/09/2026", hoy=DIA) == date(2026, 9, 28)
    with pytest.raises(ValueError, match="mayor que 0"):
        manual.leer_monto("0")
    with pytest.raises(ValueError, match="tarjeta inválida"):
        manual.registrar_pago(base.conectar(tmp_path / "p.db"), "tarjeta_mp", "100", DIA)


def test_un_monto_muy_lejos_del_fijo_pregunta(tmp_path):
    """El fijo de la demo es $13.000: $130.000 es casi seguro un cero de más."""
    motor = demo(tmp_path)
    preguntas = []
    respuesta = lambda texto: preguntas.append(texto) or "n"
    assert not manual.registrar_gasto(motor, "130000", "OBRA SOCIAL DEMO", DIA, preguntar=respuesta)
    assert "Obra social está anotado en ARS 13.000,00" in preguntas[0]
    assert manuales(motor) == []
    assert manual.registrar_gasto(motor, "14000", "OBRA SOCIAL DEMO", DIA, preguntar=nunca)


def test_borrar_un_gasto_manual_lo_saca_del_total(tmp_path):
    motor = demo(tmp_path)
    antes = gastado(motor, "2026-10")
    manual.registrar_gasto(motor, "3500", "Café Demo", DIA, preguntar=nunca)
    (cafe,) = base.manuales(motor)
    assert manual.borrar(motor, cafe["id"], preguntar=lambda _: "s", mostrar=print)
    assert gastado(motor, "2026-10") == antes
    assert base.manuales(motor) == []


def test_no_se_puede_borrar_un_movimiento_de_un_pdf(tmp_path):
    motor = demo(tmp_path)
    with base.Session(motor) as sesion:
        de_un_pdf = sesion.scalar(select(base.Movimiento.id).limit(1))
    with pytest.raises(ValueError, match="cargado a mano"):
        manual.borrar(motor, de_un_pdf, preguntar=nunca)
    assert not base.borrar_manual(motor, de_un_pdf)


def test_borrar_sin_confirmar_no_borra(tmp_path):
    motor = demo(tmp_path)
    manual.registrar_pago(motor, "tarjeta_comafi", "1000", DIA, mostrar=print)
    (pago,) = base.manuales(motor)
    assert not manual.borrar(motor, pago["id"], preguntar=lambda _: "n", mostrar=print)
    assert len(base.manuales(motor)) == 1
