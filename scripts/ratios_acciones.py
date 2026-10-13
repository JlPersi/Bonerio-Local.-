#!/usr/bin/env python3
"""Ratios fundamentales a partir de los balances cargados en data/acciones/balances/<TICKER>.json y los precios de
data/acciones/<TICKER>.json -> data/acciones/ratios.json. El formato de los balances está en data/acciones/balances/README.md.

Ratios (con el último balance publicado a cada fecha):
- P/E TTM = capitalización / resultado neto atribuible a la controlante de los últimos 12 meses
- P/VL = capitalización / patrimonio neto de la controlante
- EV/EBITDA TTM, con EV = capitalización + deuda financiera − caja e inversiones y EBITDA = resultado operativo + depreciaciones
- ROE TTM, margen EBITDA y margen neto
Inflación (NIC 29): cada balance está en moneda de su fecha de cierre. Para sumar trimestres (TTM) y para comparar con el precio de
hoy se reexpresa todo con el CER (aproximación del IPC, que va unos 45 días atrás) hasta la fecha del cálculo.
TTM con estados acumulados: acumulado actual + último anual − mismo acumulado del año anterior (cada uno reexpresado).
"""
import json, os, re, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DIR = os.path.join(ROOT, "data", "acciones")
BAL = os.path.join(DIR, "balances")
D0 = dt.date(1970, 1, 1)


def dnum(s):
    return (dt.date.fromisoformat(s) - D0).days


def load_cer():
    """CER diario: la serie larga de index.html (desde 2003) y encima data/indices.json (lo último del BCRA)."""
    cer = {}
    try:
        html = open(os.path.join(ROOT, "index.html"), encoding="utf8").read()
        m = re.search(r'"CER":\{"s":(\d+),"v":\[([^\]]*)\]', html)
        if m:
            s = int(m.group(1))
            for k, x in enumerate(m.group(2).split(",")):
                cer[s + k] = float(x)
    except Exception as e:
        print("CER de index.html no disponible:", e)
    try:
        for d, v in json.load(open(os.path.join(ROOT, "data", "indices.json")))["CER"].items():
            cer[dnum(d)] = float(v)
    except Exception:
        pass
    keys = sorted(cer)
    def at(d):
        t = dnum(d) if isinstance(d, str) else d
        if not keys:
            return None
        if t >= keys[-1]:
            return cer[keys[-1]]
        while t not in cer and t > keys[0]:
            t -= 1
        return cer.get(t)
    return at


def ttm(per, i, key, cer):
    """Flujo de los últimos 12 meses del período i, en moneda de su cierre."""
    p = per[i]; v = p.get("resultados", {}).get(key)
    if v is None:
        return None
    m = p.get("acumulado_meses", 12)
    if m == 12:
        return v
    y = int(p["cierre"][:4])
    ann = [q for q in per if q.get("acumulado_meses", 12) == 12 and q["cierre"] < p["cierre"] and q["cierre"] >= "%d-%s" % (y - 1, p["cierre"][5:])]
    same = [q for q in per if q.get("acumulado_meses") == m and q["cierre"][:4] == str(y - 1) and q["cierre"][5:7] == p["cierre"][5:7]]
    if not ann or not same:
        return None
    a, s = ann[-1], same[-1]
    va, vs = a.get("resultados", {}).get(key), s.get("resultados", {}).get(key)
    if va is None or vs is None:
        return None
    k = lambda q: cer(p["cierre"]) / cer(q["cierre"])
    return v + va * k(a) - vs * k(s)


def publicado(p):
    if p.get("publicado"):
        return p["publicado"]
    extra = 70 if p.get("acumulado_meses", 12) == 12 else 42  # plazos de presentación a la CNV
    return (dt.date.fromisoformat(p["cierre"]) + dt.timedelta(days=extra)).isoformat()


def div(a, b):
    return round(a / b, 4) if a is not None and b not in (None, 0) else None


def main():
    if not os.path.isdir(BAL):
        print("sin carpeta de balances"); return
    cer = load_cer()
    out = {"generado": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "t": {}}
    for fn in sorted(os.listdir(BAL)):
        if not fn.endswith(".json") or fn.startswith("plantilla"):
            continue
        b = json.load(open(os.path.join(BAL, fn)))
        t = b["t"]; esc = b.get("escala", 1)  # multiplicador de los montos (1e6 si están en millones de pesos)
        per = sorted(b.get("periodos", []), key=lambda p: p["cierre"])
        if not per:
            continue
        calc = []
        for i, p in enumerate(per):
            r, s = p.get("resultados", {}), p.get("situacion", {})
            ni = ttm(per, i, "resultado_neto_controlante", cer)
            if ni is None:
                ni = ttm(per, i, "resultado_neto", cer)
            ebit, da, ven = ttm(per, i, "resultado_operativo", cer), ttm(per, i, "depreciaciones", cer), ttm(per, i, "ventas", cer)
            pn = s.get("patrimonio_neto_controlante", s.get("patrimonio_neto"))
            calc.append({"cierre": p["cierre"], "pub": publicado(p), "acciones": p.get("acciones") or b.get("acciones"),
                         "ni": ni, "ebitda": (ebit + da) if ebit is not None and da is not None else None, "ventas": ven,
                         "pn": pn, "deuda": s.get("deuda_financiera"), "caja": s.get("caja_inversiones")})
        try:
            px = [(r[0], r[4]) for r in json.load(open(os.path.join(DIR, t + ".json")))["r"] if r[4]]
        except Exception:
            px = []
        serie, last = [], None
        for d, price in px:
            av = [c for c in calc if c["pub"] <= d]
            if not av:
                continue
            c = av[-1]
            if not c["acciones"]:
                continue
            f = cer(d) / cer(c["cierre"]) * esc  # balance reexpresado a moneda del día del precio
            mcap = price * c["acciones"]
            ev = mcap + ((c["deuda"] or 0) - (c["caja"] or 0)) * f if c["deuda"] is not None or c["caja"] is not None else None
            row = {"d": d, "pe": div(mcap, c["ni"] * f if c["ni"] is not None else None),
                   "pvl": div(mcap, c["pn"] * f if c["pn"] is not None else None),
                   "ev_ebitda": div(ev, c["ebitda"] * f if c["ebitda"] is not None else None)}
            serie.append([d, row["pe"], row["pvl"], row["ev_ebitda"]]); last = (row, c, mcap)
        res = {"balances": len(per), "serie_cols": ["d", "pe", "pvl", "ev_ebitda"], "serie": serie}
        if last:
            row, c, mcap = last
            res["ultimo"] = dict(row, cierre_balance=c["cierre"], capitalizacion=round(mcap),
                                 roe=div(c["ni"], c["pn"]), margen_ebitda=div(c["ebitda"], c["ventas"]), margen_neto=div(c["ni"], c["ventas"]))
        out["t"][t] = res
    json.dump(out, open(os.path.join(DIR, "ratios.json"), "w"), separators=(",", ":"))
    print("ratios de %d empresas" % len(out["t"]))


if __name__ == "__main__":
    main()
