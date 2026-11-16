// Leer operaciones desde capturas de Quantfury o Binance. Lo leído no se guarda solo: se revisa y se confirma.
import { ImageUp } from "lucide-react";
import { useRef, useState } from "react";
import { cargarOperacion, ErrorApi, leerCapturas, type OperacionLeida } from "./api";
import { Comprobante } from "./comprobante";
import { decimal, diaYMes, hoy } from "./formato";

type Fila = OperacionLeida & { clave: number; elegida: boolean; editando: boolean };
type Estado = "quieto" | "leyendo" | "revisando" | "guardando";

const APPS: Record<string, string> = { quantfury: "Quantfury", binance: "Binance", captura: "otra app" };

export function LectorCapturas({ alGuardar, alFallar }: { alGuardar: (texto: string) => void; alFallar: (texto: string) => void }) {
  const [estado, setEstado] = useState<Estado>("quieto");
  const [cuantas, setCuantas] = useState(0);
  const [filas, setFilas] = useState<Fila[]>([]);
  const [avisos, setAvisos] = useState<string[]>([]);
  const entrada = useRef<HTMLInputElement>(null);
  const elegidas = filas.filter((f) => f.elegida);

  async function leer(lista: FileList | null) {
    const archivos = [...(lista ?? [])];
    if (entrada.current) entrada.current.value = ""; // Así se puede volver a elegir la misma captura.
    if (!archivos.length) return;
    setCuantas(archivos.length);
    setEstado("leyendo");
    try {
      const leido = await leerCapturas(archivos);
      setFilas(leido.operaciones.map((o, clave) => ({ ...o, clave, elegida: true, editando: false })));
      setAvisos(leido.avisos);
      setEstado("revisando");
    } catch (error) {
      setEstado("quieto");
      alFallar((error as Error).message);
    }
  }

  function cambiar(clave: number, cambios: Partial<Fila>) {
    setFilas((anteriores) => anteriores.map((f) => (f.clave === clave ? { ...f, ...cambios } : f)));
  }

  function descartar() {
    setFilas([]);
    setAvisos([]);
    setEstado("quieto");
  }

  async function guardar() {
    setEstado("guardando");
    let guardadas = 0;
    let repetidas = 0;
    const errores: string[] = [];
    for (const f of elegidas) {
      try {
        await cargarOperacion({
          fecha: f.fecha,
          activo: f.activo,
          tipo_activo: f.tipo_activo,
          lado: f.lado,
          cantidad: f.cantidad,
          precio: f.precio,
          comision: f.comision || "0",
          fuente: f.fuente,
          numero_operacion: f.numero_operacion,
        });
        guardadas += 1;
      } catch (error) {
        if (error instanceof ErrorApi && error.estado === 409) repetidas += 1;
        else errores.push(`${f.activo} del ${diaYMes(f.fecha)}: ${(error as Error).message}`);
      }
    }
    const resumen = [
      guardadas && `${guardadas} ${guardadas === 1 ? "operación guardada" : "operaciones guardadas"}`,
      repetidas && `${repetidas} ya ${repetidas === 1 ? "estaba cargada" : "estaban cargadas"}`,
    ].filter(Boolean);
    if (errores.length) {
      // Quedan a la vista las que fallaron, para corregirlas.
      const fallidas = new Set(errores.map((e) => e.split(" del ")[0]));
      setFilas((anteriores) => anteriores.filter((f) => f.elegida && fallidas.has(f.activo)));
      setEstado("revisando");
      alFallar([...resumen, ...errores].join(". ") + ".");
      return;
    }
    descartar();
    alGuardar((resumen.join(", ") || "No había nada para guardar") + ".");
  }

  if (estado === "quieto")
    return (
      <label className="agregar lector-boton">
        <ImageUp size={16} aria-hidden="true" /> Leer capturas de Quantfury o Binance
        <input ref={entrada} type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple onChange={(e) => leer(e.target.files)} />
      </label>
    );

  if (estado === "leyendo")
    return (
      <Comprobante titulo="Leyendo capturas" className="lector">
        <p className="lector-leyendo" role="status">
          Leyendo {cuantas === 1 ? "la captura" : `${cuantas} capturas`}…
        </p>
        <p className="nota">Se mandan a Claude para leerlas. Tarda unos segundos; no se guarda nada todavía.</p>
      </Comprobante>
    );

  return (
    <Comprobante titulo="Lo que se leyó" tinte="violeta" className="lector">
      <p className="nota">Revisá cada operación antes de guardarla. Las que destildes no se cargan.</p>
      {avisos.length > 0 && (
        <ul className="lector-avisos">
          {avisos.map((aviso) => (
            <li key={aviso}>{aviso}</li>
          ))}
        </ul>
      )}
      {filas.length === 0 ? (
        <p className="vacio">No se encontraron operaciones en las capturas.</p>
      ) : (
        <ul className="lista">
          {filas.map((f) => (
            <FilaLeida key={f.clave} fila={f} alCambiar={(cambios) => cambiar(f.clave, cambios)} />
          ))}
        </ul>
      )}
      <div className="lector-acciones">
        <button type="button" className="principal" disabled={estado === "guardando" || elegidas.length === 0} onClick={guardar}>
          {estado === "guardando"
            ? "Guardando…"
            : `Guardar ${elegidas.length} ${elegidas.length === 1 ? "operación" : "operaciones"}`}
        </button>
        <button type="button" className="secundario" disabled={estado === "guardando"} onClick={descartar}>
          Descartar
        </button>
      </div>
    </Comprobante>
  );
}

function FilaLeida({ fila: f, alCambiar }: { fila: Fila; alCambiar: (cambios: Partial<Fila>) => void }) {
  const venta = f.lado === "venta";
  return (
    <li className={f.elegida ? "item lector-fila" : "item lector-fila descartada"}>
      <div className="lector-linea">
        <input
          type="checkbox"
          checked={f.elegida}
          onChange={(e) => alCambiar({ elegida: e.target.checked })}
          aria-label={`Guardar ${f.lado} de ${f.activo}`}
        />
        <div className="item-texto">
          <span className="numeros">
            {diaYMes(f.fecha)} · {venta ? "VENDE" : "COMPRA"} · {APPS[f.fuente] ?? f.fuente}
          </span>
          <strong className="numeros">
            {f.activo} {decimal(f.cantidad.replace(",", "."), 8)} @ {decimal(f.precio.replace(",", "."))}
          </strong>
          {f.nota && <span className="lector-nota">{f.nota}</span>}
        </div>
        <button type="button" className="boton-texto" onClick={() => alCambiar({ editando: !f.editando })} aria-expanded={f.editando}>
          {f.editando ? "Listo" : "Corregir"}
        </button>
      </div>
      {f.editando && (
        <div className="formulario lector-editor">
          <div className="dos-columnas">
            <label>
              Activo
              <input value={f.activo} onChange={(e) => alCambiar({ activo: e.target.value.toUpperCase() })} />
            </label>
            <label>
              Fecha
              <input type="date" max={hoy()} value={f.fecha} onChange={(e) => alCambiar({ fecha: e.target.value })} />
            </label>
          </div>
          <div className="dos-columnas">
            <label>
              Operación
              <select value={f.lado} onChange={(e) => alCambiar({ lado: e.target.value as Fila["lado"] })}>
                <option value="compra">Compra</option>
                <option value="venta">Venta</option>
              </select>
            </label>
            <label>
              Tipo
              <select value={f.tipo_activo} onChange={(e) => alCambiar({ tipo_activo: e.target.value as Fila["tipo_activo"] })}>
                <option value="cripto">Cripto</option>
                <option value="accion">Acción</option>
              </select>
            </label>
          </div>
          <div className="dos-columnas">
            <label>
              Cantidad
              <input inputMode="decimal" value={f.cantidad} onChange={(e) => alCambiar({ cantidad: e.target.value })} />
            </label>
            <label>
              Precio (U$D)
              <input inputMode="decimal" value={f.precio} onChange={(e) => alCambiar({ precio: e.target.value })} />
            </label>
          </div>
          <label>
            Comisión (U$D)
            <input inputMode="decimal" value={f.comision} onChange={(e) => alCambiar({ comision: e.target.value })} />
          </label>
        </div>
      )}
    </li>
  );
}
