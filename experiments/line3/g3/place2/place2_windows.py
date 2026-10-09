"""G3-c2 run: place the windows of fulllead (RUN, level mid) with the G3-c2 switches and report.
usage: place2_windows.py SET=pairs|first40|all  STABILITY  SEAT_KEY  SEAT_EMPTY  GROWTH  [LEVEL=mid] [PADDING=none] [VERIFY_SAMPLE=12]
  SET pairs = the 292 two-sentence windows; all = slide.place_windows(padding) (592); firstK = the first K of the sequence.
writes experiments/line3/g3/place2/<tag>.jsonl (one record per window, members left out, + timing and verifier) and <tag>.md.
Exact numbers only (shares as k/n and a rounded percentage by integer arithmetic); wall-clock seconds are the only floats and
are timing, not part of any record, spec or sha."""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide as SL            # noqa: E402
from verantyx.line3 import slide_place as SP      # noqa: E402
from verantyx.line3 import space as sp            # noqa: E402

FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
OUT = os.path.join(ROOT, "experiments/line3/g3/place2")


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


def z_arm_stats(p, w):
    """Units on the z arms of the representative; fillers = no z evidence on the inner edge; none = neither edge has it."""
    flat, L = p.members[0], p.L
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
    return on_z, fill, none


def main():
    a = sys.argv[1:]
    sel, stab, skey, sempty, growth = a[0], a[1], a[2], a[3], a[4]
    level = a[5] if len(a) > 5 else "mid"
    padding = a[6] if len(a) > 6 else "none"
    sample = int(a[7]) if len(a) > 7 else 12
    rows = sp.load_jsonl(FL)
    slide = SL.Slide(sp.build_space(rows), rows=rows)
    spec = SP.make_spec(slide, level=level, padding=padding, stability=stab, seat_key=skey, seat_empty_axis=sempty, growth=growth)
    pws = SP.place_windows(slide, padding)
    if sel == "pairs":
        pws = tuple(p for p in pws if len(p.window.sids) == 2)
    elif sel.startswith("first"):
        pws = pws[:int(sel[5:])]
    tag = "fulllead_RUN_%s_%s_%s_%s_%s_%s%s" % (level, padding, stab, skey, sempty, growth, "" if sel == "pairs" else "_" + sel)
    if sel == "pairs":
        tag += "_pairs292"
    os.makedirs(OUT, exist_ok=True)
    recs = []
    t_all = time.time()
    for pw in pws:
        t0 = time.time()
        p = SP.place_window(slide, pw, spec)
        dt = time.time() - t0
        counts = slide.counts(pw.window, spec.scope)
        wfn = SP.counts_weight_fn(counts, spec.tier)
        w = SP.ArmWeights.from_counts(counts, spec.tier)
        sides = {it.token: it.side for it in p.items}
        arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
        rep = SP.verify_class_slide(wfn, p.crosses(), stability=spec.stability, arm_names=arms, sides=sides,
                                    z_reserved=spec.growth == "z_reserved", sample=sample)
        d = p.doc(members=False)
        d["wall_s"] = dt
        d["verify"] = {"is_stable_class": rep.is_stable_class, "keys": rep.keys, "antichain": rep.antichain, "fixed": rep.members_fixed_points,
                       "closed": rep.closed, "swaps_tested": rep.swaps_tested, "members_checked": rep.members_checked,
                       "free": rep.no_unit_on_unseatable_arm}
        zu, zf, zn = z_arm_stats(p, w)
        d["z_arm_units"], d["z_arm_fillers"], d["z_arm_no_evidence"] = zu, zf, zn
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
    inside_n = sum(1 for d in recs if d["broke_on"] and d["broke_on"]["side"] in ("this", "both"))
    inside_n1 = sum(1 for d in recs if d["broke_on"] and d["broke_on"]["side"] == "next")
    st = [sum(d["tradeoffs"][k] if k != "improved_axis" else 0 for d in recs if d["tradeoffs"]) for k in
          ("moves_tested", "improve_one_worsen_another", "pareto_improving")]
    sl = [d for d in recs if d["self_links"]]
    sl_units = sum(len(d["self_links"]) for d in recs)
    sl_both = sum(1 for d in recs for x in d["self_links"] if x["both_seated"])
    sl_linked = sum(1 for d in recs for x in d["self_links"] if x["linked"])
    lines = ["# G3-c2 run: %s" % tag, "",
             "switches %s; spec sha256 %s (place), slide spec %s, scope %s, tier %s, padding %s, level %s %s" % (
                 json.dumps(spec.switches(), sort_keys=True), spec.sha256(), slide.spec.sha256(), spec.scope, spec.tier,
                 spec.padding, level, json.dumps(spec.budget.to_json_obj())), "",
             "windows %d (two-sentence %d, one-sentence %d); wall %.1f s in total, %.2f s per window (median %s s, max %.2f s)" % (
                 len(recs), len(two), len(lone), t_tot, t_tot / max(1, len(recs)),
                 "%.2f" % sorted(d["wall_s"] for d in recs)[len(recs) // 2], max(d["wall_s"] for d in recs)), "",
             "## N+1 got a seat (two-sentence windows; seats of sentence N+1)",
             "- strict (a seated unit that is in N+1 and not in N): %s" % pct(sum(d["next_seat"]["strict"] for d in two), len(two)),
             "- loose (a seated seat of sentence N+1, shared units' N+1 seats included): %s" % pct(sum(d["next_seat"]["loose"] for d in two), len(two)),
             "- windows that have at least one unit only in N+1: %s" % pct(sum(d["next_seat"]["exclusive_units"] > 0 for d in two), len(two)),
             "- seated N+1 seats / N+1 seats in the windows: %s" % pct(sum(d["next_seat"]["loose_seated"] for d in two), sum(d["next_seat"]["loose_units"] for d in two)), "",
             "## stop reasons"] + ["- %s: %d" % (k, v) for k, v in sorted(stops.items())] + ["",
             "## sizes",
             "- windows that stopped inside sentence N: %d; inside N+1: %d; never stopped: %d" % (inside_n, inside_n1, sum(1 for d in recs if not d["broke_on"])),
             "- of the two-sentence windows: stopped inside N %d, inside N+1 %d" % (
                 sum(1 for d in two if d["broke_on"] and d["broke_on"]["side"] in ("this", "both")),
                 sum(1 for d in two if d["broke_on"] and d["broke_on"]["side"] == "next")),
             "- stop reasons of the budget stops: " + ", ".join("%s %d" % (r, sum(1 for d in recs if d["broke_on"] and d["broke_on"]["reason"] == r))
                                                                for r in ("max_class", "max_states", "max_moves", "no_seat")),
             "- units(seats) in the window (median): %s; seated (median): %s; L (median): %s, max %d" % (
                 med([len(d["order_log"]) for d in recs]), med([d["size"] for d in recs]), med([d["L"] for d in recs]), max(d["L"] for d in recs)),
             "- class size: median %s, max %d; windows with class size 1: %d" % (
                 med([d["class_size"] for d in recs]), max(d["class_size"] for d in recs), sum(d["class_size"] == 1 for d in recs)),
             "- classes larger than max_class: %d windows" % sum(d["class_size"] > d["budget"]["max_class"] for d in recs),
             "- seated fraction of the seats: %d of %d" % (sum(d["size"] for d in recs), sum(len(d["order_log"]) for d in recs)),
             "- windows whose final class holds more than one per-axis key: %d (keys per window: median %s, max %d)" % (
                 sum(d["axis_splits"] > 1 for d in recs), med([d["axis_splits"] for d in recs]), max(d["axis_splits"] for d in recs)),
             "- per-axis key of the representative (sum over windows): x n=%d, y n=%d, z n=%d; summed key n=%d" % (
                 tuple(sum(d["axis_keys"][ax][0] for d in recs) for ax in ("x", "y", "z")) + (sum(d["key"][0] for d in recs),)),
             "- z-arm units (representative): %d, without z evidence on their inner edge: %d, on neither edge: %d" % (
                 sum(d["z_arm_units"] for d in recs), sum(d["z_arm_fillers"] for d in recs), sum(d["z_arm_no_evidence"] for d in recs)),
             "- windows with z evidence: %d; seatless arms (windows with at least one arm denied beyond y): %d" % (
                 sum(d["axis_evidence"]["z"] for d in recs), sum(1 for d in recs if set(d["seatless_arms"]) - {"+y", "-y"})),
             "- units with two seats (windows %d, units %d): both seated %d, the two seats directly linked by a cross edge %d" % (
                 len(sl), sl_units, sl_both, sl_linked),
             "- moves of the representative: tested %d, improving one axis and worsening another (not taken) %d, Pareto-improving "
             "(must be 0) %d" % tuple(st), "",
             "## verification (independent verifier; swaps of %d evenly spread members per class, keys / closure / legality of all)" % sample,
             "- classes that are stable (every checked member a fixed point, closed, antichain of keys, centre non-empty, no seat on a seatless arm or against the reservation): %s" % pct(
                 sum(d["verify"]["is_stable_class"] for d in recs), len(recs))]
    with open(os.path.join(OUT, tag + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
