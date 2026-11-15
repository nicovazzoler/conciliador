// Las llamadas a la API. Los tipos salen de src/tipos.ts, generado con `npm run tipos`.
import type { components } from "./tipos";

export type Esquemas = components["schemas"];
export type Reporte = Esquemas["Reporte"];
export type MesHistorial = Esquemas["MesHistorial"];
export type GastoNuevo = Esquemas["GastoNuevo"];
export type PagoNuevo = Esquemas["PagoNuevo"];
export type Aviso = Esquemas["Aviso"];
export type Guardado = Esquemas["Guardado"];
export type Manual = Esquemas["Manual"];
export type Pendiente = Esquemas["Pendiente"];
export type GrupoVarios = Esquemas["GrupoVarios"];
export type Importacion = Esquemas["Importacion"];
export type InformeArchivo = Esquemas["InformeArchivo"];

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

// Gastos.

export async function traerReporte(mes: string, opciones?: RequestInit): Promise<Reporte> {
  return leer<Reporte>(await fetch(`/api/reporte/${encodeURIComponent(mes)}`, opciones));
}

export async function traerHistorial(mes: string, meses = 6, opciones?: RequestInit): Promise<MesHistorial[]> {
  return leer<MesHistorial[]>(await fetch(`/api/historial/${encodeURIComponent(mes)}?meses=${meses}`, opciones));
}

// Cargar.

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

// Revisar.

export async function traerCategorias(): Promise<string[]> {
  return leer<string[]>(await fetch("/api/categorias"));
}

export async function traerPendientes(): Promise<Pendiente[]> {
  return leer<Pendiente[]>(await fetch("/api/pendientes"));
}

/** Con categoría (y regla opcional), o `cambio: true` si no fue un gasto. */
export async function resolverPendiente(
  id: number,
  resolucion: { categoria?: string; regla?: string | null; cambio?: boolean },
): Promise<void> {
  return leer<void>(await enviar(`/api/pendientes/${id}`, "POST", resolucion));
}

export async function traerVarios(): Promise<GrupoVarios[]> {
  return leer<GrupoVarios[]>(await fetch("/api/varios"));
}

/** Devuelve cuántos movimientos categorizó la regla. */
export async function crearRegla(texto: string, categoria: string): Promise<number> {
  const { categorizados } = await leer<{ categorizados: number }>(
    await enviar("/api/reglas", "POST", { texto, categoria }),
  );
  return categorizados;
}

// Importar.

export async function importarArchivos(archivos: File[]): Promise<Importacion> {
  const formulario = new FormData();
  for (const archivo of archivos) formulario.append("archivos", archivo);
  return leer<Importacion>(await fetch("/api/importar", { method: "POST", body: formulario }));
}

// Plan.

export type Plan = Esquemas["Plan"];
export type FijoPlan = Esquemas["FijoPlan"];
export type CuotaPlan = Esquemas["CuotaPlan"];
export type FijoEntrada = Esquemas["FijoEntrada"];
export type CuotaEntrada = Esquemas["CuotaEntrada"];

export async function traerPlan(): Promise<Plan> {
  return leer<Plan>(await fetch("/api/plan"));
}

/** Sin id crea; con id modifica. */
export async function guardarFijo(fijo: FijoEntrada, id?: number): Promise<void> {
  await leer(await enviar(id ? `/api/plan/fijos/${id}` : "/api/plan/fijos", id ? "PUT" : "POST", fijo));
}

export async function guardarCuota(cuota: CuotaEntrada, id?: number): Promise<void> {
  await leer(await enviar(id ? `/api/plan/cuotas/${id}` : "/api/plan/cuotas", id ? "PUT" : "POST", cuota));
}

export async function borrarDelPlan(tabla: "fijos" | "cuotas", id: number): Promise<void> {
  return leer<void>(await enviar(`/api/plan/${tabla}/${id}`, "DELETE"));
}

// Inversiones.

export type Inversiones = Esquemas["Inversiones"];
export type PosicionInversion = Esquemas["PosicionInversion"];
export type OperacionInversion = Esquemas["OperacionInversion"];
export type OperacionNueva = Esquemas["OperacionNueva"];

export async function traerInversiones(mes: string): Promise<Inversiones> {
  return leer<Inversiones>(await fetch(`/api/inversiones/${encodeURIComponent(mes)}`));
}

export async function cargarOperacion(operacion: OperacionNueva): Promise<void> {
  await leer(await enviar("/api/operaciones", "POST", operacion));
}

export async function borrarOperacion(id: number): Promise<void> {
  return leer<void>(await enviar(`/api/operaciones/${id}`, "DELETE"));
}

export async function actualizarPrecios(): Promise<{ actualizados: number; errores: string[] }> {
  return leer(await enviar("/api/precios", "POST"));
}
