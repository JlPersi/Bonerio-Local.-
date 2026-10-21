"""Prueba (solo en esta rama): hasta dónde llega el histórico de operaciones de Primary. No imprime credenciales."""
import os, json, urllib.request, urllib.parse
U = os.environ["ROFEX_URL"].rstrip("/")
def req(path, hdr, data=None):
    r = urllib.request.Request(U + path, data=data, headers=hdr, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(r, timeout=60) as x: return x.headers, x.read()
try:
    h, _ = req("/auth/getToken", {"X-Username": os.environ["ROFEX_USER"], "X-Password": os.environ["ROFEX_PASS"]}, b"")
    T = h["X-Auth-Token"]
except Exception as e:
    print("login falló:", type(e).__name__); raise SystemExit(0)
SYMS = ["DLR/NOV26", "DLR/DIC24", "MERV - XMEV - AL30 - 24hs", "MERV - XMEV - S31L8 - 48hs", "MERV - XMEV - S31L8 - CI", "MERV - XMEV - S30N8 - 48hs", "MERV - XMEV - S28F9 - 48hs",
        "MERV - XMEV - S31O4 - 24hs", "MERV - XMEV - S31O4 - CI", "MERV - XMEV - S30J5 - 24hs", "MERV - XMEV - S31O6 - 24hs",
        "MERV - XMEV - PESOS - 1D", "MERV - XMEV - PESOS - 1D - 24hs"]
RANGES = [("2018-07-01", "2018-07-31"), ("2023-01-02", "2023-01-31"), ("2024-10-01", "2024-10-31"), ("2025-07-01", "2025-07-10"), ("2026-10-01", "2026-10-20")]
for s in SYMS:
    for a, b in RANGES:
        q = urllib.parse.urlencode({"marketId": "ROFX", "symbol": s, "dateFrom": a, "dateTo": b, "external": "1"})
        try:
            _, body = req("/rest/data/getTrades?" + q, {"X-Auth-Token": T})
            j = json.loads(body); tr = j.get("trades") or []
            ds = sorted({str(t.get("datetime", ""))[:10] for t in tr})
            ex = tr[0] if tr else {}
            print(s, a, "status", j.get("status"), str(j.get("description") or j.get("message") or "")[:120], "trades", len(tr), "dias", len(ds), ds[:1], ds[-1:], "campos", sorted(ex.keys())[:8])
        except Exception as e:
            print(s, a, "error", type(e).__name__, getattr(e, "code", ""))
