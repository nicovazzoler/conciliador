// Controles compartidos por los formularios: opciones segmentadas y chips.
import type { ReactNode } from "react";

/** Un grupo de opciones excluyentes, como pestañas o "Pesos / Dólares". */
export function Segmentado<T extends string>({
  etiqueta,
  opciones,
  valor,
  alCambiar,
}: {
  etiqueta: string;
  opciones: readonly (readonly [T, ReactNode])[];
  valor: T;
  alCambiar: (valor: T) => void;
}) {
  return (
    <div className="segmentado" role="radiogroup" aria-label={etiqueta}>
      {opciones.map(([clave, texto]) => (
        <button
          key={clave}
          type="button"
          role="radio"
          aria-checked={clave === valor}
          className={clave === valor ? "segmento activo" : "segmento"}
          onClick={() => alCambiar(clave)}
        >
          {texto}
        </button>
      ))}
    </div>
  );
}

export function Chip({
  activo = false,
  alTocar,
  children,
}: {
  activo?: boolean;
  alTocar: () => void;
  children: ReactNode;
}) {
  return (
    <button type="button" className={activo ? "chip activo" : "chip"} aria-pressed={activo} onClick={alTocar}>
      {children}
    </button>
  );
}
