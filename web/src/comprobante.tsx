// Las piezas del sistema visual: el comprobante, su renglón con puntos guía y el sello.
import type { ReactNode } from "react";
import type { Forma, Tono } from "./atender";

type Tinte = "violeta" | "menta" | "ninguno";

/** Un bloque que se lee como comprobante. Con `pie`, cierra con un borde troquelado. */
export function Comprobante({
  titulo,
  tinte = "ninguno",
  pie,
  children,
  className = "",
}: {
  titulo?: ReactNode;
  tinte?: Tinte;
  pie?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`comprobante tinte-${tinte} ${className}`}>
      {titulo && <h2 className="comprobante-titulo">{titulo}</h2>}
      <div className="comprobante-cuerpo">{children}</div>
      {pie && <footer className="comprobante-pie">{pie}</footer>}
    </section>
  );
}

/** Concepto, puntos guía y monto. El filete marca el estado también por su forma, no solo el color. */
export function Renglon({
  concepto,
  monto,
  sello,
  tono = "neutro",
  forma,
  fuerte = false,
}: {
  concepto: ReactNode;
  monto: ReactNode;
  sello?: string;
  tono?: Tono | "bien";
  forma?: Forma;
  fuerte?: boolean;
}) {
  return (
    <li className={`renglon${forma ? "" : " sin-filete"}${fuerte ? " renglon-fuerte" : ""}`}>
      {forma && <span className={`filete filete-${forma} tono-${tono}`} aria-hidden="true" />}
      <span className="renglon-concepto">{concepto}</span>
      <span className="renglon-guia" aria-hidden="true" />
      <span className="renglon-monto">{monto}</span>
      {sello && <Sello tono={tono}>{sello}</Sello>}
    </li>
  );
}

export function Sello({ tono, children }: { tono: Tono | "bien"; children: ReactNode }) {
  return <span className={`sello tono-${tono}`}>{children}</span>;
}
