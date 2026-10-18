import json, os, urllib.request, urllib.parse, datetime as dt, time
out = {}
def get(u):
    h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=60))
try:
    q = urllib.parse.urlencode({"product": "DLR", "type": "FUT", "from": "2026-10-15", "to": "2026-10-16"})
    r = get("https://apicem.matbarofex.com.ar/api/v2/closing-prices?" + q)
    out["a3_keys"] = list((r.get("data") or [{}])[0].keys()); out["a3_rows"] = (r.get("data") or [])[:3]
except Exception as e: out["a3_err"] = str(e)[:300]
U, P = os.environ.get("ROFEX_USER", "").strip(), os.environ.get("ROFEX_PASS", "").strip()
try:
    import pyRofex
    url = (os.environ.get("ROFEX_URL") or "").strip().rstrip("/")
    env = pyRofex.Environment.LIVE
    pyRofex._set_environment_parameter("url", url + "/", env)
    pyRofex._set_environment_parameter("ws", url.replace("https://", "wss://") + "/", env)
    pyRofex.initialize(user=U, password=P, account="", environment=env)
    E = pyRofex.MarketDataEntry
    out["entries"] = [e.name for e in E]
    for s in ["DLR/NOV26", "MERV - XMEV - PESOS - 3D", "MERV - XMEV - DOLAR - 3D"]:
        try: out["md_" + s] = pyRofex.get_market_data(ticker=s, entries=list(E), environment=env)
        except Exception as e: out["md_" + s] = str(e)[:200]
    try:
        r = pyRofex.get_trade_history(ticker="DLR/NOV26", start_date=dt.date(2026,10,16), end_date=dt.date(2026,10,16), environment=env)
        tr = r.get("trades") or []
        out["hist_n"] = len(tr); out["hist_sample"] = tr[:3]
    except Exception as e: out["hist_err"] = str(e)[:300]
    try:
        r = pyRofex.get_trade_history(ticker="MERV - XMEV - PESOS - 3D", start_date=dt.date(2026,10,16), end_date=dt.date(2026,10,16), environment=env)
        tr = r.get("trades") or []
        out["hist_cau_n"] = len(tr); out["hist_cau_sample"] = tr[:3]
    except Exception as e: out["hist_cau_err"] = str(e)[:300]
except Exception as e:
    m = str(e)
    for x in (U, P):
        if x: m = m.replace(x, "<x>")
    out["rofex_err"] = m[:300]
s = json.dumps(out, indent=1, default=str)
for x in (U, P):
    if x: s = s.replace(x, "<x>")
os.makedirs("probe/out", exist_ok=True); open("probe/out/p.json", "w").write(s)
