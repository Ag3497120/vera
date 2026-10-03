"""gen_precision: what the generated definitions did to the DEV words (W3-a2, rule 5-7).

    gen_precision.py --placement DIR [--out FILE]

For every dev_vocab word (seed words removed, as in the L2 measurement): the answer is
classed (correct / wrong_single / other) and counted by
  upgraded      origin direct and gen_definition among the deciding arms (agreement)
  est_generated origin estimated, estimate_basis generated
  gen_ignored   a generated row exists but the word was decided without it (GENERATED_NOT_DECIDING)
Uses the public query API only; DEV data only.
"""
import argparse
import json
import sys
from collections import Counter

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
from verantyx import coarse_types as ct  # noqa: E402
from verantyx.coarse_place import query  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    seeds = {w for v in ct.SEEDS_NOUN.values() for w in v}
    rows = [json.loads(l) for l in open(W + "/tests/coarse_place/data/dev_vocab.jsonl", encoding="utf-8")]
    rows = [g for g in rows if g["term"] not in seeds]
    cnt = {k: Counter() for k in ("upgraded", "est_generated", "gen_ignored")}
    items = []
    for g in rows:
        r = query(g["term"], placement=args.placement)
        top, gs = r["top"], set(g["gold"])
        k = ("correct" if top and gs & set(top) and len(top) <= max(1, len(gs))
             else ("wrong_single" if len(top) == 1 else "other"))
        if r["origin"] == "direct" and "gen_definition" in (r.get("decided_by") or []):
            grp = "upgraded"
        elif r["origin"] == "estimated" and r.get("estimate_basis") == "generated":
            grp = "est_generated"
        elif "gen_definition" in (r.get("axes") or {}) and r["origin"] == "direct":
            grp = "gen_ignored"
        else:
            continue
        cnt[grp][k] += 1
        items.append((grp, g["term"], top, sorted(gs), k))
    lines = ["placement: %s" % args.placement]
    for grp, c in cnt.items():
        lines.append("%s: correct %d  wrong_single %d  other %d" % (grp, c["correct"], c["wrong_single"], c["other"]))
    u = cnt["upgraded"]
    lines.append("rule 5-7: upgrade stays ON when correct >= 3 * wrong among the upgraded: %s  (correct %d, wrong %d)"
                 % (u["correct"] >= 3 * u["wrong_single"] and u["correct"] > 0, u["correct"], u["wrong_single"]))
    for it in items:
        lines.append("  %s" % (it,))
    text = "\n".join(lines) + "\n"
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
