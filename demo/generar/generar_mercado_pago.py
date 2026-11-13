"""Genera un resumen de Mercado Pago con datos inventados y el mismo formato que el real."""
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SALDO_INICIAL = Decimal("10000.00")
FILAS_POR_PAGINA = 14
MOVIMIENTOS = [
    ("01-10-2026", "Rendimientos", "1750000000001", "12.34"),
    ("01-10-2026", "Pago SUBE Viajes", "180000000002", "-1450.00"),
    ("01-10-2026", "Transferencia enviada Ana|Demo Perez", "180000000003", "-7100.00"),
    ("01-10-2026", "Ingreso de dinero", "180000000004", "52000.00"),
    ("02-10-2026", "Transferencia recibida|TITULAR DEMO EJEMPLO", "180000000005", "870000.00"),
    ("02-10-2026", "Pago de resumen Tarjeta de|crédito", "180000000006", "-98765.43"),
    ("02-10-2026", "Transferencia enviada|Titular Demo Ejemplo", "180000000007", "-245000.00"),
    ("03-10-2026", "Pago Telefonía Demo", "180000000008", "-23456.78"),
    ("03-10-2026", "Pago con QR Kiosco Demo|SA", "180000000009", "-1900.00"),
    ("04-10-2026", "Pago de servicio Internet|Demo Hogar", "180000000010", "-21098.76"),
    ("05-10-2026", "Transferencia enviada Pedro|Inventado Gomez", "180000000011", "-180000.00"),
    ("05-10-2026", "Pago PedidosDemo", "180000000012", "-18500.50"),
    ("06-10-2026", "Rendimientos", "1750000000013", "87.10"),
    ("07-10-2026", "Pago con QR Panadería Demo", "180000000014", "-3300.00"),
    ("08-10-2026", "Transferencia recibida Lucia|Ficticia Lopez", "180000000015", "41500.00"),
    ("09-10-2026", "Pago de transporte SUBE|Viajes", "180000000016", "-1620.40"),
    ("10-10-2026", "Transferencia enviada|Vecino Demo Ejemplo", "180000000017", "-56500.00"),
    ("12-10-2026", "Pago Farmacia Demo", "180000000018", "-12999.99"),
    ("15-10-2026", "Rendimientos", "1750000000019", "45.60"),
    ("20-10-2026", "Pago Supermercado Demo", "180000000020", "-61250.75"),
]


def pesos(valor: Decimal) -> str:
    texto = f"{valor:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"$ {texto}"


def encabezado_tabla(lienzo: canvas.Canvas, y: float) -> None:
    lienzo.setFont("Helvetica-Bold", 8)
    lienzo.drawString(250, y + 9, "ID de la")
    lienzo.drawString(40, y, "Fecha")
    lienzo.drawString(100, y, "Descripción")
    lienzo.drawString(370, y, "Valor")
    lienzo.drawString(470, y, "Saldo")
    lienzo.drawString(250, y - 9, "operación")
    lienzo.setFont("Helvetica", 8)


def generar(destino: Path) -> None:
    montos = [Decimal(m[3]) for m in MOVIMIENTOS]
    entradas = sum(m for m in montos if m > 0)
    salidas = sum(m for m in montos if m < 0)
    saldo_final = SALDO_INICIAL + entradas + salidas
    paginas = (len(MOVIMIENTOS) + FILAS_POR_PAGINA - 1) // FILAS_POR_PAGINA

    lienzo = canvas.Canvas(str(destino), pagesize=A4)
    lienzo.setFont("Helvetica-Bold", 12)
    lienzo.drawString(40, 800, "RESUMEN DE CUENTA EN PESOS")
    lienzo.setFont("Helvetica", 9)
    lienzo.drawString(40, 785, "Titular Demo Ejemplo")
    lienzo.drawString(40, 772, "CVU: 0000000000000000000000 CUIT/ CUIL: 20000000000")
    lienzo.drawString(40, 759, "Periodo: Del 1 al 31 de octubre de 2026")
    lienzo.drawString(40, 746, f"Entradas: {pesos(entradas)}")
    lienzo.drawString(
        40, 733, f"Saldo inicial: {pesos(SALDO_INICIAL)} Saldo final: {pesos(saldo_final)}"
    )
    lienzo.drawString(40, 720, f"Salidas: {pesos(salidas)}")

    saldo = SALDO_INICIAL
    y = 680.0
    encabezado_tabla(lienzo, y)
    for indice, (fecha, descripcion, numero, monto) in enumerate(MOVIMIENTOS):
        if indice and indice % FILAS_POR_PAGINA == 0:
            lienzo.drawString(280, 30, f"{indice // FILAS_POR_PAGINA}/{paginas}")
            lienzo.showPage()
            y = 780.0
            encabezado_tabla(lienzo, y)
        y -= 34
        saldo += Decimal(monto)
        partes = descripcion.split("|")
        lienzo.drawString(40, y, fecha)
        if len(partes) == 1:
            lienzo.drawString(100, y, partes[0])
        else:
            lienzo.drawString(100, y + 8, partes[0])
            lienzo.drawString(100, y - 8, partes[1])
        lienzo.drawString(250, y, numero)
        lienzo.drawString(370, y, pesos(Decimal(monto)))
        lienzo.drawString(470, y, pesos(saldo))
    lienzo.drawString(40, 45, "Fecha de generación: 07-11-2026")
    lienzo.drawString(280, 30, f"{paginas}/{paginas}")
    lienzo.save()


if __name__ == "__main__":
    generar(Path(__file__).parent.parent / "mercado_pago_octubre.pdf")
