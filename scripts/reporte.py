"""Reporte diario por mail: al cierre, a los usuarios suscriptos (tabla reporte de Supabase, activo = true), por Resend.

Corre en cierre.yml después de guardar los datos del día. Sale una vez por rueda: la fecha enviada queda en data/reporte_enviado.json
(el cierre corre hasta tres veces) y solo se manda si data/volumen.json ya tiene la rueda de hoy.
Contenido: dólares (oficial, MEP, CCL, brecha y canje), riesgo país, lo más operado, las mayores subas y bajas y lo que viene en la semana.
Secrets: SUPABASE_SERVICE_KEY y RESEND_API_KEY.
"""
import json, os, re, urllib.request, urllib.error, datetime as dt

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


def armar():
    hoy = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date()
    L, P, T = ruedas()
    if L != hoy.isoformat():
        print("todavía no está la rueda de hoy en volumen.json:", L)
        return None, None
    dl = load("dolar.json") or {}
    a3, a3p = last2(dl.get("A3500"))
    dd = (dl.get("d") or {})
    di, dp = dd.get(L) or {}, dd.get(P) or {}
    mep = ((di.get("mep") or {}).get("AL30") or {}).get("close")
    mepp = ((dp.get("mep") or {}).get("AL30") or {}).get("close")
    ccl, cclp = (di.get("ccl") or {}).get("vw"), (dp.get("ccl") or {}).get("vw")
    rp, rpp = last2((load("riesgo_pais.json") or {}).get("d"))
    ch = lambda a, b: (a / b - 1) * 100 if a and b else None
    row = lambda k, v, d: f'<tr><td style="padding:7px 0;color:#52525b">{k}</td><td style="padding:7px 0;text-align:right"><b>{v}</b></td><td style="padding:7px 0 7px 12px;text-align:right">{d}</td></tr>'
    top = sorted(T.items(), key=lambda x: -(x[1][0][0] or 0))
    liq = [x for x in top[:80] if x[1][1] and x[1][1][1] and x[1][0][1]]
    mv = sorted(((t, (a[1] / b[1] - 1) * 100) for t, (a, b) in liq), key=lambda x: x[1])
    tot = sum((a[0] or 0) for a, b in T.values())
    li = lambda xs: "".join(f'<tr><td style="padding:6px 0"><b>{t}</b></td><td style="padding:6px 0;text-align:right">{pc(v)}</td></tr>' for t, v in xs)
    fecha = f"{DIA[hoy.weekday()]} {hoy.day} de {MES[hoy.month - 1]}"
    ev = semana(hoy)
    h = (
        '<div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;padding:24px;color:#18181b">'
        f'<p style="font-size:13px;color:#71717a;margin:0">Reporte diario de Bonerio Local</p><h2 style="margin:4px 0 18px;font-size:22px">Cierre del {fecha}</h2>'
        '<h3 style="font-size:15px;margin:0 0 4px">Dólar y riesgo país</h3><table style="width:100%;border-collapse:collapse;font-size:14px">'
        + row("Oficial (A3500)", "$ " + n(a3), pc(ch(a3, a3p)))
        + row("MEP (AL30)", "$ " + n(mep), pc(ch(mep, mepp)))
        + row("CCL", "$ " + n(ccl), pc(ch(ccl, cclp)))
        + row("Brecha MEP contra oficial", n(ch(mep, a3)) + "%", "")
        + row("Canje (CCL contra MEP)", n(ch(ccl, mep)) + "%", "")
        + row("Riesgo país", n(rp, 0) + " pb", (f'{"+" if rp - rpp > 0 else ""}{n(rp - rpp, 0)} pb' if rp and rpp else ""))
        + "</table>"
        f'<h3 style="font-size:15px;margin:22px 0 4px">Lo más operado</h3><p style="margin:0 0 6px;font-size:13px;color:#71717a">Total de la rueda: $ {n(tot / 1e6, 0)} millones</p><table style="width:100%;border-collapse:collapse;font-size:14px">'
        + "".join(f'<tr><td style="padding:6px 0"><b>{t}</b></td><td style="padding:6px 0;text-align:right">$ {n((a[0] or 0) / 1e6, 0)} M</td><td style="padding:6px 0 6px 12px;text-align:right">{pc(ch(a[1], b[1] if b else None))}</td></tr>' for t, (a, b) in top[:5])
        + "</table>"
        '<table style="width:100%;border-collapse:collapse;margin-top:22px"><tr><td style="width:50%;vertical-align:top;padding-right:10px"><h3 style="font-size:15px;margin:0 0 4px">Mayores subas</h3><table style="width:100%;border-collapse:collapse;font-size:14px">'
        + li(mv[::-1][:4]) + '</table></td><td style="width:50%;vertical-align:top;padding-left:10px"><h3 style="font-size:15px;margin:0 0 4px">Mayores bajas</h3><table style="width:100%;border-collapse:collapse;font-size:14px">'
        + li(mv[:4]) + "</table></td></tr></table>"
        + ('<h3 style="font-size:15px;margin:22px 0 4px">Lo que viene esta semana</h3><ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.7">'
           + "".join(f"<li><b>{DIA[f.weekday()].capitalize()} {f.day}</b>: {t}</li>" for f, t in ev) + "</ul>" if ev else "")
        + f'<p style="margin:26px 0 8px"><a href="{SITE}" style="background:#18181b;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;font-size:14px">Abrir la terminal</a></p>'
        f'<p style="font-size:12px;color:#a1a1aa">Te llega porque te suscribiste al reporte diario. Lo podés dar de baja en la pestaña Alertas.</p></div>'
    )
    return f"Cierre del {hoy.day} de {MES[hoy.month - 1]}: MEP $ {n(mep)}, riesgo país {n(rp, 0)} pb", h


def main():
    hoy = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date().isoformat()
    if (load("reporte_enviado.json") or {}).get("f") == hoy:
        print("el reporte de hoy ya salió")
        return
    if not KEY or not RESEND:
        print("faltan SUPABASE_SERVICE_KEY o RESEND_API_KEY")
        return
    asunto, html = armar()
    if not html:
        return
    h = {"apikey": KEY}
    if KEY.startswith("eyJ"):
        h["Authorization"] = "Bearer " + KEY
    try:
        subs = http(SB + "/rest/v1/reporte?activo=eq.true&select=email", headers=h) or []
    except Exception as e:
        print("supabase", e)
        return
    mails = sorted({s["email"] for s in subs if s.get("email")})
    if not mails:
        print("nadie suscripto")
    for i in range(0, len(mails), 100):
        lote = [{"from": FROM, "to": [m], "subject": asunto, "html": html} for m in mails[i:i + 100]]
        try:
            http("https://api.resend.com/emails/batch", lote, headers={"Authorization": "Bearer " + RESEND})
        except urllib.error.HTTPError as e:
            print("resend", e.code, e.read()[:300])
            return
    with open(os.path.join(D, "reporte_enviado.json"), "w") as f:
        json.dump({"f": hoy, "n": len(mails)}, f)
    print("reporte enviado a", len(mails))


if __name__ == "__main__":
    import sys
    if "--prueba" in sys.argv:  # arma el mail sin mandarlo (para revisarlo): scripts/reporte.py --prueba > /tmp/r.html
        a, h = armar()
        print(h or "sin rueda de hoy")
    else:
        main()
