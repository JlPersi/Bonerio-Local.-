#!/usr/bin/env python3
"""Dólar histórico para pasar a dólares las acciones antes de que exista el CCL de AL30 (data/volumen.json, desde 2023).
data/acciones/ccl.json: {"ccl": {fecha: valor}, "oficial": {fecha: valor}}
- ccl: contado con liquidación diario de api.argentinadatos.com (venta).
- oficial: mayorista de referencia del BCRA (Com. A 3500, serie 5), desde 2002; antes de 2002 la pestaña usa 1 (convertibilidad).
La pestaña Acciones usa, por fecha: el CCL de AL30 si lo hay, si no este CCL, si no el oficial.
Se corre a mano (Action "Acciones: dólar histórico"). Si una fuente falla, no pisa lo que ya había.
"""
import json, os, urllib.request, datetime as dt

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "acciones", "ccl.json")
BCRA = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/5?desde=%s&hasta=%s&limit=3000"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=60))


try:
    db = json.load(open(OUT))
except Exception:
    db = {}
ccl, of = {}, {}
try:
    for r in get("https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui"):
        v = r.get("venta") or r.get("compra")
        if r.get("fecha") and isinstance(v, (int, float)) and v > 0:
            ccl[r["fecha"][:10]] = v
    print("CCL: %d días desde %s" % (len(ccl), min(ccl)))
except Exception as e:
    print("CCL no disponible:", e)
try:
    for y in range(2002, dt.date.today().year + 1):
        for r in get(BCRA % ("%d-01-01" % y, "%d-12-31" % y))["results"][0]["detalle"]:
            if r.get("fecha") and isinstance(r.get("valor"), (int, float)) and r["valor"] > 0:
                of[r["fecha"]] = r["valor"]
    print("Oficial: %d días desde %s" % (len(of), min(of)))
except Exception as e:
    print("Oficial no disponible:", e)
if ccl:
    db["ccl"] = dict(sorted(ccl.items()))
if of:
    db["oficial"] = dict(sorted(of.items()))
if db:
    json.dump(db, open(OUT, "w"), separators=(",", ":"))
