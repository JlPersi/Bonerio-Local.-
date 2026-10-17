#!/usr/bin/env python3
"""Sondeo temporal de fuentes de balances (se borra)."""
import json, re, urllib.request, collections

SEC = {"User-Agent": "Bonerio Local research pipopersi@gmail.com"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

def get(url, h, n=400):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:n]
    except Exception as e:
        return 0, str(e).encode()[:n]

st, b = get("https://www.sec.gov/files/company_tickers.json", SEC)
tick = {v["ticker"]: v["cik_str"] for v in json.loads(b).values()} if st == 200 else {}
ADR = {"BBAR": "BBAR", "BMA": "BMA", "CEPU": "CEPU", "CRES": "CRESY", "EDN": "EDN", "GGAL": "GGAL", "IRSA": "IRS",
       "LOMA": "LOMA", "PAMP": "PAM", "SUPV": "SUPV", "TECO2": "TEO", "TGSU2": "TGS", "YPFD": "YPF"}
KEYS = ["Revenue", "ProfitLossFromOperatingActivities", "DepreciationAndAmortisationExpense", "ProfitLoss",
        "ProfitLossAttributableToOwnersOfParent", "Equity", "EquityAttributableToOwnersOfParent", "CashAndCashEquivalents",
        "Borrowings", "CurrentBorrowings", "NoncurrentBorrowings", "NumberOfSharesOutstanding"]
for t, a in ADR.items():
    cik = tick.get(a)
    print("==", t, a, "cik", cik)
    if not cik:
        continue
    st, b = get("https://data.sec.gov/api/xbrl/companyfacts/CIK%010d.json" % cik, SEC)
    if st != 200:
        print("  err", st); continue
    f = json.loads(b)["facts"]
    ifrs = f.get("ifrs-full", {})
    for k in KEYS:
        u = ifrs.get(k, {}).get("units", {})
        for cur, rows in u.items():
            rows = [r for r in rows if r.get("end", "") >= "2023-01-01"]
            per = sorted({(r["end"], r.get("start", "")[:7], r["form"]) for r in rows})
            print("  %-42s %s n=%d %s" % (k, cur, len(per), [(e, s, fm) for e, s, fm in per][-8:]))
    # conceptos que contienen depreciación / préstamos con otro nombre
    alt = [k for k in ifrs if re.search(r"Depreciation|Borrowing|Loans|Revenue", k)]
    print("  alt:", alt[:25])

st, b = get("https://aif2.cnv.gov.ar/", UA)
html = b.decode("utf8", "replace")
print("CNV links", sorted(set(re.findall(r'(?:href|src|action)="([^"]+)"', html)))[:80])
print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:1500])
