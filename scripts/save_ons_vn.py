#!/usr/bin/env python3
"""Valor nominal en circulación de las ONs y provinciales (data/ons.json y data/pvs.json), de la ficha técnica de BYMA (datos abiertos, sin credenciales).
Sirve para el Calendario de cobros: lo que paga cada emisor = flujo cada 100 VN × VN en circulación.
Sale data/ons_vn.json: {"act": fecha, "t": {ticker: [VN emitido, VN residual, moneda]}} (montoNominal y montoResidual de BYMA, en unidades). Lo que BYMA no devuelve se conserva de la corrida anterior.
Uso: python3 scripts/save_ons_vn.py [--max N] [--log]   (corre en el Action "ONs: VN en circulación"; desde el sandbox BYMA no responde)"""
import datetime as dt, json, os, re, sys, time, urllib.request

D = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(D, "ons_vn.json")
URL = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/bnown/fichatecnica/especies/general"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/json", "Origin": "https://open.bymadata.com.ar", "Referer": "https://open.bymadata.com.ar/"}


def ficha(sym):
    req = urllib.request.Request(URL, data=json.dumps({"symbol": sym, "Content-Type": "application/json"}).encode(), headers=H)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def plano(j, pre=""):
    """todos los pares clave/valor de la respuesta, aplanados"""
    out = {}
    if isinstance(j, dict):
        for k, v in j.items():
            out.update(plano(v, pre + k + "."))
    elif isinstance(j, list):
        for i, v in enumerate(j[:3]):
            out.update(plano(v, pre + str(i) + "."))
    else:
        out[pre[:-1]] = j
    return out


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(".", "").replace(",", ".") if re.search(r"\d\.\d{3}", v) else v.strip().replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def main():
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 0
    log = "--log" in sys.argv
    prev = json.load(open(OUT)) if os.path.exists(OUT) else {"t": {}}
    esp = {}
    for f in ("ons.json", "pvs.json"):
        try:
            for k, o in json.load(open(os.path.join(D, f))).get("on", {}).items():
                esp[k] = o.get("o") or k + "O"
        except Exception as e:
            print(f, "no se pudo leer:", e)
    keys = sorted(esp)[:mx] if mx else sorted(esp)
    T, ok, n = dict(prev.get("t", {})), 0, 0
    for k in keys:
        n += 1
        got = None
        for sym in (esp[k], k, k + "D"):
            try:
                j = ficha(sym)
            except Exception as e:
                if log:
                    print(k, sym, "error", str(e)[:120])
                continue
            P = plano(j)
            if log and n <= 3:
                print(k, sym, json.dumps(P, ensure_ascii=False)[:1500])
            d = next((x for x in (j.get("data") or []) if isinstance(x, dict)), None) if isinstance(j, dict) else None
            if d and num(d.get("montoNominal")):
                got = [num(d.get("montoNominal")), num(d.get("montoResidual")), d.get("moneda") or ""]
            if got:
                break
            time.sleep(0.2)
        if got:
            T[k] = got
            ok += 1
        time.sleep(0.15)
    print(f"{ok} de {len(keys)} con VN de BYMA")
    if ok:
        json.dump({"act": dt.date.today().isoformat(), "t": T}, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
