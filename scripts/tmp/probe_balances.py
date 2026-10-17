#!/usr/bin/env python3
"""Descarga temporal de estados contables de la CNV (se borra). Deja todo en tmp_cnv/."""
import re, os, json, html as H, urllib.request, time
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CUIT = {"ALUA": "30522780606", "BBAR": "30500003193", "BMA": "30500010084", "BYMA": "30715214147", "CEPU": "33650305499",
        "COME": "30501062150", "CRES": "30509300700", "EDN": "30655116202", "GGAL": "30704962807", "IRSA": "30525322749",
        "LOMA": "30500530851", "METR": "30657863676", "PAMP": "30526552659", "SUPV": "33500005179", "TECO2": "30639453738",
        "TGNO4": "30657863056", "TGSU2": "30657862068", "TRAN": "30663145926", "TXAR": "30516888248", "VALO": "30710914518",
        "YPFD": "30546689979"}
OUT = "tmp_cnv"; os.makedirs(OUT, exist_ok=True)
def get(url, binary=False):
    for k in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
            b = r.read()
            return r.status, (b if binary else b.decode("utf8", "replace"))
        except Exception as e:
            err = e; time.sleep(3)
    return 0, str(err)
txt = lambda s: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
res = {}
first = True
for t, c in CUIT.items():
    st, h = get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/" + c)
    if first:
        first = False
        js = sorted(set(re.findall(r'["\'](/SitioWeb/[A-Za-z/]+(?:Buscar|Search|Autocomplete|Empresas)[A-Za-z/]*)["\']', h)))
        res["_js"] = js
    m = re.search(r'<div id="container-res".*?<h1>(.*?)</h1>', h, re.S)
    name = txt(m.group(1)) if m else None
    i = h.find(">Estados Contables<")
    rows = []
    if i > 0:
        sec = h[i:h.find("</table>", i)]
        for tr in re.findall(r"<tr>(.*?)</tr>", sec, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            ln = re.search(r'EstadosContables\?presentacionId=(\d+)&amp;cucnv=(\d+)', tr)
            pv = re.search(r'presentations/publicview/([0-9a-f-]+)', tr)
            if len(tds) >= 4:
                rows.append({"fecha": txt(tds[0]), "desc": txt(tds[2]), "doc": txt(tds[3]), "xls": ln.groups() if ln else None, "pv": pv.group(1) if pv else None})
    own = [r for r in rows if "CONTROLADAS Y VINCULADAS" not in r["desc"]]
    res[t] = {"cuit": c, "status": st, "name": name, "n": len(rows), "own": own[:40]}
    print(t, st, name, len(rows), len(own))
    os.makedirs(os.path.join(OUT, t), exist_ok=True)
    for r in own[:10]:
        if r["xls"]:
            p, cu = r["xls"]
            s2, b = get("https://www.cnv.gov.ar/SitioWeb/Reportes/EstadosContables?presentacionId=%s&cucnv=%s" % (p, cu), True)
            if s2 == 200 and isinstance(b, bytes):
                open(os.path.join(OUT, t, "%s.xlsx" % p), "wb").write(b)
json.dump(res, open(os.path.join(OUT, "index.json"), "w"), ensure_ascii=False, indent=1)
