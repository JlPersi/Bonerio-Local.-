#!/usr/bin/env python3
"""Descarga temporal de estados contables de la CNV (se borra). Deja todo en tmp_cnv/."""
import re, os, json, html as H, urllib.request, time
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CUIT = {"ALUA": "30522780606", "BBAR": "30500003193", "BMA": "30500010084", "CEPU": "33650305499",
        "CRES": "30509300700", "EDN": "30655116202", "GGAL": "30704962807", "IRSA": "30525322749",
        "LOMA": "30500530851", "METR": "30657863676", "PAMP": "30526552659", "TECO2": "30639453738",
        "TGNO4": "30657863056", "TGSU2": "30657862068", "YPFD": "30546689979"}
OUT = "tmp_cnv"; os.makedirs(OUT, exist_ok=True)
def get(url, binary=False):
    err = None
    for k in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
            b = r.read()
            return r.status, (b if binary else b.decode("utf8", "replace"))
        except Exception as e:
            err = e; time.sleep(3)
    return 0, str(err)
txt = lambda s: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def rows_of(h):
    i = h.find(">Estados Contables<")
    rows = []
    if i > 0:
        sec = h[i:h.find("</table>", i)]
        for tr in re.findall(r"<tr>(.*?)</tr>", sec, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            ln = re.search(r'EstadosContables\?presentacionId=(\d+)&amp;cucnv=(\d+)', tr)
            if len(tds) >= 4:
                rows.append({"fecha": txt(tds[0]), "desc": txt(tds[2]), "xls": ln.groups() if ln else None})
    return rows

# 1) buscar en la página dónde está la lista de empresas
st, h = get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/" + CUIT["YPFD"])
with open(os.path.join(OUT, "buscar.txt"), "w") as f:
    for m in re.finditer(r"(?i)supervielle|transener|ternium|comercial del plata|bolsas y mercados|financiero valores", h):
        f.write(h[max(0, m.start() - 400): m.end() + 200].replace("\n", " ") + "\n----\n")
    for s in re.findall(r"<script[^>]*>(.*?)</script>", h, re.S):
        if len(s) < 20000:
            f.write("SCRIPT " + s[:3000] + "\n====\n")
        else:
            f.write("SCRIPT LARGO %d %s\n====\n" % (len(s), s[:1500]))

# 2) bajar estados contables propios desde 2023-09
idx = {}
for t, c in CUIT.items():
    st, h = get("https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/" + c)
    rows = [r for r in rows_of(h) if "CONTROLADAS Y VINCULADAS" not in r["desc"] and r["xls"]]
    keep = []
    for r in rows:
        m = re.search(r"FECHA CIERRE: (\d{4}-\d\d-\d\d)", r["desc"])
        if not m or m.group(1) < "2023-09-30":
            continue
        r["cierre"] = m.group(1)
        r["tipo"] = "CONSOLIDADO" if "CONSOLIDADO" in r["desc"] else ("INDIVIDUAL" if "INDIVIDUAL" in r["desc"] else "?")
        pm = re.search(r"PERIODICIDAD: (\w+)", r["desc"]); r["periodicidad"] = pm.group(1) if pm else None
        keep.append(r)
    os.makedirs(os.path.join(OUT, t), exist_ok=True)
    for r in keep:
        p, cu = r["xls"]
        fn = os.path.join(OUT, t, "%s.xlsx" % p)
        if not os.path.exists(fn):
            s2, b = get("https://www.cnv.gov.ar/SitioWeb/Reportes/EstadosContables?presentacionId=%s&cucnv=%s" % (p, cu), True)
            if s2 == 200 and isinstance(b, bytes):
                open(fn, "wb").write(b)
    idx[t] = keep
    print(t, len(keep))
json.dump(idx, open(os.path.join(OUT, "index2.json"), "w"), ensure_ascii=False, indent=1)
