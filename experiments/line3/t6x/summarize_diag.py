"""T6x B report from results/capacity_diag_query_crosses.json."""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "results", "capacity_diag_query_crosses.json")))
L = []


def out(s=""):
    L.append(s)
    print(s)


out("## T6x B: capacity diagnosis of the %d questions without an adopted state (default read rule, S300 RUN, level mid)" % len(D))
out()
out("| category | n | detail |")
out("|---|---|---|")
for cat, name in (("i", "(i) no cross holds a query unit"), ("ii", "(ii) only the unit's own seed cross, capacity 1"),
                  ("iii", "(iii) crosses with a query unit exist, no fixed point / ambiguous")):
    xs = [d for d in D if d["category"] == cat]
    det = dict(collections.Counter(d["sub"] for d in xs))
    out("| %s | %d | %s |" % (name, len(xs), det))
out()
c1 = [d for d in D if d["category"] == "i"]
out("(i) the %d questions with no cross holding a query unit: query units and the own-seed cross" % len(c1))
tot = collections.Counter()
for d in c1:
    for u in d["per_unit"]:
        tot["units"] += 1
        tot["in_tier" if u["in_tier"] else "absent"] += 1
        if u["in_tier"]:
            o = u["own"]
            tot["own_cap=%s" % o["capacity"]] += 1
            tot["own_stop=%s" % o["stop"]] += 1
            tot["own_contains_u=%s" % o["own_contains_u"]] += 1
out()
out("  query-unit totals: %s" % dict(tot))
out()
out("| id | query units (after filter) | in tier (n sentences) | own seed cross: capacity / stop / candidates |")
out("|---|---|---|---|")
for d in c1[:40]:
    out("| %s | %s | %s | %s |" % (d["id"], " ".join(d["Q"]) or "(none)",
                                   ", ".join("%s:%s" % (u["u"], u["n"] if u["in_tier"] else "absent") for u in d["per_unit"]) or "-",
                                   ", ".join("%s: %s/%s/%s" % (u["u"], u["own"]["capacity"], u["own"]["stop"], u["own"]["candidates"])
                                             for u in d["per_unit"] if u["own"]) or "-"))
out()
out("(ii)/(iii): crosses holding a query unit, their capacity at mid, and how many stopped by budget")
out()
out("| id | cat | cycle verdict | query units | n crosses holding | capacity hist | stop hist |")
out("|---|---|---|---|---|---|---|")
for d in D:
    if d["category"] != "i":
        out("| %s | %s | %s | %s | %d | %s | %s |" % (d["id"], d["category"], d["verdict"], " ".join(d["Q"]), d["n_holding"], d["cap_hist"], d["stop_hist"]))
out()
out("Budget raise (only crosses involved that stopped by budget are rebuilt; 'exhausted' crosses cannot grow):")
out()
out("| id | cat | involved crosses | stopped by budget | capacity mid -> high -> max (budget-limited crosses) | new stop at max | verdict mid -> high -> max | states adopted mid/high/max |")
out("|---|---|---|---|---|---|---|---|")
n_changed_cap = n_verdict = n_state = 0
base = {}
for d in D:
    if not d["budget_limited"]:
        continue
    caps = []
    chg = False
    for s in d["budget_limited"]:
        r = d["rebuilt"][s]
        c0 = None
        caps.append((s, r["high"]["capacity"], r["max"]["capacity"], r["max"]["stop"]))
    v = [d["verdict"]] + [d["reask"].get(lv, {}).get("verdict") for lv in ("high", "max")]
    st = [0] + [d["reask"].get(lv, {}).get("states_adopted") for lv in ("high", "max")]
    out("| %s | %s | %d | %d | %s | %s | %s | %s |" % (
        d["id"], d["category"], len(d["involved"]), len(d["budget_limited"]),
        "; ".join("%s: %s->%s->%s" % (s, d["caps"][s][0] if d["caps"] and s in d["caps"] else "?", h, m) for s, h, m, _ in caps[:4]) + (" ..." if len(caps) > 4 else ""),
        dict(collections.Counter(c[3] for c in caps)), " -> ".join(map(str, v)), "/".join(map(str, st))))
out()
nb = [d for d in D if d["budget_limited"]]
out("questions with >= 1 involved cross stopped by budget: %d / %d; questions whose involved crosses are all exhausted (budget cannot help): %d" % (
    len(nb), len(D), len(D) - len(nb)))
for lv in ("high", "max"):
    ch = [d for d in nb if d["reask"][lv]["verdict"] != d["verdict"]]
    got = [d for d in nb if d["reask"][lv]["states_adopted"] > 0]
    capup = [d for d in nb if any(d["rebuilt"][s][lv]["capacity"] > (d["caps"][s][0] if d["caps"] else 0) for s in d["budget_limited"])]
    out("  level %s: questions with a bigger cross: %d; verdict changed: %d; now with an adopted state: %d  (%s)" % (
        lv, len(capup), len(ch), len(got), ", ".join(d["id"] + ":" + d["reask"][lv]["verdict"] for d in got)))
open(os.path.join(HERE, "results", "summary_B.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
