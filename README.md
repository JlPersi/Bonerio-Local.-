Terminal Analítica 

Sitio estático: `index.html` + `data/closes.json` (cierres diarios) + `scripts/save_close.py` + `.github/workflows/cierre.yml`.

## Cómo funciona
- Precios en vivo: cada visitante consulta data912 desde su navegador cada 90 s (nadie tiene que actualizar nada).
- Historial: el Action corre de lunes a viernes 17:30 ART, guarda el cierre MEP y Cable en `data/closes.json` y lo commitea; la página lo lee al abrir. Si el día es feriado (precios iguales al cierre anterior) no guarda.
- Probar el Action ya mismo: pestaña Actions → "Guardar cierre diario" → Run workflow.
- Los spreads se reconstruyen con el Excel (hasta 2026-10-01) + los cierres guardados + el precio en vivo del día.
