-- Lo gastado por mes y por fuente (Mercado Pago, cada tarjeta, lo cargado a mano). Parámetros: :desde y :hasta.
-- Las compras con tarjeta en un pago cuentan en el mes de la compra; las cuotas, en el mes en que vence cada una.
-- Desde sqlite3: .param set :desde "'2026-06'"  .param set :hasta "'2026-11'"  y .read conciliador/consultas/historial_fuentes.sql
SELECT
    mes,
    fuente,
    -COALESCE(SUM(CASE WHEN moneda = 'ARS' THEN monto_centavos END), 0) AS pesos_centavos,
    -COALESCE(SUM(usd_centavos), 0)                                     AS total_usd_centavos
FROM movimientos
WHERE tipo IN ('consumo', 'cuota', 'impuesto')
  AND mes BETWEEN :desde AND :hasta
GROUP BY mes, fuente
ORDER BY mes, fuente;
