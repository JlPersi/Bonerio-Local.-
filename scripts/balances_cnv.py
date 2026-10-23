#!/usr/bin/env python3
"""Balances del panel líder desde la CNV -> data/acciones/balances/<TICKER>.json (formato en data/acciones/balances/README.md).

La CNV publica, por cada estado contable presentado, una planilla estandarizada (Reportes/EstadosContables) con los rubros
codificados: activo, pasivo, patrimonio, resultados acumulados del ejercicio, EBIT y EBITDA. Este script lista las
presentaciones de cada empresa en www.cnv.gov.ar/SitioWeb/Empresas/Empresa/<CUIT>, baja las planillas propias
(no las de controladas) y arma los períodos. Usa el consolidado y, si la empresa no lo presenta, el individual.

- Montos: tal como figuran (moneda de la fecha de cierre). La unidad (pesos, miles o millones) no viene en la planilla:
  se deduce del tamaño del activo total y se guarda en "escala" por período.
- Acciones: capital social / valor nominal de cada acción (VN abajo).
- Resultado operativo: el rubro "ganancia de actividades operativas". Depreciaciones: EBITDA - EBIT de la planilla (lo informa la
  empresa); si da negativo (pasa en algunas), el rubro "depreciaciones y amortizaciones" del estado de resultados.
- Bancos: sin ventas ni EBITDA (P/VL, P/E y ROE).
Para pruebas: CNV_DIR=carpeta con index.json y <TICKER>/<presentacion>.xlsx (no baja nada).
"""
import json, os, re, sys, time, zipfile, html as H, urllib.request, datetime as dt
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "acciones", "balances")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://www.cnv.gov.ar/SitioWeb"
DESDE = "2010-01-01"  # toda la historia que tenga la CNV en planillas estandarizadas
VERSION = 2  # si cambia la forma de leer las planillas, se suben: los archivos de otra versión se rearman enteros

# ticker: (CUIT, valor nominal por acción al cierre de los balances, mes de cierre del ejercicio, banco, moneda funcional)
EMPRESAS = {
    "ALUA": ("30522780606", 1, 6, False, "ARS"),
    "BBAR": ("30500003193", 1, 12, True, "ARS"),
    "BMA": ("30500010084", 1, 12, True, "ARS"),
    "BYMA": ("30715471953", 1, 12, False, "ARS"),
    "CEPU": ("33650305499", 1, 12, False, "ARS"),
    "COME": ("33526316989", 1, 12, False, "ARS"),
    "CRES": ("30509300700", 1, 6, False, "ARS"),
    "EDN": ("30655116202", 1, 12, False, "ARS"),
    "GGAL": ("30704962807", 1, 12, True, "ARS"),
    "IRSA": ("30525322749", 10, 6, False, "ARS"),
    "LOMA": ("30500530851", 0.1, 12, False, "ARS"),
    "METR": ("30657863676", 1, 12, False, "ARS"),
    "PAMP": ("30526552659", 1, 12, False, "USD"),
    "TECO2": ("30639453738", 1, 12, False, "ARS"),
    "TGNO4": ("30657863056", 1, 12, False, "ARS"),
    "SUPV": ("30617442937", 1, 12, True, "ARS"),
    "TGSU2": ("30657862068", 1, 12, False, "ARS"),
    "TRAN": ("30663148776", 1, 12, False, "ARS"),
    "TXAR": ("30516888241", 1, 12, False, "ARS"),
    "VALO": ("30576124275", 1, 12, True, "ARS"),  # Banco de Valores (absorbió a Grupo Financiero Valores)
    "YPFD": ("30546689979", 10, 12, False, "USD"),
    # panel general (y ECOG): CUIT de la lista de emisoras de la CNV; el mes de cierre (None) se deduce de los balances anuales que
    # presentó cada una (PERIODICIDAD 1), así un cambio de ejercicio (Morixe pasó de mayo a diciembre) no rompe los acumulados
    "AGRO": ("30503087967", 1, None, False, "ARS"), "AUSO": ("30677237119", 1, None, False, "ARS"),
    "BHIP": ("30500011072", 1, None, True, "ARS"), "BOLT": ("30500179151", 1, None, False, "ARS"),
    "BPAT": ("30500006613", 1, None, True, "ARS"), "CADO": ("30525406756", 1, None, False, "ARS"),
    "CAPX": ("30629827060", 1, None, False, "ARS"), "CARC": ("30504249227", 1, None, False, "ARS"),
    "CECO2": ("30652254248", 1, None, False, "ARS"), "CELU": ("30501062150", 1, None, False, "ARS"),
    "CGPA2": ("30657864281", 1, None, False, "ARS"), "CTIO": ("30587480359", 1, None, False, "ARS"),
    "CVH": ("30715591231", 1, None, False, "ARS"), "DGCU2": ("33657865589", 1, None, False, "ARS"),
    "DOME": ("30501999470", 1, None, False, "ARS"), "ECOG": ("30658275522", 1, None, False, "ARS"),
    "FERR": ("30525341263", 1, None, False, "ARS"), "FIPL": ("30502112259", 1, None, False, "ARS"),
    "GAMI": ("30709967424", 1, None, False, "ARS"), "GARO": ("30509284861", 1, None, False, "ARS"),
    "GBAN": ("30657864117", 1, None, False, "ARS"), "GCDI": ("30709282537", 1, None, False, "ARS"),
    "GCLA": ("30707001735", 1, None, False, "ARS"), "GRIM": ("30500781293", 1, None, False, "ARS"),
    "HARG": ("30501111127", 1, None, False, "ARS"), "HAVA": ("30708544082", 1, None, False, "ARS"),
    "HSAT": ("30718288718", 1, None, False, "ARS"), "INTR": ("30501290323", 1, None, False, "ARS"),
    "INVJ": ("30640285431", 1, None, False, "ARS"), "LEDE": ("30501250305", 1, None, False, "ARS"),
    "LONG": ("30500833781", 1, None, False, "ARS"), "MIRG": ("30578036071", 1, None, False, "ARS"),
    "MOLA": ("30715118773", 1, None, False, "ARS"), "MOLI": ("30500858628", 1, None, False, "ARS"),
    "MORI": ("30525346389", 1, None, False, "ARS"), "OEST": ("30663498513", 1, None, False, "ARS"),
    "PATA": ("30506730038", 1, None, False, "ARS"), "POLL": ("30538748478", 1, None, False, "ARS"),
    "RICH": ("30501152826", 1, None, False, "ARS"), "RIGO": ("30500526935", 1, None, False, "ARS"),
    "ROSE": ("30501407093", 1, None, False, "ARS"), "SAMI": ("30511190238", 1, None, False, "ARS"),
    "SEMI": ("30536928703", 1, None, False, "ARS"),
}
SPLITS = {"YPFD": [{"fecha": "2026-08-03", "factor": 10}]}  # YPF pasó de VN $10 a VN $1
# BYMA: capitalización ×5 en 2024 (la historia de precios ya viene ajustada: "ajustado") y ×2 el 26/05/2025 (sin ajustar)
SPLITS["BYMA"] = [{"fecha": "2024-06-01", "factor": 5, "ajustado": True}, {"fecha": "2025-05-26", "factor": 2}]
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}


def get(url, binary=False):
    err = None
    for k in range(3):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
            return b if binary else b.decode("utf8", "replace")
        except Exception as e:
            err = e; time.sleep(3 * (k + 1))
    raise err


def txt(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def presentaciones(cuit):
    """Filas de la tabla 'Estados Contables' de la empresa (sin controladas ni vinculadas)."""
    h = get("%s/Empresas/Empresa/%s" % (BASE, cuit))
    i = h.find(">Estados Contables<")
    if i < 0:
        return []
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", h[i:h.find("</table>", i)], re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        ln = re.search(r"EstadosContables\?presentacionId=(\d+)&amp;cucnv=(\d+)", tr)
        if len(tds) < 4 or not ln:
            continue
        desc = txt(tds[2])
        m = re.search(r"FECHA CIERRE: (\d{4}-\d\d-\d\d)", desc)
        if "CONTROLADAS Y VINCULADAS" in desc or not m:
            continue
        pr = re.search(r"PERIODICIDAD: (\d+)", desc)
        out.append({"fecha": txt(tds[0]), "desc": desc, "xls": ln.groups(), "cierre": m.group(1), "anual": bool(pr and pr.group(1) == "1"),
                    "tipo": "CONSOLIDADO" if "CONSOLIDADO" in desc else "INDIVIDUAL"})
    return out


def leer_xlsx(path):
    """{código de rubro: monto} de la planilla de la CNV (una sola hoja, columnas Nro, Rubro, Monto)."""
    z = zipfile.ZipFile(path)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            ss.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    sheet = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
    vals, meta = {}, {}
    for row in ET.fromstring(z.read(sheet)).iter("{%s}row" % ns["m"]):
        cells = []
        for c in row.findall("m:c", ns):
            v = c.find("m:v", ns); t = c.get("t")
            s = v.text if v is not None else "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
            if t == "s" and s is not None:
                s = ss[int(s)]
            cells.append((s or "").strip())
        cells = [x for x in cells if x != ""]
        if len(cells) >= 3 and re.fullmatch(r"\d{7}", cells[0]):
            n = cells[-1].replace(",", "")
            try:
                vals[cells[0]] = float(n)
            except ValueError:
                vals[cells[0]] = None  # "-" = sin dato
        elif len(cells) >= 2 and cells[0].endswith(":"):
            meta[cells[0]] = cells[1]
    return vals, meta


def fecha_pub(s):
    m = re.match(r"(\d+) (\w+)\.? (\d{4})", s)
    if not m or m.group(2)[:3].lower() not in MESES:
        return None
    return dt.date(int(m.group(3)), MESES[m.group(2)[:3].lower()], int(m.group(1))).isoformat()


def escala_de(activo):
    """Pesos, miles o millones según el tamaño del activo (el panel líder va de ~1 a ~100 billones de pesos)."""
    if activo is None:
        return None
    return 1 if activo > 1e11 else (1000 if activo > 1e8 else 1000000)


def periodo(v, p, vn, mes_cierre, banco):
    g = lambda k: v.get(k)
    def suma(*ks):
        xs = [g(k) for k in ks]
        return None if all(x is None for x in xs) else sum(x or 0 for x in xs)
    esc = escala_de(g("1999999"))
    m = int(p["cierre"][5:7])
    meses = (m - mes_cierre) % 12 or 12 if mes_cierre else p.get("meses") or 12
    pn = g("2299999"); mino = g("2211300")
    ebit, ebitda = g("8000003"), g("8000004")
    da = ebitda - ebit if ebit is not None and ebitda is not None and ebitda >= ebit else None
    if da is None and g("3011600"):
        da = abs(g("3011600"))
    oper = g("3019999") if g("3019999") is not None else ebit
    r = {
        "cierre": p["cierre"],
        "publicado": fecha_pub(p["fecha"]),
        "acumulado_meses": meses,
        "fuente": "CNV %s, presentación %s" % (p["tipo"].lower(), p["xls"][0]),
        "escala": esc,
        "acciones": round(g("2210999") * esc / vn) if g("2210999") and esc else None,
        "resultados": {
            "ventas": None if banco else g("3000100"),
            "resultado_operativo": None if banco else oper,
            "depreciaciones": None if banco else da,
            "resultado_neto": g("3049999"),
            "resultado_neto_controlante": None,
        },
        "situacion": {
            "patrimonio_neto": pn,
            "patrimonio_neto_controlante": (pn - (mino or 0)) if pn is not None else None,
            "deuda_financiera": None if banco else suma("2322200", "2312300"),
            "caja_inversiones": None if banco else suma("1122500", "1122300"),
        },
    }
    return r


def main():
    os.makedirs(OUT, exist_ok=True)
    local = os.environ.get("CNV_DIR")
    tmp = local or os.path.join(HERE, "..", ".cnv_tmp")
    idx = json.load(open(os.path.join(local, "index.json"))) if local else {}
    solo = set(filter(None, os.environ.get("TICKERS", "").split(",")))
    for t, (cuit, vn, mes_cierre, banco, moneda) in EMPRESAS.items():
        if solo and t not in solo:
            continue
        try:
            pres = idx[t] if local else presentaciones(cuit)
        except Exception as e:
            print(t, "sin lista de presentaciones:", e); continue
        pres = [p for p in pres if p["cierre"] >= DESDE]
        if mes_cierre is None:  # meses acumulados: desde el último cierre anual anterior
            an = sorted({p["cierre"] for p in pres if p.get("anual")})
            for p in pres:
                prev = [a for a in an if a < p["cierre"]]
                if p.get("anual"):
                    p["meses"] = 12
                elif not prev:  # antes del primer anual: el mes de cierre del primero que haya
                    p["meses"] = ((int(p["cierre"][5:7]) - int(an[0][5:7])) % 12 or 12) if an else None
                else:
                    y0, m0, y1, m1 = int(prev[-1][:4]), int(prev[-1][5:7]), int(p["cierre"][:4]), int(p["cierre"][5:7])
                    p["meses"] = min(12, (y1 - y0) * 12 + m1 - m0)
        # por cierre: el consolidado si existe; si se presentó más de una vez, la última (las filas vienen de la más nueva a la más vieja)
        elegido = {}
        for p in pres:
            q = elegido.get(p["cierre"])
            if q is None or (q["tipo"] != "CONSOLIDADO" and p["tipo"] == "CONSOLIDADO"):
                elegido[p["cierre"]] = p
        try:  # períodos ya cargados de la misma presentación: no se vuelven a bajar
            viejo = json.load(open(os.path.join(OUT, t + ".json")))
            previos = {q["fuente"]: dict(q, escala=viejo["escala"]) for q in viejo["periodos"]} if viejo.get("v") == VERSION else {}
        except Exception:
            previos = {}
        periodos = []
        for c in sorted(elegido):
            p = elegido[c]
            q = previos.get("CNV %s, presentación %s" % (p["tipo"].lower(), p["xls"][0]))
            if q and not local:
                periodos.append(q); continue
            fn = os.path.join(tmp, t, "%s.xlsx" % p["xls"][0])
            if not os.path.exists(fn):
                if local:
                    continue
                os.makedirs(os.path.dirname(fn), exist_ok=True)
                try:
                    b = get("%s/Reportes/EstadosContables?presentacionId=%s&cucnv=%s" % (BASE, p["xls"][0], p["xls"][1]), True)
                    open(fn, "wb").write(b)
                except Exception as e:
                    print(t, c, "no se pudo bajar:", e); continue
            try:
                v, meta = leer_xlsx(fn)
            except Exception as e:
                print(t, c, "planilla ilegible:", e); continue
            if v.get("1999999") is None:
                print(t, c, "sin activo total, se omite"); continue
            periodos.append(periodo(v, p, vn, mes_cierre, banco))
        if not periodos:
            print(t, "sin períodos"); continue
        esc = periodos[-1]["escala"]
        for p in periodos:  # todo en la unidad del último balance
            f = p.pop("escala") / esc
            for grupo in ("resultados", "situacion"):
                p[grupo] = {k: (round(x * f, 2) if x is not None else None) for k, x in p[grupo].items()}
        doc = {"t": t, "v": VERSION, "cuit": cuit, "fuente": "CNV - Estados contables (www.cnv.gov.ar)", "moneda_funcional": moneda,
               "splits": SPLITS.get(t, []),
               "escala": esc, "acciones": periodos[-1]["acciones"], "periodos": periodos}
        json.dump(doc, open(os.path.join(OUT, t + ".json"), "w"), ensure_ascii=False, indent=1)
        print(t, len(periodos), "períodos, último", periodos[-1]["cierre"])


if __name__ == "__main__":
    main()
