"""F1: tables from raw/*.jsonl (build.py output).  usage: summarize.py -> summary.md"""
import json, os, glob, statistics as st
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
L = []
def out(s=""):
    L.append(s); print(s)
def load(corpus, tier, mode, level="mid"):
    p = os.path.join(HERE, "raw", "%s_%s_%s_%s.jsonl" % (corpus, tier, mode, level))
    if not os.path.exists(p):
        return None, None
    rows = [json.loads(l) for l in open(p, encoding="utf-8")]
    return rows[0]["_meta"], rows[1:]
def pct(a, b): return "%d (%.0f%%)" % (a, 100.0 * a / b) if b else "0"
def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(p * len(xs)))]
for corpus in ("fulllead_sents", "S300"):
    out("## %s (level mid)" % corpus); out()
    out("| tier | mode | crosses | bare seed | size 2-3 | size 4-5 | size 6+ | median / p90 / max size | stop budget | exhausted | CPU s | wall s (4 workers) |")
    out("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tier in ("RUN", "WORD", "CHAR"):
        for mode in ("whole", "ordered", "reverse"):
            m, r = load(corpus, tier, mode)
            if r is None: continue
            n = len(r); sz = [x["size"] for x in r]
            out("| %s | %s | %d | %s | %d | %d | %d | %g / %d / %d | %d | %d | %.0f | %.0f |" % (
                tier, mode, n, pct(sum(s == 1 for s in sz), n), sum(2 <= s <= 3 for s in sz), sum(4 <= s <= 5 for s in sz),
                sum(s >= 6 for s in sz), st.median(sz), q(sz, 0.9), max(sz), sum(x["stop"] == "budget" for x in r),
                sum(x["stop"] == "exhausted" for x in r), m["cpu_s"], m["wall_s"]))
    out()
    out("Budget stops of the ordered build (members left): median members left in the breaking group / after it, and the reason")
    out()
    out("| tier | mode | stopped | reasons | left in group median / max | left after median / max | stopped with size 1 (first member alone broke) |")
    out("|---|---|---|---|---|---|---|")
    for tier in ("RUN", "WORD", "CHAR"):
        for mode in ("ordered", "reverse"):
            m, r = load(corpus, tier, mode)
            if r is None: continue
            b = [x for x in r if x["stop"] == "budget"]
            if not b: continue
            out("| %s | %s | %d | %s | %g / %d | %g / %d | %d |" % (
                tier, mode, len(b), dict(Counter(x["broke_reason"] for x in b)), st.median(x["left_in_group"] for x in b),
                max(x["left_in_group"] for x in b), st.median(x["left_after"] for x in b), max(x["left_after"] for x in b),
                sum(x["size"] == 1 for x in b)))
    out()
    out("Order sensitivity (forward vs reverse): crosses of the SAME size / same unit set / same size but different units")
    out()
    out("| tier | crosses | same unit set | same size, other units | different size | median |size diff| among differing |")
    out("|---|---|---|---|---|---|")
    for tier in ("RUN", "WORD", "CHAR"):
        _, a = load(corpus, tier, "ordered"); _, b = load(corpus, tier, "reverse")
        if a is None or b is None: continue
        same = sum(x["units"] == y["units"] for x, y in zip(a, b))
        ss = sum(x["units"] != y["units"] and x["size"] == y["size"] for x, y in zip(a, b))
        ds = [abs(x["size"] - y["size"]) for x, y in zip(a, b) if x["size"] != y["size"]]
        out("| %s | %d | %s | %d | %d | %s |" % (tier, len(a), pct(same, len(a)), ss, len(ds), st.median(ds) if ds else "-"))
    out()
open(os.path.join(HERE, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
