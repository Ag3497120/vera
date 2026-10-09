"""G3-c3 run: place the windows of fulllead (RUN, level mid) with the G3-c3 switches and report.
usage: place3_windows.py SET=pairs|first40|allK|all  CENTRE_SCOPE(n|both)  ARM_CAP(budget|x)  JUDGEMENT(strict|pareto)  [LEVEL=mid] [PADDING=none] [VERIFY_SAMPLE=12]
  SET pairs = the 292 two-sentence windows; all = slide.place_windows(padding) (592); firstK = the first K of the sequence.
  The G3-c2 switches are the owner's: per_axis, unit_sid, allow, z_reserved.
writes experiments/line3/g3/place3/<tag>.jsonl (one record per window, members left out, + timing and verifier) and <tag>.md.
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
OUT = os.path.join(ROOT, "experiments/line3/g3/place3")


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


def seat_stats(p):
    """From the representative's seats (record.seats): the z-arm seats by arm and depth (1 = next to the centre, deeper) with and
    without z evidence on their inner edge; the cross edges between the two sentences (different sid at the ends) and, of
    those, the ones that carry a count."""
    zs = {}
    real = real_ev = 0
    for s in p.seats:
        e = s["sources"]["edge"]
        if e is not None and e["with"]["sid"] != s["sid"]:
            real += 1
            real_ev += e["n"] > 0
        if s["arm"] in ("+z", "-z"):
            k = (s["arm"], "d1" if s["depth"] == 1 else "deeper")
            tot, ev = zs.get(k, (0, 0))
            zs[k] = (tot + 1, ev + (e is not None and e["n"] > 0))
    return zs, real, real_ev


def main():
    a = sys.argv[1:]
    sel, cs, cap, jud = a[0], a[1], a[2], a[3]
    level = a[4] if len(a) > 4 else "mid"
    padding = a[5] if len(a) > 5 else "none"
    sample = int(a[6]) if len(a) > 6 else 12
    rows = sp.load_jsonl(FL)
    slide = SL.Slide(sp.build_space(rows), rows=rows)
    spec = SP.make_spec(slide, level=level, padding=padding, centre_scope=cs, arm_cap=cap, stability_judgement=jud)
    pws = SP.place_windows(slide, padding)
    if sel == "pairs":
        pws = tuple(p for p in pws if len(p.window.sids) == 2)
    elif sel.startswith("first"):
        pws = pws[:int(sel[5:])]
    tag = "fulllead_RUN_%s_%s_%s_centre-%s_cap-%s_%s%s" % (level, padding, "per_axis_unit_sid_allow_z_reserved", cs, cap, jud, "" if sel == "pairs" else "_" + sel)
    if sel == "pairs":
        tag += "_pairs292"
    os.makedirs(OUT, exist_ok=True)
    recs = []
    t_all = time.time()
    zres = spec.growth == "z_reserved"
    for pw in pws:
        t0 = time.time()
        p = SP.place_window(slide, pw, spec)
        dt = time.time() - t0
        counts = slide.counts(pw.window, spec.scope)
        wfn = SP.counts_weight_fn(counts, spec.tier)
        sides = {it.token: it.side for it in p.items}
        arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
        xs = list(p.member_x_side)
        rep = SP.verify_class_slide(wfn, p.crosses(), stability=spec.stability, arm_names=arms, sides=sides, z_reserved=zres, sample=sample,
                                    centre_only=zres and spec.centre_scope == "both", x_sides=xs, own_Ls=list(p.member_L))
        d = p.doc(members=False)
        # the independent verifier's strict count of the representative against the record's
        frep = SP.verify_fixed_point_slide(wfn, p.cross, stability=spec.stability, arm_names=arms, sides=sides, z_reserved=zres,
                                           x_side=xs[0], centre_only=zres and spec.centre_scope == "both", own_L=p.member_L[0])
        d["wall_s"] = dt
        d["verify"] = {"is_stable_class": rep.is_stable_class, "keys": rep.keys, "antichain": rep.antichain, "fixed": rep.members_fixed_points,
                       "closed": rep.closed, "swaps_tested": rep.swaps_tested, "members_checked": rep.members_checked,
                       "free": rep.no_unit_on_unseatable_arm,
                       "strict_counts_agree": dict(frep.axis_improvable) == d["improving_moves_left"] and frep.strictly_stable == d["stable_strict"]}
        zs, real, real_ev = seat_stats(p)
        d["z_seat_stats"] = {"%s %s" % k: list(v) for k, v in sorted(zs.items())}
        d["real_edges"], d["real_edges_with_count"] = real, real_ev
        d["members_by_centre_sentence"] = {"this": xs.count("this"), "next": xs.count("next")}
        recs.append(d)
    t_tot = time.time() - t_all
    with open(os.path.join(OUT, tag + ".jsonl"), "w", encoding="utf-8") as f:
        for d in recs:
            f.write(json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str) + "\n")
    two = [d for d in recs if len(d["window"]["sids"]) == 2]
    lone = [d for d in recs if len(d["window"]["sids"]) == 1]
    # stops relative to the centre's sentence of the representative
    inside_c = inside_o = capped = never = other_budget = 0
    for d in recs:
        b = d["broke_on"]
        if d["stop"] == "cap":
            capped += 1
        elif b is None:
            never += 1
        elif b["side"] == d["centre_sentence"] or b["side"] == "both":
            inside_c += 1
        else:
            inside_o += 1
    zk = {}
    for d in recs:
        for k, (tot, ev) in d["z_seat_stats"].items():
            t0_, e0_ = zk.get(k, (0, 0))
            zk[k] = (t0_ + tot, e0_ + ev)
    cc = {}
    for d in two:
        c = d["centre_search"]["choice"]
        cc[c] = cc.get(c, 0) + 1
    unst = {}
    for d in recs:
        if d["unstable"]:
            for ax in d["unstable"]["axes"]:
                unst[ax] = unst.get(ax, 0) + 1
    lines = ["# G3-c3 run: %s" % tag, "",
             "switches %s + %s; spec sha256 %s (place), slide spec %s, scope %s, tier %s, padding %s, level %s %s" % (
                 json.dumps(spec.switches(), sort_keys=True), json.dumps(spec.switches3(), sort_keys=True), spec.sha256(), slide.spec.sha256(),
                 spec.scope, spec.tier, spec.padding, level, json.dumps(spec.budget.to_json_obj())), "",
             "windows %d (two-sentence %d, one-sentence %d); wall %.1f s in total, %.2f s per window (median %s s, max %.2f s)" % (
                 len(recs), len(two), len(lone), t_tot, t_tot / max(1, len(recs)),
                 "%.2f" % sorted(d["wall_s"] for d in recs)[len(recs) // 2], max(d["wall_s"] for d in recs)), "",
             "## the centre (representative; two-sentence windows %d)" % len(two),
             "- centre in N: %d, in N+1: %d (of the one-sentence windows the centre is in N: %d)" % (
                 sum(d["centre_sentence"] == "this" for d in two), sum(d["centre_sentence"] == "next" for d in two), sum(d["centre_sentence"] == "this" for d in lone)),
             "- choice between the two growths (two-sentence windows): " + ", ".join("%s %d" % kv for kv in sorted(cc.items())),
             "- class members with the centre in N / in N+1 (sum over windows): %d / %d" % (
                 sum(d["members_by_centre_sentence"]["this"] for d in recs), sum(d["members_by_centre_sentence"]["next"] for d in recs)),
             "## the other sentence (the one the z arms hold) got a seat (two-sentence windows)",
             "- strict (a seated unit that is only in the other sentence): %s" % pct(sum(d["other_seat"]["strict"] for d in two), len(two)),
             "- loose (a seated seat of the other sentence, shared units' seats included): %s" % pct(sum(d["other_seat"]["loose"] for d in two), len(two)),
             "- seated seats of the other sentence / its seats in the windows: %s" % pct(sum(d["other_seat"]["loose_seated"] for d in two), sum(d["other_seat"]["loose_units"] for d in two)),
             "- (N+1's own strict share, for comparison with G3-c2: %s)" % pct(sum(d["next_seat"]["strict"] for d in two), len(two)), "",
             "## stops (representative's growth; relative to the centre's sentence)",
             "- stopped inside the centre's sentence: %d; inside the other sentence: %d; arm_cap x (units of the other sentence unseated, no budget stop): %d; never stopped: %d" % (
                 inside_c, inside_o, capped, never),
             "- stop reasons of the budget stops: " + ", ".join("%s %d" % (r, sum(1 for d in recs if d["stop"] == "budget" and d["broke_on"]["reason"] == r))
                                                                for r in ("max_class", "max_states", "max_moves", "no_seat")),
             "- unseated by arm_cap x: windows %d, units %d" % (sum(1 for d in recs if d["unseated"]), sum(len(d["unseated"]) for d in recs)), "",
             "## z-arm seats of the representative with z evidence on their inner edge (evidenced / seats)"] + [
             "- %s: %s" % (k, pct(e, t)) for k, (t, e) in sorted(zk.items())] + [
             "- all z-arm seats: %s" % pct(sum(e for t, e in zk.values()), sum(t for t, e in zk.values())),
             "- real N<->N+1 edges per window (cross edges whose ends are seats of different sentences; two-sentence windows): median %s, max %d; of them with a count > 0: median %s, max %d" % (
                 med([d["real_edges"] for d in two]), max([d["real_edges"] for d in two] or [0]),
                 med([d["real_edges_with_count"] for d in two]), max([d["real_edges_with_count"] for d in two] or [0])),
             "- windows with exactly one / none / more than one real N<->N+1 edge: %d / %d / %d" % (
                 sum(d["real_edges"] == 1 for d in two), sum(d["real_edges"] == 0 for d in two), sum(d["real_edges"] > 1 for d in two)), "",
             "## stability",
             "- representative strictly stable (no single legal move improves any axis): %s; marked unstable (typed %s): %d; by axis improvable: %s" % (
                 pct(sum(d["stable_strict"] for d in recs), len(recs)), "UNSTABLE_AXIS_IMPROVABLE" if jud == "strict" else "UNSTABLE_PARETO_IMPROVABLE",
                 sum(1 for d in recs if d["unstable"]), json.dumps(unst, sort_keys=True)),
             "- representative Pareto stable: %s; the record's strict counts equal the independent verifier's (axis_improvable) on %s" % (
                 pct(sum(d["judgement"]["stable_pareto"] for d in recs), len(recs)), pct(sum(d["verify"]["strict_counts_agree"] for d in recs), len(recs))),
             "- members strictly stable (sum over windows): %s; windows with at least one strictly stable member: %s" % (
                 pct(sum(d["judgement"]["members_stable_strict"] for d in recs), sum(d["judgement"]["members_total"] for d in recs)),
                 pct(sum(d["judgement"]["first_stable_strict_member"] is not None for d in recs), len(recs))), "",
             "## sizes",
             "- class size: median %s, max %d; windows with class size 1: %d; classes larger than max_class: %d windows" % (
                 med([d["class_size"] for d in recs]), max(d["class_size"] for d in recs), sum(d["class_size"] == 1 for d in recs),
                 sum(d["class_size"] > d["budget"]["max_class"] for d in recs)),
             "- L: median %s, max %d" % (med([d["L"] for d in recs]), max(d["L"] for d in recs)),
             "- seats in the window (median): %s; seated by the representative (median): %s; seated fraction: %d of %d" % (
                 med([len(d["order_log"]) for d in recs]), med([d["size"] for d in recs]), sum(d["size"] for d in recs), sum(len(d["order_log"]) for d in recs)),
             "- windows whose final class holds more than one per-axis key: %d (keys per window: median %s, max %d)" % (
                 sum(d["axis_splits"] > 1 for d in recs), med([d["axis_splits"] for d in recs]), max(d["axis_splits"] for d in recs)),
             "- per-axis key of the representative (sum over windows): x n=%d, y n=%d, z n=%d" % tuple(sum(d["axis_keys"][ax][0] for d in recs) for ax in ("x", "y", "z")),
             "",
             "## verification (independent verifier; swaps of %d evenly spread members per class, keys / closure / legality of all)" % sample,
             "- classes that are stable (every checked member a Pareto fixed point under the member's own reservation, closed, antichain, centre non-empty, no seat against the reservation): %s" % pct(
                 sum(d["verify"]["is_stable_class"] for d in recs), len(recs))]
    with open(os.path.join(OUT, tag + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
