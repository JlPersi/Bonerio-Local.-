#!/usr/bin/env python3
"""El riesgo país del día, en vivo, en data/riesgo_vivo.json: lo saca la corrida de la rueda de tasas.yml cada 10 minutos.
ArgentinaDatos publica cada dato al día siguiente y la página lee el del día de monedapi.ar o de Ámbito desde el navegador; si esas
lecturas fallan (no responden o el navegador las bloquea), la página usa este archivo. Primero monedapi.ar, después Ámbito.
Formato: {"f": "YYYY-MM-DD", "v": puntos básicos, "h": "HH:MM" (hora de Argentina), "ant": cierre anterior, "src": fuente}.
Si ninguna trae el dato de hoy, no toca nada. Para pruebas: RP_MOCK=/carpeta con monedapi.json, variacion.json e historico.json.
"""
import datetime, json, os, re, urllib.request

AMB = "https://mercados.ambito.com//riesgopais/"
MON = "https://monedapi.ar/api/v2/arg/riesgo"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "riesgo_vivo.json")


def get(name, url):
    if os.environ.get("RP_MOCK"):
        return json.load(open(os.path.join(os.environ["RP_MOCK"], name + ".json")))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def fecha(s):  # Ámbito escribe dd-mm-aaaa o dd/mm/aaaa, a veces con la hora: «20-10-2026 - 11:05»
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", str(s or ""))
    return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1))) if m else None


def num(s):
    try:
        v = float(str(s).replace(".", "").replace(",", "."))
        return int(v) if v == int(v) else v
    except (TypeError, ValueError):
        return None


hoy = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime("%Y-%m-%d")
o = None
try:  # monedapi.ar: {"buy": 710, "sell": 710, "updatedAt": "2026-10-20T10:20:53.492-03:00", "valueType": "points", ...}
    x = get("monedapi", MON)
    x = x.get("data", x) if isinstance(x, dict) else x
    x = x[0] if isinstance(x, list) and x else x
    u = str(x.get("updatedAt") or x.get("lastScrapedAt") or "")
    v = x.get("sell") if x.get("sell") is not None else x.get("buy")
    v = v if isinstance(v, (int, float)) else num(v)
    print("monedapi:", {k: x.get(k) for k in ("buy", "sell", "updatedAt", "lastScrapedAt")})
    if u[:10] == hoy and v and v > 0:
        o = {"f": hoy, "v": v, "h": u[11:16] or None, "ant": None, "src": "monedapi.ar"}
except Exception as e:
    print("monedapi no disponible:", type(e).__name__)
try:
    if o is not None:
        raise StopIteration
    x = get("variacion", AMB + "variacion")
    f, v = fecha(x.get("fecha")), num(x.get("ultimo"))
    h = re.search(r"(\d{1,2}:\d{2})", str(x.get("fecha") or ""))
    print("Ámbito variación:", {k: x.get(k) for k in ("fecha", "ultimo", "valor_cierre_ant")})
    if f == hoy and v and v > 0:
        o = {"f": f, "v": v, "h": h.group(1) if h else None, "ant": num(x.get("valor_cierre_ant")), "src": "Ámbito"}
except StopIteration:
    pass
except Exception as e:
    print("Ámbito variación no disponible:", type(e).__name__)
if o is None:  # el histórico de Ámbito ya trae la rueda de hoy con el último valor
    try:
        d0 = (datetime.date.fromisoformat(hoy) - datetime.timedelta(days=7)).isoformat()
        d1 = (datetime.date.fromisoformat(hoy) + datetime.timedelta(days=1)).isoformat()
        for r in get("historico", AMB + "historico-general/%s/%s" % (d0, d1)):
            if fecha(r[0]) == hoy and (num(r[1]) or 0) > 0:
                o = {"f": hoy, "v": num(r[1]), "h": None, "ant": None, "src": "Ámbito"}
    except Exception as e:
        print("Ámbito histórico no disponible:", type(e).__name__)
if o is None:
    print("riesgo país en vivo: sin dato de hoy"); raise SystemExit(0)
try:
    old = json.load(open(OUT))
except Exception:
    old = None
if old == o:
    print("riesgo país en vivo: sin cambios (%s pb)" % o["v"]); raise SystemExit(0)
with open(OUT, "w") as fh:
    json.dump(o, fh, separators=(",", ":"))
print("riesgo país en vivo: %s pb (%s %s, %s)" % (o["v"], o["f"], o["h"] or "", o["src"]))
