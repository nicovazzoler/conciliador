// Importar: soltar los PDF (o el plan.csv) y ver qué entró, archivo por archivo.
import { FileUp } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { importarArchivos, type Importacion } from "./api";
import { Comprobante, Renglon } from "./comprobante";
import { leerInforme } from "./informes";

export function Importar() {
  const [resultado, setResultado] = useState<Importacion | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [encima, setEncima] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement>(null);

  async function subir(lista: FileList | null) {
    const archivos = Array.from(lista ?? []);
    if (archivos.length === 0) return;
    setSubiendo(true);
    setError(null);
    try {
      setResultado(await importarArchivos(archivos));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubiendo(false);
      if (entrada.current) entrada.current.value = "";
    }
  }

  function soltar(evento: DragEvent) {
    evento.preventDefault();
    setEncima(false);
    void subir(evento.dataTransfer.files);
  }

  return (
    <main className="pagina">
      <h1 className="titulo-pagina">Importar</h1>
      <div className="paneles">
        <div className="panel">
          <label
            className={`zona-archivos${encima ? " encima" : ""}${subiendo ? " subiendo" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setEncima(true);
            }}
            onDragLeave={() => setEncima(false)}
            onDrop={soltar}
          >
            <span className="zona-icono" aria-hidden="true">
              <FileUp size={24} />
            </span>
            <strong>{subiendo ? "Importando…" : "Elegí o soltá tus PDF"}</strong>
            <span>Resúmenes de Mercado Pago, Comafi o Nación, o el plan.csv. Hasta 20 MB cada uno.</span>
            <input
              ref={entrada}
              type="file"
              multiple
              accept=".pdf,.csv"
              disabled={subiendo}
              onChange={(e) => void subir(e.target.files)}
            />
          </label>
          {error && <p className="mensaje mensaje-error">No se pudo importar: {error}</p>}

          {resultado && (
            <Comprobante
              titulo="Quedó"
              tinte="menta"
              pie={resultado.pendientes > 0 ? <a href="#/revisar">Ir a Revisar</a> : undefined}
            >
              <ul className="renglones">
                <Renglon
                  concepto="Gastos grandes para revisar"
                  monto={resultado.pendientes}
                  tono={resultado.pendientes > 0 ? "ojo" : "bien"}
                  forma="lleno"
                />
                <Renglon
                  concepto="Movimientos sin cotización"
                  monto={resultado.sin_usd}
                  tono={resultado.sin_usd > 0 ? "ojo" : "bien"}
                  forma="lleno"
                />
              </ul>
              {resultado.aviso_cotizaciones && <p className="nota">{resultado.aviso_cotizaciones}</p>}
            </Comprobante>
          )}
        </div>

        <Comprobante titulo="Lo que entró" className="panel">
          {!resultado ? (
            <p className="vacio">
              Cada archivo aparece acá con lo que pasó: si trajo movimientos nuevos, si ya estaba importado o si no se
              pudo leer. Importar dos veces el mismo PDF no duplica nada.
            </p>
          ) : (
            <ul className="lista">
              {resultado.informes.map((informe) => {
                const lectura = leerInforme(informe);
                return (
                  <li key={informe.archivo} className="item">
                    <div className="item-texto">
                      <strong className="numeros">{informe.archivo}</strong>
                      <span>{lectura.detalle}</span>
                      {[...informe.errores.slice(informe.reconocido ? 0 : 1), ...informe.problemas].map((aviso) => (
                        <span key={aviso} className="tono-ojo">
                          {aviso}
                        </span>
                      ))}
                    </div>
                    <span className={`sello tono-${lectura.tono}`}>{lectura.sello}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Comprobante>
      </div>
    </main>
  );
}
