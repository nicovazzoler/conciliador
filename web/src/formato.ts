// Formato para mostrar. Los montos llegan en centavos enteros y se formatean sin pasar por float.

const miles = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });

/** 12345678 → "123.456,78". El signo se muestra aparte, donde haga falta. */
export function importe(centavos: number): string {
  const absoluto = Math.abs(centavos);
  const enteros = Math.trunc(absoluto / 100);
  const resto = absoluto % 100;
  return `${miles.format(enteros)},${String(resto).padStart(2, "0")}`;
}

/** 12345678, "ARS" → "$ 123.456,78"; 8824, "USD" → "U$D 88,24". */
export function plata(centavos: number, moneda: string = "ARS"): string {
  return `${moneda === "USD" ? "U$D" : "$"} ${importe(centavos)}`;
}

const NOMBRES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

/** "2026-10" → "octubre 2026". */
export function nombreMes(mes: string): string {
  const [anio, numero] = mes.split("-");
  return `${NOMBRES[Number(numero) - 1] ?? "?"} ${anio}`;
}

/** El mes de hoy, como lo pide la API: "2026-11". */
export function mesActual(hoy: Date = new Date()): string {
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

/** "2026-10-05" → "05/10". */
export function diaYMes(fecha: string): string {
  return `${fecha.slice(8, 10)}/${fecha.slice(5, 7)}`;
}
