#!/usr/bin/env python3
"""Guarda el riesgo país (EMBI, en puntos básicos) en data/riesgo_pais.json desde la API de ArgentinaDatos.
Trae el histórico completo y le suma el último dato. ArgentinaDatos publica cada dato al día siguiente, así que las
ruedas que todavía no tiene salen del histórico de Ámbito (mismos valores; ArgentinaDatos las pisa cuando las publica).
Si las fuentes fallan no pisa nada (la página sigue con lo guardado).
Formato: {"d": {"YYYY-MM-DD": valor}}. Para pruebas: RP_MOCK=/carpeta con historico.json y ultimo.json.
"""
import datetime, json, os, urllib.request

BASE = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais"
AMB = "https://mercados.ambito.com//riesgopais/historico-general/%s/%s"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "riesgo_pais.json")


def get(name, url):
    if os.environ.get("RP_MOCK"):
        return json.load(open(os.path.join(os.environ["RP_MOCK"], name + ".json")))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=40))


def rows(x):  # acepta una lista de {fecha, valor} o un solo objeto
    for r in (x if isinstance(x, list) else [x]):
        if not isinstance(r, dict):
            continue
        f, v = str(r.get("fecha") or "")[:10], r.get("valor")
        if len(f) == 10 and isinstance(v, (int, float)) and v > 0:
            yield f, v


try:
    db = json.load(open(OUT))
except Exception:
    db = {"d": {}}
d, n0 = db.setdefault("d", {}), len(db.get("d", {}))
ok = False
for name, url in (("historico", BASE), ("ultimo", BASE + "/ultimo")):
    try:
        for f, v in rows(get(name, url)):
            d[f] = v
        ok = True
    except Exception as e:
        print(name, "no disponible:", e)
try:  # Ámbito: [["Fecha","Puntos"],["14-10-2026","611,00"],...]; solo completa las fechas que faltan
    hoy = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
    for r in get("ambito", AMB % ((hoy - datetime.timedelta(days=20)).strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d"))):
        p = str(r[0]).split("-")
        if len(p) != 3 or len(p[2]) != 4:
            continue
        f = "%s-%s-%s" % (p[2], p[1], p[0])
        try:
            v = float(str(r[1]).replace(".", "").replace(",", "."))
        except ValueError:
            continue
        if v > 0 and f not in d:
            d[f] = int(v) if v == int(v) else v
            ok = True
except Exception as e:
    print("ambito no disponible:", e)
if not ok or not d:
    print("riesgo país: sin datos nuevos"); raise SystemExit(0)
db["d"] = dict(sorted(d.items()))
with open(OUT, "w") as fh:
    json.dump(db, fh, separators=(",", ":"))
k = sorted(d)
print("riesgo país: %d datos (%d nuevos), último %s = %s pb" % (len(d), len(d) - n0, k[-1], d[k[-1]]))
