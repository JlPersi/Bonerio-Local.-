#!/usr/bin/env python3
"""Dividendos en efectivo y en acciones de cada acción de data/acciones, desde Yahoo (<TICKER>.BA), en data/acciones/dividendos.json.

Formato: {"GGAL": [["2024-05-10", "c", 12.5], ["2023-06-01", "a", 1.05], ...]}
"c" = dividendo en efectivo, en pesos por acción (ya ajustado por splits); "a" = dividendo en acciones, como factor (1,05 = 5% en acciones).
Los splits enteros (2 a 1 o más) no van: la página ya los detecta y ajusta sola.
La página los usa para la opción «ajustado por dividendos» del ratio entre acciones.
"""
import json, os, time
import yfinance as yf

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "acciones")
OUT = os.path.join(DIR, "dividendos.json")


def main():
    ts = sorted(f[:-5] for f in os.listdir(DIR) if f.endswith(".json") and f[:-5].isupper() and f not in ("index.json",))
    try:
        old = json.load(open(OUT))
    except Exception:
        old = {}
    out = {}
    for t in ts:
        ev = []
        try:
            tk = yf.Ticker(t + ".BA")
            for d, v in tk.dividends.items():
                if v and v > 0:
                    ev.append([d.strftime("%Y-%m-%d"), "c", round(float(v), 6)])
            for d, v in tk.splits.items():
                if v and 1 < v < 1.9:
                    ev.append([d.strftime("%Y-%m-%d"), "a", round(float(v), 6)])
        except Exception as e:
            print(t, "error", e)
            if t in old:
                out[t] = old[t]
            continue
        if ev:
            out[t] = sorted(ev)
        elif t in old:
            out[t] = old[t]
        print(t, len(ev))
        time.sleep(0.4)
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print("tickers con dividendos:", len(out))


if __name__ == "__main__":
    main()
