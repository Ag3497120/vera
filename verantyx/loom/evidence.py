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
EVIDENCE_V3 = "evidence.v3"                                    # LOOM-reach (L-LOOM-201..): v2 + the safe set R1..R7 and the tightenings T1 / T2 of docs/LINE3_LOOM_REACH_DESIGN.md; selectable, NOT the default (OP-RE-2)
EVIDENCE_V4 = "evidence.v4"                                    # LOOM-evidence-v4 (L-LOOM-212..): v3 minus R7 (the naming verb 「いう」 of 「という」) plus the subject-chain rule; selectable, NOT the default (OP-PUB-6: only after the held-out bank7)
EVIDENCE_V5 = "evidence.v5"                                    # LOOM-evidence-v5 (L-LOOM-219..): v4 plus SU (a question whose subject phrase the cut could not read in full is refused) and TW (the article title stands in for a subject word only as a whole word of the title; a kind word alone is no subject); selectable, NOT the default
EVIDENCE_VERSIONS: Tuple[str, ...] = (EVIDENCE_V1, EVIDENCE_V2, EVIDENCE_V3, EVIDENCE_V4, EVIDENCE_V5)
EVIDENCE_LATEST = EVIDENCE_V2                                  # the rule NEW prose runs get; a ledger replays under the version its begin row recorded.  Stays v2 until the held-out bank6 passes (OP-RE-2)
PROFILE_NAMES: Dict[str, str] = {"v1": EVIDENCE_V1, "v2": EVIDENCE_V2, "v3": EVIDENCE_V3, "v4": EVIDENCE_V4, "v5": EVIDENCE_V5}     # the server / CLI spelling -> the rule version
SCOPE_TITLE, SCOPE_CLAUSE = "clause_or_title", "clause"
SUBJECT_SCOPES: Tuple[str, ...] = (SCOPE_TITLE, SCOPE_CLAUSE)
DEFAULT_SCOPE = SCOPE_TITLE                                    # L-LOOM-190: until the owner answers OP-EV-1 otherwise (he said yes: 2026-10-12)

CODES: Tuple[str, ...] = ("not_quoted", "constructed_unit", "answer_not_word_aligned", "question_form_open", "question_has_no_subject", "no_subject",
                          "wrong_arm", "no_slot_head", "not_copular", "answer_holds_question_unit",
                          "answer_glued", "answer_crosses_break", "multiple_answers",          # the last three are evidence.v2 only
                          "subject_unreadable")                                                # evidence.v5 only (SU)
IGNORE = frozenset("「」『』“”\"'・· 　\t")                  # L-LOOM-177
P7 = gm.P7
ARMS = ("の", "に", "で", "と", "を", "が")                        # the six arm particles (は is the centre relation)
CONN_PARTICLES = frozenset(P7) | {"も"}
JOINERS = frozenset("-‐‑–—−,.:/+")                                # evidence.v2: punctuation that joins the pieces of one token (JR-Y13, 73,921, 1.5, 12:30): not a break
FORM_SLOT, FORM_PREDICATE, FORM_OPEN = "slot", "predicate", "open"
# evidence.v3 (docs/LINE3_LOOM_REACH_DESIGN.md §4.2; closed lists: extending one is a new version, L-LOOM-205)
KIND_REL = frozenset("人物 人 者 国 チーム 選手 団体 施設 会社 組織 都市 街 場所".split())     # R4: the kind-noun heads of a relative-clause question
ALIAS_Y = frozenset("別名 別称 異名".split())                                              # R3: the asked items 「ともいう」 answers
NAMING = frozenset("呼ば 呼ぶ 呼び 呼ん 称さ 称し 称する 称 いう 言う 云う".split())            # R3 / R7: the naming verbs
BRACKET_OPEN, BRACKET_CLOSE = "（(", "）)"                                                   # R2: the gloss brackets
V3_RULE_IDS: Tuple[str, ...] = ("R1", "R2", "R3", "R3b", "R4", "R5", "R6", "R7", "T1", "T2")
V3_RULE_SENTENCE = ("The answer may end with the kind word of the question word (○○区 for どの区); a reading in brackets may stand between the answer and its particle; "
                    "「A ともいう」 answers 別名; 「A が V」 answers 「V した人物/国/…」; 「Y としては A」 reads as 「Y は A」.")


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
    kinds: Tuple[str, ...] = ()                  # evidence.v3 R1 (L-LOOM-202): the kind nouns of the question words (何|線 -> 線); written into `begin` under v3 only
    rel_head: Optional[str] = None               # evidence.v3 R4: the head V of the relative-clause reading 「…V した Y は 誰」 (None = the question has no such reading)
    alias: bool = False                          # evidence.v3 R3: the question asks 「Xの別名/別称/異名は何」

    def to_obj(self, scope: Optional[str] = None, version: str = EVIDENCE_V1) -> dict:
        """The `question` object of `begin` (L-LOOM-185); `version` is the rule version of the run (the cut itself is the same in v1 and v2; v3 adds `kinds`, `relative`, `alias`)."""
        o = {"evidence": version, "subject_scope": scope, "form": self.form,
             "slot": {"phrase": self.slot_phrase, "particle": self.particle, "noun": self.slot_noun, "head": self.slot_head, "fallback": self.fallback},
             "y": self.y, "y_forms": list(self.y_forms), "subject": list(self.subject), "subject_level": self.subject_level, "units": list(self.units)}
        if version == EVIDENCE_V3:
            o["kinds"] = list(self.kinds)
            o["relative"] = None if self.rel_head is None else {"head": self.rel_head}
            o["alias"] = self.alias
        return o


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


def kind_nouns(text: str) -> Tuple[str, ...]:
    """R1 (L-LOOM-202): for every WORD of `text` that is in `grammar.INTERROG`, the content WORD units glued to it (何|線 -> 線, どの|区 -> 区, 何|年 -> 年); if that is empty and
    the word is どこ followed by 「の」 and a touching content WORD, that word (どこの国 -> 国)."""
    ws = gm.words_of(text)
    out: List[str] = []
    for j, (s, a, b) in enumerate(ws):
        if s in gm.INTERROG:
            k, end, run = j, b, ""
            while k + 1 < len(ws) and ws[k + 1][1] == end and _content_word(ws[k + 1][0]):
                k += 1
                end = ws[k][2]
                run += ws[k][0]
            if not run and s == "どこ" and k + 2 < len(ws) and ws[k + 1][0] == "の" and _content_word(ws[k + 2][0]) and ws[k + 2][1] == ws[k + 1][2]:
                run = ws[k + 2][0]
            if run:
                out.append(run)
    return tuple(out)


def _y_index(ws: Sequence[gm.Word], y: str) -> Optional[int]:
    """The index of the first word of the asked item `y` in 「… y は <question word>」 (the item right before the 「は」 before the first question word)."""
    j = next((i for i, w in enumerate(ws) if w[0] in gm.INTERROG), None)
    if j is None or j < 2 or ws[j - 1][0] != "は":
        return None
    acc = ""
    i = j - 2
    while i >= 0:
        acc = ws[i][0] + acc
        if acc == y:
            return i
        if not y.endswith(acc):
            return None
        i -= 1
    return None


def relative_head(text: str, form: str, y: Optional[str]) -> Optional[str]:
    """R4 (L-LOOM-205): for a predicate question whose Y is exactly one of KIND_REL, walk left from Y's first WORD over non-content words, counting auxiliaries (any non-P7 function
    word); one 「と」 may be passed after at least one auxiliary (「地とされた」); stop at any other P7 particle.  If at least one auxiliary was passed and the walk ends on a content
    word V, and no 「が」 occurs among the question's words before V, V is the head of the slot reading 「A が … V」 (唱えた人物 -> 唱え).  None otherwise."""
    if form != FORM_PREDICATE or y not in KIND_REL:
        return None
    ws = gm.words_of(text)
    iy = _y_index(ws, y)
    if iy is None:
        return None
    i, aux, to = iy - 1, 0, 0
    while i >= 0 and not _content_word(ws[i][0]):
        if ws[i][0] in P7:
            if ws[i][0] == "と" and to == 0 and aux > 0:
                to = 1
            else:
                break
        else:
            aux += 1
        i -= 1
    if aux > 0 and i >= 0 and _content_word(ws[i][0]) and "が" not in [w[0] for w in ws[:i]]:
        return ws[i][0]
    return None


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
                         tuple(subject), level, tuple(units), kind_nouns(text), relative_head(text, form, y), form == FORM_PREDICATE and y in ALIAS_Y)


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
        self._prefix: Optional[Dict[int, str]] = None

    def prefix_ends(self) -> Dict[int, str]:
        """evidence.v3 T1 (L-LOOM-209): {the offset at which a prefix token (pos1 接頭辞) ends: its surface}, the WHOLE sentence tagged once by the line-3 tagger (the one `funcwords` uses);
        cached with the view, i.e. per (corpus sha, sid).  A prefix is a function word: it lies in the GAP of the filtered WORD cut, which the v2 glue test does not see."""
        r = self._prefix
        if r is None:
            r = {}
            pos = 0
            for w in sp._get_tagger()(self.text):
                k = self.text.find(w.surface, pos)
                if k < 0:
                    continue
                pos = k + len(w.surface)
                if w.feature.pos1 == "接頭辞":
                    r[pos] = w.surface
            self._prefix = r
        return r

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
    if version == EVIDENCE_V5:                                                          # evidence.v5 (L-LOOM-219): its own path (v4 plus SU and TW)
        return _judge_v5(corpus, qu, scope, sid, tier, i0, i1)
    if version == EVIDENCE_V4:                                                          # evidence.v4 (L-LOOM-212): its own path (v3 minus R7, plus the subject-chain rule)
        return _judge_v4(corpus, qu, scope, sid, tier, i0, i1)
    if version == EVIDENCE_V3:                                                          # evidence.v3 (L-LOOM-201): its own path; v1 / v2 below are byte-for-byte the rules they were
        return _judge_v3(corpus, qu, scope, sid, tier, i0, i1)
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
# evidence.v3 (docs/LINE3_LOOM_REACH_DESIGN.md §4.2, L-LOOM-201..211): v2 + R1..R7 + T1 + T2.  A separate path: the v1 / v2 judge above is not touched.
# ------------------------------------------------------------------------------------------------------------
def _m_glued_prefix(ans: str, prefix: str, sid: int) -> str:
    return "the stretch 「%s」 of sentence %d is glued to the prefix 「%s」 before it; quote the whole word, or the whole phrase, that answers" % (ans, sid, prefix)


def _m_alias_arm(ans: str, got: str, sid: int) -> str:
    return "the answer 「%s」 is followed by 「%s」 in sentence %d; the alias form needs 「とも」 right after the answer (「A ともいう」)" % (ans, got, sid)


def _m_alias_head(cl: str, sid: int) -> str:
    return "the clause 「%s」 of sentence %d holds no naming word (いう 呼ば 称さ ...) outside the answer: this clause does not say 「A ともいう」" % (cl, sid)


def _read_idx(surfs: Sequence[str], gap, idxs, s: str, avoid: Optional[Tuple[int, int]] = None, joiner: bool = False) -> List[Tuple[int, int]]:
    """§4.3 over an arbitrary set of unit indexes `idxs` (a range, or the clause with a gloss cut out of it): every (i, j), j reached from i over consecutive indexes of `idxs`
    whose WORD surfaces touch and spell `s` (without the ignorable characters), disjoint from `avoid`.  R6 (`joiner`): a gap made only of JOINERS is crossed and its characters
    are part of the spelled string (「U-17ワールドカップ」); any other gap breaks the reading."""
    target = strip_ignore(s)
    out: List[Tuple[int, int]] = []
    if not target:
        return out
    pos = idxs if isinstance(idxs, range) else frozenset(idxs)
    for i in idxs:
        acc = ""
        j = i
        while j in pos:
            if j > i:
                g = strip_ignore(gap(j - 1))
                if g != "":
                    if joiner and all(ch in JOINERS for ch in g):
                        acc += g
                    else:
                        break
            acc += strip_ignore(surfs[j])
            if not target.startswith(acc):
                break
            if acc == target:
                if avoid is None or j < avoid[0] or i > avoid[1]:
                    out.append((i, j))
                break
            j += 1
    return out


def _title_read(title: str, s: str, joiner: bool) -> bool:
    """The article title reads `s` (R6: across joiner punctuation)."""
    ts, tg, tn = _title_reader(title)
    target = strip_ignore(s)
    if not tn or not target:
        return False
    for i in range(tn):
        acc = ""
        for j in range(i, tn):
            if j > i:
                g = strip_ignore(tg(j - 1))
                if g != "":
                    if joiner and all(ch in JOINERS for ch in g):
                        acc += g
                    else:
                        break
            acc += strip_ignore(ts[j])
            if not target.startswith(acc):
                break
            if acc == target:
                return True
    return False


def _gloss_end(text: str, ce: int) -> Optional[int]:
    """R2 (L-LOOM-203): if one bracketed group starts right after offset `ce` (ignorable characters skipped) and its matching closing bracket (nesting counted) comes before any
    「。」, the offset after that bracket; else None."""
    i = ce
    while i < len(text) and text[i] in IGNORE:
        i += 1
    if i >= len(text) or text[i] not in BRACKET_OPEN:
        return None
    depth = 0
    for k in range(i, len(text)):
        if text[k] in BRACKET_OPEN:
            depth += 1
        elif text[k] in BRACKET_CLOSE:
            depth -= 1
            if depth == 0:
                return k + 1
        elif text[k] == "。":
            return None
    return None


@dataclass(frozen=True)
class _Reading:
    """One way a question is read against a stretch: the question's own (`base`), the relative-clause slot reading (`rel`, R4), the alias predicate (`alias`, R3)."""
    tag: str
    form: str
    particle: Optional[str]
    noun: Optional[str]
    head: Optional[str]
    alias: bool = False


def _v3_readings(qu: QuestionUnits, off: frozenset) -> List[_Reading]:
    out = [_Reading("base", qu.form, qu.particle, qu.slot_noun, qu.slot_head)]
    if qu.rel_head is not None and "R4" not in off:
        out.append(_Reading("rel", FORM_SLOT, "が", None, qu.rel_head))
    if qu.alias and "R3" not in off:
        out.append(_Reading("alias", FORM_PREDICATE, "と", qu.slot_noun, None, True))
    return out


def _v3_reading(corpus, v: "SentenceView", qu: QuestionUnits, rd: _Reading, scope: str, sid: int, a0: int, a1: int, answer: str, off: frozenset) -> Tuple[List[dict], Optional[dict], str, List[str]]:
    """The checks of evidence.v3 for ONE reading of the question: (failures, evidence | None, the clause text, the v3 rules this reading used)."""
    fails: List[dict] = []
    used: List[str] = []

    def fail(code: str, message: str, **kw) -> None:
        fails.append(dict({"code": code, "message": message}, **kw))

    def use(rule: str) -> None:
        if rule not in used:
            used.append(rule)

    n = len(v.units)
    surfs, gap = v.units, v.gap
    joiner = "R6" not in off
    avoid = (a0, a1)

    def read(idxs, s: str, av=avoid) -> List[Tuple[int, int]]:
        hits = _read_idx(surfs, gap, idxs, s, av, joiner)
        if joiner and any(strip_ignore(gap(k)) != "" for i_, j_ in hits for k in range(i_, j_)):
            use("R6")
        return hits

    if rd.form == FORM_OPEN:
        fail("question_form_open", _m_open(qu.text))
    # F2 (v2) + T1: the extent of the answer
    if (a0 > 0 and joined(gap(a0 - 1))) or (a1 < n - 1 and joined(gap(a1))):
        fail("answer_glued", _m_glued(answer, whole_word_of(v, a0, a1), sid))
    elif "T1" not in off:
        pre = v.prefix_ends().get(v.spans[a0][0])
        if pre is not None:
            fail("answer_glued", _m_glued_prefix(answer, pre, sid))
    brk = next((gap(k) for k in range(a0, a1) if not inner_ok(gap(k))), None)
    if brk is not None:
        fail("answer_crosses_break", _m_break(answer, strip_ignore(brk) or brk, sid))
    lo, hi = clause_bounds(v, a0, a1, True)
    idxs = range(lo, hi + 1)
    cl_hi = hi
    after_pos = v.spans[a1][1]                                                   # where the arm particle is read
    # R2: ONE bracketed gloss right after the answer, only when the clause ends at the answer
    if rd.form == FORM_SLOT and "R2" not in off and hi == a1:
        ge = _gloss_end(v.text, v.spans[a1][1])
        if ge is not None:
            k = next((k for k in range(a1 + 1, n) if v.spans[k][0] >= ge), None)
            if k is not None and connective(v.text[ge:v.spans[k][0]], True):
                h2 = k
                while h2 < n - 1 and connective(gap(h2), True):
                    h2 += 1
                after_pos, cl_hi = ge, h2
                idxs = sorted(set(range(lo, a1 + 1)) | set(range(k, h2 + 1)))     # the units INSIDE the brackets are not part of the clause
                use("R2")
    cl = clause_text(v, lo, cl_hi)
    # R5: 「Y としては A」 reads as 「Y は A」 (the subject is read in the union of the answer's clause and Y's clause)
    toshite = False
    if rd.form == FORM_PREDICATE and not rd.alias and "R5" not in off and a0 > 0 and strip_ignore(gap(a0 - 1)) in ("としては", "としては、") and qu.y_forms:
        l2, _h2 = clause_bounds(v, a0 - 1, a0 - 1, True)
        for f_ in qu.y_forms:
            if any(j == a0 - 1 for _i, j in read(range(l2, a0), f_, None)):
                toshite = True
                idxs = sorted(set(idxs) | set(range(l2, a0)))
                use("R5")
                break
    # E-3: the subject
    subj_ev: List[dict] = []
    title_scope = scope == SCOPE_TITLE
    if not qu.subject and rd.form in (FORM_SLOT, FORM_PREDICATE):
        fail("question_has_no_subject", _m_no_subject_at_all(qu.text))
    for s in qu.subject:
        if read(idxs, s):
            subj_ev.append({"run": s, "via": "clause"})
        elif title_scope and _title_read(v.title, s, joiner):
            subj_ev.append({"run": s, "via": "title"})
            if joiner and any(ch in JOINERS for ch in strip_ignore(s)):
                use("R6")
        else:
            fail("no_subject", _m_no_subject(s, cl, sid, v.title if title_scope else None), subject=s)
    slot_ev = None
    copula = None
    if rd.form == FORM_SLOT or rd.alias:
        if rd.alias:                                                             # R3: 「A とも <naming verb>」
            nxt = a1 + 1 < n and strip_ignore(v.text[after_pos:v.spans[a1 + 1][0]]) == "とも"
            if not nxt:
                lab, f, _ = gm.follower(v.raw, after_pos, "whole_word")
                fail("wrong_arm", _m_alias_arm(answer, f if f is not None else "(end)", sid))
            found = bool(read(idxs, "いう"))
            if not found:
                found = any(surfs[i] in NAMING for i in idxs if i < a0 or i > a1)
            if not found:
                fail("no_slot_head", _m_alias_head(cl, sid))
        else:
            p = rd.particle
            lab, f, _ = gm.follower(v.raw, after_pos, "whole_word")
            if lab == "particle" and f == p:
                from verantyx.loom.state import AXES, SPEC
                slot_ev = {"particle": p, "arm": AXES[list(SPEC.arms).index(p)] if p in SPEC.arms else None}
            else:
                fail("wrong_arm", _m_wrong_arm(answer, f if f is not None else "(end)", p, qu.slot_phrase or "", sid))
            if rd.head is None:
                fail("no_slot_head", _m_head_none(qu.text))
            else:
                found = bool(read(idxs, rd.head))
                if not found and rd.head in NAMING and "R7" not in off:         # R7: any naming word of the clause outside the answer
                    found = any(surfs[i] in NAMING for i in idxs if i < a0 or i > a1)
                    if found:
                        use("R7")
                if not found:
                    fail("no_slot_head", _m_head_clause(rd.head, cl, sid))
    elif rd.form == FORM_PREDICATE:
        reads: List[Tuple[str, int, int]] = []
        for f_ in qu.y_forms:
            for (i, j) in read(idxs, f_):
                reads.append((f_, i, j))
        if toshite:
            copula = "Y としては A"
        if not reads and copula is None:                                         # E-4p
            fail("no_slot_head", _m_item(qu.y or "", cl))
        elif copula is None:
            for f_, y0, y1 in reads:
                g_after = gap(y1) if y1 + 1 < n else None
                if g_after in ("は", "は、") and a0 == y1 + 1:
                    copula = "Y は A"
                    break
                if a1 + 1 < n and gap(a1) in ("は", "は、") and y0 > a1 and all(strip_ignore(gap(k)) == "" or strip_ignore(gap(k)) in ARMS for k in range(a1 + 1, y1)):
                    copula = "A は … Y"
                    break
            if copula is None:                                                   # E-5p
                fail("not_copular", _m_copula(answer, cl))
    # E-6 (+ T2, R1, R3b)
    echo: List[str] = []
    if "T2" not in off:                                                          # T2: the bare kind noun (or slot noun) is no answer
        bare = strip_ignore(v.text[v.spans[a0][0]:v.spans[a1][1]])
        if bare in qu.kinds or (rd.noun is not None and bare == rd.noun):
            echo.append(bare)
    for u in qu.units:
        hits = _read_idx(surfs, gap, range(a0, a1 + 1), u)
        if not hits:
            continue
        if "R1" not in off and u in qu.kinds and all(i > a0 for i, _j in hits) and (u != qu.kinds[-1] or any(j == a1 for _i, j in hits)):
            use("R1")                                                            # R1: the kind noun of the question word may END the answer (新潟市西区 for どの区)
            continue
        if rd.alias and "R3b" not in off and any(u != s and u in s for s in qu.subject) and all(u != s for s in qu.subject):
            use("R3b")                                                           # R3b: a proper piece of a subject run (アワド語 vs アワディー語's 語)
            continue
        if u not in echo:
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
        if rd.tag == "alias":
            ev["via"] = "alias"
            use("R3")
        elif rd.tag == "rel":
            ev["via"], ev["head"] = "relative", rd.head
            use("R4")
    return fails, ev, cl, used


def _judge_v3(corpus, qu: QuestionUnits, scope: str, sid: int, tier: str, i0: int, i1: int, off: frozenset = frozenset()) -> dict:
    """`judge_quote` under evidence.v3.  A stretch passes when ANY reading of the question passes (the question's own, R4's relative reading, R3's alias reading); when none passes
    the failures reported are those of the reading with the fewest codes (the question's own first).  `off`: rule ids (V3_RULE_IDS) switched off -- the ablation of the tests only;
    the product never passes it.  The result also carries `reading` (base | rel | alias) and `rules` (the v3 rules the passing reading used; [] for a refused stretch)."""
    v = view_of(corpus, sid)
    sps = corpus.spans().spans(tier, sid)
    cs, ce = sps[i0][0], sps[i1][1]
    answer = v.text[cs:ce]
    a0 = next((k for k, s in enumerate(v.spans) if s[0] == cs), None)
    a1 = next((k for k, s in enumerate(v.spans) if s[1] == ce), None)
    out = {"answer": answer, "clause": None, "sid": sid, "source": v.source, "reading": None, "rules": []}
    if not (a0 is not None and a1 is not None and a0 <= a1):
        fails = [{"code": "answer_not_word_aligned", "message": _m_not_aligned(answer, sid)}]
        if qu.form == FORM_OPEN:
            fails.append({"code": "question_form_open", "message": _m_open(qu.text)})
        return _done(out, fails, None)
    best = None
    for rd in _v3_readings(qu, off):
        fails, evd, cl, used = _v3_reading(corpus, v, qu, rd, scope, sid, a0, a1, answer, off)
        k = len({f["code"] for f in fails})
        if best is None or k < best[0]:
            best = (k, rd, fails, evd, cl, used)
        if not fails:
            break
    _k, rd, fails, evd, cl, used = best
    out["clause"], out["reading"], out["rules"] = cl, rd.tag, ([] if fails else used)
    return _done(out, fails, evd)


def v3_rules_digest() -> str:
    """The sha256 of the frozen v3 rules (L-LOOM-211): the closed lists, the rule sentence, and the source text of every function that carries a v3 rule.  A change to any of them is
    a new rule version (evidence.v4) and needs a new held-out set; the tests pin this digest."""
    import hashlib
    import inspect
    import json
    funcs = (kind_nouns, _y_index, relative_head, question_units, QuestionUnits.to_obj, SentenceView.prefix_ends, _read_idx, _title_read, _gloss_end, _v3_readings, _v3_reading,
             _judge_v3, _m_glued_prefix, _m_alias_arm, _m_alias_head)
    obj = {"version": EVIDENCE_V3, "ids": list(V3_RULE_IDS), "KIND_REL": sorted(KIND_REL), "ALIAS_Y": sorted(ALIAS_Y), "NAMING": sorted(NAMING),
           "brackets": [BRACKET_OPEN, BRACKET_CLOSE], "JOINERS": sorted(JOINERS), "IGNORE": sorted(IGNORE), "sentence": V3_RULE_SENTENCE,
           "functions": {f.__qualname__: hashlib.sha256(inspect.getsource(f).encode("utf-8")).hexdigest() for f in funcs}}
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------------
# evidence.v4 (docs/LINE3_PUBLIC_DESIGN.md §5, L-LOOM-212..): v3 minus R7, plus the subject-chain rule.  A separate path ADDED after the v3 code: no function of the frozen v3 digest is
# edited; `_judge_v3` is called with R7 switched off (its `off` argument) and the chain rule is checked on top of its verdict.
# ------------------------------------------------------------------------------------------------------------
V4_RULE_IDS: Tuple[str, ...] = ("R1", "R2", "R3", "R3b", "R4", "R5", "R6", "T1", "T2", "CH")        # v3's ids without R7, plus CH (the subject chain)
V4_OFF = frozenset({"R7"})
V4_RULE_SENTENCE = ("The answer may end with the kind word of the question word (○○区 for どの区); a reading in brackets may stand between the answer and its particle; "
                    "「A ともいう」 answers 別名; 「A が V」 answers 「V した人物/国/…」; 「Y としては A」 reads as 「Y は A」; "
                    "when the subject is a chain 「XのYの…」 (隣駅の駅番号), every noun of the chain must be in the clause that answers.")


def _m_no_chain(s: str, cl: str, sid: int) -> str:
    return "the noun 「%s」 of the question's subject chain is not in the clause 「%s」 of sentence %d: a statement about another entity does not answer a question about 「%s」" % (s, cl, sid, s)


@lru_cache(maxsize=None)
def _subject_chain(text: str) -> Tuple[str, ...]:
    """The genitive chain of a PREDICATE question, OUTERMOST noun first (「花園町駅の隣駅の駅番号は」 -> (花園町駅, 隣駅)); () when the question is not a predicate question or
    Y has no 「X の」 before it.  The same walk as step 7 of `question_units` (L-LOOM-175), which is not touched: the tests pin that the first noun here is `subject[0]` exactly when
    the cut's `subject_level` is x_chain."""
    r = gm.read_question(text)
    t = r.text
    words = gm.words_of(t)
    slot = r.slot
    fallback = False
    if slot is None:
        for fr in r.frames:
            if any(fr.unit.startswith(m) for m in gm.INTERROG):
                slot = gm.Slot(fr.unit, fr.span, fr.particle, fr.after)
                fallback = True
                break
    p = None if slot is None else slot.particle
    noun_span: Optional[Tuple[int, int]] = None
    if slot is not None and p is not None:
        lab, f, sps = gm.follower(words, slot.span[1])
        p_end = sps[1] if sps else None
        if p == "の":
            j = next((i for i, w in enumerate(words) if w[1] >= p_end), None) if p_end is not None else None
            if j is not None and words[j][1] == p_end and _content_word(words[j][0]):
                lab2, f2, sps2 = gm.follower(words, words[j][2])
                if lab2 == "particle" and f2 != "の":
                    p, noun_span = f2, (words[j][1], words[j][2])
    pred = None
    if slot is not None and not fallback:
        pred = r.predicate
    elif slot is not None and fallback and slot.particle is None:
        pred = gm.predicate_of(words, slot)
    if pred is None or pred.y is None or (slot is not None and p in P7):
        return ()
    kept, runs = _s_runs(t, words)
    excl: List[Tuple[int, int]] = [slot.span] if slot is not None else []
    if noun_span is not None:
        excl.append(noun_span)
    excl.append(pred.y_span)
    free = [r_ for r_ in runs if not _overlaps(r_["a"], r_["b"], excl)]
    cur = pred.y_span[0]
    chain: List[str] = []
    while True:
        hit = next((r_ for r_ in free if r_["after"] == "の" and r_["b"] <= cur and strip_ignore(t[r_["b"]:cur]) == "の"), None)
        if hit is None:
            break
        chain.append(hit["s"])
        cur = hit["a"]
    return tuple(reversed(chain))


def subject_chain(qu: QuestionUnits) -> Tuple[str, ...]:
    """evidence.v4: the subject chain of the question cut `qu`, outermost noun first; () when the cut did not read the subject as an x_chain."""
    if qu.subject_level != "x_chain":
        return ()
    return _subject_chain(qu.text)


def question_obj(qu: QuestionUnits, scope: Optional[str], version: str) -> dict:
    """The `question` object of the `begin` row under `version`: `QuestionUnits.to_obj` for v1..v3 (unchanged); v4 = the v3 object labelled evidence.v4 plus `chain`."""
    if version != EVIDENCE_V4:
        return qu.to_obj(scope, version)
    o = qu.to_obj(scope, EVIDENCE_V3)
    o["evidence"] = EVIDENCE_V4
    o["chain"] = list(subject_chain(qu))
    return o


def _judge_v4(corpus, qu: QuestionUnits, scope: str, sid: int, tier: str, i0: int, i1: int) -> dict:
    """`judge_quote` under evidence.v4: the v3 judge with R7 off, and then the CHAIN rule for every reading: each noun of the question's subject chain except the outermost
    (which the v3 subject check already reads, in the clause or in the article title) must be read in the clause around the answer, disjoint from the answer.  A failure is a
    `no_subject` failure naming that noun.  The result also carries `chain` (the whole chain, outermost first)."""
    out = _judge_v3(corpus, qu, scope, sid, tier, i0, i1, V4_OFF)
    chain = subject_chain(qu)
    out["chain"] = list(chain)
    inner = chain[1:]
    if not inner or out["clause"] is None:
        return out
    v = view_of(corpus, sid)
    sps = corpus.spans().spans(tier, sid)
    cs, ce = sps[i0][0], sps[i1][1]
    a0 = next(k for k, s in enumerate(v.spans) if s[0] == cs)
    a1 = next(k for k, s in enumerate(v.spans) if s[1] == ce)
    lo, hi = clause_bounds(v, a0, a1, True)
    cl = clause_text(v, lo, hi)
    fails = list(out["failures"])
    for s in inner:
        if not _read_idx(v.units, v.gap, range(lo, hi + 1), s, (a0, a1), True):
            fails.append({"code": "no_subject", "message": _m_no_chain(s, cl, sid), "subject": s})
    if len(fails) == len(out["failures"]):
        if not fails:
            out["rules"] = list(out["rules"]) + ["CH"]
        return out
    ev = None
    out["rules"] = []
    return _done(out, fails, ev)


def v4_rules_digest() -> str:
    """The sha256 of the frozen v4 rules (L-LOOM-212): the v3 digest (so a change to anything v3 froze changes this too), v4's ids, switched-off set and rule sentence, and the source text
    of every function that carries a v4 rule.  A change is evidence.v5 and needs a new held-out set; the tests pin this digest."""
    import hashlib
    import inspect
    import json
    funcs = (_m_no_chain, _subject_chain, subject_chain, question_obj, _judge_v4)
    obj = {"version": EVIDENCE_V4, "v3": v3_rules_digest(), "ids": list(V4_RULE_IDS), "off": sorted(V4_OFF), "sentence": V4_RULE_SENTENCE,
           "functions": {f.__qualname__: hashlib.sha256(inspect.getsource(f).encode("utf-8")).hexdigest() for f in funcs}}
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------------
# evidence.v5 (L-LOOM-219..): v4 plus SU and TW.  A separate path ADDED after the v4 code: no function of the frozen v3 / v4 digests is edited; `_v3_reading` is called as `_judge_v3`
# calls it (R7 off), the chain rule is the v4 one, and the two new rules are checked on top.  Cause (bank7, B7-U43 「ネノの属するネノ県の人口は何人ですか？」): the katakana name ネノ
# drops out of the question cut, the subject becomes the bare kind noun 県, and the title 「テレゴ県」 of another article read it as a word of the title.
# ------------------------------------------------------------------------------------------------------------
V5_RULE_IDS: Tuple[str, ...] = V4_RULE_IDS + ("SU", "TW")
V5_OFF = V4_OFF
# TW: the kind / suffix nouns.  The v3 list KIND_REL (the kind heads of a relative-clause question) plus the place / line / time / thing suffixes; a CLOSED list (extending it is a new version).
KIND_SUFFIX: frozenset = KIND_REL | frozenset("県 市 区 町 村 都 道 府 郡 駅 線 社 年 月 日 島 山 川 湖 海 語 号 局 校 館 院 園 部 課 店".split())
V5_RULE_SENTENCE = (V4_RULE_SENTENCE + " A question whose subject phrase holds a name the reader could not read (a katakana, kanji or Latin piece the question cut dropped) is refused; "
                    "the article title stands in for a subject word only as a whole word of the title, and a kind word alone (県 市 駅 線 ...) is no subject.")


def _m_unreadable(unread: Sequence[str], q: str) -> str:
    return "the subject phrase of the question 「%s」 holds %s that the reader could not read as a word, so no sentence can be tied to its subject" % (q, "、".join("「%s」" % u for u in unread))


def _m_kind_only(subject: Sequence[str], q: str) -> str:
    return "the only subject word of the question 「%s」 is the kind word %s: a kind word names no entity, so a sentence cannot be tied to it" % (q, "、".join("「%s」" % s for s in subject))


def _m_no_subject_whole(s: str, cl: str, sid: int, title: str) -> str:
    return "the subject 「%s」 of the question is not in the clause 「%s」 of sentence %d, and it is not a whole word of its article title 「%s」" % (s, cl, sid, title)


@lru_cache(maxsize=None)
def _subject_unread(text: str, slot_phrase: Optional[str]) -> Tuple[str, ...]:
    """SU (L-LOOM-219): the characters of the question's SUBJECT PHRASE that the cut neither keeps nor reads as grammar, grouped in runs.  The subject phrase is the text before the
    predicate's 「は / が」: before the question word (the slot phrase, else the first interrogative WORD), the last 「は」 or 「が」 word; with none, the text up to the question word.  It holds the whole
    の-chain and every relative clause.  A character is READ when a kept RUN unit of the cut (`_s_runs`) covers it or a function RUN unit does; a hiragana character is grammar (the tail of 使われた,
    の する) and is never reported; the ignorable characters and the punctuation are not content.  What is left is a name the cut dropped (the katakana ネノ: its pieces are no content WORD)."""
    ws = gm.words_of(text)
    s = text.find(slot_phrase) if slot_phrase else -1
    if s < 0:
        q = next((w for w in ws if w[0] in gm.INTERROG), None)
        if q is None:
            return ()
        s = q[1]
    piv = max([w[1] for w in ws if w[0] in ("は", "が") and w[2] <= s], default=s)
    cov = set()
    for _u, a, b in _s_runs(text, ws)[0]:
        cov.update(range(a, b))
    for u, a, b in _raw_spans(sp.RUN, text):
        if is_function_unit(u, sp.RUN):
            cov.update(range(a, b))
    out: List[str] = []
    cur = ""
    for k in range(piv):
        c = text[k]
        if k not in cov and c.isalnum() and not ("぀" <= c <= "ゟ") and c not in IGNORE:
            cur += c
        else:
            if cur:
                out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return tuple(out)


def subject_unread(qu: QuestionUnits) -> Tuple[str, ...]:
    """evidence.v5 SU: the unread pieces of the question's subject phrase; () = the whole subject phrase is read."""
    return _subject_unread(qu.text, qu.slot_phrase)


def kind_only_subject(qu: QuestionUnits) -> bool:
    """evidence.v5 TW: the question has subject words and every one of them is a kind / suffix noun (県, 市, 駅, ...)."""
    return bool(qu.subject) and all(strip_ignore(s) in KIND_SUFFIX for s in qu.subject)


@lru_cache(maxsize=None)
def _title_run_strings(title: str) -> frozenset:
    """TW: the WHOLE words of an article title as the question cut reads a name: the merged S-runs of the title (`_s_runs`, the machinery that builds the question's subject runs: touching
    content units are one run, 「花園町駅」 not 「花園町」 + 「駅」), with the runs joined across joiner punctuation (R6: 「U-17ワールドカップ」) merged into one string.  A subject unit is a word of
    the title only if it spells exactly one of these strings; a piece of one (県 of 「テレゴ県」, 六 of 「六日町駅」) is a containment and is not."""
    runs = _s_runs(title, gm.words_of(title))[1]
    out: List[List] = []
    for r in runs:
        if out:
            g = strip_ignore(title[out[-1][2]:r["a"]])
            if all(ch in JOINERS for ch in g):
                out[-1][0] += g + r["s"]
                out[-1][2] = r["b"]
                continue
        out.append([r["s"], r["a"], r["b"]])
    return frozenset(o[0] for o in out)


def _tw_recheck(v: "SentenceView", fails: List[dict], evd: Optional[dict], used: List[str], sid: int) -> Tuple[List[dict], Optional[dict], List[str]]:
    """TW on one passing reading of v3: every subject word read through the article TITLE must be a whole word of the title (`_title_run_strings`), else a `no_subject` failure."""
    if fails or evd is None:
        return fails, evd, used
    fails = list(fails)
    via_title = False
    for e in evd["subject"]:
        if e["via"] == "title":
            if strip_ignore(e["run"]) in _title_run_strings(v.title):
                via_title = True
            else:
                fails.append({"code": "no_subject", "message": _m_no_subject_whole(e["run"], evd["clause"], sid, v.title), "subject": e["run"]})
    if fails:
        return fails, None, []
    return fails, evd, (used + ["TW"] if via_title and "TW" not in used else used)


def _v5_question_failures(qu: QuestionUnits, off: frozenset) -> List[dict]:
    """The failures that belong to the QUESTION and not to a stretch: SU `subject_unreadable`, TW `question_has_no_subject` for a kind word alone."""
    fails: List[dict] = []
    if "SU" not in off:
        un = subject_unread(qu)
        if un:
            fails.append({"code": "subject_unreadable", "message": _m_unreadable(un, qu.text), "unread": list(un)})
    if "TW" not in off and kind_only_subject(qu):
        fails.append({"code": "question_has_no_subject", "message": _m_kind_only(qu.subject, qu.text)})
    return fails


def begin_question_obj(qu: QuestionUnits, scope: Optional[str], version: str) -> dict:
    """The `question` object of the `begin` row under `version` (ops.Run.begin): `question_obj` for v1..v4 (unchanged), and for v5 the v4 object labelled evidence.v5 plus `unread` (the pieces of
    the subject phrase the cut could not read; [] = none)."""
    if version != EVIDENCE_V5:
        return question_obj(qu, scope, version)
    o = question_obj(qu, scope, EVIDENCE_V4)
    o["evidence"] = EVIDENCE_V5
    o["unread"] = list(subject_unread(qu))
    return o


def _judge_v5(corpus, qu: QuestionUnits, scope: str, sid: int, tier: str, i0: int, i1: int, off: frozenset = frozenset()) -> dict:
    """`judge_quote` under evidence.v5 = the v4 judge (v3 with R7 off, and the chain rule CH) with two additions.  SU: a question whose subject phrase holds an unread piece is refused for
    every stretch (`subject_unreadable`).  TW: a kind word alone is no subject (`question_has_no_subject`), and a subject word may stand in the article title only as a whole word of it
    (`_tw_recheck`, applied to each reading before one is chosen).  `off`: rule ids ("SU", "TW") switched off -- the ablation of the tests only (all off = `_judge_v4`); the product never passes it."""
    v = view_of(corpus, sid)
    sps = corpus.spans().spans(tier, sid)
    in_range = 0 <= i0 <= i1 < len(sps)                                                 # the v5 gate never raises: a stretch outside the sentence is an unaligned stretch
    cs, ce = (sps[i0][0], sps[i1][1]) if in_range else (0, 0)
    answer = v.text[cs:ce]
    a0 = next((k for k, s in enumerate(v.spans) if s[0] == cs), None) if in_range else None
    a1 = next((k for k, s in enumerate(v.spans) if s[1] == ce), None) if in_range else None
    chain = subject_chain(qu)
    out = {"answer": answer, "clause": None, "sid": sid, "source": v.source, "reading": None, "rules": [], "chain": list(chain)}
    qf = _v5_question_failures(qu, off)
    if qf:
        if qu.form == FORM_OPEN:
            qf.append({"code": "question_form_open", "message": _m_open(qu.text)})
        return _done(out, qf, None)
    if not (a0 is not None and a1 is not None and a0 <= a1):
        fails = [{"code": "answer_not_word_aligned", "message": _m_not_aligned(answer, sid)}]
        if qu.form == FORM_OPEN:
            fails.append({"code": "question_form_open", "message": _m_open(qu.text)})
        return _done(out, fails, None)
    best = None
    for rd in _v3_readings(qu, V5_OFF):
        fails, evd, cl, used = _v3_reading(corpus, v, qu, rd, scope, sid, a0, a1, answer, V5_OFF)
        if "TW" not in off:
            fails, evd, used = _tw_recheck(v, fails, evd, used, sid)
        k = len({f["code"] for f in fails})
        if best is None or k < best[0]:
            best = (k, rd, fails, evd, cl, used)
        if not fails:
            break
    _k, rd, fails, evd, cl, used = best
    out["clause"], out["reading"] = cl, rd.tag
    fails = list(fails)
    n0 = len(fails)
    inner = chain[1:]
    if inner:                                                                           # CH, exactly as `_judge_v4`
        lo, hi = clause_bounds(v, a0, a1, True)
        cl2 = clause_text(v, lo, hi)
        for s in inner:
            if not _read_idx(v.units, v.gap, range(lo, hi + 1), s, (a0, a1), True):
                fails.append({"code": "no_subject", "message": _m_no_chain(s, cl2, sid), "subject": s})
    if len(fails) > n0:
        out["rules"] = []
        return _done(out, fails, None)
    out["rules"] = [] if fails else (list(used) + (["CH"] if inner else []))
    return _done(out, fails, evd)


def v5_rules_digest() -> str:
    """The sha256 of the frozen v5 rules (L-LOOM-219): the v4 digest (so a change to anything v3 or v4 froze changes this too), v5's ids, switched-off set, kind-noun list and rule sentence, and the
    source text of every function that carries a v5 rule.  A change is evidence.v6 and needs a new held-out set; the tests pin this digest."""
    import hashlib
    import inspect
    import json
    funcs = (_m_unreadable, _m_kind_only, _m_no_subject_whole, _subject_unread, subject_unread, kind_only_subject, _title_run_strings, _tw_recheck, _v5_question_failures, begin_question_obj,
             _judge_v5)
    obj = {"version": EVIDENCE_V5, "v4": v4_rules_digest(), "ids": list(V5_RULE_IDS), "off": sorted(V5_OFF), "KIND_SUFFIX": sorted(KIND_SUFFIX), "sentence": V5_RULE_SENTENCE,
           "functions": {f.__qualname__: hashlib.sha256(inspect.getsource(f).encode("utf-8")).hexdigest() for f in funcs}}
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


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
