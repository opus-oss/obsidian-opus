#!/usr/bin/env python3
"""Pull the raw series behind the crash-story dashboard.

FRED graph CSVs need no key. Yahoo daily closes cover the stock-side signs
that FRED does not carry (bank index, chip fund, equal-weight S&P).
Writes crash-dashboard/raw/<id>.csv and crash-dashboard/raw/_fetch_log.json.
"""
import csv, io, json, os, sys, time, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) crash-dashboard/1.0"}

FRED = [
    "DFF", "DGS10", "DGS30", "DFII10", "T10YIE", "T10Y3M", "DRTSCILM",
    "SP500", "NASDAQ100",
    "BAMLH0A3HYC", "BAMLH0A0HYM2", "BAMLH0A1HYBB", "BAMLC0A0CM",
    "DCPF3M", "DTB3",
    "WLCFLPCL", "SOFR", "IORB", "RPONTSYD", "WRESBAL", "NFCI",
    "VIXCLS", "STLFSI4", "DEXJPUS", "ICSA", "SAHMREALTIME", "WALCL",
]
YAHOO = {"BKX": "^BKX", "KRE": "KRE", "SMH": "SMH", "RSP": "RSP", "SPY": "SPY", "NVDA": "NVDA"}


def get(url, headers=UA, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace"), dict(r.headers)
        except Exception as e:
            err = e
            time.sleep(3 * (i + 1))
    raise err


def fred(sid):
    txt, _ = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
    rows = []
    for r in list(csv.reader(io.StringIO(txt)))[1:]:
        try:
            rows.append((r[0], float(r[1])))
        except (ValueError, IndexError):
            pass
    return rows


def yahoo(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}?range=30y&interval=1d"
    txt, _ = get(url)
    j = json.loads(txt)["chart"]["result"][0]
    ts = j["timestamp"]; cl = j["indicators"]["quote"][0]["close"]
    return [(dt.datetime.utcfromtimestamp(t).date().isoformat(), round(c, 4)) for t, c in zip(ts, cl) if c is not None]


def main():
    os.makedirs(RAW, exist_ok=True)
    log = {"fetched_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "ok": {}, "failed": {}}
    jobs = [(s, "fred", s) for s in FRED] + [(k, "yahoo", v) for k, v in YAHOO.items()]
    for key, kind, sym in jobs:
        try:
            rows = fred(sym) if kind == "fred" else yahoo(sym)
            if not rows:
                raise ValueError("no rows")
            with open(os.path.join(RAW, f"{key}.csv"), "w", newline="") as f:
                w = csv.writer(f); w.writerow(["date", "value"]); w.writerows(rows)
            log["ok"][key] = {"source": kind, "last": rows[-1], "n": len(rows)}
        except Exception as e:
            log["failed"][key] = f"{kind}: {e}"
        time.sleep(0.4)
    # does FRED let a browser page read it directly?
    try:
        _, h = get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS", headers={**UA, "Origin": "https://example.com"})
        log["fred_cors"] = {k: v for k, v in h.items() if k.lower().startswith("access-control")}
    except Exception as e:
        log["fred_cors"] = f"error {e}"
    with open(os.path.join(RAW, "_fetch_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    print(json.dumps({"ok": len(log["ok"]), "failed": log["failed"], "cors": log["fred_cors"]}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
