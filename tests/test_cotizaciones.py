from datetime import date
from pathlib import Path

from sqlalchemy import select

from conciliador import base, cotizaciones
from conciliador.cotizaciones import CotizacionLeida
from conciliador.importar import actualizar_cotizaciones, importar_carpeta
from conciliador.lectores import FilaLeida

DEMO = Path(__file__).parent.parent / "demo"
JUEVES = date(2026, 10, 1)
VIERNES = date(2026, 10, 2)
LUNES = date(2026, 10, 5)
GUARDADAS = [(JUEVES, 100_000), (VIERNES, 110_000), (LUNES, 120_000)]


def cotizacion(fecha, venta):
    return CotizacionLeida(fecha, venta - 5000, venta)


def buscar(motor, descripcion):
    with base.Session(motor) as sesion:
        return sesion.scalar(
            select(base.Movimiento).where(base.Movimiento.descripcion == descripcion)
        )


def guardar(motor, numero, fecha, pesos, moneda="ARS", **extras):
    fila = FilaLeida(numero, fecha, numero, pesos, moneda=moneda, tipo="consumo", **extras)
    base.guardar_movimientos(motor, "mercado_pago", [fila])


def test_lee_el_formato_de_la_fuente():
    datos = [{"casa": "oficial", "compra": 1490.5, "venta": 1540, "fecha": "2026-10-01"}]
    assert cotizaciones.parsear(datos) == [CotizacionLeida(JUEVES, 149050, 154000)]


def test_usa_la_cotizacion_del_dia():
    assert cotizaciones.elegir(GUARDADAS, VIERNES) == 110_000


def test_fin_de_semana_usa_el_ultimo_dia_anterior():
    assert cotizaciones.elegir(GUARDADAS, date(2026, 10, 3)) == 110_000


def test_fecha_sin_publicar_queda_sin_cotizacion():
    assert cotizaciones.elegir(GUARDADAS, date(2026, 10, 6)) is None
    assert cotizaciones.elegir([], JUEVES) is None


def test_fecha_anterior_al_historial_queda_sin_cotizacion():
    assert cotizaciones.elegir(GUARDADAS, date(2026, 9, 1)) is None


def test_convierte_a_usd_con_redondeo_exacto():
    assert cotizaciones.a_usd(-15_400_000, "ARS", 154_000) == -10_000
    assert cotizaciones.a_usd(100, "ARS", 300) == 33
    assert cotizaciones.a_usd(200, "ARS", 300) == 67
    assert cotizaciones.a_usd(-8824, "USD", 154_000) == -8824


def test_el_movimiento_guarda_su_cotizacion(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    guardar(motor, "pesos", JUEVES, -5_000_000)
    guardar(motor, "dolares", JUEVES, -1_000, moneda="USD")
    actualizar_cotizaciones(motor, lambda: [cotizacion(JUEVES, 100_000)])
    assert buscar(motor, "pesos").usd_centavos == -5_000
    assert buscar(motor, "dolares").usd_centavos == -1_000
    assert buscar(motor, "dolares").cotizacion_centavos == 100_000


def test_una_cotizacion_guardada_no_cambia_y_un_reporte_viejo_tampoco(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    guardar(motor, "pesos", JUEVES, -5_000_000)
    actualizar_cotizaciones(motor, lambda: [cotizacion(JUEVES, 100_000)])
    actualizar_cotizaciones(motor, lambda: [cotizacion(JUEVES, 999_000)])
    assert buscar(motor, "pesos").cotizacion_centavos == 100_000


def test_lo_no_publicado_se_completa_en_la_proxima_importacion(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    guardar(motor, "pesos", VIERNES, -1_000_000)
    actualizar_cotizaciones(motor, lambda: [cotizacion(JUEVES, 100_000)])
    assert base.contar_sin_usd(motor) == 1
    actualizar_cotizaciones(motor, lambda: [cotizacion(VIERNES, 100_000)])
    assert base.contar_sin_usd(motor) == 0


def test_la_cuota_usa_el_dolar_del_vencimiento_no_el_de_la_compra(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    guardar(motor, "cuota", JUEVES, -1_000_000, fecha_cotizacion=LUNES)
    actualizar_cotizaciones(
        motor, lambda: [cotizacion(JUEVES, 100_000), cotizacion(LUNES, 200_000)]
    )
    assert buscar(motor, "cuota").cotizacion_centavos == 200_000


def test_sin_conexion_avisa_y_usa_lo_guardado(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    guardar(motor, "pesos", JUEVES, -1_000_000)
    actualizar_cotizaciones(motor, lambda: [cotizacion(JUEVES, 100_000)])
    guardar(motor, "otro", JUEVES, -2_000_000)

    def sin_conexion():
        raise OSError("sin red")

    assert "no se pudieron traer" in actualizar_cotizaciones(motor, sin_conexion)
    assert buscar(motor, "otro").usd_centavos == -2_000


def test_gasto_grande_en_dolares_queda_para_revisar(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    guardar(motor, "nube", JUEVES, -4_000, moneda="USD")
    actualizar_cotizaciones(motor, lambda: [cotizacion(JUEVES, 150_000)])
    assert buscar(motor, "nube").pendiente is True


def test_el_demo_queda_completo_en_usd(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    importar_carpeta(DEMO, motor)
    actualizar_cotizaciones(motor, lambda: [cotizacion(date(2026, 8, 1), 100_000), cotizacion(date(2026, 11, 30), 100_000)])
    assert base.contar_sin_usd(motor) == 0
