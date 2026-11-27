# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **El dueño de los datos.** Una persona en Argentina que cobra en pesos, gasta con Mercado Pago y tarjetas de crédito, ahorra en dólares y opera cripto. Usa la app en su propia máquina, con sus datos reales, para saber a fin de mes en qué se le fue la plata, qué le cobraron de más y qué le falta pagar, y para seguir sus inversiones. La consulta tanto en la computadora como en el celular.
- **Quien mira la demo.** Reclutadores y entrevistadores técnicos que entran a una versión pública con datos inventados para evaluar el proyecto. Tienen pocos minutos y tienen que entender qué hace en el primer vistazo.

## Product Purpose

Cruzar lo que realmente se gastó contra lo planificado, en pesos y en USD al dólar oficial del día, y seguir en el mismo lugar las inversiones en cripto y su trading. El éxito es que, sin abrir una planilla, se vea qué requiere atención este mes: un fijo que no se debitó, una cuota que falta, un día que pasó el tope, un resumen sin pagar, o cuánto se gana o se pierde en cada posición.

## Positioning

No depende de conectarse al banco: lee los resúmenes en PDF que el usuario ya descarga (Mercado Pago, Comafi, Banco Nación), los verifica al centavo contra sus propios totales y nunca duplica un movimiento, porque los reconoce por número de operación. Todo corre en la máquina del usuario: los datos financieros reales no salen de ahí.

## Operating Context

- Cada mes se descargan los resúmenes en PDF y se importan; lo que no viene en un PDF (efectivo, débitos de cuentas que no se importan, cuotas en tarjetas de familiares, pagos de resúmenes) se carga a mano.
- Un plan define los gastos fijos y las cuotas esperadas. Se edita desde la app; `plan.csv` sigue sirviendo para importarlo o exportarlo.
- Las compras con tarjeta cuentan en el mes en que vence el resumen (mes vencido). Mercado Pago y lo cargado a mano, en el mes en que salió la plata.
- Los gastos grandes sin anticipar piden confirmación y categoría.
- Las operaciones de inversión son muchas por mes: se cargan desde capturas de pantalla que lee Claude, y la persona revisa lo leído antes de guardar.
- Uso típico: en el celular para cargar un gasto o mirar el mes; en la computadora para importar y revisar.

## Capabilities and Constraints

- **Gastos (construido):** reporte del mes con meses anteriores: totales en pesos y en USD, fijos (sin datos, sin debitar, más caro, más barato, bien), cuotas (sin datos, falta, sin plan, repetida, otro número, bien), días que superan el tope diario de $ 200.000, resúmenes de tarjeta (nada que pagar, impago, parcial, avisado, confirmado), gasto por categoría y qué hacer con cada aviso. Mes a mes partido por fuente, e historial de cada categoría y de cada fijo.
- **Cargar, Revisar e Importar (construido):** carga y borrado de gastos y pagos de tarjeta; revisión de pendientes y categorización por grupos con reglas; importación de PDFs.
- **Movimientos (construido):** todo lo que entró y salió, con buscador y filtros por fuente y categoría, para corregir la categoría de cualquiera. Categorías y reglas se editan desde la app.
- **Plan (construido):** fijos y cuotas editables desde la app.
- **Inversiones (construido):** posiciones con precio promedio, ganancia **realizada** y **no realizada**, la cartera día por día, stop loss y take profit, y acciones en otras monedas convertidas con el cambio del día. Opera sobre todo en Quantfury (acciones y cripto, en USD) y algo en Binance; las operaciones se cargan desde capturas que lee Claude o a mano.
- **Precios:** cripto desde Binance (API pública) y acciones desde Yahoo Finance (sin API oficial: se usa el endpoint de sus gráficos). Sin precio, no se inventa uno.
- **Sin cotización:** lo que no tiene dólar del día se muestra "sin datos" y se dice cuántos movimientos faltan; nunca U$D 0,00.
- **Por construir:** un chat con un agente propio para dictarle un gasto o pasarle cualquier cosa (una captura, un PDF, una tenencia) y que la cargue, con la confirmación de lo importante en la API y no en el modelo.
- **Por decidir:** si además de las capturas hace falta importar el historial exportado de Quantfury y de Binance, y en qué formato.
- Montos en formato argentino: `$ 1.234,56` y `U$D 88,24`. Toda la interfaz en español rioplatense.
- Backend FastAPI con esquemas que generan los tipos de TypeScript; front Vite + React + TypeScript.
- Sin login: la app escucha solo en la máquina del usuario. La demo pública usa datos inventados con el mismo formato.

## Evidence on Hand

- Datos de demo inventados en `demo/` (tres PDF y un `plan.csv`), con un caso de cada alerta.
- Capturas de la app con la demo en `docs/capturas/`, para el README.
- No hay logo, marca ni testimonios. Los datos reales del usuario nunca se usan en maquetas, demo, documentación ni capturas.

## Product Principles

1. **Lo que requiere atención, primero.** Lo que está bien no compite por la mirada con lo que no.
2. **Nunca inventar un número.** Sin datos o sin cotización se dice "sin datos", no se estima.
3. **Mismo número en todos lados.** La terminal, la página y la demo muestran exactamente lo mismo.
4. **Los datos son del usuario.** Nada real sale de su máquina.
5. **Cargar tiene que ser rápido desde el celular.**
6. **Celular y computadora pueden lo mismo.** Las mismas secciones, en el mismo orden y con las mismas funciones; cambia la disposición, nunca lo que se puede hacer.
