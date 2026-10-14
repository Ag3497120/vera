"""Maintainer tool: (re)build verantyx/harness/evals/ from the research tree.  Not used by users and not run in CI: the files it writes are committed.

    python tools/build_evals.py --line3 /path/to/line3-checkout [--out verantyx/harness/evals]

It copies, byte for byte, the question banks the gate was measured on (bank2 = the dev set's first half, bank4, bank6, bank7, bank8), the 592-sentence `fulllead` corpus they are
asked over, and builds `memory.json` from two stores of the memory meter (meter_v1: MEM-T01 and MEM-T03, arm `notes`, repeat 1): the model's raw write calls with their turns, the
planted contradictions / updates / reversals of the task and its ten questions with their gold values.  It reads nothing from the held-out folders.  MANIFEST.json holds the sha256
of every file.  `expected.json` is NOT written here: it is the frozen record of `vera eval --freeze` (see docs/ARCHITECTURE.md)."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys

BANKS = {"bank2": "bank2/bank2.tsv", "bank4": "bank4/bank4.tsv", "bank6": "bank6/bank6.tsv", "bank7": "bank7/bank7.tsv", "bank8": "bank8/bank8.tsv"}
CORPUS = "bank2/data/fulllead_sents.jsonl"
MEMORY_TASKS = ("MEM-T01", "MEM-T03")
MEMORY_ARM, MEMORY_REPEAT = "notes", "r01"


def sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def meter_sessions(store: str):
    """The raw model calls of a meter store's session ledgers: declare_topic (ok) and every write call (ok or refused), with its turn."""
    out = []
    for d in sorted(glob.glob(os.path.join(store, "sessions", "s*"))):
        ops = []
        for ln in open(os.path.join(d, "ops.jsonl"), encoding="utf-8"):
            r = json.loads(ln)
            if r.get("actor") != "model":
                continue
            if r["op"] == "declare_topic" and r["result"].get("ok") is True:
                ops.append(["declare", r["result"]["topic"]])
            elif r["op"] == "write" and isinstance(r["args"].get("text"), str):
                ops.append(["write", r["args"]["text"], r["args"].get("turn")])
        out.append(ops)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--line3", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verantyx", "harness", "evals"))
    a = ap.parse_args()
    exp = os.path.join(a.line3, "experiments", "line3")
    sys.path.insert(0, os.path.join(exp, "loom"))
    sys.path.insert(0, a.line3)
    import mem_run                                                                  # the research tree's bank5 reader (normalises refs and kinds)
    os.makedirs(a.out, exist_ok=True)
    files = {}
    for name, rel in BANKS.items():
        dst = os.path.join(a.out, name + ".tsv")
        shutil.copyfile(os.path.join(exp, rel), dst)
        files[os.path.basename(dst)] = sha256(dst)
    dst = os.path.join(a.out, "fulllead_sents.jsonl")
    shutil.copyfile(os.path.join(exp, CORPUS), dst)
    files["fulllead_sents.jsonl"] = sha256(dst)
    tasks = []
    for tid in MEMORY_TASKS:
        run = os.path.join(exp, "mem", "meter_v1", tid, MEMORY_ARM, MEMORY_REPEAT)
        res = json.load(open(os.path.join(run, "result.json"), encoding="utf-8"))
        task = mem_run.find_task(tid)
        plants = [{"kind": p["kind"], "turns": sorted(mem_run.turn_id(s, i) for s, i in p["message_refs"])} for p in task["plants"]]
        qs = []
        for q in sorted(res["answers"], key=lambda x: x["index"]):
            gk, gv = mem_run.gold_values(q["gold"])
            qs.append({"index": q["index"], "q": q["q"], "kind": q["kind"], "gold_kind": gk, "gold": gv})
        tasks.append({"id": tid, "source": "meter_v1/%s/%s/%s" % (tid, MEMORY_ARM, MEMORY_REPEAT), "title": task["title"], "sessions": meter_sessions(os.path.join(run, "store")), "plants": plants, "questions": qs})
    dst = os.path.join(a.out, "memory.json")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(json.dumps({"schema": "vera-eval-memory-1", "tasks": tasks}, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    files["memory.json"] = sha256(dst)
    with open(os.path.join(a.out, "MANIFEST.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"schema": "vera-eval-manifest-1", "files": files}, indent=1, sort_keys=True) + "\n")
    print(json.dumps(files, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
