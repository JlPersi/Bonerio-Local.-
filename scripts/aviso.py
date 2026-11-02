"""Aviso por mail a todos los usuarios registrados (Supabase Auth), por Resend. Se corre a mano desde Actions ("Aviso a usuarios").
   modo=prueba: solo a la dirección de prueba. modo=todos: a todos los registrados (de a 100 por pedido, con el envío en lote de Resend).
   El texto sale de scripts/aviso.html (la primera línea <!-- asunto: ... --> es el asunto). No sale a todos si el texto tiene COMPLETAR.
   Secrets: SUPABASE_SERVICE_KEY y RESEND_API_KEY (los mismos del reporte diario)."""
import json, os, re, sys, time, urllib.request, urllib.error

SB = "https://sbvebxqeltvkerrarzqn.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
RESEND = os.environ.get("RESEND_API_KEY", "").strip()
FROM = "Bonerio Local <hola@boneriolocal.com.ar>"


def http(url, data=None, headers=None):
    h = {"User-Agent": "bonerio-aviso/1.0"}
    h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        h["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=60) as r:
        t = r.read()
        return json.loads(t) if t else None


def usuarios():
    h = {"apikey": KEY}
    if KEY.startswith("eyJ"):
        h["Authorization"] = "Bearer " + KEY
    out, page = set(), 1
    while True:
        j = http(f"{SB}/auth/v1/admin/users?page={page}&per_page=1000", headers=h) or {}
        us = j.get("users", []) if isinstance(j, dict) else j
        for u in us:
            if u.get("email") and u.get("email_confirmed_at") is not None:
                out.add(u["email"].strip().lower())
        if len(us) < 1000:
            return sorted(out)
        page += 1


def main():
    modo, prueba = (sys.argv[1] if len(sys.argv) > 1 else "prueba"), (sys.argv[2] if len(sys.argv) > 2 else "")
    html = open(os.path.join(os.path.dirname(__file__), "aviso.html"), encoding="utf-8").read()
    m = re.match(r"\s*<!--\s*asunto:\s*(.+?)\s*-->", html)
    asunto = m.group(1) if m else "Novedades de Bonerío Local"
    if not RESEND or (modo == "todos" and not KEY):
        sys.exit("faltan SUPABASE_SERVICE_KEY o RESEND_API_KEY")
    if modo == "todos":
        if "COMPLETAR" in html:
            sys.exit("el texto todavía tiene COMPLETAR: no sale a todos")
        mails = usuarios()
    else:
        if not prueba:
            sys.exit("falta la dirección de prueba")
        mails, asunto = [prueba], "[Prueba] " + asunto
    print(len(mails), "destinatarios")
    ok = 0
    for i in range(0, len(mails), 100):  # el envío en lote de Resend: hasta 100 mails por pedido, cada uno con su propio destinatario
        lote = [{"from": FROM, "to": [x], "subject": asunto, "html": html} for x in mails[i:i + 100]]
        try:
            http("https://api.resend.com/emails/batch", lote, headers={"Authorization": "Bearer " + RESEND})
            ok += len(lote)
        except urllib.error.HTTPError as e:
            print("resend", e.code, e.read()[:300])
            break
        time.sleep(1)
    print("enviados", ok, "de", len(mails))


if __name__ == "__main__":
    main()
