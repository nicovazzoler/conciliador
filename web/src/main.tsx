import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource-variable/jetbrains-mono";
import { App } from "./App";
import "./estilos.css";
import "./pantallas.css";
import "./plan.css";
import "./inversiones.css";
import "./movimientos.css";
import "./graficos.css";
import "./gastos.css";

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
