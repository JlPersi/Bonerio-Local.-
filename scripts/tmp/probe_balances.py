#!/usr/bin/env python3
"""Sondeo temporal de la CNV (se borra)."""
import re, urllib.request, collections
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)
        return r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:400], url
    except Exception as e:
        return 0, str(e).encode(), url
for cuit in ["30546689979", "30500001735"]:
    st, b, fu = get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/" + cuit)
    h = b.decode("utf8", "replace")
    print("==", cuit, st, len(h), fu)
    t = re.search(r"<title>(.*?)</title>", h, re.S); print("title", t and t.group(1).strip()[:120])
    for m in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", h, re.S)[:30]:
        print("  H", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m)).strip()[:100])
    links = re.findall(r'href="([^"#]+)"', h)
    c = collections.Counter(re.sub(r"\d+", "N", l)[:90] for l in links)
    for k, v in c.most_common(40): print("  L", v, k)
    for l in links:
        if re.search(r"(?i)financ|balance|estado|contab|\.pdf|Descarga|Documento", l):
            print("  F", l[:200])
    i = h.find("Financier"); print("CTX", re.sub(r"\s+", " ", h[max(0, i-1500):i+2500]) if i > 0 else "sin 'Financier'")
