"""T6 read-out of the line-3 build: from the stable states the query cycle adopted, read the words
out in order along the section -> centre paths, form sentence candidates, adopt the most stable
one or present a choice, take the user's choice in.  Exact arithmetic only.

Binding decisions (ops/decisions/2026-10-06_line3_faithful_build.md):
  decision 7   "その状態から言葉を順に読み出して文の候補を作って一番安定状態を採用するか選択方式に
        する": from the stable state the words are read out in order along the section -> centre
        paths; the most stable candidate is adopted, or a choice is shown.
  L3-8   the words of the axes connecting the section to the centre are joined into the sentence.
  I-13   "並べ方すべてが候補": every ordering is a candidate.
  N-13   orderings are of whole section paths ("断面の経路ごと"): k working sections -> k! orderings
        (k <= 6, so at most 720 per state).
  I-14   one most stable candidate -> adopt (ANSWER); ties -> a list (CHOICE).
  I-15   the stability of a candidate = the stability of the state that produced it (share of
        single moves that leave the state's result unchanged; cycle.py L-103), kept as a Fraction.
  N-14   ties are built as they come ("そのまま組んで影響を見る"): no tie-break by order.
  N-20   no cap on the list; the counts are reported; a "too many" flag (L-21 default 20, a
        display value only) tells the owner; an intake takes the user's choice.
  M-4 (a)  the user's choice is written to memory as the adopted answer ("採用した答え") and the
        base arrangement is not changed: here only the intake / record (memory is T11).
  N-10   output = `answer` and `thought`.
  Every output word must trace back to the structure: trace_check.py.

Local decisions (docs/LINE3_LOCAL_DECISIONS.md, L-120..):
  L-120 Section path = the cells a working section walks from the outer end of a leg it sees toward
        the centre, exactly as cycle.Reader walks them (edge evidenced n > 0 and E of the section's
        energy not dropping), up to and including the unit it points to (d_s).  The query unit
        attached beyond the outer end is NOT part of the path (it is the question, not the
        structure).
  L-121 A section sees up to three legs (window 1, ring order previous, own, next).  Its path is
        the legs whose walk ends at the unit the section points to, read in ring order, each leg
        outer -> inner, the shared end unit written once at the end.  (The legs reaching the same
        end are all part of what the section reads; picking one would be an order tie-break.)
  L-122 Working sections only (sections that point to a unit); a state with no working section
        yields no sentence (counted).  Sentence = the words joined with no separator (the data
        are Japanese).
  L-123 A candidate is one (state, ordering of the k whole section paths).  Orderings are generated
        in lexicographic order of section index (a label).  `orderings` counts all of them
        (k! per state, exact); the sentence list is over DISTINCT texts (two orderings or two
        states that read out the same words are the same sentence); each sentence keeps all its
        origins.
  L-124 Stability of a sentence = the best stability among its origins; the list is every sentence
        at the best stability (the adopted states of the cycle are already at one stability, so
        the sentences differ only in their words).  Sentences below the best stability are
        counted, not listed.
  L-125 Verdicts: ANSWER (exactly one sentence at the best stability), CHOICE (several: the list,
        sorted by text, a label), UNKNOWN_NO_PATH (no sentence could be read out).
  L-126 "Too many" = list size > `too_many` (default 20, L-21), a display flag; the output never
        shortens the list.
  L-150.. (after T6v, owner decision): the DEFAULT answer form is `PathAnswer` (below):  per adopted
        state the agreed centre and the ordered word list of each section path, as read -- no
        sentence is built and nothing is reordered.  The sentence-candidate read-out of T6
        (everything above) is kept as the option `form="sentences"`.  See the PathAnswer docs.
  L-180.. (T6z, owner): defaults merge_sections=True, similar="word_set" (entries), see PathAnswer.
  L-127 Intake: `choose(readout, which)` accepts an index into the list or the exact text; anything
        else is an error.  `adopt(readout)` is the automatic ANSWER.  Both return an `Adoption`
        whose `memory_record()` is a `memory_answer` sentence (design L-19 kind) with `source`
        "auto" or "user_choice", the trace, `base_changed` False; nothing is stored here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import permutations
from math import factorial
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

from verantyx.line3 import cycle as cy
from verantyx.line3.geometry import DEFAULT_WINDOW, N_ARMS
from verantyx.line3.placement import Flat

UNKNOWN_NO_PATH = "UNKNOWN_NO_PATH"
TOO_MANY_DEFAULT = 20                    # L-21 / L-126
RECORD_KIND = "memory_answer"            # design L-19


def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


def parse_fraction(s: str) -> Fraction:
    a, b = s.split("/")
    return Fraction(int(a), int(b))


# --------------------------------------------------------------------------
# inputs: the adopted stable states
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class StateRef:
    """One adopted stable state of the cycle (world-view flat tuple, L-100) and its stability."""
    tier: str
    seed: str
    member: int
    flat: Flat
    stability: Fraction
    unit: Optional[str] = None          # the answer unit the cycle gave (information only)
    version: int = 0                    # design L-22 state version (T5 changes no state: 0)

    @property
    def L(self) -> int:
        return (len(self.flat) - 1) // N_ARMS


def states_from_result(tr: "cy.TierResult") -> Tuple[StateRef, ...]:
    """The adopted candidates of a cycle result (T5, in memory)."""
    return tuple(StateRef(tr.tier, c.seed, c.member, tuple(c.end.flat), c.inv, c.unit, tr.state_version)
                 for c in tr.candidates)


def states_from_answer_obj(ans: Mapping) -> Tuple[StateRef, ...]:
    """The adopted candidates of a stored T5 `answer` object (its `trace`)."""
    return tuple(StateRef(t["tier"], t["seed"], t["member"], tuple(t["state"]),
                          parse_fraction(t["stability"]), t.get("unit"), 0) for t in ans.get("trace", ()))


# --------------------------------------------------------------------------
# section paths (L-120, L-121, L-122)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SectionPath:
    section: int                            # world section 0..5
    attached: Optional[str]                 # the query unit on that section (not part of the path)
    unit: str                               # the unit the section points to (d_s)
    words: Tuple[str, ...]                  # the words read, in order
    seats: Tuple[int, ...]                  # flat index of each word's seat (0 = centre)
    segments: Tuple[Tuple[int, ...], ...]   # per leg walked: its seats outer -> inner (edges are inside)

    @property
    def text(self) -> str:
        return "".join(self.words)


def section_paths(reader: "cy.Reader", flat: Flat, L: int) -> Tuple[SectionPath, ...]:
    """The path of every working section of a state, in section order."""
    ev = reader.evaluate(flat, L)
    centre = flat[0]
    legs = [flat[1 + a * L: 1 + (a + 1) * L] for a in range(N_ARMS)]
    out: List[SectionPath] = []
    for s in range(N_ARMS):
        d = ev.sections[s]
        if d is None:
            continue
        qa = reader.attached[s]
        segs: List[Tuple[Tuple[str, int], ...]] = []
        for p in reader.pos[s]:
            cells = legs[p] + (centre,)
            if cells[0] is None:
                continue
            cur = cells[0]
            path = [(cur, 1 + p * L)]
            for j in range(1, len(cells)):
                nxt = cells[j]
                if nxt is None or reader.f.npair(cur, nxt) <= 0 or reader.en(nxt, qa) < reader.en(cur, qa):
                    break
                path.append((nxt, 1 + p * L + j if j < L else 0))
                cur = nxt
            if cur == d:
                segs.append(tuple(path))
        if not segs:                                           # cannot happen: d came from these walks
            raise AssertionError("section %d points to %r but no leg ends there" % (s, d))
        end_seat = segs[-1][-1][1]
        body: List[Tuple[str, int]] = []
        for sg in segs:
            body.extend(c for n, c in enumerate(sg) if not (n == len(sg) - 1 and c[1] == end_seat))
        body.append((d, end_seat))
        out.append(SectionPath(s, qa, d, tuple(w for w, _ in body), tuple(i for _, i in body),
                               tuple(tuple(i for _, i in sg) for sg in segs)))
    return tuple(out)


# --------------------------------------------------------------------------
# candidates (I-13, N-13, L-123..L-126)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class StateRead:
    ref: StateRef
    paths: Tuple[SectionPath, ...]

    @property
    def k(self) -> int:
        return len(self.paths)

    @property
    def orderings(self) -> int:
        return factorial(len(self.paths)) if self.paths else 0


@dataclass(frozen=True)
class Sentence:
    text: str
    words: Tuple[str, ...]
    stability: Fraction
    origins: Tuple[Tuple[int, Tuple[int, ...]], ...]    # (state index, order of section indices)


@dataclass(frozen=True)
class Readout:
    question: str
    tier: str
    states: Tuple[StateRead, ...]
    sentences: Tuple[Sentence, ...]           # the list at the best stability, sorted by text (label)
    verdict: str
    best_stability: Optional[Fraction]
    orderings_total: int                      # sum of k! over the states (exact, I-13/N-13)
    distinct_total: int                       # distinct texts over all states and stabilities
    below_best: int                           # distinct texts not at the best stability
    states_without_path: int
    too_many: bool
    too_many_limit: int

    # ---- output (N-10) ----
    def answer_obj(self, with_sentences: bool = True) -> dict:
        o = {"verdict": self.verdict, "stability": _fs(self.best_stability),
             "listed": len(self.sentences), "too_many": self.too_many,
             "text": self.sentences[0].text if self.verdict == cy.ANSWER else None}
        if with_sentences:
            o["sentences"] = [{"text": s.text, "words": list(s.words), "stability": _fs(s.stability),
                               "origins": [[i, list(order)] for i, order in s.origins]} for s in self.sentences]
        return o

    def thought_obj(self) -> dict:
        return {
            "question": self.question, "tier": self.tier,
            "counts": {"states": len(self.states), "states_without_path": self.states_without_path,
                       "orderings": self.orderings_total, "distinct_sentences": self.distinct_total,
                       "listed": len(self.sentences), "below_best_stability": self.below_best},
            "too_many_limit": self.too_many_limit,
            "states": [{"seed": st.ref.seed, "member": st.ref.member, "stability": _fs(st.ref.stability),
                        "state": list(st.ref.flat), "version": st.ref.version, "k": st.k,
                        "orderings": st.orderings,
                        "paths": [{"section": p.section, "attached": p.attached, "unit": p.unit,
                                   "words": list(p.words), "seats": list(p.seats),
                                   "segments": [list(g) for g in p.segments]} for p in st.paths]}
                       for st in self.states],
        }

    def to_json_obj(self, with_sentences: bool = True) -> dict:
        return {"answer": self.answer_obj(with_sentences), "thought": self.thought_obj()}

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json_obj(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def read_sentences(facts: "cy.TierFacts", ctx: "cy.QueryContext", states: Sequence[StateRef], *,
                   question: str = "", too_many: int = TOO_MANY_DEFAULT,
                   window: int = DEFAULT_WINDOW, by_stability: bool = True) -> Readout:
    """(T6 form, option `form="sentences"`)  Read the words of the adopted states out along their section -> centre paths and form the
    sentence candidates (every ordering of whole section paths of every state)."""
    reader = cy.Reader(facts, ctx.attached, ctx.energy_units, window)
    tier = states[0].tier if states else facts.tier.name
    reads = tuple(StateRead(s, section_paths(reader, s.flat, s.L)) for s in states)
    acc: Dict[str, dict] = {}
    orderings_total = 0
    for si, sr in enumerate(reads):
        if not sr.paths:
            continue
        idx = tuple(range(sr.k))
        for order in permutations(idx):
            orderings_total += 1
            words = tuple(w for o in order for w in sr.paths[o].words)
            text = "".join(words)
            e = acc.get(text)
            if e is None:
                e = acc[text] = {"words": words, "stab": sr.ref.stability, "origins": []}
            elif sr.ref.stability > e["stab"]:
                e["stab"] = sr.ref.stability
            e["origins"].append((si, tuple(sr.paths[o].section for o in order)))
    best = max((e["stab"] for e in acc.values()), default=None)
    # T6v V3 passes by_stability=False: the states were chosen by another rule (sharing with the
    # query), so every sentence of every given state is listed whatever its stability.
    listed = [Sentence(t, e["words"], e["stab"], tuple(e["origins"]))
              for t, e in sorted(acc.items()) if (not by_stability) or e["stab"] == best]
    below = 0 if not by_stability else sum(1 for e in acc.values() if e["stab"] != best)
    if not listed:
        verdict = UNKNOWN_NO_PATH
    elif len(listed) == 1:
        verdict = cy.ANSWER
    else:
        verdict = cy.CHOICE
    return Readout(question, tier, reads, tuple(listed), verdict, best, orderings_total, len(acc), below,
                   sum(1 for r in reads if not r.paths), len(listed) > too_many, too_many)


def read_out_stored(facts: "cy.TierFacts", question: str, ans: Mapping, *, scope: str = "first_layer",
                    too_many: int = TOO_MANY_DEFAULT, units: Optional[Sequence[str]] = None,
                    form: str = "centre_paths") -> Union[PathAnswer, Readout]:
    """Convenience: read out a stored T5 `answer` object (its trace holds the adopted states)."""
    q = tuple(units) if units is not None else cy.split_question(facts.tier.name, question)
    ctx = cy.make_context(q, scope)
    return read_out(facts, ctx, states_from_answer_obj(ans), question=question, too_many=too_many, form=form)


# --------------------------------------------------------------------------
# the default answer form after T6v: the agreed centre and the words of each section path
# --------------------------------------------------------------------------
# L-150  Answer form (owner: "断面が一致した中心と経路の語を答えにする"): for every adopted state an
#        ITEM = (centre, paths).  centre = the unit the working sections agreed on (the cycle's
#        answer unit of the state; the end unit of every section path); paths = for each working
#        section in section order, the ordered words of its path exactly as read (L-120/L-121).
#        Nothing is reordered into sentences; no ordering is chosen or enumerated.
# L-151  Items are DISTINCT by (centre, the word lists of the paths in section order): adopted
#        states that read out the same are one item (all origin states kept), so a list appears
#        only when the states genuinely differ.  Item order in the list = sorted by (centre,
#        words) (a label, never a winner).  Stability of an item = the best stability among its
#        origin states (information only; the states were already chosen by L-142).
# L-152  Verdict: ANSWER (exactly one item), CHOICE (a list of several items, N-20: the list is
#        never shortened, `too_many` is a display flag), UNKNOWN_NO_PATH (no adopted state has a
#        working section path).  `answer_obj()["centre"]`/["paths"] are set only for ANSWER.
# L-153  Trace: trace_check.trace_answer() checks every word of every path of every item (seat,
#        sentence, edge) and that every path ends at the centre; 100% required.
@dataclass(frozen=True)
class AnswerPath:
    section: int
    attached: Optional[str]
    words: Tuple[str, ...]
    # L-160: the sentences each step of the path traces to: (from, to, sids) in walk order; the
    # first step of a leg is (attached query unit, first word), every other step (previous word,
    # word); sids = every sentence holding both units (empty = none).  Not part of the item key.
    edges: Tuple[Tuple[str, str, Tuple[int, ...]], ...] = ()

    @property
    def text(self) -> str:
        return "".join(self.words)


@dataclass(frozen=True)
class AnswerItem:
    centre: str
    paths: Tuple[AnswerPath, ...]
    stability: Fraction
    origins: Tuple[int, ...]                 # indexes into PathAnswer.states (all that read out the same)

    @property
    def key(self) -> Tuple[str, Tuple[Tuple[str, ...], ...]]:
        return (self.centre, tuple(p.words for p in self.paths))

    @property
    def path_texts(self) -> Tuple[str, ...]:
        return tuple(p.text for p in self.paths)

    @property
    def source_sids(self) -> Tuple[int, ...]:
        return tuple(sorted({sid for p in self.paths for _, _, ss in p.edges for sid in ss}))


def item_words(it: "AnswerItem") -> frozenset:
    """L-180: the word set of an item = the words of all its section paths together with the centre
    (order, section and path structure ignored)."""
    return frozenset(w for p in it.paths for w in p.words) | {it.centre}


@dataclass(frozen=True)
class AnswerEntry:
    """L-180: one entry of the list shown to the user.  With similar="word_set" it is the group of
    all items that use the SAME SET of words (they differ only in arrangement); it carries every
    arrangement (no representative is picked, so no order bias), the union of their origin states
    and sources, and the word set.  With similar=None it wraps exactly one item."""
    words: Tuple[str, ...]                   # the word set, sorted by code point (a label)
    arrangements: Tuple["AnswerItem", ...]   # in item-key order (a label)
    stability: Fraction                      # the best among the arrangements (information only)
    origins: Tuple[int, ...]                 # union of the arrangements' origin states, sorted

    @property
    def count(self) -> int:
        return len(self.arrangements)

    @property
    def centres(self) -> Tuple[str, ...]:
        return tuple(sorted({a.centre for a in self.arrangements}))

    @property
    def source_sids(self) -> Tuple[int, ...]:
        return tuple(sorted({sid for a in self.arrangements for sid in a.source_sids}))

    @property
    def text(self) -> str:
        return "\n".join(self.words)


def _make_entry(arr: Sequence["AnswerItem"]) -> AnswerEntry:
    ws = frozenset().union(*(item_words(a) for a in arr))
    return AnswerEntry(tuple(sorted(ws)), tuple(arr), max(a.stability for a in arr),
                       tuple(sorted({o for a in arr for o in a.origins})))


@dataclass(frozen=True)
class PathAnswer:
    question: str
    tier: str
    states: Tuple[StateRead, ...]            # every adopted state with its section paths (the thought)
    items: Tuple[AnswerItem, ...]
    verdict: str
    states_without_path: int
    too_many: bool
    too_many_limit: int
    # sid -> the tier's unit list of that sentence (display of the source sentences; L-160)
    _sentence_units: Mapping[int, Tuple[str, ...]] = field(default_factory=dict, compare=False, repr=False)
    # L-170: True when items that differ only by which section carries which path were merged
    merge_sections: bool = False
    # L-180: the list shown to the user (entries); similar = None | "word_set"
    entries: Tuple[AnswerEntry, ...] = ()
    similar: Optional[str] = None

    @property
    def centre(self) -> Optional[str]:
        if self.verdict != cy.ANSWER:
            return None
        cs = self.entries[0].centres
        return cs[0] if len(cs) == 1 else None

    # ---- output (N-10) ----
    def answer_obj(self) -> dict:
        def item(it: AnswerItem) -> dict:
            return {"centre": it.centre, "stability": _fs(it.stability), "origins": list(it.origins),
                    "source_sids": list(it.source_sids),
                    "paths": [{"section": p.section, "attached": p.attached, "words": list(p.words),
                               "edges": [{"from": a, "to": b, "sids": list(ss)} for a, b, ss in p.edges]}
                              for p in it.paths]}
        one = self.verdict == cy.ANSWER
        sentences = {str(i): "".join(u) for i, u in sorted(self._sentence_units.items())}
        if self.similar is not None:                 # L-180: the list is of entries (word sets)
            ents = [{"words": list(e.words), "count": e.count, "centres": list(e.centres),
                     "stability": _fs(e.stability), "origins": list(e.origins),
                     "source_sids": list(e.source_sids), "arrangements": [item(a) for a in e.arrangements]}
                    for e in self.entries]
            e0 = self.entries[0] if one else None
            o = {"form": "path_words", "verdict": self.verdict, "listed": len(self.entries),
                 "arrangements": len(self.items), "too_many": self.too_many, "similar": self.similar,
                 "merge_sections": self.merge_sections,
                 "answer": ({"path_words": list(e0.words), "arrangements": e0.count,
                             "source_sids": list(e0.source_sids), "reference_centre": self.centre,
                             "reference_centres": list(e0.centres)} if one else None),
                 "centre": self.centre,
                 "paths": ents[0]["arrangements"][0]["paths"] if one and e0.count == 1 else None,
                 "entries": ents, "sentences": sentences}
            return o
        items = [item(it) for it in self.items]
        o = {"form": "path_words", "verdict": self.verdict, "listed": len(self.items),
             "too_many": self.too_many,
             # L-160 (owner: "経路の語を答えとし、中心は参考として付ける"): the answer = the path words with the
             # sentences they trace to; the centre is attached as reference only.
             "answer": ({"path_words": [p.text for p in self.items[0].paths],
                         "source_sids": list(self.items[0].source_sids),
                         "reference_centre": self.items[0].centre} if one else None),
             "centre": self.items[0].centre if one else None,
             "paths": items[0]["paths"] if one else None,
             "items": items,
             "sentences": sentences}
        if self.merge_sections:                      # L-170: only when the option is on
            o["merge_sections"] = True
        return o

    def thought_obj(self) -> dict:
        return {
            "question": self.question, "tier": self.tier,
            "counts": {"states": len(self.states), "states_without_path": self.states_without_path,
                       "listed": len(self.entries) if self.entries else len(self.items)},
            "too_many_limit": self.too_many_limit,
            "states": [{"seed": st.ref.seed, "member": st.ref.member, "stability": _fs(st.ref.stability),
                        "state": list(st.ref.flat), "version": st.ref.version, "k": st.k,
                        "paths": [{"section": p.section, "attached": p.attached, "unit": p.unit,
                                   "words": list(p.words), "seats": list(p.seats),
                                   "segments": [list(g) for g in p.segments]} for p in st.paths]}
                       for st in self.states],
        }

    def to_json_obj(self) -> dict:
        return {"answer": self.answer_obj(), "thought": self.thought_obj()}

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json_obj(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def read_answer(facts: "cy.TierFacts", ctx: "cy.QueryContext", states: Sequence[StateRef], *,
                question: str = "", too_many: int = TOO_MANY_DEFAULT,
                window: int = DEFAULT_WINDOW, merge_sections: bool = True,
                similar: Optional[str] = "word_set") -> PathAnswer:
    """L-150..L-152: the agreed centre and the section-path words of every adopted state.
    L-170 `merge_sections=True` (owner: items that differ ONLY by which section reads which words are
    one item): the item key is (centre, the multiset of section paths = their word sequences); the
    first state in key order keeps its paths (trace / sources), all origin states are kept.
    L-180 (owner, T6z): `merge_sections=True` and `similar="word_set"` are the DEFAULTS; the old
    behaviour is `merge_sections=False, similar=None` (byte-identical to T6x).  `similar="word_set"`
    collapses items that use the same set of words (path words + centre) into one list entry that
    carries all its arrangements (no representative is chosen)."""
    reader = cy.Reader(facts, ctx.attached, ctx.energy_units, window)
    tier = states[0].tier if states else facts.tier.name
    reads = tuple(StateRead(s, section_paths(reader, s.flat, s.L)) for s in states)
    tier_space = facts.tier
    post = tier_space.postings
    memo: Dict[Tuple[str, str], Tuple[int, ...]] = {}

    def common(a: str, b: str) -> Tuple[int, ...]:
        k = (a, b) if a <= b else (b, a)
        r = memo.get(k)
        if r is None:
            r = memo[k] = tuple(sorted(set(post.get(a, ())) & set(post.get(b, ()))))
        return r

    def edges_of(flat: Flat, p: SectionPath) -> Tuple[Tuple[str, str, Tuple[int, ...]], ...]:
        seen: Dict[Tuple[str, str], Tuple[int, ...]] = {}
        for seg in p.segments:
            for j, seat in enumerate(seg):
                a = p.attached if j == 0 else flat[seg[j - 1]]
                if a is None:
                    continue
                seen.setdefault((a, flat[seat]), common(a, flat[seat]))
        return tuple((a, b, ss) for (a, b), ss in seen.items())

    acc: Dict[tuple, dict] = {}
    for si, sr in enumerate(reads):
        if not sr.paths:
            continue
        centre = sr.ref.unit if sr.ref.unit is not None else sr.paths[0].unit
        if any(p.unit != centre for p in sr.paths):                       # cannot happen for an agreed state
            raise AssertionError("sections of state %d do not agree on the centre %r" % (si, centre))
        key = (centre, tuple(p.words for p in sr.paths))
        if merge_sections:
            key = (centre, tuple(sorted(p.words for p in sr.paths)))
        e = acc.get(key)
        if e is None:
            e = acc[key] = {"paths": tuple(AnswerPath(p.section, p.attached, p.words, edges_of(sr.ref.flat, p))
                                           for p in sr.paths),
                            "stab": sr.ref.stability, "origins": []}
        elif sr.ref.stability > e["stab"]:
            e["stab"] = sr.ref.stability
        e["origins"].append(si)
    items = tuple(AnswerItem(k[0], e["paths"], e["stab"], tuple(e["origins"])) for k, e in sorted(acc.items()))
    if similar is None:
        entries = tuple(_make_entry((it,)) for it in items)
    elif similar == "word_set":
        grp: Dict[frozenset, List[AnswerItem]] = {}
        for it in items:
            grp.setdefault(item_words(it), []).append(it)
        entries = tuple(sorted((_make_entry(a) for a in grp.values()), key=lambda e: e.words))
    else:
        raise ValueError("similar: None | word_set")
    verdict = UNKNOWN_NO_PATH if not entries else (cy.ANSWER if len(entries) == 1 else cy.CHOICE)
    used = {sid for it in items for sid in it.source_sids}
    return PathAnswer(question, tier, reads, items, verdict, sum(1 for r in reads if not r.paths),
                      len(entries) > too_many, too_many,
                      {sid: tier_space.sentence_units[sid] for sid in sorted(used)}, merge_sections,
                      entries, similar)


def read_out(facts: "cy.TierFacts", ctx: "cy.QueryContext", states: Sequence[StateRef], *,
             form: str = "centre_paths", **kw) -> Union[PathAnswer, Readout]:
    """Read the adopted states out.  Default form (L-150): `PathAnswer`.  `form="sentences"` =
    the T6 sentence-candidate read-out (`Readout`; extra keywords: window, by_stability, too_many)."""
    if form == "sentences":
        return read_sentences(facts, ctx, states, **kw)
    if form != "centre_paths":
        raise ValueError("form: centre_paths | sentences")
    kw.pop("by_stability", None)
    return read_answer(facts, ctx, states, **kw)


def read_out_result(tier_space, tr: "cy.TierResult", facts: Optional["cy.TierFacts"] = None, *,
                    too_many: int = TOO_MANY_DEFAULT, form: str = "centre_paths",
                    by_stability: bool = True, **kw) -> Union[PathAnswer, Readout]:
    """Convenience: read out the adopted states of an in-memory cycle result."""
    facts = facts or cy.TierFacts(tier_space)
    return read_out(facts, tr.ctx, states_from_result(tr), question=tr.question, too_many=too_many,
                    form=form, by_stability=by_stability, **kw)


# --------------------------------------------------------------------------
# intake of the adopted answer (M-4 (a), N-20, L-127)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Adoption:
    question: str
    tier: str
    sentence: Sentence
    source: str                              # "auto" | "user_choice"
    listed: int                              # how many candidates were on offer
    too_many: bool
    choice_index: Optional[int]

    def memory_record(self) -> dict:
        """M-4 (a): the adopted answer as a memory sentence (design L-19 kind `memory_answer`).
        The base arrangement is not changed.  T11 writes it."""
        return {"kind": RECORD_KIND, "source": self.source, "tier": self.tier,
                "question": self.question, "answer": self.sentence.text,
                "words": list(self.sentence.words), "stability": _fs(self.sentence.stability),
                "origins": [[i, list(o)] for i, o in self.sentence.origins],
                "offered": self.listed, "too_many": self.too_many, "choice_index": self.choice_index,
                "base_changed": False}

    def to_bytes(self) -> bytes:
        return json.dumps(self.memory_record(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def adopt(readout: Readout) -> Adoption:
    """I-14: the single most stable candidate is adopted (automatically)."""
    if readout.verdict != cy.ANSWER:
        raise ValueError("nothing to adopt automatically: verdict %s" % readout.verdict)
    return Adoption(readout.question, readout.tier, readout.sentences[0], "auto", 1, False, None)


def choose(readout: Readout, which: Union[int, str]) -> Adoption:
    """N-20 / M-4 (a): take the user's choice (an index into the list, or the exact text of one
    listed sentence).  Anything not on the list is refused."""
    if readout.verdict not in (cy.CHOICE, cy.ANSWER):
        raise ValueError("no list to choose from: verdict %s" % readout.verdict)
    if isinstance(which, bool):
        raise TypeError("choice must be an index or a text")
    if isinstance(which, int):
        if not 0 <= which < len(readout.sentences):
            raise IndexError("choice %d outside the list of %d" % (which, len(readout.sentences)))
        i = which
    elif isinstance(which, str):
        found = [k for k, s in enumerate(readout.sentences) if s.text == which]
        if len(found) != 1:
            raise ValueError("text is not on the list")
        i = found[0]
    else:
        raise TypeError("choice must be an index or a text")
    return Adoption(readout.question, readout.tier, readout.sentences[i], "user_choice",
                    len(readout.sentences), readout.too_many, i)


# --------------------------------------------------------------------------
# intake for the default answer form (M-4 (a), N-20; L-154)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AnswerAdoption:
    question: str
    tier: str
    item: AnswerItem                         # similar=None: the item; word_set: the first arrangement (label only)
    source: str                              # "auto" | "user_choice"
    listed: int
    too_many: bool
    choice_index: Optional[int]
    entry: Optional[AnswerEntry] = None      # L-180: set when the list is of word-set entries

    def memory_record(self) -> dict:
        """L-154: the adopted answer item as a memory record (kind `memory_answer`, base unchanged).
        T11 writes it; here only the form.  L-180: for a word-set entry the record carries the word
        set and every arrangement (no representative)."""
        if self.entry is not None:
            e = self.entry
            return {"kind": RECORD_KIND, "source": self.source, "tier": self.tier, "question": self.question,
                    "form": "word_set", "words": list(e.words), "centres": list(e.centres),
                    "arrangements": [{"centre": a.centre,
                                      "paths": [{"section": p.section, "attached": p.attached, "words": list(p.words)}
                                                for p in a.paths]} for a in e.arrangements],
                    "stability": _fs(e.stability), "origins": list(e.origins),
                    "offered": self.listed, "too_many": self.too_many, "choice_index": self.choice_index,
                    "base_changed": False}
        return {"kind": RECORD_KIND, "source": self.source, "tier": self.tier, "question": self.question,
                "form": "centre_paths", "centre": self.item.centre,
                "paths": [{"section": p.section, "attached": p.attached, "words": list(p.words)}
                          for p in self.item.paths],
                "stability": _fs(self.item.stability), "origins": list(self.item.origins),
                "offered": self.listed, "too_many": self.too_many, "choice_index": self.choice_index,
                "base_changed": False}

    def to_bytes(self) -> bytes:
        return json.dumps(self.memory_record(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def _adoption(ans: PathAnswer, i: int, source: str, listed: int, choice: Optional[int]) -> AnswerAdoption:
    e = ans.entries[i]
    return AnswerAdoption(ans.question, ans.tier, e.arrangements[0], source, listed,
                          ans.too_many if source == "user_choice" else False, choice,
                          e if ans.similar is not None else None)


def adopt_item(ans: PathAnswer) -> AnswerAdoption:
    """The single entry is adopted (automatically)."""
    if ans.verdict != cy.ANSWER:
        raise ValueError("nothing to adopt automatically: verdict %s" % ans.verdict)
    return _adoption(ans, 0, "auto", 1, None)


def choose_item(ans: PathAnswer, which: int) -> AnswerAdoption:
    """The user's choice: an index into the list (of entries); anything else is refused."""
    if ans.verdict not in (cy.CHOICE, cy.ANSWER):
        raise ValueError("no list to choose from: verdict %s" % ans.verdict)
    if isinstance(which, bool) or not isinstance(which, int):
        raise TypeError("choice must be an index")
    if not 0 <= which < len(ans.entries):
        raise IndexError("choice %d outside the list of %d" % (which, len(ans.entries)))
    return _adoption(ans, which, "user_choice", len(ans.entries), which)
