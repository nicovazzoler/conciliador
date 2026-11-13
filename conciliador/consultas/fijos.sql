-- Cada fijo del plan contra lo cobrado en el mes. Parámetro: :mes, por ejemplo '2026-10'.
-- Desde sqlite3: .param set :mes "'2026-10'"  y después  .read conciliador/consultas/fijos.sql
SELECT
    f.concepto,
    f.moneda,
    f.monto_centavos                        AS anotado_centavos,
    COUNT(m.id)                             AS pagos,
    COALESCE(-SUM(m.monto_centavos), 0)     AS cobrado_centavos,
    CASE
        -- Sin el PDF de Mercado Pago del mes, que no haya pago no dice nada.
        WHEN COUNT(m.id) = 0 AND NOT EXISTS (
            SELECT 1 FROM movimientos WHERE fuente = 'mercado_pago' AND mes = :mes
        )                                           THEN 'sin datos'
        WHEN COUNT(m.id) = 0                        THEN 'sin debitar'
        WHEN -SUM(m.monto_centavos) > f.monto_centavos THEN 'más caro'
        WHEN -SUM(m.monto_centavos) < f.monto_centavos THEN 'más barato'
        ELSE 'bien'
    END                                     AS estado
FROM fijos AS f
LEFT JOIN movimientos AS m
    ON  m.plan_concepto = f.concepto
    AND m.mes = :mes
    AND m.moneda = f.moneda
GROUP BY f.id
ORDER BY
    CASE estado WHEN 'sin debitar' THEN 1 WHEN 'más caro' THEN 2 WHEN 'más barato' THEN 3
                WHEN 'bien' THEN 4 ELSE 5 END,
    f.concepto;
