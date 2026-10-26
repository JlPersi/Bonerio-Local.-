---
name: ons
description: Dar de alta en la sección Obligaciones negociables las ONs que se colocaron en la CNV. Usar cuando lo pida la rutina de ONs o Juan Luis avise de una colocación.
---

# Cargar ONs nuevas desde la CNV

Script: `scripts/ons_cnv.py` (el encabezado explica la ficha). Estado en `data/ons_cnv.json`: series vistas (`cargada`, `sin ticker` con su ficha, o el motivo por el que no se carga) y alias de emisor por CUIT.

## 1. ¿Hay algo nuevo?

1. `git pull` de `main`.
2. `python3 scripts/ons_cnv.py nuevas --dias 45`: lista las colocaciones de la CNV (Empresas > Últimas colocaciones) que no están cargadas ni vistas y baja a `.ons_cnv/<serie>/` el aviso de suscripción y el de resultado (PDF y texto).
   - `ya cargada`: hay una ON del mismo emisor que vence esa semana. Si el alias del emisor sale `null` y existe en `data/ons_emisores.json` con otro nombre, sumarlo a `alias` (CUIT → nombre) y volver a correr.
   - `sin aviso de resultado todavía`: se vuelve a mirar en la próxima corrida.
3. `python3 scripts/ons_cnv.py pendientes`: para las fichas sin ticker, las especies de data912 que empezaron a cotizar y no están en `ons.json`.
4. Si no hay nuevas ni pendientes con candidato, terminar sin cambios.

## 2. Armar la ficha

Leer los `.txt` de cada serie y armar la ficha (una lista en un JSON):

- Tasa (en fijas) o margen (TAMAR, BADLAR), emisión y liquidación, vencimiento, fechas de pago de intereses, amortización (bullet o cuotas en % del VN original). Si el aviso dice "Tasa de Referencia", ver en el de suscripción si es TAMAR o BADLAR.
- Base de cálculo: suele estar en el aviso de suscripción ("un año de 365 días" → `act/365`; "360 días compuesto por doce meses de 30 días" → `30/360`). Si no aparece, `act/365`.
- Tipo: `ON` (dólares, fija; MEP o cable), `ON_DOLLAR_LINKED`, `ON_FIXED_RATE` (pesos, fija), `ON_TAMAR`, `ON_BADLAR`, `ON_CER` (UVA).
- Emisor: el nombre corto de `data/ons_emisores.json` si ya existe; si no, uno corto nuevo.
- Ticker: el que diga el aviso ("Ticker", "código BYMA"); en las adicionales, el de la clase original. Si no aparece, `null`: queda pendiente hasta que cotice. Nunca inventarlo: se confirma con `pendientes` (especie nueva del emisor, con precio coherente con la tasa).
- Adicionales (reaperturas) de una clase ya cargada: `marcar <serie> "reapertura de XXXXO"`.
- Lo que no va en la sección (no cotiza, VCP, otra moneda): `marcar <serie> "<motivo>"`.

`python3 scripts/ons_cnv.py alta ficha.json --seco` muestra los flujos: revisar que la primera renta y el total cierren con el aviso. Después sin `--seco` escribe la planilla, `ons_emisores.json`, `ons_cnv.json` y regenera `data/ons.json`. Para una pendiente que ya tiene ticker: `python3 scripts/ons_cnv.py ticker <serie> <TICKER>`.

## 3. Probar y entregar

1. `python3 -m http.server` y abrir `index.html` con Playwright, pestaña `ons` (para saltear el login, servir `auth.js` vacío; Chart.js de cdnjs puede estar bloqueado: servirlo desde `npm i chart.js@4.4.1`). Sin errores en consola, en escritorio y a 390 px. La ON aparece en la tabla cuando el Action guarda su primer cierre.
2. Commit, PR contra `main` y fusionar (Juan Luis lo autorizó). Avisar en el hilo cuáles se cargaron, cuáles quedan esperando ticker, y que recarguen con Ctrl+F5.
