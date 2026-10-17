#!/usr/bin/env python3
"""Sondeo temporal: autocompletar de empresas de la CNV (se borra)."""
import re, os, json, urllib.request, urllib.parse
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "X-Requested-With": "XMLHttpRequest"}
def get(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf8", "replace")
    except Exception as e:
        return "ERR %s" % e
out = {}
js = get("https://www.cnv.gov.ar/SitioWeb/Content/assets/js/main.js")
i = js.find('Empresas/AutoComplete')
out["bloque"] = js[max(0, i - 1500): i + 1500]
m = re.search(r'Empresas/AutoComplete(\w*)"', js)
path = "Empresas/AutoComplete" + (m.group(1) if m else "")
blk = js[i: i + 800]
pm = re.search(r"data\s*:\s*\{\s*['\"]?(\w+)['\"]?\s*:", blk)
param = pm.group(1) if pm else "term"
out["path"], out["param"] = path, param
res = {}
for q in ["Transener", "Bolsas y Mercados", "Grupo Supervielle", "Comercial del Plata", "Valores", "Ternium"]:
    for p in [param, "term", "prefix", "q"]:
        r = get("https://www.cnv.gov.ar/SitioWeb/%s?%s" % (path, urllib.parse.urlencode({p: q})))
        if not r.startswith("ERR") and len(r) > 5:
            res[q] = (p, r[:3000]); break
        res[q] = (p, r[:300])
out["res"] = res
os.makedirs("tmp_cnv", exist_ok=True)
json.dump(out, open("tmp_cnv/buscar2.json", "w"), ensure_ascii=False, indent=1)
