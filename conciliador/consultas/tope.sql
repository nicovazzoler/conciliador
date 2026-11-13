-- Días del mes en que los gastos variables superaron el tope, en pesos.
-- Variables: consumos que no son de un fijo ni de una cuota, incluido lo cargado a mano.
-- Parámetros: :mes y :tope en centavos (20000000 = $200.000).
-- Desde sqlite3: .param set :mes "'2026-10'"  .param set :tope 20000000  y .read conciliador/consultas/tope.sql
SELECT
    fecha,
    COUNT(*)                     AS movimientos,
    -SUM(CASE WHEN moneda = 'ARS' THEN monto_centavos
              ELSE monto_centavos * cotizacion_centavos / 100 END) AS pesos_centavos,
    group_concat(descripcion, ' | ') AS detalle
FROM movimientos
WHERE tipo = 'consumo'
  AND plan_concepto IS NULL
  AND mes = :mes
GROUP BY fecha
HAVING pesos_centavos > :tope
ORDER BY fecha;
