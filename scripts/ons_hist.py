#!/usr/bin/env python3
"""Historia diaria de las ONs y provinciales en dólares (MEP y cable) desde los datos abiertos de BYMA, para completar data/volumen.json
(que tiene ONs recién desde oct-26, cuando se empezó a guardar arg_corp de data912).

Para cada especie D y C de data/ons.json y data/pvs.json baja la serie diaria (cierre y volumen nominal) del gráfico de BYMA y la carga en
volumen.json solo en las ruedas que ya tiene el archivo y donde falta el dato: lo guardado por el cierre nunca se pisa. Si en las ruedas
en común el precio de BYMA no coincide con el guardado (±10%), esa especie se deja afuera.
Uso: python3 scripts/ons_hist.py [--max N]   (corre en el Action "ONs: completar historia"; desde el sandbox BYMA no responde)
"""
import json, os, sys, time, statistics, urllib.request, urllib.parse, datetime as dt

D = os.path.join(os.path.dirname(__file__), "..", "data")
URL = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/chart/historical-series/history"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://open.bymadata.com.ar", "Referer": "https://open.bymadata.com.ar/"}
PLAZOS = ["24HS", "CI", "48HS"]


def get(sym, t0, t1):
    q = urllib.parse.urlencode({"symbol": sym, "resolution": "D", "from": t0, "to": t1})
    with urllib.request.urlopen(urllib.request.Request(URL + "?" + q, headers=H), timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def serie(sym, t0, t1, log=False):
    """{fecha: (cierre, volumen)} juntando los plazos (24 hs primero); vacío si BYMA no la tiene."""
    out = {}
    for pl in PLAZOS:
        try:
            j = get(f"{sym} {pl}", t0, t1)
        except Exception as e:
            if log:
                print(sym, pl, "error", str(e)[:120])
            continue
        if log:
            print(sym, pl, str(j)[:200])
        if not isinstance(j, dict) or j.get("s") != "ok":
            continue
        for t, c, v in zip(j.get("t", []), j.get("c", []), j.get("v", []) or [0] * len(j.get("t", []))):
            d = dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
            if c and c > 0 and d not in out:
                out[d] = (float(c), float(v or 0))
        time.sleep(.1)
        if out:  # con 24 hs alcanza: los otros plazos casi nunca tienen operaciones
            break
    return out


def main():
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10 ** 6
    V = json.load(open(os.path.join(D, "volumen.json")))
    dates = V["dates"]
    ix = {d: i for i, d in enumerate(dates)}
    syms = []
    for f in ("ons.json", "pvs.json"):
        for k, o in ((json.load(open(os.path.join(D, f))) or {}).get("on") or {}).items():
            if o.get("t") not in (None, "usd") and f == "ons.json":
                continue
            syms += [o.get("d") or k + "D", o.get("c") or k + "C"]
    syms = list(dict.fromkeys(syms))[:mx]
    t0 = int(dt.datetime.fromisoformat(dates[0]).timestamp()) - 86400
    t1 = int(time.time()) + 86400
    print(len(syms), "especies;", "prueba:")
    serie(syms[0], t0, t1, log=True)
    ok = sk = vac = 0
    for n_, s in enumerate(syms):
        S = serie(s, t0, t1)
        if not S:
            vac += 1
            continue
        o = V["t"].get(s) or {"s": s[-1], "i": [], "v": [], "e": [], "c": []}
        cur, acc = {}, 0
        for di, v, e, c in zip(o["i"], o["v"], o["e"], o["c"]):
            acc += di
            cur[acc] = (v, e, c)
        com = [S[dates[i]][0] / cur[i][2] for i in cur if dates[i] in S and cur[i][2]]
        if com:
            r = statistics.median(com)
            if 0.007 < r < 0.013:  # BYMA por 1 de nominal
                S = {d: (c * 100, v) for d, (c, v) in S.items()}
            elif not 0.9 < r < 1.1:
                sk += 1
                print("no coincide", s, round(r, 3))
                continue
        add = 0
        for d, (c, v) in S.items():
            i = ix.get(d)
            if i is None or i in cur:
                continue
            cur[i] = (round(v), round(v * c / 100), c)
            add += 1
        if not add:
            continue
        ks = sorted(cur)
        o["i"] = [k - (ks[j - 1] if j else 0) for j, k in enumerate(ks)]
        o["v"], o["e"], o["c"] = [cur[k][0] for k in ks], [cur[k][1] for k in ks], [cur[k][2] for k in ks]
        V["t"][s] = o
        ok += 1
        if n_ % 50 == 0:
            print(n_, s, "+", add)
    print("con historia", ok, "| sin datos en BYMA", vac, "| precio distinto", sk)
    if ok:
        json.dump(V, open(os.path.join(D, "volumen.json"), "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
