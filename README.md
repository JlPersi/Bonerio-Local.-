Terminal Analítica 

Sitio estático: `index.html` + `data/closes.json` (cierres diarios) + `scripts/save_close.py` + `.github/workflows/cierre.yml`.

## Cómo funciona
- Precios en vivo: cada visitante consulta data912 desde su navegador cada 90 s (nadie tiene que actualizar nada).
- Historial: el Action corre de lunes a viernes 17:30 ART, guarda el cierre MEP y Cable en `data/closes.json` y lo commitea; la página lo lee al abrir. Si el día es feriado (precios iguales al cierre anterior) no guarda.
- Probar el Action ya mismo: pestaña Actions → "Guardar cierre diario" → Run workflow.
- Los spreads se reconstruyen con el Excel (hasta 2026-10-01) + los cierres guardados + el precio en vivo del día.
- Pestaña Dólar: el MEP y el CCL salen de AL30, AL30D y AL30C de `data/volumen.json` (desde agosto de 2023). `scripts/save_dolar.py` (en el mismo Action) guarda en `data/dolar.json` el A3500 del BCRA desde 2023 y la foto del cierre de data912 `/live/mep` (AL30 y GD30) y `/live/ccl` (CCL de acciones).
- Acciones (panel líder y general): `scripts/save_acciones.py` guarda los precios en `data/acciones/<TICKER>.json` (el Action de cierre agrega el día; el Action "Acciones: bajar histórico" baja toda la serie de data912 `/historical/stocks`). `scripts/metricas_acciones.py` calcula retornos, volatilidad, caídas y beta contra el panel líder, en pesos y en CCL (`data/acciones/metricas.json`). `scripts/ratios_acciones.py` cruza los balances de `data/acciones/balances/` (formato en su README) con los precios y deja P/E, P/VL, EV/EBITDA, ROE y márgenes en `data/acciones/ratios.json`. `data/acciones/saltos.json` lista saltos de precio de más de 35% para revisar splits o dividendos.
