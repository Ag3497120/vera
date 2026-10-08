"""G3-c: placement of one WINDOW cross with the PER-AXIS key (docs/LINE3_G3_SLIDING_PACKS.md 3.1, 3.4, 3.5, 6.1, 7.3).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md; the binding words, verbatim):
  OP-G3-1 「文ごとの 3 層パック。この文と次の文。1 文ずつ重ねて進む」   -> a window = sentence N + sentence N+1
  OP-G3-3 「x＝語順、y＝粒度、z＝スライド」                              -> the three axes, the arms +x -x +y -y +z -z
  OP-G3-4 「軸ごとに判定し、一致した軸がそれぞれラベル付きの答えを出す」 -> per-axis AGREEMENT of the three ratios (G3-d), not
           the key; the key below is the design's own recommendation (G3 3.4), no owner word fixes it (L-563); the record keeps
           its split by axis for every member (`axis_split_set`) so that a per-axis reading can be looked at later
  OP-G3-6 「梯子の順に x、y、z へ。重みは辺の流れと配置の結合と読む順に」 -> labels on the arms, weights in the record only
  G2 4   「基準のラベルは腕と一緒に動き、回転は全て「手」のまま」       -> rotations are moves; the labels sit on the arms
  F1     「文の語順で 1 つずつ入れ、崩れたら直前で止める」             -> insertion one unit at a time, stop before the collapse
  G3-a/b 「ちょうど良い数に後ろに仮の文を足してキリの良いところをつけて閉じるようにする」 -> padding sentence (constructed, not evidence)

What this module is.  The cross of ONE window at ONE tier (S1: RUN; the tier is a parameter).  Seats are the window's units;
the edge counts come from `slide.counts` (G3-b), so every number can be traced to the text.  Nothing is hooked into ask /
cycle / placement / matryoshka (placement.py is not modified, no existing output, cache name or test changes).

  arms     = +x -x +y -y +z -z in this order (geometry.AXES); the arm index IS the axis label (intrinsic).  A rotation moves
             the orientation only, so the labels move with the arms and the key never changes (L-565).
  key      = (sum over cross edges of n_a, sum over cross edges of omega_a), lexicographic, a = the axis of the edge's ARM
             (G3 3.4).  Per arm, an edge (outer o, inner i) weighs
               +x : (n_x(o,i), p(o,i))      o before i          -x : (n_x(o,i), p(i,o))      o after i
               +y : (n_y(o,i), 0)           o coarser than i    -y : (n_y(i,o), 0)
               +z : (n_z(o,i), n_z(o,i))    o in N, i in N+1    -z : (n_z(i,o), n_z(i,o))    o in N+1, i in N
             an empty seat weighs (0, 0).  Foundation weights (Fibonacci) are NOT in the key (I-G3-2); they are recorded.
  y arms   = in S1 the units are of ONE tier, y needs two tiers, so the y arms have no edges and no seats (L-G3-5, L-562).
  growth   = the first unit of sentence N at the centre; then one unit at a time, sentence N in word order, then sentence
             N+1 (a unit in both has its seat when N is read); each unit is inserted into EVERY member of the class
             (greedy, best-gain seats, ties branch), the results are settled (L-71) and the best-key class is kept; a unit
             that breaks the budget is restored away and growth stops (F1 stop, L-463).  The centre moves by search (I-02).
  padding  = "one": a constructed empty sentence after the last sentence of every article (flag `constructed`); it holds no
             unit, so it contributes no edge, no count and no seat; it is never evidence (L-566).
All numbers are int / Fraction.  No float, no randomness, nothing taken from a set or dict without an order.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import geometry as geo
from verantyx.line3 import slide as SL
from verantyx.line3.placement import (  # public pieces; _Layout / _Work / _Over are placement's own budget bookkeeping
    Budget, ZERO2, _Layout, _Over, _Work, budget_level, level_name, to_cross,
)

FORMAT = "line3.slide_place.v1"
ARM_NAMES: Tuple[str, ...] = geo.AXES                      # ("+x", "-x", "+y", "-y", "+z", "-z")
AXES: Tuple[str, ...] = SL.AXES                            # ("x", "y", "z")
PADDINGS: Tuple[str, ...] = ("none", "one")
MODES: Tuple[str, ...] = ("search", "line")
Score = Tuple[int, int]
Flat = Tuple[Optional[str], ...]                           # [centre, arm0 k=0..L-1, arm1 ..., ...]; arm i = ARM_NAMES[i]

KEY_TEXT = ("key = (sum over cross edges of n_a(o, i), sum over cross edges of omega_a(o, i)), lexicographic, a = the axis of the "
            "ARM the edge lies on; +x (n_x, p(o,i)), -x (n_x, p(i,o)), +y/-y (n_y, 0), +z (n_z(o,i), n_z(o,i)), "
            "-z (n_z(i,o), n_z(i,o)); an empty seat (0, 0); foundation weights are not in the key")
GROWTH_TEXT = ("first unit of sentence N at the centre; then one unit at a time: sentence N in word order, then sentence N+1 "
               "(first occurrence, a unit of both has its seat when N is read); inserted into every member of the class, "
               "settled, best-key class kept; the unit that breaks the budget is restored away and growth stops")
PADDING_TEXT = {"none": "no constructed sentence; the one-sentence windows are the slide spec's own lone rule",
                "one": "one constructed empty sentence after the last sentence of every article; flag constructed; "
                       "no unit, no edge, no count, never evidence"}


def _fk(f: Flat) -> Tuple[str, ...]:
    """Sort key of a state (a label for the bytes; no count and no winner reads it)."""
    return tuple("" if c is None else c for c in f)


# --------------------------------------------------------------------------------------------------------------
# arms, seats, layouts
# --------------------------------------------------------------------------------------------------------------
def arms_ok(y_seats: bool = False) -> Tuple[int, ...]:
    """Arm indices that have seats.  The y arms exist (they carry their labels) but in S1 hold nothing (L-G3-5)."""
    return tuple(a for a in range(geo.N_ARMS) if y_seats or ARM_NAMES[a][1] != "y")


def min_L(count: int, n_arms: int) -> int:
    """Smallest L with n_arms * L + 1 >= count (the centre plus n_arms arms of L seats; L-562)."""
    L = 1
    while n_arms * L + 1 < count:
        L += 1
    return L


_SEATS: Dict[Tuple[int, Tuple[int, ...]], Tuple[int, ...]] = {}
_EARM: Dict[int, Tuple[int, ...]] = {}


def seat_idx(L: int, arms: Tuple[int, ...]) -> Tuple[int, ...]:
    """Flat indices of the seats that may hold a unit: the centre and the seats of the arms that have seats (ascending)."""
    k = (L, arms)
    r = _SEATS.get(k)
    if r is None:
        r = _SEATS[k] = (0,) + tuple(1 + a * L + j for a in arms for j in range(L))
    return r


def _earm(L: int) -> Tuple[int, ...]:
    """The arm each edge of the layout lies on (the edge's OUTER seat is always on an arm)."""
    r = _EARM.get(L)
    if r is None:
        r = _EARM[L] = tuple((o - 1) // L for o, _i in _Layout(L).edges)
    return r


_LAY: Dict[int, _Layout] = {}


def _lay(L: int) -> _Layout:
    r = _LAY.get(L)
    if r is None:
        r = _LAY[L] = _Layout(L)
    return r


def extend_flat(flat: Flat, L: int, L2: int) -> Flat:
    """L-65 without the leg quotient: prepend empty OUTER seats to every arm (arms keep their labels and positions)."""
    pad = (None,) * (L2 - L)
    out: List[Optional[str]] = [flat[0]]
    for a in range(geo.N_ARMS):
        out.extend(pad + tuple(flat[1 + a * L: 1 + (a + 1) * L]))
    return tuple(out)


# --------------------------------------------------------------------------------------------------------------
# the per-axis weights of an edge
# --------------------------------------------------------------------------------------------------------------
class ArmWeights:
    """w(arm, outer, inner) -> (n, omega) of the key.  Built from the counts of ONE window at ONE tier (`from_counts`)
    or from a hand table (`from_table`, for toys).  Pure cache."""

    def __init__(self, fn) -> None:
        self._fn = fn
        self._c: Dict[Tuple[int, str, str], Score] = {}

    def __call__(self, arm: int, o: Optional[str], i: Optional[str]) -> Score:
        if o is None or i is None:
            return ZERO2
        k = (arm, o, i)
        v = self._c.get(k)
        if v is None:
            v = self._c[k] = self._fn(ARM_NAMES[arm], o, i)
        return v

    @staticmethod
    def from_counts(counts: SL.WindowCounts, tier: str) -> "ArmWeights":
        x, z = counts.x, counts.z

        def fn(arm: str, o: str, i: str) -> Score:
            if arm == "+x" or arm == "-x":
                b, a = x.get((tier, o, i), ((), ()))
                return (len(b) + len(a), len(b) if arm == "+x" else len(a))
            if arm == "+z":
                n = len(z.get((tier, o, tier, i), ()))
                return (n, n)
            if arm == "-z":
                n = len(z.get((tier, i, tier, o), ()))
                return (n, n)
            return ZERO2                                   # y: the pair is of one tier (L-G3-5)
        return ArmWeights(fn)

    @staticmethod
    def from_table(table: Mapping[Tuple[str, str, str], Score]) -> "ArmWeights":
        """table[(arm name, outer, inner)] = (n, omega); a missing key weighs (0, 0)."""
        return ArmWeights(lambda arm, o, i: table.get((arm, o, i), ZERO2))


def _add(a: Score, b: Score) -> Score:
    return (a[0] + b[0], a[1] + b[1])


def _sub(a: Score, b: Score) -> Score:
    return (a[0] - b[0], a[1] - b[1])


def _edge_sum(w: ArmWeights, flat: Sequence[Optional[str]], lay: _Layout, earm: Tuple[int, ...], es: Iterable[int]) -> Score:
    s = ZERO2
    for ei in es:
        o, i = lay.edges[ei]
        s = _add(s, w(earm[ei], flat[o], flat[i]))
    return s


def score_flat(w: ArmWeights, flat: Flat, L: int) -> Score:
    lay = _lay(L)
    return _edge_sum(w, flat, lay, _earm(L), range(len(lay.edges)))


def axis_key_flat(w: ArmWeights, flat: Flat, L: int) -> Tuple[Tuple[str, int, int], ...]:
    """The key split by axis: ((axis, sum n_a, sum omega_a), ...) in x, y, z order; the totals are the key."""
    lay, earm = _lay(L), _earm(L)
    acc = {a: ZERO2 for a in AXES}
    for ei, (o, i) in enumerate(lay.edges):
        a = ARM_NAMES[earm[ei]][1]
        acc[a] = _add(acc[a], w(earm[ei], flat[o], flat[i]))
    return tuple((a, acc[a][0], acc[a][1]) for a in AXES)


# --------------------------------------------------------------------------------------------------------------
# the class machinery (L-71 without the leg quotient and with arm-aware weights; L-561)
# --------------------------------------------------------------------------------------------------------------
def _swap_delta(w: ArmWeights, flat: Flat, lay: _Layout, earm: Tuple[int, ...], i: int, j: int) -> Score:
    es = tuple(lay.inc[i]) + tuple(x for x in lay.inc[j] if x not in lay.inc[i])
    old = _edge_sum(w, flat, lay, earm, es)
    f = list(flat)
    f[i], f[j] = f[j], f[i]
    return _sub(_edge_sum(w, f, lay, earm, es), old)


def _swapped(flat: Flat, i: int, j: int) -> Flat:
    f = list(flat)
    f[i], f[j] = f[j], f[i]
    return tuple(f)


def _scan(w: ArmWeights, s: Flat, L: int, idx: Tuple[int, ...]) -> Tuple[List[Flat], List[Flat], int]:
    """All single seat swaps of `s` over the seatable seats: (results of the best improving moves, results of the equal-key
    moves, moves tested).  A swap that would leave the centre empty is not a move (L-77)."""
    lay, earm = _lay(L), _earm(L)
    best = ZERO2
    best_moves: List[Tuple[int, int]] = []
    equal: Dict[Flat, None] = {}
    tested = 0
    for a in range(len(idx)):
        i = idx[a]
        for b in range(a + 1, len(idx)):
            j = idx[b]
            if s[i] == s[j]:
                continue
            if i == 0 and s[j] is None:
                continue
            tested += 1
            d = _swap_delta(w, s, lay, earm, i, j)
            if d > best:
                best, best_moves = d, [(i, j)]
            elif d == best and d > ZERO2:
                best_moves.append((i, j))
            elif d == ZERO2:
                equal[_swapped(s, i, j)] = None
    improved = sorted({_swapped(s, i, j): None for i, j in best_moves}, key=_fk)
    return improved, sorted(equal, key=_fk), tested


def _settle(w: ArmWeights, starts: Iterable[Flat], L: int, idx: Tuple[int, ...], work: _Work, budget: Budget) -> Tuple[Flat, ...]:
    """L-71: climb by all best improving swaps to the terminals of the best key, close them under equal-key swaps, climb again
    if the closure has an improving swap.  Raises placement._Over (max_states / max_moves / max_class)."""
    cur = sorted(set(starts), key=_fk)
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
                improved, _eq, t = _scan(w, s, L, idx)
                work.moves(t)
                if not improved:
                    terminals[s] = None
                else:
                    for x in improved:
                        if x not in seen:
                            nxt[x] = None
            level = sorted(nxt, key=_fk)
        kbest = max(score_flat(w, t, L) for t in terminals)
        comp: Dict[Flat, None] = {t: None for t in terminals if score_flat(w, t, L) == kbest}
        queue = sorted(comp, key=_fk)
        escapes: Dict[Flat, None] = {}
        qi = 0
        while qi < len(queue):
            s = queue[qi]
            qi += 1
            work.tick()
            improved, eq, t = _scan(w, s, L, idx)
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
            return tuple(sorted(comp, key=_fk))
        cur = sorted(escapes, key=_fk)


def _insert_one(w: ArmWeights, bases: Sequence[Flat], L: int, unit: str, idx: Tuple[int, ...],
                work: _Work, budget: Budget) -> List[Flat]:
    """L-64 for one unit: into EVERY base, at the empty seatable seats of best gain; ties branch (all kept)."""
    lay, earm = _lay(L), _earm(L)
    starts: Dict[Flat, None] = {}
    for st in sorted(bases, key=_fk):
        work.tick()
        empties = [e for e in idx if st[e] is None]
        work.moves(len(empties))
        best: Optional[Score] = None
        picks: List[int] = []
        for e in empties:
            g = ZERO2
            for ei in lay.inc[e]:
                o, i = lay.edges[ei]
                g = _add(g, w(earm[ei], unit if o == e else st[o], unit if i == e else st[i]))
            if best is None or g > best:
                best, picks = g, [e]
            elif g == best:
                picks.append(e)
        for e in picks:
            f = list(st)
            f[e] = unit
            starts[tuple(f)] = None
        if len(starts) > budget.max_states:
            raise _Over("max_states")
    return sorted(starts, key=_fk)


@dataclass(frozen=True)
class SStep:
    unit: str
    side: str                           # "this" | "next" | "both": the sentence(s) of the window that hold the unit
    status: str                         # "stable" | "budget"
    explored: int                       # distinct states handled
    size_after: Optional[int]
    class_size: Optional[int]
    reason: Optional[str] = None        # max_class | max_states | max_moves

    def doc(self) -> dict:
        return {"unit": self.unit, "side": self.side, "status": self.status, "explored": self.explored,
                "size_after": self.size_after, "class_size": self.class_size, "reason": self.reason}


@dataclass(frozen=True)
class Grown:
    L: int
    members: Tuple[Flat, ...]
    steps: Tuple[SStep, ...]
    stop: str                           # "exhausted" | "budget" | "empty"
    broke_on: Optional[SStep]
    left: Tuple[str, ...]               # units not inserted (the breaking one included)
    size: int


def grow(w: ArmWeights, order: Sequence[Tuple[str, str]], budget: Budget, arms: Tuple[int, ...]) -> Grown:
    """The F1 stop growth of one window cross.  `order` = ((unit, side), ...) in insertion order (distinct units)."""
    if len({u for u, _ in order}) != len(order):
        raise ValueError("a unit twice in the insertion order")
    if not order:
        return Grown(1, ((None,) * 7,), (), "empty", None, (), 0)
    L = 1
    state: Tuple[Flat, ...] = ((order[0][0],) + (None,) * 6,)           # L-77: the lone unit sits at the centre only
    size = 1
    steps: List[SStep] = [SStep(order[0][0], order[0][1], "stable", 0, 1, 1)]
    stop, broke, left = "exhausted", None, ()
    for pos in range(1, len(order)):
        u, side = order[pos]
        L2 = min_L(size + 1, len(arms))
        bases = [extend_flat(s, L, L2) if L2 > L else s for s in state]
        idx = seat_idx(L2, arms)
        work = _Work(budget)
        try:
            starts = _insert_one(w, bases, L2, u, idx, work, budget)
            new = _settle(w, starts, L2, idx, work, budget)
        except _Over as e:
            broke = SStep(u, side, "budget", work.n, None, None, str(e))
            steps.append(broke)
            stop, left = "budget", tuple(x for x, _ in order[pos:])
            break
        state, L, size = new, L2, size + 1
        steps.append(SStep(u, side, "stable", work.n, size, len(new)))
    return Grown(L, state, tuple(steps), stop, broke, left, size)


# --------------------------------------------------------------------------------------------------------------
# independent verification (I-05, L-74 for the per-axis key): geometry's edges / swap / rotate and the counts' accessors,
# not the search's flat layout or ArmWeights (L-564)
# --------------------------------------------------------------------------------------------------------------
def counts_weight_fn(counts: SL.WindowCounts, tier: str):
    """w(arm name, outer, inner) -> (n, omega) read through the WindowCounts accessors (the verifier's own route)."""
    def fn(arm: str, o: str, i: str) -> Score:
        if arm == "+x":
            return (counts.n_x(tier, o, i), counts.before_x(tier, o, i))
        if arm == "-x":
            return (counts.n_x(tier, o, i), counts.after_x(tier, o, i))
        if arm == "+z":
            n = counts.n_z(tier, o, tier, i)
            return (n, n)
        if arm == "-z":
            n = counts.n_z(tier, i, tier, o)
            return (n, n)
        return ZERO2
    return fn


def table_weight_fn(table: Mapping[Tuple[str, str, str], Score]):
    return lambda arm, o, i: table.get((arm, o, i), ZERO2)


def cross_key(wfn, cross: geo.Cross) -> Tuple[Score, Dict[str, Score]]:
    """Key of a Cross read from geometry.edges (outer, inner) and the seat's arm label: (total, {axis: part})."""
    tot = ZERO2
    per = {a: ZERO2 for a in AXES}
    for a, b in geo.edges(cross.L):
        o, i = cross.get(a), cross.get(b)
        if o is None or i is None:
            continue
        s = wfn(a.arm, str(o), str(i))
        tot = _add(tot, s)
        per[a.arm[1]] = _add(per[a.arm[1]], s)
    return tot, per


def _flat_of(cross: geo.Cross) -> Flat:
    out: List[Optional[str]] = [None if cross.center is None else str(cross.center)]
    for arm in cross.arms:
        out.extend(None if c is None else str(c) for c in arm)
    return tuple(out)


@dataclass(frozen=True)
class SlideFixedPointReport:
    rotations_tested: int               # the 23 non-identity rotations
    rotations_changing_key: int         # must be 0: the labels sit on the arms
    labels_follow_rotation: bool        # after every rotation the arm of label a points to r(g(a)) and holds the same cells
    swaps_total: int
    swaps_noop: int                     # equal contents
    swaps_improving: int                # must be 0
    swaps_equal_key_different: int
    is_fixed_point: bool


def _seat_ok(seat: geo.Seat, y_seats: bool) -> bool:
    return seat == geo.CENTER or y_seats or seat.arm[1] != "y"


def verify_fixed_point_slide(wfn, cross: geo.Cross, y_seats: bool = False) -> SlideFixedPointReport:
    """I-05 for the per-axis key: no rotation changes the key and no swap of two seatable seats improves it."""
    base, _ = cross_key(wfn, cross)
    rot_changed = 0
    follow = True
    for r in geo.moves_rotate():
        c2 = geo.rotate(cross, r)
        if cross_key(wfn, c2)[0] != base:
            rot_changed += 1
        world = c2.world_arms()
        for a in range(geo.N_ARMS):
            wdir = c2.orientation(a)                       # arm a (label ARM_NAMES[a]) points here
            if world[wdir] != cross.arms[a] or c2.arms[a] != cross.arms[a] or c2.orientation(a) != r(cross.orientation(a)):
                follow = False
    here = _flat_of(cross)
    total = noop = improving = 0
    plateau = set()
    for p, q in geo.moves_swap(cross.L):
        if not (_seat_ok(p, y_seats) and _seat_ok(q, y_seats)):
            continue
        total += 1
        if cross.get(p) == cross.get(q):
            noop += 1
            continue
        c2 = geo.swap(cross, p, q)
        if c2.center is None:
            continue                                       # L-77
        s2 = cross_key(wfn, c2)[0]
        if s2 > base:
            improving += 1
        elif s2 == base and _flat_of(c2) != here:
            plateau.add(_flat_of(c2))
    return SlideFixedPointReport(len(geo.moves_rotate()), rot_changed, follow, total, noop, improving, len(plateau),
                                 rot_changed == 0 and follow and improving == 0)


@dataclass(frozen=True)
class SlideClassReport:
    size: int
    one_key: bool                       # every member has the same total key
    members_fixed_points: bool
    closed: bool                        # every equal-key swap of a member stays in the class
    swaps_tested: int
    centres_nonempty: bool
    no_unit_on_unseatable_arm: bool
    labels_follow_rotation: bool
    is_stable_class: bool


def verify_class_slide(wfn, members: Sequence[geo.Cross], y_seats: bool = False) -> SlideClassReport:
    """L-70/L-74 for the per-axis key, independent of the search."""
    here = {_flat_of(c) for c in members}
    keys = {cross_key(wfn, c)[0] for c in members}
    base = next(iter(keys))
    fixed = closed = follow = True
    tested = 0
    for c in members:
        for p, q in geo.moves_swap(c.L):
            if not (_seat_ok(p, y_seats) and _seat_ok(q, y_seats)):
                continue
            if c.get(p) == c.get(q):
                continue
            c2 = geo.swap(c, p, q)
            if c2.center is None:
                continue
            tested += 1
            s2 = cross_key(wfn, c2)[0]
            if s2 > base:
                fixed = False
            elif s2 == base and _flat_of(c2) not in here:
                closed = False
        rep = verify_fixed_point_slide(wfn, c, y_seats) if c is members[0] else None
        if rep is not None:
            follow = rep.labels_follow_rotation
            if rep.rotations_changing_key:
                fixed = False
        elif any(cross_key(wfn, geo.rotate(c, r))[0] != base for r in geo.moves_rotate()):
            fixed = False
    nonempty = all(c.center is not None for c in members)
    free = all(c.get(s) is None for c in members for s in geo.seats(c.L) if not _seat_ok(s, y_seats))
    one = len(keys) == 1
    return SlideClassReport(len(here), one, fixed, closed, tested, nonempty, free, follow,
                            one and fixed and closed and nonempty and free and follow)


# --------------------------------------------------------------------------------------------------------------
# the spec of a placement (L-563): the slide spec's sha, the scope and everything the placement reads
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PlaceSpec:
    slide_spec_sha: str
    corpus_sha: str
    scope: str = "corpus"
    tier: str = "RUN"
    padding: str = "none"
    y_seats: bool = False
    mode: str = "search"
    budget: Budget = Budget()

    def __post_init__(self) -> None:
        if self.scope not in SL.SCOPES:
            raise ValueError("scope must be one of %r" % (SL.SCOPES,))
        if self.tier not in SL.TIERS:
            raise ValueError("tier must be one of %r" % (SL.TIERS,))
        if self.padding not in PADDINGS:
            raise ValueError("padding must be one of %r" % (PADDINGS,))
        if self.mode not in MODES:
            raise ValueError("mode must be one of %r" % (MODES,))

    def doc(self) -> dict:
        return {"format": FORMAT, "kind": "place_spec", "slide_spec_sha256": self.slide_spec_sha, "corpus_sha256": self.corpus_sha,
                "scope": self.scope, "tier": self.tier, "padding": self.padding, "padding_rule": PADDING_TEXT[self.padding],
                "y_arms": "seats" if self.y_seats else "no seats (one tier: no y edge exists)",
                "mode": self.mode, "key": KEY_TEXT, "growth": GROWTH_TEXT, "on_collapse": "stop",
                "budget": self.budget.to_json_obj(), "budget_level": level_name(self.budget)}

    def to_bytes(self) -> bytes:
        return SL.canonical(self.doc())

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()

    def short(self) -> str:
        """The 12 hex digits of a cache key (`_slideplace-<sha12>`)."""
        return self.sha256()[:12]


def make_spec(slide: SL.Slide, *, scope: str = "corpus", tier: str = "RUN", padding: str = "none", level: str = "mid",
              y_seats: bool = False, mode: str = "search") -> PlaceSpec:
    return PlaceSpec(slide.spec.sha256(), slide.spec.corpus_sha, scope, tier, padding, y_seats, mode, budget_level(level))


# --------------------------------------------------------------------------------------------------------------
# windows, with the padding switch (L-566)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PlaceWindow:
    window: SL.Window
    constructed: bool = False           # a constructed padding sentence follows (never evidence)
    pad: Optional[str] = None           # its name, "pad:<title>#<number>"; it has no text and no unit

    def doc(self) -> dict:
        return {"n": self.window.n, "title": self.window.title, "sids": list(self.window.sids), "idx": list(self.window.idx),
                "constructed": self.constructed, "pad": self.pad}


def place_windows(slide: SL.Slide, padding: str = "none") -> Tuple[PlaceWindow, ...]:
    """padding "none": slide.sequence() (the pairs and the slide spec's lone windows).  padding "one": the pairs and, for the
    last sentence of every article, a window (N, constructed padding sentence) -- the same units and counts as the lone window
    of that sentence, flagged constructed, so that every real sentence has a next-sentence window."""
    if padding not in PADDINGS:
        raise ValueError("padding must be one of %r" % (PADDINGS,))
    if padding == "none":
        return tuple(PlaceWindow(w) for w in slide.sequence())
    out = [PlaceWindow(w) for w in slide.pairs()]
    for w in slide.lasts():
        out.append(PlaceWindow(w, True, "pad:%s#%d" % (w.title, w.idx[-1] + 1)))
    return tuple(sorted(out, key=lambda p: (p.window.n, -len(p.window.sids))))


def padding_table(slide: SL.Slide) -> dict:
    """The open point 'what is a round number' in numbers (fulllead: counts of constructed sentences each reading would add).
    All read as: every real sentence gets a next-sentence window, then the count is rounded up as stated."""
    sizes = [len(a.sids) for a in slide.articles]
    n = sum(sizes)
    one = len(sizes)
    even = sum(1 if s % 2 == 1 else 2 for s in sizes)                  # one pad at least, then to an even article length
    four = sum(4 - (s % 4) if s % 4 != 0 else 4 for s in sizes)        # at least one pad, then up to a multiple of 4
    total = n + one
    to100 = (100 - total % 100) % 100
    return {"real_sentences": n, "articles": len(sizes),
            "one_per_article": {"pads": one, "total": n + one},
            "per_article_even": {"pads": even, "total": n + even},
            "per_article_multiple_of_4": {"pads": four, "total": n + four},
            "corpus_multiple_of_100_after_one_per_article": {"pads": one + to100, "total": total + to100},
            "corpus_multiple_of_100_alone": {"pads": (100 - n % 100) % 100, "total": n + (100 - n % 100) % 100,
                                             "note": "does not give every article's last sentence a next sentence"}}


# --------------------------------------------------------------------------------------------------------------
# insertion order and the placement record
# --------------------------------------------------------------------------------------------------------------
def insertion_order(slide: SL.Slide, window: SL.Window, tier: str) -> Tuple[Tuple[str, str], ...]:
    """Sentence N in word order (first occurrence of each distinct unit), then sentence N+1; a unit already read is skipped.
    side: "this" (only N), "next" (only N+1), "both"."""
    first = slide.space.tiers[tier].sentence_units[window.sids[0]]
    in_this = set(first)
    in_next = set(slide.space.tiers[tier].sentence_units[window.sids[1]]) if len(window.sids) == 2 else set()
    out: List[Tuple[str, str]] = []
    seen = set()
    for sid in window.sids:
        for u in slide.space.tiers[tier].sentence_units[sid]:
            if u in seen:
                continue
            seen.add(u)
            out.append((u, "both" if (u in in_this and u in in_next) else ("this" if u in in_this else "next")))
    return tuple(out)


@dataclass(frozen=True)
class NextSeat:
    """Did sentence N+1 get a seat?  (design 7.3, 6.4: if fewer than half of the 2-sentence windows, stop and report.)
    strict = a seated unit that is in N+1 and NOT in N; loose = a seated unit that is in N+1 (shared units included)."""
    exclusive_units: int                # units only in N+1 (what could be strict)
    exclusive_seated: int
    loose_units: int                    # units in N+1
    loose_seated: int

    @property
    def strict(self) -> bool:
        return self.exclusive_seated > 0

    @property
    def loose(self) -> bool:
        return self.loose_seated > 0

    def doc(self) -> dict:
        return {"exclusive_units": self.exclusive_units, "exclusive_seated": self.exclusive_seated, "strict": self.strict,
                "loose_units": self.loose_units, "loose_seated": self.loose_seated, "loose": self.loose}


def next_seat(order: Sequence[Tuple[str, str]], seated: Iterable[str]) -> NextSeat:
    s = set(seated)
    ex = [u for u, side in order if side == "next"]
    lo = [u for u, side in order if side in ("next", "both")]
    return NextSeat(len(ex), sum(1 for u in ex if u in s), len(lo), sum(1 for u in lo if u in s))


@dataclass(frozen=True)
class SlidePlacement:
    spec_sha: str                       # the PlaceSpec sha (includes the scope and the slide spec sha)
    slide_spec_sha: str
    scope: str
    tier: str
    mode: str
    window: PlaceWindow
    arm_labels: Tuple[Tuple[str, str], ...]                 # (arm, foundation particle) in arm order
    arm_weights: Tuple[Tuple[str, Fraction], ...]           # (arm, Fibonacci weight): recorded, not in the key
    seatless_arms: Tuple[str, ...]                          # arms that exist and hold no seat (the y arms in S1)
    L: int
    members: Tuple[Flat, ...]
    centres: Tuple[str, ...]
    size: int
    key: Score
    axis_key: Tuple[Tuple[str, int, int], ...]              # of the representative
    axis_splits: int                                        # distinct per-axis splits over the class (same total key)
    axis_split_set: Tuple[Tuple[int, ...], ...]             # (x n, x omega, y n, y omega, z n, z omega, members), sorted
    order_log: Tuple[Tuple[str, str], ...]
    steps: Tuple[SStep, ...]
    stop: str
    broke_on: Optional[SStep]
    left: Tuple[str, ...]
    budget: Budget
    z_self: Tuple[Tuple[str, int], ...]                     # seated units with n_z(u, u) > 0: counted, but a unit has one seat
    next_seat: Optional[NextSeat]                           # None for a one-sentence window (nothing to seat)

    @property
    def class_size(self) -> int:
        return len(self.members)

    @property
    def cross(self) -> geo.Cross:
        return to_cross(self.members[0], self.L)

    def crosses(self) -> Tuple[geo.Cross, ...]:
        return tuple(to_cross(m, self.L) for m in self.members)

    def doc(self, members: bool = True) -> dict:
        cls = SL.canonical([list(m) for m in self.members])
        d = {"format": FORMAT, "kind": "slide_place", "spec_sha256": self.spec_sha, "slide_spec_sha256": self.slide_spec_sha,
             "scope": self.scope, "tier": self.tier, "mode": self.mode, "window": self.window.doc(),
             "padding": {"constructed": self.window.constructed, "sentence": self.window.pad, "evidence": False,
                         "contributes": "no unit, no edge, no count, no seat"},
             "axis_labels": {a: l for a, l in self.arm_labels}, "arm_weights": {a: w for a, w in self.arm_weights},
             "weights_in_key": False, "seatless_arms": list(self.seatless_arms),
             "L": self.L, "size": self.size, "centres": list(self.centres), "key": list(self.key),
             "axis_key": {a: [n, o] for a, n, o in self.axis_key}, "axis_splits": self.axis_splits,
             "axis_split_set": [list(t) for t in self.axis_split_set],
             "class_size": self.class_size, "class_sha256": hashlib.sha256(cls).hexdigest(),
             "order_log": [[u, s] for u, s in self.order_log],
             "steps": [s.doc() for s in self.steps], "stop": self.stop,
             "broke_on": None if self.broke_on is None else self.broke_on.doc(), "left": list(self.left),
             "budget": self.budget.to_json_obj(), "budget_level": level_name(self.budget),
             "z_self": [[u, n] for u, n in self.z_self],
             "next_seat": None if self.next_seat is None else self.next_seat.doc()}
        if members:
            d["members"] = [list(m) for m in self.members]
        return d

    def to_bytes(self) -> bytes:
        return SL.canonical(self.doc(True))


def _finish(spec: PlaceSpec, slide: SL.Slide, pw: PlaceWindow, counts: SL.WindowCounts, w: ArmWeights, arms: Tuple[int, ...],
            order: Sequence[Tuple[str, str]], g: Grown) -> SlidePlacement:
    members = tuple(sorted(g.members, key=_fk))
    rep = members[0]
    seated = sorted(u for u in rep if u is not None)
    cent = tuple(sorted({m[0] for m in members if m[0] is not None}))
    akey = axis_key_flat(w, rep, g.L) if g.size else tuple((a, 0, 0) for a in AXES)
    split_n: Dict[Tuple[int, ...], int] = {}
    for m in members:                                    # an empty window: one member, all zeros
        t = tuple(v for _a, n, o in axis_key_flat(w, m, g.L) for v in (n, o))
        split_n[t] = split_n.get(t, 0) + 1
    split_set = tuple(sorted(t + (c,) for t, c in split_n.items()))
    splits = len(split_set)
    ns = next_seat(order, seated) if len(pw.window.sids) == 2 else None
    zself = tuple((u, counts.n_z(spec.tier, u, spec.tier, u)) for u in seated if counts.n_z(spec.tier, u, spec.tier, u) > 0)
    fnd = slide.spec.foundation
    return SlidePlacement(
        spec.sha256(), slide.spec.sha256(), spec.scope, spec.tier, spec.mode, pw,
        tuple(fnd.arms), tuple((a, fnd.arm_weight(a)) for a in ARM_NAMES),
        tuple(ARM_NAMES[a] for a in range(geo.N_ARMS) if a not in arms), g.L, members, cent, g.size,
        score_flat(w, rep, g.L) if g.size else ZERO2, akey, splits, split_set, tuple(order), g.steps, g.stop, g.broke_on, g.left,
        spec.budget, zself, ns)


def _line_arrangement(order: Sequence[Tuple[str, str]]) -> Optional[Tuple[int, Flat]]:
    """L-G3-6, the diagnostic LINE (no search): sentence N laid along the x axis through the centre by its word order
    (the centre is the lower middle unit; +x holds the units before it, outward in reverse order; -x the units after it), the
    units only in N+1 laid along -z in their word order, the first next to the centre.  Returns (L, flat) or None."""
    this = [u for u, s in order if s in ("this", "both")]
    nxt = [u for u, s in order if s == "next"]
    if not this:
        this, nxt = nxt, []
    if not this:
        return None
    m = (len(this) - 1) // 2
    plus = list(reversed(this[:m]))                          # outward from the centre: the units before it
    minus = this[m + 1:]
    L = max(1, len(plus), len(minus), len(nxt))
    legs: Dict[int, List[str]] = {0: plus, 1: minus, 5: nxt}
    flat: List[Optional[str]] = [this[m]]
    for a in range(geo.N_ARMS):
        out = legs.get(a, [])
        flat.extend((None,) * (L - len(out)) + tuple(reversed(out)))
    return L, tuple(flat)


def place_window(slide: SL.Slide, pw: PlaceWindow, spec: PlaceSpec) -> SlidePlacement:
    """Place the cross of one window (mode "search": the growth above; mode "line": the diagnostic line, no search)."""
    if spec.slide_spec_sha != slide.spec.sha256() or spec.corpus_sha != slide.spec.corpus_sha:
        raise ValueError("the place spec was made for another slide spec / corpus")
    counts = slide.counts(pw.window, spec.scope)
    w = ArmWeights.from_counts(counts, spec.tier)
    arms = arms_ok(spec.y_seats)
    order = insertion_order(slide, pw.window, spec.tier)
    if spec.mode == "line":
        la = _line_arrangement(order)
        if la is None:
            g = Grown(1, ((None,) * 7,), (), "empty", None, (), 0)
        else:
            L, flat = la
            g = Grown(L, (flat,), (), "line", None, (), sum(1 for c in flat if c is not None))
    else:
        g = grow(w, order, spec.budget, arms)
    return _finish(spec, slide, pw, counts, w, arms, order, g)
