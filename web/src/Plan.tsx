// Plan: los fijos y las cuotas que se esperan pagar. El reporte compara lo real contra esto.
import { Download, Plus } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  borrarDelPlan,
  guardarCuota,
  guardarFijo,
  traerCategorias,
  traerPlan,
  type CuotaPlan,
  type FijoPlan,
  type Plan as PlanDatos,
} from "./api";
import { Comprobante } from "./comprobante";
import { Segmentado } from "./controles";
import { importe, mesActual, moverMes, nombreMes, plata } from "./formato";

type Vista = "fijos" | "cuotas";
type Mensaje = { tipo: "bien" | "error"; texto: string } | null;
type Avisar = { alGuardar: (texto: string) => void; alFallar: (texto: string) => void };

const MONEDAS = [
  ["ARS", "Pesos"],
  ["USD", "Dólares"],
] as const;

export function Plan() {
  const [vista, setVista] = useState<Vista>("fijos");
  const [datos, setDatos] = useState<PlanDatos | null>(null);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [mensaje, setMensaje] = useState<Mensaje>(null);

  const recargar = useCallback(() => {
    traerPlan()
      .then(setDatos)
      .catch((error: Error) => setMensaje({ tipo: "error", texto: error.message }));
    traerCategorias().then(setCategorias).catch(() => setCategorias([]));
  }, []);
  useEffect(recargar, [recargar]);

  const avisar: Avisar = {
    alGuardar: (texto) => {
      setMensaje({ tipo: "bien", texto });
      recargar();
    },
    alFallar: (texto) => setMensaje({ tipo: "error", texto }),
  };

  const totalFijos = (datos?.fijos ?? []).filter((f) => f.moneda === "ARS").reduce((s, f) => s + f.monto_centavos, 0);

  return (
    <main className="pagina">
      <div className="titulo-con-accion">
        <h1 className="titulo-pagina">Plan</h1>
        <a className="boton-enlace" href="#/categorias">
          Categorías y reglas
        </a>
        <a className="boton-enlace" href="/api/plan.csv" download="plan.csv">
          <Download size={16} aria-hidden="true" /> Bajar plan.csv
        </a>
      </div>
      <p className="nota">Lo que esperás pagar cada mes. Gastos compara contra esto y avisa qué falta o vino distinto.</p>
      <div className="solo-celular">
        <Segmentado
          etiqueta="Qué ver"
          opciones={[
            ["fijos", `Fijos · ${datos?.fijos.length ?? "…"}`],
            ["cuotas", `Cuotas · ${datos?.cuotas.length ?? "…"}`],
          ]}
          valor={vista}
          alCambiar={setVista}
        />
      </div>
      {mensaje && (
        <p className={`mensaje mensaje-${mensaje.tipo}`} role="status">
          {mensaje.texto}
        </p>
      )}
      <datalist id="categorias-plan">
        {categorias.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>

      <div className="paneles paneles-parejos">
        <Comprobante
          titulo={
            <>
              Fijos <span className="contador">{plata(totalFijos)} por mes</span>
            </>
          }
          className={vista === "fijos" ? "panel" : "panel oculto-celular"}
        >
          {datos === null ? (
            <p className="nota">Cargando…</p>
          ) : (
            <ListaEditable
              items={datos.fijos}
              agregar="Agregar un fijo"
              resumen={(f) => ({
                titulo: f.concepto,
                detalle: [f.dia ? `día ${f.dia}` : null, f.categoria ?? "sin categoría", `busca "${f.texto}"`],
                monto: plata(f.monto_centavos, f.moneda),
              })}
              editor={(f, cerrar) => <EditorFijo fijo={f} alCerrar={cerrar} {...avisar} />}
            />
          )}
        </Comprobante>

        <Comprobante titulo="Cuotas" tinte="violeta" className={vista === "cuotas" ? "panel" : "panel oculto-celular"}>
          {datos === null ? (
            <p className="nota">Cargando…</p>
          ) : (
            <ListaEditable
              items={datos.cuotas}
              agregar="Agregar una cuota"
              resumen={(c) => {
                const avance = avanceCuota(c);
                return {
                  titulo: c.concepto,
                  detalle: [avance.texto, c.categoria ?? "sin categoría"],
                  monto: plata(c.monto_centavos, c.moneda),
                  avance: avance.fraccion,
                };
              }}
              editor={(c, cerrar) => <EditorCuota cuota={c} alCerrar={cerrar} {...avisar} />}
            />
          )}
        </Comprobante>
      </div>
    </main>
  );
}

type Resumen = { titulo: string; detalle: (string | null)[]; monto: string; avance?: number };

/** Una lista donde cada fila se abre para editarla, y un botón para agregar al final. */
function ListaEditable<T extends { id: number }>({
  items,
  agregar,
  resumen,
  editor,
}: {
  items: T[];
  agregar: string;
  resumen: (item: T) => Resumen;
  editor: (item: T | null, cerrar: () => void) => React.ReactNode;
}) {
  const [abierto, setAbierto] = useState<number | "nuevo" | null>(null);
  const cerrar = () => setAbierto(null);
  return (
    <>
      {items.length === 0 && abierto !== "nuevo" && <p className="vacio">Todavía no hay nada acá.</p>}
      <ul className="lista">
        {items.map((item) => {
          if (abierto === item.id) return <li key={item.id} className="item editor">{editor(item, cerrar)}</li>;
          const r = resumen(item);
          return (
            <li key={item.id} className="item">
              <div className="item-texto">
                <strong>{r.titulo}</strong>
                <span>{r.detalle.filter(Boolean).join(" · ")}</span>
                {r.avance !== undefined && (
                  <span className="avance" aria-hidden="true">
                    <span style={{ width: `${Math.round(r.avance * 100)}%` }} />
                  </span>
                )}
              </div>
              <span className="item-monto">{r.monto}</span>
              <button type="button" className="boton-texto" onClick={() => setAbierto(item.id)}>
                Editar
              </button>
            </li>
          );
        })}
        {abierto === "nuevo" && <li className="item editor">{editor(null, cerrar)}</li>}
      </ul>
      {abierto !== "nuevo" && (
        <button type="button" className="agregar" onClick={() => setAbierto("nuevo")}>
          <Plus size={16} aria-hidden="true" /> {agregar}
        </button>
      )}
    </>
  );
}

function EditorFijo({ fijo, alCerrar, alGuardar, alFallar }: { fijo: FijoPlan | null; alCerrar: () => void } & Avisar) {
  const [concepto, setConcepto] = useState(fijo?.concepto ?? "");
  const [texto, setTexto] = useState(fijo?.texto ?? "");
  const [monto, setMonto] = useState(fijo ? importe(fijo.monto_centavos) : "");
  const [moneda, setMoneda] = useState<"ARS" | "USD">((fijo?.moneda as "ARS" | "USD") ?? "ARS");
  const [dia, setDia] = useState(fijo?.dia ? String(fijo.dia) : "");
  const [categoria, setCategoria] = useState(fijo?.categoria ?? "");

  async function guardar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await guardarFijo(
        { concepto, texto, monto, moneda, dia: dia ? Number(dia) : null, categoria: categoria || null },
        fijo?.id,
      );
      alCerrar();
      alGuardar(fijo ? `${concepto}: guardado.` : `${concepto}: agregado al plan.`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  return (
    <form className="editor-plan" onSubmit={guardar}>
      <Campo etiqueta="Concepto" valor={concepto} alCambiar={setConcepto} requerido />
      <Campo etiqueta="Texto que aparece en el resumen" valor={texto} alCambiar={setTexto} requerido numeros />
      <div className="dos-columnas">
        <Campo etiqueta="Monto por mes" valor={monto} alCambiar={setMonto} requerido decimal />
        <Campo etiqueta="Día que se debita" valor={dia} alCambiar={setDia} entero />
      </div>
      <Segmentado etiqueta="Moneda" opciones={MONEDAS} valor={moneda} alCambiar={setMoneda} />
      <Campo etiqueta="Categoría" valor={categoria} alCambiar={setCategoria} lista="categorias-plan" />
      <Acciones nuevo={!fijo} alCerrar={alCerrar} alBorrar={fijo ? () => borrar("fijos", fijo.id, fijo.concepto, alCerrar, alGuardar, alFallar) : undefined} />
    </form>
  );
}

function EditorCuota({ cuota, alCerrar, alGuardar, alFallar }: { cuota: CuotaPlan | null; alCerrar: () => void } & Avisar) {
  const [concepto, setConcepto] = useState(cuota?.concepto ?? "");
  const [texto, setTexto] = useState(cuota?.texto ?? "");
  const [monto, setMonto] = useState(cuota ? importe(cuota.monto_centavos) : "");
  const [moneda, setMoneda] = useState<"ARS" | "USD">((cuota?.moneda as "ARS" | "USD") ?? "ARS");
  const [cantidad, setCantidad] = useState(cuota ? String(cuota.cantidad) : "");
  const [primerMes, setPrimerMes] = useState(cuota?.primer_mes ?? moverMes(mesActual(), 1));
  const [categoria, setCategoria] = useState(cuota?.categoria ?? "");

  async function guardar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await guardarCuota(
        { concepto, texto, monto, moneda, cantidad: Number(cantidad), primer_mes: primerMes, categoria: categoria || null },
        cuota?.id,
      );
      alCerrar();
      alGuardar(cuota ? `${concepto}: guardada.` : `${concepto}: agregada al plan.`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  return (
    <form className="editor-plan" onSubmit={guardar}>
      <Campo etiqueta="Concepto" valor={concepto} alCambiar={setConcepto} requerido />
      <Campo etiqueta="Texto que aparece en el resumen" valor={texto} alCambiar={setTexto} requerido numeros />
      <div className="dos-columnas">
        <Campo etiqueta="Monto de cada cuota" valor={monto} alCambiar={setMonto} requerido decimal />
        <Campo etiqueta="Cantidad de cuotas" valor={cantidad} alCambiar={setCantidad} requerido entero />
      </div>
      <div className="dos-columnas">
        <label className="campo">
          <span>Mes de la primera</span>
          <input type="month" required value={primerMes} onChange={(e) => setPrimerMes(e.target.value)} />
        </label>
        <Segmentado etiqueta="Moneda" opciones={MONEDAS} valor={moneda} alCambiar={setMoneda} />
      </div>
      <Campo etiqueta="Categoría" valor={categoria} alCambiar={setCategoria} lista="categorias-plan" />
      <Acciones nuevo={!cuota} alCerrar={alCerrar} alBorrar={cuota ? () => borrar("cuotas", cuota.id, cuota.concepto, alCerrar, alGuardar, alFallar) : undefined} />
    </form>
  );
}

async function borrar(
  tabla: "fijos" | "cuotas",
  id: number,
  concepto: string,
  alCerrar: () => void,
  alGuardar: (texto: string) => void,
  alFallar: (texto: string) => void,
) {
  try {
    await borrarDelPlan(tabla, id);
    alCerrar();
    alGuardar(`${concepto}: sacado del plan.`);
  } catch (error) {
    alFallar((error as Error).message);
  }
}

function Campo({
  etiqueta,
  valor,
  alCambiar,
  requerido = false,
  decimal = false,
  entero = false,
  numeros = false,
  lista,
}: {
  etiqueta: string;
  valor: string;
  alCambiar: (valor: string) => void;
  requerido?: boolean;
  decimal?: boolean;
  entero?: boolean;
  numeros?: boolean;
  lista?: string;
}) {
  return (
    <label className="campo">
      <span>{etiqueta}</span>
      <input
        className={numeros || decimal ? "con-numeros" : undefined}
        required={requerido}
        value={valor}
        list={lista}
        inputMode={decimal ? "decimal" : entero ? "numeric" : undefined}
        autoComplete="off"
        onChange={(e) => alCambiar(e.target.value)}
      />
    </label>
  );
}

function Acciones({ nuevo, alCerrar, alBorrar }: { nuevo: boolean; alCerrar: () => void; alBorrar?: () => void }) {
  const [confirmando, setConfirmando] = useState(false);
  return (
    <div className="acciones-plan">
      <button className="principal chico">{nuevo ? "Agregar" : "Guardar"}</button>
      <button type="button" className="secundario chico" onClick={alCerrar}>
        Cancelar
      </button>
      {alBorrar &&
        (confirmando ? (
          <button type="button" className="peligro chico" onClick={alBorrar}>
            Sí, sacarlo
          </button>
        ) : (
          <button type="button" className="boton-texto peligroso" onClick={() => setConfirmando(true)}>
            Sacar del plan
          </button>
        ))}
    </div>
  );
}

/** Qué cuota toca este mes, para la barra de avance. */
export function avanceCuota(cuota: { cantidad: number; primer_mes: string }, mes = mesActual()) {
  const numero = mesesEntre(cuota.primer_mes, mes) + 1;
  const ultimo = moverMes(cuota.primer_mes, cuota.cantidad - 1);
  if (numero < 1) return { fraccion: 0, texto: `empieza en ${nombreMes(cuota.primer_mes)}` };
  if (numero > cuota.cantidad) return { fraccion: 1, texto: `terminó en ${nombreMes(ultimo)}` };
  const de = `${String(numero).padStart(2, "0")}/${String(cuota.cantidad).padStart(2, "0")}`;
  return { fraccion: numero / cuota.cantidad, texto: `cuota ${de} · termina en ${nombreMes(ultimo)}` };
}

function mesesEntre(desde: string, hasta: string): number {
  const [a1, m1] = desde.split("-").map(Number) as [number, number];
  const [a2, m2] = hasta.split("-").map(Number) as [number, number];
  return a2 * 12 + m2 - (a1 * 12 + m1);
}
