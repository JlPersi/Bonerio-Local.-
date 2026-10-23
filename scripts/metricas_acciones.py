#!/usr/bin/env python3
"""Métricas de precio de cada acción a partir de data/acciones/<TICKER>.json -> data/acciones/metricas.json.

Por ticker, en pesos y en dólares CCL (el CCL sale de AL30 / AL30C de data/volumen.json, desde agosto de 2023):
- último precio y fecha, retornos 1 rueda, 1 semana, 1 mes, 3 meses, 1 año y en el año (YTD)
- volatilidad anualizada (desvío de los retornos logarítmicos diarios × √252) con 20, 60 y 252 ruedas
- caída desde el máximo histórico y máxima caída de los últimos 12 meses
- beta y correlación contra el panel líder (promedio simple de los retornos diarios de sus acciones, aproximación del Merval)
  en las últimas 252 ruedas en común
- volumen promedio de 20 ruedas (en la unidad de data912)
Además guarda el índice del panel líder (base 100) en pesos y en CCL, para graficar.
Los retornos solo usan ruedas consecutivas guardadas; las ruedas sin precio no se rellenan.
"""
import json, os, math, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "..", "data", "acciones")
SKIP = {"index.json", "saltos.json", "metricas.json", "ratios.json"}


def ccl_series():
    try:
        v = json.load(open(os.path.join(HERE, "..", "data", "volumen.json")))
    except Exception:
        return {}
    def ser(tk):
        o = v["t"].get(tk); out = {}; acc = 0
        if not o:
            return out
        for k, i in enumerate(o["i"]):
            acc += i
            if o["c"][k] and o["c"][k] > 0:
                out[v["dates"][acc]] = o["c"][k]
        return out
    a, c = ser("AL30"), ser("AL30C")
    return {d: a[d] / c[d] for d in a if d in c}


def stdev(x):
    n = len(x)
    if n < 2:
        return None
    m = sum(x) / n
    return math.sqrt(sum((y - m) ** 2 for y in x) / (n - 1))


def rets(px):
    """px: lista [(fecha, precio)] ordenada -> dict fecha -> retorno log respecto de la rueda guardada anterior."""
    return {d1: math.log(p1 / p0) for (d0, p0), (d1, p1) in zip(px, px[1:]) if p0 > 0 and p1 > 0}


def stats(px, idx_r):
    if len(px) < 2:
        return None
    d_last, p_last = px[-1]
    r = rets(px); rl = [r[d] for d, _ in px[1:] if d in r]
    def back(n):
        return round(p_last / px[-1 - n][1] - 1, 6) if len(px) > n else None
    y0 = [p for d, p in px if d < d_last[:4] + "-01-01"]
    mx = max(p for _, p in px)
    last252 = [p for _, p in px[-253:]]
    peak, mdd = 0, 0
    for p in last252:
        peak = max(peak, p); mdd = min(mdd, p / peak - 1)
    vol = {}
    for n in (20, 60, 252):
        s = stdev(rl[-n:]) if len(rl) >= min(n, 15) else None
        vol[str(n)] = round(s * math.sqrt(252), 6) if s else None
    beta = corr = None
    common = [d for d, _ in px[1:] if d in r and d in idx_r][-252:]
    if len(common) >= 40:
        a = [r[d] for d in common]; b = [idx_r[d] for d in common]
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (len(a) - 1)
        va, vb = stdev(a) ** 2, stdev(b) ** 2
        if vb > 0:
            beta = round(cov / vb, 4)
            corr = round(cov / math.sqrt(va * vb), 4) if va > 0 else None
    return {"fecha": d_last, "precio": round(p_last, 4),
            "ret": {"1d": back(1), "1s": back(5), "1m": back(21), "3m": back(63), "1a": back(252),
                    "ytd": round(p_last / y0[-1] - 1, 6) if y0 else None},
            "vol": vol, "dd_max": round(p_last / mx - 1, 6), "mdd_12m": round(mdd, 6),
            "beta": beta, "corr": corr, "n": len(px)}


def index_from(series, members):
    """Promedio simple de retornos log diarios de los miembros -> (retornos, nivel base 100)."""
    acc = {}
    for t in members:
        for d, x in rets(series[t]).items():
            acc.setdefault(d, []).append(x)
    r = {d: sum(v) / len(v) for d, v in acc.items() if len(v) >= max(3, len(members) // 3)}
    lvl, out = 100.0, []
    for d in sorted(r):
        lvl *= math.exp(r[d]); out.append([d, round(lvl, 4)])
    return r, out


def main():
    ccl = ccl_series()
    ars, usd, meta = {}, {}, {}
    for fn in sorted(os.listdir(DIR)):
        if not fn.endswith(".json") or fn in SKIP:
            continue
        o = json.load(open(os.path.join(DIR, fn)))
        px = [(r[0], r[4]) for r in o.get("r", []) if r[4] and r[4] > 0]
        if len(px) < 2:
            continue
        t = o["t"]; ars[t] = px; meta[t] = o
        usd[t] = [(d, p / ccl[d]) for d, p in px if d in ccl]
    lider = [t for t in ars if meta[t].get("panel") == "lider"]
    ir_a, il_a = index_from(ars, lider) if lider else ({}, [])
    ir_u, il_u = index_from(usd, [t for t in lider if len(usd[t]) > 1]) if lider else ({}, [])
    out = {"generado": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "indice_lider": {"ars": il_a, "ccl": il_u}, "t": {}}
    for t, px in ars.items():
        rows = meta[t]["r"]
        v20 = [r[5] for r in rows[-20:] if r[5]]  # en la unidad que manda data912 (confirmar si es cantidad de acciones o pesos)
        out["t"][t] = {"panel": meta[t].get("panel"), "ars": stats(px, ir_a), "ccl": stats(usd[t], ir_u),
                       "vol_prom_20": round(sum(v20) / len(v20)) if v20 else None,
                       "u": [[r[0], r[4], r[5]] for r in rows[-41:] if r[4] and r[4] > 0]}  # últimas ruedas (fecha, cierre, volumen) para Variación diaria
    json.dump(out, open(os.path.join(DIR, "metricas.json"), "w"), separators=(",", ":"))
    print("métricas de %d tickers (%d del panel líder), CCL con %d ruedas" % (len(out["t"]), len(lider), len(ccl)))


if __name__ == "__main__":
    main()
