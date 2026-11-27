// Gastos: el mes, mes a mes, lo que hay que atender (y cómo), los fijos y en qué se fue. Con meses anteriores.
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import {
  guardarFijo,
  traerHistorial,
  traerHistorialCategoria,
  traerHistorialFijo,
  traerPlan,
  traerReporte,
  type MesHistorial,
  type Reporte,
} from "./api";
import { aAtender, controlados } from "./atender";
import { Comprobante, Renglon, Sello } from "./comprobante";
import { Segmentado } from "./controles";
import { enDolares, importe, mesActual, moverMes, nombreMes, plata } from "./formato";
import { nombreFuente } from "./fuentes";
import { Columnas, Leyenda } from "./graficos";

type Carga =
  | { estado: "cargando" }
  | { estado: "listo"; reporte: Reporte; historial: MesHistorial[] }
  | { estado: "error"; mensaje: string };

type Mensaje = { tipo: "bien" | "error"; texto: string } | null;

export function Gastos() {
  const hoy = mesActual();
  const [mes, setMes] = useState(hoy);
  const [carga, setCarga] = useState<Carga>({ estado: "cargando" });
  const [version, setVersion] = useState(0);
  const [mensaje, setMensaje] = useState<Mensaje>(null);

  useEffect(() => {
    // Si cambiás de mes antes de que llegue la respuesta, la vieja se descarta.
    const control = new AbortController();
    setCarga((anterior) => (anterior.estado === "listo" ? anterior : { estado: "cargando" }));
    Promise.all([traerReporte(mes, { signal: control.signal }), traerHistorial(mes, 12, { signal: control.signal })])
      .then(([reporte, historial]) => setCarga({ estado: "listo", reporte, historial }))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setCarga({ estado: "error", mensaje: error.message });
      });
    return () => control.abort();
  }, [mes, version]);

  return (
    <main className="pagina">
      <header className="mes">
        <button className="redondo" onClick={() => setMes(moverMes(mes, -1))} aria-label="Mes anterior">
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
        <h1 className="mes-nombre">{nombreMes(mes)}</h1>
        <button className="redondo" onClick={() => setMes(moverMes(mes, 1))} disabled={mes >= hoy} aria-label="Mes siguiente">
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </header>

      {mensaje && (
        <p className={`mensaje mensaje-${mensaje.tipo}`} role="status">
          {mensaje.texto}
        </p>
      )}
      {carga.estado === "cargando" && <p className="nota centrada">Cargando {nombreMes(mes)}…</p>}
      {carga.estado === "error" && <p className="mensaje mensaje-error">No se pudo cargar el mes: {carga.mensaje}</p>}
      {carga.estado === "listo" && (
        <Contenido
          reporte={carga.reporte}
          historial={carga.historial}
          mes={mes}
          alElegirMes={setMes}
          alGuardar={(texto) => {
            setMensaje({ tipo: "bien", texto });
            setVersion((v) => v + 1);
          }}
          alFallar={(texto) => setMensaje({ tipo: "error", texto })}
        />
      )}
    </main>
  );
}

function Contenido({
  reporte,
  historial,
  mes,
  alElegirMes,
  alGuardar,
  alFallar,
}: {
  reporte: Reporte;
  historial: MesHistorial[];
  mes: string;
  alElegirMes: (mes: string) => void;
  alGuardar: (texto: string) => void;
  alFallar: (texto: string) => void;
}) {
  const { totales, importado } = reporte;
  const anterior = historial.at(-2);
  const vencido = (historial.at(-1)?.fuentes ?? [])
    .filter((f) => f.fuente.startsWith("tarjeta_"))
    .reduce((suma, f) => suma + f.pesos_centavos, 0);
  const variacion =
    anterior && anterior.pesos_centavos > 0
      ? Math.round(((totales.pesos_centavos - anterior.pesos_centavos) / anterior.pesos_centavos) * 100)
      : null;

  return (
    <>
      <p className="nota centrada importado">
        Mercado Pago {importado.mercado_pago ? "importado" : "sin importar: los fijos no se controlan"} ·{" "}
        {importado.resumenes ? `resúmenes que vencen: ${importado.resumenes.split(", ").length}` : "ningún resumen vence este mes"}
        {" · "}
        <a className="enlace-seccion" href={`#/movimientos/${mes}`}>
          todos los movimientos →
        </a>
      </p>
      <div className="tablero tablero-gastos">
        <Comprobante
          titulo="Gastado"
          tinte="violeta"
          className="gastado"
          pie={
            !importado.mercado_pago ? (
              <span className="nota">Falta el Mercado Pago de este mes: todavía no se puede comparar.</span>
            ) : variacion === null ? (
              <span className="nota">Sin datos del mes anterior para comparar.</span>
            ) : (
              <span className="nota">
                {variacion === 0 ? "Igual" : `${Math.abs(variacion)}% ${variacion < 0 ? "menos" : "más"}`} que{" "}
                {nombreMes(moverMes(mes, -1)).split(" ")[0]}, en pesos
              </span>
            )
          }
        >
          <p className="monto-grande">
            <span className="moneda">$</span>
            <span>{importe(totales.pesos_centavos)}</span>
          </p>
          <ul className="renglones">
            {vencido > 0 && <Renglon concepto="A mes vencido" monto={plata(vencido)} />}
            <Renglon concepto="Pagado en dólares" monto={plata(totales.dolares_centavos, "USD")} />
            <Renglon
              concepto="Todo pasado a dólares"
              monto={enDolares(totales.total_usd_centavos)}
              sello={totales.sin_usd > 0 ? `${totales.sin_usd} SIN USD` : undefined}
              tono="ojo"
              fuerte
            />
          </ul>
        </Comprobante>

        <MesAMes historial={historial} mes={mes} alElegir={alElegirMes} />
        <Atender reporte={reporte} />
        <Fijos reporte={reporte} mes={mes} alGuardar={alGuardar} alFallar={alFallar} />
        <Categorias reporte={reporte} mes={mes} />
      </div>
    </>
  );
}

// Mes a mes.

const COLOR_FUENTE: Record<string, string> = {
  mercado_pago: "var(--cat-1)",
  tarjeta_comafi: "var(--cat-5)",
  tarjeta_nacion: "var(--cat-4)",
  manual: "var(--cat-3)",
};
const ORDEN_FUENTES = ["mercado_pago", "tarjeta_comafi", "tarjeta_nacion", "manual"];

/** Los últimos doce meses apilados por fuente. En dólares por defecto: en pesos, la inflación lo tapa todo. */
function MesAMes({ historial, mes, alElegir }: { historial: MesHistorial[]; mes: string; alElegir: (mes: string) => void }) {
  const [moneda, setMoneda] = useState<"usd" | "pesos">("usd");
  const valor = (f: MesHistorial["fuentes"][number]) => (moneda === "usd" ? f.total_usd_centavos : f.pesos_centavos);
  const presentes = ORDEN_FUENTES.filter((fuente) => historial.some((m) => m.fuentes.some((f) => f.fuente === fuente && valor(f) > 0)));
  const otras = [...new Set(historial.flatMap((m) => m.fuentes.map((f) => f.fuente)))].filter((f) => !ORDEN_FUENTES.includes(f));
  const fuentes = [...presentes, ...otras];
  const formato = (centavos: number) => plata(centavos, moneda === "usd" ? "USD" : "ARS");
  const columnas = historial.map((m) => ({
    clave: m.mes,
    etiqueta: nombreMes(m.mes).slice(0, 3),
    partes: fuentes.map((fuente) => ({
      nombre: nombreFuente(fuente),
      color: COLOR_FUENTE[fuente] ?? "var(--apagado)",
      valor: valor(m.fuentes.find((f) => f.fuente === fuente) ?? { fuente, pesos_centavos: 0, total_usd_centavos: 0 }),
    })),
  }));
  const hayDatos = columnas.some((c) => c.partes.some((p) => p.valor > 0));

  return (
    <Comprobante titulo="Mes a mes" className="mes-a-mes abierto">
      <div className="evolucion-arriba">
        <Leyenda forma="caja" items={fuentes.map((f) => ({ nombre: nombreFuente(f), color: COLOR_FUENTE[f] ?? "var(--apagado)" }))} />
        <Segmentado
          etiqueta="Moneda"
          opciones={[
            ["usd", "U$D"],
            ["pesos", "Pesos"],
          ]}
          valor={moneda}
          alCambiar={setMoneda}
        />
      </div>
      {hayDatos ? (
        <Columnas
          etiqueta={`Lo gastado en cada uno de los últimos ${historial.length} meses, por fuente`}
          columnas={columnas}
          elegida={mes}
          alElegir={alElegir}
          formato={formato}
        />
      ) : (
        <p className="vacio">{moneda === "usd" ? "Sin gastos con cotización del dólar en estos meses." : "Sin gastos en estos meses."}</p>
      )}
      <p className="nota">
        Tocá un mes para verlo. Las tarjetas van a mes vencido: cuentan en el mes en que vence el resumen. Mercado Pago y lo
        cargado a mano, en el mes en que salió la plata.
      </p>
    </Comprobante>
  );
}

// A atender.

/** Lo que cerró mal este mes, con qué hacer en cada caso. Los fijos tienen su propia tabla. */
function Atender({ reporte }: { reporte: Reporte }) {
  const filas = aAtender(reporte, { fijos: false });
  return (
    <Comprobante
      titulo={
        <>
          A atender <span className="contador">{filas.length ? `${filas.length} de ${controlados(reporte)}` : "todo bien"}</span>
        </>
      }
      className="atender hundido"
      pie={reporte.pendientes > 0 ? <a href="#/revisar">{reporte.pendientes} gastos grandes para revisar →</a> : undefined}
    >
      {filas.length === 0 ? (
        <p className="vacio">Nada para atender: los resúmenes, las cuotas y los días cerraron bien.</p>
      ) : (
        <div className="tabla-trabajo" role="table" aria-label="Lo que hay que atender">
          {filas.map((r) => (
            <div key={r.clave} className="tabla-fila" role="row">
              <span className={`filete filete-${r.forma} tono-${r.tono}`} aria-hidden="true" />
              <span className="tabla-que" role="cell">
                {r.concepto}
              </span>
              <span className="tabla-monto" role="cell">
                {r.monto}
              </span>
              <span role="cell">
                <Sello tono={r.tono}>{r.sello}</Sello>
              </span>
              <span className="tabla-accion" role="cell">
                {r.enlace && <a href={r.enlace.href}>{r.enlace.texto} →</a>}
              </span>
            </div>
          ))}
        </div>
      )}
    </Comprobante>
  );
}

// Fijos.

const SELLO_FIJO: Record<string, { texto: string; tono: "mal" | "ojo" | "bien" | "neutro" }> = {
  "sin debitar": { texto: "SIN DEBITAR", tono: "mal" },
  "más caro": { texto: "MÁS CARO", tono: "ojo" },
  "más barato": { texto: "MÁS BARATO", tono: "ojo" },
  bien: { texto: "BIEN", tono: "bien" },
  "sin datos": { texto: "SIN DATOS", tono: "neutro" },
};

/** Cada fijo del plan: lo anotado contra lo cobrado. Tocar uno muestra cómo vino y deja corregirlo. */
function Fijos({ reporte, mes, alGuardar, alFallar }: { reporte: Reporte; mes: string; alGuardar: (t: string) => void; alFallar: (t: string) => void }) {
  const [abierto, setAbierto] = useState<string | null>(null);
  const diferencias = reporte.fijos.filter((f) => f.estado !== "bien" && f.estado !== "sin datos").length;
  return (
    <Comprobante
      titulo={
        <>
          Fijos{" "}
          <span className="contador">
            {reporte.fijos.length === 0 ? "" : diferencias ? `${diferencias} con diferencias de ${reporte.fijos.length}` : `${reporte.fijos.length}, todos bien`}
          </span>
        </>
      }
      className="fijos"
      pie={<a href="#/plan">Editar el plan →</a>}
    >
      {reporte.fijos.length === 0 ? (
        <p className="vacio">Todavía no hay fijos en el plan.</p>
      ) : (
        <div className="tabla-trabajo" role="table" aria-label="Fijos del plan">
          <div className="tabla-fila tabla-cabeza" role="row">
            <span role="columnheader">Fijo</span>
            <span role="columnheader">Anotado</span>
            <span role="columnheader">Cobrado</span>
            <span role="columnheader">Estado</span>
            <span aria-hidden="true" />
          </div>
          {reporte.fijos.map((f) => {
            const sello = SELLO_FIJO[f.estado] ?? { texto: f.estado.toUpperCase(), tono: "neutro" as const };
            const esteAbierto = abierto === f.concepto;
            return (
              <div key={f.concepto} className={`tabla-grupo${esteAbierto ? " abierto" : ""}`}>
                <button type="button" className="tabla-fila tabla-boton" role="row" aria-expanded={esteAbierto} onClick={() => setAbierto(esteAbierto ? null : f.concepto)}>
                  <span className="tabla-que" role="cell">
                    {f.concepto}
                  </span>
                  <span className="tabla-monto" role="cell">
                    {plata(f.anotado_centavos, f.moneda)}
                  </span>
                  <span className="tabla-monto" role="cell">
                    {f.pagos ? plata(f.cobrado_centavos, f.moneda) : "—"}
                  </span>
                  <span role="cell">
                    <Sello tono={sello.tono}>{sello.texto}</Sello>
                  </span>
                  <ChevronDown size={16} aria-hidden="true" className="tabla-flecha" />
                </button>
                {esteAbierto && <DetalleFijo fijo={f} mes={mes} alGuardar={alGuardar} alFallar={alFallar} />}
              </div>
            );
          })}
        </div>
      )}
    </Comprobante>
  );
}

function DetalleFijo({
  fijo: f,
  mes,
  alGuardar,
  alFallar,
}: {
  fijo: Reporte["fijos"][number];
  mes: string;
  alGuardar: (t: string) => void;
  alFallar: (t: string) => void;
}) {
  const [historia, setHistoria] = useState<Awaited<ReturnType<typeof traerHistorialFijo>> | null>(null);
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    traerHistorialFijo(mes, f.concepto)
      .then(setHistoria)
      .catch(() => setHistoria([]));
  }, [mes, f.concepto]);

  async function actualizarPlan() {
    setGuardando(true);
    try {
      const plan = await traerPlan();
      const actual = plan.fijos.find((p) => p.concepto === f.concepto);
      if (!actual) throw new Error(`${f.concepto} ya no está en el plan`);
      await guardarFijo(
        { concepto: actual.concepto, texto: actual.texto, monto: importe(f.cobrado_centavos), moneda: actual.moneda as "ARS" | "USD", dia: actual.dia, categoria: actual.categoria },
        actual.id,
      );
      alGuardar(`${f.concepto}: el plan ahora anota ${plata(f.cobrado_centavos, f.moneda)}.`);
    } catch (error) {
      alFallar((error as Error).message);
    } finally {
      setGuardando(false);
    }
  }

  const columnas = (historia ?? []).map((m) => ({
    clave: m.mes,
    etiqueta: nombreMes(m.mes).slice(0, 3),
    partes: [{ nombre: "cobrado", valor: m.cobrado_centavos, color: m.estado === "bien" ? "var(--menta)" : m.estado === "sin datos" ? "var(--apagado)" : "var(--ambar)" }],
  }));

  return (
    <div className="tabla-detalle">
      {historia === null ? (
        <p className="nota">Cargando cómo vino…</p>
      ) : (
        <>
          <p className="nota">Lo cobrado en los últimos meses. Anotado en el plan: {plata(f.anotado_centavos, f.moneda)}.</p>
          <Columnas etiqueta={`${f.concepto}: lo cobrado mes por mes`} columnas={columnas} alto={130} formato={(c) => plata(c, f.moneda)} elegida={mes} />
        </>
      )}
      <div className="acciones-plan">
        {(f.estado === "más caro" || f.estado === "más barato") && (
          <button type="button" className="principal chico" disabled={guardando} onClick={actualizarPlan}>
            Anotar {plata(f.cobrado_centavos, f.moneda)} en el plan
          </button>
        )}
        {f.estado === "sin debitar" && (
          <a className="boton-enlace" href="#/cargar">
            Lo pagué de otra forma: cargarlo
          </a>
        )}
        <a className="boton-enlace" href={`#/movimientos/${mes}/buscar:${encodeURIComponent(f.concepto)}`}>
          Ver sus movimientos
        </a>
      </div>
    </div>
  );
}

// En qué se fue.

const COLORES = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)", "var(--cat-5)"];

/** Las cinco categorías más grandes con su color; el resto se junta en "Otras". Tocar una muestra cómo viene. */
function Categorias({ reporte, mes }: { reporte: Reporte; mes: string }) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const categorias = reporte.categorias;
  const principales = categorias.slice(0, COLORES.length);
  const resto = categorias.slice(COLORES.length);
  const filas = principales.map((c, i) => ({
    nombre: c.categoria ?? "Sin categoría",
    usd: c.total_usd_centavos,
    porcentaje: c.porcentaje,
    color: COLORES[i] ?? "var(--apagado)",
    sola: true,
  }));
  if (resto.length > 0) {
    // "Otras" es "sin datos" solo si ninguna de las que junta tiene cotización.
    const conUsd = resto.filter((c) => c.total_usd_centavos !== null);
    filas.push({
      nombre: `Otras (${resto.length})`,
      usd: conUsd.length ? conUsd.reduce((suma, c) => suma + (c.total_usd_centavos ?? 0), 0) : null,
      porcentaje: conUsd.length ? Math.round(conUsd.reduce((suma, c) => suma + (c.porcentaje ?? 0), 0) * 10) / 10 : null,
      color: "var(--apagado)",
      sola: false,
    });
  }
  const total = filas.reduce((suma, f) => suma + (f.usd ?? 0), 0);
  const sinUsd = categorias.reduce((suma, c) => suma + c.sin_usd, 0);

  return (
    <Comprobante
      titulo={
        <>
          En qué se fue{" "}
          <a className="contador enlace-seccion" href="#/categorias">
            editar categorías
          </a>
        </>
      }
      className="categorias"
    >
      {categorias.length === 0 ? (
        <p className="vacio">Sin gastos este mes.</p>
      ) : (
        <>
          {total > 0 ? (
            <div className="composicion" aria-hidden="true">
              {filas.map((f) =>
                f.usd === null ? null : <span key={f.nombre} style={{ width: `${(f.usd / total) * 100}%`, background: f.color }} />,
              )}
            </div>
          ) : (
            <p className="nota">Sin cotización del dólar todavía: los montos en USD aparecen al bajarla.</p>
          )}
          <ul className="leyenda leyenda-tocable">
            {filas.map((f) => (
              <li key={f.nombre}>
                <Fila
                  abierta={abierta === f.nombre}
                  tocable={f.sola}
                  alTocar={() => setAbierta(abierta === f.nombre ? null : f.nombre)}
                  contenido={
                    <>
                      <span className="leyenda-punto" style={{ background: f.color }} aria-hidden="true" />
                      <span className="leyenda-nombre">{f.nombre}</span>
                      <span className="leyenda-monto">{enDolares(f.usd)}</span>
                      <span className="leyenda-porcentaje">{f.porcentaje === null ? "" : `${f.porcentaje.toLocaleString("es-AR")}%`}</span>
                    </>
                  }
                />
                {abierta === f.nombre && <DetalleCategoria categoria={f.nombre} color={f.color} mes={mes} />}
              </li>
            ))}
          </ul>
          {total > 0 && sinUsd > 0 && (
            <p className="nota">
              {sinUsd === 1 ? "Un gasto sigue" : `${sinUsd} gastos siguen`} sin cotización: los montos en USD están incompletos.
            </p>
          )}
        </>
      )}
    </Comprobante>
  );
}

function Fila({ abierta, tocable, alTocar, contenido }: { abierta: boolean; tocable: boolean; alTocar: () => void; contenido: ReactNode }) {
  if (!tocable) return <div className="leyenda-fila">{contenido}</div>;
  return (
    <button type="button" className="leyenda-fila" aria-expanded={abierta} onClick={alTocar}>
      {contenido}
    </button>
  );
}

function DetalleCategoria({ categoria, color, mes }: { categoria: string; color: string; mes: string }) {
  const [historia, setHistoria] = useState<Awaited<ReturnType<typeof traerHistorialCategoria>> | null>(null);
  useEffect(() => {
    traerHistorialCategoria(mes, categoria)
      .then(setHistoria)
      .catch(() => setHistoria([]));
  }, [mes, categoria]);
  if (historia === null) return <p className="nota tabla-detalle">Cargando cómo viene…</p>;
  const columnas = historia.map((m) => ({ clave: m.mes, etiqueta: nombreMes(m.mes).slice(0, 3), partes: [{ nombre: categoria, valor: m.total_usd_centavos, color }] }));
  return (
    <div className="tabla-detalle">
      <Columnas etiqueta={`${categoria}: lo gastado mes por mes, en dólares`} columnas={columnas} alto={130} formato={(c) => plata(c, "USD")} elegida={mes} />
      <a className="enlace-seccion" href={`#/movimientos/${mes}/categoria:${encodeURIComponent(categoria)}`}>
        Ver los movimientos de {categoria} →
      </a>
    </div>
  );
}
