// Movimientos: todo lo del mes, por día, con filtros. Tocar uno deja cambiarle la categoría.
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { elegirCategoria, traerCategorias, traerMovimientos, type MovimientoDelMes, type MovimientosDelMes } from "./api";
import { Comprobante } from "./comprobante";
import { Segmentado } from "./controles";
import { hoy, importe, mesActual, moverMes, nombreMes, plata } from "./formato";
import { nombreFuente, siglaFuente } from "./fuentes";

type Filtro = "todo" | "gastos" | "ingresos" | "otros";
type Mensaje = { tipo: "bien" | "error"; texto: string } | null;

const GASTOS = new Set(["consumo", "cuota", "impuesto"]);
const TIPOS: Record<string, string> = {
  ingreso: "ingreso",
  transferencia_propia: "entre tus cuentas",
  pago: "pago del resumen",
  pago_tarjeta: "aviso de pago",
  cambio: "cambio",
  devolucion: "devolución",
  percepcion: "percepción",
  sin_clasificar: "sin clasificar",
};

/** "dia:2026-10-05", "plan:Internet", "categoria:Salud" o "buscar:texto", desde Gastos. */
function leerFiltro(filtro?: string): { dia?: string; plan?: string; categoria?: string; buscar?: string } {
  const [clave, ...resto] = (filtro ?? "").split(":");
  const valor = resto.join(":");
  if (!valor) return {};
  return clave === "dia" || clave === "plan" || clave === "categoria" || clave === "buscar" ? { [clave]: valor } : {};
}

export function Movimientos({ mesInicial, filtro: filtroDeLaDireccion }: { mesInicial?: string; filtro?: string }) {
  const inicial = leerFiltro(filtroDeLaDireccion);
  const [dia, setDia] = useState(inicial.dia ?? "");
  const [plan, setPlan] = useState(inicial.plan ?? "");
  const [mes, setMes] = useState(mesInicial ?? mesActual());
  const [datos, setDatos] = useState<MovimientosDelMes | null>(null);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [filtro, setFiltro] = useState<Filtro>("todo");
  const [fuente, setFuente] = useState("");
  const [categoria, setCategoria] = useState(inicial.categoria ?? "");
  const [busqueda, setBusqueda] = useState(inicial.buscar ?? "");
  const [abierto, setAbierto] = useState<number | null>(null);
  const [mensaje, setMensaje] = useState<Mensaje>(null);

  const recargar = useCallback(() => {
    const control = new AbortController();
    traerMovimientos(mes, { signal: control.signal })
      .then(setDatos)
      .catch((error: Error) => {
        if (error.name !== "AbortError") setMensaje({ tipo: "error", texto: error.message });
      });
    traerCategorias().then(setCategorias).catch(() => setCategorias([]));
    return () => control.abort();
  }, [mes]);
  useEffect(recargar, [recargar]);

  const visibles = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return (datos?.movimientos ?? []).filter(
      (m) =>
        (filtro === "todo" ||
          (filtro === "gastos" && GASTOS.has(m.tipo)) ||
          (filtro === "ingresos" && m.tipo === "ingreso") ||
          (filtro === "otros" && !GASTOS.has(m.tipo) && m.tipo !== "ingreso")) &&
        (!fuente || m.fuente === fuente) &&
        (!categoria || m.categoria === categoria) &&
        (!dia || m.fecha === dia) &&
        (!plan || m.plan_concepto === plan) &&
        (!texto || m.descripcion.toLowerCase().includes(texto)),
    );
  }, [datos, filtro, fuente, categoria, busqueda, dia, plan]);

  const porDia = useMemo(() => {
    const dias = new Map<string, MovimientoDelMes[]>();
    for (const m of visibles) dias.set(m.fecha, [...(dias.get(m.fecha) ?? []), m]);
    return [...dias.entries()];
  }, [visibles]);

  const fuentes = [...new Set((datos?.movimientos ?? []).map((m) => m.fuente))];
  const categoriasDelMes = [...new Set((datos?.movimientos ?? []).map((m) => m.categoria).filter(Boolean))] as string[];

  return (
    <main className="pagina">
      <h1 className="titulo-pagina">Movimientos</h1>
      <header className="mes">
        <button className="redondo" onClick={() => setMes(moverMes(mes, -1))} aria-label="Mes anterior">
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
        <h2 className="mes-nombre">{nombreMes(mes)}</h2>
        <button className="redondo" onClick={() => setMes(moverMes(mes, 1))} disabled={mes >= mesActual()} aria-label="Mes siguiente">
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </header>

      {datos && (
        <div className="entro-salio">
          <Comprobante tinte="menta" titulo={<>Entró <span className="punto punto-menta" aria-hidden="true" /></>}>
            <p className="cifra">{plata(datos.entro_centavos)}</p>
          </Comprobante>
          <Comprobante tinte="violeta" titulo={<>Salió <span className="punto punto-rojo" aria-hidden="true" /></>}>
            <p className="cifra">{plata(datos.salio_centavos)}</p>
          </Comprobante>
        </div>
      )}

      <div className="filtros">
        <label className="buscador">
          <Search size={16} aria-hidden="true" />
          <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar un comercio…" aria-label="Buscar" />
        </label>
        <Segmentado
          etiqueta="Tipo"
          opciones={[
            ["todo", "Todo"],
            ["gastos", "Gastos"],
            ["ingresos", "Ingresos"],
            ["otros", "Otros"],
          ]}
          valor={filtro}
          alCambiar={setFiltro}
        />
        <div className="dos-columnas">
          <select value={fuente} onChange={(e) => setFuente(e.target.value)} aria-label="Fuente">
            <option value="">Todas las fuentes</option>
            {fuentes.map((f) => (
              <option key={f} value={f}>
                {nombreFuente(f)}
              </option>
            ))}
          </select>
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)} aria-label="Categoría">
            <option value="">Todas las categorías</option>
            {categoriasDelMes.sort().map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      {(dia || plan) && (
        <p className="filtro-activo">
          {dia ? `Solo el ${nombreDia(dia).toLowerCase()}` : `Solo lo de ${plan}, del plan`}
          <button
            type="button"
            className="boton-texto"
            onClick={() => {
              setDia("");
              setPlan("");
            }}
          >
            Ver todo el mes
          </button>
        </p>
      )}
      {mensaje && (
        <p className={`mensaje mensaje-${mensaje.tipo}`} role="status">
          {mensaje.texto}
        </p>
      )}
      <datalist id="categorias-movimientos">
        {categorias.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>

      {datos === null ? (
        <p className="nota">Cargando…</p>
      ) : porDia.length === 0 ? (
        <p className="vacio">{datos.movimientos.length ? "Nada coincide con los filtros." : `Sin movimientos en ${nombreMes(mes)}.`}</p>
      ) : (
        porDia.map(([fecha, movimientos]) => (
          <section key={fecha} className="dia">
            <h3 className="dia-titulo">{nombreDia(fecha)}</h3>
            <ul className="lista">
              {movimientos.map((m) => (
                <FilaMovimiento
                  key={m.id}
                  movimiento={m}
                  abierto={abierto === m.id}
                  alTocar={() => setAbierto(abierto === m.id ? null : m.id)}
                  alGuardar={(texto) => {
                    setAbierto(null);
                    setMensaje({ tipo: "bien", texto });
                    recargar();
                  }}
                  alFallar={(texto) => setMensaje({ tipo: "error", texto })}
                />
              ))}
            </ul>
          </section>
        ))
      )}
    </main>
  );
}

function FilaMovimiento({
  movimiento: m,
  abierto,
  alTocar,
  alGuardar,
  alFallar,
}: {
  movimiento: MovimientoDelMes;
  abierto: boolean;
  alTocar: () => void;
  alGuardar: (texto: string) => void;
  alFallar: (texto: string) => void;
}) {
  const [categoria, setCategoria] = useState(m.categoria_manual ? (m.categoria ?? "") : "");
  const esGasto = GASTOS.has(m.tipo);
  const detalle = [
    nombreFuente(m.fuente, m.medio),
    esGasto ? m.categoria : TIPOS[m.tipo] ?? m.tipo,
    m.cuota ? `cuota ${m.cuota}` : null,
    esGasto && m.fuente.startsWith("tarjeta_") ? "mes vencido" : null,
    m.categoria_manual ? "a mano" : null,
  ].filter(Boolean);

  async function guardar(evento: FormEvent, nueva: string | null) {
    evento.preventDefault();
    try {
      await elegirCategoria(m.id, nueva);
      alGuardar(nueva ? `${m.descripcion}: ahora en ${nueva}.` : `${m.descripcion}: vuelve a la categoría automática.`);
    } catch (error) {
      alFallar((error as Error).message);
    }
  }

  return (
    <li className={abierto ? "item movimiento abierto" : "item movimiento"}>
      <button type="button" className="movimiento-fila" onClick={alTocar} aria-expanded={abierto}>
        <span className={`iniciales marca-${m.fuente}`} title={nombreFuente(m.fuente)} aria-hidden="true">
          {siglaFuente(m.fuente)}
        </span>
        <span className="item-texto">
          <strong>{m.descripcion}</strong>
          <span>{detalle.join(" · ")}</span>
        </span>
        <span className={`monto-chip ${m.monto_centavos > 0 ? "tono-bien" : ""}`}>
          {m.monto_centavos > 0 ? "+" : "−"}
          {m.moneda === "USD" ? "U$D" : "$"} {importe(m.monto_centavos)}
        </span>
      </button>
      {abierto && (
        <div className="movimiento-detalle">
          {m.plan_concepto && <p className="nota">Del plan: {m.plan_concepto}.</p>}
          {esGasto ? (
            <form className="grupo-accion" onSubmit={(e) => guardar(e, categoria.trim() || null)}>
              <input
                autoFocus
                list="categorias-movimientos"
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
                placeholder={m.categoria ? `Ahora: ${m.categoria}` : "Categoría"}
                aria-label="Categoría"
              />
              <button className="principal chico" disabled={!categoria.trim()}>
                Guardar
              </button>
              {m.categoria_manual && (
                <button type="button" className="secundario chico" onClick={(e) => guardar(e as unknown as FormEvent, null)}>
                  Automática
                </button>
              )}
            </form>
          ) : (
            <p className="nota">No es un gasto ({TIPOS[m.tipo] ?? m.tipo}): no suma en Gastos ni lleva categoría.</p>
          )}
        </div>
      )}
    </li>
  );
}

function nombreDia(fecha: string): string {
  const actual = hoy();
  if (fecha === actual) return "Hoy";
  const ayer = new Date(`${actual}T12:00:00`);
  ayer.setDate(ayer.getDate() - 1);
  if (fecha === hoy(ayer)) return "Ayer";
  const texto = new Date(`${fecha}T12:00:00`).toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long" });
  return texto.charAt(0).toUpperCase() + texto.slice(1); // "Miércoles, 21 de octubre": solo la primera.
}
