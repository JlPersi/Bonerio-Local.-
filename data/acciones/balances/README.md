# Balances de acciones

Un archivo por empresa: `data/acciones/balances/<TICKER>.json` (el ticker como cotiza en BYMA, por ejemplo `GGAL`, `YPFD`, `TGSU2`).
Los carga Claude a partir de los estados contables que publica la CNV (PDF o Excel). `scripts/ratios_acciones.py` los cruza con los precios
y deja los ratios en `data/acciones/ratios.json`.

## Formato

```json
{
  "t": "GGAL",
  "escala": 1000000,
  "acciones": 1474692091,
  "periodos": [
    {
      "cierre": "2026-06-30",
      "publicado": "2026-08-25",
      "acumulado_meses": 6,
      "acciones": 1474692091,
      "resultados": {
        "ventas": 0,
        "resultado_operativo": 0,
        "depreciaciones": 0,
        "resultado_neto": 0,
        "resultado_neto_controlante": 0
      },
      "situacion": {
        "patrimonio_neto": 0,
        "patrimonio_neto_controlante": 0,
        "deuda_financiera": 0,
        "caja_inversiones": 0
      }
    }
  ]
}
```

- `escala`: multiplicador de los montos (1000000 si el balance está en millones de pesos, 1000 si está en miles).
- `cierre`: fecha de cierre del período. `publicado`: fecha en que se presentó a la CNV (si falta se toma cierre + 42 días los trimestrales y + 70 los anuales).
- `acumulado_meses`: 3, 6, 9 o 12. Los estados de resultados se cargan como los publica la empresa (acumulados desde el inicio del ejercicio); el TTM se arma solo.
- `acciones`: acciones en circulación (unidades) en ese período; si no cambia, alcanza con el valor general de arriba.
- Montos en moneda de la fecha de cierre (NIC 29), tal como figuran en el balance. La reexpresión la hace el script con el CER.
- Bancos: `ventas`, `resultado_operativo` y `depreciaciones` pueden ir en `null`; para ellos los ratios que importan son P/VL, P/E y ROE.
- Lo que no figure en el balance va en `null` (no en 0).
- `moneda_funcional`: "USD" para las que llevan la contabilidad en dólares (YPF, Pampa). Sus pesos son dólares convertidos al cierre,
  así que el script las lleva a la fecha con el A3500 y no con el CER.
- `splits`: lista de `{"fecha": "2026-08-03", "factor": 10}` (factor = acciones nuevas por cada vieja). Los precios guardados no se
  ajustan, así que la capitalización usa las acciones del balance multiplicadas por los splits posteriores a su cierre.

## Carga automática

`scripts/balances_cnv.py` baja de la CNV la planilla estandarizada de cada estado contable presentado (consolidado, o individual si no
hay) y reescribe estos archivos. Corre en el Action "Balances CNV" (semanal y a mano). Las empresas, su CUIT y el valor nominal de la
acción están en la tabla `EMPRESAS` del script.
