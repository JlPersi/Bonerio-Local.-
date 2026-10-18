"""Sondeo temporal 2: fuentes de caución. Sin credenciales."""
import json, os, re, ssl, urllib.request
OUT = "tmp_out"; os.makedirs(OUT, exist_ok=True)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
def req(u, data=None, h=None, t=40):
    hh = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*"}; hh.update(h or {})
    r = urllib.request.Request(u, data=json.dumps(data).encode() if data is not None else None, headers=hh, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=t, context=ctx) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, str(e)[:300]
res = {}
B = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/"
for ep in ("cauciones", "short-term-government-bonds"):
    st, b = req(B + ep, {"excludeZeroPxAndQty": False, "T2": True, "T1": False, "T0": False}, {"Content-Type": "application/json", "Origin": "https://open.bymadata.com.ar", "Referer": "https://open.bymadata.com.ar/"})
    res["byma_" + ep] = [st, b[:3000]]
st, b = req("https://marketdata.mae.com.ar/titulos/CAU/CAARS?plazo=003&segmento=K&moneda=$&fechaLiquidacion=2026-10-19T00:00:00", h={"Accept": "text/html"})
res["mae_page"] = [st, len(b), re.findall(r'(?:src|href)="([^"]+\.js[^"]*)"', b)[:20], re.findall(r'https?://[a-zA-Z0-9.\-]*mae[a-zA-Z0-9.\-/]*', b)[:30], b[:1500]]
for u in ("https://api.marketdata.mae.com.ar/api/mercado/cauciones", "https://marketdata.mae.com.ar/api/mercado/cauciones",
          "https://api.marketdata.mae.com.ar/api/cotizaciones/cauciones", "https://marketdata.mae.com.ar/api/titulos/CAU/CAARS?plazo=003&segmento=K&moneda=$"):
    res[u] = list(req(u))[:2]
    res[u][1] = res[u][1][:800]
json.dump(res, open(OUT + "/tasas2.json", "w"), indent=1, ensure_ascii=False)
