"""PUB-M2: `mem_run --profile mem.v4` end to end with a STUB model (no API, no network): the recorded client of `driver.ReplayClient` plays a script built from the task itself.

The stub is not a model: for every message of the story it writes the text (a text longer than 64 characters, the cap of one write, is cut at 「。」 into writes of its own); a text the shape
exchanger (shape.v2) gives an F0 clause is kept with `keep_unshaped` instead of `write` (the choice the owner's OP-PUB-2 offers a model); the first message of every session declares a topic; every
turn ends with `report([])`; every question is answered `abstain(no_record)`.  It exercises the harness path: the mem.v4 StructureDoor, the story driver with cap.v1 and forced reports, the
commit, the snapshot of the answer run, the answer runs, `verify_store`, `score_run`.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m2/stub_run.py --task MEM-T01 --arm notes --out DIR
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)

from verantyx.loom import driver as drv   # noqa: E402
from verantyx.loom import memshape as ms  # noqa: E402

TOPIC = "進捗確認"
WRITE_CAP = 64


def load_mem_run():
    path = os.path.join(ROOT, "experiments", "line3", "loom", "mem_run.py")
    if "mem_run" in sys.modules:
        return sys.modules["mem_run"]
    spec = importlib.util.spec_from_file_location("mem_run", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mem_run"] = mod
    spec.loader.exec_module(mod)
    return mod


def chunks(text: str):
    """The writes of one message: the text itself, or (over 64 characters) its sentences, cut after 「。」."""
    if len(text) <= WRITE_CAP:
        return [text]
    out, cur = [], ""
    for ch in text:
        cur += ch
        if ch == "。":
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def op_for(text: str):
    e = ms.exchange(text, ms.SHAPES_V2)
    return "write" if e.clauses and all(c.shape != "F0" for c in e.clauses) else "keep_unshaped"


def script(task: dict, order):
    T = lambda name, **a: ("tool", name, a)
    S = []
    for sess in task["sessions"]:
        for i, m in enumerate(sess):
            calls = [T("declare_topic", text=TOPIC)] if i == 0 else []
            for c in chunks(m["text"]):
                calls.append(T(op_for(c), text=c))
            calls.append(T("report", contradictions=[]))
            S.append(calls)
    for _ in order:
        S.append([T("abstain", type="no_record")])
    return S


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="MEM-T01")
    ap.add_argument("--arm", default="notes", choices=("blind", "notes"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeat", type=int, default=1)
    ns = ap.parse_args(argv)
    mr = load_mem_run()
    task = mr.find_task(ns.task)
    order = mr.question_order(task["id"], ns.repeat, len(task["questions"]))
    res = mr.run_one(task, ns.arm, ns.repeat, client=drv.ReplayClient(script(task, order)), model="stub-model", out_root=ns.out, profile="mem.v4")
    run_dir = os.path.join(ns.out, task["id"], ns.arm, "r%02d" % ns.repeat)
    sc = mr.score_run(run_dir, task)
    print(json.dumps({"ended": res["ended"], "store": res["store"], "verified": sc["verified"], "cost": res["cost"],
                      "turns_without_report": sum(len(s["turns_without_report"]) for s in res["sessions"]), "answers": sc["answers"]}, ensure_ascii=False, sort_keys=True, indent=1))
    return 0 if sc["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
