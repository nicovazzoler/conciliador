// Cargar gastos y pagos que no vienen en un PDF, y borrar lo cargado a mano.
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  borrarManual,
  cargarGasto,
  cargarPago,
  traerManuales,
  type Aviso,
  type GastoNuevo,
  type Manual,
} from "./api";
import { diaYMes, hoy, plata } from "./formato";

type Tipo = "gasto" | "pago";
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

export function Cargar() {
  const [tipo, setTipo] = useState<Tipo>("gasto");
  const [manuales, setManuales] = useState<Manual[]>([]);
  const [mensaje, setMensaje] = useState<Mensaje>(null);

  const recargar = useCallback(() => {
    traerManuales()
      .then(setManuales)
      .catch((error: Error) => setMensaje({ tipo: "error", texto: error.message }));
  }, []);
  useEffect(recargar, [recargar]);

  function guardado(texto: string) {
    setMensaje({ tipo: "bien", texto });
    recargar();
  }

  return (
    <main className="pagina">
      <h1 className="titulo-pagina">Cargar</h1>

      <div className="pestanias" role="tablist">
        {(["gasto", "pago"] as const).map((opcion) => (
          <button
            key={opcion}
            role="tab"
            aria-selected={tipo === opcion}
            className={tipo === opcion ? "pestania activa" : "pestania"}
            onClick={() => {
              setTipo(opcion);
              setMensaje(null);
            }}
          >
            {opcion === "gasto" ? "Gasto" : "Pago de tarjeta"}
          </button>
        ))}
      </div>

      {tipo === "gasto" ? (
        <FormularioGasto alGuardar={guardado} alFallar={(texto) => setMensaje({ tipo: "error", texto })} />
      ) : (
        <FormularioPago alGuardar={guardado} alFallar={(texto) => setMensaje({ tipo: "error", texto })} />
      )}

      {mensaje && <p className={`mensaje mensaje-${mensaje.tipo}`}>{mensaje.texto}</p>}

      <section className="seccion">
        <h2>Últimos cargados a mano</h2>
        {manuales.length === 0 ? (
          <p className="nota">Todavía no cargaste nada a mano.</p>
        ) : (
          <ul>
            {manuales.map((manual) => (
              <FilaManual
                key={manual.id}
                manual={manual}
                alBorrar={() => guardado("Borrado.")}
                alFallar={(texto) => setMensaje({ tipo: "error", texto })}
              />
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

type Avisar = { alGuardar: (texto: string) => void; alFallar: (texto: string) => void };

function FormularioGasto({ alGuardar, alFallar }: Avisar) {
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
      // Si ya mostramos avisos, este segundo envío es la confirmación.
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
      <Monto valor={datos.monto} alCambiar={(valor) => cambiar("monto", valor)} />
      <label>
        Descripción
        <input
          required
          value={datos.descripcion}
          onChange={(evento) => cambiar("descripcion", evento.target.value)}
          placeholder="Café, Medicus, PAPA Dexter…"
        />
      </label>
      <div className="dos-columnas">
        <label>
          Fecha
          <input type="date" required max={hoy()} value={datos.fecha ?? ""} onChange={(e) => cambiar("fecha", e.target.value)} />
        </label>
        <label>
          Medio
          <select value={datos.medio} onChange={(e) => cambiar("medio", e.target.value as GastoNuevo["medio"])}>
            {MEDIOS.map(([valor, texto]) => (
              <option key={valor} value={valor}>
                {texto}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Moneda valor={datos.moneda ?? "ARS"} alCambiar={(valor) => cambiar("moneda", valor)} />

      {avisos.length > 0 && (
        <div className="avisos" role="alert">
          {avisos.map((aviso) => (
            <p key={aviso.codigo}>{aviso.mensaje}</p>
          ))}
          {grande && (
            <label>
              Categoría (opcional: si la dejás vacía, queda para revisar)
              <input value={categoria} onChange={(e) => setCategoria(e.target.value)} placeholder="Hogar, Ropa…" />
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
  const [moneda, setMoneda] = useState<"ARS" | "USD">("ARS");
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      await cargarPago({ tarjeta, monto, fecha, moneda });
      alGuardar("Pago guardado. No suma como gasto: marca el resumen como avisado.");
      setMonto("");
    } catch (error) {
      alFallar((error as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="formulario" onSubmit={enviar}>
      <label>
        Tarjeta
        <select value={tarjeta} onChange={(e) => setTarjeta(e.target.value as typeof tarjeta)}>
          {TARJETAS.map(([valor, texto]) => (
            <option key={valor} value={valor}>
              {texto}
            </option>
          ))}
        </select>
      </label>
      <Monto valor={monto} alCambiar={setMonto} />
      <label>
        Fecha
        <input type="date" required max={hoy()} value={fecha} onChange={(e) => setFecha(e.target.value)} />
      </label>
      <Moneda valor={moneda} alCambiar={setMoneda} />
      <button className="principal" disabled={enviando}>
        {enviando ? "Guardando…" : "Guardar pago"}
      </button>
    </form>
  );
}

function Monto({ valor, alCambiar }: { valor: string; alCambiar: (valor: string) => void }) {
  return (
    <label>
      Monto
      {/* Texto con teclado numérico: el monto viaja como texto y nunca pasa por float. */}
      <input
        required
        inputMode="decimal"
        autoComplete="off"
        value={valor}
        onChange={(evento) => alCambiar(evento.target.value)}
        placeholder="15.000 o 9.832,83"
      />
    </label>
  );
}

function Moneda({ valor, alCambiar }: { valor: "ARS" | "USD"; alCambiar: (valor: "ARS" | "USD") => void }) {
  return (
    <fieldset className="moneda">
      <legend>Moneda</legend>
      {(["ARS", "USD"] as const).map((opcion) => (
        <label key={opcion}>
          <input type="radio" name="moneda" checked={valor === opcion} onChange={() => alCambiar(opcion)} />
          {opcion === "ARS" ? "Pesos" : "Dólares"}
        </label>
      ))}
    </fieldset>
  );
}

function FilaManual({ manual, alBorrar, alFallar }: { manual: Manual; alBorrar: () => void; alFallar: (texto: string) => void }) {
  const [confirmando, setConfirmando] = useState(false);
  const detalle = manual.plan_concepto ?? manual.categoria ?? (manual.tarjeta ? "pago de tarjeta" : "");

  async function borrar() {
    try {
      await borrarManual(manual.id);
      alBorrar();
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  return (
    <li className="fila">
      <div className="fila-texto">
        <strong>
          {diaYMes(manual.fecha)} · {plata(manual.monto_centavos, manual.moneda)}
        </strong>
        <p>
          {manual.descripcion}
          {detalle && ` · ${detalle}`}
        </p>
      </div>
      {confirmando ? (
        <div className="confirmar">
          <button className="peligro" onClick={borrar}>
            Sí, borrar
          </button>
          <button className="secundario" onClick={() => setConfirmando(false)}>
            No
          </button>
        </div>
      ) : (
        <button className="secundario" onClick={() => setConfirmando(true)}>
          Borrar
        </button>
      )}
    </li>
  );
}

function gastoVacio(): GastoNuevo {
  return { monto: "", descripcion: "", fecha: hoy(), medio: "efectivo", moneda: "ARS" };
}
