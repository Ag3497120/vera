"""LOOM-d: the per-run ledger, verify, replay and the L4 consumer (docs/LINE3_LOOM_DESIGN.md 6, 7.1 L4).

A run's folder is  <runs_root>/<run_id>/{ops.jsonl, HEAD, .lock, timing.jsonl, meta.json}.

  ops.jsonl     one canonical-JSON row per call, append-only, hash-chained:
                  {"v":1, "i":<0-based>, "actor":"model"|"harness"|"human", "op":<closed list>, "args":{...}, "result":{...},
                   "state_sha":<sha256 of the canonical state after the op>, "prev":<sha of row i-1 | 64 zeros>, "sha":sha256(canonical(row without sha))}
                a row whose arguments held a secret-shaped string also has "redacted":n and "args_sha256" (the arguments are stored redacted);
                a row whose arguments were too large (or that is beyond a guard cap) has "truncated":true, "args_sha256", "args_chars" and
                "args":{} (L-LOOM-44).  verify requires every line to BE the canonical serialisation of its row (L-LOOM-43).
                NO WALL-CLOCK TIME in a row (L-LOOM-15): that is what lets a replay reproduce the file byte for byte.
  HEAD          the sha of the last row (a pin; commit it, or pass `--head`, to catch a rewrite of the whole chain).
  timing.jsonl  {"i", "t_ns"} per row, OUTSIDE the chain (the recorder's runs/ idea).
  meta.json     where the corpus lives (a path, never hashed) so that a replay can find it.

From verantyx/ledger_events.py only the pure functions are reused (canonical, GENESIS, redact via ops, LedgerError); the recorder's own
ledger (.vera/ledger, ALL_KINDS pinned by the installed hooks) is never touched.

verify: the chain (OK / EMPTY / TAMPERED / TORN_TAIL / HEAD_MISMATCH, docs/RECORDER.md 2), then the replay: REPLAY_DIFFERS (the chain is
intact but the ops do not reproduce the results: a server bug or a forged result), REPLAY_INPUTS_MISMATCH (the corpus / space / adhesion /
seats / python the header names are not reproduced).  replay: re-execute every model row against a fresh state, re-apply the harness /
human rows as recorded, write the new rows; they must equal the original byte for byte.

emitted_output is the L4 consumer: it calls verify first and reads ONLY the successful `emit` row; nothing else of a run (lookups, reads,
statuses, free text) is ever output.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from verantyx.ledger_events import GENESIS, LedgerError, canonical
from verantyx.loom import LOOM_VERSION
from verantyx.loom import fixture as fx
from verantyx.loom import notes as notelib
from verantyx.loom.corpus import Corpus
from verantyx.loom.ops import Run, normalize_task

ROW_KEYS = frozenset(("v", "i", "actor", "op", "args", "result", "state_sha", "prev", "sha"))
ROW_KEYS_REDACTED = ROW_KEYS | {"redacted", "args_sha256"}
ROW_KEYS_TRUNCATED = ROW_KEYS | {"truncated", "args_sha256", "args_chars"}         # L-LOOM-44: the arguments are stored as sha256 + length
EXTRA_FIELDS = ("redacted", "truncated", "args_sha256", "args_chars")
DIFF_FIELDS = ("v", "i", "actor", "op", "args", "result", "state_sha", "redacted", "truncated", "args_sha256", "args_chars", "prev", "sha")
STATUSES = ("OK", "EMPTY", "TAMPERED", "TORN_TAIL", "HEAD_MISMATCH", "REPLAY_DIFFERS", "REPLAY_INPUTS_MISMATCH")
Loader = Callable[[str], bytes]


def row_sha(row: dict) -> str:
    return hashlib.sha256(canonical({k: v for k, v in row.items() if k != "sha"}).encode("utf-8")).hexdigest()


def seal(i: int, prev: str, body: dict) -> dict:
    """The row of index i whose predecessor has sha `prev`.  `body` = {actor, op, args, result, state_sha[, redacted, args_sha256 | truncated, args_sha256, args_chars]}."""
    row = {"v": 1, "i": i}
    row.update(body)
    row["prev"] = prev
    row["sha"] = row_sha(row)
    return row


def line_of(row: dict) -> bytes:
    return (canonical(row) + "\n").encode("utf-8")


# ------------------------------------------------------------------------------------------------------------
# the folder
# ------------------------------------------------------------------------------------------------------------
class Ledger:
    def __init__(self, run_dir) -> None:
        self.dir = Path(run_dir)
        self.ops = self.dir / "ops.jsonl"
        self.head = self.dir / "HEAD"
        self.lock = self.dir / ".lock"
        self.timing = self.dir / "timing.jsonl"
        self.meta = self.dir / "meta.json"

    def create(self, meta: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=False)
        self.meta.write_text(json.dumps(meta, sort_keys=True, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def read_meta(self) -> dict:
        try:
            return json.loads(self.meta.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @contextmanager
    def locked(self):
        """flock(LOCK_EX) over the append: the next index and `prev` are read from the file under the lock."""
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.lock, "a") as lk:
            fcntl.flock(lk.fileno(), fcntl.LOCK_EX)
            try:
                yield _Locked(self)
            finally:
                fcntl.flock(lk.fileno(), fcntl.LOCK_UN)


class _Locked:
    def __init__(self, led: Ledger) -> None:
        self.led = led

    def tail(self) -> Tuple[int, str]:
        """(number of rows, sha of the last row) read from the file.  A torn tail refuses (TORN_TAIL_BLOCKS_APPEND)."""
        p = self.led.ops
        if not p.exists() or p.stat().st_size == 0:
            return 0, GENESIS
        with open(p, "rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                raise LedgerError("TORN_TAIL_BLOCKS_APPEND", "the last line does not end in a newline; verify, then a person repairs it")
        raw = p.read_bytes().rstrip(b"\n")
        last = raw[raw.rfind(b"\n") + 1:]
        try:
            r = json.loads(last.decode("utf-8"))
            return int(r["i"]) + 1, r["sha"]
        except Exception:
            raise LedgerError("TORN_TAIL_BLOCKS_APPEND", "the last line cannot be read; verify, then a person repairs it")

    def append(self, body: dict, t_ns: Optional[int] = None) -> dict:
        n, prev = self.tail()
        row = seal(n, prev, body)
        line = line_of(row)
        fd_ = os.open(self.led.ops, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd_, line)
            os.fsync(fd_)
        finally:
            os.close(fd_)
        tmp = self.led.dir / (".HEAD.%d.tmp" % os.getpid())
        with open(tmp, "w") as f:
            f.write(row["sha"] + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.led.head)
        if t_ns is not None:
            with open(self.led.timing, "a", encoding="utf-8") as f:
                f.write(canonical({"i": n, "t_ns": t_ns}) + "\n")
        return row


# ------------------------------------------------------------------------------------------------------------
# verify (the chain)
# ------------------------------------------------------------------------------------------------------------
def read_raw_lines(run_dir) -> Tuple[List[bytes], bool]:
    """The RAW lines of ops.jsonl (bytes, without the newline) and whether the last one has no newline (L-LOOM-43: verify and replay
    judge the bytes of the file, never a parsed copy of them)."""
    p = Path(run_dir) / "ops.jsonl"
    raw = p.read_bytes() if p.exists() else b""
    lines = raw.split(b"\n")
    unterminated = bool(raw) and not raw.endswith(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return lines, unterminated


def read_lines(run_dir) -> Tuple[List[str], bool]:
    lines, unterminated = read_raw_lines(run_dir)
    return [ln.decode("utf-8", errors="replace") for ln in lines], unterminated


def _parse_line(ln: bytes) -> dict:
    r = json.loads(ln.decode("utf-8"))
    if not isinstance(r, dict):
        raise ValueError("not an object")
    return r


def verify_chain(run_dir, expected_head: Optional[str] = None) -> dict:
    """docs/RECORDER.md 2, for the loom's row shape.  Line numbers are 1-based."""
    d = Path(run_dir)
    lines, unterminated = read_raw_lines(d)
    problems: List[dict] = []
    expected_prev: Optional[str] = GENESIS
    last_ok_sha: Optional[str] = None
    shas: List[Tuple[int, str]] = []
    n_rows = 0
    for ln_no, ln in enumerate(lines, 1):
        is_tail = unterminated and ln_no == len(lines)
        try:
            r = _parse_line(ln)
        except Exception:
            problems.append({"line": ln_no, "type": "TORN_TAIL" if is_tail else "LINE_UNPARSABLE"})
            expected_prev = None
            continue
        n_rows += 1
        if is_tail:
            problems.append({"line": ln_no, "type": "TORN_TAIL"})            # a row that parses but has no newline: an append would be refused
        if set(r) not in (ROW_KEYS, ROW_KEYS_REDACTED, ROW_KEYS_TRUNCATED):
            problems.append({"line": ln_no, "type": "BAD_SHAPE"})
            expected_prev = None
            continue
        if r["i"] != ln_no - 1:
            problems.append({"line": ln_no, "type": "BAD_INDEX"})
        try:
            if row_sha(r) != r["sha"]:
                problems.append({"line": ln_no, "type": "SHA_MISMATCH"})
        except Exception:
            problems.append({"line": ln_no, "type": "BAD_SHAPE"})
        try:
            canon_ok = canonical(r).encode("utf-8") == ln
        except Exception:
            canon_ok = False
        if not canon_ok:       # L-LOOM-43: whitespace, key order, a duplicate key, an escape: the line is not what the server writes
            problems.append({"line": ln_no, "type": "NONCANONICAL_LINE"})
        if expected_prev is not None and r["prev"] != expected_prev:
            problems.append({"line": ln_no, "type": "PREV_MISMATCH"})
        expected_prev = r["sha"] if isinstance(r["sha"], str) else None
        if isinstance(r["sha"], str):
            shas.append((ln_no, r["sha"]))
            last_ok_sha = r["sha"]
    hp = d / "HEAD"
    head = hp.read_text().strip() if hp.exists() else None
    if head is None:
        if n_rows or lines:
            problems.append({"line": None, "type": "HEAD_MISSING"})
    elif head != last_ok_sha:
        p = {"line": None, "type": "HEAD_MISMATCH"}
        at = [i for i, s in shas if s == head]
        if at:
            p["HEAD_POINTS_TO_LINE"] = at[0]
        else:
            p["HEAD_NOT_IN_CHAIN"] = True
        problems.append(p)
    if expected_head is not None and expected_head != last_ok_sha:
        problems.append({"line": None, "type": "EXPECTED_HEAD_MISMATCH", "expected": expected_head, "actual": last_ok_sha})
    if not lines and head is None and not problems:
        return {"status": "EMPTY", "n": 0, "problems": [], "head": None}
    row_types = {p["type"] for p in problems if p["type"] in ("LINE_UNPARSABLE", "BAD_SHAPE", "BAD_INDEX", "SHA_MISMATCH", "PREV_MISMATCH",
                                                              "NONCANONICAL_LINE")}
    if row_types:
        status = "TAMPERED"
    elif any(p["type"] == "TORN_TAIL" for p in problems):
        status = "TORN_TAIL"
    elif problems:
        status = "HEAD_MISMATCH"
    else:
        status = "OK"
    return {"status": status, "n": len(lines), "problems": problems, "head": head}


# ------------------------------------------------------------------------------------------------------------
# replay
# ------------------------------------------------------------------------------------------------------------
class SandboxError(Exception):
    """`path_outside_sandbox` (L3).  Defined here so that the ledger can name it without importing mcp.py; mcp.SandboxError is this class."""

    type = "path_outside_sandbox"


class ReplayResult:
    def __init__(self) -> None:
        self.status = "IDENTICAL"          # IDENTICAL | DIFFERS | INPUTS
        self.mismatch: Optional[str] = None       # INPUTS: the typed mismatch
        self.first_diff: Optional[dict] = None    # DIFFERS: {"i", "field"}
        self.lines: List[bytes] = []              # the rows the replay produced (up to the first difference)
        self.text: Optional[str] = None           # the emitted text of the (re-derived) run, if any
        self.run: Optional[Run] = None
        self.n_rows = 0
        self.pending_note = False                 # LOOM-notes: the LAST row is a read / emit whose notes are due and its note row is not (yet) there
        self.notes_stale: List[int] = []          # LOOM-notes: the note rows recorded under another notes version, accepted as recorded

    @property
    def identical(self) -> bool:
        return self.status == "IDENTICAL"

    def exit_code(self) -> int:
        return {"IDENTICAL": 0, "DIFFERS": 1, "INPUTS": 2}[self.status]

    def to_obj(self) -> dict:
        return {"status": self.status, "mismatch": self.mismatch, "first_diff": self.first_diff, "rows": self.n_rows, "text": self.text,
                "pending_note": self.pending_note, "notes_stale": list(self.notes_stale)}


def default_loader(path: str) -> bytes:
    return Path(path).read_bytes()


def _first_diff(orig: dict, new: dict) -> str:
    for f in DIFF_FIELDS:
        if orig.get(f, "<absent>") != new.get(f, "<absent>"):
            return f
    return "shape"


def header_mismatch(recorded: dict, fresh: dict) -> Optional[str]:
    """The typed mismatch between the header a run recorded and the header the inputs reproduce now (None = reproduced)."""
    order = (("python_version", "python_mismatch"), ("python_implementation", "python_mismatch"), ("loom_version", "loom_version_mismatch"), ("corpus_sha", "corpus_sha_mismatch"),
             ("space_sha", "space_sha_mismatch"), ("adhesion_sha", "adhesion_sha_mismatch"), ("seats_sha", "seats_sha_mismatch"),
             ("code_index_sha", "code_index_sha_mismatch"))
    for key, name in order:
        if recorded.get(key) != fresh.get(key):
            return name
    return None


def replay(run_dir, corpus_path: Optional[str] = None, loader: Loader = default_loader) -> ReplayResult:
    out = ReplayResult()
    lines, unterminated = read_raw_lines(run_dir)
    out.n_rows = len(lines)
    try:
        rows = [_parse_line(ln) for ln in lines]
    except Exception:
        out.status, out.first_diff = "DIFFERS", {"i": None, "field": "unreadable"}
        return out
    if not rows or rows[0].get("op") != "begin" or not isinstance(rows[0].get("result"), dict):
        out.status, out.first_diff = "DIFFERS", {"i": 0, "field": "op"}
        return out
    r0 = rows[0]
    res0 = r0["result"]
    try:
        task = dict(res0["task"])
        task.pop("caps", None)
        task = normalize_task(task)
        recorded_header = res0["header"]
        model, run_id = r0["args"]["model"], res0["run_id"]
        stability = recorded_header["stability_mode"]
    except Exception:
        out.status, out.first_diff = "DIFFERS", {"i": 0, "field": "result"}
        return out
    path = corpus_path or Ledger(run_dir).read_meta().get("corpus")
    if not path:
        out.status, out.mismatch = "INPUTS", "corpus_unresolved"
        return out
    try:
        data = loader(path)
    except SandboxError:                                       # L-LOOM-48: a path outside the sandbox is a typed status, not a crash
        out.status, out.mismatch = "INPUTS", "corpus_outside_sandbox"
        return out
    except OSError:
        out.status, out.mismatch = "INPUTS", "corpus_unreadable"
        return out
    corpus = Corpus.load(data)
    index = None
    if recorded_header.get("code_index_sha") is not None:        # LOOM-code: rebuild the CODE index from the fixture the run names
        froot = Ledger(run_dir).read_meta().get("fixture")
        if not froot:
            out.status, out.mismatch = "INPUTS", "fixture_unresolved"
            return out
        try:
            index = fx.build_index(froot, loader)
        except SandboxError:
            out.status, out.mismatch = "INPUTS", "fixture_outside_sandbox"
            return out
        except (OSError, ValueError):
            out.status, out.mismatch = "INPUTS", "fixture_unreadable"
            return out
    run = Run(corpus, task, model, run_id, stability, index)
    mm = header_mismatch(recorded_header, run.header())
    if mm is not None:
        out.status, out.mismatch = "INPUTS", mm
        return out
    out.run = run
    run.replaying = True
    try:
        _replay_rows(out, run, rows, lines, unterminated)
    finally:
        run.replaying = False
    return out


def _replay_rows(out: ReplayResult, run: Run, rows: List[dict], lines: List[bytes], unterminated: bool) -> None:
    prev = GENESIS
    for idx, orig in enumerate(rows):
        try:
            if idx == 0:
                body = run.begin_body()
            else:
                red = {k: orig[k] for k in EXTRA_FIELDS if k in orig} or None
                body = run.step(orig["actor"], orig["op"], orig["args"], red)
            row = seal(idx, prev, body)
        except Exception:                                  # a recorded row the code can no longer execute is a difference, not a crash
            out.status, out.first_diff = "DIFFERS", {"i": idx, "field": "exception"}
            return
        out.lines.append(line_of(row))
        if row != orig:
            out.status, out.first_diff = "DIFFERS", {"i": idx, "field": _first_diff(orig, row)}
            return
        if line_of(row) != lines[idx] + b"\n" or (unterminated and idx == len(lines) - 1):
            out.status, out.first_diff = "DIFFERS", {"i": idx, "field": "bytes"}      # L-LOOM-43: the same dict, other bytes
            return
        if row["actor"] == notelib.NOTE_ACTOR and row["op"] == notelib.NOTE_OP and row["args"].get("nv") != notelib.NOTES_VERSION:
            out.notes_stale.append(idx)
        run.advance(row)
        prev = row["sha"]
        if row["op"] == "emit" and row["result"].get("ok") and row["actor"] == "model":
            out.text = row["result"]["text"]
        if run.notes_due() and not (idx + 1 < len(rows) and rows[idx + 1].get("actor") == notelib.NOTE_ACTOR and rows[idx + 1].get("op") == notelib.NOTE_OP):
            if idx + 1 == len(rows):
                out.pending_note = True        # LOOM-notes (L-LOOM-105): the last row, a crash between two appends: the run is intact, the repair is the append
                return
            out.status, out.first_diff = "DIFFERS", {"i": idx + 1, "field": "note_missing"}      # mid-ledger: a read / emit with notes is followed by its row
            return


def verify(run_dir, head: Optional[str] = None, corpus_path: Optional[str] = None, loader: Loader = default_loader) -> dict:
    """The chain, then the replay.  The result has "status" (one of STATUSES) and, when the replay ran, a "replay" object."""
    chain = verify_chain(run_dir, head)
    if chain["status"] != "OK":
        return chain
    rep = replay(run_dir, corpus_path, loader)
    chain["replay"] = rep.to_obj()
    if rep.status == "INPUTS":
        chain["status"] = "REPLAY_INPUTS_MISMATCH"
    elif rep.status == "DIFFERS":
        chain["status"] = "REPLAY_DIFFERS"
    return chain


def emitted_output(run_dir, head: Optional[str] = None, corpus_path: Optional[str] = None, loader: Loader = default_loader) -> dict:
    """L4 (design 7.1): the output of a run is its successful `emit` row, and only if `verify` is OK.  Free text, lookups, reads and
    statuses are never output.  {"status": "emitted", text, output_sha} | {"status": "no_output"} | {"status": "run_not_verified", "verify": ...}."""
    v = verify(run_dir, head, corpus_path, loader)
    if v["status"] != "OK":
        return {"status": "run_not_verified", "verify": v["status"], "problems": v.get("problems", []), "replay": v.get("replay")}
    lines, _ = read_lines(run_dir)
    for ln in lines:
        r = json.loads(ln)
        if r["actor"] == "model" and r["op"] == "emit" and r["result"].get("ok") is True and r["result"].get("status") == "emitted":
            return {"status": "emitted", "text": r["result"]["text"], "output_sha": r["result"]["output_sha"]}
    return {"status": "no_output"}
