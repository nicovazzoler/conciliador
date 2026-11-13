from dataclasses import replace
from datetime import date
from pathlib import Path

from reportlab.pdfgen import canvas

from conciliador.lectores import a_centavos, mercado_pago

DEMO = Path(__file__).parent.parent / "demo" / "mercado_pago_octubre.pdf"


def test_lee_todas_las_filas_de_todas_las_paginas():
    resumen = mercado_pago.leer(DEMO)
    assert len(resumen.filas) == 20
    assert resumen.errores == []


def test_une_las_descripciones_partidas():
    filas = {f.fila.numero_operacion: f.fila for f in mercado_pago.leer(DEMO).filas}
    assert filas["180000000005"].descripcion == "Transferencia recibida TITULAR DEMO EJEMPLO"
    assert filas["180000000006"].descripcion == "Pago de resumen Tarjeta de crédito"
    assert filas["180000000009"].fecha == date(2026, 10, 3)


def test_convierte_a_centavos_exactos():
    assert a_centavos("-1.234,56") == -123456
    assert a_centavos("2.500.000,00") == 250000000
    assert a_centavos("0,29") == 29


def test_un_resumen_correcto_pasa_la_verificacion():
    assert mercado_pago.verificar(mercado_pago.leer(DEMO)) == []


def test_una_fila_perdida_se_detecta():
    resumen = mercado_pago.leer(DEMO)
    del resumen.filas[3]
    problemas = mercado_pago.verificar(resumen)
    assert "las entradas no coinciden con el total del resumen" in problemas
    assert any("saldo no cierra" in p for p in problemas)


def test_un_monto_mal_leido_se_detecta():
    resumen = mercado_pago.leer(DEMO)
    original = resumen.filas[1]
    resumen.filas[1] = replace(
        original, fila=replace(original.fila, monto_centavos=original.fila.monto_centavos - 1)
    )
    assert mercado_pago.verificar(resumen) != []


def test_otro_pdf_no_se_reconoce(tmp_path):
    ajeno = tmp_path / "ajeno.pdf"
    lienzo = canvas.Canvas(str(ajeno))
    lienzo.drawString(40, 800, "Resumen de otra cosa")
    lienzo.save()
    assert mercado_pago.leer(ajeno) is None
