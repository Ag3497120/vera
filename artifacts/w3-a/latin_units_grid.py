"""M2 (review r1): the Latin-script units the counter table keeps, for each candidate of
(counter_latin_share_pct, counter_latin_numerals_min).  The selection rule was written in
DECISIONS.md 6-1 BEFORE this was run.  Reads only an extraction stage (no frozen data).

usage: py.sh latin_units_grid.py --stage <stage.pkl> --out <txt>"""
import argparse
import json
import pickle
import sys
from collections import Counter

sys.path.insert(0, "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S")
from tools import build_coarse_placement as b  # noqa: E402
from verantyx import coarse_types as ct  # noqa: E402

Q = ["km", "kg", "GHz", "ms", "MiB", "mm"]                    # real units seen in the r4 table
N = ["AND", "URL", "and", "app", "for", "has", "in", "is", "mas", "mis", "of", "sum", "xx"]
UNDECIDED = ["em"]                                             # also a CSS unit: only reported
THETAS = (10, 20, 33)
KS = (5, 6, 8, 12)      # 6 added AFTER the first 9-candidate run (DECISIONS 6-2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ex = pickle.load(open(a.stage, "rb"))
    assert "counter_nums" in ex, "stage without counter_nums"
    base_cfg = dict(ct.DEFAULT_CONFIG)
    lines = []
    P = lines.append
    P("stage %s" % a.stage)
    P("Q (real units) %s | N (non-units) %s | undecided %s" % (Q, N, UNDECIDED))
    # the r4 situation: no rule
    off = dict(base_cfg, counter_latin_share_pct=0, counter_latin_numerals_min=0)
    t0 = sorted(u for u, _n in b.learn_counters(ex, off) if u.isascii())
    P("no rule (share 0, numerals 0): %d Latin units: %s" % (len(t0), t0))
    P("   Q kept %s | N kept %s" % ([u for u in Q if u in t0], [u for u in N if u in t0]))
    rows = []
    for th in THETAS:
        for k in KS:
            cfg = dict(base_cfg, counter_latin_share_pct=th, counter_latin_numerals_min=k)
            tab = sorted(u for u, _n in b.learn_counters(ex, cfg) if u.isascii())
            qk = [u for u in Q if u in tab]
            nk = [u for u in N if u in tab]
            rows.append({"theta": th, "K": k, "units": tab, "q_kept": qk, "n_kept": nk,
                         "score": len(qk) - len(nk)})
            P("theta=%d K=%d: %d Latin units %s" % (th, k, len(tab), tab))
            P("   Q kept %s | Q lost %s | N kept %s | em %s | score %d"
              % (qk, [u for u in Q if u not in tab], nk, "em" in tab, len(qk) - len(nk)))
    best = max(rows, key=lambda r: (r["score"], r["theta"], r["K"]))
    P("SELECTED (max score, then larger theta, then larger K): theta=%d K=%d score=%d"
      % (best["theta"], best["K"], best["score"]))
    # for the record: the numerals each Q / N unit follows, per source (capped at %d)
    nums = ex["counter_nums"]
    P("--- per-source (after-numeral count, noun occurrences case-insensitive, distinct numerals) ---")
    for u in Q + N + UNDECIDED:
        row = {}
        for src in sorted(ex["counters"]):
            n = ex["counters"][src].get(u, 0)
            if n >= base_cfg["counter_min"]:
                seen = b._latin_seen(ex["pos"].get(src), {u})
                row[src] = (n, seen.get(u.lower(), 0), len(nums.get(src, {}).get(u, ())))
        P("%s %s" % (u, json.dumps(row, ensure_ascii=False)))
    per_src = {}
    for u in Q + N + UNDECIDED:
        for src in sorted(ex["counters"]):
            n = ex["counters"][src].get(u, 0)
            if n >= base_cfg["counter_min"]:
                seen = b._latin_seen(ex["pos"].get(src), {u})
                per_src.setdefault(u, {})[src] = {"after_numeral": n, "noun_occurrences": seen.get(u.lower(), 0),
                                                  "distinct_numerals": len(nums.get(src, {}).get(u, ()))}
    js = {"stage": a.stage, "Q": Q, "N": N, "undecided": UNDECIDED, "no_rule_units": t0,
          "grid": rows, "selected": {"theta": best["theta"], "K": best["K"]}, "per_source": per_src}
    json.dump(js, open(a.out.replace(".txt", ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1,
              sort_keys=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[-40:]))
    print("SELECTED", best["theta"], best["K"])


if __name__ == "__main__":
    main()
