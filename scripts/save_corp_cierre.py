#!/usr/bin/env python3
"""Cierre diario de ONs y bonos provinciales con data912 (/live/arg_corp y /live/arg_bonds) en data/ons_cierre.json y
data/pvs_cierre.json: precio, TIR (None: la página la calcula), monto del día, monto promedio y ruedas operadas de las
últimas 20. Los montos diarios quedan en data/corp_montos.json; mientras no hay 20 ruedas guardadas, el promedio mezcla
lo que traía la foto anterior. Lo que no operó hoy conserva su último precio. Sin operaciones (feriado) o si falla la fuente, no pisa nada."""
import json, os, urllib.request, datetime as dt

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
P = lambda n: os.path.join(DATA, n)
ahora = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)  # hora Argentina
if ahora.hour * 60 + ahora.minute < 630:  # antes de la rueda data912 todavía muestra la anterior
    d = ahora.date() - dt.timedelta(days=1)
    while d.weekday() > 4:
        d -= dt.timedelta(days=1)
    hoy = d.isoformat()
elif ahora.hour < 17 and not os.environ.get("FORZAR"):
    print("rueda en curso, se guarda después de las 17"); raise SystemExit(0)
else:
    hoy = ahora.date().isoformat()


def get(u):
    req = urllib.request.Request("https://data912.com/live/" + u, headers={"User-Agent": "Mozilla/5.0"})
    return {r["symbol"]: r for r in json.load(urllib.request.urlopen(req, timeout=40)) if r.get("symbol")}


def syms(fn):
    try:
        on = json.load(open(P(fn)))["on"]
    except Exception:
        return set()
    s = set()
    for k, o in on.items():
        s.update(x for x in (o.get("o"), o.get("d"), o.get("c")) if x)
        if o.get("t") == "usd" and fn == "ons.json":
            s.update((k + "D", k + "C"))
    return s


H = json.load(open(P("corp_montos.json"))) if os.path.exists(P("corp_montos.json")) else {}
for name, api, fl in (("ons", "arg_corp", "ons.json"), ("pvs", "arg_bonds", "pvs.json")):
    try:
        lv = get(api)
    except Exception as e:
        print(name, "data912 no disponible:", e); continue
    out = P(name + "_cierre.json")
    old = json.load(open(out)) if os.path.exists(out) else {"d": None, "px": {}}
    keys = (set(old["px"]) | syms(fl)) & set(lv) | set(old["px"])
    mo = {}
    for s in keys:
        r = lv.get(s) or {}
        if (r.get("v") or 0) > 0 and (r.get("c") or 0) > 0:
            mo[s] = round(r["v"] * r["c"] / 100)
    if not mo:
        print(name, "sin operaciones hoy, no se actualiza"); continue
    if name not in H:  # la primera vez, el promedio y las ruedas de la foto anterior sirven de base hasta juntar 20
        H[name] = {"d": [], "m": {}, "base": {s: o[3:5] for s, o in old["px"].items() if len(o) > 4}}
    h = H[name]
    if hoy in h["d"]:  # idempotente: se reemplaza la rueda de hoy
        i = h["d"].index(hoy); h["d"].pop(i)
        for v in h["m"].values():
            v.pop(i)
    h["d"].append(hoy)
    for s in set(h["m"]) | set(mo):
        h["m"].setdefault(s, [0] * (len(h["d"]) - 1)).append(mo.get(s, 0))
    if len(h["d"]) > 20:
        h["d"] = h["d"][-20:]
        h["m"] = {s: v[-20:] for s, v in h["m"].items() if any(v[-20:])}
        h.pop("base", None)
    n = len(h["d"])
    px = {}
    for s in keys:
        o, r, m = old["px"].get(s), lv.get(s) or {}, h["m"].get(s, [0] * n)
        p = r["c"] if s in mo else (o[0] if o else None)
        if not p:
            continue
        b = h.get("base", {}).get(s) if n < 20 else None
        w = (20 - n) / 20 if b else 0
        px[s] = [p, None, mo.get(s, 0), round((b[0] or 0) * w + sum(m) / 20) if b else round(sum(m) / n), (round((b[1] or 0) * w) if b else 0) + sum(1 for x in m if x > 0)]
    json.dump({"d": hoy, "px": px}, open(out, "w"), separators=(",", ":"))
    print(name, hoy, len(px), "especies,", len(mo), "operaron")
json.dump(H, open(P("corp_montos.json"), "w"), separators=(",", ":"))
