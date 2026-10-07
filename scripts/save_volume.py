#!/usr/bin/env python3
"""Guarda el volumen del día (arg_bonds + arg_notes de data912) en data/volumen.json.
Se corre después del cierre (GitHub Action). Idempotente: si corre dos veces el mismo día, pisa con el dato más completo.
Detecta solo si el campo v de la API viene en nominal (VN) o en monto, comparando con el historial ya cargado.
Para pruebas: SOURCE_FILE=bonds.json NOTES_FILE=notes.json FORCE_DATE=2026-10-07
"""
import json, os, statistics, sys, math, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "data", "volumen.json")
URLS = ["https://data912.com/live/arg_bonds", "https://data912.com/live/arg_notes"]

today = dt.datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
if os.environ.get("FORCE_DATE"):
    today = dt.date.fromisoformat(os.environ["FORCE_DATE"])
if today.weekday() >= 5:
    print("fin de semana, no se guarda"); sys.exit(0)
ds = today.isoformat()

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))

rows = []
if os.environ.get("SOURCE_FILE"):
    rows += json.load(open(os.environ["SOURCE_FILE"]))
    if os.environ.get("NOTES_FILE"):
        rows += json.load(open(os.environ["NOTES_FILE"]))
else:
    for i, u in enumerate(URLS):
        try:
            rows += get(u)
        except Exception as e:
            print("no disponible:", u, e)
            if i == 0: sys.exit(1)

live = {}
for r in rows:
    s, c, v = r.get("symbol"), r.get("c"), r.get("v")
    if s and isinstance(c, (int, float)) and c > 0 and isinstance(v, (int, float)) and v > 0:
        live[s] = (float(v), float(c))
if len(live) < 20:
    print("pocos tickers con volumen (%d), no se guarda (feriado o respuesta incompleta)" % len(live)); sys.exit(0)

# --- cargar historial (columnar -> {ticker: {s, d: {fecha: [v, e, c]}}}) ---
db = json.load(open(OUT)) if os.path.exists(OUT) else {"dates": [], "t": {}}
cur = {}
for t, o in db["t"].items():
    acc, d = 0, {}
    for k, di in enumerate(o["i"]):
        acc += di; d[db["dates"][acc]] = [o["v"][k], o["e"][k], o["c"][k]]
    cur[t] = {"s": o["s"], "d": d}

# --- ¿v viene en nominal o en monto? se compara con el promedio de las últimas ruedas guardadas ---
dist_nom, dist_eff = [], []
for t, (v, c) in live.items():
    o = cur.get(t)
    if not o: continue
    last = [x for dd, x in sorted(o["d"].items()) if dd < ds and x[0] > 0][-20:]
    if len(last) < 5: continue
    vn, ve = statistics.median(x[0] for x in last), statistics.median(x[1] for x in last)
    if vn > 0 and ve > 0:
        dist_nom.append(abs(math.log(v / vn))); dist_eff.append(abs(math.log(v / ve)))
if len(dist_nom) >= 10:
    mode = "nominal" if statistics.median(dist_nom) <= statistics.median(dist_eff) else "monto"
else:
    mode = "nominal"
print("campo v interpretado como:", mode, "(%d tickers de comparación)" % len(dist_nom))

known = set(cur)
def specie(sym):
    if sym in cur: return cur[sym]["s"]
    if sym[-1] in "DC" and sym[:-1] in live and sym[:-1] in cur: return sym[-1]
    return "P"
n_new = 0
for s, (v, c) in live.items():
    if s not in cur:
        cur[s] = {"s": specie(s), "d": {}}; n_new += 1
    if mode == "nominal": vn, e = v, v * c / 100.0
    else: e, vn = v, v * 100.0 / c
    cur[s]["d"][ds] = [int(round(vn)), int(round(e)), round(c, 4)]

alld = sorted({d for o in cur.values() for d in o["d"]})
idx = {d: i for i, d in enumerate(alld)}
t_out = {}
for t, o in sorted(cur.items()):
    prev, I, V, E, C = 0, [], [], [], []
    for d in sorted(o["d"]):
        v, e, c = o["d"][d]; I.append(idx[d] - prev); prev = idx[d]; V.append(v); E.append(e); C.append(c)
    t_out[t] = {"s": o["s"], "i": I, "v": V, "e": E, "c": C}
with open(OUT, "w") as f:
    json.dump({"dates": alld, "t": t_out}, f, separators=(",", ":"))
print("guardado %s: %d tickers con volumen (%d nuevos), %d ruedas en el historial" % (ds, len(live), n_new, len(alld)))
