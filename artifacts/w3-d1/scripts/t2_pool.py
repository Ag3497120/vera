#!/usr/bin/env python3
"""T2 pool: typed crosses (read with the placement r9) from the texts of artifacts/w10-f04/entry_r8.after.jsonl.

Selection (preregistered in docs/REALIZE.md section 3): distinct `text`; semantic_read.read(text, "ja", placement=R9) must not raise ReadError;
build_crosses(out, default_lookup(R9)) must be CROSSED with exactly one cross; ascending sha256(text.encode()); the first 100.
Run with VERA_PLACEMENT / VERA_REALIZE_FORMS unset.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
R9 = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2"
for _v in ("VERA_PLACEMENT", "VERA_REALIZE_FORMS"):
    if os.environ.get(_v):
        sys.exit("refusing to run with %s set" % _v)


def main() -> int:
    from verantyx import cross_tokens, event_cross, observe, semantic_read

    seen, texts = set(), []
    for line in (ROOT / "artifacts/w10-f04/entry_r8.after.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line).get("text")
            if isinstance(t, str) and t and t not in seen:
                seen.add(t)
                texts.append(t)
    meta = Counter()
    meta["distinct_texts"] = len(texts)
    lookup = event_cross.default_lookup(R9)
    pool = []
    for t in texts:
        try:
            out = semantic_read.read(t, "ja", placement=R9)
        except semantic_read.ReadError as exc:
            meta["excluded_ReadError_" + str(exc).split(":")[0][:40]] += 1
            continue
        except Exception as exc:
            meta["excluded_exception_" + type(exc).__name__] += 1
            continue
        got = event_cross.build_crosses(out, lookup)
        if got.status != "CROSSED":
            meta["excluded_not_crossed"] += 1
            continue
        if len(got.crosses) != 1:
            meta["excluded_multiple_crosses"] += 1
            continue
        meta["eligible"] += 1
        cross = got.crosses[0]
        pool.append({
            "sha": hashlib.sha256(t.encode()).hexdigest(), "text": t, "clause": out["clauses"][0] if out.get("clauses") else None,
            "tokens": cross_tokens.cross_to_tokens(cross), "cell_key": observe.cell_key_of(cross),
            "n_clauses": len(out.get("clauses", ())),
        })
    pool.sort(key=lambda r: r["sha"])
    chosen = pool[:100]
    with open(ROOT / "artifacts/w3-d1/t2_pool.jsonl", "w", encoding="utf-8") as fh:
        for r in chosen:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    meta["chosen"] = len(chosen)
    (ROOT / "artifacts/w3-d1/t2_pool_meta.json").write_text(json.dumps(dict(sorted(meta.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(dict(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
