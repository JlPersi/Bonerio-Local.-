#!/usr/bin/env python3
"""Calendario de balances de las acciones: data/acciones/balances/<TICKER>.json -> data/acciones/calendario_balances.json.

Por empresa: el último balance presentado en la CNV (cierre, fecha de presentación y meses que acumula) y el próximo:
- cierre: tres meses después del último (fin de mes).
- fecha estimada: la del mismo balance del año anterior, un año después (las empresas suelen repetir); si no está, el cierre
  más la demora mediana de esa empresa para ese tipo de balance (trimestral o anual), o 42 / 70 días.
- plazo: el de la CNV para las emisoras que no son bancos: 42 días corridos del cierre los trimestrales y 70 los anuales.
  A los bancos no se les pone (presentan con los plazos del BCRA).
- si la empresa anunció la fecha (data/acciones/fechas_resultados.json, cargado a mano desde los calendarios de resultados), esa.
Corre en balances.yml después de bajar los balances.
"""
import json, os, sys, glob, statistics, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from balances_cnv import EMPRESAS  # (CUIT, VN, mes de cierre, banco, moneda)

HERE = os.path.dirname(os.path.abspath(__file__))
BAL = os.path.join(HERE, "..", "data", "acciones", "balances")
ANUN = os.path.join(HERE, "..", "data", "acciones", "fechas_resultados.json")
OUT = os.path.join(HERE, "..", "data", "acciones", "calendario_balances.json")


def fin_mes(y, m):
    return (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))


def mas_meses(d, n):
    m = d.month - 1 + n
    return fin_mes(d.year + m // 12, m % 12 + 1)


def habil(d):  # si cae sábado o domingo, el lunes
    while d.weekday() > 4:
        d += dt.timedelta(days=1)
    return d


def main():
    out = {}
    try:
        A = json.load(open(ANUN))
    except Exception:
        A = {}
    for f in sorted(glob.glob(os.path.join(BAL, "*.json"))):
        t = os.path.basename(f)[:-5]
        if t not in EMPRESAS:
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        P = [p for p in d.get("periodos") or [] if p.get("cierre") and p.get("publicado")]
        if not P:
            continue
        P.sort(key=lambda p: p["cierre"])
        u = P[-1]
        c = dt.date.fromisoformat(u["cierre"])
        meses = u.get("acumulado_meses") or 3
        nc, nm = mas_meses(c, 3), meses % 12 + 3
        banco = bool((EMPRESAS.get(t) or (0, 0, 0, False))[3])
        # demora de cada presentación, por tipo
        dem = {"a": [], "t": []}
        by = {}
        for p in P:
            pc, pu = dt.date.fromisoformat(p["cierre"]), dt.date.fromisoformat(p["publicado"])
            if 0 < (pu - pc).days < 200:
                dem["a" if p.get("acumulado_meses") == 12 else "t"].append((pu - pc).days)
            by[p["cierre"]] = pu
        tipo = "a" if nm == 12 else "t"
        prev = by.get(fin_mes(nc.year - 1, nc.month).isoformat())
        if prev and 0 < (prev - fin_mes(nc.year - 1, nc.month)).days < 200:
            try:
                est = prev.replace(year=prev.year + 1)
            except ValueError:
                est = prev + dt.timedelta(days=365)
            como = "año anterior"
        else:
            dd = dem[tipo][-8:]
            est = nc + dt.timedelta(days=round(statistics.median(dd)) if dd else (70 if tipo == "a" else 42))
            como = "demora habitual"
        if A.get("cierre") == nc.isoformat() and t in A.get("f", {}):
            est, como = dt.date.fromisoformat(A["f"][t]), "anunciada"
        plazo = None if banco else nc + dt.timedelta(days=70 if tipo == "a" else 42)
        out[t] = {
            "ult": {"cierre": u["cierre"], "publicado": u["publicado"], "meses": meses},
            "prox": {"cierre": nc.isoformat(), "meses": nm, "est": habil(est).isoformat(), "como": como, "plazo": plazo.isoformat() if plazo else None},
            "banco": banco,
        }
    json.dump({"t": out}, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print("calendario de balances: %d empresas" % len(out))


if __name__ == "__main__":
    main()
