"""p5_compare: L1-L3 of W3-a (eval_runs 016-018, placement full/r2b/run1) next to the
last measurement of each later placement (W3-a2).  Every row is printed -- up AND down.

    p5_compare.py [--out artifacts/w3-a/p5_compare.json]

The numbers are read from artifacts/w3-a/eval_runs/*/summary.json (the measurement
script's own output); nothing is typed in by hand.
"""
import argparse
import glob
import json
import os
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
A = W + "/artifacts/w3-a"
B = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/"
PLACEMENTS = [("W3-a (r2b)", "full/r2b/run1"), ("W3-a2 F1-F6 only (r3c)", "full/r3c/run1"),
              ("W3-a2 round 1 (r4, before the review)", "full/r4/run1"),
              ("W3-a2 final (r5)", "full/r5/run1")]
# (label, extractor, target, kind): kind 'max' = target is a lower bound, 'min' = an upper bound
ITEMS = [
    ("L1 coverage (tokens)", "l1", lambda s: (s["token_cover"], s["tokens"]), 0.90, "max", False),
    ("L2 correct (direct)", "l2", lambda s: (s["correct_direct"], s["n"]), 0.85, "max", False),
    ("L2 wrong (direct)", "l2", lambda s: (s["wrong_single_direct"], s["n"]), 0.08, "min", True),
    ("L2 trap wrong (direct)", "l2", lambda s: (s["trap_wrong_single_direct"], s["trap_n"]), 0.05, "min", True),
    ("L3 correct", "l3", lambda s: (s["correct"], s["typed_n"]), 0.65, "max", False),
    ("L3 wrong", "l3", lambda s: (s["wrong"], s["typed_n"]), 0.15, "min", True),
    ("L3 returns a type for an unknown word", "l3",
     lambda s: (s["returned_type_among_unknown"], s["unknown_n"]), 0.20, "min", True),
]


def last_summary(cmd, rel):
    path = B + rel
    best = None
    for d in sorted(glob.glob(A + "/eval_runs/[0-9][0-9][0-9]")):
        sp = d + "/summary.json"
        if not os.path.exists(sp):
            continue
        s = json.load(open(sp, encoding="utf-8"))
        if s["command"][0] == cmd and s["placement"].rstrip("/") == path.rstrip("/"):
            best = (os.path.basename(d), s)
    return best


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=A + "/p5_compare.json")
    args = ap.parse_args(argv)
    rows = []
    for label, cmd, ex, target, kind, guard in ITEMS:
        row = {"item": label, "target": target, "target_kind": "at least" if kind == "max" else "at most",
               "approval_guard": guard, "by_placement": {}}
        for pname, rel in PLACEMENTS:
            got = last_summary(cmd, rel)
            if got is None:
                row["by_placement"][pname] = None
                continue
            seq, s = got
            n, d = ex(s)
            row["by_placement"][pname] = {"count": n, "of": d, "rate": round(n / d, 4), "run": seq}
        base = row["by_placement"][PLACEMENTS[0][0]]
        for pname, _ in PLACEMENTS[1:]:
            cur = row["by_placement"][pname]
            if cur and base:
                dc = cur["count"] - base["count"]
                good_up = kind == "max"
                row["by_placement"][pname]["delta_count_vs_w3a"] = dc
                row["by_placement"][pname]["direction"] = (
                    "same" if dc == 0 else ("better" if (dc > 0) == good_up else "worse"))
                if guard:
                    row["by_placement"][pname]["not_worse"] = dc <= 0
        rows.append(row)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"placements": dict(PLACEMENTS), "rows": rows}, f, ensure_ascii=False, indent=1,
                  sort_keys=True)
        f.write("\n")
    for r in rows:
        cells = []
        for pname, _ in PLACEMENTS:
            c = r["by_placement"][pname]
            cells.append("-" if c is None else "%d/%d=%.4f%s" % (
                c["count"], c["of"], c["rate"], "" if "direction" not in c else " (%+d %s)" % (
                    c["delta_count_vs_w3a"], c["direction"])))
        print("%-42s target %s %.2f | %s" % (r["item"], r["target_kind"], r["target"], " | ".join(cells)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
