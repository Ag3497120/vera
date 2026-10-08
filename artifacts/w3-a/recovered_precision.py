"""recovered_precision: of the dev words that ONLY the fallback definition decided
(decided_by == ["definition_recovered"]), how many are right (W3-a2, rule 5-2-2).

    recovered_precision.py --placement DIR [--out FILE]

Uses the DEV data only (tests/coarse_place/data/dev_vocab.jsonl); the public query API.
"""
import argparse
import json
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
from verantyx.coarse_place import query  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    rows = [json.loads(l) for l in open(W + "/tests/coarse_place/data/dev_vocab.jsonl", encoding="utf-8")]
    correct = wrong = other = 0
    items = []
    for g in rows:
        r = query(g["term"], placement=args.placement)
        if r["origin"] != "direct" or r.get("decided_by") != ["definition_recovered"]:
            continue
        top, gs = r["top"], set(g["gold"])
        if top and set(top) & gs and len(top) <= max(1, len(gs)):
            k = "correct"; correct += 1
        elif len(top) == 1:
            k = "wrong_single"; wrong += 1
        else:
            k = "other"; other += 1
        items.append((g["term"], top, sorted(gs), k))
    text = ("placement: %s\nonly-definition_recovered words in dev_vocab: %d  correct %d  wrong_single %d  other %d\n"
            "rule: wrong > correct/3 -> do not let it decide:  wrong*3 > correct = %s\n"
            % (args.placement, len(items), correct, wrong, other, wrong * 3 > correct))
    for it in items:
        text += "  %s\n" % (it,)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
