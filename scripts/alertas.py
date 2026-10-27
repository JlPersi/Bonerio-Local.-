"""Alertas de los usuarios: revisa las activas de Supabase contra los precios en vivo y avisa por mail (Resend) o notificación (web push).

Corre dentro del loop de tasas.yml durante la rueda, cada pocos minutos. Cada alerta salta una sola vez: queda pausada (activa = false)
con la hora en disparada_en, y el usuario la reactiva desde la pestaña Alertas.

Métricas (columna metrica):
  precio    precio de una especie (bono, letra, ON o acción) de data912
  var       variación del día (%) de una especie
  mep, ccl  dólar MEP (AL30/AL30D) y CCL (AL30/AL30C)
  canje     CCL / MEP - 1 (%)
  brecha    MEP / A3500 - 1 (%)
  ratio     precio de ticker / precio de ticker2
  riesgo    riesgo país en puntos básicos (data/riesgo_vivo.json)

Secrets: SUPABASE_SERVICE_KEY (lee las alertas de todos), RESEND_API_KEY, VAPID_PRIVATE_KEY. Sin alguno, ese canal no se usa.
"""
import json, os, urllib.request, urllib.error, urllib.parse, datetime as dt

SB = "https://sbvebxqeltvkerrarzqn.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
RESEND = os.environ.get("RESEND_API_KEY", "").strip()
VAPID = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
FROM = "Bonerio Local <hola@boneriolocal.com.ar>"
SITE = "https://boneriolocal.com.ar"
NOMBRE = {"precio": "Precio", "var": "Variación del día", "mep": "Dólar MEP", "ccl": "Dólar CCL", "canje": "Canje", "brecha": "Brecha MEP vs. oficial", "ratio": "Ratio", "riesgo": "Riesgo país"}
PCT = {"var", "canje", "brecha"}


def http(url, data=None, method=None, headers=None, timeout=30):
    h = {"User-Agent": "Mozilla/5.0"}
    h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        t = r.read()
        return json.loads(t) if t else None


def sb(path, data=None, method=None):
    h = {"apikey": KEY, "Prefer": "return=minimal"}
    if KEY.startswith("eyJ"):  # la service_role vieja es un JWT; la secret nueva (sb_secret_) va solo en apikey
        h["Authorization"] = "Bearer " + KEY
    return http(SB + "/rest/v1/" + path, data, method, h)


def precios():
    P = {}
    for ep in ("arg_bonds", "arg_notes", "arg_corp", "arg_stocks"):
        try:
            for r in http("https://data912.com/live/" + ep) or []:
                s, c = r.get("symbol"), r.get("c")
                if s and c and c > 0:
                    P[s] = {"c": float(c), "pct": r.get("pct_change")}
        except Exception as e:
            print("data912", ep, e)
    return P


def oficial():
    try:
        a = json.load(open("data/dolar.json")).get("A3500") or {}
        return a[max(a)] if a else None
    except Exception:
        return None


def riesgo():
    try:
        return float(json.load(open("data/riesgo_vivo.json"))["v"])
    except Exception:
        return None


def valor(a, P, ofi, rp):
    c = lambda s: (P.get((s or "").upper()) or {}).get("c")
    al, ald, alc = c("AL30"), c("AL30D"), c("AL30C")
    mep = al / ald if al and ald else None
    ccl = al / alc if al and alc else None
    m = a["metrica"]
    if m == "precio":
        return c(a.get("ticker"))
    if m == "var":
        v = (P.get((a.get("ticker") or "").upper()) or {}).get("pct")
        return float(v) if v is not None else None
    if m == "mep":
        return mep
    if m == "ccl":
        return ccl
    if m == "canje":
        return (ccl / mep - 1) * 100 if mep and ccl else None
    if m == "brecha":
        return (mep / ofi - 1) * 100 if mep and ofi else None
    if m == "ratio":
        x, y = c(a.get("ticker")), c(a.get("ticker2"))
        return x / y if x and y else None
    if m == "riesgo":
        return rp
    return None


def fmt(v, m):
    if v is None:
        return "—"
    d = 2 if m in PCT or m in ("mep", "ccl", "precio") else 4 if m == "ratio" else 0
    s = f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + ("%" if m in PCT else " pb" if m == "riesgo" else "")


def titulo(a):
    t = NOMBRE.get(a["metrica"], a["metrica"])
    if a["metrica"] in ("precio", "var") and a.get("ticker"):
        t += " de " + a["ticker"].upper()
    if a["metrica"] == "ratio":
        t += " " + (a.get("ticker") or "").upper() + "/" + (a.get("ticker2") or "").upper()
    return t


def mail(a, v):
    if not RESEND or not a.get("email"):
        return False
    t, cond = titulo(a), ("superó" if a["op"] == ">" else "bajó de")
    html = (
        '<div style="font-family:Inter,Arial,sans-serif;max-width:520px;margin:auto;padding:24px;color:#18181b">'
        '<p style="font-size:13px;color:#71717a;margin:0 0 6px">Alerta de Bonerio Local</p>'
        f'<h2 style="margin:0 0 14px;font-size:20px">{t} {cond} {fmt(a["valor"], a["metrica"])}</h2>'
        f'<p style="font-size:15px;margin:0 0 6px">Valor ahora: <b>{fmt(v, a["metrica"])}</b></p>'
        + (f'<p style="font-size:14px;color:#52525b;margin:0 0 6px">Tu nota: {a["nota"]}</p>' if a.get("nota") else "")
        + f'<p style="margin:22px 0"><a href="{SITE}/#alert" style="background:#18181b;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;font-size:14px">Ver mis alertas</a></p>'
        '<p style="font-size:12px;color:#a1a1aa">La alerta quedó pausada. La podés reactivar desde la pestaña Alertas.</p></div>'
    )
    try:
        http("https://api.resend.com/emails", {"from": FROM, "to": [a["email"]], "subject": f"{t}: {fmt(v, a['metrica'])}", "html": html},
             headers={"Authorization": "Bearer " + RESEND})
        return True
    except urllib.error.HTTPError as e:
        print("resend", e.code, e.read()[:300])
    except Exception as e:
        print("resend", e)
    return False


def push(a, v, subs):
    if not VAPID or not subs:
        return False
    try:
        from pywebpush import webpush, WebPushException
    except Exception as e:
        print("pywebpush", e)
        return False
    msg = json.dumps({"title": titulo(a) + ": " + fmt(v, a["metrica"]),
                      "body": ("Superó " if a["op"] == ">" else "Bajó de ") + fmt(a["valor"], a["metrica"]) + (". " + a["nota"] if a.get("nota") else ""),
                      "url": "/#alert", "tag": "alerta-" + str(a["id"])})
    ok = False
    for s in subs:
        try:
            webpush(subscription_info=s["sub"], data=msg, vapid_private_key=VAPID, vapid_claims={"sub": "mailto:hola@boneriolocal.com.ar"}, ttl=3600)
            ok = True
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            print("push", code)
            if code in (404, 410):  # la suscripción ya no existe (desinstaló o borró los permisos)
                try:
                    sb("push_subs?endpoint=eq." + urllib.parse.quote(s["endpoint"], safe=""), method="DELETE")
                except Exception:
                    pass
        except Exception as e:
            print("push", e)
    return ok


def main():
    if not KEY:
        print("sin SUPABASE_SERVICE_KEY")
        return
    try:
        AL = sb("alertas?activa=eq.true&select=*") or []
    except Exception as e:
        print("supabase", e)
        return
    if not AL:
        print("sin alertas activas")
        return
    P, ofi, rp = precios(), oficial(), riesgo()
    SUBS = {}
    if VAPID:
        try:
            for s in sb("push_subs?select=endpoint,user_id,sub") or []:
                SUBS.setdefault(s["user_id"], []).append(s)
        except Exception as e:
            print("push_subs", e)
    n = 0
    for a in AL:
        v = valor(a, P, ofi, rp)
        if v is None or a.get("valor") is None:
            continue
        if not ((a["op"] == ">" and v > a["valor"]) or (a["op"] == "<" and v < a["valor"])):
            continue
        canal = a.get("canal") or "ambos"
        sent = False
        if canal in ("push", "ambos"):
            sent = push(a, v, SUBS.get(a["user_id"])) or sent
        if canal in ("mail", "ambos") or not sent:  # si no tiene notificaciones activas, le llega igual por mail
            sent = mail(a, v) or sent
        if sent:
            sb("alertas?id=eq." + a["id"], {"activa": False, "disparada_en": dt.datetime.now(dt.timezone.utc).isoformat()}, "PATCH")
            n += 1
    print(f"{len(AL)} alertas activas, {n} disparadas")


if __name__ == "__main__":
    main()
