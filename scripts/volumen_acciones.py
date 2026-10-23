"""Volumen de las acciones en el formato de data/volumen.json, para la pestaña Volumen.

Lee data/acciones/<TICKER>.json (fecha, apertura, máximo, mínimo, cierre, volumen en acciones) y escribe
data/volumen_acciones.json con las mismas fechas que data/volumen.json:
  {"t": {ticker: {"i": saltos de índice, "v": acciones, "e": monto en pesos (cierre × acciones), "c": cierre}}}
"""
import json
import os

DIR = os.path.join(os.path.dirname(__file__), "..", "data")
ACC = os.path.join(DIR, "acciones")
SKIP = {"index.json", "saltos.json", "metricas.json", "ratios.json", "ccl.json"}


def main():
    dates = json.load(open(os.path.join(DIR, "volumen.json")))["dates"]
    pos = {d: i for i, d in enumerate(dates)}
    out = {"t": {}}
    for fn in sorted(os.listdir(ACC)):
        if not fn.endswith(".json") or fn in SKIP:
            continue
        o = json.load(open(os.path.join(ACC, fn)))
        rows = [r for r in o.get("r", []) if r[0] in pos and r[4] and r[4] > 0 and r[5] and r[5] > 0]
        if not rows:
            continue
        e = {"i": [], "v": [], "e": [], "c": []}
        last = 0
        for r in rows:
            k = pos[r[0]]
            e["i"].append(k - last); last = k
            e["v"].append(round(r[5])); e["e"].append(round(r[4] * r[5])); e["c"].append(r[4])
        out["t"][o["t"]] = e
    json.dump(out, open(os.path.join(DIR, "volumen_acciones.json"), "w"), separators=(",", ":"))
    print("volumen de %d acciones en %d ruedas" % (len(out["t"]), len(dates)))


if __name__ == "__main__":
    main()
