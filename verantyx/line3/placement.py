"""T4b placement: the deliberately built stable arrangement (a CLASS of tied
arrangements) + energy log.

Binding decisions (ops/decisions/2026-10-06_line3_faithful_build.md, incl. "T4 の測定後の決定"):
  decision 8 + I-04  placement = the arrangement where the space's energy is stable,
        measured first by the sentences shared by neighbouring units, then by word
        order.  Key (lexicographic, larger is better; the design's key is its negation):
          (1) sum over cross edges of n(x,y)
          (2) sum over cross edges, outer -> inner, of p(x,y)
        Keys are totally ordered, so two different keys never tie.
  N-02 + M-1(a)  the stable initial arrangement is built deliberately by SEARCHING with
        that stability definition; from it each query's energy changes are logged.
  M-1(b)  units are added in order of how many sentences they share with the ORIGINAL
        SEED (owner: "最初の種の語"); units with equal shares are added together.
  I-05  a state is a fixed point when no single move (24 rotations + seat swaps)
        improves it.  verify_fixed_point() / verify_class() check this against ALL single
        moves with code independent of the search.
  I-02  no centre is chosen at ingestion; the centre(s) of the final class are whatever
        the search leaves in the centre seat.
  N-09/N-05  capacity is decided only by stability; when a step cannot be completed (the
        only way now: the explicit budget), the state that was stable just before is
        restored and its size is the capacity.
  Owner's decisions after the T4 measurement (binding):
    (1) 「同点の並びをまとめて 1 つの状態として育てる」: all arrangements of equal key are
        kept TOGETHER as ONE state and that state is grown; none is picked by order.
    (2) 「区別しない（同じ状態として扱う）」: which arm holds which leg is not
        distinguished; arrangements equal up to arm assignment are the same arrangement.
    (3) no replacement with units outside the cross: moves = rotations + seat swaps.
    (4) growth order = shares with the original seed unit.

Local decisions (docs/LINE3_LOCAL_DECISIONS.md; L-60.. kept, L-62 superseded, L-70..):
  L-60 pool = the units admitted to the cross; moves are the 23 non-identity rotations
       and the swap of any two seats (empty seats included).  (kept)
  L-61 arrangement identity = (centre, multiset of legs read outer -> inner, empty seats
       kept).  Rotations only change orientation (the key is rotation-invariant).  This is
       exactly decision (2).  (kept)  The concrete Cross used as a representative places
       the legs in canonical sorted order with identity orientation (a label, not a winner).
  L-63 growth starts from the seed alone (L=1); the order anchor is the SEED.  (kept; the
       lone seed is no longer "stable by definition": its class is built like any other.)
  L-65 L = minimal with 6L+1 >= units; growing L prepends an empty outer seat to every
       leg.  (kept)
  L-70 A STATE is a CLASS: a set of arrangements, all of one key, CLOSED under single moves
       that keep the key (equal-key swaps), and containing no member from which a single
       move improves the key.  "Stable" = that fixed point of the class.
  L-71 Settling: from any set of start arrangements, level by level, every state moves by
       ALL its best improving single moves (all tied best results kept); terminals of the
       best key are taken; their closure under equal-key swaps is the class.  If any
       member of the closure has an improving move, the results of those moves (from every
       member) are climbed again, until the closure has none.  Different branches with the
       same key end up in the same class (their union).
  L-72 Growth adds the next share-group to EVERY member of the class (L-64 greedy insertion
       with all tied placements kept), settles all results (L-71) and keeps the best-key
       class.  The step never "breaks": stability is always reached; a step stops only by
       BUDGET.
  L-73 Budget (explicit, never a silent cut): max_class = most arrangements in one class,
       max_states = most distinct states handled in one growth step (insertion + climbing
       + closure), max_moves = most single moves tested / placements scored in one growth
       step (a large cross costs more per state).  Exceeding either = BUDGET: the growth stops, the previous class is
       restored (N-05) and Placement.stop == "budget"; the budget values are recorded in
       every Placement and Step.
  L-67 Energy log record per placed unit: r0, E_Q, E_Q/r0 (None if r0 = 0), seat order
       centre, AXES order, k ascending; plus the three-ratio verdict.  It is taken on the
       representative of the class; observe_class() takes it on every member.
  L-76 Budget LEVELS low / mid-low / mid / high / max (each 4x the previous in max_moves,
       max_states, max_class); mid == the T4b default; max is a compromise, still finite.
  L-77 An arrangement with an EMPTY CENTRE is not a state (owner): moves that would leave
       the centre empty are not moves, so no class contains one; the lone seed's class is
       the seed at the centre only.  (Owner point (3), reading all members of a class and
       adopting the query-stable one, belongs to the query stage; not implemented.)
  L-90 TWINS (owner after T4c: 「入れ替えても同じ語どうしは並べ方を数えない」): two units u, v of
       the candidate pool P (the seed and every unit sharing a sentence with it) are
       INTERCHANGEABLE iff the transposition (u v) is an automorphism of the I-04 weights on P:
       w(u,z) == w(v,z) and w(z,u) == w(z,v) for every z in P other than u, v (w = (n, p)
       of an edge, outer -> inner), and w(u,v) == w(v,u).  Then swapping u and v can never
       change the key of any arrangement of units of P.  This is an equivalence relation
       (the transposition (u x) = (u v)(v x)(u v)).  Twins are held as ONE interchangeable
       group: the search runs on arrangements of LABELS (one label per twin class) so
       arrangements differing only by permuting twins are not enumerated separately.  The
       stability values and the set of states do not change; only the counting.
  L-91 The quotient state is a class of label arrangements; the expanded class (the T4c
       class) is all assignments of the actual units to the label slots (up to arm
       assignment).  build_cross(quotient=False) is the T4c search byte for byte.
  G1-b (docs/LINE3_G4_GROWTH_METER.md 4.3, docs/LINE3_G1_INITIAL_PLACEMENT.md 3.1; L-G4-20..22, L-G1b-*): `foundation="on"` seats the six
       arm particles (the foundation, verantyx.line3.foundation) FIXED in the innermost ring of the six arms; the centre stays the data seed
       found by search (D-1).  A seat swap is a move only if neither seat is a foundation seat (rotations stay moves: they are the identity
       once the legs are told apart by their particle).  The key is (n, p, a), lexicographic, larger is better: n and p are the I-04 sums
       over the CONTRACTED cross (the foundation seats removed, the data on both sides neighbours: the seam), a is the adhesion (an
       integer over 377).  Everything else (F1 ordered insertion, stop / skip, the budget, tied classes held as one state) is unchanged in
       form.  `foundation="off"` (the default) runs the code that was here before, byte for byte.
Everything is exact (int / Fraction), deterministic, and hash-seed independent.
"""
from __future__ import annotations

import dataclasses
import itertools
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import energy as en
from verantyx.line3 import foundation as fd
from verantyx.line3.geometry import (
    AXES, CENTER, N_ARMS, Cross, Seat, moves_rotate, moves_swap, rotate, seats, swap,
)
from verantyx.line3.space import TierSpace

STABLE = "stable"
BUDGET = "budget"

MAX_CLASS = 1000           # L-73
MAX_STATES = 20000         # L-73
MAX_MOVES = 400000         # L-73

CENTER_IDX = 0             # flat index of the centre seat

Score = Tuple[int, int]
Flat = Tuple[Optional[str], ...]     # [centre, arm0 k=0..L-1, arm1 ..., ...]
ZERO2: Score = (0, 0)
ZERO3: Tuple[int, int, int] = (0, 0, 0)     # G1-b: the key (n, p, a) of a seated cross


@dataclass(frozen=True)
class Budget:
    """L-73: the explicit budget; recorded in every result that used it."""
    max_class: int = MAX_CLASS
    max_states: int = MAX_STATES
    max_moves: int = MAX_MOVES

    def to_json_obj(self) -> dict:
        return {"max_class": self.max_class, "max_states": self.max_states,
                "max_moves": self.max_moves}


# L-76: the five named budget levels (owner: "lowからmaxまでの五段階"; max is a COMPROMISE
# point, still finite).  Each level is 4x the previous in max_moves (and in the other two).
LEVELS: Dict[str, Budget] = {
    "low": Budget(max_class=63, max_states=1250, max_moves=25000),
    "mid-low": Budget(max_class=250, max_states=5000, max_moves=100000),
    "mid": Budget(max_class=1000, max_states=20000, max_moves=400000),     # == the T4b default
    "high": Budget(max_class=4000, max_states=80000, max_moves=1600000),
    "max": Budget(max_class=16000, max_states=320000, max_moves=6400000),
}
LEVEL_ORDER = ("low", "mid-low", "mid", "high", "max")


def budget_level(name: str) -> Budget:
    """L-76: the Budget of a named level (KeyError for an unknown name)."""
    return LEVELS[name]


def level_name(b: Budget) -> Optional[str]:
    """The level name a Budget equals, or None for a custom budget."""
    for n in LEVEL_ORDER:
        if LEVELS[n] == b:
            return n
    return None


class _Over(Exception):
    """Internal: a budget was exceeded (always surfaced as a BUDGET result)."""


class _Work:
    def __init__(self, budget: Budget) -> None:
        self.budget = budget
        self.n = 0
        self.tested = 0

    def tick(self, k: int = 1) -> None:
        self.n += k
        if self.n > self.budget.max_states:
            raise _Over("max_states")

    def moves(self, k: int) -> None:
        """Cost in single moves / placements scored (a large cross costs more per state)."""
        self.tested += k
        if self.tested > self.budget.max_moves:
            raise _Over("max_moves")


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


class _FLayout:
    """G1-b: the layout of a seated cross of arm length L (6L + 1 seats; the innermost seat of every leg is a foundation seat).
    `edges` / `inc` are the edges of the CONTRACTED cross (the seam, OP-G1-4), indexed over the full flat: on every leg the data seats
    k = 0 .. L-2 are chained outer -> inner and the innermost data seat (k = L-2) is linked to the centre; a foundation seat (k = L-1) has
    no edge.  `cons` = the foundation seats, `data` = every other seat (the only ones a move may touch), `col[i]` = the column of seat
    i in an adhesion row (0 = the centre relation, 1 + arm otherwise)."""

    def __init__(self, L: int) -> None:
        self.L = L
        self.n = 6 * L + 1
        edges: List[Tuple[int, int]] = []
        for a in range(N_ARMS):
            for k in range(L - 2):
                edges.append((1 + a * L + k, 1 + a * L + k + 1))
            if L >= 2:
                edges.append((1 + a * L + L - 2, 0))
        self.edges = tuple(edges)
        inc: List[List[int]] = [[] for _ in range(self.n)]
        for ei, (o, i) in enumerate(self.edges):
            inc[o].append(ei)
            inc[i].append(ei)
        self.inc = tuple(tuple(x) for x in inc)
        self.cons = frozenset(1 + a * L + L - 1 for a in range(N_ARMS))
        self.data = tuple(i for i in range(self.n) if i not in self.cons)
        col = [0] * self.n
        for a in range(N_ARMS):
            for k in range(L):
                col[1 + a * L + k] = 1 + a
        self.col = tuple(col)


_FLAYOUTS: Dict[int, _FLayout] = {}


def _flayout(L: int) -> _FLayout:
    if L not in _FLAYOUTS:
        _FLAYOUTS[L] = _FLayout(L)
    return _FLAYOUTS[L]


def _lay(w: "Weights", L: int):
    """The layout a search over `w` uses: the plain cross, or (a seated cross) the contracted one."""
    return _layout(L) if w.fnd is None else _flayout(L)


def min_L(count: int) -> int:
    """L-65: smallest L with 6L+1 >= count."""
    L = 1
    while 6 * L + 1 < count:
        L += 1
    return L


def _leg_key(leg: Sequence[Optional[str]]) -> Tuple[str, ...]:
    return tuple("" if c is None else c for c in leg)


def canon(flat: Flat, L: int) -> Flat:
    """L-61: legs in canonical sorted order (label only).  G1-b: a seated flat (its legs end in foundation seats) tells its legs apart by
    their particle, so the canonical order is the ladder order of the particles (the arm order of the foundation); never a content order."""
    c = flat[L]
    if c is not None and c.startswith(fd.TOKEN_PREFIX):
        return _canon_seated(flat, L)
    legs = sorted((flat[1 + a * L: 1 + (a + 1) * L] for a in range(N_ARMS)), key=_leg_key)
    out: List[Optional[str]] = [flat[0]]
    for g in legs:
        out.extend(g)
    return tuple(out)


_ARM_RANK: Dict[str, int] = {fd.token(p): i for i, p in enumerate(fd.DEFAULT_SPEC.arms)}


def _canon_seated(flat: Flat, L: int) -> Flat:
    ranks = [_ARM_RANK[flat[1 + a * L + L - 1]] for a in range(N_ARMS)]
    if ranks == sorted(ranks):
        return flat
    order = sorted(range(N_ARMS), key=lambda a: ranks[a])
    out: List[Optional[str]] = [flat[0]]
    for a in order:
        out.extend(flat[1 + a * L: 1 + (a + 1) * L])
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
class _FCtx:
    """G1-b: what a search over a SEATED cross reads besides the edge weights: the adhesion rows (numerator(p) * adj(v, p) per ladder
    column).  Built from a foundation.Adhesion; the default spec only (the leg order of a seated flat is the ladder order)."""

    def __init__(self, adhesion: "fd.Adhesion") -> None:
        if adhesion.spec != fd.DEFAULT_SPEC:
            raise ValueError("only the default foundation spec can be searched (the leg order of a seated flat is its ladder order)")
        self.adhesion = adhesion
        self.spec = adhesion.spec
        self.rows = adhesion.rows()
        self.zero7: Tuple[int, ...] = (0,) * len(adhesion.spec.ladder)
        self.sha = adhesion.spec.sha256()

    def row(self, u: Optional[str]) -> Tuple[int, ...]:
        return self.zero7 if u is None else self.rows.get(u, self.zero7)


class Weights:
    """Edge weight (n(x,y), p(x,y)) for outer x, inner y; cached per tier (pure cache).  With an `adhesion` (G1-b) the weights are those
    of a SEATED search: the edges are those of the contracted cross and the key gains a third component, a."""

    fnd: Optional[_FCtx] = None

    def __init__(self, tier: TierSpace, adhesion: Optional["fd.Adhesion"] = None) -> None:
        self.tier = tier
        self._c: Dict[Tuple[str, str], Score] = {}
        if adhesion is not None:
            if adhesion.tier != tier.name:
                raise ValueError("adhesion of tier %s given for tier %s" % (adhesion.tier, tier.name))
            self.fnd = _FCtx(adhesion)

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


# --------------------------------------------------------------------------
# L-90: interchangeable units (twins)
# --------------------------------------------------------------------------
def find_twins(w: Weights, pool: Sequence[str]) -> Dict[str, str]:
    """L-90: partition `pool` into interchangeable classes.  Returns {unit: representative}
    (representative = the smallest unit of its class; singletons map to themselves).
    u ~ v  iff  w(u,z) == w(v,z) and w(z,u) == w(z,v) for all z in pool \\ {u, v} and
    w(u,v) == w(v,u)  (the transposition (u v) leaves every edge weight on the pool
    invariant, so it leaves the I-04 key of every arrangement invariant)."""
    pool = sorted(pool)
    vec: Dict[str, Dict[str, Tuple[Score, Score]]] = {
        u: {z: (w(u, z), w(z, u)) for z in pool if z != u} for u in pool}
    buckets: Dict[Tuple, List[str]] = {}
    for u in pool:
        buckets.setdefault(tuple(sorted(vec[u].values())), []).append(u)
    rep: Dict[str, str] = {u: u for u in pool}
    for b in buckets.values():
        reps: List[str] = []
        for u in b:                                   # b is sorted: reps hold the minima
            for r in reps:
                if are_interchangeable(w, pool, r, u, vec):
                    rep[u] = r
                    break
            else:
                reps.append(u)
    return rep


def are_interchangeable(w: Weights, pool: Sequence[str], u: str, v: str,
                        vec: Optional[Dict[str, Dict[str, Tuple[Score, Score]]]] = None) -> bool:
    """L-90 definition, checked directly: swapping u and v leaves w invariant on `pool`."""
    if u == v:
        return True
    if w(u, v) != w(v, u):
        return False
    for z in pool:
        if z == u or z == v:
            continue
        if vec is not None:
            if vec[u][z] != vec[v][z]:
                return False
        elif w(u, z) != w(v, z) or w(z, u) != w(z, v):
            return False
    return True


def _refine_twins(rep: Dict[str, str], adhesion: "fd.Adhesion") -> Dict[str, str]:
    """G1-b: a twin class of L-90 is split by the adhesion row (numerator(p) * adj(u, p) for every particle of the foundation): two units
    that the I-04 weights cannot tell apart are still different if one of them sticks to a particle the other does not, because
    swapping them would change a.  The result is again a partition into classes of mutually interchangeable units; the representative
    is the smallest unit of each part."""
    parts: Dict[Tuple[str, Tuple[int, ...]], List[str]] = {}
    for u in sorted(rep):
        parts.setdefault((rep[u], adhesion.weighted(u)), []).append(u)
    out: Dict[str, str] = {}
    for us in parts.values():
        m = us[0]
        for u in us:
            out[u] = m
    return out


class QWeights(Weights):
    """Edge weight on LABELS (L-90): label = representative of a twin class.  Two slots with
    the same label hold two different twins: weight w(u, v) of any two distinct members."""

    def __init__(self, base: Weights, rep: Mapping[str, str]) -> None:
        self.tier = base.tier
        self._c = base._c
        self.fnd = base.fnd
        self._same: Dict[str, Score] = {}
        by: Dict[str, List[str]] = {}
        for u, r in rep.items():
            by.setdefault(r, []).append(u)
        for r, ms in by.items():
            if len(ms) > 1:
                ms.sort()
                self._same[r] = base(ms[0], ms[1])

    def __call__(self, x: Optional[str], y: Optional[str]) -> Score:
        if x is None or y is None:
            return ZERO2
        if x == y:
            return self._same.get(x, ZERO2)
        return Weights.__call__(self, x, y)


def _add(a: Score, b: Score) -> Score:
    return (a[0] + b[0], a[1] + b[1])


def _sub(a: Score, b: Score) -> Score:
    return (a[0] - b[0], a[1] - b[1])


def score_flat(w: Weights, flat: Flat, L: int):
    """The key of an arrangement: (n, p), or (n, p, a) for a seated cross (n, p over the contracted cross, a the adhesion)."""
    if w.fnd is not None:
        return _score_seated(w, flat, L)
    s = ZERO2
    for o, i in _layout(L).edges:
        s = _add(s, w(flat[o], flat[i]))
    return s


def _seat_a(fnd: _FCtx, u: Optional[str], col: int) -> int:
    return 0 if u is None else fnd.rows.get(u, fnd.zero7)[col]


def _score_seated(w: Weights, flat: Flat, L: int) -> Tuple[int, int, int]:
    lay = _flayout(L)
    fnd = w.fnd
    n = p = 0
    for o, i in lay.edges:
        d = w(flat[o], flat[i])
        n += d[0]
        p += d[1]
    a = 0
    col = lay.col
    for i in lay.data:
        u = flat[i]
        if u is not None:
            a += _seat_a(fnd, u, col[i])
    return (n, p, a)


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


def _swap_delta_seated(w: Weights, flat: Flat, lay: _FLayout, i: int, j: int) -> Tuple[int, int, int]:
    """(dn, dp, da) of swapping the data seats i and j of a seated cross: the edge part is _swap_delta on the contracted edges, the
    adhesion part moves each unit to the column of the other seat (the same arm: 0; the centre: the centre relation's column)."""
    d = _swap_delta(w, flat, lay, i, j)
    fnd = w.fnd
    ui, uj = flat[i], flat[j]
    ci, cj = lay.col[i], lay.col[j]
    da = 0
    if ci != cj:
        da = (_seat_a(fnd, uj, ci) + _seat_a(fnd, ui, cj)) - (_seat_a(fnd, ui, ci) + _seat_a(fnd, uj, cj))
    return (d[0], d[1], da)


def _swapped(flat: Flat, L: int, i: int, j: int) -> Flat:
    f = list(flat)
    f[i], f[j] = f[j], f[i]
    return canon(tuple(f), L)


# --------------------------------------------------------------------------
# classes: settle to a fixed point, close under equal-key moves (L-70, L-71)
# --------------------------------------------------------------------------
def _flat_sort_key(f: Flat) -> Tuple[Tuple[str, ...], ...]:
    return (_leg_key(f),)


def _scan_seated(w: Weights, s: Flat, L: int) -> Tuple[List[Flat], List[Flat], int]:
    """_scan on a seated cross (G1-b): a swap that touches a foundation seat is not a move (OP-G1-4); the key is (n, p, a)."""
    lay = _flayout(L)
    best = ZERO3
    best_moves: List[Tuple[int, int]] = []
    equal: Dict[Flat, None] = {}
    tested = 0
    data = lay.data
    nd = len(data)
    for x in range(nd):
        i = data[x]
        for y in range(x + 1, nd):
            j = data[y]
            if s[i] == s[j]:
                continue
            if i == CENTER_IDX and s[j] is None:
                continue                  # L-77: an empty centre is not an arrangement
            tested += 1
            d = _swap_delta_seated(w, s, lay, i, j)
            if d > best:
                best, best_moves = d, [(i, j)]
            elif d == best and d > ZERO3:
                best_moves.append((i, j))
            elif d == ZERO3:
                t = _swapped(s, L, i, j)
                if t != s:
                    equal[t] = None
    improved = sorted({_swapped(s, L, i, j): None for i, j in best_moves}, key=_flat_sort_key)
    return improved, sorted(equal, key=_flat_sort_key), tested


def _scan(w: Weights, s: Flat, L: int) -> Tuple[List[Flat], List[Flat], int]:
    """All single seat swaps of `s`.  Returns (results of the best improving moves,
    results of the equal-key moves giving a different arrangement, moves tested)."""
    if w.fnd is not None:
        return _scan_seated(w, s, L)
    lay = _layout(L)
    best = ZERO2
    best_moves: List[Tuple[int, int]] = []
    equal: Dict[Flat, None] = {}
    tested = 0
    for i in range(lay.n):
        for j in range(i + 1, lay.n):
            if s[i] == s[j]:
                continue
            if i == CENTER_IDX and s[j] is None:
                continue                  # L-77: an empty centre is not an arrangement
            tested += 1
            d = _swap_delta(w, s, lay, i, j)
            if d > best:
                best, best_moves = d, [(i, j)]
            elif d == best and d > ZERO2:
                best_moves.append((i, j))
            elif d == ZERO2:
                t = _swapped(s, L, i, j)
                if t != s:
                    equal[t] = None
    improved = sorted({_swapped(s, L, i, j): None for i, j in best_moves}, key=_flat_sort_key)
    return improved, sorted(equal, key=_flat_sort_key), tested


@dataclass(frozen=True)
class ClassResult:
    status: str                         # STABLE | BUDGET
    members: Tuple[Flat, ...]           # the class, canonical sorted order
    score: Optional[Score]
    work: int                           # distinct states handled
    moves_tested: int


def _settle(w: Weights, starts: Iterable[Flat], L: int, work: _Work, budget: Budget) -> Tuple[Flat, ...]:
    """L-71.  Raises _Over."""
    cur = sorted({canon(s, L) for s in starts}, key=_flat_sort_key)
    while True:
        seen: Dict[Flat, None] = {}
        terminals: Dict[Flat, None] = {}
        level = cur
        while level:
            nxt: Dict[Flat, None] = {}
            for s in level:
                if s in seen:
                    continue
                seen[s] = None
                work.tick()
                improved, _eq, t = _scan(w, s, L)
                work.moves(t)
                if not improved:
                    terminals[s] = None
                else:
                    for x in improved:
                        if x not in seen:
                            nxt[x] = None
            level = sorted(nxt, key=_flat_sort_key)
        kbest = max(score_flat(w, t, L) for t in terminals)
        comp: Dict[Flat, None] = {t: None for t in terminals if score_flat(w, t, L) == kbest}
        if len(comp) > budget.max_class:          # L-G4-47 (owner 「規則を適用、数え方の差は受け入れる」): the class built from the terminal arrangements is held to
            raise _Over("max_class")              # max_class like every later addition (before: checked only when it grew); raised BEFORE the tick of the first queue state
        queue = sorted(comp, key=_flat_sort_key)
        escapes: Dict[Flat, None] = {}
        qi = 0
        while qi < len(queue):
            s = queue[qi]
            qi += 1
            work.tick()
            improved, eq, t = _scan(w, s, L)
            work.moves(t)
            for x in improved:
                escapes[x] = None
            for x in eq:
                if x not in comp:
                    comp[x] = None
                    queue.append(x)
                    if len(comp) > budget.max_class:
                        raise _Over("max_class")
        if not escapes:
            return tuple(sorted(comp, key=_flat_sort_key))
        cur = sorted(escapes, key=_flat_sort_key)


def _insert_group(w: Weights, bases: Sequence[Flat], L: int, members: Sequence[str],
                  work: _Work, budget: Budget) -> List[Flat]:
    """L-64/L-72: insert all members order-free into EVERY base arrangement; at every
    step all (member, empty seat) pairs are scored, the best gain wins, ties branch (all
    kept).  Raises _Over."""
    lay = _lay(w, L)
    fnd = w.fnd
    rem0 = tuple(sorted(members))
    frontier: Dict[Tuple[Flat, Tuple[str, ...]], None] = {(b, rem0): None for b in bases}
    done: Dict[Flat, None] = {}
    while frontier:
        nxt: Dict[Tuple[Flat, Tuple[str, ...]], None] = {}
        for st, rem in sorted(frontier, key=lambda x: (_flat_sort_key(x[0]), x[1])):
            if not rem:
                done[st] = None
                continue
            work.tick()
            empties = [e for e in range(lay.n) if st[e] is None]
            work.moves(len(rem) * len(empties))
            best: Optional[Score] = None
            picks: List[Tuple[str, int]] = []
            for u in sorted(set(rem)):          # L-90: equal labels = one choice
                for e in empties:
                    g = ZERO2
                    for ei in lay.inc[e]:
                        o, i = lay.edges[ei]
                        g = _add(g, w(u if o == e else st[o], u if i == e else st[i]))
                    if fnd is not None:                       # G1-b: the adhesion of u to the arm (or the centre) of the target seat
                        g = (g[0], g[1], _seat_a(fnd, u, lay.col[e]))
                    if best is None or g > best:
                        best, picks = g, [(u, e)]
                    elif g == best:
                        picks.append((u, e))
            for u, e in picks:
                f = list(st)
                f[e] = u
                k = rem.index(u)                      # remove ONE occurrence (labels may repeat)
                nxt[(canon(tuple(f), L), rem[:k] + rem[k + 1:])] = None
        frontier = nxt
        if len(frontier) + len(done) > budget.max_states:
            raise _Over("max_states")
    return sorted(done, key=_flat_sort_key)


def settle_class(tier: TierSpace, starts: Sequence[Cross], budget: Budget = Budget(),
                 w: Optional[Weights] = None) -> "ClassStability":
    """Public: climb from the given crosses (all of one L) to fixed points and return the
    best-key class closed under equal-key moves (L-70/L-71)."""
    w = w or Weights(tier)
    L = starts[0].L
    if any(c.center is None for c in starts):
        raise ValueError("an arrangement with an empty centre is not a state (L-77)")
    work = _Work(budget)
    try:
        members = _settle(w, [from_cross(c) for c in starts], L, work, budget)
    except _Over:
        return ClassStability(BUDGET, (), None, work.n)
    return ClassStability(STABLE, tuple(to_cross(m, L) for m in members),
                          score_flat(w, members[0], L), work.n)


@dataclass(frozen=True)
class ClassStability:
    status: str
    members: Tuple[Cross, ...]
    score: Optional[Score]
    explored: int


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
        if c2.center is None:
            continue                  # L-77: not an arrangement
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


@dataclass(frozen=True)
class ClassReport:
    size: int
    one_key: bool                   # every member has the same key
    members_fixed_points: bool      # no member has an improving single move (all moves)
    closed: bool                    # every equal-key single move stays inside the class
    swaps_tested: int
    is_stable_class: bool
    centres_nonempty: bool = True   # L-77: every member has a unit at the centre


def verify_class(tier: TierSpace, members: Sequence[Cross]) -> ClassReport:
    """L-70: independent check (geometry's swap / edges, not the search's code) that a
    class is one key, a fixed point at every member, and closed under equal-key moves."""
    w = Weights(tier)
    L = members[0].L
    here = {canon(from_cross(c), L) for c in members}
    keys = {cross_score(w, c) for c in members}
    base = next(iter(keys))
    fixed = True
    closed = True
    tested = 0
    for c in members:
        for p, q in moves_swap(L):
            if c.get(p) == c.get(q):
                continue
            c2 = swap(c, p, q)
            if c2.center is None:
                continue              # L-77: not an arrangement
            tested += 1
            s2 = cross_score(w, c2)
            if s2 > base:
                fixed = False
            elif s2 == base and canon(from_cross(swap(c, p, q)), L) not in here:
                closed = False
        if any(cross_score(w, rotate(c, r)) != base for r in moves_rotate()):
            fixed = False
    one = len(keys) == 1
    nonempty = all(c.center is not None for c in members)
    return ClassReport(len(here), one, fixed, closed, tested,
                       one and fixed and closed and nonempty, nonempty)


@dataclass(frozen=True)
class FoundationClassReport:
    size: int
    one_key: bool                   # every member has the same key (n, p, a)
    members_fixed_points: bool      # no member has an improving swap of two data seats
    closed: bool                    # every equal-key swap of two data seats stays inside the class
    constructed_intact: bool        # every member holds the foundation tokens in the innermost ring, in the ladder order
    swaps_tested: int
    centres_nonempty: bool
    is_stable_class: bool
    key: Optional[Tuple[int, int, int]]
    matches_record: Optional[bool] = None   # (n, p, a) recomputed here == the key the Placement stored (None = no record given)


def seated_key(tier: TierSpace, adhesion: "fd.Adhesion", cross: Cross, w: Optional[Weights] = None) -> Tuple[int, int, int]:
    """(n, p, a) of a seated Cross computed from geometry's edges on the contracted cross (not the search's code).  `w` = a plain
    Weights(tier) (a pure cache) that a caller checking many crosses may share."""
    w = w if w is not None else Weights(tier)
    flat = from_cross(cross)
    cf, L2 = fd.contract(flat, cross.L)
    n, p = cross_score(w, to_cross(cf, L2))
    return (n, p, fd.a_num(adhesion, flat, cross.L))


def verify_class_foundation(tier: TierSpace, members: Sequence[Cross], adhesion: "fd.Adhesion",
                            expected: Optional[Tuple[int, int, int]] = None) -> FoundationClassReport:
    """G1-b: independent check (geometry's swap / edges, not the search's code) that a class of a SEATED cross is one key (n, p, a), a
    fixed point at every member over every swap of two NON-foundation seats, closed under equal-key swaps, with the foundation seats
    intact (no move generated by the search may touch them; here every pair that touches one is skipped by construction) and the
    centre non-empty.  Rotations are the identity once the legs are told apart by their particle.  Valid for a class of units
    (quotient=False, or a quotient build without twins); a quotient class stands for label arrangements.
    `expected` (review fix, L-G4-46): the key the Placement stored, (score[0], score[1], a_num); the independently recomputed key of the
    class has to equal it, else `matches_record` is False and the class is not stable."""
    L = members[0].L
    w = Weights(tier)
    ladder_tokens = tuple(fd.token(q) for q in adhesion.spec.arms)
    here = {canon(from_cross(c), L) for c in members}
    keys = {seated_key(tier, adhesion, c, w) for c in members}
    base = next(iter(keys))
    intact = all(tuple(from_cross(c)[1 + a * L + L - 1] for a in range(N_ARMS)) == ladder_tokens for c in members)
    fixed = closed = True
    tested = 0
    for c in members:
        for p_, q_ in moves_swap(L):
            if fd.is_constructed(None if c.get(p_) is None else str(c.get(p_))) or \
                    fd.is_constructed(None if c.get(q_) is None else str(c.get(q_))):
                continue                  # OP-G1-4: a swap that touches a foundation seat is not a move
            if c.get(p_) == c.get(q_):
                continue
            c2 = swap(c, p_, q_)
            if c2.center is None:
                continue                  # L-77
            tested += 1
            k2 = seated_key(tier, adhesion, c2, w)
            if k2 > base:
                fixed = False
            elif k2 == base and canon(from_cross(c2), L) not in here:
                closed = False
    one = len(keys) == 1
    nonempty = all(c.center is not None for c in members)
    matches = None if expected is None else (one and base == tuple(expected))
    return FoundationClassReport(len(here), one, fixed, closed, intact, tested, nonempty,
                                 one and fixed and closed and intact and nonempty and matches is not False, base if one else None, matches)


def contract_for_read(p: "Placement") -> "Placement":
    """G1-b (the seam, for the reader): every member with its foundation seats removed (a plain flat at L - 1), canonical (L-61), the
    duplicates that arm labels had kept apart merged, sorted; `cross` = the first (as build_cross chooses it).  `score` is already the
    contracted (n, p).  The identity for a placement without foundation and for one already contracted.
    Review fix (L-G4-44): the arm labels the contraction merges are kept aside for display in `arm_labels` (aligned with `members`; see
    Placement.arm_labels); they are not part of the contracted result (excluded from ==, repr and the JSON)."""
    if p.foundation is None or p.contracted:
        return p
    L2 = max(1, p.L - 1)
    labels: Dict[Flat, set] = {}
    for m in p.members:
        c = canon(fd.contract(m, p.L)[0], L2)
        labels.setdefault(c, set()).add(
            tuple((fd.particle_of(m[1 + a * p.L + p.L - 1]), tuple(m[1 + a * p.L: 1 + a * p.L + p.L - 1])) for a in range(N_ARMS)))
    cm = tuple(sorted(labels, key=_flat_sort_key))
    arm = tuple(tuple(sorted(labels[c], key=lambda lab: tuple((q, _leg_key(leg)) for q, leg in lab))) for c in cm)
    rep_cross = next(expand_flats(cm[:1], L2, p.twin_sets), cm[0])
    return dataclasses.replace(p, cross=to_cross(rep_cross, L2), members=cm, L=L2, contracted=True, arm_labels=arm)


# --------------------------------------------------------------------------
# growth of one cross (M-1(b), N-05, N-09, L-72)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Step:
    share: int                       # n(seed, v) shared by every unit of the group
    units: Tuple[str, ...]           # the group (canonical sorted label order)
    status: str                      # STABLE | BUDGET
    explored: int                    # distinct states handled for this step
    size_after: Optional[int]        # units in the cross if this step was kept
    class_size: Optional[int]        # arrangements in the class after this step
    reason: Optional[str] = None     # budget that was exceeded ("max_class" | "max_states")
    expanded_size: Optional[int] = None   # L-91: arrangements of the expanded (T4c) class


@dataclass(frozen=True)
class Placement:
    seed: str
    cross: Cross                     # representative of the class (first in canonical order; a label)
    members: Tuple[Flat, ...]        # the class: all tied arrangements, one state (L-70)
    L: int
    centres: Tuple[Optional[str], ...]   # distinct centres over the class (I-02)
    size: int                        # units placed
    capacity: int                    # N-09: size of the last stable class (== size)
    score: Score
    stop: str                        # "exhausted" | "budget" | "max_groups"
    broke_on: Optional[Step]         # the step that hit the budget (restored away)
    steps: Tuple[Step, ...]
    candidates: int                  # units with n(seed,v) > 0
    budget: Budget
    twin_sets: Tuple[Tuple[str, ...], ...] = ()   # L-90: placed twin classes with >= 2 units (sorted; [0] = the label shown in members)
    quotient: bool = True            # False = the T4c search (no twins)
    # F-1 (L-460..): ordered insertion of tied share-groups.  Defaults = the whole-group build.
    group_insert: str = "whole"      # "whole" (L-72) | "ordered" (L-460)
    order: str = "forward"           # "forward" | "reverse" (L-464, measurement only)
    order_log: Tuple[Tuple[int, Tuple[str, ...]], ...] = ()   # F-1: (share, members in the recorded insertion order) per group reached
    left_in_group: int = 0           # F-1: members of the group that broke, NOT inserted (the breaking one included)
    left_after: int = 0              # F-1: members of the groups after it, NOT inserted
    # F-1c (L-500..): on_collapse="skip".  Defaults = stop at the first collapse (L-463).
    on_collapse: str = "stop"        # "stop" (L-463) | "skip" (L-501)
    skipped: Tuple[Tuple[int, str, str], ...] = ()   # F-1c: (share, member, budget reason) of every member skipped, in the recorded order
    # G1-b (L-G4-20..22, L-G1b-*): foundation="on".  Defaults = no foundation (nothing of this is written to the JSON).
    foundation: Optional[str] = None   # G1-b: the seats_sha of the foundation spec the cross was built with; None = no foundation
    a_num: Optional[int] = None        # G1-b: the third key component a, an integer over the spec's denominator (377); None = no foundation
    contracted: bool = False           # G1-b: True = the reader's view (contract_for_read): members are PLAIN flats at L - 1, foundation seats removed
    # Review fixes (L-G4-44, L-G4-47).  Neither is part of the contracted result: arm_labels is not compared, shown or written.
    arm_labels: Optional[Tuple[Tuple[Tuple[Tuple[str, Tuple[Optional[str], ...]], ...], ...], ...]] = dataclasses.field(
        default=None, compare=False, repr=False)   # only on a contract_for_read view: arm_labels[i] = the distinct labellings merged into members[i];
                                                   # a labelling = (particle, the data seats of that arm outer -> inner) for the six particles in ladder order
    first_class_over_max: int = 0      # kept settled classes (the seed's, one per kept batch) holding more than budget.max_class arrangements (a verification quantity: 0 since _settle holds the first class to max_class, L-G4-47)

    @property
    def centre(self) -> Optional[str]:
        """The centre when every member has the same one, else None."""
        return self.centres[0] if len(self.centres) == 1 else None

    @property
    def class_size(self) -> int:
        """Arrangements in the held (quotient) class."""
        return len(self.members)

    @property
    def expanded_size(self) -> int:
        """L-91: arrangements of the expanded class (== the T4c class size)."""
        return expanded_count(self.members, self.L, _twin_counts(self.twin_sets))

    def expanded_members(self) -> Tuple[Flat, ...]:
        """L-91: the T4c class: every assignment of the placed units to the label slots
        (canonical sorted order).  Can be astronomically large: use expanded_size first."""
        return tuple(sorted(set(expand_flats(self.members, self.L, self.twin_sets)),
                            key=_flat_sort_key))

    @property
    def centre_moved(self) -> bool:
        return self.centres != (self.seed,)

    def crosses(self) -> Tuple[Cross, ...]:
        """Crosses of the EXPANDED class (see expanded_members)."""
        return tuple(to_cross(m, self.L) for m in self.expanded_members())

    def to_json_obj(self) -> dict:
        def st(s: Optional[Step]):
            return None if s is None else {"share": s.share, "units": list(s.units),
                                           "status": s.status, "explored": s.explored,
                                           "size_after": s.size_after,
                                           "class_size": s.class_size, "reason": s.reason,
                                           "expanded_size": s.expanded_size}
        o = {"seed": self.seed, "L": self.L, "centres": list(self.centres),
                "size": self.size, "capacity": self.capacity, "score": list(self.score),
                "stop": self.stop, "class_size": self.class_size,
                "members": [list(m) for m in self.members],
                "cells": json.loads(self.cross.serialize().decode("ascii")),
                "broke_on": st(self.broke_on), "steps": [st(s) for s in self.steps],
                "candidates": self.candidates, "budget": self.budget.to_json_obj(),
                "quotient": self.quotient, "twin_sets": [list(t) for t in self.twin_sets],
                "expanded_size": self.expanded_size,
                **({} if self.group_insert == "whole" else
                   {"group_insert": self.group_insert, "order": self.order,
                    "order_log": [[sh, list(us)] for sh, us in self.order_log],
                    "left_in_group": self.left_in_group, "left_after": self.left_after,
                    **({} if self.on_collapse == "stop" else
                       {"on_collapse": self.on_collapse,
                        "skipped": [[sh, u, why] for sh, u, why in self.skipped]})})}
        if self.foundation is not None:                      # G1-b: named only when on, so every committed byte is unchanged
            o.update({"foundation": self.foundation, "a_num": self.a_num, "contracted": self.contracted,
                      "first_class_over_max": self.first_class_over_max})
        return o

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json_obj(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def _twin_counts(twin_sets: Sequence[Sequence[str]]) -> Dict[str, int]:
    return {t[0]: len(t) for t in twin_sets}


def expanded_count(members: Sequence[Flat], L: int, counts: Mapping[str, int]) -> int:
    """L-91: number of arrangements the label arrangements `members` stand for.  `counts`
    = label -> number of placed twins (default 1).  Per member: prod k! over labels, divided
    by prod m! over groups of m identical NON-EMPTY legs (arm assignment is not
    distinguished, L-61; identical legs permute freely and act freely on distinct units)."""
    from math import factorial
    total = 0
    for f in members:
        n = 1
        seen: Dict[str, int] = {}
        for x in f:
            if x is not None:
                seen[x] = seen.get(x, 0) + 1
        for x in seen:
            n *= factorial(counts.get(x, 1))
        legs: Dict[Tuple[str, ...], int] = {}
        for a in range(N_ARMS):
            g = f[1 + a * L: 1 + (a + 1) * L]
            if any(c is not None for c in g):
                legs[_leg_key(g)] = legs.get(_leg_key(g), 0) + 1
        for m in legs.values():
            n //= factorial(m)
        total += n
    return total


def expand_flats(members: Sequence[Flat], L: int, twin_sets: Sequence[Sequence[str]]):
    """L-91: generator of arrangements (canonical, may repeat across members never; within
    one member distinct up to arm assignment after the caller's set())."""
    units = {t[0]: tuple(t) for t in twin_sets}
    for f in members:
        pos: Dict[str, List[int]] = {}
        for i, x in enumerate(f):
            if x in units:
                pos.setdefault(x, []).append(i)
        labels = sorted(pos)
        for combo in itertools.product(*[itertools.permutations(units[l]) for l in labels]):
            g = list(f)
            for l, perm in zip(labels, combo):
                for i, u in zip(pos[l], perm):
                    g[i] = u
            yield canon(tuple(g), L)


def _groups(tier: TierSpace, seed: str) -> List[Tuple[int, Tuple[str, ...]]]:
    """M-1(b): candidates by shared-sentence count with the seed, descending; equal
    shares together.  The within-group order is a label only (sorted)."""
    by: Dict[int, List[str]] = {}
    for v, c in tier.cooccurrence(seed).items():
        by.setdefault(c, []).append(v)
    return [(c, tuple(sorted(by[c]))) for c in sorted(by, reverse=True)]




def group_order(tier: TierSpace, seed: str, members: Sequence[str], reverse: bool = False) -> Tuple[str, ...]:
    """F-1 / L-461: the recorded insertion order of a tied share-group.  The sentences that make
    the tie are the seed's postings (ascending sid); in each, the group's units in order of their
    first occurrence in the sentence; a unit counts at the first sentence that holds it.  Every
    member shares >= 1 sentence with the seed, so the order is complete.  Hash-seed free.
    reverse=True (L-464, measurement only): the exact reverse list."""
    left = set(members)
    out: List[str] = []
    for sid in tier.postings[seed]:
        for u in dict.fromkeys(tier.sentence_units[sid]):
            if u in left:
                left.discard(u)
                out.append(u)
        if not left:
            break
    assert not left, "a group member shares no sentence with the seed"
    return tuple(reversed(out)) if reverse else tuple(out)


def _centres(members: Sequence[Flat]) -> Tuple[Optional[str], ...]:
    return tuple(sorted({m[0] for m in members}, key=lambda c: ("", "") if c is None else (c, "x")))


def build_cross(tier: TierSpace, seed: str, w: Optional[Weights] = None,
                max_groups: Optional[int] = None, budget: Budget = Budget(),
                quotient: bool = True, pool_groups: Optional[int] = None,
                group_insert: str = "whole", order: str = "forward",
                on_collapse: str = "stop", foundation: str = "off",
                adhesion: Optional["fd.Adhesion"] = None) -> Placement:
    """Build the stable CLASS around `seed` by search, growing group by group (L-72).
    quotient=True (L-90): interchangeable units are held as one group (labels);
    quotient=False: the T4c search (every unit its own label).
    pool_groups (T8, L-231; default None = unchanged): only the first `pool_groups` share-groups of
    M-1(b) enter the pool (a node budget of an upper layer: whole groups only, a tie is never split);
    when groups were left out the result's stop is "max_groups" unless the budget stopped it first.
    group_insert (F-1, L-460; default "whole" = L-72, byte-identical): "ordered" inserts the members of a
    tied share-group ONE AT A TIME in the recorded order of group_order() (order="reverse": the
    measurement probe), settling after each; a member that hits the budget is restored away and growth
    stops there (the later members and groups are not inserted; the counts are recorded).
    on_collapse (F-1c, L-500..; default "stop" = L-463, byte-identical): "skip" (only with
    group_insert="ordered", else ValueError) restores a collapsing member away, records it in
    `skipped`, and goes on with the next member of the recorded order and then the next groups.
    foundation (G1-b, L-G4-20..22; default "off" = every committed byte unchanged): "on" seats the six arm particles of the foundation FIXED in
    the innermost ring of the six arms (the centre stays the data seed, D-1); L is the smallest with 6L+1 >= the units seated plus the six;
    no move touches a foundation seat; the key is (n, p, a) with n and p over the CONTRACTED cross (the seam) and a the adhesion; needs
    `adhesion` (a foundation.Adhesion of this tier: the corpus the tier was cut from is not in a TierSpace)."""
    fd.check_foundation(foundation)
    seated = foundation == "on"
    if seated:
        if adhesion is None:
            raise ValueError("foundation='on' needs the adhesion of the tier (foundation.adhesion_of_space)")
    elif adhesion is not None:
        raise ValueError("an adhesion is only used with foundation='on'")
    if group_insert not in ("whole", "ordered"):
        raise ValueError("group_insert must be 'whole' or 'ordered'")
    if on_collapse not in ("stop", "skip"):
        raise ValueError("on_collapse must be 'stop' or 'skip'")
    if on_collapse == "skip" and group_insert != "ordered":
        raise ValueError("on_collapse='skip' needs group_insert='ordered' (a whole group is one step: nothing to skip)")
    if order not in ("forward", "reverse"):
        raise ValueError("order must be 'forward' or 'reverse'")
    if seed not in tier.postings:
        raise KeyError(seed)
    if seated:
        if w is not None and (w.fnd is None or w.fnd.adhesion is not adhesion):
            raise ValueError("w must be Weights(tier, adhesion) of the adhesion given")
        w = w or Weights(tier, adhesion)
    elif w is not None and w.fnd is not None:
        raise ValueError("w carries an adhesion but foundation is 'off'")
    else:
        w = w or Weights(tier)
    nfound = N_ARMS if seated else 0                 # G1-b: the foundation seats count in 6L+1 >= seated units
    groups = _groups(tier, seed)
    total_candidates = sum(len(g) for _, g in groups)
    cut = pool_groups is not None and len(groups) > pool_groups
    if cut:
        groups = groups[:pool_groups]
    pool = [seed] + [u for _, g in groups for u in g]
    rep = find_twins(w, pool) if quotient else {u: u for u in pool}
    if seated and quotient:
        rep = _refine_twins(rep, adhesion)           # G1-b (L-G1b-5): twins must also have the same adhesion to every particle
    qw = QWeights(w, rep) if quotient else w
    L = 1
    work0 = _Work(budget)
    start = fd.foundation_flat(rep[seed]) if seated else canon((rep[seed],) + (None,) * 6, 1)
    state = _settle(qw, [start], 1, work0, budget)   # L-63, L-70
    over_max = 1 if len(state) > budget.max_class else 0    # L-G4-47: verification only; _settle refuses such a class, so this stays 0
    size = 1
    counts: Dict[str, int] = {rep[seed]: 1}          # placed twins per label
    steps: List[Step] = []
    stop, broke = "exhausted", None
    ordered = group_insert == "ordered"
    order_log: List[Tuple[int, Tuple[str, ...]]] = []
    left_in_group = left_after = 0
    skip = on_collapse == "skip"
    skipped: List[Tuple[int, str, str]] = []
    first_skip_group = -1
    for gi, (share, members) in enumerate(groups):
        if max_groups is not None and gi >= max_groups:
            stop = "max_groups"
            break
        if ordered:                                          # F-1 / L-460, L-461
            seq = group_order(tier, seed, members, order == "reverse")
            order_log.append((share, seq))
            batches = [(u,) for u in seq]
        else:
            batches = [members]
        halted = False
        for bi, batch in enumerate(batches):
            L2 = min_L(size + len(batch) + nfound)
            bases = [extend(s, L, L2) if L2 > L else s for s in state]
            work = _Work(budget)
            try:
                starts = _insert_group(qw, bases, L2, [rep[u] for u in batch], work, budget)
                new = _settle(qw, starts, L2, work, budget)
            except _Over as e:
                bk = Step(share, batch, BUDGET, work.n, None, None, str(e))
                steps.append(bk)
                if skip:                                     # L-501: restore `state`, go on
                    if broke is None:
                        broke, first_skip_group = bk, gi
                    skipped.append((share, batch[0], str(e)))
                    if gi == first_skip_group:
                        left_in_group += 1
                    else:
                        left_after += 1
                    continue
                broke = bk
                stop = BUDGET                                # N-05: restore `state`
                if ordered:                                  # L-463
                    left_in_group = len(batches) - bi
                    left_after = sum(len(g) for _, g in groups[gi + 1:])
                halted = True
                break
            state, L, size = new, L2, size + len(batch)
            if len(new) > budget.max_class:                  # L-G4-47: verification only (must stay 0: _settle raises max_class first)
                over_max += 1
            for u in batch:
                counts[rep[u]] = counts.get(rep[u], 0) + 1
            steps.append(Step(share, batch, STABLE, work.n, size, len(new), None,
                              expanded_count(new, L, counts)))
        if halted:
            break
    score = score_flat(qw, state[0], L)
    a_num = None
    if seated:
        score, a_num = score[:2], score[2]
    # display names: the smallest PLACED unit of each class (a label, L-90)
    placed = {seed}
    for st in steps:
        if st.status == STABLE:
            placed.update(st.units)
    by_rep: Dict[str, List[str]] = {}
    for u in sorted(placed):
        by_rep.setdefault(rep[u], []).append(u)
    name = {r: us[0] for r, us in by_rep.items()}
    twin_sets = tuple(sorted(tuple(us) for us in by_rep.values() if len(us) > 1))
    if any(r != n for r, n in name.items()):
        state = tuple(sorted({canon(tuple(x if x is None or fd.is_constructed(x) else name[x] for x in f), L)
                              for f in state}, key=_flat_sort_key))
    tsets = {t[0]: t for t in twin_sets}
    cent = sorted({u for m in state for u in tsets.get(m[0], (m[0],))},
                  key=lambda c: ("", "") if c is None else (c, "x"))
    rep_cross = next(expand_flats(state[:1], L, twin_sets), state[0])
    if cut and stop == "exhausted":
        stop = "max_groups"
    return Placement(seed, to_cross(rep_cross, L), state, L, tuple(cent), size, size,
                     score, stop, broke, tuple(steps),
                     total_candidates, budget, twin_sets, quotient,
                     group_insert, order, tuple(order_log), left_in_group, left_after,
                     on_collapse, tuple(skipped),
                     *((fd.seats_sha(adhesion.spec), a_num) if seated else ()),
                     first_class_over_max=over_max)


class Placer:
    """On-demand placement with a cache (L-07): results never depend on the cache."""

    def __init__(self, tier: TierSpace, budget: Budget = Budget(), quotient: bool = True,
                 group_insert: str = "whole", order: str = "forward",
                 on_collapse: str = "stop", foundation: str = "off",
                 adhesion: Optional["fd.Adhesion"] = None) -> None:
        fd.check_foundation(foundation)
        if (foundation == "on") != (adhesion is not None):
            raise ValueError("an adhesion goes with foundation='on' and only with it")
        self.tier = tier
        self.budget = budget
        self.quotient = quotient
        self.group_insert = group_insert
        self.order = order
        self.on_collapse = on_collapse
        self.foundation = foundation
        self.adhesion = adhesion
        self.w = Weights(tier, adhesion)
        self._done: Dict[str, Placement] = {}

    def cross_for(self, seed: str) -> Placement:
        p = self._done.get(seed)
        if p is None:
            p = self._done[seed] = build_cross(self.tier, seed, self.w, budget=self.budget,
                                               quotient=self.quotient,
                                               group_insert=self.group_insert, order=self.order,
                                               on_collapse=self.on_collapse, foundation=self.foundation,
                                               adhesion=self.adhesion)
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


def observe_class(tier: TierSpace, placement: Placement,
                  queries: Iterable[Iterable[str]]) -> List[List[EnergyLog]]:
    """L-67: the energy changes under each query on EVERY member of the class
    (members in canonical order, then query order)."""
    qs = [tuple(q) for q in queries]
    return [[energy_log(tier, c, q) for q in qs] for c in placement.crosses()]
