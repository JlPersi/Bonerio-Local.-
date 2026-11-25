#!/usr/bin/env python3
"""Volumen de contado inmediato (CI) de cada especie por el websocket de Primary (cuenta de Bull): data/volumen_ci.json.
data912 (data/volumen.json) trae solo 24 hs; esto suma el CI para la pestaña Volumen (24 hs, CI o los dos).
Formato: {"d": {"AAAA-MM-DD": {"AL30C": [monto, VN], ...}}}, monto en la moneda de la especie (pesos o dólares).
Solo con los secrets ROFEX_USER, ROFEX_PASS y ROFEX_URL; sin ellos no hace nada. Las cotizaciones van por websocket, no por REST.
Idempotente: cada corrida pisa el día con el último acumulado. Se guarda solo lo que operó hoy (la fecha del último operado).
"""
import json, os, sys, time, datetime as dt
from zoneinfo import ZoneInfo

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "data", "volumen_ci.json")
VOL = os.path.join(HERE, "..", "data", "volumen.json")
TZ = ZoneInfo("America/Argentina/Buenos_Aires")
today = dt.datetime.now(TZ).date()
if today.weekday() >= 5:
    print("fin de semana"); sys.exit(0)
U, P = os.environ.get("ROFEX_USER", "").strip(), os.environ.get("ROFEX_PASS", "").strip()
if not (U and P):
    print("sin credenciales de Primary, no se toma el CI"); sys.exit(0)
num = lambda v: float(v) if isinstance(v, (int, float)) and v == v else None


def de_hoy(t):
    try:
        f = dt.datetime.fromtimestamp(t / 1000, TZ) if isinstance(t, (int, float)) else dt.datetime.fromisoformat(str(t).replace("Z", "+00:00")).astimezone(TZ)
        return f.date() == today
    except Exception:
        return False


import pyRofex
url = (os.environ.get("ROFEX_URL") or "https://api.bull.xoms.com.ar").strip().rstrip("/")
env = pyRofex.Environment.LIVE
pyRofex._set_environment_parameter("url", url + "/", env)
pyRofex._set_environment_parameter("ws", url.replace("https://", "wss://") + "/", env)
pyRofex.initialize(user=U, password=P, account="", environment=env)
valid = {(i.get("instrumentId") or {}).get("symbol", "") for i in pyRofex.get_detailed_instruments(environment=env).get("instruments", [])}  # la lista de instrumentos (no son cotizaciones)

V = json.load(open(VOL))
tks = sorted(set(V.get("t", {})) | set(V.get("on", [])))
syms = {"MERV - XMEV - %s - CI" % t: t for t in tks}
syms = {s: t for s, t in syms.items() if s in valid}
print("especies CI:", len(syms))

got = {}


def on_md(m):
    try:
        s = ((m.get("instrumentId") or {}).get("symbol")) or ""
        if s in syms:
            got[s] = m.get("marketData") or {}
    except Exception:
        pass


pyRofex.init_websocket_connection(market_data_handler=on_md, error_handler=lambda m: None, exception_handler=lambda e: None, environment=env)
E = pyRofex.MarketDataEntry
L = list(syms)
for i in range(0, len(L), 400):
    pyRofex.market_data_subscription(tickers=L[i:i + 400], entries=[E.LAST, E.TRADE_EFFECTIVE_VOLUME, E.NOMINAL_VOLUME], environment=env)
    time.sleep(1)
t0 = time.time()
while time.time() - t0 < 25 and len(got) < len(L):
    time.sleep(1)
try:
    pyRofex.close_websocket_connection(environment=env)
except Exception:
    pass
print("respondieron:", len(got))

day = {}
for s, d in got.items():
    la = d.get("LA") if isinstance(d.get("LA"), dict) else None
    if not la or not de_hoy(la.get("date")):
        continue
    nv, ev, px = num(d.get("NV")), num(d.get("EV")), num(la.get("price"))
    if not nv or nv <= 0:
        continue
    ref = nv * px / 100 if px else None  # los bonos cotizan por cada 100 nominales
    m = ev
    if ref:  # el monto efectivo de Primary puede venir en otra escala: se toma solo si confirma el de VN × precio
        if ev and 0.6 < ev / ref < 1.6:
            m = ev
        elif ev and 0.6 < ev * 100 / ref < 1.6:
            m = ev * 100
        else:
            m = ref
    if m and m > 0:
        day[syms[s]] = [round(m), round(nv)]
print("operaron hoy en CI:", len(day))
if len(day) < 5:
    print("muy pocas especies (feriado o respuesta incompleta), no se guarda"); sys.exit(0)

try:
    db = json.load(open(OUT))
except Exception:
    db = {"d": {}}
db.setdefault("d", {})[today.isoformat()] = day
db["d"] = dict(sorted(db["d"].items()))
with open(OUT, "w") as f:
    json.dump(db, f, separators=(",", ":"))
print("guardado", today, len(day))
