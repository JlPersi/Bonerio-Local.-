#!/usr/bin/env python3
"""Los relativos de un año (las últimas 250 ruedas), para que el Inicio compare cada señal contra su historia: data/relativos.json.
Sale de los cierres de data/volumen.json (cada especie desde 2023):
  GD30/AL30, GD35/AL35, ...  precio del Global en dólares MEP sobre el del Bonar, menos 1 (%): cuánto más caro está la ley NY
  canje                      CCL sobre MEP de AL30, menos 1 (%) = AL30D / AL30C - 1
  mep_gd_al                  MEP de GD30 sobre MEP de AL30, menos 1 (%)
{"dates": [...], "s": {nombre: [valor o null, ...]}}
"""
import json, os

D = os.path.join(os.path.dirname(__file__), "..", "data")
N = 250
PARES = [("AL29", "GD29"), ("AL30", "GD30"), ("AL35", "GD35"), ("AE38", "GD38"), ("AL41", "GD41")]


def main():
    with open(os.path.join(D, "volumen.json")) as f:
        v = json.load(f)
    dates = v["dates"]

    def serie(t):  # {índice de fecha: cierre}
        o, out, acc = v["t"].get(t), {}, 0
        if not o:
            return out
        for di, c in zip(o["i"], o["c"]):
            acc += di
            if c and c > 0:
                out[acc] = c
        return out

    idx = list(range(max(0, len(dates) - N), len(dates)))
    S = {}
    for a, g in PARES:
        A, G = serie(a + "D"), serie(g + "D")
        S[g + "/" + a] = [round((G[i] / A[i] - 1) * 100, 3) if i in A and i in G else None for i in idx]
    p, d, c, gp, gd = serie("AL30"), serie("AL30D"), serie("AL30C"), serie("GD30"), serie("GD30D")
    S["canje"] = [round((d[i] / c[i] - 1) * 100, 3) if i in d and i in c else None for i in idx]
    S["mep_gd_al"] = [round(((gp[i] / gd[i]) / (p[i] / d[i]) - 1) * 100, 3) if all(i in x for x in (p, d, gp, gd)) else None for i in idx]
    out = {"dates": [dates[i] for i in idx], "s": S}
    with open(os.path.join(D, "relativos.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print("relativos: %d ruedas, %d series" % (len(idx), len(S)))


if __name__ == "__main__":
    main()
