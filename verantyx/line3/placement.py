"""T4 placement: the deliberately built stable initial arrangement + energy log.

Binding decisions (ops/decisions/2026-10-06_line3_faithful_build.md):
  decision 8 + I-04  placement = the arrangement where the space's energy is stable,
        measured first by the sentences shared by neighbouring units, then by word
        order.  Key (lexicographic, larger is better; the design's key is its negation):
          (1) sum over cross edges of n(x,y)
          (2) sum over cross edges, outer -> inner, of p(x,y)
  N-02 + M-1(a)  the stable initial arrangement is built deliberately by SEARCHING with
        that stability definition; from it each query's energy changes are logged
        (energy_log).
  M-1(b)  units are added to a cross in order of how many sentences they share with the
        centre; units with equal shares are added together.
  I-05  a state is a fixed point when no single move (24 rotations + seat swaps)
        improves it.  verify_fixed_point() checks this against ALL single moves with
        code independent of the search.
  I-02  no centre is chosen at ingestion: every unit is a seed; the centre of the final
        arrangement is whatever the search leaves in the centre seat.
  N-09/N-05  capacity is decided only by stability: when adding a group breaks
        stability, the state that was stable just before is restored and its size is the
        cross's capacity (recorded: Placement.capacity / stop / broke_on).
  design 0.2 rule 4  ties are never broken by order: ties are explored in full and a
        tied result is typed (TIED / PLATEAU / BUDGET), never resolved.

Local decisions (docs/LINE3_LOCAL_DECISIONS.md, L-60 ..):
  L-60 pool = the units admitted to the cross; moves are the 23 non-identity rotations
       and the swap of any two seats (empty seats included, geometry.moves_swap).  No
       replacement by units outside the cross.
  L-61 State identity for ties = (centre, multiset of legs) (legs read outer -> inner,
       empty seats kept): the key cannot see which leg is which (every permutation of
       the 6 legs has the same key), so such states are one state.  Rotations only
       change orientation (the key is rotation-invariant).  The concrete Cross places
       the legs in canonical sorted order (a label, not a winner) with identity
       orientation.  Which of the leg permutations to use is NOT decided here.
  L-62 Status of a search result: STABLE = exactly one terminal state and no single move
       gives a different state of equal key; TIED = several terminals; PLATEAU = one
       terminal but a different state of equal key is one move away; BUDGET = more
       branches than the budget.  Only STABLE lets a cross grow.
  L-63 Growth: seed alone at the centre (L=1) is stable by definition (no pair exists).
       Candidates = units v != seed with n(seed,v) > 0, grouped by n(seed,v) descending.
       The anchor of the order is the SEED (fixed), not the current centre.
  L-64 A group is inserted simultaneously and order-free: at every step all
       (member, empty seat) pairs are scored, the best gain wins, ties branch.  Then the
       result is searched to a fixed point with all tied best improving moves branched.
  L-65 L is the minimal leg length with 6L+1 >= units; growing L prepends an empty
       outer seat to every leg (edges unchanged, empty seats toward the outer end,
       design L-09).
  L-66 Budget (design L-05): at most 8 distinct tied branches at one tie point and 64
       distinct states per growth step; beyond that BUDGET (typed, counts recorded).
  L-67 Energy log record per placed unit: r0, E_Q, E_Q/r0 (None if r0 = 0), seat order
       centre, AXES order, k ascending; plus the three-ratio verdict.
Everything is exact (int / Fraction), deterministic, and hash-seed independent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import energy as en
from verantyx.line3.geometry import (
    AXES, CENTER, N_ARMS, Cross, Seat, moves_rotate, moves_swap, rotate, seats, swap,
)
from verantyx.line3.space import TierSpace

STABLE = "stable"
TIED = "tied"
PLATEAU = "plateau"
BUDGET = "budget"

MAX_TIED_BRANCHES = 8      # L-66
MAX_STATES = 64            # L-66

Score = Tuple[int, int]
Flat = Tuple[Optional[str], ...]     # [centre, arm0 k=0..L-1, arm1 ..., ...]
ZERO2: Score = (0, 0)


# --------------------------------------------------------------------------
# layouts
# --------------------------------------------------------------------------
class _Layout:
    def __init__(self, L: int) -> None:
        self.L = L
        self.n = 6 * L + 1
        edges: List[Tuple[int, int]] = []
        for a in range(N_ARMS):
            for k in range(L - 1):
                edges.append((1 + a * L + k, 1 + a * L + k + 1))
            edges.append((1 + a * L + L - 1, 0))
        self.edges = tuple(edges)
        inc: List[List[int]] = [[] for _ in range(self.n)]
        for ei, (o, i) in enumerate(self.edges):
            inc[o].append(ei)
            inc[i].append(ei)
        self.inc = tuple(tuple(x) for x in inc)


_LAYOUTS: Dict[int, _Layout] = {}


def _layout(L: int) -> _Layout:
    if L not in _LAYOUTS:
        _LAYOUTS[L] = _Layout(L)
    return _LAYOUTS[L]


def min_L(count: int) -> int:
    """L-65: smallest L with 6L+1 >= count."""
    L = 1
    while 6 * L + 1 < count:
        L += 1
    return L


def _leg_key(leg: Sequence[Optional[str]]) -> Tuple[str, ...]:
    return tuple("" if c is None else c for c in leg)


def canon(flat: Flat, L: int) -> Flat:
    """L-61: legs in canonical sorted order (label only)."""
    legs = sorted((flat[1 + a * L: 1 + (a + 1) * L] for a in range(N_ARMS)), key=_leg_key)
    out: List[Optional[str]] = [flat[0]]
    for g in legs:
        out.extend(g)
    return tuple(out)


def extend(flat: Flat, L: int, L2: int) -> Flat:
    """L-65: prepend empty outer seats to every leg."""
    pad = (None,) * (L2 - L)
    out: List[Optional[str]] = [flat[0]]
    for a in range(N_ARMS):
        out.extend(pad + tuple(flat[1 + a * L: 1 + (a + 1) * L]))
    return canon(tuple(out), L2)


def to_cross(flat: Flat, L: int) -> Cross:
    return Cross.make(L=L, center=flat[0],
                      arms=[flat[1 + a * L: 1 + (a + 1) * L] for a in range(N_ARMS)])


def from_cross(cross: Cross) -> Flat:
    out: List[Optional[str]] = [None if cross.center is None else str(cross.center)]
    for a in cross.arms:
        out.extend(None if c is None else str(c) for c in a)
    return tuple(out)


# --------------------------------------------------------------------------
# I-04 key
# --------------------------------------------------------------------------
class Weights:
    """Edge weight (n(x,y), p(x,y)) for outer x, inner y; cached per tier (pure cache)."""

    def __init__(self, tier: TierSpace) -> None:
        self.tier = tier
        self._c: Dict[Tuple[str, str], Score] = {}

    def __call__(self, x: Optional[str], y: Optional[str]) -> Score:
        if x is None or y is None:
            return ZERO2
        k = (x, y)
        v = self._c.get(k)
        if v is None:
            t = self.tier
            if x in t.postings and y in t.postings:
                v = (t.n_pair(x, y), t.p_pair(x, y))
            else:
                v = ZERO2                                   # L-52: outside the space
            self._c[k] = v
        return v


def _add(a: Score, b: Score) -> Score:
    return (a[0] + b[0], a[1] + b[1])


def _sub(a: Score, b: Score) -> Score:
    return (a[0] - b[0], a[1] - b[1])


def score_flat(w: Weights, flat: Flat, L: int) -> Score:
    s = ZERO2
    for o, i in _layout(L).edges:
        s = _add(s, w(flat[o], flat[i]))
    return s


def _edge_sum(w: Weights, flat: Sequence[Optional[str]], lay: _Layout, es: Iterable[int]) -> Score:
    s = ZERO2
    for ei in es:
        o, i = lay.edges[ei]
        s = _add(s, w(flat[o], flat[i]))
    return s


def _union(a: Tuple[int, ...], b: Tuple[int, ...]) -> Tuple[int, ...]:
    return tuple(a) + tuple(x for x in b if x not in a)


def _swap_delta(w: Weights, flat: Flat, lay: _Layout, i: int, j: int) -> Score:
    es = _union(lay.inc[i], lay.inc[j])
    old = _edge_sum(w, flat, lay, es)
    f = list(flat)
    f[i], f[j] = f[j], f[i]
    return _sub(_edge_sum(w, f, lay, es), old)


def _swapped(flat: Flat, L: int, i: int, j: int) -> Flat:
    f = list(flat)
    f[i], f[j] = f[j], f[i]
    return canon(tuple(f), L)


# --------------------------------------------------------------------------
# search: local search to fixed points, branching on tied best moves (I-05, L-62)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SearchResult:
    status: str
    terminals: Tuple[Flat, ...]            # distinct terminal states, canonical order
    plateau: Tuple[Flat, ...]              # distinct equal-key different states one move away
    explored: int                          # distinct states visited
    moves_tested: int
    score: Optional[Score]                 # key of the (single) terminal, else None


def _flat_sort_key(f: Flat) -> Tuple[Tuple[str, ...], ...]:
    return (_leg_key(f),)


def _plateau_of(w: Weights, flat: Flat, L: int) -> Tuple[List[Flat], int]:
    lay = _layout(L)
    out: Dict[Flat, None] = {}
    tested = 0
    for i in range(lay.n):
        for j in range(i + 1, lay.n):
            if flat[i] == flat[j]:
                continue
            tested += 1
            if _swap_delta(w, flat, lay, i, j) == ZERO2:
                s = _swapped(flat, L, i, j)
                if s != flat:
                    out[s] = None
    return sorted(out, key=_flat_sort_key), tested


def _search(w: Weights, starts: Sequence[Flat], L: int, state_budget: int) -> SearchResult:
    """All tied best improving moves are branched; terminals are fixed points."""
    lay = _layout(L)
    seen: Dict[Flat, None] = {}
    stack = [canon(s, L) for s in starts]
    terminals: Dict[Flat, None] = {}
    tested = 0
    while stack:
        s = stack.pop()
        if s in seen:
            continue
        seen[s] = None
        if len(seen) > state_budget:
            return SearchResult(BUDGET, (), (), len(seen), tested, None)
        best = ZERO2
        best_moves: List[Tuple[int, int]] = []
        for i in range(lay.n):
            for j in range(i + 1, lay.n):
                if s[i] == s[j]:
                    continue
                tested += 1
                d = _swap_delta(w, s, lay, i, j)
                if d > best:
                    best, best_moves = d, [(i, j)]
                elif d == best and d > ZERO2:
                    best_moves.append((i, j))
        if not best_moves:
            terminals[s] = None
            continue
        nxt = {_swapped(s, L, i, j): None for i, j in best_moves}
        if len(nxt) > MAX_TIED_BRANCHES:
            return SearchResult(BUDGET, (), (), len(seen), tested, None)
        stack.extend(sorted(nxt, key=_flat_sort_key, reverse=True))
    terms = tuple(sorted(terminals, key=_flat_sort_key))
    if len(terms) != 1:
        return SearchResult(TIED, terms, (), len(seen), tested, None)
    plat, t2 = _plateau_of(w, terms[0], L)
    sc = score_flat(w, terms[0], L)
    return SearchResult(PLATEAU if plat else STABLE, terms, tuple(plat), len(seen), tested + t2, sc)


# --------------------------------------------------------------------------
# group insertion (L-64)
# --------------------------------------------------------------------------
def _insert_group(w: Weights, flat: Flat, L: int, members: Sequence[str],
                  state_budget: int) -> Optional[List[Flat]]:
    """Insert all members order-free; returns the complete states or None on budget."""
    lay = _layout(L)
    frontier: Dict[Tuple[Flat, Tuple[str, ...]], None] = {(flat, tuple(sorted(members))): None}
    done: Dict[Flat, None] = {}
    steps = 0
    while frontier:
        nxt: Dict[Tuple[Flat, Tuple[str, ...]], None] = {}
        for st, rem in frontier:
            if not rem:
                done[st] = None
                continue
            empties = [e for e in range(lay.n) if st[e] is None]
            best: Optional[Score] = None
            picks: List[Tuple[str, int]] = []
            for u in rem:
                for e in empties:
                    g = ZERO2
                    for ei in lay.inc[e]:
                        o, i = lay.edges[ei]
                        g = _add(g, w(u if o == e else st[o], u if i == e else st[i]))
                    if best is None or g > best:
                        best, picks = g, [(u, e)]
                    elif g == best:
                        picks.append((u, e))
            branches: Dict[Tuple[Flat, Tuple[str, ...]], None] = {}
            for u, e in picks:
                f = list(st)
                f[e] = u
                r2 = tuple(x for x in rem if x != u)
                branches[(canon(tuple(f), L), r2)] = None
            if len(branches) > MAX_TIED_BRANCHES:
                return None
            for b in branches:
                nxt[b] = None
            steps += 1
        frontier = nxt
        if len(frontier) + len(done) > state_budget:
            return None
    return sorted(done, key=_flat_sort_key)


# --------------------------------------------------------------------------
# classification of an arbitrary cross
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Stability:
    status: str
    terminals: Tuple[Cross, ...]
    plateau: Tuple[Cross, ...]
    explored: int
    score: Optional[Score]


def classify(tier: TierSpace, cross: Cross, state_budget: int = MAX_STATES) -> Stability:
    """Search from `cross` to fixed points (all tied best moves branched) and type the
    outcome (L-62).  A symmetric start is TIED/PLATEAU, never resolved by order."""
    w = Weights(tier)
    r = _search(w, [from_cross(cross)], cross.L, state_budget)
    return Stability(r.status, tuple(to_cross(t, cross.L) for t in r.terminals),
                     tuple(to_cross(t, cross.L) for t in r.plateau), r.explored, r.score)


# --------------------------------------------------------------------------
# independent verification of the fixed-point property (I-05)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FixedPointReport:
    rotations_tested: int           # 23 non-identity rotations
    rotations_changing_key: int     # must be 0 (the key is rotation-invariant)
    swaps_total: int                # C(6L+1, 2) (geometry.moves_swap)
    swaps_noop: int                 # both seats hold equal contents
    swaps_improving: int            # must be 0
    swaps_equal_key_different: int  # plateau moves (distinct resulting state, equal key)
    is_fixed_point: bool


def cross_score(w: Weights, cross: Cross) -> Score:
    """Key of a Cross computed directly from geometry's edges (not the search's code)."""
    from verantyx.line3.geometry import edges as g_edges
    s = ZERO2
    for a, b in g_edges(cross.L):
        x, y = cross.get(a), cross.get(b)       # edges() lists (outer, inner)
        s = _add(s, w(None if x is None else str(x), None if y is None else str(y)))
    return s


def verify_fixed_point(tier: TierSpace, cross: Cross) -> FixedPointReport:
    """I-05: no single move (23 rotations + every pair of seats) improves the key."""
    w = Weights(tier)
    base = cross_score(w, cross)
    rot_changed = sum(1 for r in moves_rotate() if cross_score(w, rotate(cross, r)) != base)
    total = noop = improving = plateau = 0
    plat_states = set()
    here = canon(from_cross(cross), cross.L)
    for p, q in moves_swap(cross.L):
        total += 1
        if cross.get(p) == cross.get(q):
            noop += 1
            continue
        c2 = swap(cross, p, q)
        s2 = cross_score(w, c2)
        if s2 > base:
            improving += 1
        elif s2 == base:
            f2 = canon(from_cross(c2), cross.L)
            if f2 != here:
                plat_states.add(f2)
    plateau = len(plat_states)
    return FixedPointReport(len(moves_rotate()), rot_changed, total, noop, improving,
                            plateau, rot_changed == 0 and improving == 0)


# --------------------------------------------------------------------------
# growth of one cross (M-1(b), N-05, N-09)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Step:
    share: int                       # n(seed, v) shared by every unit of the group
    units: Tuple[str, ...]           # the group (canonical sorted label order)
    status: str                      # STABLE | TIED | PLATEAU | BUDGET
    explored: int                    # distinct states visited for this step
    size_after: Optional[int]        # units in the cross if this step was kept


@dataclass(frozen=True)
class Placement:
    seed: str
    cross: Cross                     # the last stable state (N-05)
    L: int
    centre: Optional[str]            # what the search left in the centre seat (I-02)
    size: int                        # units placed
    capacity: int                    # N-09: size of the last stable state (== size)
    score: Score
    stop: str                        # "exhausted" | "tied" | "plateau" | "budget"
    broke_on: Optional[Step]         # the step that broke stability (restored away)
    steps: Tuple[Step, ...]          # all attempted steps, kept ones then the failed one
    candidates: int                  # units with n(seed,v) > 0

    @property
    def centre_moved(self) -> bool:
        return self.centre != self.seed

    def to_json_obj(self) -> dict:
        def st(s: Optional[Step]):
            return None if s is None else {"share": s.share, "units": list(s.units),
                                           "status": s.status, "explored": s.explored,
                                           "size_after": s.size_after}
        return {"seed": self.seed, "L": self.L, "centre": self.centre, "size": self.size,
                "capacity": self.capacity, "score": list(self.score), "stop": self.stop,
                "cells": json.loads(self.cross.serialize().decode("ascii")),
                "broke_on": st(self.broke_on), "steps": [st(s) for s in self.steps],
                "candidates": self.candidates}

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json_obj(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def _groups(tier: TierSpace, seed: str) -> List[Tuple[int, Tuple[str, ...]]]:
    """M-1(b): candidates by shared-sentence count with the seed, descending; equal
    shares together.  The within-group order is a label only (sorted)."""
    by: Dict[int, List[str]] = {}
    for v, c in tier.cooccurrence(seed).items():
        by.setdefault(c, []).append(v)
    return [(c, tuple(sorted(by[c]))) for c in sorted(by, reverse=True)]


def build_cross(tier: TierSpace, seed: str, w: Optional[Weights] = None,
                max_groups: Optional[int] = None) -> Placement:
    """Build the stable arrangement around `seed` by search, growing group by group."""
    if seed not in tier.postings:
        raise KeyError(seed)
    w = w or Weights(tier)
    L = 1
    state: Flat = canon((seed,) + (None,) * 6, 1)          # L-63
    size = 1
    groups = _groups(tier, seed)
    steps: List[Step] = []
    stop, broke = "exhausted", None
    for gi, (share, members) in enumerate(groups):
        if max_groups is not None and gi >= max_groups:
            stop = "max_groups"
            break
        L2 = min_L(size + len(members))
        base = extend(state, L, L2) if L2 > L else state
        starts = _insert_group(w, base, L2, members, MAX_STATES)
        if starts is None:
            res = SearchResult(BUDGET, (), (), 0, 0, None)
        else:
            res = _search(w, starts, L2, MAX_STATES)
        if res.status == STABLE:
            state, L, size = res.terminals[0], L2, size + len(members)
            steps.append(Step(share, members, STABLE, res.explored, size))
        else:
            broke = Step(share, members, res.status, res.explored, None)
            steps.append(broke)
            stop = res.status                               # N-05: restore `state`
            break
    cross = to_cross(state, L)
    return Placement(seed, cross, L, state[0], size, size, score_flat(w, state, L),
                     stop, broke, tuple(steps), sum(len(g) for _, g in groups))


class Placer:
    """On-demand placement with a cache (L-07): results never depend on the cache."""

    def __init__(self, tier: TierSpace) -> None:
        self.tier = tier
        self.w = Weights(tier)
        self._done: Dict[str, Placement] = {}

    def cross_for(self, seed: str) -> Placement:
        p = self._done.get(seed)
        if p is None:
            p = self._done[seed] = build_cross(self.tier, seed, self.w)
        return p

    def precompute_all(self, seeds: Optional[Iterable[str]] = None) -> Dict[str, Placement]:
        for s in (self.tier.units() if seeds is None else seeds):
            self.cross_for(s)
        return {s: self._done[s] for s in sorted(self._done)}


def serialize_all(placements: Mapping[str, Placement]) -> bytes:
    """Canonical bytes of a set of placements (no timings)."""
    return json.dumps([placements[s].to_json_obj() for s in sorted(placements)],
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# --------------------------------------------------------------------------
# energy log (N-02, L-20/L-67)
# --------------------------------------------------------------------------
def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


@dataclass(frozen=True)
class EnergyRecord:
    unit: str
    seat: Seat
    r0: Fraction
    energy: Fraction
    ratio: Optional[Fraction]        # E_Q / r0, None iff r0 == 0


@dataclass(frozen=True)
class EnergyLog:
    query: Tuple[str, ...]           # distinct units, canonical order (L-51)
    records: Tuple[EnergyRecord, ...]
    status: str                      # three-ratio verdict status (energy.three_ratios)
    agreed_unit: Optional[str]

    def to_json_obj(self) -> dict:
        return {"query": list(self.query), "status": self.status, "unit": self.agreed_unit,
                "records": [{"unit": r.unit, "seat": [r.seat.arm, r.seat.k], "r0": _fs(r.r0),
                             "E": _fs(r.energy), "ratio": _fs(r.ratio)} for r in self.records]}


def energy_log(tier: TierSpace, cross: Cross, query: Iterable[str]) -> EnergyLog:
    """Observe how a query changes the energy of every placed unit of the stable
    arrangement: r0 (the base), E_Q (after the query) and E_Q / r0."""
    q = tuple(sorted(set(query)))
    recs: List[EnergyRecord] = []
    for seat in seats(cross.L):
        u = cross.get(seat)
        if u is None:
            continue
        u = str(u)
        r0 = en.r0(tier, u)
        e = en.energy(tier, u, q)
        recs.append(EnergyRecord(u, seat, r0, e, None if r0 == 0 else e / r0))
    v = en.three_ratios(tier, cross, q)
    return EnergyLog(q, tuple(recs), v.status, v.unit)


def observe(tier: TierSpace, placement: Placement, queries: Iterable[Iterable[str]]) -> List[EnergyLog]:
    """N-02: the energy changes of the stable arrangement under each query, in query order."""
    return [energy_log(tier, placement.cross, q) for q in queries]
