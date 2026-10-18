import json, os, re, urllib.request, urllib.parse
OUT = "probe/out2"; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
def get(url, data=None, h=None, t=40):
    r = urllib.request.Request(url, data=data, headers=dict(H, **(h or {})))
    with urllib.request.urlopen(r, timeout=t) as f:
        return f.status, f.read()
log = []
def crawl(base, tag):
    try:
        st, b = get(base); html = b.decode("utf8", "ignore"); log.append("%s %s %d" % (base, st, len(b)))
        js = set(re.findall(r'(?:src|href)="([^"]+\.js[^"]*)"', html))
        paths = set()
        for src in js:
            u = urllib.parse.urljoin(base, src)
            try:
                st, bb = get(u); t = bb.decode("utf8", "ignore")
                paths |= set(re.findall(r'["\'`](/?(?:api|rest|vanoms|free)[^"\'`\s]{2,160})["\'`]', t))
                paths |= set(re.findall(r'https?://[a-zA-Z0-9.-]+(?:/[^"\'`\s]{0,160})?', t))
                for kw in ["imult", "pase", "Pase", "repo", "cauci"]:
                    for m in list(re.finditer(kw, t))[:15]:
                        paths.add("CTX " + kw + ": " + t[max(0, m.start() - 120):m.start() + 120].replace("\n", " "))
            except Exception as e:
                log.append("  %s ERR %s" % (u, e))
        open(os.path.join(OUT, tag + "_paths.txt"), "w").write("\n".join(sorted(paths)))
    except Exception as e:
        log.append("%s ERR %s" % (base, e))
crawl("https://marketdata.mae.com.ar/", "mae")
crawl("https://open.bymadata.com.ar/", "byma")
MH = {"Origin": "https://marketdata.mae.com.ar", "Referer": "https://marketdata.mae.com.ar/", "Accept": "application/json"}
q = urllib.parse.quote(json.dumps({"fechaDesde": "2026-10-13", "fechaHasta": "2026-10-16"}))
for ep in ["historicosimultaneas", "historicopases", "historicorepos", "simultaneas", "pases", "repos", "historicocauciones"]:
    for pre in ["https://api.marketdata.mae.com.ar/api/mercado/titulo/", "https://api.marketdata.mae.com.ar/api/mercado/"]:
        try:
            st, b = get(pre + ep + "?oTitulo=" + q, h=MH); log.append("MAE %s%s %s %d %r" % (pre[-15:], ep, st, len(b), b[:200]))
        except Exception as e:
            log.append("MAE %s%s ERR %s" % (pre[-15:], ep, e))
open(os.path.join(OUT, "log.txt"), "w").write("\n".join(log))
