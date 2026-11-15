// Las llamadas a la API. Los tipos salen de src/tipos.ts, generado con `npm run tipos`.
import type { components } from "./tipos";

export type Esquemas = components["schemas"];
export type Reporte = Esquemas["Reporte"];
export type GastoNuevo = Esquemas["GastoNuevo"];
export type PagoNuevo = Esquemas["PagoNuevo"];
export type Aviso = Esquemas["Aviso"];
export type Guardado = Esquemas["Guardado"];
export type Manual = Esquemas["Manual"];

/** Un error de la API con el mensaje que mandó el servidor, para mostrarlo tal cual. */
export class ErrorApi extends Error {
  constructor(
    readonly estado: number,
    mensaje: string,
  ) {
    super(mensaje);
  }
}

/** Lo que puede pasar al cargar un gasto: se guardó, o hay avisos que confirmar (409). */
export type ResultadoGasto =
  | { tipo: "guardado"; guardado: Guardado }
  | { tipo: "avisos"; avisos: Aviso[] };

async function leer<T>(respuesta: Response): Promise<T> {
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => null);
    throw new ErrorApi(respuesta.status, detalle(cuerpo) ?? respuesta.statusText);
  }
  return respuesta.status === 204 ? (undefined as T) : (respuesta.json() as Promise<T>);
}

/** FastAPI manda `detail` como texto (nuestros errores) o como lista (validación de Pydantic). */
function detalle(cuerpo: unknown): string | null {
  const valor = (cuerpo as { detail?: unknown } | null)?.detail;
  if (typeof valor === "string") return valor;
  if (Array.isArray(valor)) return valor.map((error) => error?.msg ?? String(error)).join("; ");
  return null;
}

function enviar(ruta: string, metodo: string, datos?: unknown): Promise<Response> {
  return fetch(ruta, {
    method: metodo,
    headers: datos === undefined ? undefined : { "Content-Type": "application/json" },
    body: datos === undefined ? undefined : JSON.stringify(datos),
  });
}

export type MesHistorial = Esquemas["MesHistorial"];

export async function traerHistorial(mes: string, meses = 6, opciones?: RequestInit): Promise<MesHistorial[]> {
  return leer<MesHistorial[]>(await fetch(`/api/historial/${encodeURIComponent(mes)}?meses=${meses}`, opciones));
}

export async function traerReporte(mes: string, opciones?: RequestInit): Promise<Reporte> {
  return leer<Reporte>(await fetch(`/api/reporte/${encodeURIComponent(mes)}`, opciones));
}

/** Un 409 no es un error: son los avisos que hay que confirmar antes de guardar. */
export async function cargarGasto(gasto: GastoNuevo): Promise<ResultadoGasto> {
  const respuesta = await enviar("/api/gastos", "POST", gasto);
  if (respuesta.status === 409) {
    const { avisos } = (await respuesta.json()) as Esquemas["Avisos"];
    return { tipo: "avisos", avisos };
  }
  return { tipo: "guardado", guardado: await leer<Guardado>(respuesta) };
}

export async function cargarPago(pago: PagoNuevo): Promise<Guardado> {
  return leer<Guardado>(await enviar("/api/pagos", "POST", pago));
}

export async function traerManuales(): Promise<Manual[]> {
  return leer<Manual[]>(await fetch("/api/manuales"));
}

export async function borrarManual(id: number): Promise<void> {
  return leer<void>(await enviar(`/api/manuales/${id}`, "DELETE"));
}
