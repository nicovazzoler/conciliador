// Lo que requiere atención en un mes, armado como renglones de comprobante. Sin React: se prueba solo.
import type { Reporte } from "./api";
import { diaYMes, plata } from "./formato";

export type Tono = "mal" | "ojo" | "neutro";

/** Cómo se dibuja el filete: lleno, algo pasó y cerró mal; punteado, algo que no llegó. */
export type Forma = "lleno" | "punteado";

export type Renglon = {
  clave: string;
  concepto: string;
  monto: string;
  sello: string;
  tono: Tono;
  forma: Forma;
  enlace?: { texto: string; href: string }; // Qué hacer con esto.
};

const ORDEN_TONO: Record<Tono, number> = { mal: 0, ojo: 1, neutro: 2 };

export function aAtender(reporte: Reporte, { fijos = true }: { fijos?: boolean } = {}): Renglon[] {
  const renglones: Renglon[] = [];
  const mes = reporte.mes;
  const pago = { texto: "Cargar el pago", href: "#/cargar/pago" };
  const plan = { texto: "Ver en el plan", href: "#/plan" };
  const cobros = (concepto: string) => ({ texto: "Ver los cobros", href: `#/movimientos/${mes}/plan:${encodeURIComponent(concepto)}` });

  for (const r of reporte.resumenes) {
    const tarjeta = nombreTarjeta(r.tarjeta);
    const falta = r.falta_usd > 0 ? `${plata(r.falta_pesos)} + ${plata(r.falta_usd, "USD")}` : plata(r.falta_pesos);
    if (r.estado === "impago")
      renglones.push(fila(`resumen-${r.numero}`, `Resumen ${tarjeta} · vence ${diaYMes(r.vencimiento)}`, falta, "IMPAGO", "mal", "lleno", pago));
    if (r.estado === "parcial")
      renglones.push(fila(`resumen-${r.numero}`, `Resumen ${tarjeta} · falta`, falta, "PARCIAL", "ojo", "lleno", pago));
    if (r.estado === "avisado")
      renglones.push(fila(`resumen-${r.numero}`, `Resumen ${tarjeta}`, plata(r.a_pagar_pesos), "AVISADO", "neutro", "punteado", pago));
  }

  for (const f of fijos ? reporte.fijos : []) {
    const anotado = plata(f.anotado_centavos, f.moneda);
    const cobrado = plata(f.cobrado_centavos, f.moneda);
    if (f.estado === "sin debitar") renglones.push(fila(`fijo-${f.concepto}`, f.concepto, anotado, "SIN DEBITAR", "mal", "punteado", plan));
    if (f.estado === "más caro")
      renglones.push(fila(`fijo-${f.concepto}`, `${f.concepto} · ${veces(f.pagos)}`, cobrado, "MÁS CARO", "ojo", "lleno", plan));
    if (f.estado === "más barato")
      renglones.push(fila(`fijo-${f.concepto}`, `${f.concepto} · anotado ${anotado}`, cobrado, "MÁS BARATO", "ojo", "lleno", plan));
  }

  reporte.cuotas.forEach((c, i) => {
    const clave = `cuota-${c.concepto}-${i}`;
    const monto = plata(c.monto_centavos);
    if (c.estado === "falta") renglones.push(fila(clave, `${c.concepto} · cuota ${c.esperada}`, monto, "FALTA", "mal", "punteado", plan));
    if (c.estado === "repetida") renglones.push(fila(clave, `${c.concepto} · ${c.cobros} cobros`, monto, "REPETIDA", "mal", "lleno", cobros(c.concepto)));
    if (c.estado === "otro número")
      renglones.push(fila(clave, `${c.concepto} · llegó ${c.llegaron}, se esperaba ${c.esperada}`, monto, "OTRO NÚMERO", "ojo", "lleno", cobros(c.concepto)));
    if (c.estado === "sin plan")
      renglones.push(fila(clave, `${c.concepto} · cuota ${c.llegaron}`, monto, "SIN PLAN", "ojo", "lleno", { texto: "Agregarla al plan", href: "#/plan" }));
  });

  for (const d of reporte.dias_sobre_tope)
    renglones.push(
      fila(`tope-${d.fecha}`, `${diaYMes(d.fecha)} · ${d.movimientos} gastos`, plata(d.pesos_centavos), "TOPE", "ojo", "lleno", {
        texto: "Ver ese día",
        href: `#/movimientos/${mes}/dia:${d.fecha}`,
      }),
    );

  // Estable: dentro de un mismo tono se respeta el orden de arriba (resúmenes, fijos, cuotas, días).
  return renglones.sort((a, b) => ORDEN_TONO[a.tono] - ORDEN_TONO[b.tono]);
}

/** Cuántas cosas se controlaron este mes: fijos y cuotas con datos, días con tope y resúmenes. */
export function controlados(reporte: Reporte): number {
  const conDatos = (e: string) => e !== "sin datos";
  return (
    reporte.fijos.filter((f) => conDatos(f.estado)).length +
    reporte.cuotas.filter((c) => conDatos(c.estado)).length +
    reporte.resumenes.length +
    reporte.dias_sobre_tope.length
  );
}

function fila(clave: string, concepto: string, monto: string, sello: string, tono: Tono, forma: Forma, enlace?: Renglon["enlace"]): Renglon {
  return { clave, concepto, monto, sello, tono, forma, enlace };
}

function veces(pagos: number): string {
  return pagos === 1 ? "1 pago" : `${pagos} pagos`;
}

export function nombreTarjeta(tarjeta: string): string {
  return { tarjeta_comafi: "Comafi", tarjeta_nacion: "Nación" }[tarjeta] ?? tarjeta;
}
