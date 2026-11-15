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
- Un plan (`plan.csv`) define los gastos fijos y las cuotas esperadas.
- Los gastos grandes sin anticipar piden confirmación y categoría.
- Las operaciones son muchas por mes: entran importadas o leídas por el agente desde una captura, no una por una a mano.
- Uso típico: en el celular para cargar un gasto o mirar el mes; en la computadora para importar y revisar.

## Capabilities and Constraints

- **Gastos (construido):** reporte del mes con totales en pesos y en USD, fijos (sin datos, sin debitar, más caro, más barato, bien), cuotas (sin datos, falta, sin plan, repetida, otro número, bien), días que superan el tope diario de $ 200.000, resúmenes de tarjeta (nada que pagar, impago, parcial, avisado, confirmado), gasto por categoría; carga y borrado de gastos y pagos de tarjeta; revisión de pendientes y categorización por grupos con reglas; importación de PDFs.
- **Portafolio y Trading (por construir):** tenencias derivadas de las operaciones, valor actual, ganancia o pérdida por posición; historial de compras y ventas con ganancia realizada. Opera sobre todo en Quantfury (acciones y cripto, en USD) y algo en Binance. Opera seguido, así que cargar a mano no alcanza: la intención es importar el historial o que el agente de la etapa 3 lea una captura de pantalla de las operaciones y las cargue, con confirmación.
- **Precios:** la idea del usuario es tomarlos de Google Finance y, si falta alguno, de otra fuente. Por decidir: Google Finance no tiene API oficial, así que hay que validar la fuente antes de construir.
- **Por decidir:** el formato de exportación de Quantfury y de Binance.
- Montos en formato argentino: `$ 1.234,56` y `U$D 88,24`. Toda la interfaz en español rioplatense.
- Backend FastAPI con esquemas que generan los tipos de TypeScript; front Vite + React + TypeScript.
- Sin login: la app escucha solo en la máquina del usuario. La demo pública usa datos inventados con el mismo formato.

## Evidence on Hand

- Datos de demo inventados en `demo/` (tres PDF y un `plan.csv`), con un caso de cada alerta.
- No hay logo, marca, testimonios ni capturas reales. Los datos reales del usuario nunca se usan en maquetas, demo, documentación ni capturas.

## Product Principles

1. **Lo que requiere atención, primero.** Lo que está bien no compite por la mirada con lo que no.
2. **Nunca inventar un número.** Sin datos o sin cotización se dice "sin datos", no se estima.
3. **Mismo número en todos lados.** La terminal, la página y la demo muestran exactamente lo mismo.
4. **Los datos son del usuario.** Nada real sale de su máquina.
5. **Cargar tiene que ser rápido desde el celular.**
6. **Celular y computadora pueden lo mismo.** Las mismas secciones, en el mismo orden y con las mismas funciones; cambia la disposición, nunca lo que se puede hacer.
