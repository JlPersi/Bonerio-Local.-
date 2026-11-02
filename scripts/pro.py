"""Alta PRO: marca a un usuario (por mail) como PRO hasta una fecha, en app_metadata.pro_hasta de Supabase Auth.
   Se corre a mano desde Actions («Alta PRO»): mail y meses (1, 6 o 12; 0 = quitar PRO). Si ya era PRO, suma desde su vencimiento.
   Secret: SUPABASE_SERVICE_KEY."""
import datetime as dt, json, os, sys, urllib.request

SB = "https://sbvebxqeltvkerrarzqn.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
H = {"apikey": KEY, "User-Agent": "bonerio-pro/1.0", "Content-Type": "application/json"}
if KEY.startswith("eyJ"):
    H["Authorization"] = "Bearer " + KEY


def http(url, data=None, method=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=H, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read()
        return json.loads(t) if t else None


def buscar(mail):
    page = 1
    while True:
        j = http(f"{SB}/auth/v1/admin/users?page={page}&per_page=1000") or {}
        us = j.get("users", []) if isinstance(j, dict) else j
        for u in us:
            if (u.get("email") or "").strip().lower() == mail:
                return u
        if len(us) < 1000:
            return None
        page += 1


def sumar_meses(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    dias = [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return dt.date(y, m, min(d.day, dias))


def main():
    mail, meses = sys.argv[1].strip().lower(), int(sys.argv[2] or 1)
    if not KEY:
        sys.exit("Falta SUPABASE_SERVICE_KEY")
    u = buscar(mail)
    if not u:
        sys.exit(f"No hay ningún usuario con el mail {mail} (tiene que registrarse primero en la página).")
    hoy = (dt.datetime.utcnow() - dt.timedelta(hours=3)).date()
    am = u.get("app_metadata") or {}
    if meses <= 0:
        hasta = None
    else:
        try:
            base = max(hoy, dt.date.fromisoformat(str(am.get("pro_hasta"))[:10]))
        except ValueError:
            base = hoy
        hasta = sumar_meses(base, meses).isoformat()
    http(f"{SB}/auth/v1/admin/users/{u['id']}", {"app_metadata": {"pro_hasta": hasta}}, "PUT")
    print(f"{mail}: " + (f"PRO hasta el {hasta}" if hasta else "PRO quitado"))


if __name__ == "__main__":
    main()
