"""Curvas y dólar del día contra la rueda anterior, para el reporte diario (scripts/reporte.py).

Precios: los cierres de data/volumen.json (hoy y la rueda anterior). En la prueba (en_vivo=True) "hoy" son los precios de ahora de data912.
Flujos: los que trae la página embebidos en index.html (PX para Globales y Bonares, PSD para los bonos en pesos y su CER).
  Tasa fija   TEA de Lecaps y Boncaps
  CER         TIR real (precio dividido por el CER de 10 días hábiles antes de la liquidación sobre el de la emisión)
  Hard dollar TIR en dólares de Globales (GD) y Bonares (AL, AE) con su precio en MEP, contra la duration
Liquidación T+1. Los gráficos salen en PNG (matplotlib) y van pegados en el mail.
"""
import io, json, os, urllib.request, datetime as dt

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = os.path.join(ROOT, "data")
E0 = dt.date(1970, 1, 1)
USD = ["GD29", "GD30", "GD35", "GD38", "GD41", "GD46", "AL29", "AL30", "AL35", "AE38", "AL41"]


def day(d):
    return (d - E0).days


def sday(n):
    return (E0 + dt.timedelta(n)).isoformat()


def const(src, name):
    i = src.index("const " + name + " = ") + len("const " + name + " = ")
    return json.loads(src[i:src.index("\n", i)].rstrip().rstrip(";"))


def datos():
    src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    PX, PSD = const(src, "PX"), const(src, "PSD")
    with open(os.path.join(D, "volumen.json")) as f:
        V = json.load(f)
    return PX, PSD, V


def cierres(V, k):
    """{ticker: (cierre de la rueda k, cierre de la rueda k-1)} con k = índice en V['dates']."""
    out = {}
    for t, o in V["t"].items():
        acc, last = 0, {}
        for di, c in zip(o["i"], o["c"]):
            acc += di
            if acc in (k, k - 1) and c and c > 0:
                last[acc] = c
        out[t] = (last.get(k), last.get(k - 1))
    return out


def vivo():
    P = {}
    for ep in ("arg_bonds", "arg_notes"):
        try:
            req = urllib.request.Request("https://data912.com/live/" + ep, headers={"User-Agent": "Mozilla/5.0"})
            for r in json.load(urllib.request.urlopen(req, timeout=30)) or []:
                if r.get("symbol") and (r.get("c") or 0) > 0:
                    P[r["symbol"]] = float(r["c"])
        except Exception as e:
            print("data912", ep, e)
    return P


def habil(HOL):
    H = set(HOL)
    return lambda t: (t + 3) % 7 < 5 and t not in H


def irr(fl, P, t0):
    """TIR anual (365) de los flujos [(día, monto)] contra el precio P liquidando en t0."""
    fl = [(t, c) for t, c in fl if t > t0 and c]
    if not fl or not P or P <= 0:
        return None
    f = lambda y: sum(c / (1 + y) ** ((t - t0) / 365) for t, c in fl) - P
    lo, hi = -0.9, 5.0
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(100):
        m = (lo + hi) / 2
        if f(lo) * f(m) <= 0:
            hi = m
        else:
            lo = m
    return (lo + hi) / 2


def dur(fl, y, t0):
    fl = [(t, c) for t, c in fl if t > t0 and c]
    pv = [(t, c / (1 + y) ** ((t - t0) / 365)) for t, c in fl]
    s = sum(v for _, v in pv)
    return sum((t - t0) / 365 * v for t, v in pv) / s if s else None


def curvas(en_vivo=False):
    """Devuelve (fecha hoy, fecha ayer, etiqueta hoy, {curva: [(ticker, x, tir_hoy, tir_ayer)]}, precios hoy, precios ayer)."""
    PX, PSD, V = datos()
    k = len(V["dates"]) - 1
    C = cierres(V, k)
    if en_vivo:
        live = vivo()
        hoy = {t: live.get(t) for t in C}
        ayer = {t: C[t][0] for t in C}
        f_hoy, f_ayer, lab = dt.date.today().isoformat(), V["dates"][k], "Ahora"
    else:
        hoy = {t: C[t][0] for t in C}
        ayer = {t: C[t][1] for t in C}
        f_hoy, f_ayer, lab = V["dates"][k], V["dates"][k - 1], "Hoy"
    biz = habil(PX.get("HOL", []))
    st = lambda f: next(t for t in range(day(dt.date.fromisoformat(f)) + 1, day(dt.date.fromisoformat(f)) + 10) if biz(t))  # T+1

    cer = {}
    o = PSD["IDX"]["CER"]
    for i, v in enumerate(o["v"]):
        cer[o["s"] + i] = v
    try:
        for d_, v in json.load(open(os.path.join(D, "indices.json")))["CER"].items():
            cer[day(dt.date.fromisoformat(d_))] = v
    except Exception:
        pass

    def cer10(t):
        d, n = t, 0
        while n < 10:
            d -= 1
            if biz(d):
                n += 1
        while d not in cer and d > t - 40:
            d -= 1
        return cer.get(d)

    out = {"fija": [], "cer": [], "usd": []}
    for t, ins in PSD["INST"].items():
        if ins.get("f") not in ("fija", "cer") or (ins["f"] == "fija" and ins.get("k") != "cap"):
            continue
        fl = [(r[0], r[1]) for r in ins["r"]]
        mat = fl[-1][0]
        row = []
        for P, f in ((hoy.get(t), f_hoy), (ayer.get(t), f_ayer)):
            t0 = st(f)
            if not P or mat - t0 < 15:
                row.append(None)
                continue
            if ins["f"] == "cer":
                a, b = cer10(t0), cer10(ins["iss"])
                P = P / (a / b) if a and b else None
            row.append(irr(fl, P, t0))
        if row[0] is not None and row[1] is not None:
            out["fija" if ins["f"] == "fija" else "cer"].append((t, mat - st(f_hoy), row[0], row[1]))
    for b in USD:
        ins = PX["S"].get(b)
        if not ins:
            continue
        fl = [(r[0], r[1] + r[2]) for r in ins["r"]]
        y = [irr(fl, hoy.get(b + "D"), st(f_hoy)), irr(fl, ayer.get(b + "D"), st(f_ayer))]
        if y[0] is not None and y[1] is not None:
            out["usd"].append((b, dur(fl, y[0], st(f_hoy)), y[0], y[1]))
    for kk in out:
        out[kk].sort(key=lambda x: x[1])
    return f_hoy, f_ayer, lab, out, hoy, ayer


def grafico(rows, titulo, xlab, color, lab_hoy, lab_ayer, ley=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=110)
    grupos = [rows] if not ley else [[r for r in rows if r[0].startswith(p)] for p in ley]
    cols = [color] if not ley else ["#2563eb", "#16a34a"]
    for g, c, nm in zip(grupos, cols, ley or [""]):
        if not g:
            continue
        x = [r[1] for r in g]
        ax.plot(x, [r[3] * 100 for r in g], "--o", color="#a1a1aa", ms=3.5, lw=1.2, label=lab_ayer if c == cols[0] else None)
        ax.plot(x, [r[2] * 100 for r in g], "-o", color=c, ms=5, lw=2, label=lab_hoy + (" · ley " + ("NY" if nm == "GD" else "local") if nm else ""))
        for r in g:
            ax.annotate(r[0], (r[1], r[2] * 100), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7.5, color="#3f3f46")
    ax.set_xlabel(xlab, fontsize=9, color="#52525b")
    ax.set_ylabel("%", fontsize=9, color="#52525b")
    ax.grid(alpha=0.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors="#52525b")
    ax.legend(fontsize=8, frameon=False, loc="best")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def dolar(hoy, ayer):
    """Filas (nombre, hoy, ayer) del dólar con los AL30 y GD30 de los mismos cierres."""
    q = lambda P, a, b: P.get(a) / P.get(b) if P.get(a) and P.get(b) else None
    rows = [("MEP (AL30)", q(hoy, "AL30", "AL30D"), q(ayer, "AL30", "AL30D")),
            ("MEP (GD30)", q(hoy, "GD30", "GD30D"), q(ayer, "GD30", "GD30D")),
            ("CCL (AL30)", q(hoy, "AL30", "AL30C"), q(ayer, "AL30", "AL30C")),
            ("CCL (GD30)", q(hoy, "GD30", "GD30C"), q(ayer, "GD30", "GD30C"))]
    cj = lambda P: (q(P, "AL30D", "AL30C") - 1) * 100 if q(P, "AL30D", "AL30C") else None
    rows.append(("Canje (CCL contra MEP, %)", cj(hoy), cj(ayer)))
    return rows
