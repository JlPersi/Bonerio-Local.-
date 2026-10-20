#!/usr/bin/env python3
"""Intradiario de los bonos y letras (data912, el mismo precio en vivo de la página): data/intra_bonos.json.
{fecha: {especie: [[minuto del día (hora Argentina), último operado], ...]}}: un punto por especie cada vez que cambia el último
operado, con la foto que saca la corrida de la rueda de tasas.yml (cada pocos minutos, de 10:30 a 17:05). Quedan las dos últimas ruedas,
así fuera del horario la ficha de cada bono muestra la anterior.
La corrida acumula en un archivo fuera del repo (ACUM, para que los git pull de cada foto no lo pisen) y lo copia a data/ al commitear:
  save_intra_bonos.py          foto: agrega los precios de ahora a ACUM (si ACUM no existe, arranca de lo que ya está en data/)
  save_intra_bonos.py --copiar  copia ACUM a data/intra_bonos.json
Si data912 no responde, no toca nada. Para pruebas: FORCE_NOW="2026-10-20 12:34".
"""
import json, os, shutil, sys, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "intra_bonos.json")
ACUM = os.environ.get("INTRA_ACUM", "/tmp/intra_bonos.json")
URLS = ["https://data912.com/live/arg_bonds", "https://data912.com/live/arg_notes"]
TZ = ZoneInfo("America/Argentina/Buenos_Aires")
RUEDAS = 2


def ahora():
    f = os.environ.get("FORCE_NOW")
    return dt.datetime.strptime(f, "%Y-%m-%d %H:%M") if f else dt.datetime.now(TZ)


def leer(p):
    try:
        with open(p) as f:
            o = json.load(f)
        return o if isinstance(o, dict) else {}
    except Exception:
        return {}


def guardar(o, p):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(o, f, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, p)


def precios():
    out = {}
    for u in URLS:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        for r in json.load(urllib.request.urlopen(req, timeout=30)) or []:
            s, c = (r or {}).get("symbol"), (r or {}).get("c")
            if s and isinstance(c, (int, float)) and c > 0:
                out[s] = round(float(c), 4)
    return out


def foto():
    n = ahora()
    hoy, m = n.strftime("%Y-%m-%d"), n.hour * 60 + n.minute
    o = leer(ACUM) if os.path.exists(ACUM) else leer(OUT)
    try:
        px = precios()
    except Exception as e:
        print("data912 no respondió:", type(e).__name__)
        return
    if not px:
        print("data912 vino vacío")
        return
    d = o.setdefault(hoy, {})
    nuevos = 0
    for s, c in px.items():
        a = d.setdefault(s, [])
        if a and a[-1][1] == c:
            continue
        if a and a[-1][0] == m:
            a[-1][1] = c
        else:
            a.append([m, c])
        nuevos += 1
    for k in sorted(o)[:-RUEDAS]:
        del o[k]
    guardar(o, ACUM)
    print("intradiario de bonos: %d especies, %d cambios a las %02d:%02d" % (len(d), nuevos, m // 60, m % 60))


if __name__ == "__main__":
    if "--copiar" in sys.argv:
        if os.path.exists(ACUM):
            shutil.copyfile(ACUM, OUT)
    else:
        foto()
