#!/usr/bin/env python3
"""Guarda en data/tasas.json lo de la pestaña Tasas cortas (GitHub Action durante la rueda y al cierre). Idempotente.
- cau[fecha]: cierre de la caución en pesos de A3 (api.marketdata.mae.com.ar, histórico de cauciones, moneda $), una fila por plazo:
  [días, tasa promedio ponderada (TNA %), mínima, máxima, monto en pesos, fecha de liquidación].
- fut[fecha]: cierres de los futuros de dólar de A3 (apicem.matbarofex.com.ar, closing-prices):
  [contrato, vencimiento, ajuste, interés abierto, volumen, tasa implícita (TNA %) que publica A3].
- cfut[fecha]: lo mismo para los futuros de tasa de caución (el precio es la tasa): [contrato, vencimiento, ajuste, interés abierto, volumen].
- pf y badlar: tasa de plazo fijo a 30 días (serie 12 del BCRA) y BADLAR de bancos privados (serie 7), TNA %.
- vivo: foto de la rueda por la API de Primary con la cuenta de Bull (secrets ROFEX_USER, ROFEX_PASS, ROFEX_URL; sin ellos no se toma):
    fut y cfut: [contrato, vencimiento, compra, venta, último, ajuste, interés abierto, volumen]
    cau: caución de BYMA en pesos por plazo, [días, compra, venta, última, volumen nominal]
La primera vez trae la historia desde DESDE; después, las últimas dos semanas (A3 y el BCRA a veces corrigen el último dato).
Si una fuente falla, no pisa lo que ya había. Para pruebas: FORCE_DATE (fecha de hoy) y SIN_VIVO=1.
"""
import json, os, re, time, urllib.parse, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "tasas.json")
DESDE = dt.date(2025, 1, 2)
A3 = "https://apicem.matbarofex.com.ar/api/v2/closing-prices?"
CAU = "https://api.marketdata.mae.com.ar/api/mercado/titulo/historicocauciones?oTitulo="
BCRA = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/%d?desde=%s&hasta=%s&limit=3000"
MES = {m: i + 1 for i, m in enumerate("ENE FEB MAR ABR MAY JUN JUL AGO SEP OCT NOV DIC".split())}

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
today = dt.datetime.now(TZ).date()
if os.environ.get("FORCE_DATE"):
    today = dt.date.fromisoformat(os.environ["FORCE_DATE"])


def get(url, t=60, tries=3):
    h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://marketdata.mae.com.ar", "Referer": "https://marketdata.mae.com.ar/"}
    for k in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=t))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 + 3 * k)


def ultimo_habil(y, m):  # los futuros de dólar y de caución vencen el último día hábil del mes (sin contar feriados)
    d = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d.isoformat()


def venc(sym):  # DLR102026, CAUC/OCT26, DLR/OCT26
    m = re.fullmatch(r"DLR(\d{2})(\d{4})", sym)
    if m:
        return ultimo_habil(int(m.group(2)), int(m.group(1)))
    m = re.search(r"/([A-Z]{3})(\d{2})$", sym)
    if m and m.group(1) in MES:
        return ultimo_habil(2000 + int(m.group(2)), MES[m.group(1)])
    return None


def chunks(d0, d1, n):
    while d0 <= d1:
        e = min(d1, d0 + dt.timedelta(days=n - 1))
        yield d0, e
        d0 = e + dt.timedelta(days=1)


num = lambda v: v if isinstance(v, (int, float)) and v == v else None
try:
    db = json.load(open(OUT))
except Exception:
    db = {}
before = json.dumps({k: v for k, v in db.items() if k not in ("generado",)}, sort_keys=True)
for k in ("cau", "fut", "cfut", "pf", "badlar"):
    db.setdefault(k, {})


def desde(key):
    return DESDE if len(db[key]) < 20 else max(DESDE, today - dt.timedelta(days=14))


# --- caución de A3 ---
try:
    n = 0
    for a, b in chunks(desde("cau"), today, 20):
        q = urllib.parse.quote(json.dumps({"fechaDesde": a.isoformat(), "fechaHasta": b.isoformat()}))
        for day in get(CAU + q):
            f, rows = day.get("fecha", "")[:10], []
            for r in day.get("details") or []:
                if r.get("moneda") != "$" or not num(r.get("tasaPP")) or not r["tasaPP"] > 0:
                    continue
                liq = (r.get("fechaLiquidacion") or "")[:10]
                dias = (dt.date.fromisoformat(liq) - dt.date.fromisoformat(f)).days if liq else int(r.get("plazo") or 0)
                rows.append([dias, round(r["tasaPP"], 4), num(r.get("minimo")), num(r.get("maximo")), round(r.get("montoConcertado") or 0), liq])
            if f and rows:
                db["cau"][f] = sorted(rows)
                n += 1
    print("caución A3: %d ruedas" % n)
except Exception as e:
    print("caución A3 no disponible:", e)

# --- futuros de dólar y de caución de A3 (cierres) ---
for key, prod in (("fut", "DLR"), ("cfut", "Tasa de Caución")):
    try:
        n, got = 0, {}
        for a, b in chunks(desde(key), today, 6):  # hasta 100 filas por pedido: 6 días de 14 contratos
            q = urllib.parse.urlencode({"product": prod, "type": "FUT", "from": a.isoformat(), "to": b.isoformat()})
            for r in get(A3 + q).get("data", []):
                f, s = r["dateTime"][:10], r["symbol"]
                if not num(r.get("settlement")):
                    continue
                row = [s, venc(s), r["settlement"], num(r.get("openInterest")), num(r.get("volume"))]
                if key == "fut":
                    if not re.fullmatch(r"DLR\d{6}", s):
                        continue
                    row.append(num(r.get("impliedRate")))
                got.setdefault(f, []).append(row)
        for f, rows in got.items():
            db[key][f] = sorted(rows, key=lambda x: x[1] or "")
            n += 1
        print("%s A3: %d ruedas" % (prod, n))
    except Exception as e:
        print(prod, "A3 no disponible:", e)

# --- BCRA: plazo fijo a 30 días y BADLAR ---
for key, i in (("pf", 12), ("badlar", 7)):
    try:
        rows = get(BCRA % (i, desde(key).isoformat(), today.isoformat()))["results"][0]["detalle"]
        for r in rows:
            if r.get("fecha") and num(r.get("valor")) and r["valor"] > 0:
                db[key][r["fecha"]] = r["valor"]
        print(key, "BCRA:", len(rows), "filas")
    except Exception as e:
        print(key, "BCRA no disponible:", e)

# --- foto en vivo por Primary (Bull) ---
U, P = os.environ.get("ROFEX_USER", "").strip(), os.environ.get("ROFEX_PASS", "").strip()
if U and P and not os.environ.get("SIN_VIVO"):
    try:
        import pyRofex
        url = (os.environ.get("ROFEX_URL") or "https://api.bull.xoms.com.ar").strip().rstrip("/")
        env = pyRofex.Environment.LIVE
        pyRofex._set_environment_parameter("url", url + "/", env)
        pyRofex._set_environment_parameter("ws", url.replace("https://", "wss://") + "/", env)
        pyRofex.initialize(user=U, password=P, account="", environment=env)
        items = pyRofex.get_detailed_instruments(environment=env).get("instruments", [])
        by = {(i.get("instrumentId") or {}).get("symbol", ""): i for i in items}
        E = pyRofex.MarketDataEntry
        ENTS = [E.BIDS, E.OFFERS, E.LAST, E.CLOSING_PRICE, E.SETTLEMENT_PRICE, E.OPEN_INTEREST, E.TRADE_VOLUME, E.NOMINAL_VOLUME]

        def md(s):
            for k in range(4):
                try:
                    r = pyRofex.get_market_data(ticker=s, entries=ENTS, environment=env)
                    if r.get("status") == "OK":
                        return r.get("marketData") or {}
                except Exception:
                    pass
                time.sleep(0.6 + k)
            return None

        px = lambda o: num((o or {}).get("price")) if isinstance(o, dict) else None
        top = lambda l: num(l[0].get("price")) if l else None

        def mat(s):
            m = (by[s].get("maturityDate") or "")
            return "%s-%s-%s" % (m[:4], m[4:6], m[6:8]) if len(m) == 8 else venc(s)

        viv = {"ts": dt.datetime.now(TZ).strftime("%Y-%m-%dT%H:%M"), "fut": [], "cfut": [], "cau": []}
        for key, pat in (("fut", r"DLR/[A-Z]{3}\d{2}"), ("cfut", r"CAUC/[A-Z]{3}\d{2}")):
            for s in sorted((s for s in by if re.fullmatch(pat, s)), key=mat):
                d = md(s)
                if d is None:
                    continue
                viv[key].append([s, mat(s), top(d.get("BI")), top(d.get("OF")), px(d.get("LA")), px(d.get("SE")) or px(d.get("CL")),
                                 (d.get("OI") or {}).get("size") if isinstance(d.get("OI"), dict) else None, num(d.get("TV"))])
        cau = sorted((s for s in by if re.fullmatch(r"MERV - XMEV - PESOS - \d+D", s)), key=lambda s: int(s.rsplit("-", 1)[1].strip()[:-1]))
        for s in cau:
            dias = int(s.rsplit("-", 1)[1].strip()[:-1])
            if dias > 35:
                break
            d = md(s)
            if d is None:
                continue
            row = [dias, top(d.get("BI")), top(d.get("OF")), px(d.get("LA")) or px(d.get("CL")), num(d.get("NV")) or num(d.get("TV"))]
            if any(v for v in row[1:]):
                viv["cau"].append(row)
        print("vivo: %d futuros de dólar, %d de caución, %d plazos de caución" % (len(viv["fut"]), len(viv["cfut"]), len(viv["cau"])))
        same = lambda a, b: {k: v for k, v in (a or {}).items() if k != "ts"} == {k: v for k, v in (b or {}).items() if k != "ts"}
        if (viv["fut"] or viv["cau"]) and not same(viv, db.get("vivo")):  # fuera de la rueda la foto no cambia: no se vuelve a guardar
            db["vivo"] = viv
    except Exception as e:
        m = type(e).__name__ + ": " + str(e)
        for x in (U, P):
            m = m.replace(x, "<x>")
        print("Primary no disponible:", m[:300])

for k in ("cau", "fut", "cfut", "pf", "badlar"):
    db[k] = dict(sorted(db[k].items()))
if json.dumps({k: v for k, v in db.items() if k != "generado"}, sort_keys=True) != before:
    db["generado"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    with open(OUT, "w") as fh:
        json.dump(db, fh, separators=(",", ":"), ensure_ascii=False)
    print("tasas.json actualizado")
else:
    print("sin cambios")
