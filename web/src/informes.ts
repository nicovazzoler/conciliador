// Cómo se lee el informe de un archivo importado. Sin React: se prueba solo.
import type { InformeArchivo } from "./api";
import type { Tono } from "./atender";

export type Lectura = { sello: string; tono: Tono | "bien"; detalle: string };

export function leerInforme(informe: InformeArchivo): Lectura {
  if (!informe.reconocido) {
    return {
      sello: "RECHAZADO",
      tono: "mal",
      detalle: informe.errores[0] ?? "no es un resumen conocido o la clave no es la correcta",
    };
  }
  const detalle = `${informe.nuevas} ${informe.nuevas === 1 ? "nueva" : "nuevas"} · ${informe.repetidas} ${
    informe.repetidas === 1 ? "repetida" : "repetidas"
  }`;
  if (informe.problemas.length > 0) return { sello: "NO CIERRA", tono: "ojo", detalle };
  if (informe.nuevas > 0) return { sello: "NUEVO", tono: "bien", detalle };
  return { sello: "YA ESTABA", tono: "neutro", detalle };
}
