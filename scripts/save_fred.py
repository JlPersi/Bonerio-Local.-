"""Spreads (OAS) de los índices ICE BofA desde FRED, para comparar las ONs con sus pares internacionales.

Escribe data/fred_spreads.json: {"generado": ..., "s": {id: {fecha: pb}}}. Usa el CSV público de FRED (sin clave);
si hay FRED_API_KEY en el entorno, usa la API. Si una serie falla, conserva lo que ya había.
"""
import csv, io, json, os, sys, urllib.request, datetime

DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DIR, "fred_spreads.json")
SERIES = ["BAMLEMHBHYCRPIOAS", "BAMLH0A2HYB", "BAMLEMRLCRPILAOAS"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bonerio-local)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def serie(sid):
    key = os.environ.get("FRED_API_KEY")
    out = {}
    if key:
        j = json.loads(get("https://api.stlouisfed.org/fred/series/observations?series_id=%s&api_key=%s&file_type=json" % (sid, key)))
        for o in j.get("observations", []):
            if o["value"] not in (".", ""):
                out[o["date"]] = round(float(o["value"]) * 100, 1)
    else:
        rows = list(csv.reader(io.StringIO(get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + sid))))
        for r in rows[1:]:
            if len(r) >= 2 and r[1] not in (".", ""):
                out[r[0]] = round(float(r[1]) * 100, 1)
    return out


def main():
    try:
        prev = json.load(open(OUT))
    except Exception:
        prev = {"s": {}}
    s = prev.get("s", {})
    ok = 0
    for sid in SERIES:
        try:
            v = serie(sid)
            if len(v) > 50:
                s[sid] = {**s.get(sid, {}), **v}
                ok += 1
                print(sid, len(v), "datos, último", max(v))
        except Exception as e:
            print("falló", sid, e, file=sys.stderr)
    if not ok:
        sys.exit("FRED no respondió")
    json.dump({"generado": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "s": s}, open(OUT, "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
