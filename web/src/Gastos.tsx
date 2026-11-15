// Gastos: el mes como comprobante, lo que requiere atención y en qué se fue. Con meses anteriores.
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { traerHistorial, traerReporte, type MesHistorial, type Reporte } from "./api";
import { aAtender, controlados } from "./atender";
import { Comprobante, Renglon } from "./comprobante";
import { importe, inicialMes, mesActual, moverMes, nombreMes, plata } from "./formato";

type Carga =
  | { estado: "cargando" }
  | { estado: "listo"; reporte: Reporte; historial: MesHistorial[] }
  | { estado: "error"; mensaje: string };

export function Gastos() {
  const hoy = mesActual();
  const [mes, setMes] = useState(hoy);
  const [carga, setCarga] = useState<Carga>({ estado: "cargando" });

  useEffect(() => {
    // Si cambiás de mes antes de que llegue la respuesta, la vieja se descarta.
    const control = new AbortController();
    setCarga((anterior) => (anterior.estado === "listo" ? anterior : { estado: "cargando" }));
    Promise.all([traerReporte(mes, { signal: control.signal }), traerHistorial(mes, 6, { signal: control.signal })])
      .then(([reporte, historial]) => setCarga({ estado: "listo", reporte, historial }))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setCarga({ estado: "error", mensaje: error.message });
      });
    return () => control.abort();
  }, [mes]);

  return (
    <main className="pagina">
      <header className="mes">
        <button className="redondo" onClick={() => setMes(moverMes(mes, -1))} aria-label="Mes anterior">
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
        <h1 className="mes-nombre">{nombreMes(mes)}</h1>
        <button
          className="redondo"
          onClick={() => setMes(moverMes(mes, 1))}
          disabled={mes >= hoy}
          aria-label="Mes siguiente"
        >
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </header>

      {carga.estado === "cargando" && <p className="nota centrada">Cargando {nombreMes(mes)}…</p>}
      {carga.estado === "error" && <p className="mensaje mensaje-error">No se pudo cargar el mes: {carga.mensaje}</p>}
      {carga.estado === "listo" && (
        <Contenido reporte={carga.reporte} historial={carga.historial} mes={mes} alElegirMes={setMes} />
      )}
    </main>
  );
}

function Contenido({
  reporte,
  historial,
  mes,
  alElegirMes,
}: {
  reporte: Reporte;
  historial: MesHistorial[];
  mes: string;
  alElegirMes: (mes: string) => void;
}) {
  const { totales, importado } = reporte;
  const atender = aAtender(reporte);
  const anterior = historial.at(-2);
  const variacion =
    anterior && anterior.pesos_centavos > 0
      ? Math.round(((totales.pesos_centavos - anterior.pesos_centavos) / anterior.pesos_centavos) * 100)
      : null;

  return (
    <div className="tablero">
      <p className="nota centrada importado">
        Mercado Pago {importado.mercado_pago ? "importado" : "sin importar: los fijos no se controlan"} ·{" "}
        {importado.resumenes ? `resúmenes que vencen: ${importado.resumenes.split(", ").length}` : "ningún resumen vence este mes"}
      </p>

      <Comprobante
        titulo="Gastado"
        tinte="violeta"
        className="gastado"
        pie={
          variacion === null ? (
            <span className="nota">Sin datos del mes anterior para comparar.</span>
          ) : (
            <span className="nota">
              {variacion === 0 ? "Igual" : `${Math.abs(variacion)}% ${variacion < 0 ? "menos" : "más"}`} que {nombreMes(moverMes(mes, -1)).split(" ")[0]}
            </span>
          )
        }
      >
        <div className="gastado-arriba">
          <p className="monto-grande">
            <span className="moneda">$</span> {importe(totales.pesos_centavos)}
          </p>
          <Meses historial={historial} actual={mes} alElegir={alElegirMes} />
        </div>
        <ul className="renglones">
          <Renglon concepto="Pagado en dólares" monto={plata(totales.dolares_centavos, "USD")} />
          <Renglon
            concepto="Todo pasado a dólares"
            monto={plata(totales.total_usd_centavos, "USD")}
            sello={totales.sin_usd > 0 ? `${totales.sin_usd} SIN USD` : undefined}
            tono="ojo"
            fuerte
          />
        </ul>
      </Comprobante>

      <Comprobante
        titulo={
          <>
            A atender <span className="contador">{atender.length} de {controlados(reporte)}</span>
          </>
        }
        className="atender"
        pie={reporte.pendientes > 0 ? <a href="#/revisar">{reporte.pendientes} gastos grandes para revisar</a> : undefined}
      >
        {atender.length === 0 ? (
          <p className="vacio">Todo cerró bien este mes.</p>
        ) : (
          <ul className="renglones">
            {atender.map((r) => (
              <Renglon key={r.clave} concepto={r.concepto} monto={r.monto} sello={r.sello} tono={r.tono} forma={r.forma} />
            ))}
          </ul>
        )}
      </Comprobante>

      <Comprobante titulo="En qué se fue" className="categorias">
        {reporte.categorias.length === 0 ? (
          <p className="vacio">Sin gastos este mes.</p>
        ) : (
          <ul className="barras">
            {reporte.categorias.map((c) => (
              <li key={c.categoria ?? "sin categoría"}>
                <span className="barras-nombre">{c.categoria ?? "Sin categoría"}</span>
                <span className="barras-pista" aria-hidden="true">
                  <span style={{ width: `${Math.max(c.porcentaje ?? 0, 1.5)}%` }} />
                </span>
                <span className="barras-valor">{(c.porcentaje ?? 0).toLocaleString("es-AR")}%</span>
              </li>
            ))}
          </ul>
        )}
      </Comprobante>
    </div>
  );
}

/** Los últimos meses como barras: la altura es lo gastado; tocar una lleva a ese mes. */
function Meses({
  historial,
  actual,
  alElegir,
}: {
  historial: MesHistorial[];
  actual: string;
  alElegir: (mes: string) => void;
}) {
  const maximo = Math.max(1, ...historial.map((m) => m.pesos_centavos));
  return (
    <div className="meses" role="group" aria-label="Meses anteriores">
      {historial.map((m) => (
        <button
          key={m.mes}
          className="mes-barra"
          aria-current={m.mes === actual ? "true" : undefined}
          aria-label={`${nombreMes(m.mes)}: ${plata(m.pesos_centavos)}`}
          onClick={() => alElegir(m.mes)}
        >
          <span className="mes-barra-pista">
            <span style={{ height: `${Math.max((m.pesos_centavos / maximo) * 100, 4)}%` }} />
          </span>
          <span className="mes-barra-inicial">{inicialMes(m.mes)}</span>
        </button>
      ))}
    </div>
  );
}
