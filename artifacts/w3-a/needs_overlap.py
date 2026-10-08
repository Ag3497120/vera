"""needs_overlap: AFTER the needs list was chosen (by frequency only), how many of its words
are test-data words (W3-a2).  The list was not built from these files; this only counts.

    needs_overlap.py [--needs FILE] [--out FILE]
"""
import argparse
import json
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
D = W + "/tests/coarse_place/data/"
NAMES = ("typed_vocab", "dev_vocab", "unknown_words", "dev_unknown", "predicate_check")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--needs", default=W + "/artifacts/w3-a/needs_evidence.jsonl")
    ap.add_argument("--out", default=W + "/artifacts/w3-a/needs_evidence_overlap.json")
    args = ap.parse_args(argv)
    words = {json.loads(l)["word"] for l in open(args.needs, encoding="utf-8") if l.strip()}
    out = {"needs_total": len(words), "overlap": {}, "test_terms": {}}
    for n in NAMES:
        terms = {json.loads(l)["term"] for l in open(D + n + ".jsonl", encoding="utf-8") if l.strip()}
        hit = sorted(words & terms)
        out["overlap"][n] = len(hit)
        out["test_terms"][n] = len(terms)
        out.setdefault("examples", {})[n] = hit[:10]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps(out, ensure_ascii=False))
    assert out["overlap"]["unknown_words"] == 0 and out["overlap"]["dev_unknown"] == 0, "excluded terms leaked"
    return 0


if __name__ == "__main__":
    sys.exit(main())
