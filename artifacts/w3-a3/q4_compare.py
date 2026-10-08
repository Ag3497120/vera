"""W3-a3 Q4: the W3-a frozen measurements (L1, L2, L3, predicates, speed) of a placement beside R5's.

  q4_compare.py --placement DIR [--eval-runs artifacts/w3-a3/eval_runs]

Reads the LATEST numbered run of each of l1 l2 l3 pred l5 that ``measure_w3a3.py`` made for DIR, and R5's
``artifacts/w3-a/eval_runs/041..045/summary.json`` (read only; nothing is copied by hand).  Prints every
number that went up and every number that went down, then ONE last line with the four acceptance
booleans (the right-hand sides are R5's values, read from 041 / 042)."""
import argparse
import json
import os
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
R5 = {"l2": "041", "l3": "042", "l1": "043", "pred": "044", "l5": "045"}


def latest(eval_runs, cmd, placement):
    best = None
    for d in sorted(os.listdir(eval_runs)):
        p = os.path.join(eval_runs, d, "summary.json")
        if not os.path.exists(p):
            continue
        s = json.load(open(p, encoding="utf-8"))
        if s.get("command", [None])[0] == cmd and os.path.abspath(s.get("placement", "")) == os.path.abspath(placement):
            best = (d, s)
    return best


def flat(prefix, o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            flat(prefix + "." + k if prefix else k, v, out)
    elif isinstance(o, bool):
        return
    elif isinstance(o, (int, float)):
        out[prefix] = o


KEYS = {
    "l2": ["n", "direct_n", "correct_direct", "correct_rate", "wrong_single_direct", "wrong_single_rate",
           "trap_n", "trap_wrong_single_direct", "trap_wrong_single_rate", "non_direct", "by_state"],
    "l3": ["typed_n", "unknown_n", "correct", "correct_rate", "wrong", "wrong_rate", "unknown_among_typed",
           "returned_type_among_unknown", "returned_type_rate"],
    "l1": ["sentences", "tokens", "token_cover", "token_cover_rate", "distinct", "distinct_cover",
           "distinct_cover_rate", "by_pos_rate", "placed_direct_headwords", "tokens_by_origin", "tokens_by_basis",
           "tokens_typed_by_basis"],
    "pred": ["all", "non_seed", "non_seed_now", "seed_now"],
    "l5": ["n_queries", "mean_ms", "p95_ms", "max_ms", "median_ms", "placement_bytes"],
}


def compute(placement, eval_runs):
    """Everything ``main`` prints, as data: (header lines, ups, downs, same, extra, last) or None + a message."""
    r5_root = os.path.join(W, "artifacts/w3-a/eval_runs")
    r5 = {c: json.load(open(os.path.join(r5_root, d, "summary.json"), encoding="utf-8")) for c, d in R5.items()}
    new, runs = {}, {}
    for c in R5:
        got = latest(eval_runs, c, placement)
        if got is None:
            return None, "MISSING run of %s for %s (run measure_w3a3.py %s --placement ...)" % (c, placement, c)
        runs[c], new[c] = got
    head = ["R5 placement content_sha256: %s" % r5["l2"]["content_sha256"],
            "new placement: %s content_sha256: %s" % (placement, new["l2"]["content_sha256"]),
            "runs used: " + json.dumps(runs)]
    ups, downs, same = [], [], 0
    for c in R5:
        old, cur = {}, {}
        flat("", {k: r5[c][k] for k in KEYS[c] if k in r5[c]}, old)
        flat("", {k: new[c][k] for k in KEYS[c] if k in new[c]}, cur)
        for k in sorted(set(old) | set(cur)):
            o, n = old.get(k), cur.get(k)
            if o == n:
                same += 1
                continue
            (ups if (n or 0) > (o or 0) else downs).append(
                "%s.%s: R5 %s -> new %s (%+g)" % (c, k, o, n, (n or 0) - (o or 0)))
    l2o, l2n, l3o, l3n = r5["l2"], new["l2"], r5["l3"], new["l3"]
    extra = {"L2 correct not lower": l2n["correct_direct"] >= l2o["correct_direct"],
             "L1 token cover not lower": new["l1"]["token_cover"] >= r5["l1"]["token_cover"],
             "L3 correct not lower": l3n["correct"] >= l3o["correct"],
             "L3 leaks (direct, not notation) none": not l3n["leaks_direct_not_notation"]}
    last = {"L2 wrong<=%d" % l2o["wrong_single_direct"]: l2n["wrong_single_direct"] <= l2o["wrong_single_direct"],
            "trap<=%d" % l2o["trap_wrong_single_direct"]: l2n["trap_wrong_single_direct"] <= l2o["trap_wrong_single_direct"],
            "L3 wrong<=%d" % l3o["wrong"]: l3n["wrong"] <= l3o["wrong"],
            "unk_returned<=%d" % l3o["returned_type_among_unknown"]:
                l3n["returned_type_among_unknown"] <= l3o["returned_type_among_unknown"]}
    return {"head": head, "ups": ups, "downs": downs, "same": same, "extra": extra, "last": last,
            "r5": r5, "new": new, "runs": runs}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--eval-runs", default=os.path.join(W, "artifacts/w3-a3/eval_runs"))
    a = ap.parse_args()
    r, err = compute(a.placement, a.eval_runs)
    if err:
        print(err)
        return 2
    print("\n".join(r["head"]))
    print("\n== went UP (%d) ==" % len(r["ups"]))
    print("\n".join(r["ups"]))
    print("\n== went DOWN (%d) ==" % len(r["downs"]))
    print("\n".join(r["downs"]))
    print("\n(unchanged numbers: %d)" % r["same"])
    print("\nreported alongside: " + json.dumps(r["extra"]))
    print(json.dumps(r["last"], ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
