"""bank_score の 2 つの出力（前・後）を、時計の鍵と一時ディレクトリの名前を落として比べる（b2_semantic_compare.py の作法。差は全部出す）。
usage: bank_compare.py BEFORE AFTER"""
import json
import re
import sys
from pathlib import Path

CLOCK = {"elapsed_ms", "ingest_ms", "modules"}      # modules: how many verantyx modules were imported (doc_answer is a new one: 80 -> 83 in provenance)
TMP = re.compile(r"/(?:private/)?var/folders/[^\"' ]*?/bank_score_[A-Za-z0-9_]+")


def norm(o):
    if isinstance(o, dict):
        return {k: norm(v) for k, v in o.items() if k not in CLOCK}
    if isinstance(o, list):
        return [norm(v) for v in o]
    if isinstance(o, str):
        return TMP.sub("<TMP>", o)
    return o


b, a = Path(sys.argv[1]), Path(sys.argv[2])
diffs = []
names = sorted(p.name for p in (b / "raw").iterdir())
assert names == sorted(p.name for p in (a / "raw").iterdir())
for n in names:
    if norm(json.loads((b / "raw" / n).read_text())) != norm(json.loads((a / "raw" / n).read_text())):
        diffs.append("raw/" + n)
rb = [norm(json.loads(l)) for l in (b / "results.jsonl").read_text().splitlines() if l.strip()]
ra = [norm(json.loads(l)) for l in (a / "results.jsonl").read_text().splitlines() if l.strip()]
for i, (p, q) in enumerate(zip(rb, ra)):
    if p != q:
        diffs.append("results row %d: %s" % (i, sorted(k for k in set(p) | set(q) if p.get(k) != q.get(k))))
sb, sa = norm(json.loads((b / "summary.json").read_text())), norm(json.loads((a / "summary.json").read_text()))
print("raw files compared:", len(names), "results rows:", len(rb), len(ra), "summary equal:", sb == sa)
print("differences after dropping clock keys and tmp names:", len(diffs))
for d in diffs:
    print("  ", d)
