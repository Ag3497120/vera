"""F1c: tables from raw/*.jsonl (build.py output) against experiments/line3/f1/raw (ordered+stop).  usage: summarize.py -> summary.md"""
import glob, json, os, statistics as st
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
F1 = os.path.join(os.path.dirname(HERE), "f1", "raw")
L = []
def out(s=""):
    L.append(s); print(s)
def load(path):
    if not os.path.exists(path): return None, None
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    return rows[0]["_meta"], rows[1:]
def pct(a, b): return "%d (%.0f%%)" % (a, 100.0 * a / b) if b else "0"
def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else "-"
out("# F1c: ordered + stop (L-463) vs ordered + skip (L-501), fulllead_sents, level mid"); out()
out("Crosses that EXHAUSTED under stop are the same under skip (nothing collapses) and were copied; only the budget-stopped ones were rebuilt (build.py).")
out()
T = {}
SAMPLE = {}
for tier in ("RUN", "WORD", "CHAR"):
    ms, rs = load(os.path.join(F1, "fulllead_sents_%s_ordered_mid.jsonl" % tier))
    mk, rk = load(os.path.join(HERE, "raw", "fulllead_sents_%s_skip_mid.jsonl" % tier))
    if rk is None:                      # no full run of this tier: the sample (every k-th seed), compared on the same seeds
        sm = sorted(glob.glob(os.path.join(HERE, "raw", "fulllead_sents_%s_skip_mid_lim*.jsonl" % tier)))
        sm = [f for f in sm if "_reach" not in f]
        if not sm: continue
        mk, rk = load(sm[-1])
        keep = {x["seed"] for x in rk}
        rs = [x for x in rs if x["seed"] in keep]
        ms = dict(ms, cpu_s=round(sum(x["secs"] for x in rs), 1))
        SAMPLE[tier] = (len(rk), "sample")
    T[tier] = (ms, rs, mk, rk)
out("Tiers with a full run: " + (", ".join(t for t in T if t not in SAMPLE) or "none") + ". Sample (every k-th seed, same seeds on both sides): " +
    (", ".join("%s %d seeds" % (t, v[0]) for t, v in SAMPLE.items()) or "none") + ".")
out()
out("## Sizes and stop reasons"); out()
out("| tier | mode | crosses | bare seed | size 2-3 | size 4-5 | size 6+ | median / p90 / max size | stop budget | exhausted |")
out("|---|---|---|---|---|---|---|---|---|---|")
for tier, (ms, rs, mk, rk) in T.items():
    for mode, r in (("stop", rs), ("skip", rk)):
        n = len(r); sz = [x["size"] for x in r]
        out("| %s | %s | %d | %s | %d | %d | %d | %g / %d / %d | %d | %d |" % (
            tier, mode, n, pct(sum(s == 1 for s in sz), n), sum(2 <= s <= 3 for s in sz), sum(4 <= s <= 5 for s in sz),
            sum(s >= 6 for s in sz), st.median(sz), q(sz, 0.9), max(sz), sum(x["stop"] == "budget" for x in r),
            sum(x["stop"] == "exhausted" for x in r)))
out()
out("## Crosses that differ from stop"); out()
out("differ = the set of units seated differs from the stop cross (skip only adds units: stop's units are a subset, checked). Skipped members: among crosses with >= 1 skipped member.")
out()
out("| tier | stopped on budget (stop) | with >= 1 skipped member | differ from stop | of which gain >= 1 unit | gained units median / p90 / max | skipped per cross (with skips) median / p90 / max | skipped members total | candidates tried to seat after the first collapse (median / max) | reasons of skipped members |")
out("|---|---|---|---|---|---|---|---|---|---|")
for tier, (ms, rs, mk, rk) in T.items():
    bud = sum(x["stop"] == "budget" for x in rs)
    ws = [x for x in rk if x["n_skipped"] > 0]
    diff = [x for x in rk if set(x["units"]) != set(x["first_stop_units"])]
    assert all(set(x["first_stop_units"]) <= set(x["units"]) for x in rk), "skip lost a unit of the stop cross"
    gain = [x["size"] - x["first_stop_size"] for x in diff]
    tried = [x["left_in_group"] + x["left_after"] for x in ws]
    reasons = Counter(w[2] for x in ws for w in x["skipped"])
    out("| %s | %d | %d | %s | %d | %s / %s / %s | %s / %s / %s | %d | %s / %s | %s |" % (
        tier, bud, len(ws), pct(len(diff), len(rk)), len(diff), st.median(gain) if gain else "-", q(gain, 0.9), max(gain) if gain else "-",
        st.median([x["n_skipped"] for x in ws]) if ws else "-", q([x["n_skipped"] for x in ws], 0.9), max([x["n_skipped"] for x in ws]) if ws else "-",
        sum(x["n_skipped"] for x in ws), st.median(tried) if tried else "-", max(tried) if tried else "-", dict(reasons)))
out()
out("Among the differing crosses: the stop reason under stop was (left_after > 0 under stop = the stop also dropped later groups):")
out()
out("| tier | differ | stop had left_after > 0 | size gain 1 | gain 2-5 | gain 6+ | exhausted wholly after skipping with 0 skips (impossible) |")
out("|---|---|---|---|---|---|---|")
for tier, (ms, rs, mk, rk) in T.items():
    prev = {x["seed"]: x for x in rs}
    diff = [x for x in rk if set(x["units"]) != set(x["first_stop_units"])]
    g = [x["size"] - x["first_stop_size"] for x in diff]
    out("| %s | %d | %d | %d | %d | %d | %d |" % (tier, len(diff), sum(prev[x["seed"]]["left_after"] > 0 for x in diff),
        sum(v == 1 for v in g), sum(2 <= v <= 5 for v in g), sum(v >= 6 for v in g), sum(x["n_skipped"] == 0 for x in diff)))
out()
out("## Cost (CPU seconds)"); out()
out("Pro column = f1 ordered+stop as measured on the Pro (4 workers). Air columns = the rebuilt (budget-stopped) crosses, stop and skip timed in the same worker on the Air (same machine, same load).")
out()
out("| tier | stop total (Pro) | skip total (reused Pro secs + rebuilt Air secs) | rebuilt crosses | stop on those (Air) | skip on those (Air) | ratio skip / stop on those |")
out("|---|---|---|---|---|---|---|")
for tier, (ms, rs, mk, rk) in T.items():
    reb = [x for x in rk if not x["reused"]]
    a = sum(x["stop_secs_here"] for x in reb); b = sum(x["secs"] for x in reb)
    out("| %s | %.0f | %.0f | %d | %.0f | %.0f | %s |" % (tier, ms["cpu_s"], mk["cpu_s"], len(reb), a, b, "%d.%02d" % divmod(int(100 * b / a), 100) if a else "-"))
out()
out("Checks: " + "; ".join("%s: Air stop build equals f1/raw units on %d of %d rebuilt, %d reused crosses re-verified, mismatches %s" % (
    tier, sum(x.get("stop_here_units_equal_f1", False) for x in rk if not x["reused"]), sum(not x["reused"] for x in rk),
    mk["verified"], mk["verify_mismatch"]) for tier, (ms, rs, mk, rk) in T.items()))
out()
out("## The reach seeds (the budget-stopped crosses whose seed lies in N(question unit) and N(gold unit) of some of the 69 golds; all rebuilt)"); out()
out("| tier | seeds | with >= 1 skipped member | differ from stop | gained units median / max | skipped per cross median / max | CPU stop (Air) | CPU skip (Air) | ratio |")
out("|---|---|---|---|---|---|---|---|---|")
for tier in ("RUN", "WORD", "CHAR"):
    f = os.path.join(HERE, "raw", "fulllead_sents_%s_skip_mid_reach.jsonl" % tier)
    if tier == "RUN":
        sel = set(json.load(open(os.path.join(HERE, "reach_seeds_RUN.json"), encoding="utf-8")))
        m, r = load(os.path.join(HERE, "raw", "fulllead_sents_RUN_skip_mid.jsonl"))
        r = [x for x in r if x["seed"] in sel] if r else None
    else:
        m, r = load(f)
    if not r: continue
    ws = [x for x in r if x["n_skipped"] > 0]; diff = [x for x in r if set(x["units"]) != set(x["first_stop_units"])]
    g = [x["size"] - x["first_stop_size"] for x in diff]
    a_ = sum(x["stop_secs_here"] for x in r); b_ = sum(x["secs"] for x in r)
    out("| %s | %d | %d | %d (%.0f%%) | %s / %s | %s / %s | %.0f | %.0f | %.1f |" % (tier, len(r), len(ws), len(diff), 100.0 * len(diff) / len(r),
        st.median(g) if g else "-", max(g) if g else "-", st.median([x["n_skipped"] for x in ws]) if ws else "-",
        max([x["n_skipped"] for x in ws]) if ws else "-", a_, b_, b_ / a_))
open(os.path.join(HERE, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
