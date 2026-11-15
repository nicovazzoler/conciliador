-- Lo gastado por mes en un rango, para comparar el mes con los anteriores. Parámetros: :desde y :hasta.
-- Desde sqlite3: .param set :desde "'2026-06'"  .param set :hasta "'2026-11'"  y .read conciliador/consultas/historial.sql
SELECT
    mes,
    -COALESCE(SUM(CASE WHEN moneda = 'ARS' THEN monto_centavos END), 0) AS pesos_centavos,
    -COALESCE(SUM(CASE WHEN moneda = 'USD' THEN monto_centavos END), 0) AS dolares_centavos,
    -COALESCE(SUM(usd_centavos), 0)                                     AS total_usd_centavos
FROM movimientos
WHERE tipo IN ('consumo', 'cuota', 'impuesto')
  AND mes BETWEEN :desde AND :hasta
GROUP BY mes
ORDER BY mes;
