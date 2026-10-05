"""W16-t2: the ONE function that answers from documents (docs/OBSERVATION.md, W16-t2). `vera ask --mode round5 --document`, `vera chat --mode round5` and `vera serve`
(decode_grammar.read_turn) all call `answer()`; nothing else holds the later stage or the placement of the environment.

  answer(question, documents | Prepared, *, placement=None, read_mode=None, stage=None) -> dict   (the same dict `vera ask --mode round5` hands to the basis policy)

The round5 reading (`one.Vera.ask`) comes first; only when it stopped with UNKNOWN_UNREAD / UNKNOWN_NO_EVIDENCE the question cross of the sentences of the documents runs as the later stage (W3-c4;
moved here from cli.py unchanged). `placement`: a placement directory for the duration of the call (without it: the environment, `coarse_place.placement_from_env`; both
VERA_PLACEMENT and VERA_COARSE_PLACEMENT set to different places is `PlacementEnvConflict`). `read_mode`: None | 'strict' | 'assume' is accepted for the callers that carry one, and changes
nothing: the round5 answer path of `one.Vera` has no read mode (checked: `Vera._ask_round5` takes none); any other value is ValueError('BAD_READ_MODE'). `stage`: the later stage to
run (default `later_stage`): cli passes its own name so that its module-level hook stays the one the tests patch. This module does not import cli.
"""
from __future__ import annotations

import contextlib
import os
import re
from pathlib import Path

from . import coarse_place

# --- W3-c4: the question cross as a LATER STAGE of `vera ask --mode round5 --document` (docs/OBSERVATION.md, 文書 QA の後段（W3-c4）) ---------------------------
# Only when the round5 reading stopped with one of these two abstentions (closed set, registered before the build) and a document was handed over: the sentences of the
# documents are observed from the cross of the question (observe.observe_question_records, in memory, no file). Anything else is returned as the same object.
QC_TRIGGER = ("UNKNOWN_UNREAD", "UNKNOWN_NO_EVIDENCE")
QC_SPLIT = r"(?<=。)|(?<=\.)(?=\s)"
QC_PAIRS = (("「", "」"), ("『", "』"), ("“", "”"))


def records(documents):
    """Documents read as `one.Vera.load_documents` reads them -> ([{"id","text"}], {id: {"source","line","text"}}, loaded, skipped)."""
    from .document_loaders import load_directory, load_paths
    loaded, skipped = [], []
    for item in documents:
        path = Path(item)
        res = load_directory(str(path)) if path.is_dir() else load_paths([str(path)])
        loaded.extend(res["documents"])
        skipped.extend(res["skipped"])
    cut = re.compile(QC_SPLIT)
    records, where = [], {}
    for doc in loaded:
        for line_no, line in enumerate(doc.text.split("\n"), 1):
            pieces = [x.strip() for x in cut.split(line) if x.strip()]
            for k, piece in enumerate(pieces, 1):
                sid = "%s#%d:%d" % (doc.source, line_no, k)
                records.append({"id": sid, "text": piece})
                # a '.' cut that may not be the end of a sentence (an abbreviation, an initial): the piece before it is one token ending in '.', or the
                # piece after it starts with a lower-case letter. Both pieces next to such a cut are possibly the middle of a sentence: never the evidence of an answer.
                after = k < len(pieces) and piece.endswith(".") and pieces[k][:1].islower()
                before = k > 1 and pieces[k - 2].endswith(".") and (len(pieces[k - 2].split()) == 1 or piece[:1].islower())
                where.setdefault(sid, {"source": doc.source, "line": line_no, "text": piece, "cut_uncertain": bool(after or before)})
    return records, where, len(loaded), [{"verdict": x.get("verdict"), "path": x.get("path")} for x in skipped]


def _sources(evidence, where):
    """The sentences that attest a filler, in the observer's order, each sentence once."""
    out, seen = [], set()
    for ev in evidence:
        sid = ev["reading"]
        if sid in seen:
            continue
        seen.add(sid)
        w = where[sid]
        out.append({"family": "document", "source": w["source"], "line": w["line"], "text": w["text"], "sentence_id": sid})
    return out


def _quotes_open(text):
    return any(text.count(a) != text.count(b) for a, b in QC_PAIRS) or text.count('"') % 2 == 1


QC_END = "。．.！!？? \t\r\n　"


def predicate_form(text, tail):
    """Round 2 (M1). The reader gives `読みたかった` / `読みたがった` / `読んだらしかった` / a final `読んだら` the same clause as the plain past `読んだ` (it does not see the
    conjugated mark). So an evidence sentence of Japanese is an answer only when its WRITTEN predicate (from the reader's span of the predicate to the end of the sentence) is the end
    of the question as it was written. None: it is. Otherwise the reason: PREDICATE_POSITION_UNKNOWN (no single clause / no span) or PREDICATE_FORM_DIFFERS. Reads only; no word list."""
    from . import semantic_read
    try:
        out = semantic_read.read(text)
    except Exception:
        return "PREDICATE_POSITION_UNKNOWN"
    if not isinstance(out, dict) or out.get("lang") != "ja":
        return None                                 # not applied to other languages (docs/OBSERVATION.md, 事前登録の変更記録 第 2 ラウンド)
    meta, clauses = out.get("clause_meta") or [], out.get("clauses") or []
    if not out.get("readable") or len(meta) != 1 or len(clauses) != 1 or not isinstance(meta[0], dict):
        return "PREDICATE_POSITION_UNKNOWN"
    span = meta[0].get("span")
    if not (isinstance(span, (list, tuple)) and len(span) == 2 and all(type(i) is int for i in span) and 0 <= span[0] <= span[1] <= len(text)):
        return "PREDICATE_POSITION_UNKNOWN"
    written = text[span[0]:].rstrip(QC_END)
    return None if written and tail.endswith(written) else "PREDICATE_FORM_DIFFERS"


def _wrap(result, qc, step_state, observed, mapped):
    """The ORIGINAL form: a shallow copy of the result plus `question_cross` and one step of the trace (the original is not modified)."""
    out = dict(result)
    out["question_cross"] = qc
    out["trace"] = list(result.get("trace") or []) + [{"part": "question_cross", "status": "ran" if observed else "abstained",
                                                        "state": step_state, "mapped_to": mapped}]
    return out


def _info(state, reason, mapped, answer, coord, structure, documents):
    q = (answer or {}).get("question") or {}
    return {"state": state, "reason": reason, "mapped_to": mapped, "hole_role": q.get("hole_role"), "hole_type": q.get("hole_type"),
            "coord": coord, "structure": structure, "documents": documents}


def _run(result, documents, query, *, predicate_form=predicate_form):
    from .observe import observe_question_records
    recs, where, n_loaded, skipped = records(documents)
    docs_info = {"loaded": n_loaded, "skipped": skipped}
    if n_loaded == 0:
        return _wrap(result, _info("DOCUMENTS_NOT_LOADED", None, "ORIGINAL", None, None, None, docs_info), "DOCUMENTS_NOT_LOADED", False, "ORIGINAL")
    try:
        obs = observe_question_records(query, recs)
    except ValueError as exc:
        marker = "BAD_ARGUMENTS:STRUCTURE_INVALID:"
        if not str(exc).startswith(marker):
            raise
        return _wrap(result, _info("STRUCTURE_INVALID", str(exc)[len(marker):], "ORIGINAL", None, None, None, docs_info), "STRUCTURE_INVALID", False, "ORIGINAL")
    answer = obs.get("answer")
    if not answer:
        return _wrap(result, _info("NOT_A_QUESTION", None, "ORIGINAL", None, None, None, docs_info), "NOT_A_QUESTION", False, "ORIGINAL")
    state = answer["status"]
    reasons = answer.get("reasons") or []
    structure = {"sentences": answer["structure"]["sentences"], "crossed": answer["structure"]["crossed"],
                 "unread": answer["structure"]["unread"], "reasons": reasons}
    coord = [c for rank in (obs.get("ranks") or [])[:1] for el in rank["elements"] for c in el["coords"]]
    reason = reasons[0] if reasons else None

    def original(why=None):
        return _wrap(result, _info(state, why or reason, "ORIGINAL", answer, None, structure, docs_info), state, True, "ORIGINAL")

    if state not in ("FILLED", "TIE"):
        return original()
    rows = answer["fillers"]
    cands = [(row["surface"], _sources(row["evidence"], where)) for row in rows]
    tail = query.strip().rstrip("？?").rstrip()     # the question as written, without its final question mark
    for surface, srcs in cands:                     # a surface that is not in its own evidence, or evidence cut in the middle of a quotation, is not an answer
        if not any(surface in s["text"] for s in srcs):
            return original("SURFACE_NOT_IN_EVIDENCE")
        if any(_quotes_open(s["text"]) for s in srcs):
            return original("QUOTE_UNBALANCED_EVIDENCE")
        if any(where[s["sentence_id"]]["cut_uncertain"] for s in srcs):
            return original("PERIOD_CUT_UNCERTAIN")
        for s in srcs:                              # the written predicate of the evidence is the end of the question (round 2, M1)
            why = predicate_form(s["text"], tail)
            if why:
                return original(why)
    if state == "FILLED" and len(rows) == 1:
        surface, srcs = cands[0]
        qc = _info("FILLED", reason, "ANSWER", answer, coord, structure, docs_info)
        return {"kind": "answer", "verdict": "ANSWER", "text": surface, "values": [surface], "evidence": [s["text"] for s in srcs], "sources": srcs,
                "door": "question_cross", "question_cross": qc,
                "trace": list(result.get("trace") or []) + [{"part": "question_cross", "status": "ran", "state": "FILLED", "mapped_to": "ANSWER"}]}
    why = "SURFACES_DIFFER:%d" % len(rows) if state == "FILLED" else reason
    qc = _info(state, why, "AMBIGUOUS_QUESTION_CROSS_TIE", answer, coord, structure, docs_info)
    return {"kind": "unknown", "verdict": "AMBIGUOUS_QUESTION_CROSS_TIE", "text": "",
            "candidates": [{"text": surface, "sources": srcs} for surface, srcs in cands], "sources": [], "evidence": [],
            "door": "question_cross", "question_cross": qc,
            "trace": list(result.get("trace") or []) + [{"part": "question_cross", "status": "ran", "state": state, "mapped_to": "AMBIGUOUS_QUESTION_CROSS_TIE"}]}


def later_stage(result, documents, query, *, predicate_form=None):
    if not (documents and isinstance(result, dict) and result.get("verdict") in QC_TRIGGER):
        return result
    try:
        return _run(result, documents, query, predicate_form=predicate_form or globals()["predicate_form"])
    except Exception as exc:    # the one outer frame of the later stage: it must never break the abstention that was already there
        info = _info("ERROR", "%s: %s" % (type(exc).__name__, exc), "ORIGINAL", None, None, None, None)
        return _wrap(result, info, "ERROR", False, "ORIGINAL")


READ_MODES = (None, "strict", "assume")


@contextlib.contextmanager
def placement_scope(placement=None):
    """VERA_PLACEMENT is `placement` for the duration (restored afterwards, also on an exception). Without `placement`: what the environment names (`coarse_place.placement_from_env`; the
    compatible name alone is mapped to VERA_PLACEMENT for the duration, because the readers below read VERA_PLACEMENT). A conflict raises `coarse_place.PlacementEnvConflict`."""
    target = str(placement).strip() if placement is not None and str(placement).strip() else coarse_place.placement_from_env()
    old = os.environ.get(coarse_place.PLACEMENT_ENV)
    if target is not None and target != (old or "").strip():
        os.environ[coarse_place.PLACEMENT_ENV] = target
    try:
        yield target
    finally:
        if old is None:
            os.environ.pop(coarse_place.PLACEMENT_ENV, None)
        else:
            os.environ[coarse_place.PLACEMENT_ENV] = old


class Prepared:
    """The documents of a conversation: the round5 reader (`one.Vera`, built when first asked) and the sentences of the documents (`records`, read when first needed:
    a document that cannot be read must fail where the later stage's own frame catches it, as before)."""

    def __init__(self, documents):
        self.documents = [str(d) for d in documents]
        self._vera = None
        self._records = None

    def _read(self):
        if self._records is None:
            self._records = records(self.documents)
        return self._records

    @classmethod
    def of(cls, vera, documents):
        """A reader the caller already built (`vera chat` loads documents into one session reader and adds more with /doc)."""
        out = cls(documents)
        out._vera = vera
        return out

    records = property(lambda self: self._read()[0])
    where = property(lambda self: self._read()[1])
    n_loaded = property(lambda self: self._read()[2])
    skipped = property(lambda self: self._read()[3])

    @property
    def vera(self):
        if self._vera is None:
            from .one import Vera
            self._vera = Vera(mode="round5")
            if self.documents:
                self._vera.load_documents(self.documents)
        return self._vera


def prepare(documents):
    return Prepared(documents)


def answer(question, documents, *, placement=None, read_mode=None, stage=None):
    if read_mode not in READ_MODES:
        raise ValueError("BAD_READ_MODE")
    prepared = documents if isinstance(documents, Prepared) else Prepared(documents)
    with placement_scope(placement):
        result = prepared.vera.ask(question)
        return (stage or later_stage)(result, prepared.documents, question)
