-- Lo gastado en una categoría, mes por mes. Parámetros: :categoria, :desde y :hasta.
-- Desde sqlite3: .param set :categoria "'Salud'"  .param set :desde "'2026-06'"  .param set :hasta "'2026-11'"
SELECT
    mes,
    COUNT(*)                                                           AS movimientos,
    -COALESCE(SUM(CASE WHEN moneda = 'ARS' THEN monto_centavos END), 0) AS pesos_centavos,
    -COALESCE(SUM(usd_centavos), 0)                                     AS total_usd_centavos
FROM movimientos
WHERE tipo IN ('consumo', 'cuota', 'impuesto')
  AND categoria = :categoria
  AND mes BETWEEN :desde AND :hasta
GROUP BY mes
ORDER BY mes;
