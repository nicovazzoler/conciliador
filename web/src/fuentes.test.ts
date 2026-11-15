import { describe, expect, it } from "vitest";
import { nombreFuente, siglaFuente } from "./fuentes";

describe("fuentes", () => {
  it("nombra cada fuente y dice el medio de lo cargado a mano", () => {
    expect(nombreFuente("tarjeta_nacion")).toBe("Tarjeta Nación");
    expect(nombreFuente("mercado_pago", "debito")).toBe("Mercado Pago");
    expect(nombreFuente("manual", "debito")).toBe("Cargado a mano, débito");
  });

  it("muestra tal cual una fuente nueva", () => {
    expect(nombreFuente("banco_nuevo")).toBe("banco_nuevo");
    expect(siglaFuente("banco_nuevo")).toBe("BA");
    expect(siglaFuente("mercado_pago")).toBe("MP");
  });
});
