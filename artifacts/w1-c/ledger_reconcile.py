"""Ledger vs. item files for code, even/code, conversation, even/conversation (corpus read-only).

Facts only: for every directory, ledger counts (rows, verdicts, batch-name prefixes, summed `kept`,
duplicate batch names) and, per item file (train / heldout / overlap_dropped), the number of rows per
`source` batch. Then which ledger batches have no rows in any item file, which item batches have no
ledger row, and for batches in both the difference between ledger `kept` and rows found.
No explanation of any difference is given here.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CORPUS, HERE, dump  # noqa: E402

DIRS = {
    "code": ("code/ledger.jsonl", {"train": "code/items.jsonl", "heldout": "code/heldout/items.jsonl", "overlap_dropped": "code/overlap_dropped/items.jsonl"}),
    "even/code": ("even/code/ledger.jsonl", {"train": "even/code/items.jsonl", "heldout": "even/code/heldout/items.jsonl", "overlap_dropped": "even/code/overlap_dropped/items.jsonl"}),
    "conversation": ("conversation/ledger.jsonl", {"train": "conversation/utterances.jsonl", "heldout": "conversation/heldout/utterances.jsonl", "overlap_dropped": "conversation/overlap_dropped/utterances.jsonl"}),
    "even/conversation": ("even/conversation/ledger.jsonl", {"train": "even/conversation/utterances.jsonl", "heldout": "even/conversation/heldout/utterances.jsonl", "overlap_dropped": "even/conversation/overlap_dropped/utterances.jsonl"}),
}
TAG = "llm_authored:codex:"


def batch_prefix(name: str) -> str:
    m = re.match(r"^(.*?)-b\d+$", name)
    return m.group(1) if m else name


def main() -> int:
    t0 = time.perf_counter()
    out = {}
    for key, (ledger_rel, files) in DIRS.items():
        ledger = [json.loads(l) for l in (CORPUS / ledger_rel).read_bytes().split(b"\n") if l.strip()]
        batches = Counter(r.get("batch") for r in ledger)
        kept = {}
        for r in ledger:
            if r.get("verdict") == "KEPT":
                kept[r["batch"]] = kept.get(r["batch"], 0) + int(r.get("kept") or 0)
        items = {}
        for split, rel in files.items():
            c, bad_source = Counter(), 0
            for raw in (CORPUS / rel).read_bytes().split(b"\n"):
                if not raw.strip():
                    continue
                src = json.loads(raw).get("source")
                if isinstance(src, str) and src.startswith(TAG):
                    c[src[len(TAG):]] += 1
                else:
                    bad_source += 1
            items[split] = dict(path=rel, rows=sum(c.values()), batches=len(c), rows_without_codex_source=bad_source, by_batch=dict(c))
        any_items = Counter()
        for v in items.values():
            any_items.update(v["by_batch"])
        led_set, item_set = set(b for b in batches if b), set(any_items)
        only_ledger = sorted(led_set - item_set)
        only_items = sorted(item_set - led_set)
        both = sorted(led_set & item_set)
        diffs = [(b, kept.get(b, 0), any_items[b]) for b in both if kept.get(b, 0) != any_items[b]]
        th = Counter()
        for split in ("train", "heldout"):
            th.update(items[split]["by_batch"])
        diffs_th = [(b, kept.get(b, 0), th[b]) for b in both if kept.get(b, 0) != th[b]]
        pref = lambda names: dict(Counter(batch_prefix(b) for b in names))
        out[key] = dict(
            ledger_path=ledger_rel, ledger_rows=len(ledger),
            ledger_verdicts=dict(Counter(r.get("verdict") for r in ledger)),
            ledger_batch_prefixes=dict(Counter(batch_prefix(r.get("batch", "")) for r in ledger)),
            ledger_kept_total=sum(kept.values()), ledger_distinct_batches=len(led_set),
            ledger_duplicate_batch_names=sum(1 for n in batches.values() if n > 1),
            item_files={s: {k: v for k, v in d.items() if k != "by_batch"} for s, d in items.items()},
            item_rows_all_splits=sum(any_items.values()), item_distinct_batches=len(item_set),
            ledger_batches_not_in_any_item_file=dict(count=len(only_ledger), by_prefix=pref(only_ledger),
                                                    kept_total=sum(kept.get(b, 0) for b in only_ledger),
                                                    verdicts=dict(Counter(r.get("verdict") for r in ledger if r.get("batch") in set(only_ledger)))),
            item_batches_not_in_ledger=dict(count=len(only_items), by_prefix=pref(only_items),
                                            rows=sum(any_items[b] for b in only_items)),
            batches_in_both=dict(count=len(both), by_prefix=pref(both), ledger_kept_total=sum(kept.get(b, 0) for b in both),
                                 item_rows_total=sum(any_items[b] for b in both),
                                 batches_where_kept_differs_from_rows=len(diffs),
                                 sum_kept_minus_rows=sum(k - n for _, k, n in diffs),
                                 item_rows_train_plus_heldout_total=sum(th[b] for b in both),
                                 batches_where_kept_differs_from_train_plus_heldout_rows=len(diffs_th),
                                 sum_kept_minus_train_plus_heldout_rows=sum(k - n for _, k, n in diffs_th),
                                 first_differing=[dict(batch=b, kept=k, rows=n) for b, k, n in diffs[:10]]),
        )
    out["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
    dump(HERE / "ledger_reconcile.json", out)
    for k, v in out.items():
        if k == "elapsed_seconds":
            continue
        print(k, "ledger_rows", v["ledger_rows"], "kept", v["ledger_kept_total"], "item_rows", v["item_rows_all_splits"],
              "ledger-only", v["ledger_batches_not_in_any_item_file"]["count"], "items-only", v["item_batches_not_in_ledger"]["count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
