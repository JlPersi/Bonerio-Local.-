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


def cierres(V, k, kb=None):
    """{ticker: (cierre de la rueda k, cierre de la rueda kb)} con k = índice en V['dates'] y kb la rueda de comparación (por defecto k-1)."""
    kb = k - 1 if kb is None else kb
    out = {}
    for t, o in V["t"].items():
        acc, last = 0, {}
        for di, c in zip(o["i"], o["c"]):
            acc += di
            if acc in (k, kb) and c and c > 0:
                last[acc] = c
        out[t] = (last.get(k), last.get(kb))
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


def cer10f(PSD, biz):
    """CER(t): el de 10 días hábiles antes de t (con la serie embebida en index.html más data/indices.json)."""
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
    return cer10


def curvas(en_vivo=False, base=None):
    """Devuelve (fecha hoy, fecha ayer, etiqueta hoy, {curva: [(ticker, x, tir_hoy, tir_ayer)]}, precios hoy, precios ayer).
    base: fecha de comparación (la última rueda <= base) en vez de la rueda anterior, para los resúmenes semanal y mensual."""
    PX, PSD, V = datos()
    k = len(V["dates"]) - 1
    kb = max(i for i, d in enumerate(V["dates"]) if d <= base) if base else k - 1
    C = cierres(V, k, kb)
    if en_vivo:
        live = vivo()
        hoy = {t: live.get(t) for t in C}
        ayer = {t: C[t][0] for t in C}
        f_hoy, f_ayer, lab = dt.date.today().isoformat(), V["dates"][k], "Ahora"
    else:
        hoy = {t: C[t][0] for t in C}
        ayer = {t: C[t][1] for t in C}
        f_hoy, f_ayer, lab = V["dates"][k], V["dates"][kb], "Hoy"
    biz = habil(PX.get("HOL", []))
    st = lambda f: next(t for t in range(day(dt.date.fromisoformat(f)) + 1, day(dt.date.fromisoformat(f)) + 10) if biz(t))  # T+1

    cer10 = cer10f(PSD, biz)

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


def grafico(rows, titulo, xlab, color, lab_hoy, lab_ayer, ley=None, oscuro=False):
    """PNG de la curva: los puntos de hoy (llenos) y los de ayer (huecos, en gris) unidos por un trazo fino que muestra cuánto se movió cada
    bono, y una curva ajustada (logarítmica) por grupo: la de hoy en color, la de ayer punteada. Sin unir los puntos entre sí."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.ticker import FuncFormatter
    INK, MUTED, GRID, GRAY = ("#f4f4f5", "#a1a1aa", "#2a2a2e", "#71717a") if oscuro else ("#18181b", "#71717a", "#ececec", "#a1a1aa")
    BGc = "#131314" if oscuro else "white"  # oscuro: el fondo de las tarjetas del mail
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, ax = plt.subplots(figsize=(6.4, 3.5), dpi=250)
    fig.patch.set_facecolor(BGc)
    ax.set_facecolor(BGc)
    grupos = [("", rows, color)] if not ley else [(p, [r for r in rows if r[0].startswith(p)], c) for p, c in zip(ley, ["#2563eb", "#d97706"])]
    xs = [r[1] for r in rows]
    span = (max(xs) - min(xs)) or 1
    for nm, g, c in grupos:
        if not g:
            continue
        x = np.array([r[1] for r in g], float)
        yh, ya = np.array([r[2] * 100 for r in g]), np.array([r[3] * 100 for r in g])
        for xi, a, b in zip(x, ya, yh):
            ax.plot([xi, xi], [a, b], color=c, lw=1.2, alpha=.45, zorder=2, solid_capstyle="round")
        if len(g) >= 3 and (x > 0).all():  # curva ajustada: y = a + b ln(x)
            xx = np.linspace(x.min(), x.max(), 120)
            for y, st, cc, lw in ((ya, (0, (3, 3)), GRAY, 1.3), (yh, "-", c, 2)):
                b_, a_ = np.polyfit(np.log(x), y, 1)
                ax.plot(xx, a_ + b_ * np.log(xx), linestyle=st, color=cc, lw=lw, zorder=1, alpha=.9)
        ax.scatter(x, ya, s=26, facecolor=BGc, edgecolor=GRAY, linewidth=1.2, zorder=3)
        ax.scatter(x, yh, s=36, color=c, edgecolor=BGc, linewidth=1, zorder=4,
                   label=(("Globales" if nm == "GD" else "Bonares") + " (" + lab_hoy.split(" (")[0].lower() + ")") if nm else lab_hoy)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%" if abs(v - round(v)) < 1e-9 else f"{v:.1f}%".replace(".", ",")))
    ax.grid(axis="y", color=GRID, lw=1)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID if oscuro else "#d4d4d8")
    ax.tick_params(axis="both", labelsize=8.5, colors=MUTED, length=0, pad=6)
    from matplotlib.transforms import Bbox
    ax.scatter([], [], s=26, facecolor=BGc, edgecolor=GRAY, linewidth=1.2, label=lab_ayer)
    ax.set_xlabel(xlab, fontsize=9, color=MUTED, labelpad=6)
    ax.margins(x=.06, y=.18)
    lg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=8.5, handletextpad=.4, columnspacing=1.4, borderaxespad=.2)
    for tx_ in lg.get_texts():
        tx_.set_color(INK)
    fig.tight_layout()  # antes de ubicar las etiquetas: después ya no se mueve nada
    fig.canvas.draw()
    # etiquetas: arriba del punto de hoy; si choca, abajo, a la derecha o a la izquierda; si no entra en ningún lado, va sin etiqueta (está en la tabla)
    rend, k = fig.canvas.get_renderer(), fig.dpi / 72 * 3.5  # los puntos también ocupan lugar
    puestas = [Bbox.from_extents(px - k, py - k, px + k, py + k) for px, py in ax.transData.transform([(r[1], r[2] * 100) for r in rows])]
    for r in sorted(rows, key=lambda r: r[2]):
        for off, ha in (((0, 8), "center"), ((0, -15), "center"), ((7, -4), "left"), ((-7, -4), "right")):
            t = ax.annotate(r[0], (r[1], r[2] * 100), textcoords="offset points", xytext=off, ha=ha, fontsize=8, color=INK, zorder=5)
            bb = t.get_window_extent(rend).expanded(1.08, 1.15)
            if not any(bb.overlaps(q) for q in puestas):
                puestas.append(bb)
                break
            t.remove()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=BGc)
    plt.close(fig)
    return buf.getvalue()


def ajuste(rows, i=2):
    """Curva logarítmica y = a + b ln(x) por los puntos (x = rows[k][1], y = rows[k][i]); None si hay menos de 3."""
    import math
    pts = [(math.log(r[1]), r[i]) for r in rows if r[1] > 0 and r[i] is not None]
    if len(pts) < 3:
        return None
    n_ = len(pts)
    mx, my = sum(p[0] for p in pts) / n_, sum(p[1] for p in pts) / n_
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    b = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx if sxx else 0
    a = my - b * mx
    return lambda x: a + b * math.log(x)


def _fig(w=6.4, h=3.3):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    return plt, plt.subplots(figsize=(w, h), dpi=250)


def _estilo(ax, pct=True):
    from matplotlib.ticker import FuncFormatter
    if pct:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%" if abs(v - round(v)) < 1e-9 else f"{v:.1f}%".replace(".", ",")))
    ax.grid(axis="y", color="#ececec", lw=1)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#d4d4d8")
    ax.tick_params(axis="both", labelsize=8.5, colors="#71717a", length=0, pad=6)


def _png(plt, fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def barras(items, color="#2563eb"):
    """Barras horizontales [(nombre, valor en millones)], de mayor a menor, con el valor al final de cada una."""
    plt, (fig, ax) = _fig(6.4, 0.42 * len(items) + 0.6)
    items = items[::-1]
    y = range(len(items))
    v = [x[1] for x in items]
    ax.barh(y, v, color=color, height=.62, edgecolor="white", linewidth=1)
    ax.set_yticks(list(y))
    ax.set_yticklabels([x[0] for x in items])
    mx = max(v) or 1
    for yi, vi in zip(y, v):
        ax.text(vi + mx * .015, yi, "$ " + f"{vi:,.0f}".replace(",", ".") + " M", va="center", fontsize=8.5, color="#18181b")
    ax.set_xlim(0, mx * 1.22)
    ax.set_xticks([])
    _estilo(ax, pct=False)
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", labelsize=9, colors="#18181b")
    fig.tight_layout()
    return _png(plt, fig)


def tasas_fut(lecaps, fut):
    """TNA de Lecaps (puntos y curva ajustada) contra la tasa implícita de los futuros de dólar, por días al vencimiento."""
    import numpy as np
    plt, (fig, ax) = _fig()
    if lecaps:
        x = np.array([r[0] for r in lecaps], float)
        ax.scatter(x, [r[1] for r in lecaps], s=36, color="#d97706", edgecolor="white", linewidth=1, zorder=4, label="Lecaps y Boncaps (TNA)")
        f = ajuste([(None, r[0], r[1]) for r in lecaps])
        if f:
            xx = np.linspace(x.min(), x.max(), 120)
            ax.plot(xx, [f(v) for v in xx], color="#d97706", lw=2, alpha=.9, zorder=2)
    if fut:
        ax.plot([r[0] for r in fut], [r[1] for r in fut], "-o", color="#2563eb", lw=2, ms=5.5, mec="white", mew=1, zorder=3, label="Futuros de dólar (tasa implícita)")
        for r in fut[:6]:
            ax.annotate(r[2], (r[0], r[1]), textcoords="offset points", xytext=(0, -14), ha="center", fontsize=7.5, color="#52525b")
    ax.set_xlabel("días al vencimiento", fontsize=9, color="#71717a", labelpad=6)
    ax.margins(x=.05, y=.2)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=8.5, handletextpad=.4, columnspacing=1.4, borderaxespad=.2)
    _estilo(ax)
    fig.tight_layout()
    return _png(plt, fig)


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
