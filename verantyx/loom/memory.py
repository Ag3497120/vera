"""MEM-a: the memory store, the memory session and the `write` path (docs/LINE3_LOOM_MEMORY_DESIGN.md 3-4, 9.2; owner decisions OP-MEM-1/2/3 (a)).

The loom as the model's MEMORY, WORK LOG and CONTEXT EXTENSION, starting EMPTY: M0 = (the foundation, the rules, H = (), ledger = ()).  Everything else is derived from
H (the model's own sentences, in order) and the ledgers.  This is a NEW MODE next to the loom, behind an explicit door (`MemStore.begin`): no byte of an ordinary loom
run, ledger or corpus changes.  It reuses the loom's pieces unchanged: `Corpus` (built by `Corpus(...)` per write, never `Corpus.load`: L-MEM-15), `weave_span.v2`
(`ops.h_weave_span`, the whole sentence, WORD tier: L-MEM-04), `LoomState`, the ledger rows (`ledger.seal` / `Ledger` / `verify_chain`) and `read.stability_of`.

THE STORE (L-MEM-17; `--store DIR` is required, there is no default path)
  <store>/sessions/<run_id>/{ops.jsonl, HEAD, timing.jsonl, meta.json}   one loom-format ledger per session = THE WORK LOG (the single source of truth)
  <store>/memory.jsonl     DERIVED: the ok `write` rows of every listed session, in order, as corpus rows {kind, sent, source}; re-derived and checked at every `begin`
  <store>/HEAD             canonical JSON {store_id, kind_policy, sessions: [{run_id, session_no, head, rows, sentences_after}], sentences, memory_sha}
  <store>/.lock            flock: one open session per store (`store_locked`)
A session is one stacked document (the frozen-stack fold): `state(1..k+1) = session_{k+1}(state(1..k))`.  `begin` rebuilds the cumulative state from H by weaving every
earlier sentence in order against its own prefix corpus (`MemRun.carry`, the same code path as a live write), so a session starts from exactly the structure the
earlier ones left, and `mem replay` re-executes every session in order from an empty M0 and must reproduce every row byte for byte.

THE WRITE (L-MEM-03..05, 16, 18)
  1. text: NFC, 1..64 chars, no control character (`bad_sentence`); a secret-shaped text is refused `secret_shaped_sentence` and its row holds it redacted + sha.
  2. row = {sent, source "mem:<store>/<session>#<i>[:user]", kind base | memory_answer (OP-MEM-1)}; C_t = Corpus(H + row); no WORD unit -> `no_unit`.
  3. `weave_span.v2` of the whole sentence over C_t; a refusal (`span_inexpressible`: two case particles before one head, a gap that is not a particle) REFUSES the
     write and stores nothing in H (OP-MEM-3 (a)); the model rephrases.
  4. commit: H gains the row; the crosses are linked at the end of the cumulative thread and FROZEN (`memory_frozen`: unseat swap extend topic set_depth link unlink drop).
  5. provenance per unit: `history_n` = postings of the surface in C_<t, `origin` = new iff history_n == 0 (the model supplied a word the structure lacked).
  6. the notes (memnotes.py): REVERSAL / NEW_RELATION / UNANCHORED from the HISTORY KEY (C_<t only), CONFLICT touching this write, SAME_QUESTION through the pluggable
     `self_question` hook; they never block (L-MEM-09), travel in the result and in a `loom_note` row after the write row.
`recall` (the evidence gate over the memory) is MEM-c: its name is reserved and refused `recall_unavailable` until the gate is merged.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.ledger_events import GENESIS, args_sha256, redact, redact_obj
from verantyx.loom import ledger as lg
from verantyx.loom import memnotes as mn
from verantyx.loom import notes as notelib
from verantyx.loom import ops
from verantyx.loom import read as rd
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import (MEM_KINDS, STORE_ID_RX, check_memory_rows, make_source, parse_source)
from verantyx.loom.ops import Run, refusal
from verantyx.loom.state import ARG_STR_CAP, ARGS_CHARS_CAP, GUARD_CAPS, LoomState, Refuse, canonical, sha256_text

MEM_VERSION = "mem.v1"
MEM_TASK_ID = "memory"
KIND_POLICIES: Tuple[str, ...] = ("a", "b", "c")          # OP-MEM-1: a base in the memory space (chosen), b memory_answer (no adhesion), c a session's own sentences give no adhesion
ROLES: Tuple[str, ...] = ("model", "user")
CROSS_UNCAPPED = 1 << 30                                   # L-MEM-14: no cross cap across sessions (a session's writes are capped instead)
CAPS_MEM_V1: Dict[str, int] = {"writes": 60, "recalls": 60, "lookups": 60, "ops": 300, "reads": 0, "emit_attempts": 0, "constructed": 0, "unit_chars": 8,
                               "max_L": 2, "crosses": CROSS_UNCAPPED, "max_depth": 0}
TOOLS: Tuple[str, ...] = ("write", "recall", "lookup", "read_sentence", "status", "commit")         # the memory session's tools (begin is the store's door)
FROZEN_OPS: Tuple[str, ...] = ("unseat", "swap", "extend", "topic", "set_depth", "link", "unlink", "drop")
OPS_CLASS: Tuple[str, ...] = ("write",) + FROZEN_OPS         # the calls the `ops` cap counts
MEM_RULES: Dict[str, Any] = {
    "output": "A memory session never emits: its only product is the sentences it writes. Plain text is discarded unread.",
    "write": "write(text, role) weaves the WHOLE sentence (WORD tier, weave_span.v2) into the memory. A sentence the structure cannot seat is refused and stores "
             "nothing: rephrase it. Shape: 「X の Y は A」 and short chains; two case particles before one head are refused.",
    "frozen": "Every cross a write made is frozen: " + " ".join(FROZEN_OPS) + " -> memory_frozen. add / open_cross / seat / emit are not tools of a memory session.",
    "history": "A write is judged against the sentences BEFORE it, never against itself (REVERSAL / NEW_RELATION / UNANCHORED); notes never block.",
    "recall": "reserved (MEM-c): recall_unavailable until the evidence gate is merged.",
    "close": "commit closes the session; an uncommitted session is not part of the memory.",
}
_MODEL_RX = re.compile(r"^[^\x00-\x1f\x7f]{1,64}$")
_RUN_RX = re.compile(r"^s[0-9]{4,}$")
STORE_FILES = ("sessions", "memory.jsonl", "HEAD", ".lock")


# ------------------------------------------------------------------------------------------------------------
# H as bytes
# ------------------------------------------------------------------------------------------------------------
def row_line(row: dict) -> str:
    return canonical({"kind": row.get("kind", "base"), "sent": row["sent"], "source": row["source"]}) + "\n"


def rows_bytes(rows: Sequence[dict]) -> bytes:
    return "".join(row_line(r) for r in rows).encode("utf-8")


def mem_sha(rows: Sequence[dict]) -> str:
    return hashlib.sha256(rows_bytes(rows)).hexdigest()


def build_corpus(rows: Sequence[dict]) -> Corpus:
    """The memory corpus of H[0..n-1]: `Corpus(...)` over the canonical bytes (never `Corpus.load`: its process-wide cache would hold every prefix, L-MEM-15), after the
    memory guard (every row a `mem:` row)."""
    check_memory_rows(rows)
    return Corpus(rows_bytes(rows))


def kind_of(kind_policy: str) -> str:
    return "memory_answer" if kind_policy == "b" else "base"


def _key_rows(rows: Sequence[dict], kind_policy: str, session_no: int) -> Sequence[dict]:
    """The history as the KEY reads it.  OP-MEM-1 (c): the rows of the CURRENT session are relabelled `memory_answer`, so they give no adhesion (the adhesion of a
    session counts only the sentences of earlier sessions); (a)/(b): as stored."""
    if kind_policy != "c":
        return rows
    out = []
    for r in rows:
        p = parse_source(r["source"])
        out.append(dict(r, kind="memory_answer") if p is not None and p[1] == session_no else r)
    return out


def head_obj(store_id: str, kind_policy: str, sessions: Sequence[dict], rows: Sequence[dict]) -> dict:
    return {"v": 1, "mem_version": MEM_VERSION, "store_id": store_id, "kind_policy": kind_policy, "sessions": [dict(s) for s in sessions],
            "sentences": len(rows), "memory_sha": mem_sha(rows)}


def head_sha(obj: Optional[dict]) -> str:
    return GENESIS if obj is None else sha256_text(canonical(obj))


# ------------------------------------------------------------------------------------------------------------
# the memory run
# ------------------------------------------------------------------------------------------------------------
class MemRun(Run):
    """A loom `Run` whose corpus GROWS: the memory space.  The cumulative `LoomState` (units, crosses, one thread) is carried from the earlier sessions by
    `carry`; counters and guards are the session's own.  Ops: `write` `lookup` `read_sentence` `status` `commit` (+ `recall`, reserved) and the frozen ops, which
    only refuse; every other loom op is `unknown_tool`.  Never emits."""

    def __init__(self, store_id: str, session_no: int, run_id: str, model: str, *, store_head_before: str = GENESIS, kind_policy: str = "a",
                 contradiction_policy: str = "a", unseatable_policy: str = "a", self_question: Optional[mn.SelfQuestionFn] = None) -> None:
        if kind_policy not in KIND_POLICIES:
            raise Refuse("bad_policy", {"policy": "kind", "value": kind_policy, "allowed": list(KIND_POLICIES)})
        if contradiction_policy not in mn.CONTRADICTION_POLICIES:
            raise Refuse("bad_policy", {"policy": "contradiction", "value": contradiction_policy, "allowed": list(mn.CONTRADICTION_POLICIES)})
        if unseatable_policy not in mn.UNSEATABLE_POLICIES:
            raise Refuse("policy_not_built", {"policy": "unseatable", "value": unseatable_policy, "built": list(mn.UNSEATABLE_POLICIES),
                                              "reason": "OP-MEM-3 (c), store verbatim with only the expressible stretches seated, is not built (the owner chose (a))"})
        if not STORE_ID_RX.match(store_id):
            raise Refuse("bad_store_id", {"store_id": store_id[:32]})
        task = {"task_id": MEM_TASK_ID, "text": "memory session", "lang": "prose", "mode": "record_only", "tiers": ["WORD"]}
        super().__init__(Corpus(b""), task, model, run_id, "report", None, None, "notes.v1")
        self.caps = dict(CAPS_MEM_V1)
        self.store_id, self.session_no = store_id, session_no
        self.store_head_before = store_head_before
        self.kind_policy, self.contradiction_policy, self.unseatable_policy = kind_policy, contradiction_policy, unseatable_policy
        self.hook = self_question
        self.hook_id = mn.hook_id(self_question)
        self.rows: List[dict] = []                     # H: the memory rows (earlier sessions + this one)
        self.rows0 = 0                                 # |H| when the session began
        self.corpus_cur: Corpus = self.corpus          # C over the whole of H (self.corpus is C_t only while a weave runs)
        self.session_written = 0                       # ok writes of this session (the `#i` of the source)
        self.counts: Dict[str, int] = {"writes": 0, "recalls": 0}
        self.tally: Dict[str, Any] = {"notes": {t: 0 for t in mn.NOTE_TYPES}, "refused": {}}
        self._pending: List[dict] = []
        self._begin_header: Optional[dict] = None

    # -- the carried state (the frozen-stack fold) ------------------------------------------------------------------
    def carry(self, rows: Sequence[dict]) -> None:
        """Weave every earlier sentence, in order, against its own prefix corpus: the cumulative state of the sessions before (a pure function of H).  The same code
        path as a live write minus the notes; a row that no longer weaves means the store is not what it says (`store_unverified`)."""
        rows = list(rows)
        prev = Corpus(b"")
        for t in range(len(rows)):
            c_t = build_corpus(rows[:t + 1])
            try:
                self._weave_row(t, prev, c_t)
            except Refuse as r:
                raise Refuse("store_unverified", {"reason": "carried_sentence_does_not_weave", "sid": t, "refusal": r.type})
            prev = c_t
        self.rows = rows
        self.rows0 = len(rows)
        self.corpus = self.corpus_cur = prev
        self._begin_header = None

    def _weave_row(self, t: int, c_before: Corpus, c_t: Corpus) -> dict:
        units = c_t.tier("WORD").sentence_units[t]
        if not units:
            raise Refuse("no_unit", {})
        self.corpus = c_t
        try:
            wv = ops.h_weave_span(self, {"sid": t, "tier": "WORD", "from": 0, "to": len(units) - 1}, self.i)
        finally:
            self.corpus = self.corpus_cur
        for c in wv["crosses"]:                                          # sentence order: the arm unit, then the centre (L-MEM-16)
            for uid in [s["uid"] for s in c["seated"]] + [c["centre"]["uid"]]:
                u = self.state.units[uid]
                hist = len(c_before.postings("WORD", u.surface) or ())
                u.prov["history_n"] = hist
                u.prov["origin"] = "record" if hist else "new"
        return wv

    # -- header / begin -------------------------------------------------------------------------------------------------
    def header(self) -> dict:
        if self._begin_header is None:
            h = super().header()
            h.update({"mem_version": MEM_VERSION, "store_id": self.store_id, "session_no": self.session_no, "store_head_before": self.store_head_before,
                      "memory_sha_before": mem_sha(self.rows), "sessions_before": self.session_no - 1, "sentences_before": len(self.rows),
                      "evidence_version": None, "notes_profile": mn.MEM_NOTES_VERSION, "caps": MEM_VERSION, "kind_policy": self.kind_policy,
                      "contradiction_policy": self.contradiction_policy, "unseatable_policy": self.unseatable_policy, "self_question": self.hook_id})
            self._begin_header = h
        return self._begin_header

    def begin_body(self) -> dict:
        res = {"ok": True, "run_id": self.run_id, "mode": "memory", "task": ops.task_view(self.task, self.caps), "rules": MEM_RULES, "header": self.header()}
        return {"actor": "model", "op": "begin", "args": {"task_id": self.task["task_id"], "model": self.model}, "result": res, "state_sha": self.mem_state_sha()}

    def mem_state_sha(self) -> str:
        """The state after a row: the loom state (units, crosses, thread, counters, guards) + the memory (|H|, its sha, the write / recall counts)."""
        return sha256_text(canonical({"loom": self.state.to_obj(), "mem": {"sentences": len(self.rows), "memory_sha": mem_sha(self.rows),
                                                                           "writes": self.counts["writes"], "recalls": self.counts["recalls"]}}))

    # -- one call = one body ---------------------------------------------------------------------------------------------
    def notes_due(self) -> List[dict]:
        if self._prev != ("model", "write", True):
            return []
        return list(self._pending)

    def _executable(self, op: Any) -> bool:
        return isinstance(op, str) and (op in TOOLS or op in FROZEN_OPS)

    def _precheck(self, op: str) -> None:
        st = self.state
        if st.closed is not None:
            st.guards["closed_calls"] += 1
            raise Refuse("run_closed", {"closed": list(st.closed)})
        if op == "write" and self.counts["writes"] >= self.caps["writes"]:
            raise Refuse("write_cap", {"limit": self.caps["writes"]})
        if op == "recall" and self.counts["recalls"] >= self.caps["recalls"]:
            raise Refuse("recall_cap", {"limit": self.caps["recalls"]})
        if op in OPS_CLASS and st.counters["ops"] >= self.caps["ops"]:
            raise Refuse("ops_cap", {"limit": self.caps["ops"]})
        if op in ("lookup", "read_sentence") and st.counters["lookups"] >= self.caps["lookups"]:
            raise Refuse("lookup_cap", {"limit": self.caps["lookups"]})
        if op == "write":
            self.counts["writes"] += 1
        if op == "recall":
            self.counts["recalls"] += 1
        if op in OPS_CLASS:
            st.counters["ops"] += 1
        if op in ("lookup", "read_sentence"):
            st.counters["lookups"] += 1

    def _model_step(self, op: str, args: dict, replay_extra: Optional[dict]) -> dict:
        self._pending = []
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
        elif blocked is not None or ops._oversize(args):
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
            if not self._executable(op):
                raise Refuse("unknown_tool", {"tool": op if isinstance(op, str) else None, "reason": "not a tool of a memory session"})
            self._precheck(op)
            if trunc:
                raise Refuse("args_too_large", {"chars": extra["args_chars"], "limit": ARGS_CHARS_CAP, "string_limit": ARG_STR_CAP})
            if n:
                raise Refuse("secret_shaped_sentence" if op == "write" else "secret_shaped_unit", {"redacted": n})
            result = _HANDLERS[op](self, args, self.i)
        except Refuse as r:
            result = refusal(r.type, r.detail)
            if op == "write":
                self.tally["refused"][r.type] = self.tally["refused"].get(r.type, 0) + 1
        body = {"actor": "model", "op": op, "args": stored, "result": result, "state_sha": self.mem_state_sha()}
        body.update(extra)
        return body

    def _outside_step(self, actor: str, op: str, args: dict) -> dict:
        if actor == notelib.NOTE_ACTOR:
            if op != notelib.NOTE_OP:
                raise ValueError("op %r is not a row of actor %r" % (op, actor))
            notes = self.notes_due()
            if not notes:
                raise ValueError("note: no notes are due after the previous row")
            return {"actor": actor, "op": op, "args": {"after": self.i - 1, "of": "write", "notes": notes, "nv": mn.MEM_NOTES_VERSION},
                    "result": {"ok": True}, "state_sha": self.mem_state_sha()}
        body = super()._outside_step(actor, op, args)
        body["state_sha"] = self.mem_state_sha()
        return body


# ------------------------------------------------------------------------------------------------------------
# handlers
# ------------------------------------------------------------------------------------------------------------
def _marked(wv_crosses: Sequence[dict], new_uids: set) -> str:
    """The sentence as the structure read it back, a word the model supplied marked 【新:…】 (L-MEM-16)."""
    out = []
    for c in wv_crosses:
        for s in c["seated"]:
            out.append(("【新:%s】" % s["surface"] if s["uid"] in new_uids else s["surface"]) + s["particle"])
        cs = c["centre"]
        out.append("【新:%s】" % cs["surface"] if cs["uid"] in new_uids else cs["surface"])
        if c["topic"]:
            out.append("は")
    return "".join(out)


def h_write(run: MemRun, a: dict, i: int) -> dict:
    a = ops._args(a, {"text": (str, True), "role": (str, False)})
    role = a.get("role", "model")
    if role not in ROLES:
        raise Refuse("bad_args", {"field": "role", "reason": "one of %s" % (list(ROLES),)})
    text = unicodedata.normalize("NFC", a["text"])
    if not 1 <= len(text) <= ARG_STR_CAP or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in text):
        raise Refuse("bad_sentence", {"reason": "1 to %d characters, no newline / NUL / control character" % ARG_STR_CAP})
    t = len(run.rows)
    row = {"kind": kind_of(run.kind_policy), "sent": text, "source": make_source(run.store_id, run.session_no, run.session_written, role)}
    rows_after = run.rows + [row]
    c_before = run.corpus_cur
    c_t = build_corpus(rows_after)
    wv = run._weave_row(t, c_before, c_t)                              # a Refuse here changes nothing (weave_span refuses before it touches the state)
    # -- committed from here on: H gains the row, the crosses are linked (by the weave) and frozen ----------------------------------------------------
    rows_before = run.rows
    run.rows = rows_after
    run.corpus_cur = run.corpus = c_t
    run.session_written += 1
    st = run.state
    new_crosses = [st.crosses[c["cid"]] for c in wv["crosses"]]
    linked = [st.crosses[cid] for cid in st.thread]
    c_key = c_before if run.kind_policy != "c" else build_corpus(_key_rows(rows_before, "c", run.session_no))
    notes, extra = mn.compute_write_notes(t=t, row=row, rows_before=rows_before, rows_after=rows_after, corpus_key=c_key, corpus_before=c_before, corpus_after=c_t,
                                          state=st, linked=linked, new_crosses=new_crosses, weave=wv, contradiction_policy=run.contradiction_policy,
                                          self_question=run.hook)
    run._pending = notes
    for n in notes:
        run.tally["notes"][n["type"]] += 1
    units: List[dict] = []
    new_uids = set()
    for c in wv["crosses"]:
        for s in c["seated"]:
            units.append({"uid": s["uid"], "surface": s["surface"], "cid": c["cid"], "seat": s["seat"]})
        units.append({"uid": c["centre"]["uid"], "surface": c["centre"]["surface"], "cid": c["cid"], "seat": "centre"})
    for u in units:
        pv = st.units[u["uid"]].prov
        u["origin"], u["history_n"] = pv["origin"], pv["history_n"]
        if pv["origin"] == "new":
            new_uids.add(u["uid"])
    read_back = "".join(sg["s"] for cr in new_crosses for sg in rd.read_prose(st, cr))
    res = {"ok": True, "sid": t, "source": row["source"], "kind": row["kind"], "role": role, "text": text, "tier": "WORD", "from": wv["from"], "to": wv["to"],
           "crosses": wv["crosses"], "units": units, "readback": {"text": read_back, "same": read_back == wv["text"]}, "marked": _marked(wv["crosses"], new_uids),
           "history": {"sentences": t, "corpus_sha": c_key.corpus_sha}, "keys": extra["keys"], "clause": extra["clause"], "thread_length": len(st.thread)}
    if notes:
        res["notes"] = notes
    return res


def h_recall(run: MemRun, a: dict, i: int) -> dict:
    ops._args(a, {"question": (str, True)})
    raise Refuse("recall_unavailable", {"ticket": "MEM-c", "reason": "the evidence gate is not merged into line3; recall over the memory is MEM-c"})


def h_lookup(run: MemRun, a: dict, i: int) -> dict:
    return ops.h_lookup(run, a, i)


def h_read_sentence(run: MemRun, a: dict, i: int) -> dict:
    return ops.h_read_sentence(run, a, i)


def h_status(run: MemRun, a: dict, i: int) -> dict:
    ops._args(a, {})
    st = run.state
    return {"ok": True, "run_id": run.run_id, "store_id": run.store_id, "session_no": run.session_no, "closed": None if st.closed is None else list(st.closed),
            "sentences_before": run.rows0, "sentences": len(run.rows), "written": run.session_written, "units": len(st.units), "crosses": len(st.crosses),
            "thread_length": len(st.thread), "counters": dict(st.counters), "writes": run.counts["writes"], "recalls": run.counts["recalls"],
            "caps": dict(run.caps), "notes": dict(run.tally["notes"]), "refused_writes": dict(sorted(run.tally["refused"].items())), "guards": dict(st.guards),
            "memory_sha": mem_sha(run.rows), "ledger_head": run.head}


def h_commit(run: MemRun, a: dict, i: int) -> dict:
    ops._args(a, {})
    sha = mem_sha(run.rows)
    run.state.closed = ["committed", sha]
    return {"ok": True, "status": "committed", "memory_sha": sha, "sentences": len(run.rows), "new_sentences": len(run.rows) - run.rows0,
            "session_no": run.session_no, "sessions_after": run.session_no}


def _frozen_handler(op: str):
    def h(run: MemRun, a: dict, i: int) -> dict:
        cid = a.get("cid") if isinstance(a, dict) else None
        if not isinstance(cid, str):
            raise Refuse("bad_args", {"field": "cid", "reason": "missing"})
        if cid not in run.state.crosses:
            raise Refuse("unknown_cid", {"cid": cid[:32]})
        raise Refuse("memory_frozen", {"cid": cid, "op": op, "reason": "a cross a write made is frozen"})
    return h


_HANDLERS = {"write": h_write, "recall": h_recall, "lookup": h_lookup, "read_sentence": h_read_sentence, "status": h_status, "commit": h_commit}
_HANDLERS.update({op: _frozen_handler(op) for op in FROZEN_OPS})


# ------------------------------------------------------------------------------------------------------------
# the store
# ------------------------------------------------------------------------------------------------------------
def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.parent / (".%s.%d.tmp" % (path.name, os.getpid()))
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def session_memory_rows(run_dir) -> Tuple[List[dict], bool, Optional[dict]]:
    """(the memory rows the ok `write` rows of a session ledger made, whether the ledger ends with an ok `commit`, its begin result)."""
    lines, _ = lg.read_raw_lines(run_dir)
    out: List[dict] = []
    committed = False
    begin: Optional[dict] = None
    for k, ln in enumerate(lines):
        r = lg._parse_line(ln)
        if k == 0:
            begin = r.get("result")
        if r["actor"] == "model" and r["op"] == "write" and r["result"].get("ok") is True:
            res = r["result"]
            out.append({"kind": res["kind"], "sent": res["text"], "source": res["source"]})
        committed = (k == len(lines) - 1 and r["actor"] == "model" and r["op"] == "commit" and r["result"].get("ok") is True)
    return out, committed, begin


class MemStore:
    """A memory store on disk (`--store DIR`, required).  One memory per store; two stores never merge (L-MEM-01)."""

    def __init__(self, path, store_id: Optional[str] = None) -> None:
        if path is None or str(path) == "":
            raise ValueError("a memory store needs an explicit directory (--store DIR): there is no default path (L-MEM-17)")
        self.path = Path(path)
        self.sessions_dir = self.path / "sessions"
        self.memory_path = self.path / "memory.jsonl"
        self.head_path = self.path / "HEAD"
        self.lock_path = self.path / ".lock"
        head = self._read_head()
        if head is not None:
            if store_id is not None and store_id != head["store_id"]:
                raise ValueError("this store is %r, not %r" % (head["store_id"], store_id))
            store_id = head["store_id"]
        if store_id is None:
            store_id = re.sub(r"[^A-Za-z0-9._-]", "-", self.path.name or "mem").lstrip("._-")[:32] or "mem"
        if not STORE_ID_RX.match(store_id):
            raise ValueError("store_id: 1..32 characters of [A-Za-z0-9._-], starting with a letter or digit")
        self.store_id = store_id

    # -- HEAD / verification ------------------------------------------------------------------------------------------
    def _read_head(self) -> Optional[dict]:
        if not self.head_path.exists():
            return None
        try:
            h = json.loads(self.head_path.read_text(encoding="utf-8"))
            if not (isinstance(h, dict) and h.get("mem_version") == MEM_VERSION and STORE_ID_RX.match(h["store_id"]) and isinstance(h["sessions"], list)
                    and h["kind_policy"] in KIND_POLICIES):
                raise ValueError("shape")
            return h
        except (ValueError, KeyError, TypeError):
            raise Refuse("store_unverified", {"reason": "head_unreadable"})

    def head(self) -> Optional[dict]:
        return self._read_head()

    def check(self) -> Tuple[Optional[dict], List[dict]]:
        """The cheap verification of `begin` (the full one, with the replay, is `verify`): every listed session's chain is intact and ends with a commit, the memory
        rows derived from the ledgers are exactly memory.jsonl and the HEAD's sha.  -> (HEAD or None, H).  `store_unverified` otherwise."""
        head = self._read_head()
        on_disk = self.memory_path.read_bytes() if self.memory_path.exists() else b""
        if head is None:
            if on_disk:
                raise Refuse("store_unverified", {"reason": "memory_without_head"})
            return None, []
        rows: List[dict] = []
        for e in head["sessions"]:
            d = self.sessions_dir / e["run_id"]
            if not _RUN_RX.match(e["run_id"]) or not (d / "ops.jsonl").exists():
                raise Refuse("store_unverified", {"reason": "session_missing", "run_id": e["run_id"]})
            vc = lg.verify_chain(d, e["head"])
            if vc["status"] != "OK" or vc["n"] != e["rows"]:
                raise Refuse("store_unverified", {"reason": "chain", "run_id": e["run_id"], "status": vc["status"]})
            mrows, committed, _ = session_memory_rows(d)
            if not committed:
                raise Refuse("store_unverified", {"reason": "session_not_committed", "run_id": e["run_id"]})
            rows.extend(mrows)
            if len(rows) != e["sentences_after"]:
                raise Refuse("store_unverified", {"reason": "sentence_count", "run_id": e["run_id"]})
        if head["memory_sha"] != mem_sha(rows) or head["sentences"] != len(rows) or on_disk != rows_bytes(rows):
            raise Refuse("store_unverified", {"reason": "memory_jsonl_differs_from_the_ledgers"})
        return head, rows

    def rows(self) -> List[dict]:
        return self.check()[1]

    def _write_state(self, sessions: Sequence[dict], rows: Sequence[dict], kind_policy: str) -> dict:
        _atomic_write(self.memory_path, rows_bytes(rows))
        h = head_obj(self.store_id, kind_policy, sessions, rows)
        _atomic_write(self.head_path, (canonical(h) + "\n").encode("utf-8"))
        return h

    def _adopt_pending(self, head: Optional[dict], rows: List[dict]) -> Tuple[Optional[dict], List[dict]]:
        """A crash between the `commit` row and the HEAD write leaves a session that is complete but not listed.  If the next unlisted session is intact, ends with its
        commit, and began from this very HEAD, the commit is finished (memory.jsonl and HEAD are written); anything else is left alone (an abandoned session is not memory)."""
        if not self.sessions_dir.exists():
            return head, rows
        listed = {e["run_id"] for e in (head["sessions"] if head else [])}
        for name in sorted(os.listdir(self.sessions_dir)):
            if name in listed or not _RUN_RX.match(name):
                continue
            d = self.sessions_dir / name
            vc = lg.verify_chain(d)
            if vc["status"] != "OK":
                continue
            mrows, committed, begin = session_memory_rows(d)
            hdr = (begin or {}).get("header", {})
            n_sess = len(head["sessions"]) if head else 0
            if not committed or hdr.get("session_no") != n_sess + 1 or hdr.get("store_head_before") != head_sha(head) or hdr.get("store_id") != self.store_id:
                continue
            lines, _ = lg.read_raw_lines(d)
            last = lg._parse_line(lines[-1])
            new_rows = rows + mrows
            if last["result"].get("memory_sha") != mem_sha(new_rows):
                continue
            entry = {"run_id": name, "session_no": n_sess + 1, "head": last["sha"], "rows": len(lines), "sentences_after": len(new_rows)}
            head = self._write_state((head["sessions"] if head else []) + [entry], new_rows, hdr["kind_policy"])
            rows = new_rows
        return head, rows

    # -- sessions -----------------------------------------------------------------------------------------------------
    def begin(self, model: str, *, kind_policy: Optional[str] = None, contradiction_policy: str = "a", unseatable_policy: str = "a",
              self_question: Optional[mn.SelfQuestionFn] = None) -> "MemSession":
        """Open a memory session: the store's lock, the cheap verification, the carried state, the `begin` row (L-MEM-18).  Raises `Refuse` (store_locked,
        store_unverified, bad_model_id, policy_mismatch, ...).  The defaults are the owner's choices: OP-MEM-1 (a), OP-MEM-2 (a), OP-MEM-3 (a)."""
        if not isinstance(model, str) or not _MODEL_RX.match(model) or redact(model)[1]:
            raise Refuse("bad_model_id", {"reason": "1 to 64 printable characters, no secret-shaped text"})
        self.path.mkdir(parents=True, exist_ok=True)
        fd_ = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd_, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd_)
            raise Refuse("store_locked", {"store": self.store_id})
        try:
            head, rows = self.check()
            head, rows = self._adopt_pending(head, rows)
            policy = kind_policy if kind_policy is not None else (head["kind_policy"] if head else "a")
            if head is not None and policy != head["kind_policy"]:
                raise Refuse("policy_mismatch", {"policy": "kind", "store": head["kind_policy"], "asked": policy})
            n_sess = len(head["sessions"]) if head else 0
            k = n_sess + 1
            while (self.sessions_dir / ("s%04d" % k)).exists():          # an abandoned (never committed) session keeps its folder; the next one takes the next number
                k += 1
            run_id = "s%04d" % k
            run = MemRun(self.store_id, n_sess + 1, run_id, model, store_head_before=head_sha(head), kind_policy=policy,
                         contradiction_policy=contradiction_policy, unseatable_policy=unseatable_policy, self_question=self_question)
            run.carry(rows)
            led = lg.Ledger(self.sessions_dir / run_id)
            led.create({"store": self.store_id, "mode": "memory", "session_no": n_sess + 1})
            with led.locked() as lk:
                row = lk.append(run.begin_body(), 0)
                run.advance(row)
            return MemSession(self, run, led, fd_)
        except BaseException:
            fcntl.flock(fd_, fcntl.LOCK_UN)
            os.close(fd_)
            raise

    def _finalize(self, sess: "MemSession") -> dict:
        run = sess.run
        head = self._read_head()
        sessions = list(head["sessions"]) if head else []
        sessions.append({"run_id": run.run_id, "session_no": run.session_no, "head": run.head, "rows": run.i, "sentences_after": len(run.rows)})
        return self._write_state(sessions, run.rows, run.kind_policy)

    def verify(self, self_question: Optional[mn.SelfQuestionFn] = None) -> dict:
        return verify_store(self.path, self_question)

    def replay(self, self_question: Optional[mn.SelfQuestionFn] = None) -> "MemReplay":
        return replay_store(self.path, self_question)


class MemSession:
    """An open memory session: the door.  `call(tool, args)` executes one op, appends exactly one ledger row (a refused call too) and, when the write has notes, the
    `loom_note` row right after it.  The store's lock is held until `commit` or `close`."""

    def __init__(self, store: MemStore, run: MemRun, led: lg.Ledger, lock_fd: int) -> None:
        self.store, self.run, self.ledger = store, run, led
        self._fd: Optional[int] = lock_fd
        self.t0 = time.monotonic_ns()
        self.committed = False

    @property
    def run_id(self) -> str:
        return self.run.run_id

    def call(self, tool: Any, args: Any = None) -> dict:
        if self._fd is None:
            raise RuntimeError("the session is closed")
        args = {} if args is None else args
        with self.ledger.locked() as lk:
            body = self.run.step("model", tool, args)
            row = lk.append(body, time.monotonic_ns() - self.t0)
            self.run.advance(row)
            if self.run.notes_due():
                nrow = lk.append(self.run.step(notelib.NOTE_ACTOR, notelib.NOTE_OP, {}), time.monotonic_ns() - self.t0)
                self.run.advance(nrow)
        res = body["result"]
        if tool == "commit" and res.get("ok") is True:
            self.store._finalize(self)
            self.committed = True
            self.close()
        return res

    def write(self, text: str, role: str = "model") -> dict:
        return self.call("write", {"text": text, "role": role} if role != "model" else {"text": text})

    def status(self) -> dict:
        return self.call("status", {})

    def commit(self) -> dict:
        return self.call("commit", {})

    def rows(self) -> List[dict]:
        """The ledger rows of this session so far (parsed)."""
        lines, _ = lg.read_raw_lines(self.ledger.dir)
        return [lg._parse_line(ln) for ln in lines]

    def events(self) -> dict:
        r = self.run
        return mn.session_events(self.rows(), r.contradiction_policy, r.unseatable_policy)

    def close(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    def __enter__(self) -> "MemSession":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


# ------------------------------------------------------------------------------------------------------------
# replay and verify: the chain of sessions
# ------------------------------------------------------------------------------------------------------------
class MemReplay:
    def __init__(self) -> None:
        self.status = "IDENTICAL"                 # IDENTICAL | DIFFERS | INPUTS
        self.mismatch: Optional[str] = None
        self.first_diff: Optional[dict] = None    # {"session", "i", "field"}
        self.sessions = 0
        self.rows = 0
        self.rows_h: List[dict] = []              # H as re-derived
        self.pending_note = False

    @property
    def identical(self) -> bool:
        return self.status == "IDENTICAL"

    def to_obj(self) -> dict:
        return {"status": self.status, "mismatch": self.mismatch, "first_diff": self.first_diff, "sessions": self.sessions, "rows": self.rows,
                "sentences": len(self.rows_h), "pending_note": self.pending_note}


_HEADER_OPT_KEYS = ("kind_policy", "contradiction_policy", "unseatable_policy")


def replay_store(path, self_question: Optional[mn.SelfQuestionFn] = None) -> MemReplay:
    """`mem replay`: re-execute every listed session, in order, against an empty M0 (each session starts from the H the earlier ones re-derived, not from
    memory.jsonl) and require every row, every byte, the HEAD and memory.jsonl to be reproduced.  `self_question` must be the hook the sessions were recorded
    with (its `id` is in the begin header; a mismatch is INPUTS `self_question_mismatch`)."""
    out = MemReplay()
    store = MemStore(path)
    try:
        head = store._read_head()
    except Refuse:
        out.status, out.first_diff = "DIFFERS", {"session": None, "i": None, "field": "head"}
        return out
    if head is None:
        if (store.sessions_dir.exists() and any(True for _ in os.scandir(store.sessions_dir))) and False:
            pass
        return out
    H: List[dict] = []
    sessions: List[dict] = []
    before = GENESIS
    for e in head["sessions"]:
        d = store.sessions_dir / e["run_id"]
        try:
            lines, unterminated = lg.read_raw_lines(d)
            rows = [lg._parse_line(ln) for ln in lines]
            r0 = rows[0]
            res0 = r0["result"]
            hdr = res0["header"]
            opts = {k: hdr[k] for k in _HEADER_OPT_KEYS}
            model, run_id = r0["args"]["model"], res0["run_id"]
        except Exception:
            out.status, out.first_diff = "DIFFERS", {"session": e["run_id"], "i": 0, "field": "result"}
            return out
        if r0.get("op") != "begin" or hdr.get("mem_version") != MEM_VERSION or hdr.get("caps") != MEM_VERSION or res0["task"].get("caps") != CAPS_MEM_V1:
            out.status, out.mismatch = "INPUTS", "mem_version_unknown"
            return out
        if hdr.get("self_question") != mn.hook_id(self_question):
            out.status, out.mismatch = "INPUTS", "self_question_mismatch"
            return out
        try:
            run = MemRun(hdr["store_id"], hdr["session_no"], run_id, model, store_head_before=before, self_question=self_question, **opts)
            run.carry(H)
        except Refuse:
            out.status, out.first_diff = "DIFFERS", {"session": e["run_id"], "i": 0, "field": "carry"}
            return out
        mm = lg.header_mismatch(hdr, run.header())
        if mm is None:
            for k in ("mem_version", "store_id", "session_no", "store_head_before", "memory_sha_before", "sessions_before", "sentences_before", "evidence_version",
                      "notes_profile", "caps", "kind_policy", "contradiction_policy", "unseatable_policy", "self_question", "stability_mode", "declared_model"):
                if hdr.get(k) != run.header().get(k):
                    mm = "header_" + k
                    break
        if mm is not None:
            out.status, out.mismatch = "INPUTS", mm
            return out
        if _replay_rows(out, run, e["run_id"], rows, lines, unterminated) is False:
            return out
        if not rows or rows[-1]["op"] != "commit" or rows[-1]["result"].get("ok") is not True:
            out.status, out.first_diff = "DIFFERS", {"session": e["run_id"], "i": len(rows) - 1, "field": "commit_missing"}
            return out
        H = list(run.rows)
        ent = {"run_id": e["run_id"], "session_no": run.session_no, "head": rows[-1]["sha"], "rows": len(rows), "sentences_after": len(H)}
        if ent != e:
            out.status, out.first_diff = "DIFFERS", {"session": e["run_id"], "i": None, "field": "head_entry"}
            return out
        sessions.append(ent)
        before = head_sha(head_obj(hdr["store_id"], hdr["kind_policy"], sessions, H))
        out.sessions += 1
        out.rows += len(rows)
    out.rows_h = H
    on_disk = store.memory_path.read_bytes() if store.memory_path.exists() else b""
    if on_disk != rows_bytes(H):
        out.status, out.first_diff = "DIFFERS", {"session": None, "i": None, "field": "memory_jsonl"}
    elif head != head_obj(head["store_id"], head["kind_policy"], sessions, H):
        out.status, out.first_diff = "DIFFERS", {"session": None, "i": None, "field": "head"}
    return out


def _replay_rows(out: MemReplay, run: MemRun, run_id: str, rows: List[dict], lines: List[bytes], unterminated: bool) -> bool:
    prev = GENESIS
    for idx, orig in enumerate(rows):
        try:
            if idx == 0:
                body = run.begin_body()
            else:
                red = {k: orig[k] for k in lg.EXTRA_FIELDS if k in orig} or None
                body = run.step(orig["actor"], orig["op"], orig["args"], red)
            row = lg.seal(idx, prev, body)
        except Exception:
            out.status, out.first_diff = "DIFFERS", {"session": run_id, "i": idx, "field": "exception"}
            return False
        if row != orig:
            out.status, out.first_diff = "DIFFERS", {"session": run_id, "i": idx, "field": lg._first_diff(orig, row)}
            return False
        if lg.line_of(row) != lines[idx] + b"\n" or (unterminated and idx == len(lines) - 1):
            out.status, out.first_diff = "DIFFERS", {"session": run_id, "i": idx, "field": "bytes"}
            return False
        run.advance(row)
        prev = row["sha"]
        if run.notes_due() and not (idx + 1 < len(rows) and rows[idx + 1].get("actor") == notelib.NOTE_ACTOR and rows[idx + 1].get("op") == notelib.NOTE_OP):
            if idx + 1 == len(rows):
                out.pending_note = True
                return True
            out.status, out.first_diff = "DIFFERS", {"session": run_id, "i": idx + 1, "field": "note_missing"}
            return False
    return True


def verify_store(path, self_question: Optional[mn.SelfQuestionFn] = None) -> dict:
    """`mem verify`: every listed session's chain (TAMPERED), the derived memory against memory.jsonl and the HEAD (STORE_UNVERIFIED), then the replay
    (REPLAY_DIFFERS / REPLAY_INPUTS_MISMATCH).  {"status": "OK" | "EMPTY" | ..., ...}"""
    store = MemStore(path)
    try:
        head = store._read_head()
    except Refuse as r:
        return {"status": "STORE_UNVERIFIED", "problems": [{"type": r.type, **r.detail}]}
    if head is None:
        return {"status": "EMPTY" if not store.memory_path.exists() or not store.memory_path.read_bytes() else "STORE_UNVERIFIED", "sessions": 0, "sentences": 0}
    for e in head["sessions"]:
        d = store.sessions_dir / e["run_id"]
        if not (d / "ops.jsonl").exists():
            return {"status": "STORE_UNVERIFIED", "problems": [{"type": "session_missing", "run_id": e["run_id"]}]}
        vc = lg.verify_chain(d, e["head"])
        if vc["status"] != "OK":
            return {"status": vc["status"] if vc["status"] in ("TAMPERED", "TORN_TAIL") else "TAMPERED", "run_id": e["run_id"], "problems": vc["problems"]}
    try:
        store.check()
    except Refuse as r:
        return {"status": "STORE_UNVERIFIED", "problems": [{"type": r.type, **r.detail}]}
    rep = replay_store(path, self_question)
    res = {"status": "OK", "sessions": len(head["sessions"]), "sentences": head["sentences"], "replay": rep.to_obj()}
    if rep.status == "INPUTS":
        res["status"] = "REPLAY_INPUTS_MISMATCH"
    elif rep.status == "DIFFERS":
        res["status"] = "REPLAY_DIFFERS"
    return res


def store_events(path, contradiction_policy: str = "a", unseatable_policy: str = "a") -> dict:
    """session_events over every listed session of a store, keyed by run_id (the work log read as a meter would)."""
    store = MemStore(path)
    head = store._read_head()
    out = {}
    for e in (head["sessions"] if head else []):
        lines, _ = lg.read_raw_lines(store.sessions_dir / e["run_id"])
        out[e["run_id"]] = mn.session_events([lg._parse_line(ln) for ln in lines], contradiction_policy, unseatable_policy)
    return out


# ------------------------------------------------------------------------------------------------------------
# CLI:  python -m verantyx.loom.memory {verify,replay,status,events} --store DIR
# ------------------------------------------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m verantyx.loom.memory", description="the memory store of the loom (MEM-a)")
    ap.add_argument("cmd", choices=("verify", "replay", "status", "events"))
    ap.add_argument("--store", required=True, help="the store directory (required; there is no default path)")
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    if ns.cmd == "verify":
        res = verify_store(ns.store)
        code = 0 if res["status"] in ("OK", "EMPTY") else 1
    elif ns.cmd == "replay":
        res = replay_store(ns.store).to_obj()
        code = {"IDENTICAL": 0, "DIFFERS": 1, "INPUTS": 2}[res["status"]]
    elif ns.cmd == "events":
        res, code = store_events(ns.store), 0
    else:
        h = MemStore(ns.store).head()
        res, code = ({"sessions": 0, "sentences": 0} if h is None else {"store_id": h["store_id"], "sessions": len(h["sessions"]), "sentences": h["sentences"],
                                                                          "memory_sha": h["memory_sha"], "kind_policy": h["kind_policy"]}), 0
    print(json.dumps(res, sort_keys=True, ensure_ascii=False, indent=1))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
