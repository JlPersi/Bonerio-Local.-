#!/usr/bin/env python3
"""Sondeo de la API de Matriz/Primary (futuros): solo lectura. Guarda en data/_probe_rofex.json la forma real
de las respuestas (lista de contratos, market data con volumen y open interest, trades históricos) para armar la pestaña.
Credenciales: variables de entorno ROFEX_USER, ROFEX_PASS (secrets de GitHub). Nunca se imprimen ni se guardan."""
import json, os, sys, urllib.request, urllib.error, urllib.parse, datetime as dt

BASE = os.environ.get("ROFEX_URL", "https://api.bull.xoms.com.ar").rstrip("/")  # confirmar con el broker
USER, PASS = os.environ.get("ROFEX_USER", ""), os.environ.get("ROFEX_PASS", "")
OUT = {"base": BASE, "when": dt.datetime.utcnow().isoformat() + "Z", "steps": {}}

def call(path, headers=None, method="GET", timeout=30):
    req = urllib.request.Request(BASE + path, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            try: body = json.loads(body)
            except Exception: pass
            return r.status, dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, {}, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, {}, str(e)[:300]

def main():
    if not USER or not PASS:
        print("Faltan los secrets ROFEX_USER / ROFEX_PASS"); OUT["error"] = "sin credenciales"; save(); return 1
    st, hd, body = call("/auth/getToken", {"X-Username": USER, "X-Password": PASS}, "POST")
    tok = hd.get("X-Auth-Token") or hd.get("x-auth-token")
    OUT["steps"]["token"] = {"status": st, "ok": bool(tok)}
    if not tok:
        OUT["steps"]["token"]["body"] = body if isinstance(body, str) else str(body)[:300]
        print("No se obtuvo token (estado %s)" % st); save(); return 1
    H = {"X-Auth-Token": tok}
    st, _, ins = call("/rest/instruments/detailed", H)
    OUT["steps"]["instruments_status"] = st
    items = (ins.get("instruments") if isinstance(ins, dict) else None) or []
    OUT["steps"]["instruments_count"] = len(items)
    dlr = [i for i in items if "DLR" in json.dumps(i)][:60]
    OUT["steps"]["instruments_dlr_sample"] = dlr[:4]
    OUT["steps"]["instruments_dlr_count"] = len(dlr)
    syms = []
    for i in dlr:
        s = (i.get("instrumentId") or {}).get("symbol")
        if s and s.startswith("DLR/") and s not in syms: syms.append(s)
    OUT["steps"]["dlr_symbols"] = syms
    ents = "BI,OF,LA,OP,CL,SE,OI,TV,HI,LO,NV,EV,IV,ACP"
    md = {}
    for s in syms[:12]:
        q = urllib.parse.urlencode({"marketId": "ROFX", "symbol": s, "entries": ents, "depth": 1})
        md[s] = call("/rest/marketdata/get?" + q, H)[2]
    OUT["steps"]["marketdata"] = md
    if syms:
        d1 = dt.date.today(); d0 = d1 - dt.timedelta(days=10)
        q = urllib.parse.urlencode({"marketId": "ROFX", "symbol": syms[0], "dateFrom": d0.isoformat(), "dateTo": d1.isoformat()})
        st, _, tr = call("/rest/data/getTrades?" + q, H)
        OUT["steps"]["trades_status"] = st
        OUT["steps"]["trades_sample"] = (tr.get("trades")[:5] if isinstance(tr, dict) and tr.get("trades") else tr if isinstance(tr, str) else tr)
    # cauciones y otros tipos
    OUT["steps"]["types_in_list"] = sorted({(i.get("cficode") or "")[:2] for i in items if isinstance(i, dict)})[:30]
    save(); print("Listo: data/_probe_rofex.json"); return 0

def save():
    os.makedirs("data", exist_ok=True)
    with open("data/_probe_rofex.json", "w") as f: json.dump(OUT, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    sys.exit(main())
