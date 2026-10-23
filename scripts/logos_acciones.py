#!/usr/bin/env python3
"""Logos redondos de las acciones (los de TradingView) en data/logos/<TICKER>.svg y la lista en data/logos.json.
Para cada ticker de data/acciones/index.json busca su logoid en el buscador de TradingView (BYMA primero) y baja el SVG.
Lo que no encuentra queda afuera y la página usa el logo de antes. Un logo cargado a mano (data/logos/BPAT.jpg con
"BPAT": "BPAT.jpg" en logos.json) se respeta."""
import json, os, re, time, urllib.request, urllib.parse

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
OUT = os.path.join(DATA, "logos")
H = {"User-Agent": "Mozilla/5.0", "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}


def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30).read()


def logoid(t):
    for ex in ("BCBA", ""):
        q = {"text": t, "hl": "0", "lang": "es", "search_type": "stocks", "domain": "production"}
        if ex:
            q["exchange"] = ex
        try:
            r = json.loads(get("https://symbol-search.tradingview.com/symbol_search/v3/?" + urllib.parse.urlencode(q)))
        except Exception as e:
            print(t, ex, "búsqueda falló:", e); continue
        syms = r.get("symbols", r) if isinstance(r, dict) else r
        for s in syms or []:
            sym = re.sub(r"<[^>]+>", "", s.get("symbol", ""))
            lid = s.get("logoid") or (s.get("logo") or {}).get("logoid")
            if lid and sym == t:
                return lid
    return None


os.makedirs(OUT, exist_ok=True)
idx = json.load(open(os.path.join(DATA, "acciones", "index.json")))
try:  # los que se cargaron a mano (un archivo con extensión, como BPAT.jpg) no se pisan
    done = {k: v for k, v in json.load(open(os.path.join(DATA, "logos.json"))).items() if "." in v}
except Exception:
    done = {}
for t in sorted({x["t"] for x in idx} - set(done)):
    lid = logoid(t)
    if not lid:
        print(t, "sin logo"); continue
    try:
        svg = get("https://s3-symbol-logo.tradingview.com/%s--big.svg" % lid)
    except Exception as e:
        print(t, lid, "no se pudo bajar:", e); continue
    if b"<svg" not in svg[:500]:
        print(t, lid, "no es svg"); continue
    open(os.path.join(OUT, t + ".svg"), "wb").write(svg)
    done[t] = lid
    time.sleep(0.3)
json.dump(done, open(os.path.join(DATA, "logos.json"), "w"), separators=(",", ":"), sort_keys=True)
print("logos: %d de %d" % (len(done), len(idx)))
