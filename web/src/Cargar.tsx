// Cargar gastos y pagos que no vienen en un PDF, y borrar lo cargado a mano.
import { Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  borrarManual,
  cargarGasto,
  cargarPago,
  traerCategorias,
  traerManuales,
  type Aviso,
  type GastoNuevo,
  type Manual,
} from "./api";
import { nombreTarjeta } from "./atender";
import { Comprobante } from "./comprobante";
import { Segmentado } from "./controles";
import { diaYMes, hoy, plata } from "./formato";

type Tipo = "gasto" | "pago";
type Moneda = "ARS" | "USD";
type Mensaje = { tipo: "bien" | "error"; texto: string } | null;

const MEDIOS = [
  ["efectivo", "Efectivo"],
  ["debito", "Débito"],
  ["transferencia", "Transferencia"],
] as const;

const TARJETAS = [
  ["tarjeta_comafi", "Comafi"],
  ["tarjeta_nacion", "Nación"],
] as const;

const MONEDAS = [
  ["ARS", "Pesos"],
  ["USD", "Dólares"],
] as const;

export function Cargar() {
  const [tipo, setTipo] = useState<Tipo>("gasto");
  const [manuales, setManuales] = useState<Manual[]>([]);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [mensaje, setMensaje] = useState<Mensaje>(null);

  const recargar = useCallback(() => {
    traerManuales()
      .then(setManuales)
      .catch((error: Error) => setMensaje({ tipo: "error", texto: error.message }));
  }, []);
  useEffect(recargar, [recargar]);
  useEffect(() => {
    traerCategorias().then(setCategorias).catch(() => setCategorias([]));
  }, []);

  const avisar = {
    alGuardar: (texto: string) => {
      setMensaje({ tipo: "bien", texto });
      recargar();
    },
    alFallar: (texto: string) => setMensaje({ tipo: "error", texto }),
  };

  return (
    <main className="pagina">
      <h1 className="titulo-pagina">Cargar</h1>
      <div className="paneles">
        <section className="panel">
          <Segmentado
            etiqueta="Qué cargar"
            opciones={[
              ["gasto", "Gasto"],
              ["pago", "Pago de tarjeta"],
            ]}
            valor={tipo}
            alCambiar={(valor) => {
              setTipo(valor);
              setMensaje(null);
            }}
          />
          {tipo === "gasto" ? <FormularioGasto {...avisar} categorias={categorias} /> : <FormularioPago {...avisar} />}
          {mensaje && (
            <p className={`mensaje mensaje-${mensaje.tipo}`} role="status">
              {mensaje.texto}
            </p>
          )}
        </section>

        <Comprobante titulo="Últimos cargados a mano" className="panel">
          {manuales.length === 0 ? (
            <p className="vacio">Todavía no cargaste nada a mano.</p>
          ) : (
            <ul className="lista">
              {manuales.map((manual) => (
                <FilaManual key={manual.id} manual={manual} alBorrar={() => avisar.alGuardar("Borrado.")} alFallar={avisar.alFallar} />
              ))}
            </ul>
          )}
        </Comprobante>
      </div>
    </main>
  );
}

type Avisar = { alGuardar: (texto: string) => void; alFallar: (texto: string) => void };

function FormularioGasto({ alGuardar, alFallar, categorias }: Avisar & { categorias: string[] }) {
  const [datos, setDatos] = useState<GastoNuevo>(gastoVacio());
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const [categoria, setCategoria] = useState("");
  const [enviando, setEnviando] = useState(false);
  const grande = avisos.some((aviso) => aviso.codigo === "grande_sin_anticipar");

  function cambiar<K extends keyof GastoNuevo>(campo: K, valor: GastoNuevo[K]) {
    setDatos((anterior) => ({ ...anterior, [campo]: valor }));
    setAvisos([]); // Si cambia el gasto, los avisos de antes ya no valen.
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      // Si ya se mostraron avisos, este segundo envío es la confirmación.
      const confirmado = avisos.length > 0;
      const resultado = await cargarGasto({
        ...datos,
        confirmado,
        categoria: confirmado && categoria.trim() ? categoria.trim() : null,
      });
      if (resultado.tipo === "avisos") {
        setAvisos(resultado.avisos);
        return;
      }
      const { categoria: queQuedo, plan_concepto } = resultado.guardado;
      alGuardar(`Guardado${plan_concepto ? `: es de ${plan_concepto}` : queQuedo ? ` en ${queQuedo}` : ""}.`);
      setDatos(gastoVacio());
      setAvisos([]);
      setCategoria("");
    } catch (error) {
      alFallar((error as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="formulario" onSubmit={enviar}>
      <Monto valor={datos.monto} moneda={datos.moneda ?? "ARS"} alCambiar={(valor) => cambiar("monto", valor)} />
      <Segmentado etiqueta="Moneda" opciones={MONEDAS} valor={datos.moneda ?? "ARS"} alCambiar={(valor) => cambiar("moneda", valor)} />
      <label>
        Descripción
        <input
          required
          value={datos.descripcion}
          onChange={(evento) => cambiar("descripcion", evento.target.value)}
          placeholder="Café, Medicus, PAPA Dexter…"
        />
      </label>
      <label>
        Fecha
        <input type="date" required max={hoy()} value={datos.fecha ?? ""} onChange={(e) => cambiar("fecha", e.target.value)} />
      </label>
      <div className="campo">
        <span>Medio</span>
        <Segmentado etiqueta="Medio" opciones={MEDIOS} valor={datos.medio ?? "efectivo"} alCambiar={(valor) => cambiar("medio", valor)} />
      </div>

      {avisos.length > 0 && (
        <div className="avisos" role="alert">
          {avisos.map((aviso) => (
            <p key={aviso.codigo}>{aviso.mensaje}</p>
          ))}
          {grande && (
            <label>
              Categoría, si querés ponerla ya
              <input list="categorias-cargar" value={categoria} onChange={(e) => setCategoria(e.target.value)} placeholder="Hogar, Ropa…" />
              <datalist id="categorias-cargar">
                {categorias.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </label>
          )}
        </div>
      )}

      <button className="principal" disabled={enviando}>
        {enviando ? "Guardando…" : avisos.length > 0 ? "Guardar igual" : "Guardar gasto"}
      </button>
      {avisos.length > 0 && (
        <button type="button" className="secundario" onClick={() => setAvisos([])}>
          Cancelar
        </button>
      )}
    </form>
  );
}

function FormularioPago({ alGuardar, alFallar }: Avisar) {
  const [tarjeta, setTarjeta] = useState<(typeof TARJETAS)[number][0]>("tarjeta_comafi");
  const [monto, setMonto] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [moneda, setMoneda] = useState<Moneda>("ARS");
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      await cargarPago({ tarjeta, monto, fecha, moneda });
      alGuardar("Pago guardado. No suma como gasto: deja el resumen como avisado.");
      setMonto("");
    } catch (error) {
      alFallar((error as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="formulario" onSubmit={enviar}>
      <Monto valor={monto} moneda={moneda} alCambiar={setMonto} />
      <Segmentado etiqueta="Moneda" opciones={MONEDAS} valor={moneda} alCambiar={setMoneda} />
      <div className="campo">
        <span>Tarjeta</span>
        <Segmentado etiqueta="Tarjeta" opciones={TARJETAS} valor={tarjeta} alCambiar={setTarjeta} />
      </div>
      <label>
        Fecha del pago
        <input type="date" required max={hoy()} value={fecha} onChange={(e) => setFecha(e.target.value)} />
      </label>
      <button className="principal" disabled={enviando}>
        {enviando ? "Guardando…" : "Guardar pago"}
      </button>
    </form>
  );
}

/** El monto, grande y primero, con el teclado numérico. Viaja como texto y nunca pasa por float. */
function Monto({ valor, moneda, alCambiar }: { valor: string; moneda: string; alCambiar: (valor: string) => void }) {
  return (
    <label className="monto-entrada">
      <span>Monto</span>
      <span className="monto-entrada-caja">
        <span className="monto-entrada-moneda" aria-hidden="true">
          {moneda === "USD" ? "U$D" : "$"}
        </span>
        <input
          required
          inputMode="decimal"
          autoComplete="off"
          value={valor}
          onChange={(evento) => alCambiar(evento.target.value)}
          placeholder="0"
        />
      </span>
    </label>
  );
}

function FilaManual({ manual, alBorrar, alFallar }: { manual: Manual; alBorrar: () => void; alFallar: (texto: string) => void }) {
  const [confirmando, setConfirmando] = useState(false);
  const detalle = manual.plan_concepto ?? manual.categoria ?? (manual.tarjeta ? `pago ${nombreTarjeta(manual.tarjeta)}` : "");

  async function borrar() {
    try {
      await borrarManual(manual.id);
      alBorrar();
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  return (
    <li className="item">
      <div className="item-texto">
        <strong>{manual.descripcion}</strong>
        <span>
          {diaYMes(manual.fecha)}
          {manual.medio && ` · ${manual.medio}`}
          {detalle && ` · ${detalle}`}
        </span>
      </div>
      <span className="item-monto">{plata(manual.monto_centavos, manual.moneda)}</span>
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
        <button className="icono" onClick={() => setConfirmando(true)} aria-label={`Borrar ${manual.descripcion}`}>
          <Trash2 size={16} aria-hidden="true" />
        </button>
      )}
    </li>
  );
}

function gastoVacio(): GastoNuevo {
  return { monto: "", descripcion: "", fecha: hoy(), medio: "efectivo", moneda: "ARS" };
}
