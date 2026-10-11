#!/usr/bin/env python3
"""Guarda en data/tasas.json las tasas en pesos para "¿Qué convino?" (API de estadísticas del BCRA, v4.0). Se corre junto al cierre diario. Idempotente.
Ids: 12 = plazo fijo a 30 días (tasa minorista, TNA %), 7 = BADLAR bancos privados (TNA %), 44 = TAMAR bancos privados (TNA %, desde octubre de 2024).
La primera vez trae todo desde junio de 2023; después, los últimos 45 días (el BCRA a veces corrige el último dato).
Si una serie falla no pisa lo que ya había. Para pruebas: BCRA_MOCK=/carpeta con 12.json, 7.json y 44.json (misma forma que la respuesta).
"""
import json, os, urllib.request, datetime as dt

BASE = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/%d?desde=%s&hasta=%s&limit=3000"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "tasas.json")
SERIES = {"PF": 12, "BADLAR": 7, "TAMAR": 44}
today = dt.date.today()


def fetch(i, desde):
    if os.environ.get("BCRA_MOCK"):
        return json.load(open(os.path.join(os.environ["BCRA_MOCK"], "%d.json" % i)))
    req = urllib.request.Request(BASE % (i, desde, today.isoformat()), headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=40))


try:
    db = json.load(open(OUT))
except Exception:
    db = {}
changed = False
for name, i in SERIES.items():
    d = db.setdefault(name, {})
    desde = "2023-06-01" if len(d) < 300 else (today - dt.timedelta(days=45)).isoformat()
    try:
        rows = fetch(i, desde)["results"][0]["detalle"]
    except Exception as e:
        print(name, "no disponible:", e)
        continue
    for r in rows:
        f, v = r.get("fecha"), r.get("valor")
        if f and isinstance(v, (int, float)) and v > 0 and d.get(f) != v:
            d[f] = v
            changed = True
    db[name] = dict(sorted(d.items()))
    print(name, "ok", len(rows), "filas desde", desde, "(", len(db[name]), "en total )")
if changed:
    with open(OUT, "w") as fh:
        json.dump(db, fh, separators=(",", ":"))
    print("tasas.json actualizado")
else:
    print("sin cambios")
