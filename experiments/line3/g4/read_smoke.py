#!/usr/bin/env python3
"""G4-c smoke run: build the first N articles of fulllead as a RUN+WORD+CHAR stack (foundation on, level mid), save every step, then read the bank2 questions whose
entry step is <= N through `Index.from_stack` (the arm-A reader: structure flat, view all, effort fast, grammar on) and report verdict, list size, gold, time.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/g4/read_smoke.py --root DIR [--articles 8] [--workers 2] [--out FILE.json]
      [--also-at-entry] [--skip-build]

`--root DIR` is where the stack snapshots go (outside the repository).  `--also-at-entry` also reads each question at the step it enters (e(q) / s(q)), to show
the step before and after the evidence article.  The gold is scored by t9/scorer.py (`hits_words`, unchanged, L-G4-6): an entry holds the gold when a gold alternative
is a substring of ONE word of the entry.  Seconds are not part of any hashed byte.  Never opens vera-impl/hidden; no network.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import resource
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from verantyx.line3 import ask as A          # noqa: E402
from verantyx.line3 import stack as st       # noqa: E402

DATA = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments", "line3", "bank2", "bank2.tsv")
TIERS = ("RUN", "WORD", "CHAR")


def cpu_s():
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def scorer():
    spec = importlib.util.spec_from_file_location("t9scorer", os.path.join(ROOT, "experiments", "line3", "t9", "scorer.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def questions(max_step, steps):
    out = []
    with open(BANK, encoding="utf-8", newline="") as f:
        head = f.readline().rstrip("\r\n").lstrip("#").split("\t")
        for row in csv.DictReader(f, fieldnames=head, delimiter="\t"):
            q = row["id"]
            if q in steps["entry_steps"] and steps["entry_steps"][q] <= max_step and row["corpus"] == "fulllead":
                out.append({"id": q, "kind": row["kind"], "question": row["question"], "gold": row["gold"], "entry": steps["entry_steps"][q],
                            "evidence": row["evidence"]})
    return sorted(out, key=lambda r: (r["entry"], r["id"]))


def read_one(ix, q, sc, grammar):
    t0, c0 = time.time(), cpu_s()
    c = A.ask(ix, q["question"], effort="fast", view="all", structure="flat", grammar=grammar)
    wall, cpu = time.time() - t0, cpu_s() - c0
    entries = [(t, e) for t, e in c.entries]
    gold_entries = [i for i, (_t, e) in enumerate(entries) if q["gold"] and sc.hits_words(q["gold"], e.words)]
    rd = c.read_obj()
    return {"id": q["id"], "kind": q["kind"], "entry": q["entry"], "step": ix.stack["step"], "grammar": grammar, "verdict": c.verdict, "listed": len(entries),
            "per_tier_listed": {o.tier: len(o.entries) for o in c.outcomes}, "tier_verdicts": {o.tier: o.verdict for o in c.outcomes},
            "gold_entries": gold_entries, "gold_in_candidate": bool(gold_entries), "first_gold_pos": gold_entries[0] if gold_entries else None,
            "single_wrong": c.verdict == A.ANSWER and not gold_entries, "partial": rd["partial"], "reasons": rd.get("partial_reasons"),
            "refused": rd["rebuild_refused"]["per_tier"], "read": {t: [v["crosses_read"], v["left_unread"]] for t, v in rd["per_tier"].items()},
            "answer_sha16": hashlib.sha256(c.to_bytes()).hexdigest()[:16], "wall_s": round(wall, 2), "cpu_s": round(cpu, 2),
            "words": [[t, list(e.words)] for t, e in entries[:6]]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--articles", type=int, default=8)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--level", default="mid")
    ap.add_argument("--out", default=None)
    ap.add_argument("--also-at-entry", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--grammar", default="on", choices=["on", "off"])
    a = ap.parse_args(argv)
    docs = st.load_docs(DATA)[:a.articles]
    steps = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))
    qs = questions(a.articles, steps)
    sc = scorer()
    rec = {"args": vars(a), "build": [], "reads": []}
    print("articles=%d tiers=%s level=%s foundation=on workers=%d  load1=%s  questions=%s" % (
        len(docs), ",".join(TIERS), a.level, a.workers, os.getloadavg()[0], ",".join(q["id"] for q in qs)), flush=True)
    if not a.skip_build:
        t_all, c_all = time.time(), cpu_s()

        def log(state, stats):
            rec["build"].append({"step": state.step, "wall_s": round(stats["wall_s"], 1), "cpu_main_s": round(stats["cpu_main_s"], 1), "sentences": stats["sentences"],
                                 "closed": {t: sum(1 for c in state.crosses[t].values() if c.closed) for t in TIERS},
                                 "crosses": {t: len(state.crosses[t]) for t in TIERS}})
            print("build step %d: %d sentences, wall %.1f s, crosses %s, closed %s" % (
                state.step, stats["sentences"], stats["wall_s"], rec["build"][-1]["crosses"], rec["build"][-1]["closed"]), flush=True)
        state = st.build(docs, foundation="on", tiers=TIERS, level=a.level, workers=a.workers, save_root=a.root, log=log)
        rec["build_total"] = {"wall_s": round(time.time() - t_all, 1), "cpu_s": round(cpu_s() - c_all, 1)}
        print("BUILD total wall %.1f s cpu %.1f s" % (rec["build_total"]["wall_s"], rec["build_total"]["cpu_s"]), flush=True)
    cache = {}

    def index_at(k):
        if k not in cache:
            t0 = time.time()
            cache[k] = A.Index.from_stack(a.root, TIERS, data=DATA, step=k, foundation="on", level=a.level)
            rec.setdefault("load_s", {})[str(k)] = round(time.time() - t0, 1)
        return cache[k]
    for q in qs:
        ix = index_at(len(docs))
        r = read_one(ix, q, sc, a.grammar)
        rec["reads"].append(r)
        print("%s step %d  entry %d  %-22s listed %-3d gold %s first_gold %s partial %s  wall %.1f s cpu %.1f s" % (
            q["id"], r["step"], q["entry"], r["verdict"], r["listed"], "yes" if r["gold_in_candidate"] else "no", r["first_gold_pos"], r["partial"],
            r["wall_s"], r["cpu_s"]), flush=True)
        if a.also_at_entry and q["entry"] != len(docs):
            r2 = read_one(index_at(q["entry"]), q, sc, a.grammar)
            rec["reads"].append(r2)
            print("%s step %d  entry %d  %-22s listed %-3d gold %s first_gold %s partial %s  wall %.1f s cpu %.1f s" % (
                q["id"], r2["step"], q["entry"], r2["verdict"], r2["listed"], "yes" if r2["gold_in_candidate"] else "no", r2["first_gold_pos"], r2["partial"],
                r2["wall_s"], r2["cpu_s"]), flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
