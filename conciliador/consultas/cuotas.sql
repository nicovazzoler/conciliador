-- Cuotas del mes: las esperadas según el plan y las que llegaron sin plan. Parámetro: :mes.
-- Desde sqlite3: .param set :mes "'2026-11'"  y después  .read conciliador/consultas/cuotas.sql
WITH numerado AS (
    -- Cada cuota del plan con el número de cuota que le toca este mes.
    SELECT
        c.*,
        (CAST(substr(:mes, 1, 4) AS INTEGER) * 12 + CAST(substr(:mes, 6, 2) AS INTEGER))
      - (CAST(substr(c.primer_mes, 1, 4) AS INTEGER) * 12 + CAST(substr(c.primer_mes, 6, 2) AS INTEGER))
      + 1 AS numero
    FROM cuotas AS c
),
esperadas AS (
    SELECT * FROM numerado WHERE numero BETWEEN 1 AND cantidad
),
reporte AS (
SELECT
    e.concepto,
    printf('%02d/%02d', e.numero, e.cantidad)   AS esperada,
    group_concat(m.cuota, ', ')                AS llegaron,
    COUNT(m.id)                                AS cobros,
    e.monto_centavos                           AS monto_centavos,
    CASE
        -- Sin ningún resumen que venza este mes, que no haya cobro no dice nada.
        WHEN COUNT(m.id) = 0 AND NOT EXISTS (
            SELECT 1 FROM resumenes WHERE strftime('%Y-%m', vencimiento) = :mes
        ) THEN 'sin datos'
        WHEN COUNT(m.id) = 0 THEN 'falta'
        WHEN COUNT(m.id) > 1 THEN 'repetida'
        WHEN max(m.cuota) <> printf('%02d/%02d', e.numero, e.cantidad) THEN 'otro número'
        ELSE 'bien'
    END                                        AS estado
FROM esperadas AS e
LEFT JOIN movimientos AS m
    ON  m.plan_concepto = e.concepto
    AND m.mes = :mes
GROUP BY e.id

UNION ALL

-- Cuotas cobradas que no corresponden a ninguna cuota vigente del plan.
SELECT
    m.descripcion,
    NULL,
    m.cuota,
    1,
    -m.monto_centavos,
    'sin plan'
FROM movimientos AS m
WHERE m.tipo = 'cuota'
  AND m.mes = :mes
  AND m.plan_concepto IS NULL
)
SELECT * FROM reporte
ORDER BY
    CASE estado WHEN 'falta' THEN 1 WHEN 'sin plan' THEN 2 WHEN 'repetida' THEN 3
                WHEN 'otro número' THEN 4 WHEN 'bien' THEN 5 ELSE 6 END,
    concepto;
