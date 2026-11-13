-- Qué se importó que cubra el mes: sin esto, no tener un pago no significa que falte.
-- Desde sqlite3: .param set :mes "'2026-10'"  y después  .read conciliador/consultas/importado.sql
SELECT
    EXISTS (
        SELECT 1 FROM movimientos WHERE fuente = 'mercado_pago' AND mes = :mes
    ) AS mercado_pago,
    (
        SELECT group_concat(tarjeta, ', ') FROM resumenes
        WHERE strftime('%Y-%m', vencimiento) = :mes
    ) AS resumenes;
