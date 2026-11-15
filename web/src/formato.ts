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

/** La fecha de hoy, como la pide la API: "2026-11-15". */
export function hoy(fecha: Date = new Date()): string {
  return `${mesActual(fecha)}-${String(fecha.getDate()).padStart(2, "0")}`;
}

/** "2026-01", -1 → "2025-12": mueve un mes cruzando el cambio de año. */
export function moverMes(mes: string, cuanto: number): string {
  const [anio, numero] = mes.split("-").map(Number) as [number, number];
  const total = anio * 12 + (numero - 1) + cuanto;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

/** "2026-10" → "O": la inicial del mes, para las barras de los meses anteriores. */
export function inicialMes(mes: string): string {
  return (NOMBRES[Number(mes.slice(5, 7)) - 1] ?? "?").charAt(0).toUpperCase();
}

/** "2026-10-05" → "05/10". */
export function diaYMes(fecha: string): string {
  return `${fecha.slice(8, 10)}/${fecha.slice(5, 7)}`;
}

/** Un decimal que llega como texto ("2610.4545"), con miles y hasta `decimales` decimales. Solo para mostrar. */
export function decimal(texto: string, decimales = 2): string {
  return new Intl.NumberFormat("es-AR", { maximumFractionDigits: decimales }).format(Number(texto));
}
