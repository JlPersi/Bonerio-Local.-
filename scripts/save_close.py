#!/usr/bin/env python3
"""Guarda el cierre del día (precio sucio MEP 'D' y Cable 'C') en data/closes.json.
Se corre una vez por día hábil después del cierre (GitHub Action). Idempotente.
Para pruebas: SOURCE_FILE=/ruta/respuesta.json  y  FORCE_DATE=2026-10-05
"""
import json, os, re, sys, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

URL = "https://data912.com/live/arg_bonds"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "closes.json")
PAT = re.compile(r"^(AL|GD|AE|AO|AN)\d{2}[DC]$")

today = dt.datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
if os.environ.get("FORCE_DATE"):
    today = dt.date.fromisoformat(os.environ["FORCE_DATE"])
if today.weekday() >= 5:
    print("fin de semana, no se guarda"); sys.exit(0)

if os.environ.get("SOURCE_FILE"):
    data = json.load(open(os.environ["SOURCE_FILE"]))
else:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=30))

new = {"D": {}, "C": {}}
for r in data:
    sym, c = r.get("symbol", ""), r.get("c")
    if PAT.match(sym) and isinstance(c, (int, float)) and c > 0:
        new[sym[-1]][sym[:-1]] = round(float(c), 4)
# --- instrumentos en pesos (arg_bonds + arg_notes): se guardan en data/closes_ars.json ---
ARS = set(json.load(open(os.path.join(os.path.dirname(__file__), "pesos_tickers.json"))))
rows = list(data)
if not os.environ.get("SOURCE_FILE"):
    try:
        req2 = urllib.request.Request("https://data912.com/live/arg_notes", headers={"User-Agent": "Mozilla/5.0"})
        rows += json.load(urllib.request.urlopen(req2, timeout=30))
    except Exception as e:
        print("arg_notes no disponible:", e)
ars = {r["symbol"]: round(float(r["c"]), 4) for r in rows if r.get("symbol") in ARS and isinstance(r.get("c"), (int, float)) and r["c"] > 0}
if len(new["D"]) < 5:
    print("respuesta incompleta, no se guarda"); sys.exit(1)

db = json.load(open(OUT))
ds = today.isoformat()
# feriado (o sin operar): los precios son idénticos al último cierre guardado -> no se guarda
prev = [d for d in sorted(db["D"]) if d < ds]
if prev and db["D"][prev[-1]] == new["D"] and ds not in db["D"]:
    print("precios idénticos al cierre anterior (feriado?), no se guarda"); sys.exit(0)

for sp in "DC":
    db[sp][ds] = new[sp]
    db[sp] = dict(sorted(db[sp].items()))
with open(OUT, "w") as f:
    json.dump(db, f, separators=(",", ":"))
OUT2 = os.path.join(os.path.dirname(__file__), "..", "data", "closes_ars.json")
try:
    db2 = json.load(open(OUT2))
except Exception:
    db2 = {}
p2 = [d for d in sorted(db2) if d < ds]
if len(ars) >= 5 and not (p2 and db2[p2[-1]] == ars and ds not in db2):
    db2[ds] = ars
    with open(OUT2, "w") as f:
        json.dump(dict(sorted(db2.items())), f, separators=(",", ":"))
    print(f"pesos: {len(ars)} instrumentos")
print(f"guardado {ds}: {len(new['D'])} MEP, {len(new['C'])} Cable")
