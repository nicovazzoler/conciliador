---
version: 1
slug: "web-src-app-tsx"
primary_target: "web/src/App.tsx"
related_targets: ["web/src/Mes.tsx","web/src/Cargar.tsx"]
---

# App Conciliador (web)

Scope: toda la app web: Mes, Cargar, Revisar, Importar, Portafolio y Trading. Mode: Operate.
Audience: el dueño de los datos, en el celular para cargar y mirar, en la computadora para importar y revisar; y quien mira la demo pública con datos inventados.
Task: ver qué requiere atención este mes, cargar rápido, seguir las posiciones.
Constraints: base pedida por el usuario y fija: fondo oscuro, verde lima como acento, navegación en píldora, tarjetas KPI. Montos `$ 1.234,56` / `U$D 88,24`. Portafolio y Trading sin API todavía: se muestran con datos de ejemplo, rotulados.

## Direction contract

THESIS: La app lee comprobantes, así que cada número se presenta como una línea de comprobante: concepto, puntos guía y monto alineado. Rechaza el dashboard de tarjetas sueltas con un número gigante y un porcentaje decorativo.

OWN-WORLD: Carbón casi negro con un leve tinte verde, superficies un paso más claras, lima como tinta de "conciliado". Grotesca de trabajo para el texto, monoespaciada tabular para cada monto. Bordes troquelados (perforado punteado) en el cierre de cada bloque. Sellos en mayúscula con borde de una línea.

STORY: Al abrir, se ve el total del mes y, debajo, solo lo que no cerró. Se entiende qué falta pagar o qué se cobró de más. Se toca una línea y se ve de dónde sale.

FIRST VIEWPORT: Arriba, la marca a la izquierda y la píldora de navegación (Mes, Cargar, Revisar, Importar, Portafolio, Trading); en el celular, la píldora baja al pie. Debajo, el mes con su selector. Luego la tira de comprobantes de totales: gastado en pesos, en USD, y portafolio, cada uno con su historia mínima. Después, el comprobante "A atender": líneas con sello. Acción principal: Cargar, siempre a un toque.

FORM: Comprobante, candidato 6 de 7 de la lista propia; seed:e8a5a62a49122952. Firma: la línea de comprobante con puntos guía y sello; el estado también se codifica en la forma del filete (lleno = cerrado, punteado = pendiente, tachado = anulado), aporte del rail de líneas de emisión. Escala tipográfica corta (dos tamaños de cuerpo, jerarquía por peso y mayúsculas), aporte del horario de una sola medida. Reacomodo por celdas enteras, aporte de la grilla de Crouwel.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
