// Gráficos hechos a mano en SVG: una línea en el tiempo, una rueda de partes y columnas apiladas.
// Marcas finas, grilla recesiva, una sola escala, y el valor exacto en el tooltip y en la tabla.
import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import { diaYMes, importe, nombreMes } from "./formato";

/** El ancho real del contenedor, para dibujar en píxeles y que el texto no se deforme. */
function useAncho<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [ancho, setAncho] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const observador = new ResizeObserver(([entrada]) => setAncho(entrada?.contentRect.width ?? 0));
    observador.observe(ref.current);
    return () => observador.disconnect();
  }, []);
  return [ref, ancho];
}

/** 12.345 → "12K"; 1.234 → "1.234": compacto solo cuando el eje lo necesita. */
export function compacto(centavos: number): string {
  const valor = centavos / 100;
  if (Math.abs(valor) >= 10_000) return `${(valor / 1000).toLocaleString("es-AR", { maximumFractionDigits: 0 })}K`;
  return valor.toLocaleString("es-AR", { maximumFractionDigits: 0 });
}

/** Ticks redondos entre 0 (o el mínimo) y el máximo. */
function ticks(minimo: number, maximo: number, cuantos = 4): number[] {
  const rango = Math.max(maximo - minimo, 1);
  const paso0 = rango / cuantos;
  const magnitud = 10 ** Math.floor(Math.log10(paso0));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * magnitud).find((p) => p >= paso0) ?? paso0;
  const desde = Math.floor(minimo / paso) * paso;
  const lista: number[] = [];
  for (let v = desde; v <= maximo + paso * 0.001; v += paso) lista.push(v);
  const ultimo = lista[lista.length - 1] ?? desde;
  if (ultimo < maximo) lista.push(ultimo + paso);
  return lista;
}

export type Serie = { nombre: string; color: string; valores: number[]; area?: boolean };

/** Líneas en el tiempo, una escala. El crosshair busca la fecha más cercana y el tooltip muestra todas las series. */
export function GraficoLinea({
  fechas,
  series,
  alto = 220,
  formato,
  etiqueta,
}: {
  fechas: string[];
  series: Serie[];
  alto?: number;
  formato: (centavos: number) => string;
  etiqueta: string;
}) {
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const [indice, setIndice] = useState<number | null>(null);
  const margen = { arriba: 12, derecha: 12, abajo: 26, izquierda: 44 };
  const todos = series.flatMap((s) => s.valores);
  const escala = ticks(Math.min(...todos) * 0.98, Math.max(...todos));
  const [minimo, maximo] = [escala[0] ?? 0, escala[escala.length - 1] ?? 1];
  const adentro = { ancho: Math.max(ancho - margen.izquierda - margen.derecha, 10), alto: alto - margen.arriba - margen.abajo };
  const x = (i: number) => margen.izquierda + (fechas.length > 1 ? (i / (fechas.length - 1)) * adentro.ancho : adentro.ancho / 2);
  const y = (v: number) => margen.arriba + adentro.alto - ((v - minimo) / (maximo - minimo || 1)) * adentro.alto;
  const linea = (valores: number[]) => valores.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");

  // Una marca por mes en el eje de abajo, la primera fecha de cada uno.
  const marcas = fechas
    .map((f, i) => ({ f, i }))
    .filter(({ f, i }) => i === 0 || f.slice(0, 7) !== fechas[i - 1]?.slice(0, 7))
    .filter((_, k, todas) => todas.length <= 7 || k % Math.ceil(todas.length / 6) === 0);

  function mover(evento: PointerEvent<SVGRectElement>) {
    const caja = evento.currentTarget.getBoundingClientRect();
    const relativo = (evento.clientX - caja.left) / caja.width;
    setIndice(Math.round(Math.min(Math.max(relativo, 0), 1) * (fechas.length - 1)));
  }

  const elegido = indice ?? null;
  return (
    <div className="grafico" ref={ref}>
      {ancho > 0 && (
        <svg width={ancho} height={alto} role="img" aria-label={etiqueta}>
          {escala.map((v) => (
            <g key={v}>
              <line className="grafico-grilla" x1={margen.izquierda} x2={ancho - margen.derecha} y1={y(v)} y2={y(v)} />
              <text className="grafico-eje" x={margen.izquierda - 8} y={y(v)} textAnchor="end" dominantBaseline="middle">
                {compacto(v)}
              </text>
            </g>
          ))}
          {marcas.map(({ f, i }) => (
            <text key={f} className="grafico-eje" x={x(i)} y={alto - 6} textAnchor={i === 0 ? "start" : "middle"}>
              {nombreMes(f.slice(0, 7)).slice(0, 3)}
            </text>
          ))}
          {series.map((s) =>
            s.area ? (
              <path
                key={`${s.nombre}-area`}
                d={`${linea(s.valores)}L${x(s.valores.length - 1)},${y(minimo)}L${x(0)},${y(minimo)}Z`}
                fill={s.color}
                opacity={0.1}
              />
            ) : null,
          )}
          {series.map((s) => (
            <path key={s.nombre} d={linea(s.valores)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          ))}
          {series.map((s) => (
            <circle key={`${s.nombre}-fin`} cx={x(s.valores.length - 1)} cy={y(s.valores[s.valores.length - 1] ?? 0)} r={4} fill={s.color} stroke="var(--superficie)" strokeWidth={2} />
          ))}
          {elegido !== null && (
            <>
              <line className="grafico-cruz" x1={x(elegido)} x2={x(elegido)} y1={margen.arriba} y2={margen.arriba + adentro.alto} />
              {series.map((s) => (
                <circle key={`${s.nombre}-punto`} cx={x(elegido)} cy={y(s.valores[elegido] ?? 0)} r={4} fill={s.color} stroke="var(--superficie)" strokeWidth={2} />
              ))}
            </>
          )}
          <rect
            x={margen.izquierda}
            y={margen.arriba}
            width={adentro.ancho}
            height={adentro.alto}
            fill="transparent"
            onPointerMove={mover}
            onPointerDown={mover}
            onPointerLeave={() => setIndice(null)}
          />
        </svg>
      )}
      {elegido !== null && (
        <div className="grafico-tooltip" style={{ left: Math.min(Math.max(x(elegido), 70), ancho - 70) }} role="status">
          <span className="grafico-tooltip-fecha">{diaYMes(fechas[elegido] ?? "")}</span>
          {series.map((s) => (
            <span key={s.nombre} className="grafico-tooltip-fila">
              <span className="clave-linea" style={{ background: s.color }} aria-hidden="true" />
              <strong>{formato(s.valores[elegido] ?? 0)}</strong>
              <span>{s.nombre}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export type Parte = { nombre: string; valor: number; color: string };

/** Una rueda: cada parte es un arco, con un corte del color del fondo entre una y otra. */
export function Rueda({
  partes,
  centro,
  resaltada,
  alResaltar,
  tamano = 168,
}: {
  partes: Parte[];
  centro: ReactNode;
  resaltada: string | null;
  alResaltar: (nombre: string | null) => void;
  tamano?: number;
}) {
  const total = partes.reduce((s, p) => s + p.valor, 0) || 1;
  const grosor = 16;
  const radio = (tamano - grosor) / 2 - 2;
  const circunferencia = 2 * Math.PI * radio;
  const corte = partes.length > 1 ? 3 : 0;
  let acumulado = 0;
  return (
    <div className="rueda" style={{ width: tamano, height: tamano }}>
      <svg width={tamano} height={tamano} aria-hidden="true">
        <g transform={`rotate(-90 ${tamano / 2} ${tamano / 2})`}>
          {partes.map((p) => {
            const largo = (p.valor / total) * circunferencia;
            const arco = (
              <circle
                key={p.nombre}
                cx={tamano / 2}
                cy={tamano / 2}
                r={radio}
                fill="none"
                stroke={p.color}
                strokeWidth={resaltada === p.nombre ? grosor + 4 : grosor}
                strokeDasharray={`${Math.max(largo - corte, 0.5)} ${circunferencia}`}
                strokeDashoffset={-acumulado}
                opacity={resaltada && resaltada !== p.nombre ? 0.35 : 1}
                onPointerEnter={() => alResaltar(p.nombre)}
                onPointerLeave={() => alResaltar(null)}
              />
            );
            acumulado += largo;
            return arco;
          })}
        </g>
      </svg>
      <div className="rueda-centro">{centro}</div>
    </div>
  );
}

export type Columna = { clave: string; etiqueta: string; partes: { nombre: string; valor: number; color: string }[] };

/** Columnas apiladas, una escala, con 2px del fondo entre segmentos. Tocar una columna la elige. */
export function Columnas({
  columnas,
  elegida,
  alElegir,
  formato,
  alto = 200,
  etiqueta,
}: {
  columnas: Columna[];
  elegida?: string;
  alElegir?: (clave: string) => void;
  formato: (centavos: number) => string;
  alto?: number;
  etiqueta: string;
}) {
  const [ref, ancho] = useAncho<HTMLDivElement>();
  const [encima, setEncima] = useState<string | null>(null);
  const margen = { arriba: 10, derecha: 4, abajo: 24, izquierda: 44 };
  const totales = columnas.map((c) => c.partes.reduce((s, p) => s + p.valor, 0));
  const escala = ticks(0, Math.max(...totales, 1));
  const maximo = escala[escala.length - 1] ?? 1;
  const adentro = { ancho: Math.max(ancho - margen.izquierda - margen.derecha, 10), alto: alto - margen.arriba - margen.abajo };
  const banda = adentro.ancho / Math.max(columnas.length, 1);
  const grueso = Math.min(24, banda * 0.6);
  const y = (v: number) => margen.arriba + adentro.alto - (v / maximo) * adentro.alto;
  const actual = columnas.find((c) => c.clave === encima);

  return (
    <div className="grafico" ref={ref}>
      {ancho > 0 && (
        <svg width={ancho} height={alto} role="img" aria-label={etiqueta}>
          {escala.map((v) => (
            <g key={v}>
              <line className="grafico-grilla" x1={margen.izquierda} x2={ancho - margen.derecha} y1={y(v)} y2={y(v)} />
              <text className="grafico-eje" x={margen.izquierda - 8} y={y(v)} textAnchor="end" dominantBaseline="middle">
                {compacto(v)}
              </text>
            </g>
          ))}
          {columnas.map((c, i) => {
            const centro = margen.izquierda + banda * i + banda / 2;
            let base = 0;
            const visibles = c.partes.filter((p) => p.valor > 0);
            return (
              <g
                key={c.clave}
                className={`columna${c.clave === elegida ? " elegida" : ""}`}
                onPointerEnter={() => setEncima(c.clave)}
                onPointerLeave={() => setEncima(null)}
                onClick={() => alElegir?.(c.clave)}
                style={{ cursor: alElegir ? "pointer" : undefined }}
              >
                <rect x={centro - banda / 2} y={margen.arriba} width={banda} height={adentro.alto} fill="transparent" />
                {visibles.map((p, k) => {
                  const desde = y(base);
                  base += p.valor;
                  const hasta = y(base);
                  const ultimo = k === visibles.length - 1;
                  const altura = Math.max(desde - hasta - (ultimo ? 0 : 2), 1);
                  return ultimo ? (
                    <path key={p.nombre} fill={p.color} d={barraRedondeada(centro - grueso / 2, hasta, grueso, altura)} />
                  ) : (
                    <rect key={p.nombre} x={centro - grueso / 2} y={hasta + 2} width={grueso} height={altura} fill={p.color} />
                  );
                })}
                {/* Con poco lugar, una etiqueta cada dos; la elegida siempre. */}
                {(banda >= 34 || i % 2 === (columnas.length - 1) % 2 || c.clave === elegida) && (
                  <text className={`grafico-eje${c.clave === elegida ? " grafico-eje-fuerte" : ""}`} x={centro} y={alto - 6} textAnchor="middle">
                    {c.etiqueta}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      )}
      {actual && (
        <div
          className="grafico-tooltip"
          style={{ left: Math.min(Math.max(margen.izquierda + banda * columnas.indexOf(actual) + banda / 2, 80), ancho - 80) }}
          role="status"
        >
          <span className="grafico-tooltip-fecha">{nombreMes(actual.clave)}</span>
          <span className="grafico-tooltip-fila">
            <strong>{formato(actual.partes.reduce((s, p) => s + p.valor, 0))}</strong>
            <span>en total</span>
          </span>
          {actual.partes
            .filter((p) => p.valor > 0)
            .map((p) => (
              <span key={p.nombre} className="grafico-tooltip-fila">
                <span className="clave-caja" style={{ background: p.color }} aria-hidden="true" />
                <strong>{formato(p.valor)}</strong>
                <span>{p.nombre}</span>
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

/** Rectángulo con 4px redondeados arriba y recto en la base. */
function barraRedondeada(x: number, y: number, ancho: number, alto: number): string {
  const r = Math.min(4, alto, ancho / 2);
  return `M${x},${y + alto}V${y + r}Q${x},${y} ${x + r},${y}H${x + ancho - r}Q${x + ancho},${y} ${x + ancho},${y + r}V${y + alto}Z`;
}

/** Una leyenda de claves: línea para series de línea, caja para barras y partes. */
export function Leyenda({ items, forma }: { items: { nombre: string; color: string }[]; forma: "linea" | "caja" }) {
  return (
    <ul className="grafico-leyenda">
      {items.map((i) => (
        <li key={i.nombre}>
          <span className={forma === "linea" ? "clave-linea" : "clave-caja"} style={{ background: i.color }} aria-hidden="true" />
          {i.nombre}
        </li>
      ))}
    </ul>
  );
}

/** Para escribir montos en el tooltip: U$D con el formato de siempre. */
export function enDolares(centavos: number): string {
  return `U$D ${importe(centavos)}`;
}

/** Agrupa una serie diaria por mes: el último valor de cada uno, para la tabla. */
export function porMes<T extends { fecha: string }>(puntos: T[]): T[] {
  const meses = new Map<string, T>();
  for (const p of puntos) meses.set(p.fecha.slice(0, 7), p);
  return [...meses.values()];
}
