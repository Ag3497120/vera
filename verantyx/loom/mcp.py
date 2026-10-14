"""LOOM-d: the loom server (docs/LINE3_LOOM_DESIGN.md 4, 7.1 L3, 9.1).

  Sandbox      L3 in code.  Every path the server touches is resolve()d (symlinks followed) and checked: it READS only the corpus
               file(s) / fixture roots named by the task bank (and `--allow-root`), and WRITES only `<runs_root>/<run_id>/`.  Anything else is
               `path_outside_sandbox`.  The package imports no network and no process module (a test reads the imports).
  LoomServer   several runs per process, keyed by run_id (L-LOOM-07).  `call(tool, args)` is the one door: it executes one op, appends exactly
               one row to that run's ledger (refused calls and read-only calls too) and returns the result.  Pure Python: the scripted weaver, the
               tests and the FastMCP wrapper all use it.  Nothing here knows the MCP SDK.
  build/serve  the FastMCP stdio server named `vera-loom` (tool list = the 20 operations), the same pattern as verantyx/mcp_server.py but a
               separate module that does not touch the 126 tools of `vera mcp`.  The SDK is imported inside `build`, so this module imports
               without it.

A call that the SDK itself rejects (a mistyped argument against the tool schema) never reaches `LoomServer.call` and therefore leaves no row;
every call that reaches it does (design 4, open point in docs/LINE3_LOCAL_DECISIONS.md LOOM-core).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from verantyx.ledger_events import LedgerError, canonical, redact
from verantyx.loom import evidence as evl
from verantyx.loom import fixture as fx
from verantyx.loom import ledger as lg
from verantyx.loom import notes as notelib
from verantyx.loom.ledger import SandboxError
from verantyx.loom import paths
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import holds_memory_rows
from verantyx.loom.ops import MODEL_OPS, Run, check_task_against_index, normalize_task, refusal
from verantyx.loom.read import DEFAULT_STABILITY, STABILITY_MODES
from verantyx.loom.state import CAPS_PROFILES, CURRENT_CAPS

_RUN_ID_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MODEL_RX = re.compile(r"^[^\x00-\x1f\x7f]{1,64}$")
# the model-facing names of a tool's arguments -> the names the LEDGER stores (L-LOOM-145).  `from` is a Python keyword and cannot be a plain parameter of
# an MCP tool function, so the model sees `first` / `last` (inclusive) and the one door (`LoomServer.call`) stores `from` / `to`, as every ledger since LOOM-span has them.
DOOR_NAMES = {"weave_span": (("first", "from"), ("last", "to"))}
MAX_BEGINS = 256                  # L-LOOM-44: runs one server process opens


class Sandbox:
    def __init__(self, runs_root, read_files: Iterable = (), read_roots: Iterable = ()) -> None:
        self.runs_root = Path(runs_root).resolve()
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.runs_root = self.runs_root.resolve()
        self.read_files = {Path(p).resolve() for p in read_files}
        self.read_roots = [Path(p).resolve() for p in read_roots]

    def allow_file(self, path) -> Path:
        r = Path(path).resolve()
        self.read_files.add(r)
        return r

    def _allowed_read(self, r: Path) -> bool:
        if r in self.read_files:
            return True
        return any(r == root or root in r.parents for root in self.read_roots)

    def read_bytes(self, path) -> bytes:
        r = Path(path).resolve()
        if not self._allowed_read(r):
            raise SandboxError(str(path))
        return r.read_bytes()

    def run_dir(self, run_id) -> Path:
        """`<runs_root>/<run_id>`: the id is one path component of a fixed alphabet, and the resolved folder must be a direct child of runs_root."""
        if not isinstance(run_id, str) or not _RUN_ID_RX.match(run_id) or run_id in (".", ".."):
            raise SandboxError("run_id")
        p = (self.runs_root / run_id).resolve()
        if p.parent != self.runs_root:
            raise SandboxError(run_id)
        return p


class _Entry:
    def __init__(self, run: Run, ledger: lg.Ledger) -> None:
        self.run = run
        self.ledger = ledger
        self.t0 = time.monotonic_ns()


class LoomServer:
    def __init__(self, tasks: Iterable[dict], runs_dir, allow_roots: Iterable = (), stability: str = DEFAULT_STABILITY,
                 nonce: Optional[str] = None, max_begins: int = MAX_BEGINS, caps: str = CURRENT_CAPS, notes: str = notelib.NOTES_VERSION,
                 evidence: str = "v6", subject_scope: str = evl.DEFAULT_SCOPE) -> None:
        """`notes`: the notes definitions NEW runs of this server get (notes.v1 = CONFLICT / UNANCHORED / NO_RECORD, notes.v2 = + QUESTION_ECHO; L-LOOM-147).  It is
        written into each run's `begin` row (v1 writes nothing, as before).  `caps`: the cap profile NEW runs of this server get (state.CAPS_PROFILES: "v1" = the first measurement's numbers, "v2" = the current
        ones; L-LOOM-122).  It is written into each run's `begin` row; a run reloaded from its ledger keeps the profile it was recorded with.
        `evidence`: the reader's evidence gate NEW prose runs of this server get (LOOM-evidence, L-LOOM-170): "v6" (evidence.v6, the default: v2 plus the refusal-only safety rules CH, SU, TW and NEG, a pure filter over the v2 verdict; L-LOOM-226), "v2" (evidence.v2, the reviewed rules without the filter), "v1" (evidence.v1, the first build), "v3"
        (evidence.v3, the widened reach of docs/LINE3_LOOM_REACH_DESIGN.md: selectable, NOT the default until the held-out bank6 passes, OP-RE-2), "v4" (evidence.v4: v3 without the naming-verb rule R7 and with the subject-chain rule: selectable, NOT the default until the held-out bank7 passes, OP-PUB-6) "v5" (evidence.v5: v4 plus SU, a question whose subject phrase holds a piece the reader could not read is refused, and TW, the article title stands in for a subject word only as a whole word and a kind word alone is no subject: selectable, NOT the default) or "off" (no gate: the demo and the hand-built tests).  `subject_scope`: OP-EV-1, "clause_or_title" (owner: yes, the article title may stand in for the subject) or "clause".  Both are written into each
        prose run's `begin` row; a run reloaded from its ledger keeps the profile it was recorded with."""
        if stability not in STABILITY_MODES:
            raise ValueError("stability must be one of %s" % (STABILITY_MODES,))
        if caps not in CAPS_PROFILES:
            raise ValueError("caps must be one of %s" % (sorted(CAPS_PROFILES),))
        self.caps_profile = caps
        if notes not in notelib.NOTES_VERSIONS:
            raise ValueError("notes must be one of %s" % (notelib.NOTES_VERSIONS,))
        self.notes_profile = notes
        if evidence not in ("v1", "v2", "v3", "v4", "v5", "v6", "off"):
            raise ValueError("evidence must be 'v1', 'v2', 'v3', 'v4', 'v5', 'v6' or 'off'")
        if subject_scope not in evl.SUBJECT_SCOPES:
            raise ValueError("subject_scope must be one of %s" % (evl.SUBJECT_SCOPES,))
        self.evidence_profile: Optional[tuple] = None if evidence == "off" else (evl.PROFILE_NAMES[evidence], subject_scope)
        self.stability = stability
        self.nonce = nonce                                  # L-LOOM-45: None = reproducible ids (scripted runs); the MCP door passes os.urandom
        self.max_begins = max_begins
        self.n_begins = 0
        self.isolation: Optional[str] = None                # LOOM-d2 (L-LOOM-118): the profile sha the launcher declared, or None (not isolated)
        self.tasks: Dict[str, dict] = {}
        files = []
        for t in tasks:
            nt = normalize_task(t)
            if nt["task_id"] in self.tasks:
                raise ValueError("duplicate task_id %r" % nt["task_id"])
            if "corpus" not in nt:
                raise ValueError("task %r names no corpus" % nt["task_id"])
            self.tasks[nt["task_id"]] = nt
            files.append(nt["corpus"])
        roots = [Path(r) for r in allow_roots] + [Path(t["fixture"]) for t in self.tasks.values() if "fixture" in t]
        self.sandbox = Sandbox(runs_dir, files, roots)
        self.runs: Dict[str, _Entry] = {}
        self._seq = 0

    @classmethod
    def from_file(cls, tasks_path, runs_dir, allow_roots: Iterable = (), stability: str = DEFAULT_STABILITY, caps: str = CURRENT_CAPS,
                  evidence: str = "v6", subject_scope: str = evl.DEFAULT_SCOPE) -> "LoomServer":
        """The task bank is read once, here, before any tool call (an operator file: it holds no gold)."""
        rows = [json.loads(ln) for ln in Path(tasks_path).read_text(encoding="utf-8").splitlines() if ln.strip()]
        return cls(rows, runs_dir, allow_roots, stability, caps=caps, evidence=evidence, subject_scope=subject_scope)

    tool_names = MODEL_OPS

    # -- runs ---------------------------------------------------------------------------------------------------------
    def _loader(self, path: str) -> bytes:
        return self.sandbox.read_bytes(path)

    def _derive_run_id(self, task_id: str, model: str, corpus_sha: str) -> str:
        while True:
            ident = {"task_id": task_id, "model": model, "corpus_sha": corpus_sha, "seq": self._seq}
            if self.nonce is not None:
                ident["nonce"] = self.nonce
            rid = hashlib.sha256(canonical(ident).encode("utf-8")).hexdigest()[:12]
            self._seq += 1
            if not (self.sandbox.runs_root / rid).exists() and rid not in self.runs:
                return rid

    def begin(self, task_id: str, model: str, run_id: Optional[str] = None) -> dict:
        if self.n_begins >= self.max_begins:                # no run exists yet, so there is no ledger to hold this call: nothing is stored
            return refusal("cap_exceeded", {"guard": "begin", "limit": self.max_begins})
        if not isinstance(task_id, str) or task_id not in self.tasks:
            return refusal("unknown_task", {"task_id": task_id[:64] if isinstance(task_id, str) else None})
        if not isinstance(model, str) or not _MODEL_RX.match(model) or redact(model)[1]:
            return refusal("bad_model_id", {"reason": "1 to 64 printable characters, no secret-shaped text"})
        task = self.tasks[task_id]
        try:
            data = self.sandbox.read_bytes(task["corpus"])
        except SandboxError:
            return refusal("path_outside_sandbox", {})
        if holds_memory_rows(data):                           # MEM-a (L-MEM-02): a base corpus never holds the model's memory (a `mem:` row)
            return refusal("memory_in_base", {})
        corpus = Corpus.load(data)
        rid = run_id if run_id is not None else self._derive_run_id(task_id, model, corpus.corpus_sha)
        try:
            rdir = self.sandbox.run_dir(rid)
        except SandboxError:
            return refusal("bad_run_id", {"run_id": rid if isinstance(rid, str) else None})
        if rdir.exists() or rid in self.runs:
            return refusal("run_exists", {"run_id": rid})
        index = None
        if "fixture" in task:                                  # LOOM-code (L-LOOM-70): the CODE record index, read through the sandbox
            try:
                index = fx.build_index(task["fixture"], self.sandbox.read_bytes)
            except SandboxError:
                return refusal("path_outside_sandbox", {})
            except (OSError, ValueError):
                return refusal("fixture_unreadable", {})
            bad = check_task_against_index(task, index)       # L-LOOM-80: the target file / explicit context names must exist in the fixture
            if bad is not None:
                return refusal(bad["refusal"], bad["detail"])
        run = Run(corpus, task, model, rid, self.stability, index, CAPS_PROFILES[self.caps_profile][task["lang"]], self.notes_profile,
                  self.evidence_profile if task["lang"] == "prose" else None)
        led = lg.Ledger(rdir)
        meta = {"corpus": paths.meta_corpus(task["corpus"], rdir.parent), "corpus_sha": corpus.corpus_sha, "task_id": task_id, "isolated": self.isolation is not None}      # LOOM-path: relative to the repo root
        if self.isolation is not None:
            meta["isolation_profile_sha"] = self.isolation
        if index is not None:
            meta["fixture"] = paths.rel_to_root(task["fixture"])
        led.create(meta)
        with led.locked() as lk:
            body = run.begin_body()
            row = lk.append(body, 0)
            run.advance(row)
        self.runs[rid] = _Entry(run, led)
        self.n_begins += 1
        return dict(body["result"], isolated=self.isolation is not None)    # NOT in the stored row 0: the chain must replay the same on any machine

    def _entry(self, run_id) -> Optional[_Entry]:
        if not isinstance(run_id, str):
            return None
        e = self.runs.get(run_id)
        if e is not None:
            return e
        try:
            rdir = self.sandbox.run_dir(run_id)
        except SandboxError:
            return None
        if not (rdir / "ops.jsonl").exists():
            return None
        return self._reload(run_id, lg.Ledger(rdir))

    def _reload(self, run_id: str, led: lg.Ledger, lk=None) -> Optional[_Entry]:
        """Rebuild a run from its own ledger (a restarted server, or rows appended by another process).  `lk` = the append lock when the
        caller already holds it.  A ledger whose last row is a read / emit with notes due but no note row (a crash between the two appends,
        L-LOOM-105) is repaired here: the note row is appended first, so the repaired file is the file that never crashed."""
        rep = lg.replay(led.dir, loader=self._loader)
        if rep.identical and rep.run is not None and rep.pending_note:
            if lk is not None:
                _append_pending_note(rep.run, lk)
            else:
                with led.locked() as lk2:
                    rep = lg.replay(led.dir, loader=self._loader)                 # again, under the lock: another process may have repaired it
                    if rep.identical and rep.run is not None and rep.pending_note:
                        _append_pending_note(rep.run, lk2)
        if not rep.identical or rep.run is None:
            raise LedgerError("RUN_NOT_REPRODUCIBLE", "%s: %s %s" % (run_id, rep.status, rep.mismatch or rep.first_diff))
        e = _Entry(rep.run, led)
        self.runs[run_id] = e
        return e

    # -- the door -------------------------------------------------------------------------------------------------------
    def call(self, tool: str, args: Optional[dict] = None) -> dict:
        args = json.loads(canonical(args or {}))
        if tool == "begin":
            if set(args) - {"task_id", "model"} or "task_id" not in args or "model" not in args:
                return refusal("bad_args", {"reason": "begin takes task_id and model"})
            return self.begin(args["task_id"], args["model"])
        if tool not in MODEL_OPS:
            return refusal("unknown_tool", {"tool": tool if isinstance(tool, str) else None})
        rid = args.pop("run_id", None)
        e = self._entry(rid)
        if e is None:
            return refusal("unknown_run", {"run_id": rid if isinstance(rid, str) else None})
        if tool == "weave_span":                              # the model's names are first / last (inclusive); the ledger stores from / to (L-LOOM-145)
            for door, stored in DOOR_NAMES["weave_span"]:
                if door in args:
                    if stored in args:
                        return refusal("bad_args", {"field": door, "reason": "give %s, not %s as well" % (door, stored)})
                    args[stored] = args.pop(door)
        return self._exec(e, "model", tool, args)

    def harness(self, run_id: str, op: str, args: dict, actor: str = "harness") -> dict:
        """A row that is not the model's (free_text_dropped, harness_meta, abandoned, grade, ...)."""
        e = self._entry(run_id)
        if e is None:
            return refusal("unknown_run", {"run_id": run_id})
        return self._exec(e, actor, op, json.loads(canonical(args)))

    def _exec(self, e: _Entry, actor: str, op: str, args: dict) -> dict:
        with e.ledger.locked() as lk:
            n, prev = lk.tail()
            if n != e.run.i or prev != e.run.head:           # someone else appended (the harness CLI): rebuild from the file
                e = self._reload(e.run.run_id, e.ledger, lk)
            body = e.run.step(actor, op, args)
            try:
                row = lk.append(body, time.monotonic_ns() - e.t0)
            except BaseException:
                self.runs.pop(e.run.run_id, None)             # the in-memory run is ahead of the file: the next call rebuilds it from the file
                raise
            e.run.advance(row)
            result = body["result"]
            notes = e.run.notes_due() if actor == "model" else []
            if notes:                                         # LOOM-notes: a row of its own AFTER the read / emit row; that row is unchanged
                try:
                    nrow = lk.append(e.run.step(notelib.NOTE_ACTOR, notelib.NOTE_OP, {}), time.monotonic_ns() - e.t0)
                except BaseException:                         # the read / emit row is stored, its note row is not: rebuild (and repair) on the next call
                    self.runs.pop(e.run.run_id, None)
                    raise
                e.run.advance(nrow)
                result = dict(result, notes=notes)             # a copy: the stored row and the replayed row never hold the notes
        return result

    def closed(self, run_id: str) -> Optional[List[str]]:
        e = self._entry(run_id)
        return None if e is None or e.run.state.closed is None else list(e.run.state.closed)

    def run_dir(self, run_id: str) -> Path:
        return self.sandbox.run_dir(run_id)


def _append_pending_note(run: Run, lk) -> None:
    """Append the note row a stored read / emit is owed (replay found it last, notes due, no note row) and advance the run past it."""
    run.advance(lk.append(run.step(notelib.NOTE_ACTOR, notelib.NOTE_OP, {})))


def isolation_claim() -> Optional[str]:
    """LOOM-d2 (L-LOOM-118): `vera loom mcp --isolated` re-executes the server under sandbox-exec with LOOM_ISOLATED=<profile sha> in a cleared
    environment.  This is the one place that READS it.  The claim is a declaration of the launcher, corroborated here by the one cheap witness
    that needs no network and no process module: under the profile /etc/passwd cannot be opened.  A set variable with a readable /etc/passwd is
    not believed (None).  It is not a proof (the probe ran before the exec, not from inside this process); it makes a run made under
    `--isolated` distinguishable from one that was not (LOOM-i)."""
    claim = os.environ.get("LOOM_ISOLATED", "")
    if not claim or not re.fullmatch(r"[0-9a-f]{64}", claim):
        return None
    try:
        with open("/etc/passwd", "rb"):
            return None
    except OSError:
        return claim


def append_outside_row(run_dir, actor: str, op: str, args: dict, loader: lg.Loader = lg.default_loader) -> dict:
    """The CLI's door for harness / human rows (`vera loom note`, `close`): rebuild the run from its own ledger, check that it replays
    identically, step it, append.  Raises LedgerError if the run does not reproduce."""
    led = lg.Ledger(run_dir)
    with led.locked() as lk:
        rep = lg.replay(run_dir, loader=loader)
        if not rep.identical or rep.run is None:
            raise LedgerError("RUN_NOT_REPRODUCIBLE", "%s %s" % (rep.status, rep.mismatch or rep.first_diff))
        if rep.pending_note:                                   # L-LOOM-105: a crash between a read / emit and its note row: the repair comes first
            _append_pending_note(rep.run, lk)
        body = rep.run.step(actor, op, json.loads(canonical(args)))
        n, prev = lk.tail()
        if n != rep.run.i or prev != rep.run.head:
            raise LedgerError("RUN_NOT_REPRODUCIBLE", "the ledger moved while it was being replayed")
        return lk.append(body)


# ------------------------------------------------------------------------------------------------------------
# the FastMCP wrapper
# ------------------------------------------------------------------------------------------------------------
def build(tasks_path, runs_dir, allow_roots: Iterable = (), stability: str = DEFAULT_STABILITY, nonce: Optional[str] = None, caps: str = CURRENT_CAPS,
          evidence: str = "v6", subject_scope: str = evl.DEFAULT_SCOPE):
    """The FastMCP server `vera-loom` WITHOUT running it (None if the SDK is missing).  `mcp.loom_server` is the LoomServer behind it."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print('MCP SDK not installed. Run:  pip install "mcp[cli]"')
        return None
    server = LoomServer.from_file(tasks_path, runs_dir, allow_roots, stability, caps, evidence, subject_scope)
    server.isolation = isolation_claim()
    server.nonce = nonce if nonce is not None else os.urandom(16).hex()      # L-LOOM-45: a weaver cannot compute another weaver's run id
    mcp = FastMCP("vera-loom")
    mcp.loom_server = server

    def out(tool: str, args: dict) -> str:
        return json.dumps(server.call(tool, args), ensure_ascii=False, sort_keys=True)

    @mcp.tool()
    def begin(task_id: str, model: str) -> str:
        """Start a run. Returns run_id, the task text, the mode and the rules. `model` is your own model id (testimony, at most 64 chars). The only way to answer is to build Vera's structure and call emit; plain text is discarded."""
        return out("begin", {"task_id": task_id, "model": model})

    @mcp.tool()
    def lookup(run_id: str, text: str, tier: str) -> str:
        """Find a corpus unit by exact surface (no substring search). tier: RUN | WORD | CHAR | any. Returns n, every sentence id, and the first 5 sentences."""
        return out("lookup", {"run_id": run_id, "text": text, "tier": tier})

    @mcp.tool()
    def read_sentence(run_id: str, sid: int) -> str:
        """Read one corpus sentence by id, with the units it holds in each tier."""
        return out("read_sentence", {"run_id": run_id, "sid": sid})

    @mcp.tool()
    def add(run_id: str, text: str, kind: str, tier: str = "") -> str:
        """Add a unit to the pool. kind=record: text must be exactly a unit of `tier` (RUN|WORD|CHAR). kind=constructed: your own word, marked as yours, only if the mode allows it (1-8 chars, not a corpus unit). Returns the uid."""
        a = {"run_id": run_id, "text": text, "kind": kind}
        if tier:
            a["tier"] = tier
        return out("add", a)

    @mcp.tool()
    def open_cross(run_id: str, tier: str, L: int, depth: int = 0) -> str:
        """Open a cross of arm length L (prose 1-5, code 1-8). In a prose cross the innermost seat of each arm holds the foundation particle (の に で と を が) and is never yours. depth is for code lines only."""
        a = {"run_id": run_id, "tier": tier, "L": L}
        if depth:
            a["depth"] = depth
        return out("open_cross", a)

    @mcp.tool()
    def seat(run_id: str, cid: str, seat: str, uid: str) -> str:
        """Seat a unit. seat = 'centre' or '<arm>:<k>' (k=0 is the outer end), or a bare arm such as '+x' for the innermost empty seat of that arm."""
        return out("seat", {"run_id": run_id, "cid": cid, "seat": seat, "uid": uid})

    @mcp.tool()
    def seat_run(run_id: str, cid: str, arm: str, uids: list[str]) -> str:
        """Seat several units on one arm IN THE ORDER THEY ARE READ (prose: outer to inner, ending next to the particle; code: inner to outer)."""
        return out("seat_run", {"run_id": run_id, "cid": cid, "arm": arm, "uids": uids})

    @mcp.tool()
    def weave_span(run_id: str, sid: int, tier: str, first: str, last: str) -> str:
        """SPAN WEAVING in one call. Give a corpus sentence id you have read (read_sentence), a tier (RUN|WORD|CHAR) and the stretch you want, from the unit `first` to the unit `last` (both included), each written exactly as read_sentence lists that unit for the tier (plain text, no quotation marks; `last` is searched from `first` on). The loom makes record units for exactly those units and builds the chain of crosses whose read-out is that stretch WORD FOR WORD, linked at the end of the thread: a unit followed by one of の に で と を が goes on that particle's arm of the cross whose centre is the very next unit; units that touch each other become one-unit crosses in order; a unit followed by は is a topic centre. If the stretch is not expressible (a word the loom cannot write between two units, such as という or として, or a chain like AのBのC that needs one unit as both a centre and an arm unit) it is refused as span_inexpressible and nothing changes; weave a smaller stretch. Returns the crosses and seats it made and the text of the stretch (not the rest of the sentence). Record units only; one operation. Use `drop` to throw a cross away."""
        # STRINGS ONLY in the schema: with `int | str` (anyOf) Haiku 5.5 sent every value as a string, 9 of 21 calls with the unit in literal quotation marks and
        # 11 with an index as a digit string, and 20 of the 21 were refused (results_h55c0_aborted, L-LOOM-133).  The handler still takes an int (an index into
        # read_sentence's unit list) from a programmatic caller.  `first` / `last` are the model's names; the LEDGER stores `from` / `to` (L-LOOM-145): the
        # rename happens in LoomServer.call, the one door of both the MCP wrapper and the API driver.
        return out("weave_span", {"run_id": run_id, "sid": sid, "tier": tier, "first": first, "last": last})

    @mcp.tool()
    def unseat(run_id: str, cid: str, seat: str) -> str:
        """Take a unit off a seat; it goes back to the pool."""
        return out("unseat", {"run_id": run_id, "cid": cid, "seat": seat})

    @mcp.tool()
    def swap(run_id: str, cid: str, seat_a: str, seat_b: str) -> str:
        """Exchange two data seats of one cross; either may be empty (then it is a move)."""
        return out("swap", {"run_id": run_id, "cid": cid, "seat_a": seat_a, "seat_b": seat_b})

    @mcp.tool()
    def extend(run_id: str, cid: str, L2: int) -> str:
        """Grow a cross to arm length L2 by adding empty outer seats to every arm."""
        return out("extend", {"run_id": run_id, "cid": cid, "L2": L2})

    @mcp.tool()
    def topic(run_id: str, cid: str, on: bool) -> str:
        """Mark a prose cross as a topic: は is read right after its centre word."""
        return out("topic", {"run_id": run_id, "cid": cid, "on": on})

    @mcp.tool()
    def set_depth(run_id: str, cid: str, depth: int) -> str:
        """Set the indentation depth (0-8) of a code cross."""
        return out("set_depth", {"run_id": run_id, "cid": cid, "depth": depth})

    @mcp.tool()
    def link(run_id: str, cid: str, pos: int = -1) -> str:
        """Add a cross to the thread at position pos (default: the end). Crosses are read in thread order."""
        a = {"run_id": run_id, "cid": cid}
        if pos != -1:                                       # -1 = the end; any other negative number reaches h_link and is `bad_pos` (L-LOOM-49)
            a["pos"] = pos
        return out("link", a)

    @mcp.tool()
    def unlink(run_id: str, cid: str) -> str:
        """Remove a cross from the thread; its units stay seated."""
        return out("unlink", {"run_id": run_id, "cid": cid})

    @mcp.tool()
    def drop(run_id: str, cid: str) -> str:
        """Throw a whole cross away: the cross and the units seated in it are removed (they are gone, not returned to the pool), and the cross leaves the thread if it was linked. One operation."""
        return out("drop", {"run_id": run_id, "cid": cid})

    @mcp.tool()
    def read(run_id: str) -> str:
        """Dry run of emit: returns the text the thread reads as, the annotated segments, every refusal emit would give, and the stability of each cross. Nothing closes. `notes` may list structural observations (CONFLICT, UNANCHORED, NO_RECORD, QUESTION_ECHO: a unit that is a word of the question); they never block."""
        return out("read", {"run_id": run_id})

    @mcp.tool()
    def emit(run_id: str) -> str:
        """Fix the output: the text the thread reads as. Refused with every reason if the structure is not sound (unstable cross, unlinked cross, empty centre, no_evidence, ...). A successful emit may carry `notes` (CONFLICT, UNANCHORED, NO_RECORD, QUESTION_ECHO: a unit that is a word of the question); they never block."""
        return out("emit", {"run_id": run_id})

    @mcp.tool()
    def abstain(run_id: str, type: str) -> str:
        """Close the run without an output. type: no_record | cannot_weave | unknown."""
        return out("abstain", {"run_id": run_id, "type": type})

    @mcp.tool()
    def status(run_id: str) -> str:
        """The thread, the crosses and their seats, the pool, the counters and the caps."""
        return out("status", {"run_id": run_id})

    return mcp


def serve(tasks_path, runs_dir, allow_roots: Iterable = (), stability: str = DEFAULT_STABILITY, evidence: str = "v6", subject_scope: str = evl.DEFAULT_SCOPE) -> int:
    mcp = build(tasks_path, runs_dir, allow_roots, stability, evidence=evidence, subject_scope=subject_scope)
    if mcp is None:
        return 2
    mcp.run()
    return 0
