import json, os, urllib.request, urllib.parse
OUT = "probe/out3"; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://marketdata.mae.com.ar", "Referer": "https://marketdata.mae.com.ar/"}
def get(url, t=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=t) as f:
        return f.read()
log = []
for d in ["2015-03-02", "2018-03-01", "2020-03-02", "2021-03-01", "2022-03-01", "2023-03-01", "2024-03-01", "2024-09-02"]:
    a = d; b = d[:8] + "%02d" % (int(d[8:]) + 6)
    try:
        q = urllib.parse.quote(json.dumps({"fechaDesde": a, "fechaHasta": b}))
        j = json.loads(get("https://api.marketdata.mae.com.ar/api/mercado/titulo/historicocauciones?oTitulo=" + q))
        n = sum(len(x.get("details") or []) for x in j); mon = sorted(set(r.get("moneda") for x in j for r in x.get("details") or []))
        smp = [(r["descripcion"], r["tasaPP"], r["montoConcertado"]) for x in j[:1] for r in (x.get("details") or [])[:4]]
        log.append("CAU %s: %d días, %d filas, monedas %s %s" % (d, len(j), n, mon, smp))
    except Exception as e:
        log.append("CAU %s ERR %s" % (d, e))
    for prod in ["DLR", "Tasa de Caución"]:
        try:
            q = urllib.parse.urlencode({"product": prod, "type": "FUT", "from": a, "to": b})
            j = json.loads(get("https://apicem.matbarofex.com.ar/api/v2/closing-prices?" + q)).get("data", [])
            log.append("  %s %s: %d filas %s" % (prod, d, len(j), sorted(set(r["symbol"] for r in j))[:8]))
        except Exception as e:
            log.append("  %s %s ERR %s" % (prod, d, e))
open(os.path.join(OUT, "log.txt"), "w").write("\n".join(log))
