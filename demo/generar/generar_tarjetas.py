"""Genera resúmenes de tarjeta con datos inventados y el mismo formato que los reales."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.pdfgen import canvas

COL_PESOS = 450
COL_DOLARES = 540

# Fecha, concepto, pesos, dólares.
CARGOS_COMAFI = [
    ("07/10/2026", "SU PAGO EN PESOS", "-100.000,00", "-"),
    ("07/10/2026", "SU PAGO EN USD", "-", "-20,00"),
    ("13/10/2026", "DEV.IMP. RG 5617 30%( 50000,00)", "-15.000,00", "-"),
    ("29/10/2026", "IMPUESTO DE SELLOS $", "1.200,00", "-"),
    ("29/10/2026", "IVA RG 4240 21%( 2000,00)", "420,00", "-"),
    ("29/10/2026", "DB.RG 5617 30% ( 60000,00 )", "18.000,00", "-"),
]
# Fecha, detalle, comprobante, importe, en dólares.
CONSUMOS_COMAFI = [
    ("10/08/2026", "ZAPATERIA DEMO C.03/06", "700101", "20.000,00", False),
    ("03/10/2026", "SUPER DEMO 99", "700102", "41.300,00", False),
    ("05/10/2026", "CINE INVENTADO", "700103", "9.000,50", False),
    ("10/10/2026", "NUBE DEMO USD", "700104", "7,00", True),
    ("13/10/2026", "SOFTWARE FICTICIO USD", "700105", "33,00", True),
]
COMAFI = {
    "saldo_pesos": "100.000,00",
    "saldo_dolares": "20,00",
    "total_pesos": "74.920,50",
    "total_dolares": "40,00",
}

# Sección, fecha, detalle, cuota, cupón, importe, en dólares.
CONSUMOS_NACION = [
    ("COMPRAS DEL MES", "13-Oct-26", "DESCUENTO DEMO", "", "00501", "-26000,00", False),
    ("COMPRAS DEL MES", "20-Oct-26", "RESTAURANTE DEMO", "", "00502", "64000,00", False),
    ("COMPRAS DEL MES", "21-Oct-26", "TIENDA EXTERIOR DEMO", "", "00503", "12,50", True),
    ("CUOTAS DEL MES", "13-Oct-26", "ROPA DEMO", "01/12", "00501", "7200,00", False),
    ("CUOTAS DEL MES", "17-Oct-26", "ELECTRO INVENTADO", "01/12", "00504", "8400,00", False),
]
NACION = {"pesos": "53600,00", "dolares": "12,50", "saldo": "53.600,00"}


def fila(lienzo, y, texto, importe, en_dolares):
    lienzo.drawString(40, y, texto)
    lienzo.drawRightString(COL_DOLARES if en_dolares else COL_PESOS, y, importe)


def generar_comafi(destino: Path) -> None:
    c = canvas.Canvas(str(destino), pagesize=A4)
    c.setFont("Helvetica", 8)
    textos = [
        "TARJETA DE CRÉDITO MASTERCARD",
        "TITULAR DEMO EJEMPLO Nro. de cuenta: 0000000000",
        "LIQ:003 - Resumen Nro.:000000111",
        "Cierre anterior: 01/10/2026 Próximo cierre: 26/11/2026 Cierre: 29/10/2026",
        "Vencimiento anterior: 13/10/2026 Próximo vencimiento: 09/12/2026 Vencimiento: 11/11/2026",
        "Saldo total ant.: Pago mín. ant.:",
        f"$ Total a pagar: {COMAFI['total_pesos']} | Pago mín.: 1.000,00",
        f"$ {COMAFI['saldo_pesos']} $ 1.000,00",
        f"U$D Total a pagar: {COMAFI['total_dolares']} | Pago mín.: 0,00",
        f"U$D {COMAFI['saldo_dolares']} U$D 0,00",
    ]
    y = 800
    for texto in textos:
        c.drawString(40, y, texto)
        y -= 14
    y -= 10
    c.drawString(40, y, "Consolidado")
    y -= 14
    c.drawString(40, y, "Fecha Detalle")
    c.drawRightString(COL_PESOS, y, "Pesos")
    c.drawRightString(COL_DOLARES, y, "Dólares")
    for fecha, concepto, pesos, dolares in CARGOS_COMAFI:
        y -= 13
        c.drawString(40, y, f"{fecha} {concepto}")
        c.drawRightString(COL_PESOS, y, pesos)
        c.drawRightString(COL_DOLARES, y, dolares)
    y -= 25
    c.drawString(40, y, "Detalle de consumo")
    y -= 14
    c.drawString(40, y, "Fecha Detalle Comprobante")
    c.drawRightString(COL_PESOS, y, "Pesos")
    c.drawRightString(COL_DOLARES, y, "Dólares")
    for fecha, detalle, comprobante, importe, en_dolares in CONSUMOS_COMAFI:
        y -= 13
        fila(c, y, f"{fecha} {detalle} {comprobante}", importe, en_dolares)
    y -= 13
    c.drawString(40, y, "TARJETA 0000 Total Consumos de TITULAR DEMO")
    c.drawRightString(COL_PESOS, y, "70.300,50")
    c.drawRightString(COL_DOLARES, y, "40,00")
    y -= 20
    c.drawString(40, y, "BANCO COMAFI S.A")
    c.save()


def generar_nacion(destino: Path, clave: str | None = None) -> None:
    cifrado = StandardEncryption(clave, canPrint=1) if clave else None
    c = canvas.Canvas(str(destino), pagesize=A4, encrypt=cifrado)
    c.setFont("Helvetica", 8)
    textos = [
        "TITULAR DEMO EJEMPLO HOJA 1/1",
        "CUIT Entidad 30-50001091-2",
        "MASTERCARD GOLD",
        "N° de Resumen 000000222",
        "Estado de cuenta al : 29-Oct-26 Saldo Actual: $ 53.600,00 U$S 12,50",
        "Vencimiento actual : 11-Nov-26 Pago Minimo: $ 0,00",
        "RESUMEN CONSOLIDADO PESOS DOLAR",
        "SALDO PENDIENTE 0,00 0,00",
        f"SALDO ACTUAL {NACION['saldo']} {NACION['dolares']}",
    ]
    y = 800
    for texto in textos:
        c.drawString(40, y, texto)
        y -= 14
    y -= 10
    c.drawString(40, y, "DETALLES DEL MES NRO CUPON")
    c.drawRightString(COL_PESOS, y, "PESOS")
    c.drawRightString(COL_DOLARES, y, "DOLAR")
    seccion = None
    for nombre, fecha, detalle, cuota, cupon, importe, en_dolares in CONSUMOS_NACION:
        if nombre != seccion:
            y -= 13
            c.drawString(100, y, nombre)
            seccion = nombre
        y -= 13
        texto = " ".join(p for p in (fecha, detalle, cuota, cupon) if p)
        fila(c, y, texto, importe, en_dolares)
    y -= 13
    c.drawString(100, y, "TOTAL TITULAR DEMO")
    c.drawRightString(COL_PESOS, y, NACION["pesos"])
    c.drawRightString(COL_DOLARES, y, NACION["dolares"])
    c.save()


if __name__ == "__main__":
    carpeta = Path(__file__).parent.parent
    generar_comafi(carpeta / "tarjeta_comafi_octubre.pdf")
    generar_nacion(carpeta / "tarjeta_nacion_octubre.pdf")
