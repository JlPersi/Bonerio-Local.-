---
name: licitacion
description: Cargar en el sitio un llamado o un resultado de licitación del Tesoro (Secretaría de Finanzas). Usar cuando salga un comunicado nuevo o lo pida la rutina de licitaciones.
---

# Cargar un llamado o resultado de licitación

Todo se hace en una rama nueva desde `main` actualizado, se prueba en el navegador, se abre el PR y se fusiona. Al terminar se avisa en el hilo que recarguen con Ctrl+F5.

## 1. ¿Hay algo nuevo?

1. Mirar `CAL` en `licitaciones.html` (`[llamado, licitación, liquidación]`). Si hoy no es día de llamado ni de licitación, y no quedó pendiente nada de una fecha anterior, terminar sin cambios.
2. Fuente oficial: noticias de la Secretaría de Finanzas en `https://www.argentina.gob.ar/economia/finanzas` (títulos "Llamado a licitación de instrumentos del Tesoro Nacional…" y "Resultado de la licitación…"). El Ministerio de Economía también lo publica en X (@MinEconomia_Ar) con el link a `argentina.gob.ar/noticias/…`. Los resultados suelen salir el día de la licitación entre las 17:10 y las 18 hs; la rutina corre 18:22 y 20:22 por si se atrasan. El listado de noticias tarda en mostrar el comunicado nuevo: probar también directo el link con el número siguiente al último (`/noticias/llamado-licitacion-de-instrumentos-del-tesoro-nacional-denominados-en-pesos-y-en-dolares-NN`, y `resultado-de-la-licitacion-por-efectivo-de-instrumentos-del-tesoro-nacional-denominados-NN`): si responde 200, ya salió. Si no se puede entrar, buscar el comunicado con WebSearch (los brokers suelen republicar el PDF). Nunca inventar datos: si no hay comunicado, avisar y terminar.
3. Comparar con lo cargado: llamado → `LLAM[fechaLicitación]`; resultado → `RES[fechaLicitación]` y `LD.AUC` (entrada con `c` = fecha de licitación).

## 2. Llamado

En `licitaciones.html`:

- `LLAM["AAAA-MM-DD"]` (clave = fecha de licitación): un objeto por instrumento, en el orden del comunicado: `{t, f, k, ve}`.
  - `t` ticker; `f` familia: `fija`, `cer`, `tamar`, `dl` o `dual`; `k` texto ("Lecap", "Boncap", "Boncer cero", "Bono TAMAR", "Dollar linked", "Dual CER / TAMAR", "Dual TAMAR / dólar linked"); `ve` vencimiento `dd/mm/aaaa`.
  - Si el ticker ya está en `data/flujos.xlsx` es reapertura; si no, es instrumento nuevo y hay que darlo de alta (punto 4).
- Si el cronograma cambió (fechas corridas), corregir `CAL`.

## 3. Resultado (script: segundos)

Rápido es la prioridad: el resultado sale entre las 17:10 y las 18 hs y tiene que estar en la página minutos después.

1. **Cierre del día.** Si `data/closes_ars.json` en `origin/main` no tiene la fecha de la licitación, dispararlo ya: `mcp__github__actions_run_trigger` con `run_workflow`, `workflow_id: cierre.yml`, `ref: main` (el cron de GitHub se atrasa horas). Tarda ~1 minuto; mientras, seguir.
2. **Datos.** Guardar el texto del comunicado (o del posteo del MECON en X, o lo que se lea de la captura que pase Juan Luis) en un archivo y correr:
   ```
   node scripts/licitacion/cargar.js --texto resultado.txt
   ```
   Si el texto tiene otro formato, armar el JSON (formato en el encabezado del script) y usar `--json`. `--seco` muestra el resultado sin escribir.
   El script calcula con el código de Curva Pesos (precio de corte, tasa en la unidad de cada familia, yields del secundario, curvas, premios contra el mismo bono y contra la curva) y escribe `RES`, `LD.AUC`, `ADJ`, `ROLL`, `L2C`, `CUTAVG`, `PREM` y `PERFIL` (lo de la licitación anterior pasa a la base). Corrige el vencimiento del llamado si no coincide con la ficha.
   Mercado: el cierre del día si ya está guardado; si no, el vivo de data912 si responde; si no, el último cierre (la página lo aclara).
3. **Revisar la salida** (cortes, premios) contra el comunicado. Si un bono es nuevo el script se frena: darlo de alta (punto 4) y volver a correr.
4. Si se cargó con un cierre anterior, volver a correr el script cuando entre el cierre del día (`git pull`) y publicar de nuevo: la segunda corrida reemplaza la primera.

Qué escribe, por si hace falta tocar algo a mano (montos en billones de $, tasas en %):

- `RES[fechaLicitación]`: `{adjTotal, oferTotal, rollover, instrumentos:[{t, f, k, ve, adj, tasa, u, x?, pP, pD, secP, secD}]}`.
- `LD.ADJ` `{l, a, f, p, mn, mx, n, src}`; `LD.ROLL[liq]`, `LD.L2C[liq]`, `LD.CUTAVG[liq]`, `LD.PREM` (premio promedio por familia en pb).
- `LD.AUC` `{c, q, ref, same, adj, ofr, fam, cuts}`: `fam[g].pts` = `[ticker, días desde la liquidación, yield, atípico, tipo (0, 1 dual, 2 cupones), precio, yield 2da pata, pata]`, `fam[g].segs` la curva ajustada (`fairFit`), `cuts` uno por instrumento (`y` corte, `s` secundario, `po` premio vs el mismo bono, `pc` vs la curva, `cv` curva en `x`).
- `LD.PERFIL[mes].new`: pago al vencimiento con los índices de hoy; `LD.PFN.c` = licitación que está en `new`.
- Unidades: fija TNA simple al vencimiento (en `RES`, la TIREA), CER TNA real 30/365, TAMAR margen, DL TNA en USD, duales margen de la pata TAMAR (y la otra pata en `y2`).
- `CUR` ya no se usa.

## 4. Instrumento nuevo (apertura)

Darlo de alta en todo el sitio:

1. `data/flujos.xlsx`, hoja «Pesos»: una fila por pago con Ticker, Clase, Familia, Emisión, Fecha de pago, Pago, Amortización, Tasa, Interés, Residual y Tipo (la hoja «Leeme» explica cada columna). Copiar las filas de un bono de la misma clase (por ejemplo `S29E7`, `TMG28`, `TXMD9`, `TMVE8`) y cambiar lo que corresponda. En la hoja «Precio de emisión», el ticker y su precio de emisión: arranca su serie de precios hasta que el Action guarde cierres.
2. `python3 scripts/flujos.py build`: pasa la planilla a `index.html` y `preview.html` (`PSD.INST`, y `PSD.H` del bono nuevo) y suma el ticker a `scripts/pesos_tickers.json`. Si se sube solo la planilla a `main`, el Action «Flujos» hace lo mismo. Nunca editar `PSD.INST` a mano en el HTML: la planilla es la fuente y lo pisaría.
3. Revisar que `scripts/pesos_tickers.json` tenga el ticker (lo agrega `flujos.py build`) para que el Action guarde su cierre diario.
4. Verificar que aparezca en Curva Pesos, Variación diaria y Rotación (y en el gráfico del llamado de `licitaciones.html`).

## 5. Probar y entregar

Con el script, alcanza con abrir `licitaciones.html` (y la pestaña Licitaciones de `index.html`) sin errores en consola y publicar. Con el resultado cargado, los gráficos de Próxima licitación muestran el corte y su premio contra la curva y el precio de hoy.


1. `python3 -m http.server` y abrir con Playwright `licitaciones.html` y `index.html` (pestaña Curva Pesos). Sin errores en consola; el llamado o el resultado nuevos se ven; capturas en escritorio y celular (390 px).
2. Usar `?hoy=AAAA-MM-DD` en `licitaciones.html` para ver cómo queda el día del llamado o la licitación.
3. Commit, PR contra `main` y fusionar (Juan Luis lo autorizó). Avisar en el hilo con un resumen corto y que recarguen con Ctrl+F5.
