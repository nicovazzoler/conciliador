// Categorías y reglas: renombrar, unir y borrar categorías; cambiar o borrar reglas.
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  borrarCategoria,
  borrarRegla,
  editarRegla,
  renombrarCategoria,
  traerCategoriasDetalle,
  traerReglas,
  type CategoriaDetalle,
  type ReglaDetalle,
} from "./api";
import { Comprobante } from "./comprobante";

type Mensaje = { tipo: "bien" | "error"; texto: string } | null;
type Avisar = { alGuardar: (texto: string) => void; alFallar: (texto: string) => void };

export function Categorias() {
  const [categorias, setCategorias] = useState<CategoriaDetalle[] | null>(null);
  const [reglas, setReglas] = useState<ReglaDetalle[] | null>(null);
  const [mensaje, setMensaje] = useState<Mensaje>(null);

  const recargar = useCallback(() => {
    traerCategoriasDetalle()
      .then(setCategorias)
      .catch((error: Error) => setMensaje({ tipo: "error", texto: error.message }));
    traerReglas()
      .then(setReglas)
      .catch((error: Error) => setMensaje({ tipo: "error", texto: error.message }));
  }, []);
  useEffect(recargar, [recargar]);

  const avisar: Avisar = {
    alGuardar: (texto) => {
      setMensaje({ tipo: "bien", texto });
      recargar();
    },
    alFallar: (texto) => setMensaje({ tipo: "error", texto }),
  };

  return (
    <main className="pagina">
      <h1 className="titulo-pagina">Categorías y reglas</h1>
      <p className="nota">
        Para unir dos categorías, renombrá una con el nombre de la otra. Borrar una manda lo suyo de vuelta a Gastos varios.
      </p>
      {mensaje && (
        <p className={`mensaje mensaje-${mensaje.tipo}`} role="status">
          {mensaje.texto}
        </p>
      )}
      <datalist id="categorias-edicion">
        {(categorias ?? []).map((c) => (
          <option key={c.nombre} value={c.nombre} />
        ))}
      </datalist>
      <div className="paneles paneles-parejos">
        <Comprobante titulo="Categorías" className="panel">
          {categorias === null ? (
            <p className="nota">Cargando…</p>
          ) : categorias.length === 0 ? (
            <p className="vacio">Todavía no hay categorías.</p>
          ) : (
            <ul className="lista">
              {categorias.map((c) => (
                <FilaCategoria key={c.nombre} categoria={c} {...avisar} />
              ))}
            </ul>
          )}
        </Comprobante>
        <Comprobante titulo="Reglas" tinte="violeta" className="panel">
          {reglas === null ? (
            <p className="nota">Cargando…</p>
          ) : reglas.length === 0 ? (
            <p className="vacio">Todavía no hay reglas. Se crean desde Revisar.</p>
          ) : (
            <ul className="lista">
              {reglas.map((r) => (
                <FilaRegla key={r.id} regla={r} {...avisar} />
              ))}
            </ul>
          )}
        </Comprobante>
      </div>
    </main>
  );
}

function FilaCategoria({ categoria: c, alGuardar, alFallar }: { categoria: CategoriaDetalle } & Avisar) {
  const [modo, setModo] = useState<"ver" | "renombrar" | "borrar">("ver");
  const [nombre, setNombre] = useState(c.nombre);
  const uso = [
    c.movimientos && `${c.movimientos} ${c.movimientos === 1 ? "movimiento" : "movimientos"}`,
    c.reglas && `${c.reglas} ${c.reglas === 1 ? "regla" : "reglas"}`,
    c.en_plan && `${c.en_plan} del plan`,
  ].filter(Boolean);

  async function renombrar(evento: FormEvent) {
    evento.preventDefault();
    try {
      const cambiados = await renombrarCategoria(c.nombre, nombre.trim());
      setModo("ver");
      alGuardar(`${c.nombre} → ${nombre.trim()} (${cambiados} ${cambiados === 1 ? "movimiento" : "movimientos"}).`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  async function borrar() {
    try {
      await borrarCategoria(c.nombre);
      alGuardar(`${c.nombre}: borrada.`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  return (
    <li className="item grupo">
      <div className="item-texto">
        <strong>{c.nombre}</strong>
        <span>{uso.join(" · ") || "sin uso"}</span>
      </div>
      {modo === "ver" && (
        <span className="item-acciones">
          <button type="button" className="boton-texto" onClick={() => setModo("renombrar")}>
            Renombrar
          </button>
          <button type="button" className="boton-texto peligroso" onClick={() => setModo("borrar")}>
            Borrar
          </button>
        </span>
      )}
      {modo === "renombrar" && (
        <form className="grupo-accion" onSubmit={renombrar}>
          <input autoFocus list="categorias-edicion" value={nombre} onChange={(e) => setNombre(e.target.value)} aria-label={`Nuevo nombre para ${c.nombre}`} />
          <button className="principal chico" disabled={!nombre.trim() || nombre.trim() === c.nombre}>
            Guardar
          </button>
          <button type="button" className="secundario chico" onClick={() => setModo("ver")}>
            Cancelar
          </button>
        </form>
      )}
      {modo === "borrar" && (
        <div className="grupo-accion confirmar-borrado">
          <span className="nota">¿Borrar {c.nombre}? Lo suyo vuelve a Gastos varios.</span>
          <button type="button" className="peligro chico" onClick={borrar}>
            Sí, borrar
          </button>
          <button type="button" className="secundario chico" onClick={() => setModo("ver")}>
            No
          </button>
        </div>
      )}
    </li>
  );
}

function FilaRegla({ regla: r, alGuardar, alFallar }: { regla: ReglaDetalle } & Avisar) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(r.texto);
  const [categoria, setCategoria] = useState(r.categoria);

  async function guardar(evento: FormEvent) {
    evento.preventDefault();
    try {
      await editarRegla(r.id, texto.trim(), categoria.trim());
      setEditando(false);
      alGuardar(`Regla "${texto.trim()}" → ${categoria.trim()}.`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  async function borrar() {
    try {
      await borrarRegla(r.id);
      alGuardar(`Regla "${r.texto}" borrada.`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  if (editando)
    return (
      <li className="item editor">
        <form className="editor-plan" onSubmit={guardar}>
          <label className="campo">
            <span>Texto que se busca</span>
            <input className="con-numeros" autoFocus value={texto} onChange={(e) => setTexto(e.target.value)} />
          </label>
          <label className="campo">
            <span>Categoría</span>
            <input list="categorias-edicion" value={categoria} onChange={(e) => setCategoria(e.target.value)} />
          </label>
          <div className="acciones-plan">
            <button className="principal chico">Guardar</button>
            <button type="button" className="secundario chico" onClick={() => setEditando(false)}>
              Cancelar
            </button>
            <button type="button" className="boton-texto peligroso" onClick={borrar}>
              Borrar regla
            </button>
          </div>
        </form>
      </li>
    );

  return (
    <li className="item">
      <div className="item-texto">
        <strong className="numeros">{r.texto}</strong>
        <span>→ {r.categoria}</span>
      </div>
      <button type="button" className="boton-texto" onClick={() => setEditando(true)}>
        Editar
      </button>
    </li>
  );
}
