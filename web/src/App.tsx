// Las pantallas y la barra de abajo. Cada pantalla tiene su dirección (#/cargar), así funciona
// el botón "atrás" del navegador. Para pocas pantallas no hace falta una librería de rutas.
import { useEffect, useState } from "react";
import { Cargar } from "./Cargar";
import { Mes } from "./Mes";

const PANTALLAS = {
  mes: { titulo: "Mes", componente: Mes },
  cargar: { titulo: "Cargar", componente: Cargar },
} as const;

type Pantalla = keyof typeof PANTALLAS;

function pantallaDe(hash: string): Pantalla {
  const nombre = hash.replace(/^#\/?/, "");
  return nombre in PANTALLAS ? (nombre as Pantalla) : "mes";
}

export function App() {
  const [pantalla, setPantalla] = useState(pantallaDe(window.location.hash));

  useEffect(() => {
    const alCambiar = () => setPantalla(pantallaDe(window.location.hash));
    window.addEventListener("hashchange", alCambiar);
    return () => window.removeEventListener("hashchange", alCambiar);
  }, []);

  const Actual = PANTALLAS[pantalla].componente;
  return (
    <>
      <Actual />
      <nav className="barra-abajo">
        {(Object.keys(PANTALLAS) as Pantalla[]).map((nombre) => (
          <a key={nombre} href={`#/${nombre}`} aria-current={nombre === pantalla ? "page" : undefined}>
            {PANTALLAS[nombre].titulo}
          </a>
        ))}
      </nav>
    </>
  );
}
