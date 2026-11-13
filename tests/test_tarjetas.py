import importlib.util
from datetime import date
from pathlib import Path

import pytest

from conciliador import base
from conciliador.importar import importar_carpeta
from conciliador.lectores import FilaLeida, tarjeta_comafi, tarjeta_nacion, tarjetas

DEMO = Path(__file__).parent.parent / "demo"
COMAFI = DEMO / "tarjeta_comafi_octubre.pdf"
NACION = DEMO / "tarjeta_nacion_octubre.pdf"


def por_descripcion(resumen):
    return {f.descripcion: f for f in resumen.filas}


def test_comafi_cierra_contra_sus_totales():
    resumen = tarjeta_comafi.leer(COMAFI)
    assert len(resumen.filas) == 11
    assert resumen.errores == []
    assert tarjetas.verificar(resumen) == []


def test_comafi_clasifica_cada_fila():
    filas = por_descripcion(tarjeta_comafi.leer(COMAFI))
    assert filas["SU PAGO EN PESOS"].tipo == "pago"
    assert filas["IMPUESTO DE SELLOS $"].tipo == "impuesto"
    assert filas["DB.RG 5617 30% ( 60000,00 )"].tipo == "percepcion"
    assert filas["DEV.IMP. RG 5617 30%( 50000,00)"].tipo == "percepcion"
    assert filas["SUPER DEMO 99"].tipo == "consumo"


def test_comafi_separa_los_dolares_por_columna():
    filas = por_descripcion(tarjeta_comafi.leer(COMAFI))
    assert (filas["NUBE DEMO USD"].moneda, filas["NUBE DEMO USD"].monto_centavos) == ("USD", 700)
    assert filas["SUPER DEMO 99"].moneda == "ARS"
    assert filas["SU PAGO EN USD"].moneda == "USD"


def test_cuotas_e_impuestos_cuentan_en_el_mes_de_vencimiento():
    filas = por_descripcion(tarjeta_comafi.leer(COMAFI))
    cuota = filas["ZAPATERIA DEMO"]
    assert (cuota.tipo, cuota.cuota, cuota.fecha) == ("cuota", "03/06", date(2026, 8, 10))
    assert cuota.mes == "2026-11"
    assert filas["SUPER DEMO 99"].mes == "2026-10"
    assert filas["IMPUESTO DE SELLOS $"].mes == "2026-11"
    assert filas["SU PAGO EN PESOS"].mes == "2026-10"


def test_el_comprobante_se_guarda_sin_comerse_la_descripcion():
    assert por_descripcion(tarjeta_comafi.leer(COMAFI))["SUPER DEMO 99"].numero_operacion == (
        "700102|-|2026-10-03"
    )


def test_la_percepcion_se_informa_para_descontarla_del_total():
    assert tarjeta_comafi.leer(COMAFI).percepcion == 1800000


def test_nacion_cierra_contra_sus_totales():
    resumen = tarjeta_nacion.leer(NACION)
    assert len(resumen.filas) == 5
    assert resumen.errores == []
    assert tarjetas.verificar(resumen) == []


def test_nacion_lee_descuentos_cuotas_y_dolares():
    filas = por_descripcion(tarjeta_nacion.leer(NACION))
    assert filas["DESCUENTO DEMO"].tipo == "devolucion"
    assert (filas["ROPA DEMO"].tipo, filas["ROPA DEMO"].cuota) == ("cuota", "01/12")
    assert filas["TIENDA EXTERIOR DEMO"].moneda == "USD"
    assert filas["RESTAURANTE DEMO"].moneda == "ARS"


def test_mismo_cupon_en_compra_y_cuota_son_filas_distintas():
    claves = [f.numero_operacion for f in tarjeta_nacion.leer(NACION).filas]
    assert len(claves) == len(set(claves))
    assert "00501|-|2026-10-13" in claves and "00501|01/12|2026-10-13" in claves


@pytest.fixture
def generador():
    spec = importlib.util.spec_from_file_location("generar", DEMO / "generar" / "generar_tarjetas.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_nacion_con_clave_abre_y_sin_clave_no(generador, tmp_path):
    protegido = tmp_path / "nacion.pdf"
    generador.generar_nacion(protegido, clave="secreta")
    assert tarjeta_nacion.leer(protegido) is None
    assert tarjeta_nacion.leer(protegido, "otra") is None
    assert len(tarjeta_nacion.leer(protegido, "secreta").filas) == 5


def test_una_fila_perdida_se_detecta():
    resumen = tarjeta_comafi.leer(COMAFI)
    del resumen.filas[-1]
    assert tarjetas.verificar(resumen) == ["las filas en USD no coinciden con el total del resumen"]


def test_la_cuota_del_mes_siguiente_no_es_repetida(tmp_path):
    motor = base.conectar(tmp_path / "prueba.db")
    fecha = date(2026, 8, 10)
    cuotas = [
        FilaLeida(tarjetas.clave_detalle("700101", c, fecha), fecha, "Zapatería", 100, cuota=c)
        for c in ("03/06", "04/06")
    ]
    assert base.guardar_movimientos(motor, tarjeta_comafi.FUENTE, cuotas) == (2, 0)


def test_reimportar_no_duplica_movimientos_ni_resumenes(tmp_path):
    motor = base.conectar(tmp_path / "prueba.db")
    importar_carpeta(DEMO, motor)
    informes = [i for i in importar_carpeta(DEMO, motor) if i.archivo.endswith(".pdf")]
    assert len(informes) == 3
    assert all(i.nuevas == 0 and i.problemas == [] for i in informes)
    with base.Session(motor) as sesion:
        assert sesion.query(base.Resumen).count() == 2
