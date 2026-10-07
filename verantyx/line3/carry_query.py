"""C5 of the line-3 "carry" build (docs/LINE3_CARRY_DESIGN.md 5, 6 P-4, 9 C5): question answering over the tower.

The input is a finished `carry.CarryTower` (built under either pack-overflow rule; only `units()`, `packs`, `carry`
and `tier` are used).  Nothing in carry.py, placement.py, cycle.py, readout.py, trace_check.py, ask.py is changed.

Binding: design 5.1 (entry: the newest units hold the compression of everything), 5.2 (coarse -> fine descent below the
packs of the SELECTED path only, C-5 "ショートカット"), 5.3 (candidates = path words of the level-0 blacks that were read;
entry shape = a T7b entry plus a chain mark), 5.4 (presets of T7b: fast 4 / standard 10 / full unbounded units, never
rebuild), 6 P-4 (every answer word traces to a source sentence by GLOBAL sid), conditions 1-2 (an inherited element is
named, never expanded; its sources are the new sentences of the black it sits in).  Owner: candidates are for real users
to grade; the 90-question score is not the goal.  Exact arithmetic only; no float; no order decides a tie.

Local choices (design numbers L-313..L-318 as designed; new ones from L-420; docs/LINE3_LOCAL_DECISIONS.md "C5"):
  L-313 exact skip: rq(U) = sum over the distinct question units q of the number of local sentences of U that hold a
        scope occurrence of q.  rq(U) = 0 -> U is not read (a read could only be UNKNOWN: no question unit is in its
        space, so no section works, N-03).  `read_unit` reads a unit without the skip so the claim is testable.
  L-314 read order = (level descending, rq descending); units with the same (level, rq) are ONE group, read together or
        not at all (never split).  All descents of a group are applied after the whole group was read, so the order
        inside a group cannot matter.
  L-315 presets are `ask.EFFORTS` (4 / 10 / unbounded units), QueryBudget(64, 8), no rebuild (a closed unit is never
        rebuilt: that would change the later closing points and every copy).
  L-316 default descent = the packs on the paths of the ADOPTED states of the unit read (a unit with no adopted state
        does not descend); `fallback="index"` = every pack seated in the unit read (rq > 0 children), flag for comparison.
  L-317 candidates come from read level-0 blacks only; the path of an upper unit goes to `thought`.
  L-318 an entry's sources are the scope sentences of its black (global sids); an inherited element is named with
        {"inherited": true, "pack", "unit"} and not expanded into words.
  L-420 question units Q = the question cut like the tier (`cycle.split_question`) with the V2 filter, or the `units`
        given; distinct; the entrance set = the OPEN units of every level.
  L-421 read tier (`ReadTier`, a TierSpace over the unit's LOCAL sentences): postings of the seated elements; a question
        unit that is not an element (always the case above level 0: the elements are packs) gets postings from the scope
        occurrences of that unit, so the cycle can attach it (I-07) and N-03 sees it; an element that no scope
        occurrence touches (n = 0) is left out (L-52: outside the space).  `sids` maps local -> global sid.
  L-422 a unit's class (`Black.state`) is given to the cycle as a `Placement` (members = the whole tied class, L, no twin
        quotient L-303); the read is `cycle._ask_tier_once(plan_override=...)` with the T7b defaults (V1 plan given, V3
        state rule, first-layer scope), `observe=False`; `member_cap` is optional (None = every member).
  L-423 several parents: a unit reached from more than one read unit keeps ALL parent links (parent, pack, lateral), so
        its chain mark does not depend on which parent was read first.  The chain mark of a black is NOT a list of
        paths (their number is exponential: a first run of the index descent wrote 5.6 GB) but the backward closure of
        its links: `entrances` (the entrance units it is reached from, or is) and `links` (parent unit, pack, unit,
        lateral), every link on any way from an entrance to it; `lateral` of a link = the pack is inherited (woken) in
        the parent unit.  A way [U1:0 -> P1:1 -> U0:1] is read off the links.
  L-424 entry merge across blacks: same (set of own words, set of inherited pack ids) = one entry (T6y/T6z word-set
        rule, conservative about inherited packs); arrangements are summed, centres and sources united, stability = the
        best, origins (one per black) kept, each with its chain mark, global source sids and per-word sources.
  L-425 verdict: one entry ANSWER, several CHOICE; no entry: UNKNOWN_NO_EVIDENCE if no question unit occurs in any
        entrance scope (the exact skip left nothing to read), else UNKNOWN_NO_STATE (no read unit adopted a state) or
        UNKNOWN_NO_PATH (states adopted, no entry).  `partial` marks a read that stopped on the budget.
  L-426 read counts follow L-222: crosses_read (units), left_unread (queued units that the budget did not allow),
        would_read_in_full = the INDEX count of units with rq > 0 in the whole tower (an upper bound of what the full
        descent reads), plus `tied_group_not_split`, reads per level, exact skips.
  L-427 P-4 trace (`trace`): independent of the read-out; every entry word has a scope occurrence in its black, every
        source sid is a scope sentence of that black (and, with the tier space, holds the word); every chain link is a
        real pack of the tower seated in the unit it leaves; every inherited element is in the copy of the black; plus
        `trace_check.trace_answer` on each read tier (seats / edges, local sids).
  L-428 `memory_record(i)` = the T7b record shape for the user's choice plus `chain`; the base is not changed.
  L-429 the output bytes contain no wall time (`ms` is an attribute).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from verantyx.line3 import ask as A
from verantyx.line3 import cycle as cy
from verantyx.line3 import placement as pl
from verantyx.line3 import readout as ro
from verantyx.line3 import trace_check as tc
from verantyx.line3.carry import ORIGIN_INHERITED, ORIGIN_NEW, STATUS_OPEN, Black, CarryTower
from verantyx.line3.space import TierSpace

ANSWER, CHOICE = cy.ANSWER, cy.CHOICE
UNKNOWN_NO_STATE, UNKNOWN_NO_PATH = A.UNKNOWN_NO_STATE, ro.UNKNOWN_NO_PATH
UNKNOWN_NO_EVIDENCE = cy.UNKNOWN_NO_EVIDENCE
DEFAULT_BUDGET = A.DEFAULT_BUDGET                          # L-315: QueryBudget(64, 8)
FALLBACKS = (None, "index")


def _unit_key(u: str) -> Tuple[int, int]:
    """A label order for a unit id "U{k}:{j}" (L-301); it never decides a winner."""
    a, b = u[1:].split(":")
    return int(a), int(b)


def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# --------------------------------------------------------------------------
# question units (L-420)
# --------------------------------------------------------------------------
def question_units(tier: str, question: str, units: Optional[Sequence[str]] = None) -> Tuple[str, ...]:   # L-420
    """Q = the question cut like the tier with the V2 function-word filter (the T7b default), or `units` as given."""
    if units is not None:
        q = tuple(units)
    else:
        q = cy.split_question(tier, question)
        from verantyx.line3.funcwords import default_filter
        flt = default_filter(tier)
        if flt is not None:
            q = tuple(u for u in q if not flt(u))
    return tuple(dict.fromkeys(q))


def rq(black: Black, q: Iterable[str]) -> int:   # L-313 (index lookup, not a count of evidence)
    """L-313: sum over the distinct question units of the local sentences with a scope occurrence of that unit."""
    wf = black.space.word_first
    return sum(len(wf.get(u, ())) for u in sorted(set(q)))


# --------------------------------------------------------------------------
# read tier and placement adapter (L-421, L-422)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ReadTier(TierSpace):
    """TierSpace over one unit's local sentences, for the cycle / read-out / trace unchanged."""
    sids: Tuple[int, ...] = field(default=(), compare=False)          # local sentence index -> global sid


def read_tier(tier_name: str, black: Black, q: Iterable[str]) -> ReadTier:   # L-421
    sp = black.space
    post: Dict[str, Tuple[int, ...]] = {}
    for e in sp.elements:
        f = sp.first_pos[e.id]
        if f:                                                         # n = 0: outside the space (L-52)
            post[e.id] = tuple(sorted(f))
    extra: Dict[str, Mapping[int, int]] = {}
    for u in sorted(set(q)):
        if u in sp.first_pos:
            continue                                                  # an element: its own postings
        wf = sp.word_first.get(u)
        if wf:
            post[u] = tuple(sorted(wf))
            extra[u] = wf
    su = []
    for li in range(sp.N):
        rows = [(f[li], eid) for eid, f in sp.first_pos.items() if li in f]
        rows += [(wf[li], u) for u, wf in extra.items() if li in wf]
        su.append(tuple(i for _, i in sorted(rows)))                  # (position, id): a listing, no count uses it
    return ReadTier(tier_name, tuple(su), post, None, sp.sids)


class _UnitStore:   # L-422
    """cross_for(seed) of one unit: its tied class as a Placement (L-422)."""

    def __init__(self, black: Black) -> None:
        st = black.state
        cs = tuple(sorted({f[0] for f in st if f[0] is not None}))
        self._p = pl.Placement(black.unit, pl.to_cross(st[0], black.L), st, black.L, cs, len(black.space.elements),
                               len(black.space.elements), pl.ZERO2, "budget", None, (), 0, black.budget, (), False)

    def cross_for(self, seed: str) -> pl.Placement:
        return self._p


# --------------------------------------------------------------------------
# one unit read
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class UnitRead:
    unit: str
    level: int
    status: str
    rq: int
    result: cy.TierResult
    answer: Optional[ro.PathAnswer]            # None when no state was adopted
    tier: ReadTier = field(compare=False, repr=False)
    ms: int = 0

    @property
    def states(self) -> int:
        return len(self.result.candidates)

    @property
    def verdict(self) -> str:
        return self.answer.verdict if self.answer is not None else self.result.verdict

    def path_elements(self) -> Tuple[str, ...]:
        """Every element on the section paths (centre included) of the adopted states."""
        if self.answer is None:
            return ()
        return tuple(sorted({w for st in self.answer.states for p in st.paths for w in p.words}))


def read_unit(tower: CarryTower, unit: str, q: Sequence[str], *, budget: cy.QueryBudget = DEFAULT_BUDGET,
              member_cap: Optional[int] = None, _idx=None) -> UnitRead:
    """Read one unit under the question WITHOUT the exact skip (L-313 is tested against this)."""
    black, status = (_idx or _index(tower))[unit]
    t0 = time.monotonic_ns()
    q = tuple(dict.fromkeys(q))
    rt = read_tier(tower.tier, black, q)
    facts = cy.TierFacts(rt)
    plan = cy.ReadPlan((("unit", (unit,)),), (unit,), (), 1, None, False, 0, None, 0, 1)
    res = cy._ask_tier_once(rt, "", _UnitStore(black), units=q, facts=facts, budget=budget, unit_filter=None,
                            plan_override=plan, member_cap=member_cap, observe=False)
    ans = ro.read_out_result(rt, res, facts) if res.candidates else None
    return UnitRead(unit, black.level, status, rq(black, q), res, ans, rt, (time.monotonic_ns() - t0) // 1000000)


def _index(tower: CarryTower) -> Dict[str, Tuple[Black, str]]:
    return {b.unit: (b, st) for b, st in tower.units()}


# --------------------------------------------------------------------------
# entries (L-424) and the answer object
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Origin:
    """One black an entry was read from."""
    unit: str
    entrances: Tuple[str, ...]                              # L-423: entrance units it is reached from (or is), sorted
    links: Tuple[Tuple[str, str, str, bool], ...]           # L-423: (parent unit, pack, unit, lateral), backward closure, sorted
    source_sids: Tuple[int, ...]                            # global
    word_sources: Tuple[Tuple[str, Tuple[int, ...]], ...]   # word -> global sids of the steps into / out of it
    arrangements: int
    stability: Fraction


@dataclass(frozen=True)
class Entry:
    tier: str
    words: Tuple[str, ...]                                  # own words (a pack is never expanded)
    inherited: Tuple[Tuple[str, str, bool], ...]            # (pack, unit of the pack, is_centre)
    arrangements: int
    centres: Tuple[str, ...]
    stability: Fraction
    source_sids: Tuple[int, ...]
    origins: Tuple[Origin, ...]

    @property
    def key(self) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        return (self.words, tuple(p for p, _, _ in self.inherited))

    def to_obj(self) -> dict:
        return {"tier": self.tier, "words": list(self.words), "arrangements": self.arrangements,
                "centres": list(self.centres), "stability": _fs(self.stability), "source_sids": list(self.source_sids),
                "tier_is_most_stable": True,                    # one tower = one tier: trivially the most stable
                "inherited": [{"inherited": True, "pack": p, "unit": u, "is_centre": c} for p, u, c in self.inherited],
                "chain": [{"unit": o.unit, "entrances": list(o.entrances), "lateral": any(k[3] for k in o.links),
                           "links": [{"from": a, "pack": k, "to": b, "lateral": lat} for a, k, b, lat in o.links],
                           "source_sids": list(o.source_sids), "arrangements": o.arrangements,
                           "stability": _fs(o.stability),
                           "word_sources": {w: list(s) for w, s in o.word_sources}} for o in self.origins]}


@dataclass(frozen=True)
class CarryAnswer:
    question: str
    tier: str
    query: Tuple[str, ...]
    verdict: str
    entries: Tuple[Entry, ...]
    reads: Tuple[UnitRead, ...]                              # in the order the groups were read
    entrance: Tuple[Tuple[str, int, int], ...]               # (unit, level, rq) of every open unit
    skipped: Tuple[Tuple[str, int, Tuple[Tuple[str, str, bool], ...]], ...]   # exact skips: (unit, level, parent links)
    parents: Mapping[str, Tuple[Tuple[str, str, bool], ...]]
    queue_left: Tuple[Tuple[str, int, int], ...]             # (unit, level, rq) queued, not read
    index_positive: int                                      # units with rq > 0 in the whole tower (index count)
    tied_group_not_split: int
    effort: Optional[str]
    node_budget: Optional[int]
    fallback: Optional[str]
    member_cap: Optional[int]
    ms: int = 0
    sentences: Mapping[int, Tuple[str, ...]] = field(default_factory=dict, compare=False, repr=False)

    @property
    def partial(self) -> bool:
        return bool(self.queue_left)

    def read_obj(self) -> dict:
        by_level: Dict[int, int] = {}
        for r in self.reads:
            by_level[r.level] = by_level.get(r.level, 0) + 1
        return {"effort": self.effort, "node_budget": self.node_budget, "rebuild_levels": [], "partial": self.partial,
                "per_tier": {self.tier: {"crosses_read": len(self.reads), "left_unread": len(self.queue_left),
                                         "would_read_in_full": self.index_positive}},
                "rebuild_skipped": {}, "tied_group_not_split": self.tied_group_not_split,
                "reads_per_level": {str(k): v for k, v in sorted(by_level.items())},
                "exact_skips": len(self.skipped), "fallback": self.fallback}

    def answer_obj(self) -> dict:
        one = self.verdict == ANSWER
        ents = [e.to_obj() for e in self.entries]
        o = {"verdict": self.verdict, "view": "all", "tiers": [self.tier] if self.entries else [],
             "listed": len(ents), "per_tier_listed": {self.tier: len(ents)}, "read": self.read_obj(),
             "answer": ({"tier": self.tier, "path_words": ents[0]["words"], "source_sids": ents[0]["source_sids"],
                         "reference_centres": ents[0]["centres"], "chain": ents[0]["chain"]} if one else None),
             "entries": ents}
        if self.sentences:
            o["sources"] = [{"sid": s, "units": list(u)} for s, u in sorted(self.sentences.items())]
        return o

    def thought_obj(self) -> dict:
        reads = []
        for r in self.reads:
            reads.append({"unit": r.unit, "level": r.level, "status": r.status, "rq": r.rq, "verdict": r.verdict,
                          "states": r.states, "listed": len(r.answer.entries) if r.answer is not None else 0,
                          "members_read": r.result.members_read, "members_total": r.result.members_total,
                          "path_elements": list(r.path_elements()),
                          "parents": [{"unit": p, "pack": k, "lateral": lat} for p, k, lat in self.parents.get(r.unit, ())]})
        return {"question": self.question, "tier": self.tier, "query": list(self.query),
                "rule": "C5: entrance = the open units; coarse -> fine below the packs of the selected path; exact skip rq = 0",
                "fallback": self.fallback, "member_cap": self.member_cap,
                "entrance": [{"unit": u, "level": lv, "rq": n} for u, lv, n in self.entrance],
                "reads": reads,
                "exact_skips": [{"unit": u, "level": lv, "parents": [{"unit": p, "pack": k, "lateral": lat}
                                                                       for p, k, lat in ps]} for u, lv, ps in self.skipped],
                "queue_left": [{"unit": u, "level": lv, "rq": n} for u, lv, n in self.queue_left],
                "read": self.read_obj()}

    def to_json_obj(self) -> dict:
        return {"answer": self.answer_obj(), "thought": self.thought_obj()}

    def to_bytes(self) -> bytes:                                  # L-429: no wall time
        return _canon(self.to_json_obj())

    def memory_record(self, which: Optional[int] = None) -> dict:  # L-428
        if which is None:
            if self.verdict != ANSWER:
                raise ValueError("nothing to adopt automatically: verdict %s" % self.verdict)
            which, source = 0, "auto"
        else:
            if isinstance(which, bool) or not isinstance(which, int):
                raise TypeError("choice must be an index")
            if not 0 <= which < len(self.entries):
                raise IndexError("choice %d outside the list of %d" % (which, len(self.entries)))
            source = "user_choice"
        e = self.entries[which]
        o = e.to_obj()
        return {"kind": ro.RECORD_KIND, "source": source, "tier": self.tier, "question": self.question,
                "form": "word_set", "words": o["words"], "centres": o["centres"], "inherited": o["inherited"],
                "stability": o["stability"], "offered": len(self.entries),
                "too_many": len(self.entries) > ro.TOO_MANY_DEFAULT,
                "choice_index": which if source == "user_choice" else None, "base_changed": False,
                "view": "all", "effort": self.effort, "node_budget": self.node_budget, "partial_read": self.partial,
                "crosses": self.read_obj()["per_tier"][self.tier], "chain": o["chain"]}


# --------------------------------------------------------------------------
# the question
# --------------------------------------------------------------------------
def _links(parents: Mapping[str, Set[Tuple[str, str, bool]]], entrance: Set[str],
           u: str) -> Tuple[Tuple[str, ...], Tuple[Tuple[str, str, str, bool], ...]]:
    """L-423: the backward closure of the parent links of `u` (polynomial in the number of units) and the entrance
    units among {u} and the parents reached."""
    seen: Set[str] = set()
    todo = [u]
    links: Set[Tuple[str, str, str, bool]] = set()
    while todo:
        x = todo.pop()
        if x in seen:
            continue
        seen.add(x)
        for p, k, lat in parents.get(x, ()):
            links.add((p, k, x, lat))
            todo.append(p)
    return tuple(sorted(x for x in seen if x in entrance)), tuple(sorted(links))


def ask(tower: CarryTower, question: str = "", *, units: Optional[Sequence[str]] = None,
        effort: Optional[str] = None, nodes: Optional[int] = None, budget: cy.QueryBudget = DEFAULT_BUDGET,
        fallback: Optional[str] = None, member_cap: Optional[int] = None,
        tier_space: Optional[TierSpace] = None) -> CarryAnswer:
    """Design 5.1 - 5.4.  `effort` fast | standard | full or `nodes` N (units read, any level) as in T7b; neither = the
    whole descent.  `tier_space` (optional) only adds the source sentences to the output."""
    if fallback not in FALLBACKS:
        raise ValueError("fallback: None | 'index'")
    name, cap, _ = A.resolve_effort(effort, nodes)          # L-315: T7b presets 4 / 10 / unbounded, never a rebuild
    t0 = time.monotonic_ns()
    idx = _index(tower)
    q = question_units(tower.tier, question, units)
    qs = set(q)
    rqs = {u: rq(b, qs) for u, (b, _) in idx.items()}
    entrance_ids = sorted((u for u, (_, st) in idx.items() if st == STATUS_OPEN), key=_unit_key, reverse=True)
    entrance = tuple((u, idx[u][0].level, rqs[u]) for u in entrance_ids)
    index_positive = sum(1 for v in rqs.values() if v > 0)
    parents: Dict[str, Set[Tuple[str, str, bool]]] = {}
    skipped: Dict[str, int] = {}
    queue: Dict[str, int] = {u: rqs[u] for u in entrance_ids if rqs[u] > 0}
    for u in entrance_ids:
        if rqs[u] == 0:
            skipped[u] = idx[u][0].level                        # L-313
    reads: Dict[str, UnitRead] = {}
    order: List[UnitRead] = []
    tied = 0
    while queue:
        key = min((-idx[u][0].level, -v) for u, v in queue.items())            # L-314: the head group (a priority, not a tie-break)
        group = sorted((u for u, v in queue.items() if (-idx[u][0].level, -v) == key), key=_unit_key)
        if cap is not None and len(reads) + len(group) > cap:   # L-314/L-426: the group is not split; stop, counted below
            tied = len(group)
            break
        done = [read_unit(tower, u, q, budget=budget, member_cap=member_cap, _idx=idx) for u in group]
        for ur in done:
            reads[ur.unit] = ur
            order.append(ur)
            del queue[ur.unit]
        adds: List[Tuple[str, str, str, bool]] = []
        for ur in done:
            b = idx[ur.unit][0]
            els = {e.id: e for e in b.space.elements}
            if fallback == "index":                              # L-316: comparison flag
                xs = sorted(e for e in els if els[e].kind == "pack")
            else:                                                # C-5 / L-316: only below the packs of the SELECTED path
                xs = [x for x in ur.path_elements() if els[x].kind == "pack"]
            for x in xs:
                adds.append((tower.packs[x].unit, ur.unit, x, els[x].origin == ORIGIN_INHERITED))
        for child, parent, pack, lat in sorted(adds):           # canonical; the order of the group cannot matter
            parents.setdefault(child, set()).add((parent, pack, lat))      # L-423: every link is kept
            if child in reads or child in queue:
                continue
            if rqs[child] == 0:
                skipped[child] = idx[child][0].level            # L-313
                continue
            queue[child] = rqs[child]
    ent_set = set(entrance_ids)
    entries = _entries(tower, idx, order, parents, ent_set)          # L-424
    left = tuple((u, idx[u][0].level, v) for u, v in sorted(queue.items(), key=lambda kv: _unit_key(kv[0])))
    if len(entries) == 1:                                        # L-425
        verdict = ANSWER
    elif entries:
        verdict = CHOICE
    elif all(rqs[u] == 0 for u in entrance_ids):
        verdict = UNKNOWN_NO_EVIDENCE
    elif any(r.states for r in order):
        verdict = UNKNOWN_NO_PATH
    else:
        verdict = UNKNOWN_NO_STATE
    sk = tuple((u, lv, tuple(sorted(parents.get(u, ())))) for u, lv in sorted(skipped.items(), key=lambda kv: _unit_key(kv[0])))
    sents: Dict[int, Tuple[str, ...]] = {}
    if tier_space is not None:
        for e in entries:
            for s in e.source_sids:
                sents[s] = tier_space.sentence_units[s]
    return CarryAnswer(question, tower.tier, q, verdict, entries, tuple(order), entrance, sk,
                       {u: tuple(sorted(v)) for u, v in sorted(parents.items(), key=lambda kv: _unit_key(kv[0]))},
                       left, index_positive, tied, name, cap, fallback, member_cap,
                       (time.monotonic_ns() - t0) // 1000000, sents)


def _entries(tower: CarryTower, idx, order: Sequence[UnitRead], parents, entrance: Set[str]) -> Tuple[Entry, ...]:
    acc: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], dict] = {}
    for ur in order:
        if ur.level != 0 or ur.answer is None:                   # L-317
            continue
        b = idx[ur.unit][0]
        els = {e.id: e for e in b.space.elements}
        gl = ur.tier.sids
        ent, lnk = _links(parents, entrance, ur.unit)
        for e in ur.answer.entries:
            wd = tuple(w for w in e.words if els[w].kind == "word")
            pk = tuple(w for w in e.words if els[w].kind == "pack")
            centres = tuple(c for c in e.centres if els[c].kind == "word")
            pcent = {c for c in e.centres if els[c].kind == "pack"}
            ws = tuple((w, tuple(sorted({gl[i] for i in ro.entry_word_sources(e, w)}))) for w in wd)
            ps = tuple((w, tuple(sorted({gl[i] for i in ro.entry_word_sources(e, w)}))) for w in pk)
            org = Origin(ur.unit, ent, lnk, tuple(sorted({gl[i] for i in e.source_sids})), ws + ps, e.count, e.stability)
            k = (wd, pk)
            a = acc.setdefault(k, {"inh": {}, "arr": 0, "cen": set(), "stab": e.stability, "org": []})
            for p in pk:
                a["inh"][p] = (tower.packs[p].unit, a["inh"].get(p, ("", False))[1] or p in pcent)
            a["arr"] += e.count
            a["cen"].update(centres)
            a["stab"] = max(a["stab"], e.stability)
            a["org"].append(org)
    out = []
    for (wd, pk), a in sorted(acc.items()):
        orgs = tuple(sorted(a["org"], key=lambda o: _unit_key(o.unit)))
        out.append(Entry(tower.tier, wd, tuple((p, a["inh"][p][0], a["inh"][p][1]) for p in pk), a["arr"],
                         tuple(sorted(a["cen"])), a["stab"], tuple(sorted({s for o in orgs for s in o.source_sids})),
                         orgs))
    return tuple(out)


# --------------------------------------------------------------------------
# P-4: every answer word traces to its source sentences (global sids)  (L-427)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CarryTrace:
    words_checked: int
    words_traced: int
    local_ok: int                      # read tiers whose `trace_check.trace_answer` report is ok
    local_checked: int
    failures: Tuple[str, ...]

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.words_traced, self.words_checked) if self.words_checked else Fraction(1)

    @property
    def ok(self) -> bool:
        return self.fraction == 1 and self.local_ok == self.local_checked and not self.failures


def trace(tower: CarryTower, ans: CarryAnswer, tier_space: Optional[TierSpace] = None) -> CarryTrace:
    """Independent of the read-out (it uses the tower's scopes, packs and copies, and `trace_check` on the read tiers)."""
    idx = _index(tower)
    fails: List[str] = []
    checked = traced = 0
    entrance = {u for u, _, _ in ans.entrance}
    for ei, e in enumerate(ans.entries):
        covered_w: Set[str] = set()
        covered_p: Set[str] = set()
        for o in e.origins:
            if o.unit not in idx or idx[o.unit][0].level != 0:
                fails.append("entry %d: origin %r is not a level-0 unit of the tower" % (ei, o.unit))
                continue
            b = idx[o.unit][0]
            scope_sids = set(b.space.sids)
            occ = {(x.sid, x.unit) for x in b.space.scope}
            els = {x.id: x for x in b.space.elements}
            reach = {o.unit} | {l[0] for l in o.links}                       # the chain mark is real (L-423)
            if not o.entrances or not set(o.entrances) <= entrance or not (set(o.entrances) <= reach):
                fails.append("entry %d %s: the chain does not start at an entrance unit" % (ei, o.unit))
            for up, k, dn, lat in o.links:
                pk = tower.packs.get(k)
                ue = {x.id: x for x in idx[up][0].space.elements} if up in idx else {}
                if pk is None or pk.unit != dn or k not in ue or ue[k].kind != "pack" or dn not in idx:
                    fails.append("entry %d: chain link %s -> %s -> %s is not a pack seated in %s" % (ei, up, k, dn, up))
                elif (ue[k].origin == ORIGIN_INHERITED) != lat:
                    fails.append("entry %d %s: link %s -> %s -> %s has a wrong lateral mark" % (ei, o.unit, up, k, dn))
            if any(l[0] not in entrance and not any(m[2] == l[0] for m in o.links) for l in o.links):
                fails.append("entry %d %s: a chain link starts at a unit that is not reached" % (ei, o.unit))
            if o.links and not any(l[2] == o.unit for l in o.links) and o.unit not in entrance:
                fails.append("entry %d %s: no link ends at the unit" % (ei, o.unit))
            for w, sids in o.word_sources:
                x = els.get(w)
                if x is None:
                    fails.append("entry %d %s: %r is not seated in the unit" % (ei, o.unit, w))
                    continue
                if x.kind == "word":
                    checked += 1
                    good = x.origin == ORIGIN_NEW and any((s, w) in occ for s in scope_sids)
                    good = good and all(s in scope_sids and (s, w) in occ for s in sids)
                    if tier_space is not None:
                        good = good and all(w in tier_space.sentence_units[s] for s in sids)
                        good = good and all(any(oc.sid == s and oc.unit == w for oc in b.space.scope) for s in sids)
                    if good:
                        traced += 1
                        covered_w.add(w)
                    else:
                        fails.append("entry %d %s: word %r does not trace to a scope sentence" % (ei, o.unit, w))
                else:                                                       # an inherited pack (conditions 1-2)
                    good = (x.origin == ORIGIN_INHERITED and w in {p.id for p in tower.carry.get(o.unit, ())}
                            and all(s in scope_sids for s in sids))
                    if good:
                        covered_p.add(w)
                    else:
                        fails.append("entry %d %s: inherited %r is not in the copy / sources outside the scope" % (ei, o.unit, w))
            if not set(o.source_sids) <= scope_sids:
                fails.append("entry %d %s: a source sid is outside the black's scope" % (ei, o.unit))
        if covered_w != set(e.words) or covered_p != {p for p, _, _ in e.inherited}:
            fails.append("entry %d: the words are not exactly the union of its origins' words" % ei)
        for p, u, _ in e.inherited:
            if tower.packs[p].unit != u:
                fails.append("entry %d: inherited %s names the wrong unit %s" % (ei, p, u))
    lok = lchk = 0
    for r in ans.reads:
        if r.level == 0 and r.answer is not None:
            lchk += 1
            _, rep = tc.trace_answer(r.tier, r.answer)
            if rep.ok:
                lok += 1
            else:
                fails.append("read tier %s: trace_check failed (%s)" % (r.unit, "; ".join(rep.failures[:3])))
    return CarryTrace(checked, traced, lok, lchk, tuple(fails))
