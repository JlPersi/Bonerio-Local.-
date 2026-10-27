"""Los datos de las alertas que no son un precio directo: TIR, TNA, paridad, duration y volumen de cada bono, los futuros de dólar con
su tasa implícita y la caución. Lo usa scripts/alertas.py (para ver si saltó cada alerta) y deja la foto en data/alertas_vivo.json,
que la pestaña Alertas muestra como «Ahora» (así lo que ve el usuario es lo mismo que revisa el servidor).

Bonos
  Tasa fija  Lecaps y Boncaps: TIR (TEA) y TNA al vencimiento
  CER        TIR real (precio dividido por el CER de 10 días hábiles antes de la liquidación sobre el de la emisión)
  Dólares    Globales y Bonares (flujos embebidos en index.html), ONs (data/ons.json) y provinciales (data/pvs.json): TIR, paridad y
             duration con el precio en dólares MEP (o cable si la especie termina en C)
Liquidación T+1, igual que el reporte diario (scripts/reporte_curvas.py).
Futuros y caución: la foto de Primary y BYMA de data/tasas.json (vivo), que sale cada 10 minutos en la rueda.
"""
import json, os, datetime as dt
import reporte_curvas as RC

D = RC.D


def _j(n):
    try:
        with open(os.path.join(D, n)) as f:
            return json.load(f)
    except Exception:
        return {}


class Bonos:
    def __init__(self):
        self.PX, self.PSD, _ = RC.datos()
        self.biz = RC.habil(self.PX.get("HOL", []))
        self.cer10 = RC.cer10f(self.PSD, self.biz)
        hoy = RC.day(dt.date.today())
        self.t0 = next(t for t in range(hoy + 1, hoy + 10) if self.biz(t))
        self.ext, self.alias = {}, {}  # ONs y provinciales en dólares: clave -> (flujos [(día, total, interés)], día del último cupón, especie D, especie C)
        for ons, src in ((1, _j("ons.json").get("on") or {}), (0, _j("pvs.json").get("on") or {})):
            for k, o in src.items():
                if o.get("t") != "usd" or not o.get("fl"):
                    continue
                d, c = o.get("d") or (k + "D" if ons else None), o.get("c") or (k + "C" if ons else None)
                if not d:
                    continue
                fl = [(RC.day(dt.date.fromisoformat(f[0])), f[1], f[2]) for f in o["fl"]]
                lc = RC.day(dt.date.fromisoformat(o["lc"])) if o.get("lc") else None
                self.ext[k] = (fl, lc, d, c)
                for t in (k, o.get("o"), d):
                    if t:
                        self.alias.setdefault(t, (k, d))
                if c:
                    self.alias.setdefault(c, (k, c))

    def busca(self, tk):
        """(tipo, clave, especie de precio) de lo que escribió el usuario: AL30, AL30D, GD30C, S13N6, TX26, YMCXO..."""
        t = (tk or "").strip().upper()
        if t in self.PSD["INST"]:
            return "ars", t, t
        for b in ([t[:-1], t] if t[-1:] in ("D", "C") else [t]):
            if b in self.PX["S"]:
                return "sob", b, b + ("C" if t.endswith("C") and b != t else "D")
        if t in self.alias:
            return ("ext",) + self.alias[t]
        return None, None, None

    def calc(self, tk, P):
        """{'tir', 'tna', 'par', 'dur'} del bono tk al precio P (lo que no aplica queda en None)."""
        tipo, k, _ = self.busca(tk)
        out = {"tir": None, "tna": None, "par": None, "dur": None}
        if not tipo or not P or P <= 0:
            return out
        t0 = self.t0
        if tipo == "ars":
            ins = self.PSD["INST"][k]
            if ins.get("f") not in ("fija", "cer") or (ins["f"] == "fija" and ins.get("k") != "cap"):
                return out  # duales, TAMAR y dólar linked: no
            fl = [(r[0], r[1]) for r in ins["r"]]
            if ins["f"] == "cer":
                a, b = self.cer10(t0), self.cer10(ins["iss"])
                if not (a and b):
                    return out
                P = P / (a / b)
            y = RC.irr(fl, P, t0)
            if y is None:
                return out
            out["tir"], out["dur"] = y, RC.dur(fl, y, t0)
            n = fl[-1][0] - t0
            if ins["f"] == "fija" and n > 0:
                out["tna"] = ((1 + y) ** (n / 365) - 1) * 365 / n
            return out
        if tipo == "sob":
            ins = self.PX["S"][k]
            rows = ins["r"]
            fl = [(r[0], r[1] + r[2]) for r in rows]
            i = next((j for j, r in enumerate(rows) if r[0] > t0), None)
            if i is None:
                return out
            prev = rows[i - 1][0] if i > 0 else ins["iss"]
            res = rows[i][2] + rows[i][3]
            acc = rows[i][1] * (t0 - prev) / max(1, rows[i][0] - prev)
        else:
            fl3, lc = self.ext[k][:2]
            fut = [f for f in fl3 if f[0] > t0]
            if not fut:
                return out
            fl = [(f[0], f[1]) for f in fl3]
            prev = lc or t0
            res = sum(f[1] - f[2] for f in fut)
            acc = fut[0][2] * (t0 - prev) / max(1, fut[0][0] - prev)
        y = RC.irr(fl, P, t0)
        if y is not None:
            out["tir"], out["dur"] = y, RC.dur(fl, y, t0)
        if res > 0:
            out["par"] = P / (res + acc) * 100
        return out

    def todos(self):
        """Lo que se puede buscar en la pestaña: claves de bonos con su especie de precio por defecto."""
        L = [(k, k) for k, i in self.PSD["INST"].items() if i.get("f") == "cer" or (i.get("f") == "fija" and i.get("k") == "cap")]
        L += [(k, k + "D") for k in self.PX["S"]] + [(k, e[2]) for k, e in self.ext.items()]
        return L


def futuros():
    """{contrato: {'p': precio, 'vto': 'AAAA-MM-DD', 'tna': tasa implícita contra el oficial spot (%)}}, ordenado por vencimiento."""
    v = (_j("tasas.json").get("vivo") or {})
    S, hoy, out = v.get("spot"), dt.date.today(), {}
    for r in sorted(v.get("fut") or [], key=lambda r: r[1] or ""):
        if not str(r[0]).startswith("DLR/") or not r[1]:
            continue
        p = r[4] or r[5] or ((r[2] + r[3]) / 2 if r[2] and r[3] else None)
        n = (dt.date.fromisoformat(r[1]) - hoy).days
        if not p or n < 0:
            continue
        out[r[0]] = {"p": p, "vto": r[1], "tna": (p / S - 1) * 365 / n * 100 if S and n > 0 else None}
    return out


def futuro(F, tk):
    """El contrato que pidió: DLR/NOV26, NOV26 o 1 y 2 para el primero y el segundo que no vencieron."""
    t = (tk or "1").strip().upper()
    if t.isdigit():
        L = list(F)
        return L[int(t) - 1] if 0 < int(t) <= len(L) else None
    t = t if t.startswith("DLR/") else "DLR/" + t
    return t if t in F else None


def caucion():
    """{plazo en días: TNA %} de la caución en pesos (BYMA, en vivo)."""
    v = (_j("tasas.json").get("vivo") or {})
    out = {}
    for r in ((v.get("bcau") or {}).get("ARS") or v.get("cau") or []):
        if r and r[0] and r[1]:
            out.setdefault(int(r[0]), float(r[1]))
    return out


def oficial():
    v = (_j("tasas.json").get("vivo") or {})
    if v.get("spot") and str(v.get("ts", ""))[:10] == dt.date.today().isoformat():
        return float(v["spot"])
    a = _j("dolar.json").get("A3500") or {}
    return a[max(a)] if a else None


def foto(P, B, path=os.path.join(D, "alertas_vivo.json")):
    """data/alertas_vivo.json: TIR, TNA, paridad y duration de cada bono, futuros y caución, para el «Ahora» de la pestaña."""
    bon = {}
    for k, sp in B.todos():
        q = (P.get(sp) or {}).get("c")
        if not q:
            continue
        m = B.calc(sp, q)
        if m["tir"] is None and m["par"] is None:
            continue
        bon[sp] = [round(x * 100, 3) if x is not None and n != "par" and n != "dur" else (round(x, 2) if x is not None else None) for n, x in (("tir", m["tir"]), ("tna", m["tna"]), ("par", m["par"]), ("dur", m["dur"]))]
    F = futuros()
    o = {"ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "bon": bon,
         "fut": {k: [round(x["p"], 2), x["vto"], round(x["tna"], 2) if x["tna"] is not None else None] for k, x in F.items()},
         "cau": {str(k): v for k, v in sorted(caucion().items())}, "ofi": oficial(),
         "al": {t: d for t, (k, d) in B.alias.items() if t != d and d in bon and t[:-1] + "D" != d and t + "D" != d}}  # BA37D -> BA7DD
    with open(path + ".tmp", "w") as f:
        json.dump(o, f, separators=(",", ":"))
    os.replace(path + ".tmp", path)
