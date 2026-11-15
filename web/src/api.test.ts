import { afterEach, describe, expect, it, vi } from "vitest";
import { borrarManual, cargarGasto, ErrorApi } from "./api";

function responder(estado: number, cuerpo?: unknown) {
  const respuesta = new Response(cuerpo === undefined ? null : JSON.stringify(cuerpo), { status: estado });
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(respuesta);
}

afterEach(() => {
  vi.restoreAllMocks();
});

const gasto = { monto: "200000", descripcion: "Mueble Demo" };

describe("cargarGasto", () => {
  it("un 201 es un gasto guardado", async () => {
    responder(201, { id: 7, categoria: null, plan_concepto: null });
    expect(await cargarGasto(gasto)).toEqual({
      tipo: "guardado",
      guardado: { id: 7, categoria: null, plan_concepto: null },
    });
  });

  it("un 409 no es un error: devuelve los avisos para confirmar", async () => {
    const aviso = { codigo: "grande_sin_anticipar", mensaje: "ARS 200.000,00 es un gasto grande sin anticipar." };
    responder(409, { avisos: [aviso] });
    expect(await cargarGasto(gasto)).toEqual({ tipo: "avisos", avisos: [aviso] });
  });

  it("un 422 es un error con el mensaje del servidor", async () => {
    responder(422, { detail: "el monto tiene que ser mayor que 0" });
    await expect(cargarGasto({ ...gasto, monto: "0" })).rejects.toThrow("el monto tiene que ser mayor que 0");
  });

  it("los errores de validación de Pydantic llegan como lista y se juntan en un mensaje", async () => {
    responder(422, { detail: [{ msg: "Field required" }, { msg: "Input should be 'ARS' or 'USD'" }] });
    await expect(cargarGasto(gasto)).rejects.toThrow("Field required; Input should be 'ARS' or 'USD'");
  });

  it("manda el gasto como JSON, con el monto como texto", async () => {
    const fetch = responder(201, { id: 1 });
    await cargarGasto({ ...gasto, confirmado: true, categoria: "Hogar" });
    const [ruta, opciones] = fetch.mock.calls[0]!;
    expect(ruta).toBe("/api/gastos");
    expect(JSON.parse(String(opciones?.body))).toEqual({ ...gasto, confirmado: true, categoria: "Hogar" });
  });
});

describe("borrarManual", () => {
  it("un 404 avisa que no se pudo borrar", async () => {
    responder(404, { detail: "no hay un gasto o pago cargado a mano con ese número" });
    const error = await borrarManual(99).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ErrorApi);
    expect((error as ErrorApi).estado).toBe(404);
  });
});
