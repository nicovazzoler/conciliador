// Inversiones: Portafolio (lo que tenés hoy) y Trading (lo que operaste en el mes).
import { ChevronLeft, ChevronRight, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  actualizarPrecios,
  borrarOperacion,
  cargarOperacion,
  traerInversiones,
  type Inversiones as Datos,
  type OperacionInversion,
  type OperacionNueva,
} from "./api";
import { Comprobante, Renglon, Sello } from "./comprobante";
import { Segmentado } from "./controles";
import { decimal, hoy, importe, mesActual, moverMes, nombreMes, plata } from "./formato";

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
        <Portafolio datos={datos} actualizando={actualizando} alActualizar={precios} />
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

function Portafolio({ datos, actualizando, alActualizar }: { datos: Datos; actualizando: boolean; alActualizar: () => void }) {
  const conValor = datos.posiciones.filter((p) => p.valor_centavos !== null);
  const total = conValor.reduce((s, p) => s + (p.valor_centavos ?? 0), 0);
  const porcentaje = datos.invertido_centavos ? (datos.no_realizado_centavos / datos.invertido_centavos) * 100 : 0;

  if (datos.posiciones.length === 0)
    return (
      <Comprobante titulo="Cartera" className="inversion-vacia">
        <p className="vacio">No tenés posiciones abiertas. Cargá tus compras en Trading y acá aparece lo que tenés.</p>
      </Comprobante>
    );

  return (
    <div className="paneles">
      <Comprobante
        titulo="Cartera"
        tinte="menta"
        className="panel"
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
        {total > 0 && (
          <>
            <div className="composicion" aria-hidden="true">
              {conValor.map((p, i) => (
                <span key={p.activo} style={{ width: `${((p.valor_centavos ?? 0) / total) * 100}%`, background: COLORES[i % COLORES.length] }} />
              ))}
            </div>
            <p className="nota numeros">
              {conValor.map((p) => `${p.activo} ${Math.round(((p.valor_centavos ?? 0) / total) * 100)}%`).join(" · ")}
            </p>
          </>
        )}
        <ul className="renglones">
          <Renglon concepto="Invertido en lo que tenés" monto={plata(datos.invertido_centavos, "USD")} />
        </ul>
        {datos.sin_precio.length > 0 && <p className="nota tono-ojo">Sin precio: {datos.sin_precio.join(", ")}. Su valor no suma a la cartera.</p>}
      </Comprobante>

      <Comprobante titulo="Posiciones" className="panel">
        <ul className="lista">
          {datos.posiciones.map((p) => {
            const variacion = p.no_realizado_centavos !== null && p.invertido_centavos ? (p.no_realizado_centavos / p.invertido_centavos) * 100 : null;
            return (
              <li key={p.activo} className="item">
                <span className="iniciales" aria-hidden="true">
                  {p.activo.slice(0, 3)}
                </span>
                <div className="item-texto">
                  <strong>{p.activo}</strong>
                  <span className="numeros">
                    {decimal(p.cantidad, 8)} · prom. U$D {decimal(p.costo_promedio)}
                  </span>
                </div>
                <div className="item-derecha">
                  <span className="item-monto">{p.valor_centavos === null ? "sin precio" : plata(p.valor_centavos, "USD")}</span>
                  {variacion !== null && (
                    <span className={`numeros ${variacion >= 0 ? "tono-bien" : "tono-mal"}`}>
                      {signo(variacion)}
                      {Math.abs(variacion).toLocaleString("es-AR", { maximumFractionDigits: 1 })}%
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </Comprobante>
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
  });
  const cambiar = <K extends keyof OperacionNueva>(campo: K, valor: OperacionNueva[K]) =>
    setDatos((anterior) => ({ ...anterior, [campo]: valor }));

  async function guardar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await cargarOperacion({ ...datos, comision: datos.comision || "0" });
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
          Precio por unidad (U$D)
          <input required inputMode="decimal" value={datos.precio} onChange={(e) => cambiar("precio", e.target.value)} placeholder="94.120,55" />
        </label>
      </div>
      <label>
        Comisión (U$D, opcional)
        <input inputMode="decimal" value={datos.comision ?? ""} onChange={(e) => cambiar("comision", e.target.value)} placeholder="0" />
      </label>
      <p className="nota">Usá coma para los decimales: 0,0412. El punto solo, como en 94.120, se lee como miles.</p>
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
