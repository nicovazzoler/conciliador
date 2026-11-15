import { describe, expect, it } from "vitest";
import type { InformeArchivo } from "./api";
import { leerInforme } from "./informes";

const informe = (cambios: Partial<InformeArchivo>): InformeArchivo => ({
  archivo: "resumen.pdf",
  reconocido: true,
  nuevas: 0,
  repetidas: 0,
  errores: [],
  problemas: [],
  ...cambios,
});

describe("leerInforme", () => {
  it("un archivo con movimientos nuevos es NUEVO", () => {
    expect(leerInforme(informe({ nuevas: 12, repetidas: 1 }))).toEqual({
      sello: "NUEVO",
      tono: "bien",
      detalle: "12 nuevas · 1 repetida",
    });
  });

  it("reimportar el mismo PDF no es un error: YA ESTABA", () => {
    expect(leerInforme(informe({ repetidas: 117 })).sello).toBe("YA ESTABA");
  });

  it("si los saldos o totales no cierran, se avisa aunque haya traído filas", () => {
    expect(leerInforme(informe({ nuevas: 3, problemas: ["el saldo no cierra"] })).sello).toBe("NO CIERRA");
  });

  it("un archivo que no se reconoce muestra el motivo", () => {
    const lectura = leerInforme(informe({ reconocido: false, errores: ["solo se aceptan PDF o plan.csv"] }));
    expect(lectura).toMatchObject({ sello: "RECHAZADO", tono: "mal", detalle: "solo se aceptan PDF o plan.csv" });
  });
});
