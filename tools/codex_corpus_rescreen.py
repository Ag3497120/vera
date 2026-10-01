"""Re-screen records dropped by the old 8-gram overlap rule with the current
leakage rule (codex_corpus_general.Block). Records that now pass are APPENDED
to <family>/<split>/records.jsonl (their cell's split); nothing is deleted or
rewritten. Idempotent: a record whose sha is already in train/heldout is skipped.

    python3.11 codex_corpus_rescreen.py --root ~/vera-codex-corpus --block-dirs ~/vera-eval-block
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codex_corpus_general import Block, locked_append, record_texts  # noqa: E402

FAMS = ("general_qa", "code_qa", "figurative_commonsense", "narrative", "paraphrase_entail")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--block-dirs", nargs="+", required=True)
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    block = Block(a.block_dirs)
    summary = {}
    for fam in FAMS:
        d = root / fam
        src = d / "overlap_dropped" / "records.jsonl"
        if not src.exists():
            continue
        seen = set()
        for sp in ("train", "heldout"):
            f = d / sp / "records.jsonl"
            if f.exists():
                for line in f.open(encoding="utf-8"):
                    try:
                        seen.add(json.loads(line)["sha"])
                    except Exception:
                        pass
        c, bufs, still = Counter(), {"train": [], "heldout": []}, Counter()
        for line in src.open(encoding="utf-8"):
            r = json.loads(line)
            c["dropped_before"] += 1
            if r["sha"] in seen:
                c["already_present"] += 1
                continue
            hit = block.hit(record_texts(r))
            if hit:
                c["still_dropped"] += 1
                still[hit] += 1
                continue
            seen.add(r["sha"])
            old = r.pop("overlap_gram", None)
            r["rescreened"] = {"date": time.strftime("%Y-%m-%d"), "old_gram": old}
            bufs[r["split"]].append(json.dumps(r, ensure_ascii=False) + "\n")
            c["moved_" + r["split"]] += 1
        for sp, lines in bufs.items():
            if lines:
                locked_append(d / sp / "records.jsonl", "".join(lines))
        summary[fam] = dict(c)
        locked_append(d / "rescreen_log.jsonl", json.dumps(
            {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), **c,
             "still_top": dict(still.most_common(10))}, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
