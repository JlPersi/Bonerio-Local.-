"""Reporte diario por mail: al cierre, a los usuarios suscriptos (tabla reporte de Supabase, activo = true), por Resend.

Corre en cierre.yml después de guardar los datos del día. Sale una vez por rueda: la fecha enviada queda en data/reporte_enviado.json
(el cierre corre hasta tres veces) y solo se manda si data/volumen.json ya tiene la rueda de hoy.
Contenido: dólar día contra día (oficial, MEP y CCL de AL30 y GD30, canje y brecha), riesgo país, las curvas de tasa fija, CER y hard dollar
de hoy contra la rueda anterior (gráficos pegados en el mail, de scripts/reporte_curvas.py), lo más operado, subas y bajas y lo que viene en la semana.
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


def armar(en_vivo=False):
    """(asunto, html, imágenes {cid: png}). en_vivo: precios de ahora (data912) contra el último cierre, para la prueba."""
    import base64
    sys.path.insert(0, os.path.dirname(__file__))
    import reporte_curvas as RC
    hoy = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date()
    L, P, T = ruedas()
    if not en_vivo and L != hoy.isoformat():
        print("todavía no está la rueda de hoy en volumen.json:", L)
        return None, None, None
    f_hoy, f_ayer, lab, CV, ph, pa = RC.curvas(en_vivo)
    dm = lambda s: s[8:10] + "/" + s[5:7]
    lab_h, lab_a = (lab + " (" + dm(f_hoy) + ")"), "Cierre " + dm(f_ayer)
    dl = load("dolar.json") or {}
    a3, a3p = last2(dl.get("A3500"))
    rv = load("riesgo_vivo.json") or {}
    rp, rpp = last2((load("riesgo_pais.json") or {}).get("d"))
    if en_vivo and rv.get("v"):
        rp, rpp = float(rv["v"]), rp
    ch = lambda a, b: (a / b - 1) * 100 if a and b else None
    TD = 'style="padding:7px 0;text-align:right;font-variant-numeric:tabular-nums"'
    th = f'<tr><td></td><td {TD}><small style="color:#71717a">{lab_h}</small></td><td {TD}><small style="color:#71717a">{lab_a}</small></td><td {TD}><small style="color:#71717a">Cambio</small></td></tr>'
    def row(k, a, b, fmt=lambda v: "$ " + n(v), d=None):
        dd = d if d is not None else pc(ch(a, b))
        return f'<tr><td style="padding:7px 0;color:#52525b">{k}</td><td {TD}><b>{fmt(a)}</b></td><td {TD} style="color:#71717a">{fmt(b)}</td><td {TD}>{dd}</td></tr>'
    pp = lambda a, b: f'{"+" if a - b > 0 else ""}{n(a - b, 2)} pp' if a is not None and b is not None else ""
    dol = RC.dolar(ph, pa)
    mep, mepp = dol[0][1], dol[0][2]
    brecha = lambda m, o: (m / o - 1) * 100 if m and o else None
    tabla_dol = ('<table style="width:100%;border-collapse:collapse;font-size:14px">' + th
                 + row("Oficial (A3500)", a3 if not en_vivo else a3, a3p if not en_vivo else a3p)
                 + "".join(row(k, a, b) for k, a, b in dol[:4])
                 + row(dol[4][0], dol[4][1], dol[4][2], lambda v: n(v) + "%", pp(dol[4][1], dol[4][2]))
                 + row("Brecha MEP contra oficial (%)", brecha(mep, a3), brecha(mepp, a3 if en_vivo else a3p), lambda v: n(v) + "%", pp(brecha(mep, a3), brecha(mepp, a3 if en_vivo else a3p)))
                 + row("Riesgo país", rp, rpp, lambda v: n(v, 0) + " pb", (f'{"+" if rp - rpp > 0 else ""}{n(rp - rpp, 0)} pb' if rp and rpp else ""))
                 + "</table>")
    IMG = {}
    def curva(key, titulo, xlab, color, ley=None, maxx=None):
        rows = [r for r in CV[key] if (maxx is None or r[1] <= maxx) and -0.2 < r[2] < 2]
        if len(rows) < 2:
            return ""
        IMG[key] = RC.grafico(rows, titulo, xlab, color, lab_h, lab_a, ley)
        bp = lambda r: (r[2] - r[3]) * 1e4
        med = sorted(bp(r) for r in rows)[len(rows) // 2]
        cel = [f'<td style="padding:4px 6px;font-size:12px;text-align:center;border-top:1px solid #e4e4e7"><b>{r[0]}</b><br>{n(r[2] * 100, 2)}%<br><span style="color:{"#b91c1c" if bp(r) > 0 else "#15803d" if bp(r) < 0 else "#52525b"}">{"+" if bp(r) > 0 else ""}{n(bp(r), 0)} pb</span></td>' for r in rows]
        return (f'<h3 style="font-size:15px;margin:24px 0 2px">{titulo}</h3><p style="margin:0 0 6px;font-size:13px;color:#71717a">Mediana del cambio: <b>{"+" if med > 0 else ""}{n(med, 0)} pb</b> (en rojo sube la tasa, el precio baja)</p>'
                f'<img src="cid:{key}" alt="{titulo}" width="560" style="width:100%;max-width:560px;border:1px solid #e4e4e7;border-radius:8px">'
                '<table style="border-collapse:collapse;margin-top:6px;width:100%">' + "".join("<tr>" + "".join(cel[i:i + 8]) + "</tr>" for i in range(0, len(cel), 8)) + "</table>")
    curvas_html = (curva("fija", "Tasa fija: TEA de Lecaps y Boncaps", "días al vencimiento", "#d97706", maxx=800)
                   + curva("cer", "CER: TIR real", "días al vencimiento", "#0d9488", maxx=2000)
                   + curva("usd", "Hard dollar: TIR en dólares", "duration (años)", "#2563eb", ley=["GD", "A"]))
    top = sorted(T.items(), key=lambda x: -(x[1][0][0] or 0))
    liq = [x for x in top[:80] if x[1][1] and x[1][1][1] and x[1][0][1]]
    mv = sorted(((t, (a[1] / b[1] - 1) * 100) for t, (a, b) in liq), key=lambda x: x[1])
    tot = sum((a[0] or 0) for a, b in T.values())
    li = lambda xs: "".join(f'<tr><td style="padding:6px 0"><b>{t}</b></td><td style="padding:6px 0;text-align:right">{pc(v)}</td></tr>' for t, v in xs)
    fecha = f"{DIA[hoy.weekday()]} {hoy.day} de {MES[hoy.month - 1]}"
    ev = semana(hoy)
    vol_nota = f' (rueda del {dm(L)})' if en_vivo else ""
    h = (
        '<div style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:auto;padding:24px;color:#18181b">'
        + ('<p style="background:#fef3c7;color:#92400e;padding:10px 12px;border-radius:8px;font-size:13px;margin:0 0 14px">Ejemplo con los precios de ahora contra el último cierre. El reporte de verdad sale al cierre, con los cierres de hoy contra los de la rueda anterior.</p>' if en_vivo else "")
        + f'<p style="font-size:13px;color:#71717a;margin:0">Reporte diario de Bonerio Local</p><h2 style="margin:4px 0 18px;font-size:22px">{"Rueda del" if en_vivo else "Cierre del"} {fecha}</h2>'
        '<h3 style="font-size:15px;margin:0 0 4px">Dólar y riesgo país, día contra día</h3>' + tabla_dol
        + curvas_html
        + f'<h3 style="font-size:15px;margin:24px 0 4px">Lo más operado{vol_nota}</h3><p style="margin:0 0 6px;font-size:13px;color:#71717a">Total: $ {n(tot / 1e6, 0)} millones</p><table style="width:100%;border-collapse:collapse;font-size:14px">'
        + "".join(f'<tr><td style="padding:6px 0"><b>{t}</b></td><td style="padding:6px 0;text-align:right">$ {n((a[0] or 0) / 1e6, 0)} M</td><td style="padding:6px 0 6px 12px;text-align:right">{pc(ch(a[1], b[1] if b else None))}</td></tr>' for t, (a, b) in top[:5])
        + "</table>"
        f'<table style="width:100%;border-collapse:collapse;margin-top:22px"><tr><td style="width:50%;vertical-align:top;padding-right:10px"><h3 style="font-size:15px;margin:0 0 4px">Mayores subas{vol_nota}</h3><table style="width:100%;border-collapse:collapse;font-size:14px">'
        + li(mv[::-1][:4]) + f'</table></td><td style="width:50%;vertical-align:top;padding-left:10px"><h3 style="font-size:15px;margin:0 0 4px">Mayores bajas{vol_nota}</h3><table style="width:100%;border-collapse:collapse;font-size:14px">'
        + li(mv[:4]) + "</table></td></tr></table>"
        + ('<h3 style="font-size:15px;margin:22px 0 4px">Lo que viene esta semana</h3><ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.7">'
           + "".join(f"<li><b>{DIA[f.weekday()].capitalize()} {f.day}</b>: {t}</li>" for f, t in ev) + "</ul>" if ev else "")
        + f'<p style="margin:26px 0 8px"><a href="{SITE}" style="background:#18181b;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;font-size:14px">Abrir la terminal</a></p>'
        '<p style="font-size:12px;color:#a1a1aa">Te llega porque te suscribiste al reporte diario. Lo podés dar de baja en la pestaña Alertas.</p></div>'
    )
    asunto = ("[Prueba] " if en_vivo else "") + f"{'Rueda' if en_vivo else 'Cierre'} del {hoy.day} de {MES[hoy.month - 1]}: MEP $ {n(mep)}, riesgo país {n(rp, 0)} pb"
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
    h = {"apikey": KEY}
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
