"""MEM-fix: re-run the RECORDED model calls of a stored meter under mem.v3, offline (no API, no model).

The meter's structure arms (A2b, A2) stored every call the model made in its session ledgers.  This script feeds the same calls, in the same order, to fresh stores under profile `mem.v3`
(through a `StructureDoor`, so the turn of a write / report is the door's, as in a run), and reads what the v3 structure does with them:
  - a declared topic that holds a particle (のにでとをが) is refused by v3 (L-MEM-58); the model of a real run would pick another, so the re-run strips the particles from it
    (培養条件の共同実験 -> 培養条件共同実験): the stand-in of "the model adapted", and the only change made to a recorded call;
  - everything else is the recorded call as it was; a call that refers to a sid (supersede) is made as recorded and may be refused if the stores diverged.
It reports, per arm and in total, the stored sentences, the refused writes (by reason), the expanded sentences, the share of unreadable self-questions, the SAME_QUESTION pairs that hit
planted contradictions, the REVERSAL precision with the cited pairs, and (with --reach) the recall reach of the answer run on the new stores (offline_reach's evaluation).
The new stores go to --work (default: a fresh folder you name; they are not part of the repo).
  python experiments/line3/mem/memfix/rerun_story.py --work DIR [--meter DIR] [--out DIR] [--reach] [--limit N] [--no-clause-at --name rerun_story_no_clause_at]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import memfix_common as C
import offline_reach as OR
import reversal_precision as RP
from verantyx.loom import memanswer as ma
from verantyx.loom import memdoor as md
from verantyx.loom import memnotes as mn
from verantyx.loom import memory as mem

REPLAYED = ("declare_topic", "write", "supersede", "recall", "read_sentence", "lookup", "status", "report")


def strip_particles(topic: str) -> str:
    return "".join(ch for ch in topic if ch not in mem.TOPIC_FORBIDDEN)


def rerun_store(src_store: str, dst_store: str, profile: str = mem.PROFILE_V3) -> dict:
    """Feed the recorded model calls of every committed session of `src_store` to a new store; -> {"refused": {...}, "calls": n}."""
    refused: Dict[str, int] = collections.Counter()
    calls = 0
    for run_id, rows in C.session_ledger_rows(src_store):
        door = md.StructureDoor(dst_store, "notes", "rerun", profile=profile)
        for r in rows:
            if r["actor"] != "model" or r["op"] not in REPLAYED or r.get("truncated"):
                continue
            args = dict(r["args"])
            turn = args.get("turn") or r["result"].get("turn")
            if turn:
                door.set_turn(turn)
            if r["op"] == "declare_topic" and profile == mem.PROFILE_V3:
                args["text"] = strip_particles(args["text"])
            res = door.call(r["op"], args)
            calls += 1
            if res.get("ok") is not True:
                refused["%s:%s" % (r["op"], res.get("refusal"))] += 1
        door.commit()
        door.close()
    return {"refused": dict(sorted(refused.items())), "calls": calls}


def store_stats(store: str) -> dict:
    """What a store's ledgers say: ok writes, refused writes by reason, expanded writes, note counts, unreadable by reason, SAME_QUESTION pairs."""
    st = collections.Counter()
    notes = collections.Counter()
    unread = collections.Counter()
    sq_pairs: List[List[str]] = []
    for _rid, rows in C.session_ledger_rows(store):
        for r in rows:
            if r["actor"] == "model" and r["op"] == "write":
                if r["result"].get("ok") is True:
                    st["ok_writes"] += 1
                    if "implicit_topic" in r["result"]:
                        st["expanded"] += 1
                else:
                    st["refused_writes"] += 1
                    st["refused:" + str(r["result"].get("refusal")) + ":" + str(r["result"].get("detail", {}).get("reason", ""))] += 1
        for w in C.written_with_notes(rows):
            for n in w["notes"]:
                notes[n["type"]] += 1
                if n["type"] == mn.SELF_QUESTION_UNREADABLE:
                    unread[n.get("reason", "gate")] += 1
                if n["type"] == mn.SAME_QUESTION:
                    turns = [[o.get("turn") for o in v["occurrences"] if o.get("turn")] for v in n["variants"]]
                    for i in range(len(turns)):
                        for j in range(i + 1, len(turns)):
                            for a in turns[i]:
                                for b in turns[j]:
                                    if a != b and sorted([a, b]) not in sq_pairs:
                                        sq_pairs.append(sorted([a, b]))
    return {"counts": dict(st), "notes": dict(notes), "unreadable": dict(unread), "same_question_pairs": sorted(sq_pairs)}


def plants_hit(task: dict, pairs: Sequence[Sequence[str]]) -> int:
    plants = C.plant_sets(task)
    hit = set()
    for a, b in pairs:
        for k in C.classify_pair(plants, a, b):
            if plants[k]["kind"] == "contradiction":
                hit.add(k)
    return len(hit)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meter", default=C.METER_V1)
    ap.add_argument("--work", required=True, help="a folder for the re-run stores (created; never overwritten)")
    ap.add_argument("--out", default=os.path.join(C.HERE, "results"))
    ap.add_argument("--reach", action="store_true", help="also evaluate the recall reach on the new stores")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-clause-at", action="store_true", help="counterfactual: a mem.v3 session WITHOUT `clause_at` (a sentence with its own subject is asked from its first unit as in v2)")
    ap.add_argument("--name", default="rerun_story", help="the result file name (without .json)")
    ns = ap.parse_args(argv)
    if ns.no_clause_at:
        mem.clause_run_start = lambda *a, **k: None
    dirs = C.structure_runs(ns.meter)[:ns.limit]
    per: List[dict] = []
    reach_runs: List[dict] = []
    for d in dirs:
        r = C.load_result(d)
        task = C.mem_run.find_task(r["task_id"])
        dst = os.path.join(ns.work, C.label(d).replace("/", "_"), "store")
        if os.path.exists(dst):
            raise SystemExit("exists: %s" % dst)
        rr = rerun_store(os.path.join(d, "store"), dst)
        old = store_stats(os.path.join(d, "store"))
        new = store_stats(dst)
        entry = {"run": C.label(d), "arm": r["arm_label"], "task": r["task_id"], "calls": rr["calls"], "refused_calls": rr["refused"],
                 "old": dict(old, plants_hit=plants_hit(task, old["same_question_pairs"])), "new": dict(new, plants_hit=plants_hit(task, new["same_question_pairs"]))}
        entry["reversal_old"] = RP.analyse_store(os.path.join(d, "store"), task)
        entry["reversal_new"] = RP.analyse_store(dst, task, use_cite=True)
        per.append(entry)
        if ns.reach:
            snap = ma.write_snapshot(dst, topics=True)
            from verantyx.loom.corpus import Corpus
            from verantyx.loom import evidence as ev, memrecall as mr
            data, rows = ma.read_snapshot(snap["path"])
            corpus, sup, topics = Corpus(data), ma.superseded_of_rows(rows), snap["topics"]
            qs = []
            for a in sorted(r["answers"], key=lambda a: a["index"]):
                gk, gv = C.mem_run.gold_values(a["gold"])
                q = {"index": a["index"], "q": a["q"], "kind": a["kind"], "gold": gv}
                for name, tp in (("before", None), ("after", topics)):
                    res = mr.recall(corpus, a["q"], ev.EVIDENCE_V2, subject_guard=True, superseded=sup or None, topics=tp or None)
                    q[name] = {"verdict": res["verdict"], "strict": OR.judge(res, a["kind"], gv, False), "lenient": OR.judge(res, a["kind"], gv, True)}
                qs.append(q)
            reach_runs.append({"run": C.label(d), "arm": r["arm_label"], "task": r["task_id"], "topics": topics, "sentences": len(rows), "questions": qs})
        print(entry["run"], rr["calls"], new["counts"].get("ok_writes"), "ok writes,", new["counts"].get("refused_writes", 0), "refused", flush=True)

    def agg(sel: Sequence[dict], side: str) -> dict:
        c = collections.Counter()
        notes = collections.Counter()
        unread = collections.Counter()
        hit = 0
        for e in sel:
            c.update(e[side]["counts"])
            notes.update(e[side]["notes"])
            unread.update(e[side]["unreadable"])
            hit += e[side]["plants_hit"]
        n_ok = c["ok_writes"]
        return {"ok_writes": n_ok, "refused_writes": c["refused_writes"], "expanded": c["expanded"], "notes": dict(notes), "unreadable": dict(unread),
                "unreadable_share": round(sum(unread.values()) / n_ok, 3) if n_ok else None, "contradiction_plants_hit_by_same_question": hit,
                "refused_by_reason": {k[len("refused:"):]: v for k, v in sorted(c.items()) if k.startswith("refused:")}}

    out = {"meter": os.path.relpath(ns.meter, C.ROOT), "runs": len(per), "clause_at": not ns.no_clause_at, "note": "the recorded model calls re-run under mem.v3; declared topics lose their particles (the stand-in of a model that adapted)",
           "total": {"old": agg(per, "old"), "new": agg(per, "new"), "reversal_old": RP.tally([e["reversal_old"] for e in per]), "reversal_new": RP.tally([e["reversal_new"] for e in per])},
           "by_arm": {arm: {"old": agg([e for e in per if e["arm"] == arm], "old"), "new": agg([e for e in per if e["arm"] == arm], "new"),
                            "reversal_old": RP.tally([e["reversal_old"] for e in per if e["arm"] == arm]), "reversal_new": RP.tally([e["reversal_new"] for e in per if e["arm"] == arm])}
                      for arm in ("A2b", "A2")},
           "by_task": {t: {"old": agg([e for e in per if e["task"] == t], "old"), "new": agg([e for e in per if e["task"] == t], "new")} for t in sorted({e["task"] for e in per})},
           "per_run": per}
    if ns.reach:
        out["reach"] = {"total": OR.tally(reach_runs), "by_arm": {arm: OR.tally([r for r in reach_runs if r["arm"] == arm]) for arm in ("A2b", "A2")}}
    os.makedirs(ns.out, exist_ok=True)
    with open(os.path.join(ns.out, ns.name + ".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True, indent=1)
        f.write("\n")
    print(json.dumps({"total": out["total"], "reach": out.get("reach", {}).get("total")}, ensure_ascii=False, sort_keys=True, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
