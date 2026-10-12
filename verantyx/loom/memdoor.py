"""MEM-d: the DOORS of the memory meter (docs/LINE3_LOOM_MEMORY_DESIGN.md 5.2; owner 2026-10-13 「記憶の計器の前の決定」: arms = context only / plain text log / structure with
notes hidden / structure with notes, every arm ends each turn with the same `report` tool).

A DOOR is what a driver (`memdriver`) and the MCP wrapper (`memmcp`) talk to: `call(tool, args) -> result`, `harness(run_id, op, args)`, `closed(run_id)`.  The model reaches nothing
else.  Four arms, two phases:

                    STORY phase (messages arrive one by one, a session = one conversation)      QUESTION phase (one fresh conversation per question)
  A0 context        report                                                                       answer
  A1 log            log_append, log_read, report                                                 log_read, answer
  A2b blind         write, declare_topic, supersede, recall, read_sentence, report, status      recall, lookup, read_sentence, weave_span, drop, read, emit, abstain, status
  A2 notes          the same as A2b                                                              the same as A2b

`report(contradictions, bugs)` is the SAME tool in every arm (`memory.report_result`): pairs of turn ids "<session>-<message>"; the turn is supplied by the door.  The structure
arms keep the memory in a `MemStore` (profile mem.v2); a session boundary is a NEW conversation and only the structure (A2, A2b) or the log (A1) carries anything across it.
A0 carries nothing.  In the blind arm the notes (and the `keys` of a write, which are note-like) are logged but not returned; everything else is the same code.

THE BASELINES.  `BaselineRun` is a ledger-backed run in the loom's row format (chain, canonical bytes, no clock) for the two arms without the structure: one per story session
and one per question.  `log_append` / `log_read` are an append-only text log with the memory's own limits (64 characters an entry, 60 appends, 60 reads per session); `answer` is the
closed answer of a baseline (kind value | contested | none + the values): the structure arms' answers are normalised to the same (kind, values) by `answer_of_output`.
Pure Python, no clock, no float, no network, no process.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.ledger_events import GENESIS, args_sha256, redact_obj
from verantyx.loom import ledger as lg
from verantyx.loom import memanswer as ma
from verantyx.loom import memory as mem
from verantyx.loom import ops
from verantyx.loom.ops import _oversize, refusal
from verantyx.loom.state import ARG_STR_CAP, ARGS_CHARS_CAP, Refuse, canonical, sha256_text

ARMS: Tuple[str, ...] = ("context", "log", "blind", "notes")
ARM_LABEL: Dict[str, str] = {"context": "A0", "log": "A1", "blind": "A2b", "notes": "A2"}
STRUCTURE_ARMS: Tuple[str, ...] = ("blind", "notes")
STORY_TOOLS: Dict[str, Tuple[str, ...]] = {
    "context": ("report",),
    "log": ("log_append", "log_read", "report"),
    "blind": ("write", "declare_topic", "supersede", "recall", "read_sentence", "report", "status"),
    "notes": ("write", "declare_topic", "supersede", "recall", "read_sentence", "report", "status"),
}
QUESTION_TOOLS: Dict[str, Tuple[str, ...]] = {
    "context": ("answer",),
    "log": ("log_read", "answer"),
    "blind": ma.ANSWER_TOOLS,
    "notes": ma.ANSWER_TOOLS,
}
LOG_ENTRY_CHARS = 64
LOG_CAPS = {"appends": 60, "reads": 60, "reports": 60, "answers": 3}
LOG_READ_LINES = 30
ANSWER_KINDS = ("value", "contested", "none")
ANSWER_VALUE_CHARS = 32
BASELINE_VERSION = "membase.v1"


# ------------------------------------------------------------------------------------------------------------
# the tool schemas: ONE table, read by the API driver (`api_tools`) and by the MCP wrapper (memmcp, which a test compares with it)
# ------------------------------------------------------------------------------------------------------------
def _p(typ: str, desc: str, **kw: Any) -> dict:
    d = {"type": typ, "description": desc}
    d.update(kw)
    return d


_STR_LIST = {"type": "array", "items": {"type": "string"}}
TOOL_SPECS: Dict[str, dict] = {
    "write": {"description": "Write ONE fact into the memory, as a sentence 「X の Y は A」 (X the whole subject, Y what is asked about, A a noun phrase), at most 64 characters. The structure weaves "
                             "the whole sentence; a sentence it cannot seat is refused and stores nothing: rewrite it in that form. Returns the sid and, in some arms, notes.",
              "properties": {"text": _p("string", "the fact, 「X の Y は A」, at most 64 characters")}, "required": ["text"]},
    "declare_topic": {"description": "Say what this session is about (a noun phrase, at most 24 characters, no particle at the end). A fact you write with no subject (「締め切りは水曜」) is "
                                     "stored as 「<topic>の締め切りは水曜」. Call it first; declare it again when the subject changes.",
                      "properties": {"text": _p("string", "the topic, e.g. 展示会準備")}, "required": ["text"]},
    "supersede": {"description": "Resolve a contested fact explicitly: the sentence new_sid REPLACES the older statement (old_sid, or old_answer = the text of the old answer). Recall then "
                                 "answers with the newest and lists the old as history (nothing is deleted). Only for an explicit update; a real contradiction stays unresolved. Refused "
                                 "with a typed reason if it does not name an existing contested group.",
                  "properties": {"new_sid": _p("integer", "sid of the sentence that replaces"), "reason": _p("string", "short reason, at most 40 characters"),
                                 "old_sid": _p("integer", "sid of an old sentence of the answer being replaced"),
                                 "old_answer": _p("string", "the old answer as text (instead of old_sid)"),
                                 "question": _p("string", "optional: the question whose answer groups are meant, default the new sentence's own 「…は何ですか」")},
                  "required": ["new_sid", "reason"]},
    "recall": {"description": "Ask the memory a question 「X の Y は何ですか」 (at most 64 characters). Returns ANSWER (one group of sentences), CHOICE (two or more answers nobody resolved), or NONE "
                              "(no sentence answers; the codes say why). Superseded sentences are listed under `history`.",
               "properties": {"question": _p("string", "e.g. 広報の担当は何ですか")}, "required": ["question"]},
    "read_sentence": {"description": "Read one memory sentence by id, with the units it holds.",
                      "properties": {"sid": _p("integer", "sentence id")}, "required": ["sid"]},
    "lookup": {"description": "Find memory units by exact surface (no substring search). tier: WORD | any. Returns n, every sentence id, and the first 5 sentences.",
               "properties": {"text": _p("string", "a unit surface"), "tier": _p("string", "WORD or any")}, "required": ["text", "tier"]},
    "status": {"description": "The counters, caps and (in a memory session) the topic and the number of notes.", "properties": {}, "required": []},
    "report": {"description": "END EVERY TURN WITH THIS. contradictions = pairs of turn ids (\"1-3\" = session 1, message 3) whose statements disagree, [] if none; bugs = [] here. "
                              "Only turns already delivered. There is no free text.",
               "properties": {"contradictions": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "e.g. [[\"1-1\", \"2-3\"]]"},
                              "bugs": dict(_STR_LIST, description="short strings, usually []")}, "required": ["contradictions"]},
    "log_append": {"description": "Append ONE line to the plain text log (at most 64 characters). The log is the only thing that survives the end of this session.",
                   "properties": {"text": _p("string", "the line")}, "required": ["text"]},
    "log_read": {"description": "Read the log: every line, or only the lines that contain `grep` (plain substring). At most 30 lines (the latest), each with its number.",
                 "properties": {"grep": _p("string", "optional substring, at most 32 characters")}, "required": []},
    "answer": {"description": "Give your final answer to the question and end. kind = value (values = [the answer]), contested (the earlier sessions state two different answers: values = [first, "
                              "second]), none (nothing in what you can see answers it: values = []). Each value at most 32 characters.",
               "properties": {"kind": _p("string", "value | contested | none", enum=list(ANSWER_KINDS)), "values": dict(_STR_LIST, description="the answer value(s)")}, "required": ["kind", "values"]},
    # the answer run (the loom's own tools over the memory snapshot)
    "weave_span": {"description": "Quote a stretch of a memory sentence. Give its sid, the tier WORD, and the stretch from the unit `first` to the unit `last` (both included), each written exactly as "
                                  "read_sentence lists that unit (plain text). The loom builds the chain of crosses whose read-out is the stretch word for word. Refused for a superseded "
                                  "sentence (superseded_sentence) and when the stretch is not expressible (span_inexpressible).",
                   "properties": {"sid": _p("integer", "sentence id"), "tier": _p("string", "WORD"), "first": _p("string", "first unit"), "last": _p("string", "last unit")},
                   "required": ["sid", "tier", "first", "last"]},
    "drop": {"description": "Throw a whole cross away (the cross and its units).", "properties": {"cid": _p("string", "cross id")}, "required": ["cid"]},
    "read": {"description": "Dry run of emit: the text the thread reads as, every refusal emit would give, and the evidence the quote was read from. Nothing closes.", "properties": {}, "required": []},
    "emit": {"description": "Fix the output: the text the thread reads as. Refused with every reason unless the thread is ONE unchanged weave_span quote that the evidence gate reads as an "
                            "answer to the question.", "properties": {}, "required": []},
    "abstain": {"description": "Close the run without an output. type: no_record (the memory does not state it) | contested (the memory holds two answers nobody resolved) | cannot_weave | unknown.",
                "properties": {"type": _p("string", "no_record | contested | cannot_weave | unknown", enum=list(ma.ANSWER_ABSTAIN))}, "required": ["type"]},
}


def api_tools(names: Sequence[str], strict: bool = False, done: bool = False) -> List[dict]:
    """The `tools` array of the Messages API for a toolset: exactly the names given, in order, with the schemas of TOOL_SPECS (+ the driver's `done` when asked)."""
    out = []
    for n in names:
        sp = TOOL_SPECS[n]
        d = {"name": n, "description": sp["description"],
             "input_schema": {"type": "object", "properties": json.loads(json.dumps(sp["properties"])), "additionalProperties": False}}
        if sp["required"]:
            d["input_schema"]["required"] = list(sp["required"])
        if strict:
            d["strict"] = True
        out.append(d)
    if done:
        out.append({"name": "done", "description": "Call when you have finished. Ends the episode. Takes no arguments.",
                    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}, **({"strict": True} if strict else {})})
    return out


def reports_of(rows: Sequence[dict]) -> List[dict]:
    """[{turn, contradictions, bugs, i}] of the ok `report` rows of a ledger, in order: what the model NOTICED, as a lookup."""
    return [{"turn": r["result"]["turn"], "contradictions": r["result"]["contradictions"], "bugs": r["result"]["bugs"], "i": r["i"]}
            for r in rows if r["actor"] == "model" and r["op"] == "report" and r["result"].get("ok") is True]


def noticed_pairs(rows: Sequence[dict]) -> List[List[str]]:
    """Every distinct pair of turn ids a ledger's reports named, sorted."""
    seen: List[List[str]] = []
    for rp in reports_of(rows):
        for p in rp["contradictions"]:
            if p not in seen:
                seen.append(p)
    return sorted(seen)


def _read_rows(run_dir) -> List[dict]:
    lines, _ = lg.read_raw_lines(run_dir)
    return [lg._parse_line(ln) for ln in lines]


def _blind(res: dict) -> dict:
    """The blind arm's view (A2b): the notes of the loom (CONFLICT, SAME_QUESTION, REVERSAL, ...) and the `keys` of a write (the stability of each cross: the same information as
    a REVERSAL note) are logged in the ledger and NOT returned.  Every other field is the arm's own code."""
    return {k: v for k, v in res.items() if k not in ("notes", "keys")}


# ------------------------------------------------------------------------------------------------------------
# the structure arms
# ------------------------------------------------------------------------------------------------------------
class _Door:
    phase = "?"

    def __init__(self, arm: str) -> None:
        if arm not in ARMS:
            raise ValueError("arm must be one of %s" % (ARMS,))
        self.arm = arm
        self.turn: Optional[str] = None

    @property
    def tool_names(self) -> Tuple[str, ...]:
        return (STORY_TOOLS if self.phase == "story" else QUESTION_TOOLS)[self.arm]

    def set_turn(self, turn: str) -> None:
        self.turn = turn

    def _gate(self, tool: Any, args: Any) -> Optional[dict]:
        """A tool outside the arm's list never reaches a run: refused with no row (as `LoomServer.call` refuses an unknown tool)."""
        if not isinstance(tool, str) or tool not in self.tool_names:
            return refusal("unknown_tool", {"tool": tool[:32] if isinstance(tool, str) else None})
        return None


class StructureDoor(_Door):
    """The STORY phase of A2 / A2b: one `MemSession` (profile mem.v2) of a `MemStore`.  `call` = one ledger row.  `commit()` is the harness's (the model has no such tool)."""
    phase = "story"

    def __init__(self, store_path, arm: str, model: str, *, hook: Any = mem.DEFAULT, kind_policy: Optional[str] = None) -> None:
        if arm not in STRUCTURE_ARMS:
            raise ValueError("a StructureDoor is the structure arms' (blind | notes)")
        super().__init__(arm)
        self.store = mem.MemStore(store_path)
        self.session = self.store.begin(model, profile=mem.PROFILE_V2, self_question=hook, kind_policy=kind_policy)
        self.run_id = self.session.run_id
        self.begin_result: dict = self.session.rows()[0]["result"]

    def intro(self) -> dict:
        b = self.begin_result
        return {"session": b["header"]["session_no"], "sentences_in_memory": b["header"]["sentences_before"], "task": b["task"], "rules": b["rules"], "tools": b["tools"]}

    def call(self, tool: Any, args: Any = None) -> dict:
        bad = self._gate(tool, args)
        if bad is not None:
            return bad
        a = dict(args) if isinstance(args, dict) else {}
        a.pop("run_id", None)                                       # the model cannot address another run
        a.pop("turn", None)                                         # the model never types a turn: the door knows which message it just delivered
        if tool == "report":
            if self.turn is None:
                return refusal("no_turn", {"reason": "no message has been delivered"})
            a["turn"] = self.turn
        elif tool == "write" and self.turn is not None:
            a["turn"] = self.turn                                   # the sentence is stored with the turn it was written at: a later recall names it, a report can cite it
        res = self.session.call(tool, a)
        return _blind(res) if self.arm == "blind" else res

    def harness(self, run_id: Any, op: str, args: dict) -> dict:
        return self.session.harness(op, args)

    def closed(self, run_id: Any = None) -> Optional[List[str]]:
        return list(self.session.run.state.closed) if self.session.run.state.closed is not None else None

    def commit(self) -> dict:
        return self.session.commit()

    def close(self) -> None:
        self.session.close()


class AnswerDoor(_Door):
    """The QUESTION phase of A2 / A2b: an `AnswerSession` over a snapshot of the store.  `call` = one ledger row (a note row after a read / emit)."""
    phase = "question"

    def __init__(self, store_path, arm: str, question: str, model: str, snapshot: Optional[dict] = None) -> None:
        if arm not in STRUCTURE_ARMS:
            raise ValueError("an AnswerDoor is the structure arms'")
        super().__init__(arm)
        self.session = ma.AnswerSession(store_path, question, model, snapshot=snapshot)
        self.run_id = self.session.run_id
        self.begin_result: dict = self.session.begin_result

    def call(self, tool: Any, args: Any = None) -> dict:
        bad = self._gate(tool, args)
        if bad is not None:
            return bad
        a = dict(args) if isinstance(args, dict) else {}
        a.pop("run_id", None)
        res = self.session.call(tool, a)
        return _blind(res) if self.arm == "blind" else res

    def harness(self, run_id: Any, op: str, args: dict) -> dict:
        return self.session.harness(op, args)

    def closed(self, run_id: Any = None) -> Optional[List[str]]:
        return self.session.closed()

    def output(self) -> dict:
        return ma.answer_output(self.session.ledger.dir)


def answer_of_output(out: dict) -> dict:
    """Normalise what a structure arm's answer run produced to the baselines' closed answer {kind, values}: an emitted quote = value; abstain contested = contested, its values the
    answers of the LAST CHOICE the model recalled (one per group, longest first); any other abstention or an open run = none."""
    if out.get("status") == "emitted":
        return {"kind": "value", "values": [out["text"]]}
    if out.get("status") == "abstained" and out.get("type") == "contested":
        choice = [r for r in out.get("recalls", []) if r["verdict"] == "CHOICE"]
        return {"kind": "contested", "values": [g[0] for g in choice[-1]["answers"]] if choice else []}
    return {"kind": "none", "values": []}


# ------------------------------------------------------------------------------------------------------------
# the baseline arms: a ledger-backed run without the structure
# ------------------------------------------------------------------------------------------------------------
class BaselineRun:
    """A run of A0 (context only) or A1 (plain log): ops `log_append` `log_read` `report` (story) / `log_read` `answer` (question) and `begin`; rows in the loom's format, no clock.
    `entries_before` = the log lines of the earlier sessions (A1; [] for A0).  Never reads a file."""

    def __init__(self, arm: str, phase: str, run_id: str, model: str, session_no: int, entries_before: Sequence[dict] = (), question: Optional[str] = None) -> None:
        if arm not in ("context", "log") or phase not in ("story", "question"):
            raise ValueError("BaselineRun: arm context | log, phase story | question")
        self.arm, self.phase, self.run_id, self.model, self.session_no, self.question = arm, phase, run_id, model, session_no, question
        self.entries: List[dict] = [dict(e) for e in entries_before]
        self.n_before = len(self.entries)
        self.counts = {"appends": 0, "reads": 0, "reports": 0, "answers": 0}
        self.closed: Optional[List[str]] = None
        self.i, self.head = 0, GENESIS
        self.tools = (STORY_TOOLS if phase == "story" else QUESTION_TOOLS)[arm]

    # -- state / begin -----------------------------------------------------------------------------------------------
    def log_sha(self) -> str:
        return sha256_text(canonical(self.entries))

    def state_sha(self) -> str:
        return sha256_text(canonical({"arm": self.arm, "log": self.log_sha(), "counts": self.counts, "closed": self.closed}))

    def begin_body(self) -> dict:
        res = {"ok": True, "run_id": self.run_id, "mode": "baseline", "arm": self.arm, "phase": self.phase, "tools": list(self.tools), "caps": dict(LOG_CAPS),
               "header": {"baseline_version": BASELINE_VERSION, "arm": self.arm, "phase": self.phase, "session_no": self.session_no, "declared_model": self.model,
                          "log_sha_before": self.log_sha(), "log_lines_before": self.n_before}}
        if self.question is not None:
            res["question"] = self.question
        return {"actor": "model", "op": "begin", "args": {"task_id": "story" if self.phase == "story" else "answer", "model": self.model}, "result": res,
                "state_sha": self.state_sha()}

    def advance(self, row: dict) -> None:
        self.i = row["i"] + 1
        self.head = row["sha"]

    # -- one call = one body -----------------------------------------------------------------------------------------
    def step(self, actor: str, op: str, args: dict, replay_extra: Optional[dict] = None) -> dict:
        if actor == "model":
            return self._model_step(op, args, replay_extra)
        if actor != "harness" or op not in ("free_text_dropped", "harness_meta", "abandoned", "session_end"):
            raise ValueError("op %r is not a row of actor %r" % (op, actor))
        if op == "abandoned" and self.closed is None:
            self.closed = ["abandoned", str(args.get("reason", "?"))]
        if op == "session_end" and self.closed is None:
            self.closed = ["committed", self.log_sha()]
        canonical(args)
        return {"actor": actor, "op": op, "args": args, "result": {"ok": True}, "state_sha": self.state_sha()}

    def _model_step(self, op: str, args: dict, replay_extra: Optional[dict] = None) -> dict:
        extra: Dict[str, Any] = {}
        stored = args
        trunc = False
        n = 0
        if replay_extra is not None:
            extra = dict(replay_extra)
            n = extra.get("redacted", 0)
            trunc = "truncated" in extra
        elif _oversize(args):
            trunc, stored = True, {}
            try:
                extra = {"truncated": True, "args_sha256": args_sha256(args), "args_chars": len(canonical(args))}
            except (TypeError, ValueError, RecursionError):
                extra = {"truncated": True, "args_sha256": sha256_text("unserialisable"), "args_chars": 0}
        else:
            stored, n = redact_obj(args)
            if n:
                extra = {"redacted": n, "args_sha256": args_sha256(args)}
        try:
            if op not in self.tools:
                raise Refuse("unknown_tool", {"tool": op[:32] if isinstance(op, str) else None})
            if self.closed is not None:
                raise Refuse("run_closed", {"closed": list(self.closed)})
            if trunc:
                raise Refuse("args_too_large", {"chars": extra["args_chars"], "limit": ARGS_CHARS_CAP, "string_limit": ARG_STR_CAP})
            if n:
                raise Refuse("secret_shaped_entry", {"redacted": n})
            result = getattr(self, "_h_" + op)(args)
        except Refuse as r:
            result = refusal(r.type, r.detail)
        body = {"actor": "model", "op": op, "args": stored, "result": result, "state_sha": self.state_sha()}
        body.update(extra)
        return body

    # -- the tools ---------------------------------------------------------------------------------------------------
    def _count(self, key: str) -> None:
        if self.counts[key] >= LOG_CAPS[key]:
            raise Refuse(key[:-1] + "_cap", {"limit": LOG_CAPS[key]})
        self.counts[key] += 1

    def _h_log_append(self, a: dict) -> dict:
        a = ops._args(a, {"text": (str, True)})
        self._count("appends")
        t = unicodedata.normalize("NFC", a["text"])
        if not 1 <= len(t) <= LOG_ENTRY_CHARS or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in t):
            raise Refuse("bad_entry", {"reason": "1 to %d characters, no newline / control character" % LOG_ENTRY_CHARS})
        self.entries.append({"session": self.session_no, "text": t})
        return {"ok": True, "line": len(self.entries) - 1, "lines": len(self.entries), "text": t}

    def _h_log_read(self, a: dict) -> dict:
        a = ops._args(a, {"grep": (str, False)})
        self._count("reads")
        g = unicodedata.normalize("NFC", a.get("grep", ""))
        if len(g) > 32:
            raise Refuse("bad_grep", {"reason": "at most 32 characters"})
        hits = [{"n": k, "session": e["session"], "text": e["text"]} for k, e in enumerate(self.entries) if g in e["text"]]
        shown = hits[-LOG_READ_LINES:]
        return {"ok": True, "lines": len(self.entries), "matched": len(hits), "more": len(hits) - len(shown), "entries": shown}

    def _h_report(self, a: dict) -> dict:
        a = ops._args(a, {"turn": (str, True), "contradictions": (list, True), "bugs": (list, False)})
        self._count("reports")
        return mem.report_result(a)

    def _h_answer(self, a: dict) -> dict:
        a = ops._args(a, {"kind": (str, True), "values": (list, True)})
        self._count("answers")
        k, vals = a["kind"], a["values"]
        if k not in ANSWER_KINDS:
            raise Refuse("bad_answer", {"field": "kind", "allowed": list(ANSWER_KINDS)})
        want = {"value": 1, "contested": 2, "none": 0}[k]
        if len(vals) != want or not all(isinstance(v, str) and 1 <= len(v) <= ANSWER_VALUE_CHARS for v in vals):
            raise Refuse("bad_answer", {"field": "values", "reason": "kind %s takes %d value(s) of 1 to %d characters" % (k, want, ANSWER_VALUE_CHARS)})
        self.closed = ["answered", k]
        return {"ok": True, "status": "answered", "kind": k, "values": list(vals)}


def baseline_answer(rows: Sequence[dict]) -> dict:
    """{kind, values} of a baseline question ledger (the ok `answer` row), else none."""
    for r in rows:
        if r["actor"] == "model" and r["op"] == "answer" and r["result"].get("ok") is True:
            return {"kind": r["result"]["kind"], "values": list(r["result"]["values"])}
    return {"kind": "none", "values": []}


class BaselineStore:
    """The folder of one baseline arm run: `<dir>/sessions/l%04d/` (story, one per session) and `<dir>/answers/b%04d/` (one per question), each a loom-format ledger; `log.txt` is a
    human-readable copy of the log (the ledgers are the truth)."""

    def __init__(self, path, arm: str) -> None:
        if arm not in ("context", "log"):
            raise ValueError("BaselineStore: arm context | log")
        self.path, self.arm = Path(path), arm

    def story_dirs(self) -> List[Path]:
        d = self.path / "sessions"
        return sorted(p for p in d.iterdir() if p.is_dir() and re.fullmatch(r"l[0-9]{4}", p.name)) if d.is_dir() else []

    def entries(self) -> List[dict]:
        """The log lines of the COMMITTED story sessions, from their verified ledgers (A0 has none)."""
        out: List[dict] = []
        for d in self.story_dirs():
            if lg.verify_chain(d)["status"] != "OK":
                raise Refuse("store_unverified", {"reason": "chain", "run_id": d.name})
            rows = _read_rows(d)
            if not rows or rows[-1]["op"] != "session_end":
                continue                                            # an abandoned session is not part of the log
            out += [{"session": rows[0]["result"]["header"]["session_no"], "text": r["result"]["text"]}
                    for r in rows if r["actor"] == "model" and r["op"] == "log_append" and r["result"].get("ok") is True]
        return out

    def next_dir(self, kind: str) -> Tuple[Path, str]:
        pre, sub = ("l", "sessions") if kind == "story" else ("b", "answers")
        d = self.path / sub
        k = 1
        while (d / ("%s%04d" % (pre, k))).exists():
            k += 1
        return d / ("%s%04d" % (pre, k)), "%s%04d" % (pre, k)


class BaselineDoor(_Door):
    """A0 / A1, either phase: a `BaselineRun` with its ledger.  `call` = one row; `commit()` ends a story session (a `session_end` harness row and, for A1, `log.txt`)."""

    def __init__(self, store_path, arm: str, phase: str, model: str, question: Optional[str] = None, session_no: Optional[int] = None) -> None:
        if arm not in ("context", "log"):
            raise ValueError("a BaselineDoor is the baseline arms' (context | log)")
        super().__init__(arm)
        self.phase = phase
        self.store = BaselineStore(store_path, arm)
        before = self.store.entries() if arm == "log" else []
        n_story = sum(1 for d in self.store.story_dirs() if _read_rows(d)[-1]["op"] == "session_end")
        d, rid = self.store.next_dir(phase)
        self.run = BaselineRun(arm, phase, rid, model, session_no if session_no is not None else n_story + 1, before, question)
        self.run_id = rid
        self.ledger = lg.Ledger(d)
        self.ledger.create({"mode": "baseline", "arm": arm, "phase": phase})
        self.t0 = time.monotonic_ns()
        with self.ledger.locked() as lk:
            self.run.advance(lk.append(self.run.begin_body(), 0))
        self.begin_result: dict = _read_rows(d)[0]["result"]

    def intro(self) -> dict:
        h = self.begin_result["header"]
        return {"session": h["session_no"], "log_lines": h["log_lines_before"], "tools": self.begin_result["tools"], "caps": self.begin_result["caps"]}

    def call(self, tool: Any, args: Any = None) -> dict:
        bad = self._gate(tool, args)
        if bad is not None:
            return bad
        a = dict(args) if isinstance(args, dict) else {}
        a.pop("run_id", None)
        if tool == "report":
            if self.turn is None:
                return refusal("no_turn", {"reason": "no message has been delivered"})
            a.pop("turn", None)
            a["turn"] = self.turn
        with self.ledger.locked() as lk:
            body = self.run.step("model", tool, json.loads(canonical(a)))
            self.run.advance(lk.append(body, time.monotonic_ns() - self.t0))
        return body["result"]

    def harness(self, run_id: Any, op: str, args: dict) -> dict:
        with self.ledger.locked() as lk:
            body = self.run.step("harness", op, json.loads(canonical(args)))
            self.run.advance(lk.append(body, time.monotonic_ns() - self.t0))
        return body["result"]

    def closed(self, run_id: Any = None) -> Optional[List[str]]:
        return None if self.run.closed is None else list(self.run.closed)

    def commit(self) -> dict:
        self.harness(None, "session_end", {})
        if self.arm == "log":
            with open(self.store.path / "log.txt", "w", encoding="utf-8") as f:
                for e in self.run.entries:
                    f.write("S%d %s\n" % (e["session"], e["text"]))
        return {"ok": True, "status": "committed", "log_lines": len(self.run.entries)}

    def close(self) -> None:
        pass

    def output(self) -> dict:
        return baseline_answer(_read_rows(self.ledger.dir))


def verify_baseline(run_dir) -> dict:
    """The chain, then the re-execution of every row by a fresh `BaselineRun` (the log of the earlier sessions comes from the begin row's sha: a replay with the wrong earlier log
    differs at row 0).  {"status": "OK" | chain status | "REPLAY_DIFFERS", "first_diff"}.  `entries_before` is read from the sibling ledgers, as the door did."""
    chain = lg.verify_chain(run_dir)
    if chain["status"] != "OK":
        return chain
    rd = Path(run_dir)
    rows = _read_rows(rd)
    h = rows[0]["result"]["header"]
    arm, phase = h["arm"], h["phase"]
    store = BaselineStore(rd.parent.parent, arm)
    before: List[dict] = []
    if arm == "log":
        for d in store.story_dirs():
            if d.name >= rd.name and phase == "story":
                break
            sr = _read_rows(d)
            if sr and sr[-1]["op"] == "session_end":
                before += [{"session": sr[0]["result"]["header"]["session_no"], "text": r["result"]["text"]}
                           for r in sr if r["actor"] == "model" and r["op"] == "log_append" and r["result"].get("ok") is True]
    run = BaselineRun(arm, phase, rows[0]["result"]["run_id"], rows[0]["args"]["model"], h["session_no"], before, rows[0]["result"].get("question"))
    prev = GENESIS
    for idx, orig in enumerate(rows):
        try:
            body = run.begin_body() if idx == 0 else run.step(orig["actor"], orig["op"], orig["args"], {k: orig[k] for k in lg.EXTRA_FIELDS if k in orig} or None)
            row = lg.seal(idx, prev, body)
        except Exception:
            return {"status": "REPLAY_DIFFERS", "first_diff": {"i": idx, "field": "exception"}}
        if row != orig:
            return {"status": "REPLAY_DIFFERS", "first_diff": {"i": idx, "field": lg._first_diff(orig, row)}}
        run.advance(row)
        prev = row["sha"]
    return {"status": "OK", "rows": len(rows)}
