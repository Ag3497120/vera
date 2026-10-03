"""counter_dev_check: choose ``counter_min`` on the DEV data only (DECISIONS 5-4).

    counter_dev_check.py --cache STAGE.pkl --out FILE

For counter_min in (100, 80, 60): learn the counter table from the cached extraction
counts (tools/build_coarse_placement.learn_counters), then check every dev_vocab word
whose gold is QUANTITY and which starts with a digit (it must read as QUANTITY by the
spelling rule given the learned table).  Prints the failures and the units that are
4+ characters or Latin, for review.  The frozen test data are not read.
"""
import argparse
import json
import pickle
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
sys.path.insert(0, W + "/tools")
import build_coarse_placement as b  # noqa: E402
from verantyx import coarse_types as ct  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    ex = pickle.load(open(args.cache, "rb"))
    gold = [json.loads(l) for l in open(W + "/tests/coarse_place/data/dev_vocab.jsonl", encoding="utf-8")]
    gold = [g for g in gold if g["gold"] == ["QUANTITY"] and g["term"][:1].isdigit()]
    lines = ["dev words (gold QUANTITY, start with a digit): %d" % len(gold)]
    for cm in (100, 80, 60):
        cfg = dict(ct.DEFAULT_CONFIG)
        cfg["counter_min"] = cm
        units = b.learn_counters(ex, cfg)
        us = {u for u, _n in units}
        miss = [g["term"] for g in gold if ct.notation_type(g["term"], us) != ("QUANTITY", "number+counter")
                and ct.notation_type(g["term"], us) != ("QUANTITY", "number")]
        lines.append("counter_min=%d: units %d; dev words not QUANTITY: %d %s" % (cm, len(us), len(miss), miss))
        lines.append("   4+ chars: %s" % sorted(u for u in us if len(u) >= 4))
        lines.append("   Latin: %s" % sorted(u for u in us if u.isascii()))
        lines.append("   all: %s" % sorted(us))
    text = "\n".join(lines) + "\n"
    open(args.out, "w", encoding="utf-8").write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
