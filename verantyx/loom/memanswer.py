"""MEM-d: the ANSWER RUN over a memory snapshot (docs/LINE3_LOOM_MEMORY_DESIGN.md 4.1 (2), 6, 9.2 L-MEM-21; docs/LINE3_LOCAL_DECISIONS.md MEM-d).

A question asked AFTER the sessions is answered the way the loom answers any question: the only output is the text of a successful `emit`, and `emit` passes only an
unchanged `weave_span` QUOTE that the evidence gate (evidence.v2, scope `clause`, UNCHANGED) reads as an answer to the question.  What differs is the corpus: it is the model's
own MEMORY, frozen as a SNAPSHOT file, and two tools are added:

  recall(question)  the memory reader (`memrecall.recall`): ANSWER / CHOICE / NONE over the snapshot, with the sentences a model superseded listed under `history` (never answered)
  abstain(type)     the loom's no_record / cannot_weave / unknown, plus `contested`: the memory holds two answers that no supersede resolved (a CHOICE is an answer of its own;
                    the values are in the ledger's recall rows, so "CHOICE holding both" is a lookup, not a judgement)

The snapshot (`write_snapshot`) is `<store>/snapshots/memory_<sha12>.jsonl`, named by the first 12 hex digits of its sha256: the rows of memory.jsonl, in order, each also
carrying `superseded_by {by, reason, session}` when the model replaced it.  The run's header pins `corpus_sha` (so the supersede marks are pinned too), and an answer run never
reads a growing memory (L-MEM-21).  `weave_span` on a superseded sentence is refused `superseded_sentence`: history is visible (lookup, read_sentence, recall) and never a quote.

The ordinary loom still refuses a corpus that holds a `mem:` row (`memory_in_base`, L-MEM-02: `LoomServer.begin`, `ledger.replay`); this module is the explicit door, and it opens
nothing but a memory snapshot (`check_memory_rows` on every row).  One ledger per answer run, `<store>/answers/<run_id>/` (loom format, chain, notes rows after a read / emit).
`replay_answer` / `verify_answer` re-execute it from the snapshot file and require every row, every byte, to be reproduced.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.ledger_events import GENESIS
from verantyx.loom import evidence as evl
from verantyx.loom import ledger as lg
from verantyx.loom import memask as mask
from verantyx.loom import memcross as mx
from verantyx.loom import memguard as mg
from verantyx.loom import memnotes as mn
from verantyx.loom import memory as mem
from verantyx.loom import memrecall as mr
from verantyx.loom import notes as notelib
from verantyx.loom import ops
from verantyx.loom import read as rd
from verantyx.loom.corpus import Corpus
from verantyx.loom.ledger import ReplayResult
from verantyx.loom.ops import Run, refusal
from verantyx.loom.read import DEFAULT_STABILITY
from verantyx.loom.state import ABSTAIN_TYPES, ARG_STR_CAP, Refuse, canonical, sha256_text

ANSWER_VERSION = "memanswer.v1"
ANSWER_V2 = "memanswer.v2"          # MEM-fix (L-MEM-59 / 60): the answer run holds the store's declared topics (read from a file the snapshot is paired with) and `recall` reads the question in its other forms
ANSWER_V3 = "memanswer.v3"          # PUB-M6: the answer run of a mem.v4 store: `recall` reads the memory CROSSES (memask), rebuilt from the snapshot and the file `crosses_<sha12>.json` (nest declarations + bridges) it is paired with
ANSWER_V4 = "memanswer.v4"          # PUB-M6c: memanswer.v3 + the versions of the store (shape / ask / qwords, in the crosses file) + `bridge` in the run + weave_span.v4 (the source slice is emitted) + `contested_value`
ANSWER_VERSIONS: Tuple[str, ...] = (ANSWER_VERSION, ANSWER_V2, ANSWER_V3, ANSWER_V4)
GUARD_V3 = "ansguard.v1"            # PUB-M6b (L-PUB-54..57; memanswer.v3 only, no v3 ledger was ever recorded with a model): weave_span refuses a stretch that is not verbatim and a value the recall replaced; emit may hand the gate a completed question
GUARD_V4 = "ansguard.v2"            # PUB-M6c (memanswer.v4): ansguard.v1 with the joiner-aware verbatim check + an emit of one value of a same-seat CHOICE is refused `contested_value`
BRIDGE_CAP = 5                      # memanswer.v4: at most this many bridges a run
ANSWER_TASK_ID = "answer"
ANSWER_EVIDENCE = (mr.MEM_GATE_VERSION, evl.SCOPE_CLAUSE)      # the gate NEW answer runs judge with: `memrecall.MEM_GATE_VERSION` (evidence.v6 since PUB-M6c, L-PUB-76), scope clause (L-MEM-12).  A run records it in its
                                                               # begin row (`evidence_profile`) and replays under THAT; a stored run (evidence.v2) is not touched
LEGACY_EVIDENCE = (evl.EVIDENCE_V2, evl.SCOPE_CLAUSE)          # what a begin row without an `evidence_profile` was recorded with (never happens for an answer run: every one has the gate)
RECALL_CAP = 20
ANSWER_ABSTAIN: Tuple[str, ...] = ABSTAIN_TYPES + ("contested",)
V4_TOOL: Tuple[str, ...] = ("bridge",)
ANSWER_TOOLS: Tuple[str, ...] = ("recall", "lookup", "read_sentence", "weave_span", "drop", "read", "emit", "abstain", "status")     # what the model is offered
ANSWER_TOOLS_V4: Tuple[str, ...] = ANSWER_TOOLS + V4_TOOL          # memanswer.v4: + bridge(question_phrase, memory_phrase), the model's confirmation of a candidate
_RUN_RX = re.compile(r"^a[0-9]{4,}$")
ANSWER_RULES: Dict[str, str] = {
    "memory": "The corpus is the memory of earlier sessions: one sentence per fact, 「X の Y は A」. You see it only through recall, lookup and read_sentence.",
    "recall": "recall(question) asks the memory: ANSWER (one group of sentences), CHOICE (two or more answers that nobody resolved), NONE (no sentence answers). A sentence a model "
              "replaced is listed under `history`; it is never the answer and weave_span refuses it (superseded_sentence).",
    "answer": "To answer, weave the answer stretch of an ANSWER sentence (weave_span with its sid) and emit. CHOICE -> abstain(type=contested). NONE -> abstain(type=no_record). "
              "Do not answer from anywhere else: plain text is discarded.",
    "abstain": list(ANSWER_ABSTAIN),
}
ANSWER_RULES_V2: Dict[str, str] = {
    "recall": ANSWER_RULES["recall"] + " The session topics are known: a question with no subject is also read with each topic in front (「<topic>の…」), and if nothing answers, with its subject "
              "read as the fused slot; `forms.tried` lists the questions read and each occurrence's `via` the forms that read it. emit still judges the question AS ASKED: a sentence found only "
              "through another form may be refused (no_evidence).",
}


ANSWER_RULES_V3: Dict[str, str] = {
    "recall": "recall(question) reads the question with the shape exchanger and answers from the memory CROSSES: ANSWER (one value), UPDATED (the latest value + `history`), CHOICE (two or more values at one "
              "place: nothing is ranked), NONE (`issues` say why). Each value comes with its sentence (`sid`) and the units of the stretch to quote (`span`): weave_span that stretch and emit. "
              "emit still judges the quote against the question AS ASKED: a value found through a bridge or a slot-noun class may be refused (no_evidence). "
              "weave_span refuses a stretch the loom would read out without its punctuation (quote_not_verbatim: 「v2.4」 would be emitted as 「v24」) and a value recall listed under `history` "
              "(replaced_value); abstain (cannot_weave) then. A subject-less question whose value came through a nest, and the new value of a change clause, are judged by the same gate against the "
              "question completed by the nest centre (via: nest) or the form of the change (via: update).",
}


ANSWER_RULES_V4: Dict[str, str] = {
    "bridge": "bridge(question_phrase, memory_phrase): the model's confirmation that a part of the question means a phrase the memory holds (a candidate's `phrase`, or a centre). Marked constructed, kept in the log.",
    "recall": "recall(question) reads the question with the shape exchanger and answers from the memory CROSSES: ANSWER (one value), UPDATED (the latest value + `history`), CHOICE (two or more values at one "
              "place: nothing is ranked), NONE (`issues` say why), or CANDIDATES: no exact route reaches a value, so the positions that share >= 2 content units with the question are offered, each with its "
              "sentence; recall NEVER answers a question fuzzily. If one candidate is what the question means, confirm it with bridge(question_phrase, memory_phrase) (question_phrase a part of the question, "
              "memory_phrase the candidate's `phrase`; constructed, marked, ledgered) and recall again: only then does recall answer, through the bridge. Each value comes with its sentence (`sid`) and the units "
              "of the stretch to quote (`span`): weave_span that stretch and emit. emit still judges the quote against the question AS ASKED: a value found through a bridge may be refused (no_evidence). "
              "weave_span refuses a stretch whose read-out is not the source text (quote_not_verbatim; a number with . , - : / inside is read out as written: v2.4, 6.5万円) and a value recall listed under "
              "`history` (replaced_value). emit refuses one value of a CHOICE whose sources disagree at one place (contested_value): abstain(type=contested). A subject-less question whose value came through a "
              "nest, and the new value of a change clause, are judged by the same gate against the question completed by the nest centre (via: nest) or the form of the change (via: update).",
}


# ------------------------------------------------------------------------------------------------------------
# the snapshot
# ------------------------------------------------------------------------------------------------------------
def snapshot_rows(rows: Sequence[dict], superseded: Dict[int, dict]) -> List[dict]:
    out = []
    for sid, r in enumerate(rows):
        d = {"kind": r.get("kind", "base"), "sent": r["sent"], "source": r["source"]}
        if "topic_at" in r:
            d["topic_at"] = r["topic_at"]
        if "turn" in r:
            d["turn"] = r["turn"]
        if r.get("unshaped") is True:                # mem.v4 rows only
            d["unshaped"] = True
        if "weave_refused" in r:
            d["weave_refused"] = r["weave_refused"]
        if sid in superseded:
            d["superseded_by"] = {"by": superseded[sid]["by"], "reason": superseded[sid]["reason"], "session": superseded[sid]["session"]}
        out.append(d)
    return out


def snapshot_bytes(rows: Sequence[dict], superseded: Dict[int, dict]) -> bytes:
    return "".join(canonical(r) + "\n" for r in snapshot_rows(rows, superseded)).encode("utf-8")


def superseded_of_rows(rows: Sequence[dict]) -> Dict[int, dict]:
    """{sid: {by, reason, session}} from the `superseded_by` keys of snapshot rows."""
    out: Dict[int, dict] = {}
    for sid, r in enumerate(rows):
        sb = r.get("superseded_by")
        if sb is not None:
            if not (isinstance(sb, dict) and isinstance(sb.get("by"), int) and 0 <= sb["by"] < len(rows) and isinstance(sb.get("reason"), str)
                    and isinstance(sb.get("session"), int)):
                raise Refuse("snapshot_unverified", {"sid": sid, "reason": "bad superseded_by"})
            out[sid] = {"by": sb["by"], "reason": sb["reason"], "session": sb["session"]}
    return out


def snapshot_name(sha256: str) -> str:
    return "memory_%s.jsonl" % sha256[:12]


def topics_name(sha256: str) -> str:
    return "topics_%s.json" % sha256[:12]


def crosses_name(sha256: str) -> str:
    return "crosses_%s.json" % sha256[:12]


def crosses_bytes(decls: Sequence[dict], bridges: Sequence[dict]) -> bytes:
    """The file a memanswer.v3 snapshot is paired with: the nest declarations [{session, at, topic}] and the bridges [{session, at, qword, phrase}] of the committed sessions, canonical."""
    return (canonical({"bridges": [{"at": b["at"], "phrase": b["phrase"], "qword": b["qword"], "session": b["session"]} for b in bridges],
                       "decls": [{"at": d["at"], "session": d["session"], "topic": d["topic"]} for d in decls]}) + "\n").encode("utf-8")


def _crosses_ok(obj: Any) -> bool:
    return (isinstance(obj, dict) and set(obj) == {"bridges", "decls"}
            and all(isinstance(d, dict) and set(d) == {"at", "session", "topic"} and isinstance(d["at"], int) and isinstance(d["session"], int) and isinstance(d["topic"], str)
                    and 1 <= len(d["topic"]) <= mem.TOPIC_MAX_CHARS for d in obj["decls"])
            and all(isinstance(b, dict) and set(b) == {"at", "phrase", "qword", "session"} and isinstance(b["at"], int) and isinstance(b["session"], int) and isinstance(b["phrase"], str)
                    and isinstance(b["qword"], str) for b in obj["bridges"]))


def crosses_bytes_v4(decls: Sequence[dict], bridges: Sequence[dict], versions: Dict[str, str]) -> bytes:
    """The crosses file of a memanswer.v4 snapshot: crosses_bytes + the versions {shape, qwords, ask} the store's sessions were written with (the index is rebuilt from the snapshot with them)."""
    obj = json.loads(crosses_bytes(decls, bridges).decode("utf-8"))
    obj["versions"] = {"ask": versions["ask"], "qwords": versions["qwords"], "shape": versions["shape"]}
    return (canonical(obj) + "\n").encode("utf-8")


def read_crosses_v4(path) -> Tuple[bytes, List[dict], List[dict], Dict[str, str]]:
    """(bytes, decls, bridges, versions) of a crosses file with versions: its name must be the sha256 of its bytes (`crosses_unverified`), the content canonical, the versions a legal bundle."""
    p = Path(path)
    data = p.read_bytes()
    if p.name != crosses_name(hashlib.sha256(data).hexdigest()):
        raise Refuse("crosses_unverified", {"reason": "the file name is not the sha256 of its bytes"})
    try:
        obj = json.loads(data.decode("utf-8"))
        versions = obj.pop("versions")
        if not (isinstance(versions, dict) and set(versions) == {"ask", "qwords", "shape"} and all(isinstance(v, str) for v in versions.values())):
            raise ValueError("versions")
        mem.check_versions(versions)
        ok = _crosses_ok(obj)
        decls, bridges = obj["decls"], obj["bridges"]
    except (ValueError, KeyError, TypeError, Refuse):
        ok = False
    if not ok or data != crosses_bytes_v4(decls, bridges, versions):
        raise Refuse("crosses_unverified", {"reason": "not the canonical bytes of declarations, bridges and versions"})
    return data, decls, bridges, versions


def read_crosses(path) -> Tuple[bytes, List[dict], List[dict]]:
    """(bytes, decls, bridges) of a crosses file: its name must be the sha256 of its bytes (`crosses_unverified`), the content the canonical form of what it holds."""
    p = Path(path)
    data = p.read_bytes()
    if p.name != crosses_name(hashlib.sha256(data).hexdigest()):
        raise Refuse("crosses_unverified", {"reason": "the file name is not the sha256 of its bytes"})
    try:
        obj = json.loads(data.decode("utf-8"))
        decls, bridges = obj["decls"], obj["bridges"]
        ok = (isinstance(obj, dict) and set(obj) == {"bridges", "decls"} and all(isinstance(d, dict) and set(d) == {"at", "session", "topic"} and isinstance(d["at"], int) and isinstance(d["session"], int)
                                                                                 and isinstance(d["topic"], str) and 1 <= len(d["topic"]) <= mem.TOPIC_MAX_CHARS for d in decls)
              and all(isinstance(b, dict) and set(b) == {"at", "phrase", "qword", "session"} and isinstance(b["at"], int) and isinstance(b["session"], int) and isinstance(b["phrase"], str)
                      and isinstance(b["qword"], str) for b in bridges))
    except (ValueError, KeyError, TypeError):
        ok = False
    if not ok or data != crosses_bytes(decls, bridges):
        raise Refuse("crosses_unverified", {"reason": "not the canonical bytes of a list of declarations and bridges"})
    return data, decls, bridges


def distinct_topics(entries: Sequence[dict]) -> List[str]:
    """The distinct topic texts of the declarations [{session, topic}], first declaration first."""
    out: List[str] = []
    for e in entries:
        if e["topic"] not in out:
            out.append(e["topic"])
    return out


def topics_bytes(entries: Sequence[dict]) -> bytes:
    return (canonical({"topics": [{"session": e["session"], "topic": e["topic"]} for e in entries]}) + "\n").encode("utf-8")


def read_topics(path) -> Tuple[bytes, List[dict]]:
    """The bytes and declarations of a topics file: its name must be the sha256 of its bytes (`topics_unverified`) and every entry {session: int, topic: a plain 1..24 char string}."""
    p = Path(path)
    data = p.read_bytes()
    if p.name != topics_name(hashlib.sha256(data).hexdigest()):
        raise Refuse("topics_unverified", {"reason": "the file name is not the sha256 of its bytes"})
    obj = json.loads(data.decode("utf-8"))
    ents = obj.get("topics") if isinstance(obj, dict) and set(obj) == {"topics"} else None
    if not isinstance(ents, list) or not all(isinstance(e, dict) and set(e) == {"session", "topic"} and isinstance(e["session"], int) and not isinstance(e["session"], bool)
                                             and isinstance(e["topic"], str) and 1 <= len(e["topic"]) <= mem.TOPIC_MAX_CHARS for e in ents):
        raise Refuse("topics_unverified", {"reason": "not a list of {session, topic}"})
    if data != topics_bytes(ents):
        raise Refuse("topics_unverified", {"reason": "not the canonical bytes"})
    return data, ents


def write_snapshot(store_path, topics: bool = False, crosses: bool = False, versions: bool = False) -> dict:
    """`mem snapshot`: verify the store (the chain of every listed session, memory.jsonl against the ledgers), derive H and the supersede marks from the ledgers, write
    `<store>/snapshots/memory_<sha12>.jsonl` (never overwritten with other bytes).  -> {"path", "name", "sha256", "sentences", "superseded", "store_id"}.  An empty store has no
    snapshot (`empty_store`)."""
    store = mem.MemStore(store_path)
    head, rows = store.check()
    if head is None or not rows:
        raise Refuse("empty_store", {"reason": "a store with no committed sentence has nothing to answer from"})
    sup: Dict[int, dict] = {}
    for e in head["sessions"]:
        sup.update(mem.session_supersedes(store.sessions_dir / e["run_id"]))
    data = snapshot_bytes(rows, sup)
    sha = hashlib.sha256(data).hexdigest()
    d = Path(store_path) / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    p = d / snapshot_name(sha)
    if p.exists():
        if p.read_bytes() != data:
            raise Refuse("snapshot_unverified", {"reason": "a file of this name holds other bytes"})
    else:
        mem._atomic_write(p, data)
    out = {"path": str(p), "name": p.name, "sha256": sha, "sentences": len(rows), "superseded": len(sup), "store_id": head["store_id"]}
    if topics:                                          # MEM-fix: the declared topics of the committed sessions, derived from the verified ledgers and paired with the snapshot by a file of their own
        ents: List[dict] = []
        for e in head["sessions"]:
            ents += mem.session_topics(store.sessions_dir / e["run_id"])
        tdata = topics_bytes(ents)
        tp = d / topics_name(hashlib.sha256(tdata).hexdigest())
        if not tp.exists():
            mem._atomic_write(tp, tdata)
        out.update(topics_path=str(tp), topics_name=tp.name, topics=distinct_topics(ents))
    if crosses:                                         # PUB-M6 (memanswer.v3): the nest declarations and the bridges of the committed sessions, from the verified ledgers
        decls: List[dict] = []
        brs: List[dict] = []
        for e in head["sessions"]:
            decls += mem.session_nest_decls(store.sessions_dir / e["run_id"])
            brs += mem.session_bridges(store.sessions_dir / e["run_id"])
        if versions:                                    # memanswer.v4: the versions every committed session recorded (one store, one bundle)
            vs = [mem.session_versions(store.sessions_dir / e["run_id"]) for e in head["sessions"]]
            if not vs or any(v is None or v != vs[0] for v in vs):
                raise Refuse("versions_unverified", {"reason": "the committed sessions of the store do not all record one bundle of shape / qwords / ask versions"})
            cdata = crosses_bytes_v4(decls, brs, vs[0])
        else:
            cdata = crosses_bytes(decls, brs)
        cp = d / crosses_name(hashlib.sha256(cdata).hexdigest())
        if not cp.exists():
            mem._atomic_write(cp, cdata)
        out.update(crosses_path=str(cp), crosses_name=cp.name)
    return out


def read_snapshot(path) -> Tuple[bytes, List[dict]]:
    """The bytes and rows of a snapshot file; its name must be the sha it holds (`snapshot_unverified`), and every row a memory row."""
    p = Path(path)
    data = p.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if p.name != snapshot_name(sha):
        raise Refuse("snapshot_unverified", {"reason": "the file name is not the sha256 of its bytes"})
    rows = [json.loads(ln) for ln in data.decode("utf-8").splitlines() if ln.strip()]
    mg.check_memory_rows(rows)
    superseded_of_rows(rows)
    return data, rows


# ------------------------------------------------------------------------------------------------------------
# the run
# ------------------------------------------------------------------------------------------------------------
class AnswerRun(Run):
    """A loom `Run` over a memory snapshot.  Prose, record_only, tier WORD, the evidence gate (`evidence_profile` of its begin row: evidence.v2 for a stored run, `memrecall.MEM_GATE_VERSION` for a new one) / scope clause; + `recall`, + abstain `contested`; `weave_span` refuses a
    superseded sentence.  Everything else (lookup, read_sentence, weave_span, drop, read, emit, abstain, status, the hand-seating ops) is the loom's own code."""
    EXTRA_OPS = ("recall",)
    ABSTAIN = ANSWER_ABSTAIN

    def __init__(self, corpus: Corpus, rows: Sequence[dict], store_id: str, snapshot_name_: str, question: str, model: str, run_id: str,
                 topics: Optional[Sequence[str]] = None, topics_file: Optional[str] = None, crosses: Optional[Tuple[str, Sequence[dict], Sequence[dict]]] = None,
                 evidence: Optional[Tuple[str, str]] = None, versions: Optional[Dict[str, str]] = None) -> None:
        mg.check_memory_rows(rows)
        task = {"task_id": ANSWER_TASK_ID, "text": question, "lang": "prose", "mode": "record_only", "tiers": ["WORD"]}
        super().__init__(corpus, task, model, run_id, DEFAULT_STABILITY, None, None, notelib.NOTES_VERSION, tuple(evidence if evidence is not None else ANSWER_EVIDENCE))
        self.rows = list(rows)
        self.store_id = store_id
        self.snapshot = snapshot_name_
        self.superseded = superseded_of_rows(self.rows)
        self.recalls = 0
        self.v2 = topics is not None                      # memanswer.v2: the declared topics are known (possibly none: a store whose sessions declared none)
        self.topics: Tuple[str, ...] = tuple(topics or ())
        self.topics_file = topics_file
        self.v3 = crosses is not None                     # memanswer.v3: recall reads the memory crosses of a mem.v4 store (memanswer.v4 too)
        self.v4 = versions is not None                    # memanswer.v4: + the store's versions, `bridge`, weave_span.v4, contested_value
        if self.v4 and not self.v3:
            raise ValueError("memanswer.v4 reads the memory crosses")
        self.versions: Dict[str, str] = mem.check_versions(versions) if self.v4 else dict(mem.V4_VERSIONS_V2)
        self.run_bridges: List[mx.Bridge] = []            # memanswer.v4: the bridges the model confirmed in this run (the ledger is their source: replay re-executes the rows)
        if self.v4:
            self.weave_wv = ops.WEAVE_SPAN_V4
        self.single_spans: List[Tuple[int, int, int]] = []              # (sid, first, last) of every occurrence a recall with ONE answer (ANSWER / UPDATED) returned
        self.single_norms: List[str] = []
        self.contested_spans: List[Tuple[int, int, int]] = []           # ... of a same-seat CHOICE of >= 2 sources (memanswer.v4: an emit of one of them is refused)
        self.contested_norms: List[str] = []
        self.crosses_file: Optional[str] = None if crosses is None else crosses[0]
        self.decls: List[dict] = [] if crosses is None else [dict(d) for d in crosses[1]]
        self.bridges: List[dict] = [] if crosses is None else [dict(b) for b in crosses[2]]
        self._index: Optional[mx.MemIndex] = None
        self.live_spans: List[Tuple[int, int, int]] = []                 # (sid, first unit, last unit) of every live occurrence the recalls of this run returned
        self.hist_spans: List[Tuple[int, int, int]] = []                 # ... of every replaced (history) occurrence
        self.live_norms: List[str] = []                                  # the normalised live / replaced values
        self.hist_norms: List[str] = []
        self.completions: Dict[Tuple[int, int, int], dict] = {}          # (sid, first, last) -> the question the gate may be handed for that stretch (memask.completions)

    def index(self) -> "mx.MemIndex":
        """The memory crosses of the snapshot (memanswer.v3): the full rebuild `build_index` over its rows, the nest declarations and the bridges of its crosses file (cached by the names of both files:
        a pure function of the bytes)."""
        if self._index is None:
            key = (self.snapshot, self.crosses_file)
            ix = _INDEX_CACHE.get(key)
            if ix is None:
                ix = _INDEX_CACHE[key] = mx.build_index(self.rows, self.decls, self.superseded, shape_version=self.versions["shape"], bridges=self.bridges)
            self._index = ix
        return self._index

    def begin_body(self) -> dict:
        b = super().begin_body()
        res = b["result"]
        res["rules"] = dict(res["rules"], **dict(ANSWER_RULES, abstain=list(ANSWER_ABSTAIN)))
        res["mem_answer"] = {"version": ANSWER_V2 if self.v2 else ANSWER_VERSION, "store_id": self.store_id, "snapshot": self.snapshot, "sentences": len(self.rows),
                             "superseded": sorted(self.superseded), "recall_cap": RECALL_CAP, "hook": mr.GATE_SUBJECT_HOOK_ID}
        if self.v2:
            res["mem_answer"].update(topics=list(self.topics), topics_file=self.topics_file, forms=mr.FORMS_VERSION)
            res["rules"] = dict(res["rules"], recall=ANSWER_RULES_V2["recall"])
        if self.v3:
            res["mem_answer"]["version"] = ANSWER_V3
            res["mem_answer"].update(crosses_file=self.crosses_file, ask=mask.ASK_VERSION, cross=mx.CROSS_VERSION, guard=GUARD_V3, complete=mask.COMPLETE_VERSION)
            res["rules"] = dict(res["rules"], recall=ANSWER_RULES_V3["recall"])
        if self.v4:
            res["mem_answer"]["version"] = ANSWER_V4
            res["mem_answer"].update(ask=self.versions["ask"], qwords=self.versions["qwords"], shape=self.versions["shape"], guard=GUARD_V4, readout=ops.WEAVE_SPAN_V4, bridge_cap=BRIDGE_CAP,
                                     evidence=self.evidence[0])
            res["rules"] = dict(res["rules"], recall=ANSWER_RULES_V4["recall"], bridge=ANSWER_RULES_V4["bridge"])
        res["tools"] = list(ANSWER_TOOLS_V4 if self.v4 else ANSWER_TOOLS)
        return b

    def _executable(self, op: Any) -> bool:
        return super()._executable(op) or (self.v4 and op == "bridge")

    def _handler(self, op: str):
        if op == "recall":
            return _h_recall
        if op == "bridge":
            return _h_bridge
        if op == "weave_span":
            return _h_weave_span
        if op == "emit" and self.v3:
            return _h_emit_v3
        return super()._handler(op)

    def _precheck(self, op: str) -> None:
        if op == "bridge":
            st = self.state
            if st.closed is not None:
                st.guards["closed_calls"] += 1
                raise Refuse("run_closed", {"closed": list(st.closed)})
            if len(self.run_bridges) >= BRIDGE_CAP:
                raise Refuse("bridge_cap", {"limit": BRIDGE_CAP})
            return
        if op == "recall":
            st = self.state
            if st.closed is not None:
                st.guards["closed_calls"] += 1
                raise Refuse("run_closed", {"closed": list(st.closed)})
            if self.recalls >= RECALL_CAP:
                raise Refuse("recall_cap", {"limit": RECALL_CAP})
            self.recalls += 1
            return
        super()._precheck(op)


_INDEX_CACHE: Dict[Tuple[str, Optional[str]], "mx.MemIndex"] = {}      # (snapshot name, crosses file name) -> its index: a pure cache


def _h_recall(run: AnswerRun, a: dict, i: int) -> dict:
    a = ops._args(a, {"question": (str, True)})
    q = unicodedata.normalize("NFC", a["question"])
    if not 1 <= len(q) <= ARG_STR_CAP or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in q):
        raise Refuse("bad_question", {"reason": "1 to %d characters, no newline / NUL / control character" % ARG_STR_CAP})
    mg.check_memory_rows(run.rows)
    if run.v3:
        ix = run.index()
        res = mask.recall(ix, run.rows, run.corpus, q, ask=run.versions["ask"], bridges=tuple(ix.bridges) + tuple(run.run_bridges)) if run.v4 else mask.recall(ix, run.rows, run.corpus, q)
        res.update(ok=True, text=q)
        _note_recall(run, res, q)
        return res
    turns = {k: r["turn"] for k, r in enumerate(run.rows) if "turn" in r}
    res = mr.recall(run.corpus, q, run.evidence[0], subject_guard=True, superseded=run.superseded or None, turns=turns or None, topics=run.topics or None)
    res.update(ok=True, text=q)
    return res


def _h_bridge(run: AnswerRun, a: dict, i: int) -> dict:
    """memanswer.v4: bridge(question_phrase, memory_phrase) -- the model confirms that a part of the question means a phrase of the memory (a candidate of `recall`, or a centre the memory holds).  A
    CONSTRUCTED, marked entry that the next `recall` of this run uses (route `bridge`); nothing in the memory changes.  Refused: bad_bridge, unknown_phrase, bridge_exists, bridge_cap, run_closed."""
    a = ops._args(a, {"question_word": (str, False), "question_phrase": (str, False), "memory_phrase": (str, True)})
    if ("question_word" in a) == ("question_phrase" in a):
        raise Refuse("bad_args", {"field": "question_phrase", "reason": "give question_phrase (or question_word), not both and not neither"})
    qwd = mem._plain_text(a["question_word"] if "question_word" in a else a["question_phrase"], "question_phrase", 1, 24, "bad_bridge")
    ph = mem._plain_text(a["memory_phrase"], "memory_phrase", 1, 40, "bad_bridge")
    if qwd == ph:
        raise Refuse("bad_bridge", {"field": "memory_phrase", "reason": "the question phrase and the memory phrase are the same"})
    ix = run.index()
    positions = ix.positions_text(ph)
    if not positions and not any(ix.cross(t, ph) is not None for t in mx.TANKS):
        raise Refuse("unknown_phrase", {"memory_phrase": ph, "reason": "no cross of the memory has this phrase as its centre and no position has it as its phrase: give it as a candidate of recall shows it"})
    if any(b.qword == qwd and b.phrase == ph for b in tuple(ix.bridges) + tuple(run.run_bridges)):
        raise Refuse("bridge_exists", {"question_word": qwd, "memory_phrase": ph})
    at = len(run.rows)
    run.run_bridges.append(mx.Bridge(qwd, ph, 0, at))
    return {"ok": True, "question_word": qwd, "memory_phrase": ph, "origin": "constructed", "at": at, "positions": len(positions), "bridges": len(run.run_bridges)}


def _spans_of(groups: Sequence[dict]) -> Tuple[List[Tuple[int, int, int]], List[str]]:
    spans: List[Tuple[int, int, int]] = []
    norms: List[str] = []
    for g in groups:
        for a in g["answers"]:
            n = mn.norm_answer(a)
            if n not in norms:
                norms.append(n)
        for o in g["occurrences"]:
            if o.get("span"):
                k = (o["sid"], o["span"][0], o["span"][1])
                if k not in spans:
                    spans.append(k)
    return spans, norms


def _note_recall(run: AnswerRun, res: dict, question: str) -> None:
    """What the recalls of this run returned, for the guards of `weave_span` (a replaced value is never a quote) and the completions of `emit`.  A pure function of the recall results, which the replay
    re-executes, so it is the same on replay."""
    sp, nr = _spans_of(res.get("answers", ()))
    for k in sp:
        if k not in run.live_spans:
            run.live_spans.append(k)
    for n in nr:
        if n not in run.live_norms:
            run.live_norms.append(n)
    if run.v4:                                         # memanswer.v4: which values a recall returned ALONE, and which only as one side of a contradiction (same seat, >= 2 sentences)
        if res.get("verdict") in ("ANSWER", "UPDATED"):
            for k in sp:
                if k not in run.single_spans:
                    run.single_spans.append(k)
            for n in nr:
                if n not in run.single_norms:
                    run.single_norms.append(n)
        elif res.get("verdict") == "CHOICE" and res.get("choice_kind") == "same_seat" and res.get("sources", 0) >= 2:
            for k in sp:
                if k not in run.contested_spans:
                    run.contested_spans.append(k)
            for n in nr:
                if n not in run.contested_norms:
                    run.contested_norms.append(n)
    hsp, hnr = _spans_of(res.get("history", ()))
    for k in hsp:
        if k not in run.hist_spans:
            run.hist_spans.append(k)
    for n in hnr:
        if n not in run.hist_norms:
            run.hist_norms.append(n)
    for c in mask.completions(run.index(), res, question):
        run.completions.setdefault((c["sid"], c["span"][0], c["span"][1]), c)


def _weave_target(run: AnswerRun, a: Any) -> Optional[Tuple[int, str, int, int]]:
    """(sid, tier, first unit, last unit) of a well-formed weave_span call, else None (the loom's own refusal then says what is wrong)."""
    try:
        if not isinstance(a, dict) or not isinstance(a.get("sid"), int) or isinstance(a.get("sid"), bool) or not 0 <= a["sid"] < run.corpus.n_sentences or a.get("tier") != "WORD":
            return None
        units = list(run.corpus.tier("WORD").sentence_units[a["sid"]])
        i0 = ops._unit_index(units, a["from"], "from")
        i1 = ops._unit_index(units, a["to"], "to", i0)
    except (Refuse, KeyError, TypeError):
        return None
    return (a["sid"], "WORD", i0, i1) if i0 <= i1 else None


def _h_weave_span(run: AnswerRun, a: dict, i: int) -> dict:
    sid = a.get("sid") if isinstance(a, dict) else None
    if isinstance(sid, int) and not isinstance(sid, bool) and sid in run.superseded:
        s = run.superseded[sid]
        raise Refuse("superseded_sentence", {"sid": sid, "by": s["by"], "reason": s["reason"], "hint": "history is not a quote: weave the sentence that replaced it"})
    if run.v3:
        tg = _weave_target(run, a)
        if tg is not None:
            joiners = run.v4 and (a.get("wv", run.weave_wv) == ops.WEAVE_SPAN_V4)        # weave_span.v4 reads the joiners . , - : / out as the source has them
            readout, source, verbatim = mask.quote_check(run.corpus, tg[0], tg[2], tg[3], None, joiners)
            if not verbatim:                      # PUB-M6b (L-PUB-54): an emit is the READ-OUT of the thread, which has no punctuation: 「v2.4」 would be emitted as 「v24」, a value nobody wrote
                raise Refuse("quote_not_verbatim", {"sid": tg[0], "source": source[:64], "readout": readout[:64],
                                                    "hint": "the loom reads this stretch out without its punctuation, so emitting it would change the value: abstain (cannot_weave)"})
            n = mn.norm_answer(source)
            key = (tg[0], tg[2], tg[3])
            if (key in run.hist_spans and key not in run.live_spans) or (n in run.hist_norms and n not in run.live_norms):
                raise Refuse("replaced_value", {"sid": tg[0], "text": source[:64], "hint": "the memory replaced this value (recall `history`): only the latest value is a quote"})
    return ops.h_weave_span(run, a, i)


def _h_emit_v3(run: AnswerRun, a: dict, i: int) -> dict:
    """`emit` of a memanswer.v3 run: the loom's own emit, and, only when the evidence gate refuses the quote against the question as asked, ONE more judgement of the SAME gate (evidence.py unchanged)
    against the question the recall named for that very stretch (`memask.completions`; PUB-M6b, OP-PUB-4): the question completed by the centre of the nest the value was reached through
    (`via: nest`), or the form of the change for the new value of a change clause at the question's own position (`via: update`).  The completion is recorded on the emit row; a refusal says what the
    completed question was refused for (`completion`)."""
    ops._args(a, {})
    if run.v4:                                                                                  # memanswer.v4: one side of a contradiction is no answer (owner 2026-10-13 「片方だけは拒否する」)
        for wv in evl.intact_weaves(run).values():
            key = (wv["sid"], wv["i0"], wv["i1"])
            _r, source, _v = mask.quote_check(run.corpus, wv["sid"], wv["i0"], wv["i1"], None, True)
            n = mn.norm_answer(source)
            if (key in run.contested_spans and key not in run.single_spans) or (n in run.contested_norms and n not in run.single_norms):
                raise Refuse("contested_value", {"sid": wv["sid"], "text": source[:64], "hint": "recall returned this value as one side of a CHOICE (the memory states two answers at one place): abstain(type=contested)"})
    ev = rd.evaluate(run)
    used: Optional[dict] = None
    tried: Optional[dict] = None
    intact = evl.intact_weaves(run) if ev["refusals"] else {}
    if ev["refusals"] and len(ev["refusals"]) == 1 and ev["refusals"][0]["type"] == "no_evidence" and len(intact) == 1:
        wv = next(iter(intact.values()))
        comp = run.completions.get((wv["sid"], wv["i0"], wv["i1"]))
        if comp is not None:
            saved = run.question_units
            run.question_units = evl.question_units(comp["question"])
            try:
                ev2 = rd.evaluate(run)
            finally:
                run.question_units = saved
            if not ev2["refusals"]:
                ev, used = ev2, comp
            else:
                codes: List[str] = []
                for rf in ev2["refusals"]:
                    for w in rf.get("weaves", []):
                        for c in w.get("codes", []):
                            if c not in codes:
                                codes.append(c)
                tried = {"via": comp["via"], "question": comp["question"], "codes": codes}
    if ev["refusals"]:
        detail: Dict[str, Any] = {"refusals": ev["refusals"], "stability": ev["stability"]}
        if tried is not None:
            detail["completion"] = tried
        raise Refuse(ev["refusals"][0]["type"], detail)
    run.state.closed = ["emitted", ev["output_sha"]]
    out: Dict[str, Any] = {"ok": True, "status": "emitted", "text": ev["text"], "annotated": ev["annotated"], "output_sha": ev["output_sha"], "shares": ev["shares"], "stability": ev["stability"]}
    if run.evidence is not None:
        out.update(ev=run.evidence[0], evidence=ev["evidence"])
    if used is not None:
        out["via"] = used["via"]
        out["completed_question"] = used["question"]
        out["position"] = used["position"]
        if used["via"] == "nest":
            out["nest"] = used["nest"]
    return out


# ------------------------------------------------------------------------------------------------------------
# the session (the door: one call = one ledger row)
# ------------------------------------------------------------------------------------------------------------
def answers_dir(store_path) -> Path:
    return Path(store_path) / "answers"


class AnswerSession:
    """An open answer run: `call(tool, args)` executes one op, appends exactly one row (a refused call too) and, after a read / emit / weave with notes, the `loom_note` row;
    `harness(op, args)` appends a row that is not the model's.  No lock is taken on the store: an answer run only READS the snapshot it was begun on."""

    def __init__(self, store_path, question: str, model: str, run_id: Optional[str] = None, snapshot: Optional[dict] = None, answer_version: str = ANSWER_VERSION,
                 evidence: Optional[Tuple[str, str]] = None) -> None:
        if not isinstance(question, str) or not 1 <= len(question) <= 256 or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in question):
            raise Refuse("bad_question", {"reason": "1 to 256 characters, no control character"})
        if not isinstance(model, str) or not mem._MODEL_RX.match(model):
            raise Refuse("bad_model_id", {"reason": "1 to 64 printable characters"})
        if answer_version not in ANSWER_VERSIONS:
            raise Refuse("bad_answer_version", {"allowed": list(ANSWER_VERSIONS)})
        want_topics = answer_version == ANSWER_V2
        want_crosses = answer_version in (ANSWER_V3, ANSWER_V4)
        want_versions = answer_version == ANSWER_V4
        snap = snapshot if snapshot is not None else write_snapshot(store_path, topics=want_topics, crosses=want_crosses, versions=want_versions)
        if want_topics and "topics_name" not in snap:                 # a snapshot handed in without its topics file is refused, never replaced by a fresh snapshot of the store as it is now
            raise Refuse("snapshot_without_topics", {"reason": "memanswer.v2 needs the snapshot dict of write_snapshot(store, topics=True)", "snapshot": snap.get("name")})
        if want_crosses and "crosses_name" not in snap:
            raise Refuse("snapshot_without_crosses", {"reason": "memanswer.v3 needs the snapshot dict of write_snapshot(store, crosses=True)", "snapshot": snap.get("name")})
        data, rows = read_snapshot(snap["path"])
        crosses = None
        versions = None
        if want_versions:
            _, cdecls, cbridges, versions = read_crosses_v4(snap["crosses_path"])
            crosses = (snap["crosses_name"], cdecls, cbridges)
        elif want_crosses:
            _, cdecls, cbridges = read_crosses(snap["crosses_path"])
            crosses = (snap["crosses_name"], cdecls, cbridges)
        topics = topics_file = None
        if want_topics:
            _, tents = read_topics(snap["topics_path"])
            topics, topics_file = distinct_topics(tents), snap["topics_name"]
        self.store_path = Path(store_path)
        d = answers_dir(store_path)
        d.mkdir(parents=True, exist_ok=True)
        if run_id is None:
            k = 1
            while (d / ("a%04d" % k)).exists():
                k += 1
            run_id = "a%04d" % k
        if not _RUN_RX.match(run_id) or (d / run_id).exists():
            raise Refuse("bad_run_id", {"run_id": run_id})
        self.run = AnswerRun(Corpus(data), rows, snap["store_id"], snap["name"], question, model, run_id, topics, topics_file, crosses, evidence, versions)
        self.ledger = lg.Ledger(d / run_id)
        meta = {"store": snap["store_id"], "mode": "memory_answer", "snapshot": snap["name"], "corpus_sha": hashlib.sha256(data).hexdigest()}
        if want_topics:
            meta["topics"] = topics_file
        if want_crosses:
            meta["crosses"] = snap["crosses_name"]
        self.ledger.create(meta)
        self.t0 = time.monotonic_ns()
        with self.ledger.locked() as lk:
            self.run.advance(lk.append(self.run.begin_body(), 0))
        self.begin_result: dict = lg._parse_line(lg.read_raw_lines(self.ledger.dir)[0][0])["result"]

    @property
    def run_id(self) -> str:
        return self.run.run_id

    def call(self, tool: Any, args: Any = None) -> dict:
        args = json.loads(canonical({} if args is None else args))
        if tool == "weave_span" and isinstance(args, dict):        # the model's names are first / last (inclusive); the ledger stores from / to (L-LOOM-145), as the loom's one door does
            for door, stored in (("first", "from"), ("last", "to")):
                if door in args:
                    if stored in args:
                        return refusal("bad_args", {"field": door, "reason": "give %s, not %s as well" % (door, stored)})
                    args[stored] = args.pop(door)
        with self.ledger.locked() as lk:
            body = self.run.step("model", tool, args)
            row = lk.append(body, time.monotonic_ns() - self.t0)
            self.run.advance(row)
            result = body["result"]
            notes = self.run.notes_due()
            if notes:
                self.run.advance(lk.append(self.run.step(notelib.NOTE_ACTOR, notelib.NOTE_OP, {}), time.monotonic_ns() - self.t0))
                result = dict(result, notes=notes)                  # a copy: the stored row never holds the notes (they are in the note row)
        return result

    def harness(self, op: str, args: dict) -> dict:
        with self.ledger.locked() as lk:
            body = self.run.step("harness", op, json.loads(canonical(args)))
            self.run.advance(lk.append(body, time.monotonic_ns() - self.t0))
        return body["result"]

    def closed(self) -> Optional[List[str]]:
        c = self.run.state.closed
        return None if c is None else list(c)


# ------------------------------------------------------------------------------------------------------------
# replay and verify
# ------------------------------------------------------------------------------------------------------------
def replay_answer(run_dir, store_path=None) -> ReplayResult:
    """Re-execute an answer run from its snapshot file (`<store>/snapshots/`, the store being two folders above the run unless given) and require every row to be reproduced."""
    out = ReplayResult()
    run_dir = Path(run_dir)
    store_path = Path(store_path) if store_path is not None else run_dir.parent.parent
    lines, unterminated = lg.read_raw_lines(run_dir)
    out.n_rows = len(lines)
    try:
        rows = [lg._parse_line(ln) for ln in lines]
        r0 = rows[0]
        res0 = r0["result"]
        ma = res0["mem_answer"]
        model, run_id, question = r0["args"]["model"], res0["run_id"], res0["task"]["text"]
        recorded_header = res0["header"]
        if r0.get("op") != "begin" or ma.get("version") not in ANSWER_VERSIONS:
            raise ValueError("version")
    except Exception:
        out.status, out.first_diff = "DIFFERS", {"i": 0, "field": "result"}
        return out
    snap = store_path / "snapshots" / str(ma["snapshot"])
    if not re.fullmatch(r"memory_[0-9a-f]{12}\.jsonl", str(ma["snapshot"])) or not snap.is_file():
        out.status, out.mismatch = "INPUTS", "snapshot_missing"
        return out
    try:
        data, srows = read_snapshot(snap)
    except Refuse:
        out.status, out.mismatch = "INPUTS", "snapshot_unverified"
        return out
    except (OSError, ValueError, KeyError, UnicodeDecodeError):
        out.status, out.mismatch = "INPUTS", "snapshot_unreadable"
        return out
    topics = topics_file = None
    if ma["version"] == ANSWER_V2:                       # the topics are read from the file the begin row names and must be what the begin row recorded
        tf = str(ma.get("topics_file"))
        tp = store_path / "snapshots" / tf
        if not re.fullmatch(r"topics_[0-9a-f]{12}\.json", tf) or not tp.is_file():
            out.status, out.mismatch = "INPUTS", "topics_missing"
            return out
        try:
            _, tents = read_topics(tp)
        except (Refuse, OSError, ValueError, KeyError, UnicodeDecodeError):
            out.status, out.mismatch = "INPUTS", "topics_unverified"
            return out
        topics, topics_file = distinct_topics(tents), tf
        if ma.get("topics") != topics:
            out.status, out.mismatch = "INPUTS", "topics_unverified"
            return out
    crosses = None
    versions = None
    if ma["version"] in (ANSWER_V3, ANSWER_V4):          # the crosses file the begin row names (nest declarations + bridges, memanswer.v4: + versions) must be there and be what its name says
        cf = str(ma.get("crosses_file"))
        cp = store_path / "snapshots" / cf
        if not re.fullmatch(r"crosses_[0-9a-f]{12}\.json", cf) or not cp.is_file():
            out.status, out.mismatch = "INPUTS", "crosses_missing"
            return out
        try:
            if ma["version"] == ANSWER_V4:
                _, cdecls, cbridges, versions = read_crosses_v4(cp)
            else:
                _, cdecls, cbridges = read_crosses(cp)
        except (Refuse, OSError, ValueError, KeyError, UnicodeDecodeError):
            out.status, out.mismatch = "INPUTS", "crosses_unverified"
            return out
        crosses = (cf, cdecls, cbridges)
    ep = res0.get("evidence_profile")                    # the gate the run was recorded with (a run before PUB-M6c: evidence.v2)
    evidence = (ep["version"], ep["subject_scope"]) if isinstance(ep, dict) and "version" in ep and "subject_scope" in ep else LEGACY_EVIDENCE
    try:
        run = AnswerRun(Corpus(data), srows, str(ma["store_id"]), str(ma["snapshot"]), question, model, run_id, topics, topics_file, crosses, evidence, versions)
    except (Refuse, ValueError):
        out.status, out.mismatch = "INPUTS", "snapshot_unverified"
        return out
    mm = lg.header_mismatch(recorded_header, run.header())
    if mm is not None:
        out.status, out.mismatch = "INPUTS", mm
        return out
    out.run = run
    run.replaying = True
    try:
        lg._replay_rows(out, run, rows, lines, unterminated)
    finally:
        run.replaying = False
    return out


def verify_answer(run_dir, store_path=None, head: Optional[str] = None) -> dict:
    """The chain (TAMPERED / TORN_TAIL / HEAD_MISMATCH), then the replay (REPLAY_DIFFERS / REPLAY_INPUTS_MISMATCH), then OK."""
    chain = lg.verify_chain(run_dir, head)
    if chain["status"] != "OK":
        return chain
    rep = replay_answer(run_dir, store_path)
    chain["replay"] = rep.to_obj()
    if rep.status == "INPUTS":
        chain["status"] = "REPLAY_INPUTS_MISMATCH"
    elif rep.status == "DIFFERS":
        chain["status"] = "REPLAY_DIFFERS"
    return chain


def answer_output(run_dir, store_path=None) -> dict:
    """What an answer run produced, from the VERIFIED ledger only: {"status": "emitted", "text"} | {"status": "abstained", "type", "recalls": [...]} | {"status": "open"}
    | {"status": "run_not_verified"}.  An abstention `contested` carries the CHOICE the last recall returned (its answer texts), the mechanical "CHOICE holding both"."""
    v = verify_answer(run_dir, store_path)
    if v["status"] != "OK":
        return {"status": "run_not_verified", "verify": v["status"]}
    lines, _ = lg.read_lines(run_dir)
    rows = [json.loads(ln) for ln in lines]
    recalls = [{"question": r["result"]["text"], "verdict": r["result"]["verdict"], "answers": [g["answers"] for g in r["result"]["answers"]]}
               for r in rows if r["actor"] == "model" and r["op"] == "recall" and r["result"].get("ok") is True]
    for r in rows:
        if r["actor"] == "model" and r["op"] == "emit" and r["result"].get("ok") is True:
            out = {"status": "emitted", "text": r["result"]["text"], "output_sha": r["result"]["output_sha"], "recalls": recalls}
            if "via" in r["result"]:                                                  # PUB-M6b: the value was judged against a completed question (nest) or the form of a change (update)
                out.update(via=r["result"]["via"], completed_question=r["result"]["completed_question"])
                if "nest" in r["result"]:
                    out["nest"] = r["result"]["nest"]
            return out
        if r["actor"] == "model" and r["op"] == "abstain" and r["result"].get("ok") is True:
            return {"status": "abstained", "type": r["result"]["type"], "recalls": recalls}
    return {"status": "open", "recalls": recalls}
