#!/usr/bin/env python3
"""Turn the raw series into data.json for the crash-story dashboard.

Every reading carries its source and date. Every verdict comes from a written
trip line shown on the page. History lines are computed from the same series
where the series reaches back that far; where it does not, the line says so.

  python3 crash-dashboard/build.py            -> crash-dashboard/data.json
"""
import csv, datetime as dt, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "data.json")
D = dt.date.fromisoformat

TOPS = {"2000": D("2000-03-24"), "2008": D("2007-10-09"), "2020": D("2020-02-19")}
LOWS = {"2000": D("2002-10-09"), "2008": D("2009-03-09"), "2020": D("2020-03-23")}
FRED_URL = "https://fred.stlouisfed.org/series/{}"
YAHOO_URL = "https://finance.yahoo.com/quote/{}/history"


# ---------- series helpers ----------
def load(key):
    p = os.path.join(RAW, f"{key}.csv")
    if not os.path.exists(p):
        return None
    rows = []
    with open(p) as f:
        for r in list(csv.reader(f))[1:]:
            try:
                rows.append((D(r[0]), float(r[1])))
            except (ValueError, IndexError):
                pass
    return rows or None


def at(s, day):
    """Last value on or before day."""
    best = None
    for d, v in s:
        if d > day:
            break
        best = (d, v)
    return best


def window(s, a, b):
    return [(d, v) for d, v in s if a <= d <= b]


def peak(s, a, b, lo=False):
    w = window(s, a, b)
    if not w:
        return None
    return (min if lo else max)(w, key=lambda x: x[1])


def avg_last(s, n):
    tail = s[-n:]
    return sum(v for _, v in tail) / len(tail)


def drawdown(s, day=None, look=365):
    """% under the highest close of the prior `look` days, on `day` (default last)."""
    day = day or s[-1][0]
    now = at(s, day)
    hi = peak(s, day - dt.timedelta(days=look), day)
    return (now[1] / hi[1] - 1) * 100, hi, now


def max_drop(s, a, b):
    """Worst peak-to-trough fall inside a window, in %."""
    w = window(s, a, b)
    if not w:
        return None
    hi, worst = w[0][1], 0
    for _, v in w:
        hi = max(hi, v)
        worst = min(worst, v / hi - 1)
    return worst * 100


def covers(s, day):
    return s and s[0][0] <= day


def spark(s, years=3, n=150, f=lambda v: v):
    if not s:
        return []
    start = s[-1][0] - dt.timedelta(days=int(365.25 * years))
    w = [(d, v) for d, v in s if d >= start]
    step = max(1, len(w) // n)
    pts = w[::step]
    if pts[-1] != w[-1]:
        pts.append(w[-1])
    return [[d.isoformat(), round(f(v), 3)] for d, v in pts]


def diff(a, b):
    """a minus b on matching dates."""
    bd = dict(b)
    return [(d, v - bd[d]) for d, v in a if d in bd]


def mon(d):
    return d.strftime("%b %Y")


def day(d):
    return d.strftime("%b %-d, %Y")


def pct(x):
    return f"{abs(x):.0f}%"


# ---------- indicator records ----------
def card(id, chapter, name, what, value, unit_text, as_of, verdict, rule, history, src, src_label,
         spark_pts=None, trip=None, trip_label=None, note=None, invert=False):
    return {
        "id": id, "chapter": chapter, "name": name, "what": what,
        "value": value, "reading": unit_text, "as_of": as_of.isoformat() if as_of else None,
        "verdict": verdict, "rule": rule, "history": history,
        "source": src, "source_label": src_label,
        "spark": spark_pts or [], "trip": trip, "trip_label": trip_label, "note": note,
    }


def nodata(id, chapter, name, what, rule, src, src_label, why):
    c = card(id, chapter, name, what, None, "No live reading", None, "nodata", rule,
             "", src, src_label)
    c["note"] = why
    return c


def grade(x, fired, warming, higher_is_worse=True):
    if x is None:
        return "nodata"
    if higher_is_worse:
        return "fired" if x >= fired else "warming" if x >= warming else "quiet"
    return "fired" if x <= fired else "warming" if x <= warming else "quiet"


def build():
    S = {k[:-4]: load(k[:-4]) for k in os.listdir(RAW) if k.endswith(".csv")}
    log = json.load(open(os.path.join(RAW, "_fetch_log.json"))) if os.path.exists(os.path.join(RAW, "_fetch_log.json")) else {}
    cards, why_missing = [], log.get("failed", {})

    def miss(k):
        return f"Could not pull {k} on the last refresh ({why_missing.get(k, 'not fetched')})."

    # ===== Chapter 1: money gets dear =====
    s = S.get("DFF")
    if s:
        d0, v0 = s[-1]
        v12 = at(s, d0 - dt.timedelta(days=365))[1]
        v24 = at(s, d0 - dt.timedelta(days=730))[1]
        ch12 = v0 - v12
        v6 = at(s, d0 - dt.timedelta(days=182))[1]
        last_cut = any(b_ < a_ - 0.2 for (_, a_), (_, b_) in zip(window(s, d0 - dt.timedelta(days=182), d0), window(s, d0 - dt.timedelta(days=182), d0)[1:]))
        verdict = "fired" if v0 - v6 >= 0.2 and not last_cut else "warming" if ch12 > 0 else "quiet"
        hist = []
        for y, t in TOPS.items():
            a, b = at(s, t - dt.timedelta(days=730))[1], at(s, t)[1]
            hist.append(f"{y}: {a:.2f}% two years before the top, {b:.2f}% at it")
        cards.append(card("fed", 1, "The Fed's rate",
            "The rate banks pay to borrow overnight, set by the Fed. Raising it into a boom is how most busts start.",
            v0, f"{v0:.2f}%, {'up' if v0 - v6 >= 0 else 'down'} {abs(v0 - v6):.2f} points in six months", d0, verdict,
            "Fired: the Fed has raised in the last six months and not cut since. Warming: higher than a year ago.",
            ". ".join(hist) + ".", FRED_URL.format("DFF"), "FRED DFF, daily", spark(s)))
    else:
        cards.append(nodata("fed", 1, "The Fed's rate", "", "", FRED_URL.format("DFF"), "FRED DFF", miss("DFF")))

    s = S.get("DGS30")
    if s:
        d0, v0 = s[-1]
        lo = peak(s, d0 - dt.timedelta(days=365), d0, lo=True)
        ch = v0 - at(s, d0 - dt.timedelta(days=365))[1]
        verdict = grade(ch, 0.75, 0.25)
        cards.append(card("long", 1, "Long-term borrowing cost",
            "What the US government pays to borrow for 30 years. When it jumps, mortgages, company debt and stock prices all feel it.",
            v0, f"{v0:.2f}%, {'up' if ch >= 0 else 'down'} {abs(ch):.2f} points in a year", d0, verdict,
            "Fired: up three quarters of a point in a year. Warming: up a quarter point.",
            "Before 1987 it rose from about 7.5% to over 10% in seven months. Britain's long bonds broke in 2022 and pension funds hit margin calls within three days. (From the project's earlier crash study, rounded.)",
            FRED_URL.format("DGS30"), "FRED DGS30, daily", spark(s)))

    s = S.get("T10Y3M")
    if s:
        d0, v0 = s[-1]
        past = window(s, d0 - dt.timedelta(days=730), d0)
        inverted_days = sum(1 for _, v in past if v < 0)
        if v0 < 0:
            verdict, state = "warming", "below zero now (inverted)"
        elif inverted_days >= 60:
            verdict, state = "quiet", "above zero"
        else:
            verdict, state = "quiet", "above zero, no recent inversion"
        eps, cur = [], None
        for d, v in s:
            if v < 0:
                if cur and (d - cur[1]).days < 90:
                    cur[1] = d
                else:
                    cur = [d, d]; eps.append(cur)
        eps = [e for e in eps if (e[1] - e[0]).days > 60]
        last_ep = eps[-1] if eps else None
        if v0 >= 0 and last_ep and (d0 - last_ep[1]).days <= 730:
            verdict, state = "fired", f"back above zero since {mon(last_ep[1])} after {((last_ep[1] - last_ep[0]).days / 30.4):.0f} months below. The late, dangerous part"
        hist = []
        for y, t in TOPS.items():
            near = [e for e in eps if t - dt.timedelta(days=730) <= e[1] <= t + dt.timedelta(days=400)]
            if near:
                e = max(near, key=lambda e: (e[1] - e[0]).days)
                hist.append(f"{y}: below zero {mon(e[0])} to {mon(e[1])}; stocks topped {mon(t)}")
        cards.append(card("curve", 1, "The yield curve",
            "Long-term rates minus 3-month rates. Below zero means the bond market expects trouble. The crash usually comes after it flips back above zero.",
            v0, f"{v0:+.2f} points, {state}", d0, verdict,
            "Warming: below zero. Fired: back above zero within two years of a long stretch below it. Recessions have usually begun in that window.",
            ". ".join(hist) + ".", FRED_URL.format("T10Y3M"), "FRED T10Y3M, daily", spark(s, years=4), 0, "zero"))

    s = S.get("DRTSCILM")
    if s:
        d0, v0 = s[-1]
        hist = []
        for y, t in TOPS.items():
            a = at(s, t)
            pk = peak(s, t, LOWS[y] + dt.timedelta(days=200))
            if a and pk:
                hist.append(f"{y}: {a[1]:.0f}% at the top, peaked at {pk[1]:.0f}%")
        cards.append(card("loans", 1, "Banks getting stingy",
            "The Fed asks bank loan officers each quarter whether they are tightening business-loan rules. The number is the share tightening minus the share easing.",
            v0, f"{v0:+.1f}% of banks tightening (net)", d0, grade(v0, 20, 0.01),
            "Fired: 20% or more tightening on net. Warming: above zero.",
            ". ".join(hist) + ". Quarterly; the next survey is due early February.",
            FRED_URL.format("DRTSCILM"), "FRED DRTSCILM, Fed loan officer survey", spark(s, years=8), 20, "fired line"))

    # thesis check box (falsifier 1 and 4 from THESIS.md)
    thesis = None
    r, b = S.get("DFII10"), S.get("T10YIE")
    if r and b:
        thesis = {
            "real": r[-1][1], "real_date": r[-1][0].isoformat(),
            "be": b[-1][1], "be_date": b[-1][0].isoformat(),
            "f1": r[-1][1] > 3.0 and b[-1][1] < 2.0,
            "f4": r[-1][1] < 2.0 and b[-1][1] > 2.6,
            "src": [FRED_URL.format("DFII10"), FRED_URL.format("T10YIE")],
        }

    # ===== Chapter 2: leaders break =====
    ndx, spx = S.get("NASDAQ100"), S.get("SP500")
    if ndx and spx:
        dd_n, hi_n, now_n = drawdown(ndx)
        dd_s, hi_s, now_s = drawdown(spx, now_n[0])
        verdict = "fired" if dd_n <= -15 else "warming" if dd_n <= -8 else "quiet"
        spy = S.get("SPY")
        h2000 = f"2000: the Nasdaq-100 fell {pct(max_drop(ndx, D('2000-03-01'), D('2000-05-31')))} from March to May"
        if spy and covers(spy, D("2000-01-01")):
            dd_spy_sep = drawdown(spy, D("2000-09-01"), look=400)[0]
            h2000 += f", yet the S&P 500 fund was only {pct(dd_spy_sep)} under its high on Sept 1"
        h2008 = f"2008: the Nasdaq-100 fell {pct(max_drop(ndx, TOPS['2008'], LOWS['2008']))} top to bottom"
        h2020 = f"2020: {pct(max_drop(ndx, TOPS['2020'], LOWS['2020']))} in five weeks"
        cards.append(card("leaders", 2, "Tech leaders vs the whole market",
            "The Nasdaq-100 holds the giants that led the boom. In a mania they fall first while the broad S&P 500 hides the damage.",
            dd_n, f"Nasdaq-100 {pct(dd_n)} under its high ({day(hi_n[0])}); S&P 500 {pct(dd_s)} under its high", now_n[0], verdict,
            "Fired: Nasdaq-100 15% or more under its one-year high. Warming: 8% or more.",
            f"{h2000}. {h2008}. {h2020}.", FRED_URL.format("NASDAQ100"), "FRED NASDAQ100 and SP500, daily",
            spark(ndx, years=2, f=lambda v: v), None, None))
    chips, nv = S.get("SMH"), S.get("NVDA")
    if chips:
        dd_c, hi_c, now_c = drawdown(chips)
        extra = ""
        if nv:
            dd_v, _, _ = drawdown(nv)
            extra = f"; Nvidia (NVDA) {pct(dd_v)} under"
        hist = []
        if covers(chips, D("2000-07-01")):
            hist.append(f"2000 to 2002: the chip fund fell {pct(max_drop(chips, D('2000-06-01'), LOWS['2000']))}")
        hist.append(f"2008: {pct(max_drop(chips, TOPS['2008'], LOWS['2008']))}")
        hist.append(f"2020: {pct(max_drop(chips, TOPS['2020'], LOWS['2020']))}")
        cards.append(card("chips", 2, "Chip stocks, the AI leaders",
            "The semiconductor fund (SMH) holds Nvidia, Broadcom and the rest of the AI build-out. This boom's leaders.",
            dd_c, f"Chip fund {pct(dd_c)} under its high ({day(hi_c[0])}){extra}", now_c[0], grade(-dd_c, 20, 10),
            "Fired: 20% or more under its one-year high. Warming: 10% or more.",
            ". ".join(hist) + ".", YAHOO_URL.format("SMH"), "Yahoo Finance daily closes", spark(chips, years=2)))
    else:
        cards.append(nodata("chips", 2, "Chip stocks, the AI leaders",
            "The semiconductor fund (SMH) holds Nvidia, Broadcom and the rest of the AI build-out.",
            "Fired: 20% under its one-year high.", YAHOO_URL.format("SMH"), "Yahoo Finance", miss("SMH")))

    # ===== Chapter 3: credit cracks =====
    ccc, hy, bb = S.get("BAMLH0A3HYC"), S.get("BAMLH0A0HYM2"), S.get("BAMLH0A1HYBB")
    if ccc:
        d0, v0 = ccc[-1]
        lo = peak(ccc, d0 - dt.timedelta(days=365), d0, lo=True)
        rise = v0 - lo[1]
        hi = peak(ccc, d0 - dt.timedelta(days=365), d0)
        extra = f" BB bonds, the safest junk, {bb[-1][1]:.2f}." if bb else ""
        cards.append(card("ccc", 3, "The weakest junk bonds",
            "CCC bonds come from the companies most likely to default. The extra interest they pay over Treasuries widens first, because they are the first cut off.",
            v0, f"{v0:.2f} points over Treasuries, up {rise:.2f} from its one-year low ({day(lo[0])}). Year high {hi[1]:.2f} on {day(hi[0])}.{extra}", d0,
            grade(rise, 3, 1.5),
            "Fired: up 3 points or more from its one-year low. Warming: up 1.5.",
            "This pattern, the weakest blown out while the rest of junk stays calm, caught 1990 and 2007, and gave false alarms in 1998, 2011 and 2016. (From the project's earlier study. FRED now only serves three years of this series, so older readings can't be shown live.)",
            FRED_URL.format("BAMLH0A3HYC"), "FRED BAMLH0A3HYC (ICE BofA), daily", spark(ccc), 13.56, "Oct 23 high"))
    if hy:
        d0, v0 = hy[-1]
        lo = peak(hy, d0 - dt.timedelta(days=365), d0, lo=True)
        rise = v0 - lo[1]
        verdict = "fired" if v0 >= 6 else "warming" if (v0 >= 4.5 or rise >= 1.5) else "quiet"
        cards.append(card("hy", 3, "All junk bonds",
            "The extra interest all below-investment-grade companies pay. When this widens, the whole risky-borrower market is shutting.",
            v0, f"{v0:.2f} points over Treasuries, up {rise:.2f} from its one-year low", d0, verdict,
            "Fired: 6 points or more. Warming: 4.5 or more, or up 1.5 from its one-year low.",
            "From memory, rounded: about 2.4 at the 2007 low, about 22 at the December 2008 peak; about 3.5 before the 2020 drop and about 11 at its March 23 peak; roughly 5 entering 2000 and around 9 by that year's end. FRED only serves three years now, so these can't be checked live.",
            FRED_URL.format("BAMLH0A0HYM2"), "FRED BAMLH0A0HYM2 (ICE BofA), daily", spark(hy), 6, "fired line"))
    cp, tb = S.get("DCPF3M"), S.get("DTB3")
    if cp and tb:
        sp = diff(cp, tb)
        d0 = sp[-1][0]
        v0 = avg_last(sp, 5)
        hist = []
        for y, (a, b) in {"2000": (D("2000-01-01"), D("2001-12-31")), "2008": (D("2007-07-01"), D("2008-12-31")), "2020": (TOPS["2020"], D("2020-04-30"))}.items():
            pk = peak(sp, a, b)
            if pk:
                hist.append(f"{y}: peaked at {pk[1]:.2f} on {day(pk[0])}")
        cards.append(card("cp", 3, "Short-term company IOUs",
            "Commercial paper is how banks and big companies borrow for weeks at a time. The gap over Treasury bills jumps when lenders stop trusting borrowers. It broke first in August 2007.",
            v0, f"{v0:.2f} points over Treasury bills (5-day average)", d0, grade(v0, 1.0, 0.5),
            "Fired: 1 point or more. Warming: half a point.",
            ". ".join(hist) + ".", FRED_URL.format("DCPF3M"), "FRED DCPF3M minus DTB3, daily", spark(sp), 1.0, "fired line"))

    # ===== Chapter 4: banks and the money pipes =====
    bkx = S.get("BKX")
    if bkx:
        dd_b, hi_b, now_b = drawdown(bkx)
        hist = []
        for y, t in TOPS.items():
            if covers(bkx, t - dt.timedelta(days=365)):
                ddt, hit, _ = drawdown(bkx, t)
                hist.append(f"{y}: the day the S&P topped, banks were already {pct(ddt)} under their high of {mon(hit[0])}")
        kre = S.get("KRE")
        extra = f"; regional banks (KRE) {pct(drawdown(kre)[0])} under" if kre else ""
        cards.append(card("banks", 4, "Bank stocks",
            "Banks feel bad loans first, so their stocks roll over while the index is still near its high.",
            dd_b, f"Bank index {pct(dd_b)} under its high ({day(hi_b[0])}){extra}", now_b[0], grade(-dd_b, 20, 10),
            "Fired: 20% or more under its one-year high. Warming: 10% or more.",
            ". ".join(hist) + ".", YAHOO_URL.format("%5EBKX"), "KBW bank index, Yahoo Finance daily closes", spark(bkx, years=2)))
    else:
        cards.append(nodata("banks", 4, "Bank stocks",
            "Banks feel bad loans first, so their stocks roll over while the index is still near its high.",
            "Fired: 20% under its one-year high.", YAHOO_URL.format("%5EBKX"), "Yahoo Finance", miss("BKX")))
    s = S.get("WLCFLPCL")
    if s:
        sb = [(d, v / 1000) for d, v in s]
        d0, v0 = sb[-1]
        two = sb[-2][1] if len(sb) > 1 else v0
        verdict = "fired" if v0 >= 22 and two >= 22 else "warming" if v0 >= 10 else "quiet"
        hist = []
        for y, (a, b) in {"2008": (D("2007-08-01"), D("2009-06-30")), "2020": (D("2020-02-01"), D("2020-06-30")), "2023": (D("2023-03-01"), D("2023-05-31"))}.items():
            pk = peak(sb, a, b)
            if pk:
                hist.append(f"{y}: peaked at ${pk[1]:.0f} billion ({day(pk[0])})")
        cards.append(card("window", 4, "Banks at the Fed's emergency window",
            "The discount window is where banks borrow from the Fed when nobody else will lend to them. A jump means a bank is losing its funding.",
            v0, f"${v0:.1f} billion (week of {day(d0)}); ${two:.1f} billion the week before", d0, verdict,
            "Fired: $22 billion or more two weeks running (the project's go-time line). Warming: $10 billion or more.",
            ". ".join(hist) + ". It sat at $5 to $10 billion for 15 weeks before Silicon Valley Bank failed.",
            FRED_URL.format("WLCFLPCL"), "FRED WLCFLPCL, Fed weekly balance sheet", spark(sb), 22, "go-time line"))
    so, io_ = S.get("SOFR"), S.get("IORB")
    if so and io_:
        sp = diff(so, io_)
        d0 = sp[-1][0]
        v0 = avg_last(sp, 5)
        pk19 = peak(so, D("2019-09-01"), D("2019-09-30"))
        cards.append(card("sofr", 4, "Overnight lending vs the Fed's floor",
            "SOFR is what it costs to borrow cash overnight against Treasuries. When it climbs above the rate the Fed pays banks on reserves, cash is getting scarce in the pipes.",
            v0, f"{v0*100:+.0f} basis points (5-day average; 100 basis points = 1%)", d0, grade(v0, 0.10, 0.0),
            "Fired: 10 basis points or more above the Fed's rate. Warming: above it at all.",
            (f"Sept 2019: overnight cash jumped to {pk19[1]:.2f}% on {day(pk19[0])}, more than double the normal rate, and the Fed had to step in. " if pk19 else "") +
            "SOFR only began in 2018, so there is no reading for 2000 or 2008.",
            FRED_URL.format("SOFR"), "FRED SOFR minus IORB, daily", spark([(d, v * 100) for d, v in sp], years=2), 10, "fired line"))
    s = S.get("RPONTSYD")
    if s:
        d0 = s[-1][0]
        v0 = avg_last(s, 5)
        pk = peak(s, D("2019-09-01"), D("2020-06-30"))
        cards.append(card("repo", 4, "Banks borrowing from the Fed's repo desk",
            "Cash the Fed lends overnight against Treasuries. Heavy use means private lenders are pulling back.",
            v0, f"${v0:.1f} billion a day (5-day average)", d0, grade(v0, 25, 10),
            "Fired: $25 billion a day or more on average. Warming: $10 billion. Month-end spikes are normal; the average smooths them.",
            (f"2019-2020: peaked at ${pk[1]:.0f} billion on {day(pk[0])}. " if pk else "") + "This tool only restarted in Sept 2019.",
            FRED_URL.format("RPONTSYD"), "FRED RPONTSYD, daily", spark(s, years=2), 25, "fired line"))
    s = S.get("NFCI")
    if s:
        d0, v0 = s[-1]
        hist = []
        for y, t in TOPS.items():
            a = at(s, t)[1]
            pk = peak(s, t, LOWS[y])
            hist.append(f"{y}: {a:+.2f} at the top, peaked at {pk[1]:+.2f}")
        cards.append(card("nfci", 4, "Overall money conditions",
            "The Chicago Fed blends 105 measures of credit, funding and markets into one number. Zero is average; above zero means money is tighter than normal.",
            v0, f"{v0:+.2f}", d0, grade(v0, 0, -0.25),
            "Fired: above zero. Warming: above minus 0.25.",
            ". ".join(hist) + ".", FRED_URL.format("NFCI"), "FRED NFCI, weekly", spark(s, years=4), 0, "average"))

    # ===== Chapter 5: panic =====
    s = S.get("VIXCLS")
    if s:
        d0, v0 = s[-1]
        a5 = avg_last(s, 5)
        hist = []
        for y, t in TOPS.items():
            pk = peak(s, t, LOWS[y])
            hist.append(f"{y}: {at(s, t)[1]:.0f} at the top, peaked at {pk[1]:.0f} ({mon(pk[0])})")
        cards.append(card("vix", 5, "The fear gauge",
            "The VIX is the price of insurance on the S&P 500. It rises on the way down, not before, so it confirms panic rather than warning of it.",
            v0, f"{v0:.1f} (5-day average {a5:.1f})", d0, grade(a5, 30, 20),
            "Fired: 5-day average of 30 or more. Warming: 20 or more.",
            ". ".join(hist) + ".", FRED_URL.format("VIXCLS"), "FRED VIXCLS (CBOE), daily", spark(s, years=2), 30, "fired line"))
    s = S.get("STLFSI4")
    if s:
        d0, v0 = s[-1]
        hist = []
        for y, t in TOPS.items():
            if covers(s, t):
                pk = peak(s, t, LOWS[y])
                hist.append(f"{y}: {at(s, t)[1]:+.1f} at the top, peaked at {pk[1]:+.1f}")
        cards.append(card("stress", 5, "Financial stress index",
            "The St. Louis Fed's stress gauge built from 18 market series. Zero is normal; above zero is stress.",
            v0, f"{v0:+.2f}", d0, grade(v0, 1, 0),
            "Fired: above 1. Warming: above zero.",
            ". ".join(hist) + ".", FRED_URL.format("STLFSI4"), "FRED STLFSI4, weekly", spark(s, years=4), 0, "normal"))
    s = S.get("DEXJPUS")
    if s:
        d0, v0 = s[-1]
        base = s[-21][1] if len(s) > 21 else s[0][1]
        stronger = (base / v0 - 1) * 100      # yen gains when yen-per-dollar falls
        hist = []
        for label, a, b in (("Oct 1998", D("1998-09-15"), D("1998-10-31")), ("2008", D("2008-08-01"), D("2008-12-31")), ("Aug 2024", D("2024-07-01"), D("2024-08-31"))):
            w = window(s, a, b)
            if len(w) > 21:
                best = max((w[i - 20][1] / w[i][1] - 1) * 100 for i in range(20, len(w)))
                hist.append(f"{label}: the yen gained up to {best:.0f}% in a month")
        cards.append(card("yen", 5, "The yen jumps",
            "Traders borrow cheap yen to buy everything else. When they are forced to sell, they buy yen back and it spikes. A rising yen means fewer yen per dollar.",
            v0, f"{v0:.2f} yen per dollar; the yen is {'stronger' if stronger >= 0 else 'weaker'} by {abs(stronger):.1f}% over 20 trading days", d0,
            grade(stronger, 7, 3),
            "Fired: yen 7% stronger in 20 trading days. Warming: 3% stronger.",
            ". ".join(hist) + ". FRED posts this weekly, so it can lag the market by a few days.",
            FRED_URL.format("DEXJPUS"), "FRED DEXJPUS (Fed H.10), daily, posted weekly", spark(s, years=2)))
    s = S.get("SAHMREALTIME")
    if s:
        d0, v0 = s[-1]
        hist = []
        for y, t in TOPS.items():
            hit = next((d for d, v in s if d >= t - dt.timedelta(days=200) and v >= 0.5), None)
            if hit:
                hist.append(f"{y}: crossed 0.5 in {mon(hit)}, {((hit - t).days / 30.4):+.0f} months from the stock top")
        cards.append(card("jobs", 5, "The job market cracks",
            "The Sahm rule: when the 3-month average jobless rate rises half a point above its low of the past year, a recession has begun. It confirms late; it does not warn early.",
            v0, f"{v0:.2f} points", d0, grade(v0, 0.5, 0.3),
            "Fired: 0.5 or more. Warming: 0.3 or more.",
            ". ".join(hist) + ".", FRED_URL.format("SAHMREALTIME"), "FRED SAHMREALTIME, monthly", spark(s, years=4), 0.5, "fired line"))

    # ===== Chapter 6: rescue =====
    s = S.get("DFF")
    if s:
        d0, v0 = s[-1]
        ch3 = v0 - at(s, d0 - dt.timedelta(days=91))[1]
        cards.append(card("cuts", 6, "The Fed cuts fast",
            "Emergency or rapid rate cuts. This comes after the panic, never before it.",
            ch3, f"{'down' if ch3 < 0 else 'up'} {abs(ch3):.2f} points in three months", d0, grade(ch3, -0.5, -0.2, higher_is_worse=False),
            "Fired: cut half a point or more in three months. Warming: cut a fifth of a point.",
            "Jan 2001 surprise cut; Jan 22, 2008 emergency three-quarter-point cut; March 3 and 15, 2020, two emergency cuts to zero.",
            FRED_URL.format("DFF"), "FRED DFF, daily", spark(s, years=2)))
    s = S.get("WALCL")
    if s:
        sb = [(d, v / 1e6) for d, v in s]
        d0, v0 = sb[-1]
        ch = (v0 / sb[-9][1] - 1) * 100 if len(sb) > 9 else 0
        h08 = (at(sb, D("2008-12-31"))[1] / at(sb, D("2008-09-10"))[1] - 1) * 100
        h20 = (at(sb, D("2020-06-10"))[1] / at(sb, D("2020-03-11"))[1] - 1) * 100
        cards.append(card("printing", 6, "The Fed's balance sheet jumps",
            "When the Fed buys bonds or lends on a huge scale, its balance sheet balloons. This is the money-printing turn, the inflationary second phase of the thesis.",
            ch, f"${v0:.2f} trillion, {'up' if ch >= 0 else 'down'} {abs(ch):.1f}% in eight weeks", d0, grade(ch, 5, 2),
            "Fired: up 5% or more in eight weeks. Warming: up 2%.",
            f"Sept to Dec 2008: up {h08:.0f}%. March to June 2020: up {h20:.0f}%.",
            FRED_URL.format("WALCL"), "FRED WALCL, weekly", spark(sb, years=4)))

    # ===== go-time watch lines (from the Nov 8 plan; watch lines, not rules) =====
    watch = []
    c = next((x for x in cards if x["id"] == "window" and x["value"] is not None), None)
    if c:
        sb = [(d, v / 1000) for d, v in S["WLCFLPCL"]]
        watch.append({"name": "Fed emergency window at $22 billion two weeks running",
                      "now": f"${sb[-1][1]:.1f}B and ${sb[-2][1]:.1f}B", "as_of": c["as_of"],
                      "fired": sb[-1][1] >= 22 and sb[-2][1] >= 22})
    c = next((x for x in cards if x["id"] == "yen"), None)
    if c:
        watch.append({"name": "The yen strengthens fast while stocks fall", "now": c["reading"], "as_of": c["as_of"],
                      "fired": c["verdict"] == "fired"})
    if ccc and hy:
        hy_rise = hy[-1][1] - hy[-21][1]
        watch.append({"name": "Weakest junk above 13.56 while all junk widens",
                      "now": f"CCC {ccc[-1][1]:.2f}; all junk {hy[-1][1]:.2f}, {'+' if hy_rise >= 0 else ''}{hy_rise:.2f} in a month",
                      "as_of": ccc[-1][0].isoformat(), "fired": ccc[-1][1] > 13.56 and hy_rise > 0.25})

    fmt = {
        "fed": "{:.2f}%", "long": "{:.2f}%", "curve": "{:+.2f}", "loans": "{:+.1f}%",
        "leaders": "{:.0f}%", "chips": "{:.0f}%", "banks": "{:.0f}%",
        "ccc": "{:.2f}", "hy": "{:.2f}", "cp": "{:.2f}", "window": "${:.1f}B", "repo": "${:.1f}B",
        "nfci": "{:+.2f}", "vix": "{:.1f}", "stress": "{:+.2f}", "yen": "{:.2f}", "jobs": "{:.2f}",
        "cuts": "{:+.2f}", "printing": "{:+.1f}%",
    }
    for c in cards:
        v = c["value"]
        if v is None:
            c["big"] = "No reading"
        elif c["id"] == "sofr":
            c["big"] = f"{v * 100:+.0f} bp"
        else:
            c["big"] = fmt.get(c["id"], "{}").format(v)
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fetched_utc": log.get("fetched_utc"),
        "failed": why_missing,
        "cards": cards, "watch": watch, "thesis": thesis,
    }


if __name__ == "__main__":
    data = build()
    with open(OUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    v = {}
    for c in data["cards"]:
        v.setdefault(c["chapter"], []).append(f'{c["id"]}:{c["verdict"]}')
    print(json.dumps(v, indent=1))
