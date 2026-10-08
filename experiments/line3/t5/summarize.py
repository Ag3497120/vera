"""Verdict counts and timings of the T5 result files (no grading)."""
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for path in sorted(glob.glob(os.path.join(HERE, "results", "*.jsonl"))):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    c = collections.Counter(r["answer"]["verdict"] for r in rows)
    alt = collections.Counter(r["thought"]["alt_member_rule_verdict"]["verdict"] for r in rows)
    part = sum(1 for r in rows if r["answer"]["partial_read"])
    stack = sum(1 for r in rows if r["thought"]["stacking"]["would_stack"])
    centre_fn = sum(1 for r in rows if r["answer"]["verdict"] == "ANSWER" and len(r["answer"]["units"][0]) == 1 and r["answer"]["units"][0] in "はがのをにへとでもやかね")
    secs = [r["secs"] for r in rows]
    print(os.path.basename(path), "questions", len(rows))
    print("  verdicts:", dict(sorted(c.items())))
    print("  alt member rule (answering_only):", dict(sorted(alt.items())))
    print("  partial_read marked:", part, " questions with a stacking point (N-11):", stack,
          " ANSWER with a particle-like single char:", centre_fn)
    print("  secs per question: min %.1f median %.1f max %.1f total(sum) %.1f" %
          (min(secs), sorted(secs)[len(secs) // 2], max(secs), sum(secs)))
    sc = collections.Counter()
    for r in rows:
        for k, v in r["thought"]["search"].items():
            sc[k] += v
    print("  search totals:", dict(sorted(sc.items())))
