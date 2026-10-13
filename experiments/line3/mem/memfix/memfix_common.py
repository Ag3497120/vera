"""MEM-fix offline tools: shared helpers.  No network, no API: everything here reads stored stores / ledgers and runs the structure's own code.

`structure_stores(meter)` lists the meter's structure-arm run folders; `load_run` reads result.json + the bank task; `answer_snapshot` gives the corpus of the answer phase of a stored
store (the snapshot file the stored answer runs were begun on); `topics_of_store` the declared topics of its session ledgers."""
from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
LOOM = os.path.join(ROOT, "experiments", "line3", "loom")
if LOOM not in sys.path:
    sys.path.insert(0, LOOM)

import mem_run                                                                  # noqa: E402
from verantyx.loom import memanswer as ma                                       # noqa: E402
from verantyx.loom import memnotes as mn                                        # noqa: E402
from verantyx.loom import memory as mem                                         # noqa: E402
from verantyx.loom.corpus import Corpus                                         # noqa: E402

METER_V1 = os.path.join(ROOT, "experiments", "line3", "mem", "meter_v1")
STRUCTURE = ("blind", "notes")


def structure_runs(meter: str = METER_V1) -> List[str]:
    """['<meter>/MEM-T01/blind/r01', ...] sorted: the structure arms' run folders (those with a store)."""
    out = []
    for arm in STRUCTURE:
        out += sorted(glob.glob(os.path.join(meter, "*", arm, "r*")))
    return sorted(out, key=lambda p: (p.split(os.sep)[-3], p.split(os.sep)[-2], p.split(os.sep)[-1]))


def load_result(run_dir: str) -> dict:
    with open(os.path.join(run_dir, "result.json"), encoding="utf-8") as f:
        return json.load(f)


def label(run_dir: str) -> str:
    p = run_dir.split(os.sep)
    return "%s/%s/%s" % (p[-3], p[-2], p[-1])


def snapshot_corpus(store: str) -> Tuple[Corpus, List[dict], Dict[int, dict]]:
    """(corpus, rows, supersede marks) of the answer phase of a stored store: the one snapshot file in <store>/snapshots."""
    snaps = sorted(glob.glob(os.path.join(store, "snapshots", "memory_*.jsonl")))
    if len(snaps) != 1:
        raise RuntimeError("%s: expected one snapshot, found %d" % (store, len(snaps)))
    data, rows = ma.read_snapshot(snaps[0])
    return Corpus(data), rows, ma.superseded_of_rows(rows)


def topics_of_store(store: str) -> List[str]:
    """The distinct declared topics of the store's committed sessions, first declaration first (from the verified session ledgers)."""
    head = mem.MemStore(store).head()
    ents: List[dict] = []
    for e in head["sessions"]:
        ents += mem.session_topics(mem.MemStore(store).sessions_dir / e["run_id"])
    return ma.distinct_topics(ents)


def norm(s: str) -> str:
    return mn.norm_answer(s)


def match(gold: str, answer: str, lenient: bool) -> bool:
    """Does the recalled answer text stand for the gold value?  strict: equal after the gate's own normalisation; lenient: one is a prefix of the other (the unit after the number:
    gold 37.0℃ / answer 37.0), the shorter at least two characters."""
    a, b = norm(gold), norm(answer)
    if a == b:
        return True
    if not lenient:
        return False
    s, l = (a, b) if len(a) <= len(b) else (b, a)
    return len(s) >= 2 and l.startswith(s)


# ------------------------------------------------------------------------------------------------------------
# ledgers
# ------------------------------------------------------------------------------------------------------------
def session_ledger_rows(store: str) -> List[Tuple[str, List[dict]]]:
    """[(run_id, rows)] of the committed sessions of a store, in order (the ops.jsonl rows, parsed)."""
    head = mem.MemStore(store).head()
    out = []
    for e in head["sessions"]:
        with open(os.path.join(store, "sessions", e["run_id"], "ops.jsonl"), encoding="utf-8") as f:
            out.append((e["run_id"], [json.loads(ln) for ln in f if ln.strip()]))
    return out


def written_with_notes(rows: Sequence[dict]) -> List[dict]:
    """[{i, sid, turn, text, notes}] for every ok write of a session ledger, with the notes of the loom_note row that follows it."""
    out = []
    for k, r in enumerate(rows):
        if r["actor"] == "model" and r["op"] == "write" and r["result"].get("ok") is True:
            notes = []
            if k + 1 < len(rows) and rows[k + 1]["actor"] == mn.NOTE_ACTOR and rows[k + 1]["op"] == mn.NOTE_OP:
                notes = rows[k + 1]["args"]["notes"]
            out.append({"i": r["i"], "sid": r["result"]["sid"], "turn": r["result"].get("turn"), "text": r["result"]["text"], "notes": notes})
    return out


def memory_rows(store: str) -> List[dict]:
    return mem.MemStore(store).rows()


def plant_sets(task: dict) -> List[dict]:
    """[{kind, turns: set of turn ids}] for every plant of a task."""
    return [{"kind": p["kind"], "turns": {mem_run.turn_id(s, i) for s, i in p["message_refs"]}} for p in task["plants"]]


def classify_pair(plants: Sequence[dict], a: str, b: str) -> List[int]:
    """The indices of the plants whose message_refs hold both turns."""
    return [k for k, p in enumerate(plants) if a in p["turns"] and b in p["turns"] and a != b]
