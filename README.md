# Soberanos USD: Terminal Analítica — publicación

Sitio estático: `index.html` + `data/closes.json` (cierres diarios) + `scripts/save_close.py` + `.github/workflows/cierre.yml`.

## Publicar (una sola vez, ~5 min)
1. Crear cuenta en github.com y un repositorio nuevo (ej. `soberanos`), público.
2. Subir TODO el contenido de esta carpeta (incluida la carpeta oculta `.github`) al repositorio.
3. Settings → Pages → Source: "Deploy from a branch" → Branch `main` / carpeta `/ (root)` → Save.
4. Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save.
5. Tu página queda en `https://TU_USUARIO.github.io/soberanos/`.

## Cómo funciona
- Precios en vivo: cada visitante consulta data912 desde su navegador cada 90 s (nadie tiene que actualizar nada).
- Historial: el Action corre de lunes a viernes 17:30 ART, guarda el cierre MEP y Cable en `data/closes.json` y lo commitea; la página lo lee al abrir. Si el día es feriado (precios iguales al cierre anterior) no guarda.
- Probar el Action ya mismo: pestaña Actions → "Guardar cierre diario" → Run workflow.
- Los spreads se reconstruyen con el Excel (hasta 2026-10-01) + los cierres guardados + el precio en vivo del día.

## Pestaña «Quant y Valor Relativo»
Valor relativo vs curva (con z-score histórico), carry y roll-down, escenarios de TIR, cartera con DV01 y VaR, volatilidad y correlaciones, canje Local↔NY, pendientes/mariposas y desvío histórico. Todo se calcula en el navegador.

## Pestaña Pesos
Lecaps/Boncaps, CER, TAMAR, dólar linked y duales: curvas, TIR/TNA/TEM/TEA, inflación, devaluación y TAMAR breakeven contra la curva fija.
Los cronogramas, el CER, la TAMAR y el A3500 vienen embebidos (hasta 02/10/2026); los precios se leen en vivo de data912 (arg_bonds y arg_notes).
El Action también guarda el cierre diario de estos instrumentos en `data/closes_ars.json`.
