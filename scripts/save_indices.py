#!/usr/bin/env python3
"""Actualiza data/indices.json con CER, TAMAR y A3500 desde la API de estadísticas del BCRA (v4.0).
Ids: 30 = CER, 44 = TAMAR bancos privados (TNA %), 5 = tipo de cambio mayorista de referencia (Com. A 3500).
Se corre junto al cierre diario. Si la API falla no pisa nada (la página sigue con los datos embebidos).
Para pruebas: BCRA_MOCK=/carpeta con 30.json, 44.json y 5.json (misma forma que la respuesta).
"""
import json, os, sys, urllib.request, datetime as dt

BASE = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/%d?desde=%s&hasta=%s&limit=3000"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "indices.json")
SERIES = {"CER": 30, "TAMAR": 44, "FX": 5}
today = dt.date.today()
desde = (today - dt.timedelta(days=75)).isoformat()
hasta = (today + dt.timedelta(days=20)).isoformat()  # el CER se publica unos días adelante


def fetch(i):
    if os.environ.get("BCRA_MOCK"):
        return json.load(open(os.path.join(os.environ["BCRA_MOCK"], "%d.json" % i)))
    req = urllib.request.Request(BASE % (i, desde, hasta), headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=40))


try:
    db = json.load(open(OUT))
except Exception:
    db = {"CER": {}, "TAMAR": {}, "FX": {}}
changed = False
for name, i in SERIES.items():
    try:
        data = fetch(i)
        rows = data["results"][0]["detalle"]
    except Exception as e:
        print(name, "no disponible:", e)
        continue
    d = db.setdefault(name, {})
    for r in rows:
        f, v = r.get("fecha"), r.get("valor")
        if f and isinstance(v, (int, float)) and v > 0 and d.get(f) != v:
            d[f] = v
            changed = True
    db[name] = dict(sorted(d.items())[-400:])
    print(name, "ok", len(rows), "filas")
if changed:
    with open(OUT, "w") as fh:
        json.dump(db, fh, separators=(",", ":"))
    print("indices.json actualizado")
else:
    print("sin cambios")
