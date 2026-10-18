import json, os, re, time, urllib.request, urllib.parse, datetime as dt, subprocess
OUT = "probe/out"; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
def get(url, data=None, h=None, t=40):
    r = urllib.request.Request(url, data=data, headers=dict(H, **(h or {})))
    with urllib.request.urlopen(r, timeout=t) as f:
        return f.status, f.read()
log = []
def w(name, b):
    open(os.path.join(OUT, name), "wb").write(b if isinstance(b, bytes) else b.encode())
# 1) tablero BYMA
try:
    st, b = get("https://tablero.bymaeduca.com.ar/"); w("tablero.html", b); log.append("tablero %s %d" % (st, len(b)))
    html = b.decode("utf8", "ignore")
    for src in set(re.findall(r'(?:src|href)="([^"]+\.(?:js|json|css))"', html)):
        u = urllib.parse.urljoin("https://tablero.bymaeduca.com.ar/", src)
        try:
            st, bb = get(u); fn = re.sub(r"[^A-Za-z0-9._-]", "_", src)[-80:]; w("tb_" + fn, bb); log.append("  %s %s %d" % (u, st, len(bb)))
        except Exception as e:
            log.append("  %s ERR %s" % (u, e))
    for p in ["data/rf.json", "data.json", "data/tablero.json", "rf.json", "data/caucion.json"]:
        try:
            st, bb = get("https://tablero.bymaeduca.com.ar/" + p); log.append("  try %s %s %d %r" % (p, st, len(bb), bb[:120]))
        except Exception as e:
            log.append("  try %s ERR %s" % (p, e))
except Exception as e:
    log.append("tablero ERR %s" % e)
# 2) caución A3: monedas
try:
    d1 = dt.date.today(); d0 = d1 - dt.timedelta(days=12)
    q = urllib.parse.quote(json.dumps({"fechaDesde": d0.isoformat(), "fechaHasta": d1.isoformat()}))
    st, b = get("https://api.marketdata.mae.com.ar/api/mercado/titulo/historicocauciones?oTitulo=" + q, h={"Origin": "https://marketdata.mae.com.ar", "Referer": "https://marketdata.mae.com.ar/", "Accept": "application/json"})
    w("a3_cau.json", b); j = json.loads(b)
    mon = {}
    for day in j:
        for r in day.get("details") or []:
            mon.setdefault(r.get("moneda"), r)
    log.append("A3 monedas: %s" % json.dumps(mon, ensure_ascii=False)[:3000])
except Exception as e:
    log.append("A3 ERR %s" % e)
# 3) BYMA open data
BY = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/"
body = json.dumps({"excludeZeroPxAndQty": False, "T2": True, "T1": True, "T0": True, "Content-Type": "application/json"}).encode()
for ep in ["cauciones", "caucion", "repos", "simultaneas", "short-term-government-bonds", "lebacs", "public-bonds", "cauciones-tasas", "index-price"]:
    try:
        st, b = get(BY + ep, data=body, h={"Content-Type": "application/json", "Origin": "https://open.bymadata.com.ar", "Referer": "https://open.bymadata.com.ar/"})
        w("byma_" + ep + ".json", b); log.append("BYMA %s %s %d %r" % (ep, st, len(b), b[:300]))
    except Exception as e:
        log.append("BYMA %s ERR %s" % (ep, e))
# 4) data912
for ep in ["live/arg_repos", "live/arg_cauciones", "live/arg_notes", "live/arg_bonds"]:
    try:
        st, b = get("https://data912.com/" + ep); log.append("d912 %s %s %d %r" % (ep, st, len(b), b[:300]))
        if ep in ("live/arg_notes",): w("d912_notes.json", b)
    except Exception as e:
        log.append("d912 %s ERR %s" % (ep, e))
# 5) Primary: símbolos de caución y simultáneas
U, P = os.environ.get("ROFEX_USER", "").strip(), os.environ.get("ROFEX_PASS", "").strip()
if U and P:
    try:
        import pyRofex
        url = (os.environ.get("ROFEX_URL") or "https://api.bull.xoms.com.ar").strip().rstrip("/")
        env = pyRofex.Environment.LIVE
        pyRofex._set_environment_parameter("url", url + "/", env)
        pyRofex._set_environment_parameter("ws", url.replace("https://", "wss://") + "/", env)
        pyRofex.initialize(user=U, password=P, account="", environment=env)
        items = pyRofex.get_detailed_instruments(environment=env).get("instruments", [])
        syms = sorted((i.get("instrumentId") or {}).get("symbol", "") for i in items)
        pat = re.compile(r"XMEV|CAUC|SIMUL|PASE|REPO", re.I)
        sel = [s for s in syms if pat.search(s) and not s.startswith("CAUC/")]
        w("primary_syms.txt", "\n".join(sel))
        cfi = {}
        for i in items:
            s = (i.get("instrumentId") or {}).get("symbol", "")
            if pat.search(s):
                k = (i.get("cficode"), i.get("segment", {}).get("marketSegmentId") if isinstance(i.get("segment"), dict) else None, re.sub(r"\d+D$", "nD", s))
                cfi[str(k)] = cfi.get(str(k), 0) + 1
        w("primary_groups.json", json.dumps(cfi, indent=1))
        ex = [s for s in sel if "PESOS" not in s][:3] + [s for s in sel if "PESOS" in s][:1]
        E = pyRofex.MarketDataEntry
        md = {}
        for s in ex:
            try:
                md[s] = pyRofex.get_market_data(ticker=s, entries=[E.BIDS, E.OFFERS, E.LAST, E.CLOSING_PRICE, E.NOMINAL_VOLUME, E.TRADE_VOLUME], environment=env)
            except Exception as e:
                md[s] = str(type(e).__name__)
        w("primary_md.json", json.dumps(md, indent=1, default=str))
        smp = [i for i in items if (i.get("instrumentId") or {}).get("symbol", "") in ex]
        w("primary_inst.json", json.dumps(smp, indent=1, default=str))
        log.append("Primary %d símbolos, %d de caución/simult" % (len(syms), len(sel)))
    except Exception as e:
        m = type(e).__name__ + ": " + str(e)
        for x in (U, P):
            m = m.replace(x, "<x>")
        log.append("Primary ERR " + m[:300])
w("log.txt", "\n".join(log))
