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
Las empresas con moneda funcional dólar ("moneda_funcional": "USD", como YPF y Pampa) presentan en pesos convertidos al tipo de
cambio del cierre: a esas se las lleva a la fecha con el A3500 (data/dolar.json) en vez del CER.
TTM con estados acumulados: acumulado actual + último anual − mismo acumulado del año anterior (cada uno reexpresado).
Además, por empresa:
- "ultimo": EV, deuda neta, EBITDA, ventas y resultado de los últimos 12 meses en pesos de hoy, earnings yield y deuda neta / EBITDA
- "trim": cada trimestre suelto (ventas, EBITDA y resultado neto, en dólares: pesos del cierre / CCL de ese día, o el A3500 si la
  moneda funcional es el dólar) y el patrimonio neto, para las variaciones interanuales y contra el trimestre anterior.
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


def load_fx():
    """A3500 diario (data/dolar.json y lo último de data/indices.json), con la misma interfaz que load_cer."""
    fx = {}
    for fn, key in (("acciones/ccl.json", "oficial"), ("dolar.json", "A3500"), ("indices.json", "FX")):  # el oficial histórico (desde 2002) y encima el A3500 más reciente
        try:
            for d, v in json.load(open(os.path.join(ROOT, "data", fn)))[key].items():
                fx[dnum(d)] = float(v)
        except Exception:
            pass
    keys = sorted(fx)
    def at(d):
        t = dnum(d) if isinstance(d, str) else d
        if not keys:
            return None
        if t >= keys[-1]:
            return fx[keys[-1]]
        while t not in fx and t > keys[0]:
            t -= 1
        return fx.get(t)
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
    c0, ca, cs = cer(p["cierre"]), cer(a["cierre"]), cer(s["cierre"])
    if not (c0 and ca and cs):  # sin índice para esas fechas (balances viejos)
        return None
    return v + va * c0 / ca - vs * c0 / cs


def load_ccl():
    """CCL histórico (data/acciones/ccl.json, desde 2013) y el oficial antes, con la misma interfaz que load_cer."""
    fx = {}
    try:
        h = json.load(open(os.path.join(DIR, "ccl.json")))
        c0 = min(h.get("ccl", {}) or {"9999": 0})
        for d, v in h.get("oficial", {}).items():
            if d < c0:
                fx[dnum(d)] = float(v)
        for d, v in h.get("ccl", {}).items():
            fx[dnum(d)] = float(v)
    except Exception as e:
        print("CCL histórico no disponible:", e)
    keys = sorted(fx)
    def at(d):
        t = dnum(d) if isinstance(d, str) else d
        if not keys or t < keys[0]:
            return None
        if t >= keys[-1]:
            return fx[keys[-1]]
        while t not in fx:
            t -= 1
        return fx[t]
    return at


def quarter(per, i, key, cer):
    """Flujo del trimestre que cierra en el período i, en moneda de su cierre (acumulado − acumulado anterior del mismo ejercicio)."""
    p = per[i]; v = p.get("resultados", {}).get(key); m = p.get("acumulado_meses", 12)
    if v is None:
        return None
    if m == 3:
        return v
    prev = [q for q in per[:i] if q.get("acumulado_meses") == m - 3 and 80 < dnum(p["cierre"]) - dnum(q["cierre"]) < 100]
    if not prev:
        return None
    vq = prev[-1].get("resultados", {}).get(key)
    c0, c1 = cer(p["cierre"]), cer(prev[-1]["cierre"])
    if vq is None or not (c0 and c1):
        return None
    return v - vq * c0 / c1


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
    cer_idx, fx_idx, ccl_idx = load_cer(), load_fx(), load_ccl()
    out = {"generado": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "t": {}}
    for fn in sorted(os.listdir(BAL)):
        if not fn.endswith(".json") or fn.startswith("plantilla"):
            continue
        b = json.load(open(os.path.join(BAL, fn)))
        cer = fx_idx if b.get("moneda_funcional") == "USD" else cer_idx  # índice con que se lleva cada balance a la fecha
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
        # si a un balance le falta el TTM (no está el mismo período del año anterior), se usa el del balance previo
        # reexpresado, siempre que sea de hasta ~6 meses antes
        for i in range(1, len(calc)):
            a, c = calc[i - 1], calc[i]
            if dnum(c["cierre"]) - dnum(a["cierre"]) > 200:
                continue
            for key in ("ni", "ebitda", "ventas"):
                if c[key] is None and a[key] is not None and cer(c["cierre"]) and cer(a["cierre"]):
                    c[key] = a[key] * cer(c["cierre"]) / cer(a["cierre"])
        try:
            px = [(r[0], r[4]) for r in json.load(open(os.path.join(DIR, t + ".json")))["r"] if r[4]]
        except Exception:
            px = []
        serie, last = [], None
        splits = b.get("splits", [])
        for d, price in px:
            av = [c for c in calc if c["pub"] <= d]
            if not av:
                continue
            c = av[-1]
            if not c["acciones"]:
                continue
            if not (cer(d) and cer(c["cierre"])):
                continue
            f = cer(d) / cer(c["cierre"]) * esc  # balance reexpresado a moneda del día del precio
            k = 1  # splits posteriores al cierre del balance (los precios no vienen ajustados)
            for sp in splits:
                if c["cierre"] < sp["fecha"] <= d:
                    k *= sp["factor"]
            mcap = price * c["acciones"] * k
            ev = mcap + ((c["deuda"] or 0) - (c["caja"] or 0)) * f if c["deuda"] is not None or c["caja"] is not None else None
            row = {"d": d, "pe": div(mcap, c["ni"] * f if c["ni"] is not None else None),
                   "pvl": div(mcap, c["pn"] * f if c["pn"] is not None else None),
                   "ev_ebitda": div(ev, c["ebitda"] * f if c["ebitda"] is not None else None)}
            serie.append([d, row["pe"], row["pvl"], row["ev_ebitda"]]); last = (row, c, mcap)
        res = {"balances": len(per), "serie_cols": ["d", "pe", "pvl", "ev_ebitda"], "serie": serie}
        if last:
            row, c, mcap = last
            f = cer(row["d"]) / cer(c["cierre"]) * esc
            hoy = lambda v: round(v * f) if v is not None else None
            dn = ((c["deuda"] or 0) - (c["caja"] or 0)) if c["deuda"] is not None or c["caja"] is not None else None
            res["ultimo"] = dict(row, cierre_balance=c["cierre"], capitalizacion=round(mcap),
                                 roe=div(c["ni"], c["pn"]), margen_ebitda=div(c["ebitda"], c["ventas"]), margen_neto=div(c["ni"], c["ventas"]),
                                 ev=round(mcap + dn * f) if dn is not None else None, deuda_neta=hoy(dn), deuda=hoy(c["deuda"]), caja=hoy(c["caja"]),
                                 ebitda=hoy(c["ebitda"]), ventas=hoy(c["ventas"]), ni=hoy(c["ni"]), pn=hoy(c["pn"]),
                                 ey=div(c["ni"] * f if c["ni"] is not None else None, mcap), dn_ebitda=div(dn, c["ebitda"]))
        # trimestres sueltos en dólares
        usd = fx_idx if b.get("moneda_funcional") == "USD" else ccl_idx
        trim = []
        for i, p in enumerate(per):
            fx = usd(p["cierre"])
            if not fx:
                continue
            q = lambda k: quarter(per, i, k, cer)
            ebit, da = q("resultado_operativo"), q("depreciaciones")
            ni = q("resultado_neto_controlante")
            if ni is None:
                ni = q("resultado_neto")
            u = lambda v: round(v * esc / fx / 1e6, 1) if v is not None else None  # millones de dólares
            s = p.get("situacion", {}); pn = s.get("patrimonio_neto_controlante", s.get("patrimonio_neto"))
            trim.append([p["cierre"], u(q("ventas")), u(ebit + da if ebit is not None and da is not None else None), u(ni), u(pn),
                         u(s.get("deuda_financiera")), u(s.get("caja_inversiones"))])
        res["trim_cols"] = ["cierre", "ventas", "ebitda", "ni", "pn", "deuda", "caja"]
        res["trim"] = trim[-16:]
        out["t"][t] = res
    json.dump(out, open(os.path.join(DIR, "ratios.json"), "w"), separators=(",", ":"))
    print("ratios de %d empresas" % len(out["t"]))


if __name__ == "__main__":
    main()
