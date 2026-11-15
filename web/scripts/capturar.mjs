// Saca capturas de la app en celular y computadora, para revisar el diseño sin abrir un navegador.
// Uso: node scripts/capturar.mjs <url base> <carpeta de salida> [ruta[:texto del botón a tocar] ...]
// Ejemplo: node scripts/capturar.mjs http://127.0.0.1:8765 ../.impeccable/review gastos inversiones:Trading
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const [base = "http://127.0.0.1:8765", salida = "capturas", ...rutas] = process.argv.slice(2);
const TAMANIOS = { celular: { width: 390, height: 844 }, computadora: { width: 1440, height: 900 } };

await mkdir(salida, { recursive: true });
const navegador = await chromium.launch();
for (const pedido of rutas.length ? rutas : ["gastos"]) {
  const [ruta, boton] = pedido.split(":");
  for (const [nombre, viewport] of Object.entries(TAMANIOS)) {
    const pagina = await navegador.newPage({ viewport, deviceScaleFactor: 2, colorScheme: "dark" });
    await pagina.goto(`${base}/#/${ruta}`, { waitUntil: "networkidle" });
    if (boton) {
      await pagina.getByRole("radio", { name: boton }).click();
      await pagina.waitForLoadState("networkidle");
      await pagina.waitForTimeout(400); // Que termine la transición del botón.
    }
    await pagina.evaluate(() => document.fonts.ready);
    const archivo = `${salida}/${ruta.replaceAll("/", "-")}${boton ? `-${boton.toLowerCase()}` : ""}-${nombre}.png`;
    await pagina.screenshot({ path: archivo, fullPage: true });
    console.log(archivo);
    await pagina.close();
  }
}
await navegador.close();
