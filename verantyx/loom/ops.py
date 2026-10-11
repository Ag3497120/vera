"""LOOM-a: the operations of the loom (docs/LINE3_LOOM_DESIGN.md 4) and Run.step, the one door through which a call becomes a row.

THE 18 TOOLS (MODEL_OPS): begin lookup read_sentence add open_cross seat seat_run unseat swap extend topic set_depth link unlink
read emit abstain status.  There is NO `rotate` (L-LOOM-01) and NO undo (L-LOOM-09).

A call never raises to its caller: it returns {"ok": true, ...} or {"ok": false, "refusal": <type>, "detail": {...}}.  Every
refusal is raised as `state.Refuse` BEFORE any mutation, so a refused call leaves the state exactly as it was (apart from the
counter of its class).  Counters count every call of a class that was not itself refused by that class's cap, refused or not,
so "caps fire exactly at the limit" and a run cannot spin on refusals for ever.

THE CAPS (L-LOOM-08), per run: state-changing ops (add open_cross seat seat_run unseat swap extend topic set_depth link unlink),
lookups (lookup + read_sentence), reads, emit attempts, constructed units, crosses; chars per constructed unit.  `emit`, `abstain`
and `status` are not capped, except `emit` by its own attempt cap.  After the run is closed every model call is `run_closed`.

Run.step(actor, op, args) is what both the live server and the replay call: it executes the op, builds the body of the ledger row
({actor, op, args, result, state_sha}), and never looks at a clock.  A call whose arguments contain a secret-shaped string is
refused `secret_shaped_unit` and its arguments are stored redacted (with the sha256 of the original arguments), so no secret
reaches a row (design 5.1).
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
from verantyx.loom import read as rd
from verantyx.loom.code import CodeIndex
from verantyx.loom.corpus import Corpus
from verantyx.loom.state import (ABSTAIN_TYPES, ALL_TIERS, ARG_STR_CAP, ARGS_CHARS_CAP, AXES, CAPS, CENTRE, CODE, CODE_TIER, CONSTRUCTED, GUARD_CAPS, LANGS, MODES,
                                 PROSE, PROSE_TIERS, RECORD, LoomCross, LoomState, Refuse, canonical, fmt_seat, parse_seat, sha256_text)

MODEL_OPS: Tuple[str, ...] = ("begin", "lookup", "read_sentence", "add", "open_cross", "seat", "seat_run", "unseat", "swap", "extend",
                              "topic", "set_depth", "link", "unlink", "read", "emit", "abstain", "status")
HARNESS_OPS: Tuple[str, ...] = ("abandoned", "free_text_dropped", "free_text_control", "harness_meta")
HUMAN_OPS: Tuple[str, ...] = ("grade",)
LOOP_OPS: Tuple[str, ...] = ("attest", "audit_verdict", "stacked")                  # design 6.1 / 11: rows appended by later tickets
ALL_OPS: Tuple[str, ...] = MODEL_OPS + HARNESS_OPS + HUMAN_OPS + LOOP_OPS
ACTORS: Tuple[str, ...] = ("model", "harness", "human")

STATE_CHANGING: Tuple[str, ...] = ("add", "open_cross", "seat", "seat_run", "unseat", "swap", "extend", "topic", "set_depth", "link", "unlink")
CLASS_OF: Dict[str, str] = dict({op: "ops" for op in STATE_CHANGING},
                                lookup="lookups", read_sentence="lookups", read="reads", emit="emit_attempts")
CAP_REFUSAL: Dict[str, str] = {"ops": "ops_cap", "lookups": "lookup_cap", "reads": "read_cap", "emit_attempts": "emit_cap"}

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


def task_view(task: dict) -> dict:
    """What `begin` returns and what the row stores: the task WITHOUT paths (no absolute path in a hashed row) and with the caps."""
    view = {"task_id": task["task_id"], "text": task["text"], "lang": task["lang"], "mode": task["mode"], "tiers": list(task["tiers"]),
            "caps": dict(CAPS[task["lang"]])}
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
    refused `args_too_large`.  Every legitimate call of the 18 tools is far below both."""
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
        ok = (isinstance(v, list) and all(isinstance(x, str) for x in v)) if typ == "strs" else \
             (isinstance(v, int) and not isinstance(v, bool)) if typ is int else isinstance(v, typ)
        if not ok:
            raise Refuse("bad_args", {"field": name, "reason": "expected %s" % ("list of str" if typ == "strs" else typ.__name__)})
        out[name] = v
    return out


# ------------------------------------------------------------------------------------------------------------
# the run
# ------------------------------------------------------------------------------------------------------------
class Run:
    def __init__(self, corpus: Corpus, task: dict, model: str, run_id: str, stability_mode: str = rd.DEFAULT_STABILITY,
                 code_index: Optional[CodeIndex] = None) -> None:
        if stability_mode not in rd.STABILITY_MODES:
            raise ValueError("stability must be one of %s" % (rd.STABILITY_MODES,))
        self.corpus = corpus
        self.code_index = code_index                       # the CODE record index of the task's fixture (None: prose, or a code task with no fixture)
        self.task = normalize_task(task)
        self.model = model
        self.run_id = run_id
        self.lang = self.task["lang"]
        self.mode = self.task["mode"]
        self.caps = dict(CAPS[self.lang])
        self.stability_mode = stability_mode
        self.state = LoomState(self.lang)
        self.i = 0                         # the index of the next row
        self.head = GENESIS                # the sha of the last row

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
        res = {"ok": True, "run_id": self.run_id, "task": task_view(self.task), "rules": RULES, "header": self.header()}
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
        if actor == "model":
            return self._model_step(op, args, replay_extra)
        return self._outside_step(actor, op, args)

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
        blocked = self._guard_blocked(op, args) if isinstance(op, str) and op in MODEL_OPS else None
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
        try:
            if blocked is not None:
                raise Refuse("cap_exceeded", {"guard": blocked, "limit": GUARD_CAPS[blocked]})
            if op == "begin" or op not in MODEL_OPS:
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
        ok = (actor == "harness" and (op in HARNESS_OPS or op in LOOP_OPS)) or (actor == "human" and op in HUMAN_OPS)
        if not ok:
            raise ValueError("op %r is not a row of actor %r" % (op, actor))
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
            "seat_run": h_seat_run, "unseat": h_unseat, "swap": h_swap, "extend": h_extend, "topic": h_topic, "set_depth": h_set_depth,
            "link": h_link, "unlink": h_unlink, "read": h_read, "emit": h_emit, "abstain": h_abstain, "status": h_status}
