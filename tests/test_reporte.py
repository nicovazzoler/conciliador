from datetime import date
from pathlib import Path

import pytest

from conciliador import base, clasificar, cotizaciones, manual, plan, reporte
from conciliador.importar import importar_carpeta
from conciliador.lectores import FilaLeida

DEMO = Path(__file__).parent.parent / "demo"


def demo(tmp_path):
    motor = base.conectar(tmp_path / "demo.db")
    importar_carpeta(DEMO, motor)
    return motor


def test_fijos_de_la_demo(tmp_path):
    """Con la demo hay un caso de cada alerta: más caro y sin debitar."""
    fijos = {f["concepto"]: f for f in base.consultar(demo(tmp_path), "fijos", mes="2026-10")}
    assert (fijos["Internet"]["estado"], fijos["Internet"]["cobrado_centavos"]) == ("más caro", 2_109_876)
    assert (fijos["Obra social"]["estado"], fijos["Obra social"]["pagos"]) == ("sin debitar", 0)


def test_un_fijo_sin_pagos_en_el_mes_no_desaparece(tmp_path):
    """El filtro de mes va en el ON: en el WHERE, el LEFT JOIN perdería los fijos sin pagos."""
    fijos = base.consultar(demo(tmp_path), "fijos", mes="2030-01")
    assert {f["estado"] for f in fijos} == {"sin datos"}
    assert len(fijos) == 2


def cuotas(motor, mes):
    return {c["concepto"]: c for c in base.consultar(motor, "cuotas", mes=mes)}


def test_cuotas_de_la_demo(tmp_path):
    """Octubre: la 02/06 de Zapatillas queda sin datos, porque no hay resumen que venza en octubre.
    Noviembre: llega la 03/06, falta la 01/03 de Heladera y hay dos cuotas sin plan."""
    motor = demo(tmp_path)
    octubre = cuotas(motor, "2026-10")
    assert (octubre["Zapatillas"]["esperada"], octubre["Zapatillas"]["estado"]) == ("02/06", "sin datos")
    noviembre = cuotas(motor, "2026-11")
    assert noviembre["Zapatillas"]["estado"] == "bien"
    assert (noviembre["Heladera"]["esperada"], noviembre["Heladera"]["estado"]) == ("01/03", "falta")
    assert {c for c, f in noviembre.items() if f["estado"] == "sin plan"} == {
        "ELECTRO INVENTADO", "ROPA DEMO"
    }


def con_cuotas(tmp_path, cobradas, cantidad=3, primer_mes="2026-11"):
    """Una cuota de plan 'Tele' y los cobros dados como (número de operación, mes, cuota)."""
    motor = base.conectar(tmp_path / "p.db")
    filas = [
        FilaLeida(numero, date(2026, 10, 1), "TELE DEMO", -100_000, tipo="cuota", mes=mes, cuota=cuota)
        for numero, mes, cuota in cobradas
    ]
    base.guardar_movimientos(motor, "tarjeta_comafi", filas)
    plan_tele = plan.CuotaPlan("Tele", "TELE DEMO", 100_000, "ARS", cantidad, primer_mes)
    base.reemplazar_plan(motor, plan.PlanLeido(cuotas=[plan_tele]))
    base.aplicar_reglas(motor)
    return motor


def test_numero_de_cuota_cruza_el_anio(tmp_path):
    """Plan desde 2026-11 en 3 cuotas: en 2027-01 se espera la 03/03 y en 2027-02 ninguna."""
    motor = con_cuotas(tmp_path, [("1", "2027-01", "03/03")])
    assert (cuotas(motor, "2027-01")["Tele"]["esperada"], cuotas(motor, "2027-01")["Tele"]["estado"]) == (
        "03/03", "bien"
    )
    assert cuotas(motor, "2027-02") == {}


def test_dos_cobros_de_la_misma_cuota_es_repetida(tmp_path):
    motor = con_cuotas(tmp_path, [("1", "2026-12", "02/03"), ("2", "2026-12", "02/03")])
    assert cuotas(motor, "2026-12")["Tele"]["estado"] == "repetida"


def test_otro_numero_avisa_que_el_plan_esta_corrido(tmp_path):
    motor = con_cuotas(tmp_path, [("1", "2026-12", "03/03")])
    assert cuotas(motor, "2026-12")["Tele"]["estado"] == "otro número"


def gasto_simple(motor, numero, descripcion, centavos, dia=5):
    fila = FilaLeida(numero, date(2026, 10, dia), descripcion, -centavos, tipo="consumo")
    base.guardar_movimientos(motor, "mercado_pago", [fila])


def test_los_porcentajes_suman_100(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    base.guardar_cotizaciones(motor, [
        cotizaciones.CotizacionLeida(date(2026, 10, 1), 140_000, 150_000),
        cotizaciones.CotizacionLeida(date(2026, 10, 31), 140_000, 150_000),
    ])
    gasto_simple(motor, "1", "SUPER DEMO", 3_000_000)
    gasto_simple(motor, "2", "SUPER DEMO", 1_500_000)
    gasto_simple(motor, "3", "BAR DEMO", 1_000_000)
    base.asignar_cotizaciones(motor)
    with base.Session(motor) as sesion, sesion.begin():
        sesion.add_all([base.Regla(valor="SUPER DEMO", categoria="Super"), base.Regla(valor="BAR DEMO", categoria="Bar")])
    base.aplicar_reglas(motor)

    filas = base.consultar(motor, "categorias", mes="2026-10")
    assert [f["categoria"] for f in filas] == ["Super", "Bar"]
    assert sum(f["porcentaje"] for f in filas) == 100
    assert {f["sin_usd"] for f in filas} == {0}


def tope(motor):
    return base.consultar(motor, "tope", mes="2026-10", tope=clasificar.TOPE_DIARIO_CENTAVOS)


def test_dia_sobre_el_tope_en_la_demo(tmp_path):
    (dia,) = tope(demo(tmp_path))
    assert (dia["fecha"], dia["pesos_centavos"]) == ("2026-10-05", 20_750_100)


def test_los_fijos_no_cuentan_para_el_tope(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto_simple(motor, "1", "Alquiler Demo", 30_000_000)
    base.reemplazar_plan(
        motor, plan.PlanLeido(fijos=[plan.FijoPlan("Alquiler", "Alquiler Demo", 30_000_000, "ARS", 5)])
    )
    base.aplicar_reglas(motor)
    assert tope(motor) == []


def test_200000_justos_no_superan_el_tope(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    gasto_simple(motor, "1", "Compra Demo", 20_000_000, dia=5)
    gasto_simple(motor, "2", "Compra Demo", 20_000_001, dia=6)
    assert [d["fecha"] for d in tope(motor)] == ["2026-10-06"]


def resumenes(motor, mes="2026-11"):
    return {r["tarjeta"]: r for r in base.consultar(motor, "resumenes", mes=mes)}


def resumen(motor, tarjeta, cierre, vencimiento, pesos, dolares=0, percepcion=0, numero="1"):
    with base.Session(motor) as sesion, sesion.begin():
        sesion.add(base.Resumen(
            tarjeta=tarjeta, numero=numero, cierre=cierre, vencimiento=vencimiento,
            total_pesos_centavos=pesos, total_dolares_centavos=dolares, percepcion_centavos=percepcion,
        ))


def pago_del_banco(motor, numero, fecha, centavos, moneda="ARS"):
    """El 'SU PAGO' que trae el resumen siguiente: positivo, con la fuente de la tarjeta."""
    fila = FilaLeida(numero, fecha, "SU PAGO DEMO", centavos, moneda, tipo="pago")
    base.guardar_movimientos(motor, "tarjeta_comafi", [fila])


def test_resumen_sin_pagos_es_impago_y_no_cuenta_el_pago_anterior_al_cierre(tmp_path):
    """El 'SU PAGO' del 07/10 de la demo paga el resumen de septiembre, no el de octubre."""
    comafi = resumenes(demo(tmp_path))["tarjeta_comafi"]
    assert (comafi["estado"], comafi["a_pagar_pesos"], comafi["a_pagar_usd"]) == ("impago", 5_692_050, 4000)


def test_resumen_con_saldo_a_favor_no_hay_nada_que_pagar(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    resumen(motor, "tarjeta_nacion", date(2026, 10, 29), date(2026, 11, 11), pesos=-400_000)
    assert resumenes(motor)["tarjeta_nacion"]["estado"] == "nada que pagar"


def test_aviso_parcial_dice_cuanto_falta(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    resumen(motor, "tarjeta_comafi", date(2026, 10, 29), date(2026, 11, 11), 10_000_000, percepcion=2_000_000)
    manual.registrar_pago(motor, "tarjeta_comafi", "50000", date(2026, 11, 10), mostrar=print)
    comafi = resumenes(motor)["tarjeta_comafi"]
    assert (comafi["estado"], comafi["falta_pesos"]) == ("parcial", 3_000_000)


def test_aviso_completo_y_despues_confirmado(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    resumen(motor, "tarjeta_comafi", date(2026, 10, 29), date(2026, 11, 11), 10_000_000, dolares=500)
    manual.registrar_pago(motor, "tarjeta_comafi", "100000", date(2026, 11, 10), mostrar=print)
    assert resumenes(motor)["tarjeta_comafi"]["estado"] == "parcial"  # Faltan los dólares.
    manual.registrar_pago(motor, "tarjeta_comafi", "5", date(2026, 11, 10), "USD", mostrar=print)
    assert resumenes(motor)["tarjeta_comafi"]["estado"] == "avisado"

    resumen(motor, "tarjeta_comafi", date(2026, 11, 26), date(2026, 12, 9), 0, numero="2")
    pago_del_banco(motor, "a", date(2026, 11, 10), 10_000_000)
    pago_del_banco(motor, "b", date(2026, 11, 10), 500, "USD")
    assert resumenes(motor)["tarjeta_comafi"]["estado"] == "confirmado"


def test_un_resumen_viejo_impago_sigue_apareciendo(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    resumen(motor, "tarjeta_comafi", date(2026, 10, 29), date(2026, 11, 11), 10_000_000)
    assert resumenes(motor, mes="2027-01")["tarjeta_comafi"]["estado"] == "impago"
    manual.registrar_pago(motor, "tarjeta_comafi", "100000", date(2026, 11, 10), mostrar=print)
    pago_del_banco(motor, "a", date(2026, 11, 10), 10_000_000)
    assert resumenes(motor, mes="2027-01") == {}


def test_el_reporte_de_la_demo_tiene_un_caso_de_cada_alerta(tmp_path):
    """La condición de 'lista' de la etapa 1. La demo tiene el Mercado Pago de octubre y resúmenes
    que vencen en noviembre, así que los fijos se ven en octubre y las cuotas en noviembre."""
    motor = demo(tmp_path)
    octubre, noviembre = reporte.armar(motor, "2026-10"), reporte.armar(motor, "2026-11")
    estados_fijos = {f["estado"] for f in octubre.fijos}
    assert {"más caro", "sin debitar"} <= estados_fijos
    assert "falta" in {c["estado"] for c in noviembre.cuotas}
    assert "sin plan" in {c["estado"] for c in noviembre.cuotas}
    assert octubre.dias_sobre_tope
    assert "impago" in {r["estado"] for r in noviembre.resumenes}
    assert octubre.totales["pesos_centavos"] > 0  # Sin USD: los tests no bajan cotizaciones.


def test_un_mes_mal_escrito_da_error(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    for malo in ("2026-13", "26-11", "2026-11' OR '1'='1"):
        with pytest.raises(ValueError, match="mes inválido"):
            reporte.armar(motor, malo)


def test_el_texto_no_consulta_la_base():
    """Presentación separada de los datos: texto() funciona sin motor."""
    datos = reporte.Reporte(
        mes="2026-10",
        totales={"pesos_centavos": 150_000, "dolares_centavos": 0, "total_usd_centavos": 100, "sin_usd": 0},
        categorias=[], fijos=[], cuotas=[], dias_sobre_tope=[], resumenes=[], pendientes=0,
        importado={"mercado_pago": 1, "resumenes": None},
    )
    salida = reporte.texto(datos)
    assert salida.startswith("OCTUBRE 2026\nImportado: Mercado Pago sí; resúmenes que vencen este mes: ninguno")
    assert "\nGastado: $ 1.500,00" in salida
    assert salida.count("(nada que avisar)") == 5


def test_sin_mercado_pago_del_mes_los_fijos_no_faltan_y_con_el_pdf_si(tmp_path):
    motor = base.conectar(tmp_path / "p.db")
    base.reemplazar_plan(motor, plan.PlanLeido(fijos=[plan.FijoPlan("Luz", "LUZ DEMO", 100, "ARS", 5)]))
    assert base.consultar(motor, "fijos", mes="2026-10")[0]["estado"] == "sin datos"
    gasto_simple(motor, "1", "Otra cosa", 500)  # Cualquier movimiento de Mercado Pago del mes.
    assert base.consultar(motor, "fijos", mes="2026-10")[0]["estado"] == "sin debitar"


def test_con_un_resumen_que_vence_en_el_mes_la_cuota_falta(tmp_path):
    motor = con_cuotas(tmp_path, [], primer_mes="2026-12")
    assert cuotas(motor, "2026-12")["Tele"]["estado"] == "sin datos"
    resumen(motor, "tarjeta_comafi", date(2026, 11, 26), date(2026, 12, 9), 0)
    assert cuotas(motor, "2026-12")["Tele"]["estado"] == "falta"
