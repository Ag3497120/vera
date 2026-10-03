"""List the verbs / adjectives of the material by use count, per source (W3-a r2, M4).

Reproduces how the predicate seeds are chosen: the seeds must come from the
head of THIS list (rank <= --range), counted from the material alone (the
extraction stage cache of a build), never from the test data.  The test file
``predicate_check.jsonl`` is read ONLY to flag overlaps (the seeds must not
overlap it beyond the words the frozen file marked ``seed_overlap: true``).

  pred_seed_freq.py --stage-cache PKL --out TSV [--range N]

Columns: rank, word, class (V verb / A adjective / S adjectival noun), total uses
(a LISTING order only -- no source's count decides anything), the per-source uses,
``seed`` (the type it is a seed of in coarse_types.SEEDS_PRED, or "-"),
``in_predicate_check`` (flag only).
"""
import argparse
import json
import os
import pickle
import sys
from collections import Counter, defaultdict

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
from verantyx import coarse_types as ct  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage-cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--range", type=int, default=600)
    ap.add_argument("--top", type=int, default=3000)
    a = ap.parse_args()
    ex = pickle.load(open(a.stage_cache, "rb"))
    per = defaultdict(lambda: defaultdict(Counter))      # word -> class -> src -> n
    srcs = sorted(ex["pos"])
    for src in srcs:
        for (w, cl), n in ex["pos"][src].items():
            if cl in ("V", "A", "S"):
                per[w][cl][src] += n
    rows = []
    for w, d in per.items():
        cl = max(d, key=lambda c: sum(d[c].values()))     # the commonest class (listing only)
        tot = sum(sum(v.values()) for v in d.values())
        rows.append((w, cl, tot, {s: sum(d[c].get(s, 0) for c in d) for s in srcs}))
    rows.sort(key=lambda r: (-r[2], r[0]))
    seeds = {w: t for t, ws in ct.SEEDS_PRED.items() for w in ws}
    pc = {}
    for line in open(os.path.join(W, "tests/coarse_place/data/predicate_check.jsonl"), encoding="utf-8"):
        d = json.loads(line)
        pc[d["term"]] = d
    rank_of = {r[0]: i + 1 for i, r in enumerate(rows)}
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("rank\tword\tclass\ttotal\t" + "\t".join(srcs) + "\tseed\tin_predicate_check\n")
        for i, (w, cl, tot, ps) in enumerate(rows):
            if i >= a.top and w not in seeds:
                continue
            f.write("%d\t%s\t%s\t%d\t%s\t%s\t%s\n" % (
                i + 1, w, cl, tot, "\t".join(str(ps[s]) for s in srcs),
                seeds.get(w, "-"), "yes" if w in pc else "-"))
    outside = sorted((rank_of.get(w, 10 ** 9), w) for w in seeds if rank_of.get(w, 10 ** 9) > a.range)
    ov = sorted(w for w in seeds if w in pc)
    summ = {"verbs_and_adjectives_listed": len(rows), "range": a.range,
            "predicate_seeds": len(seeds), "seeds_outside_range": outside,
            "seeds_in_predicate_check": ov,
            "frozen_seed_overlap_true": sorted(t for t, d in pc.items() if d.get("seed_overlap"))}
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
