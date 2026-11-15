// Las pantallas y la navegación. Cada pantalla tiene su dirección (#/gastos), así funciona el
// botón "atrás" del navegador. Para pocas pantallas no hace falta una librería de rutas.
import { useEffect, useState } from "react";
import { Cargar } from "./Cargar";
import { Categorias } from "./Categorias";
import { Gastos } from "./Gastos";
import { Importar } from "./Importar";
import { Inversiones } from "./Inversiones";
import { Movimientos } from "./Movimientos";
import { CalendarClock } from "lucide-react";
import { Navegacion, SECCIONES, type Ruta } from "./Navegacion";
import { Plan } from "./Plan";
import { Revisar } from "./Revisar";

// Plan, Movimientos y Categorías no están en el menú: se llega desde la barra, Gastos o Plan.
const EXTRAS = ["plan", "movimientos", "categorias"] as const;
type Pantalla = Ruta | (typeof EXTRAS)[number];

/** "#/movimientos/2026-10" → ["movimientos", "2026-10"]. */
function rutaDe(hash: string): [Pantalla, string | undefined] {
  const [nombre = "", parametro] = hash.replace(/^#\/?/, "").split("/");
  if (nombre === "mes") return ["gastos", undefined]; // La dirección vieja sigue funcionando.
  if ((EXTRAS as readonly string[]).includes(nombre)) return [nombre as Pantalla, parametro];
  return [SECCIONES.some((s) => s.ruta === nombre) ? (nombre as Ruta) : "gastos", undefined];
}

export function App() {
  const [[ruta, parametro], setRuta] = useState(rutaDe(window.location.hash));

  useEffect(() => {
    const alCambiar = () => setRuta(rutaDe(window.location.hash));
    window.addEventListener("hashchange", alCambiar);
    return () => window.removeEventListener("hashchange", alCambiar);
  }, []);

  return (
    <div className="app">
      <header className="barra">
        <a className="marca" href="#/gastos">
          Conciliador
        </a>
        <Navegacion actual={(EXTRAS as readonly string[]).includes(ruta) ? (ruta === "movimientos" ? "gastos" : undefined) : (ruta as Ruta)} />
        <a className="barra-plan" href="#/plan" aria-current={ruta === "plan" ? "page" : undefined}>
          <CalendarClock size={18} aria-hidden="true" />
          <span>Plan</span>
        </a>
      </header>
      {ruta === "gastos" && <Gastos />}
      {ruta === "cargar" && <Cargar />}
      {ruta === "revisar" && <Revisar />}
      {ruta === "importar" && <Importar />}
      {ruta === "plan" && <Plan />}
      {ruta === "movimientos" && <Movimientos key={parametro} mesInicial={parametro} />}
      {ruta === "categorias" && <Categorias />}
      {ruta === "inversiones" && <Inversiones />}
    </div>
  );
}
