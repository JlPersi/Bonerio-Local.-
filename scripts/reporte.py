"""Reporte diario por mail: al cierre, a los usuarios suscriptos (tabla reporte de Supabase, activo = true), por Resend.

Corre en cierre.yml después de guardar los datos del día. Sale una vez por rueda: la fecha enviada queda en data/reporte_enviado.json
(el cierre corre hasta tres veces) y solo se manda si data/volumen.json ya tiene la rueda de hoy.
Formato de informe de research: lo más importante del día (texto armado con los datos), KPIs, dólar día contra día, las curvas de tasa fija,
CER y hard dollar de hoy contra la rueda anterior con su lectura, la inflación implícita (Lecaps contra CER), los futuros de dólar contra las
Lecaps, el volumen por familia, lo más operado, subas y bajas y la agenda. Gráficos: scripts/reporte_curvas.py, pegados en el mail.
Prueba: scripts/reporte.py --prueba-envio manda a los suscriptos un ejemplo con los precios de ahora contra el último cierre.
Secrets: SUPABASE_SERVICE_KEY y RESEND_API_KEY.
"""
import json, os, re, sys, urllib.request, urllib.error, datetime as dt

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


def ruedas():
    v = load("volumen.json")
    if not v:
        return None, None, {}
    dates, T = v["dates"], {}
    L = len(dates) - 1
    for t, o in v["t"].items():
        if o.get("s") != "P":
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


# estilos del mail (todo en línea: los clientes de correo ignoran las hojas de estilo)
INK, MU, BD, AC = "#18181b", "#71717a", "#e4e4e7", "#0f172a"
H2 = f'style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{MU};margin:30px 0 4px;font-weight:700"'
H3 = f'style="font-size:17px;margin:0 0 6px;color:{INK}"'
PP = f'style="font-size:14px;line-height:1.6;color:#3f3f46;margin:0 0 10px"'
IMGS = 'width="592" style="display:block;width:100%;max-width:592px;height:auto;margin:8px 0 6px"'


def sec(num, rubro, titulo, cuerpo):
    return (f'<tr><td style="padding:0 28px"><p {H2}>{num} · {rubro}</p><h3 {H3}>{titulo}</h3>{cuerpo}</td></tr>')


def armar(en_vivo=False):
    """(asunto, html, imágenes {cid: png}). en_vivo: precios de ahora (data912) contra el último cierre, para la prueba."""
    sys.path.insert(0, os.path.dirname(__file__))
    import reporte_curvas as RC
    hoy = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date()
    L, P, T = ruedas()
    if not en_vivo and L != hoy.isoformat():
        print("todavía no está la rueda de hoy en volumen.json:", L)
        return None, None, None
    f_hoy, f_ayer, lab, CV, ph, pa = RC.curvas(en_vivo)
    PX, PSD, _ = RC.datos()
    dm = lambda s: s[8:10] + "/" + s[5:7]
    lab_h, lab_a = (lab + " (" + dm(f_hoy) + ")"), "Cierre " + dm(f_ayer)
    sg = lambda v, d=0, u="": "—" if v is None else ("+" if round(v, d) > 0 else "") + n(round(v, d) + 0, d) + u
    col = lambda v, inv=False: MU if not v else ("#b91c1c" if (v > 0) != inv else "#15803d")

    # ---------- dólar, riesgo país, caución ----------
    dl = load("dolar.json") or {}
    a3, a3p = last2(dl.get("A3500"))
    TJ = load("tasas.json") or {}
    if en_vivo and (TJ.get("vivo") or {}).get("spot") and str(TJ["vivo"].get("ts", ""))[:10] == hoy.isoformat():
        a3, a3p = float(TJ["vivo"]["spot"]), a3
    rv = load("riesgo_vivo.json") or {}
    rp, rpp = last2((load("riesgo_pais.json") or {}).get("d"))
    if en_vivo and rv.get("v"):
        rp, rpp = float(rv["v"]), rp
    ch = lambda a, b: (a / b - 1) * 100 if a and b else None
    dol = RC.dolar(ph, pa)
    mep, mepp, ccl, cclp = dol[0][1], dol[0][2], dol[2][1], dol[2][2]
    brecha = lambda m, o: (m / o - 1) * 100 if m and o else None
    cau = TJ.get("cau") or {}
    ck = sorted(cau)
    c1 = lambda d: next((r[1] for r in cau.get(d, []) if r[0] == 1), None)
    cau_h, cau_a = (c1(ck[-1]) if ck else None), (c1(ck[-2]) if len(ck) > 1 else None)

    # ---------- curvas ----------
    IMG = {}
    rows_f = [r for r in CV["fija"] if r[1] <= 800 and -0.2 < r[2] < 2]
    rows_c = [r for r in CV["cer"] if r[1] <= 2000 and -0.2 < r[2] < 2]
    rows_u = [r for r in CV["usd"] if -0.2 < r[2] < 2]
    bp = lambda r: round((r[2] - r[3]) * 1e4) + 0
    med = lambda rs: sorted(bp(r) for r in rs)[len(rs) // 2] if rs else None
    prom = lambda rs: sum(bp(r) for r in rs) / len(rs) if rs else None

    def tabla(rows):
        td = 'style="padding:6px 8px;font-size:12.5px;border-top:1px solid #f0f0f0'
        cel = [f'<td {td};font-weight:600">{r[0]}</td><td {td};text-align:right">{n(r[2] * 100, 2)}%</td><td {td};text-align:right;color:{col(bp(r))}">{sg(bp(r), 0, " pb")}</td>' for r in rows]
        half = (len(cel) + 1) // 2
        hd = f'<th style="padding:6px 8px;font-size:10.5px;font-weight:600;color:{MU};text-align:{{}};text-transform:uppercase;letter-spacing:.05em">{{}}</th>'
        hdr = "".join(hd.format(a, t) for a, t in (("left", "Bono"), ("right", "TIR"), ("right", "Cambio")))
        return ('<table style="border-collapse:collapse;width:100%"><tr>' + hdr + '<th style="width:16px"></th>' + hdr + "</tr>"
                + "".join("<tr>" + cel[i] + "<td></td>" + (cel[i + half] if i + half < len(cel) else '<td colspan="3"></td>') + "</tr>" for i in range(half)) + "</table>")

    def tramo(rows, corte):
        c, l = [r for r in rows if r[1] <= corte], [r for r in rows if r[1] > corte]
        return prom(c), prom(l)

    def lectura(rows, nombre, corte, unidad):
        if not rows:
            return ""
        m, (c, l) = prom(rows), tramo(rows, corte)
        mx = max(rows, key=lambda r: abs(bp(r)))
        t = f"La curva de {nombre} {'subió' if m > 0.5 else 'bajó' if m < -0.5 else 'quedó sin cambios'}"
        t += f" {n(abs(m), 0)} pb en promedio" if abs(m) > 0.5 else ""
        if c is not None and l is not None and abs(c - l) >= 5:
            empina = l > c
            t += f": el tramo corto (hasta {corte} {unidad}) se movió {sg(c, 0, ' pb')} y el largo {sg(l, 0, ' pb')}, así que se {'empinó' if empina else 'aplanó'}"
        t += f". El mayor movimiento fue {mx[0]} ({sg(bp(mx), 0, ' pb')}, a {n(mx[2] * 100, 2)}%)."
        return f"<p {PP}>{t}</p>"

    def curva(key, rows, xlab, color, ley=None):
        if len(rows) < 2:
            return ""
        IMG[key] = RC.grafico(rows, "", xlab, color, lab_h, lab_a, ley)
        return f'<img src="cid:{key}" alt="" {IMGS}>' + tabla(rows)

    # inflación implícita (breakeven): Lecaps contra CER al mismo plazo, con las dos curvas ajustadas
    ff, fc = RC.ajuste(rows_f), RC.ajuste(rows_c)
    ffa, fca = RC.ajuste(rows_f, 3), RC.ajuste(rows_c, 3)
    be = []
    if ff and fc and rows_f:
        top_x = max(r[1] for r in rows_f)
        for d in (60, 120, 180, 240, 300, 365):
            if d <= top_x + 5 and d >= min(r[1] for r in rows_f) - 5:
                bm = lambda f1, f2: ((1 + f1(d)) / (1 + f2(d))) ** (1 / 12) - 1
                be.append((d, bm(ff, fc) * 100, bm(ffa, fca) * 100 if ffa and fca else None))
    be_html = ""
    if be:
        td = 'style="padding:7px 8px;font-size:13px;border-top:1px solid #f0f0f0;text-align:right'
        be_html = (f"<p {PP}>La diferencia entre la tasa de las Lecaps y la tasa real de los bonos CER al mismo plazo es la inflación que descuenta el mercado. "
                   f"A {be[min(2, len(be) - 1)][0]} días da <b>{n(be[min(2, len(be) - 1)][1], 2)}% mensual</b> promedio.</p>"
                   f'<table style="border-collapse:collapse;width:100%"><tr><th style="padding:6px 8px;font-size:10.5px;color:{MU};text-align:left;text-transform:uppercase;letter-spacing:.05em">Plazo</th><th style="padding:6px 8px;font-size:10.5px;color:{MU};text-align:right;text-transform:uppercase;letter-spacing:.05em">Inflación mensual implícita</th><th style="padding:6px 8px;font-size:10.5px;color:{MU};text-align:right;text-transform:uppercase;letter-spacing:.05em">Rueda anterior</th></tr>'
                   + "".join(f'<tr><td {td};text-align:left;font-weight:600">{d} días</td><td {td}">{n(v, 2)}%</td><td {td};color:{MU}">{n(a, 2) + "%" if a is not None else "—"}</td></tr>' for d, v, a in be) + "</table>")

    # hard dollar: spread entre ley local y ley NY en los pares
    pares = []
    U = {r[0]: r for r in rows_u}
    for gd, al in (("GD29", "AL29"), ("GD30", "AL30"), ("GD35", "AL35"), ("GD38", "AE38"), ("GD41", "AL41")):
        if gd in U and al in U:
            pares.append((al + "/" + gd, (U[al][2] - U[gd][2]) * 1e4, (U[al][3] - U[gd][3]) * 1e4))
    hd_txt = ""
    if rows_u:
        m = prom(rows_u)
        hd_txt = f"<p {PP}>Los bonos en dólares {'comprimieron' if m < -0.5 else 'ampliaron' if m > 0.5 else 'quedaron estables'}" + (f": la TIR bajó {n(abs(m), 0)} pb en promedio" if m < -0.5 else f": la TIR subió {n(m, 0)} pb en promedio" if m > 0.5 else "")
        if rp and rpp:
            hd_txt += f", con el riesgo país en {n(rp, 0)} pb ({sg(rp - rpp, 0, ' pb')})"
        hd_txt += "."
        if pares:
            sp = sum(p[1] for p in pares) / len(pares)
            spa = sum(p[2] for p in pares) / len(pares)
            hd_txt += f" Los Bonares rinden en promedio <b>{n(sp, 0)} pb</b> más que los Globales del mismo vencimiento (el premio por ley local), {'más' if sp > spa else 'menos'} que en la rueda anterior ({n(spa, 0)} pb)."
        hd_txt += "</p>"

    # futuros de dólar contra Lecaps
    fut_rows, spot = [], a3
    if en_vivo:
        for r in (TJ.get("vivo") or {}).get("fut") or []:
            p_ = r[4] or r[5]
            if str(r[0]).startswith("DLR/") and p_ and r[1]:
                fut_rows.append((r[0][4:], r[1], p_))
    else:
        fk = sorted(TJ.get("fut") or {})
        if fk and fk[-1] == hoy.isoformat():
            for r in TJ["fut"][fk[-1]]:
                if str(r[0]).startswith("DLR") and r[2]:
                    fut_rows.append((r[0][3:5] + "/" + r[0][7:9], r[1], r[2]))
    fut_pts = []
    for nm, vto, p_ in sorted(fut_rows, key=lambda x: x[1]):
        d = (dt.date.fromisoformat(vto) - hoy).days
        if d > 3 and spot and d <= 400:
            fut_pts.append((d, (p_ / spot - 1) * 365 / d * 100, nm, p_))
    lec = [(r[1], ((1 + r[2]) ** (r[1] / 365) - 1) * 365 / r[1] * 100) for r in rows_f if r[1] > 0]
    fut_html = ""
    if fut_pts and lec:
        IMG["fut"] = RC.tasas_fut(lec, fut_pts)
        fl = RC.ajuste([(None, x, y) for x, y in lec])
        cmp_ = [(nm, d, y, fl(d)) for d, y, nm, _ in fut_pts if fl and min(x for x, _ in lec) - 10 <= d <= max(x for x, _ in lec) + 10]
        txt = "Si la tasa en pesos de las Lecaps supera la devaluación que descuentan los futuros al mismo plazo, el carry cubierto rinde."
        if cmp_:
            c0 = cmp_[min(1, len(cmp_) - 1)]
            dif = (c0[3] - c0[2]) * 100
            txt += f" Al vencimiento de {c0[0]} ({c0[1]} días) la Lecap rinde {n(c0[3], 2)}% de TNA contra {n(c0[2], 2)}% del futuro: <b>{sg(dif, 0, ' pb')}</b> a favor de {'los pesos' if dif > 0 else 'la cobertura'}."
        fut_html = (f"<p {PP}>{txt}</p>" + f'<img src="cid:fut" alt="" {IMGS}>'
                    + '<table style="border-collapse:collapse;width:100%"><tr>' + "".join(f'<th style="padding:6px 6px;font-size:10.5px;color:{MU};text-align:right;text-transform:uppercase;letter-spacing:.05em">{h}</th>' for h in ("Contrato", "Precio", "Días", "TNA implícita")) + "</tr>"
                    + "".join(f'<tr><td style="padding:6px;font-size:12.5px;border-top:1px solid #f0f0f0;text-align:right;font-weight:600">{nm}</td><td style="padding:6px;font-size:12.5px;border-top:1px solid #f0f0f0;text-align:right">$ {n(p_, 2)}</td><td style="padding:6px;font-size:12.5px;border-top:1px solid #f0f0f0;text-align:right">{d}</td><td style="padding:6px;font-size:12.5px;border-top:1px solid #f0f0f0;text-align:right">{n(y, 2)}%</td></tr>' for d, y, nm, p_ in fut_pts[:6]) + "</table>")

    # ---------- volumen ----------
    ON = (load("ons.json") or {}).get("on") or {}
    PV = (load("pvs.json") or {}).get("on") or {}
    fam = {}
    for t, (a, b) in T.items():
        f = familia(t, PX, PSD, ON, PV)
        fam[f] = fam.get(f, 0) + (a[0] or 0)
    fams = sorted(((k, v / 1e6) for k, v in fam.items() if v > 0), key=lambda x: -x[1])
    tot = sum(fam.values())
    if fams:
        IMG["vol"] = RC.barras(fams[:8])
    top = sorted(T.items(), key=lambda x: -(x[1][0][0] or 0))
    liq = [x for x in top[:80] if x[1][1] and x[1][1][1] and x[1][0][1]]
    mv = sorted(((t, (a[1] / b[1] - 1) * 100) for t, (a, b) in liq), key=lambda x: x[1])
    vol_d = dm(L)
    li = lambda xs: "".join(f'<tr><td style="padding:6px 0;font-size:13px;border-top:1px solid #f0f0f0"><b>{t}</b></td><td style="padding:6px 0;text-align:right;font-size:13px;border-top:1px solid #f0f0f0">{pc(v)}</td></tr>' for t, v in xs)
    vol_html = (f"<p {PP}>Se operaron <b>$ {n(tot / 1e6, 0)} millones</b> en renta fija y ONs en pesos (rueda del {vol_d}). "
                + (f"Lideró {fams[0][0].lower()} con el {n(fams[0][1] * 1e6 / tot * 100, 0)}% del total." if fams and tot else "") + "</p>"
                + (f'<img src="cid:vol" alt="" {IMGS}>' if "vol" in IMG else "")
                + f'<p style="font-size:13px;font-weight:700;margin:14px 0 4px">Lo más operado</p><table style="width:100%;border-collapse:collapse">'
                + "".join(f'<tr><td style="padding:6px 0;font-size:13px;border-top:1px solid #f0f0f0"><b>{t}</b> <span style="color:{MU}">{familia(t, PX, PSD, ON, PV).lower()}</span></td><td style="padding:6px 0;text-align:right;font-size:13px;border-top:1px solid #f0f0f0">$ {n((a[0] or 0) / 1e6, 0)} M</td><td style="padding:6px 0 6px 12px;text-align:right;font-size:13px;border-top:1px solid #f0f0f0">{pc(ch(a[1], b[1] if b else None))}</td></tr>' for t, (a, b) in top[:6])
                + "</table>"
                + '<table style="width:100%;border-collapse:collapse;margin-top:16px"><tr><td style="width:50%;vertical-align:top;padding-right:12px"><p style="font-size:13px;font-weight:700;margin:0 0 4px">Mayores subas</p><table style="width:100%;border-collapse:collapse">'
                + li(mv[::-1][:5]) + '</table></td><td style="width:50%;vertical-align:top;padding-left:12px"><p style="font-size:13px;font-weight:700;margin:0 0 4px">Mayores bajas</p><table style="width:100%;border-collapse:collapse">'
                + li(mv[:5]) + "</table></td></tr></table>"
                + f'<p style="font-size:12px;color:{MU};margin:6px 0 0">Entre las 80 especies más operadas.</p>')

    # ---------- lo más importante (resumen arriba) ----------
    pts = []
    if mep and mepp:
        pts.append(f"El <b>MEP</b> {'subió' if mep > mepp else 'bajó'} {n(abs(ch(mep, mepp)), 2)}% a $ {n(mep)} y el <b>CCL</b> {'subió' if (ccl or 0) > (cclp or 0) else 'bajó'} {n(abs(ch(ccl, cclp) or 0), 2)}% a $ {n(ccl)}; la brecha con el oficial quedó en {n(brecha(mep, a3), 2)}%.")
    if rp and rpp:
        pts.append(f"El <b>riesgo país</b> {'subió' if rp > rpp else 'bajó' if rp < rpp else 'quedó'} {n(abs(rp - rpp), 0) + ' pb ' if rp != rpp else ''}a {n(rp, 0)} pb.")
    if rows_f:
        pts.append(f"<b>Tasa fija</b>: la curva {'subió' if prom(rows_f) > 0.5 else 'bajó' if prom(rows_f) < -0.5 else 'quedó estable'}" + (f" {n(abs(prom(rows_f)), 0)} pb en promedio" if abs(prom(rows_f)) > 0.5 else "") + (f"; la inflación implícita a {be[min(2, len(be) - 1)][0]} días es {n(be[min(2, len(be) - 1)][1], 2)}% mensual." if be else "."))
    if fut_pts:
        f0 = fut_pts[min(1, len(fut_pts) - 1)]
        pts.append(f"El futuro de dólar de {f0[2]} cerró en $ {n(f0[3], 2)}, con una tasa implícita de {n(f0[1], 2)}% de TNA.")
    if fams:
        pts.append(f"Se operaron $ {n(tot / 1e6, 0)} millones; lo más operado fue {top[0][0]} ($ {n((top[0][1][0][0] or 0) / 1e6, 0)} M).")
    kpi = lambda k, v, d, inv=False: (f'<td style="width:33%;padding:12px 14px;border:1px solid {BD};vertical-align:top"><div style="font-size:10.5px;color:{MU};text-transform:uppercase;letter-spacing:.06em">{k}</div>'
                                       f'<div style="font-size:19px;font-weight:700;margin:3px 0 1px;color:{INK}">{v}</div><div style="font-size:12px;color:{col(d[0], inv) if d[0] is not None else MU}">{d[1]}</div></td>')
    kpis = ('<table style="width:100%;border-collapse:collapse;margin:14px 0 0"><tr>'
            + kpi("Dólar MEP", "$ " + n(mep), (ch(mep, mepp), sg(ch(mep, mepp), 2, "%")))
            + kpi("Dólar CCL", "$ " + n(ccl), (ch(ccl, cclp), sg(ch(ccl, cclp), 2, "%")))
            + kpi("Oficial A3500", "$ " + n(a3), (ch(a3, a3p), sg(ch(a3, a3p), 2, "%"))) + "</tr><tr>"
            + kpi("Riesgo país", n(rp, 0) + " pb", ((rp - rpp) if rp and rpp else None, sg((rp - rpp) if rp and rpp else None, 0, " pb")))
            + kpi("Caución 1 día", (n(cau_h, 2) + "%") if cau_h else "—", ((cau_h - cau_a) if cau_h and cau_a else None, sg((cau_h - cau_a) * 100 if cau_h and cau_a else None, 0, " pb")))
            + kpi("Brecha MEP", n(brecha(mep, a3), 2) + "%", (None, "contra " + n(brecha(mepp, a3p if not en_vivo else a3p), 2) + "% anterior"))
            + "</tr></table>")
    # colores de los KPI: suba del dólar en rojo no tiene sentido; se marca solo el signo
    fecha = f"{DIA[hoy.weekday()]} {hoy.day} de {MES[hoy.month - 1]} de {hoy.year}"
    ev = semana(hoy)
    tabla_dol = ('<table style="width:100%;border-collapse:collapse;font-size:13.5px"><tr>'
                 + "".join(f'<th style="padding:6px 0;font-size:10.5px;color:{MU};text-align:{a};text-transform:uppercase;letter-spacing:.05em">{h}</th>' for a, h in (("left", ""), ("right", lab_h), ("right", lab_a), ("right", "Cambio")))
                 + "</tr>"
                 + "".join(f'<tr><td style="padding:7px 0;border-top:1px solid #f0f0f0;color:#3f3f46">{k}</td><td style="padding:7px 0;border-top:1px solid #f0f0f0;text-align:right"><b>{v1}</b></td><td style="padding:7px 0;border-top:1px solid #f0f0f0;text-align:right;color:{MU}">{v0}</td><td style="padding:7px 0;border-top:1px solid #f0f0f0;text-align:right">{d}</td></tr>'
                           for k, v1, v0, d in ([("Oficial (A3500)", "$ " + n(a3), "$ " + n(a3p), pc(ch(a3, a3p)))]
                                                + [(k, "$ " + n(a), "$ " + n(b), pc(ch(a, b))) for k, a, b in dol[:4]]
                                                + [("Canje (CCL contra MEP)", n(dol[4][1]) + "%", n(dol[4][2]) + "%", sg((dol[4][1] or 0) - (dol[4][2] or 0), 2, " pp")),
                                                   ("Brecha MEP contra oficial", n(brecha(mep, a3)) + "%", n(brecha(mepp, a3p)) + "%", sg((brecha(mep, a3) or 0) - (brecha(mepp, a3p) or 0), 2, " pp"))]))
                 + "</table>")
    cuerpo = (
        sec("01", "Dólar", "Dólar y brecha", tabla_dol)
        + sec("02", "Pesos", "Curva de tasa fija", lectura(rows_f, "Lecaps y Boncaps", 90, "días") + curva("fija", rows_f, "días al vencimiento", "#d97706"))
        + sec("03", "Pesos", "Curva CER", lectura(rows_c, "bonos CER (TIR real)", 365, "días") + curva("cer", rows_c, "días al vencimiento", "#0d9488"))
        + (sec("04", "Pesos", "Inflación implícita", be_html) if be_html else "")
        + (sec("05", "Dólar", "Futuros de dólar contra Lecaps", fut_html) if fut_html else "")
        + sec("06", "Dólares", "Curva hard dollar", hd_txt + curva("usd", rows_u, "duration (años)", "#2563eb", ley=["GD", "A"]))
        + sec("07", "Mercado", "Volumen", vol_html)
        + (sec("08", "Agenda", "Lo que viene esta semana", '<table style="width:100%;border-collapse:collapse">' + "".join(f'<tr><td style="padding:7px 0;font-size:13.5px;border-top:1px solid #f0f0f0;width:120px;font-weight:600">{DIA[f.weekday()].capitalize()} {f.day}</td><td style="padding:7px 0;font-size:13.5px;border-top:1px solid #f0f0f0">{t}</td></tr>' for f, t in ev) + "</table>") if ev else "")
    )
    h = (
        f'<div style="background:#f4f4f5;padding:20px 0;font-family:Inter,Helvetica,Arial,sans-serif;color:{INK}"><table role="presentation" style="max-width:648px;width:100%;margin:auto;background:#fff;border-collapse:collapse;border:1px solid {BD}">'
        + (f'<tr><td style="padding:12px 28px;background:#fef3c7;color:#92400e;font-size:12.5px">Ejemplo con los precios de ahora contra el último cierre. El informe de verdad sale al cierre, con los cierres de hoy contra los de la rueda anterior.</td></tr>' if en_vivo else "")
        + f'<tr><td style="padding:22px 28px 18px;background:{AC};color:#fff"><div style="font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#a5b4fc;font-weight:700">Bonerio Local · Research</div>'
        f'<div style="font-size:24px;font-weight:700;margin:6px 0 2px">Informe de cierre</div><div style="font-size:14px;color:#cbd5e1">{fecha.capitalize()}</div></td></tr>'
        f'<tr><td style="padding:22px 28px 4px"><p style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{MU};margin:0 0 8px;font-weight:700">Lo más importante</p>'
        f'<ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.65;color:#27272a">' + "".join(f"<li style='margin-bottom:4px'>{x}</li>" for x in pts) + "</ul>" + kpis + "</td></tr>"
        + cuerpo
        + f'<tr><td style="padding:26px 28px 8px"><a href="{SITE}" style="display:inline-block;background:{AC};color:#fff;padding:11px 18px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600">Abrir la terminal</a></td></tr>'
        f'<tr><td style="padding:14px 28px 24px;font-size:11.5px;line-height:1.55;color:#a1a1aa">Informe generado automáticamente con precios de BYMA (data912), A3 Mercados y el BCRA. Las TIR son con liquidación T+1; la inflación implícita surge de las curvas ajustadas de Lecaps y CER. '
        'No es una recomendación de inversión. Te llega porque te suscribiste al reporte diario: lo podés dar de baja en la pestaña Alertas.</td></tr></table></div>'
    )
    asunto = ("[Prueba] " if en_vivo else "") + f"Informe de cierre {hoy.day}/{hoy.month}: MEP $ {n(mep)} ({sg(ch(mep, mepp), 2, '%')}), riesgo país {n(rp, 0)} pb"
    return asunto, h, IMG


def enviar(asunto, html, img, mails):
    import base64
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
    if "--html" in sys.argv:  # arma el mail sin mandarlo, para revisarlo: scripts/reporte.py --html [--vivo] (deja las imágenes en /tmp)
        a, h, img = armar("--vivo" in sys.argv)
        for k, v in (img or {}).items():
            open("/tmp/reporte_" + k + ".png", "wb").write(v)
            h = h.replace("cid:" + k, "/tmp/reporte_" + k + ".png")
        print(h or "sin rueda de hoy")
    else:
        main("--prueba-envio" in sys.argv)
