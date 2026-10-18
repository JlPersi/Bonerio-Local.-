"""Sondeo temporal 3: endpoints de caución de A3/MAE. Sin credenciales."""
import json, os, re, urllib.request
OUT = "tmp_out"; os.makedirs(OUT, exist_ok=True)
def req(u, t=40, h=None):
    hh = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*", "Origin": "https://marketdata.mae.com.ar", "Referer": "https://marketdata.mae.com.ar/"}; hh.update(h or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=hh), timeout=t) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, str(e)[:300]
res = {}
for f in ("cauciones-DXQgoFr0.js", "cauciones-az370nHs.js", "useHistoricData-DjjkRpIu.js", "historical-data-context-D3rw2pou.js", "caucionesWidgets-ClADJlb0.js", "useTitles-BBe08nU6.js"):
    st, js = req("https://marketdata.mae.com.ar/assets/" + f)
    res[f] = {"st": st, "len": len(js), "strs": sorted(set(re.findall(r'["`]([^"`]{0,80}(?:/|\$\{)[^"`]{0,120})["`]', js)))[:150]}
json.dump(res, open(OUT + "/tasas3.json", "w"), indent=1, ensure_ascii=False)
