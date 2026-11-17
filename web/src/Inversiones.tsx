// Inversiones: Portafolio (lo que tenés hoy) y Trading (lo que operaste en el mes).
import { ChevronLeft, ChevronRight, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  actualizarPrecios,
  borrarOperacion,
  cargarOperacion,
  cerrarPorNivel,
  descartarNivel,
  guardarNiveles,
  traerHistoriaInversiones,
  traerInversiones,
  type AvisoNivel,
  type HistoriaInversiones,
  type Inversiones as Datos,
  type OperacionInversion,
  type OperacionNueva,
} from "./api";
import { Comprobante, Renglon, Sello } from "./comprobante";
import { Segmentado } from "./controles";
import { decimal, diaYMes, hoy, importe, mesActual, moverMes, nombreMes, plata } from "./formato";
import { enDolares, GraficoLinea, Leyenda, porMes, Rueda } from "./graficos";
import { LectorCapturas } from "./LectorCapturas";

type Vista = "portafolio" | "trading";
type Mensaje = { tipo: "bien" | "error"; texto: string } | null;

const COLORES = ["var(--cat-2)", "var(--cat-1)", "var(--cat-3)", "var(--cat-5)", "var(--cat-4)"];

export function Inversiones() {
  const [vista, setVista] = useState<Vista>("portafolio");
  const [mes, setMes] = useState(mesActual());
  const [datos, setDatos] = useState<Datos | null>(null);
  const [mensaje, setMensaje] = useState<Mensaje>(null);
  const [actualizando, setActualizando] = useState(false);

  const recargar = useCallback(() => {
    traerInversiones(mes)
      .then(setDatos)
      .catch((error: Error) => setMensaje({ tipo: "error", texto: error.message }));
  }, [mes]);
  useEffect(recargar, [recargar]);

  async function precios() {
    setActualizando(true);
    try {
      const { actualizados, errores } = await actualizarPrecios();
      setMensaje(
        errores.length
          ? { tipo: "error", texto: `Se actualizaron ${actualizados}. ${errores.join(" · ")}` }
          : { tipo: "bien", texto: `Precios actualizados (${actualizados}).` },
      );
      recargar();
    } catch (error) {
      setMensaje({ tipo: "error", texto: (error as Error).message });
    } finally {
      setActualizando(false);
    }
  }

  return (
    <main className="pagina">
      <h1 className="titulo-pagina">Inversiones</h1>
      <Segmentado
        etiqueta="Qué ver"
        opciones={[
          ["portafolio", "Portafolio"],
          ["trading", "Trading"],
        ]}
        valor={vista}
        alCambiar={setVista}
      />
      {mensaje && (
        <p className={`mensaje mensaje-${mensaje.tipo}`} role="status">
          {mensaje.texto}
        </p>
      )}
      {datos?.avisos.map((aviso) => (
        <p key={aviso} className="mensaje mensaje-error">
          {aviso}
        </p>
      ))}
      {datos === null ? (
        <p className="nota">Cargando…</p>
      ) : vista === "portafolio" ? (
        <Portafolio
          datos={datos}
          actualizando={actualizando}
          alActualizar={precios}
          alGuardar={(texto) => {
            setMensaje({ tipo: "bien", texto });
            recargar();
          }}
          alFallar={(texto) => setMensaje({ tipo: "error", texto })}
        />
      ) : (
        <Trading
          datos={datos}
          mes={mes}
          alCambiarMes={setMes}
          alGuardar={(texto) => {
            setMensaje({ tipo: "bien", texto });
            recargar();
          }}
          alFallar={(texto) => setMensaje({ tipo: "error", texto })}
        />
      )}
    </main>
  );
}

function Portafolio({
  datos,
  actualizando,
  alActualizar,
  alGuardar,
  alFallar,
}: {
  datos: Datos;
  actualizando: boolean;
  alActualizar: () => void;
  alGuardar: (texto: string) => void;
  alFallar: (texto: string) => void;
}) {
  const porcentaje = datos.invertido_centavos ? (datos.no_realizado_centavos / datos.invertido_centavos) * 100 : 0;

  if (datos.posiciones.length === 0)
    return (
      <Comprobante titulo="Cartera" className="inversion-vacia">
        <p className="vacio">No tenés posiciones abiertas. Cargá tus compras en Trading y acá aparece lo que tenés.</p>
      </Comprobante>
    );

  return (
    <>
      {datos.niveles_tocados.map((n) => (
        <AvisoDeNivel key={n.activo} aviso={n} alGuardar={alGuardar} alFallar={alFallar} />
      ))}
      <div className="portafolio">
        <Comprobante
          titulo="Cartera"
          tinte="menta"
          className="cartera"
          pie={
            <span className="pie-precios">
              <span className="nota">
                {datos.precios_al ? `Precios del ${new Date(datos.precios_al).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}` : "Todavía no se bajaron precios"}
              </span>
              <button type="button" className="boton-texto" onClick={alActualizar} disabled={actualizando}>
                <RefreshCw size={14} aria-hidden="true" className={actualizando ? "girando" : undefined} /> {actualizando ? "Actualizando…" : "Actualizar"}
              </button>
            </span>
          }
        >
          <p className="monto-grande">
            <span className="moneda">U$D</span>
            <span>{importe(datos.cartera_centavos)}</span>
          </p>
          <p className={`chip-variacion ${datos.no_realizado_centavos >= 0 ? "tono-bien" : "tono-mal"}`}>
            {signo(datos.no_realizado_centavos)}U$D {importe(datos.no_realizado_centavos)} sin realizar ·{" "}
            {signo(datos.no_realizado_centavos)}
            {Math.abs(porcentaje).toLocaleString("es-AR", { maximumFractionDigits: 1 })}%
          </p>
          <ul className="renglones">
            <Renglon concepto="Invertido en lo que tenés" monto={plata(datos.invertido_centavos, "USD")} />
          </ul>
          {datos.sin_precio.length > 0 && <p className="nota tono-ojo">Sin precio: {datos.sin_precio.join(", ")}. Su valor no suma a la cartera.</p>}
        </Comprobante>
        <Evolucion />
        <Posiciones datos={datos} alGuardar={alGuardar} alFallar={alFallar} />
      </div>
    </>
  );
}

const RANGOS = [
  ["1m", "1M", 31],
  ["3m", "3M", 92],
  ["6m", "6M", 183],
  ["todo", "Todo", 100000],
] as const;
type Rango = (typeof RANGOS)[number][0];

/** La cartera día por día: lo que valía contra lo que se había puesto. */
function Evolucion() {
  const [historia, setHistoria] = useState<HistoriaInversiones | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rango, setRango] = useState<Rango>("todo");
  useEffect(() => {
    traerHistoriaInversiones()
      .then(setHistoria)
      .catch((e: Error) => setError(e.message));
  }, []);
  const dias = RANGOS.find(([clave]) => clave === rango)?.[2] ?? 100000;
  const puntos = (historia?.puntos ?? []).slice(-dias);

  return (
    <Comprobante titulo="Evolución" className="evolucion abierto">
      {error ? (
        <p className="nota">No se pudo armar la evolución: {error}</p>
      ) : historia === null ? (
        <p className="nota cargando-grafico">Armando la evolución con los precios de cada día…</p>
      ) : puntos.length < 2 ? (
        <p className="vacio">Hace falta más de un día con operaciones para ver la evolución.</p>
      ) : (
        <>
          <div className="evolucion-arriba">
            <Leyenda
              forma="linea"
              items={[
                { nombre: "Lo que valía", color: "var(--violeta)" },
                { nombre: "Lo invertido", color: "var(--suave)" },
              ]}
            />
            <Segmentado etiqueta="Período" opciones={RANGOS.map(([clave, texto]) => [clave, texto] as const)} valor={rango} alCambiar={setRango} />
          </div>
          <GraficoLinea
            etiqueta="Valor de la cartera y lo invertido, día por día"
            fechas={puntos.map((p) => p.fecha)}
            formato={enDolares}
            series={[
              { nombre: "lo invertido", color: "var(--suave)", valores: puntos.map((p) => p.invertido_centavos) },
              { nombre: "lo que valía", color: "var(--violeta)", valores: puntos.map((p) => p.valor_centavos), area: true },
            ]}
          />
          {historia.sin_precio.length > 0 && (
            <p className="nota">Sin precios viejos de {historia.sin_precio.join(", ")}: no entran en la evolución.</p>
          )}
          <details className="tabla-datos">
            <summary>Ver como tabla</summary>
            <table>
              <thead>
                <tr>
                  <th>Fin de mes</th>
                  <th>Valía</th>
                  <th>Invertido</th>
                </tr>
              </thead>
              <tbody>
                {porMes(puntos).map((p) => (
                  <tr key={p.fecha}>
                    <td>{diaYMes(p.fecha)}</td>
                    <td>{enDolares(p.valor_centavos)}</td>
                    <td>{enDolares(p.invertido_centavos)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </Comprobante>
  );
}

const VISIBLES = 5;

/** La rueda con la composición y la lista; arriba de cinco, "Ver todas". */
function Posiciones({ datos, alGuardar, alFallar }: { datos: Datos; alGuardar: (t: string) => void; alFallar: (t: string) => void }) {
  const [todas, setTodas] = useState(false);
  const [resaltada, setResaltada] = useState<string | null>(null);
  const [abierta, setAbierta] = useState<string | null>(null);
  const conValor = datos.posiciones.filter((p) => p.valor_centavos !== null);
  const principales = conValor.slice(0, COLORES.length);
  const color = new Map(principales.map((p, i) => [p.activo, COLORES[i]]));
  const resto = conValor.slice(COLORES.length);
  const partes = [
    ...principales.map((p) => ({ nombre: p.activo, valor: p.valor_centavos ?? 0, color: color.get(p.activo) ?? "var(--apagado)" })),
    ...(resto.length ? [{ nombre: "Otras", valor: resto.reduce((s, p) => s + (p.valor_centavos ?? 0), 0), color: "var(--apagado)" }] : []),
  ];
  const total = partes.reduce((s, p) => s + p.valor, 0);
  const lista = todas ? datos.posiciones : datos.posiciones.slice(0, VISIBLES);

  return (
    <Comprobante titulo={<>Posiciones <span className="contador">{datos.posiciones.length}</span></>} className="posiciones">
      <div className="posiciones-cuerpo">
        {total > 0 && (
          <div className="posiciones-rueda">
            <Rueda
              partes={partes}
              resaltada={resaltada}
              alResaltar={setResaltada}
              centro={
                resaltada ? (
                  <>
                    <strong>{resaltada}</strong>
                    <span>{Math.round(((partes.find((p) => p.nombre === resaltada)?.valor ?? 0) / total) * 100)}%</span>
                  </>
                ) : (
                  <>
                    <strong>{conValor.length}</strong>
                    <span>{conValor.length === 1 ? "activo" : "activos"}</span>
                  </>
                )
              }
            />
            <Leyenda forma="caja" items={partes.map((p) => ({ nombre: `${p.nombre} ${Math.round((p.valor / total) * 100)}%`, color: p.color }))} />
          </div>
        )}
        <div className="posiciones-lista">
          <ul className="lista">
            {lista.map((p) => (
              <FilaPosicion
                key={p.activo}
                posicion={p}
                color={color.get(p.activo) ?? "var(--apagado)"}
                resaltada={resaltada === p.activo}
                abierta={abierta === p.activo}
                alTocar={() => setAbierta(abierta === p.activo ? null : p.activo)}
                alResaltar={setResaltada}
                alGuardar={(texto) => {
                  setAbierta(null);
                  alGuardar(texto);
                }}
                alFallar={alFallar}
              />
            ))}
          </ul>
          {datos.posiciones.length > VISIBLES && (
            <button type="button" className="agregar" onClick={() => setTodas(!todas)}>
              {todas ? "Ver menos" : `Ver todas (${datos.posiciones.length})`}
            </button>
          )}
        </div>
      </div>
    </Comprobante>
  );
}

function FilaPosicion({
  posicion: p,
  color,
  resaltada,
  abierta,
  alTocar,
  alResaltar,
  alGuardar,
  alFallar,
}: {
  posicion: Datos["posiciones"][number];
  color: string;
  resaltada: boolean;
  abierta: boolean;
  alTocar: () => void;
  alResaltar: (activo: string | null) => void;
  alGuardar: (t: string) => void;
  alFallar: (t: string) => void;
}) {
  const [stopLoss, setStopLoss] = useState(p.stop_loss ?? "");
  const [takeProfit, setTakeProfit] = useState(p.take_profit ?? "");
  const variacion = p.no_realizado_centavos !== null && p.invertido_centavos ? (p.no_realizado_centavos / p.invertido_centavos) * 100 : null;
  const niveles = [p.stop_loss && `SL ${decimal(p.stop_loss)}`, p.take_profit && `TP ${decimal(p.take_profit)}`].filter(Boolean);

  async function guardar(evento: FormEvent, quitar = false) {
    evento.preventDefault();
    try {
      await guardarNiveles(p.activo, quitar ? "" : stopLoss, quitar ? "" : takeProfit, p.moneda);
      alGuardar(quitar ? `${p.activo}: sin stop loss ni take profit.` : `${p.activo}: niveles guardados. Se revisan cada vez que actualizás los precios.`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  return (
    <li className={`item posicion${resaltada ? " resaltada" : ""}${abierta ? " abierta" : ""}`} onPointerEnter={() => alResaltar(p.activo)} onPointerLeave={() => alResaltar(null)}>
      <button type="button" className="posicion-fila" onClick={alTocar} aria-expanded={abierta}>
        <span className="posicion-color" style={{ background: color }} aria-hidden="true" />
        <span className="item-texto">
          <strong>{p.activo}</strong>
          <span className="numeros">
            {decimal(p.cantidad, 8)} · prom. U$D {decimal(p.costo_promedio)}
          </span>
          {niveles.length > 0 && <span className="posicion-niveles numeros">{niveles.join(" · ")}{p.moneda !== "USD" && ` ${p.moneda}`}</span>}
        </span>
        <span className="item-derecha">
          <span className="item-monto">{p.valor_centavos === null ? "sin precio" : plata(p.valor_centavos, "USD")}</span>
          {variacion !== null && (
            <span className={`numeros ${variacion >= 0 ? "tono-bien" : "tono-mal"}`}>
              {signo(variacion)}
              {Math.abs(variacion).toLocaleString("es-AR", { maximumFractionDigits: 1 })}%
            </span>
          )}
        </span>
      </button>
      {abierta && (
        <form className="formulario niveles-editor" onSubmit={(e) => guardar(e)}>
          <div className="dos-columnas">
            <label>
              Stop loss ({p.moneda})
              <input inputMode="decimal" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} placeholder="sin stop loss" />
            </label>
            <label>
              Take profit ({p.moneda})
              <input inputMode="decimal" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} placeholder="sin take profit" />
            </label>
          </div>
          <div className="acciones-plan">
            <button className="principal chico">Guardar</button>
            {niveles.length > 0 && (
              <button type="button" className="boton-texto peligroso" onClick={(e) => guardar(e as unknown as FormEvent, true)}>
                Quitar los dos
              </button>
            )}
          </div>
        </form>
      )}
    </li>
  );
}

/** El precio llegó a un nivel: lo más probable es que la posición se haya cerrado. Se confirma con un toque. */
function AvisoDeNivel({ aviso: n, alGuardar, alFallar }: { aviso: AvisoNivel; alGuardar: (t: string) => void; alFallar: (t: string) => void }) {
  const [enviando, setEnviando] = useState(false);
  const cual = n.tipo === "stop_loss" ? "stop loss" : "take profit";
  async function hacer(accion: () => Promise<void>, texto: string) {
    setEnviando(true);
    try {
      await accion();
      alGuardar(texto);
    } catch (error) {
      alFallar((error as Error).message);
    } finally {
      setEnviando(false);
    }
  }
  return (
    <div className={`aviso-nivel tono-${n.tipo === "stop_loss" ? "mal" : "bien"}`} role="alert">
      <p>
        <strong>{n.activo}</strong> llegó a tu {cual} ({decimal(n.nivel)} {n.moneda}) el {diaYMes(n.fecha)}. ¿Se cerró la posición?
      </p>
      <div className="aviso-nivel-acciones">
        <button
          type="button"
          className="principal chico"
          disabled={enviando}
          onClick={() => hacer(() => cerrarPorNivel(n.activo), `${n.activo}: venta de ${decimal(n.cantidad, 8)} a ${decimal(n.nivel)} cargada.`)}
        >
          Sí, cargar la venta de {decimal(n.cantidad, 8)}
        </button>
        <button type="button" className="secundario chico" disabled={enviando} onClick={() => hacer(() => descartarNivel(n.activo), "Listo, la posición sigue abierta.")}>
          No se cerró
        </button>
      </div>
    </div>
  );
}

function Trading({
  datos,
  mes,
  alCambiarMes,
  alGuardar,
  alFallar,
}: {
  datos: Datos;
  mes: string;
  alCambiarMes: (mes: string) => void;
  alGuardar: (texto: string) => void;
  alFallar: (texto: string) => void;
}) {
  const [cargando, setCargando] = useState(false);
  return (
    <>
      <header className="mes">
        <button className="redondo" onClick={() => alCambiarMes(moverMes(mes, -1))} aria-label="Mes anterior">
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
        <h2 className="mes-nombre">{nombreMes(mes)}</h2>
        <button className="redondo" onClick={() => alCambiarMes(moverMes(mes, 1))} disabled={mes >= mesActual()} aria-label="Mes siguiente">
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </header>
      <div className="paneles">
        <div className="panel">
          <Comprobante titulo="Resultado" tinte="menta">
            <div className="dos-cifras">
              <div>
                <span className="nota">Realizado en {nombreMes(mes).split(" ")[0]}</span>
                <p className={`cifra ${datos.realizado_mes_centavos >= 0 ? "tono-bien" : "tono-mal"}`}>
                  {signo(datos.realizado_mes_centavos)}U$D {importe(datos.realizado_mes_centavos)}
                </p>
              </div>
              <div>
                <span className="nota">No realizado hoy</span>
                <p className={`cifra ${datos.no_realizado_centavos >= 0 ? "tono-bien" : "tono-mal"}`}>
                  {signo(datos.no_realizado_centavos)}U$D {importe(datos.no_realizado_centavos)}
                </p>
              </div>
            </div>
            <p className="nota numeros">
              {datos.operaciones_mes} {datos.operaciones_mes === 1 ? "operación" : "operaciones"} · comisiones U$D {importe(datos.comisiones_mes_centavos)}
            </p>
          </Comprobante>
          {cargando ? (
            <FormularioOperacion
              alCerrar={() => setCargando(false)}
              alGuardar={(texto) => {
                setCargando(false);
                alGuardar(texto);
              }}
              alFallar={alFallar}
            />
          ) : (
            <button type="button" className="agregar" onClick={() => setCargando(true)}>
              <Plus size={16} aria-hidden="true" /> Cargar una operación
            </button>
          )}
          <LectorCapturas alGuardar={alGuardar} alFallar={alFallar} />
        </div>

        <Comprobante titulo="Operaciones" className="panel">
          {datos.operaciones.length === 0 ? (
            <p className="vacio">Sin operaciones en {nombreMes(mes)}.</p>
          ) : (
            <ul className="lista">
              {datos.operaciones.map((o) => (
                <FilaOperacion key={o.id} operacion={o} alBorrar={() => alGuardar("Operación borrada.")} alFallar={alFallar} />
              ))}
            </ul>
          )}
        </Comprobante>
      </div>
    </>
  );
}

function FilaOperacion({ operacion: o, alBorrar, alFallar }: { operacion: OperacionInversion; alBorrar: () => void; alFallar: (t: string) => void }) {
  const [confirmando, setConfirmando] = useState(false);
  const venta = o.lado === "venta";
  const tono = venta ? ((o.resultado_centavos ?? 0) >= 0 ? "bien" : "mal") : o.abierta ? "ojo" : "neutro";
  async function borrar() {
    try {
      await borrarOperacion(o.id);
      alBorrar();
    } catch (error) {
      alFallar((error as Error).message);
    }
  }
  return (
    <li className="item">
      <span className={`filete filete-${venta ? "lleno" : "punteado"} tono-${tono}`} aria-hidden="true" />
      <div className="item-texto">
        <span className="numeros">
          {o.fecha.slice(8, 10)}/{o.fecha.slice(5, 7)} · {venta ? "VENDE" : "COMPRA"}
        </span>
        <strong className="numeros">
          {o.activo} {decimal(o.cantidad, 8)} @ {decimal(o.precio)}
          {o.moneda !== "USD" && ` ${o.moneda}`}
        </strong>
      </div>
      <div className="item-derecha">
        {venta && o.resultado_centavos !== null && (
          <span className={`item-monto tono-${tono}`}>
            {signo(o.resultado_centavos)}U$D {importe(o.resultado_centavos)}
          </span>
        )}
        <Sello tono={tono}>{venta ? "CERRADA" : o.abierta ? "ABIERTA" : "COMPRA"}</Sello>
      </div>
      {confirmando ? (
        <span className="item-acciones">
          <button className="peligro chico" onClick={borrar}>
            Borrar
          </button>
          <button className="secundario chico" onClick={() => setConfirmando(false)}>
            No
          </button>
        </span>
      ) : (
        <button className="icono" onClick={() => setConfirmando(true)} aria-label={`Borrar operación de ${o.activo}`}>
          <Trash2 size={16} aria-hidden="true" />
        </button>
      )}
    </li>
  );
}

function FormularioOperacion({ alCerrar, alGuardar, alFallar }: { alCerrar: () => void; alGuardar: (t: string) => void; alFallar: (t: string) => void }) {
  const [datos, setDatos] = useState<OperacionNueva>({
    fecha: hoy(),
    activo: "",
    tipo_activo: "cripto",
    lado: "compra",
    cantidad: "",
    precio: "",
    comision: "",
    moneda: "USD",
  });
  const cambiar = <K extends keyof OperacionNueva>(campo: K, valor: OperacionNueva[K]) =>
    setDatos((anterior) => ({ ...anterior, [campo]: valor }));

  async function guardar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await cargarOperacion({ ...datos, comision: datos.comision || "0", moneda: datos.moneda || "USD" });
      alGuardar(`${datos.lado === "compra" ? "Compra" : "Venta"} de ${datos.activo.toUpperCase()} guardada.`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  return (
    <form className="formulario" onSubmit={guardar}>
      <Segmentado etiqueta="Compra o venta" opciones={[["compra", "Compra"], ["venta", "Venta"]] as const} valor={datos.lado ?? "compra"} alCambiar={(v) => cambiar("lado", v)} />
      <div className="dos-columnas">
        <label>
          Activo
          <input required value={datos.activo} onChange={(e) => cambiar("activo", e.target.value.toUpperCase())} placeholder="BTC, NVDA…" autoCapitalize="characters" />
        </label>
        <label>
          Fecha
          <input type="date" required max={hoy()} value={datos.fecha} onChange={(e) => cambiar("fecha", e.target.value)} />
        </label>
      </div>
      <Segmentado etiqueta="Tipo de activo" opciones={[["cripto", "Cripto"], ["accion", "Acción"]] as const} valor={datos.tipo_activo} alCambiar={(v) => cambiar("tipo_activo", v)} />
      <div className="dos-columnas">
        <label>
          Cantidad
          <input required inputMode="decimal" value={datos.cantidad} onChange={(e) => cambiar("cantidad", e.target.value)} placeholder="0,0412" />
        </label>
        <label>
          Precio por unidad
          <input required inputMode="decimal" value={datos.precio} onChange={(e) => cambiar("precio", e.target.value)} placeholder="182,40" />
        </label>
      </div>
      <div className="dos-columnas">
        <label>
          Moneda del precio
          <input
            required
            maxLength={3}
            value={datos.moneda ?? "USD"}
            onChange={(e) => cambiar("moneda", e.target.value.toUpperCase())}
            placeholder="USD"
            autoCapitalize="characters"
          />
        </label>
        <label>
          Comisión (U$D)
          <input inputMode="decimal" value={datos.comision ?? ""} onChange={(e) => cambiar("comision", e.target.value)} placeholder="0" />
        </label>
      </div>
      <p className="nota">
        Punto o coma, los dos sirven para los decimales. Una acción de Brasil, como WEGE3, va en BRL: se pasa a dólares con el
        cambio de ese día.
      </p>
      <button className="principal">Guardar operación</button>
      <button type="button" className="secundario" onClick={alCerrar}>
        Cancelar
      </button>
    </form>
  );
}

function signo(valor: number): string {
  return valor > 0 ? "+" : valor < 0 ? "−" : "";
}
