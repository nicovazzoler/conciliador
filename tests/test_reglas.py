from datetime import date
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from conciliador import base, clasificar, plan
from conciliador.importar import importar_carpeta
from conciliador.lectores import FilaLeida, mercado_pago
from conciliador.revisar import revisar, texto_sugerido

DEMO = Path(__file__).parent.parent / "demo"
TITULAR = "José María Ejemplo"


def tipo(descripcion, monto=-100):
    return clasificar.tipo_mercado_pago(descripcion, monto, TITULAR)


def gasto(motor, numero, descripcion, pesos, **extras):
    fila = FilaLeida(
        numero, date(2026, 10, 5), descripcion, -pesos * 100, tipo="consumo", **extras
    )
    base.guardar_movimientos(motor, "mercado_pago", [fila])


def buscar(motor, descripcion):
    with base.Session(motor) as sesion:
        return sesion.scalar(
            select(base.Movimiento).where(base.Movimiento.descripcion == descripcion)
        )


def test_transferencia_propia_sin_importar_orden_ni_acentos():
    assert tipo("Transferencia enviada Ejemplo Jose Maria") == "transferencia_propia"
    assert tipo("Transferencia recibida EJEMPLO JOSE MARIA", 100) == "transferencia_propia"
    assert tipo("Ingreso de dinero", 100) == "transferencia_propia"


def test_un_familiar_con_el_mismo_apellido_es_un_gasto():
    assert tipo("Transferencia enviada Ejemplo Pablo Luis") == "consumo"


def test_ingresos_y_gastos():
    assert tipo("Rendimientos", 100) == "ingreso"
    assert tipo("Transferencia recibida Lucia Lopez", 100) == "ingreso"
    assert tipo("Pago de resumen Tarjeta de crédito") == "consumo"


def test_el_lector_usa_el_titular_del_pdf():
    filas = {f.fila.numero_operacion: f.fila for f in mercado_pago.leer(DEMO / "mercado_pago_octubre.pdf").filas}
    assert filas["180000000007"].tipo == "transferencia_propia"
    assert filas["180000000017"].tipo == "consumo"


def test_gana_la_regla_mas_especifica():
    reglas = [("Demo", "General"), ("Farmacia Demo", "Salud")]
    assert clasificar.categoria_por_regla("Pago FARMACIA DEMO", reglas) == "Salud"


def test_gasto_chico_sin_regla_va_a_gastos_varios(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto(motor, "1", "Kiosco", 49_999)
    base.aplicar_reglas(motor)
    fila = buscar(motor, "Kiosco")
    assert (fila.categoria, fila.pendiente) == ("Gastos varios", False)


def test_50000_justos_sin_regla_queda_para_revisar(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto(motor, "1", "Mueblería", 50_000)
    base.aplicar_reglas(motor)
    assert buscar(motor, "Mueblería").pendiente is True


def test_gasto_grande_anticipado_no_se_revisa(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto(motor, "1", "Alquiler Demo", 300_000)
    base.reemplazar_plan(
        motor, plan.PlanLeido(fijos=[plan.FijoPlan("Alquiler", "alquiler demo", 1, "ARS", 1)])
    )
    base.aplicar_reglas(motor)
    assert buscar(motor, "Alquiler Demo").pendiente is False


def movimiento(descripcion, centavos, mes="2026-10", moneda="ARS"):
    return SimpleNamespace(
        descripcion=descripcion, monto_centavos=centavos, mes=mes, moneda=moneda
    )


def test_cuota_fuera_de_su_plan_no_se_vincula():
    cuotas = [plan.CuotaPlan("Tele", "TELE DEMO", 100, "ARS", 3, "2026-11")]
    assert clasificar.ultimo_mes_de_cuota("2026-11", 3) == "2027-01"
    assert clasificar.del_plan(movimiento("TELE DEMO", -100, "2027-01"), [], cuotas) == "Tele"
    assert clasificar.del_plan(movimiento("TELE DEMO", -100, "2027-02"), [], cuotas) is None


TELEFONO = [
    plan.FijoPlan("Celular", "Telefonía Demo", 2_500_000, "ARS", None),
    plan.FijoPlan("Fibra", "Telefonía Demo", 1_200_000, "ARS", None),
]


def test_cada_movimiento_va_al_monto_mas_cercano():
    assert clasificar.del_plan(movimiento("Telefonía Demo", -2_400_000), TELEFONO, []) == "Celular"
    assert clasificar.del_plan(movimiento("Telefonía Demo", -1_300_000), TELEFONO, []) == "Fibra"


def test_dos_pagos_parecidos_van_al_mismo_fijo():
    """No es uno a uno: si no, el segundo pago caería en la fibra y escondería un pago doble."""
    pagos = [movimiento("Telefonía Demo", -2_500_000), movimiento("Telefonía Demo", -2_600_000)]
    assert [clasificar.del_plan(p, TELEFONO, []) for p in pagos] == ["Celular", "Celular"]


def test_gana_el_candidato_en_la_misma_moneda():
    fijos = [
        plan.FijoPlan("Nube en pesos", "NUBE DEMO", 500, "ARS", None),
        plan.FijoPlan("Nube en dólares", "NUBE DEMO", 900, "USD", None),
    ]
    gasto_usd = movimiento("NUBE DEMO", -500, moneda="USD")
    assert clasificar.del_plan(gasto_usd, fijos, []) == "Nube en dólares"


def test_la_vinculacion_sigue_al_reimportar_el_plan(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto(motor, "1", "Telefonía Demo", 25_000)
    for _ in range(2):  # Cada importación del plan cambia los id; el concepto no.
        base.reemplazar_plan(motor, plan.PlanLeido(fijos=TELEFONO))
        base.aplicar_reglas(motor)
        assert buscar(motor, "Telefonía Demo").plan_concepto == "Celular"
    base.reemplazar_plan(motor, plan.PlanLeido())
    base.aplicar_reglas(motor)
    assert buscar(motor, "Telefonía Demo").plan_concepto is None


def test_plan_con_concepto_repetido_informa_error(tmp_path):
    archivo = tmp_path / "plan.csv"
    archivo.write_text(
        "tipo;concepto;texto;monto;moneda;dia;cuotas;primer_mes\n"
        "fijo;Luz;LUZ DEMO;100;ARS;;;\n"
        "fijo;Luz;OTRA DEMO;200;ARS;;;\n",
        encoding="utf-8",
    )
    leido = plan.leer(archivo)
    assert len(leido.fijos) == 1
    assert leido.errores == ["fila 3: concepto repetido: 'Luz'"]


def gasto_usd(centavos, cotizacion):
    return SimpleNamespace(
        descripcion="Nube", monto_centavos=centavos, moneda="USD",
        cotizacion_centavos=cotizacion, mes="2026-10",
    )


def test_gasto_en_dolares_sin_cotizacion_no_se_puede_evaluar():
    assert clasificar.decidir(gasto_usd(-9_000_000, None), [], [], []) == ("Gastos varios", False)


def test_gasto_en_dolares_se_compara_en_pesos():
    assert clasificar.decidir(gasto_usd(-4000, 150_000), [], [], [])[1] is True
    assert clasificar.decidir(gasto_usd(-3000, 150_000), [], [], [])[1] is False


def test_revisar_guarda_la_regla_y_categoriza_a_los_parecidos(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto(motor, "1", "Pago Mueblería Demo", 60_000)
    gasto(motor, "2", "Pago Mueblería Demo Sur", 70_000)
    base.aplicar_reglas(motor)
    respuestas = iter(["Hogar", ""])
    revisar(motor, lambda _: next(respuestas), lambda _: None)

    assert buscar(motor, "Pago Mueblería Demo").categoria_manual is True
    parecido = buscar(motor, "Pago Mueblería Demo Sur")
    assert (parecido.categoria, parecido.pendiente) == ("Hogar", False)
    assert parecido.categoria_manual is False


def test_una_regla_nueva_no_pisa_lo_puesto_a_mano(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto(motor, "1", "Pago Librería", 60_000)
    gasto(motor, "2", "Pago Librería Centro", 60_000)
    base.aplicar_reglas(motor)
    primero, segundo = base.pendientes(motor)
    base.resolver_pendiente(motor, primero.id, "Regalos", None)
    base.resolver_pendiente(motor, segundo.id, "Estudio", "Librería")
    assert buscar(motor, "Pago Librería").categoria == "Regalos"


def test_saltear_no_cambia_nada(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto(motor, "1", "Pago Mueblería", 60_000)
    base.aplicar_reglas(motor)
    revisar(motor, lambda _: "", lambda _: None)
    assert buscar(motor, "Pago Mueblería").pendiente is True


def test_un_cambio_deja_de_ser_gasto_y_no_guarda_regla(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto(motor, "1", "Compra Demo USDT", 80_000)
    base.aplicar_reglas(motor)
    revisar(motor, lambda _: "cambio", lambda _: None)

    movimiento = buscar(motor, "Compra Demo USDT")
    assert (movimiento.tipo, movimiento.pendiente) == ("cambio", False)
    assert base.pendientes(motor) == []
    with base.Session(motor) as sesion:
        assert sesion.scalars(select(base.Regla)).all() == []


def test_el_texto_sugerido_saca_lo_generico():
    assert texto_sugerido("Transferencia enviada Pedro Gomez") == "Pedro Gomez"
    assert texto_sugerido("Pago con QR Kiosco Demo SA") == "Kiosco Demo SA"


def test_plan_acepta_los_formatos_de_excel():
    assert plan.monto_a_centavos("1234,56") == 123456
    assert plan.monto_a_centavos("1.234,56") == 123456
    assert plan.monto_a_centavos("1234.56") == 123456
    assert plan.monto_a_centavos("2.500.000") == 250000000


def test_plan_informa_filas_malas_y_sigue(tmp_path):
    ruta = tmp_path / "plan.csv"
    ruta.write_text(
        "tipo;concepto;texto;monto;moneda;dia;cuotas;primer_mes\n"
        "fijo;Luz;LUZ;1000,00;ARS;5;;\n"
        "otro;Mal;MAL;1,00;ARS;;;\n"
        "cuota;Mal;MAL;1,00;ARS;;3;noviembre\n",
        encoding="utf-8",
    )
    leido = plan.leer(ruta)
    assert len(leido.fijos) == 1
    assert len(leido.errores) == 2


def test_el_demo_deja_pendientes_solo_gastos_reales(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    importar_carpeta(DEMO, motor)
    descripciones = {p.descripcion for p in base.pendientes(motor)}
    assert "Transferencia enviada Pedro Inventado Gomez" in descripciones
    assert "Transferencia enviada Titular Demo Ejemplo" not in descripciones
    assert buscar(motor, "Transferencia recibida Lucia Ficticia Lopez").categoria is None


def test_en_la_base_todo_gasto_es_negativo_sin_importar_la_fuente(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    importar_carpeta(DEMO, motor)
    assert buscar(motor, "Pago Farmacia Demo").monto_centavos == -1299999
    assert buscar(motor, "SUPER DEMO 99").monto_centavos == -4130000
    assert buscar(motor, "DESCUENTO DEMO").monto_centavos == 2600000


def test_compara_desde_el_inicio_de_cada_palabra():
    assert not clasificar.coincide("CIO", "Pago de servicio Internet")
    assert clasificar.coincide("CIO", "Pago Instituto CIO Ingles")
    assert clasificar.coincide("ONEILL", "O'NEILL TIENDA")
    assert clasificar.coincide("TIENDA", "PAGO *TiendaPremium")
    assert clasificar.coincide("Tienda Centro", "121-TIENDA CENTRO DEMO")
