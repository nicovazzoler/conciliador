import { describe, expect, it } from "vitest";
import { diaYMes, enDolares, importe, mesActual, nombreMes, plata } from "./formato";

describe("importe", () => {
  it("usa punto para miles y coma para decimales, como en los PDF", () => {
    expect(importe(12345678)).toBe("123.456,78");
    expect(importe(5)).toBe("0,05");
    expect(importe(0)).toBe("0,00");
  });

  it("muestra el valor absoluto: en la base, un gasto es negativo", () => {
    expect(importe(-2512399)).toBe("25.123,99");
  });

  it("no pierde centavos con montos grandes, porque no pasa por float", () => {
    expect(importe(999999999999)).toBe("9.999.999.999,99");
  });
});

describe("plata", () => {
  it("antepone el símbolo de la moneda", () => {
    expect(plata(8824, "USD")).toBe("U$D 88,24");
    expect(plata(1500000)).toBe("$ 15.000,00");
  });
});

describe("enDolares", () => {
  it("sin cotización dice sin datos, no U$D 0,00", () => {
    expect(enDolares(null)).toBe("sin datos");
    expect(enDolares(0)).toBe("U$D 0,00");
    expect(enDolares(5250)).toBe("U$D 52,50");
  });
});

describe("meses y fechas", () => {
  it("nombra el mes", () => {
    expect(nombreMes("2026-10")).toBe("octubre 2026");
  });

  it("arma el mes de hoy con el formato de la API", () => {
    expect(mesActual(new Date(2026, 0, 31))).toBe("2026-01");
  });

  it("muestra día y mes", () => {
    expect(diaYMes("2026-10-05")).toBe("05/10");
  });
});
