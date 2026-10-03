"""W3-a3 step 7-1: how many of the verbs on the generation list are verbs of the dev / frozen verb data.
Counts only: the list is never changed by the test data (it is made from the placement and the cache alone)."""
import json
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
needs = [json.loads(l)["word"] for l in open(W + "/artifacts/w3-a3/needs_pred.jsonl", encoding="utf-8")]
ns = set(needs)
out = {"needs_total": len(needs)}
for name in ("dev_verbs", "verb_check_300"):
    rows = [json.loads(l) for l in open("%s/tests/coarse_place/data/%s.jsonl" % (W, name), encoding="utf-8")]
    hit = [r for r in rows if r["term"] in ns]
    out[name] = {"rows": len(rows), "on_the_list": len(hit),
                 "by_kind": {k: sum(1 for r in hit if r["kind"] == k) for k in ("typed", "unknown_fragment", "unknown_coined")}}
out["note"] = "counted only; the list was made without the test data; the mid-level auditor's 100 verbs are unknown to the implementer"
json.dump(out, open(W + "/artifacts/w3-a3/needs_pred_overlap.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
print(json.dumps(out, ensure_ascii=False))
