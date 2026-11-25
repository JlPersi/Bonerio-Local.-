#!/usr/bin/env python3
"""Actualiza data/monetario.json con el M2 diario (millones de pesos) de las «Series principales» del BCRA (series.xlsm, hoja DEPOSITOS).
Es el denominador del ratio cobertura cambiaria / M2 (futuros de dólar + dollar linked). Se corre con el cierre diario; si falla no pisa nada.
Para pruebas: BCRA_XLSM=/ruta/a/series.xlsm.
"""
import json, os, sys, tempfile, urllib.request, datetime as dt

URL = "https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/series.xlsm"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "monetario.json")
DESDE = dt.datetime(2024, 1, 1)


def main():
    import openpyxl
    path = os.environ.get("BCRA_XLSM")
    if not path:
        fd, path = tempfile.mkstemp(suffix=".xlsm"); os.close(fd)
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["DEPOSITOS"]
    rows = ws.iter_rows(values_only=True)
    col = typ = None; m2 = {}
    for r in rows:
        if col is None:  # la fila de títulos: «M2(6) (expresado en Pesos)» y «Tipo de serie» (D = diaria)
            for i, x in enumerate(r):
                s = str(x or "").replace("\n", " ")
                if s.startswith("M2(") and col is None: col = i
                if s.startswith("Tipo") and "serie" in s: typ = i
            continue
        d = r[0]
        if not isinstance(d, dt.datetime) or d < DESDE: continue
        if typ is not None and r[typ] != "D": continue  # sin los promedios mensuales ni las variaciones
        v = r[col] if col < len(r) else None
        if isinstance(v, (int, float)) and v > 0: m2[d.date().isoformat()] = round(v, 1)
    if col is None or len(m2) < 100:
        print("monetario: no encontré el M2 (col %s, %d datos)" % (col, len(m2))); return 0
    try: old = json.load(open(OUT))
    except Exception: old = {}
    db = {"fuente": "BCRA, Series principales (hoja DEPOSITOS): M2 en millones de pesos", "M2": dict(sorted(m2.items()))}
    if old.get("M2") == db["M2"]: print("monetario: sin cambios"); return 0
    json.dump(db, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print("monetario: %d días, último %s" % (len(m2), max(m2)))
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as e:
        print("monetario: error", e); sys.exit(0)
