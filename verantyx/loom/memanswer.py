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
from verantyx.loom import memguard as mg
from verantyx.loom import memory as mem
from verantyx.loom import memrecall as mr
from verantyx.loom import notes as notelib
from verantyx.loom import ops
from verantyx.loom.corpus import Corpus
from verantyx.loom.ledger import ReplayResult
from verantyx.loom.ops import Run, refusal
from verantyx.loom.read import DEFAULT_STABILITY
from verantyx.loom.state import ABSTAIN_TYPES, ARG_STR_CAP, Refuse, canonical, sha256_text

ANSWER_VERSION = "memanswer.v1"
ANSWER_V2 = "memanswer.v2"          # MEM-fix (L-MEM-59 / 60): the answer run holds the store's declared topics (read from a file the snapshot is paired with) and `recall` reads the question in its other forms
ANSWER_VERSIONS: Tuple[str, ...] = (ANSWER_VERSION, ANSWER_V2)
ANSWER_TASK_ID = "answer"
ANSWER_EVIDENCE = (evl.EVIDENCE_V2, evl.SCOPE_CLAUSE)          # the gate of every memory use: evidence.v2, scope clause (L-MEM-12)
RECALL_CAP = 20
ANSWER_ABSTAIN: Tuple[str, ...] = ABSTAIN_TYPES + ("contested",)
ANSWER_TOOLS: Tuple[str, ...] = ("recall", "lookup", "read_sentence", "weave_span", "drop", "read", "emit", "abstain", "status")     # what the model is offered
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


def write_snapshot(store_path, topics: bool = False) -> dict:
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
    """A loom `Run` over a memory snapshot.  Prose, record_only, tier WORD, the evidence gate evidence.v2 / scope clause; + `recall`, + abstain `contested`; `weave_span` refuses a
    superseded sentence.  Everything else (lookup, read_sentence, weave_span, drop, read, emit, abstain, status, the hand-seating ops) is the loom's own code."""
    EXTRA_OPS = ("recall",)
    ABSTAIN = ANSWER_ABSTAIN

    def __init__(self, corpus: Corpus, rows: Sequence[dict], store_id: str, snapshot_name_: str, question: str, model: str, run_id: str,
                 topics: Optional[Sequence[str]] = None, topics_file: Optional[str] = None) -> None:
        mg.check_memory_rows(rows)
        task = {"task_id": ANSWER_TASK_ID, "text": question, "lang": "prose", "mode": "record_only", "tiers": ["WORD"]}
        super().__init__(corpus, task, model, run_id, DEFAULT_STABILITY, None, None, notelib.NOTES_VERSION, ANSWER_EVIDENCE)
        self.rows = list(rows)
        self.store_id = store_id
        self.snapshot = snapshot_name_
        self.superseded = superseded_of_rows(self.rows)
        self.recalls = 0
        self.v2 = topics is not None                      # memanswer.v2: the declared topics are known (possibly none: a store whose sessions declared none)
        self.topics: Tuple[str, ...] = tuple(topics or ())
        self.topics_file = topics_file

    def begin_body(self) -> dict:
        b = super().begin_body()
        res = b["result"]
        res["rules"] = dict(res["rules"], **dict(ANSWER_RULES, abstain=list(ANSWER_ABSTAIN)))
        res["mem_answer"] = {"version": ANSWER_V2 if self.v2 else ANSWER_VERSION, "store_id": self.store_id, "snapshot": self.snapshot, "sentences": len(self.rows),
                             "superseded": sorted(self.superseded), "recall_cap": RECALL_CAP, "hook": mr.GATE_SUBJECT_HOOK_ID}
        if self.v2:
            res["mem_answer"].update(topics=list(self.topics), topics_file=self.topics_file, forms=mr.FORMS_VERSION)
            res["rules"] = dict(res["rules"], recall=ANSWER_RULES_V2["recall"])
        res["tools"] = list(ANSWER_TOOLS)
        return b

    def _handler(self, op: str):
        if op == "recall":
            return _h_recall
        if op == "weave_span":
            return _h_weave_span
        return super()._handler(op)

    def _precheck(self, op: str) -> None:
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


def _h_recall(run: AnswerRun, a: dict, i: int) -> dict:
    a = ops._args(a, {"question": (str, True)})
    q = unicodedata.normalize("NFC", a["question"])
    if not 1 <= len(q) <= ARG_STR_CAP or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in q):
        raise Refuse("bad_question", {"reason": "1 to %d characters, no newline / NUL / control character" % ARG_STR_CAP})
    mg.check_memory_rows(run.rows)
    turns = {k: r["turn"] for k, r in enumerate(run.rows) if "turn" in r}
    res = mr.recall(run.corpus, q, evl.EVIDENCE_V2, subject_guard=True, superseded=run.superseded or None, turns=turns or None, topics=run.topics or None)
    res.update(ok=True, text=q)
    return res


def _h_weave_span(run: AnswerRun, a: dict, i: int) -> dict:
    sid = a.get("sid") if isinstance(a, dict) else None
    if isinstance(sid, int) and not isinstance(sid, bool) and sid in run.superseded:
        s = run.superseded[sid]
        raise Refuse("superseded_sentence", {"sid": sid, "by": s["by"], "reason": s["reason"], "hint": "history is not a quote: weave the sentence that replaced it"})
    return ops.h_weave_span(run, a, i)


# ------------------------------------------------------------------------------------------------------------
# the session (the door: one call = one ledger row)
# ------------------------------------------------------------------------------------------------------------
def answers_dir(store_path) -> Path:
    return Path(store_path) / "answers"


class AnswerSession:
    """An open answer run: `call(tool, args)` executes one op, appends exactly one row (a refused call too) and, after a read / emit / weave with notes, the `loom_note` row;
    `harness(op, args)` appends a row that is not the model's.  No lock is taken on the store: an answer run only READS the snapshot it was begun on."""

    def __init__(self, store_path, question: str, model: str, run_id: Optional[str] = None, snapshot: Optional[dict] = None, answer_version: str = ANSWER_VERSION) -> None:
        if not isinstance(question, str) or not 1 <= len(question) <= 256 or any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in question):
            raise Refuse("bad_question", {"reason": "1 to 256 characters, no control character"})
        if not isinstance(model, str) or not mem._MODEL_RX.match(model):
            raise Refuse("bad_model_id", {"reason": "1 to 64 printable characters"})
        if answer_version not in ANSWER_VERSIONS:
            raise Refuse("bad_answer_version", {"allowed": list(ANSWER_VERSIONS)})
        want_topics = answer_version == ANSWER_V2
        snap = snapshot if snapshot is not None else write_snapshot(store_path, topics=want_topics)
        if want_topics and "topics_name" not in snap:                 # a snapshot handed in without its topics file is refused, never replaced by a fresh snapshot of the store as it is now
            raise Refuse("snapshot_without_topics", {"reason": "memanswer.v2 needs the snapshot dict of write_snapshot(store, topics=True)", "snapshot": snap.get("name")})
        data, rows = read_snapshot(snap["path"])
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
        self.run = AnswerRun(Corpus(data), rows, snap["store_id"], snap["name"], question, model, run_id, topics, topics_file)
        self.ledger = lg.Ledger(d / run_id)
        meta = {"store": snap["store_id"], "mode": "memory_answer", "snapshot": snap["name"], "corpus_sha": hashlib.sha256(data).hexdigest()}
        if want_topics:
            meta["topics"] = topics_file
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
    try:
        run = AnswerRun(Corpus(data), srows, str(ma["store_id"]), str(ma["snapshot"]), question, model, run_id, topics, topics_file)
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
            return {"status": "emitted", "text": r["result"]["text"], "output_sha": r["result"]["output_sha"], "recalls": recalls}
        if r["actor"] == "model" and r["op"] == "abstain" and r["result"].get("ok") is True:
            return {"status": "abstained", "type": r["result"]["type"], "recalls": recalls}
    return {"status": "open", "recalls": recalls}
