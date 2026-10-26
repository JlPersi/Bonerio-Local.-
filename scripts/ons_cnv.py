#!/usr/bin/env python3
"""ONs nuevas desde la CNV -> data/ons_flujos.xlsx -> data/ons.json.

  python3 scripts/ons_cnv.py nuevas [--dias 45] [--dir carpeta]
      Lista las últimas colocaciones de ON de la CNV (Empresas > Últimas colocaciones) que no están cargadas
      ni marcadas en data/ons_cnv.json, y baja el aviso de suscripción y el de resultado de cada una a <dir>/<serie>/*.pdf
      y .txt (la base de cálculo de la renta suele estar en el de suscripción).
      Una ON está cargada si en ons.json hay una del mismo emisor que vence dentro de la semana.
  python3 scripts/ons_cnv.py alta ficha.json [--seco]
      Da de alta las ONs de la ficha (una o una lista): flujos en la planilla, emisor en ons_emisores.json,
      serie en ons_cnv.json, y corre scripts/ons.py. --seco muestra los flujos sin escribir.
  python3 scripts/ons_cnv.py pendientes
      Las fichas sin ticker y, para cada una, las especies de data912 (live/arg_corp) que todavía no están en ons.json
      y empiezan como las otras ONs del emisor (o todas las nuevas si el emisor no tiene ninguna).
  python3 scripts/ons_cnv.py ticker <serie> <TICKER>
      Le pone el ticker a una ficha pendiente y la da de alta.
  python3 scripts/ons_cnv.py marcar <serie> "<motivo>"
      Deja una colocación como vista sin cargarla (por ejemplo, no cotiza o es una reapertura ya cargada).

Ficha (por 100 VN; fechas AAAA-MM-DD; tasas en %):
  {"serie": 89106, "ticker": "ARC2O", "emisor": "AA2000", "tipo": "ON",
   "emision": "2026-11-05", "vto": "2036-11-05", "tasa": 8.0, "base": "30/360",
   "pagos": {"primero": "2027-05-05", "meses": 3},            o una lista de fechas
   "amort": [["2032-02-05", 5], ...]}                         o "bullet"; % del VN original
  tipo: ON (dólares, tasa fija), ON_DOLLAR_LINKED, ON_FIXED_RATE (pesos fija), ON_TAMAR, ON_BADLAR, ON_CER.
  TAMAR y BADLAR: "tasa" es el margen y la renta queda en 0 (la página la proyecta con el índice), como en la planilla.
  base: 30/360, act/360 o act/365. Las fechas de pago que caen en fin de semana o feriado (FER de licitaciones.html)
  pasan al día hábil siguiente, sin renta por los días corridos (lo usual en los avisos).
  Sin ticker todavía (no empezó a cotizar): "ticker": null deja la ficha en ons_cnv.json como pendiente.
"""
import json, os, re, sys, time, html, datetime as dt, calendar, subprocess, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
XLSX = os.path.join(ROOT, "data", "ons_flujos.xlsx")
STATE = os.path.join(ROOT, "data", "ons_cnv.json")
EMIS = os.path.join(ROOT, "data", "ons_emisores.json")
ONS = os.path.join(ROOT, "data", "ons.json")
CNV = "https://www.cnv.gov.ar/SitioWeb/"
AIF = "https://aif2.cnv.gov.ar/"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
MES = {m: i + 1 for i, m in enumerate("ene feb mar abr may jun jul ago sep oct nov dic".split())}


def get(url, data=None, raw=False):
    req = urllib.request.Request(url, data=data, headers=dict(UA, **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})))
    for i in range(4):  # la AIF corta conexiones seguido
        try:
            b = urllib.request.urlopen(req, timeout=60).read()
            break
        except OSError:
            if i == 3:
                raise
            time.sleep(3 * (i + 1))
    return b if raw else b.decode("utf-8", "replace")


def txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def fecha(s):  # "22 oct. 2026" -> 2026-10-22
    d, m, a = re.match(r"(\d+) (\w{3})\w*\.? (\d{4})", s.strip()).groups()
    return dt.date(int(a), MES[m.lower()], int(d)).isoformat()


def norm(s):
    s = re.sub(r"\b(s\.?a\.?u?|s\.?r\.?l|saic?|sa|ciasa|sociedad anonima|compa[ñn][ií]a|cia|argentina|financiera)\b\.?", " ", s.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load(p, d):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d


def save(p, o):
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(p, "a").write("\n")


# ---------- nuevas ----------

def colocaciones(desde):
    out, page = [], 1
    while page < 30:
        s = get(CNV + "Empresas/UltimasColocaciones/ON?page=%d" % page)
        rows = re.findall(r"(?s)<tr>(.*?)</tr>", s)
        if not rows:
            break
        for r in rows:
            td = [txt(x) for x in re.findall(r"(?s)<td[^>]*>(.*?)</td>", r)]
            m = re.search(r"ObtenerSerieID_Para_DetallesFormularios\((\d+), '([^']*)', '([^']*)', '(\d+)'\)", r)
            if len(td) < 6 or not m:
                continue
            out.append({"serie": int(m.group(1)), "fecha": fecha(td[0]), "emisor": html.unescape(m.group(2)), "clase": html.unescape(m.group(3)),
                        "cuit": m.group(4), "moneda": td[3], "monto": td[4], "vto": fecha(td[5]) if re.search(r"\d{4}", td[5]) else None})
        if out and out[-1]["fecha"] < desde:
            break
        page += 1
    return [c for c in out if c["fecha"] >= desde]


def documentos(c):
    q = urllib.parse.urlencode({"serieID": c["serie"], "nombreserie": c["clase"], "idfiscal": c["cuit"], "nombresociedad": c["emisor"]})
    s = get(CNV + "Empresas/DetallesDeFormularios?" + q)
    docs = []
    for r in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", s):
        td = [txt(x) for x in re.findall(r"(?s)<td[^>]*>(.*?)</td>", r)]
        u = re.search(r'href="(https://aif2\.cnv\.gov\.ar/Presentations/publicview/[^"]+)"', r)
        if len(td) >= 4 and u:
            docs.append({"fecha": td[0], "id": td[2], "form": td[3], "url": u.group(1)})
    return docs


def bajar(url, carpeta, pref):
    """Adjuntos (PDF) de una presentación de la AIF: la página trae los guid; cada uno se baja con una llave de un solo uso."""
    s = get(url)
    hechos = []
    for m in re.finditer(r'"nombreArchivo":"([^"]+)","tamano":"[^"]*","guid":"([0-9a-f-]{36})"', s):
        nom, g = m.groups()
        k = json.loads(get(AIF + "api/ValetKeyProvider/GetPublicValetKey/%s?operation=DownloadBlob" % g))["valetKeyData"]
        b = get("https://blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/" + g, urllib.parse.urlencode({"ValetKey": k}).encode(), raw=True)
        p = os.path.join(carpeta, pref + "-" + re.sub(r"[^\w.-]+", "_", nom))
        open(p, "wb").write(b)
        if b[:4] == b"%PDF":
            t = p[:-4] + ".txt"
            try:
                subprocess.run(["pdftotext", "-layout", p, t], check=True)
            except Exception:
                from pypdf import PdfReader
                open(t, "w").write("\n".join(pg.extract_text() or "" for pg in PdfReader(p).pages))
            hechos.append(t)
        else:
            hechos.append(p)
    return hechos


def nuevas(dias, carpeta):
    st = load(STATE, {"series": {}, "alias": {}})
    on = load(ONS, {"on": {}})["on"]
    em = load(EMIS, {})
    desde = (dt.date.today() - dt.timedelta(days=dias)).isoformat()
    vtos = {}
    for b, o in on.items():
        vtos.setdefault(o["mat"], set()).add(em.get(b, ""))
    res = []
    for c in colocaciones(desde):
        if str(c["serie"]) in st["series"]:
            continue
        alias = st["alias"].get(c["cuit"]) or next((n for n in set(em.values()) if norm(n) and (norm(n) in norm(c["emisor"]) or norm(c["emisor"]) in norm(n))), None)
        c["alias"] = alias
        v = c["vto"] and dt.date.fromisoformat(c["vto"])
        if alias and v and any(alias in vtos.get((v + dt.timedelta(days=k)).isoformat(), ()) for k in range(-7, 8)):
            c["estado"] = "ya cargada"
            res.append(c)
            continue
        d = os.path.join(carpeta, str(c["serie"]))
        os.makedirs(d, exist_ok=True)
        c["archivos"] = []
        for doc in documentos(c):
            if re.search(r"resultado|^aviso de suscripci[oó]n$", doc["form"], re.I):
                try:
                    c["archivos"] += bajar(doc["url"], d, doc["id"])
                except Exception as e:
                    c["archivos"].append("error %s: %s" % (doc["id"], e))
        c["estado"] = "nueva" if any(re.search("result", a, re.I) for a in c["archivos"]) else "sin aviso de resultado todavía"
        res.append(c)
    print(json.dumps(res, ensure_ascii=False, indent=1))


# ---------- alta ----------

def feriados():
    s = open(os.path.join(ROOT, "licitaciones.html"), encoding="utf-8").read()
    m = re.search(r"const FER=\{(.*?)\}", s, re.S)
    return set(re.findall(r'"(\d{4}-\d\d-\d\d)"', m.group(1))) if m else set()


def habil(d, fer):
    while d.weekday() >= 5 or d.isoformat() in fer:
        d += dt.timedelta(days=1)
    return d


def add_m(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    return dt.date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def d360(a, b):
    da, db = min(a.day, 30), b.day
    if da == 30 and db == 31:
        db = 30
    return ((b.year - a.year) * 360 + (b.month - a.month) * 30 + db - da) / 360


def flujos(f, fer):
    D = dt.date.fromisoformat
    em, vto = D(f["emision"]), D(f["vto"])
    p = f["pagos"]
    if isinstance(p, dict):
        fs, d, i = [], D(p["primero"]), 0
        while d < vto:
            fs.append(d)
            i += 1
            d = add_m(D(p["primero"]), p["meses"] * i)
        fs.append(vto)
    else:
        fs = sorted(D(x) for x in p)
    am = {fs[-1]: 100.0} if f.get("amort", "bullet") == "bullet" else {D(a): float(b) for a, b in f["amort"]}
    if abs(sum(am.values()) - 100) > 1e-6:
        raise SystemExit("%s: la amortización suma %s%%, no 100%%" % (f.get("ticker"), sum(am.values())))
    if not set(am) <= set(fs):
        raise SystemExit("%s: hay amortizaciones fuera de las fechas de pago: %s" % (f.get("ticker"), sorted(set(am) - set(fs))))
    flot = f["tipo"] in ("ON_TAMAR", "ON_BADLAR")
    base = f.get("base", "30/360")
    rows, res, prev = [], 100.0, em
    for d in fs:
        h = habil(d, fer)
        yf = d360(prev, d) if base == "30/360" else (d - prev).days / (360 if base == "act/360" else 365)
        ren = 0.0 if flot else res * f["tasa"] / 100 * yf
        a = am.get(d, 0.0)
        res = round(res - a, 6)
        rows.append((h.isoformat(), round(a, 6), f["tasa"] / 100, round(ren, 6), res, round(a + ren, 6), 360 if base.endswith("360") else 365, d.isoformat() if flot else None))
        prev = d
    return rows


def alta(path, seco):
    import openpyxl
    fichas = json.load(open(path, encoding="utf-8"))
    fichas = fichas if isinstance(fichas, list) else [fichas]
    fer = feriados()
    st = load(STATE, {"series": {}, "alias": {}})
    em = load(EMIS, {})
    wb = None if seco else openpyxl.load_workbook(XLSX)
    ws = wb.worksheets[0] if wb else None
    ya = {r[0] for r in ws.iter_rows(min_row=2, values_only=True)} if ws else set()
    for f in fichas:
        rows = flujos(f, fer)
        t = f.get("ticker")
        print("%s %s %s %s %s%% %s: %d pagos, total %.4f" % (t, f["emisor"], f["tipo"], f["vto"], f["tasa"], f.get("base", "30/360"), len(rows), sum(r[5] for r in rows)))
        if seco:
            for r in rows:
                print("  ", r[0], "amort", r[1], "renta", r[3], "residual", r[4], "flujo", r[5])
            continue
        ser = str(f.get("serie", ""))
        if not t:
            st["series"][ser] = {"estado": "sin ticker", "ficha": f}
            continue
        if t in ya:
            raise SystemExit("%s ya está en la planilla" % t)
        for r in rows:
            ws.append([t, f["tipo"], None, f["emision"], r[0], str(r[1]), str(r[2]), str(r[3]), str(r[4]), str(r[5]), str(r[6]), r[7], None])
        em[t[:-1]] = f["emisor"]
        if ser:
            st["series"][ser] = {"estado": "cargada", "ticker": t}
        if f.get("cuit"):
            st["alias"][f["cuit"]] = f["emisor"]
    if seco:
        return
    wb.save(XLSX)
    save(STATE, st)
    json.dump(dict(sorted(em.items())), open(EMIS, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    subprocess.run([sys.executable, os.path.join(HERE, "ons.py")], check=True)


def pendientes():
    st = load(STATE, {"series": {}, "alias": {}})
    on = load(ONS, {"on": {}})["on"]
    em = load(EMIS, {})
    req = urllib.request.Request("https://data912.com/live/arg_corp", headers=UA)
    vivo = {r["symbol"]: r for r in json.load(urllib.request.urlopen(req, timeout=40)) if r.get("symbol")}
    nuevos = sorted(s for s in vivo if s.endswith("O") and s[:-1] not in on)
    for ser, x in sorted(st["series"].items()):
        if x.get("estado") != "sin ticker":
            continue
        f = x["ficha"]
        pref = {b[:2] for b, n in em.items() if n == f["emisor"]}
        cand = [s for s in nuevos if not pref or s[:2] in pref]
        print(ser, f["emisor"], f["tipo"], f["vto"], "->", ", ".join("%s (%s, vol %s)" % (s, vivo[s].get("c"), vivo[s].get("v")) for s in cand) or "sin candidatos")


def con_ticker(ser, t):
    st = load(STATE, {"series": {}, "alias": {}})
    f = dict(st["series"][ser]["ficha"], ticker=t)
    p = os.path.join(ROOT, ".ons_cnv", "ficha-%s.json" % ser)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(f, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    alta(p, False)


def main():
    a = sys.argv[1:]
    if a[:1] == ["nuevas"]:
        dias = int(a[a.index("--dias") + 1]) if "--dias" in a else 45
        carpeta = a[a.index("--dir") + 1] if "--dir" in a else os.path.join(ROOT, ".ons_cnv")
        nuevas(dias, carpeta)
    elif a[:1] == ["alta"] and len(a) >= 2:
        alta(a[1], "--seco" in a)
    elif a[:1] == ["pendientes"]:
        pendientes()
    elif a[:1] == ["ticker"] and len(a) == 3:
        con_ticker(a[1], a[2])
    elif a[:1] == ["marcar"] and len(a) == 3:
        st = load(STATE, {"series": {}, "alias": {}})
        st["series"][a[1]] = {"estado": a[2]}
        save(STATE, st)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
