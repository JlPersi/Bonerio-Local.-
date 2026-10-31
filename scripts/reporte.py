"""Reporte diario por mail: al cierre, a los usuarios suscriptos (tabla reporte de Supabase, activo = true), por Resend.

Corre en cierre.yml después de guardar los datos del día. Sale una vez por rueda: la fecha enviada queda en data/reporte_enviado.json
(el cierre corre hasta tres veces) y solo se manda si data/volumen.json ya tiene la rueda de hoy.
Las curvas, gráficos y tablas salen de la propia página (scripts/reporte_web.js la abre en Chromium y lee sus pestañas), así son los mismos
que se ven en la terminal: Variación diaria (hard dollar, Lecaps, CER, TAMAR, duales, dólar linked, ONs y provinciales en dólares, acciones
del panel líder), Dólar, Futuros, Inflación y Devaluación implícita y Forwards. De acá: riesgo país, caución, volumen por familia y agenda.
El mail tiene la estética de la página (fondo oscuro, colores de cada familia).
Prueba: scripts/reporte.py --prueba-envio manda a los suscriptos un ejemplo con los precios de ahora contra el último cierre.
Revisar sin mandar: scripts/reporte.py --html [--web datos.json] (deja el HTML y las imágenes en /tmp).
Los viernes suma el balance de la semana y en la última rueda hábil del mes sale la edición de fin de mes (balance del mes y del año);
REPORTE_EDICION=semana|mes fuerza una edición para probar.
Secrets: SUPABASE_SERVICE_KEY y RESEND_API_KEY.
"""
import base64, json, os, re, subprocess, sys, urllib.request, urllib.error, datetime as dt

D = os.path.join(os.path.dirname(__file__), "..", "data")
SB = "https://sbvebxqeltvkerrarzqn.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
RESEND = os.environ.get("RESEND_API_KEY", "").strip()
FROM = "Bonerio Local <hola@boneriolocal.com.ar>"
SITE = "https://boneriolocal.com.ar"
MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def load(f):
    try:
        with open(os.path.join(D, f)) as fh:
            return json.load(fh)
    except Exception:
        return None


def http(url, data=None, headers=None, method=None):
    h = {"User-Agent": "Mozilla/5.0"}
    h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        h["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h, method=method), timeout=40) as r:
        t = r.read()
        return json.loads(t) if t else None


def n(v, d=2):
    if v is None:
        return "—"
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pc(v, d=2):
    if v is None:
        return "—"
    col = "#15803d" if v > 0 else "#b91c1c" if v < 0 else "#52525b"
    return f'<span style="color:{col}">{"+" if v > 0 else ""}{n(v, d)}%</span>'


def last2(o):
    k = sorted(o or {})
    return (o[k[-1]] if k else None), (o[k[-2]] if len(k) > 1 else None)


def ruedas(esp="P"):
    v = load("volumen.json")
    if not v:
        return None, None, {}
    dates, T = v["dates"], {}
    L = len(dates) - 1
    for t, o in v["t"].items():
        if o.get("s") != esp:
            continue
        acc, row = 0, {}
        for di, e, c in zip(o["i"], o["e"], o["c"]):
            acc += di
            if acc >= L - 1:
                row[acc] = (e, c)
        if L in row:
            T[t] = (row[L], row.get(L - 1))
    return dates[-1], (dates[-2] if len(dates) > 1 else None), T


def semana(hoy):
    ev, fin = [], hoy + dt.timedelta(days=7)
    try:
        m = re.search(r"const CAL=(\[[\s\S]*?\]);", open(os.path.join(D, "..", "licitaciones.html")).read())
        for c in json.loads(m.group(1)) if m else []:
            for i, t in ((0, "Llamado a licitación del Tesoro"), (1, "Licitación del Tesoro"), (2, "Liquidación de la licitación")):
                f = dt.date.fromisoformat(c[i])
                if hoy < f <= fin:
                    ev.append((f, t))
    except Exception:
        pass
    for e in (load("calendario.json") or {}).get("eventos", []):
        f = dt.date.fromisoformat(e["f"])
        if hoy < f <= fin:
            ev.append((f, e["n"] + (" (" + e["h"] + " h)" if e.get("h") else "")))
    p = (hoy.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    if hoy < p <= fin:
        ev.append((p, "Cambia el ajuste mensual del techo de la banda"))
    return sorted(ev)


def familia(t, PX, PSD, ON, PV):
    if t in PX["S"]:
        return "Soberanos en dólares"
    ins = PSD["INST"].get(t)
    if ins:
        return {"fija": "Lecaps y Boncaps", "cer": "Bonos CER", "dl": "Dólar linked"}.get(ins.get("f"), "TAMAR y duales")
    if t in ON or (t[:-1] in ON and t.endswith("O")):
        return "Obligaciones negociables"
    if t in PV:
        return "Otros" if PV[t].get("x") else "Provinciales"
    if t.startswith("BPO") or t.startswith("BPY") or t.startswith("BPJ") or t.startswith("BPA"):
        return "Bopreal"
    return "Otros"


def edicion(hoy):
    """'mes' en la última rueda hábil del mes (lunes a viernes), 'semana' los viernes, None el resto."""
    fin = (hoy.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    if not any((hoy + dt.timedelta(days=k)).weekday() < 5 for k in range(1, (fin - hoy).days)):
        return "mes"
    return "semana" if hoy.weekday() == 4 else None


def serie_vd(o, dates):
    """{fecha: (cierre, monto)} de una especie de volumen.json."""
    out, acc = {}, 0
    for di, e, c in zip(o["i"], o["e"], o["c"]):
        acc += di
        if 0 <= acc < len(dates):
            out[dates[acc]] = (c, e)
    return out


def al(o, f):
    """Último valor de un dict por fecha con fecha <= f."""
    k = [x for x in o if x <= f]
    return o[max(k)] if k else None


def periodo(hoy, tipo, PX, PSD, ON, PV):
    """Secciones del resumen semanal o mensual (y renglones para 'lo más importante'): todo de los archivos guardados al cierre."""
    V = load("volumen.json")
    if not V:
        return [], []
    dates, H = V["dates"], hoy.isoformat()
    ini = hoy - dt.timedelta(days=hoy.weekday()) if tipo == "semana" else hoy.replace(day=1)
    pre = [d for d in dates if d < ini.isoformat()]
    if not pre:
        return [], []
    b = pre[-1]  # cierre de referencia: la última rueda antes del período
    nr = len([d for d in dates if b < d <= H])
    prev = [d for d in pre if d < b]
    b2 = prev[-nr] if len(prev) >= nr else None  # período anterior de igual cantidad de ruedas, para el volumen
    nom = "la semana" if tipo == "semana" else MES[hoy.month - 1]
    y0 = f"{hoy.year - 1}-12-31"
    # dólar y riesgo país
    DL = (load("dolar.json") or {}).get("d") or {}
    CH = (load("acciones/ccl.json") or {}).get("ccl") or {}  # historia larga del CCL (data/dolar.json arranca en oct-26)
    A30, A30D = serie_vd(V["t"].get("AL30", {"i": [], "e": [], "c": []}), dates), serie_vd(V["t"].get("AL30D", {"i": [], "e": [], "c": []}), dates)
    def mep(f):
        x = ((DL.get(f) or {}).get("mep") or {}).get("AL30", {}).get("close")
        p, q = al(A30, f), al(A30D, f)
        return x or (p[0] / q[0] if p and q and p[0] and q[0] else None)
    ccl = lambda f: ((DL.get(f) or {}).get("ccl") or {}).get("vw") or al(CH, f)
    RP = (load("riesgo_pais.json") or {}).get("d") or {}
    var = lambda a, z: (a / z - 1) * 100 if a and z else None
    m1, m0, c1, c0, r1, r0 = mep(H), mep(b), ccl(H), ccl(b), al(RP, H), al(RP, b)
    ch = [("Dólar MEP", "$ " + n(m1), sg(var(m1, m0), 2, "%") + f" en {nom}", cv(var(m1, m0))),
          ("Dólar CCL", "$ " + n(c1), sg(var(c1, c0), 2, "%") + f" en {nom}", cv(var(c1, c0))),
          ("Riesgo país", n(r1, 0) + " pb", sg(r1 - r0 if r1 and r0 else None, 0, " pb") + f" en {nom}", cv(r1 - r0 if r1 and r0 else None, True))]
    if tipo == "mes":
        ma, ca, ra = mep(y0), ccl(y0), al(RP, y0)
        ch += [("MEP en el año", sg(var(m1, ma), 1, "%"), "desde el 31/12", cv(var(m1, ma))), ("CCL en el año", sg(var(c1, ca), 1, "%"), "desde el 31/12", cv(var(c1, ca))),
               ("Riesgo país en el año", sg(r1 - ra if r1 and ra else None, 0, " pb"), "desde el 31/12", cv(r1 - ra if r1 and ra else None, True))]
    # renta fija en pesos: variación de precio de lo líquido del período, por familia
    rows, fam, vol, vol0 = [], {}, {}, 0
    for t, o in V["t"].items():
        if o.get("s") != "P":
            continue
        S = serie_vd(o, dates)
        a, z = S.get(H) or al(S, H), al(S, b)
        mo = sum(e or 0 for d, (c, e) in S.items() if b < d <= H)
        if b2:
            vol0 += sum(e or 0 for d, (c, e) in S.items() if b2 < d <= b)
        f = familia(t, PX, PSD, ON, PV)
        vol[f] = vol.get(f, 0) + mo
        if a and z and a[0] and z[0] and mo > 0 and f != "Otros":
            rows.append((t, f, (a[0] / z[0] - 1) * 100, mo))
    rows.sort(key=lambda r: -r[3])
    liq = [r for r in rows[:150] if abs(r[2]) < 60]  # las 150 más operadas, sin saltos raros (cortes de cupón, amortizaciones)
    for r in liq:
        fam.setdefault(r[1], []).append(r[2])
    med = lambda x: sorted(x)[len(x) // 2]
    ft = sorted(((k, med(v), len(v)) for k, v in fam.items() if len(v) >= 3), key=lambda x: -x[1])
    up, dn = sorted(liq, key=lambda r: -r[2])[:5], sorted(liq, key=lambda r: r[2])[:5]
    tv, sv = sum(vol.values()), sorted(((k, v) for k, v in vol.items() if v > 0), key=lambda x: -x[1])
    rf = (f"<p {PP}>Variación de precio en pesos entre el cierre del {b[8:10]}/{b[5:7]} y el de hoy ({nr} ruedas), en las 150 especies más operadas del período.</p>"
          + tabla(["Familia", "Mediana", "Especies"], [[k, (sg(v, 2, "%"), cv(v)), str(c)] for k, v, c in ft])
          + f'<p style="font-size:13px;font-weight:700;color:{TX};margin:14px 0 2px">Mayores subas</p>'
          + tabla(["Especie", "Familia", "Var. precio"], [[t, f, (sg(v, 2, "%"), cv(v))] for t, f, v, _ in up])
          + f'<p style="font-size:13px;font-weight:700;color:{TX};margin:14px 0 2px">Mayores bajas</p>'
          + tabla(["Especie", "Familia", "Var. precio"], [[t, f, (sg(v, 2, "%"), cv(v))] for t, f, v, _ in dn])
          + f'<p style="font-size:14px;line-height:1.6;color:#d4d4d8;margin:12px 0 0">Se operaron <b>$ {n(tv / 1e6, 0)} millones</b> en {nom}'
          + (f" ({sg(var(tv, vol0), 1, '%')} contra las {nr} ruedas anteriores)" if vol0 else "") + "; " + ", ".join(f"{k[0].lower() + k[1:]} $ {n(v / 1e6, 0)} M" for k, v in sv[:4]) + ".</p>")
    # acciones del panel líder
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from save_acciones import LIDER
    except Exception:
        LIDER = set()
    try:  # precios ajustados por splits, como en la página
        import metricas_acciones as MA
        spl, bad = MA.splits()
        aj = lambda t, px: MA.adj(px, spl.get(t, []), bad.get(t, set()))
    except Exception:
        aj = lambda t, px: px
    ac = []
    for t in sorted(LIDER):
        o = load(f"acciones/{t}.json") or {}
        P = dict(aj(t, [(r[0], r[4]) for r in o.get("r", []) if r[4] and r[4] > 0]))
        a, z = al(P, H), al(P, b)
        if a and z:
            ac.append((t, var(a, z), var(a / c1, z / c0) if c1 and c0 else None, var(a, al(P, y0)) if tipo == "mes" and al(P, y0) else None))
    ac.sort(key=lambda r: -r[1])
    hd = ["Acción", "En pesos", "En US$ CCL"] + (["En el año"] if tipo == "mes" else [])
    ah = (f"<p {PP}>Variación del panel líder en {nom} ({b[8:10]}/{b[5:7]} a hoy). En dólares, al CCL de cada fecha.</p>"
          + tabla(hd, [[t, (sg(p, 2, "%"), cv(p)), (sg(u, 2, "%"), cv(u))] + ([(sg(y, 1, "%"), cv(y))] if tipo == "mes" else []) for t, p, u, y in ac])) if ac else ""
    pts = []
    if m1 and m0:
        pts.append(f"<b>En {nom}</b>: MEP {sg(var(m1, m0), 2, '%')}, CCL {sg(var(c1, c0), 2, '%')}" + (f", riesgo país {sg(r1 - r0, 0, ' pb')}" if r1 and r0 else "")
                   + (f"; en pesos, {ft[0][0][0].lower() + ft[0][0][1:]} lo mejor ({sg(ft[0][1], 2, '%')}) y {ft[-1][0][0].lower() + ft[-1][0][1:]} lo peor ({sg(ft[-1][1], 2, '%')})" if len(ft) > 1 else "")
                   + (f"; en acciones, {ac[0][0]} ({sg(ac[0][1], 1, '%')}) y {ac[-1][0]} ({sg(ac[-1][1], 1, '%')})" if ac else "") + ".")
    rub = "Semana" if tipo == "semana" else "Mes"
    tit = "de la semana" if tipo == "semana" else f"de {MES[hoy.month - 1]}"
    S = [(rub, f"Balance {tit}: dólar y riesgo país", chips(ch), AC), (rub, f"Renta fija en pesos: {nom}", rf if liq else "", FC["fija"]), (rub, f"Acciones: {nom}", ah, FC["acc"])]
    return S, pts


# estilos del mail: los de la página en modo oscuro (todo en línea: los clientes de correo ignoran las hojas de estilo)
BG, CARD, TX, MU, BD, AC, OK, BAD = "#0a0a0b", "#131314", "#f4f4f5", "#a1a1aa", "#232326", "#ffc542", "#34d399", "#ff6b8b"
FC = {"usd": "#b8e986", "fija": "#ffc542", "cer": "#2fd4a7", "tamar": "#ff8fb3", "dl": "#5cc8ff", "dual": "#c9a0ff", "on": "#f0abfc", "pv": "#fdba74", "acc": "#e4e4e7", "fut": "#5cc8ff", "dol": "#5cc8ff", "exp": "#c9a0ff", "vol": "#ffc542"}
FONT = "Inter,'Helvetica Neue',Helvetica,Arial,sans-serif"
FH = "'Bricolage Grotesque',Inter,Helvetica,Arial,sans-serif"
PP = f'style="font-size:14px;line-height:1.6;color:#d4d4d8;margin:0 0 12px"'
NOTE = f'style="font-size:12px;line-height:1.5;color:{MU};margin:8px 0 0"'
IMGS = f'width="560" style="display:block;width:100%;max-width:560px;height:auto;margin:6px 0 10px;border-radius:10px;border:1px solid {BD}"'
TD = f"padding:7px 6px;font-size:12.5px;border-top:1px solid {BD};color:{TX};font-variant-numeric:tabular-nums"
TH = f"padding:6px 6px;font-size:10.5px;font-weight:600;color:{MU};text-transform:uppercase;letter-spacing:.05em"


def num(s):
    """'−1.234,5%' de la página a float."""
    if s is None:
        return None
    m = re.search(r"[-−+]?[\d.]*\d(?:,\d+)?", str(s).replace("−", "-"))
    return float(m.group(0).replace(".", "").replace(",", ".")) if m else None


def sg(v, d=0, u=""):
    return "—" if v is None else ("+" if round(v, d) > 0 else "") + n(round(v, d) + 0, d) + u


def cv(v, inv=False, eps=0.0):
    """Color de una variación: verde si sube (o si baja, con inv: tasas), rojo al revés."""
    if v is None or abs(v) <= eps:
        return MU
    return OK if (v > 0) != inv else BAD


def tabla(head, rows, align=None, w=None):
    """head: títulos; rows: listas de celdas (texto o (texto, color)). La primera columna va a la izquierda y en negrita."""
    al = align or (["left"] + ["right"] * (len(head) - 1))
    h = "".join(f'<th style="{TH};text-align:{a}{";width:" + w[i] if w and w[i] else ""}">{t}</th>' for i, (t, a) in enumerate(zip(head, al)))
    b = ""
    for r in rows:
        b += "<tr>" + "".join(
            f'<td style="{TD};text-align:{al[i]};{"font-weight:700;" if i == 0 else ""}color:{c[1] if isinstance(c, tuple) else (TX if i == 0 else "#e4e4e7")}">{c[0] if isinstance(c, tuple) else c}</td>'
            for i, c in enumerate(r)) + "</tr>"
    return f'<table role="presentation" style="border-collapse:collapse;width:100%">{"<tr>" + h + "</tr>"}{b}</table>'


def chips(items):
    """Tarjetitas como las de la página: (título, valor, detalle, color del detalle)."""
    cel = [f'<td style="width:{100 // 3}%;padding:4px;vertical-align:top"><div style="background:{BG};border:1px solid {BD};border-radius:10px;padding:10px 12px">'
           f'<div style="font-size:10.5px;color:{MU};text-transform:uppercase;letter-spacing:.06em;font-weight:600">{t}</div>'
           f'<div style="font-family:{FH};font-size:19px;font-weight:700;color:{TX};margin:3px 0 1px;white-space:nowrap">{v}</div>'
           f'<div style="font-size:12px;color:{c or MU}">{s}</div></div></td>' for t, v, s, c in items]
    return ('<table role="presentation" style="border-collapse:collapse;width:100%;margin:0 0 6px">'
            + "".join("<tr>" + "".join(cel[i:i + 3]) + ("<td></td>" * (3 - len(cel[i:i + 3]))) + "</tr>" for i in range(0, len(cel), 3)) + "</table>")


def sec(num_, rubro, titulo, cuerpo, color=AC):
    return (f'<tr><td style="padding:10px 16px"><div style="background:{CARD};border:1px solid {BD};border-radius:14px;padding:18px 18px 16px">'
            f'<div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:{color};font-weight:700;margin:0 0 4px">{num_} · {rubro}</div>'
            f'<div style="font-family:{FH};font-size:20px;font-weight:700;color:{TX};margin:0 0 10px;letter-spacing:-.01em">{titulo}</div>{cuerpo}</div></td></tr>')


def leyenda(g):
    dot = lambda c, t, ring=False: f'<span style="white-space:nowrap;margin-right:12px"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;{"border:1.5px solid " + MU if ring else "background:" + c};vertical-align:middle;margin-right:5px"></span>{t}</span>'
    lin = lambda c, t, dash=False: f'<span style="white-space:nowrap;margin-right:12px"><span style="display:inline-block;width:18px;border-top:{"2px dashed" if dash else "3px solid"} {c};vertical-align:middle;margin-right:5px"></span>{t}</span>'
    cur = (lin(FC["usd"], "Curva de Globales (●)") + lin(FC["dual"], "Curva de Bonares (▲)")) if g == "usd" else lin(FC.get(g, AC), "Curva de hoy")
    return (f'<p style="font-size:11.5px;line-height:1.9;color:{MU};margin:0 0 4px">{dot(OK, "la tasa bajó")}{dot(BAD, "la tasa subió")}{dot(MU, "sin cambio")}'
            f'{dot("", "cierre anterior", True)}{cur}{lin(MU, "curva anterior", True)}</p>')


def web_datos(path=None):
    """Lo que se lee de la página (scripts/reporte_web.js)."""
    if not path:
        path = "/tmp/reporte_web.json"
        r = subprocess.run(["node", os.path.join(os.path.dirname(__file__), "reporte_web.js"), path], capture_output=True, text=True, timeout=600)
        print(r.stdout[-3000:], r.stderr[-3000:])
        if r.returncode:
            return None
    with open(path) as f:
        return json.load(f)


def armar(en_vivo=False, web=None):
    """(asunto, html, imágenes {cid: png}). en_vivo: la prueba, con los precios de ahora contra el último cierre."""
    sys.path.insert(0, os.path.dirname(__file__))
    import reporte_curvas as RC
    hoy = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date()
    L, P, T = ruedas()
    _, _, TD_ = ruedas("D")
    if not en_vivo and L != hoy.isoformat():
        print("todavía no está la rueda de hoy en volumen.json:", L)
        return None, None, None
    W = web_datos(web)
    if not W:
        print("no se pudo leer la página")
        return None, None, None
    PX, PSD, _ = RC.datos()
    IMG = {}

    def img(key, b64):
        if not b64:
            return ""
        IMG[key] = base64.b64decode(b64)
        return f'<img src="cid:{key}" alt="" {IMGS}>'

    # ---------- dólar, riesgo país, caución ----------
    dol = {r[0]: r for r in (W.get("dol") or {}).get("rows", [])}
    dv = lambda k, i=1: num(dol[k][i]) if k in dol else None
    mep, ccl, a3 = dv("MEP (AL30)"), dv("CCL (AL30)"), dv("Oficial (A3500)")
    mep_d, ccl_d, a3_d = dv("MEP (AL30)", 2), dv("CCL (AL30)", 2), dv("Oficial (A3500)", 2)
    bre, bre_d, can, can_d = dv("Brecha MEP"), dv("Brecha MEP", 2), dv("Canje CCL/MEP"), dv("Canje CCL/MEP", 2)
    brc, brc_d = dv("Brecha CCL"), dv("Brecha CCL", 2)
    rv = load("riesgo_vivo.json") or {}
    rp, rpp = last2((load("riesgo_pais.json") or {}).get("d"))
    if en_vivo and rv.get("v"):
        rp, rpp = float(rv["v"]), rp
    TJ = load("tasas.json") or {}
    cau = TJ.get("cau") or {}
    ck = sorted(cau)
    c1 = lambda d: next((r[1] for r in cau.get(d, []) if r[0] == 1), None)
    cau_h, cau_a = (c1(ck[-1]) if ck else None), (c1(ck[-2]) if len(ck) > 1 else None)
    mm = lambda t, M=T: ((M[t][0][0] or 0) / 1e6, ((M[t][1] or (0, 0))[0] or 0) / 1e6) if t in M else (None, None)
    vrows = []
    for nm, tk, M, u in (("AL30 en pesos", "AL30", T, "$"), ("AL30 en dólares (MEP)", "AL30D", TD_, "US$"), ("GD30 en dólares (MEP)", "GD30D", TD_, "US$")):
        a, b = mm(tk, M)
        if a:
            vrows.append([nm, f"{u} {n(a, 1)} M", (sg((a / b - 1) * 100, 0, "%") if b else "—", cv((a / b - 1) if b else None))])
    dol_html = (chips([("MEP (AL30)", "$ " + n(mep), sg(mep_d, 2, "%"), cv(mep_d)), ("CCL (AL30)", "$ " + n(ccl), sg(ccl_d, 2, "%"), cv(ccl_d)), ("Oficial (A3500)", "$ " + n(a3), sg(a3_d, 2, "%"), cv(a3_d)),
                        ("Brecha MEP", n(bre, 1) + "%", sg(bre_d, 1, " pp"), MU), ("Brecha CCL", n(brc, 1) + "%", sg(brc_d, 1, " pp"), MU), ("Canje CCL/MEP", n(can, 1) + "%", sg(can_d, 1, " pp"), MU)])
                + tabla(["", "Último", "1 rueda", "1 semana", "1 mes"], [[r[0], r[1], (r[2], cv(num(r[2]))), (r[3], cv(num(r[3]))), (r[4], cv(num(r[4])))] for r in (W.get("dol") or {}).get("rows", []) if "real" not in r[0]])
                + (f'<p style="font-size:13px;font-weight:700;color:{TX};margin:16px 0 2px">Volumen del dólar bolsa</p>' + tabla(["", "Monto", "Contra la rueda anterior"], vrows) if vrows else "")
                + f'<p {NOTE}>MEP y CCL de AL30, como en la pestaña Dólar. Brecha y canje: variación en puntos porcentuales.</p>')

    # ---------- curvas (Variación diaria de la página) ----------
    C = W.get("cur") or {}
    short = lambda r, g: g not in ("usd", "on", "pv") and (r.get("d") or 0) < 30
    med = lambda a: (sorted(a)[len(a) // 2] if len(a) % 2 else (sorted(a)[len(a) // 2 - 1] + sorted(a)[len(a) // 2]) / 2) if a else None

    def resumen(g):
        rs = [r for r in C.get(g, {}).get("rows", []) if r.get("dpb") is not None and not short(r, g) and not r.get("tf")]
        return (med([r["dpb"] for r in rs]), rs)

    def lectura(g, nombre, corte):
        m, rs = resumen(g)
        if m is None:
            return ""
        t = f"La curva de {nombre} {'subió' if m > 0.5 else 'bajó' if m < -0.5 else 'quedó sin cambios'}" + (f" {n(abs(m), 0)} pb (mediana)" if abs(m) > 0.5 else "")
        c, l = [r["dpb"] for r in rs if r["d"] <= corte], [r["dpb"] for r in rs if r["d"] > corte]
        if c and l and abs(med(c) - med(l)) >= 5:
            t += f": el tramo corto se movió {sg(med(c), 0, ' pb')} y el largo {sg(med(l), 0, ' pb')}, así que se {'empinó' if med(l) > med(c) else 'aplanó'}"
        mx = max(rs, key=lambda r: abs(r["dpb"]))
        up, dn = sum(1 for r in C[g]["rows"] if (r.get("dpct") or 0) > 0.005), sum(1 for r in C[g]["rows"] if (r.get("dpct") or 0) < -0.005)
        t += f". El mayor movimiento fue {mx['k']} ({sg(mx['dpb'], 0, ' pb')}, a {n(mx['y1'], 2)}%). En precio, {up} {'sube' if up == 1 else 'suben'} y {dn} {'baja' if dn == 1 else 'bajan'}."
        return f"<p {PP}>{t}</p>"

    def curva(g, nombre, corte):
        o = C.get(g) or {}
        rs = sorted(o.get("rows", []), key=lambda r: r.get("d") or 0)
        if not rs:
            return ""
        usd = g in ("on", "pv")
        yl = rs[0].get("yl") or "TIR"
        filas = []
        for r in rs:
            v = (r.get("usdv") or 0) / 1e3 if usd else mm(r["k"])[0]
            name = r["k"] + (f' <span style="font-weight:400;color:{MU}">{r["em"]}</span>' if usd and r.get("em") else "")
            yl_r = r.get("yl") or yl
            filas.append([name, n(r["P1"], 2), (sg(r["dpct"], 2, "%"), cv(r["dpct"], eps=0.005)),
                          (n(r["y1"], 2) + "%" + ("" if yl_r == yl else f' <span style="color:{MU}">{yl_r}</span>')) if r.get("y1") is not None else "—",
                          (sg(r["dpb"], 0), MU if short(r, g) or r.get("dpb") is None else cv(r["dpb"], True, 0.5)),
                          (n(v, 0) if usd else n(v, 1)) if v else "—"])
        return (lectura(g, nombre, corte) + leyenda(g) + img(g, o.get("png"))
                + tabla(["Bono", "Precio", "Δ %", yl, "Δ pb", "Monto (US$ miles)" if usd else "Monto ($ M)"], filas)
                + f'<p {NOTE}>{o.get("info", "").split(" · ")[0]}. Δ pb: cambio de la tasa' + ("" if usd or g == "usd" else "; los de menos de 30 días no se comparan (en gris) y quedan fuera de la curva") + ". Mismo gráfico que la pestaña Variación diaria.</p>")

    # spread ley local contra ley NY en los pares
    U = {r["k"]: r for r in C.get("usd", {}).get("rows", [])}
    pares = [((U[a]["y1"] - U[g]["y1"]) * 100, (U[a]["y0"] - U[g]["y0"]) * 100) for g, a in (("GD29", "AL29"), ("GD30", "AL30"), ("GD35", "AL35"), ("GD38", "AE38"), ("GD41", "AL41"))
             if g in U and a in U and U[a].get("y0") is not None and U[g].get("y0") is not None]
    hd_txt = ""
    if rp:
        hd_txt = f"<p {PP}>El <b>riesgo país</b> {'cerró' if not en_vivo else 'está'} en <b>{n(rp, 0)} pb</b>" + (f" ({sg(rp - rpp, 0, ' pb')} contra la rueda anterior)" if rpp else "") + "."
        if pares:
            sp, spa = sum(p[0] for p in pares) / len(pares), sum(p[1] for p in pares) / len(pares)
            hd_txt += f" Los Bonares rinden en promedio <b>{n(sp, 0)} pb</b> más que los Globales del mismo vencimiento (el premio por ley local), {'más' if sp > spa else 'menos'} que en la rueda anterior ({n(spa, 0)} pb)."
        hd_txt += "</p>"

    # ---------- futuros ----------
    F = W.get("fut") or {}
    fh = (F.get("tbl") or {}).get("head", [])
    fi = lambda name: next((i for i, h in enumerate(fh) if h.upper().startswith(name)), None)
    fr_ = [r for r in (F.get("tbl") or {}).get("rows", []) if r and r[0].startswith("DLR")]
    cols = [("CONTRATO", "Contrato"), ("AJUSTE", "Ajuste"), ("VAR. %", "Var."), ("VOLUMEN", "Volumen"), ("I.A.", "Int. abierto"), ("VAR. I.A.", "Var. I.A."), ("TNA", "TNA"), ("DEV. MENSUAL", "Dev. mensual")]
    ix = [fi(c) for c, _ in cols]
    fut_html, fut_pts = "", []
    if fr_ and None not in ix[:2]:
        filas = []
        for r in fr_[:10]:
            row = []
            for (c, _), i in zip(cols, ix):
                v = r[i] if i is not None and i < len(r) else "—"
                row.append((v, cv(num(v))) if c in ("VAR. %", "VAR. I.A.") else v.replace("DLR ", ""))
            filas.append(row)
        vol = sum(num(r[ix[3]]) or 0 for r in fr_) if ix[3] is not None else None
        oi = sum(num(r[ix[4]]) or 0 for r in fr_) if ix[4] is not None else None
        doi = sum(num(r[ix[5]]) or 0 for r in fr_) if ix[5] is not None else None
        top = max(fr_, key=lambda r: num(r[ix[3]]) or 0) if ix[3] is not None else None
        # forwards: devaluación mensual implícita entre contratos consecutivos (de un fin de mes al siguiente)
        di = fi("DÍAS")
        fw = []
        for a, b in zip(fr_, fr_[1:7]):
            pa, pb_, da, db = num(a[ix[1]]), num(b[ix[1]]), num(a[di]) if di is not None else None, num(b[di]) if di is not None else None
            if pa and pb_ and da is not None and db and db > da:
                fw.append((a[0].replace("DLR ", "") + " → " + b[0].replace("DLR ", ""), ((pb_ / pa) ** (30 / (db - da)) - 1) * 100))
        fut_pts = fw
        fut_html = (f"<p {PP}>Se operaron <b>{n(vol, 0)} contratos</b> de dólar futuro" + (f"; el interés abierto quedó en {n(oi, 0)} ({sg(doi, 0)})" if oi else "")
                    + (f". El más operado fue {top[0].replace('DLR ', '')} ({top[ix[3]]} contratos, ajuste $ {top[ix[1]]}, {top[ix[2]]})." if top else ".") + "</p>"
                    + img("fut", F.get("png")) + tabla([h for _, h in cols], filas)
                    + (f'<p style="font-size:13px;font-weight:700;color:{TX};margin:16px 0 2px">Forwards entre contratos</p><p {NOTE} >La devaluación mensual que descuenta el mercado entre el vencimiento de un contrato y el siguiente.</p>'
                       + tabla(["Tramo", "Devaluación mensual implícita"], [[a, n(v, 2) + "%"] for a, v in fw]) if fw else "")
                    + f'<p {NOTE}>Ajustes de A3 de la pestaña Futuros. Volumen e interés abierto en contratos; TNA y devaluación mensual, implícitas contra el spot de A3.</p>')

    # ---------- expectativas: inflación y devaluación implícitas, forwards de Lecaps ----------
    def implicita(sx, que, contra):
        B = W.get("be" + sx) or {}
        pl = (B.get("plazos") or {}).get("rows", [])
        ay = B.get("ayer") or {}
        if not pl:
            return "", None
        filas, prim = [], None
        for r in pl:
            h, a = (ay.get(r[0]) or [None, None])
            hv = h if h is not None else num(r[1])
            prim = prim or (r[0], hv, a)
            filas.append([r[0].replace(" (extrapolada", "<br><span style='font-weight:400;color:#a1a1aa;font-size:11px'>(extrapolada").replace(")", ")</span>") if "extrapolada" in r[0] else r[0],
                          n(hv, 2) + "%", (sg((hv - a) * 100, 0, " pb"), MU) if a is not None else "—", r[2]])
        bo = (B.get("bonos") or {})
        bh = bo.get("head", [])
        bi = [next((i for i, x in enumerate(bh) if x.upper().startswith(k)), None) for k in ("BONO", "DÍAS", "TIR", "BREAKEVEN MENSUAL")]
        bf = [[r[bi[0]], r[bi[1]], r[bi[2]], r[bi[3]]] for r in bo.get("rows", []) if None not in bi][:10]
        txt = (f"<p {PP}>Lo que descuenta el mercado comparando la curva de tasa fija con la de {contra} al mismo plazo: a {prim[0].split(' (')[0]}, "
               f"<b>{n(prim[1], 2)}% mensual</b>" + (f" ({sg((prim[1] - prim[2]) * 100, 0, ' pb')} contra la rueda anterior)" if prim[2] is not None else "") + ".</p>")
        return (txt + tabla(["Plazo", "Hoy", "Contra ayer", "Promedio"], filas)
                + f'<p style="font-size:13px;font-weight:700;color:{TX};margin:16px 0 2px">{que.capitalize()} breakeven de cada bono</p>' + img("be" + sx, B.get("png"))
                + (tabla(["Bono", "Días", bh[bi[2]].replace("?", "").capitalize() if bi[2] is not None else "Tasa", "Breakeven mensual"], bf) if bf else "")
                + f'<p {NOTE}>Breakeven: la {que} mensual que iguala lo que rinde cada bono con la Lecap del mismo plazo. Verde: el bono exige menos que la curva; rojo: conviene la tasa fija. Sin proyecciones: solo lo que paga el mercado.</p>'), prim

    infl_html, infl = implicita("i", "inflación", "CER")
    deva_html, deva = implicita("d", "devaluación", "dólar linked")
    FW = W.get("fw") or {}
    fwt = (FW.get("tbl") or {})
    fw_html = ""
    if fwt.get("rows"):
        fw_html = (f"<p {PP}>{FW.get('txt', '')}</p>" + img("fw", FW.get("png"))
                   + tabla(["Tramo", "Tasa implícita (TEA)", "Entre", "Días"], [r[:4] for r in fwt["rows"]])
                   + f'<p {NOTE}>La tasa que el mercado paga por estirar de un vencimiento de Lecap o Boncap al siguiente.</p>')

    # ---------- acciones del panel líder ----------
    A = W.get("acc") or {}
    ah = (A.get("tbl") or {}).get("head", [])
    ar = (A.get("tbl") or {}).get("rows", [])
    acc_html, acc_s = "", None
    if ar:
        ia = {k: next((i for i, x in enumerate(ah) if x.upper().startswith(k)), None) for k in ("ACCIÓN", "PRECIO", "VARIACIÓN", "MONTO", "VAR. MONTO")}
        vs = [(r[ia["ACCIÓN"]], num(r[ia["VARIACIÓN"]])) for r in ar]
        up, dn = sum(1 for _, v in vs if v and v > 0), sum(1 for _, v in vs if v and v < 0)
        mvs = sorted(vs, key=lambda x: x[1] or 0)
        acc_s = (up, dn, mvs[-1], mvs[0])
        acc_html = (chips([("Suben / bajan", f"{up} / {dn}", f"de {len(vs)} acciones", MU), ("Mayor suba", mvs[-1][0], sg(mvs[-1][1], 2, "%"), cv(mvs[-1][1])), ("Mayor baja", mvs[0][0], sg(mvs[0][1], 2, "%"), cv(mvs[0][1]))])
                    + img("acc", A.get("png"))
                    + tabla(["Acción", "Precio", "Variación", "Monto", "Var. monto"], [[r[ia["ACCIÓN"]], r[ia["PRECIO"]], (r[ia["VARIACIÓN"]], cv(num(r[ia["VARIACIÓN"]]))), r[ia["MONTO"]], (r[ia["VAR. MONTO"]], cv(num(r[ia["VAR. MONTO"]])))] for r in ar])
                    + f'<p {NOTE}>{A.get("sum", "").replace(" Tocá una acción para ver su ficha.", "")}</p>')

    # ---------- volumen de renta fija ----------
    ON = (load("ons.json") or {}).get("on") or {}
    PV = (load("pvs.json") or {}).get("on") or {}
    fam = {}
    for t, (a, b) in T.items():
        f = familia(t, PX, PSD, ON, PV)
        fam[f] = fam.get(f, 0) + (a[0] or 0)
    fams = sorted(((k, v / 1e6) for k, v in fam.items() if v > 0), key=lambda x: -x[1])
    tot = sum(fam.values())
    top = sorted(T.items(), key=lambda x: -(x[1][0][0] or 0))
    mx = fams[0][1] if fams else 1
    barras = "".join(f'<tr><td style="padding:5px 8px 5px 0;font-size:12.5px;color:#e4e4e7;white-space:nowrap;width:1%">{k}</td><td style="padding:5px 0;width:99%"><table role="presentation" style="border-collapse:collapse;width:100%"><tr>'
                     f'<td style="width:{max(1, round(v / mx * 78))}%;background:{AC};height:14px;border-radius:3px"></td><td style="padding-left:8px;font-size:12px;color:{TX};white-space:nowrap">$ {n(v, 0)} M</td></tr></table></td></tr>' for k, v in fams[:8])
    vol_html = (f"<p {PP}>Se operaron <b>$ {n(tot / 1e6, 0)} millones</b> en renta fija y ONs en pesos (rueda del {L[8:10]}/{L[5:7]})."
                + (f" Lideró {fams[0][0].lower()} con el {n(fams[0][1] * 1e6 / tot * 100, 0)}% del total." if fams and tot else "") + "</p>"
                + f'<table role="presentation" style="border-collapse:collapse;width:100%;margin-bottom:12px">{barras}</table>'
                + f'<p style="font-size:13px;font-weight:700;color:{TX};margin:6px 0 2px">Lo más operado</p>'
                + tabla(["Especie", "Familia", "Monto", "Var. precio"], [[t, familia(t, PX, PSD, ON, PV), f"$ {n((a[0] or 0) / 1e6, 0)} M", (sg((a[1] / b[1] - 1) * 100, 2, "%"), cv(a[1] / b[1] - 1)) if b and b[1] and a[1] else "—"] for t, (a, b) in top[:8]]))

    # ---------- lo más importante ----------
    pts = []
    if mep:
        pts.append(f"<b>Dólar</b>: el MEP {'subió' if (mep_d or 0) > 0 else 'bajó' if (mep_d or 0) < 0 else 'quedó'} {n(abs(mep_d or 0), 2)}% a $ {n(mep)} y el CCL {'subió' if (ccl_d or 0) > 0 else 'bajó' if (ccl_d or 0) < 0 else 'quedó'} {n(abs(ccl_d or 0), 2)}% a $ {n(ccl)}; brecha {n(bre, 1)}% y canje {n(can, 1)}%.")
    if rp:
        pts.append(f"<b>Riesgo país</b> en {n(rp, 0)} pb" + (f" ({sg(rp - rpp, 0, ' pb')})" if rpp else "") + (f"; los Globales {'comprimieron' if resumen('usd')[0] < -0.5 else 'ampliaron' if resumen('usd')[0] > 0.5 else 'quedaron estables'} ({sg(resumen('usd')[0], 0, ' pb')} de mediana)." if resumen("usd")[0] is not None else "."))
    pe = [(nm, resumen(g)[0]) for g, nm in (("fija", "Lecaps"), ("cer", "CER"), ("tamar", "TAMAR"), ("dual", "duales"), ("dl", "dólar linked")) if resumen(g)[0] is not None]
    if pe:
        pts.append("<b>Pesos</b>: " + ", ".join(f"{nm} {sg(v, 0, ' pb')}" for nm, v in pe) + " (mediana del cambio de tasa).")
    if infl or deva:
        pts.append("<b>Implícitas</b>: " + "; ".join(f"{t} a {p[0].split(' (')[0]} {n(p[1], 2)}% mensual" + (f" ({sg((p[1] - p[2]) * 100, 0, ' pb')})" if p[2] is not None else "") for t, p in (("inflación", infl), ("devaluación", deva)) if p) + ".")
    if fr_ and ix[3] is not None:
        pts.append(f"<b>Futuros</b>: {n(sum(num(r[ix[3]]) or 0 for r in fr_), 0)} contratos; " + ", ".join(f"{r[0].replace('DLR ', '')} $ {r[ix[1]]} ({r[ix[2]]})" for r in fr_[1:3]) + ".")
    cor = [(nm, resumen(g)[0]) for g, nm in (("on", "ONs"), ("pv", "provinciales")) if resumen(g)[0] is not None]
    if cor:
        pts.append("<b>Corporativos y provincias</b>: " + ", ".join(f"{nm} {sg(v, 0, ' pb')}" for nm, v in cor) + " (mediana, ley NY).")
    if acc_s:
        pts.append(f"<b>Acciones</b>: en el panel líder suben {acc_s[0]} y bajan {acc_s[1]}; la mejor, {acc_s[2][0]} ({sg(acc_s[2][1], 2, '%')}), la peor, {acc_s[3][0]} ({sg(acc_s[3][1], 2, '%')}).")
    if fams:
        pts.append(f"<b>Volumen</b>: $ {n(tot / 1e6, 0)} millones en renta fija; lo más operado, {top[0][0]} ($ {n((top[0][1][0][0] or 0) / 1e6, 0)} M).")
    kpis = chips([("Dólar MEP", "$ " + n(mep), sg(mep_d, 2, "%"), cv(mep_d)), ("Dólar CCL", "$ " + n(ccl), sg(ccl_d, 2, "%"), cv(ccl_d)), ("Oficial A3500", "$ " + n(a3), sg(a3_d, 2, "%"), cv(a3_d)),
                  ("Riesgo país", n(rp, 0) + " pb" if rp else "—", sg((rp - rpp) if rp and rpp else None, 0, " pb"), cv((rp - rpp) if rp and rpp else None, True)),
                  ("Caución 1 día", (n(cau_h, 2) + "%") if cau_h else "—", sg((cau_h - cau_a) * 100 if cau_h and cau_a else None, 0, " pb"), MU),
                  ("Inflación implícita", (n(infl[1], 2) + "%") if infl else "—", (infl[0].split(" (")[0] + " · mensual") if infl else "", MU)])

    fecha = f"{DIA[hoy.weekday()]} {hoy.day} de {MES[hoy.month - 1]} de {hoy.year}"
    ev = semana(hoy)
    S = [("Dólar", "Dólares: MEP, CCL, brecha y canje", dol_html, FC["dol"]),
         ("Soberanos", "Curva hard dollar: Globales y Bonares", hd_txt + curva("usd", "Globales y Bonares", 1100), FC["usd"]),
         ("Pesos", "Curva de Lecaps y Boncaps", curva("fija", "tasa fija", 90), FC["fija"]),
         ("Pesos", "Curva CER", curva("cer", "bonos CER (tasa real)", 365), FC["cer"]),
         ("Pesos", "Curva TAMAR", curva("tamar", "bonos TAMAR (margen)", 365), FC["tamar"]),
         ("Pesos", "Curva de duales", curva("dual", "duales", 365), FC["dual"]),
         ("Pesos", "Curva dólar linked", curva("dl", "dólar linked", 180), FC["dl"]),
         ("Futuros", "Futuros de dólar", fut_html, FC["fut"]),
         ("Expectativas", "Inflación implícita", infl_html, FC["cer"]),
         ("Expectativas", "Devaluación implícita", deva_html, FC["dl"]),
         ("Expectativas", "Forwards de tasa fija", fw_html, FC["fija"]),
         ("Corporativos", "ONs en dólares: principales ley NY", curva("on", "ONs", 1100).replace("</p>", " Las más operadas de las emisoras con deuda en Nueva York.</p>", 1) if C.get("on", {}).get("rows") else "", FC["on"]),
         ("Provincias", "Provinciales en dólares: principales ley NY", curva("pv", "provinciales", 1100) if C.get("pv", {}).get("rows") else "", FC["pv"]),
         ("Acciones", "Panel líder", acc_html, FC["acc"]),
         ("Mercado", "Volumen de renta fija", vol_html, FC["vol"])]
    tipo = os.environ.get("REPORTE_EDICION") or edicion(hoy)  # REPORTE_EDICION=semana|mes para probar
    if tipo in ("semana", "mes"):
        SP, pp = periodo(hoy, tipo, PX, PSD, ON, PV)
        if tipo == "mes" and hoy.weekday() == 4:
            SW, _ = periodo(hoy, "semana", PX, PSD, ON, PV)
            SP += SW[:1]
        S, pts = SP + S, pp + pts
    else:
        tipo = None
    if ev:
        S.append(("Agenda", "Lo que viene esta semana", tabla(["", ""], [[f"{DIA[f.weekday()].capitalize()} {f.day}", t] for f, t in ev], ["left", "left"], ["120px", None]), AC))
    cuerpo, i = "", 0
    for rub, tit, body, col in S:
        if body:
            i += 1
            cuerpo += sec(f"{i:02d}", rub, tit, body, col)
    h = (
        f'<div style="background:{BG};padding:16px 0;font-family:{FONT};color:{TX}"><table role="presentation" bgcolor="{BG}" style="max-width:640px;width:100%;margin:auto;border-collapse:collapse;background:{BG}">'
        + (f'<tr><td style="padding:6px 16px"><div style="padding:10px 14px;background:#2a2410;border:1px solid #4d3f12;border-radius:10px;color:{AC};font-size:12.5px">Prueba con los precios de ahora contra el último cierre. El informe de verdad sale al cierre, con los cierres de hoy contra los de la rueda anterior.</div></td></tr>' if en_vivo else "")
        + f'<tr><td style="padding:14px 16px 6px"><div style="font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:{AC};font-weight:700">Bonerio Local · Research</div>'
        f'<div style="font-family:{FH};font-size:30px;font-weight:700;margin:6px 0 2px;color:{TX};letter-spacing:-.02em">{ {"semana": "Cierre semanal", "mes": "Edición de fin de mes"}.get(tipo, "Informe de cierre") }</div><div style="font-size:14px;color:{MU}">{fecha.capitalize()}</div></td></tr>'
        f'<tr><td style="padding:10px 16px"><div style="background:{CARD};border:1px solid {BD};border-radius:14px;padding:18px">'
        f'<div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:{AC};font-weight:700;margin:0 0 10px">Lo más importante</div>'
        f'<ul style="margin:0 0 14px;padding-left:18px;font-size:14px;line-height:1.65;color:#d4d4d8">' + "".join(f"<li style='margin-bottom:5px'>{x}</li>" for x in pts) + "</ul>" + kpis + "</div></td></tr>"
        + cuerpo
        + f'<tr><td style="padding:18px 16px 8px"><a href="{SITE}" style="display:inline-block;background:{AC};color:#141414;padding:12px 20px;border-radius:10px;text-decoration:none;font-size:14px;font-weight:700">Abrir la terminal</a></td></tr>'
        f'<tr><td style="padding:12px 16px 24px;font-size:11.5px;line-height:1.55;color:#71717a">Informe generado automáticamente con los mismos datos y gráficos de la terminal: precios de BYMA (data912), A3 Mercados y el BCRA. '
        'Tasas con liquidación T+1. Te llega porque te suscribiste al reporte diario: lo podés dar de baja en Alertas.'
        f'<div style="margin-top:12px;padding:12px 14px;border:1px solid {BD};border-radius:10px;color:{MU};font-size:11.5px;line-height:1.55"><b style="color:{TX}">Aviso legal.</b> '
        'Este informe tiene carácter exclusivamente informativo y no constituye una recomendación de inversión ni una oferta o invitación a comprar o vender valores. '
        'Los datos y cálculos pueden contener errores u omisiones; verificalos antes de operar. Rendimientos pasados no garantizan resultados futuros.</div></td></tr></table></div>'
    )
    asunto = ("[Prueba] " if en_vivo else "") + f"{ {'semana': 'Cierre semanal', 'mes': 'Fin de ' + MES[hoy.month - 1]}.get(tipo, 'Informe de cierre') } {hoy.day}/{hoy.month}: MEP $ {n(mep)} ({sg(mep_d, 2, '%')}), riesgo país {n(rp, 0)} pb"
    return asunto, h, IMG


def enviar(asunto, html, img, mails):
    att = [{"filename": k + ".png", "content": base64.b64encode(v).decode(), "content_id": k} for k, v in img.items()]
    ok = 0
    for m in mails:  # de a uno: el envío en lote de Resend no acepta imágenes adjuntas
        try:
            http("https://api.resend.com/emails", {"from": FROM, "to": [m], "subject": asunto, "html": html, "attachments": att}, headers={"Authorization": "Bearer " + RESEND})
            ok += 1
        except urllib.error.HTTPError as e:
            print("resend", e.code, e.read()[:300])
    return ok


def suscriptos():
    h = {"apikey": KEY, "User-Agent": "bonerio-reporte/1.0"}  # Supabase rechaza la clave secret (401) si el User-Agent parece de un navegador
    if KEY.startswith("eyJ"):
        h["Authorization"] = "Bearer " + KEY
    subs = http(SB + "/rest/v1/reporte?activo=eq.true&select=email", headers=h) or []
    return sorted({s["email"] for s in subs if s.get("email")})


def main(prueba=False):
    hoy = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date().isoformat()
    if not prueba and (load("reporte_enviado.json") or {}).get("f") == hoy:
        print("el reporte de hoy ya salió")
        return
    if not KEY or not RESEND:
        print("faltan SUPABASE_SERVICE_KEY o RESEND_API_KEY")
        return
    asunto, html, img = armar(prueba)
    if not html:
        return
    try:
        mails = suscriptos()
    except Exception as e:
        print("supabase", e, "| clave:", "sb_secret" if KEY.startswith("sb_secret_") else "JWT service_role/anon" if KEY.startswith("eyJ") else "sb_publishable (no sirve)" if KEY.startswith("sb_publishable_") else "formato desconocido", len(KEY), "caracteres")  # para ver qué se cargó sin mostrarla
        return
    if not mails:
        print("nadie suscripto")
        return
    ok = enviar(asunto, html, img, mails)
    print("reporte" + (" de prueba" if prueba else "") + " enviado a", ok, "de", len(mails))
    if not prueba and ok:
        with open(os.path.join(D, "reporte_enviado.json"), "w") as f:
            json.dump({"f": hoy, "n": ok}, f)


if __name__ == "__main__":
    if "--html" in sys.argv:  # arma el mail sin mandarlo, para revisarlo: scripts/reporte.py --html [--web datos.json] (deja el HTML y las imágenes en /tmp)
        w = sys.argv[sys.argv.index("--web") + 1] if "--web" in sys.argv else None
        a, h, img = armar(True, w)
        for k, v in (img or {}).items():
            open("/tmp/reporte_" + k + ".png", "wb").write(v)
            h = h.replace("cid:" + k, "/tmp/reporte_" + k + ".png")
        open("/tmp/reporte.html", "w").write(h or "sin datos")
        print(a)
    else:
        main("--prueba-envio" in sys.argv)
