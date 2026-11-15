// Las pantallas y la navegación. Cada pantalla tiene su dirección (#/gastos), así funciona el
// botón "atrás" del navegador. Para pocas pantallas no hace falta una librería de rutas.
import { useEffect, useState } from "react";
import { Cargar } from "./Cargar";
import { Gastos } from "./Gastos";
import { Importar } from "./Importar";
import { Inversiones } from "./Inversiones";
import { CalendarClock } from "lucide-react";
import { Navegacion, SECCIONES, type Ruta } from "./Navegacion";
import { Plan } from "./Plan";
import { Revisar } from "./Revisar";

// Plan no está en el menú de abajo: se usa poco y se llega desde la barra o desde Gastos.
type Pantalla = Ruta | "plan";

function rutaDe(hash: string): Pantalla {
  const nombre = hash.replace(/^#\/?/, "");
  if (nombre === "mes") return "gastos"; // La dirección vieja sigue funcionando.
  if (nombre === "plan") return "plan";
  return SECCIONES.some((s) => s.ruta === nombre) ? (nombre as Ruta) : "gastos";
}

export function App() {
  const [ruta, setRuta] = useState(rutaDe(window.location.hash));

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
        <Navegacion actual={ruta === "plan" ? undefined : ruta} />
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
      {ruta === "inversiones" && <Inversiones />}
    </div>
  );
}
