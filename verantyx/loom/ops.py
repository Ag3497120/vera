"""LOOM-a: the operations of the loom (docs/LINE3_LOOM_DESIGN.md 4) and Run.step, the one door through which a call becomes a row.

THE 20 TOOLS (MODEL_OPS): begin lookup read_sentence add open_cross seat seat_run weave_span unseat swap extend topic set_depth link unlink drop
read emit abstain status.  There is NO `rotate` (L-LOOM-01) and NO undo (L-LOOM-09).  `weave_span` (LOOM-span, L-LOOM-130..) is the batch seating:
ONE op that cuts a stretch of a corpus sentence into the units of a tier and builds the chain of crosses whose read-out equals that stretch WORD FOR
WORD; `drop` removes a whole cross with its units.  `weave_sentence` (LOOM-batch, L-LOOM-123..126) is LEGACY: it is no longer a tool (a live call is
`unknown_tool`), and its code stays only so that a ledger recorded with it (runs_h55b) still replays byte for byte (LEGACY_OPS, executed only while
a ledger is being replayed).

A call never raises to its caller: it returns {"ok": true, ...} or {"ok": false, "refusal": <type>, "detail": {...}}.  Every
refusal is raised as `state.Refuse` BEFORE any mutation, so a refused call leaves the state exactly as it was (apart from the
counter of its class).  Counters count every call of a class that was not itself refused by that class's cap, refused or not,
so "caps fire exactly at the limit" and a run cannot spin on refusals for ever.

THE CAPS (L-LOOM-08), per run: state-changing ops (add open_cross seat seat_run weave_span unseat swap extend topic set_depth link unlink drop),
lookups (lookup + read_sentence), reads, emit attempts, constructed units, crosses; chars per constructed unit.  `emit`, `abstain`
and `status` are not capped, except `emit` by its own attempt cap.  After the run is closed every model call is `run_closed`.

Run.step(actor, op, args) is what both the live server and the replay call: it executes the op, builds the body of the ledger row
({actor, op, args, result, state_sha}), and never looks at a clock.  A call whose arguments contain a secret-shaped string is
refused `secret_shaped_unit` and its arguments are stored redacted (with the sha256 of the original arguments), so no secret
reaches a row (design 5.1).  A `weave_span` row carries the version of the rule that derived its crosses in its args (`wv`, stamped by
`step`, L-LOOM-135), so a later change of the rule can never turn an old ledger into REPLAY_DIFFERS.
"""
from __future__ import annotations

import keyword
import platform
import re
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from verantyx.ledger_events import GENESIS, args_sha256, redact_obj
from verantyx.line3 import foundation as fd
from verantyx.loom import LOOM_VERSION
from verantyx.loom import code as codelib
from verantyx.loom import notes as notelib
from verantyx.loom import read as rd
from verantyx.loom.code import CodeIndex
from verantyx.loom.corpus import Corpus
from verantyx.loom.state import (SPEC, ABSTAIN_TYPES, ALL_TIERS, ARG_STR_CAP, ARGS_CHARS_CAP, AXES, CAPS, CAPS_PROFILES, CENTRE, CODE, CODE_TIER, CONSTRUCTED,
                                 GUARD_CAPS, LANGS, MODES, PROSE, PROSE_TIERS, RECORD, LoomCross, LoomState, Refuse, caps_profile_of, canonical, fmt_seat,
                                 parse_seat, sha256_text)

MODEL_OPS: Tuple[str, ...] = ("begin", "lookup", "read_sentence", "add", "open_cross", "seat", "seat_run", "weave_span", "unseat", "swap",
                              "extend", "topic", "set_depth", "link", "unlink", "drop", "read", "emit", "abstain", "status")
LEGACY_OPS: Tuple[str, ...] = ("weave_sentence",)       # no longer tools; executed ONLY while a recorded ledger is replayed (L-LOOM-136)
HARNESS_OPS: Tuple[str, ...] = ("abandoned", "free_text_dropped", "free_text_control", "harness_meta")
HUMAN_OPS: Tuple[str, ...] = ("grade",)
LOOP_OPS: Tuple[str, ...] = ("attest", "audit_verdict", "stacked")                  # design 6.1 / 11: rows appended by later tickets
ALL_OPS: Tuple[str, ...] = MODEL_OPS + HARNESS_OPS + HUMAN_OPS + LOOP_OPS
LOOM_OPS: Tuple[str, ...] = (notelib.NOTE_OP,)                                      # LOOM-notes: rows the loom itself writes (actor "loom")
ACTORS: Tuple[str, ...] = ("model", "harness", "human", notelib.NOTE_ACTOR)

STATE_CHANGING: Tuple[str, ...] = ("add", "open_cross", "seat", "seat_run", "weave_span", "weave_sentence", "unseat", "swap", "extend", "topic",
                                    "set_depth", "link", "unlink", "drop")                       # weave_sentence: legacy rows of old ledgers
CLASS_OF: Dict[str, str] = dict({op: "ops" for op in STATE_CHANGING},
                                lookup="lookups", read_sentence="lookups", read="reads", emit="emit_attempts")
CAP_REFUSAL: Dict[str, str] = {"ops": "ops_cap", "lookups": "lookup_cap", "reads": "read_cap", "emit_attempts": "emit_cap"}

WEAVE_SPAN_V1 = "weave_span.v1"
WEAVE_SPAN_V2 = "weave_span.v2"         # = v1, and the crosses it makes carry the sid they quote (`LoomCross.span`), which the gate reads (L-LOOM-146)
WEAVE_SPAN_WV = WEAVE_SPAN_V2            # the CURRENT rule that derives a weave_span's crosses (L-LOOM-135); stamped into the args of every new weave_span row
SPEC_ARMS: Tuple[str, ...] = tuple(SPEC.arms)                  # the particle of each arm, in AXES order (LoomCross puts SPEC.arms[ai] on arm ai)
DRIVERS = ("L1-subagent", "L2-api", "scripted")
GRADES = ("pass", "fail", "unclear")
_SHA_RX = re.compile(r"^[0-9a-f]{64}$")
_REASON_RX = re.compile(r"^[a-z_]{1,64}$")

RULES: Dict[str, Any] = {
    "output": "The only output is the text of a successful emit. Anything you write as plain text is discarded unread.",
    "read_prose": "Each cross is read: for the arms が(-z) を(+z) と(-y) で(+y) に(-x) の(+x), the arm's units from the outer seat to the "
                  "inner seat, then the arm's particle if the arm holds a unit; then the centre unit; then は if the cross is a topic. "
                  "Crosses are read in thread order, with nothing between them.",
    "read_code": "A code line is read: the centre token, then each arm (+x -x +y -y +z -z) from the inner seat outward; layout "
                 "(indentation by depth, spacing) is added by the loom.",
    "seats": "seat names are 'centre' and '<arm>:<k>' (k = 0 is the outer end). In a prose cross the innermost seat of every arm is the "
             "foundation (the particle) and is never yours.",
    "emit": "A cross must be a fixed point of Vera's key (n, p, a): if one swap of two data seats raises the key, emit is refused and "
            "names the swaps.",
    "units": "record units are exactly the corpus's units of a tier; constructed units are marked and only allowed in constructed_allowed.",
    "abstain": ["no_record", "cannot_weave", "unknown"],
}


# ------------------------------------------------------------------------------------------------------------
# tasks
# ------------------------------------------------------------------------------------------------------------
def normalize_task(d: dict) -> dict:
    """A task-bank entry -> {task_id, text, lang, mode, tiers, corpus?, fixture?, context_names?}.  Gold is never in a task."""
    if not isinstance(d, dict):
        raise ValueError("a task is a JSON object")
    for k in ("task_id", "text", "lang", "mode"):
        if not isinstance(d.get(k), str) or not d[k]:
            raise ValueError("task: %r must be a non-empty string" % k)
    if d["lang"] not in LANGS:
        raise ValueError("task: lang must be prose or code")
    if d["mode"] not in MODES:
        raise ValueError("task: mode must be record_only or constructed_allowed")
    tiers = d.get("tiers") or (list(PROSE_TIERS) if d["lang"] == PROSE else [CODE_TIER])
    allowed = PROSE_TIERS if d["lang"] == PROSE else (CODE_TIER,)
    if not isinstance(tiers, list) or not tiers or any(t not in allowed for t in tiers) or len(set(tiers)) != len(tiers):
        raise ValueError("task: tiers must be a non-empty subset of %s without repeats" % (list(allowed),))
    out = {"task_id": d["task_id"], "text": d["text"], "lang": d["lang"], "mode": d["mode"],
           "tiers": [t for t in allowed if t in tiers]}
    for k in ("corpus", "fixture"):
        if d.get(k) is not None:
            if not isinstance(d[k], str):
                raise ValueError("task: %r must be a path string" % k)
            if k == "fixture" and d["lang"] != CODE:        # L-LOOM-79: a prose task with a fixture built a CODE index (header, begin and replay all branch on it)
                raise ValueError("task: fixture belongs to a code task")
            out[k] = d[k]
    if d.get("context_names") is not None:
        cn = d["context_names"]
        if d["lang"] != CODE:
            raise ValueError("task: context_names belong to a code task")
        if not (isinstance(cn, list) and all(isinstance(x, str) and x.isidentifier() and not keyword.iskeyword(x) for x in cn)):
            raise ValueError("task: context_names is a list of identifiers")
        out["context_names"] = list(cn)
    if d.get("target") is not None or d.get("tests") is not None:
        if d["lang"] != CODE:
            raise ValueError("task: target / tests belong to a code task")
        if d.get("target") is not None:
            tg = d["target"]
            if not (isinstance(tg, dict) and set(tg) == {"file"} and _relpath(tg["file"])):
                raise ValueError("task: target is {\"file\": <relative .py path in the fixture>}")
            out["target"] = {"file": tg["file"]}
        if d.get("tests") is not None:
            ts = d["tests"]
            if not (isinstance(ts, list) and ts and all(_relpath(t) for t in ts)):
                raise ValueError("task: tests is a non-empty list of relative .py paths in the fixture")
            out["tests"] = list(ts)
    return out


def _relpath(p: Any) -> bool:
    """A relative posix path of a .py file, no `..`, no absolute part, no backslash, and NOT starting with `-` (L-LOOM-80: the name goes
    into pytest's argv, where `-x` or `--pyargs` would be an option): the fixture is addressed only by such names."""
    return (isinstance(p, str) and p.endswith(".py") and not p.startswith(("/", "-")) and "\\" not in p and "\x00" not in p
            and all(part not in ("", ".", "..") for part in p.split("/")))


def check_task_against_index(task: dict, index: CodeIndex) -> Optional[dict]:
    """L-LOOM-80: what a code task names must exist in the fixture it names.  None, or {"refusal", "detail"} for `begin`:
    `target_not_in_fixture {file}` (the target must be a file the index holds, i.e. a non-test .py of the fixture) and
    `unknown_context_name {name}` (an explicit context name must be a module-level name of some module of the fixture)."""
    tg = task.get("target")
    if tg is not None and tg["file"] not in index.file_sha:
        return {"refusal": "target_not_in_fixture", "detail": {"file": tg["file"]}}
    known = {n for names in index.top.values() for n in names}
    for name in task.get("context_names", ()):
        if name not in known:
            return {"refusal": "unknown_context_name", "detail": {"name": name}}
    return None


def task_view(task: dict, caps: Optional[Dict[str, int]] = None) -> dict:
    """What `begin` returns and what the row stores: the task WITHOUT paths (no absolute path in a hashed row) and with the caps (the run's own;
    the current profile when none is given)."""
    view = {"task_id": task["task_id"], "text": task["text"], "lang": task["lang"], "mode": task["mode"], "tiers": list(task["tiers"]),
            "caps": dict(caps if caps is not None else CAPS[task["lang"]])}
    for k in ("target", "tests", "context_names"):         # code only, and only when the task has them: a prose row 0 is unchanged
        if k in task:
            view[k] = task[k]
    return view


def refusal(type: str, detail: Optional[dict] = None) -> dict:
    return {"ok": False, "refusal": type, "detail": dict(detail or {})}


# ------------------------------------------------------------------------------------------------------------
# argument checks
# ------------------------------------------------------------------------------------------------------------
def _long_str(o: Any) -> bool:
    if isinstance(o, str):
        return len(o) > ARG_STR_CAP
    if isinstance(o, dict):
        return any(_long_str(k) or _long_str(v) for k, v in o.items())
    if isinstance(o, (list, tuple)):
        return any(_long_str(v) for v in o)
    return False


def _oversize(args: Any) -> bool:
    """L-LOOM-44: the arguments of a call are stored verbatim only while the canonical JSON has at most ARGS_CHARS_CAP characters and no
    string (value or key) has more than ARG_STR_CAP; otherwise the row holds their sha256 and length (`truncated`) and the call is
    refused `args_too_large`.  Every legitimate call of the 20 tools is far below both."""
    try:
        if len(canonical(args)) > ARGS_CHARS_CAP:
            return True
    except (TypeError, ValueError, RecursionError):
        return True
    return _long_str(args)


def _args(a: dict, spec: Dict[str, Tuple[Any, bool]]) -> dict:
    """spec: name -> (type, required).  type: str | int | bool | 'strs' (a non-empty list of str).  Unknown or mistyped -> bad_args."""
    if not isinstance(a, dict):
        raise Refuse("bad_args", {"reason": "arguments must be an object"})
    for k in a:
        if k not in spec:
            raise Refuse("bad_args", {"field": k if isinstance(k, str) else None, "reason": "unknown argument"})
    out = {}
    for name, (typ, required) in spec.items():
        if name not in a:
            if required:
                raise Refuse("bad_args", {"field": name, "reason": "missing"})
            continue
        v = a[name]
        if isinstance(typ, tuple):                                  # a union such as (int, str): a bool is never an int here
            ok = isinstance(v, typ) and not (isinstance(v, bool) and bool not in typ)
        else:
            ok = (isinstance(v, list) and all(isinstance(x, str) for x in v)) if typ == "strs" else \
                 (isinstance(v, int) and not isinstance(v, bool)) if typ is int else isinstance(v, typ)
        if not ok:
            raise Refuse("bad_args", {"field": name, "reason": "expected %s" % ("list of str" if typ == "strs" else
                                                                                  " or ".join(t.__name__ for t in typ) if isinstance(typ, tuple) else typ.__name__)})
        out[name] = v
    return out


# ------------------------------------------------------------------------------------------------------------
# the run
# ------------------------------------------------------------------------------------------------------------
class Run:
    def __init__(self, corpus: Corpus, task: dict, model: str, run_id: str, stability_mode: str = rd.DEFAULT_STABILITY,
                 code_index: Optional[CodeIndex] = None, caps: Optional[Dict[str, int]] = None, notes_version: Optional[str] = None) -> None:
        """`caps`: the cap set of this run for its language, None = the current profile (a new run).  Replay passes the set the `begin` row recorded;
        it must be exactly one of the known profiles (L-LOOM-122).  `notes_version`: the notes definitions of this run (None = the current, a new run;
        replay passes what the `begin` row named, notes.v1 when it names none: L-LOOM-147)."""
        if stability_mode not in rd.STABILITY_MODES:
            raise ValueError("stability must be one of %s" % (rd.STABILITY_MODES,))
        self.corpus = corpus
        self.code_index = code_index                       # the CODE record index of the task's fixture (None: prose, or a code task with no fixture)
        self.task = normalize_task(task)
        self.model = model
        self.run_id = run_id
        self.lang = self.task["lang"]
        self.mode = self.task["mode"]
        if caps is not None and caps_profile_of(self.lang, caps) is None:
            raise ValueError("caps: not a known cap profile (%s)" % (sorted(CAPS_PROFILES),))
        self.caps = dict(caps if caps is not None else CAPS[self.lang])
        self.stability_mode = stability_mode
        if notes_version is not None and notes_version not in notelib.NOTES_VERSIONS:
            raise ValueError("notes_version must be one of %s" % (notelib.NOTES_VERSIONS,))
        self.notes_version = notes_version if notes_version is not None else notelib.NOTES_VERSION
        self.state = LoomState(self.lang)
        self.i = 0                         # the index of the next row
        self.head = GENESIS                # the sha of the last row
        # LOOM-notes: NOT part of the hashed state.  Rebuilt by step() on live calls and on replay alike, so both see the same history.
        self.lookup_log: List[Tuple[int, str, bool]] = []      # (row index, NFC text, matches empty) of every ok model `lookup`
        self._prev: Optional[Tuple[str, str, bool]] = None      # (actor, op, ok) of the row stepped last
        self.replaying = False             # set by ledger.replay only: a recorded note row of another notes version is accepted as recorded

    # -- header (design 3.1) ------------------------------------------------------------------------------------------
    def header(self) -> dict:
        # L-LOOM-47: the FULL interpreter identity.  tokenize / ast (the code tier) change between patch releases, so MAJOR.MINOR was not enough
        return {"loom_version": LOOM_VERSION, "python_version": "%d.%d.%d" % tuple(sys.version_info[:3]),
                "python_implementation": platform.python_implementation(), "corpus_sha": self.corpus.corpus_sha,
                "space_sha": self.corpus.space_sha, "adhesion_sha": dict(self.corpus.adhesion_sha), "seats_sha": self.corpus.seats_sha,
                "code_index_sha": self.code_index.sha if self.code_index is not None else None, "stability_mode": self.stability_mode, "declared_model": self.model}

    def context_names(self) -> List[str]:
        """The names a code thread may use without defining them: the task's `context_names` and the top-level names of the target file
        (the emitted text is appended at the end of it, so every one of them is earlier)."""
        names = set(self.task.get("context_names", ()))
        if self.code_index is not None and "target" in self.task:
            names.update(self.code_index.top_names(self.task["target"]["file"]))
        return sorted(names)

    def begin_body(self) -> dict:
        res = {"ok": True, "run_id": self.run_id, "task": task_view(self.task, self.caps), "rules": RULES, "header": self.header()}
        if self.notes_version != notelib.NOTES_V1:          # notes.v1 runs (every ledger before L-LOOM-147) have no such key: their begin rows are as they were
            res["notes_profile"] = self.notes_version
        return {"actor": "model", "op": "begin", "args": {"task_id": self.task["task_id"], "model": self.model}, "result": res,
                "state_sha": self.state.sha()}

    def advance(self, row: dict) -> None:
        self.i = row["i"] + 1
        self.head = row["sha"]

    # -- one call = one body ---------------------------------------------------------------------------------------------
    def step(self, actor: str, op: str, args: dict, replay_extra: Optional[dict] = None) -> dict:
        """`replay_extra` (replay only): the optional top-level fields of the recorded row ({redacted, args_sha256} or {truncated,
        args_sha256, args_chars}); the live call computes them itself."""
        if actor not in ACTORS:
            raise ValueError("actor must be one of %s" % (ACTORS,))
        i = self.i
        body = self._model_step(op, args, replay_extra) if actor == "model" else self._outside_step(actor, op, args)
        res = body["result"]
        if actor == "model" and op == "lookup" and res.get("ok") is True:
            self.lookup_log.append((i, notelib.nfc(args["text"]), res.get("matches") == []))
        self._prev = (actor, op, res.get("ok") is True)
        return body

    def notes_due(self) -> List[dict]:
        """LOOM-notes: the notes the row stepped LAST calls for: [] unless it was an ok model `read` / `emit`.  A non-empty answer means a
        `loom_note` row (actor "loom") must follow that row: the server appends it, and replay requires it (unless that row is the last one: L-LOOM-105)."""
        if self._prev is None or self._prev[0] != "model" or self._prev[1] not in notelib.NOTE_AFTER_OPS or not self._prev[2]:
            return []
        return notelib.compute(self)

    def _guard_blocked(self, op: str, args: Any) -> Optional[str]:
        """L-LOOM-44: the calls no class cap counts are counted here, and beyond their cap a call is refused `cap_exceeded` and stored as
        its sha256 and length only.  closed_calls: every model call after the run is closed.  abstain_refused: refused `abstain` calls
        (a VALID abstain is never blocked, so a run can always be closed by the model)."""
        st = self.state
        if st.closed is not None:
            return "closed_calls" if st.guards["closed_calls"] >= GUARD_CAPS["closed_calls"] else None
        if op == "abstain" and st.guards["abstain_refused"] >= GUARD_CAPS["abstain_refused"]:
            valid = isinstance(args, dict) and set(args) == {"type"} and args["type"] in ABSTAIN_TYPES
            return None if valid else "abstain_refused"
        return None

    def _model_step(self, op: str, args: dict, replay_extra: Optional[dict]) -> dict:
        extra: Dict[str, Any] = {}
        n = 0
        trunc = False
        blocked = self._guard_blocked(op, args) if self._executable(op) else None
        if replay_extra is not None:
            stored = args
            extra = dict(replay_extra)
            n = extra.get("redacted", 0)
            trunc = "truncated" in extra
            if blocked is not None and not trunc:
                raise ValueError("a call beyond a guard cap is stored as sha256 and length only")
        elif blocked is not None or _oversize(args):
            trunc = True
            stored = {}
            try:
                extra = {"truncated": True, "args_sha256": args_sha256(args), "args_chars": len(canonical(args))}
            except (TypeError, ValueError, RecursionError):
                extra = {"truncated": True, "args_sha256": sha256_text("unserialisable"), "args_chars": 0}
        else:
            stored, n = redact_obj(args)
            if n:
                extra = {"redacted": n, "args_sha256": args_sha256(args)}
            if op == "weave_span" and isinstance(stored, dict) and "wv" not in stored:
                stored = dict(stored, wv=WEAVE_SPAN_WV)           # the rule version that derives this row's crosses (L-LOOM-135); the handler defaults to it
        try:
            if blocked is not None:
                raise Refuse("cap_exceeded", {"guard": blocked, "limit": GUARD_CAPS[blocked]})
            if op == "begin" or not self._executable(op):
                raise Refuse("unknown_tool", {"tool": op if isinstance(op, str) else None})
            self._precheck(op)
            if trunc:
                raise Refuse("args_too_large", {"chars": extra["args_chars"], "limit": ARGS_CHARS_CAP, "string_limit": ARG_STR_CAP})
            if n:
                raise Refuse("secret_shaped_unit", {"redacted": n})
            result = HANDLERS[op](self, args, self.i)
        except Refuse as r:
            result = refusal(r.type, r.detail)
            if op == "abstain" and r.type not in ("run_closed", "cap_exceeded"):
                self.state.guards["abstain_refused"] += 1
        body = {"actor": "model", "op": op, "args": stored, "result": result, "state_sha": self.state.sha()}
        body.update(extra)
        return body

    def _executable(self, op: Any) -> bool:
        """A model op the run executes: a tool (MODEL_OPS), or a LEGACY op while a recorded ledger is being replayed (never on a live call)."""
        return isinstance(op, str) and (op in MODEL_OPS or (self.replaying and op in LEGACY_OPS))

    def _precheck(self, op: str) -> None:
        st = self.state
        if st.closed is not None:
            st.guards["closed_calls"] += 1
            raise Refuse("run_closed", {"closed": list(st.closed)})
        cls = CLASS_OF.get(op)
        if cls is not None:
            if st.counters[cls] >= self.caps[cls]:
                raise Refuse(CAP_REFUSAL[cls], {"limit": self.caps[cls]})
            st.counters[cls] += 1

    def _outside_step(self, actor: str, op: str, args: dict) -> dict:
        """Rows of the harness and the human (and, later, the loops).  They never go through the model's caps."""
        ok = (actor == "harness" and (op in HARNESS_OPS or op in LOOP_OPS)) or (actor == "human" and op in HUMAN_OPS) \
            or (actor == notelib.NOTE_ACTOR and op in LOOM_OPS)
        if not ok:
            raise ValueError("op %r is not a row of actor %r" % (op, actor))
        if actor == notelib.NOTE_ACTOR:
            # the loom's own row.  Its content is DERIVED (the args of a live call are ignored), so a forged note row cannot replay as itself.
            if self.replaying and args.get("nv") != self.notes_version:
                # recorded under another definition of the notes (L-LOOM-106): accepted AS RECORDED when its shape is right; the replay reports
                # it (`notes_stale`) instead of comparing it with what the current definitions would say
                prev = self._prev
                if prev is None or prev[0] != "model" or prev[1] not in notelib.NOTE_AFTER_OPS or not prev[2] \
                        or not set(args) <= {"after", "of", "notes", "nv"} or not {"after", "of", "notes"} <= set(args) \
                        or args["after"] != self.i - 1 or args["of"] != prev[1] or not isinstance(args["notes"], list) \
                        or not isinstance(args.get("nv", ""), str):
                    raise ValueError("note: a recorded note row of another version has the wrong shape")
                return {"actor": actor, "op": op, "args": args, "result": {"ok": True}, "state_sha": self.state.sha()}
            notes = self.notes_due()
            if not notes:
                raise ValueError("note: no notes are due after the previous row")
            return {"actor": actor, "op": op, "args": {"after": self.i - 1, "of": self._prev[1], "notes": notes, "nv": self.notes_version},
                    "result": {"ok": True}, "state_sha": self.state.sha()}
        args = dict(args)
        if op == "abandoned":
            _need(args, {"reason": str}, op)
            if not _REASON_RX.match(args["reason"]):
                raise ValueError("abandoned: reason is a short lower-case token")
            if self.state.closed is None:
                self.state.closed = ["abandoned", args["reason"]]
        elif op in ("free_text_dropped", "free_text_control"):
            need = {"sha256": str, "chars": int}
            if op == "free_text_control":
                need["text"] = str
            _need(args, need, op)
            if not _SHA_RX.match(args["sha256"]) or args["chars"] < 0:
                raise ValueError("%s: sha256 / chars malformed" % op)
        elif op == "harness_meta":
            allowed = {"driver", "requested_model", "agent_definition_sha", "response_model"}
            if not args or set(args) - allowed or any(not isinstance(v, str) for v in args.values()):
                raise ValueError("harness_meta: keys within %s, string values" % sorted(allowed))
            if "driver" in args and args["driver"] not in DRIVERS:
                raise ValueError("harness_meta: driver must be one of %s" % (DRIVERS,))
        elif op == "grade":
            _need(args, {"grade": str, "grader": str}, op)
            if args["grade"] not in GRADES:
                raise ValueError("grade: one of %s" % (GRADES,))
        # attest / audit_verdict / stacked: accepted as JSON objects; their shapes are fixed by the tickets that write them (LOOM-i/j)
        canonical(args)                                      # JSON-able, or it raises
        return {"actor": actor, "op": op, "args": args, "result": {"ok": True}, "state_sha": self.state.sha()}


def _need(args: dict, spec: Dict[str, Any], op: str) -> None:
    for k, t in spec.items():
        if k not in args or not isinstance(args[k], t) or (t is int and isinstance(args[k], bool)):
            raise ValueError("%s: argument %r (%s) is required" % (op, k, t.__name__))


# ------------------------------------------------------------------------------------------------------------
# handlers: (run, args, row index) -> result dict; they raise Refuse
# ------------------------------------------------------------------------------------------------------------
def _task_tier(run: Run, tier: str) -> str:
    if tier not in ALL_TIERS:
        raise Refuse("bad_args", {"field": "tier", "reason": "one of %s" % (list(ALL_TIERS),)})
    if tier not in run.task["tiers"]:
        raise Refuse("tier_not_in_task", {"tier": tier, "tiers": list(run.task["tiers"])})
    if tier == CODE_TIER and run.code_index is None:
        raise Refuse("code_index_unavailable", {"tier": tier, "reason": "the task names no fixture, so there is no CODE record index"})
    return tier


def h_lookup(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"text": (str, True), "tier": (str, True)})
    text, tier = a["text"], a["tier"]
    if not 1 <= len(text) <= 32:
        raise Refuse("bad_args", {"field": "text", "reason": "1 to 32 characters"})
    if run.code_index is not None and tier in (CODE_TIER, "any"):
        m = run.code_index.match(text)
        return {"ok": True, "matches": [m] if m else []}
    if tier == "any":
        tiers = [t for t in PROSE_TIERS if t in run.task["tiers"]]
        if not tiers:
            raise Refuse("code_index_unavailable", {"tier": CODE_TIER, "reason": "the task names no fixture, so there is no CODE record index"})
    else:
        tiers = [_task_tier(run, tier)]
    matches = []
    for t in tiers:
        post = run.corpus.postings(t, text)
        if post is not None:
            matches.append({"tier": t, "surface": text, "n": len(post), "sids": list(post),
                            "sentences": [run.corpus.sentence(s) for s in post[:5]]})
    return {"ok": True, "matches": matches}


def h_read_sentence(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"sid": (int, True)})
    sid = a["sid"]
    if run.code_index is not None:
        if not 0 <= sid < run.code_index.n_sentences:
            raise Refuse("unknown_sid", {"sid": sid, "n": run.code_index.n_sentences})
        out = dict(run.code_index.sentence(sid))
        out["units"] = {CODE_TIER: list(run.code_index.sentences[sid]["tokens"])}
        out["ok"] = True
        return out
    if not 0 <= sid < run.corpus.n_sentences:
        raise Refuse("unknown_sid", {"sid": sid, "n": run.corpus.n_sentences})
    if CODE_TIER in run.task["tiers"]:
        raise Refuse("code_index_unavailable", {"reason": "the task names no fixture, so there is no CODE record index"})
    units = run.corpus.units_of(sid)
    out = dict(run.corpus.sentence(sid))
    out["units"] = {t: units[t] for t in PROSE_TIERS if t in run.task["tiers"]}
    out["ok"] = True
    return out


def _constructed_text(run: Run, text: str) -> str:
    cap = run.caps["unit_chars"]
    t = unicodedata.normalize("NFC", text)
    if not t or len(t) > cap:
        raise Refuse("bad_unit_text", {"reason": "length", "limit": cap})
    for ch in t:
        # prose: no whitespace at all.  code: a STRING token may hold plain spaces; the one-token check below decides the rest
        if unicodedata.category(ch)[0] == "C" or (ch.isspace() and not (run.lang == CODE and ch == " ")):
            raise Refuse("bad_unit_text", {"reason": "whitespace_or_control"})
    if run.lang == CODE and not codelib.is_one_token(t):
        raise Refuse("bad_unit_text", {"reason": "not_one_token"})
    return t


def h_add(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"text": (str, True), "kind": (str, True), "tier": (str, False)})
    st = run.state
    if a["kind"] == RECORD:
        if "tier" not in a:
            raise Refuse("bad_args", {"field": "tier", "reason": "required for a record unit"})
        tier = _task_tier(run, a["tier"])
        if tier == CODE_TIER:
            if run.code_index.occurrences(a["text"]) is None:
                raise Refuse("not_a_record", {"text": a["text"], "tier": tier, "in_tiers": []})
            u = st.new_unit(a["text"], RECORD, tier, run.code_index.prov(a["text"]))
            return {"ok": True, "uid": u.uid, "kind": u.kind, "surface": u.surface, "prov": u.prov}
        post = run.corpus.postings(tier, a["text"])
        if post is None:
            raise Refuse("not_a_record", {"text": a["text"], "tier": tier, "in_tiers": run.corpus.tiers_holding(a["text"])})
        u = st.new_unit(a["text"], RECORD, tier, {"tier": tier, "n": len(post), "sids": list(post)})
    elif a["kind"] == CONSTRUCTED:
        if run.mode == "record_only":
            raise Refuse("constructed_forbidden", {"mode": run.mode})
        if st.counters["constructed"] >= run.caps["constructed"]:
            raise Refuse("constructed_cap", {"limit": run.caps["constructed"]})
        t = _constructed_text(run, a["text"])
        if t in fd.P7:
            raise Refuse("constructed_is_foundation", {"text": t})
        if run.lang == PROSE:
            held = run.corpus.tiers_holding(t)
            if held:
                raise Refuse("constructed_shadows_record", {"text": t, "tiers": held})
        elif run.code_index is not None:                  # code: a token the fixture has must be added as a record (its provenance cannot be hidden)
            occ = run.code_index.occurrences(t)
            if occ is not None:
                raise Refuse("constructed_shadows_record", {"text": t, "tiers": [CODE_TIER], "n": len(occ)})
        u = st.new_unit(t, CONSTRUCTED, None, {"by": run.model, "at": i})
        st.counters["constructed"] += 1
    else:
        raise Refuse("bad_args", {"field": "kind", "reason": "record or constructed"})
    return {"ok": True, "uid": u.uid, "kind": u.kind, "surface": u.surface, "prov": u.prov}


def h_open_cross(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"tier": (str, True), "L": (int, True), "depth": (int, False)})
    st = run.state
    if len(st.crosses) >= run.caps["crosses"]:
        raise Refuse("cross_cap", {"limit": run.caps["crosses"]})
    tier = a["tier"]
    if tier not in ALL_TIERS:
        raise Refuse("bad_args", {"field": "tier", "reason": "one of %s" % (list(ALL_TIERS),)})
    if tier not in run.task["tiers"]:
        raise Refuse("tier_not_in_task", {"tier": tier, "tiers": list(run.task["tiers"])})
    L, depth = a["L"], a.get("depth", 0)
    if not 1 <= L <= run.caps["max_L"]:
        raise Refuse("bad_L", {"L": L, "min": 1, "max": run.caps["max_L"]})
    if run.lang == PROSE and depth != 0:
        raise Refuse("not_code", {"field": "depth"})
    if not 0 <= depth <= run.caps["max_depth"]:
        raise Refuse("bad_depth", {"depth": depth, "max": run.caps["max_depth"]})
    c = st.new_cross(tier, L, depth)
    foundation = {ax: fd.particle_of(c.arms[AXES.index(ax)][L - 1]) for ax in AXES} if run.lang == PROSE else {}
    return {"ok": True, "cid": c.cid, "tier": tier, "L": L, "depth": depth, "seats": c.data_seats(), "foundation": foundation}


def _unit_into(run: Run, cross: LoomCross, arm: Optional[str], k: Optional[int], uid: str) -> None:
    """The refusals of putting one unit into one data seat, in the order of the design; raises before anything is touched."""
    st = run.state
    u = st.unit(uid)
    occupant = cross.get(arm, k)
    if occupant is not None:
        raise Refuse("seat_occupied", {"cid": cross.cid, "seat": fmt_seat(arm, k), "uid": occupant})
    if u.seated is not None:
        raise Refuse("unit_already_seated", {"uid": uid, "at": list(u.seated)})
    if u.kind == RECORD and u.tier != cross.tier:
        raise Refuse("tier_mismatch", {"uid": uid, "unit_tier": u.tier, "cross_tier": cross.tier})


def h_seat(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True), "seat": (str, True), "uid": (str, True)})
    st = run.state
    cross = st.cross(a["cid"])
    arm, k = parse_seat(a["seat"])
    st.unit(a["uid"])
    if arm is not None and k is None:
        k = cross.bare_arm_seat(arm)
    cross.check_seat(arm, k)
    _unit_into(run, cross, arm, k, a["uid"])
    st.place(cross, arm, k, a["uid"])
    return {"ok": True, "cid": cross.cid, "seat": fmt_seat(arm, k), "uid": a["uid"]}


def h_seat_run(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True), "arm": (str, True), "uids": ("strs", True)})
    st = run.state
    cross = st.cross(a["cid"])
    arm, k = parse_seat(a["arm"])
    if arm is None or k is not None:
        raise Refuse("bad_args", {"field": "arm", "reason": "a bare arm such as +x"})
    uids = a["uids"]
    if not uids:
        raise Refuse("bad_args", {"field": "uids", "reason": "at least one unit"})
    for uid in uids:
        st.unit(uid)
    if len(set(uids)) != len(uids):
        raise Refuse("unit_already_seated", {"reason": "the same unit twice in one run", "uids": list(uids)})
    n, m = len(uids), cross.inner_k + 1
    if n > m:
        raise Refuse("arm_too_short", {"cid": cross.cid, "arm": arm, "data_seats": max(m, 0), "units": n})
    # reading order: prose outer -> inner (ends on the innermost data seat); code inner -> outer (starts on it)  (L-LOOM-23)
    ks = [cross.inner_k - n + 1 + j for j in range(n)] if cross.lang == PROSE else [cross.inner_k - j for j in range(n)]
    for uid, kk in zip(uids, ks):
        _unit_into(run, cross, arm, kk, uid)
    for uid, kk in zip(uids, ks):
        st.place(cross, arm, kk, uid)
    return {"ok": True, "cid": cross.cid, "arm": arm, "seated": [{"seat": fmt_seat(arm, kk), "uid": uid} for uid, kk in zip(uids, ks)]}


def _arm_of(name: str) -> str:
    """An arm named as an axis ("+x") or as its particle ("の"): the axis.  Anything else: bad_args."""
    if name in AXES:
        return name
    if name in SPEC_ARMS:
        return AXES[SPEC_ARMS.index(name)]
    raise Refuse("bad_args", {"field": "arms", "reason": "an axis such as +x or one of が を と で に の"})


def _unit_index(units: List[str], v: Any, which: str, lo: int = 0) -> int:
    """`from` / `to` of weave_span: an index into the sentence's units of the tier (0-based, as `read_sentence` lists them), or a unit surface
    (the first unit at or after `lo` with that surface).  Raises `unit_not_in_sentence` (a surface that is no unit of the sentence) or
    `span_out_of_range` (an index outside the sentence); NEITHER returns the sentence's units: what a refused call says is only what was asked."""
    if isinstance(v, int):
        if not 0 <= v < len(units):
            raise Refuse("span_out_of_range", {"which": which, "index": v})
        return v
    for j in range(lo, len(units)):
        if units[j] == v:
            return j
    raise Refuse("unit_not_in_sentence", {"which": which, "text": v[:32],
                                          "hint": "write the unit exactly as read_sentence lists it for this tier, plain text without quotation marks"})


def _weave_span_v1(run: Run, sid: int, tier: str, f: Any, t: Any) -> dict:
    """`weave_span.v1`: the rule of `_weave_span_core` with no marker on the crosses (the h55c ledgers name it; they replay by it forever)."""
    return _weave_span_core(run, sid, tier, f, t, WEAVE_SPAN_V1, False)


def _weave_span_v2(run: Run, sid: int, tier: str, f: Any, t: Any) -> dict:
    """`weave_span.v2` (L-LOOM-146): EXACTLY v1, and each cross it makes remembers the sid of the sentence it quotes (`LoomCross.span`), so that the gate
    can say "faithful to sentence N, unstable under the key" and offer no swap for it (every improving swap would change the quoted text).  The marker is
    not hashed and not in the ledger: replay derives it from the row's `wv`."""
    return _weave_span_core(run, sid, tier, f, t, WEAVE_SPAN_V2, True)


def _weave_span_core(run: Run, sid: int, tier: str, f: Any, t: Any, wv: str, mark: bool) -> dict:
    """The rule `weave_span.v1` / `.v2` (L-LOOM-130..134).  A STRETCH of corpus sentence `sid` -- the units `from` .. `to` (both included) of the tier -- becomes
    a chain of crosses whose read-out is that stretch word for word.  Between two neighbouring units of the stretch the sentence has a GAP (its letters
    only: punctuation, quotes, spaces and 「・」 are not letters and the loom writes none of them; the T9 normaliser drops only whitespace and 「・」/「·」,
    so a stretch with quotes or hyphens in it is NOT its own read-out under T9 -- the read-out equals the stretch's units verbatim with letters-only gaps, L-LOOM-144):
      ""            the units touch (ハッシュ+表, カール+マルクス, 1981+年): the next unit starts a new cross; the crosses are linked in order
      an arm particle (の に で と を が)   HEAD-FINAL: the unit goes on that particle's arm of the cross whose CENTRE is the very next unit
      は            the unit is the centre of a cross marked topic (it reads 東京は)
      anything else (という, として, とも, でも, ...)   the loom cannot write it: REFUSED `span_inexpressible`
    So a cross is (at most one arm unit) + centre (+ は).  Two arm-particle gaps in a row (日本の大学の学生, 東京で日本の首都) would need the middle unit to be
    an arm unit AND a centre, or two units on one arm (the read rule has ONE particle per arm): REFUSED `span_inexpressible`, nothing changed.
    The units are record units (uid and provenance exactly as `add` gives them), made in sentence order, ONLY for the stretch.  Each cross is
    L = 1 (centre only) or L = 2 (one data seat per arm: the attached unit is on `<arm>:0`).  The crosses are linked at the end of the thread."""
    st = run.state
    units = list(run.corpus.tier(tier).sentence_units[sid])
    i0 = _unit_index(units, f, "from")
    i1 = _unit_index(units, t, "to", i0)
    if i1 < i0:
        raise Refuse("bad_span", {"from": i0, "to": i1, "reason": "to is before from"})
    held = {st.crosses[cid].tier for cid in st.thread if st.crosses[cid].uids()}
    if held and held != {tier}:
        raise Refuse("tier_mix", {"tier": tier, "thread_tiers": sorted(held)})
    ok, gaps = run.corpus.span_gaps(tier, sid, i0, i1)
    surf = units[i0:i1 + 1]
    n = len(surf)
    if not ok:
        raise Refuse("span_inexpressible", {"reason": "unit_is_not_the_text", "from": i0, "to": i1})
    kinds: List[Optional[str]] = []                                # per gap: an axis (arm particle), "topic", or None (touching)
    for k, g in enumerate(gaps):
        if g == "":
            kinds.append(None)
        elif g in SPEC_ARMS:
            kinds.append(AXES[SPEC_ARMS.index(g)])
        elif g == SPEC.centre:
            kinds.append("topic")
        else:
            raise Refuse("span_inexpressible", {"reason": "gap_is_not_a_particle", "between": [surf[k], surf[k + 1]], "gap": g[:16]})
    for k in range(n - 2):
        if kinds[k] in AXES and kinds[k + 1] in AXES:
            raise Refuse("span_inexpressible", {"reason": "nested_particle_chain", "units": [surf[k], surf[k + 1], surf[k + 2]],
                                                "particles": [gaps[k], gaps[k + 1]]})
    plan: List[Tuple[int, Optional[int], bool]] = []              # (centre k, attached unit k or None, topic)
    for k in range(n):
        if k < n - 1 and kinds[k] in AXES:
            continue                                              # this unit is an arm unit of the cross of unit k + 1
        att = k - 1 if k > 0 and kinds[k - 1] in AXES else None
        plan.append((k, att, k < n - 1 and kinds[k] == "topic"))
    text = "".join(surf[k] + (gaps[k] if k < n - 1 else "") for k in range(n))
    read = "".join((surf[att] + gaps[att] if att is not None else "") + surf[k] + (SPEC.centre if top else "") for k, att, top in plan)
    if read != text:                                              # cannot happen by construction; kept so that "word for word" is checked, not assumed
        raise Refuse("span_inexpressible", {"reason": "readout_differs", "from": i0, "to": i1})
    if len(st.crosses) + len(plan) > run.caps["crosses"]:
        raise Refuse("cross_cap", {"limit": run.caps["crosses"], "needed": len(plan)})
    # -- from here on the op changes the state (it cannot refuse any more) --------------------------------------------------------------------
    uid_of: Dict[int, str] = {}
    for k, surface in enumerate(surf):
        post = run.corpus.postings(tier, surface)
        uid_of[k] = st.new_unit(surface, RECORD, tier, {"tier": tier, "n": len(post), "sids": list(post)}).uid
    out_crosses: List[dict] = []
    for k, att, top in plan:
        cross = st.new_cross(tier, 1 if att is None else 2)
        st.place(cross, None, None, uid_of[k])
        seated: List[dict] = []
        if att is not None:
            ax = kinds[att]
            st.place(cross, ax, 0, uid_of[att])
            seated.append({"seat": fmt_seat(ax, 0), "uid": uid_of[att], "surface": surf[att], "particle": gaps[att]})
        cross.topic = top
        cross.span = sid if mark else None
        st.thread.append(cross.cid)
        cross.linked = True
        out_crosses.append({"cid": cross.cid, "L": cross.L, "centre": {"uid": uid_of[k], "surface": surf[k]}, "seated": seated, "topic": top})
    return {"ok": True, "wv": wv, "sid": sid, "tier": tier, "from": i0, "to": i1, "text": text, "crosses": out_crosses, "thread": list(st.thread)}


WEAVE_SPAN_RULES = {WEAVE_SPAN_V1: _weave_span_v1, WEAVE_SPAN_V2: _weave_span_v2}                # rule version -> the rule; a new version is ADDED here, an old one is never edited or removed


def h_weave_span(run: Run, a: dict, i: int) -> dict:
    """LOOM-span (L-LOOM-130..): `weave_span(sid, tier, from, to)`, ONE op (one count against `ops`, one ledger row).  The stretch of corpus sentence
    `sid` from unit `from` to unit `to` of `tier` (each an index into the units `read_sentence` lists, 0-based, or a unit surface) becomes the chain of
    crosses of the rule `wv` (default and only: weave_span.v1, see `_weave_span_v1`), linked in sentence order.  Record units only.  The result
    names the crosses and seats it made and the text of the stretch; it does NOT return the units of the rest of the sentence and does NOT run
    `read` (use `read`, which is counted).  `wv` is not a field of the tool: `Run.step` stamps it into the stored args; replay executes the rule
    the row names.  Refusals (all before anything is touched): not_prose, tier_not_in_task, unknown_sid, unit_not_in_sentence, span_out_of_range,
    bad_span, tier_mix, span_inexpressible, cross_cap, bad_args."""
    a = _args(a, {"sid": (int, True), "tier": (str, True), "from": ((int, str), True), "to": ((int, str), True), "wv": (str, False)})
    rule = WEAVE_SPAN_RULES.get(a.get("wv", WEAVE_SPAN_WV))
    if rule is None:
        raise Refuse("bad_args", {"field": "wv", "reason": "unknown rule version"})
    if run.lang != PROSE:
        raise Refuse("not_prose", {"tool": "weave_span"})
    tier = _task_tier(run, a["tier"])
    sid = a["sid"]
    if not 0 <= sid < run.corpus.n_sentences:
        raise Refuse("unknown_sid", {"sid": sid, "n": run.corpus.n_sentences})
    return rule(run, sid, tier, a["from"], a["to"])


def h_drop(run: Run, a: dict, i: int) -> dict:
    """LOOM-span: `drop(cid)` removes a whole cross and the units seated in it (one op, one row); the cross leaves the thread if it was linked.  The
    registry forgets the removed units and cross: their uids and cid are never made again (state `made`).  Units that are in the pool stay."""
    a = _args(a, {"cid": (str, True)})
    st = run.state
    cross = st.cross(a["cid"])
    surfaces = {uid: st.units[uid].surface for uid in cross.uids()}
    uids = st.drop_cross(cross)
    return {"ok": True, "cid": a["cid"], "removed": [{"uid": u, "surface": surfaces[u]} for u in uids], "thread": list(st.thread)}


def h_weave_sentence(run: Run, a: dict, i: int) -> dict:
    """LEGACY (LOOM-batch, L-LOOM-123..126; no longer a tool: Run._executable lets it run ONLY while a recorded ledger is replayed).  Its code is
    kept EXACTLY as it was, rule `weave_sentence.v1` (implicit: its rows carry no `wv`), so the ledgers recorded with it (runs_h55b) still verify
    and replay byte for byte.  It was replaced by `weave_span` because it seated units a particle does not govern and packed same-particle units
    on one arm; and its refusal `centre_not_in_sentence` and its result returned the whole sentence's units for free.  Do not call it, do not fix it.

    BATCH SEATING, one op (one count against `ops`, one ledger row).

    weave_sentence(sid, tier, centre, arms?, pos?).  The loom cuts corpus sentence `sid` into the record units of `tier` (the units
    `read_sentence` shows), opens a prose cross on the first unit whose surface is `centre`, and seats every OTHER unit of the sentence on the arm
    of the particle that immediately follows it in the sentence, by the grammar layer's evidence (`Corpus.particle_after`): a unit followed by
    の goes to the の arm, followed by に to the に arm, and so on, the units of one arm in sentence order (outer -> inner, the reading order of
    seat_run).  A unit followed by none of the six arm particles (は, a copula, nothing, a unit of another kind) stays UNSEATED; so does a unit whose
    arm is excluded by `arms`, and a unit that does not fit (an arm holds at most max_L - 1 units: the OUTERMOST ones, the earliest in the
    sentence, are left out).  Every unit of the sentence becomes a record unit (uid, provenance exactly as `add` gives it), in sentence order, so
    the unseated ones can be placed later with `seat`.  The cross is linked to the thread (at `pos`, default the end).  L = (most units on one arm)
    + 2, i.e. one spare data seat per arm, at most max_L.  Only record units are used (no constructed unit, in either mode).  Nothing is gated here:
    the result carries the read-out `rd.evaluate` gives now (text, every refusal an emit would give, the stability), computed WITHOUT counting a
    `read`.  Refusals are raised before anything is touched: not_prose, tier_not_in_task, unknown_sid, tier_mix, cross_cap, bad_pos,
    centre_not_in_sentence, bad_args."""
    a = _args(a, {"sid": (int, True), "tier": (str, True), "centre": (str, True), "arms": ("strs", False), "pos": (int, False)})
    st = run.state
    if run.lang != PROSE:
        raise Refuse("not_prose", {"tool": "weave_sentence"})
    tier = _task_tier(run, a["tier"])
    sid = a["sid"]
    if not 0 <= sid < run.corpus.n_sentences:
        raise Refuse("unknown_sid", {"sid": sid, "n": run.corpus.n_sentences})
    allowed = None
    if "arms" in a:
        if not a["arms"]:
            raise Refuse("bad_args", {"field": "arms", "reason": "at least one arm, or leave it out"})
        allowed = {_arm_of(n) for n in a["arms"]}
    held = {run.state.crosses[cid].tier for cid in st.thread if run.state.crosses[cid].uids()}
    if held and held != {tier}:
        raise Refuse("tier_mix", {"tier": tier, "thread_tiers": sorted(held)})
    if len(st.crosses) >= run.caps["crosses"]:
        raise Refuse("cross_cap", {"limit": run.caps["crosses"]})
    pos = a.get("pos", len(st.thread))
    if not 0 <= pos <= len(st.thread):
        raise Refuse("bad_pos", {"pos": pos, "thread_length": len(st.thread)})
    units = list(run.corpus.tier(tier).sentence_units[sid])
    if a["centre"] not in units:
        raise Refuse("centre_not_in_sentence", {"sid": sid, "tier": tier, "centre": a["centre"], "units": units})
    ci = units.index(a["centre"])
    spans = run.corpus.spans().spans(tier, sid)
    follow = run.corpus.particle_after(tier, sid)
    # the plan (pure; nothing touched yet): per unit its following particle and the arm it is entitled to
    plan: List[Tuple[int, Optional[str], Optional[str]]] = []                     # (index, particle or None, axis or None)
    for idx in range(len(units)):
        if idx == ci:
            continue
        p = follow.get(tuple(spans[idx]))
        plan.append((idx, p, AXES[SPEC_ARMS.index(p)] if p in SPEC_ARMS else None))
    room = run.caps["max_L"] - 1
    why: Dict[int, str] = {}
    by_arm: Dict[str, List[int]] = {ax: [] for ax in AXES}
    for idx, p, ax in plan:
        if ax is None:
            why[idx] = "no_arm_particle"
        elif allowed is not None and ax not in allowed:
            why[idx] = "arm_not_allowed"
        else:
            by_arm[ax].append(idx)
    for ax in AXES:
        if len(by_arm[ax]) > room:
            for idx in by_arm[ax][:len(by_arm[ax]) - room]:
                why[idx] = "arm_full"
            by_arm[ax] = by_arm[ax][len(by_arm[ax]) - room:]
    L = min(run.caps["max_L"], max([len(v) for v in by_arm.values()]) + 2)
    # -- from here on the op changes the state (it cannot refuse any more) ----------------------------------------------------------------
    uid_of: Dict[int, str] = {}
    for idx, surf in enumerate(units):
        post = run.corpus.postings(tier, surf)
        uid_of[idx] = st.new_unit(surf, RECORD, tier, {"tier": tier, "n": len(post), "sids": list(post)}).uid
    cross = st.new_cross(tier, L)
    st.place(cross, None, None, uid_of[ci])
    seated: List[dict] = []
    for ax in AXES:
        idxs = by_arm[ax]
        ks = [cross.inner_k - len(idxs) + 1 + j for j in range(len(idxs))]
        for idx, k in zip(idxs, ks):
            st.place(cross, ax, k, uid_of[idx])
            seated.append({"seat": fmt_seat(ax, k), "uid": uid_of[idx], "surface": units[idx], "particle": SPEC_ARMS[AXES.index(ax)]})
    st.thread.insert(pos, cross.cid)
    cross.linked = True
    pmap = {idx: p for idx, p, _ in plan}
    unseated = [{"uid": uid_of[idx], "surface": units[idx], "followed_by": pmap[idx], "why": why[idx]} for idx in sorted(why)]
    ev = rd.evaluate(run)
    return {"ok": True, "cid": cross.cid, "sid": sid, "tier": tier, "L": L, "centre": {"uid": uid_of[ci], "surface": units[ci]},
            "seated": seated, "unseated": unseated, "thread": list(st.thread),
            "readout": {"text": ev["text"], "refusals": ev["refusals"], "stability": ev["stability"]}}


def _full_seat(cross: LoomCross, name: str) -> Tuple[Optional[str], Optional[int]]:
    arm, k = parse_seat(name)
    if arm is not None and k is None:
        raise Refuse("bad_seat", {"seat": name, "reason": "an arm needs its k, such as +x:0"})
    cross.check_seat(arm, k)
    return arm, k


def h_unseat(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True), "seat": (str, True)})
    cross = run.state.cross(a["cid"])
    arm, k = _full_seat(cross, a["seat"])
    if cross.get(arm, k) is None:
        raise Refuse("seat_empty", {"cid": cross.cid, "seat": fmt_seat(arm, k)})
    uid = run.state.lift(cross, arm, k)
    return {"ok": True, "cid": cross.cid, "uid": uid}


def h_swap(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True), "seat_a": (str, True), "seat_b": (str, True)})
    cross = run.state.cross(a["cid"])
    sa = _full_seat(cross, a["seat_a"])
    sb = _full_seat(cross, a["seat_b"])
    if sa == sb:
        raise Refuse("same_seat", {"seat": fmt_seat(*sa)})
    run.state.swap(cross, sa, sb)
    return {"ok": True, "cid": cross.cid}


def h_extend(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True), "L2": (int, True)})
    cross = run.state.cross(a["cid"])
    if not cross.L < a["L2"] <= run.caps["max_L"]:
        raise Refuse("bad_L", {"L": cross.L, "L2": a["L2"], "max": run.caps["max_L"]})
    run.state.extend_cross(cross, a["L2"])
    return {"ok": True, "cid": cross.cid, "L": cross.L}


def h_topic(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True), "on": (bool, True)})
    cross = run.state.cross(a["cid"])
    if cross.lang != PROSE:
        raise Refuse("not_prose", {"cid": cross.cid})
    if cross.topic != a["on"]:
        cross.span = None                                  # no longer the quoted stretch (L-LOOM-146)
    cross.topic = a["on"]
    return {"ok": True, "cid": cross.cid, "topic": cross.topic}


def h_set_depth(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True), "depth": (int, True)})
    cross = run.state.cross(a["cid"])
    if cross.lang != CODE:
        raise Refuse("not_code", {"cid": cross.cid})
    if not 0 <= a["depth"] <= run.caps["max_depth"]:
        raise Refuse("bad_depth", {"depth": a["depth"], "max": run.caps["max_depth"]})
    cross.depth = a["depth"]
    return {"ok": True, "cid": cross.cid, "depth": cross.depth}


def h_link(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True), "pos": (int, False)})
    st = run.state
    cross = st.cross(a["cid"])
    if cross.linked:
        raise Refuse("already_linked", {"cid": cross.cid})
    pos = a.get("pos", len(st.thread))
    if not 0 <= pos <= len(st.thread):
        raise Refuse("bad_pos", {"pos": pos, "thread_length": len(st.thread)})
    st.thread.insert(pos, cross.cid)
    cross.linked = True
    return {"ok": True, "thread": list(st.thread)}


def h_unlink(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"cid": (str, True)})
    st = run.state
    cross = st.cross(a["cid"])
    if not cross.linked:
        raise Refuse("not_linked", {"cid": cross.cid})
    st.thread.remove(cross.cid)
    cross.linked = False
    return {"ok": True, "thread": list(st.thread)}


def h_read(run: Run, a: dict, i: int) -> dict:
    _args(a, {})
    ev = rd.evaluate(run)
    return {"ok": True, "text": ev["text"], "annotated": ev["annotated"], "refusals": ev["refusals"], "stability": ev["stability"],
            "shares": ev["shares"]}


def h_emit(run: Run, a: dict, i: int) -> dict:
    _args(a, {})
    ev = rd.evaluate(run)
    if ev["refusals"]:
        raise Refuse(ev["refusals"][0]["type"], {"refusals": ev["refusals"], "stability": ev["stability"]})
    run.state.closed = ["emitted", ev["output_sha"]]
    return {"ok": True, "status": "emitted", "text": ev["text"], "annotated": ev["annotated"], "output_sha": ev["output_sha"],
            "shares": ev["shares"], "stability": ev["stability"]}


def h_abstain(run: Run, a: dict, i: int) -> dict:
    a = _args(a, {"type": (str, True)})
    if a["type"] not in ABSTAIN_TYPES:
        raise Refuse("bad_type", {"type": a["type"][:32], "allowed": list(ABSTAIN_TYPES)})      # L-LOOM-44: never echo more than 32 chars
    run.state.closed = ["abstained", a["type"]]
    return {"ok": True, "status": "abstained", "type": a["type"]}


def h_status(run: Run, a: dict, i: int) -> dict:
    _args(a, {})
    st = run.state
    crosses = {}
    for cid, c in st.crosses.items():
        seats = {}
        if c.centre is not None:
            seats[CENTRE] = c.centre
        for ai, ax in enumerate(AXES):
            for k, cell in enumerate(c.arms[ai]):
                if cell is not None:
                    seats[fmt_seat(ax, k)] = ("F:" + fd.particle_of(cell)) if fd.is_constructed(cell) else cell
        crosses[cid] = {"tier": c.tier, "L": c.L, "depth": c.depth, "topic": c.topic, "linked": c.linked, "seats": seats}
    return {"ok": True, "run_id": run.run_id, "closed": None if st.closed is None else list(st.closed), "thread": list(st.thread),
            "crosses": crosses, "surfaces": {uid: u.surface for uid, u in st.units.items()},
            "kinds": {uid: u.kind for uid, u in st.units.items()}, "pool": st.pool(), "counters": dict(st.counters), "guards": dict(st.guards),
            "caps": dict(run.caps), "ledger_head": run.head}


HANDLERS = {"lookup": h_lookup, "read_sentence": h_read_sentence, "add": h_add, "open_cross": h_open_cross, "seat": h_seat,
            "seat_run": h_seat_run, "weave_span": h_weave_span, "weave_sentence": h_weave_sentence, "unseat": h_unseat, "swap": h_swap, "extend": h_extend,
            "topic": h_topic, "set_depth": h_set_depth, "link": h_link, "unlink": h_unlink, "drop": h_drop, "read": h_read, "emit": h_emit,
            "abstain": h_abstain, "status": h_status}
