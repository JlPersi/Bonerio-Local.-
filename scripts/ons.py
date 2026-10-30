"""Arma data/ons.json para la sección de Obligaciones negociables.

Entrada: data/ons_flujos.xlsx (flujos de fondos por 100 VN de cada ON, hoja «Cashflow de Bonos»)
y, opcional, la foto de cierres (data/ons_cierre.json, que arma el Action). Salida por ON (código sin la letra de especie):
tipo, emisión, vencimiento, tasa, residual y los flujos que faltan cobrar.
"""
import json, os, datetime
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "data", "ons_flujos.xlsx")
OUT = os.path.join(HERE, "..", "data", "ons.json")
TP = {"ON": "usd", "ON_DOLLAR_LINKED": "dl", "ON_TAMAR": "tamar", "ON_BADLAR": "badlar", "ON_CER": "cer", "ON_FIXED_RATE": "fija"}


def main():
    hoy = datetime.date.today().isoformat()
    wb = openpyxl.load_workbook(SRC, read_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    head = [str(h) for h in rows[0]]
    ix = {h: i for i, h in enumerate(head)}
    by = {}
    for r in rows[1:]:
        t = r[ix["ticker"]]
        if not t:
            continue
        by.setdefault(t, []).append(r)
    out = {}
    for t, rs in by.items():
        rs.sort(key=lambda r: r[ix["payment_date"]])
        mat = rs[-1][ix["payment_date"]]
        if mat < hoy:
            continue  # ya venció
        f = lambda r, c: float(r[ix[c]] or 0)
        fut = [r for r in rs if r[ix["payment_date"]] > hoy]
        past = [r for r in rs if r[ix["payment_date"]] <= hoy]
        res = f(past[-1], "residual_value") if past else 100.0
        base = t[:-1]
        out[base] = {
            "t": TP.get(rs[0][ix["type"]], "otro"),
            "o": t,
            "iss": rs[0][ix["issue_date"]],
            "mat": mat,
            "r": round(f(fut[0], "interest_rate") * 100, 4) if fut else None,
            "res": round(res, 4),
            "lc": past[-1][ix["payment_date"]] if past else rs[0][ix["issue_date"]],
            "b": int(rs[0][ix["days_convention"]] or 365),
            "fl": [[r[ix["payment_date"]], round(f(r, "cash_flow"), 6), round(f(r, "interest_amount"), 6)] for r in fut],
            "fp": [[r[ix["payment_date"]], round(f(r, "cash_flow"), 6), round(f(r, "interest_amount"), 6)] for r in past],
        }
    json.dump({"hoy": hoy, "on": out}, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    print(len(out), "ONs vigentes")


if __name__ == "__main__":
    main()
