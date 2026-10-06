"""T6 trace check: every word of every output sentence must trace back to the structure (design
4.7 "痕跡", decision "every output word must trace back to the structure", 100%).

Independent of the read-out: it does not call the cycle's Reader.  For every word occurrence of
every listed sentence it checks, from the tier space's postings and sentence unit lists alone,

  (a) the seat: the state of origin (the adopted stable state, which carries the seed, member and
      state version) holds exactly this word at the seat the path names (seat 0 = centre, seat
      1 + arm*L + k = arm `arm`, depth k from the outer end);
  (b) the sentence: the word is a unit of the tier (>= 1 sentence of the space has it; the first
      sid is recorded);
  (c) the edge: unless the word opens a leg, the previous word on the leg is its structural
      neighbour (consecutive seats of the leg, the last seat of a leg being next to the centre)
      and the pair is evidenced by >= 1 sentence that holds both (the first such sid recorded);
  (d) the sentence text and words are exactly the section paths in the stated order, for every
      origin of the sentence.

The report gives words checked / traced as an exact Fraction (100% = 1), the failures with reasons,
and the trace records {tier, state (seed, member, version), section, position, word, seat, sid,
n sentences, edge sid, n edge sentences}.  Nothing here changes the read-out.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Tuple

from verantyx.line3.geometry import N_ARMS
from verantyx.line3.readout import Adoption, PathAnswer, Readout, SectionPath, StateRead
from verantyx.line3.space import TierSpace


@dataclass(frozen=True)
class WordTrace:
    state: int
    seed: str
    member: int
    version: int
    section: int
    pos: int
    word: str
    seat: int
    sid: Optional[int]
    n_sentences: int
    edge_sid: Optional[int]
    edge_sentences: int
    ok: bool
    reason: str

    def to_json_obj(self) -> dict:
        return {"state": self.state, "seed": self.seed, "member": self.member, "version": self.version,
                "section": self.section, "pos": self.pos, "word": self.word, "seat": self.seat,
                "sid": self.sid, "n_sentences": self.n_sentences, "edge_sid": self.edge_sid,
                "edge_sentences": self.edge_sentences, "ok": self.ok, "reason": self.reason}


@dataclass(frozen=True)
class TraceReport:
    words_checked: int                       # word occurrences in the listed sentences
    words_traced: int
    sentences_checked: int
    sentences_ok: int
    path_words_checked: int                  # distinct (state, section, position) path words
    path_words_ok: int
    failures: Tuple[str, ...]

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.words_traced, self.words_checked) if self.words_checked else Fraction(1)

    @property
    def ok(self) -> bool:
        return self.fraction == 1 and self.sentences_ok == self.sentences_checked and not self.failures

    def to_json_obj(self) -> dict:
        f = self.fraction
        return {"words_checked": self.words_checked, "words_traced": self.words_traced,
                "fraction": "%d/%d" % (f.numerator, f.denominator),
                "sentences_checked": self.sentences_checked, "sentences_ok": self.sentences_ok,
                "path_words_checked": self.path_words_checked, "path_words_ok": self.path_words_ok,
                "failures": list(self.failures[:20]), "n_failures": len(self.failures)}


def _first_common(tier: TierSpace, a: str, b: str) -> Tuple[Optional[int], int]:
    pa, pb = tier.postings.get(a), tier.postings.get(b)
    if not pa or not pb:
        return None, 0
    common = sorted(set(pa).intersection(pb))
    for sid in common:
        us = tier.sentence_units[sid]
        if a in us and b in us:
            return sid, len(common)
    return None, 0


def _trace_path(tier: TierSpace, si: int, st: StateRead, p: SectionPath) -> List[WordTrace]:
    ref = st.ref
    flat, L = ref.flat, ref.L
    out: List[WordTrace] = []
    in_seg: Dict[int, Tuple[int, int]] = {}        # seat -> (segment index, index in segment)
    prev_in_seg: Dict[int, Optional[int]] = {}
    seg_ok = True
    for gi, seg in enumerate(p.segments):
        if not seg:
            seg_ok = False
            continue
        if not (1 <= seg[0] <= N_ARMS * L and (seg[0] - 1) % L == 0):
            seg_ok = False                          # a leg walk starts at its outer end
        for j, seat in enumerate(seg):
            if j > 0:
                a = seg[j - 1]
                adjacent = (seat == a + 1 and 1 <= a and (a - 1) % L != L - 1) or \
                           (seat == 0 and 1 <= a and (a - 1) % L == L - 1)
                if not adjacent:
                    seg_ok = False
            in_seg.setdefault(seat, (gi, j))
            prev_in_seg.setdefault(seat, seg[j - 1] if j > 0 else None)
    for pos, (w, seat) in enumerate(zip(p.words, p.seats)):
        reason = ""
        if not (0 <= seat < len(flat)) or flat[seat] != w:
            reason = "seat does not hold the word in the state"
        sid = None
        n = 0
        posting = tier.postings.get(w)
        if not reason:
            if not posting:
                reason = "word is not a unit of the tier"
            else:
                sid = posting[0]
                n = len(posting)
                if w not in tier.sentence_units[sid]:
                    reason = "posting does not match the sentence"
        esid, en_ = None, 0
        if not reason:
            if seat not in in_seg:
                reason = "seat is not on any walked leg"
            elif not seg_ok:
                reason = "leg walk is not a chain of neighbouring seats"
            else:
                prev = prev_in_seg[seat]
                if prev is not None:
                    esid, en_ = _first_common(tier, flat[prev], w)
                    if esid is None:
                        reason = "edge not evidenced by any sentence"
        out.append(WordTrace(si, ref.seed, ref.member, ref.version, p.section, pos, w, seat, sid, n,
                             esid, en_, not reason, reason))
    if p.words and p.words[-1] != p.unit:
        out[-1] = _fail(out[-1], "path does not end at the unit the section points to")
    return out


def _fail(t: WordTrace, reason: str) -> WordTrace:
    return WordTrace(t.state, t.seed, t.member, t.version, t.section, t.pos, t.word, t.seat, t.sid,
                     t.n_sentences, t.edge_sid, t.edge_sentences, False, reason)


def trace_answer(tier: TierSpace, ans: PathAnswer) -> Tuple[Tuple[WordTrace, ...], TraceReport]:
    """L-153: trace every word of every path of every item of the default answer form: seat, sentence
    and edge exactly as for sentences (_trace_path), and every path of an item ends at the item's
    centre.  `words_checked` counts the path words of the items; an item is ok iff all its words
    trace (an item that several states read out is checked on its first origin state, and every
    other origin must hold the same words)."""
    ptrace: Dict[Tuple[int, int, int], WordTrace] = {}
    all_traces: List[WordTrace] = []
    failures: List[str] = []
    for si, st in enumerate(ans.states):
        for p in st.paths:
            for t in _trace_path(tier, si, st, p):
                ptrace[(si, p.section, t.pos)] = t
                all_traces.append(t)
                if not t.ok:
                    failures.append("state %d section %d pos %d %r: %s" % (si, p.section, t.pos, t.word, t.reason))
    words_checked = words_traced = items_ok = 0
    for it in ans.items:
        n = sum(len(p.words) for p in it.paths)
        words_checked += n
        good = bool(it.origins)
        traced = 0
        for k, si in enumerate(it.origins):
            st = ans.states[si]
            same = (sorted(p.words for p in st.paths) == sorted(p.words for p in it.paths)) if ans.merge_sections \
                else (tuple(p.words for p in st.paths) == tuple(p.words for p in it.paths))
            if not same:
                good = False
                failures.append("item %r: origin state %d does not reproduce the words" % (it.centre, si))
            if any(p.unit != it.centre or (p.words and p.words[-1] != it.centre) for p in st.paths):
                good = False
                failures.append("item %r: a path of state %d does not end at the centre" % (it.centre, si))
            if k == 0:
                traced = sum(1 for p in st.paths for i in range(len(p.words)) if ptrace[(si, p.section, i)].ok)
        if it.centre not in tier.postings:
            good = False
            failures.append("item %r: the centre is not a unit of the tier" % it.centre)
        words_traced += traced if good else 0
        if good and traced == n:
            items_ok += 1
        elif good:
            failures.append("item %r: a path word does not trace" % it.centre)
    rep = TraceReport(words_checked, words_traced, len(ans.items), items_ok,
                      len(ptrace), sum(1 for t in ptrace.values() if t.ok), tuple(failures))
    return tuple(all_traces), rep


def trace_readout(tier: TierSpace, readout) -> Tuple[Tuple[WordTrace, ...], TraceReport]:
    """Trace every word of every listed sentence; returns (word traces of the section paths used,
    report).  A word occurrence counts as traced iff its path word traces (a)-(c) and its sentence
    reproduces (d) for every origin.  A `PathAnswer` (the default answer form) is traced by
    `trace_answer`."""
    if isinstance(readout, PathAnswer):
        return trace_answer(tier, readout)
    ptrace: Dict[Tuple[int, int, int], WordTrace] = {}
    all_traces: List[WordTrace] = []
    failures: List[str] = []
    paths_by: Dict[Tuple[int, int], SectionPath] = {}
    for si, st in enumerate(readout.states):
        for p in st.paths:
            paths_by[(si, p.section)] = p
            for t in _trace_path(tier, si, st, p):
                ptrace[(si, p.section, t.pos)] = t
                all_traces.append(t)
                if not t.ok:
                    failures.append("state %d section %d pos %d %r: %s" % (si, p.section, t.pos, t.word, t.reason))
    words_checked = words_traced = sent_ok = 0
    for s in readout.sentences:
        words_checked += len(s.words)
        good = bool(s.origins) and "".join(s.words) == s.text
        used: List[Tuple[int, int, int]] = []
        for k, (si, order) in enumerate(s.origins):
            ws: List[str] = []
            keys: List[Tuple[int, int, int]] = []
            for sec in order:
                p = paths_by.get((si, sec))
                if p is None:
                    good = False
                    break
                ws.extend(p.words)
                keys.extend((si, sec, i) for i in range(len(p.words)))
            else:
                if tuple(ws) != s.words:
                    good = False
                    failures.append("sentence %r: origin %d does not reproduce the words" % (s.text, k))
                elif k == 0:
                    used = keys
                continue
            failures.append("sentence %r: origin %d names a missing section path" % (s.text, k))
        if good and len(used) == len(s.words) and all(ptrace[k].ok for k in used):
            sent_ok += 1
            words_traced += len(s.words)
        else:
            words_traced += sum(1 for k in used if ptrace[k].ok) if good else 0
            if good:
                failures.append("sentence %r: a path word does not trace" % s.text)
    rep = TraceReport(words_checked, words_traced, len(readout.sentences), sent_ok,
                      len(ptrace), sum(1 for t in ptrace.values() if t.ok), tuple(failures))
    return tuple(all_traces), rep


def check_adoption(readout: Readout, adoption: Adoption) -> bool:
    """The adopted answer is one of the listed sentences, with the same words and origins."""
    return any(s == adoption.sentence for s in readout.sentences)
