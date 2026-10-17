#!/usr/bin/env python3
"""Sondeo temporal de fuentes de balances (se borra)."""
import json, urllib.request, time

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "*/*"}

def get(url, h=None, n=600):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h or UA), timeout=40)
        b = r.read()
        return r.status, b
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:n]
    except Exception as e:
        return 0, str(e).encode()[:n]

T = "quarterlyTotalRevenue,quarterlyOperatingIncome,quarterlyReconciledDepreciation,quarterlyNetIncomeCommonStockholders,quarterlyStockholdersEquity,quarterlyTotalDebt,quarterlyCashCashEquivalentsAndShortTermInvestments,quarterlyOrdinarySharesNumber,annualTotalRevenue,annualNetIncomeCommonStockholders,annualStockholdersEquity"
p2 = int(time.time())
for tk in ["GGAL.BA", "ALUA.BA", "YPFD.BA"]:
    for host in ["query1", "query2"]:
        u = "https://%s.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/%s?type=%s&period1=1609459200&period2=%d" % (host, tk, T, p2)
        st, b = get(u)
        print("YAHOO", tk, host, st, len(b))
        if st == 200:
            try:
                res = json.loads(b)["timeseries"]["result"]
                for r in res:
                    typ = r["meta"]["type"][0]
                    vals = [(x["asOfDate"], x["reportedValue"]["raw"], x.get("currencyCode")) for x in (r.get(typ) or []) if x]
                    print("  ", typ, vals[-6:])
            except Exception as e:
                print("  parse", e, b[:300])
            break
        else:
            print("  ", b[:300])

for name, u in [("SEC GGAL", "https://data.sec.gov/api/xbrl/companyfacts/CIK0001114700.json"),
                ("SEC YPF", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000904851.json")]:
    st, b = get(u, {"User-Agent": "Bonerio Local research pipopersi@gmail.com"})
    print(name, st, len(b))
    if st == 200:
        d = json.loads(b); f = d.get("facts", {})
        print("  taxonomias", list(f), "n ifrs", len(f.get("ifrs-full", {})))
        for k in ["Revenue", "ProfitLossAttributableToOwnersOfParent", "EquityAttributableToOwnersOfParent"]:
            x = f.get("ifrs-full", {}).get(k, {}).get("units", {})
            for cur, rows in x.items():
                print("  ", k, cur, [(r.get("end"), r.get("val"), r.get("form"), r.get("fp")) for r in rows[-6:]])

for name, u in [("CNV aif2", "https://aif2.cnv.gov.ar/"), ("CNV www", "https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30500001735"),
                ("BYMA balances", "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/bnown/fichatecnica/especies/balances"),
                ("Screener", "https://www.screenermatic.com/"), ("MarketScreener", "https://www.marketscreener.com/")]:
    st, b = get(u)
    print(name, st, len(b), b[:200])
