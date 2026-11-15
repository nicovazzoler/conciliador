// Las mismas cinco secciones, en el mismo orden, en el celular (abajo, flotante) y en la computadora (arriba).
import { ChartLine, FileUp, ListChecks, Plus, ReceiptText, type LucideIcon } from "lucide-react";

export const SECCIONES = [
  { ruta: "gastos", titulo: "Gastos", icono: ReceiptText },
  { ruta: "revisar", titulo: "Revisar", icono: ListChecks },
  { ruta: "cargar", titulo: "Cargar", icono: Plus },
  { ruta: "importar", titulo: "Importar", icono: FileUp },
  { ruta: "inversiones", titulo: "Inversiones", icono: ChartLine },
] as const satisfies readonly { ruta: string; titulo: string; icono: LucideIcon }[];

export type Ruta = (typeof SECCIONES)[number]["ruta"];

export function Navegacion({ actual }: { actual: Ruta }) {
  return (
    <nav className="navegacion" aria-label="Secciones">
      {SECCIONES.map(({ ruta, titulo, icono: Icono }) => (
        <a
          key={ruta}
          href={`#/${ruta}`}
          className={ruta === "cargar" ? "nav-item nav-cargar" : "nav-item"}
          aria-current={ruta === actual ? "page" : undefined}
        >
          <Icono aria-hidden="true" size={ruta === "cargar" ? 22 : 18} strokeWidth={2} />
          <span>{titulo}</span>
        </a>
      ))}
    </nav>
  );
}
