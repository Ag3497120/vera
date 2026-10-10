"""G2-f: the grammar layer Gamma -- particle records, kinds, the question's slot and granularity pattern, the grammar
cross with its 24 rotations as moves, and the read order (docs/LINE3_G2_AXES_AND_GRAMMAR_LAYER.md 4, docs/LINE3_G3_SLIDING_PACKS.md 4).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md, quoted):
  G1 後: 「助詞などを文法層という別の層を作ってそこから読むのと読む際に十字の種類で読む順番などを調整する」
  G2 5-8: 「文法層も粒度を変えたものと因果関係を持たせて全体をパックするソブリンの中で回るようにします」
          「粒度のパターンからの未知への対応を含めたもの」
          「軸では腕のラベルとして、文法層では十字ごとの参照として」
  G3 5-6: 「文法層の十字の回転を「手」にして、助詞の腕をデータの腕に合わせる」
          「梯子の順に x、y、z へ。重みは辺の流れと配置の結合と読む順に」

What is here (all judgement points are numbered L-540.. in docs/LINE3_LOCAL_DECISIONS.md, section "G2-f"):
  records    for every content unit occurrence of the RUN and WORD tiers, the foundation particle (P7, a hand-written
             list, not UniDic tags) that immediately follows it, with provenance (tier, sid, start, end, particle
             span); exact counts per (tier, unit, particle) and per (tier, unit).        -> build_records
  kind       the particle that most often follows a unit (over P7, G2 4.1: the kind of a layer-0 cross); a window's
             kind is over the six arm particles only (G3 4.2); a tie is a labelled group, never broken by order.
                                                                                    -> kind_of_counts
  question   the particle after the interrogative phrase (slot), the predicate Y of 「XのYは何ですか」 (a separate,
             labelled field), the frames, and the granularity pattern with stand-ins.   -> read_question
  cross      a 6-arm geometry.Cross per window placeholder: the foundation particles in ladder order on
             +x -x +y -y +z -z, Fibonacci weights as exact Fractions, the 24 rotations as moves, an exact alignment
             score (no search beyond the 24 rotations).                                    -> grammar_cross, align
  read order the deterministic order of candidate crosses / windows given a question and their kinds. -> read_order
  bytes      canonical `to_bytes()` for every object; no float, no division, no set / dict order dependence.

Nothing here touches the space, the energy, placement, ask or cycle (Gamma is not evidence: I-G2-2); a later ticket hooks
the read order in.  The functions are pure functions of their arguments.
"""
from __future__ import annotations

import bisect
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from verantyx.lang import strip_attribution
from verantyx.line3 import geometry as geo
from verantyx.line3 import space as sp
from verantyx.line3.funcwords import is_function_unit
from verantyx.line3.granularity import SpanIndex, _raw_spans

FORMAT = "line3.grammar.v1"

# ---------------------------------------------------------------------------------------------------------------
# the foundation (G1 P7), hand-written (G1 2.4: the particles are not tagged, "人の手の一覧")
# ---------------------------------------------------------------------------------------------------------------
P7: Tuple[str, ...] = ("は", "の", "に", "を", "が", "で", "と")          # G1 3.1.1 order; a label order only
LADDER: Tuple[str, ...] = ("は", "の", "に", "で", "と", "を", "が")      # OP-G1-3 (a) rank 1..7 (fulllead WORD share order)
CENTRE_PARTICLE = LADDER[0]                                              # 233/377
ARM_PARTICLES: Tuple[str, ...] = LADDER[1:]                              # +x -x +y -y +z -z (OP-G3-6 (a))
RECORD_TIERS: Tuple[str, ...] = (sp.RUN, sp.WORD)                        # L-541: CHAR has no records


def _fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


FIB_DEN = _fib(14)                                                       # 377
WEIGHTS: Mapping[str, Fraction] = {p: Fraction(_fib(14 - k), FIB_DEN) for k, p in enumerate(LADDER, 1)}
assert FIB_DEN == 377 and WEIGHTS["は"] == Fraction(233, 377) and WEIGHTS["が"] == Fraction(1, 377) * 13

# hand-written interrogatives (copied from experiments/line3/g2/probe_particles.py INTERROG), L-545
INTERROG = frozenset({"何", "なに", "なん", "どこ", "誰", "だれ", "いつ", "どの", "どれ", "いくつ", "どう", "どんな",
                      "いくら", "なぜ", "何故", "どちら"})


def foundation_obj() -> dict:
    """The foundation F as data (G1 L-G1-6, G3 L-G3 `F_ref`): centre, arms in ladder order, exact weights."""
    return {"format": FORMAT, "centre": [CENTRE_PARTICLE, str(WEIGHTS[CENTRE_PARTICLE])],
            "arms": [[geo.AXES[i], p, str(WEIGHTS[p])] for i, p in enumerate(ARM_PARTICLES)]}


def _canon(obj) -> bytes:
    return json.dumps(_plain(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _plain(x):
    """Canonical-JSON-ready: Fractions as 'n/d', tuples as lists; a float is a bug (L-02)."""
    if isinstance(x, float):
        raise TypeError("float in a grammar object")
    if isinstance(x, Fraction):
        return "%d/%d" % (x.numerator, x.denominator)
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    return x


def foundation_sha() -> str:
    return hashlib.sha256(_canon(foundation_obj())).hexdigest()


# ---------------------------------------------------------------------------------------------------------------
# the particle after a span (L-542): adjacency is read on the WORD cut, punctuation skipped
# ---------------------------------------------------------------------------------------------------------------
Word = Tuple[str, int, int]


def words_of(text: str) -> List[Word]:
    """The WORD units of the (attribution-stripped) sentence with spans, function words kept, punctuation dropped
    (L-32): `granularity._raw_spans` -- the same cut as the space's WORD tier before its filter."""
    return _raw_spans(sp.WORD, text)


STEMS: Tuple[str, ...] = ("straddle", "whole_word")                       # G3-k (L-801): what a unit that ends inside a WORD takes


def follower(words: Sequence[Word], end: int, stem: str = "straddle") -> Tuple[str, Optional[str], Optional[Tuple[int, int]]]:
    """What follows a span ending at `end`: the first WORD unit that starts at or after `end` (only characters no tier
    keeps lie in between, L-32).  `stem` (G3-k, L-801; owner after G2-f: 「語全体（WORD）の後ろの助詞を取る」): "straddle" (default,
    L-542) labels a span that ends inside a WORD `straddle`; "whole_word" reads what follows that WORD instead (never `straddle`).
    Returns (label, surface, span):
      ("particle", p, span)   p in P7
      ("other", surface, span) any other WORD unit (content or another function word)
      ("end", None, None)      nothing follows (sentence end, punctuation skipped)
      ("straddle", surface, span) a WORD unit covers `end`: the span ends inside a word, nothing is decided (L-542)"""
    starts = [a for _, a, _ in words]
    i = bisect.bisect_left(starts, end)
    if i > 0 and words[i - 1][2] > end:
        s, a, b = words[i - 1]
        if stem == "whole_word":
            return follower(words, b, stem)
        return ("straddle", s, (a, b))
    if i >= len(words):
        return ("end", None, None)
    s, a, b = words[i]
    return (("particle" if s in P7 else "other"), s, (a, b))


def particle_after(text: str, end: int) -> Optional[str]:
    """The P7 particle right after offset `end` of the (stripped) sentence `text`, else None."""
    lab, s, _ = follower(words_of(text), end)
    return s if lab == "particle" else None


def answer_particle(sentence: str, answer_alternatives: Iterable[str]) -> Tuple[Optional[Tuple[int, int]], Optional[str], str]:
    """Where the first alternative of an answer that occurs in the (stripped) sentence ends and what follows:
    (span, P7 particle or None, label) with label in {particle, other, end, straddle, notfound} (L-546, as the G2 probe)."""
    for alt in answer_alternatives:
        i = sentence.find(alt)
        if i >= 0:
            lab, s, _ = follower(words_of(sentence), i + len(alt))
            return (i, i + len(alt)), (s if lab == "particle" else None), lab
    return None, None, "notfound"


# ---------------------------------------------------------------------------------------------------------------
# (1) particle records
# ---------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True, order=True)
class Attachment:
    """One occurrence: the content unit `unit` (tier `tier`) at [start, end) of the stripped sentence `sid` is
    immediately followed by the foundation particle `particle` at [p_start, p_end)."""
    tier: str
    sid: int
    start: int
    end: int
    unit: str
    particle: str
    p_start: int
    p_end: int

    def as_list(self) -> list:
        return [self.tier, self.sid, self.start, self.end, self.unit, self.particle, self.p_start, self.p_end]


FOLLOW_LABELS = P7 + ("other", "end", "straddle")


class Records:
    """All attachments of a corpus (sorted), the number of content head occurrences per (tier, unit), and the count of
    every follower label per tier (nothing is dropped silently, L-542).  Immutable by convention."""

    def __init__(self, attachments: Sequence[Attachment], heads: Mapping[Tuple[str, str], int],
                 follow: Mapping[str, Mapping[str, int]], n_sentences: int, sids: Sequence[int], stem: str = "straddle",
                 stemmed: Optional[Mapping[str, int]] = None) -> None:
        if stem not in STEMS:
            raise ValueError("stem: %s" % " | ".join(STEMS))
        self.stem = stem                                                # G3-k (L-801)
        # G3-k (L-814): per tier the heads that ended inside a WORD and took what follows the whole WORD (stem "whole_word" only).  Kept OUT of `follow`: they are
        # counted inside particle / other / end there, so a sum over `follow` must not see them twice.
        self.stemmed: Dict[str, int] = {t: int(v) for t, v in sorted((stemmed or {}).items())}
        self.attachments: Tuple[Attachment, ...] = tuple(sorted(attachments))
        self.heads: Dict[Tuple[str, str], int] = dict(heads)
        self.follow: Dict[str, Dict[str, int]] = {t: dict(v) for t, v in follow.items()}
        self.n_sentences = n_sentences
        self.sids: Tuple[int, ...] = tuple(sids)
        by_unit: Dict[Tuple[str, str], List[Attachment]] = {}
        for a in self.attachments:
            by_unit.setdefault((a.tier, a.unit), []).append(a)
        self._by_unit = by_unit

    # -- counts -------------------------------------------------------------------------------------------------
    def tiers(self) -> Tuple[str, ...]:
        return tuple(t for t in RECORD_TIERS if t in self.follow)

    def units(self, tier: str) -> List[str]:
        """Every content unit with at least one head occurrence, in code-point order (canonical, never a winner)."""
        return sorted(u for (t, u) in self.heads if t == tier)

    def n_head(self, tier: str, unit: str) -> int:
        """Occurrences of the unit as a content head (every occurrence, followed by a particle or not)."""
        return self.heads.get((tier, unit), 0)

    def of(self, tier: str, unit: str) -> Tuple[Attachment, ...]:
        return tuple(self._by_unit.get((tier, unit), ()))

    def n_attached(self, tier: str, unit: str) -> int:
        return len(self._by_unit.get((tier, unit), ()))

    def counts(self, tier: str, unit: str, sids: Optional[Iterable[int]] = None) -> Dict[str, int]:
        """{particle: number of attachments of (tier, unit)} for the particles that occur (P7 order)."""
        keep = None if sids is None else frozenset(sids)
        c: Dict[str, int] = {}
        for a in self._by_unit.get((tier, unit), ()):
            if keep is None or a.sid in keep:
                c[a.particle] = c.get(a.particle, 0) + 1
        return {p: c[p] for p in P7 if p in c}

    def count(self, tier: str, unit: str, particle: str) -> int:
        return self.counts(tier, unit).get(particle, 0)

    def particle_totals(self, tier: str) -> Dict[str, int]:
        c = {p: 0 for p in P7}
        for a in self.attachments:
            if a.tier == tier:
                c[a.particle] += 1
        return c

    def n_attachments(self, tier: str) -> int:
        return sum(1 for a in self.attachments if a.tier == tier)

    # -- kind ---------------------------------------------------------------------------------------------------
    def kind(self, tier: str, unit: str) -> "Kind":
        return kind_of_counts(self.counts(tier, unit))

    def kind_distribution(self, tier: str) -> Dict[str, int]:
        """Over the distinct content head units of the tier: {particle kinds by particle..., 'tied', 'none'}."""
        out: Dict[str, int] = {}
        for u in self.units(tier):
            k = self.kind(tier, u)
            key = k.particles[0] if k.label == "particle" else k.label
            out[key] = out.get(key, 0) + 1
        return out

    def kind_totals(self, tier: str) -> Dict[str, int]:
        """The same, summed to the three labels: {'particle': .., 'tied': .., 'none': ..}."""
        d = {"particle": 0, "tied": 0, "none": 0}
        for u in self.units(tier):
            d[self.kind(tier, u).label] += 1
        return d

    # -- bytes --------------------------------------------------------------------------------------------------
    def to_obj(self) -> dict:
        o = {"format": FORMAT, "foundation": foundation_sha(), "p7": list(P7), "tiers": list(self.tiers()),
             "n_sentences": self.n_sentences, "sids": list(self.sids),
             "heads": [[t, u, n] for (t, u), n in sorted(self.heads.items())],
             "follow": {t: {k: v[k] for k in sorted(v)} for t, v in sorted(self.follow.items())},
             "attachments": [a.as_list() for a in self.attachments]}
        if self.stem != "straddle":                                     # G3-k: named only when not the default, so the default bytes are unchanged
            o["stem"] = self.stem
            o["stem_whole_word"] = {t: self.stemmed[t] for t in sorted(self.stemmed)}      # L-814: outside `follow`; already counted inside particle / other / end there
        return o

    def to_bytes(self) -> bytes:
        return _canon(self.to_obj())

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()


def build_records(texts: Sequence[str], stem: str = "straddle") -> Records:
    """Records of a list of sentences; sid = position in the list (L-33)."""
    return _build(list(enumerate(texts)), len(texts), stem=stem)


def records_of_space(space: sp.Space, stem: str = "straddle") -> Records:
    """Records of the BASE sentences of a space (memory sentences are not corpus text, L-547); sids are the space's."""
    items = [(sid, t) for sid, (t, _) in enumerate(space.sentences) if space.kinds[sid] == sp.BASE]
    return _build(items, space.N, stem=stem)


def _build(items: Sequence[Tuple[int, str]], n_sentences: int, tiers: Sequence[str] = RECORD_TIERS, stem: str = "straddle") -> Records:
    if stem not in STEMS:
        raise ValueError("stem: %s" % " | ".join(STEMS))
    heads: Dict[Tuple[str, str], int] = {}
    follow: Dict[str, Dict[str, int]] = {t: {k: 0 for k in FOLLOW_LABELS} for t in tiers}
    stemmed: Dict[str, int] = {t: 0 for t in tiers}
    atts: List[Attachment] = []
    for sid, raw in items:
        text = strip_attribution(raw)                                   # L-44
        words = words_of(text)
        for tier in tiers:
            for u, a, b in (words if tier == sp.WORD else _raw_spans(tier, text)):
                if is_function_unit(u, tier):
                    continue                                            # L-540: heads are content units
                heads[(tier, u)] = heads.get((tier, u), 0) + 1
                lab, s, span = follower(words, b, stem)
                if stem == "whole_word" and follower(words, b)[0] == "straddle":
                    stemmed[tier] += 1                                  # G3-k: a head that ended inside a WORD and took what follows the whole WORD
                if lab == "particle":
                    follow[tier][s] += 1
                    atts.append(Attachment(tier, sid, a, b, u, s, span[0], span[1]))
                else:
                    follow[tier][lab] += 1
    return Records(atts, heads, follow, n_sentences, [sid for sid, _ in items], stem, stemmed if stem == "whole_word" else None)


def trace_check(records: Records, sentence_text) -> List[str]:
    """I-G2-1: every attachment re-read against its sentence.  `sentence_text(sid)` = the sentence text (the stored one;
    the attribution is stripped here).  [] = all consistent: the surface at [start, end) is the unit, the surface at
    [p_start, p_end) is the particle (in P7), no letter-like character lies between them, the unit is a content unit,
    and the counts per (tier, unit, particle) add up to the attachments."""
    bad: List[str] = []
    for a in records.attachments:
        t = strip_attribution(sentence_text(a.sid))
        if t[a.start:a.end] != a.unit:
            bad.append("unit surface %r != %r (sid %d)" % (t[a.start:a.end], a.unit, a.sid))
        if t[a.p_start:a.p_end] != a.particle or a.particle not in P7:
            bad.append("particle surface %r != %r (sid %d)" % (t[a.p_start:a.p_end], a.particle, a.sid))
        if records.stem == "whole_word":                                # G3-k: only the rest of the WORD the unit ends in may lie between
            lab, s_, sp_ = follower(words_of(t), a.end, "whole_word")
            if lab != "particle" or s_ != a.particle or sp_ != (a.p_start, a.p_end):
                bad.append("the particle is not the one after the whole word (sid %d, %r)" % (a.sid, a.unit))
        elif a.p_start < a.end or sp._has_letter(t[a.end:a.p_start]):
            bad.append("a letter lies between unit and particle (sid %d, %r)" % (a.sid, a.unit))
        if is_function_unit(a.unit, a.tier):
            bad.append("head is a function unit: %r" % a.unit)
    tot = sum(sum(records.counts(t, u).values()) for (t, u) in records._by_unit)
    if tot != len(records.attachments):
        bad.append("counts do not add up to the attachments")
    return bad


# ---------------------------------------------------------------------------------------------------------------
# (2) kind
# ---------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Kind:
    """label 'particle' (one most frequent follower), 'tied' (>= 2 followers share the maximum: the group, kept whole),
    or 'none' (no foundation particle ever follows).  `particles` is in P7 order -- a label order, not a winner (L-543)."""
    label: str
    particles: Tuple[str, ...]
    count: int

    def to_obj(self) -> list:
        return [self.label, list(self.particles), self.count]


NONE_KIND = Kind("none", (), 0)


def kind_of_counts(counts: Mapping[str, int]) -> Kind:
    pos = {p: c for p, c in counts.items() if c > 0 and p in P7}
    if not pos:
        return NONE_KIND
    m = max(pos.values())
    top = tuple(p for p in P7 if pos.get(p) == m)
    return Kind("particle" if len(top) == 1 else "tied", top, m)


# ---------------------------------------------------------------------------------------------------------------
# (3) the question side
# ---------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Frame:
    """A content WORD unit of the question and the particle right after it (None = no P7 particle; `after` says what)."""
    unit: str
    span: Tuple[int, int]
    particle: Optional[str]
    after: str

    def to_obj(self) -> list:
        return [self.unit, list(self.span), self.particle, self.after]


@dataclass(frozen=True)
class Slot:
    """The interrogative phrase (the interrogative WORD plus the content WORD units glued to it, e.g. 何+年) and what
    follows it.  `particle` is the P7 particle (the slot of OP-G2-7 (a)) or None; `after` = 'particle' | 'other:<w>' |
    'end'."""
    phrase: str
    span: Tuple[int, int]
    particle: Optional[str]
    after: str

    def to_obj(self) -> list:
        return [self.phrase, list(self.span), self.particle, self.after]


@dataclass(frozen=True)
class Predicate:
    """「XのYは何ですか」: Y = the content run right before は, X = the content run before の before Y (OP-G2-7 (c); a
    separate field, never merged into `slot`, L-548)."""
    y: str
    y_span: Tuple[int, int]
    x: Optional[str]
    x_span: Optional[Tuple[int, int]]

    def to_obj(self) -> list:
        return [self.y, list(self.y_span), self.x, None if self.x_span is None else list(self.x_span)]


@dataclass(frozen=True)
class Standin:
    """G1 3.2 stand-in: the unit `unit` of tier `tier` (in the space) whose span in sentence `sid` contains the span of an
    occurrence of the known part `part` (a finer tier's unit of the unknown word)."""
    tier: str
    unit: str
    sid: int
    span: Tuple[int, int]
    part_tier: str
    part: str
    part_span: Tuple[int, int]

    def to_obj(self) -> list:
        return [self.tier, self.unit, self.sid, list(self.span), self.part_tier, self.part, list(self.part_span)]


@dataclass(frozen=True)
class Part:
    tier: str
    unit: str
    span: Tuple[int, int]
    known: bool

    def to_obj(self) -> list:
        return [self.tier, self.unit, list(self.span), self.known]


@dataclass(frozen=True)
class PatternItem:
    """How one content RUN unit of the question is cut across the tiers (the granularity pattern) and, when the RUN unit is
    unknown, its stand-ins.  type: T1 the RUN unit is in the space; T2 unknown, all its (>= 1) WORD content parts are in the
    space; T3 unknown, some but not all; T4 no WORD part but some CHAR part is; T5 no part at all (G3 4.4).
    `via` = the tier of the parts the stand-ins come from ('WORD' for T2/T3, 'CHAR' for T4, '' otherwise).
    `n_standins` = distinct stand-in units; `n_sentences` = distinct sentences they come from; `pool` = units of the tier in
    the space (the chance a random unit is a stand-in is n_standins/pool, L-550)."""
    unit: str
    span: Tuple[int, int]
    type: str
    word_parts: Tuple[Part, ...]
    char_parts: Tuple[Part, ...]
    via: str
    standins: Tuple[Standin, ...]
    n_standins: int
    n_sentences: int
    pool: int

    def to_obj(self) -> list:
        return [self.unit, list(self.span), self.type, [p.to_obj() for p in self.word_parts],
                [p.to_obj() for p in self.char_parts], self.via, [s.to_obj() for s in self.standins],
                self.n_standins, self.n_sentences, self.pool]


@dataclass(frozen=True)
class QuestionReading:
    text: str                                   # the question as cut (attribution stripped)
    frames: Tuple[Frame, ...]
    slot: Optional[Slot]
    predicate: Optional[Predicate]
    pattern: Optional[Tuple[PatternItem, ...]]  # None when no space was given

    @property
    def slot_particle(self) -> Optional[str]:
        return None if self.slot is None else self.slot.particle

    def to_obj(self) -> dict:
        return {"format": FORMAT, "text": self.text, "frames": [f.to_obj() for f in self.frames],
                "slot": None if self.slot is None else self.slot.to_obj(),
                "predicate": None if self.predicate is None else self.predicate.to_obj(),
                "pattern": None if self.pattern is None else [p.to_obj() for p in self.pattern]}

    def to_bytes(self) -> bytes:
        return _canon(self.to_obj())


def _content(u: str, tier: str = sp.WORD) -> bool:
    return sp._has_letter(u) and not is_function_unit(u, tier)


def _after_label(lab: str, s: Optional[str]) -> str:
    return "particle" if lab == "particle" else ("end" if lab == "end" else "%s:%s" % (lab, s))


def slot_of(words: Sequence[Word]) -> Optional[Slot]:
    """The first interrogative WORD, extended over the content WORD units glued to it (no character between), and the
    P7 particle after the phrase (as the G2 probe, L-545)."""
    for j, (s, a, b) in enumerate(words):
        if s in INTERROG:
            k, end = j, b
            while k + 1 < len(words) and words[k + 1][1] == end and _content(words[k + 1][0]):
                k += 1
                end = words[k][2]
            lab, f, _ = follower(words, end)
            return Slot("".join(w[0] for w in words[j:k + 1]), (a, end), f if lab == "particle" else None,
                        _after_label(lab, f))
    return None


def predicate_of(words: Sequence[Word], slot: Optional[Slot]) -> Optional[Predicate]:
    """「XのYは何…」 when the interrogative has no P7 particle after it and stands right after は: Y = the run that ends at the
    unit before は, X = the same kind of run before the の that precedes Y
    (OP-G2-7 (c); a separate field, never merged into `slot`, L-548).  A run is the contiguous content WORD units, plus at
    most one function unit at its end (長+さ); a cleft 「…のは何」 (the unit before は is の) gives None."""
    if slot is None or slot.particle is not None:
        return None
    j = next((i for i, w in enumerate(words) if w[1] == slot.span[0]), None)
    if j is None or j < 2 or words[j - 1][0] != "は" or words[j - 1][2] != words[j][1]:
        return None

    def run_before(e: int) -> Optional[Tuple[str, Tuple[int, int], int]]:
        if e < 0 or words[e][0] in P7:
            return None
        i = e
        if not _content(words[i][0]):                        # one trailing function unit (a suffix: 長+さ) is allowed
            i -= 1
            if i < 0 or words[i][2] != words[i + 1][1] or words[i][0] in P7 or not _content(words[i][0]):
                return None
        k = i
        while k - 1 >= 0 and words[k - 1][2] == words[k][1] and _content(words[k - 1][0]):
            k -= 1
        return "".join(w[0] for w in words[k:e + 1]), (words[k][1], words[e][2]), k

    y = run_before(j - 2)
    if y is None:
        return None
    x = None
    k = y[2]
    if k - 1 >= 0 and words[k - 1][0] == "の" and words[k - 1][2] == words[k][1]:
        x = run_before(k - 2)
    return Predicate(y[0], y[1], None if x is None else x[0], None if x is None else x[1])


def _cut_inside(tier: str, u: str, a: int) -> List[Word]:
    """The parts of the unit string `u` (placed at offset `a` of the sentence) as `tier` cuts the string ITSELF (G1 3.2:
    「u を WORD の区切りで切った」; L-550) -- not as it is cut in its sentence context, which differs for a few units."""
    return [(w, a + x, a + y) for w, x, y in _raw_spans(tier, u)]


def standins_of(space: sp.Space, ix: SpanIndex, tier: str, parts: Sequence[Tuple[str, str]]) -> List[Standin]:
    """G1 3.2: the units v of `tier` (in the space) such that in some sentence the span of v contains the span of an
    occurrence of one of `parts` = [(part_tier, part unit)] (all in the space).  Every occurrence is listed, sorted by
    (unit, sid, span) -- a canonical order, not a ranking.  No cap (N-20)."""
    out: List[Standin] = []
    ts = space.tiers[tier]
    for ptier, part in parts:
        pt = space.tiers[ptier]
        for sid in pt.postings[part]:
            pspans = [sp_ for u, sp_ in zip(pt.sentence_units[sid], ix.spans(ptier, sid)) if u == part]
            vspans = list(zip(ts.sentence_units[sid], ix.spans(tier, sid)))
            for (pa, pb) in pspans:
                for v, (va, vb) in vspans:
                    if va <= pa and pb <= vb:
                        out.append(Standin(tier, v, sid, (va, vb), ptier, part, (pa, pb)))
    return sorted(set(out), key=lambda s: (s.unit, s.sid, s.span, s.part_tier, s.part, s.part_span))


def _pattern(space: sp.Space, ix: SpanIndex, text: str, words: Sequence[Word]) -> Tuple[PatternItem, ...]:
    items: List[PatternItem] = []
    for u, a, b in _raw_spans(sp.RUN, text):
        if is_function_unit(u, sp.RUN):
            continue
        wp = tuple(Part(sp.WORD, w, (wa, wb), w in space.tiers[sp.WORD].postings)
                   for w, wa, wb in _cut_inside(sp.WORD, u, a) if _content(w))
        cp = tuple(Part(sp.CHAR, c, (ca, cb), c in space.tiers[sp.CHAR].postings)
                   for c, ca, cb in _cut_inside(sp.CHAR, u, a) if _content(c, sp.CHAR))
        if u in space.tiers[sp.RUN].postings:
            items.append(PatternItem(u, (a, b), "T1", wp, cp, "", (), 0, 0, len(space.tiers[sp.RUN].postings)))
            continue
        kw = [p for p in wp if p.known]
        kc = [p for p in cp if p.known]
        if kw and len(kw) == len(wp):
            typ, via, use = "T2", sp.WORD, kw
        elif kw:
            typ, via, use = "T3", sp.WORD, kw
        elif kc:
            typ, via, use = "T4", sp.CHAR, kc
        else:
            typ, via, use = "T5", "", []
        st = standins_of(space, ix, sp.RUN, sorted({(p.tier, p.unit) for p in use})) if use else []
        items.append(PatternItem(u, (a, b), typ, wp, cp, via, tuple(st), len({s.unit for s in st}),
                                 len({s.sid for s in st}), len(space.tiers[sp.RUN].postings)))
    return tuple(items)


def read_question(question: str, space: Optional[sp.Space] = None, span_index: Optional[SpanIndex] = None) -> QuestionReading:
    """Gamma_Q (G3 4.2): the frames (the particle after every content WORD unit), the slot (the particle after the
    interrogative phrase), the predicate Y (if there is no P7 slot), and -- when a space is given -- the granularity
    pattern of the question's content RUN units with stand-ins (G3 4.4).  `space` should be a space built with the default
    function-word filter (what the question path reads); RUN units are 'known' iff they have a posting."""
    text = strip_attribution(question)
    words = words_of(text)
    frames = []
    for u, a, b in words:
        if _content(u):
            lab, f, _ = follower(words, b)
            frames.append(Frame(u, (a, b), f if lab == "particle" else None, _after_label(lab, f)))
    slot = slot_of(words)
    pattern = None
    if space is not None:
        pattern = _pattern(space, span_index or SpanIndex(space), text, words)
    return QuestionReading(text, tuple(frames), slot, predicate_of(words, slot), pattern)


# ---------------------------------------------------------------------------------------------------------------
# (4) the grammar cross of a window, its 24 rotations, the alignment
# ---------------------------------------------------------------------------------------------------------------
def foundation_cross() -> geo.Cross:
    """A geometry.Cross with L=1: centre は, arms the foundation particles in ladder order on
    +x -x +y -y +z -z (geometry.AXES order): の に で と を が (OP-G3-6 (a), the owner's 「梯子の順に x、y、z へ」)."""
    return geo.Cross.make(1, CENTRE_PARTICLE, [(p,) for p in ARM_PARTICLES])


@dataclass(frozen=True)
class GrammarCross:
    """Gamma_N for a window placeholder (G3 4.2): the foundation cross by reference (`foundation` = its sha, L-G1-6; the
    weights are not copied into any ratio), the attachments of the window's sentences by particle (the arm's seats), and
    kind(window) = the kind of the counts of the SIX ARM particles (G3 4.2 kind(W_N) = {p: |arm p|}; は is the centre, it
    has no arm, its count is recorded in `counts` but never enters the kind, L-549).  `window` is an opaque id, `sids` the
    window's sentences."""
    window: Union[int, str]
    sids: Tuple[int, ...]
    tiers: Tuple[str, ...]
    cross: geo.Cross
    foundation: str
    attachments: Tuple[Attachment, ...]
    counts: Tuple[Tuple[str, int], ...]          # per P7 particle, P7 order
    kind: Kind

    def seats(self, particle: str) -> Tuple[Tuple[str, str], ...]:
        """The distinct (tier, unit) of the arm of `particle`, in attachment order (tier, sid, start): sentence position
        order within a tier (G3 4.2).  `seats("は")` lists what follows-は records the window has; は is the centre, not an
        arm (L-549)."""
        return tuple(dict.fromkeys((a.tier, a.unit) for a in self.attachments if a.particle == particle))

    def to_obj(self) -> dict:
        return {"format": FORMAT, "window": self.window, "sids": list(self.sids), "tiers": list(self.tiers),
                "cross": json.loads(self.cross.serialize().decode("ascii")), "foundation": self.foundation,
                "counts": [[p, n] for p, n in self.counts], "kind": self.kind.to_obj(),
                "attachments": [a.as_list() for a in self.attachments]}

    def to_bytes(self) -> bytes:
        return _canon(self.to_obj())


def grammar_cross(records: Records, window: Union[int, str], sids: Iterable[int],
                  tiers: Sequence[str] = (sp.WORD,)) -> GrammarCross:
    """The grammar cross of a window placeholder: the records of the window's sentences (`sids`) on the given tiers
    (default WORD, L-549: summing two tiers would count one sentence's adjacency twice)."""
    keep = tuple(sorted(set(sids)))
    ks = frozenset(keep)
    ts = tuple(tiers)
    atts = tuple(a for a in records.attachments if a.sid in ks and a.tier in ts)
    cnt = {p: 0 for p in P7}
    for a in atts:
        cnt[a.particle] += 1
    return GrammarCross(window, keep, ts, foundation_cross(), foundation_sha(), atts,
                        tuple((p, cnt[p]) for p in P7), kind_of_counts({p: cnt[p] for p in ARM_PARTICLES}))  # L-549


def data_arm_counts(records: Records, arms: Sequence[Iterable[Union[str, Tuple[str, str]]]],
                    sids: Optional[Iterable[int]] = None, tier: str = sp.WORD) -> Tuple[Dict[str, int], ...]:
    """For each of the 6 data arms (index = world direction, geometry.AXES order) the exact number of attachments of the
    units seated on it, per particle: {particle: n}.  A unit is a plain string (tier `tier`) or (tier, unit).  With `sids`,
    only the attachments in those sentences count (the window's)."""
    if len(arms) != geo.N_ARMS:
        raise ValueError("six data arms expected")
    out = []
    for seat_units in arms:
        c: Dict[str, int] = {}
        for u in seat_units:
            t, w = (tier, u) if isinstance(u, str) else u
            for p, n in records.counts(t, w, sids).items():
                c[p] = c.get(p, 0) + n
        out.append({p: c[p] for p in P7 if p in c})
    return tuple(out)


@dataclass(frozen=True)
class Alignment:
    """The score of every one of the 24 rotations (`geometry.G24` order, an index is a label, L-16) and the group of all
    rotations that reach the maximum (a tie is a group, never broken by index, L-551)."""
    scores: Tuple[int, ...]
    best: int
    best_indices: Tuple[int, ...]
    identity_score: int

    @property
    def tied(self) -> bool:
        return len(self.best_indices) > 1

    def to_obj(self) -> dict:
        return {"format": FORMAT, "scores": list(self.scores), "best": self.best, "best_indices": list(self.best_indices),
                "identity_score": self.identity_score}

    def to_bytes(self) -> bytes:
        return _canon(self.to_obj())


def rotated_cross(r: geo.Rotation) -> geo.Cross:
    """The foundation cross turned by the cube rotation r (geometry.rotate: the labels move with the arms)."""
    return geo.rotate(foundation_cross(), r)


def align_score(arm_counts: Sequence[Mapping[str, int]], r: geo.Rotation) -> int:
    """Exact count of attachments agreeing with the label that the rotated grammar arm gives the data arm: grammar arm i
    (particle p_i) faces data arm r(i); the score adds counts[r(i)][p_i] over the six arms (the centre は faces the
    data centre in every rotation: it adds the same constant, so it is left out; L-551)."""
    world = rotated_cross(r).world_arms()
    return sum(arm_counts[w].get(world[w][0], 0) for w in range(geo.N_ARMS))


def align(arm_counts: Sequence[Mapping[str, int]]) -> Alignment:
    """All 24 rotations scored (no search beyond them); the maximum and every rotation that reaches it."""
    if len(arm_counts) != geo.N_ARMS:
        raise ValueError("six data arms expected")
    scores = tuple(align_score(arm_counts, r) for r in geo.G24)
    m = max(scores)
    return Alignment(scores, m, tuple(i for i, s in enumerate(scores) if s == m), scores[geo.G24.index(geo.IDENTITY)])


# ---------------------------------------------------------------------------------------------------------------
# (5) the read order
# ---------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Group:
    """Candidates read together.  `reason`: 'match' (the kind is the question's slot), 'particle' (another single
    particle, by ladder weight), 'tied' (the same tied set), 'none'.  `members` is sorted by id for byte identity only."""
    reason: str
    kind: Kind
    members: Tuple[Union[int, str], ...]

    def to_obj(self) -> list:
        return [self.reason, self.kind.to_obj(), list(self.members)]


@dataclass(frozen=True)
class ReadOrder:
    slot: Optional[str]
    groups: Tuple[Group, ...]

    def flat(self) -> Tuple[Union[int, str], ...]:
        return tuple(m for g in self.groups for m in g.members)

    def to_obj(self) -> dict:
        return {"format": FORMAT, "slot": self.slot, "groups": [g.to_obj() for g in self.groups]}

    def to_bytes(self) -> bytes:
        return _canon(self.to_obj())


def _id_key(i):
    return (type(i).__name__, i)


def read_order(question: Union[QuestionReading, str, None], candidates: Sequence[Tuple[Union[int, str], Kind]]) -> ReadOrder:
    """Deterministic read order of candidate crosses / windows from their kinds (G2 4.2 step 2, G3 4.2 steps 2-3):
      group 'match'    kind is the single particle that is the question's slot (only when the slot is in P7);
      then single-particle kinds, one group per particle, by the ladder weight (は 233 > の 144 > に 89 > で 55 > と 34 > を 21 > が 13);
      then tied kinds, one group per distinct tied set, by the descending ladder weights of the set compared in turn;
      then 'none'.
    A tied kind never matches a slot (L-G2-9); candidates of equal kind are one group, read together, whatever order they
    were given in.  A question with no P7 slot (None, or a predicate-only reading) has no 'match' group (L-548).
    The candidates are only ordered: the set is unchanged."""
    slot = question.slot_particle if isinstance(question, QuestionReading) else question
    if slot is not None and slot not in P7:
        raise ValueError("slot must be a foundation particle or None")
    seen = [c[0] for c in candidates]
    if len(set(seen)) != len(seen):
        raise ValueError("duplicate candidate ids")
    buckets: Dict[Tuple, List] = {}
    for cid, k in candidates:
        if k.label == "particle":
            m = k.particles[0] == slot
            key, reason = (0 if m else 1, (-WEIGHTS[k.particles[0]],)), ("match" if m else "particle")
        elif k.label == "tied":
            key, reason = (2, tuple(sorted(-WEIGHTS[p] for p in k.particles))), "tied"
        else:
            key, reason = (3, ()), "none"
        buckets.setdefault(key, []).append((cid, k, reason))
    groups = []
    for key in sorted(buckets):
        mem = buckets[key]
        groups.append(Group(mem[0][2], mem[0][1], tuple(sorted((m[0] for m in mem), key=_id_key))))
    return ReadOrder(slot, tuple(groups))
