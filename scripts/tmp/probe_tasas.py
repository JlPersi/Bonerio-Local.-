"""Sondeo temporal 3: endpoints de caución de A3/MAE. Sin credenciales."""
import json, os, re, urllib.request, urllib.parse
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
for f in ("history-service-CA9Ln2Wy.js", "title-service-kUUUrdIx.js", "price-VhhV66PB.js", "page-muF-wEik.js"):
    st, js = req("https://marketdata.mae.com.ar/assets/" + f)
    res[f] = {"st": st, "len": len(js), "strs": sorted(set(re.findall(r'["`]([^"`]{0,80}(?:/|\$\{)[^"`]{0,120})["`]', js)))[:150]}
B = "https://api.marketdata.mae.com.ar/api/"
for u in ("mercado/cauciones", "cauciones/historico", "mercado/cauciones/historico", "mercado/especieplazos?oTitulo=" + urllib.parse.quote(json.dumps({"codTitulo": "CAARS"})),
          "titulos/CAU/CAARS?plazo=003&segmento=K&moneda=%24&fechaLiquidacion=2026-10-19T00:00:00", "mercado/titulo/forexofertas"):
    st, b = req(B + u); res["call " + u] = [st, b[:1500]]
for f in ("history-service-CA9Ln2Wy.js", "title-service-kUUUrdIx.js"):
    st, js = req("https://marketdata.mae.com.ar/assets/" + f); res["raw " + f] = js[:6000]
json.dump(res, open(OUT + "/tasas3.json", "w"), indent=1, ensure_ascii=False)
