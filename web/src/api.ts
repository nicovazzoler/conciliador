// Las llamadas a la API. Los tipos salen de src/tipos.ts, generado con `npm run tipos`.
import type { components } from "./tipos";

export type Esquemas = components["schemas"];
export type Reporte = Esquemas["Reporte"];

/** Un error de la API con el mensaje que mandó el servidor, para mostrarlo tal cual. */
export class ErrorApi extends Error {
  constructor(
    readonly estado: number,
    mensaje: string,
  ) {
    super(mensaje);
  }
}

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const respuesta = await fetch(ruta, opciones);
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => null);
    const detalle = typeof cuerpo?.detail === "string" ? cuerpo.detail : respuesta.statusText;
    throw new ErrorApi(respuesta.status, detalle);
  }
  return respuesta.json() as Promise<T>;
}

export function traerReporte(mes: string, opciones?: RequestInit): Promise<Reporte> {
  return pedir<Reporte>(`/api/reporte/${encodeURIComponent(mes)}`, opciones);
}
