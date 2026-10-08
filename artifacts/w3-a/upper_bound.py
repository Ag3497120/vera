"""upper_bound: for how many frozen L2 words does the gold type appear ANYWHERE in the
evidence table (below-threshold votes included)?  No rule can place more words than this
(report only; W3-a2).  Counted twice: with the generated arm, and without it.

    upper_bound.py --placement DIR [--out FILE]
"""
import argparse
import json
import sqlite3
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    fr = json.load(open(W + "/artifacts/w3-a/FROZEN.json", encoding="utf-8"))
    seed = set(fr["seed_overlap_terms"])
    G = [json.loads(l) for l in open(W + "/tests/coarse_place/data/typed_vocab.jsonl", encoding="utf-8")]
    G = [g for g in G if g["term"] not in seed]
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % args.placement, uri=True)
    n = len(G)
    with_gen = without_gen = 0
    for g in G:
        types = {}
        for arm, t in con.execute("SELECT arm, type FROM evidence WHERE word=? AND arm!='ns_vote'", (g["term"],)):
            types.setdefault(arm, set()).add(t)
        allt = set().union(*types.values()) if types else set()
        nog = set().union(*[v for k, v in types.items() if k != "gen_definition"]) if types else set()
        gs = set(g["gold"])
        with_gen += bool(allt & gs)
        without_gen += bool(nog & gs)
    out = {"placement": args.placement, "n": n, "gold_type_in_evidence_with_generated": with_gen,
           "gold_type_in_evidence_without_generated": without_gen,
           "rate_with": round(with_gen / n, 4), "rate_without": round(without_gen / n, 4)}
    text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
