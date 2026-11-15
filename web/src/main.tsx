import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Mes } from "./Mes";
import "./estilos.css";

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <Mes />
  </StrictMode>,
);
