-- Estado de cada resumen de tarjeta: impago, parcial, avisado, confirmado o nada que pagar.
-- Un pago corresponde al resumen si es posterior a su cierre y no posterior al cierre siguiente.
-- "Avisado" sale de lo dictado con `pago`; "confirmado", del pago que trae el resumen siguiente.
-- Parámetro: :mes. Muestra los que vencen ese mes y los anteriores que siguen sin confirmar.
-- Desde sqlite3: .param set :mes "'2026-11'"  y después  .read conciliador/consultas/resumenes.sql
WITH resumen AS (
    SELECT
        r.*,
        LEAD(r.cierre) OVER (PARTITION BY r.tarjeta ORDER BY r.cierre) AS cierre_siguiente,
        MAX(r.total_pesos_centavos - r.percepcion_centavos, 0)        AS a_pagar_pesos,
        MAX(r.total_dolares_centavos, 0)                              AS a_pagar_usd
    FROM resumenes AS r
),
pagado AS (
    SELECT
        r.id,
        COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.moneda = 'ARS' THEN m.monto_centavos END), 0)          AS confirmado_pesos,
        COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.moneda = 'USD' THEN m.monto_centavos END), 0)          AS confirmado_usd,
        COALESCE(SUM(CASE WHEN m.tipo = 'pago_tarjeta' AND m.moneda = 'ARS' THEN -m.monto_centavos END), 0) AS avisado_pesos,
        COALESCE(SUM(CASE WHEN m.tipo = 'pago_tarjeta' AND m.moneda = 'USD' THEN -m.monto_centavos END), 0) AS avisado_usd
    FROM resumen AS r
    LEFT JOIN movimientos AS m
        ON  m.tipo IN ('pago', 'pago_tarjeta')
        AND (m.fuente = r.tarjeta OR m.tarjeta = r.tarjeta)
        AND m.fecha > r.cierre
        AND (r.cierre_siguiente IS NULL OR m.fecha <= r.cierre_siguiente)
    GROUP BY r.id
),
estado AS (
    SELECT
        r.tarjeta, r.numero, r.cierre, r.vencimiento,
        r.a_pagar_pesos, r.a_pagar_usd,
        MAX(r.a_pagar_pesos - MAX(p.confirmado_pesos, p.avisado_pesos), 0) AS falta_pesos,
        MAX(r.a_pagar_usd   - MAX(p.confirmado_usd,   p.avisado_usd),   0) AS falta_usd,
        CASE
            WHEN r.a_pagar_pesos = 0 AND r.a_pagar_usd = 0                                   THEN 'nada que pagar'
            WHEN p.confirmado_pesos >= r.a_pagar_pesos AND p.confirmado_usd >= r.a_pagar_usd THEN 'confirmado'
            WHEN MAX(p.confirmado_pesos, p.avisado_pesos) >= r.a_pagar_pesos
             AND MAX(p.confirmado_usd,   p.avisado_usd)   >= r.a_pagar_usd                   THEN 'avisado'
            WHEN p.confirmado_pesos + p.avisado_pesos + p.confirmado_usd + p.avisado_usd > 0 THEN 'parcial'
            ELSE 'impago'
        END AS estado
    FROM resumen AS r
    JOIN pagado AS p ON p.id = r.id
)
SELECT * FROM estado
WHERE strftime('%Y-%m', vencimiento) = :mes
   OR (strftime('%Y-%m', vencimiento) < :mes AND estado IN ('impago', 'parcial', 'avisado'))
ORDER BY vencimiento, tarjeta;
