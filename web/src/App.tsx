// Las pantallas y la navegación. Cada pantalla tiene su dirección (#/gastos), así funciona el
// botón "atrás" del navegador. Para pocas pantallas no hace falta una librería de rutas.
import { useEffect, useState } from "react";
import { Cargar } from "./Cargar";
import { Gastos } from "./Gastos";
import { Importar } from "./Importar";
import { Navegacion, SECCIONES, type Ruta } from "./Navegacion";
import { Revisar } from "./Revisar";

function rutaDe(hash: string): Ruta {
  const nombre = hash.replace(/^#\/?/, "");
  if (nombre === "mes") return "gastos"; // La dirección vieja sigue funcionando.
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
        <Navegacion actual={ruta} />
      </header>
      {ruta === "gastos" && <Gastos />}
      {ruta === "cargar" && <Cargar />}
      {ruta === "revisar" && <Revisar />}
      {ruta === "importar" && <Importar />}
      {ruta === "inversiones" && <EnConstruccion titulo="Inversiones" detalle="Portafolio y Trading." />}
    </div>
  );
}

function EnConstruccion({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <main className="pagina">
      <h1 className="titulo-pagina">{titulo}</h1>
      <p className="vacio">
        {detalle} Esta pantalla llega en el próximo paso; mientras tanto, la API ya la tiene y se puede usar desde la
        terminal.
      </p>
    </main>
  );
}
