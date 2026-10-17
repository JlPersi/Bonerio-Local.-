#!/usr/bin/env python3
"""Sondeo temporal de la CNV (se borra)."""
import re, html as H, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90)
        return r.status, r.read().decode("utf8", "replace")
    except Exception as e:
        return 0, str(e)
st, h = get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30546689979")
opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', h)
print("opciones", len(opts))
PAT = r"(?i)galicia|aluar|bbva|macro|byma|bolsas y mercados|central puerto|comercial del plata|cresud|edenor|empresa distribuidora y comercializadora norte|irsa|loma negra|metrogas|pampa energ|supervielle|telecom arg|transportadora de gas|transener|compa..a de transporte de energ|ternium|siderar|valores|ypf"
for v, n in opts:
    if re.search(PAT, n): print("  OPT", v, "|", H.unescape(n).strip())
i = h.find("Estados Contables")
print(re.sub(r"\s+", " ", h[i:i+3000]))
links = re.findall(r'/SitioWeb/Reportes/EstadosContables\?presentacionId=(\d+)&amp;cucnv=(\d+)', h)
print("YPF EC", len(links), links[:3])
if links:
    p, c = links[0]
    st, r = get("https://www.cnv.gov.ar/SitioWeb/Reportes/EstadosContables?presentacionId=%s&cucnv=%s" % (p, c))
    t = re.sub(r"[ \t]+", " ", H.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", "", r))))
    t = re.sub(r"\n\s*\n+", "\n", t)
    print("REPORTE", st, len(r)); print(t[:9000])
