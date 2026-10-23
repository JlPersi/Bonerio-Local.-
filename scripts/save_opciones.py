#!/usr/bin/env python3
"""Foto de las opciones de data912 (/live/arg_options) en data/acciones/opciones.json: la pestaña Acciones la usa
como último dato cuando el mercado está cerrado (con el mercado abierto lee la API en vivo). Si la fuente falla, no pisa nada."""
import json, os, urllib.request, datetime as dt

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "acciones", "opciones.json")
try:
    req = urllib.request.Request("https://data912.com/live/arg_options", headers={"User-Agent": "Mozilla/5.0"})
    rows = json.load(urllib.request.urlopen(req, timeout=40))
except Exception as e:
    print("opciones no disponibles:", e); raise SystemExit(0)
if rows:
    json.dump({"d": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "r": rows}, open(OUT, "w"), separators=(",", ":"))
    print("opciones: %d" % len(rows))
