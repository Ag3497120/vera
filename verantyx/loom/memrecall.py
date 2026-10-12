"""MEM-c: recall and the self-question through the evidence gate (docs/LINE3_LOOM_MEMORY_DESIGN.md 4.3, 6, 9.2 L-MEM-11, 12, 21; docs/LINE3_LOCAL_DECISIONS.md MEM-c).

ONE reader, two doors.  The reader is Vera's evidence gate, UNCHANGED: `evidence.judge_quote(corpus, qu, scope, sid, tier, i0, i1, version)` with
  qu      = evidence.question_units(question)             the reader's own cut of the question
  scope   = evidence.SCOPE_CLAUSE                          a memory sentence has no article title (L-MEM-12): the subject must be read in the CLAUSE
  tier    = "WORD"                                         the tier every memory sentence is woven in (L-MEM-04)
  corpus  = the MEMORY corpus (`mem:` rows only; `assert_memory_corpus`); never a base corpus
  version = the evidence version the session's begin row recorded (evidence.v2 for the gate hook)
A stretch (sid, i0, i1) PASSES iff `codes == []`.  Candidates (L-MEM-11): every stretch of at most 4 WORD units (i1 - i0 <= 3) of a sentence that holds a word of a Y
form of the question or its slot head (a prefilter that only drops sentences on which the gate's own E-4p / E-5s would fail; `prefilter=False` proves it).

  door 1  the SELF-QUESTION of MEM-b (`GateSelfQuestion`, hook id `gate.evidence.v2`): over H[0..t] (the corpus handed in as `corpus_after`), sentence t included;
          the passes become `Answer(sid, answer, (i0, i1))` and the detection of MEM-b (answer_groups, SAME_QUESTION / SELF_QUESTION_UNREADABLE) is unchanged.
  door 2  `recall(question)` (the memory session's tool): the same loop over ALL committed sentences; the passes are grouped exactly as the self-question groups them
          (a sentence's answer set = its MAXIMAL passing stretches; two sentences agree iff the sets intersect; components by union-find in sid order):
            NONE    no stretch passes (the code histogram and the question's own problems are returned: why)
            ANSWER  one component (every occurrence listed, longest answer first)
            CHOICE  two or more components: contested facts stay listed, never ranked, never retracted (L-MEM-13: a tie abstains, order is never a winner)
Pure functions of (corpus, question, version): no clock, no float, no environment, no file; byte-identical across PYTHONHASHSEED.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.loom import evidence as ev
from verantyx.loom import memnotes as mn
from verantyx.loom.memguard import MEM_PREFIX, parse_source
from verantyx.loom.state import Refuse

GATE_HOOK_ID = "gate.evidence.v2"
RECALL_VERSION = ev.EVIDENCE_V2               # the evidence version the gate hook records in the begin row (evidence_version)
RECALL_SCOPE = ev.SCOPE_CLAUSE                # L-MEM-12
RECALL_TIER = "WORD"
MAX_STRETCH = 3                               # L-MEM-11: i1 - i0 <= 3
VERDICTS: Tuple[str, ...] = ("ANSWER", "CHOICE", "NONE")


# ------------------------------------------------------------------------------------------------------------
# the guard: the gate reads the memory and nothing else
# ------------------------------------------------------------------------------------------------------------
def assert_memory_corpus(corpus: Any) -> None:
    """Recall over memory never reads a base corpus: every sentence of the corpus has a `mem:<store>/<session>#<i>` source (L-MEM-02 read the other way).
    `Refuse("not_memory_row", {"sid"})` at the first sentence that has not."""
    for sid in range(corpus.n_sentences):
        src = corpus.sentence(sid)["source"]
        if not (isinstance(src, str) and src.startswith(MEM_PREFIX) and parse_source(src) is not None):
            raise Refuse("not_memory_row", {"sid": sid, "reason": "recall reads only the memory corpus"})


# ------------------------------------------------------------------------------------------------------------
# the loop
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Pass:
    """One stretch the gate accepted: sentence `sid`, units i0..i1 of the WORD tier, the answer text and the clause the gate read it in."""
    sid: int
    i0: int
    i1: int
    answer: str
    clause: str


def targets_of(qu: ev.QuestionUnits) -> List[str]:
    """The words a candidate sentence has to hold (stripped of the ignorable characters): the Y forms of the question and its slot head."""
    out: List[str] = []
    for t in list(qu.y_forms) + ([qu.slot_head] if qu.slot_head else []):
        s = ev.strip_ignore(t)
        if s and s not in out:
            out.append(s)
    return out


def candidate_sids(corpus: Any, qu: ev.QuestionUnits, prefilter: bool = True) -> List[int]:
    """The sentences whose stretches are judged, in sid order.  With the prefilter: those whose WORD units, written together, hold a Y form or the slot head
    (a superset of what the gate's `_read_in` can find, so no passing sentence is lost).  Without it: every sentence (the control of the exactness test)."""
    n = corpus.n_sentences
    if not prefilter:
        return list(range(n))
    tg = targets_of(qu)
    if not tg:
        return []
    t = corpus.tier(RECALL_TIER)
    out = []
    for sid in range(n):
        s = ev.strip_ignore("".join(t.sentence_units[sid]))
        if any(x in s for x in tg):
            out.append(sid)
    return out


def stretches(n_units: int) -> List[Tuple[int, int]]:
    return [(i0, i1) for i0 in range(n_units) for i1 in range(i0, min(n_units, i0 + MAX_STRETCH + 1))]


def judge_memory(corpus: Any, question: str, version: str = RECALL_VERSION, prefilter: bool = True) -> dict:
    """The loop: {"qu", "sentences", "candidates": [sid], "judged": n, "passes": [Pass], "codes": {code: n over the failing stretches}}."""
    assert_memory_corpus(corpus)
    qu = ev.question_units(question)
    cands = candidate_sids(corpus, qu, prefilter)
    t = corpus.tier(RECALL_TIER)
    passes: List[Pass] = []
    codes: Dict[str, int] = {}
    judged = 0
    for sid in cands:
        for i0, i1 in stretches(len(t.sentence_units[sid])):
            r = ev.judge_quote(corpus, qu, RECALL_SCOPE, sid, RECALL_TIER, i0, i1, version)
            judged += 1
            if r["codes"]:
                for c in r["codes"]:
                    codes[c] = codes.get(c, 0) + 1
            else:
                passes.append(Pass(sid, i0, i1, r["answer"], r["clause"]))
    return {"qu": qu, "sentences": corpus.n_sentences, "candidates": cands, "judged": judged, "passes": passes, "codes": dict(sorted(codes.items()))}


def as_answers(passes: Sequence[Pass]) -> List[mn.Answer]:
    return [mn.Answer(p.sid, p.answer, (p.i0, p.i1)) for p in passes]


# ------------------------------------------------------------------------------------------------------------
# door 1: the self-question hook of MEM-b
# ------------------------------------------------------------------------------------------------------------
class GateSelfQuestion:
    """The hook of MEM-b through the evidence gate: `self_question(question, MemoryBefore) -> [Answer]` over H[0..t] (the corpus `corpus_after` = C_t).  Records
    `evidence_version` in the begin row of the session (replay needs the same id and version)."""
    id = GATE_HOOK_ID
    evidence_version = RECALL_VERSION

    def __call__(self, question: str, mem: mn.MemoryBefore) -> List[mn.Answer]:
        return as_answers(judge_memory(mem.corpus_after, question, self.evidence_version)["passes"])


# ------------------------------------------------------------------------------------------------------------
# door 2: recall
# ------------------------------------------------------------------------------------------------------------
def question_issues(qu: ev.QuestionUnits) -> List[str]:
    """Why the question can never be answered from any sentence, whatever the memory holds (the gate's own question-level codes)."""
    out: List[str] = []
    if qu.form == ev.FORM_OPEN:
        out.append("question_form_open")
    if not qu.subject and (qu.form == ev.FORM_SLOT or qu.form == ev.FORM_PREDICATE):
        out.append("question_has_no_subject")
    return out


def recall(corpus: Any, question: str, version: str = RECALL_VERSION, prefilter: bool = True) -> dict:
    """The verdict of one question over the whole memory `corpus`.  {"verdict", "question", "evidence", "scope", "sentences", "candidates", "judged", "answers": [group],
    ("codes", "issues", "looked_for" for NONE)} where a group = {"text", "answers": [display, longest first], "occurrences": [{"sid", "source", "session", "role", "answer",
    "span", "clause"}] in sid order}."""
    j = judge_memory(corpus, question, version, prefilter)
    qu: ev.QuestionUnits = j["qu"]
    out: Dict[str, Any] = {"verdict": "NONE", "question": qu.to_obj(RECALL_SCOPE, version), "evidence": version, "scope": RECALL_SCOPE,
                           "sentences": j["sentences"], "candidates": len(j["candidates"]), "judged": j["judged"], "answers": []}
    if not j["passes"]:
        out["codes"] = j["codes"]                                      # over the judged stretches of the candidate sentences ({} when no sentence was a candidate)
        out["issues"] = question_issues(qu) + ([] if j["candidates"] else ["no_sentence_holds_the_question_words"])
        out["looked_for"] = targets_of(qu)                             # the words (Y forms, slot head) a sentence must hold to be judged at all
        return out
    answers = as_answers(j["passes"])
    sets, comps = mn.answer_groups(answers)
    by_sid: Dict[int, List[Pass]] = {}
    for p in j["passes"]:
        by_sid.setdefault(p.sid, []).append(p)
    groups = []
    for comp in comps:
        occ: List[dict] = []
        shown: Dict[str, str] = {}
        for sid in comp:
            src = corpus.sentence(sid)["source"]
            _, session, _, role = parse_source(src)
            for norm, display in sets[sid].items():
                best = max((p for p in by_sid[sid] if mn.norm_answer(p.answer) == norm and p.answer == display), key=lambda p: (p.i1 - p.i0, -p.i0))
                occ.append({"sid": sid, "source": src, "session": session, "role": role, "answer": display, "span": [best.i0, best.i1], "clause": best.clause})
                if norm not in shown or len(display) > len(shown[norm]):
                    shown[norm] = display
        occ.sort(key=lambda o: (o["sid"], o["span"][0], o["span"][1]))
        names = [shown[n] for n in sorted(shown, key=lambda n: (-len(n), n))]
        groups.append({"text": names[0], "answers": names, "occurrences": occ})
    out["answers"] = groups
    out["verdict"] = "ANSWER" if len(groups) == 1 else "CHOICE"
    return out
