"""Sondeo temporal 5: API de A3 para cauciones. Sin credenciales."""
import json, os, urllib.request, urllib.parse
OUT = "tmp_out"; os.makedirs(OUT, exist_ok=True)
def req(u, t=60):
    hh = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*", "Origin": "https://marketdata.mae.com.ar", "Referer": "https://marketdata.mae.com.ar/"}
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=hh), timeout=t) as x:
            return x.status, x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, str(e)[:300]
B = "https://api.marketdata.mae.com.ar/api/"
q = lambda o: urllib.parse.quote(json.dumps(o))
res = {}
calls = ["mercado/datos/cauciones", "mercado/datos/caucion", "mercado/datos/CAU", "mercado/fechahabilanterior?fecha=2026-10-18",
         "mercado/cauciones/valorescierre/volumentasas?oTitulo=" + q({"fechaDesde": "2026-10-01", "fechaHasta": "2026-10-17"}),
         "mercado/cauciones/valorescierre/volumentasas?oTitulo=" + q({"fecha": "2026-10-16"}),
         "mercado/cauciones/valorescierre/volumentasas?oTitulo=" + q({}),
         "mercado/titulo/historicocauciones?oTitulo=" + q({"fechaDesde": "2026-10-14", "fechaHasta": "2026-10-16"}),
         "mercado/titulo/historicocaucion?oTitulo=" + q({"fechaDesde": "2026-10-14", "fechaHasta": "2026-10-16"}),
         "mercado/titulo/historicocauciones?oTitulo=" + q({"fechaDesde": "2026-10-14", "fechaHasta": "2026-10-16", "skip": 0, "take": 50}),
         "mercado/resumen/cauciones", "mercado/estado"]
for u in calls:
    st, b = req(B + u); res[u] = [st, len(b), b[:2500]]
json.dump(res, open(OUT + "/tasas5.json", "w"), indent=1, ensure_ascii=False)
