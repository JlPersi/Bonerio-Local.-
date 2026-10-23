#!/usr/bin/env python3
"""Histórico de acciones que data912 no tiene (ECOG), con yfinance (Yahoo, ticker <T>.BA), en data/acciones/<T>.json.
Mismo formato que save_acciones.py: [fecha, apertura, máximo, mínimo, cierre, volumen]. Conserva las ruedas
que Yahoo todavía no trae. TICKERS=ECOG,OTRO (por defecto ECOG)."""
import os, json, importlib.util
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
sp = importlib.util.spec_from_file_location("sa", os.path.join(HERE, "save_acciones.py"))
sa = importlib.util.module_from_spec(sp); sp.loader.exec_module(sa)

for t in [x.strip().upper() for x in (os.environ.get("TICKERS") or "ECOG").split(",") if x.strip()]:
    df = yf.download(t + ".BA", period="max", interval="1d", auto_adjust=False, progress=False)
    if df is None or df.empty:
        print(t, "Yahoo no trae datos"); continue
    if hasattr(df.columns, "levels"):  # columnas (campo, ticker) en las versiones nuevas
        df.columns = [c[0] for c in df.columns]
    rows = []
    for d, r in df.iterrows():
        c = float(r["Close"])
        if not c == c or c <= 0:
            continue
        f = lambda k: round(float(r[k]), 4) if r[k] == r[k] and float(r[k]) > 0 else None
        rows.append([d.date().isoformat(), f("Open"), f("High"), f("Low"), round(c, 4), float(r["Volume"]) if r["Volume"] == r["Volume"] else 0.0])
    old = sa.load(t)
    if old:
        have = {x[0] for x in rows}
        rows += [x for x in old.get("r", []) if x[0] not in have]
        rows.sort(key=lambda x: x[0])
    sa.save(t, rows)
    print(t, len(rows), "ruedas,", rows[0][0], "a", rows[-1][0])
sa.write_index()
