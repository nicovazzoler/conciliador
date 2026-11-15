// Revisar: los gastos grandes sin categoría y "Gastos varios" agrupado, para categorizar con un toque.
import { useCallback, useEffect, useState } from "react";
import {
  crearRegla,
  resolverPendiente,
  traerCategorias,
  traerPendientes,
  traerVarios,
  type GrupoVarios,
  type Pendiente,
} from "./api";
import { Comprobante } from "./comprobante";
import { Chip, Segmentado } from "./controles";
import { diaYMes, importe, plata } from "./formato";

type Vista = "pendientes" | "varios";
type Mensaje = { tipo: "bien" | "error"; texto: string } | null;

export function Revisar() {
  const [vista, setVista] = useState<Vista>("pendientes");
  const [pendientes, setPendientes] = useState<Pendiente[] | null>(null);
  const [grupos, setGrupos] = useState<GrupoVarios[] | null>(null);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [mensaje, setMensaje] = useState<Mensaje>(null);

  const recargar = useCallback(() => {
    // Cada pedido por su lado: si uno falla, lo demás se muestra igual.
    const fallo = (que: string) => (error: Error) => setMensaje({ tipo: "error", texto: `No se pudieron traer ${que}: ${error.message}` });
    traerPendientes().then(setPendientes).catch(fallo("los pendientes"));
    traerVarios().then(setGrupos).catch(fallo("los grupos"));
    // Las categorías solo ayudan a elegir: sin ellas se escribe a mano.
    traerCategorias().then(setCategorias).catch(() => setCategorias([]));
  }, []);
  useEffect(recargar, [recargar]);

  const avisar = {
    alResolver: (texto: string) => {
      setMensaje({ tipo: "bien", texto });
      recargar();
    },
    alFallar: (texto: string) => setMensaje({ tipo: "error", texto }),
  };

  return (
    <main className="pagina">
      <h1 className="titulo-pagina">Revisar</h1>
      <div className="solo-celular">
        <Segmentado
          etiqueta="Qué revisar"
          opciones={[
            ["pendientes", `Pendientes · ${pendientes?.length ?? "…"}`],
            ["varios", `Gastos varios · ${grupos?.length ?? "…"}`],
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

      <div className="paneles">
        <div className={vista === "pendientes" ? "panel" : "panel oculto-celular"}>
          {pendientes === null ? (
            <p className="nota">Cargando…</p>
          ) : pendientes.length === 0 ? (
            <Comprobante titulo="Pendientes">
              <p className="vacio">No hay gastos grandes sin categoría.</p>
            </Comprobante>
          ) : (
            <TarjetaPendiente
              key={pendientes[0]!.id}
              pendiente={pendientes[0]!}
              total={pendientes.length}
              categorias={categorias}
              {...avisar}
            />
          )}
        </div>

        <Comprobante
          titulo={
            <>
              Gastos varios por grupo <span className="contador">de mayor a menor</span>
            </>
          }
          className={vista === "varios" ? "panel" : "panel oculto-celular"}
        >
          {grupos === null ? (
            <p className="nota">Cargando…</p>
          ) : grupos.length === 0 ? (
            <p className="vacio">Nada en Gastos varios: todo tiene categoría.</p>
          ) : (
            <ul className="lista">
              {grupos.map((grupo) => (
                <FilaGrupo key={`${grupo.texto}-${grupo.moneda}`} grupo={grupo} categorias={categorias} {...avisar} />
              ))}
            </ul>
          )}
        </Comprobante>
      </div>
      <datalist id="categorias-revisar">
        {categorias.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
    </main>
  );
}

type Avisar = { alResolver: (texto: string) => void; alFallar: (texto: string) => void };

function TarjetaPendiente({
  pendiente,
  total,
  categorias,
  alResolver,
  alFallar,
}: { pendiente: Pendiente; total: number; categorias: string[] } & Avisar) {
  const [categoria, setCategoria] = useState("");
  const [regla, setRegla] = useState(pendiente.sugerido);
  const [enviando, setEnviando] = useState(false);

  async function resolver(resolucion: { categoria?: string; regla?: string | null; cambio?: boolean }, texto: string) {
    setEnviando(true);
    try {
      await resolverPendiente(pendiente.id, resolucion);
      alResolver(texto);
    } catch (error) {
      alFallar((error as Error).message);
      setEnviando(false);
    }
  }

  const elegida = categoria.trim();
  return (
    <Comprobante
      tinte="violeta"
      titulo={
        <>
          Pendiente <span className="contador">1 de {total}</span>
        </>
      }
      pie={
        <button
          type="button"
          className="boton-texto"
          disabled={enviando}
          onClick={() => resolver({ cambio: true }, "Marcado como cambio: no suma como gasto.")}
        >
          No es un gasto: es un cambio (USDT, efectivo)
        </button>
      }
    >
      <p className="pendiente-meta">
        {diaYMes(pendiente.fecha)} · {pendiente.moneda}
      </p>
      <p className="pendiente-descripcion">{pendiente.descripcion}</p>
      <p className="monto-grande">
        <span className="moneda">{pendiente.moneda === "USD" ? "U$D" : "$"}</span>
        <span>{importe(pendiente.monto_centavos)}</span>
      </p>

      <div className="campo">
        <span>¿En qué categoría va?</span>
        <div className="chips">
          {categorias.slice(0, 8).map((c) => (
            <Chip key={c} activo={c === elegida} alTocar={() => setCategoria(c)}>
              {c}
            </Chip>
          ))}
        </div>
        <input
          list="categorias-revisar"
          value={categoria}
          onChange={(e) => setCategoria(e.target.value)}
          placeholder={categorias.length ? "O escribí una nueva" : "Escribí una categoría"}
          aria-label="Categoría"
        />
      </div>
      <label className="campo-regla">
        Regla para lo que venga (vacía: solo este gasto)
        <input value={regla} onChange={(e) => setRegla(e.target.value)} />
      </label>
      <button
        className="principal"
        disabled={!elegida || enviando}
        onClick={() => resolver({ categoria: elegida, regla: regla.trim() || null }, `Guardado en ${elegida}.`)}
      >
        {enviando ? "Guardando…" : elegida ? `Guardar en ${elegida}` : "Elegí una categoría"}
      </button>
    </Comprobante>
  );
}

function FilaGrupo({ grupo, alResolver, alFallar }: { grupo: GrupoVarios; categorias: string[] } & Avisar) {
  const [abierto, setAbierto] = useState(false);
  const [categoria, setCategoria] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function crear() {
    setEnviando(true);
    try {
      const cuantos = await crearRegla(grupo.texto, categoria.trim());
      alResolver(`Regla "${grupo.texto}" → ${categoria.trim()}: ${cuantos === 1 ? "1 movimiento" : `${cuantos} movimientos`}.`);
    } catch (error) {
      alFallar((error as Error).message);
      setEnviando(false);
    }
  }

  return (
    <li className={abierto ? "item grupo abierto" : "item grupo"}>
      <div className="item-texto">
        <strong>{grupo.texto}</strong>
        <span>
          {grupo.movimientos === 1 ? "1 movimiento" : `${grupo.movimientos} movimientos`}
          {grupo.plan_concepto && ` · del plan: ${grupo.plan_concepto}`}
        </span>
      </div>
      <span className="item-monto">{plata(grupo.total_centavos, grupo.moneda)}</span>
      {!abierto && (
        <button type="button" className="boton-texto" onClick={() => setAbierto(true)}>
          Categorizar
        </button>
      )}
      {abierto && (
      <form
        className="grupo-accion"
        onSubmit={(evento) => {
          evento.preventDefault();
          if (categoria.trim()) void crear();
        }}
      >
        <input
          autoFocus
          list="categorias-revisar"
          value={categoria}
          onChange={(e) => setCategoria(e.target.value)}
          placeholder={`Categoría para "${grupo.texto}"`}
          aria-label={`Categoría para ${grupo.texto}`}
        />
        <button className="principal chico" disabled={!categoria.trim() || enviando}>
          Crear regla
        </button>
        <button type="button" className="secundario chico" onClick={() => setAbierto(false)}>
          Cancelar
        </button>
      </form>
      )}
    </li>
  );
}
