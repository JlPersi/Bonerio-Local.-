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
  oficial   dólar oficial (A3500 o mayorista del día)
  brechaccl CCL / A3500 - 1 (%)
  tir, tna  TIR o TNA (%) de un bono; paridad (%) y duration (años) de un bono en dólares (scripts/metricas.py)
  spread    TIR de ticker menos TIR de ticker2, en puntos básicos
  futuro    precio de un futuro de dólar (ticker: DLR/NOV26, NOV26, o 1 y 2 para el primero y el segundo)
  implicita tasa implícita (TNA %) de ese futuro contra el oficial
  caucion   TNA (%) de la caución en pesos al plazo en días que diga ticker (1 si no dice)
  volumen   nominales operados hoy de una especie
MEP, CCL y canje usan el bono de ticker si lo trae (AL30 si no).

Secrets: SUPABASE_SERVICE_KEY (lee las alertas de todos), RESEND_API_KEY, VAPID_PRIVATE_KEY. Sin alguno, ese canal no se usa.
"""
import json, os, sys, urllib.request, urllib.error, urllib.parse, datetime as dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metricas as MT

SB = "https://sbvebxqeltvkerrarzqn.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
RESEND = os.environ.get("RESEND_API_KEY", "").strip()
VAPID = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
FROM = "Bonerio Local <hola@boneriolocal.com.ar>"
SITE = "https://boneriolocal.com.ar"
NOMBRE = {"precio": "Precio", "var": "Variación del día", "mep": "Dólar MEP", "ccl": "Dólar CCL", "canje": "Canje", "brecha": "Brecha MEP vs. oficial", "ratio": "Ratio", "riesgo": "Riesgo país",
          "oficial": "Dólar oficial", "brechaccl": "Brecha CCL vs. oficial", "tir": "TIR", "tna": "TNA", "paridad": "Paridad", "dur": "Duration", "spread": "Spread de TIR",
          "futuro": "Futuro", "implicita": "Tasa implícita del futuro", "caucion": "Caución", "volumen": "Volumen"}
PCT = {"var", "canje", "brecha", "brechaccl", "tir", "tna", "paridad", "implicita", "caucion"}
CON_TK = {"precio", "var", "ratio", "tir", "tna", "paridad", "dur", "spread", "volumen"}


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
    h = {"apikey": KEY, "Prefer": "return=minimal", "User-Agent": "bonerio-alertas/1.0"}  # Supabase rechaza la clave secret (401) si el User-Agent parece de un navegador
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
                    P[s] = {"c": float(c), "pct": r.get("pct_change"), "v": r.get("v")}
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


def valor(a, P, ofi, rp, B=None, F=None, CAU=None):
    c = lambda s: (P.get((s or "").upper()) or {}).get("c")
    m, tk = a["metrica"], (a.get("ticker") or "").strip().upper()
    bono = tk if m in ("mep", "ccl", "canje") and tk else "AL30"
    al, ald, alc = c(bono), c(bono + "D"), c(bono + "C")
    mep = al / ald if al and ald else None
    ccl = al / alc if al and alc else None
    if m == "precio":
        return c(tk)
    if m == "var":
        v = (P.get(tk) or {}).get("pct")
        return float(v) if v is not None else None
    if m == "volumen":
        v = (P.get(tk) or {}).get("v")
        return float(v) if v is not None else None
    if m == "mep":
        return mep
    if m == "ccl":
        return ccl
    if m == "canje":
        return (ccl / mep - 1) * 100 if mep and ccl else None
    if m == "brecha":
        return (mep / ofi - 1) * 100 if mep and ofi else None
    if m == "brechaccl":
        return (ccl / ofi - 1) * 100 if ccl and ofi else None
    if m == "oficial":
        return ofi
    if m == "ratio":
        x, y = c(tk), c(a.get("ticker2"))
        return x / y if x and y else None
    if m == "riesgo":
        return rp
    if m in ("tir", "tna", "paridad", "dur", "spread") and B:
        def met(t, n):
            sp = B.busca(t)[2]
            x = B.calc(sp, c(sp)).get(n) if sp else None
            return x
        if m == "spread":
            x, y = met(tk, "tir"), met(a.get("ticker2"), "tir")
            return (x - y) * 1e4 if x is not None and y is not None else None
        x = met(tk, {"paridad": "par"}.get(m, m))
        return None if x is None else x if m in ("paridad", "dur") else x * 100
    if m in ("futuro", "implicita") and F is not None:
        k = MT.futuro(F, tk)
        return None if not k else F[k]["p"] if m == "futuro" else F[k]["tna"]
    if m == "caucion" and CAU is not None:
        return CAU.get(int(tk) if tk.isdigit() else 1)
    return None


def fmt(v, m):
    if v is None:
        return "—"
    d = 2 if m in PCT or m in ("mep", "ccl", "precio", "oficial", "futuro", "dur") else 4 if m == "ratio" else 0
    s = f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + ("%" if m in PCT else " pb" if m in ("riesgo", "spread") else " años" if m == "dur" else "")


def titulo(a):
    t = NOMBRE.get(a["metrica"], a["metrica"])
    m, tk = a["metrica"], (a.get("ticker") or "").upper()
    if m in ("ratio", "spread"):
        t += " " + tk + (" / " if m == "spread" else "/") + (a.get("ticker2") or "").upper()
    elif m in CON_TK and tk:
        t += " de " + tk
    elif m in ("futuro", "implicita"):
        t += " " + (tk if not tk.isdigit() else ("1.er" if tk == "1" else "2.º") + " contrato") if tk else " 1.er contrato"
    elif m == "caucion":
        t += " a " + (tk or "1") + " día" + ("" if (tk or "1") == "1" else "s")
    elif m in ("mep", "ccl", "canje") and tk:
        t += " (" + tk + ")"
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
    P, B = None, None
    try:  # la foto de TIR, futuros y caución para la pestaña: va siempre, haya alertas o no
        P, B = precios(), MT.Bonos()
        if P:
            MT.foto(P, B)
    except Exception as e:
        print("metricas", e)
    if not KEY:
        print("sin SUPABASE_SERVICE_KEY")
        return
    try:
        AL = sb("alertas?activa=eq.true&select=*") or []
    except Exception as e:
        print("supabase", e, "| clave:", "sb_secret" if KEY.startswith("sb_secret_") else "JWT service_role/anon" if KEY.startswith("eyJ") else "sb_publishable (no sirve)" if KEY.startswith("sb_publishable_") else "formato desconocido", len(KEY), "caracteres")  # para ver qué se cargó sin mostrarla
        return
    if not AL:
        print("sin alertas activas")
        return
    P, ofi, rp = P or precios(), MT.oficial() or oficial(), riesgo()
    F, CAU = MT.futuros(), MT.caucion()
    SUBS = {}
    if VAPID:
        try:
            for s in sb("push_subs?select=endpoint,user_id,sub") or []:
                SUBS.setdefault(s["user_id"], []).append(s)
        except Exception as e:
            print("push_subs", e)
    n = 0
    for a in AL:
        v = valor(a, P, ofi, rp, B, F, CAU)
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
