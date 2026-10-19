#!/usr/bin/env python3
"""Guarda en data/tasas.json lo de la pestaña Tasas cortas (GitHub Action durante la rueda y al cierre). Idempotente.
- cau[fecha] y cauD[fecha]: cierre de la caución de A3 (api.marketdata.mae.com.ar, histórico de cauciones) en pesos y en dólares,
  una fila por plazo: [días, tasa promedio ponderada (TNA %), mínima, máxima, monto, fecha de liquidación]. Hay datos desde 2023.
- fut[fecha]: cierres de los futuros de dólar de A3 (apicem.matbarofex.com.ar, closing-prices):
  [contrato, vencimiento, ajuste, interés abierto, volumen, tasa implícita (TNA %) que publica A3,
   apertura, máximo, mínimo, último operado, variación del interés abierto, cantidad de operaciones].
- cfut[fecha]: lo mismo para los futuros de tasa de caución (el precio es la tasa), con la tasa implícita en null.
- pf y badlar: tasa de plazo fijo a 30 días (serie 12 del BCRA) y BADLAR de bancos privados (serie 7), TNA %. a3500: serie 5 del BCRA.
- spot[fecha]: el dólar spot que usa A3 para su tasa implícita (sale de despejar ajuste / (1 + tasa × días / 365); es uno por rueda).
- f90[fecha]: tasa implícita a 3 meses de los futuros de dólar (TNA %), con ese spot (o el A3500 si falta): (futuro / spot − 1) × 365 / días,
  interpolada a 90 días entre los contratos de 30 días o más. Se calcula desde 2020 con los cierres de A3 (en fut quedan solo los de DESDE en adelante).
- vto: el vencimiento de cada contrato según Primary (el último día hábil del mes; el de diciembre es el 30).
- bcau: caución de BYMA (open.bymadata.com.ar, sin credenciales) en pesos, dólar MEP y dólar cable. vivo.bcau = foto de la rueda por plazo
  [días, compra, venta, última, cierre, vwap, monto]; bcau[fecha] = cierre del plazo más corto de cada moneda [días, cierre, vwap, monto].
- vivo: foto de la rueda por la API de Primary con la cuenta de Bull (secrets ROFEX_USER, ROFEX_PASS, ROFEX_URL; sin ellos no se toma):
    fut y cfut: [contrato, vencimiento, compra, venta, último, ajuste, interés abierto, volumen, apertura, máximo, mínimo]
    cau: caución de BYMA en pesos por plazo, [días, compra, venta, última, volumen nominal]
    spot: el spot de A3 de hoy por Primary (spotF "A3") o, si Primary no tiene uno de hoy, el mayorista de dolarapi.com (spotF "mayorista")
data/intra.json: el intradiario de las últimas ruedas, {fecha: {"cau": {"ARS"|"USD"|"EXT": [[minuto del día, tasa, monto]]}, "cd": {moneda: días},
  "fut": {contrato: [[minuto, último, cantidad]]}}}. La caución es el plazo más corto de BYMA en cada corrida del Action (cada 10 minutos);
  los futuros de dólar y de caución, todas las operaciones del día por Primary agrupadas cada 5 minutos.
La primera vez trae la historia desde DESDE; después, las últimas dos semanas (A3 y el BCRA a veces corrigen el último dato).
Si una fuente falla, no pisa lo que ya había. Para pruebas: FORCE_DATE (fecha de hoy) y SIN_VIVO=1.
"""
import json, os, re, time, urllib.parse, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "tasas.json")
OUTI = os.path.join(os.path.dirname(__file__), "..", "data", "intra.json")
DESDE = dt.date(2025, 1, 2)
DESDE_CAU = dt.date(2022, 6, 1)  # A3 tiene la caución desde 2023
DESDE_F90 = dt.date(2020, 1, 2)  # y los cierres de futuros de dólar desde 2020
A3 = "https://apicem.matbarofex.com.ar/api/v2/closing-prices?"
CAU = "https://api.marketdata.mae.com.ar/api/mercado/titulo/historicocauciones?oTitulo="
MAY = "https://dolarapi.com/v1/dolares/mayorista"
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


NOHAB = {(1, 1), (3, 24), (4, 2), (5, 1), (5, 25), (6, 20), (7, 9), (12, 8), (12, 24), (12, 25), (12, 31)}  # feriados fijos y los días no laborables del 24 y el 31 de diciembre
VTO = {}  # vencimientos que informa Primary (db["vto"]): cubren los feriados móviles


def ultimo_habil(y, m):  # los futuros de dólar y de caución vencen el último día hábil del mes
    d = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
    while d.weekday() >= 5 or (d.month, d.day) in NOHAB:
        d -= dt.timedelta(days=1)
    return d.isoformat()


def psym(sym):  # DLR102026 (A3) -> DLR/OCT26 (Primary)
    m = re.fullmatch(r"DLR(\d{2})(\d{4})", sym)
    return "DLR/%s%s" % (list(MES)[int(m.group(1)) - 1], m.group(2)[2:]) if m else sym


def venc(sym):  # DLR102026, CAUC/OCT26, DLR/OCT26
    if VTO.get(psym(sym)):
        return VTO[psym(sym)]
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


def de_hoy(t):  # fecha de un dato (epoch en ms o ISO) que cae en la rueda de hoy
    try:
        f = dt.datetime.fromtimestamp(t / 1000, TZ) if isinstance(t, (int, float)) else dt.datetime.fromisoformat(str(t).replace("Z", "+00:00")).astimezone(TZ)
        return f.date() == today
    except Exception:
        return False


try:
    db = json.load(open(OUT))
except Exception:
    db = {}
before = json.dumps({k: v for k, v in db.items() if k not in ("generado",)}, sort_keys=True)
KEYS = ("cau", "cauD", "fut", "cfut", "pf", "badlar", "a3500", "f90", "bcau", "vto", "spot")
for k in KEYS:
    db.setdefault(k, {})
VTO.update(db["vto"])


def desde(key, d0=DESDE):  # toda la historia si falta el principio o el formato quedó viejo; si no, las últimas dos semanas
    if len(db[key]) < 20 or min(db[key]) > (d0 + dt.timedelta(days=200)).isoformat():
        return d0
    if key in ("fut", "cfut") and any(len(r) < 12 for v in db[key].values() for r in v):
        return d0
    return max(d0, today - dt.timedelta(days=14))


# --- caución de A3, en pesos y en dólares ---
try:
    n = 0
    for a, b in chunks(min(desde("cau", DESDE_CAU), desde("cauD", DESDE_CAU)), today, 20):
        q = urllib.parse.quote(json.dumps({"fechaDesde": a.isoformat(), "fechaHasta": b.isoformat()}))
        for day in get(CAU + q):
            f, rows = day.get("fecha", "")[:10], {"$": [], "D": []}
            for r in day.get("details") or []:
                if r.get("moneda") not in rows or not num(r.get("tasaPP")) or not r["tasaPP"] > 0:
                    continue
                liq = (r.get("fechaLiquidacion") or "")[:10]
                dias = (dt.date.fromisoformat(liq) - dt.date.fromisoformat(f)).days if liq else int(r.get("plazo") or 0)
                rows[r["moneda"]].append([dias, round(r["tasaPP"], 4), num(r.get("minimo")), num(r.get("maximo")), round(r.get("montoConcertado") or 0), liq])
            for m, key in (("$", "cau"), ("D", "cauD")):
                if f and rows[m]:
                    db[key][f] = sorted(rows[m])
                    n += 1
    print("caución A3: %d filas día-moneda" % n)
except Exception as e:
    print("caución A3 no disponible:", e)

# --- futuros de dólar y de caución de A3 (cierres) ---
OLD = {}  # cierres de futuros anteriores a DESDE: solo para la tasa a 3 meses, no se guardan
for key, prod in (("fut", "DLR"), ("cfut", "Tasa de Caución")):
    try:
        n, got = 0, {}
        d0 = desde(key)
        if key == "fut" and (len(db["f90"]) < 20 or min(db["f90"] or ["9"]) > (DESDE_F90 + dt.timedelta(days=200)).isoformat()
                             or min(db["spot"] or ["9"]) > (DESDE_F90 + dt.timedelta(days=200)).isoformat()):
            d0 = DESDE_F90
        for a, b in chunks(d0, today, 6):  # hasta 100 filas por pedido: 6 días de 14 contratos
            q = urllib.parse.urlencode({"product": prod, "type": "FUT", "from": a.isoformat(), "to": b.isoformat()})
            for r in get(A3 + q).get("data", []):
                f, s = r["dateTime"][:10], r["symbol"]
                if not num(r.get("settlement")):
                    continue
                if key == "fut" and not re.fullmatch(r"DLR\d{6}", s):
                    continue
                row = [s, venc(s), r["settlement"], num(r.get("openInterest")), num(r.get("volume")), num(r.get("impliedRate")) if key == "fut" else None,
                       num(r.get("open")), num(r.get("high")), num(r.get("low")), num(r.get("close")), num(r.get("openInterestChange")), num(r.get("tradeCount"))]
                got.setdefault(f, []).append(row)
        for f, rows in got.items():
            if f < DESDE.isoformat():
                OLD[f] = rows
                continue
            db[key][f] = sorted(rows, key=lambda x: x[1] or "")
            n += 1
        print("%s A3: %d ruedas" % (prod, n))
    except Exception as e:
        print(prod, "A3 no disponible:", e)

# --- BCRA: plazo fijo a 30 días y BADLAR ---
for key, i, d0 in (("pf", 12, DESDE_F90), ("badlar", 7, DESDE_F90), ("a3500", 5, DESDE_F90)):
    try:
        rows = get(BCRA % (i, desde(key, d0).isoformat(), today.isoformat()))["results"][0]["detalle"]
        for r in rows:
            if r.get("fecha") and num(r.get("valor")) and r["valor"] > 0:
                db[key][r["fecha"]] = r["valor"]
        print(key, "BCRA:", len(rows), "filas")
    except Exception as e:
        print(key, "BCRA no disponible:", e)

# --- el dólar spot de A3: el que usa para su tasa implícita (uno por rueda; sale de despejar ajuste / (1 + tasa × días / 365)) ---
def a3spot(f, rows):
    v = []
    for r in rows:
        if r[1] and r[2] and r[5]:
            d = (dt.date.fromisoformat(r[1]) - dt.date.fromisoformat(f)).days
            if d > 0:
                v.append(r[2] / (1 + r[5] / 100 * d / 365))
    v.sort()
    return round(v[len(v) // 2], 4) if v and v[-1] - v[0] < 0.5 else None  # si los contratos no coinciden, el vencimiento está mal: no se usa


# --- tasa implícita a 3 meses de los futuros de dólar, con ese spot (o el A3500 del BCRA si A3 no publicó la tasa) ---
def f90(f, rows):
    ks = [d for d in db["a3500"] if d <= f]
    sp, c = db["spot"].get(f) or (db["a3500"][max(ks)] if ks else None), []
    if not sp:
        return None
    for r in rows:
        if not r[1] or not r[2]:
            continue
        d = (dt.date.fromisoformat(r[1]) - dt.date.fromisoformat(f)).days
        if d >= 30:
            c.append((d, (r[2] / sp - 1) * 365 / d * 100))
    c.sort()
    for (d0, t0), (d1, t1) in zip(c, c[1:]):
        if d0 <= 90 <= d1:
            return round(t0 + (t1 - t0) * (90 - d0) / (d1 - d0), 4)
    return round(c[0][1], 4) if c and c[0][0] > 90 else None


for key in ("fut", "cfut"):  # el vencimiento de cada fila con la regla de hoy (feriados y lo que informa Primary)
    for f, rows in db[key].items():
        for r in rows:
            r[1] = venc(r[0]) or r[1]
        rows.sort(key=lambda x: x[1] or "")
for src in (OLD, db["fut"]):
    for f, rows in src.items():
        if a3spot(f, rows):
            db["spot"][f] = a3spot(f, rows)
        v = f90(f, rows)
        if v is not None:
            db["f90"][f] = v
print("f90: %d ruedas desde %s" % (len(db["f90"]), min(db["f90"] or [""])))

# --- intradiario (archivo aparte): las últimas ruedas ---
try:
    IN = json.load(open(OUTI))
except Exception:
    IN = {}
IN_before = json.dumps(IN, sort_keys=True)
NOW = dt.datetime.now(TZ)
MIN = NOW.hour * 60 + NOW.minute
RUEDA = not os.environ.get("FORCE_DATE") and NOW.weekday() < 5 and 10 * 60 + 25 <= MIN <= 17 * 60 + 10

# --- caución de BYMA (datos abiertos): pesos, dólar MEP y dólar cable ---
pc = lambda v: round(v * 100, 4) if v is not None else None  # BYMA da la tasa como fracción (0,209): se guarda en % (20,9), como A3 y Primary
try:
    BY = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/cauciones"
    body = json.dumps({"excludeZeroPxAndQty": False, "T2": True, "T1": True, "T0": True, "Content-Type": "application/json"}).encode()
    req = urllib.request.Request(BY, data=body, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Accept": "application/json",
                                                         "Origin": "https://open.bymadata.com.ar", "Referer": "https://open.bymadata.com.ar/"})
    lst = json.load(urllib.request.urlopen(req, timeout=40))
    lst = lst.get("data", lst) if isinstance(lst, dict) else lst
    fb = {"ARS": [], "USD": [], "EXT": []}
    for r in lst:
        m, d = r.get("denominationCcy"), r.get("daysToMaturity")
        if m not in fb or not isinstance(d, int) or not 0 < d <= 35:
            continue
        row = [d] + [pc(num(r.get(k))) or None for k in ("bidPrice", "offerPrice", "trade", "closingPrice", "vwap")] + [num(r.get("volumeAmount")) or None]
        if any(row[1:]):
            fb[m].append(row)
    for m in fb:
        fb[m].sort()
    if any(fb.values()):
        viv = db.get("vivo") or {}
        viv["bcau"] = fb
        viv["bts"] = dt.datetime.now(TZ).strftime("%Y-%m-%dT%H:%M")
        db["vivo"] = viv
        if RUEDA:  # el intradiario: el plazo más corto de cada moneda, con la última tasa operada (o la promedio)
            day = IN.setdefault(today.isoformat(), {})
            for m in fb:
                r = next((r for r in fb[m] if r[3] or r[5]), None)
                if r:
                    day.setdefault("cd", {})[m] = r[0]
                    pts = day.setdefault("cau", {}).setdefault(m, [])
                    pt = [MIN, r[3] or r[5], r[6]]
                    if not pts or pts[-1][1:] != pt[1:]:
                        pts.append(pt)
        if dt.datetime.now(TZ).hour >= 17:  # al cierre: el plazo más corto de cada moneda queda en la historia
            cl = {m: [r[0], r[4], r[5], r[6]] for m in fb for r in fb[m][:1] if r[4]}
            if cl:
                db["bcau"][today.isoformat()] = cl
    print("caución BYMA:", {m: len(v) for m, v in fb.items()})
except Exception as e:
    print("caución BYMA no disponible:", e)

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
        ENTS = [E.BIDS, E.OFFERS, E.LAST, E.CLOSING_PRICE, E.SETTLEMENT_PRICE, E.OPEN_INTEREST, E.TRADE_VOLUME, E.NOMINAL_VOLUME,
                E.OPENING_PRICE, E.HIGH_PRICE, E.LOW_PRICE]

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

        for s in by:  # los vencimientos de Primary quedan para las próximas corridas
            if re.fullmatch(r"(DLR|CAUC)/[A-Z]{3}\d{2}", s) and len(by[s].get("maturityDate") or "") == 8:
                db["vto"][s] = mat(s)

        viv = {"ts": dt.datetime.now(TZ).strftime("%Y-%m-%dT%H:%M"), "fut": [], "cfut": [], "cau": []}
        if "DLR/SPOT" in by:  # el spot de A3 en la rueda, si Primary lo publica y es de hoy (el cierre que repite es el de la rueda anterior)
            d = (md("DLR/SPOT") or {}).get("LA")
            if isinstance(d, dict) and de_hoy(d.get("date")):
                viv["spot"], viv["spotF"] = px(d), "A3"
        if not viv.get("spot"):  # si no, el mayorista de hoy
            try:
                m = get(MAY, t=20)
                if de_hoy(m.get("fechaActualizacion")) and num(m.get("venta")):
                    viv["spot"], viv["spotF"] = m["venta"], "mayorista"
            except Exception as e:
                print("mayorista no disponible:", type(e).__name__)
        for key, pat in (("fut", r"DLR/[A-Z]{3}\d{2}"), ("cfut", r"CAUC/[A-Z]{3}\d{2}")):
            for s in sorted((s for s in by if re.fullmatch(pat, s)), key=mat):
                d = md(s)
                if d is None:
                    continue
                viv[key].append([s, mat(s), top(d.get("BI")), top(d.get("OF")), px(d.get("LA")), px(d.get("SE")) or px(d.get("CL")),
                                 (d.get("OI") or {}).get("size") if isinstance(d.get("OI"), dict) else None, num(d.get("TV")),
                                 px(d.get("OP")), px(d.get("HI")), px(d.get("LO"))])
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
        # intradiario de los futuros: las operaciones de hoy y de las ruedas anteriores que falten, cada 5 minutos
        habiles = [today - dt.timedelta(days=i) for i in range(8) if (today - dt.timedelta(days=i)).weekday() < 5][:5]
        nh = 0
        for f in habiles:
            k = f.isoformat()
            if k != today.isoformat() and (IN.get(k) or {}).get("fut"):
                continue
            got = {}
            for s in [r[0] for r in viv["fut"]] + [r[0] for r in viv["cfut"]]:
                try:
                    tr = pyRofex.get_trade_history(ticker=s, start_date=f, end_date=f, environment=env).get("trades") or []
                except Exception:
                    continue
                b5 = {}
                for t in sorted(tr, key=lambda t: t.get("servertime") or 0):
                    if not num(t.get("price")) or not t.get("servertime"):
                        continue
                    h = dt.datetime.fromtimestamp(t["servertime"] / 1000, TZ)
                    if h.date() != f:
                        continue
                    m5 = (h.hour * 60 + h.minute) // 5 * 5
                    o = b5.setdefault(m5, [m5, t["price"], 0])
                    o[1] = t["price"]
                    o[2] += num(t.get("size")) or 0
                if b5:
                    got[s] = [b5[m] for m in sorted(b5)]
            if got:
                IN.setdefault(k, {})["fut"] = got
                nh += 1
        print("intradiario de futuros: %d ruedas" % nh)
        old = db.get("vivo") or {}
        for k in ("bcau", "bts"):  # la foto de BYMA se toma aparte
            if k in old:
                viv[k] = old[k]
        same = lambda a, b: {k: v for k, v in (a or {}).items() if k not in ("ts", "bts")} == {k: v for k, v in (b or {}).items() if k not in ("ts", "bts")}
        if (viv["fut"] or viv["cau"]) and not same(viv, old):  # fuera de la rueda la foto no cambia: no se vuelve a guardar
            db["vivo"] = viv
    except Exception as e:
        m = type(e).__name__ + ": " + str(e)
        for x in (U, P):
            m = m.replace(x, "<x>")
        print("Primary no disponible:", m[:300])

IN = {k: IN[k] for k in sorted(IN)[-6:]}  # las últimas seis ruedas
if json.dumps(IN, sort_keys=True) != IN_before:
    with open(OUTI, "w") as fh:
        json.dump(IN, fh, separators=(",", ":"))
    print("intra.json actualizado")
for k in KEYS:
    db[k] = dict(sorted(db[k].items()))
strip = lambda o: {k: ({a: b for a, b in v.items() if a != "bts"} if k == "vivo" and isinstance(v, dict) else v) for k, v in o.items() if k != "generado"}
if json.dumps(strip(db), sort_keys=True) != json.dumps(strip(json.loads(before)), sort_keys=True):
    db["generado"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    with open(OUT, "w") as fh:
        json.dump(db, fh, separators=(",", ":"), ensure_ascii=False)
    print("tasas.json actualizado")
else:
    print("sin cambios")
