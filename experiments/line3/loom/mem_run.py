"""MEM-d: the harness entry points of the memory meter (docs/LINE3_LOOM_MEMORY_DESIGN.md 5; docs/LINE3_LOCAL_DECISIONS.md MEM-d; owner 2026-10-13 「記憶の計器の前の決定」).

  python experiments/line3/loom/mem_run.py --list [--bank PATH]
  python experiments/line3/loom/mem_run.py --validate [--bank PATH]                          # the bank5 schema checks (exit 1 on a problem)
  python experiments/line3/loom/mem_run.py --prepare --task MEM-T01 --arm notes            # prints the plan (tool lists, agent files, folders); writes nothing
  python experiments/line3/loom/mem_run.py --task MEM-T01 --arm notes --repeat 2 [--model claude-haiku-5-5] [--out DIR]     # ONE run: repeat number 2 of (task, arm)
  python experiments/line3/loom/mem_run.py --task MEM-T01 --arm notes --repeats 3          # repeats 1, 2, 3 in turn
  python experiments/line3/loom/mem_run.py --score DIR/MEM-T01/notes/r02                   # the raw mechanical reading of a finished run (no API)
  python experiments/line3/loom/mem_run.py --task ... --arm ... [--profile mem.v2|mem.v3]  # mem.v3 (the default, MEM-fix) or mem.v2 = the meter v1's settings (12 calls a turn, no forced report)

THE TASK (the bank5 schema, bank2-author/PROMPT5.md): {id, title, sessions: [[{speaker, text}, ...] x3], plants: [{kind, fact, values, message_refs: [[s, i], ...], note}],
questions: [{q, gold, kind, refs}]}.  The model never sees plants, golds or kinds.  `--bank` defaults to the audited bank5 (`experiments/line3/bank5/bank5.jsonl`) when it exists, then the toy task
`experiments/line3/loom/mem_toy.jsonl` (MEM-TOY1); a task id is looked up in the bank(s) in that order.  The audited bank5 (README.md there): refs 0-based, plant kinds contradiction | update | list_trap | repeat | reversal, question kinds contradiction | update | plain, gold 「矛盾: X と Y」 /
the latest value / the value; the questions of a task come in ONE fixed order, so a run SHUFFLES them (`question_order`: a pure function of task id and repeat, the same for every arm).
message_refs are 0-based [session, message] pairs (a bank whose refs are all
1-based is detected from the value strings it plants, and normalised: `load_tasks`; a ref must name a message that holds at least one value of its plant).

THE ARMS (owner: 構造なし / 平文ログ / 構造(注記なし) / 構造(注記あり)):  context (A0), log (A1), blind (A2b), notes (A2).  Each story session is a NEW conversation; messages arrive one by one
with a turn id "<session>-<message>" (1-based); every turn ends with `report` (the same closed tool in every arm); after the 3rd session each question is a fresh conversation
(the answer phase).  Only the arm's tools carry anything across a session: the MemStore (structure arms), the log (A1), nothing (A0).

THE OUTPUT of one run, `<out>/<task>/<arm>/r<k>/`: `store/` (the MemStore with its session ledgers and the answer-run ledgers under answers/; or the baseline ledgers) and `result.json`
(everything mechanical: per-session driver reports, the reports the model made, the plants noticed, the structure's events, the answers as {kind, values} with the raw `hit`).  Nothing
is overwritten.  The API meter itself (MEM-g) is the operator's run; this module never calls a network on its own: `--driver api` builds the client through harness.make_anthropic_client.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from verantyx.ledger_events import LedgerError                                  # noqa: E402
from verantyx.loom import driver as drv                                         # noqa: E402
from verantyx.loom import ledger as lg                                          # noqa: E402
from verantyx.loom import memanswer as ma                                       # noqa: E402
from verantyx.loom import memdoor as md                                         # noqa: E402
from verantyx.loom import memdriver as mdrv                                     # noqa: E402
from verantyx.loom import memory as mem                                         # noqa: E402
from verantyx.loom.state import Refuse                                          # noqa: E402

TOY_BANK = os.path.join(HERE, "mem_toy.jsonl")
BANK5 = os.path.join(ROOT, "experiments", "line3", "bank5", "bank5.jsonl")        # the AUDITED bank5 (on line3: 6 tasks MEM-T01..T06; AUDIT5.md, README.md there); this worktree gets it with the merge
OUT_ROOT = os.path.join(ROOT, "experiments", "line3", "mem", "runs")
AGENTS_DIR = os.path.join(ROOT, ".claude", "agents")
DEFAULT_MODEL = "claude-haiku-5-5"
SCHEMA = "mem-run-1"
SCHEMA_V3 = "mem-run-2"                                  # MEM-fix: a mem.v3 run (result.json also says profile, turn_limit, forced / missing reports)
PROFILE_CHOICES = (mem.PROFILE_V2, mem.PROFILE_V3)
MAX_CALLS_V3 = mdrv.MAX_CALLS_PER_TURN_V3
STORY_AGENT = {"context": "mem-plain", "log": "mem-log", "blind": "mem-blind", "notes": "mem-writer"}
QUESTION_AGENT = {"context": "mem-plain", "log": "mem-log", "blind": "mem-answer", "notes": "mem-answer"}
TOOL_PREFIX = "mcp__vera-mem__"
ANSWER_MAX_TURNS = 40
STORY_NOTE = ("\n\n(Driver note: this is the STORY phase. The session has already begun; its first message and the result of begin are in the first user message. Never pass run_id. "
              "Messages arrive one at a time; end every turn with report. The session ends when the last message has been handled.)\n")
QUESTION_NOTE = ("\n\n(Driver note: this is the QUESTION phase. One question, one conversation. The run has already begun; its result is in the first message. Never pass run_id. "
                 "The episode ends when your answer is accepted, or you call done.)\n")


class MemRunError(Exception):
    def __init__(self, msg: str, code: Optional[str] = None) -> None:
        super().__init__(("%s: %s" % (code, msg)) if code else msg)
        self.code = code


# ------------------------------------------------------------------------------------------------------------
# agent files
# ------------------------------------------------------------------------------------------------------------
def parse_agent_file(path: str) -> Tuple[Dict[str, Any], str]:
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---\n"):
        raise MemRunError("%s: no front matter" % path)
    end = text.index("\n---\n", 4)
    meta: Dict[str, Any] = {}
    for ln in text[4:end].splitlines():
        if ln.strip():
            k, _, v = ln.partition(":")
            meta[k.strip()] = v.strip()
    if "tools" in meta:
        meta["tools"] = [t.strip() for t in meta["tools"].split(",") if t.strip()]
    return meta, text[end + 5:]


def agent_path(name: str) -> str:
    return os.path.join(AGENTS_DIR, name + ".md")


def system_prompt(arm: str, phase: str) -> str:
    name = (STORY_AGENT if phase == "story" else QUESTION_AGENT)[arm]
    _, body = parse_agent_file(agent_path(name))
    return body + (STORY_NOTE if phase == "story" else QUESTION_NOTE)


def agent_sha(arm: str, phase: str) -> str:
    return hashlib.sha256(system_prompt(arm, phase).encode("utf-8")).hexdigest()


def expected_agent_tools(arm: str, phase: str) -> List[str]:
    """The `tools:` list the agent file of (arm, phase) must carry: the arm's tools of that phase; a BASELINE arm's file serves both phases, so it carries the union."""
    if arm in md.STRUCTURE_ARMS:
        names = list((md.STORY_TOOLS if phase == "story" else md.QUESTION_TOOLS)[arm])
    else:
        names = list(md.STORY_TOOLS[arm])
        names += [n for n in md.QUESTION_TOOLS[arm] if n not in names]
    return [TOOL_PREFIX + n for n in names]


# ------------------------------------------------------------------------------------------------------------
# the bank
# ------------------------------------------------------------------------------------------------------------
_KIND_WORDS = (("contradiction", ("contradiction", "矛盾")), ("update", ("update", "更新", "変更")), ("list_trap", ("list", "trap", "列挙")),
               ("repeat", ("repeat", "繰り返し", "再掲")), ("reversal", ("reversal", "逆", "前提")))


def canon_plant_kind(kind: str) -> str:
    k = (kind or "").lower()
    for name, words in _KIND_WORDS:
        if any(w in k for w in words):
            return name
    return k


def canon_question_kind(kind: str) -> str:
    k = (kind or "").lower()
    if "contradict" in k or "矛盾" in k:
        return "contradicted"
    if "update" in k or "更新" in k or "変更" in k:
        return "updated"
    return "plain"


def _refs_ok(sessions: Sequence[Sequence[dict]], plants: Sequence[dict], base: int) -> bool:
    for p in plants:
        for s, i in p["message_refs"]:
            s, i = s - base, i - base
            if not (0 <= s < len(sessions) and 0 <= i < len(sessions[s])):
                return False
            if not any(v in sessions[s][i]["text"] for v in p["values"]):         # a referenced message holds at least one of the plant's values (the values of a contradiction differ per message)
                return False
    return True


def normalize_task(d: dict) -> dict:
    """A bank row -> the task the harness uses: refs 0-based, kinds canonical.  Refuses (MemRunError) a row that is not the bank5 shape."""
    if not isinstance(d, dict) or not isinstance(d.get("id"), str) or not d["id"]:
        raise MemRunError("a task has a non-empty string id", "bad_task")
    sessions = d.get("sessions")
    if not (isinstance(sessions, list) and sessions and all(isinstance(s, list) and s for s in sessions)):
        raise MemRunError("%s: sessions is a non-empty list of non-empty message lists" % d["id"], "bad_task")
    for s in sessions:
        for m in s:
            if not (isinstance(m, dict) and isinstance(m.get("speaker"), str) and isinstance(m.get("text"), str) and m["text"]):
                raise MemRunError("%s: a message is {speaker, text}" % d["id"], "bad_task")
    plants = d.get("plants", [])
    qs = d.get("questions", [])
    for p in plants:
        if not (isinstance(p, dict) and isinstance(p.get("values"), list) and isinstance(p.get("message_refs"), list)
                and all(isinstance(r, list) and len(r) == 2 and all(isinstance(x, int) for x in r) for r in p["message_refs"])):
            raise MemRunError("%s: a plant has values and message_refs [[s, i], ...]" % d["id"], "bad_task")
    for q in qs:
        if not (isinstance(q, dict) and isinstance(q.get("q"), str) and isinstance(q.get("gold"), str) and q["q"]):
            raise MemRunError("%s: a question has q and gold" % d["id"], "bad_task")
    base = 0
    if plants and not _refs_ok(sessions, plants, 0):
        if _refs_ok(sessions, plants, 1):
            base = 1
        else:
            raise MemRunError("%s: message_refs name no message that holds the plant's values (0- or 1-based)" % d["id"], "bad_refs")

    def shift(r: Sequence[Sequence[int]]) -> List[List[int]]:
        return [[s - base, i - base] for s, i in r]

    return {"id": d["id"], "title": d.get("title", ""), "sessions": [[{"speaker": m["speaker"], "text": m["text"]} for m in s] for s in sessions],
            "plants": [{"kind": canon_plant_kind(p.get("kind", "")), "fact": p.get("fact", ""), "values": list(p["values"]), "message_refs": shift(p["message_refs"]),
                        "note": p.get("note", "")} for p in plants],
            "questions": [{"q": q["q"], "gold": q["gold"], "kind": canon_question_kind(q.get("kind", "")), "refs": shift(q.get("refs", []))} for q in qs]}


PLANT_KINDS = ("contradiction", "update", "list_trap", "repeat", "reversal")
BANK5_SHAPE = {"sessions": 3, "questions": 10, "plants": {"contradiction": 6, "update": 3, "list_trap": 4, "repeat": 2, "reversal": 2},
               "question_kinds": {"contradicted": 4, "updated": 3, "plain": 3}}


def bank_problems(task: dict, shape: Optional[dict] = None) -> List[str]:
    """What is wrong with a normalised task against the bank5 schema (`shape` = BANK5_SHAPE for the audited bank: 3 sessions, 10 questions, 6/3/4/2/2 plants, 4/3/3 question kinds);
    always: known plant kinds, refs in range, an update / contradiction gold of the right form, every question has a gold.  [] = fine."""
    out: List[str] = []
    for p in task["plants"]:
        if p["kind"] not in PLANT_KINDS:
            out.append("unknown plant kind %r" % p["kind"])
        if len(p["message_refs"]) < 1:
            out.append("plant %r has no message_refs" % p["fact"])
    for q in task["questions"]:
        gk, gv = gold_values(q["gold"])
        if q["kind"] == "contradicted" and (gk != "contested" or len(gv) != 2):
            out.append("question %r is contradicted but its gold is not 「矛盾: X と Y」" % q["q"])
        if q["kind"] != "contradicted" and gk == "contested":
            out.append("question %r has a contradiction gold but is %s" % (q["q"], q["kind"]))
        for s_, i_ in q["refs"]:
            if not (0 <= s_ < len(task["sessions"]) and 0 <= i_ < len(task["sessions"][s_])):
                out.append("question %r names a message that does not exist" % q["q"])
    if shape is not None:
        if len(task["sessions"]) != shape["sessions"]:
            out.append("%d sessions, want %d" % (len(task["sessions"]), shape["sessions"]))
        if len(task["questions"]) != shape["questions"]:
            out.append("%d questions, want %d" % (len(task["questions"]), shape["questions"]))
        pk = {k: sum(1 for p in task["plants"] if p["kind"] == k) for k in shape["plants"]}
        if pk != shape["plants"]:
            out.append("plant kinds %s, want %s" % (pk, shape["plants"]))
        qk = {k: sum(1 for q in task["questions"] if q["kind"] == k) for k in shape["question_kinds"]}
        if qk != shape["question_kinds"]:
            out.append("question kinds %s, want %s" % (qk, shape["question_kinds"]))
    return out


def question_order(task_id: str, repeat: int, n: int) -> List[int]:
    """The order a run asks the questions in: the indices 0..n-1 sorted by sha256("task|repeat|i") -- a pure function of the task and the repeat (no clock, no random module), the
    same for every arm of that repeat, different for the next repeat.  (The bank's questions come in one positional order; a model must not be able to learn it.)"""
    return sorted(range(n), key=lambda i: hashlib.sha256(("%s|%d|%d" % (task_id, repeat, i)).encode("utf-8")).hexdigest())


def load_tasks(path: str) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for n, ln in enumerate(f, 1):
            if not ln.strip():
                continue
            try:
                row = json.loads(ln)
            except ValueError as e:
                raise MemRunError("%s line %d is not JSON" % (path, n), "bad_task") from e
            t = normalize_task(row)
            if t["id"] in out:
                raise MemRunError("duplicate task id %s" % t["id"], "bad_task")
            out[t["id"]] = t
    return out


def bank_paths(bank: Optional[str]) -> List[str]:
    if bank:
        return [bank]
    env = os.environ.get("MEM_BANK")
    return [p for p in ([env] if env else []) + [BANK5, TOY_BANK] if os.path.isfile(p)]


def find_task(task_id: str, bank: Optional[str] = None) -> dict:
    for p in bank_paths(bank):
        ts = load_tasks(p)
        if task_id in ts:
            return ts[task_id]
    raise MemRunError("task %r is in none of %s" % (task_id, bank_paths(bank)), "unknown_task")


def turn_id(s: int, i: int) -> str:
    return "%d-%d" % (s + 1, i + 1)


def render(task: dict, s: int, i: int) -> str:
    m = task["sessions"][s][i]
    return "[%s] %s: %s" % (turn_id(s, i), m["speaker"], m["text"])


# ------------------------------------------------------------------------------------------------------------
# the reading of a finished run (mechanical; MEM-g builds the tables from these)
# ------------------------------------------------------------------------------------------------------------
def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().replace(" ", "").replace("　", "")


def gold_values(gold: str) -> Tuple[str, List[str]]:
    """('contested', [X, Y]) for a gold 「矛盾: X と Y」, else ('value', [gold])."""
    g = gold.strip()
    for head in ("矛盾:", "矛盾："):
        if g.startswith(head):
            rest = g[len(head):].strip()
            parts = [p.strip() for p in rest.split(" と ")] if " と " in rest else [p.strip() for p in rest.split("と")]
            return "contested", [p for p in parts if p]
    return "value", [g]


def answer_hit(answer: dict, q: dict) -> Optional[bool]:
    """Did the answer equal the gold?  contradicted -> kind contested holding exactly the gold values; updated / plain -> kind value equal to the gold.  None for a `none` answer
    (an abstention is neither right nor wrong here: the tables count it)."""
    if answer["kind"] == "none":
        return None
    gk, gv = gold_values(q["gold"])
    if answer["kind"] != gk:
        return False
    return sorted(_norm(v) for v in answer["values"]) == sorted(_norm(v) for v in gv)


def plants_noticed(task: dict, pairs: Sequence[Sequence[str]]) -> List[dict]:
    """For each plant: was it NOTICED, i.e. did some report name a pair of turns that are both among the plant's message_refs (two different messages)?  A lookup."""
    want = [set(turn_id(s, i) for s, i in p["message_refs"]) for p in task["plants"]]
    out = []
    for k, p in enumerate(task["plants"]):
        hit = [list(pr) for pr in pairs if pr[0] in want[k] and pr[1] in want[k] and pr[0] != pr[1]]
        out.append({"plant": k, "kind": p["kind"], "fact": p["fact"], "noticed": bool(hit), "pairs": hit})
    return out


def false_pairs(task: dict, pairs: Sequence[Sequence[str]]) -> List[List[str]]:
    """The reported pairs that are two messages of NO contradiction / reversal plant (an update, a list trap, a repeat or nothing): the false alarms, as a lookup."""
    real = [set(turn_id(s, i) for s, i in p["message_refs"]) for p in task["plants"] if p["kind"] in ("contradiction", "reversal")]
    return [list(pr) for pr in pairs if not any(pr[0] in w and pr[1] in w for w in real)]


# ------------------------------------------------------------------------------------------------------------
# one run
# ------------------------------------------------------------------------------------------------------------
def _intro_text(door: Any, task: dict, s: int) -> str:
    n = len(task["sessions"])
    head = ("This is session %d of %d of the project \"%s\". It is a NEW conversation: you remember nothing of the earlier ones except through your tools.\n"
            "The result of begin (the rules, your tools and caps) follows; the first message of the session comes after it.\n" % (s + 1, n, task["title"] or task["id"]))
    return head + json.dumps(door.intro(), ensure_ascii=False, sort_keys=True)


def _first_question_message(door: Any, begin_result: dict) -> str:
    if hasattr(door, "session"):                                   # AnswerDoor: the loom's own first message (task text, rules, the loom's cut of the question)
        return drv.first_message(begin_result)
    return ("The run has been begun for you; the run id is supplied by the system, never pass it. This is the result of begin:\n"
            + json.dumps({k: begin_result[k] for k in ("question", "tools", "caps") if k in begin_result}, ensure_ascii=False, sort_keys=True))


def run_one(task: dict, arm: str, repeat: int, *, client: Any, model: str, out_root: str, tag: str = "", max_calls: Optional[int] = None,
            extra_api: Optional[dict] = None, profile: str = mem.PROFILE_V2) -> dict:
    """Run one (task, arm, repeat): the story sessions, then the questions.  Returns the result object (also written to result.json).  Refuses to touch an existing run folder.

    `profile` (MEM-fix, L-MEM-62..64): `mem.v2` (the API default here: the meter v1, 12 tool calls a turn, no forced report) or `mem.v3` (the CLI default: the structure arms' sessions are mem.v3, the
    baselines membase.v2, the answer run memanswer.v2; 24 tool calls a turn for EVERY arm and a turn that ends without a report gets the forced final `report` or an explicit `report_missing`).
    `max_calls` overrides the profile's limit."""
    if arm not in md.ARMS:
        raise MemRunError("arm must be one of %s" % (md.ARMS,), "bad_arm")
    if profile not in PROFILE_CHOICES:
        raise MemRunError("profile must be one of %s" % (PROFILE_CHOICES,), "bad_profile")
    v3 = profile == mem.PROFILE_V3
    caps = drv.RUNAWAY_CAPS_V1 if v3 else None          # PUB-H1: every mem.v3 run is driven with cap.v1 (the `cap_turn` row is a mem.v3 / membase.v2 row); mem.v2 reproduces the meter v1 as it was
    if max_calls is None:
        max_calls = MAX_CALLS_V3 if v3 else mdrv.MAX_CALLS_PER_TURN
    base_version = md.BASELINE_V2 if v3 else md.BASELINE_VERSION
    answer_version = ma.ANSWER_V2 if v3 else ma.ANSWER_VERSION
    run_dir = os.path.join(out_root, task["id"], arm + (("." + tag) if tag else ""), "r%02d" % repeat)
    if os.path.exists(run_dir):
        raise MemRunError("run folder exists (never overwritten): %s" % run_dir, "run_exists")
    os.makedirs(run_dir)
    store = os.path.join(run_dir, "store")
    choice, strict = drv.tool_choice_for(model)
    t0 = time.monotonic_ns()
    result: Dict[str, Any] = {"schema": SCHEMA_V3 if v3 else SCHEMA, "task_id": task["id"], "arm": arm, "arm_label": md.ARM_LABEL[arm], "repeat": repeat, "model": model, "tool_choice": choice,
                              "system_prompt_sha256": {"story": agent_sha(arm, "story"), "question": agent_sha(arm, "question")},
                              "tools": {"story": list(md.STORY_TOOLS[arm]), "question": list(md.QUESTION_TOOLS[arm])}, "sessions": [], "answers": []}
    if v3:
        result.update(profile=profile, turn_limit=max_calls, baseline_version=base_version, answer_version=answer_version)
    all_pairs: List[List[str]] = []
    # -- the story phase: every session a new conversation -----------------------------------------------------------
    for s, msgs in enumerate(task["sessions"]):
        door = (md.StructureDoor(store, arm, model, profile=profile) if arm in md.STRUCTURE_ARMS
                else md.BaselineDoor(store, arm, "story", model, session_no=s + 1, version=base_version))
        tools = md.api_tools(door.tool_names, strict)
        sysp = system_prompt(arm, "story")
        turns = [(turn_id(s, i), render(task, s, i)) for i in range(len(msgs))]
        res = mdrv.run_story_session(client, door, model, sysp, _intro_text(door, task, s), turns, tools, tool_choice=choice, max_calls=max_calls, extra=extra_api,
                                      force_report=v3, caps=caps)
        committed = None
        if res.ended == "complete":
            committed = door.commit()
        if hasattr(door, "close"):
            door.close()
        ledger_dir = door.session.ledger.dir if hasattr(door, "session") else door.ledger.dir
        rows = [lg._parse_line(ln) for ln in lg.read_raw_lines(ledger_dir)[0]]
        pairs = md.noticed_pairs(rows)
        all_pairs += [p for p in pairs if p not in all_pairs]
        sess: Dict[str, Any] = {"session": s + 1, "run_id": door.run_id, "ledger": os.path.relpath(str(ledger_dir), run_dir), "story": res.to_obj(), "committed": committed is not None,
                                "reports": md.reports_of(rows), "turns_without_report": [t["turn"] for t in res.turns if t["report"] is None]}
        if caps is not None:
            sess["turns_capped"] = [h["turn"] for h in res.cap_hits]                 # PUB-H1: the turns the runaway cap ended (counted per arm in cost.turns_capped)
        if v3:
            sess["turns_forced"] = [t["turn"] for t in res.turns if t.get("forced")]
            sess["turns_report_missing"] = [t["turn"] for t in res.turns if t["ended"] == "report_missing"]
        if hasattr(door, "session"):
            sess["events"] = door.session.events()
        result["sessions"].append(sess)
        if res.ended != "complete":
            result["ended"] = "story_api_error"
            break
    else:
        result["ended"] = "story_complete"
    result["reports"] = {"pairs": sorted(all_pairs)}
    result["noticed"] = plants_noticed(task, all_pairs)
    result["false_pairs"] = false_pairs(task, all_pairs)
    # -- the question phase: one conversation per question ---------------------------------------------------------------
    if result["ended"] == "story_complete":
        snap = ma.write_snapshot(store, topics=v3) if arm in md.STRUCTURE_ARMS else None
        if snap is not None:
            result["snapshot"] = {k: snap[k] for k in ("name", "sha256", "sentences", "superseded")}
        order = question_order(task["id"], repeat, len(task["questions"]))
        result["question_order"] = order
        for k in order:
            q = task["questions"][k]
            qd = (md.AnswerDoor(store, arm, q["q"], model, snapshot=snap, answer_version=answer_version) if arm in md.STRUCTURE_ARMS
                  else md.BaselineDoor(store, arm, "question", model, question=q["q"], version=base_version))
            tools = md.api_tools(qd.tool_names, strict, done=True)
            er = drv.run_episode(client, qd, qd.run_id, model, system_prompt(arm, "question"), _first_question_message(qd, qd.begin_result), tools, tool_choice=choice,
                                 max_turns=ANSWER_MAX_TURNS, extra=extra_api, caps=caps)
            out = qd.output()
            ans = md.answer_of_output(out) if arm in md.STRUCTURE_ARMS else out
            ledger_dir = qd.session.ledger.dir if hasattr(qd, "session") else qd.ledger.dir
            result["answers"].append({"index": k, "q": q["q"], "kind": q["kind"], "gold": q["gold"], "run_id": qd.run_id, "ledger": os.path.relpath(str(ledger_dir), run_dir),
                                      "episode": er.to_obj(), "answer": ans, "hit": answer_hit(ans, q), "output": out if arm in md.STRUCTURE_ARMS else None})
    # -- the store ----------------------------------------------------------------------------------------------------
    if arm in md.STRUCTURE_ARMS:
        v = mem.verify_store(store, mem.FROM_HEADER)
        h = mem.MemStore(store).head()
        result["store"] = {"verify": v["status"], "sentences": 0 if h is None else h["sentences"], "sessions": 0 if h is None else len(h["sessions"])}
    result["cost"] = _cost(result)
    result["wall"] = {"run_ns": time.monotonic_ns() - t0}
    with open(os.path.join(run_dir, "result.json"), "x", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    return result


def _cost(result: dict) -> dict:
    """What the run cost, from the result alone: rewrites (the form: refused-then-rewritten sentences), tool calls, API calls and tokens, turns without a report."""
    c = {"api_calls": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0, "rewrites": 0, "refused_writes": 0, "turns_without_report": 0, "text_blocks_dropped": 0}
    for s in result["sessions"]:
        st = s["story"]
        c["api_calls"] += st["api_calls"]
        c["tool_calls"] += st["tool_calls"]
        c["input_tokens"] += st["usage"]["input_tokens"]
        c["output_tokens"] += st["usage"]["output_tokens"]
        c["text_blocks_dropped"] += st["text_blocks_dropped"]
        c["turns_without_report"] += len(s["turns_without_report"])
        if "turns_capped" in s:
            c["turns_capped"] = c.get("turns_capped", 0) + len(s["turns_capped"])
        if "turns_forced" in s:
            c["reports_forced"] = c.get("reports_forced", 0) + len(s["turns_forced"])
            c["reports_missing"] = c.get("reports_missing", 0) + len(s["turns_report_missing"])
        ev = s.get("events")
        if ev:
            c["rewrites"] += ev["rewrites"]["rewritten"]
            c["refused_writes"] += ev["rewrites"]["refused"]
    for a in result["answers"]:
        e = a["episode"]
        c["api_calls"] += e["usage"]["calls"]
        c["tool_calls"] += e["tool_calls"]
        c["input_tokens"] += e["usage"]["input_tokens"]
        c["output_tokens"] += e["usage"]["output_tokens"]
    return c


def score_run(run_dir: str, task: dict) -> dict:
    """The raw reading of a finished run from its folder (no API): verify every ledger and tabulate what the run says.  Not the MEM-g tables."""
    with open(os.path.join(run_dir, "result.json"), encoding="utf-8") as f:
        r = json.load(f)
    store = os.path.join(run_dir, "store")
    arm = r["arm"]
    checks: Dict[str, str] = {}
    if arm in md.STRUCTURE_ARMS:
        checks["store"] = mem.verify_store(store, mem.FROM_HEADER)["status"]
        for a in r["answers"]:
            checks[a["run_id"]] = ma.verify_answer(os.path.join(run_dir, a["ledger"]), store)["status"]
    else:
        for s in r["sessions"]:
            checks[s["run_id"]] = md.verify_baseline(os.path.join(run_dir, s["ledger"]))["status"]
        for a in r["answers"]:
            checks[a["run_id"]] = md.verify_baseline(os.path.join(run_dir, a["ledger"]))["status"]
    hits = [a["hit"] for a in r["answers"]]
    return {"task_id": r["task_id"], "arm": r["arm_label"], "repeat": r["repeat"], "verified": all(v == "OK" for v in checks.values()), "checks": checks,
            "noticed": sum(1 for n in r["noticed"] if n["noticed"] and n["kind"] in ("contradiction", "reversal")),
            "planted": sum(1 for n in r["noticed"] if n["kind"] in ("contradiction", "reversal")), "false_pairs": len(r["false_pairs"]),
            "answers": {"hit": sum(1 for h in hits if h is True), "miss": sum(1 for h in hits if h is False), "none": sum(1 for h in hits if h is None), "n": len(hits)},
            "cost": r["cost"]}


# ------------------------------------------------------------------------------------------------------------
# the plan and the CLI
# ------------------------------------------------------------------------------------------------------------
def prepare(task: dict, arm: str, model: str, out_root: str, repeat: int = 1, profile: str = mem.PROFILE_V2) -> dict:
    """What a run would do.  Writes nothing."""
    return {"profile": profile, "turn_limit": MAX_CALLS_V3 if profile == mem.PROFILE_V3 else mdrv.MAX_CALLS_PER_TURN, "task_id": task["id"], "arm": arm, "arm_label": md.ARM_LABEL[arm], "model": model, "repeat": repeat, "run_dir": os.path.join(out_root, task["id"], arm, "r%02d" % repeat),
            "sessions": [len(s) for s in task["sessions"]], "questions": len(task["questions"]),
            "story": {"agent": STORY_AGENT[arm], "tools": [TOOL_PREFIX + n for n in md.STORY_TOOLS[arm]], "system_prompt_sha256": agent_sha(arm, "story")},
            "question": {"agent": QUESTION_AGENT[arm], "tools": [TOOL_PREFIX + n for n in md.QUESTION_TOOLS[arm]], "system_prompt_sha256": agent_sha(arm, "question")},
            "command": "python experiments/line3/loom/mem_run.py --task %s --arm %s --repeat %d --model %s --profile %s" % (task["id"], arm, repeat, model, profile)}


def make_client(driver: str, script: Optional[str]) -> Any:
    if driver == "api":
        spec = importlib.util.spec_from_file_location("loom_harness_for_mem", os.path.join(HERE, "harness.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["loom_harness_for_mem"] = mod
        spec.loader.exec_module(mod)
        try:
            return mod.make_anthropic_client()
        except Exception as e:                                       # noqa: BLE001  harness.HarnessError: no SDK / no key -> a typed refusal of this CLI, nothing was called
            raise MemRunError(str(e), "no_client") from e
    if driver == "replay":
        if not script:
            raise MemRunError("--driver replay needs --script FILE (a JSON list of turns: [[\"text\", s] | [\"tool\", name, {...}] ...])", "no_script")
        with open(script, encoding="utf-8") as f:
            turns = [[tuple(b) for b in t] for t in json.load(f)]
        return drv.ReplayClient(turns)
    raise MemRunError("unknown driver %r" % driver, "bad_driver")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="mem_run", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", default=None, help="a bank5-schema JSONL (default: bank5 when it exists, then the toy task)")
    ap.add_argument("--out", default=OUT_ROOT, help="the folder runs are written under (default experiments/line3/mem/runs)")
    ap.add_argument("--list", action="store_true", help="list the tasks of the bank(s)")
    ap.add_argument("--validate", action="store_true", help="check every task of the bank(s) against the bank5 schema (the audited bank also against its shape)")
    ap.add_argument("--prepare", action="store_true", help="print the plan for --task / --arm and exit")
    ap.add_argument("--score", default=None, metavar="RUN_DIR", help="the raw mechanical reading of a finished run (needs --task for the plants)")
    ap.add_argument("--task", default=None)
    ap.add_argument("--arm", default=None, choices=md.ARMS)
    ap.add_argument("--repeat", type=int, default=1, help="the repeat NUMBER of this run (1-based)")
    ap.add_argument("--repeats", type=int, default=None, help="run repeats 1..N in turn (instead of --repeat)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--driver", default=None, choices=("api", "replay"), help="REQUIRED to run: api = the real model through the Anthropic API (costs money, needs network and a key); replay = a recorded script")
    ap.add_argument("--script", default=None, help="--driver replay: the recorded turns (JSON)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--profile", default=mem.PROFILE_V3, choices=PROFILE_CHOICES,
                    help="mem.v3 (default, MEM-fix: topic rule v2, cited REVERSAL, topic-aware answer recall, 24 tool calls a turn + forced final report for every arm, long-story caps) or mem.v2 (the meter v1)")
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        if ns.list:
            for p in bank_paths(ns.bank):
                for t in load_tasks(p).values():
                    print("%-14s %s  sessions=%s questions=%d  %s" % (t["id"], os.path.relpath(p, ROOT), [len(s) for s in t["sessions"]], len(t["questions"]), t["title"]))
            return 0
        if ns.validate:
            bad = 0
            for p in bank_paths(ns.bank):
                for t in load_tasks(p).values():
                    probs = bank_problems(t, BANK5_SHAPE if os.path.abspath(p) == os.path.abspath(BANK5) else None)
                    bad += len(probs)
                    print("%-12s %s %s" % (t["id"], os.path.relpath(p, ROOT), "ok" if not probs else "; ".join(probs)))
            return 1 if bad else 0
        if ns.score:
            if not ns.task:
                raise MemRunError("--score needs --task (the plants)", "no_task")
            print(json.dumps(score_run(ns.score, find_task(ns.task, ns.bank)), ensure_ascii=False, sort_keys=True, indent=1))
            return 0
        if not ns.task or not ns.arm:
            raise MemRunError("--task and --arm are required", "no_task")
        task = find_task(ns.task, ns.bank)
        if ns.prepare:
            print(json.dumps(prepare(task, ns.arm, ns.model, ns.out, ns.repeat, ns.profile), ensure_ascii=False, sort_keys=True, indent=1))
            return 0
        if ns.driver is None:
            raise MemRunError("say which driver runs it: --driver api (the real model: network, a key, money) or --driver replay --script FILE", "no_driver")
        for k in (range(1, ns.repeats + 1) if ns.repeats else [ns.repeat]):
            client = make_client(ns.driver, ns.script)
            r = run_one(task, ns.arm, k, client=client, model=ns.model, out_root=ns.out, tag=ns.tag, profile=ns.profile)
            print("%s %s r%02d %s noticed=%d/%d answers hit=%d/%d  ->  %s" % (
                r["task_id"], r["arm_label"], k, r["ended"], sum(1 for n in r["noticed"] if n["noticed"] and n["kind"] in ("contradiction", "reversal")),
                sum(1 for n in r["noticed"] if n["kind"] in ("contradiction", "reversal")), sum(1 for a in r["answers"] if a["hit"] is True), len(r["answers"]),
                os.path.relpath(os.path.join(ns.out, r["task_id"], ns.arm + (("." + ns.tag) if ns.tag else ""), "r%02d" % k), ROOT)))
        return 0
    except (MemRunError, LedgerError, Refuse) as e:
        print("mem_run: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
