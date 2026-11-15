import { describe, expect, it } from "vitest";
import { avanceCuota } from "./Plan";

describe("avanceCuota", () => {
  const cuota = { cantidad: 6, primer_mes: "2026-09" };

  it("dice qué cuota toca y cuándo termina", () => {
    expect(avanceCuota(cuota, "2026-11")).toEqual({ fraccion: 0.5, texto: "cuota 03/06 · termina en febrero 2027" });
  });

  it("antes de empezar, dice cuándo empieza", () => {
    expect(avanceCuota(cuota, "2026-08").texto).toBe("empieza en septiembre 2026");
  });

  it("después de la última, dice que terminó", () => {
    expect(avanceCuota(cuota, "2027-05")).toEqual({ fraccion: 1, texto: "terminó en febrero 2027" });
  });
});
