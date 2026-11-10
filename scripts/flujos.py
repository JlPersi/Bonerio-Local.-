"""Flujos de fondos de los bonos: los CSV data/flujos_*.csv son la fuente; la página los lleva adentro (PX.S, PSD.INST y PSOLD.INST).

    python3 scripts/flujos.py build    # CSV -> index.html y preview.html (lo corre solo el Action cuando cambia un CSV)
    python3 scripts/flujos.py export   # index.html -> CSV (para rearmarlos desde lo que tiene la página)
    python3 scripts/flujos.py check    # verifica que los CSV y la página digan lo mismo

Un CSV por planilla (una fila por pago; los datos del bono se repiten en cada fila, el orden solo importa dentro de cada bono):
- flujos_pesos.csv y flujos_pesos_vencidos.csv: Ticker, Clase, Familia, Emisión, Fecha de pago, Pago, Amortización, Tasa, Interés, Residual, Tipo.
    Clase: cap (Lecap/Boncap), cpn (tasa fija con cupón), cer0 (CER cupón cero), cerc (Boncer con cupón), tamar, dl (dollar linked),
    dual (paga el mayor de dos patas: dos filas con la misma fecha), dualtf (dual tasa fija / TAMAR).
    Familia: fija, cer, tamar, dl, o las dos patas de un dual (cer+tamar, dl+tamar). Tipo: FIXED_RATE, CER, TAMAR o DOLLAR_LINKED.
    Pago = cupón + amortización (en CER, TAMAR y DL, sin ajustar); Interés 0 si capitaliza; Residual = VN que queda después del pago.
- flujos_dolares.csv: Ticker, Emisión, Fecha de pago, Cupón, Amortización, Residual (globales y bonares).
- flujos_precio_emision.csv (opcional): Ticker, Precio. Para un bono nuevo sin historia de precios: arranca su serie con ese precio.
Fechas AAAA-MM-DD (o DD/MM/AAAA); montos por 100 de valor nominal; tasas en decimal (0.021 = 2,1%).
Se editan en GitHub (lápiz) o en Excel: si Excel los guarda con «;» y coma decimal, también se leen bien.
"""
import csv
import datetime as dt
import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = [os.path.join(ROOT, f) for f in ("index.html", "preview.html")]
TICKERS = os.path.join(ROOT, "scripts", "pesos_tickers.json")
EPOCH = dt.date(1970, 1, 1)

H_PESOS = ["Ticker", "Clase", "Familia", "Emisión", "Fecha de pago", "Pago", "Amortización", "Tasa", "Interés", "Residual", "Tipo"]
H_USD = ["Ticker", "Emisión", "Fecha de pago", "Cupón", "Amortización", "Residual"]
CLASES = {"cap": "Lecap / Boncap", "cpn": "Bono a tasa fija con cupón", "cer0": "Lecer / Boncer cupón cero", "cerc": "Boncer con cupón",
          "tamar": "Bono TAMAR", "dl": "Dollar linked", "dual": "Dual (el mayor de dos pagos)", "dualtf": "Dual tasa fija / TAMAR"}
SHEETS = {"Pesos": "pesos", "Dólares": "dolares", "Pesos vencidos": "pesos_vencidos", "Precio de emisión": "precio_emision"}


def csv_path(name):
    return os.path.join(ROOT, "data", "flujos_%s.csv" % SHEETS[name])


def d2n(v):
    if isinstance(v, dt.datetime):
        v = v.date()
    if isinstance(v, dt.date):
        return (v - EPOCH).days
    if isinstance(v, (int, float)):
        return int(v)
    v = str(v).strip()
    if "/" in v:  # DD/MM/AAAA (Excel en castellano)
        d, m, y = (int(x) for x in v.split()[0].split("/"))
        return (dt.date(y, m, d) - EPOCH).days
    return (dt.date.fromisoformat(v[:10]) - EPOCH).days


def n2d(n):
    return EPOCH + dt.timedelta(days=int(n))


def num(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, str):
        v = v.strip().replace(",", ".")
    return float(v)


def read_page(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    out = {}
    for name in ("PX", "PSD", "PSOLD"):
        pre = "const %s = " % name
        n = next(i for i, l in enumerate(lines) if l.startswith(pre))
        s = lines[n]; i = s.index("{"); j = s.rindex("}")
        out[name] = (n, s[:i], json.loads(s[i:j + 1]), s[j + 1:])
    return lines, out


def dump(o):
    return json.dumps(o, separators=(",", ":"), ensure_ascii=False)


# ---------- página -> planilla ----------
def write_csv(name, head, rows):
    def cell(v):
        return v.isoformat() if isinstance(v, dt.date) else repr(v) if isinstance(v, float) else v
    with open(csv_path(name), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n"); w.writerow(head)
        for r in rows:
            w.writerow([cell(v) for v in r])


def export():
    _, P = read_page(PAGES[0])

    def pesos_rows(inst):
        return [[t, b["k"], b["f"], n2d(b["iss"]), n2d(r[0]), r[1], r[2], r[3], r[4], r[5], r[6]] for t, b in inst.items() for r in b["r"]]
    write_csv("Pesos", H_PESOS, pesos_rows(P["PSD"][2]["INST"]))
    write_csv("Dólares", H_USD, [[t, n2d(b["iss"]), n2d(r[0]), r[1], r[2], r[3]] for t, b in P["PX"][2]["S"].items() for r in b["r"]])
    write_csv("Pesos vencidos", H_PESOS, pesos_rows(P["PSOLD"][2]["INST"]))
    if not os.path.exists(csv_path("Precio de emisión")):
        write_csv("Precio de emisión", ["Ticker", "Precio"], [])
    print("planillas guardadas: data/flujos_*.csv")


# ---------- planilla -> página ----------
def read_csv(name):
    """Filas de data/flujos_<hoja>.csv. Acepta coma o punto y coma como separador (Excel en castellano guarda con «;» y coma decimal)."""
    f = csv_path(name)
    if not os.path.exists(f):
        return None
    txt = open(f, encoding="utf-8-sig").read()
    first = txt.split("\n", 1)[0]
    return list(csv.reader(txt.splitlines(), delimiter=";" if first.count(";") > first.count(",") else ","))


def read_planilla():
    def rows(name, head):
        data = read_csv(name)
        if not data:
            return []
        it = iter(data); h = [str(x or "").strip() for x in next(it)]
        miss = [c for c in head if c not in h]
        if miss:
            sys.exit("%s: faltan las columnas %s" % (os.path.basename(csv_path(name)), ", ".join(miss)))
        ix = [h.index(c) for c in head]
        out = []
        for n, r in enumerate(it, 2):
            if not r or all(v.strip() == "" for v in r):
                continue
            out.append((n, [r[i] if i < len(r) else None for i in ix]))
        return out
    def pesos(name):
        inst = {}
        for n, (t, k, f, iss, fe, pago, am, tasa, intr, res, tipo) in rows(name, H_PESOS):
            try:
                t = str(t).strip(); b = inst.setdefault(t, {"k": str(k).strip(), "f": str(f).strip(), "iss": d2n(iss), "r": []})
                b["r"].append([d2n(fe), num(pago), num(am), num(tasa), num(intr), num(res), str(tipo).strip()])
            except Exception as e:
                sys.exit("%s, fila %d: %s" % (os.path.basename(csv_path(name)), n, e))
        for b in inst.values():
            b["r"].sort(key=lambda r: r[0])
        return inst

    usd = {}
    for n, (t, iss, fe, cu, am, res) in rows("Dólares", H_USD):
        try:
            t = str(t).strip(); b = usd.setdefault(t, {"iss": d2n(iss), "r": []})
            b["r"].append([d2n(fe), num(cu), num(am), num(res)])
        except Exception as e:
            sys.exit("flujos_dolares.csv, fila %d: %s" % (n, e))
    for b in usd.values():
        b["r"].sort(key=lambda r: r[0])
    px = {str(t).strip(): num(p) for _, (t, p) in rows("Precio de emisión", ["Ticker", "Precio"]) if t and p not in (None, "")}
    return pesos("Pesos"), usd, pesos("Pesos vencidos"), px


def validate(inst, usd):
    err = []
    for t, b in inst.items():
        if b["k"] not in CLASES:
            err.append("%s: clase «%s» desconocida" % (t, b["k"]))
        for r in b["r"]:
            if r[6] not in ("FIXED_RATE", "CER", "TAMAR", "DOLLAR_LINKED"):
                err.append("%s: tipo «%s» desconocido" % (t, r[6]))
            if r[0] <= b["iss"]:
                err.append("%s: pago del %s anterior a la emisión" % (t, n2d(r[0])))
    for t, b in usd.items():
        for r in b["r"]:
            if r[0] <= b["iss"]:
                err.append("%s: pago del %s anterior a la emisión" % (t, n2d(r[0])))
    if err:
        sys.exit("la planilla tiene errores:\n  " + "\n  ".join(err))


def build(write=True):
    inst, usd, old, px = read_planilla()
    validate(inst, usd)
    changed = []
    for path in PAGES:
        lines, P = read_page(path)
        new = {}
        n, a, o, b = P["PX"]; o["S"] = usd; new[n] = a + dump(o) + b
        n, a, o, b = P["PSD"]; o["INST"] = inst
        for t, ins in inst.items():  # bono nuevo sin historia: la serie arranca en la emisión, con su precio
            if t not in o["H"] and t in px:
                o["H"][t] = {"s": ins["iss"], "d": [0], "p": [px[t]]}
        new[n] = a + dump(o) + b
        n, a, o, b = P["PSOLD"]; o["INST"] = old; new[n] = a + dump(o) + b
        if any(lines[k] != v for k, v in new.items()):
            changed.append(os.path.basename(path))
            for k, v in new.items():
                lines[k] = v
            if write:
                open(path, "w", encoding="utf-8").write("\n".join(lines))
    sin_h = [t for t in inst if t not in P["PSD"][2]["H"]]
    if sin_h:
        print("ojo: sin historia de precios (cargar su precio en data/flujos_precio_emision.csv):", ", ".join(sin_h))
    raw = open(TICKERS, encoding="utf-8").read(); tk = json.loads(raw); END = "\n" if raw.endswith("\n") else ""
    lst = tk if isinstance(tk, list) else None
    if lst is not None:
        falt = [t for t in inst if t not in lst]
        if falt and write:
            open(TICKERS, "w", encoding="utf-8").write(json.dumps(sorted(lst + falt), ensure_ascii=False) + END)
            print("tickers sumados a scripts/pesos_tickers.json:", ", ".join(falt))
    print("páginas actualizadas:" if write else "difieren de la planilla:", ", ".join(changed) or "ninguna")
    return changed


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "export":
        export()
    elif cmd == "build":
        build()
    elif cmd == "check":
        sys.exit(1 if build(write=False) else 0)
    else:
        sys.exit(__doc__)
