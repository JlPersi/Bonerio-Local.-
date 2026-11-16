#!/usr/bin/env python3
"""Foto diaria del valor de cuotaparte (VCP) de todos los FCI, de la planilla diaria de CAFCI (api.pub.cafci.org.ar/pb_get, un Excel).
Guarda data/fci_m/AAAA-MM.json = {"d": fecha del informe, "v": {nombre del fondo y clase: VCP por cuotaparte}}: el archivo del mes se
pisa con cada informe nuevo, así al terminar el mes queda el del último día hábil (con eso el libro de operaciones valúa los fondos al cierre).
El primer informe de un mes también trae el VCP anterior (el del último día hábil del mes pasado): si el archivo del mes pasado no tiene
esa fecha, lo completa con eso. CAFCI publica el VCP cada mil cuotapartes: se guarda por cuotaparte.
Para pruebas: CAFCI_FILE (un Excel guardado). Si la planilla no se puede leer, no pisa nada.
"""
import io, json, os, re, sys, urllib.request, datetime as dt
import openpyxl

URL = "https://api.pub.cafci.org.ar/pb_get"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*",
     "Origin": "https://www.cafci.org.ar", "Referer": "https://www.cafci.org.ar/"}
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "fci_m")


def norm(c):
    return re.sub(r"\s+", " ", str(c if c is not None else "")).strip()


def fdate(v):
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    s = norm(v)
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        y = int(m[3]); y = y + 2000 if y < 100 else y
        return "%04d-%02d-%02d" % (y, int(m[2]), int(m[1]))
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return m[0] if m else None


def num(v):
    if isinstance(v, (int, float)) and v == v:
        return float(v)
    s = norm(v).replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse(b):
    ws = openpyxl.load_workbook(io.BytesIO(b), read_only=True, data_only=True).worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    hi = next((i for i, r in enumerate(rows[:60]) if any(norm(c).lower().startswith("fondo") for c in r)), None)
    if hi is None:
        sys.exit("save_fci: no encuentro el encabezado (Fondo)")
    h1 = [norm(c).lower() for c in rows[hi]]
    h2 = [norm(c).lower() for c in rows[hi + 1]] if hi + 1 < len(rows) else []
    n = max(len(h1), len(h2)); grp = ""; hd = []
    for j in range(n):  # encabezado en dos filas (celdas combinadas): «Valor (mil cuotapartes)» arriba, «Actual» y «Anterior» abajo
        a = h1[j] if j < len(h1) else ""; b2 = h2[j] if j < len(h2) else ""
        if a:
            grp = a
        hd.append(((a or grp) + " " + b2).strip())
    col = lambda f: next((j for j, h in enumerate(hd) if f(h)), None)
    cN = col(lambda h: h.startswith("fondo"))
    cF = col(lambda h: "fecha" in h)
    cA = col(lambda h: "actual" in h and ("valor" in h or "vcp" in h or "cuota" in h)) or col(lambda h: "actual" in h)
    cP = col(lambda h: "anterior" in h and ("valor" in h or "vcp" in h or "cuota" in h)) or col(lambda h: "anterior" in h)
    if cA is None:
        sys.exit("save_fci: no encuentro la columna del VCP actual: %s" % hd[:20])
    mil = 1000.0 if "mil" in hd[cA] else 1.0
    print("save_fci: columnas", {"fondo": cN, "fecha": cF, "actual": hd[cA], "anterior": cP is not None and hd[cP]}, "por mil" if mil > 1 else "")
    v, a, fechas = {}, {}, {}
    for r in rows[hi + 1:]:
        if cN >= len(r) or cA >= len(r):
            continue
        nm = norm(r[cN]); x = num(r[cA])
        if not nm or x is None or x <= 0 or nm in v:
            continue
        v[nm] = round(x / mil, 8)
        if cP is not None and cP < len(r):
            p = num(r[cP])
            if p and p > 0:
                a[nm] = round(p / mil, 8)
        d = fdate(r[cF]) if cF is not None and cF < len(r) else None
        if d:
            fechas[d] = fechas.get(d, 0) + 1
    if len(v) < 100:
        sys.exit("save_fci: muy pocos fondos (%d), no guardo" % len(v))
    d = max(fechas, key=fechas.get) if fechas else dt.date.today().isoformat()  # la fecha que tiene la mayoría (algún fondo informa atrasado)
    return d, v, a


def prev_weekday(d):
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def save(mk, d, v):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, mk + ".json")
    old = json.load(open(p)) if os.path.exists(p) else None
    if old and old.get("d", "") > d:
        return False
    json.dump({"d": d, "v": v}, open(p, "w"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return True


def main():
    if os.environ.get("CAFCI_FILE"):
        b = open(os.environ["CAFCI_FILE"], "rb").read()
    else:
        b = urllib.request.urlopen(urllib.request.Request(URL, headers=H), timeout=90).read()
    d, v, a = parse(b)
    print("save_fci: %s, %d fondos" % (d, len(v)))
    save(d[:7], d, v)
    pd = prev_weekday(dt.date.fromisoformat(d)).isoformat()
    if a and pd[:7] != d[:7]:  # primer día hábil del mes: el VCP anterior es el del cierre del mes pasado
        p = os.path.join(OUT, pd[:7] + ".json")
        old = json.load(open(p)) if os.path.exists(p) else {}
        if old.get("d", "") < pd:
            save(pd[:7], pd, a); print("save_fci: cierre de %s completado con el VCP anterior (%s)" % (pd[:7], pd))


if __name__ == "__main__":
    main()
