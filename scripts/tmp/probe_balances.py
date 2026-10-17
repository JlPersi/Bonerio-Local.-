#!/usr/bin/env python3
"""Sondeo temporal: CUIT de las empresas que faltan (se borra)."""
import re, os, json, html as H, urllib.request, time
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf8", "replace")
    except Exception as e:
        return "ERR %s" % e
txt = lambda s: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
out = {}
h = get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30546689979")
srcs = sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', h)))
out["srcs"] = srcs
hits = []
for s in srcs:
    if s.startswith("http") and "cnv.gov.ar" not in s:
        continue
    u = s if s.startswith("http") else "https://www.cnv.gov.ar" + (s if s.startswith("/") else "/SitioWeb/" + s)
    js = get(u)
    for m in re.finditer(r"(?i)(url\s*:\s*[^,]{0,200}|\$\.(get|post|ajax|getJSON)\([^)]{0,200})", js):
        hits.append((s, m.group(0)[:250]))
out["ajax"] = hits[:80]
# formulario de búsqueda de la página
i = h.find("Elegí la empresa")
out["form"] = h[i:i + 2500] if i > 0 else None
cand = {"TRAN": ["30663145920"], "TXAR": ["30516888241"], "BYMA": ["30714976113", "30715214144"],
        "VALO": ["30710914512", "30709101451"], "SUPV": ["30708134240"], "COME": ["30501493029"]}
res = {}
for t, cs in cand.items():
    for c in cs:
        p = get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/" + c)
        m = re.search(r'<div id="container-res".*?<h1>(.*?)</h1>', p, re.S)
        res[c] = (t, txt(m.group(1))[:120] if m else None)
        print(t, c, res[c][1])
out["cand"] = res
os.makedirs("tmp_cnv", exist_ok=True)
json.dump(out, open("tmp_cnv/buscar.json", "w"), ensure_ascii=False, indent=1)
