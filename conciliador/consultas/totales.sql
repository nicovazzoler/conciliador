-- Lo gastado en el mes: en pesos, en dólares y todo pasado a USD. Es la consulta de M1.
-- Desde sqlite3: .param set :mes "'2026-10'"  y después  .read conciliador/consultas/totales.sql
SELECT
    COUNT(*)                                                           AS movimientos,
    -COALESCE(SUM(CASE WHEN moneda = 'ARS' THEN monto_centavos END), 0) AS pesos_centavos,
    -COALESCE(SUM(CASE WHEN moneda = 'USD' THEN monto_centavos END), 0) AS dolares_centavos,
    -- NULL si hay gastos y ninguno tiene cotización: es "sin datos", no cero. Si faltan algunos, ver sin_usd.
    CASE WHEN COUNT(*) = 0 THEN 0 ELSE -SUM(usd_centavos) END          AS total_usd_centavos,
    COUNT(*) - COUNT(usd_centavos)                                     AS sin_usd
FROM movimientos
WHERE tipo IN ('consumo', 'cuota', 'impuesto')
  AND mes = :mes;
