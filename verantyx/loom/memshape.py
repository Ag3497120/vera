"""PUB-M1: the shape exchanger (docs/LINE3_PUBLIC_DESIGN.md 4.2; owner OP-PUB-2: a sentence that fits no shape is recorded as F0 and may be kept as a sentence without a shape).

`exchange(sentence)` is a PURE FUNCTION of one sentence: it cuts the sentence into clauses with the grammar layer and gives every clause a SHAPE, the centre, the arm seats, the value seat and the
character span of the clause.  It reads no store, no corpus and no history, writes nothing and is deterministic (no clock, no float, no environment; no output depends on set / dict order).

THE GRAMMAR LAYER IS THE ONLY SOURCE OF UNITS.  The units of a sentence are exactly the loom's WORD-tier units: the tagger cut `granularity._raw_spans` makes (`grammar.words_of`), minus the function
units of `funcwords.is_function_unit` (L-150).  What lies between two units is their GAP (the letters of the function units between them, as `Corpus.span_gaps`); units that touch (gap "") form one
PHRASE.  A gap the loom's `weave_span` can write is one of the six arm particles の に で と を が or は; any other gap (では, という, として, も, へ, ...) makes the clause F0 `gap_is_not_a_particle`,
the very judgement that refuses a `write` today (`span_inexpressible`).  The three differences from today are written down as L-PUB-: a chain 「XのYのZ」 and a case particle after a の-chain
(`nested_particle_chain` of weave_span) are shapes now; 「から」 is a gap only in a change clause.

THE CLAUSE CUT.  Hard cuts: 。 ． ! ? ！ ？ ; ； and a line break.  Soft cuts: 、 ， and ASCII "," (but not a comma between two digits: 2,400).  A colon (： or :, not between digits) ends a LABEL
(「監視設定メモ:」): the label is listed in `skipped`, it is not a clause.  A piece without any letter is nothing; a piece with letters but without a unit is F0 `no_unit`.  A LEADING ADVERBIAL (a piece ended by a
soft cut that is only function words (では、 しかし、 はい、) or only time words (昨日、 来週は、), and is followed by a clause) is not a clause: it is attached to the following clause as `adverbial`.

THE SHAPES (frozen; `SHAPES_SHA` is the sha256 of the version, the constants and the SOURCE of every rule below):
  F1 属性      「X の Y は A」  centre = the PHRASE Y as it is written (開催地; `centre_units` = its WORD units 開催, 地), arm の = X (a chain 「X の Y の Z は A」: centre Z, arm の = Y whose own arm の = X),
               value = A (a noun phrase, may hold の); every seat is a phrase (`text`) with its units.
  F2 主題値    「X は A」      centre = X, no arm, value = A.
  F3 出来事    case arguments が を に で と + a predicate: centre = the PREDICATE ONLY (a サ変 noun followed by する/し/さ/なる or by 済み, or a verb: the centre of a verb is its DICTIONARY FORM, the lemma of the
               tokenizer, 開いた -> 開く, and the inflected surface is kept in `surface`: owner, the memory takes inflected verbs in, the output gate does not); arms = the arguments, one per particle; a numeral + counter touching the predicate is the `quantity` seat (52本), other nouns touching it the `object_bare` seat (資料), never part of the centre.  「X は …」 with arguments after the は is F3 whose subject arm が is X (`via_topic`).
  F4 主語なし  an event clause with no が and no は: the arms are the arguments it has (may be none); the clause goes to the open topic's nest (M3).
  F0 形なし    anything else; `reason` says why: no_unit | gap_is_not_a_particle | negated | question | no_predicate | no_relation | case_before_topic | two_topics |
               repeated_case_particle | coordination | value_not_noun.
  CHANGE       「[X は | Y を] A から B に 変更」: a change clause keeps the shape of its slot (F1 when the slot has a の-arm, else F2; no slot: F4), value = B, `change` = (old A, new B).
"""
from __future__ import annotations

import hashlib
import inspect
import json
import unicodedata
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.lang import strip_attribution
from verantyx.line3 import grammar as gm
from verantyx.line3 import space as sp
from verantyx.line3.funcwords import is_function_unit

SHAPES_VERSION = "shape.v1"
SHAPE_NAMES: Dict[str, str] = {"F1": "属性", "F2": "主題値", "F3": "出来事", "F4": "主語なし", "F0": "形なし"}
SHAPE_ORDER: Tuple[str, ...] = ("F1", "F2", "F3", "F4", "F0")
F0_REASONS: Tuple[str, ...] = ("no_unit", "gap_is_not_a_particle", "negated", "question", "no_predicate", "no_relation", "case_before_topic", "two_topics",
                               "repeated_case_particle", "coordination", "value_not_noun")

ARM_PARTICLES = "のにでとをが"                      # the six arms of the foundation (grammar.ARM_PARTICLES)
CASE_ARGS = "がをにでと"                            # the argument particles of an event (の is the chain particle, は the topic)
READ_ORDER = "がをとでにの"                         # OP-LOOM-3: the order the arms are read in (then the centre)
TOPIC = "は"
FROM, TO, CHANGE_PREDICATE = "から", "に", "変更"
HARD_CUTS = "。．!?！？;；\n"
SOFT_CUTS = "、，,"
LABEL_CUTS = "：:"
NEGATION = ("ない", "なかっ", "ません")             # in the tail of a clause: the clause is not an affirmative statement
VALUE_POS1 = ("名詞", "接尾辞", "記号", "未知語")   # the head of a value (the A of 「X は A」): a noun phrase or a number (F2, 4.2)
LIGHT_LEMMAS = ("為る", "成る", "居る", "有る", "来る", "出来る", "行く", "置く", "仕舞う", "見る", "呉れる", "遣る", "上げる", "貰う", "下さる", "頂く")   # 非自立可能 verbs that are verb endings, not predicates
DONE_SUFFIXES = ("済み", "済")                      # 資料送付済み: a サ変 noun + 済み is a finished event of that noun
COUNTER_POS3 = ("助数詞", "助数詞可能")             # a counter (本, 日, 台, 回) after a numeral
ADVERBIAL_POS3 = "副詞可能"                         # a noun that is a time word (昨日, 来週, 今朝)


# ------------------------------------------------------------------------------------------------------------------------------------------
# the records
# ------------------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Seat:
    """A phrase on a seat: the text of the stretch (from its first unit to its last), the units (the grammar layer's WORD units) and the span in `Exchange.text`."""
    text: str
    units: Tuple[str, ...]
    span: Tuple[int, int]

    def to_obj(self) -> dict:
        return {"text": self.text, "units": list(self.units), "span": list(self.span)}


@dataclass(frozen=True)
class Arm:
    """One arm of a centre: the particle, the seat, and the arms of that seat's own centre (the の chain 「X の Y の Z」: Z's arm の is Y, whose arm の is X)."""
    particle: str
    seat: Seat
    arms: Tuple["Arm", ...] = ()

    def to_obj(self) -> dict:
        return {"particle": self.particle, "seat": self.seat.to_obj(), "arms": [a.to_obj() for a in self.arms]}


@dataclass(frozen=True)
class Change:
    old: Optional[Seat]                         # None in shape.v2 for a change form that names no old value (「B に更新」)
    new: Seat
    form: str = ""                              # shape.v2: the id of the change form in CHANGE_FORMS_V2 ("" in shape.v1)

    def to_obj(self) -> dict:
        d = {"old": None if self.old is None else self.old.to_obj(), "new": self.new.to_obj()}
        if self.form:
            d["form"] = self.form
        return d


@dataclass(frozen=True)
class Clause:
    shape: str                                  # F0..F4
    span: Tuple[int, int]                       # character span of the clause in `Exchange.text` (first to last letter of the clause, punctuation at the cuts excluded)
    text: str
    centre: Optional[str] = None                # the centre as a PHRASE (開催地; for a verb its dictionary form: 開く); None for F0
    centre_units: Tuple[str, ...] = ()          # the WORD units of the centre phrase (開催, 地; a verb: ..., 開く)
    arms: Tuple[Arm, ...] = ()                  # in READ_ORDER
    value: Optional[Seat] = None                # the value seat (F1, F2, a change clause)
    reason: Optional[str] = None                # F0 only
    detail: Optional[str] = None                # F0: the gap / unit the reason is about
    change: Optional[Change] = None
    via_topic: bool = False                     # F3: the subject arm が is the は-topic
    tail: str = ""                              # the letters of the function units after the last unit (です, した, ...)
    surface: Optional[str] = None               # a verb predicate as written (開いた, 遅れている): the provenance of the lemma in `centre`
    adverbial: Tuple[Seat, ...] = ()            # the leading adverbials that were attached to this clause (昨日、 来週は、 では、)
    quantity: Optional[Seat] = None             # an event: the numeral + counter touching the predicate (52本 of 52本保管します); never part of the centre
    object_bare: Optional[Seat] = None          # an event: the other nouns touching the predicate without a particle (資料 of 資料送付済み); never part of the centre

    def to_obj(self) -> dict:
        return {"shape": self.shape, "span": list(self.span), "text": self.text, "centre": self.centre, "centre_units": list(self.centre_units),
                "arms": [a.to_obj() for a in self.arms], "value": None if self.value is None else self.value.to_obj(), "reason": self.reason, "detail": self.detail,
                "change": None if self.change is None else self.change.to_obj(), "via_topic": self.via_topic, "tail": self.tail, "surface": self.surface,
                "adverbial": [a.to_obj() for a in self.adverbial], "quantity": None if self.quantity is None else self.quantity.to_obj(),
                "object_bare": None if self.object_bare is None else self.object_bare.to_obj()}


@dataclass(frozen=True)
class Exchange:
    text: str                                   # the sentence as the exchanger read it: NFC, attribution stripped
    clauses: Tuple[Clause, ...]
    skipped: Tuple[Tuple[Tuple[int, int], str], ...]    # ((span, why)): a label ending in a colon
    version: str = SHAPES_VERSION               # the table that cut it: shape.v1 (default) or shape.v2

    def shapes(self) -> Tuple[str, ...]:
        return tuple(c.shape for c in self.clauses)

    def to_obj(self) -> dict:
        return {"v": self.version, "text": self.text, "clauses": [c.to_obj() for c in self.clauses], "skipped": [[list(s), w] for s, w in self.skipped]}


@dataclass(frozen=True)
class _Tok:
    s: str
    a: int
    b: int
    pos1: str
    pos2: str
    pos3: str
    lemma: str
    cform: str
    fn: bool                                    # a function unit: the loom's filter on the surface alone, or a particle / auxiliary / light-verb token (助詞 助動詞 非自立可能) as the sentence reads it


# ------------------------------------------------------------------------------------------------------------------------------------------
# the cut (rules, frozen)
# ------------------------------------------------------------------------------------------------------------------------------------------
def _tokens(text: str) -> List[_Tok]:
    """The WORD tokens of `text` with their spans -- the cut of `granularity._raw_spans` / `grammar.words_of` (a token without a letter is dropped) -- with the tagger's features and
    the function-unit flag of the loom's unit filter.  The features of ALL tokens are read before `is_function_unit` is asked (it runs the same tagger on a unit and would overwrite the
    sentence's lattice: a feature read after it can be 'BOS/EOS'; and which tokens it had cached would make the answer depend on the process history)."""
    raw: List[Tuple[str, int, int, str, str, str, str, str]] = []
    pos = 0
    for w in sp._get_tagger()(text):
        i = text.find(w.surface, pos)
        if i < 0:
            continue
        pos = i + len(w.surface)
        if sp._has_letter(w.surface):
            f = w.feature
            raw.append((w.surface, i, pos, str(f.pos1 or ""), str(f.pos2 or ""), str(f.pos3 or ""), str(f.lemma or ""), str(f.cForm or "")))
    out: List[_Tok] = []
    for surface, i, j, p1, p2, p3, lemma, cform in raw:
        fn = bool(is_function_unit(surface, sp.WORD)) or p1 in ("助詞", "助動詞") or (p2 == "非自立可能" and lemma in LIGHT_LEMMAS)      # the loom's rule on the surface, and the tokens of a verb ending as the sentence reads them
        out.append(_Tok(surface, i, j, p1, p2, p3, lemma, cform, fn))
    return out


def _pieces(text: str) -> List[Tuple[int, int, str]]:
    """(start, end, terminator) of the pieces between the cuts.  A comma / colon between two digits is no cut."""
    out: List[Tuple[int, int, str]] = []
    start = 0
    for i, ch in enumerate(text):
        if ch in HARD_CUTS or ch in SOFT_CUTS or ch in LABEL_CUTS:
            if ch in SOFT_CUTS + LABEL_CUTS and 0 < i < len(text) - 1 and text[i - 1].isdigit() and text[i + 1].isdigit():
                continue
            out.append((start, i, ch))
            start = i + 1
    out.append((start, len(text), ""))
    return out


def _predicate(head: _Tok, tail: Sequence[_Tok], has_case_arg: bool, done: bool = False) -> bool:
    """Can `head` (the last unit of the last phrase) be the centre of an event?  A verb the grammar layer keeps (any inflection: its centre is the lemma), a サ変 noun with する / し / さ /
    に・と + なる after it, or such a noun alone with a case argument before it (体言止め)."""
    if done or head.pos1 == "動詞":
        return True
    if head.pos1 == "名詞" and head.pos3 == "サ変可能":
        t0 = tail[0] if tail else None
        if t0 is not None and t0.lemma == "為る":                                  # 延期した, 開催する, 作成された
            return True
        if t0 is not None and t0.s in ("に", "と") and len(tail) > 1 and tail[1].lemma == "成る":      # 延期になった
            return True
        if t0 is None and has_case_arg:                                               # 体言止め: 「認証の期限を変更」
            return True
    return False


def _classify(text: str, toks: Sequence[_Tok], term: str) -> Clause:
    """One piece (its tokens, in order) -> one clause."""
    span = (toks[0].a, toks[-1].b)
    units = [t for t in toks if not t.fn]
    ctext = text[span[0]:span[1]]

    def f0(reason: str, detail: Optional[str] = None, tail: str = "") -> Clause:
        return Clause("F0", span, ctext, reason=reason, detail=detail, tail=tail)

    if not units:
        return f0("no_unit")
    tail_toks = [t for t in toks if t.a >= units[-1].b]
    tail = "".join(t.s for t in tail_toks)
    gaps = ["".join(t.s for t in toks if units[k].b <= t.a and t.b <= units[k + 1].a) for k in range(len(units) - 1)]
    for g in gaps:
        if g != "" and g != TOPIC and g != FROM and g not in ARM_PARTICLES:
            return f0("gap_is_not_a_particle", g, tail)
    if any(n in tail for n in NEGATION):
        return f0("negated", tail, tail)
    if (term != "" and term in "?？") or tail.endswith("か"):
        return f0("question", tail, tail)

    # phrases (touching units) and segments (phrases joined by の; a segment ends at a case gap)
    phrases: List[List[int]] = [[0]]                                       # indexes into `units`
    pgaps: List[str] = []
    for k, g in enumerate(gaps):
        if g == "":
            phrases[-1].append(k + 1)
        else:
            pgaps.append(g)
            phrases.append([k + 1])
    segs: List[List[List[int]]] = [[phrases[0]]]                           # a segment = a list of phrases
    cs: List[str] = []                                                     # the case gaps between segments
    for p, g in zip(phrases[1:], pgaps):
        if g == "の":
            segs[-1].append(p)
        else:
            cs.append(g)
            segs.append([p])
    r = len(cs)

    def seat(ph: Sequence[int]) -> Seat:
        a, b = units[ph[0]].a, units[ph[-1]].b
        return Seat(text[a:b], tuple(units[i].s for i in ph), (a, b))

    def seat_of_seg(seg: Sequence[Sequence[int]]) -> Seat:                 # the whole chain as one stretch (a value)
        a, b = units[seg[0][0]].a, units[seg[-1][-1]].b
        return Seat(text[a:b], tuple(units[i].s for ph in seg for i in ph), (a, b))

    def nest(seg: Sequence[Sequence[int]]) -> Tuple[Arm, ...]:             # 「X の Y の Z」 -> the arms of Z: の = Y (whose arm の = X)
        if len(seg) < 2:
            return ()
        return (Arm("の", seat(seg[-2]), nest(seg[:-1])),)

    def centre_of(seg: Sequence[Sequence[int]]) -> Tuple[str, Tuple[str, ...]]:      # the phrase as written, and its units
        s = seat(seg[-1])
        return s.text, s.units

    def predicate_of(seg: Sequence[Sequence[int]]) -> Tuple[str, Tuple[str, ...], Optional[str], Optional[Seat], Optional[Seat]]:
        """(centre, units, surface, quantity, object_bare) of the predicate phrase `seg[-1]`: the centre is the predicate ONLY (a verb: its lemma, the written form kept in `surface`; a サ変 noun: the noun;
        a サ変 noun + 済み: the noun).  The units that touch it before it are never part of the centre: numerals with their counters are the `quantity`, any other noun is the `object_bare`."""
        ph = seg[-1]
        k = ph.index(hidx)
        h = units[hidx]
        pre = ph[:k]
        num: List[bool] = []
        for j, i in enumerate(pre):
            u = units[i]
            num.append(u.pos2 == "数詞" or (j > 0 and num[j - 1] and (u.pos1 == "接尾辞" or u.pos3 in COUNTER_POS3)))

        def mk(ids: List[int]) -> Optional[Seat]:
            if not ids:
                return None
            a_, b_ = units[ids[0]].a, units[ids[-1]].b
            return Seat(text[a_:b_], tuple(units[i].s for i in ids), (a_, b_))
        q, bare = mk([i for i, n in zip(pre, num) if n]), mk([i for i, n in zip(pre, num) if not n])
        if h.pos1 == "動詞":
            lemma = h.lemma.split("-")[0] or h.s
            return lemma, (lemma,), text[h.a:h.b] + tail, q, bare
        return h.s, (h.s,), (text[h.a:units[ph[-1]].b] + tail) if done else None, q, bare

    def arm_of(c: str, seg: Sequence[Sequence[int]]) -> Arm:
        return Arm(c, seat(seg[-1]), nest(seg))

    def ordered(arms: Sequence[Arm]) -> Tuple[Arm, ...]:
        return tuple(sorted(arms, key=lambda a: READ_ORDER.index(a.particle)))

    # -- a change clause: [X は | Y を] A から B に 変更 ---------------------------------------------------------------------------------------
    last = segs[-1]
    if (r >= 2 and cs[-2] == FROM and cs[-1] == TO and len(last) == 1 and [units[i].s for i in last[0]] == [CHANGE_PREDICATE] and (r == 2 or (r == 3 and cs[0] in (TOPIC, "を")))):
        old, new = seat_of_seg(segs[-3]), seat_of_seg(segs[-2])
        ch = Change(old, new)
        if r == 2:                                                         # no slot: the change of whatever the open topic's nest holds
            return Clause("F4", span, ctext, CHANGE_PREDICATE, (CHANGE_PREDICATE,), (), new, change=ch, tail=tail)
        slot = segs[0]
        c, cu = centre_of(slot)
        return Clause("F1" if len(slot) > 1 else "F2", span, ctext, c, cu, nest(slot), new, change=ch, tail=tail)
    for c in cs:
        if c == FROM:
            return f0("gap_is_not_a_particle", FROM, tail)

    args = [c for c in cs if c in CASE_ARGS]
    for c in CASE_ARGS:
        if args.count(c) > 1:
            return f0("repeated_case_particle", c, tail)
    for i, c in enumerate(cs[:-1]):
        if c == "と" and cs[i + 1] in ("が", TOPIC, "を"):
            return f0("coordination", "と", tail)
    if cs.count(TOPIC) > 1:
        return f0("two_topics", TOPIC, tail)
    lastu = units[last[-1][-1]]
    hidx = last[-1][-1]                                                    # the predicate unit: the last unit, or the サ変 noun before a final 済み
    done = len(last[-1]) > 1 and lastu.pos1 == "接尾辞" and lastu.s in DONE_SUFFIXES and units[last[-1][-2]].pos1 == "名詞" and units[last[-1][-2]].pos3 == "サ変可能"
    if done:
        hidx = last[-1][-2]
    head = units[hidx]

    def event(subject: Optional[Sequence[Sequence[int]]], rest: Sequence[Tuple[str, Sequence[Sequence[int]]]], via_topic: bool) -> Clause:
        """The final segment is the predicate; `rest` = the (particle, segment) arguments before it."""
        has_case = any(c in CASE_ARGS for c, _ in rest)
        if not _predicate(head, tail_toks, has_case, done) or len(last) != 1:
            return f0("no_predicate", head.s, tail)
        arms = [arm_of(c, s) for c, s in rest]
        if subject is not None:
            arms.append(arm_of("が", subject))
        has_subject = any(a.particle == "が" for a in arms)
        c, cu, sf, qn, ob = predicate_of(last)
        return Clause("F3" if has_subject else "F4", span, ctext, c, cu, ordered(arms), via_topic=via_topic, tail=tail, surface=sf, quantity=qn, object_bare=ob)

    # -- a topic -----------------------------------------------------------------------------------------------------------------------------
    if TOPIC in cs:
        t = cs.index(TOPIC)
        if t != 0:
            return f0("case_before_topic", cs[0], tail)
        subject = segs[0]
        after = list(zip(cs[1:], segs[1:-1]))
        if after:
            return event(subject, after, True)
        if _predicate(head, tail_toks, False, done) and len(last) == 1:
            c, cu, sf, qn, ob = predicate_of(last)
            return Clause("F3", span, ctext, c, cu, (arm_of("が", subject),), via_topic=True, tail=tail, surface=sf, quantity=qn, object_bare=ob)
        if lastu.pos1 not in VALUE_POS1:
            return f0("value_not_noun", lastu.s, tail)
        c, cu = centre_of(subject)
        return Clause("F1" if len(subject) > 1 else "F2", span, ctext, c, cu, nest(subject), seat_of_seg(last), tail=tail)

    # -- no topic ------------------------------------------------------------------------------------------------------------------------------
    if r == 0:
        if _predicate(head, tail_toks, False, done) and len(last) == 1:
            return event(None, [], False)
        return f0("no_relation", None, tail)
    return event(None, list(zip(cs, segs[:-1])), False)


def _adverbial(pt: Sequence[_Tok], c: Clause, term: str) -> bool:
    """A piece ended by a soft cut that is no clause of its own and says only when / how: only function words (では、 しかし、 はい、), or only time words (昨日、 来週は、)."""
    if term == "" or term not in SOFT_CUTS or c.shape != "F0" or c.reason not in ("no_unit", "no_relation"):
        return False
    us = [t for t in pt if not t.fn]
    return all(t.pos3 == ADVERBIAL_POS3 for t in us) and not any(t.lemma in ("です", "だ", "である") for t in pt)


def _exchange(text: str) -> Exchange:
    toks = _tokens(text)
    clauses: List[Clause] = []
    skipped: List[Tuple[Tuple[int, int], str]] = []
    pending: List[Tuple[Seat, Clause]] = []                                 # leading adverbials waiting for the clause that follows

    def flush() -> None:                                                    # an adverbial with no clause after it stays what it was: a clause of F0
        clauses.extend(c for _, c in pending)
        pending.clear()

    for a, b, term in _pieces(text):
        pt = [t for t in toks if a <= t.a < b]
        if not pt:
            if term != "" and term in HARD_CUTS:                            # a sentence ended: an adverbial before it has no clause
                flush()
            continue
        if term != "" and term in LABEL_CUTS:
            flush()
            skipped.append(((pt[0].a, pt[-1].b), "label"))
            continue
        c = _classify(text, pt, term)
        if _adverbial(pt, c, term):
            sp_ = (pt[0].a, pt[-1].b)
            pending.append((Seat(text[sp_[0]:sp_[1]], tuple(t.s for t in pt if not t.fn), sp_), c))
            continue
        if pending:
            c = replace(c, adverbial=tuple(x for x, _ in pending))
            pending.clear()
        clauses.append(c)
    flush()
    return Exchange(text, tuple(clauses), tuple(skipped))


# ------------------------------------------------------------------------------------------------------------------------------------------
# the frozen table
# ------------------------------------------------------------------------------------------------------------------------------------------
RULES = (_tokens, _pieces, _predicate, _classify, _adverbial, _exchange)
CONSTANTS: Dict[str, Any] = {"version": SHAPES_VERSION, "shapes": SHAPE_NAMES, "f0": list(F0_REASONS), "arms": ARM_PARTICLES, "case": CASE_ARGS, "read_order": READ_ORDER, "topic": TOPIC,
                             "change": [FROM, TO, CHANGE_PREDICATE], "hard": HARD_CUTS, "soft": SOFT_CUTS, "label": LABEL_CUTS, "negation": list(NEGATION), "value_pos1": list(VALUE_POS1),
                             "light": list(LIGHT_LEMMAS), "adverbial": ADVERBIAL_POS3, "done": list(DONE_SUFFIXES), "counter": list(COUNTER_POS3)}


def _shapes_sha() -> str:
    h = hashlib.sha256()
    h.update(json.dumps(CONSTANTS, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for f in RULES:
        h.update(b"\x00")
        h.update(inspect.getsource(f).encode("utf-8"))
    return h.hexdigest()


SHAPES_SHA = _shapes_sha()


# ------------------------------------------------------------------------------------------------------------------------------------------
# shape.v2 (PUB-M4, L-PUB-24..): the SAME table plus more CHANGE FORMS.  shape.v1 above is not edited (its SHAPES_SHA and every test stay); a clause is first read by the v1 rules, and a clause
# that is one of the change forms below is then read as a change clause instead.  Every form is recorded in CHANGE_FORMS_V2 (hashed).
#   [X は | Y を] A から B {に | へ} {変更 | 更新 | 延期}     old A -> new B        (kara_{ni,he}_{henkou,koushin,enki}; kara_ni_henkou is the v1 form)
#   [X は | Y を] A から B へ                                 old A -> new B        (kara_he: no predicate; the slot is required)
#   [X は | Y を] B に {変更 | 更新 | 延期}                    new B, no old value    (ni_{henkou,koushin,enki})
# The slot X / Y gives the clause the shape of its slot (F1 when it has a の arm, else F2; value = B); with no slot the clause is F4 with the predicate as its centre (the form that needs a slot
# is then not a change clause).  Negated and questioned clauses are never change clauses.  Any tail (した, になりました, されました) is allowed after the predicate.
# ------------------------------------------------------------------------------------------------------------------------------------------
SHAPES_V2 = "shape.v2"
CHANGE_PREDICATES = ("変更", "更新", "延期")
FROM_TO_PARTICLES = ("に", "へ")
TO_ONLY_PARTICLE = "に"
BARE_TO = "へ"
SLOT_PARTICLES = ("は", "を")
_TO_ID = {"に": "ni", "へ": "he"}
_PRED_ID = {"変更": "henkou", "更新": "koushin", "延期": "enki"}
CHANGE_FORMS_V2 = tuple(["kara_%s_%s" % (_TO_ID[t], _PRED_ID[p]) for p in CHANGE_PREDICATES for t in FROM_TO_PARTICLES] + ["kara_he"]
                        + ["ni_%s" % _PRED_ID[p] for p in CHANGE_PREDICATES])
CONSTANTS_V2: Dict[str, Any] = dict(CONSTANTS, version=SHAPES_V2, change_forms=list(CHANGE_FORMS_V2), change_predicates=list(CHANGE_PREDICATES), from_to=list(FROM_TO_PARTICLES),
                                    to_only=TO_ONLY_PARTICLE, bare_to=BARE_TO, slot=list(SLOT_PARTICLES))


def _segments_v2(units: Sequence[_Tok], gaps: Sequence[str]) -> Tuple[List[List[List[int]]], List[str]]:
    """The segments of a clause (phrases joined by の) and the case gaps between them -- the same cut as `_classify`."""
    phrases: List[List[int]] = [[0]]
    pgaps: List[str] = []
    for k, g in enumerate(gaps):
        if g == "":
            phrases[-1].append(k + 1)
        else:
            pgaps.append(g)
            phrases.append([k + 1])
    segs: List[List[List[int]]] = [[phrases[0]]]
    cs: List[str] = []
    for p, g in zip(phrases[1:], pgaps):
        if g == "の":
            segs[-1].append(p)
        else:
            cs.append(g)
            segs.append([p])
    return segs, cs


def _change_v2(text: str, toks: Sequence[_Tok], term: str) -> Optional[Clause]:
    """The change forms of shape.v2 (see the block comment above): a Clause, or None when the piece is none of them."""
    units = [t for t in toks if not t.fn]
    if not units:
        return None
    tail = "".join(t.s for t in toks if t.a >= units[-1].b)
    gaps = ["".join(t.s for t in toks if units[k].b <= t.a and t.b <= units[k + 1].a) for k in range(len(units) - 1)]
    for g in gaps:
        if g != "" and g != "の" and g != TOPIC and g != "を" and g != FROM and g not in FROM_TO_PARTICLES:
            return None
    if any(n in tail for n in NEGATION) or (term != "" and term in "?？") or tail.endswith("か"):
        return None
    segs, cs = _segments_v2(units, gaps)
    r = len(cs)
    last = segs[-1]
    lastu = units[last[-1][-1]]
    pred = lastu.s if len(last) == 1 and len(last[0]) == 1 and lastu.s in CHANGE_PREDICATES else None
    slot: Optional[List[List[int]]] = None
    old_seg: Optional[List[List[int]]] = None
    form = ""
    if pred is not None and r >= 2 and cs[-2] == FROM and cs[-1] in FROM_TO_PARTICLES and (r == 2 or (r == 3 and cs[0] in SLOT_PARTICLES)):
        old_seg, new_seg = segs[-3], segs[-2]
        slot = segs[0] if r == 3 else None
        form = "kara_%s_%s" % (_TO_ID[cs[-1]], _PRED_ID[pred])
    elif pred is not None and r >= 1 and cs[-1] == TO_ONLY_PARTICLE and FROM not in cs and (r == 1 or (r == 2 and cs[0] in SLOT_PARTICLES)):
        new_seg = segs[-2]
        slot = segs[0] if r == 2 else None
        form = "ni_%s" % _PRED_ID[pred]
    elif pred is None and r == 2 and cs[0] in SLOT_PARTICLES and cs[1] == FROM and tail.startswith(BARE_TO):
        slot, old_seg, new_seg = segs[0], segs[1], segs[2]
        form = "kara_he"
    else:
        return None
    span = (toks[0].a, toks[-1].b)
    ctext = text[span[0]:span[1]]

    def seat(ph: Sequence[int]) -> Seat:
        a, b = units[ph[0]].a, units[ph[-1]].b
        return Seat(text[a:b], tuple(units[i].s for i in ph), (a, b))

    def seat_of_seg(seg: Sequence[Sequence[int]]) -> Seat:
        a, b = units[seg[0][0]].a, units[seg[-1][-1]].b
        return Seat(text[a:b], tuple(units[i].s for ph in seg for i in ph), (a, b))

    def nest(seg: Sequence[Sequence[int]]) -> Tuple[Arm, ...]:
        if len(seg) < 2:
            return ()
        return (Arm("の", seat(seg[-2]), nest(seg[:-1])),)

    new = seat_of_seg(new_seg)
    ch = Change(None if old_seg is None else seat_of_seg(old_seg), new, form)
    if slot is None:
        return Clause("F4", span, ctext, pred, (pred,), (), new, change=ch, tail=tail)
    s = seat(slot[-1])
    return Clause("F1" if len(slot) > 1 else "F2", span, ctext, s.text, s.units, nest(slot), new, change=ch, tail=tail)


def _classify_v2(text: str, toks: Sequence[_Tok], term: str) -> Clause:
    """shape.v2: the v1 reading of the piece, unless the piece is one of the change forms."""
    c = _classify(text, toks, term)
    ch = _change_v2(text, toks, term)
    return c if ch is None else ch


def _exchange_v2(text: str) -> Exchange:
    toks = _tokens(text)
    clauses: List[Clause] = []
    skipped: List[Tuple[Tuple[int, int], str]] = []
    pending: List[Tuple[Seat, Clause]] = []

    def flush() -> None:
        clauses.extend(c for _, c in pending)
        pending.clear()

    for a, b, term in _pieces(text):
        pt = [t for t in toks if a <= t.a < b]
        if not pt:
            if term != "" and term in HARD_CUTS:
                flush()
            continue
        if term != "" and term in LABEL_CUTS:
            flush()
            skipped.append(((pt[0].a, pt[-1].b), "label"))
            continue
        c = _classify_v2(text, pt, term)
        if _adverbial(pt, c, term):
            sp_ = (pt[0].a, pt[-1].b)
            pending.append((Seat(text[sp_[0]:sp_[1]], tuple(t.s for t in pt if not t.fn), sp_), c))
            continue
        if pending:
            c = replace(c, adverbial=tuple(x for x, _ in pending))
            pending.clear()
        clauses.append(c)
    flush()
    return Exchange(text, tuple(clauses), tuple(skipped), SHAPES_V2)


RULES_V2 = RULES + (_segments_v2, _change_v2, _classify_v2, _exchange_v2)


def _shapes_sha_v2() -> str:
    h = hashlib.sha256()
    h.update(json.dumps(CONSTANTS_V2, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for f in RULES_V2:
        h.update(b"\x00")
        h.update(inspect.getsource(f).encode("utf-8"))
    return h.hexdigest()


SHAPES_SHA_V2 = _shapes_sha_v2()


# ------------------------------------------------------------------------------------------------------------------------------------------
# shape.v3 (PUB-M6c, stage 1 of the owner's staged shape table, L-PUB-64..): the SAME table as shape.v2 plus the constructions that were F0 only because of how the tokenizer / the unit filter cut the
# sentence ("artefacts": no meaning is dropped or guessed).  shape.v1 / shape.v2 above are not edited (their SHAPES_SHA and every test stay).  THE RULE OF THE VERSION: a clause that shape.v2 reads as
# F1-F4 is read EXACTLY the same by shape.v3; only a piece that shape.v2 gives F0 is read again, with its tokens rewritten as below, and if the new reading is still F0 the v2 clause (with its v2 reason)
# stays.  Everything that makes a clause F0 for what it MEANS is untouched (a gap that is not a particle: も だけ まで へ ごとに ない-relative clauses; negation; questions; 「と」-lists; two topics ...).
#   R2 AFFIXES (SUFFIX_SA, COUNTER_TSU, PREFIX)  a function-unit suffix 「さ」 / 「つ」 touching the unit before it (読みにくさ, ひとつ) and a prefix touching the unit after it (閉室日, 試音, 大閲覧室) extend the
#                                                SPAN of that unit, so the phrase is written whole (読みにくさ, 閉室日); the units stay the loom's own (にく, 室): the affix is not a unit and is not in `units`.
#   R1 LIGHT-VERB PREDICATE (LIGHT_PRED, NOUN_HEAD, NI_LIGHT, EXIST_ARU)  a verb the unit filter takes for a verb ending (見 置き しまっ つけ 通し あり ...) that stands right after a case particle
#                                                (を に が で と, or は) which follows a unit -- or touches a noun unit (仮置き) -- is the PREDICATE, not an ending: 「次の束を見た」 「脇に置き」 「輸送表にある」 「目に通して」.  Its centre
#                                                is the dictionary form (見る 置く 有る).  Not for する (サ変 is read by shape.v1) and できる; after a verb ending or a て (見てみる, 置いておく) the token stays an ending.
#   FRAGMENTS (FRAG_TOPIC, FRAG_ADV)             a piece that is only a topic (「寄贈資料の受け入れ方は、」) joins the piece after it, so the topic is the topic of that clause; a piece with no particle,
#                                                no predicate and nothing after its last unit, ended by a soft cut (「念のため、」 「清掃、」), is an adverbial of the clause that follows (as the leading adverbials of v1).
# NOT in this version (owner: each stage is measured before the next): 「へ」 read as 「に」 (stage 2), 「X は A だと…」 (stage 3), 「ことにした」, も, だけ, 連体修飾 verbs.
# ------------------------------------------------------------------------------------------------------------------------------------------
SHAPES_V3 = "shape.v3"
AFFIX_SUFFIXES = ("さ", "つ")                       # R2: the function-unit suffixes that extend the phrase of the unit before them
LIGHT_CASE = "がをにでと"                           # R1: the case particles after which a verb-ending token is the predicate (は too)
LIGHT_EXCLUDED = ("為る", "出来る")                 # R1: する is read by the サ変 rule of shape.v1; できる is a potential ending
FORMAL_NOUN = "事"                                 # R1: not after 「こと」 (ことになった / ことがある are modalities of the clause before them, not events of their own)
FRAG_SOFT = SOFT_CUTS
CONSTANTS_V3: Dict[str, Any] = dict(CONSTANTS_V2, version=SHAPES_V3, affix_suffixes=list(AFFIX_SUFFIXES), light_case=LIGHT_CASE, light_excluded=list(LIGHT_EXCLUDED), formal_noun=FORMAL_NOUN,
                                    rules=["R2_affix", "R1_light_predicate", "frag_topic", "frag_adverbial"])


def _rewrite_v3(toks: Sequence[_Tok]) -> List[_Tok]:
    """The tokens of a piece with the artefacts of shape.v3 repaired (see the block comment above): affixes extend the span of the unit they touch, light verbs after a case particle become units."""
    suf: List[_Tok] = []
    for t in toks:                                                          # R2: a suffix 「さ」 / 「つ」 extends the unit before it
        if t.fn and t.pos1 == "接尾辞" and t.s in AFFIX_SUFFIXES and suf and not suf[-1].fn and suf[-1].b == t.a:
            suf[-1] = replace(suf[-1], b=t.b)
            continue
        suf.append(t)
    pre: List[_Tok] = []
    i = 0
    while i < len(suf):                                                     # R2: a prefix extends the unit after it
        t = suf[i]
        if t.fn and t.pos1 == "接頭辞" and i + 1 < len(suf) and not suf[i + 1].fn and suf[i + 1].a == t.b:
            pre.append(replace(suf[i + 1], a=t.a))
            i += 2
            continue
        pre.append(t)
        i += 1
    out = list(pre)
    for k, t in enumerate(pre):                                             # R1: a verb ending right after a case particle (which follows a unit) or touching a noun unit is the predicate
        if k == 0 or not (t.fn and t.pos1 == "動詞") or t.lemma in LIGHT_EXCLUDED:
            continue
        p = pre[k - 1]
        after_case = p.pos1 == "助詞" and ((p.pos2 == "格助詞" and p.s in LIGHT_CASE) or (p.pos2 == "係助詞" and p.s == TOPIC)) and k >= 2 and not pre[k - 2].fn and pre[k - 2].lemma != FORMAL_NOUN
        after_noun = (not p.fn) and p.pos1 == "名詞" and p.b == t.a
        if after_case or after_noun:
            out[k] = replace(t, fn=False)
    return out


def _classify_v3(text: str, toks: Sequence[_Tok], term: str) -> Clause:
    """shape.v3: the v2 reading of the piece; only if that is F0, the piece is read again with `_rewrite_v3`'s tokens, and the new reading is kept iff it is not F0."""
    c = _classify_v2(text, toks, term)
    if c.shape != "F0":
        return c
    toks2 = _rewrite_v3(toks)
    if toks2 == list(toks):
        return c
    c2 = _classify_v2(text, toks2, term)
    if c2.shape == "F0" or sum(1 for x in c2.arms if x.particle == "が") > 1:                  # a new reading never has two subjects
        return c
    if c2.shape in ("F1", "F2") and c2.change is None:                                         # a value clause ends in a noun (+ です / だ ...): a verb after it (維持できている) makes it no value
        units = [t for t in toks2 if not t.fn]
        if any(t.pos1 == "動詞" for t in toks2 if t.a >= units[-1].b):
            return c
    return c2


def _frag_topic(c: Clause, term: str) -> bool:
    """A piece that is only a topic (「X は」 and nothing after) ended by a soft cut."""
    return c.shape == "F0" and c.reason == "no_relation" and c.tail == TOPIC and term != "" and term in FRAG_SOFT


def _adverbial_v3(pt: Sequence[_Tok], c: Clause, term: str) -> bool:
    """shape.v2's leading adverbials, and a soft-cut piece of units only (nothing after the last unit, no particle, no predicate): 「念のため、」 「清掃、」."""
    if _adverbial(pt, c, term):
        return True
    return c.shape == "F0" and c.reason == "no_relation" and c.tail == "" and term != "" and term in FRAG_SOFT


def _exchange_v3(text: str) -> Exchange:
    toks = _tokens(text)
    clauses: List[Clause] = []
    skipped: List[Tuple[Tuple[int, int], str]] = []
    pending: List[Tuple[Seat, Clause]] = []
    pieces = [(a, b, term, [t for t in toks if a <= t.a < b]) for a, b, term in _pieces(text)]

    def flush() -> None:
        clauses.extend(c for _, c in pending)
        pending.clear()

    k = 0
    while k < len(pieces):
        a, b, term, pt = pieces[k]
        k += 1
        if not pt:
            if term != "" and term in HARD_CUTS:
                flush()
            continue
        if term != "" and term in LABEL_CUTS:
            flush()
            skipped.append(((pt[0].a, pt[-1].b), "label"))
            continue
        c = _classify_v3(text, pt, term)
        if _frag_topic(c, term) and k < len(pieces) and pieces[k][3] and not (pieces[k][2] != "" and pieces[k][2] in LABEL_CUTS):
            merged = pt + pieces[k][3]                                       # the topic joins the piece after it
            c2 = _classify_v3(text, merged, pieces[k][2])
            if c2.shape != "F0" and sum(1 for x in c2.arms if x.particle == "が") <= 1:         # not when the next piece has a subject of its own (two が arms)
                c, pt, term = c2, merged, pieces[k][2]
                k += 1
        if _adverbial_v3(pt, c, term):
            sp_ = (pt[0].a, pt[-1].b)
            pending.append((Seat(text[sp_[0]:sp_[1]], tuple(t.s for t in pt if not t.fn), sp_), c))
            continue
        if pending:
            c = replace(c, adverbial=tuple(x for x, _ in pending))
            pending.clear()
        clauses.append(c)
    flush()
    return Exchange(text, tuple(clauses), tuple(skipped), SHAPES_V3)


RULES_V3 = RULES_V2 + (_rewrite_v3, _classify_v3, _frag_topic, _adverbial_v3, _exchange_v3)


def _shapes_sha_v3() -> str:
    h = hashlib.sha256()
    h.update(json.dumps(CONSTANTS_V3, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for f in RULES_V3:
        h.update(b"\x00")
        h.update(inspect.getsource(f).encode("utf-8"))
    return h.hexdigest()


SHAPES_SHA_V3 = _shapes_sha_v3()
SHAPE_TABLES: Dict[str, str] = {SHAPES_VERSION: SHAPES_SHA, SHAPES_V2: SHAPES_SHA_V2}      # version -> sha: what a ledger header records (shape.v1, shape.v2: pinned by the tests of PUB-M4)
SHAPE_TABLES_ALL: Dict[str, str] = dict(SHAPE_TABLES, **{SHAPES_V3: SHAPES_SHA_V3})      # version -> sha of every table (SHAPE_TABLES: v1 and v2, as the tests of PUB-M4 pin it)
SHAPE_VERSIONS: Tuple[str, ...] = (SHAPES_VERSION, SHAPES_V2, SHAPES_V3)


def exchange(sentence: str, version: str = SHAPES_VERSION) -> Exchange:
    """The shape exchanger: a sentence -> its clauses, each with a shape (F1..F4, or F0 with a reason).  Pure.  `version`: shape.v1 (default: the table of PUB-M1, unchanged), shape.v2 (PUB-M4: the
    change forms of CHANGE_FORMS_V2 are clauses of their own) or shape.v3 (PUB-M6c: v2 plus the artefacts of stage 1, see above)."""
    text = strip_attribution(unicodedata.normalize("NFC", sentence or ""))
    if version == SHAPES_VERSION:
        return _exchange(text)
    if version == SHAPES_V2:
        return _exchange_v2(text)
    if version == SHAPES_V3:
        return _exchange_v3(text)
    raise ValueError("unknown shape version %r (one of %s)" % (version, SHAPE_VERSIONS))


def shapes_of(sentence: str, version: str = SHAPES_VERSION) -> Tuple[str, ...]:
    return exchange(sentence, version).shapes()
