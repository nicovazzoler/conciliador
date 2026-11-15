// De dónde viene cada movimiento. Un solo lugar con los nombres, para Movimientos y Revisar.

const NOMBRES: Record<string, [nombre: string, sigla: string]> = {
  mercado_pago: ["Mercado Pago", "MP"],
  tarjeta_comafi: ["Tarjeta Comafi", "CF"],
  tarjeta_nacion: ["Tarjeta Nación", "BN"],
  manual: ["Cargado a mano", "✎"],
};

const MEDIOS: Record<string, string> = { efectivo: "efectivo", debito: "débito", transferencia: "transferencia" };

/** "tarjeta_comafi" → "Tarjeta Comafi". Una fuente que no se conoce se muestra tal cual. */
export function nombreFuente(fuente: string, medio?: string | null): string {
  const nombre = NOMBRES[fuente]?.[0] ?? fuente;
  return fuente === "manual" && medio ? `${nombre}, ${MEDIOS[medio] ?? medio}` : nombre;
}

/** Dos letras para el círculo de la fila: "MP", "CF", "BN". */
export function siglaFuente(fuente: string): string {
  return NOMBRES[fuente]?.[1] ?? fuente.slice(0, 2).toUpperCase();
}
