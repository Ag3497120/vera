#!/usr/bin/env python3.11
"""Deterministic scale benchmark for verantyx.library (JSONL, one row per size).

Selection ranks the existing sha field after xor with a fixed seed. The first
300 rows are held out at every size; the next N build each sampled library.
The full run streams every non-held-out row. No network or model is used.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import heapq
import json
import statistics
import time
from collections import Counter
from pathlib import Path

import psutil

from verantyx.library import Library
from verantyx.typed_edges import _tagger

DEFAULT_CORPUS = Path.home() / "Projects/vera-corpus/codex/local/sentences.jsonl"
SEED = 0x9E3779B97F4A7C15
HOLDOUT = 300
MAX_MB = 6000


def rank(row: dict) -> int:
    sha = row.get("sha") or hashlib.sha256(row["text"].encode()).hexdigest()[:16]
    return int(sha, 16) ^ SEED


def resident_mb() -> float:
    return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)


def question(text: str) -> str:
    words = []
    for token in _tagger()(text):
        if token.feature.pos1 in ("名詞", "動詞"):
            word = token.feature.lemma or token.surface
            if word and word not in words:
                words.append(word.split("-")[0])
    return "、".join(words) + "？" if words else text + "？"


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--sizes", type=int, nargs="*", default=[1000, 10000, 100000, -1],
                    help="-1 means the full file")
    args = ap.parse_args()
    largest = max((n for n in args.sizes if n > 0), default=0)
    keep = largest + HOLDOUT
    selected: list[tuple[int, int, dict]] = []
    total = 0
    with args.corpus.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            total += 1
            key = rank(row)
            item = (-key, -total, row)
            if len(selected) < keep:
                heapq.heappush(selected, item)
            elif item > selected[0]:
                heapq.heapreplace(selected, item)
    ordered = [row for _, _, row in sorted(selected, reverse=True)]
    heldout = ordered[:HOLDOUT]
    excluded = {row.get("sha") for row in heldout}
    questions = [(question(row["text"]), row.get("scene", "")) for row in heldout]

    for size in args.sizes:
        gc.collect()
        before_mb = resident_mb()
        if size == -1:
            def full_rows():
                with args.corpus.open(encoding="utf-8") as f:
                    for index, line in enumerate(f):
                        if index >= total:
                            break
                        row = json.loads(line)
                        if row.get("sha") not in excluded:
                            yield row
            records = full_rows()
            label = "full"
            count = total - HOLDOUT
        else:
            records = ordered[HOLDOUT:HOLDOUT + size]
            label = str(size)
            count = len(records)
        start = time.perf_counter()
        try:
            lib = Library.from_records(records, max_resident_mb=MAX_MB)
        except MemoryError:
            print(json.dumps({"size": label, "sentences": count, "status": "memory_limit",
                              "resident_mb": resident_mb()}, ensure_ascii=False), flush=True)
            break
        build_s = round(time.perf_counter() - start, 2)
        memory = resident_mb()
        if memory > MAX_MB:
            print(json.dumps({"size": label, "sentences": count, "status": "memory_limit",
                              "build_s": build_s, "resident_mb": memory}, ensure_ascii=False), flush=True)
            break
        outcomes = [lib.ask(q) for q, _ in questions]
        times = [r["ms"] for r in outcomes]
        mix = Counter(r["path"] for r in outcomes)
        frame_cap_hits = sum(r["frame_cap_hit"] for r in outcomes)
        hits = sum(any(scene == wanted for _, scene, _ in r["sentences"])
                   for r, (_, wanted) in zip(outcomes, questions))
        print(json.dumps({"size": label, "sentences": count,
                          "build_s": build_s, "resident_mb": memory,
                          "incremental_mb": round(memory - before_mb, 1),
                          "leaves": len(lib.leaves), "depth": lib.depth,
                          "median_ms": round(statistics.median(times), 3),
                          "p95_ms": round(percentile(times, .95), 3),
                          "path_mix": dict(mix), "frame_cap_hits": frame_cap_hits,
                          "hit_at_5": round(hits / len(questions), 4)},
                         ensure_ascii=False), flush=True)
        del lib


if __name__ == "__main__":
    main()
