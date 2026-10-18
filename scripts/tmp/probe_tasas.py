"""Sondeo temporal de fuentes para Tasas cortas. No imprime ni guarda credenciales."""
import json, os, re, datetime as dt, urllib.request, urllib.parse, pyRofex
OUT = "tmp_out"; os.makedirs(OUT, exist_ok=True)
U, P = os.environ.get("ROFEX_USER", "").strip(), os.environ.get("ROFEX_PASS", "").strip()
url = (os.environ.get("ROFEX_URL") or "https://api.bull.xoms.com.ar").strip().rstrip("/")
def clean(m):
    for x in (U, P):
        if x: m = m.replace(x, "<x>")
    return m[:400]
def get(u, t=60):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t))
res = {}
# BCRA: lista de variables
try:
    v = get("https://api.bcra.gob.ar/estadisticas/v4.0/monetarias?limit=1000")
    res["bcra_vars"] = [(r.get("idVariable"), r.get("descripcion"), r.get("ultFechaInformada"), r.get("ultValorInformado"))
                        for r in v.get("results", []) if re.search(r"plazo|dep[oó]sit|badlar|tamar|cauci|pase", (r.get("descripcion") or ""), re.I)]
except Exception as e:
    res["bcra_err"] = str(e)[:300]
# A3 cierres
B = "https://apicem.matbarofex.com.ar/api/v2/closing-prices"
for prod in ("DLR", "Tasa de Caución"):
    try:
        q = urllib.parse.urlencode({"product": prod, "type": "FUT", "excludeEmptyVol": "false", "from": "2026-09-01", "to": "2026-10-18"})
        d = get(B + "?" + q, 120)["data"]
        res["a3_" + prod] = {"n": len(d), "sample": d[:3], "dates": sorted({r["dateTime"][:10] for r in d})[-5:]}
    except Exception as e:
        res["a3_err_" + prod] = str(e)[:300]
try:
    q = urllib.parse.urlencode({"product": "DLR", "type": "FUT", "from": "2026-10-15", "to": "2026-10-17", "page": 1, "pageSize": 5000})
    res["a3_paged"] = len(get(B + "?" + q)["data"])
except Exception as e:
    res["a3_paged_err"] = str(e)[:200]
# Primary
env = pyRofex.Environment.LIVE
try:
    pyRofex._set_environment_parameter("url", url + "/", env)
    pyRofex._set_environment_parameter("ws", url.replace("https://", "wss://") + "/", env)
    pyRofex.initialize(user=U, password=P, account="", environment=env)
    items = pyRofex.get_detailed_instruments(environment=env).get("instruments", [])
    by = {(i.get("instrumentId") or {}).get("symbol", ""): i for i in items}
    dlr = sorted(s for s in by if re.fullmatch(r"DLR/[A-Z]{3}\d{2}", s))
    cauc = sorted(s for s in by if re.fullmatch(r"CAUC/[A-Z]{3}\d{2}", s))
    pes = sorted((s for s in by if re.fullmatch(r"MERV - XMEV - PESOS - \d+D", s)), key=lambda s: int(s.split("-")[-1].strip()[:-1]))
    res["dlr"], res["cauc"], res["pesos"] = dlr, cauc, pes
    res["detail_dlr"] = by.get(dlr[0]) if dlr else None
    res["detail_pes"] = by.get(pes[0]) if pes else None
    res["detail_cauc"] = by.get(cauc[0]) if cauc else None
    E = pyRofex.MarketDataEntry
    ents = [E.BIDS, E.OFFERS, E.LAST, E.CLOSING_PRICE, E.SETTLEMENT_PRICE, E.OPEN_INTEREST, E.TRADE_VOLUME, E.OPENING_PRICE, E.HIGH_PRICE, E.LOW_PRICE, E.NOMINAL_VOLUME, E.TRADE_EFFECTIVE_VOLUME]
    md = {}
    for s in dlr + cauc + pes[:12]:
        try:
            md[s] = pyRofex.get_market_data(ticker=s, entries=ents, environment=env).get("marketData")
        except Exception as e:
            md[s] = clean(str(e))
    res["md"] = md
    tr = {}
    d1 = dt.date.today(); d0 = d1 - dt.timedelta(days=6)
    for s in pes[:3] + dlr[:1]:
        try:
            t = pyRofex.get_trade_history(ticker=s, start_date=d0, end_date=d1, environment=env)
            tr[s] = {"n": len(t.get("trades", [])), "sample": t.get("trades", [])[-3:], "status": t.get("status")}
        except Exception as e:
            tr[s] = clean(str(e))
    res["trades"] = tr
except Exception as e:
    res["primary_err"] = clean(type(e).__name__ + ": " + str(e))
json.dump(res, open(OUT + "/tasas.json", "w"), indent=1, ensure_ascii=False, default=str)
