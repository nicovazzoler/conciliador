import { describe, expect, it } from "vitest";
import type { Reporte } from "./api";
import { aAtender, controlados } from "./atender";
import { inicialMes, moverMes } from "./formato";

function reporte(cambios: Partial<Reporte>): Reporte {
  return {
    mes: "2026-11",
    totales: { movimientos: 0, pesos_centavos: 0, dolares_centavos: 0, total_usd_centavos: 0, sin_usd: 0 },
    categorias: [],
    fijos: [],
    cuotas: [],
    dias_sobre_tope: [],
    resumenes: [],
    pendientes: 0,
    importado: { mercado_pago: true, resumenes: null },
    ...cambios,
  };
}

const fijo = (concepto: string, estado: Reporte["fijos"][number]["estado"]) => ({
  concepto,
  moneda: "ARS",
  anotado_centavos: 2_500_000,
  pagos: estado === "sin debitar" ? 0 : 1,
  cobrado_centavos: 3_000_000,
  estado,
});

describe("aAtender", () => {
  it("lo que está bien o sin datos no aparece", () => {
    const r = reporte({ fijos: [fijo("Luz", "bien"), fijo("Gas", "sin datos")] });
    expect(aAtender(r)).toEqual([]);
  });

  it("lo rojo va antes que lo amarillo, aunque venga después", () => {
    const r = reporte({ fijos: [fijo("Celular", "más caro"), fijo("Internet", "sin debitar")] });
    expect(aAtender(r).map((x) => [x.concepto, x.sello, x.tono])).toEqual([
      ["Internet", "SIN DEBITAR", "mal"],
      ["Celular · 1 pago", "MÁS CARO", "ojo"],
    ]);
  });

  it("lo que no llegó se dibuja punteado; lo que llegó mal, lleno", () => {
    const r = reporte({ fijos: [fijo("Internet", "sin debitar"), fijo("Celular", "más caro")] });
    expect(aAtender(r).map((x) => x.forma)).toEqual(["punteado", "lleno"]);
  });

  it("un resumen impago dice cuánto falta, en pesos y en dólares", () => {
    const r = reporte({
      resumenes: [
        {
          tarjeta: "tarjeta_comafi",
          numero: "1",
          cierre: "2026-10-29",
          vencimiento: "2026-11-11",
          a_pagar_pesos: 15_000_000,
          a_pagar_usd: 9_324,
          falta_pesos: 15_000_000,
          falta_usd: 9_324,
          estado: "impago",
        },
      ],
    });
    expect(aAtender(r)[0]).toMatchObject({
      concepto: "Resumen Comafi · vence 11/11",
      monto: "$ 150.000,00 + U$D 93,24",
      sello: "IMPAGO",
    });
  });

  it("cuenta como controlado solo lo que tenía datos", () => {
    const r = reporte({ fijos: [fijo("Luz", "bien"), fijo("Gas", "sin datos"), fijo("Internet", "sin debitar")] });
    expect(controlados(r)).toBe(2);
  });
});

describe("meses", () => {
  it("mueve el mes cruzando el cambio de año, para los dos lados", () => {
    expect(moverMes("2026-01", -1)).toBe("2025-12");
    expect(moverMes("2026-12", 1)).toBe("2027-01");
    expect(moverMes("2026-11", -6)).toBe("2026-05");
  });

  it("da la inicial del mes", () => {
    expect(inicialMes("2026-10")).toBe("O");
    expect(inicialMes("2026-01")).toBe("E");
  });
});
