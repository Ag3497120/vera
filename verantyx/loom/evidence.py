"""LOOM-evidence (docs/LINE3_LOOM_EVIDENCE_GATE.md; owner 2026-10-12 「読み手の証拠の門を emit に入れる」, OP-EV-1 (a) 「認める」): the reader's evidence gate.

WHAT THE GATE SAYS.  A prose emit is a QUOTATION.  Every cross of the emitted thread must be an unchanged `weave_span.v3` cross (L-LOOM-183), and the stretch it
quotes has to be READ, by Vera's own grammar, as an answer to the question:
  * the CLAUSE of the quoted sentence around the answer (the stretch joined to its neighbours only by the particles は の に で と を が も or by nothing) must hold
    every SUBJECT word of the question (OP-EV-1 (a): or the sentence's own article title must);
  * the answer holds no word of the question;
  * a SLOT question (「何年に設立」) needs the question's slot particle right after the answer's last word AND the slot head (設立) among the sentence's units;
  * a PREDICATE question (「XのYは何」) needs the clause to read 「Y は A」 or 「A は ... Y」;
  * a question with neither a slot particle nor a 「〜は何」 head can never be answered (`question_form_open`).
Otherwise `no_evidence`, with one typed code and one message per missing piece.  The evidence is DERIVED from the quote (L-LOOM-182): nothing is declared by the model.

THE QUESTION CUT (`question_units`, a pure function of the question text; L-LOOM-171..176) is computed by the loom at `begin` and returned read-only as
`question` (L-LOOM-185): the model cannot forge it, and the gate recomputes it from the task bank's text.

This module imports the grammar layer READ-ONLY (grammar, granularity, funcwords, space): it cuts the question and the clause deterministically, exactly as
the reader's own records do, and changes none of them.  No clock, no environment, no float; byte-identical across PYTHONHASHSEED.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

from verantyx.line3 import grammar as gm
from verantyx.line3 import space as sp
from verantyx.line3.funcwords import is_function_unit
from verantyx.line3.granularity import _raw_spans

EVIDENCE_V1 = "evidence.v1"
EVIDENCE_V2 = "evidence.v2"                                    # the review's fixes (L-LOOM-191..): a subject-less predicate question is refused, the answer's extent is checked, one answer only
EVIDENCE_VERSIONS: Tuple[str, ...] = (EVIDENCE_V1, EVIDENCE_V2)
EVIDENCE_LATEST = EVIDENCE_V2                                  # the rule NEW prose runs get; a ledger replays under the version its begin row recorded
PROFILE_NAMES: Dict[str, str] = {"v1": EVIDENCE_V1, "v2": EVIDENCE_V2}     # the server / CLI spelling -> the rule version
SCOPE_TITLE, SCOPE_CLAUSE = "clause_or_title", "clause"
SUBJECT_SCOPES: Tuple[str, ...] = (SCOPE_TITLE, SCOPE_CLAUSE)
DEFAULT_SCOPE = SCOPE_TITLE                                    # L-LOOM-190: until the owner answers OP-EV-1 otherwise (he said yes: 2026-10-12)

CODES: Tuple[str, ...] = ("not_quoted", "constructed_unit", "answer_not_word_aligned", "question_form_open", "question_has_no_subject", "no_subject",
                          "wrong_arm", "no_slot_head", "not_copular", "answer_holds_question_unit",
                          "answer_glued", "answer_crosses_break", "multiple_answers")          # the last three are evidence.v2 only
IGNORE = frozenset("「」『』“”\"'・· 　\t")                  # L-LOOM-177
P7 = gm.P7
ARMS = ("の", "に", "で", "と", "を", "が")                        # the six arm particles (は is the centre relation)
CONN_PARTICLES = frozenset(P7) | {"も"}
JOINERS = frozenset("-‐‑–—−,.:/+")                                # evidence.v2: punctuation that joins the pieces of one token (JR-Y13, 73,921, 1.5, 12:30): not a break
FORM_SLOT, FORM_PREDICATE, FORM_OPEN = "slot", "predicate", "open"


@lru_cache(maxsize=1 << 18)
def strip_ignore(s: str) -> str:
    return "".join(ch for ch in s if ch not in IGNORE)


def _content_word(w: str) -> bool:
    return gm._content(w)


# ------------------------------------------------------------------------------------------------------------
# the question's units (QU), L-LOOM-171..176
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class QuestionUnits:
    text: str                                    # the question as the grammar layer cut it (attribution stripped)
    form: str                                    # slot | predicate | open
    slot_phrase: Optional[str]
    slot_particle: Optional[str]                 # the particle right after the slot phrase (None = none)
    particle: Optional[str]                      # the EFFECTIVE particle p (「どこの国で」: で)
    slot_noun: Optional[str]
    slot_head: Optional[str]
    fallback: bool
    y: Optional[str]
    y_forms: Tuple[str, ...]
    subject: Tuple[str, ...]
    subject_level: Optional[str]                 # x_chain | topic | ga | case | None
    units: Tuple[str, ...]                       # the echo set (L-LOOM-181)

    def to_obj(self, scope: Optional[str] = None, version: str = EVIDENCE_V1) -> dict:
        """The `question` object of `begin` (L-LOOM-185); `version` is the rule version of the run (the cut itself is the same in v1 and v2)."""
        return {"evidence": version, "subject_scope": scope, "form": self.form,
                "slot": {"phrase": self.slot_phrase, "particle": self.particle, "noun": self.slot_noun, "head": self.slot_head, "fallback": self.fallback},
                "y": self.y, "y_forms": list(self.y_forms), "subject": list(self.subject), "subject_level": self.subject_level, "units": list(self.units)}


def _touching(text: str, a: int, b: int) -> bool:
    return strip_ignore(text[a:b]) == ""


def _s_runs(text: str, words: Sequence[gm.Word]) -> Tuple[List[Tuple[str, int, int]], List[dict]]:
    """Step 6: (the kept RUN units with spans, the merged S-runs {s, a, b, after})."""
    kept: List[Tuple[str, int, int]] = []
    for u, a, b in _raw_spans(sp.RUN, text):
        if is_function_unit(u, sp.RUN):
            continue
        if any(_content_word(w) for w, _, _ in gm.words_of(u)):
            kept.append((u, a, b))
    runs: List[dict] = []
    for u, a, b in kept:
        if runs and _touching(text, runs[-1]["b"], a):
            runs[-1]["s"] += strip_ignore(u)
            runs[-1]["b"] = b
        else:
            runs.append({"s": strip_ignore(u), "a": a, "b": b})
    for r in runs:
        lab, f, _ = gm.follower(words, r["b"])
        r["after"] = f if lab == "particle" else None
    return kept, runs


def run_units(question: str) -> List[str]:
    """The kept RUN units of the question (§3.1 step 6, before merging): the reader's query units, i.e. the question's RUN cut without its function units."""
    r = gm.read_question(question)
    return [u for u, _, _ in _s_runs(r.text, gm.words_of(r.text))[0]]


def _overlaps(a: int, b: int, spans: Sequence[Tuple[int, int]]) -> bool:
    return any(a < y and x < b for x, y in spans)


def question_units(question: str) -> QuestionUnits:
    r = gm.read_question(question)
    text = r.text
    words = gm.words_of(text)
    slot = r.slot
    fallback = False
    if slot is None:                                                           # step 1 (L-LOOM-171)
        for fr in r.frames:
            if any(fr.unit.startswith(m) for m in gm.INTERROG):
                slot = gm.Slot(fr.unit, fr.span, fr.particle, fr.after)
                fallback = True
                break
    p = None if slot is None else slot.particle
    noun: Optional[str] = None
    noun_span: Optional[Tuple[int, int]] = None
    p_end: Optional[int] = None                                                # where the effective particle ends (for the slot head)
    if slot is not None and p is not None:
        lab, f, sps = gm.follower(words, slot.span[1])
        p_end = sps[1] if sps else None
        if p == "の":                                                          # step 2 (L-LOOM-172)
            j = next((i for i, w in enumerate(words) if w[1] >= p_end), None) if p_end is not None else None
            if j is not None and words[j][1] == p_end and _content_word(words[j][0]):
                lab2, f2, sps2 = gm.follower(words, words[j][2])
                if lab2 == "particle" and f2 != "の":
                    p, noun, noun_span, p_end = f2, words[j][0], (words[j][1], words[j][2]), sps2[1]
    y = None                                                                   # step 3
    y_span: Optional[Tuple[int, int]] = None
    pred = None
    if slot is not None and not fallback:
        pred = r.predicate
    elif slot is not None and fallback and slot.particle is None:
        pred = gm.predicate_of(words, slot)
    if pred is not None:
        y, y_span = pred.y, pred.y_span
    if slot is not None and p in P7:                                           # step 4 (L-LOOM-173)
        form = FORM_SLOT
    elif y is not None:
        form = FORM_PREDICATE
    else:
        form = FORM_OPEN
    y_forms: List[str] = []                                                    # step 5 (L-LOOM-174)
    if y is not None:
        for w, a, _ in gm.words_of(y):
            if _content_word(w) and len(y) - a >= 2:
                f_ = y[a:]
                if f_ not in y_forms:
                    y_forms.append(f_)
        y_forms.sort(key=lambda s: (-len(s), s))
    kept, runs = _s_runs(text, words)                                          # step 6
    excl: List[Tuple[int, int]] = []
    if slot is not None:
        excl.append(slot.span)
    if noun_span is not None:
        excl.append(noun_span)
    if y_span is not None:
        excl.append(y_span)
    free = [r_ for r_ in runs if not _overlaps(r_["a"], r_["b"], excl)]
    subject: List[str] = []                                                    # step 7 (L-LOOM-175)
    level: Optional[str] = None
    if form == FORM_PREDICATE and y_span is not None:
        cur = y_span[0]
        chain: List[str] = []
        while True:
            hit = next((r_ for r_ in free if r_["after"] == "の" and r_["b"] <= cur and strip_ignore(text[r_["b"]:cur]) == "の"), None)
            if hit is None:
                break
            chain.append(hit["s"])
            cur = hit["a"]
        if chain:
            subject, level = [chain[-1]], "x_chain"
    if not subject:
        for name, parts in (("topic", ("は",)), ("ga", ("が",)), ("case", ("を", "に", "で", "と", "の"))):
            hit = [r_["s"] for r_ in free if r_["after"] in parts]
            if hit:
                subject, level = hit, name
                break
    head: Optional[str] = None                                                 # step 8 (L-LOOM-176)
    if form == FORM_SLOT and p_end is not None:
        lab, f, _ = gm.follower(words, p_end)
        if lab == "other" and _content_word(f):
            head = f
    units: List[str] = []                                                      # step 9 (L-LOOM-181)
    for u, _, _ in kept:
        s = strip_ignore(u)
        if s and not any(m in s for m in gm.INTERROG) and s not in units:
            units.append(s)
    for s in subject + y_forms:
        if s and s not in units:
            units.append(s)
    return QuestionUnits(text, form, None if slot is None else slot.phrase, None if slot is None else slot.particle, p, noun, head, fallback, y, tuple(y_forms),
                         tuple(subject), level, tuple(units))


# ------------------------------------------------------------------------------------------------------------
# the sentence and its clause (§4)
# ------------------------------------------------------------------------------------------------------------
_VIEWS: Dict[Tuple[str, int], "SentenceView"] = {}           # (corpus sha, sid) -> view: a pure cache of what the corpus holds


class SentenceView:
    """One corpus sentence as the gate reads it: the stripped text, the WORD units of the space (function words filtered, as the reader's records are
    built) with their spans, the raw WORD cut (function words kept: for the particle after the answer), the title."""

    def __init__(self, corpus, sid: int) -> None:
        self.sid = sid
        idx = corpus.spans()
        self.text: str = idx.text(sid)
        self.source: str = corpus.sentence(sid)["source"]
        self.title: str = re.sub(r"#\d+$", "", self.source)
        t = corpus.tier(sp.WORD)
        self.units: List[str] = list(t.sentence_units[sid])
        self.spans: List[Tuple[int, int]] = [tuple(s) for s in idx.spans(sp.WORD, sid)]
        self.raw: List[gm.Word] = gm.words_of(self.text)
        self.unit_set = frozenset(self.units)

    def gap(self, k: int) -> str:
        """The sentence text between WORD unit k and unit k + 1."""
        return self.text[self.spans[k][1]:self.spans[k + 1][0]]


def view_of(corpus, sid: int) -> SentenceView:
    key = (corpus.corpus_sha, sid)
    v = _VIEWS.get(key)
    if v is None:
        v = _VIEWS[key] = SentenceView(corpus, sid)
    return v


@lru_cache(maxsize=None)
def connective(gap: str, stacked: bool = False) -> bool:
    """§4.2 step 3: a gap that does not break the clause: nothing (after the ignorable characters), 「は、」, or a stack of the particles は の に で と を が も
    (the first one of the seven) without a 「、」."""
    g = strip_ignore(gap)
    if g == "" or g == "は、":
        return True
    if "、" in g:
        return False
    if stacked and g[0] in P7 and all(ch in CONN_PARTICLES for ch in g):         # evidence.v2: 「とも」 「でも」 「をも」 are stacks of the particles too (words_of reads them as ONE function word)
        return True
    toks = gm.words_of(g)
    if "".join(t[0] for t in toks) != g:
        return False
    return bool(toks) and toks[0][0] in P7 and all(t[0] in CONN_PARTICLES for t in toks)


def clause_bounds(v: SentenceView, a0: int, a1: int, stacked: bool = False) -> Tuple[int, int]:
    lo, hi = a0, a1
    while lo > 0 and connective(v.gap(lo - 1), stacked):
        lo -= 1
    while hi < len(v.units) - 1 and connective(v.gap(hi), stacked):
        hi += 1
    return lo, hi


def clause_text(v: SentenceView, lo: int, hi: int) -> str:
    return v.text[v.spans[lo][0]:v.spans[hi][1]]


def _read_in(surfs: Sequence[str], gap, lo: int, hi: int, s: str, avoid: Optional[Tuple[int, int]] = None) -> List[Tuple[int, int]]:
    """Every [i, j] within [lo, hi], disjoint from `avoid`, such that the WORD surfaces i..j touch (every gap between them is empty after the ignorable
    characters) and spell `s` (without the ignorable characters).  §4.3."""
    target = strip_ignore(s)
    out: List[Tuple[int, int]] = []
    if not target:
        return out
    for i in range(lo, hi + 1):
        acc = ""
        for j in range(i, hi + 1):
            if j > i and strip_ignore(gap(j - 1)) != "":
                break
            acc += strip_ignore(surfs[j])
            if not target.startswith(acc):
                break
            if acc == target:
                if avoid is None or j < avoid[0] or i > avoid[1]:
                    out.append((i, j))
                break
    return out


@lru_cache(maxsize=None)
def _title_reader(title: str):
    ws = gm.words_of(title)
    surfs = [w[0] for w in ws]

    def gap(k: int) -> str:
        return title[ws[k][2]:ws[k + 1][1]]

    return surfs, gap, len(ws)


# ------------------------------------------------------------------------------------------------------------
# messages (English; quoted words in 「」), §5
# ------------------------------------------------------------------------------------------------------------
def _m_not_aligned(ans: str, sid: int) -> str:
    return "the stretch 「%s」 does not begin and end on words of sentence %d" % (ans, sid)


def _m_open(q: str) -> str:
    return "the question 「%s」 has no particle after its question word and no 「〜は何」 head, so no answer can be read from a sentence for it" % q


def _m_no_subject(s: str, cl: str, sid: int, title: Optional[str]) -> str:
    base = "the subject 「%s」 of the question is not in the clause 「%s」 of sentence %d" % (s, cl, sid)
    return base + ((" (nor in its article title 「%s」)" % title) if title is not None else "")


def _m_no_subject_at_all(q: str) -> str:
    return "the question 「%s」 has no subject word, so a sentence cannot be tied to it" % q


def _m_wrong_arm(ans: str, got: str, p: str, phrase: str, sid: int) -> str:
    return "the answer 「%s」 is followed by 「%s」 in sentence %d; the question asks for the word before 「%s」 (「%s%s」)" % (ans, got, sid, p, phrase, p)


def _m_head(h: str, sid: int) -> str:
    return "sentence %d does not contain 「%s」, the question's predicate" % (sid, h)


def _m_head_clause(h: str, cl: str, sid: int) -> str:
    return "the question's predicate 「%s」 is not in the clause 「%s」 of sentence %d: this clause does not say what is asked" % (h, cl, sid)


def _m_head_none(q: str) -> str:
    return "the question 「%s」 has no predicate word after its question word, so no clause can be tied to what it asks" % q


def _m_item(y: str, cl: str) -> str:
    return "the asked item 「%s」 is not in the clause 「%s」: this sentence does not state what is asked" % (y, cl)


def _m_copula(ans: str, cl: str) -> str:
    return "the answer 「%s」 is not read as 「Y は A」 or 「A は … Y」 in the clause 「%s」" % (ans, cl)


def _m_echo(u: str) -> str:
    return "the answer contains 「%s」, a word of the question; quote only what answers" % u


def _m_glued(ans: str, whole: str, sid: int) -> str:
    return "the stretch 「%s」 of sentence %d is glued to a neighbouring word (it is a piece of 「%s」); quote the whole word, or the whole phrase, that answers" % (ans, sid, whole)


def _m_break(ans: str, gap: str, sid: int) -> str:
    return "the stretch 「%s」 of sentence %d crosses 「%s」: an answer is one phrase, not a stretch over a comma, a bracket or a particle" % (ans, sid, gap)


def _m_multiple(answers: Sequence[str]) -> str:
    return "the thread holds %d quotes that each read as an answer (%s); emit exactly one" % (len(answers), "、".join("「%s」" % a for a in answers))


def _m_not_quoted(cid: str) -> str:
    return "cross %s is not an unchanged weave_span quote: only a quoted stretch of a corpus sentence can be emitted" % cid


def _m_constructed(uid: str, cid: str) -> str:
    return "unit %s (in cross %s) is a constructed unit: a constructed unit cannot be emitted in prose" % (uid, cid)


# ------------------------------------------------------------------------------------------------------------
# the answer's extent (evidence.v2, F2)
# ------------------------------------------------------------------------------------------------------------
def joined(gap: str) -> bool:
    """Two WORD units of the sentence that touch (nothing between them after the ignorable characters) or are joined only by joiner punctuation (「-」 「,」 「.」 ...)
    are pieces of ONE token."""
    g = strip_ignore(gap)
    return all(ch in JOINERS for ch in g)


def inner_ok(gap: str) -> bool:
    """A gap that may lie INSIDE an answer: a join, or the genitive 「の」 (キューバの太陽).  Any other gap (は を に で が と も, 「、」, a bracket, a word) is a break."""
    return joined(gap) or strip_ignore(gap) == "の"


def whole_word_of(v: "SentenceView", a0: int, a1: int) -> str:
    """The maximal run of touching / joined WORD units around units a0..a1 of the sentence (what the answer is a piece of)."""
    lo, hi = a0, a1
    while lo > 0 and joined(v.gap(lo - 1)):
        lo -= 1
    while hi < len(v.units) - 1 and joined(v.gap(hi)):
        hi += 1
    return clause_text(v, lo, hi)


# ------------------------------------------------------------------------------------------------------------
# judging one quotation (§5, per weave)
# ------------------------------------------------------------------------------------------------------------
def judge_quote(corpus, qu: QuestionUnits, scope: str, sid: int, tier: str, i0: int, i1: int, version: str = EVIDENCE_LATEST) -> dict:
    """The gate for ONE quoted stretch (tier `tier`, units i0..i1 of sentence `sid`).  {"codes": [...], "messages": [...], "failures": [{"code", "message"}],
    "answer", "clause", "evidence": {...} | None}.  All checks run; every failing code is listed (E-1 failing leaves only E-2: there is no clause to read).
    `version` is the rule version (evidence.v1: the rules of the first build; evidence.v2: + F1 a predicate question with no subject is refused, F2 the answer is a
    whole word / phrase: not glued to a neighbouring word, no break inside)."""
    if version not in EVIDENCE_VERSIONS:
        raise ValueError("version must be one of %s" % (EVIDENCE_VERSIONS,))
    v2 = version != EVIDENCE_V1
    v = view_of(corpus, sid)
    sps = corpus.spans().spans(tier, sid)
    cs, ce = sps[i0][0], sps[i1][1]
    answer = v.text[cs:ce]
    fails: List[dict] = []

    def fail(code: str, message: str, **kw) -> None:
        fails.append(dict({"code": code, "message": message}, **kw))

    a0 = next((k for k, s in enumerate(v.spans) if s[0] == cs), None)
    a1 = next((k for k, s in enumerate(v.spans) if s[1] == ce), None)
    aligned = a0 is not None and a1 is not None and a0 <= a1
    if not aligned:
        fail("answer_not_word_aligned", _m_not_aligned(answer, sid))
    if qu.form == FORM_OPEN:
        fail("question_form_open", _m_open(qu.text))
    out = {"answer": answer, "clause": None, "sid": sid, "source": v.source}
    if not aligned:
        return _done(out, fails, None)
    if v2:                                                                              # F2: the extent of the answer
        if (a0 > 0 and joined(v.gap(a0 - 1))) or (a1 < len(v.units) - 1 and joined(v.gap(a1))):
            fail("answer_glued", _m_glued(answer, whole_word_of(v, a0, a1), sid))
        brk = next((v.gap(k) for k in range(a0, a1) if not inner_ok(v.gap(k))), None)
        if brk is not None:
            fail("answer_crosses_break", _m_break(answer, strip_ignore(brk) or brk, sid))
    lo, hi = clause_bounds(v, a0, a1, v2)
    cl = clause_text(v, lo, hi)
    out["clause"] = cl
    surfs, gap = v.units, v.gap
    avoid = (a0, a1)
    title_scope = scope == SCOPE_TITLE
    # E-3
    subj_ev: List[dict] = []
    if not qu.subject and (qu.form == FORM_SLOT or (v2 and qu.form == FORM_PREDICATE)):       # F1 (v2): a predicate question with no subject word is tied to no sentence either
        fail("question_has_no_subject", _m_no_subject_at_all(qu.text))
    for s in qu.subject:
        if _read_in(surfs, gap, lo, hi, s, avoid):
            subj_ev.append({"run": s, "via": "clause"})
            continue
        if title_scope:
            ts, tg, tn = _title_reader(v.title)
            if tn and _read_in(ts, tg, 0, tn - 1, s):
                subj_ev.append({"run": s, "via": "title"})
                continue
        fail("no_subject", _m_no_subject(s, cl, sid, v.title if title_scope else None), subject=s)
    slot_ev = None
    copula = None
    if qu.form == FORM_SLOT:
        p = qu.particle
        lab, f, _ = gm.follower(v.raw, v.spans[a1][1], "whole_word")                     # E-4s
        if not (lab == "particle" and f == p):
            fail("wrong_arm", _m_wrong_arm(answer, f if f is not None else "(end)", p, qu.slot_phrase or "", sid))
        else:
            from verantyx.loom.state import AXES, SPEC
            slot_ev = {"particle": p, "arm": AXES[list(SPEC.arms).index(p)] if p in SPEC.arms else None}
        if not v2:                                                                       # E-5s
            if qu.slot_head is not None and qu.slot_head not in v.unit_set:
                fail("no_slot_head", _m_head(qu.slot_head, sid))
        elif qu.slot_head is None:                                                       # v2 (owner 2026-10-12): the head is required, and read in the CLAUSE; none = refuse
            fail("no_slot_head", _m_head_none(qu.text))
        elif not _read_in(surfs, gap, lo, hi, qu.slot_head, avoid):
            fail("no_slot_head", _m_head_clause(qu.slot_head, cl, sid))
    elif qu.form == FORM_PREDICATE:
        reads: List[Tuple[str, int, int]] = []
        for f_ in qu.y_forms:
            for (i, j) in _read_in(surfs, gap, lo, hi, f_, avoid):
                reads.append((f_, i, j))
        if not reads:                                                                   # E-4p
            fail("no_slot_head", _m_item(qu.y or "", cl))
        else:
            for f_, y0, y1 in reads:
                g_after = gap(y1) if y1 + 1 < len(surfs) else None
                if g_after in ("は", "は、") and a0 == y1 + 1:
                    copula = "Y は A"
                    break
                if a1 + 1 < len(surfs) and gap(a1) in ("は", "は、") and y0 > a1 and all(strip_ignore(gap(k)) == "" or strip_ignore(gap(k)) in ARMS
                                                                                         for k in range(a1 + 1, y1)):
                    copula = "A は … Y"
                    break
            if copula is None:                                                          # E-5p
                fail("not_copular", _m_copula(answer, cl))
    # E-6
    echo = []
    for u in qu.units:
        if _read_in(surfs, gap, a0, a1, u):
            echo.append(u)
    if echo:
        fail("answer_holds_question_unit", _m_echo(echo[0]), units=echo)
    ev = None
    if not fails:
        ev = {"sid": sid, "source": v.source, "clause": cl, "subject": subj_ev}
        if slot_ev is not None:
            ev["slot"] = slot_ev
        if copula is not None:
            ev["copula"] = copula
            ev["y"] = qu.y
    return _done(out, fails, ev)


def _done(out: dict, fails: List[dict], ev: Optional[dict]) -> dict:
    codes: List[str] = []
    for f in fails:
        if f["code"] not in codes:
            codes.append(f["code"])
    out.update(codes=codes, messages=[f["message"] for f in fails], failures=fails, evidence=ev)
    return out


# ------------------------------------------------------------------------------------------------------------
# the gate at read / emit (§5 T)
# ------------------------------------------------------------------------------------------------------------
def intact_weaves(run) -> Dict[int, dict]:
    """§4.1: the v3 weaves whose crosses all still exist, still carry their quote marker, are all linked and stand in the thread consecutively in creation order."""
    st = run.state
    out: Dict[int, dict] = {}
    for wv in run.weaves:
        cids = wv["cids"]
        ok = all(c in st.crosses and st.crosses[c].quote is not None and st.crosses[c].quote[0] == wv["w"] and st.crosses[c].linked for c in cids)
        if ok:
            pos = [st.thread.index(c) for c in cids]
            ok = pos == list(range(pos[0], pos[0] + len(pos)))
        if ok:
            out[wv["w"]] = wv
    return out


def gate(run) -> dict:
    """{"refusal": the `no_evidence` refusal dict | None, "evidence": [one entry per passing weave]} for a prose run with an evidence profile."""
    st = run.state
    qu = run.question_units
    version, scope = run.evidence
    held = [st.crosses[c] for c in st.thread if st.crosses[c].uids()]
    if not held:
        return {"refusal": None, "evidence": []}
    intact = intact_weaves(run)
    crosses: List[dict] = []                    # exactly {"cid", "code"} (§5); the words for them are in `cross_messages`, one per entry
    cross_messages: List[str] = []
    for c in held:
        if c.quote is None or c.quote[0] not in intact:
            crosses.append({"cid": c.cid, "code": "not_quoted"})
            cross_messages.append(_m_not_quoted(c.cid))
    for c in held:
        for uid in c.uids():
            if st.units[uid].kind != "record":
                crosses.append({"cid": c.cid, "code": "constructed_unit"})
                cross_messages.append(_m_constructed(uid, c.cid))
    weaves: List[dict] = []
    evidence: List[dict] = []
    answers: List[str] = []
    for w in sorted(intact):
        wv = intact[w]
        if not any(st.crosses[c].uids() for c in wv["cids"]):
            continue
        j = judge_quote(run.corpus, qu, scope, wv["sid"], wv["tier"], wv["i0"], wv["i1"], version)
        if j["codes"]:
            weaves.append({"w": w, "cids": list(wv["cids"]), "sid": j["sid"], "source": j["source"], "tier": wv["tier"], "answer": j["answer"], "clause": j["clause"],
                           "codes": j["codes"], "messages": j["messages"]})
        else:
            evidence.append(dict(j["evidence"], w=w))
            answers.append(j["answer"])
    if version != EVIDENCE_V1 and len(evidence) > 1:                                   # F3 (v2): ONE answer; several are not joined into one text
        for e in evidence[1:]:
            crosses.append({"cid": intact[e["w"]]["cids"][0], "code": "multiple_answers"})
            cross_messages.append(_m_multiple(answers))
    if not weaves and not crosses:
        return {"refusal": None, "evidence": evidence}
    return {"refusal": {"type": "no_evidence", "weaves": weaves, "crosses": crosses, "cross_messages": cross_messages}, "evidence": evidence}
