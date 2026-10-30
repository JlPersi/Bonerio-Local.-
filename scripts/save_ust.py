#!/usr/bin/env python3
"""Guarda la curva de Treasuries de EE.UU. (rendimiento par, % anual) en data/ust.json desde FRED (fredgraph.csv, sin clave).
Si FRED falla usa el CSV del Tesoro (home.treasury.gov). Si las dos fallan no pisa nada (la página sigue con lo guardado).
Formato: {"generado": ..., "plazos": [años], "d": {"YYYY-MM-DD": [tasa por plazo o null]}}. Desde 2023.
Para pruebas: UST_MOCK=archivo.csv con las columnas de FRED.
"""
import csv, datetime, io, json, os, urllib.request

IDS = ["DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS3", "DGS5", "DGS7", "DGS10", "DGS20", "DGS30"]
PLAZOS = [1 / 12, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30]
TRE = ["1 Mo", "3 Mo", "6 Mo", "1 Yr", "2 Yr", "3 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr"]
DESDE = "2023-01-01"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "ust.json")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def num(v):
    try:
        x = float(v)
        return x if 0 <= x < 30 else None
    except (TypeError, ValueError):
        return None


def fred():
    txt = open(os.environ["UST_MOCK"]).read() if os.environ.get("UST_MOCK") else get(
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s" % (",".join(IDS), DESDE))
    out = {}
    for r in csv.DictReader(io.StringIO(txt)):
        d = (r.get("observation_date") or r.get("DATE") or "")[:10]
        v = [num(r.get(i)) for i in IDS]
        if len(d) == 10 and d >= DESDE and sum(x is not None for x in v) >= 5:
            out[d] = v
    return out


def tesoro():
    out = {}
    for y in range(int(DESDE[:4]), datetime.date.today().year + 1):
        txt = get("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/%d/all?type=daily_treasury_yield_curve&field_tdr_date_value=%d&page&_format=csv" % (y, y))
        for r in csv.DictReader(io.StringIO(txt)):
            m, dd, yy = (r.get("Date") or "//").split("/")
            d = "%s-%s-%s" % (yy, m.zfill(2), dd.zfill(2))
            v = [num(r.get(c)) for c in TRE]
            if len(d) == 10 and sum(x is not None for x in v) >= 5:
                out[d] = v
    return out


def main():
    d = {}
    for f in (fred, tesoro):
        try:
            d = f()
        except Exception as e:  # la otra fuente
            print(f.__name__, "falló:", e)
        if len(d) > 20:
            break
    if len(d) <= 20:
        print("sin datos de la curva: no se toca", OUT)
        return
    try:  # conserva lo guardado que la fuente ya no trae
        old = json.load(open(OUT)).get("d", {})
        old.update(d)
        d = old
    except Exception:
        pass
    json.dump({"generado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "plazos": [round(p, 6) for p in PLAZOS],
               "d": {k: d[k] for k in sorted(d)}}, open(OUT, "w"), separators=(",", ":"))
    print(len(d), "días; último", max(d))


if __name__ == "__main__":
    main()
