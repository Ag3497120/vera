"""G3-c4: the independent verifier (slide_place.verify_class_slide / verify_fixed_point_slide through counts_weight_fn, which reads the deeper z
edges by the counts' accessors) on real fulllead windows placed with z_deep "order", at the G3-c3 defaults: is every sampled member a stable
arrangement under the same rule, and do the record's strict counts equal the verifier's?
usage: verify_order.py [K=292] [SAMPLE=12] [OUT.md]        (the first K pair windows; SAMPLE members of every class swap-tested)"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide as SL            # noqa: E402
from verantyx.line3 import slide_place as SP      # noqa: E402
from verantyx.line3 import space as sp            # noqa: E402

FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
K = int(sys.argv[1]) if len(sys.argv) > 1 else 292
SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 12
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "results", "verify_order.md")
rows = sp.load_jsonl(FL)
space = sp.build_space(rows)
lines = ["# G3-c4: the independent verifier on z_deep order placements (first %d pair windows, %d members of each class swap-tested)" % (K, SAMPLE), ""]
for zd in ("order", "slide"):
    slide = SL.Slide(space, SL.default_spec(space, z_deep=zd), rows=rows)
    spec = SP.make_spec(slide)
    pws = [p for p in SP.place_windows(slide, "none") if len(p.window.sids) == 2][:K]
    t0 = time.time()
    stable = counts_eq = key_eq = deep_edges = rule_ok = 0
    for pw in pws:
        p = SP.place_window(slide, pw, spec)
        counts = slide.counts(pw.window, spec.scope)
        wfn = SP.counts_weight_fn(counts, spec.tier)
        arms = [n for n in SP.ARM_NAMES if n not in p.seatless_arms]
        sides = {it.token: it.side for it in p.items}
        rep = SP.verify_class_slide(wfn, p.crosses(), stability=spec.stability, arm_names=arms, sides=sides, z_reserved=True, sample=SAMPLE, centre_only=True,
                                    x_sides=list(p.member_x_side), own_Ls=list(p.member_L))
        frep = SP.verify_fixed_point_slide(wfn, p.cross, stability=spec.stability, arm_names=arms, sides=sides, z_reserved=True, x_side=p.member_x_side[0],
                                           centre_only=True, own_L=p.member_L[0])
        stable += rep.is_stable_class
        counts_eq += dict(frep.axis_improvable) == p.improving_moves_left and frep.strictly_stable == p.stable_strict
        tot, per = SP.cross_key(wfn, p.cross)
        key_eq += {a: list(per[a]) for a in SL.AXES} == p.axis_keys
        for r in p.seats:
            e = r["sources"]["edge"]
            if r["arm"] in ("+z", "-z") and e is not None:
                deep_edges += r["depth"] > 1
                rule_ok += (e.get("rule") == "order") if (zd == "order" and r["depth"] > 1) else ((e.get("rule") == "slide") if zd == "order" else "rule" not in e)
    lines.append("- z_deep %s: %d windows; verifier-stable classes %d; record strict counts = verifier's %d; representative's axis key = verifier's key %d; "
                 "z-arm edges read with their rule %d (of them deeper edges %d); %.0f s" % (zd, len(pws), stable, counts_eq, key_eq, rule_ok, deep_edges, time.time() - t0))
    print(lines[-1], flush=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
