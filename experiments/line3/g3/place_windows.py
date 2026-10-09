"""G3-c small run: place the first K windows of fulllead (RUN, level mid) with the per-axis key and report.
usage: place_windows.py [K=40] [LEVEL=mid] [PADDING=none] [PAIRS=0]   (PAIRS=1: the first K two-sentence windows instead)
writes experiments/line3/g3/place/<tag>.jsonl (one record per window, members left out, + timing, verifier, line version)
and place/<tag>.md (the summary).  Exact numbers only: shares are printed as k/n and a rounded percentage by integer arithmetic."""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide as SL            # noqa: E402
from verantyx.line3 import slide_place as SP      # noqa: E402
from verantyx.line3 import space as sp            # noqa: E402

FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
OUT = os.path.join(ROOT, "experiments/line3/g3/place")


def pct(a, b):
    return "n/a" if b == 0 else "%d/%d = %d.%d%%" % (a, b, (1000 * a // b) // 10, (1000 * a // b) % 10)


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    if n % 2:
        return xs[n // 2]
    t = xs[n // 2 - 1] + xs[n // 2]
    return t // 2 if t % 2 == 0 else "%d.5" % (t // 2)


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    level = sys.argv[2] if len(sys.argv) > 2 else "mid"
    padding = sys.argv[3] if len(sys.argv) > 3 else "none"
    pairs_only = len(sys.argv) > 4 and sys.argv[4] == "1"
    rows = sp.load_jsonl(FL)
    space = sp.build_space(rows)
    slide = SL.Slide(space, rows=rows)
    spec = SP.make_spec(slide, level=level, padding=padding)
    lspec = SP.make_spec(slide, level=level, padding=padding, mode="line")
    pws = SP.place_windows(slide, padding)
    if pairs_only:
        pws = tuple(p for p in pws if len(p.window.sids) == 2)
    pws = pws[:K]
    tag = "fulllead_RUN_%s_%s_%s%d" % (level, padding, "pairs" if pairs_only else "first", K)
    os.makedirs(OUT, exist_ok=True)
    recs = []
    t_all = time.time()
    for pw in pws:
        t0 = time.time()
        p = SP.place_window(slide, pw, spec)
        dt = time.time() - t0
        counts = slide.counts(pw.window, spec.scope)
        wfn = SP.counts_weight_fn(counts, spec.tier)
        rep = SP.verify_class_slide(wfn, p.crosses())
        w = SP.ArmWeights.from_counts(counts, spec.tier)
        q = SP.place_window(slide, pw, lspec)
        lfp = SP.verify_fixed_point_slide(wfn, q.cross)
        # units on the z arms of the representative and the weight of their edge (0 = a filler with no z evidence)
        flat, L = p.members[0], p.L
        # (review) z_arm_fillers = the inner edge has no z evidence (as built); z_arm_no_evidence = neither edge of the unit has
        on_z = fill = none = 0
        for a in (4, 5):
            leg = flat[1 + a * L: 1 + (a + 1) * L]
            for k, u in enumerate(leg):
                if u is None:
                    continue
                inner = leg[k + 1] if k + 1 < L else flat[0]
                outer = leg[k - 1] if k > 0 else None
                on_z += 1
                fill += w(a, u, inner)[0] == 0
                none += w(a, u, inner)[0] == 0 and w(a, outer, u)[0] == 0
        d = p.doc(members=False)
        d["wall_s"] = dt
        d["verify"] = {"is_stable_class": rep.is_stable_class, "one_key": rep.one_key, "fixed": rep.members_fixed_points,
                       "closed": rep.closed, "swaps_tested": rep.swaps_tested}
        d["line"] = {"key": list(q.key), "is_fixed_point": lfp.is_fixed_point, "swaps_improving": lfp.swaps_improving,
                     "swaps_equal_key_different": lfp.swaps_equal_key_different, "size": q.size, "L": q.L,
                     "key_search": list(p.key), "line_key_below_search": q.key < p.key}
        d["z_arm_units"] = on_z
        d["z_arm_fillers"] = fill
        d["z_arm_no_evidence"] = none
        recs.append(d)
    t_tot = time.time() - t_all
    with open(os.path.join(OUT, tag + ".jsonl"), "w", encoding="utf-8") as f:
        for d in recs:
            f.write(json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str) + "\n")
    two = [d for d in recs if len(d["window"]["sids"]) == 2]
    lone = [d for d in recs if len(d["window"]["sids"]) == 1]
    stops = {}
    for d in recs:
        k = "%d-sentence %s%s" % (len(d["window"]["sids"]), d["stop"], "" if d["broke_on"] is None else " (%s, inside %s)" % (
            d["broke_on"]["reason"], d["broke_on"]["side"]))
        stops[k] = stops.get(k, 0) + 1
    lines = ["# G3-c small run: %s" % tag, "",
             "spec sha256 %s (place), slide spec %s, scope %s, tier %s, padding %s, level %s %s" % (
                 spec.sha256(), slide.spec.sha256(), spec.scope, spec.tier, spec.padding, level, json.dumps(spec.budget.to_json_obj())), "",
             "windows %d (two-sentence %d, one-sentence %d); wall %.1f s in total, %.2f s per window (median %s s, max %.2f s)" % (
                 len(recs), len(two), len(lone), t_tot, t_tot / max(1, len(recs)),
                 "%.2f" % sorted(d["wall_s"] for d in recs)[len(recs) // 2], max(d["wall_s"] for d in recs)), "",
             "## N+1 got a seat (two-sentence windows)",
             "- strict (a seated unit that is in N+1 and not in N): %s" % pct(sum(d["next_seat"]["strict"] for d in two), len(two)),
             "- loose (a seated unit that is in N+1, shared units included): %s" % pct(sum(d["next_seat"]["loose"] for d in two), len(two)),
             "- windows that have at least one unit only in N+1: %s" % pct(sum(d["next_seat"]["exclusive_units"] > 0 for d in two), len(two)),
             "- of those, strict seat: %s" % pct(sum(d["next_seat"]["strict"] for d in two if d["next_seat"]["exclusive_units"] > 0),
                                                 sum(d["next_seat"]["exclusive_units"] > 0 for d in two)), "",
             "## stop reasons"] + ["- %s: %d" % (k, v) for k, v in sorted(stops.items())] + ["",
             "## sizes (units seated / units in the window; class sizes)",
             "- units in the window (median): %s; seated (median): %s; L (median): %s" % (
                 med([len(d["order_log"]) for d in recs]), med([d["size"] for d in recs]), med([d["L"] for d in recs])),
             "- class size: median %s, max %d; windows with class size 1: %d" % (
                 med([d["class_size"] for d in recs]), max(d["class_size"] for d in recs), sum(d["class_size"] == 1 for d in recs)),
             "- windows that stopped inside sentence N: %d; inside N+1: %d; never stopped: %d" % (
                 sum(1 for d in recs if d["broke_on"] and d["broke_on"]["side"] in ("this", "both")),
                 sum(1 for d in recs if d["broke_on"] and d["broke_on"]["side"] == "next"),
                 sum(1 for d in recs if not d["broke_on"])),
             "- seated fraction of the units: %d of %d units" % (sum(d["size"] for d in recs), sum(len(d["order_log"]) for d in recs)),
             "- per-axis key split of the representative (sum over windows): x n=%d, y n=%d, z n=%d" % tuple(
                 sum(d["axis_key"][a][0] for d in recs) for a in ("x", "y", "z")),
             "- windows whose class holds more than one per-axis split (same total key): %d" % sum(d["axis_splits"] > 1 for d in recs),
             "- classes larger than max_class (the terminals of the best key are not counted against max_class, as in "
             "placement._settle): %d windows, %d stable steps" % (
                 sum(d["class_size"] > d["budget"]["max_class"] for d in recs),
                 sum(1 for d in recs for st in d["steps"] if st["class_size"] and st["class_size"] > d["budget"]["max_class"])),
             "- units on z arms (representative): %d, of which fillers with no z evidence on their inner edge: %d, on neither "
             "edge: %d" % (sum(d["z_arm_units"] for d in recs), sum(d["z_arm_fillers"] for d in recs),
                           sum(d["z_arm_no_evidence"] for d in recs)), "",
             "## verification (independent verifier)",
             "- classes that are stable (one key, every member a fixed point, closed, no unit on a y arm): %s" % pct(
                 sum(d["verify"]["is_stable_class"] for d in recs), len(recs)),
             "- diagnostic LINE (no search; x by sentence position, -z by next-sentence position): fixed point of single swaps: %s; "
             "key below the search's: %s; equal-key different arrangements one swap away (median): %s" % (
                 pct(sum(d["line"]["is_fixed_point"] for d in recs), len(recs)),
                 pct(sum(d["line"]["line_key_below_search"] for d in recs), len(recs)),
                 med([d["line"]["swaps_equal_key_different"] for d in recs])),
             "- the line seats every unit, the search only those before its stop: compared on the windows where both seat the same "
             "units (search exhausted, %d): line key below the search's %d, equal %d, above %d" % (
                 sum(d["line"]["size"] == d["size"] for d in recs),
                 sum(d["line"]["size"] == d["size"] and d["line"]["key"] < d["line"]["key_search"] for d in recs),
                 sum(d["line"]["size"] == d["size"] and d["line"]["key"] == d["line"]["key_search"] for d in recs),
                 sum(d["line"]["size"] == d["size"] and d["line"]["key"] > d["line"]["key_search"] for d in recs)),
             "- z self-links on a seated unit (n_z(u,u) > 0; counted, a unit has one seat): %d windows, %d units" % (
                 sum(bool(d["z_self"]) for d in recs), sum(len(d["z_self"]) for d in recs))]
    with open(os.path.join(OUT, tag + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
