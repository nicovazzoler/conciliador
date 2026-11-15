// La pantalla del mes: lo mismo que `conciliador reporte`, pensado primero para el celular.
import { useEffect, useState } from "react";
import { traerReporte, type Esquemas, type Reporte } from "./api";
import { diaYMes, importe, mesActual, nombreMes, plata } from "./formato";

// Lo que está bien o sin datos no necesita atención: mostrarlo taparía lo que sí.
const SIN_AVISO = new Set(["bien", "sin datos"]);

type Carga =
  | { estado: "cargando" }
  | { estado: "listo"; reporte: Reporte }
  | { estado: "error"; mensaje: string };

export function Mes() {
  const [mes, setMes] = useState(mesActual());
  const [carga, setCarga] = useState<Carga>({ estado: "cargando" });

  useEffect(() => {
    // Si cambiás de mes antes de que llegue la respuesta, la vieja se descarta.
    const control = new AbortController();
    setCarga({ estado: "cargando" });
    traerReporte(mes, { signal: control.signal })
      .then((reporte) => setCarga({ estado: "listo", reporte }))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setCarga({ estado: "error", mensaje: error.message });
      });
    return () => control.abort();
  }, [mes]);

  return (
    <main className="pagina">
      <header className="encabezado">
        <h1>{nombreMes(mes)}</h1>
        <input
          type="month"
          aria-label="Mes"
          value={mes}
          onChange={(evento) => evento.target.value && setMes(evento.target.value)}
        />
      </header>

      {carga.estado === "cargando" && <p className="nota">Cargando…</p>}
      {carga.estado === "error" && <p className="nota error">No se pudo cargar: {carga.mensaje}</p>}
      {carga.estado === "listo" && <Contenido reporte={carga.reporte} />}
    </main>
  );
}

function Contenido({ reporte }: { reporte: Reporte }) {
  const { totales, importado } = reporte;
  const fijos = reporte.fijos.filter((f) => !SIN_AVISO.has(f.estado));
  const cuotas = reporte.cuotas.filter((c) => !SIN_AVISO.has(c.estado));

  return (
    <>
      <section className="totales">
        <Total titulo="En pesos" valor={plata(totales.pesos_centavos)} />
        <Total titulo="En dólares" valor={plata(totales.dolares_centavos, "USD")} />
        <Total titulo="Todo en USD" valor={plata(totales.total_usd_centavos, "USD")} destacado />
      </section>

      <p className="nota">
        Mercado Pago: {importado.mercado_pago ? "importado" : "falta (los fijos no se controlan)"} ·
        Resúmenes que vencen: {importado.resumenes ?? "ninguno (las cuotas no se controlan)"}
      </p>
      {(reporte.pendientes > 0 || totales.sin_usd > 0) && (
        <p className="nota aviso">
          {reporte.pendientes > 0 && `${reporte.pendientes} gastos para revisar. `}
          {totales.sin_usd > 0 && `${totales.sin_usd} movimientos sin cotización: el total en USD da de menos.`}
        </p>
      )}

      <Seccion titulo="Fijos" vacia={fijos.length === 0}>
        {fijos.map((f) => (
          <Fila key={f.concepto} estado={f.estado} titulo={f.concepto}>
            anotado {plata(f.anotado_centavos, f.moneda)}
            {f.pagos > 0 && ` · cobrado ${plata(f.cobrado_centavos, f.moneda)} en ${f.pagos} ${f.pagos === 1 ? "pago" : "pagos"}`}
          </Fila>
        ))}
      </Seccion>

      <Seccion titulo="Cuotas" vacia={cuotas.length === 0}>
        {cuotas.map((c, i) => (
          <Fila key={`${c.concepto}-${i}`} estado={c.estado} titulo={c.concepto}>
            {c.esperada ? `cuota ${c.esperada}` : `llegó la ${c.llegaron}`} · {plata(c.monto_centavos)}
          </Fila>
        ))}
      </Seccion>

      <Seccion titulo="Días sobre el tope de $ 200.000" vacia={reporte.dias_sobre_tope.length === 0}>
        {reporte.dias_sobre_tope.map((d) => (
          <Fila key={d.fecha} estado="tope" titulo={`${diaYMes(d.fecha)} · ${plata(d.pesos_centavos)}`}>
            {d.movimientos} gastos: {d.detalle}
          </Fila>
        ))}
      </Seccion>

      <Seccion titulo="Resúmenes de tarjeta" vacia={reporte.resumenes.length === 0}>
        {reporte.resumenes.map((r) => (
          <Fila key={`${r.tarjeta}-${r.numero}`} estado={r.estado} titulo={nombreTarjeta(r.tarjeta)}>
            vence {diaYMes(r.vencimiento)}
            {(r.falta_pesos > 0 || r.falta_usd > 0) &&
              ` · falta ${plata(r.falta_pesos)}${r.falta_usd > 0 ? ` y ${plata(r.falta_usd, "USD")}` : ""}`}
          </Fila>
        ))}
      </Seccion>

      <Seccion titulo="Por categoría (USD)" vacia={reporte.categorias.length === 0}>
        {reporte.categorias.map((c) => (
          <Categoria key={c.categoria ?? "sin categoría"} categoria={c} />
        ))}
      </Seccion>
    </>
  );
}

function Total({ titulo, valor, destacado }: { titulo: string; valor: string; destacado?: boolean }) {
  return (
    <div className={destacado ? "total destacado" : "total"}>
      <span>{titulo}</span>
      <strong>{valor}</strong>
    </div>
  );
}

function Seccion({ titulo, vacia, children }: { titulo: string; vacia: boolean; children: React.ReactNode }) {
  return (
    <section className="seccion">
      <h2>{titulo}</h2>
      {vacia ? <p className="nota">Nada que avisar.</p> : <ul>{children}</ul>}
    </section>
  );
}

function Fila({ estado, titulo, children }: { estado: string; titulo: string; children: React.ReactNode }) {
  return (
    <li className="fila">
      <span className={`estado estado-${estado.replaceAll(" ", "-")}`}>{estado}</span>
      <div>
        <strong>{titulo}</strong>
        <p>{children}</p>
      </div>
    </li>
  );
}

function Categoria({ categoria }: { categoria: Esquemas["Categoria"] }) {
  const porcentaje = categoria.porcentaje ?? 0;
  return (
    <li className="categoria">
      <div className="categoria-texto">
        <span>{categoria.categoria ?? "Sin categoría"}</span>
        <span>
          {importe(categoria.total_usd_centavos ?? 0)} · {porcentaje.toLocaleString("es-AR")}%
        </span>
      </div>
      <div className="barra" role="presentation">
        <div style={{ width: `${Math.max(porcentaje, 1)}%` }} />
      </div>
    </li>
  );
}

function nombreTarjeta(tarjeta: string): string {
  return { tarjeta_comafi: "Comafi", tarjeta_nacion: "Nación" }[tarjeta] ?? tarjeta;
}
