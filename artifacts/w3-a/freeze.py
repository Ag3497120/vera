"""Freeze the test data: write FROZEN.json (sha256 + counts + time)."""
import datetime
import hashlib
import json
import os
import sys
from collections import Counter

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
from verantyx import coarse_types as ct  # noqa: E402

FILES = [
    "tests/coarse_place/data/typed_vocab.jsonl",
    "tests/coarse_place/data/unknown_words.jsonl",
    "tests/coarse_place/data/dev_vocab.jsonl",
    "tests/coarse_place/data/dev_unknown.jsonl",
    "tests/coarse_place/data/predicate_check.jsonl",
    "artifacts/w3-a/holdout_2000.jsonl",
    "artifacts/w3-a/PREREG.md",
    "verantyx/coarse_types.py",
]


def main():
    out = {"frozen_at_utc": None, "files": {}, "categories": {},
           "seed_overlap_terms": []}
    seeds = {w for v in ct.SEEDS_NOUN.values() for w in v}
    for rel in FILES:
        p = os.path.join(W, rel)
        data = open(p, "rb").read()
        out["files"][rel] = {"sha256": hashlib.sha256(data).hexdigest(),
                             "lines": data.count(b"\n"), "bytes": len(data)}
    rows = [json.loads(l) for l in open(os.path.join(W, FILES[0]), encoding="utf-8")]
    out["categories"] = dict(Counter(r["category"] for r in rows))
    out["suffix_trap_count"] = sum(r["suffix_trap"] for r in rows)
    out["seed_overlap_terms"] = sorted(r["term"] for r in rows if r["term"] in seeds)
    unk = [json.loads(l) for l in open(os.path.join(W, FILES[1]), encoding="utf-8")]
    out["unknown_words"] = {"total": len(unk),
                            "gold_unknown": sum(u["gold_unknown"] for u in unk)}
    out["types_version"] = ct.TYPES_VERSION
    out["frozen_at_utc"] = datetime.datetime.now(datetime.timezone.utc
                                                 ).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(W, "artifacts/w3-a/FROZEN.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps({k: v for k, v in out.items() if k != "files"},
                     ensure_ascii=False))
    for rel, m in out["files"].items():
        print(m["sha256"], m["lines"], rel)


if __name__ == "__main__":
    main()
