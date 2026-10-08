"""Dump the answers of the placement R5 for a list of terms with whatever `verantyx` is on PYTHONPATH
(run once with the base commit's tree and once with this tree; r5_answer_compare.py compares the dumps)."""
import json
import sys

from verantyx.coarse_place import query

R5 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1"
W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
terms = []
for f in ("dev_vocab", "dev_unknown", "typed_vocab", "unknown_words", "dev_verbs", "verb_check_300", "predicate_check"):
    for l in open("%s/tests/coarse_place/data/%s.jsonl" % (W, f), encoding="utf-8"):
        terms.append(json.loads(l)["term"])
terms += ["昨日", "行く", "食べる", "図書館", "2024年", "10kg", "存在しない語です"]
out = {}
for t in sorted(set(terms)):
    r = query(t, placement=R5)
    out[t] = r
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, sort_keys=False)
print(len(out), "terms")
