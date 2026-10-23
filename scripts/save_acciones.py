#!/usr/bin/env python3
"""Precios de acciones argentinas (panel líder y panel general) en data/acciones/<TICKER>.json.

Dos modos:
- Diario (por defecto, en el Action de cierre): toma /live/arg_stocks de data912 y agrega el cierre del día a cada ticker.
- Histórico (FULL=1, Action "Acciones: bajar histórico"): baja /historical/stocks/<TICKER> de cada ticker y reescribe su archivo.
  TICKERS=GGAL,YPFD limita la descarga a esos tickers.

Formato de cada archivo: {"t": "GGAL", "panel": "lider"|"general", "cols": ["d","o","h","l","c","v"], "r": [["2024-01-02", o, h, l, c, v], ...]}
(o, h, l pueden ser null en los días agregados por el modo diario, porque /live solo trae el último precio).
data/acciones/index.json: la lista de tickers con su panel, primera y última fecha y cantidad de ruedas.
data/acciones/saltos.json: variaciones de más de 35% entre dos ruedas, candidatas a split o dividendo no ajustado (para revisar).
Para pruebas: SOURCE_FILE=respuesta_live.json, HIST_DIR=carpeta con <TICKER>.json, FORCE_DATE=2026-10-13.
"""
import json, os, sys, time, math, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

BASES = ["https://data912.com", "https://api.data912.com"]
HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "..", "data", "acciones")
# Panel líder de BYMA (octubre 2026, como lo muestra la pantalla del broker): lo que no está acá es panel general.
# El índice (data/acciones/index.json) toma el panel de esta lista cada vez que se arma.
LIDER = {"ALUA", "BBAR", "BMA", "BYMA", "CEPU", "CRES", "ECOG", "EDN", "GGAL", "LOMA", "METR", "PAMP",
         "SUPV", "TGNO4", "TGSU2", "TRAN", "TXAR", "VALO", "YPFD"}
SALTO = 0.35


def get(path):
    err = None
    for b in BASES:
        for k in range(3):
            try:
                req = urllib.request.Request(b + path, headers={"User-Agent": "Mozilla/5.0"})
                return json.load(urllib.request.urlopen(req, timeout=40))
            except Exception as e:
                err = e; time.sleep(2 * (k + 1))
    raise err


def num(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def pick(r, names):
    for n in names:
        if n in r and r[n] is not None:
            return r[n]
    return None


def norm_date(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):  # epoch en segundos o milisegundos
        x = x / 1000 if x > 1e11 else x
        return dt.datetime.fromtimestamp(x, dt.timezone.utc).date().isoformat()
    return str(x)[:10]


def norm_rows(data):
    """Acepta lista de dicts (date/o/h/l/c/v con variantes de nombre) o dict de columnas."""
    if isinstance(data, dict):
        for k in ("data", "results", "rows", "historical"):
            if isinstance(data.get(k), list):
                data = data[k]; break
        else:
            cols = {k: v for k, v in data.items() if isinstance(v, list)}
            if cols:
                n = max(len(v) for v in cols.values())
                data = [{k: (v[i] if i < len(v) else None) for k, v in cols.items()} for i in range(n)]
    out = {}
    for r in data or []:
        if not isinstance(r, dict):
            continue
        d = norm_date(pick(r, ["date", "fecha", "d", "t", "time", "timestamp"]))
        c = num(pick(r, ["c", "close", "cierre", "px_close", "last", "price"]))
        if not d or not c or c <= 0:
            continue
        out[d] = [d, num(pick(r, ["o", "open", "apertura"])), num(pick(r, ["h", "high", "max", "maximo"])),
                  num(pick(r, ["l", "low", "min", "minimo"])), c, num(pick(r, ["v", "volume", "vol", "volumen"]))]
    return [out[d] for d in sorted(out)]


def path(t):
    return os.path.join(DIR, t + ".json")


def load(t):
    try:
        return json.load(open(path(t)))
    except Exception:
        return None


def save(t, rows):
    o = {"t": t, "panel": "lider" if t in LIDER else "general", "cols": ["d", "o", "h", "l", "c", "v"], "r": rows}
    with open(path(t), "w") as f:
        json.dump(o, f, separators=(",", ":"))


def live():
    if os.environ.get("SOURCE_FILE"):
        return json.load(open(os.environ["SOURCE_FILE"]))
    return get("/live/arg_stocks")


def tickers_from_live(rows):
    out = {}
    for r in rows:
        s = str(r.get("symbol", "")).strip().upper()
        c = num(r.get("c"))
        if s and c and c > 0:
            out[s] = r
    return out


def write_index():
    idx, saltos = [], []
    for fn in sorted(os.listdir(DIR)):
        if not fn.endswith(".json") or fn in ("index.json", "saltos.json", "metricas.json", "ratios.json"):
            continue
        o = json.load(open(os.path.join(DIR, fn)))
        r = o.get("r") or []
        if not r:
            continue
        idx.append({"t": o["t"], "panel": "lider" if o["t"] in LIDER else "general", "desde": r[0][0], "hasta": r[-1][0], "n": len(r)})
        for a, b in zip(r, r[1:]):
            if a[4] and b[4] and abs(b[4] / a[4] - 1) > SALTO:
                saltos.append({"t": o["t"], "de": a[0], "a": b[0], "c0": a[4], "c1": b[4], "var": round(b[4] / a[4] - 1, 4)})
    json.dump(idx, open(os.path.join(DIR, "index.json"), "w"), separators=(",", ":"))
    json.dump(saltos, open(os.path.join(DIR, "saltos.json"), "w"), indent=0)
    print("index: %d tickers · %d saltos de más de %d%% para revisar" % (len(idx), len(saltos), SALTO * 100))


def full():
    want = [t.strip().upper() for t in os.environ.get("TICKERS", "").split(",") if t.strip()]
    if not want:
        L = tickers_from_live(live())
        want = sorted(t for t in L if "." not in t and not (t[-1] in "DC" and t[:-1] in L))  # sin las especies en dólares
    print("histórico de %d tickers" % len(want))
    ok = 0
    for i, t in enumerate(want):
        try:
            if os.environ.get("HIST_DIR"):
                data = json.load(open(os.path.join(os.environ["HIST_DIR"], t + ".json")))
            else:
                data = get("/historical/stocks/" + t)
            if i == 0:  # deja en el log la forma de la respuesta, para revisar nombres de campos
                print("muestra", t, json.dumps(data[:2] if isinstance(data, list) else {k: str(v)[:120] for k, v in list(data.items())[:6]})[:600])
            rows = norm_rows(data)
            if len(rows) < 5:
                print("  %s: sin datos útiles (%d filas)" % (t, len(rows))); continue
            old = load(t)
            if old:  # conserva los días diarios que el histórico todavía no trae
                have = {r[0] for r in rows}
                rows += [r for r in old.get("r", []) if r[0] not in have and r[0] > rows[-1][0]]
            save(t, rows); ok += 1
            print("  %s: %d ruedas, %s a %s" % (t, len(rows), rows[0][0], rows[-1][0]))
        except Exception as e:
            print("  %s: error %s" % (t, e))
        time.sleep(0.4)
    print("ok %d de %d" % (ok, len(want)))
    write_index()


def daily():
    today = dt.datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    if os.environ.get("FORCE_DATE"):
        today = dt.date.fromisoformat(os.environ["FORCE_DATE"])
    if today.weekday() >= 5:
        print("fin de semana, no se guarda"); return
    ds = today.isoformat()
    L = tickers_from_live(live())
    if len(L) < 5:
        print("respuesta incompleta (%d tickers), no se guarda" % len(L)); sys.exit(1)
    same = tot = 0
    upd = {}
    for t, r in L.items():
        old = load(t)
        if not old and t in LIDER:  # del panel líder sin histórico en data912 (ECOG): arranca con el cierre de hoy
            old = {"r": []}
        if not old:  # solo tickers con histórico: /live/arg_stocks también trae las especies en dólares (GGALD, BMA.D...) y otros papeles
            continue
        rows = old.get("r", [])
        c = num(r.get("c"))
        prev = [x for x in rows if x[0] < ds]
        if prev:
            tot += 1
            if prev[-1][4] == c:
                same += 1
        cur = [x for x in rows if x[0] == ds]
        if cur and cur[0][1] is not None:  # ese día ya vino completo del histórico (con apertura, máximo y mínimo)
            continue
        upd[t] = (rows, [ds, None, None, None, c, num(r.get("v"))])
    if tot and same == tot:
        print("precios idénticos al cierre anterior (feriado?), no se guarda"); return
    for t, (rows, new) in upd.items():
        rows = [x for x in rows if x[0] != ds] + [new]
        rows.sort(key=lambda x: x[0])
        save(t, rows)
    print("cierre %s: %d tickers con histórico" % (ds, len(upd)))
    write_index()


if __name__ == "__main__":
    os.makedirs(DIR, exist_ok=True)
    full() if os.environ.get("FULL") else daily()
