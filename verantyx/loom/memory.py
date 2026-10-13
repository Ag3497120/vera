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
`recall` (MEM-c, memrecall.py): the evidence gate over the whole memory, verdicts ANSWER / CHOICE / NONE; available in a session whose begin row records an
evidence version (the gate hook `gate.evidence.v2`), otherwise refused `recall_unavailable` exactly as before (so every MEM-a/b ledger replays unchanged).
THE HOOK (MEM-c, L-MEM-29): `begin(self_question=DEFAULT)` -- DEFAULT is the gate hook for a new store; `None` = no hook; `StubSelfQuestion()` keeps the stub for tests.
MEM-c2: DEFAULT is now `gate.evidence.v2+subject` (the gate + the whole-subject guard); stores written with `gate.evidence.v2` replay with `FROM_HEADER` / `GateSelfQuestion()`.
MEM-d (owner 2026-10-13, 「記憶の計器の前の決定」): the PROFILE `mem.v2` of a session (`begin(profile=PROFILE_V2)`, recorded as `header.mem_profile`; a session without it is `mem.v1`
and replays exactly as before): the rules text guides the model to write 「X の Y は A」 (a sentence that does not seat is refused and the model rewrites; the rewrites are a cost
column, `memnotes.op_counts`), `declare_topic(text)` (a subject-less sentence is stored as 「<topic>の…」 and self-questioned with it; the expansion is in the row), `supersede`
(the model resolves a contested group explicitly; recall answers with the newest and lists the old as history, nothing is deleted) and `report` (what the model noticed in a
turn, mechanically).  The structure, the gate and the clause cut are not changed: the expanded sentence is an ordinary sentence of the memory.
MEM-fix (owner 2026-10-13 「不具合を直し、長い物語で測る」, L-MEM-57..): the PROFILE `mem.v3` = mem.v2 + the topic rule `topic.v2` (a topic is put in front of a clause only if it truly has no
subject: never twice, never before a subject of its own; a topic holding a particle is refused; a sentence with its own subject whose clause starts inside a token is asked from the start
of that token: `clause_at`), REVERSAL notes that cite the two sentences (notes `mem.v2`), the harness rows `report_forced` / `report_missing`, and the long-story caps `CAPS_MEM_V3`.  Every
older session replays under the profile its header records.
PUB-M2..M4 (owner 2026-10-13, OP-PUB-1..8; docs/LINE3_PUBLIC_DESIGN.md 4): the PROFILE `mem.v4` = mem.v3 + (a) WRITE ACCEPTANCE BY THE SHAPE EXCHANGER (`memshape.exchange`, table shape.v2): a write is accepted
iff every clause is F1-F4; an F0 clause refuses it (`no_shape`, the reasons in the result) and the model may keep the sentence unshaped with `keep_unshaped(text)` (in H, searchable as text, in no cross, no note); the
`weave_span` thread is still attempted for every accepted write and a refusal is recorded on the row (`weave: refused(...)`, the row field `weave_refused`), the sentence is stored anyway; (b) the MEMORY CROSSES
(`memcross`: one tank per shape, one cross per centre phrase, seats with provenance, derived from H and never stored as truth: its sha is part of every row's state); (c) NESTS: `declare_topic` opens a nest, an F4 clause
is completed by the nest's centre and NOTHING is put in front of any text (the mem.v3 prefix is not applied); (d) the slide order and the updates (shape.v2 change forms).  mem.v1..v3 are not touched.
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
from verantyx.loom import evidence
from verantyx.loom import memask as mask
from verantyx.loom import memcross as mx
from verantyx.loom import memdetect as mdt
from verantyx.loom import memnotes as mn
from verantyx.loom import memqwords as qw
from verantyx.loom import memrecall as mr
from verantyx.loom import notes as notelib
from verantyx.loom import memshape as ms
from verantyx.loom import ops
from verantyx.loom import read as rd
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import (MEM_KINDS, STORE_ID_RX, check_memory_rows, make_source, parse_source)
from verantyx.loom.memrecall import GateSelfQuestion, GateSubjectSelfQuestion
from verantyx.loom.ops import Run, refusal
from verantyx.loom.state import ARG_STR_CAP, ARGS_CHARS_CAP, GUARD_CAPS, LoomState, Refuse, canonical, sha256_text

MEM_VERSION = "mem.v1"
MEM_TASK_ID = "memory"
KIND_POLICIES: Tuple[str, ...] = ("a", "b", "c")          # OP-MEM-1: a base in the memory space (chosen), b memory_answer (no adhesion), c a session's own sentences give no adhesion
ROLES: Tuple[str, ...] = ("model", "user")
CROSS_UNCAPPED = 1 << 30                                   # L-MEM-14: no cross cap across sessions (a session's writes are capped instead)
CAPS_MEM_V1: Dict[str, int] = {"writes": 60, "recalls": 60, "lookups": 60, "ops": 300, "reads": 0, "emit_attempts": 0, "constructed": 0, "unit_chars": 8,
                               "max_L": 2, "crosses": CROSS_UNCAPPED, "max_depth": 0}
PROFILE_V1, PROFILE_V2, PROFILE_V3, PROFILE_V4 = "mem.v1", "mem.v2", "mem.v3", "mem.v4"
PROFILES: Tuple[str, ...] = (PROFILE_V1, PROFILE_V2, PROFILE_V3, PROFILE_V4)
V2_PLUS: Tuple[str, ...] = (PROFILE_V2, PROFILE_V3, PROFILE_V4)  # the profiles that have declare_topic / supersede / report and the door-supplied turn
V3_PLUS: Tuple[str, ...] = (PROFILE_V3, PROFILE_V4)              # the profiles with the mem.v3 rules (clause_at, cited REVERSAL, the long-story caps, notes mem.v2, the forced / capped turn rows)
V4_OPS: Tuple[str, ...] = ("keep_unshaped",)                     # PUB-M2: the op a mem.v4 session adds (the F0 tank)
V4_BRIDGE: Tuple[str, ...] = ("bridge",)                          # PUB-M6: the op a mem.v4 session adds to bridge a question word to a memory phrase
DEFAULT_PROFILE = PROFILE_V1                     # the API default: every store and test before MEM-d. The meter's doors (memdoor) ask for PROFILE_V2.
CAPS_MEM_V2: Dict[str, int] = dict(CAPS_MEM_V1, topics=8, supersedes=30, reports=60)
# MEM-fix (L-MEM-63): the caps of a LONG story (a session of 100+ messages must not run into 60 reports / 60 writes: the arms would stop being comparable).  Every count is the
# v2 one times 4; the shape caps (unit_chars, max_L, crosses, max_depth) are unchanged.  The baselines' log caps move the same way (memdoor.LOG_CAPS_V2).
CAPS_MEM_V3: Dict[str, int] = dict(CAPS_MEM_V2, writes=240, recalls=240, lookups=240, ops=1200, topics=32, supersedes=120, reports=240)
CAPS_MEM_V4: Dict[str, int] = dict(CAPS_MEM_V3, bridges=60)          # PUB-M6: + at most 60 bridges a session
# PUB-M6c: the VERSIONS a mem.v4 session reads and writes with, recorded in its begin row (`header.shape`, `header.qwords`, `header.ask`).  The default is the bundle of PUB-M2..M6b (every stored mem.v4 ledger and
# every test); `V4_VERSIONS_M6C` is the bundle of this ticket: shape.v3 (stage 1 of the staged table), ask.v3 + qwords.v2 (candidates, 「どの<名詞>」, relative clauses, bridges to a whole position).
V4_VERSIONS_V2: Dict[str, str] = {"shape": ms.SHAPES_V2, "qwords": qw.QWORDS_VERSION, "ask": mask.ASK_VERSION}
V4_VERSIONS_M6C: Dict[str, str] = {"shape": ms.SHAPES_V3, "qwords": qw.QWORDS_V2, "ask": mask.ASK_V3}
V4_VERSIONS_M6D: Dict[str, str] = dict(V4_VERSIONS_M6C, shape=ms.SHAPES_V4)             # PUB-M6d: the bundle of M6C with stage 2 of the shape table (「へ」 read like 「に」)
V4_ASK_QWORDS: Dict[str, str] = {mask.ASK_VERSION: qw.QWORDS_VERSION, mask.ASK_V3: qw.QWORDS_V2}      # an ask version reads one question-word table


def check_versions(versions: Optional[Dict[str, str]]) -> Dict[str, str]:
    """The versions of a mem.v4 session: the default bundle with the given keys replaced; `Refuse bad_policy` for an unknown version or an ask version with the wrong question-word table."""
    v = dict(V4_VERSIONS_V2)
    for k, x in (versions or {}).items():
        if k not in v:
            raise Refuse("bad_policy", {"policy": "versions", "value": k, "allowed": sorted(v)})
        v[k] = x
    if v["shape"] not in ms.SHAPE_TABLES_ALL or v["shape"] == ms.SHAPES_VERSION or v["ask"] not in V4_ASK_QWORDS or v["qwords"] != V4_ASK_QWORDS[v["ask"]]:
        raise Refuse("bad_policy", {"policy": "versions", "value": dict(v), "allowed": {"shape": [ms.SHAPES_V2, ms.SHAPES_V3, ms.SHAPES_V4], "ask": sorted(V4_ASK_QWORDS), "qwords": "the table of the ask version"}})
    return v


TOPIC_FORBIDDEN = "のにでとをが"                                    # a mem.v3 topic holds none of the arm particles (L-MEM-58): with one inside, 「<topic>の…」 is a nested particle chain and EVERY expansion is refused
LEAD_PARTICLES = "のにでとをがはもへ"                              # a particle in the lead-in of a clause (text from the start of its token up to the Y) means the clause already has its own subject
FORCE_OPS: Tuple[str, ...] = ("report_forced", "report_missing")  # MEM-fix (L-MEM-62): the harness rows of a turn that ended without a report of its own (mem.v3 / membase.v2)
FORCE_REASONS: Tuple[str, ...] = ("turn_limit", "no_tool_call", "cap_turn")      # "cap_turn" (PUB-H1, L-PUB-20): a turn the runaway cap ended is asked for its report too
CAP_OPS: Tuple[str, ...] = ("cap_turn",)                          # PUB-H1 (L-PUB-14): the harness row of a turn that the runaway cap ended; written only by a run driven with cap.v1 (mem.v3 / membase.v2), never by an older one
CAP_REASONS: Tuple[str, ...] = ("cap_repeat", "cap_status")
TOOLS: Tuple[str, ...] = ("write", "recall", "lookup", "read_sentence", "status", "commit")         # the memory session's tools (begin is the store's door)
V2_OPS: Tuple[str, ...] = ("declare_topic", "supersede", "report")                                 # MEM-d: the ops a `mem.v2` session adds
TOPIC_MAX_CHARS = 24
TOPIC_PARTICLE = "の"
REASON_MAX_CHARS = 40
TURN_RX = re.compile(r"^([1-9][0-9]?)-([1-9][0-9]{0,2})$")        # a turn id "<session>-<message>", 1-based (the harness names every message so)
REPORT_MAX_PAIRS, REPORT_MAX_BUGS = 10, 5
FROZEN_OPS: Tuple[str, ...] = ("unseat", "swap", "extend", "topic", "set_depth", "link", "unlink", "drop")
OPS_CLASS: Tuple[str, ...] = ("write",) + V4_OPS + V4_BRIDGE + FROZEN_OPS         # the calls the `ops` cap counts
MEM_RULES: Dict[str, Any] = {
    "output": "A memory session never emits: its only product is the sentences it writes. Plain text is discarded unread.",
    "write": "write(text, role) weaves the WHOLE sentence (WORD tier, weave_span.v2) into the memory. A sentence the structure cannot seat is refused and stores "
             "nothing: rephrase it. Shape: 「X の Y は A」 and short chains; two case particles before one head are refused.",
    "frozen": "Every cross a write made is frozen: " + " ".join(FROZEN_OPS) + " -> memory_frozen. add / open_cross / seat / emit are not tools of a memory session.",
    "history": "A write is judged against the sentences BEFORE it, never against itself (REVERSAL / NEW_RELATION / UNANCHORED); notes never block.",
    "recall": "reserved (MEM-c): recall_unavailable until the evidence gate is merged.",     # a session WITHOUT an evidence version (stub / no hook): byte-identical to MEM-a/b
    "close": "commit closes the session; an uncommitted session is not part of the memory.",
}
def caps_of(profile: str) -> Dict[str, int]:
    return CAPS_MEM_V4 if profile == PROFILE_V4 else CAPS_MEM_V3 if profile in V3_PLUS else CAPS_MEM_V2 if profile == PROFILE_V2 else CAPS_MEM_V1


def tools_of(profile: str) -> Tuple[str, ...]:
    return TOOLS + V2_OPS + (V4_OPS + V4_BRIDGE if profile == PROFILE_V4 else ()) if profile in V2_PLUS else TOOLS


MEM_RULES_GATE: Dict[str, Any] = dict(MEM_RULES, recall="recall(question) asks the evidence gate (scope clause, " + mr.RECALL_VERSION + ") of the WHOLE memory: ANSWER (one "
                                      "group), CHOICE (two or more: contested facts stay listed, nothing is retracted or ranked), NONE (no sentence passes: the codes say why).")


MEM_RULES_V2: Dict[str, Any] = dict(
    MEM_RULES_GATE,
    write="write(text, role) weaves the WHOLE sentence into the memory (at most 64 characters). A sentence the structure cannot seat is refused (span_inexpressible) and stores "
          "nothing: rewrite it in the form below and call write again. Every rewrite is counted as cost.",
    form="Write every fact as 「X の Y は A」: X the WHOLE subject (the thing: 広報, 備品, 山本さんのチーム), Y what you are asked about (担当, 期限, ポート, 会場), A a noun phrase "
         "(山本, 水曜, 10.0.0.5, 大阪). One fact per sentence, a noun at the end, no verb, no chain of が を で に before it. Example: 「備品の期限は水曜」, not 「備品は水曜までに揃える」.",
    topic="declare_topic(text) at the start of the session: what it is about (a noun phrase, at most 24 characters, no particle at the end). A sentence you write with no subject "
          "(「締め切りは水曜」) is stored as 「<topic>の締め切りは水曜」 and the result says so (implicit_topic). Declare it again when the subject changes.",
    supersede="A write that answers a question differently from an earlier sentence shows a SAME_QUESTION note (always). If the later statement REPLACES the earlier one (an explicit change, "
              "a postponement, a move), call supersede(new_sid, old_sid or old_answer, reason): recall then answers with the newest and lists the old ones as history (nothing is deleted). "
              "A real contradiction (no sign that one replaces the other) is left alone: recall shows CHOICE. A supersede that does not name an existing contested group is refused with a reason.",
    report="report(contradictions, bugs) ends EVERY turn: contradictions = pairs of turn ids (\"1-3\" = session 1, message 3) whose statements disagree, [] if none; bugs = [] here.",
    recall="recall(question) asks the evidence gate (scope clause, " + mr.RECALL_VERSION + ") of the WHOLE memory: ANSWER (one group), CHOICE (two or more: contested facts stay listed, "
           "nothing is ranked), NONE (no sentence passes: the codes say why). Superseded sentences are returned under `history`, not as the answer.")


MEM_RULES_V3: Dict[str, Any] = dict(
    MEM_RULES_V2,
    topic="declare_topic(text) at the start of the session: what it is about (a noun phrase, at most 24 characters, NO particle in it: の に で と を が -- 展示会準備, not 展示会の準備). A sentence you write with NO subject "
          "(「締め切りは水曜」) is stored as 「<topic>の締め切りは水曜」 and the result says so (implicit_topic). A sentence that already has its own subject (「広報の締め切りは水曜」, or one that "
          "names the topic) is stored AS WRITTEN: the topic is never added twice. Declare it again when the subject changes.",
    report="report(contradictions, bugs) ends EVERY turn: contradictions = pairs of turn ids (\"1-3\" = session 1, message 3) whose statements disagree, [] if none; bugs = [] here. A REVERSAL "
           "note names the two sentences it is about (`sentence`, `earlier`, and `cite`: the turn pairs you can report).")


MEM_RULES_V4: Dict[str, Any] = dict(
    MEM_RULES_V3,
    write="write(text, role) puts the sentence through the SHAPE EXCHANGER (at most 64 characters). Every clause must have a shape: F1 「X の Y は A」, F2 「Y は A」, F3 an event with が を に で と, F4 an event with no "
          "subject (it is completed by the open nest). A clause with no shape (F0: " + ", ".join(ms.F0_REASONS) + ") refuses the whole sentence, stores nothing and says why: rewrite it, or keep it with keep_unshaped. "
          "An accepted sentence is also woven (weave_span) when the loom can; if it cannot, it is stored anyway and the result says weave: refused(...).",
    keep_unshaped="keep_unshaped(text, role) stores a sentence that has no shape (the F0 tank): it is in the memory and can be searched as text, it enters no cross and fires no note. Refused (shaped) if every clause has a shape: use write.",
    topic="declare_topic(text) opens a NEST: what the following sentences are about (a noun phrase, at most 24 characters; particles are allowed: A社のB事業 is the nest B事業 with the の-arm A社). An event with no subject "
          "(「資料を送付した」) is placed in the open nest and its subject is the nest's centre; nothing is added to your text. Declare it again when the subject changes. A new session declares its own.",
    form="Write each fact as one sentence: 「X の Y は A」 (X the whole subject, Y what is asked about, A a noun phrase) or an event 「X が Y を V」; a change as 「Y は A から B に変更」 or 「Y は B に更新」. One fact per sentence.",
    supersede="A write whose value differs from an earlier value at the SAME place (the same Y of the same X, in the same nest) shows a SAME_SEAT note, a change clause an UPDATE note, a pair of phrases in opposite roles "
              "a REVERSAL_X note, another owner of the same attribute an ENUMERATION note (information only); each names the sentences it is about. If the later statement REPLACES the earlier one, call "
              "supersede(new_sid, old_sid or old_answer, reason): recall then answers with the newest and lists the old as history. A real contradiction is left alone: recall shows CHOICE.",
    recall="recall(question) reads the question with the same shape exchanger as a write and answers from the CROSSES: ANSWER (one value), UPDATED (the latest value + `history`), CHOICE (two or more values at one place: "
           "nothing is ranked), NONE (`issues` say why). Every value comes with the sentence that wrote it (`sid`, `span`): quote that stretch and emit.",
    bridge="bridge(question_word, memory_phrase) when a question names a slot in words the memory does not use (the question says 開ける日, the memory has 開館日): it adds the mapping, marked as constructed, "
           "and recall uses it. The memory phrase must be the centre of a cross the memory holds.",
)


class _Sentinel:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


DEFAULT = _Sentinel("DEFAULT")              # self_question=DEFAULT: the default hook of a new store (the gate)
LATEST = _Sentinel("LATEST")                # self_question=LATEST: the gate of today (`latest_hook`), recorded explicitly in the begin row
FROM_HEADER = _Sentinel("FROM_HEADER")      # replay / verify: each session with the hook its own begin row names (the registry below)
HOOKS: Dict[str, Any] = {mn.StubSelfQuestion.id: mn.StubSelfQuestion, GateSelfQuestion.id: GateSelfQuestion, GateSubjectSelfQuestion.id: GateSubjectSelfQuestion}     # the hook code, by recorded id
for _v in evidence.EVIDENCE_VERSIONS:                # PUB-M6c: the gate hooks of the other evidence versions (ids gate.<version>, gate.<version>+subject), so that a session replays under the gate its begin row recorded
    if _v != mr.RECALL_VERSION and _v != evidence.EVIDENCE_V1:
        for _c in mr.hook_classes(_v):
            HOOKS[_c.id] = _c


def latest_hook() -> Any:
    """The hook a NEW run of the meter is given: the gate with the whole-subject guard, reading with `memrecall.MEM_GATE_VERSION` (the one line to change when the default gate changes).  The sentinel
    `LATEST` resolves to it; the doors (`StructureDoor`, `mem_run`) pass it, so a new session RECORDS its gate explicitly (`header.self_question`, `header.evidence_version`)."""
    return mr.hook_classes(mr.MEM_GATE_VERSION)[1]()


# THE MEANING OF `DEFAULT` IS FROZEN (L-PUB-76): the API default of `MemStore.begin` / `verify_store` / `replay_store` is the hook of MEM-c2, gate.evidence.v2+subject, as it always was -- a store or a
# session that records no other hook is read with it, and the pre-MEM-d bytes stay what they were.  Replay never depends on a mutable default: it reads the recorded id (FROM_HEADER).
DEFAULT_HOOK_FACTORY = GateSubjectSelfQuestion      # a callable returning the default hook (or None); tests that need the pre-MEM-c behaviour replace it (monkeypatch)


def resolve_hook(spec: Any, header_id: Optional[str] = None) -> Optional[mn.SelfQuestionFn]:
    """DEFAULT -> the default hook; FROM_HEADER -> the registry entry of `header_id` (None for 'none' or an unknown id: replay then reports the mismatch);
    anything else (a hook, or None = no hook) as given."""
    if spec is DEFAULT:
        return DEFAULT_HOOK_FACTORY()
    if spec is LATEST:
        return latest_hook()
    if spec is FROM_HEADER:
        f = HOOKS.get(header_id) if isinstance(header_id, str) else None
        return None if f is None else f()
    return spec


_MODEL_RX = re.compile(r"^[^\x00-\x1f\x7f]{1,64}$")
_RUN_RX = re.compile(r"^s[0-9]{4,}$")
STORE_FILES = ("sessions", "memory.jsonl", "HEAD", ".lock")


# ------------------------------------------------------------------------------------------------------------
# H as bytes
# ------------------------------------------------------------------------------------------------------------
def row_line(row: dict) -> str:
    d = {"kind": row.get("kind", "base"), "sent": row["sent"], "source": row["source"]}
    if "topic_at" in row:                  # MEM-d: where the declared topic was put in front of the clause (only a row that was expanded has it; every other row is as it was)
        d["topic_at"] = row["topic_at"]
    if "clause_at" in row:                 # MEM-fix (mem.v3): where the self-question starts when the clause's own first unit is inside a token (a compound Y); only such a row has it
        d["clause_at"] = row["clause_at"]
    if "turn" in row:                      # MEM-d: the turn id the door told the session ("1-3"): only a mem.v2 write that was given one has it
        d["turn"] = row["turn"]
    if row.get("unshaped") is True:        # PUB-M2 (mem.v4): a sentence kept in the F0 tank; only such a row has it
        d["unshaped"] = True
    if "weave_refused" in row:             # PUB-M2 (mem.v4): an accepted sentence the loom's weave_span refused (the reason); only such a row has it
        d["weave_refused"] = row["weave_refused"]
    return canonical(d) + "\n"


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
                 contradiction_policy: str = "a", unseatable_policy: str = "a", self_question: Optional[mn.SelfQuestionFn] = None,
                 profile: str = PROFILE_V1, versions: Optional[Dict[str, str]] = None) -> None:
        if profile not in PROFILES:
            raise Refuse("bad_policy", {"policy": "profile", "value": profile, "allowed": list(PROFILES)})
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
        self.profile = profile
        self.v2plus = profile in V2_PLUS               # declare_topic / supersede / report, the door-supplied turn, the v2 state; mem.v3 adds the topic rule `topic.v2`, cited REVERSALs, the long-story caps
        self.v3 = profile in V3_PLUS
        self.v4 = profile == PROFILE_V4                # PUB-M2..M4: the shape exchanger accepts writes, memory crosses, nests, slide order
        if versions is not None and profile != PROFILE_V4:
            raise Refuse("bad_policy", {"policy": "versions", "value": "only a mem.v4 session has versions", "allowed": []})
        self.versions: Dict[str, str] = check_versions(versions) if self.v4 else {}
        self.shape_version: str = self.versions.get("shape", ms.SHAPES_V2)
        self.ask_version: str = self.versions.get("ask", mask.ASK_VERSION)
        self.builder = mx.IndexBuilder(self.shape_version) if self.v4 else None
        self.decls: List[dict] = []                    # mem.v4: the topic declarations [{session, at, topic}] of every earlier v4 session and this one (the ledger is their source)
        self.notes_profile = mn.MEM_NOTES_V4 if self.v4 else mn.MEM_NOTES_V2 if self.v3 else mn.MEM_NOTES_VERSION
        self.bridge_log: List[dict] = []                # mem.v4: the bridges [{session, at, qword, phrase}] of every earlier v4 session and this one (the ledger is their source)
        self.counts4: Dict[str, int] = {"bridges": 0}   # kept apart from counts2 so that the state of a mem.v2 / v3 session is as it was
        self.caps = dict(caps_of(profile))
        self.store_id, self.session_no = store_id, session_no
        self.store_head_before = store_head_before
        self.kind_policy, self.contradiction_policy, self.unseatable_policy = kind_policy, contradiction_policy, unseatable_policy
        self.hook = self_question
        self.hook_id = mn.hook_id(self_question)
        ev_v = getattr(self_question, "evidence_version", None)           # MEM-c: the evidence version the hook (and `recall`) read with; None = no gate in this session
        if ev_v is not None and ev_v not in evidence.EVIDENCE_VERSIONS:
            raise ValueError("a hook's evidence_version must be one of %s (or None)" % (evidence.EVIDENCE_VERSIONS,))
        self.evidence_version: Optional[str] = ev_v
        self.rows: List[dict] = []                     # H: the memory rows (earlier sessions + this one)
        self.rows0 = 0                                 # |H| when the session began
        self.corpus_cur: Corpus = self.corpus          # C over the whole of H (self.corpus is C_t only while a weave runs)
        self.session_written = 0                       # ok writes of this session (the `#i` of the source)
        self.counts: Dict[str, int] = {"writes": 0, "recalls": 0}
        self.counts2: Dict[str, int] = {"topics": 0, "supersedes": 0, "reports": 0}      # MEM-d (mem.v2 only), kept apart so that a mem.v1 session's counts are exactly the MEM-a..c ones
        self.topic: Optional[str] = None               # MEM-d (mem.v2): the declared topic of THIS session (not carried: a new session declares its own)
        self.superseded: Dict[int, dict] = {}          # MEM-d: {sid: {"by", "reason", "session"}} -- carried from the ledgers of the earlier sessions, extended by `supersede`
        self.starts: Dict[int, int] = {}               # MEM-d: {sid: topic_at} of the sentences stored with a declared topic (from the rows, so it survives the session)
        self.shapes: Dict[int, List[dict]] = {}        # MEM-d: per sentence the woven crosses' shape (cid, topic, seat names): what `sentence_clause` reads, for `supersede`
        self.tally: Dict[str, Any] = {"notes": {t: 0 for t in (mn.NOTE_TYPES_V4 if self.v4 else mn.NOTE_TYPES)}, "refused": {}}
        self._pending: List[dict] = []
        self._begin_header: Optional[dict] = None

    # -- the carried state (the frozen-stack fold) ------------------------------------------------------------------
    def carry(self, rows: Sequence[dict], superseded: Optional[Dict[int, dict]] = None, decls: Optional[Sequence[dict]] = None, bridges: Optional[Sequence[dict]] = None) -> None:
        """Weave every earlier sentence, in order, against its own prefix corpus: the cumulative state of the sessions before (a pure function of H).  The same code
        path as a live write minus the notes; a row that no longer weaves means the store is not what it says (`store_unverified`)."""
        rows = list(rows)
        prev = Corpus(b"")
        ds = list(decls or []) if self.v4 else []
        order = sorted(range(len(ds)), key=lambda i: (ds[i]["at"], i))
        di = 0
        for t in range(len(rows)):
            c_t = build_corpus(rows[:t + 1])
            if self.v4:                                                  # mem.v4: the nests declared before sentence t are open for it; a kept-unshaped / weave-refused row is not woven (the row says so)
                while di < len(order) and ds[order[di]]["at"] <= t:
                    d = ds[order[di]]
                    self.builder.declare(d["session"], d["at"], d["topic"])
                    di += 1
            if not (self.v4 and (rows[t].get("unshaped") is True or "weave_refused" in rows[t])):
                try:
                    self._weave_row(t, prev, c_t)
                except Refuse as r:
                    raise Refuse("store_unverified", {"reason": "carried_sentence_does_not_weave", "sid": t, "refusal": r.type})
            if self.v4:
                self.builder.add_row(t, rows[t], prev)
            prev = c_t
            if "topic_at" in rows[t]:
                self.starts[t] = rows[t]["topic_at"]
            elif "clause_at" in rows[t]:
                self.starts[t] = rows[t]["clause_at"]
        sup = {int(k): dict(v) for k, v in (superseded or {}).items()}
        if any(not 0 <= k < len(rows) or not 0 <= v["by"] < len(rows) for k, v in sup.items()):
            raise Refuse("store_unverified", {"reason": "supersede_names_no_sentence"})
        self.superseded = sup
        if self.v4:
            while di < len(order):
                d = ds[order[di]]
                self.builder.declare(d["session"], d["at"], d["topic"])
                di += 1
            self.decls = [dict(d) for d in ds]
            for k in sorted(sup):
                self.builder.supersede(k, sup[k]["by"], sup[k]["reason"], sup[k]["session"])
            self.bridge_log = [dict(b) for b in (bridges or [])]
            for b in self.bridge_log:
                self.builder.bridge(b["session"], b["at"], b["qword"], b["phrase"])
        self.rows = rows
        self.rows0 = len(rows)
        self.corpus = self.corpus_cur = prev
        self._begin_header = None

    def _weave_row(self, t: int, c_before: Corpus, c_t: Corpus, record: bool = True) -> dict:
        units = c_t.tier("WORD").sentence_units[t]
        if not units:
            raise Refuse("no_unit", {})
        self.corpus = c_t
        try:
            wv = ops.h_weave_span(self, {"sid": t, "tier": "WORD", "from": 0, "to": len(units) - 1}, self.i)
        finally:
            self.corpus = self.corpus_cur
        if record:
            self.shapes[t] = [{"cid": c["cid"], "topic": c["topic"], "seated": [{"seat": s["seat"]} for s in c["seated"]]} for c in wv["crosses"]]
        for c in wv["crosses"]:                                          # sentence order: the arm unit, then the centre (L-MEM-16)
            for uid in [s["uid"] for s in c["seated"]] + [c["centre"]["uid"]]:
                u = self.state.units[uid]
                hist = len(c_before.postings("WORD", u.surface) or ())
                u.prov["history_n"] = hist
                u.prov["origin"] = "record" if hist else "new"
        return wv

    def turns(self) -> Dict[int, str]:
        """{sid: turn id} of the sentences that were written with one (mem.v2 through a door that knows the turn); {} otherwise."""
        return {k: r["turn"] for k, r in enumerate(self.rows) if "turn" in r}

    def clause_of(self, sid: int) -> Optional[dict]:
        """The clause 「[X の] Y は A」 of sentence `sid` as the self-question cuts it (None: no clause), from the shape of its weave."""
        shape = self.shapes.get(sid)
        return None if shape is None else mn.sentence_clause(self.corpus_cur, sid, shape, self.starts.get(sid))

    # -- header / begin -------------------------------------------------------------------------------------------------
    def header(self) -> dict:
        if self._begin_header is None:
            h = super().header()
            h.update({"mem_version": MEM_VERSION, "store_id": self.store_id, "session_no": self.session_no, "store_head_before": self.store_head_before,
                      "memory_sha_before": mem_sha(self.rows), "sessions_before": self.session_no - 1, "sentences_before": len(self.rows),
                      "evidence_version": self.evidence_version, "notes_profile": self.notes_profile, "caps": MEM_VERSION, "kind_policy": self.kind_policy,
                      "contradiction_policy": self.contradiction_policy, "unseatable_policy": self.unseatable_policy, "self_question": self.hook_id})
            if self.v2plus:                                   # absent in a mem.v1 header: every earlier begin row is as it was
                h["mem_profile"] = self.profile
            if self.v4:                                       # PUB-M2: the frozen shape table and the version of the memory cross serialisation this session reads / writes
                h["shape"] = {"version": self.shape_version, "sha": ms.SHAPE_TABLES_ALL[self.shape_version]}
                h["cross"] = {"version": mx.CROSS_VERSION}
                h["qwords"] = {"version": self.versions["qwords"], "sha": qw.QWORDS_SHAS[self.versions["qwords"]]}        # PUB-M6: the question-word tank (frozen)
                h["detect"] = {"version": mdt.DETECT_VERSION}                              # PUB-M5: the detections on the crosses
                h["ask"] = {"version": self.ask_version}                                   # PUB-M6: recall on the crosses
            self._begin_header = h
        return self._begin_header

    def begin_body(self) -> dict:
        rules = MEM_RULES if self.evidence_version is None else MEM_RULES_GATE
        if self.v2plus:
            base = MEM_RULES_V4 if self.v4 else MEM_RULES_V3 if self.v3 else MEM_RULES_V2
            rules = base if (self.evidence_version is not None or self.v4) else dict(base, recall=MEM_RULES["recall"])
        if self.evidence_version is not None and self.evidence_version != mr.RECALL_VERSION:       # PUB-M6c: the rule text names the gate the session reads with
            rules = {k: (v.replace(mr.RECALL_VERSION, self.evidence_version) if k == "recall" and isinstance(v, str) else v) for k, v in rules.items()}
        res = {"ok": True, "run_id": self.run_id, "mode": "memory", "task": ops.task_view(self.task, self.caps), "rules": rules, "header": self.header()}
        if self.v2plus:
            res["tools"] = list(tools_of(self.profile))
        return {"actor": "model", "op": "begin", "args": {"task_id": self.task["task_id"], "model": self.model}, "result": res, "state_sha": self.mem_state_sha()}

    def mem_state_sha(self) -> str:
        """The state after a row: the loom state (units, crosses, thread, counters, guards) + the memory (|H|, its sha, the write / recall counts)."""
        mem = {"sentences": len(self.rows), "memory_sha": mem_sha(self.rows), "writes": self.counts["writes"], "recalls": self.counts["recalls"]}
        if self.v2plus:                                        # MEM-d: what a mem.v2 session adds to its state; absent for mem.v1, so those hashes are as they were
            mem["v2"] = {"topic": self.topic, **self.counts2}
        if self.superseded:
            mem["superseded"] = [[k, v["by"], v["session"], v["reason"]] for k, v in sorted(self.superseded.items())]
        if self.v4:                                            # the memory crosses are derived from H, the declarations and the marks: their sha is part of every row's state (a replay must rebuild them identically)
            mem["v4"] = {"index": self.builder.index().index_sha, "bridges": self.counts4["bridges"]}
        return sha256_text(canonical({"loom": self.state.to_obj(), "mem": mem}))

    # -- one call = one body ---------------------------------------------------------------------------------------------
    def notes_due(self) -> List[dict]:
        if self._prev != ("model", "write", True) and not (self.v4 and self._prev == ("model", "keep_unshaped", True)):       # mem.v4: a kept sentence's F1-F4 clauses make cross notes too (L-PUB-42)
            return []
        return list(self._pending)

    def _executable(self, op: Any) -> bool:
        return isinstance(op, str) and (op in TOOLS or op in FROZEN_OPS or (self.v2plus and op in V2_OPS) or (self.v4 and (op in V4_OPS or op in V4_BRIDGE)))

    def _precheck(self, op: str) -> None:
        st = self.state
        if st.closed is not None:
            st.guards["closed_calls"] += 1
            raise Refuse("run_closed", {"closed": list(st.closed)})
        if (op == "write" or op in V4_OPS) and self.counts["writes"] >= self.caps["writes"]:          # keep_unshaped is a write for the cap
            raise Refuse("write_cap", {"limit": self.caps["writes"]})
        if op == "recall" and self.counts["recalls"] >= self.caps["recalls"]:
            raise Refuse("recall_cap", {"limit": self.caps["recalls"]})
        if op in V4_BRIDGE and self.counts4["bridges"] >= self.caps["bridges"]:
            raise Refuse("bridge_cap", {"limit": self.caps["bridges"]})
        for v2op, cnt, refusal_name in (("declare_topic", "topics", "topic_cap"), ("supersede", "supersedes", "supersede_cap"), ("report", "reports", "report_cap")):
            if op == v2op and self.counts2[cnt] >= self.caps[cnt]:
                raise Refuse(refusal_name, {"limit": self.caps[cnt]})
        if op in OPS_CLASS and st.counters["ops"] >= self.caps["ops"]:
            raise Refuse("ops_cap", {"limit": self.caps["ops"]})
        if op in ("lookup", "read_sentence") and st.counters["lookups"] >= self.caps["lookups"]:
            raise Refuse("lookup_cap", {"limit": self.caps["lookups"]})
        if op == "write" or op in V4_OPS:
            self.counts["writes"] += 1
        if op == "recall":
            self.counts["recalls"] += 1
        if op in V4_BRIDGE:
            self.counts4["bridges"] += 1
        if op == "declare_topic":
            self.counts2["topics"] += 1
        if op == "supersede":
            self.counts2["supersedes"] += 1
        if op == "report":
            self.counts2["reports"] += 1
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
                raise Refuse("secret_shaped_sentence" if op == "write" or op in V4_OPS else "secret_shaped_unit", {"redacted": n})
            result = _HANDLERS[op](self, args, self.i)
        except Refuse as r:
            result = refusal(r.type, r.detail)
            if op == "write" or op in V4_OPS:
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
            return {"actor": actor, "op": op, "args": {"after": self.i - 1, "of": self._prev[1], "notes": notes, "nv": self.notes_profile},
                    "result": {"ok": True}, "state_sha": self.mem_state_sha()}
        if actor == "harness" and op in FORCE_OPS:             # MEM-fix (L-MEM-62): only a mem.v3 session has them; any other session refuses them as it always did
            if not self.v3:
                raise ValueError("op %r is not a row of actor %r" % (op, actor))
            return {"actor": actor, "op": op, "args": force_args(args), "result": {"ok": True}, "state_sha": self.mem_state_sha()}
        if actor == "harness" and op in CAP_OPS:               # PUB-H1: like the forced-report rows, only a mem.v3 session has it
            if not self.v3:
                raise ValueError("op %r is not a row of actor %r" % (op, actor))
            return {"actor": actor, "op": op, "args": cap_args(args), "result": {"ok": True}, "state_sha": self.mem_state_sha()}
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
    if run.v4:
        return _write_v4(run, a, i)
    a = ops._args(a, {"text": (str, True), "role": (str, False), **({"turn": (str, False)} if run.v2plus else {})})
    turn = a.get("turn")
    if turn is not None and not TURN_RX.match(turn):
        raise Refuse("bad_turn", {"turn": turn[:16]})
    role = a.get("role", "model")
    if role not in ROLES:
        raise Refuse("bad_args", {"field": "role", "reason": "one of %s" % (list(ROLES),)})
    text = unicodedata.normalize("NFC", a["text"])
    if not 1 <= len(text) <= ARG_STR_CAP or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in text):
        raise Refuse("bad_sentence", {"reason": "1 to %d characters, no newline / NUL / control character" % ARG_STR_CAP})
    t = len(run.rows)
    implicit: Optional[dict] = None
    if run.v2plus and run.topic is not None:                          # MEM-d: a subject-less sentence is stored with the declared topic as its subject
        implicit = _expand_with_topic(run, t, text, role)
        if implicit is not None:
            text = implicit["stored"]
    row = {"kind": kind_of(run.kind_policy), "sent": text, "source": make_source(run.store_id, run.session_no, run.session_written, role)}
    if implicit is not None:
        row["topic_at"] = implicit["at"]
    if turn is not None:
        row["turn"] = turn
    rows_after = run.rows + [row]
    c_before = run.corpus_cur
    c_t = build_corpus(rows_after)
    wv = run._weave_row(t, c_before, c_t)                              # a Refuse here changes nothing (weave_span refuses before it touches the state)
    # -- committed from here on: H gains the row, the crosses are linked (by the weave) and frozen ----------------------------------------------------
    rows_before = run.rows
    run.rows = rows_after
    run.corpus_cur = run.corpus = c_t
    run.session_written += 1
    if implicit is not None:
        run.starts[t] = implicit["at"]
    elif run.v3:                                                      # MEM-fix (L-MEM-58): a sentence with its own subject whose clause starts inside a token is asked from the start of that token
        cs = clause_run_start(c_t, t, text, wv)
        if cs is not None:
            row["clause_at"] = cs
            run.starts[t] = cs
            c_t = run.corpus_cur = run.corpus = build_corpus(rows_after)       # the row changed after c_t was built from it: the live corpus must be the corpus of memory.jsonl's bytes (history.corpus_sha, mem_sha)
    st = run.state
    new_crosses = [st.crosses[c["cid"]] for c in wv["crosses"]]
    linked = [st.crosses[cid] for cid in st.thread]
    c_key = c_before if run.kind_policy != "c" else build_corpus(_key_rows(rows_before, "c", run.session_no))
    notes, extra = mn.compute_write_notes(t=t, row=row, rows_before=rows_before, rows_after=rows_after, corpus_key=c_key, corpus_before=c_before, corpus_after=c_t,
                                          state=st, linked=linked, new_crosses=new_crosses, weave=wv, contradiction_policy=run.contradiction_policy,
                                          self_question=run.hook, superseded=run.superseded or None, clause_start=run.starts.get(t), cite=run.v3)
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
    if implicit is not None:
        res["implicit_topic"] = {"topic": run.topic, "at": implicit["at"], "written": implicit["written"]}
    if "clause_at" in row:
        res["clause_at"] = row["clause_at"]
    if turn is not None:
        res["turn"] = turn
    if notes:
        res["notes"] = notes
    return res


def _model_text(a: dict, run: MemRun) -> Tuple[str, str, Optional[str]]:
    """(text, role, turn) of a mem.v4 `write` / `keep_unshaped`: the checks of `h_write`, shared."""
    a = ops._args(a, {"text": (str, True), "role": (str, False), "turn": (str, False)})
    turn = a.get("turn")
    if turn is not None and not TURN_RX.match(turn):
        raise Refuse("bad_turn", {"turn": turn[:16]})
    role = a.get("role", "model")
    if role not in ROLES:
        raise Refuse("bad_args", {"field": "role", "reason": "one of %s" % (list(ROLES),)})
    text = unicodedata.normalize("NFC", a["text"])
    if not 1 <= len(text) <= ARG_STR_CAP or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in text):
        raise Refuse("bad_sentence", {"reason": "1 to %d characters, no newline / NUL / control character" % ARG_STR_CAP})
    return text, role, turn


def _clause_summary(c: mx.ClauseRec) -> dict:
    d: Dict[str, Any] = {"k": c.k, "shape": c.shape, "text": c.text[:32]}
    if c.tank is None:
        d["reason"] = c.reason
        return d
    d.update(tank=c.tank, centre=c.centre, via=c.via, nest=c.nest, value=c.value, change=None if c.change is None else c.change.form)
    return d


def _index_view(run: MemRun) -> dict:
    ix = run.builder.index()
    st = ix.stats()
    return {"sha": ix.index_sha, "crosses": sum(st[t]["crosses"] for t in mx.TANKS), "seats": sum(st[t]["seats"] for t in mx.TANKS), "f0": st[mx.F0_TANK]["sentences"], "nests": st["nests"], "bridges": len(ix.bridges)}


def _no_shape(ex: ms.Exchange) -> Refuse:
    bad = [c for c in ex.clauses if c.shape == "F0"]
    return Refuse("no_shape", {"shape": "F0", "reason": bad[0].reason if bad else "no_clause", "n_clauses": len(ex.clauses),
                               "clauses": [{"text": c.text[:32], "reason": c.reason, "detail": (c.detail or "")[:16]} for c in bad[:8]],
                               "hint": "rewrite it so that every clause has a shape (X の Y は A / Y は A / an event with が を に で と), or keep_unshaped(text)"})


def _write_v4(run: MemRun, a: dict, i: int) -> dict:
    """mem.v4 (PUB-M2, L-PUB-26): the shape exchanger decides.  Accepted iff every clause is F1-F4 (an F0 clause: `no_shape`, nothing stored).  An accepted sentence is stored; the `weave_span` thread of the loom
    is attempted for it, and if it is refused the sentence is stored anyway with `weave: refused(...)` (the tanks hold it, the thread does not).  Nothing is put in front of the text."""
    text, role, turn = _model_text(a, run)
    ex = ms.exchange(text, run.shape_version)
    if not ex.clauses or any(c.shape == "F0" for c in ex.clauses):
        raise _no_shape(ex)
    t = len(run.rows)
    row = {"kind": kind_of(run.kind_policy), "sent": text, "source": make_source(run.store_id, run.session_no, run.session_written, role)}
    if turn is not None:
        row["turn"] = turn
    rows_after = run.rows + [row]
    c_before = run.corpus_cur
    c_t = build_corpus(rows_after)
    wv: Optional[dict] = None
    wr: Optional[str] = None
    try:
        wv = run._weave_row(t, c_before, c_t)                          # a Refuse here changes nothing (weave_span refuses before it touches the state)
    except Refuse as r:
        why = r.detail.get("reason")
        wr = "%s:%s" % (r.type, why) if isinstance(why, str) and why else r.type
        row["weave_refused"] = wr
        c_t = c_t.rebased(rows_bytes(rows_after))                      # the row changed after c_t was built from it: the live corpus is the corpus of memory.jsonl's bytes (the space does not read the flag: no second build, L-PUB-41)
    # -- committed from here on ------------------------------------------------------------------------------------------------------------------
    rows_before = run.rows
    run.rows = rows_after
    run.corpus_cur = run.corpus = c_t
    run.session_written += 1
    placed = run.builder.add_row(t, row, c_before)
    cross_notes = [dict(n, counted=n["type"] in mn.COUNTED_V4) for n in run.builder.last_notes]      # PUB-M5: made on the crosses, never blocking
    st = run.state
    c_key = c_before if run.kind_policy != "c" else build_corpus(_key_rows(rows_before, "c", run.session_no))
    res: Dict[str, Any] = {"ok": True, "sid": t, "source": row["source"], "kind": row["kind"], "role": role, "text": text, "tier": "WORD"}
    old_notes: List[dict] = []
    if wv is not None:
        cs = clause_run_start(c_t, t, text, wv)                        # MEM-fix (L-MEM-58), as in mem.v3
        if cs is not None:
            row["clause_at"] = cs
            run.starts[t] = cs
            c_t = run.corpus_cur = run.corpus = c_t.rebased(rows_bytes(rows_after))
        new_crosses = [st.crosses[c["cid"]] for c in wv["crosses"]]
        linked = [st.crosses[cid] for cid in st.thread]
        notes, extra = mn.compute_write_notes(t=t, row=row, rows_before=rows_before, rows_after=rows_after, corpus_key=c_key, corpus_before=c_before, corpus_after=c_t,
                                              state=st, linked=linked, new_crosses=new_crosses, weave=wv, contradiction_policy=run.contradiction_policy,
                                              self_question=run.hook, superseded=run.superseded or None, clause_start=run.starts.get(t), cite=True)
        old_notes = [dict(n, counted=n["type"] in mn.COUNTED_V4) for n in notes]               # notes profile mem.v4: the mem.v3 notes are second witnesses, only the cross notes are counted
        units: List[dict] = []
        new_uids = set()
        for c in wv["crosses"]:
            for s_ in c["seated"]:
                units.append({"uid": s_["uid"], "surface": s_["surface"], "cid": c["cid"], "seat": s_["seat"]})
            units.append({"uid": c["centre"]["uid"], "surface": c["centre"]["surface"], "cid": c["cid"], "seat": "centre"})
        for u in units:
            pv = st.units[u["uid"]].prov
            u["origin"], u["history_n"] = pv["origin"], pv["history_n"]
            if pv["origin"] == "new":
                new_uids.add(u["uid"])
        read_back = "".join(sg["s"] for cr in new_crosses for sg in rd.read_prose(st, cr))
        res.update({"from": wv["from"], "to": wv["to"], "crosses": wv["crosses"], "units": units, "readback": {"text": read_back, "same": read_back == wv["text"]},
                    "marked": _marked(wv["crosses"], new_uids), "history": {"sentences": t, "corpus_sha": c_key.corpus_sha}, "keys": extra["keys"], "clause": extra["clause"],
                    "thread_length": len(st.thread), "weave": "ok"})
        if "clause_at" in row:
            res["clause_at"] = row["clause_at"]
    else:
        res.update({"from": None, "to": None, "crosses": [], "units": [], "readback": {"text": "", "same": True}, "marked": "", "history": {"sentences": t, "corpus_sha": c_key.corpus_sha},
                    "keys": [], "clause": None, "thread_length": len(st.thread), "weave": "refused(%s)" % wr, "weave_refused": wr})
    all_notes = _witness(old_notes, cross_notes, wv is not None)
    run._pending = all_notes
    for n in all_notes:
        run.tally["notes"][n["type"]] += 1
    if all_notes:
        res["notes"] = all_notes
    res["shape"] = {"v": run.shape_version, "clauses": [_clause_summary(c) for c in placed]}
    res["index"] = _index_view(run)
    if turn is not None:
        res["turn"] = turn
    return res


def _witness(old: List[dict], cross: List[dict], woven: bool) -> List[dict]:
    """The notes of a mem.v4 write: the mem.v3 notes (in the order they came) and then the cross notes (in theirs), each of the two routes annotated with whether the other agreed.  SAME_SEAT (cross) and
    SAME_QUESTION (the evidence-gate route) are two witnesses of one fact: `witness` = {by, state}.  state: agree | cross_only | sq_only | unavailable (the sentence was not woven: no self-question) |
    unreadable (the gate could not read the clause) | not_applicable (an event position: the self-question asks 「Y は…」 only).  REVERSAL_X is compared with the old REVERSAL the same way."""
    sq = [n for n in old if n["type"] == mn.SAME_QUESTION]
    unreadable = [n for n in old if n["type"] == mn.SELF_QUESTION_UNREADABLE]
    rev = [n for n in old if n["type"] == mn.REVERSAL]
    seat = [n for n in cross if n["type"] == mdt.SAME_SEAT]
    revx = [n for n in cross if n["type"] == mdt.REVERSAL_X]
    out: List[dict] = []
    for n in old:
        if n["type"] == mn.SAME_QUESTION:
            n = dict(n, witness={"by": mdt.SAME_SEAT, "state": "agree" if seat else "sq_only"})
        elif n["type"] == mn.REVERSAL:
            n = dict(n, witness={"by": mdt.REVERSAL_X, "state": "agree" if revx else "rev_only"})
        out.append(n)
    for n in cross:
        if n["type"] == mdt.SAME_SEAT:
            if not woven:
                st = "unavailable"
            elif n["tank"] == "F3":
                st = "not_applicable"
            elif sq:
                st = "agree"
            elif unreadable:
                st = "unreadable"
            else:
                st = "cross_only"
            n = dict(n, witness={"by": mn.SAME_QUESTION, "state": st})
        elif n["type"] == mdt.REVERSAL_X:
            n = dict(n, witness={"by": mn.REVERSAL, "state": "unavailable" if not woven else ("agree" if rev else "cross_only")})
        out.append(n)
    return out


def h_keep_unshaped(run: MemRun, a: dict, i: int) -> dict:
    """mem.v4 (OP-PUB-2, L-PUB-27): store a sentence that has no shape in the F0 tank.  It is in H (the memory corpus: searchable as text, `lookup` / `recall` read it as any sentence) but enters no cross, is not
    woven, fires no note; its row says `unshaped`.  Refused `shaped` when every clause has a shape (use `write`) and `bad_sentence` when there is no letter in it."""
    text, role, turn = _model_text(a, run)
    if not any(ch.isalnum() for ch in text):
        raise Refuse("bad_sentence", {"reason": "no letter in the sentence"})
    ex = ms.exchange(text, run.shape_version)
    if ex.clauses and all(c.shape != "F0" for c in ex.clauses):
        raise Refuse("shaped", {"shapes": list(ex.shapes()), "hint": "every clause has a shape: use write"})
    t = len(run.rows)
    row = {"kind": kind_of(run.kind_policy), "sent": text, "source": make_source(run.store_id, run.session_no, run.session_written, role), "unshaped": True}
    if turn is not None:
        row["turn"] = turn
    rows_after = run.rows + [row]
    c_before = run.corpus_cur
    c_t = build_corpus(rows_after)
    run.rows = rows_after
    run.corpus_cur = run.corpus = c_t
    run.session_written += 1
    placed = run.builder.add_row(t, row, c_before)                       # L-PUB-42: the F1-F4 clauses of the sentence enter the crosses, the F0 clause does not
    all_notes = _witness([], [dict(n, counted=n["type"] in mn.COUNTED_V4) for n in run.builder.last_notes], False)
    run._pending = all_notes
    for n in all_notes:
        run.tally["notes"][n["type"]] += 1
    res: Dict[str, Any] = {"ok": True, "sid": t, "source": row["source"], "kind": row["kind"], "role": role, "text": text, "tank": mx.F0_TANK, "unshaped": True, "weave": "none",
                           "shape": {"v": run.shape_version, "shapes": list(ex.shapes()), "reasons": [c.reason for c in ex.clauses if c.shape == "F0"], "indexed": [_clause_summary(c) for c in placed if c.tank is not None]},
                           "index": _index_view(run)}
    if all_notes:
        res["notes"] = all_notes
    if turn is not None:
        res["turn"] = turn
    return res


def _expand_with_topic(run: MemRun, t: int, text: str, role: str) -> Optional[dict]:
    """MEM-d (owner 2026-10-13 「主語の無い文」): is the sentence SUBJECT-LESS (its clause is 「Y は A」 with no 「X の」 before the Y)?  Then the topic goes in front of the
    clause: 「締め切りは金曜」 -> 「<topic>の締め切りは金曜」 (inserted where the clause starts, at the beginning of the written token it sits in, so a lead-in such as 「メモ、」 stays), and THAT sentence is what the memory stores and the
    gate reads, with its ordinary self-question 「<topic>の締め切りは何ですか」.  The probe weaves the written sentence into a throw-away state (the run's own state, units and weave
    counter are untouched); None = not subject-less, no clause, or it does not weave (the real write then judges the sentence as written, refusal included)."""
    row0 = {"kind": kind_of(run.kind_policy), "sent": text, "source": make_source(run.store_id, run.session_no, run.session_written, role)}
    c0 = build_corpus(run.rows + [row0])
    saved = (run.state, len(run.weaves), run._nweaves)
    run.state = LoomState("prose")
    try:
        wv0 = run._weave_row(t, run.corpus_cur, c0, record=False)
    except Refuse:
        return None
    finally:
        run.state, nw, run._nweaves = saved
        del run.weaves[nw:]
    g = mn.clause_geometry(c0, t, wv0["crosses"])
    if g is None or not mn.subject_less(wv0["crosses"], g):
        return None
    at = g["start"]
    while at > 0 and mr.mid_token(text, at):           # the clause starts inside a written token (新規|締め切り): the topic goes before the WHOLE token, the subject stays whole (MEM-c2 rule)
        at -= 1
    if run.v3 and not topic_is_missing(run.topic, text, at, g):
        return None
    return {"stored": text[:at] + run.topic + TOPIC_PARTICLE + text[at:], "at": at, "written": text}


def clause_run_start(corpus_t: Any, t: int, text: str, wv: dict) -> Optional[int]:
    """MEM-fix (L-MEM-58): the offset the self-question of sentence t starts at when the clause's own first unit sits INSIDE a written token -- 「監視設定の本番監視ポートは…」, whose Y 本番監視ポート the
    word cut seats as 本番 / 監視 / ポート and whose topic cross therefore begins at 「ポート」: the question 「ポートは何ですか」 is a cut subject (MEM-c2 guard: UNREADABLE).  In a mem.v2 session the
    topic expansion's walk-back accidentally asked these sentences from the start of the token (and put the topic in front); a mem.v3 session no longer invents the topic, so it asks them from
    that same start: 「監視設定の本番監視ポートは何ですか」.  None when the clause starts at a token boundary (nothing changes) or there is no clause.  The guard and the gate are not touched."""
    g = mn.clause_geometry(corpus_t, t, wv["crosses"])
    if g is None or not mr.mid_token(text, g["start"]):
        return None
    at = g["start"]
    while at > 0 and mr.mid_token(text, at):
        at -= 1
    return at


def topic_is_missing(topic: str, text: str, at: int, geometry: dict) -> bool:
    """MEM-fix (L-MEM-58, rule `topic.v2`, owner 「主題の二重付与」: 254 of the 654 expanded sentences of meter v1 carried the topic twice, 430 more were given a topic in front of a subject of
    their own): a sentence whose clause the geometry reads as subject-less is given the topic ONLY IF the clause truly has no subject, i.e.
      - the topic is not already in the clause (`topic` in text[:end of the は]: the sentence starts with it, or has it as part of its subject), and
      - the lead-in of the clause (text from `at`, the start of the token the Y sits in, to the Y) holds no particle (のにでとをがはもへ): 「端末テストの責任者は…」 has the subject 端末テスト
        although the word cut seats 責任 / 者 as separate crosses and leaves the topic cross without an arm.
    A lead-in of kana / kanji / Latin with no particle (「新規」 in 「新規締め切りは水曜」, 「チェックサム責任」, 「CDNキャッシュ」) is a compound Y, not a subject.  A missed expansion leaves the sentence as written
    (the self-question then reads it or calls it UNREADABLE); a false one would invent a subject, so the doubt goes to not expanding."""
    if topic in text[:geometry["end"]]:
        return False
    return not any(ch in LEAD_PARTICLES for ch in text[at:geometry["start"]])


RECALL_UNAVAILABLE = {"ticket": "MEM-c", "reason": "the evidence gate is not merged into line3; recall over the memory is MEM-c"}      # bytes as MEM-a/b recorded them


def h_recall(run: MemRun, a: dict, i: int) -> dict:
    """recall(question): the evidence gate over the WHOLE memory (every committed sentence of every session and this one's), `memrecall.recall`.  It reads
    `run.corpus_cur` -- the memory corpus the session already holds (no corpus is built, no file is read) -- after the memory guard.  A session whose begin row records no
    evidence version (stub / no hook) refuses exactly as MEM-a/b did."""
    a = ops._args(a, {"question": (str, True)})
    q = unicodedata.normalize("NFC", a["question"])
    if run.evidence_version is None and not run.v4:
        raise Refuse("recall_unavailable", dict(RECALL_UNAVAILABLE))
    if not 1 <= len(q) <= ARG_STR_CAP or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in q):
        raise Refuse("bad_question", {"reason": "1 to %d characters, no newline / NUL / control character" % ARG_STR_CAP})
    check_memory_rows(run.rows)
    if run.v4:                                                          # PUB-M6: the question is read by the shape exchanger and answered from the crosses (memask); the gate judges only the emitted quote
        res = mask.recall(run.builder.index(), run.rows, run.corpus_cur, q, open_nest=run.builder.open_nest_id(run.session_no), ask=run.ask_version)
        res.update(ok=True, text=q)
        return res
    res = mr.recall(run.corpus_cur, q, run.evidence_version, subject_guard=bool(getattr(run.hook, "subject_guard", False)), superseded=run.superseded or None,
                    turns=run.turns() or None)
    res.update(ok=True, text=q)
    return res


def h_bridge(run: MemRun, a: dict, i: int) -> dict:
    """mem.v4 (PUB-M6, OP-PUB-7): bridge(question_word, memory_phrase) -- the model adds a mapping the question-word tank lacks: the question word / phrase stands for a phrase the memory holds as the centre of a
    cross.  A CONSTRUCTED, marked, ledgered entry of the index (`origin: constructed`) that recall then uses (route `bridge`).  Refused: bad_bridge, unknown_phrase (no cross has that centre), bridge_exists.
    ask.v3 (PUB-M6c, L-PUB-71): the argument may be called `question_phrase` (an alias: the row stores it as `question_word`), the question phrase may be 24 and the memory phrase 40 characters, and the memory
    phrase may also be the phrase of a whole POSITION as a candidate of `recall` shows it (棚ラベル照合の締切): recall then answers a question that holds the question phrase from that position."""
    v3 = run.ask_version == mask.ASK_V3
    if v3:
        a = ops._args(a, {"question_word": (str, False), "question_phrase": (str, False), "memory_phrase": (str, True)})
        if ("question_word" in a) == ("question_phrase" in a):
            raise Refuse("bad_args", {"field": "question_phrase", "reason": "give question_phrase (or question_word), not both and not neither"})
        a = {"question_word": a["question_word"] if "question_word" in a else a["question_phrase"], "memory_phrase": a["memory_phrase"]}
    else:
        a = ops._args(a, {"question_word": (str, True), "memory_phrase": (str, True)})
    qwd = _plain_text(a["question_word"], "question_word", 1, 24 if v3 else 16, "bad_bridge")
    ph = _plain_text(a["memory_phrase"], "memory_phrase", 1, 40 if v3 else 24, "bad_bridge")
    if qwd == ph:
        raise Refuse("bad_bridge", {"field": "memory_phrase", "reason": "the question word and the memory phrase are the same"})
    positions = run.builder.index().positions_text(ph) if v3 else ()
    if not run.builder.has_centre(ph) and not positions:
        raise Refuse("unknown_phrase", {"memory_phrase": ph, "reason": "no cross of the memory has this phrase as its centre%s: give the phrase as the memory writes it" % (" and no position has it as its phrase" if v3 else "")})
    at = len(run.rows)
    if not run.builder.bridge(run.session_no, at, qwd, ph):
        raise Refuse("bridge_exists", {"question_word": qwd, "memory_phrase": ph})
    run.bridge_log.append({"session": run.session_no, "at": at, "qword": qwd, "phrase": ph})
    ix = run.builder.index()
    res = {"ok": True, "question_word": qwd, "memory_phrase": ph, "origin": "constructed", "session": run.session_no, "at": at,
           "tanks": [t for t in mx.TANKS if ix.cross(t, ph) is not None], "bridges": len(ix.bridges)}
    if v3:
        res["positions"] = len(positions)
    return res


def h_lookup(run: MemRun, a: dict, i: int) -> dict:
    return ops.h_lookup(run, a, i)


def h_read_sentence(run: MemRun, a: dict, i: int) -> dict:
    return ops.h_read_sentence(run, a, i)


def h_status(run: MemRun, a: dict, i: int) -> dict:
    ops._args(a, {})
    st = run.state
    res = {"ok": True, "run_id": run.run_id, "store_id": run.store_id, "session_no": run.session_no, "closed": None if st.closed is None else list(st.closed),
            "sentences_before": run.rows0, "sentences": len(run.rows), "written": run.session_written, "units": len(st.units), "crosses": len(st.crosses),
            "thread_length": len(st.thread), "counters": dict(st.counters), "writes": run.counts["writes"], "recalls": run.counts["recalls"],
            "caps": dict(run.caps), "notes": dict(run.tally["notes"]), "refused_writes": dict(sorted(run.tally["refused"].items())), "guards": dict(st.guards),
            "memory_sha": mem_sha(run.rows), "ledger_head": run.head}
    if run.v2plus:
        res.update(profile=run.profile, topic=run.topic, topics=run.counts2["topics"], supersedes=run.counts2["supersedes"], reports=run.counts2["reports"],
                   superseded=len(run.superseded))
    if run.v4:
        res["index"] = _index_view(run)
    return res


def h_commit(run: MemRun, a: dict, i: int) -> dict:
    ops._args(a, {})
    sha = mem_sha(run.rows)
    run.state.closed = ["committed", sha]
    return {"ok": True, "status": "committed", "memory_sha": sha, "sentences": len(run.rows), "new_sentences": len(run.rows) - run.rows0,
            "session_no": run.session_no, "sessions_after": run.session_no}


def _plain_text(s: str, field: str, lo: int, hi: int, refusal_name: str) -> str:
    t = unicodedata.normalize("NFC", s)
    if not lo <= len(t) <= hi or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in t) or t != t.strip():
        raise Refuse(refusal_name, {"field": field, "reason": "%d to %d characters, no newline / control character, no space at either end" % (lo, hi)})
    return t


def h_declare_topic(run: MemRun, a: dict, i: int) -> dict:
    """MEM-d: the session's topic (a ledger row).  A noun phrase of at most 24 characters with at least one WORD unit, not ending in a particle (the expansion adds の).  May be
    declared again (the newest applies from then on; each is a row); `at_start` says whether nothing was written yet."""
    a = ops._args(a, {"text": (str, True)})
    t = _plain_text(a["text"], "text", 1, TOPIC_MAX_CHARS, "bad_topic")
    if run.v4:                                                          # PUB-M3 (OP-PUB-3): the topic opens a NEST; particles inside it are allowed (A社のB事業), nothing is put in front of any text
        if t[-1] in "のはがをにでともへ" or any(ch in t for ch in "。、．，"):
            raise Refuse("bad_topic", {"field": "text", "reason": "a noun phrase: no particle at the end, no 。 or 、"})
        if mx.topic_head(t) is None or not mn.word_units(t):
            raise Refuse("bad_topic", {"field": "text", "reason": "no word unit"})
        at = len(run.rows)
        info = run.builder.declare(run.session_no, at, t)
        run.decls.append({"session": run.session_no, "at": at, "topic": t})
        prev = run.topic
        run.topic = t
        return {"ok": True, "topic": t, "units": mn.word_units(t), "previous": prev, "at_start": run.session_written == 0, "at": at, "nest": info}
    if t[-1] in "のはがをにでともへ" or any(ch in t for ch in "。、．，"):
        raise Refuse("bad_topic", {"field": "text", "reason": "a noun phrase: no particle at the end (the structure adds の), no 。 or 、"})
    if run.v3 and any(ch in TOPIC_FORBIDDEN for ch in t):
        raise Refuse("bad_topic", {"field": "text", "reason": "no particle (%s) inside the topic: the structure puts の after it, and a second particle before the head makes the sentence unseatable "
                                                              "(nested_particle_chain); write 展示会準備, not 展示会の準備" % "".join(TOPIC_FORBIDDEN)})
    units = mn.word_units(t)
    if not units:
        raise Refuse("bad_topic", {"field": "text", "reason": "no word unit"})
    prev = run.topic
    run.topic = t
    return {"ok": True, "topic": t, "units": units, "previous": prev, "at_start": run.session_written == 0, "form": "%sの<Y>は<A>" % t}


def h_supersede(run: MemRun, a: dict, i: int) -> dict:
    """MEM-d (owner 2026-10-13 「更新と矛盾」): the model resolves a CONTESTED group explicitly.  supersede(new_sid, reason, old_sid | old_answer, question?) marks every live sentence
    of the OLD answer group (the component of `old_sid`, or the one that holds the answer text `old_answer`) as superseded by `new_sid`; the new group must be a different component
    of the SAME question (`question`, default the self-question of sentence `new_sid`).  Nothing is deleted: recall answers with the live group and lists the old one under
    `history`.  One row.  Typed refusals, all before anything changes: supersede_unavailable, bad_args, bad_reason, bad_question, unknown_sid, no_self_question, not_an_answer
    {which}, new_superseded, unknown_answer, same_group, already_superseded."""
    a = ops._args(a, {"new_sid": (int, True), "reason": (str, True), "old_sid": (int, False), "old_answer": (str, False), "question": (str, False)})
    if run.evidence_version is None:
        raise Refuse("supersede_unavailable", {"reason": "this session has no evidence gate: nothing defines a contested group"})
    if ("old_sid" in a) == ("old_answer" in a):
        raise Refuse("bad_args", {"field": "old_sid", "reason": "give exactly one of old_sid / old_answer"})
    reason = _plain_text(a["reason"], "reason", 1, REASON_MAX_CHARS, "bad_reason")
    n = len(run.rows)
    new_sid = a["new_sid"]
    if not 0 <= new_sid < n:
        raise Refuse("unknown_sid", {"sid": new_sid, "n": n, "which": "new"})
    if "old_sid" in a and not 0 <= a["old_sid"] < n:
        raise Refuse("unknown_sid", {"sid": a["old_sid"], "n": n, "which": "old"})
    if "question" in a:
        question = _plain_text(a["question"], "question", 1, ARG_STR_CAP, "bad_question")
    else:
        g = run.clause_of(new_sid)
        if g is None:
            raise Refuse("no_self_question", {"sid": new_sid, "reason": "the sentence has no clause 「Y は A」; give `question`"})
        question = g["question"]
    guard = bool(getattr(run.hook, "subject_guard", False))
    j = mr.analyse(run.corpus_cur, question, run.evidence_version, True, guard)
    comps, sets = j["comps"], j["sets"]
    of = {s: k for k, comp in enumerate(comps) for s in comp}
    if new_sid not in of:
        raise Refuse("not_an_answer", {"which": "new", "sid": new_sid, "question": question})
    if new_sid in run.superseded:
        raise Refuse("new_superseded", {"sid": new_sid, "by": run.superseded[new_sid]["by"]})
    if "old_sid" in a:
        old_sid = a["old_sid"]
        if old_sid not in of:
            raise Refuse("not_an_answer", {"which": "old", "sid": old_sid, "question": question})
        old_k = of[old_sid]
    else:
        norm = mn.norm_answer(a["old_answer"])
        hits = [k for k, comp in enumerate(comps) if any(norm in sets[s] for s in comp)]
        if not norm or not hits:
            shown = sorted({d for comp in comps for s in comp for d in sets[s].values()})[:8]
            raise Refuse("unknown_answer", {"answer": a["old_answer"][:32], "question": question, "answers": shown})
        old_k = hits[0]                                  # an answer text lies in ONE component (two that share it would be one)
    if old_k == of[new_sid]:
        raise Refuse("same_group", {"new_sid": new_sid, "question": question, "reason": "old and new are one answer group: nothing is contested"})
    targets = [s for s in comps[old_k] if s not in run.superseded]
    if not targets:
        raise Refuse("already_superseded", {"sids": comps[old_k], "question": question})
    for s in targets:
        run.superseded[s] = {"by": new_sid, "reason": reason, "session": run.session_no}
        if run.v4:
            run.builder.supersede(s, new_sid, reason, run.session_no)         # the mark only: the seats of the sentence stay (history kept)
    after = mr.recall(run.corpus_cur, question, run.evidence_version, True, guard, run.superseded, run.turns() or None)
    return {"ok": True, "question": question, "new_sid": new_sid, "reason": reason, "session": run.session_no,
            "superseded": [dict({"sid": s, "source": run.rows[s]["source"], "answers": list(sets[s].values())}, **({"turn": run.rows[s]["turn"]} if "turn" in run.rows[s] else {}))
                           for s in targets],
            "verdict_after": after["verdict"], "answers_after": [g["text"] for g in after["answers"]],
            "history": [{"sid": o["sid"], "answer": o["answer"], "superseded_by": o["superseded_by"]} for g in after.get("history", []) for o in g["occurrences"]]}


def h_report(run: MemRun, a: dict, i: int) -> dict:
    """MEM-d: the closed record of what the model NOTICED in a turn (`report_result`).  `turn` is supplied by the door (the harness knows which message it just delivered; the
    model never types it)."""
    return report_result(ops._args(a, {"turn": (str, True), "contradictions": (list, True), "bugs": (list, False)}))


def report_result(a: dict) -> dict:
    """The one definition of a `report` (the memory session and the baseline arms share it, so "what the model noticed" is the same closed format in every arm):
    contradictions = up to 10 pairs of turn ids "<session>-<message>" (1-based, distinct, none later than `turn`), bugs = up to 5 short strings.  There is no free-text field:
    whether a pair was found is a lookup, not a judgement.  Normalised: each pair sorted, no duplicate pair, the list sorted."""
    m = TURN_RX.match(a["turn"])
    if not m:
        raise Refuse("bad_turn", {"turn": a["turn"][:16]})
    now = (int(m.group(1)), int(m.group(2)))
    cs = a["contradictions"]
    if len(cs) > REPORT_MAX_PAIRS:
        raise Refuse("bad_report", {"field": "contradictions", "reason": "at most %d pairs" % REPORT_MAX_PAIRS})
    pairs = []
    for c in cs:
        if not (isinstance(c, list) and len(c) == 2 and all(isinstance(x, str) for x in c)):
            raise Refuse("bad_report", {"field": "contradictions", "reason": "each is a pair of turn ids [\"1-3\", \"2-5\"]"})
        ms = [TURN_RX.match(x) for x in c]
        if not all(ms):
            raise Refuse("bad_report", {"field": "contradictions", "reason": "a turn id is \"<session>-<message>\", 1-based"})
        ids = sorted((int(x.group(1)), int(x.group(2))) for x in ms)
        if ids[0] == ids[1]:
            raise Refuse("bad_report", {"field": "contradictions", "reason": "a pair names two different turns"})
        if ids[1] > now:
            raise Refuse("future_turn", {"turn": a["turn"], "id": "%d-%d" % ids[1]})
        pair = ["%d-%d" % ids[0], "%d-%d" % ids[1]]
        if pair not in pairs:
            pairs.append(pair)
    bugs = a.get("bugs", [])
    if len(bugs) > REPORT_MAX_BUGS or not all(isinstance(b, str) and 1 <= len(b) <= ARG_STR_CAP for b in bugs):
        raise Refuse("bad_report", {"field": "bugs", "reason": "at most %d strings of 1 to %d characters" % (REPORT_MAX_BUGS, ARG_STR_CAP)})
    return {"ok": True, "turn": a["turn"], "contradictions": sorted(pairs), "bugs": list(bugs)}


def force_args(args: Any) -> dict:
    """The args of a `report_forced` / `report_missing` harness row (MEM-fix, L-MEM-62): {turn (a turn id), reason (turn_limit | no_tool_call), calls (tool calls the turn had used)}.  Raises
    ValueError, as every malformed harness row does."""
    if not (isinstance(args, dict) and set(args) == {"turn", "reason", "calls"}):
        raise ValueError("report_forced / report_missing: arguments are turn, reason, calls")
    if not (isinstance(args["turn"], str) and TURN_RX.match(args["turn"]) and args["reason"] in FORCE_REASONS and isinstance(args["calls"], int)
            and not isinstance(args["calls"], bool) and args["calls"] >= 0):
        raise ValueError("report_forced / report_missing: turn is a turn id, reason one of %s, calls a count" % (FORCE_REASONS,))
    return dict(args)


def cap_args(args: Any) -> dict:
    """The args of a `cap_turn` harness row (PUB-H1, L-PUB-14): {turn (a turn id), reason (cap_repeat | cap_status), cap (the cap version), tool (the tool of the call that was not run; "" if the name was
    not a string), n (the count that call would have reached), calls (tool calls the turn had used)}.  Raises ValueError, as every malformed harness row does."""
    if not (isinstance(args, dict) and set(args) == {"turn", "reason", "cap", "tool", "n", "calls"}):
        raise ValueError("cap_turn: arguments are turn, reason, cap, tool, n, calls")
    ints = all(isinstance(args[k], int) and not isinstance(args[k], bool) and args[k] >= 0 for k in ("n", "calls"))
    if not (isinstance(args["turn"], str) and TURN_RX.match(args["turn"]) and args["reason"] in CAP_REASONS and isinstance(args["cap"], str) and re.match(r"^cap\.v[0-9]+$", args["cap"])
            and isinstance(args["tool"], str) and len(args["tool"]) <= 64 and ints):
        raise ValueError("cap_turn: turn is a turn id, reason one of %s, cap a cap version, tool a name, n / calls counts" % (CAP_REASONS,))
    return dict(args)


def _frozen_handler(op: str):
    def h(run: MemRun, a: dict, i: int) -> dict:
        cid = a.get("cid") if isinstance(a, dict) else None
        if not isinstance(cid, str):
            raise Refuse("bad_args", {"field": "cid", "reason": "missing"})
        if cid not in run.state.crosses:
            raise Refuse("unknown_cid", {"cid": cid[:32]})
        raise Refuse("memory_frozen", {"cid": cid, "op": op, "reason": "a cross a write made is frozen"})
    return h


_HANDLERS = {"write": h_write, "recall": h_recall, "lookup": h_lookup, "read_sentence": h_read_sentence, "status": h_status, "commit": h_commit,
             "declare_topic": h_declare_topic, "supersede": h_supersede, "report": h_report, "keep_unshaped": h_keep_unshaped, "bridge": h_bridge}
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
        if r["actor"] == "model" and r["op"] in ("write", "keep_unshaped") and r["result"].get("ok") is True:
            res = r["result"]
            out.append({"kind": res["kind"], "sent": res["text"], "source": res["source"]})
            if "implicit_topic" in res:
                out[-1]["topic_at"] = res["implicit_topic"]["at"]
            if "clause_at" in res:
                out[-1]["clause_at"] = res["clause_at"]
            if "turn" in res:
                out[-1]["turn"] = res["turn"]
            if res.get("unshaped") is True:
                out[-1]["unshaped"] = True
            if "weave_refused" in res:
                out[-1]["weave_refused"] = res["weave_refused"]
        committed = (k == len(lines) - 1 and r["actor"] == "model" and r["op"] == "commit" and r["result"].get("ok") is True)
    return out, committed, begin


def session_supersedes(run_dir) -> Dict[int, dict]:
    """MEM-d: {sid: {"by", "reason", "session"}} -- what the ok `supersede` rows of a session ledger marked, in order (a later row never un-marks).  Read from the chain-verified
    ledger; the store's HEAD / memory.jsonl hold nothing of it (the ledger is the single source of truth)."""
    lines, _ = lg.read_raw_lines(run_dir)
    out: Dict[int, dict] = {}
    for ln in lines:
        r = lg._parse_line(ln)
        if r["actor"] == "model" and r["op"] == "supersede" and r["result"].get("ok") is True:
            res = r["result"]
            for x in res["superseded"]:
                out[x["sid"]] = {"by": res["new_sid"], "reason": res["reason"], "session": res["session"]}
    return out


def session_topics(run_dir) -> List[dict]:
    """MEM-fix (L-MEM-59): [{"session": n, "topic": text}] -- the ok `declare_topic` rows of a session ledger, in order (the ledger is the single source of truth, as for the supersede
    marks).  A session without a topic (every mem.v1 session, a v2 session that declared none) gives []."""
    lines, _ = lg.read_raw_lines(run_dir)
    out: List[dict] = []
    session = None
    for k, ln in enumerate(lines):
        r = lg._parse_line(ln)
        if k == 0:
            session = r["result"]["header"]["session_no"]
        if r["actor"] == "model" and r["op"] == "declare_topic" and r["result"].get("ok") is True:
            out.append({"session": session, "topic": r["result"]["topic"]})
    return out


def session_nest_decls(run_dir) -> List[dict]:
    """PUB-M3: [{"session", "at", "topic"}] -- the ok `declare_topic` rows of a mem.v4 session ledger, in order (`at` = how many sentences H held when it was declared).  Another profile's topics are not nests (a
    mem.v3 topic was put in front of the sentences it was about): [] for them."""
    lines, _ = lg.read_raw_lines(run_dir)
    out: List[dict] = []
    session = None
    v4 = False
    for k, ln in enumerate(lines):
        r = lg._parse_line(ln)
        if k == 0:
            hdr = r["result"]["header"]
            session, v4 = hdr["session_no"], hdr.get("mem_profile") == PROFILE_V4
        if v4 and r["actor"] == "model" and r["op"] == "declare_topic" and r["result"].get("ok") is True:
            out.append({"session": session, "at": r["result"]["at"], "topic": r["result"]["topic"]})
    return out


def session_bridges(run_dir) -> List[dict]:
    """PUB-M6: [{"session", "at", "qword", "phrase"}] -- the ok `bridge` rows of a mem.v4 session ledger, in order.  The ledger is their source; [] for another profile."""
    lines, _ = lg.read_raw_lines(run_dir)
    out: List[dict] = []
    session = None
    v4 = False
    for k, ln in enumerate(lines):
        r = lg._parse_line(ln)
        if k == 0:
            hdr = r["result"]["header"]
            session, v4 = hdr["session_no"], hdr.get("mem_profile") == PROFILE_V4
        if v4 and r["actor"] == "model" and r["op"] == "bridge" and r["result"].get("ok") is True:
            out.append({"session": session, "at": r["result"]["at"], "qword": r["result"]["question_word"], "phrase": r["result"]["memory_phrase"]})
    return out


def session_versions(run_dir) -> Optional[Dict[str, str]]:
    """PUB-M6c: {"shape", "qwords", "ask"} -- the versions the begin row of a mem.v4 session ledger records; None for another profile (or a header without them)."""
    lines, _ = lg.read_raw_lines(run_dir)
    if not lines:
        return None
    hdr = lg._parse_line(lines[0])["result"]["header"]
    if hdr.get("mem_profile") != PROFILE_V4:
        return None
    try:
        return {"shape": hdr["shape"]["version"], "qwords": hdr["qwords"]["version"], "ask": hdr["ask"]["version"]}
    except (KeyError, TypeError):
        return None


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
              self_question: Any = DEFAULT, profile: str = DEFAULT_PROFILE, versions: Optional[Dict[str, str]] = None) -> "MemSession":
        """Open a memory session: the store's lock, the cheap verification, the carried state, the `begin` row (L-MEM-18).  Raises `Refuse` (store_locked,
        store_unverified, bad_model_id, policy_mismatch, ...).  The defaults are the owner's choices: OP-MEM-1 (a), OP-MEM-2 (a), OP-MEM-3 (a).
        `self_question`: DEFAULT = the gate hook `gate.evidence.v2` (MEM-c, L-MEM-29); `StubSelfQuestion()` the stub; None no hook (no SAME_QUESTION, no recall).
        `profile` (MEM-d): `mem.v1` (the default of this API: no topic / supersede / report, the MEM-a..c begin row) or `mem.v2` (the meter's profile, recorded in the header)."""
        self_question = resolve_hook(self_question)
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
                         contradiction_policy=contradiction_policy, unseatable_policy=unseatable_policy, self_question=self_question, profile=profile, versions=versions)
            sup: Dict[int, dict] = {}
            decls: List[dict] = []
            brs: List[dict] = []
            for e in (head["sessions"] if head else []):
                sup.update(session_supersedes(self.sessions_dir / e["run_id"]))
                if profile == PROFILE_V4:
                    sv = session_versions(self.sessions_dir / e["run_id"])
                    if sv is not None and sv != run.versions:                    # one store, one bundle: the index is rebuilt from H with one table
                        raise Refuse("policy_mismatch", {"policy": "versions", "store": sv, "asked": dict(run.versions)})
                    decls += session_nest_decls(self.sessions_dir / e["run_id"])
                    brs += session_bridges(self.sessions_dir / e["run_id"])
            run.carry(rows, sup, decls, brs)
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

    def verify(self, self_question: Any = FROM_HEADER) -> dict:
        return verify_store(self.path, self_question)

    def index(self) -> "mx.MemIndex":
        """PUB-M2: the memory crosses of the committed sessions, derived from the verified ledgers (never stored): `memcross.build_index(H, the nest declarations, the supersede marks)`."""
        head, rows = self.check()
        sup: Dict[int, dict] = {}
        decls: List[dict] = []
        brs: List[dict] = []
        vs: Optional[Dict[str, str]] = None
        for e in (head["sessions"] if head else []):
            sup.update(session_supersedes(self.sessions_dir / e["run_id"]))
            decls += session_nest_decls(self.sessions_dir / e["run_id"])
            brs += session_bridges(self.sessions_dir / e["run_id"])
            vs = session_versions(self.sessions_dir / e["run_id"]) or vs
        return mx.build_index(rows, decls, sup, shape_version=(vs or V4_VERSIONS_V2)["shape"], bridges=brs)

    def replay(self, self_question: Any = FROM_HEADER) -> "MemReplay":
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

    def harness(self, op: str, args: dict) -> dict:
        """A row that is not the model's (`free_text_dropped`, `harness_meta`, `abandoned`): the driver's.  Same ledger, same chain, not counted against any cap."""
        if self._fd is None:
            raise RuntimeError("the session is closed")
        with self.ledger.locked() as lk:
            body = self.run.step("harness", op, args)
            row = lk.append(body, time.monotonic_ns() - self.t0)
            self.run.advance(row)
        return body["result"]

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
        return mn.session_events(self.rows(), r.contradiction_policy, r.unseatable_policy, r.notes_profile if r.v4 else None)

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


def replay_store(path, self_question: Any = FROM_HEADER) -> MemReplay:
    """`mem replay`: re-execute every listed session, in order, against an empty M0 (each session starts from the H the earlier ones re-derived, not from
    memory.jsonl) and require every row, every byte, the HEAD and memory.jsonl to be reproduced.  `self_question` is by default FROM_HEADER (PUB-M6e: each session
    is replayed with the hook its begin row names); an explicit hook must be the one the sessions were recorded with (a mismatch is INPUTS `self_question_mismatch`).  DEFAULT = the default hook of a new store (so a store recorded with the
    stub replays under `StubSelfQuestion()` or `FROM_HEADER`, and is INPUTS under the default); FROM_HEADER = each session with the registry hook its begin row names."""
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
    D: List[dict] = []                        # mem.v4: the nest declarations of the earlier sessions, as RE-derived by this replay
    B: List[dict] = []                        # mem.v4: the bridges of the earlier sessions, as RE-derived by this replay
    S: Dict[int, dict] = {}                   # what the earlier sessions' supersede ops marked, as RE-derived by this replay
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
        profile = hdr.get("mem_profile", PROFILE_V1)
        if profile not in PROFILES:
            out.status, out.mismatch = "INPUTS", "mem_profile_unknown"
            return out
        if r0.get("op") != "begin" or hdr.get("mem_version") != MEM_VERSION or hdr.get("caps") != MEM_VERSION or res0["task"].get("caps") != caps_of(profile):
            out.status, out.mismatch = "INPUTS", "mem_version_unknown"
            return out
        hook = resolve_hook(self_question, hdr.get("self_question"))
        if hdr.get("self_question") != mn.hook_id(hook):
            out.status, out.mismatch = "INPUTS", "self_question_mismatch"
            return out
        versions = None
        if profile == PROFILE_V4:                         # PUB-M6c: the versions the begin row recorded (a header without them: the bundle of PUB-M2..M6b)
            versions = session_versions(d)
            try:
                check_versions(versions)
            except Refuse:
                out.status, out.mismatch = "INPUTS", "versions_unknown"
                return out
        try:
            run = MemRun(hdr["store_id"], hdr["session_no"], run_id, model, store_head_before=before, self_question=hook, profile=profile, versions=versions, **opts)
            run.carry(H, S, D, B)
        except Refuse:
            out.status, out.first_diff = "DIFFERS", {"session": e["run_id"], "i": 0, "field": "carry"}
            return out
        mm = lg.header_mismatch(hdr, run.header())
        if mm is None:
            for k in ("mem_version", "store_id", "session_no", "store_head_before", "memory_sha_before", "sessions_before", "sentences_before", "evidence_version",
                      "notes_profile", "caps", "kind_policy", "contradiction_policy", "unseatable_policy", "self_question", "stability_mode", "declared_model", "mem_profile"):
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
        if run.v4 and mx.build_index(run.rows, run.decls, run.superseded, shape_version=run.shape_version, bridges=run.bridge_log).index_sha != run.builder.index().index_sha:     # the memory crosses must be rebuilt identically from H alone
            out.status, out.first_diff = "DIFFERS", {"session": e["run_id"], "i": None, "field": "index"}
            return out
        H = list(run.rows)
        if run.v4:
            D = [dict(d) for d in run.decls]
            B = [dict(b) for b in run.bridge_log]
        S = dict(run.superseded)
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


def verify_store(path, self_question: Any = FROM_HEADER) -> dict:
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
        parsed = [lg._parse_line(ln) for ln in lines]
        np_ = parsed[0]["result"]["header"].get("notes_profile") if parsed else None
        out[e["run_id"]] = mn.session_events(parsed, contradiction_policy, unseatable_policy, np_ if np_ == mn.MEM_NOTES_V4 else None)
    return out


# ------------------------------------------------------------------------------------------------------------
# CLI:  python -m verantyx.loom.memory {verify,replay,status,events} --store DIR
# ------------------------------------------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m verantyx.loom.memory", description="the memory store of the loom (MEM-a)")
    ap.add_argument("cmd", choices=("verify", "replay", "status", "events"))
    ap.add_argument("--store", required=True, help="the store directory (required; there is no default path)")
    ap.add_argument("--hook", default="header", choices=("default", "header") + tuple(sorted(HOOKS)) + (mn.NO_HOOK,),
                    help="verify / replay: the self-question hook to replay with (default = the default hook of a new store; header = each session's recorded id)")
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    hook = {"default": DEFAULT, "header": FROM_HEADER, mn.NO_HOOK: None}.get(ns.hook) if ns.hook in ("default", "header", mn.NO_HOOK) else HOOKS[ns.hook]()
    if ns.cmd == "verify":
        res = verify_store(ns.store, hook)
        code = 0 if res["status"] in ("OK", "EMPTY") else 1
    elif ns.cmd == "replay":
        res = replay_store(ns.store, hook).to_obj()
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
