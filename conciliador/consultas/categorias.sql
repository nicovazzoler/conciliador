-- Gasto del mes por categoría, en USD, con el porcentaje de cada una. Parámetro: :mes.
-- Desde sqlite3: .param set :mes "'2026-10'"  y después  .read conciliador/consultas/categorias.sql
SELECT
    categoria,
    COUNT(*)                                                         AS movimientos,
    -SUM(usd_centavos)                                               AS total_usd_centavos,
    ROUND(100.0 * SUM(usd_centavos) / SUM(SUM(usd_centavos)) OVER (), 1) AS porcentaje,
    COUNT(*) - COUNT(usd_centavos)                                   AS sin_usd
FROM movimientos
WHERE tipo IN ('consumo', 'cuota', 'impuesto')
  AND mes = :mes
GROUP BY categoria
ORDER BY total_usd_centavos DESC;
