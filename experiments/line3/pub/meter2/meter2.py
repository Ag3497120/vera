"""PUB-M10-prep: the harness of the LONG-STORY METER, instrument v2 (docs/LINE3_PUBLIC_DESIGN.md 6, 8; owner OP-PUB-1..8, OP-PUB-8 as CHANGED; local decisions L-PUB-120..).

  PYTHONPATH=. python experiments/line3/pub/meter2/meter2.py --bank experiments/line3/bank_ls/dev/stories.jsonl --story LS-D01 --arms A0,A1,A3,A3f --repeats 1 --checkpoints 2 --client stub --out DIR
  PYTHONPATH=. python experiments/line3/pub/meter2/meter2.py --report DIR            # (re)build DIR/report.md and DIR/report.json from the result.json files under DIR; no run, no API
  PYTHONPATH=. python experiments/line3/pub/meter2/meter2.py --plan --bank ... --story ... --arms ... --repeats N --checkpoints K     # what a run would do; writes nothing

THE RUN.  One story set x arms {A0 context only, A1 log + grep, A3 structure (crosses), A3f flat table} x repeats.  A story is fed session by session (each session a NEW conversation; messages one by one with a turn
id "<session>-<message>"; every turn ends with `report`).  After the session named by a checkpoint (bank_ls: 4 checkpoints, `after_session`) the committed memory is asked that checkpoint's 10 questions
(kinds present | contested | updated | absent), each in a fresh conversation, and the next sessions follow.  `--checkpoints K` feeds only up to the K-th checkpoint (the smoke test: K = 2).
EVERY ARM has the same runaway cap (cap.v1), the same 24 tool calls and forced final `report` per turn, and the same per-turn BUDGET of tool-result characters (`--budget`, default 6000; recorded in the begin
row of every story ledger of A0 / A1 / A3 / A3f and, for a question, in `result.json`): `memview.BudgetDoor`, one class for all four.

THE ARMS (what each one is; the differing functions of A3f are listed in docs/LINE3_LOCAL_DECISIONS.md, L-PUB-12x):
  A0  membase.v3 context only: `report`.  Question phase: `answer`.
  A1  membase.v3 log: `log_append`, `log_grep(terms, max_lines)`, `log_read(start, end)`, `report`.  Question phase: `log_grep`, `log_read`, `answer`.
      ASYMMETRY (stated, not hidden): the log arm cannot use the loom's output gate (there is no evidence gate over a free log).  Its answer is the closed `answer(kind, values)` of the meter v1: a value of at most 32
      characters that is NOT required to be a quote of the log, scored by exact match (NFKC, case and space folded) against the gold -- more permissive than the structure arms' `weave_span` + `emit` (a verbatim quote
      passed by the gate).  Where the log arm is wrong, it is wrong with no gate; where the structure arm abstains for the gate's reasons, the log arm may be right.  So a structure win on right answers is conservative.
  A3  mem.v4 + the bundle `--bundle` (default m6d: shape.v4, ask.v3, qwords.v2) + `view.v1`; the answer run memanswer.v18 over the crosses.
  A3f the same, with `versions.index = flat.v1`: the same exchanger, write acceptance, provenance, notes and answer path (memanswer.v18) over a FLAT TABLE (no nests, no slide edges, no (n, p, a) key, no key swap).

THE CLIENT.  `--client stub` (default): the deterministic stub of `stub_client.py` (no network, no API; estimated tokens).  `--client api` needs `--allow-api` AND is refused unless the environment variable
VERA_METER2_ALLOW_API=1 is set: both default OFF; the SDK is imported only in that branch.  Nothing here runs the API by itself.

HELD-OUT SETS ARE SINGLE-USE.  A path with a `heldout` component is a judging set: `--judge` is required, the harness records the sha256 of the file in `used_heldout.jsonl` next to this file and REFUSES a second use of the
same set (`--allow-reuse` is the owner's), it prints no story text and writes no question / gold / answer text into `result.json` (counts and classes only).  The designer and the implementers never open such an output
folder: only `report.md` / `report.json`, which hold numbers.

Pure harness: it calls the loom's doors and drivers; no clock in any ledger (wall time is in result.json only).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from verantyx.loom import driver as drv                       # noqa: E402
from verantyx.loom import ledger as lg                        # noqa: E402
from verantyx.loom import memanswer as ma                     # noqa: E402
from verantyx.loom import memdoor as md                       # noqa: E402
from verantyx.loom import memdriver as mdrv                   # noqa: E402
from verantyx.loom import memory as mem                       # noqa: E402
from verantyx.loom import memview as mview                    # noqa: E402
import prompts as P                                           # noqa: E402
import scoring as S                                           # noqa: E402

SCHEMA = "meter2-1"
DEFAULT_MODEL = "claude-haiku-5-5"
DEFAULT_BUDGET = mview.BUDGET_DEFAULT
MAX_CALLS = mdrv.MAX_CALLS_PER_TURN_V3
ANSWER_MAX_TURNS = 40
ARMS: Dict[str, dict] = {
    "A0": {"arm": "context", "flat": False, "label": "context only"},
    "A1": {"arm": "log", "flat": False, "label": "log + grep"},
    "A3": {"arm": "notes", "flat": False, "label": "structure (crosses)"},
    "A3f": {"arm": "notes", "flat": True, "label": "flat table (no geometry)"},
}
BUNDLES = {"m6c": mem.V4_VERSIONS_M6C, "m6d": mem.V4_VERSIONS_M6D}
ANSWER_VERSION = ma.ANSWER_V18
USED_FILE = os.path.join(HERE, "used_heldout.jsonl")


class MeterError(Exception):
    pass


# ------------------------------------------------------------------------------------------------------------
# stories
# ------------------------------------------------------------------------------------------------------------
def is_heldout(path: str) -> bool:
    return any(part.startswith("heldout") for part in os.path.abspath(path).split(os.sep))


def stories_path(bank: str) -> str:
    return os.path.join(bank, "stories.jsonl") if os.path.isdir(bank) else bank


def check_story(d: dict) -> dict:
    """The bank_ls shape the harness needs (counts and refs only; it prints nothing of the text)."""
    if not (isinstance(d.get("id"), str) and isinstance(d.get("sessions"), list) and d["sessions"] and isinstance(d.get("questions"), list) and isinstance(d.get("checkpoints"), list) and d["checkpoints"]):
        raise MeterError("a story needs id, sessions, questions, checkpoints")
    for s in d["sessions"]:
        if not (isinstance(s, list) and s and all(isinstance(m, dict) and isinstance(m.get("speaker"), str) and isinstance(m.get("text"), str) and m["text"] for m in s)):
            raise MeterError("%s: a session is a non-empty list of {speaker, text}" % d["id"])
    for c in d["checkpoints"]:
        if not (isinstance(c.get("index"), int) and isinstance(c.get("after_session"), int) and 0 <= c["after_session"] < len(d["sessions"])):
            raise MeterError("%s: bad checkpoint" % d["id"])
    for q in d["questions"]:
        if not (isinstance(q.get("q"), str) and isinstance(q.get("gold"), str) and isinstance(q.get("checkpoint"), int)):
            raise MeterError("%s: a question has q, gold, checkpoint" % d["id"])
    d.setdefault("plants", [])
    return d


def load_stories(bank: str) -> List[dict]:
    out = []
    with open(stories_path(bank), encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                out.append(check_story(json.loads(ln)))
    return out


def question_order(story_id: str, cp: int, repeat: int, n: int) -> List[int]:
    """The order a checkpoint's questions are asked in: indices sorted by sha256("story|cp|repeat|i") -- a pure function, the same for every arm of that repeat."""
    return sorted(range(n), key=lambda i: hashlib.sha256(("%s|%d|%d|%d" % (story_id, cp, repeat, i)).encode("utf-8")).hexdigest())


def render(story: dict, s: int, i: int) -> str:
    m = story["sessions"][s][i]
    return "[%s] %s: %s" % (S.turn_id(s, i), m["speaker"], m["text"])


def intro_text(door: Any, story: dict, s: int, budget: int) -> str:
    n = len(story["sessions"])
    head = ("This is session %d of %d of the project \"%s\". It is a NEW conversation: you remember nothing of the earlier ones except through your tools.\n"
            "The result of begin (the rules, your tools and caps) follows; the first message of the session comes after it. Tool results are cut after %d characters per turn.\n"
            % (s + 1, n, story.get("title") or story["id"], budget))
    return head + json.dumps(door.intro(), ensure_ascii=False, sort_keys=True)


# ------------------------------------------------------------------------------------------------------------
# doors
# ------------------------------------------------------------------------------------------------------------
def versions_of(arm_key: str, bundle: str) -> Dict[str, str]:
    v = dict(BUNDLES[bundle])
    if ARMS[arm_key]["flat"]:
        v["index"] = mem.INDEX_FLAT
    return v


def story_door(arm_key: str, store: str, model: str, session_no: int, budget: int, bundle: str) -> Tuple[Any, Any]:
    a = ARMS[arm_key]
    if a["arm"] in md.STRUCTURE_ARMS:
        door = md.StructureDoor(store, a["arm"], model, profile=mem.PROFILE_V4, versions=versions_of(arm_key, bundle), view=mview.make_view(budget))
    else:
        door = md.BaselineDoor(store, a["arm"], "story", model, session_no=session_no, version=md.BASELINE_V3, budget=budget)
    return door, mview.BudgetDoor(door, budget, ledger=True)


def story_tool_specs(arm_key: str) -> Optional[dict]:
    return md.TOOL_SPECS_V3 if ARMS[arm_key]["arm"] in ("log",) else None


# ------------------------------------------------------------------------------------------------------------
# the question phase of one checkpoint
# ------------------------------------------------------------------------------------------------------------
def first_question_message(door: Any, begin_result: dict) -> str:
    if hasattr(door, "session"):
        return drv.first_message(begin_result)
    return ("The run has been begun for you; the run id is supplied by the system, never pass it. This is the result of begin:\n"
            + json.dumps({k: begin_result[k] for k in ("question", "tools", "caps") if k in begin_result}, ensure_ascii=False, sort_keys=True))


def ask_checkpoint(story: dict, cp: dict, arm_key: str, repeat: int, *, client: Any, model: str, store: str, run_dir: str, budget: int, bundle: str, choice: dict, strict: bool,
                   redact: bool) -> dict:
    a = ARMS[arm_key]
    qs = [(k, q) for k, q in enumerate(story["questions"]) if q["checkpoint"] == cp["index"]]
    order = question_order(story["id"], cp["index"], repeat, len(qs))
    snap = None
    if a["arm"] in md.STRUCTURE_ARMS:
        snap = ma.write_snapshot(store, topics=False, crosses=True, versions=True)
    rows_out: List[dict] = []
    scored: List[dict] = []
    for j in order:
        k, q = qs[j]
        if a["arm"] in md.STRUCTURE_ARMS:
            qd = md.AnswerDoor(store, a["arm"], q["q"], model, snapshot=snap, answer_version=ANSWER_VERSION)
            wd = mview.BudgetDoor(qd, budget, ledger=False)                         # an answer run is a loom run: its ledger is not extended; the cuts are in the result
        else:
            qd = md.BaselineDoor(store, a["arm"], "question", model, question=q["q"], version=md.BASELINE_V3, budget=budget)
            wd = mview.BudgetDoor(qd, budget, ledger=True)
            wd.set_turn("Q%d" % k)
        tools = md.api_tools(qd.tool_names, strict, done=True, specs=story_tool_specs(arm_key))
        er = drv.run_episode(client, wd, qd.run_id, model, P.system_prompt(arm_key, "question"), first_question_message(qd, qd.begin_result), tools, tool_choice=choice,
                             max_turns=ANSWER_MAX_TURNS, caps=drv.RUNAWAY_CAPS_V1)
        out = qd.output()
        ans = md.answer_of_output(out) if a["arm"] in md.STRUCTURE_ARMS else out
        cls = S.classify(ans, q)
        scored.append({"q": q, "answer": ans})
        e = er.to_obj()
        row = {"index": k, "kind": S.question_kind(q), "form": q.get("form"), "class": cls, "answer_kind": ans["kind"], "false_contested": S.false_contested(ans, q),
               "ended": e.get("ended"), "usage": e["usage"], "tool_calls": e.get("tool_calls", 0), "api_calls": e["usage"].get("calls", 0),
               "capped": bool(e.get("cap_hit")), "budget_cuts": len(wd.events), "budget_omitted": sum(x["omitted"] for x in wd.events)}
        if a["arm"] in md.STRUCTURE_ARMS:
            row["abstain_type"] = out.get("type") if out.get("status") == "abstained" else None
            row["answer_status"] = out.get("status")
        if not redact:
            row.update(q=q["q"], gold=q["gold"], answer=ans)
        rows_out.append(row)
    sc = S.score_answers(scored)
    return {"checkpoint": cp["index"], "after_session": cp["after_session"], "n": len(rows_out), "answers": rows_out, "score": sc}


# ------------------------------------------------------------------------------------------------------------
# detections from the story ledgers
# ------------------------------------------------------------------------------------------------------------
def story_ledger_dirs(store: str) -> List[str]:
    d = os.path.join(store, "sessions")
    return sorted(os.path.join(d, x) for x in os.listdir(d)) if os.path.isdir(d) else []


def read_rows(dir_: str) -> List[dict]:
    lines, _ = lg.read_raw_lines(dir_)
    return [lg._parse_line(ln) for ln in lines]


def detections(store: str, structure: bool) -> dict:
    notes: List[dict] = []
    turn_of_sid: Dict[int, str] = {}
    pairs: List[List[str]] = []
    sup_turns: List[str] = []
    for d in story_ledger_dirs(store):
        rows = read_rows(d)
        for r in rows:
            if r.get("actor") != "model":
                continue
            res = r.get("result") or {}
            if structure and r["op"] in ("write", "keep_unshaped") and res.get("ok") is True:
                sid = res["sid"]
                if res.get("turn"):
                    turn_of_sid[sid] = res["turn"]
                for n in res.get("notes", []):
                    n = dict(n)
                    n.setdefault("sid", sid)
                    if res.get("turn") and not n.get("turn"):
                        n["turn"] = res["turn"]
                    notes.append(n)
            elif structure and r["op"] == "supersede" and res.get("ok") is True:
                sid = (r.get("args") or {}).get("new_sid")
                if isinstance(sid, int) and sid in turn_of_sid:
                    sup_turns.append(turn_of_sid[sid])
        for p in md.noticed_pairs(rows):
            if p not in pairs:
                pairs.append(p)
    return {"notes": notes, "turn_of_sid": turn_of_sid, "pairs": sorted(pairs), "supersede_turns": sup_turns}


# ------------------------------------------------------------------------------------------------------------
# one run
# ------------------------------------------------------------------------------------------------------------
def zero_cost() -> dict:
    return {"api_calls": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0, "turns": 0, "turns_capped": 0, "turns_without_report": 0, "reports_forced": 0, "reports_missing": 0,
            "budget_cuts": 0, "budget_omitted_chars": 0, "story_input_tokens": 0, "question_input_tokens": 0, "question_api_calls": 0}


def run_one(story: dict, arm_key: str, repeat: int, *, client: Any, model: str, out_root: str, budget: int = DEFAULT_BUDGET, bundle: str = "m6d", n_checkpoints: int = 4,
            redact: bool = False, client_kind: str = "stub", max_calls: int = MAX_CALLS) -> dict:
    a = ARMS[arm_key]
    structure = a["arm"] in md.STRUCTURE_ARMS
    run_dir = os.path.join(out_root, story["id"], arm_key, "r%02d" % repeat)
    if os.path.exists(run_dir):
        raise MeterError("run folder exists (never overwritten): %s" % run_dir)
    os.makedirs(run_dir)
    store = os.path.join(run_dir, "store")
    cps = sorted(story["checkpoints"], key=lambda c: c["index"])[:n_checkpoints]
    last_session = cps[-1]["after_session"]
    cp_at = {c["after_session"]: c for c in cps}
    choice, strict = drv.tool_choice_for(model)
    t0 = time.monotonic_ns()
    result: Dict[str, Any] = {"schema": SCHEMA, "story": story["id"], "arm": arm_key, "arm_label": a["label"], "repeat": repeat, "model": model, "client": client_kind, "budget": budget,
                              "bundle": bundle if structure else None, "answer_version": ANSWER_VERSION if structure else None, "profile": mem.PROFILE_V4 if structure else md.BASELINE_V3,
                              "checkpoints_run": [c["index"] for c in cps], "last_session": last_session, "redacted": redact, "prompts": {ph: P.prompt_shas()[ph][arm_key] for ph in ("story", "question")},
                              "sessions": [], "checkpoints": [], "ended": "?"}
    cost = zero_cost()
    for s in range(last_session + 1):
        door, wd = story_door(arm_key, store, model, s + 1, budget, bundle)
        tools = md.api_tools(door.tool_names, strict, specs=story_tool_specs(arm_key))
        turns = [(S.turn_id(s, i), render(story, s, i)) for i in range(len(story["sessions"][s]))]
        res = mdrv.run_story_session(client, wd, model, P.system_prompt(arm_key, "story"), intro_text(wd, story, s, budget), turns, tools, tool_choice=choice, max_calls=max_calls,
                                     force_report=True, caps=drv.RUNAWAY_CAPS_V1)
        committed = None
        if res.ended == "complete":
            committed = wd.commit()
        if hasattr(door, "close"):
            door.close()
        ldir = door.session.ledger.dir if hasattr(door, "session") else door.ledger.dir
        st = res.to_obj()
        rows = read_rows(str(ldir))
        sess = {"session": s + 1, "messages": len(turns), "run_id": door.run_id, "ended": res.ended, "committed": committed is not None, "api_calls": st["api_calls"], "tool_calls": st["tool_calls"],
                "usage": st["usage"], "turns_capped": [h["turn"] for h in res.cap_hits], "turns_without_report": [t["turn"] for t in res.turns if t["report"] is None],
                "turns_forced": [t["turn"] for t in res.turns if t.get("forced")], "reports_missing": [t["turn"] for t in res.turns if t["ended"] == "report_missing"],
                "budget_cuts": len(wd.events), "budget_omitted_chars": sum(x["omitted"] for x in wd.events), "budget_rows_in_ledger": sum(1 for r in rows if r["op"] == "budget_turn"),
                "ledger": os.path.relpath(str(ldir), run_dir), "chars_by_tool": dict(sorted(wd.tool_chars.items()))}
        result["sessions"].append(sess)
        cost["api_calls"] += st["api_calls"]
        cost["tool_calls"] += st["tool_calls"]
        cost["input_tokens"] += st["usage"]["input_tokens"]
        cost["story_input_tokens"] += st["usage"]["input_tokens"]
        cost["output_tokens"] += st["usage"]["output_tokens"]
        cost["turns"] += len(res.turns)
        cost["turns_capped"] += len(sess["turns_capped"])
        cost["turns_without_report"] += len(sess["turns_without_report"])
        cost["reports_forced"] += len(sess["turns_forced"])
        cost["reports_missing"] += len(sess["reports_missing"])
        cost["budget_cuts"] += sess["budget_cuts"]
        cost["budget_omitted_chars"] += sess["budget_omitted_chars"]
        if res.ended != "complete":
            result["ended"] = "story_%s" % res.ended
            break
        if s in cp_at:
            cpr = ask_checkpoint(story, cp_at[s], arm_key, repeat, client=client, model=model, store=store, run_dir=run_dir, budget=budget, bundle=bundle, choice=choice, strict=strict,
                                 redact=redact)
            result["checkpoints"].append(cpr)
            for x in cpr["answers"]:
                cost["api_calls"] += x["api_calls"]
                cost["question_api_calls"] += x["api_calls"]
                cost["tool_calls"] += x["tool_calls"]
                cost["input_tokens"] += x["usage"]["input_tokens"]
                cost["question_input_tokens"] += x["usage"]["input_tokens"]
                cost["output_tokens"] += x["usage"]["output_tokens"]
                cost["turns_capped"] += 1 if x["capped"] else 0
                cost["budget_cuts"] += x["budget_cuts"]
                cost["budget_omitted_chars"] += x["budget_omitted"]
    else:
        result["ended"] = "complete"
    if structure:
        v = mem.verify_store(store, mem.FROM_HEADER)
        h = mem.MemStore(store).head()
        result["store"] = {"verify": v["status"], "sentences": 0 if h is None else h["sentences"], "sessions": 0 if h is None else len(h["sessions"])}
    det = detections(store, structure)
    result["plants"] = S.score_plants(story, last_session, det, structure, a["flat"])
    # the per-run answer score is the sum of the checkpoint scores (each answer carries its class already)
    tot = {"n": 0, **{c: 0 for c in S.CLASSES}, "false_contested": 0}
    kinds: Dict[str, Any] = {k: {"n": 0, **{c: 0 for c in S.CLASSES}} for k in S.ANSWER_KINDS}
    for c in result["checkpoints"]:
        for k in S.ANSWER_KINDS:
            for f in ("n",) + S.CLASSES:
                kinds[k][f] += c["score"][k][f]
        for f in ("n",) + S.CLASSES + ("false_contested",):
            tot[f] += c["score"]["total"][f]
    result["answers"] = {"by_kind": kinds, "total": tot, "right_per_mille": None if tot["n"] == 0 else tot["right"] * 1000 // tot["n"]}
    result["notes_counts"] = {t: sum(1 for n in det["notes"] if n["type"] == t) for t in ("SAME_SEAT", "UPDATE", "REVERSAL_X", "ENUMERATION", "SAME_QUESTION", "REVERSAL")} if structure else None
    result["reports"] = {"pairs": det["pairs"], "supersedes": len(det["supersede_turns"])}
    result["cost"] = cost
    result["wall_ns"] = time.monotonic_ns() - t0
    with open(os.path.join(run_dir, "result.json"), "x", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    return result


# ------------------------------------------------------------------------------------------------------------
# clients
# ------------------------------------------------------------------------------------------------------------
def make_client(kind: str, allow_api: bool, model: str) -> Any:
    if kind == "stub":
        import stub_client
        return stub_client.StubClient(model="stub-model")
    if kind == "api":
        if not allow_api:
            raise MeterError("--client api needs --allow-api (the real API costs money and is a separately approved step)")
        if os.environ.get("VERA_METER2_ALLOW_API") != "1":
            raise MeterError("--client api also needs the environment variable VERA_METER2_ALLOW_API=1")
        path = os.path.join(ROOT, "experiments", "line3", "loom", "harness.py")
        spec = importlib.util.spec_from_file_location("loom_harness_for_meter2", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["loom_harness_for_meter2"] = mod
        spec.loader.exec_module(mod)
        try:
            return mod.make_anthropic_client()
        except Exception as e:                                          # noqa: BLE001
            raise MeterError("no API client: %s" % e) from e
    raise MeterError("unknown client %r" % kind)


# ------------------------------------------------------------------------------------------------------------
# the report
# ------------------------------------------------------------------------------------------------------------
PREREG = [
    ("P-PUB-1", "Under the budget, A1's right answers fall well below the meter v1's 55/60 (916 per mille). Operationalised: A1 right_per_mille < 750."),
    ("P-PUB-2", "A3 notices more contradictions than A1 (structure or model, 'any'). Confirmed iff min over repeats of A3 > max over repeats of A1 (ranges do not overlap)."),
    ("P-PUB-3", "A3 and A3f differ little on same-seat contradictions (|mean A3 - mean A3f| <= 1 plant per story-set) and A3 is higher on reversals + updates ('any')."),
    ("P-PUB-4", "A3's input tokens are about those of A1 or lower. Operationalised: mean A3 <= 1.25 x mean A1."),
]


def load_results(root: str) -> List[dict]:
    out = []
    for p in sorted(glob.glob(os.path.join(root, "*", "*", "r*", "result.json"))):
        with open(p, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def per_repeat(results: Sequence[dict], arm: str, fn: Any) -> Dict[int, int]:
    """repeat -> the sum over the stories of fn(result), for the runs of `arm`."""
    d: Dict[int, int] = {}
    for r in results:
        if r["arm"] == arm:
            v = fn(r)
            if v is not None:
                d[r["repeat"]] = d.get(r["repeat"], 0) + v
    return d


def rng(d: Dict[int, int]) -> Optional[Tuple[int, int]]:
    return (min(d.values()), max(d.values())) if d else None


def mean(d: Dict[int, int]) -> Optional[float]:
    return sum(d.values()) / len(d) if d else None


def fmt(d: Dict[int, int]) -> str:
    if not d:
        return "n/a"
    lo, hi = min(d.values()), max(d.values())
    m = sum(d.values()) / len(d)
    ms = ("%d" % m) if m == int(m) else ("%.1f" % m)
    return "%s (%d-%d)" % (ms, lo, hi) if lo != hi else ms


def beats(a: Dict[int, int], b: Dict[int, int], higher: bool = True) -> Optional[bool]:
    """True iff the range of `a` lies strictly above (below if not higher) the range of `b`; None if either is empty."""
    ra, rb = rng(a), rng(b)
    if ra is None or rb is None:
        return None
    return ra[0] > rb[1] if higher else ra[1] < rb[0]


def metrics(results: Sequence[dict], arm: str) -> Dict[str, Dict[int, int]]:
    g = lambda f: per_repeat(results, arm, f)                                                       # noqa: E731
    pl = lambda kind, key: g(lambda r: r["plants"][kind][key])                                      # noqa: E731
    m = {
        "contra_n": g(lambda r: r["plants"]["contradiction"]["n"]), "contra_structure": pl("contradiction", "structure"), "contra_model": pl("contradiction", "model"), "contra_any": pl("contradiction", "any"),
        "reversal_n": g(lambda r: r["plants"]["reversal"]["n"]), "reversal_structure": pl("reversal", "structure"), "reversal_model": pl("reversal", "model"), "reversal_any": pl("reversal", "any"),
        "update_n": g(lambda r: r["plants"]["update"]["n"]), "update_structure": pl("update", "structure"), "update_model": pl("update", "model"), "update_any": pl("update", "any"),
        "false_structure_list_trap": g(lambda r: r["plants"]["false"]["structure_list_trap"]), "false_structure_unmatched": g(lambda r: r["plants"]["false"]["structure_unmatched"]),
        "false_model_pairs": g(lambda r: r["plants"]["false"]["model_false_pairs"]),
        "q_n": g(lambda r: r["answers"]["total"]["n"]), "q_right": g(lambda r: r["answers"]["total"]["right"]), "q_over_broad": g(lambda r: r["answers"]["total"]["over_broad"]),
        "q_abstain": g(lambda r: r["answers"]["total"]["abstain"]), "q_confident_wrong": g(lambda r: r["answers"]["total"]["confident_wrong"]),
        "q_absent_admit": g(lambda r: r["answers"]["total"]["absent_admit"]), "q_false_contested": g(lambda r: r["answers"]["total"]["false_contested"]),
        "right_per_mille": g(lambda r: r["answers"]["right_per_mille"]),
        "input_tokens": g(lambda r: r["cost"]["input_tokens"]), "output_tokens": g(lambda r: r["cost"]["output_tokens"]), "api_calls": g(lambda r: r["cost"]["api_calls"]),
        "tool_calls": g(lambda r: r["cost"]["tool_calls"]), "turns": g(lambda r: r["cost"]["turns"]), "turns_capped": g(lambda r: r["cost"]["turns_capped"]),
        "budget_cuts": g(lambda r: r["cost"]["budget_cuts"]), "budget_omitted_chars": g(lambda r: r["cost"]["budget_omitted_chars"]),
    }
    for k in S.ANSWER_KINDS:
        m["n_" + k] = g(lambda r, k=k: r["answers"]["by_kind"][k]["n"])
        m["right_" + k] = g(lambda r, k=k: r["answers"]["by_kind"][k]["absent_admit" if k == "absent" else "right"])
        m["wrong_" + k] = g(lambda r, k=k: r["answers"]["by_kind"][k]["confident_wrong"])
    return m


def build_report(root: str) -> dict:
    results = load_results(root)
    arms = [k for k in ARMS if any(r["arm"] == k for r in results)]
    M = {a: metrics(results, a) for a in arms}
    reps = sorted({r["repeat"] for r in results})
    stories = sorted({r["story"] for r in results})
    stub = any(r.get("client") == "stub" for r in results)
    verdict: Dict[str, Any] = {}

    def has(*a: str) -> bool:
        return all(x in M for x in a)

    if has("A1"):
        rpm = M["A1"]["right_per_mille"]
        verdict["P-PUB-1"] = None if not rpm else (mean(rpm) < 750)
    if has("A3", "A1"):
        verdict["P-PUB-2"] = beats(M["A3"]["contra_any"], M["A1"]["contra_any"])
    if has("A3", "A3f"):
        a3, a3f = M["A3"], M["A3f"]
        d_same = None if not a3["contra_any"] or not a3f["contra_any"] else abs(mean(a3["contra_any"]) - mean(a3f["contra_any"])) <= 1
        ra = {r: a3["reversal_any"].get(r, 0) + a3["update_any"].get(r, 0) for r in a3["reversal_any"]}
        rf = {r: a3f["reversal_any"].get(r, 0) + a3f["update_any"].get(r, 0) for r in a3f["reversal_any"]}
        verdict["P-PUB-3"] = None if d_same is None or not ra or not rf else bool(d_same and mean(ra) > mean(rf))
    if has("A3", "A1"):
        i3, i1 = M["A3"]["input_tokens"], M["A1"]["input_tokens"]
        verdict["P-PUB-4"] = None if not i3 or not i1 else mean(i3) <= 1.25 * mean(i1)
    # the two conditions of OP-PUB-8 (changed): P2 structure beats log, P3 geometry beats flat table
    p2 = p3 = None
    if has("A3", "A1"):
        a3, a1 = M["A3"], M["A1"]
        c = beats(a3["contra_any"], a1["contra_any"])
        r_ok = None if not a3["q_right"] or not a1["q_right"] else mean(a3["q_right"]) >= mean(a1["q_right"])
        w_ok = None if not a3["q_confident_wrong"] or not a1["q_confident_wrong"] else mean(a3["q_confident_wrong"]) <= mean(a1["q_confident_wrong"])
        p2 = None if None in (c, r_ok, w_ok) else bool(c and r_ok and w_ok)
    if has("A3", "A3f"):
        a3, a3f = M["A3"], M["A3f"]
        better = [beats(a3[k], a3f[k]) for k in ("contra_any", "reversal_any", "update_any", "q_right")]
        not_worse = [None if not a3[k] or not a3f[k] else mean(a3[k]) >= mean(a3f[k]) for k in ("contra_any", "reversal_any", "update_any", "q_right")]
        p3 = None if None in not_worse else bool(any(b is True for b in better) and all(not_worse))
    return {"stories": stories, "repeats": reps, "arms": arms, "client_is_stub": stub, "metrics": {a: {k: {str(r): v for r, v in d.items()} for k, d in M[a].items()} for a in arms},
            "predictions": verdict, "P2": p2, "P3": p3, "n_runs": len(results)}


def write_report(root: str) -> str:
    rep = build_report(root)
    results = load_results(root)
    arms = rep["arms"]
    M = {a: metrics(results, a) for a in arms}
    L: List[str] = []
    L.append("# Meter v2 report (long stories, equal per-turn budget)")
    L.append("")
    L.append("Stories: %s. Repeats: %s. Arms: %s. Runs: %d." % (", ".join(rep["stories"]), rep["repeats"], ", ".join("%s (%s)" % (a, ARMS[a]["label"]) for a in arms), rep["n_runs"]))
    if rep["client_is_stub"]:
        L.append("")
        L.append("**These runs used the deterministic STUB client: the numbers measure the harness, not a model. Tokens are estimates. No verdict below is a result about structure vs log.**")
    if len(rep["repeats"]) < 3:
        L.append("")
        L.append("Fewer than 3 repeats: a range is a single value, 'beats' is indicative only (OP-PUB-8 asks for ranges that do not overlap).")
    L.append("")
    L.append("Every cell is `mean (min-max)` over repeats of the SUM over the stories of the set.")
    L.append("")

    def table(title: str, rows: List[Tuple[str, str]]) -> None:
        L.append("## " + title)
        L.append("")
        L.append("| metric | " + " | ".join(arms) + " |")
        L.append("|---|" + "---|" * len(arms))
        for label, key in rows:
            L.append("| %s | %s |" % (label, " | ".join(fmt(M[a][key]) for a in arms)))
        L.append("")

    table("Plants noticed at intake (structure notes and model reports, separately)", [
        ("contradictions planted", "contra_n"), ("contradictions: structure notes", "contra_structure"), ("contradictions: model reports", "contra_model"), ("contradictions: either", "contra_any"),
        ("reversals planted", "reversal_n"), ("reversals: structure notes", "reversal_structure"), ("reversals: model reports", "reversal_model"), ("reversals: either", "reversal_any"),
        ("updates planted", "update_n"), ("updates: structure notes (UPDATE)", "update_structure"), ("updates: model (supersede)", "update_model"), ("updates: either", "update_any"),
        ("false alarm: structure, list-trap pairs", "false_structure_list_trap"), ("false alarm: structure, unmatched (an unplanted conflict is possible)", "false_structure_unmatched"),
        ("false alarm: model report pairs matching no plant", "false_model_pairs")])
    table("Answers at the checkpoints", [
        ("questions asked", "q_n"), ("right", "q_right"), ("over-broad", "q_over_broad"), ("abstain", "q_abstain"), ("confident wrong", "q_confident_wrong"), ("absent admitted (right)", "q_absent_admit"),
        ("false conflict claimed (inside confident wrong)", "q_false_contested"), ("right per mille", "right_per_mille"),
        ("present: asked", "n_present"), ("present: right", "right_present"), ("present: confident wrong", "wrong_present"),
        ("contested: asked", "n_contested"), ("contested: right", "right_contested"), ("contested: confident wrong", "wrong_contested"),
        ("updated: asked", "n_updated"), ("updated: right", "right_updated"), ("updated: confident wrong", "wrong_updated"),
        ("absent: asked", "n_absent"), ("absent: admitted (right)", "right_absent"), ("absent: confident wrong", "wrong_absent")])
    table("Cost (tokens are estimates when the client is the stub)", [
        ("input tokens", "input_tokens"), ("output tokens", "output_tokens"), ("API calls (assistant turns)", "api_calls"), ("tool calls", "tool_calls"), ("story turns", "turns"),
        ("turns / episodes capped by the runaway cap", "turns_capped"), ("results cut by the budget", "budget_cuts"), ("characters omitted by the budget", "budget_omitted_chars")])
    L.append("## P2 and P3 (OP-PUB-8, changed: revise until BOTH hold)")
    L.append("")
    L.append("- **P2, the structure beats the log + search** (A3 vs A1): contradictions found (either) with ranges that do not overlap, right answers at least equal, confident wrong at most equal. Verdict: **%s**." % {True: "met", False: "not met", None: "not decidable (missing arm or data)"}[rep["P2"]])
    L.append("- **P3, the geometry beats the flat table** (A3 vs A3f): ranges that do not overlap on at least one of contradictions / reversals / updates / right answers, and not worse on the others. Verdict: **%s**." % {True: "met", False: "not met", None: "not decidable (missing arm or data)"}[rep["P3"]])
    L.append("")
    L.append("## Pre-registered predictions P-PUB-1..4 (design 6.4; thresholds are this harness's operationalisation, frozen with the code)")
    L.append("")
    L.append("| id | prediction | outcome |")
    L.append("|---|---|---|")
    for pid, text in PREREG:
        v = rep["predictions"].get(pid)
        L.append("| %s | %s | %s |" % (pid, text, {True: "confirmed", False: "not confirmed", None: "not decidable"}[v]))
    L.append("")
    L.append("Asymmetry of A1 (see the module doc): its answer is a closed value scored by exact match, not a gate-passed quote.")
    path = os.path.join(root, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(root, "report.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(rep, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    return path


# ------------------------------------------------------------------------------------------------------------
# held-out single use
# ------------------------------------------------------------------------------------------------------------
def register_heldout(path: str, allow_reuse: bool) -> str:
    sha = hashlib.sha256(open(stories_path(path), "rb").read()).hexdigest()
    used = []
    if os.path.exists(USED_FILE):
        used = [json.loads(ln) for ln in open(USED_FILE, encoding="utf-8") if ln.strip()]
    if any(u["sha256"] == sha for u in used) and not allow_reuse:
        raise MeterError("this judging set was already used (sha256 %s...): a held-out set is single-use (design 6.6); --allow-reuse is the owner's" % sha[:12])
    with open(USED_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"sha256": sha, "path": os.path.relpath(os.path.abspath(path), ROOT)}, sort_keys=True) + "\n")
    return sha


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="meter2", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", default=None, help="a bank_ls split folder or its stories.jsonl")
    ap.add_argument("--story", default=None, help="comma-separated story ids (default: all)")
    ap.add_argument("--arms", default="A0,A1,A3,A3f")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--checkpoints", type=int, default=4, help="feed the story up to the K-th checkpoint (default 4 = all)")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--bundle", default="m6d", choices=sorted(BUNDLES))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--client", default="stub", choices=("stub", "api"))
    ap.add_argument("--allow-api", action="store_true", help="REQUIRED with --client api (default OFF)")
    ap.add_argument("--judge", action="store_true", help="REQUIRED for a held-out split (single use)")
    ap.add_argument("--allow-reuse", action="store_true", help="the owner's: use a judging set a second time")
    ap.add_argument("--redact", action="store_true", help="write no question / gold / answer text into result.json (automatic for a held-out split)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--report", default=None, metavar="DIR", help="build report.md / report.json from the result.json files under DIR and exit")
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        if ns.report:
            print(write_report(ns.report))
            return 0
        if not ns.bank or (not ns.out and not ns.plan):
            raise MeterError("--bank and --out are required")
        arms = [x for x in ns.arms.split(",") if x]
        for x in arms:
            if x not in ARMS:
                raise MeterError("unknown arm %r (A0, A1, A3, A3f)" % x)
        client = None if ns.plan else make_client(ns.client, ns.allow_api, ns.model)       # refuses (--client api without --allow-api) before anything is read, registered or run
        held = is_heldout(ns.bank)
        if held and not ns.judge and not ns.plan:
            raise MeterError("a held-out split needs --judge (it is single-use, design 6.6)")
        stories = load_stories(ns.bank)
        if ns.story:
            want = ns.story.split(",")
            stories = [s for s in stories if s["id"] in want]
        if not stories:
            raise MeterError("no story selected")
        redact = held or ns.redact
        if ns.plan:
            plan = [{"story": s["id"], "sessions_fed": sorted(s["checkpoints"], key=lambda c: c["index"])[:ns.checkpoints][-1]["after_session"] + 1, "arms": arms, "repeats": ns.repeats} for s in stories]
            print(json.dumps({"runs": len(stories) * len(arms) * ns.repeats, "plan": plan, "budget": ns.budget, "client": ns.client, "model": ns.model, "held_out": held}, ensure_ascii=False, sort_keys=True, indent=1))
            return 0
        if held:
            print("held-out split registered: sha256 %s..." % register_heldout(ns.bank, ns.allow_reuse))
        os.makedirs(ns.out, exist_ok=True)
        for story in stories:
            for rep in range(1, ns.repeats + 1):
                for arm in arms:
                    r = run_one(story, arm, rep, client=client, model=ns.model, out_root=ns.out, budget=ns.budget, bundle=ns.bundle, n_checkpoints=ns.checkpoints, redact=redact, client_kind=ns.client)
                    tot = r["answers"]["total"]
                    print("%s %-3s r%02d %s  plants(any) c=%d/%d r=%d/%d u=%d/%d  answers right=%d/%d wrong=%d  tokens in=%d out=%d%s" % (
                        story["id"] if not held else "(held-out)", arm, rep, r["ended"], r["plants"]["contradiction"]["any"], r["plants"]["contradiction"]["n"], r["plants"]["reversal"]["any"],
                        r["plants"]["reversal"]["n"], r["plants"]["update"]["any"], r["plants"]["update"]["n"], tot["right"], tot["n"], tot["confident_wrong"], r["cost"]["input_tokens"],
                        r["cost"]["output_tokens"], " (estimated)" if ns.client == "stub" else ""))
        print(write_report(ns.out))
        return 0
    except MeterError as e:
        print("meter2: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
