#!/usr/bin/env python3
"""Guarda en data/dolar.json lo propio de la pestaña Dólar. Se corre junto al cierre diario (GitHub Action). Idempotente.
- A3500: dólar mayorista de referencia del BCRA (Com. A 3500, serie 5), con la historia completa desde junio de 2023.
  La primera vez la trae entera; después, los últimos 30 días (el BCRA a veces corrige el último dato).
- d[fecha]: foto del cierre de data912
    mep: /live/mep, el MEP de AL30 y GD30: cierre, mark (punto medio), bid y ask, precios de cada pata, volumen de cada pata
         (v_ars y v_usd como los da la API: nominal por precio cada 100, o sea 100 veces el monto) y cantidad de operaciones.
    ccl: /live/ccl, el CCL de acciones (ADR): promedio ponderado por volumen en pesos, mediana de los 10 más operados,
         cantidad de papeles, volumen total en pesos y el de GGAL.
El MEP y el CCL de AL30 de cada día ya quedan en data/volumen.json (precio y monto de AL30, AL30D y AL30C): la pestaña los toma de ahí.
Si una fuente falla, no pisa lo que ya había. Para pruebas: MEP_FILE, CCL_FILE, BCRA_FILE (respuestas guardadas) y FORCE_DATE.
"""
import json, os, statistics, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "dolar.json")
BCRA = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/5?desde=%s&hasta=%s&limit=3000"
BONDS = ("AL30", "GD30")
MEPF = ("close", "mark", "bid", "ask", "ars_bid", "ars_ask", "usd_bid", "usd_ask", "v_ars", "v_usd", "q_ars", "q_usd")


def get(url, env):
    if os.environ.get(env):
        return json.load(open(os.environ[env]))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=40))


num = lambda v: isinstance(v, (int, float)) and v == v
today = dt.datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
if os.environ.get("FORCE_DATE"):
    today = dt.date.fromisoformat(os.environ["FORCE_DATE"])
ds = today.isoformat()
try:
    db = json.load(open(OUT))
except Exception:
    db = {}
fx, days = db.setdefault("A3500", {}), db.setdefault("d", {})
changed = False

# --- A3500 ---
desde = "2023-06-01" if len(fx) < 500 else (today - dt.timedelta(days=30)).isoformat()
try:
    rows = get(BCRA % (desde, ds), "BCRA_FILE")["results"][0]["detalle"]
    for r in rows:
        f, v = r.get("fecha"), r.get("valor")
        if f and num(v) and v > 0 and fx.get(f) != v:
            fx[f] = v
            changed = True
    print("A3500: %d filas desde %s (%d en total)" % (len(rows), desde, len(fx)))
except Exception as e:
    print("A3500 no disponible:", e)

# --- foto del cierre: solo días hábiles ---
if today.weekday() < 5:
    snap, holiday = dict(days.get(ds, {})), False
    try:
        mep = {}
        for r in get("https://data912.com/live/mep", "MEP_FILE"):
            if r.get("ticker") in BONDS and num(r.get("close")) and r["close"] > 0:
                mep[r["ticker"]] = {k: r[k] for k in MEPF if num(r.get(k))}
        prev = [d for d in sorted(days) if d < ds]
        if mep and prev and days[prev[-1]].get("mep", {}).get("AL30") == mep.get("AL30") and ds not in days:
            print("MEP idéntico al cierre anterior (¿feriado?): no se guarda la foto del día")
            mep, holiday = {}, True
        if mep:
            snap["mep"] = mep
        print("MEP:", {k: v.get("close") for k, v in mep.items()})
    except Exception as e:
        print("MEP no disponible:", e)
    try:
        if holiday:
            raise RuntimeError("feriado")
        ok = [r for r in get("https://data912.com/live/ccl", "CCL_FILE")
              if num(r.get("CCL_close")) and r["CCL_close"] > 0 and num(r.get("ars_volume")) and r["ars_volume"] > 0]
        if len(ok) >= 5:
            vol = sum(r["ars_volume"] for r in ok)
            top = sorted(ok, key=lambda r: -r["ars_volume"])[:10]
            g = [r for r in ok if r.get("ticker_ar") == "GGAL"]
            snap["ccl"] = {"vw": round(sum(r["CCL_close"] * r["ars_volume"] for r in ok) / vol, 4),
                           "med": round(statistics.median(r["CCL_close"] for r in top), 4), "n": len(ok), "vol": round(vol),
                           "GGAL": round(g[0]["CCL_close"], 4) if g else None}
            print("CCL acciones:", snap["ccl"])
        else:
            print("CCL acciones: respuesta incompleta (%d papeles), no se guarda" % len(ok))
    except Exception as e:
        print("CCL no disponible:", e)
    if snap and snap != days.get(ds):
        days[ds] = snap
        changed = True
else:
    print("fin de semana: solo A3500")

if changed:
    db["A3500"] = dict(sorted(fx.items()))
    db["d"] = dict(sorted(days.items()))
    with open(OUT, "w") as f:
        json.dump(db, f, separators=(",", ":"))
    print("dolar.json actualizado")
else:
    print("sin cambios")
