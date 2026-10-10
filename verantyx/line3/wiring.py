"""G3-k: the unknown-word stand-ins and the grammar layer's read order, wired into the question path (docs/LINE3_LOCAL_DECISIONS.md "G3-k", L-800..).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md, 「G3 の系統の頭打ち後の方向」, verbatim choice): 「未知語の代役と文法層の読む順を結合した一覧に繋ぐ
（G2-f の成果を使う）」.  Binding from before: the grammar layer decides the READ ORDER only, never the candidate set (G2 4.2 / B-1; L-552); it reads the
particle after the interrogative (slot), the predicate slot 「XのYは何ですか」 (L-548), the question's granularity pattern with its stand-ins for unknown
words (L-550); a stem takes the particle after the WHOLE word (owner after G2-f, grammar.STEMS "whole_word"); the question is fed to every sovereign and
sorted by FORM (「両替機…タンク」); a stand-in is `granularity-derived`, NOT evidence of the unknown word (G1 I-G1-2), and a chance control is always reported.

This module is the only place that imports both the grammar layer and what the question path needs of it; `ask.py`, `cycle.py`, `matryoshka.py` import this
module lazily (never `grammar`: tests/line3/test_grammar.py keeps the question path free of the grammar module) and the grammar module imports none of them.

What it provides (pure functions of their arguments; no floating-point number, no division operator, nothing from a set or dict order):
  * `intake(space, question, span_index)`: the question cut like the RUN tier (cycle.split_question, then V2), the grammar reading, the FORM (L-642 order: slot >
    predicate > standin > plain) and, for each content RUN unit that is absent from the corpus (pattern type T2..T5), its stand-in units (grammar.standins_of:
    WORD parts for T2 / T3, CHAR parts for T4, nothing for T5: G1's L_RW / L_RC).  `GrammarIntake.run_units` = the question units + the stand-in units that are not
    already question units, in that order (the stand-ins in the order of the unknown words in the question, each word's in code point order: a label, not a rank).
  * `ReadHook`: the picklable callable `cycle.plan_read(grammar=...)` takes: seeds -> {seed: (rank, reason, kind label)}, the kind of a cross = the kind of its
    centre word (grammar.Records.kind, the records read with stem "whole_word"; CHAR has no records, L-541: kind none), ordered by grammar.read_order with the
    question's slot (form "slot" only; every other form passes None, L-642 / L-548).
  * `tier_kw`: the keywords of one tier's cycle.ask_tier: RUN gets the extended units, the stand-ins marked in QueryContext.standins (they select the crosses to
    read and count in the read order; they are NOT in the query cross, the sections or E_Q: the energies of the question are the original units', L-802);
    every tier gets the read hook.
  * `via_standin_of(answer, originals, placements)`: per entry of a tier's answer, whether every state it came from lies in a cross that holds no ORIGINAL question
    unit (centre, seats and twins of the placement of the state's seed): the entry exists only through a stand-in.  `read_via_standin_of`: whether every state it came
    from lies in a cross that the same ordering would NOT have read under the same cap without the stand-ins (the exact diff of two plans, L-811).
  * `reask_kw`: the keywords of the layers' re-asks (the read hook of every tier, the mark for RUN).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import cycle as cy
from verantyx.line3 import grammar as gr
from verantyx.line3 import space as sp
from verantyx.line3.funcwords import default_filter
from verantyx.line3.granularity import SpanIndex

GRAMMARS: Tuple[str, ...] = ("off", "on")                 # the switch of ask / combined / CLI `--grammar`; "off" = every committed byte
TIER = sp.RUN                                              # the tier whose unknown words get stand-ins (grammar.standins_of is RUN, L-550)
PROVENANCE = "stand-in"                                    # the mark of an added query unit
FORMS: Tuple[str, ...] = ("slot", "predicate", "standin", "plain")


def classify_form(reading: gr.QuestionReading) -> str:
    """L-642: slot (a P7 particle after the interrogative phrase) > predicate (the XのYは何ですか slot, L-548) > standin (an unknown RUN unit of the question: pattern
    type T2..T5) > plain."""
    if reading.slot_particle is not None and reading.slot_particle in gr.P7:
        return "slot"
    if reading.predicate is not None:
        return "predicate"
    if any(p.type != "T1" for p in (reading.pattern or ())):
        return "standin"
    return "plain"


# --------------------------------------------------------------------------------------------------------------
# (1) the question intake with the stand-ins  (L-801, L-802)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class StandinWord:
    """One unknown content RUN unit of the question and what stands in for it."""
    word: str
    type: str                                  # T2 | T3 | T4 | T5 (grammar.PatternItem.type)
    via: str                                   # "WORD" (T2, T3) | "CHAR" (T4) | "" (T5)
    parts: Tuple[Tuple[str, str], ...]         # the known parts the stand-ins come through, (tier, unit), sorted
    units: Tuple[str, ...]                     # ALL the stand-in units of this word (RUN units of the space), code point order
    added: Tuple[str, ...]                     # those of them that were ADDED to the query (not already a question unit nor added for an earlier word)
    unit_parts: Tuple[Tuple[str, Tuple[Tuple[str, str], ...], Tuple[int, ...]], ...]   # per unit: (unit, the parts it stands in through, its sentences)
    n_standins: int
    n_sentences: int
    pool: int                                  # the RUN units of the space (G1: the chance a random RUN unit is a stand-in is n_standins / pool)

    def chance(self) -> Fraction:
        return Fraction(self.n_standins, self.pool) if self.pool else Fraction(0)

    def to_obj(self, full: bool = False) -> dict:
        o = {"word": self.word, "type": self.type, "via": self.via, "parts": [list(p) for p in self.parts], "provenance": PROVENANCE,
             "units": list(self.units), "added": list(self.added), "n_standins": self.n_standins, "n_sentences": self.n_sentences,
             "pool": self.pool, "chance": "%d/%d" % (self.n_standins, self.pool)}
        if full:
            o["unit_parts"] = [[u, [list(p) for p in ps], list(sids)] for u, ps, sids in self.unit_parts]
        return o


@dataclass(frozen=True)
class GrammarIntake:
    question: str
    units: Tuple[str, ...]                     # the question cut like the RUN tier, after V2: the ORIGINAL query units
    reading: gr.QuestionReading
    form: str                                  # slot | predicate | standin | plain
    slot: Optional[str]                        # the P7 particle that selects the match group (form "slot"), else None
    words: Tuple[StandinWord, ...]             # the unknown content RUN units that are query units, in question order
    standins: Tuple[str, ...]                  # the units ADDED to the query, in order

    @property
    def run_units(self) -> Tuple[str, ...]:
        return self.units + self.standins

    @property
    def n_standins(self) -> int:
        return len(self.standins)

    def grammar_form(self) -> dict:
        r = self.reading
        types: Dict[str, int] = {}
        for p in (r.pattern or ()):
            types[p.type] = types.get(p.type, 0) + 1
        return {"form": self.form, "slot": None if r.slot is None else r.slot.particle,
                "slot_phrase": None if r.slot is None else r.slot.phrase, "slot_after": None if r.slot is None else r.slot.after,
                "predicate": None if r.predicate is None else r.predicate.y, "predicate_of": None if r.predicate is None else r.predicate.x,
                "pattern_types": {k: types[k] for k in sorted(types)}, "standin_units": len(self.standins),
                "read_order": ("question units held (originals, then stand-ins), then the kind of the cross = the slot, then the ladder weight of the kind, "
                               "then E_Q" if self.form == "slot" else
                               "question units held (originals, then stand-ins), then the ladder weight of the kind (no slot particle), then E_Q")}

    def standins_obj(self, full: bool = False) -> List[dict]:
        return [w.to_obj(full) for w in self.words]

    def header_row(self) -> dict:
        """The `grammar` row of the combined list's header (L-808)."""
        r = self.reading
        return {"source": "grammar", "form": self.form, "slot": None if r.slot is None else r.slot.particle,
                "predicate": None if r.predicate is None else r.predicate.y, "standins": len(self.standins),
                "unknown_words": [w.word for w in self.words]}


def intake(space: sp.Space, question: str, span_index: Optional[SpanIndex] = None) -> GrammarIntake:
    """The question as the RUN tier cuts it (V2 applied), its grammar reading and form, and the stand-ins of its unknown content RUN units.  A unit of the
    pattern that V2 drops (a question word, a function unit) is not a query unit and gets no stand-ins; an unknown unit is one that has no posting
    (pattern type != T1).  The stand-in units already in the question are not added again."""
    ix = span_index or SpanIndex(space)
    all_units = cy.split_question(TIER, question)
    flt = default_filter(TIER)
    units = tuple(u for u in all_units if not flt(u)) if flt is not None else tuple(all_units)
    reading = gr.read_question(question, space, ix)
    form = classify_form(reading)
    have = set(units)
    words: List[StandinWord] = []
    added_all: List[str] = []
    for p in (reading.pattern or ()):
        if p.type == "T1" or p.unit not in have:
            continue
        us = sorted({s.unit for s in p.standins if s.tier == TIER})
        new = [u for u in us if u not in have]
        have.update(new)
        added_all.extend(new)
        by: Dict[str, Tuple[set, set]] = {}
        for s in p.standins:
            if s.tier == TIER:
                a, b = by.setdefault(s.unit, (set(), set()))
                a.add((s.part_tier, s.part))
                b.add(s.sid)
        words.append(StandinWord(p.unit, p.type, p.via, tuple(sorted({(x.tier, x.unit) for x in p.word_parts + p.char_parts if x.known and x.tier == p.via})),
                                 tuple(us), tuple(new),
                                 tuple((u, tuple(sorted(by[u][0])), tuple(sorted(by[u][1]))) for u in us), p.n_standins, p.n_sentences, p.pool))
    return GrammarIntake(question, units, reading, form, reading.slot_particle if form == "slot" else None, tuple(words), tuple(added_all))


# --------------------------------------------------------------------------------------------------------------
# (2) the read order of the crosses: the kind of the centre word  (L-803)
# --------------------------------------------------------------------------------------------------------------
def kind_label(k: gr.Kind) -> str:
    return k.label + ("" if not k.particles else ":" + "+".join(k.particles))


class ReadHook:
    """cycle.plan_read(grammar=...): the grammar layer's read order of candidate crosses of one tier.  A cross's kind is the kind of its seed (centre word)
    over the particle records (`records.kind(tier, seed)`: the particle after the word, a stem taking the particle after the whole WORD); a tier with no records
    (CHAR, L-541) has kind none for every cross.  `slot` = the question's slot particle (form "slot") or None.  Picklable (the sweeps fork workers)."""

    def __init__(self, tier: str, records: gr.Records, slot: Optional[str]) -> None:
        self.tier, self.records, self.slot = tier, records, slot

    def kind(self, seed: str) -> gr.Kind:
        if self.tier in self.records.tiers():
            return self.records.kind(self.tier, seed)
        return gr.NONE_KIND

    def __call__(self, seeds: Sequence[str]) -> Dict[str, Tuple[int, str, str]]:
        ro = gr.read_order(self.slot, [(s, self.kind(s)) for s in seeds])
        out: Dict[str, Tuple[int, str, str]] = {}
        for i, g in enumerate(ro.groups):
            for m in g.members:
                out[m] = (i, g.reason, kind_label(g.kind))
        return out


def context_of(owner) -> Tuple[SpanIndex, gr.Records]:
    """(span index, particle records with the whole-word stem rule) of the space of `owner` (an ask.Index or a slide_query.WindowIndex), built once and kept on it."""
    c = getattr(owner, "_wiring_ctx", None)
    if c is None:
        c = (getattr(owner, "span_index", None) or SpanIndex(owner.space), records_of(owner.space))
        try:
            owner._wiring_ctx = c
        except AttributeError:
            pass
    return c


def records_of(space: sp.Space) -> gr.Records:
    """The particle records read with the owner's stem rule (a unit that ends inside a WORD takes the particle after the whole WORD)."""
    return gr.records_of_space(space, stem="whole_word")


def tier_kw(gi: GrammarIntake, tier: str, records: gr.Records) -> dict:
    """The keywords of cycle.ask_tier for one tier under grammar "on": the read hook for every tier; for RUN with stand-ins the extended unit list and the mark
    `standins` (L-802: the stand-ins select crosses and count in the read order, E_Q stays the original units')."""
    kw: dict = {"grammar": ReadHook(tier, records, gi.slot)}
    if tier == TIER and gi.standins:
        kw.update(units=gi.run_units, standins=gi.standins)
    return kw


def reask_kw(gi: GrammarIntake, tiers: Sequence[str], records: gr.Records) -> Dict[str, dict]:
    """The keywords of the layers' re-asks (matryoshka.ask_layered(tier_kw=), feedback "down", L-807 / L-813): the same read hook as layer 0 for every tier, and for RUN with
    stand-ins the mark `standins`.  NOT `tier_kw`: a re-ask passes its own `units` (the question's plus what the upper layers found)."""
    out: Dict[str, dict] = {}
    for t in tiers:
        kw: dict = {"grammar": ReadHook(t, records, gi.slot)}
        if t == TIER and gi.standins:
            kw["standins"] = gi.standins
        out[t] = kw
    return out


def via_standin_of(answer, originals: frozenset, placements) -> Tuple[bool, ...]:
    """Per entry of a tier's read-out (readout.PathAnswer): True iff the entry came from at least one state and EVERY state it came from lies in a cross that holds no
    ORIGINAL question unit, i.e. the entry exists only through a stand-in.  The cross of a state is the placement of its seed (`placements.cross_for(seed)`),
    its units are what V1 saw (cycle.placement_units: the centre, the seats and the twins), not the single arrangement the end state shows.  () when there is no answer;
    an entry with no origin state is False (L-812)."""
    if answer is None:
        return ()
    held: Dict[str, bool] = {}

    def holds_original(seed: str) -> bool:
        if seed not in held:
            held[seed] = bool(cy.placement_units(placements.cross_for(seed)) & originals)
        return held[seed]
    out: List[bool] = []
    for e in answer.entries:
        sts = {si for a in e.arrangements for si in a.origins}
        out.append(bool(sts) and all(not holds_original(answer.states[si].ref.seed) for si in sts))
    return tuple(out)


def read_via_standin_of(answer, order_only_read: Optional[Sequence[str]]) -> Tuple[bool, ...]:
    """Per entry: True iff the entry came from at least one state and EVERY state it came from lies in a cross that the SAME ordering would NOT have read under the same cap
    without the stand-ins (`ReadPlan.order_only_read`, computed by also planning the read without them: an exact diff of the two read sets).  `via_standin`
    implies it for crosses (a cross with no original unit is no candidate without the stand-ins; a window entry can be `via_standin` through a member that holds only a stand-in in a window both orders read, so the implication is not claimed there).  It also covers the entries of a cross that holds an original unit and was read only
    because a stand-in decided the tie.  `order_only_read` None (no stand-ins in the query) = nothing was read because of one: all False.  () when there is no answer (L-811)."""
    if answer is None:
        return ()
    if order_only_read is None:
        return tuple(False for _ in answer.entries)
    ro = set(order_only_read)
    out: List[bool] = []
    for e in answer.entries:
        sts = {si for a in e.arrangements for si in a.origins}
        out.append(bool(sts) and all(answer.states[si].ref.seed not in ro for si in sts))
    return tuple(out)
