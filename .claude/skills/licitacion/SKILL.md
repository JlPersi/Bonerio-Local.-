---
name: licitacion
description: Cargar en el sitio un llamado o un resultado de licitación del Tesoro (Secretaría de Finanzas). Usar cuando salga un comunicado nuevo o lo pida la rutina de licitaciones.
---

# Cargar un llamado o resultado de licitación

Todo se hace en una rama nueva desde `main` actualizado, se prueba en el navegador, se abre el PR y se fusiona. Al terminar se avisa en el hilo que recarguen con Ctrl+F5.

## 1. ¿Hay algo nuevo?

1. Mirar `CAL` en `licitaciones.html` (`[llamado, licitación, liquidación]`). Si hoy no es día de llamado ni de licitación, y no quedó pendiente nada de una fecha anterior, terminar sin cambios.
2. Fuente oficial: noticias de la Secretaría de Finanzas en `https://www.argentina.gob.ar/economia/finanzas` (títulos "Llamado a licitación de instrumentos del Tesoro Nacional…" y "Resultado de la licitación…"). Si no se puede entrar, buscar el comunicado con WebSearch (los brokers suelen republicar el PDF). Nunca inventar datos: si no hay comunicado, avisar y terminar.
3. Comparar con lo cargado: llamado → `LLAM[fechaLicitación]`; resultado → `RES[fechaLicitación]` y `LD.AUC` (entrada con `c` = fecha de licitación).

## 2. Llamado

En `licitaciones.html`:

- `LLAM["AAAA-MM-DD"]` (clave = fecha de licitación): un objeto por instrumento, en el orden del comunicado: `{t, f, k, ve}`.
  - `t` ticker; `f` familia: `fija`, `cer`, `tamar`, `dl` o `dual`; `k` texto ("Lecap", "Boncap", "Boncer cero", "Bono TAMAR", "Dollar linked", "Dual CER / TAMAR", "Dual TAMAR / dólar linked"); `ve` vencimiento `dd/mm/aaaa`.
  - Si el ticker ya existe en `PSD.INST` (index.html) es reapertura; si no, es instrumento nuevo y hay que darlo de alta (punto 4).
- Si el cronograma cambió (fechas corridas), corregir `CAL`.

## 3. Resultado

Montos en **billones de $** (VN adjudicado), tasas en %, la unidad de cada familia: fija TNA (o TIREA si el comunicado la da, aclarado en `u`), CER TIREA real, TAMAR margen, DL TIREA USD, duales margen de la rama TAMAR.

En `licitaciones.html`:

- `RES["fechaLicitación"] = {adjTotal, oferTotal, rollover, instrumentos:[…]}` con `{t, f, k, ve, adj, tasa, u, x?, pP, pD, secP, secD, fl?}`. `pP`/`pD` precio de corte y precio del secundario; `secP`/`secD` yield del mismo bono en el secundario al cierre previo y al cierre del día. Ver la entrada `2026-09-28` como modelo.
- `LD.ADJ`: agregar `{l: liquidación, a: adjudicado total, f: {familia: adjudicado}, p: plazo promedio ponderado en días, mn, mx, n: cantidad de instrumentos, src: "texto oficial dd/mm"}`.
- `LD.ROLL[liquidación] = [rollover %, "MECON"]` y `LD.L2C[liquidación] = fechaLicitación`.
- `LD.CUTAVG[liquidación]`: tasa de corte promedio ponderada por familia.
- `LD.AUC`: una entrada `{c, q, ref, same, adj, ofr, fam, cuts}` como la del 28/09. `fam[g].pts` son los bonos del secundario `[ticker, días, yield, atípico(0/1/2), tipo(0/1 dual/2 amortiza), precio, yield 2da rama, rama]` y `fam[g].segs` la curva ajustada; `cuts` un objeto por instrumento adjudicado (`t, g, x días, v adjudicado, y corte, P precio, s yield secundario, ps precio secundario, po premio vs el mismo bono en pb, pc premio vs la curva, cv yield de la curva en x, du dual, …`).
- `LD.PREM`: premio promedio por familia en pb y cantidad (`n_fija`, …).
- `LD.PERFIL`: sumar lo adjudicado en el mes de vencimiento de cada instrumento, en `new`.
- `CUR[fechaLicitación]`: curvas por familia al cierre previo y del día `[ticker, meses, yield previo, yield día, dual]`.
- Si el resultado trae una licitación fuera de cronograma, anotarla en `LD.EXTRA`.

**Yields y curvas del secundario:** calcularlos con el mismo código del sitio, no a mano. Servir el repo (`python3 -m http.server`), abrir `index.html` con Playwright (Chromium ya instalado), esperar `window.PSX` y usar `PSX.yieldAt(ticker, día, precioSucio)`, `PSX.ptsOf`, `PSX.durAt` y `PSX.snap`. Los precios de cierre salen de `data/closes_ars.json` (cierre del día de la licitación; si todavía no está, del vivo de data912 y reemplazarlo al día siguiente). Si un bono nuevo no cotiza todavía, va sin premio contra el mismo bono (`po: null`) y con premio contra la curva.

## 4. Instrumento nuevo (apertura)

Darlo de alta en todo el sitio:

1. `index.html`, línea `const PSD = …` → `PSD.INST[ticker] = {k, f, iss, r}` con fechas en días desde 1970 (`Date.parse('AAAA-MM-DDT00:00:00Z')/864e5`).
   - `k`: `cap` (Lecap/Boncap), `cerc` (Boncer), `tamar`, `dl`, `dual`, `dualtf`, `cpn`. `f`: `fija`, `cer`, `tamar`, `dl`, `cer+tamar`, `dl+tamar`. `iss`: fecha de emisión.
   - `r`: `[fecha de pago, monto o cupón, amortización, tasa (TEM, margen, etc. en decimal), 0, 0, tipo]` con tipo `FIXED_RATE`, `CER`, `TAMAR` o `DOLLAR_LINKED`. Copiar la forma de un bono de la misma clase (por ejemplo `S29E7`, `TMG28`, `TXMD9`, `TMVE8`).
2. `PSD.H[ticker] = {s: día de emisión, d: [0], p: [precio de emisión]}` para que tenga serie hasta que el Action guarde cierres.
3. `scripts/pesos_tickers.json`: agregar el ticker (orden alfabético) para que el Action guarde su cierre diario.
4. Verificar que aparezca en Curva Pesos, Variación diaria y Rotación (y en el gráfico del llamado de `licitaciones.html`).

## 5. Probar y entregar

1. `python3 -m http.server` y abrir con Playwright `licitaciones.html` y `index.html` (pestaña Curva Pesos). Sin errores en consola; el llamado o el resultado nuevos se ven; capturas en escritorio y celular (390 px).
2. Usar `?hoy=AAAA-MM-DD` en `licitaciones.html` para ver cómo queda el día del llamado o la licitación.
3. Commit, PR contra `main` y fusionar (Juan Luis lo autorizó). Avisar en el hilo con un resumen corto y que recarguen con Ctrl+F5.
