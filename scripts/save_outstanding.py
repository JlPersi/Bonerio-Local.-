"""Deuda en circulación (outstanding) por bono del Tesoro, de dos fuentes oficiales de la Secretaría de Finanzas:
   1) «Datos trimestrales de la deuda» (Excel, hojas A.1.7, A.1.8 y A.1.9): valor nominal residual y actualizado de cada título,
      en miles de US$ al cierre del trimestre. Hard dollar con ticker; los de pesos se emparejan en la página por tipo y vencimiento.
   2) Los comunicados de resultado de cada licitación: «VNO total en circulación» de cada instrumento licitado (con ticker),
      en millones de $ o de US$. Sirve para lo emitido después del corte trimestral y para cruzar con (1).
   Sale data/outstanding.json. Se corre con el cierre diario; no baja de nuevo lo que ya tiene."""
import datetime as dt, html, io, json, os, re, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "outstanding.json")
GOB = "https://www.argentina.gob.ar"
LIC = GOB + "/noticias/resultado-de-la-licitacion-por-efectivo-de-instrumentos-del-tesoro-nacional-denominados"
UA = {"User-Agent": "Mozilla/5.0 (bonerio-outstanding/1.0)"}
MES = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
HD = {("GLOBAL", "2029"): "GD29", ("GLOBAL", "2030"): "GD30", ("GLOBAL", "2035"): "GD35", ("GLOBAL", "2038"): "GD38", ("GLOBAL", "2041"): "GD41", ("GLOBAL", "2046"): "GD46",
      ("R.A.", "2029"): "AL29", ("R.A.", "2030"): "AL30", ("R.A.", "2035"): "AL35", ("R.A.", "2038"): "AE38", ("R.A.", "2041"): "AL41"}


def get(url, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(4 * (k + 1))
        except Exception:
            time.sleep(4 * (k + 1))
    return False  # no se pudo (403 del firewall): se saltea y se vuelve a probar en la próxima corrida


def clase(d, hoja):
    u = d.upper()
    if "DLK" in u or "LELINK" in u:
        return "dl"
    if "DUAL" in u:
        return "dual" if "CER" in u else "dualtf"
    if "TAMAR" in u or "BADLAR" in u:
        return "tamar"
    if "CER" in u:
        return "cer0" if hoja == "A.1.8" and (u.startswith("LECER") or re.search(r"\+CER/\d\d-\d\d-\d{4}", u)) else "cerc"
    if hoja == "A.1.9":
        return "usd"
    if u.startswith(("LECAP", "BONCAP")):
        return "cap"
    return "cpn"


def trimestral(prev):
    pg = get(GOB + "/economia/finanzas/datos-trimestrales-de-la-deuda").decode("utf-8", "ignore")
    url = re.search(r'href="([^"]*deuda_publica_[\d-]+[^"]*\.xlsx)"', pg).group(1)
    url = url if url.startswith("http") else GOB + url
    if prev and prev.get("url") == url:
        return prev
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(get(url)), read_only=True, data_only=True)
    rows, corte = [], None
    for h in ("A.1.7", "A.1.8", "A.1.9"):
        for r in wb[h].iter_rows(values_only=True):
            v = [x for x in r if x is not None]
            if not corte:
                m = next((re.search(r"(\d\d)/(\d\d)/(\d{4})", str(x)) for x in v if re.search(r"DATOS AL \d", str(x))), None)
                if m:
                    corte = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
            if len(v) < 7 or not hasattr(v[0], "year"):
                continue
            d = str(v[1]).strip()
            m = re.search(r"(\d\d)-(\d\d)-(\d{4})", d)
            if not m or not isinstance(v[5], (int, float)) or v[5] <= 0:
                continue
            o = {"d": d, "v": "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)), "c": clase(d, h), "vn": round(v[5], 1), "va": round(float(v[6]), 1), "e": v[0].date().isoformat()}
            if h == "A.1.9" and "U$S" in d:
                k = "GLOBAL" if "GLOBAL" in d else "R.A." if "R.A." in d else None
                t = HD.get((k, m.group(3))) if k else None
                if not t and d.startswith("BONTE/U$S"):
                    t = {"2027": "AO27", "2028": "AO28", "2029": "AN29" if m.group(2) == "11" else "AO29"}.get(m.group(3))
                if t:
                    o["t"] = t
            rows.append(o)
    return {"url": url, "corte": corte, "rows": rows}


def texto(b):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", b.decode("utf-8", "ignore"), flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))


def licitaciones(prev):
    vistos, out = dict(prev.get("vistos", {})), {k: list(v) for k, v in prev.get("t", {}).items()}
    hay = [int(k) for k in vistos if vistos[k]]
    desde = max(hay) - 1 if hay else 1  # las últimas dos se vuelven a mirar (por si faltó alguna)
    falt, i = 0, max(1, desde)
    while falt < 3 and i < 400:
        if str(i) in vistos and i < desde:
            i += 1; continue
        b = get(LIC + "-" + str(i)); time.sleep(1.5)
        if b is False:
            i += 1; continue
        if not b:
            falt += 1; i += 1; continue
        falt = 0; t = texto(b)
        m = re.search(r"(\d{1,2}) de ([a-z]+) de (20\d\d) Compartir", t)
        if m:
            f = "%s-%02d-%02d" % (m.group(3), MES[m.group(2)], int(m.group(1))); vistos[str(i)] = f
            s = t[t.find("Seguidamente"):] if "Seguidamente" in t else t
            ms = list(re.finditer(r"\(([A-Z][A-Z0-9]{3,5})(?:\s*-\s*[^)]*)?\)", s))
            for k, mm in enumerate(ms):
                seg = s[mm.end():ms[k + 1].start() if k + 1 < len(ms) else len(s)].split("(*)")[0]
                am = re.findall(r"(\$|USD|U\$S)\s*([\d.]+(?:,\d+)?)", seg)
                if len(am) < 3:
                    continue
                cur, v = am[-1]
                x = [f, float(v.replace(".", "").replace(",", ".")), "ARS" if cur == "$" else "USD"]
                L = [y for y in out.get(mm.group(1), []) if y[0] != f] + [x]
                out[mm.group(1)] = sorted(L)
        i += 1
    # canjes / conversiones: comunicados aparte (los que linkea la portada de Finanzas). Suman lo adjudicado y restan lo rescatado.
    cv, cvv = list(prev.get("cv", [])), dict(prev.get("cvv", {}))
    try:
        pg = get(GOB + "/economia/finanzas") or b""
        for slug in sorted(set(re.findall(r'href="(/noticias/resultado-de-la-licitacion-(?:para-la-)?conversion[^"]*)"', pg.decode("utf-8", "ignore")))):
            if slug in cvv:
                continue
            b = get(GOB + slug); time.sleep(1.5)
            if not b:
                continue
            t = texto(b); m = re.search(r"(\d{1,2}) de ([a-z]+) de (20\d\d) Compartir", t)
            if not m:
                continue
            f = "%s-%02d-%02d" % (m.group(3), MES[m.group(2)], int(m.group(1))); cvv[slug] = f
            for mm in re.finditer(r"\(([A-Z][A-Z0-9]{3,5})\s*-\s*(?:nueva|reapertura)[^)]*\)((?:\s*(?:\$|USD|U\$S)\s*[\d.,]+)+)", t):
                am = re.findall(r"(\$|USD|U\$S)\s*([\d.]+(?:,\d+)?)", mm.group(2))
                if len(am) >= 2:
                    cv.append([f, mm.group(1), float(am[1][1].replace(".", "").replace(",", ".")), "ARS" if am[1][0] == "$" else "USD"])
            for mm in re.finditer(r"VNO RESCATADO TOTAL (?:DE LA |DEL )?(?:[A-Z]+ )?([A-Z][A-Z0-9]{3,5}) (\$|USD|U\$S)\s*([\d.]+(?:,\d+)?)", t):
                cv.append([f, mm.group(1), -float(mm.group(3).replace(".", "").replace(",", ".")), "ARS" if mm.group(2) == "$" else "USD"])
    except Exception as e:
        print("conversiones:", e)
    return {"vistos": vistos, "t": out, "cv": sorted(cv), "cvv": cvv}


def main():
    prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
    q = prev.get("trim")
    try:
        q = trimestral(q)
    except Exception as e:
        print("trimestral:", e)
    lic = prev.get("lic", {})
    try:
        lic = licitaciones(lic)
    except Exception as e:
        print("licitaciones:", e)
    fx = None
    try:
        a = json.load(open(os.path.join(ROOT, "data", "dolar.json")))["A3500"]
        fx = a.get(q["corte"]) or a[max(k for k in a if k <= q["corte"])]
    except Exception:
        pass
    json.dump({"act": dt.date.today().isoformat(), "trim": q, "fx": fx, "lic": lic}, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print("outstanding:", q and q.get("corte"), len(q and q.get("rows") or []), "títulos;", len(lic.get("t", {})), "tickers de licitaciones")


if __name__ == "__main__":
    main()
