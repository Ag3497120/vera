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

G3-c2 (L-580..; docs/LINE3_LOCAL_DECISIONS.md "G3-c2"): the owner's decisions after G3-c are spec switches, the G3-c behaviour is one
named configuration (`LEGACY`) and stays byte-identical:
  stability        "sum" (G3-c: the summed key decides) | "per_axis" (the key of each axis x, y, z decides separately; Pareto)
  seat_key         "unit" (G3-c: one seat per unit) | "unit_sid" (a unit in both sentences of a window has two seats, one per sentence)
  seat_empty_axis  "allow" (G3-c) | "deny" (an arm of an axis with no evidence in the window has no seats)
  growth           "n_then_n1" (G3-c) | "interleave" | "z_reserved" (x arms take sentence-N seats, z arms sentence-N+1 seats)
The module defaults are the owner's configuration (per_axis, unit_sid, allow, z_reserved); the low-level functions (`grow`,
`verify_*`) default to the G3-c behaviour so that the G3-c hand tables read unchanged.
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
STABILITIES: Tuple[str, ...] = ("sum", "per_axis")
SEAT_KEYS: Tuple[str, ...] = ("unit", "unit_sid")
SEAT_EMPTY: Tuple[str, ...] = ("allow", "deny")
GROWTHS: Tuple[str, ...] = ("n_then_n1", "interleave", "z_reserved")
LEGACY: Dict[str, str] = {"stability": "sum", "seat_key": "unit", "seat_empty_axis": "allow", "growth": "n_then_n1"}
DEFAULTS: Dict[str, str] = {"stability": "per_axis", "seat_key": "unit_sid", "seat_empty_axis": "allow", "growth": "z_reserved"}
SEP = "\x00"                                               # a seat token of a unit in both sentences: unit + SEP + sid
Score = Tuple[int, int]
Vec = Tuple[int, int, int, int, int, int]                  # (n_x, omega_x, n_y, omega_y, n_z, omega_z): the key split by axis
ZERO6: Vec = (0, 0, 0, 0, 0, 0)
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
STABILITY_TEXT = {
    "sum": "the summed key (sum n_a, sum omega_a) decides: a move improves when it raises it (G3-c, L-563)",
    "per_axis": "the key of each axis (n_a, omega_a), a = x, y, z, is its own: a move is improving when no axis falls and one "
                "rises (each axis compared lexicographically), equal when no axis changes, otherwise neither; a state is a fixed "
                "point when it has no improving move; the best classes are the closed classes whose per-axis key no other "
                "closed class's dominates (several incomparable keys may stay); the summed key is recorded, not read"}
SEAT_KEY_TEXT = {
    "unit": "one seat per unit; a unit of both sentences is seated when N is read (G3-c)",
    "unit_sid": "a seat is (unit, sentence): a unit in both sentences of the window has two seats, linked by the z self-edge "
                "n_z(u, u); every seat has its own sentence and provenance"}
SEAT_EMPTY_TEXT = {
    "allow": "an arm whose axis has no evidence in the window may hold seats (G3-c)",
    "deny": "an arm whose axis has no evidence in the window (no x / y / z count for the tier) has no seats"}
GROWTH_TEXTS = {
    "n_then_n1": GROWTH_TEXT,
    "interleave": "first unit of sentence N at the centre; then N's first, N+1's first, N's second, N+1's second, ... "
                  "(each sentence in word order; the shorter one runs out first); a unit already seated is skipped (seats=unit)",
    "z_reserved": "as n_then_n1, and the x arms take only sentence-N seats, the z arms only sentence-N+1 seats (y arms "
                  "unchanged, the centre any); the reservation binds insertion and every swap; the arm length grows until the "
                  "reserved arms hold their sentence"}


def _fk(f: Flat) -> Tuple[str, ...]:
    """Sort key of a state (a label for the bytes; no count and no winner reads it)."""
    return tuple("" if c is None else c for c in f)


# --------------------------------------------------------------------------------------------------------------
# arms, seats, layouts
# --------------------------------------------------------------------------------------------------------------
def arms_ok(y_seats: bool = False) -> Tuple[int, ...]:
    """Arm indices that have seats.  The y arms exist (they carry their labels) but in S1 hold nothing (L-G3-5)."""
    return tuple(a for a in range(geo.N_ARMS) if y_seats or ARM_NAMES[a][1] != "y")


def min_L(count: int, n_arms: int) -> Optional[int]:
    """Smallest L with n_arms * L + 1 >= count (the centre plus n_arms arms of L seats; L-562).  None when no arm has seats
    and count > 1 (L-581: a denied window can have only its centre)."""
    if n_arms == 0:
        return 1 if count <= 1 else None
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
            o, i = unit_of(o), unit_of(i)                    # a seat token (unit, sentence) weighs as its unit (L-584)
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
# seat tokens and the seating policy (L-580, L-583, L-584)
# --------------------------------------------------------------------------------------------------------------
def unit_of(token: str) -> str:
    """The unit of a seat token: the token itself, or the part before SEP (a unit in both sentences has two tokens)."""
    return token.split(SEP, 1)[0]


def _axis_arms(arms: Sequence[int], axis: str) -> int:
    return sum(1 for a in arms if ARM_NAMES[a][1] == axis)


class Policy:
    """Which arms hold seats (`arms`: the y arms without y_seats, the arms of a denied axis removed) and, under growth
    "z_reserved", which token may sit where: a token of sentence N (side "this") on the centre and the x / y arms, a token of
    sentence N+1 (side "next") on the centre and the z / y arms, a token of both (side "both", seats="unit") anywhere.
    `sides` = {token: side}.  Without z_reserved every token may sit on every seatable seat (the G3-c rule)."""

    def __init__(self, arms: Tuple[int, ...], z_reserved: bool = False, sides: Optional[Mapping[str, str]] = None) -> None:
        self.arms = tuple(arms)
        self.z_reserved = z_reserved
        self.sides = dict(sides or {})
        self._ok: Dict[Tuple[str, int], frozenset] = {}

    @property
    def free(self) -> bool:
        return not self.z_reserved

    def arm_ok(self, token: str, arm: int) -> bool:
        if arm not in self.arms:
            return False
        if not self.z_reserved:
            return True
        ax, side = ARM_NAMES[arm][1], self.sides.get(token, "both")
        return ax == "y" or (ax == "x" and side in ("this", "both")) or (ax == "z" and side in ("next", "both"))

    def allowed(self, token: str, L: int) -> frozenset:
        """Flat indices where `token` may sit (the centre included)."""
        k = (token, L)
        r = self._ok.get(k)
        if r is None:
            r = self._ok[k] = frozenset((0,) + tuple(1 + a * L + j for a in self.arms if self.arm_ok(token, a) for j in range(L)))
        return r

    def capacity_ok(self, L: int, na: int, nb: int, nc: int) -> bool:
        """Is there an assignment of na tokens of side "this", nb of "next", nc of "both" to the seats of arm length L?
        (Hall's conditions; the centre takes any token.)"""
        C, X, Y, Z = 1, L * _axis_arms(self.arms, "x"), L * _axis_arms(self.arms, "y"), L * _axis_arms(self.arms, "z")
        if not self.z_reserved:
            return na + nb + nc <= C + X + Y + Z
        return na <= C + X + Y and nb <= C + Z + Y and na + nb + nc <= C + X + Y + Z

    def need_L(self, L: int, counts: Tuple[int, int, int], bound: int) -> Optional[int]:
        """The smallest L' >= L whose capacity holds the counts, or None (no L' <= bound does)."""
        while L <= bound:
            if self.capacity_ok(L, *counts):
                return L
            L += 1
        return None


# ---- the key split by axis, as a 6-vector; the per-axis order -------------------------------------------------------
def _vadd(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3], a[4] + b[4], a[5] + b[5])


def _vsub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3], a[4] - b[4], a[5] - b[5])


def _vsum(v: Vec) -> Score:
    """The summed key of a split (recorded; not read by the per-axis decision)."""
    return (v[0] + v[2] + v[4], v[1] + v[3] + v[5])


def _vflags(d: Vec) -> Tuple[bool, bool]:
    """(some axis improves, some axis worsens) for a DELTA: an axis improves when its (n, omega) delta is > (0, 0)
    lexicographically."""
    pos = neg = False
    for a in (0, 2, 4):
        p = (d[a], d[a + 1])
        if p > ZERO2:
            pos = True
        elif p < ZERO2:
            neg = True
    return pos, neg


def _vdom(a: Vec, b: Vec) -> bool:
    """a dominates b: every axis of a is >= that of b (lexicographic on (n, omega)) and a != b."""
    if a == b:
        return False
    return (a[0], a[1]) >= (b[0], b[1]) and (a[2], a[3]) >= (b[2], b[3]) and (a[4], a[5]) >= (b[4], b[5])


def _maximal(vs: Iterable[Vec]) -> List[Vec]:
    u = sorted(set(vs))
    return [v for v in u if not any(_vdom(o, v) for o in u)]


def _edge_vec(w: "ArmWeights", flat: Sequence[Optional[str]], lay: _Layout, earm: Tuple[int, ...], es: Iterable[int]) -> Vec:
    acc = [0, 0, 0, 0, 0, 0]
    for ei in es:
        o, i = lay.edges[ei]
        a = earm[ei]
        n, om = w(a, flat[o], flat[i])
        acc[a // 2 * 2] += n
        acc[a // 2 * 2 + 1] += om
    return (acc[0], acc[1], acc[2], acc[3], acc[4], acc[5])


def score_vec(w: "ArmWeights", flat: Flat, L: int) -> Vec:
    lay = _lay(L)
    return _edge_vec(w, flat, lay, _earm(L), range(len(lay.edges)))


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


def _swap_legal(pol: Policy, s: Flat, L: int, i: int, j: int) -> bool:
    """A swap may not put a token on a seat the policy denies it (growth z_reserved); an empty seat takes anything."""
    return (s[i] is None or j in pol.allowed(s[i], L)) and (s[j] is None or i in pol.allowed(s[j], L))


def _scan(w: ArmWeights, s: Flat, L: int, idx: Tuple[int, ...], pol: Optional[Policy] = None) -> Tuple[List[Flat], List[Flat], int]:
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
            if pol is not None and not pol.free and not _swap_legal(pol, s, L, i, j):
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


def _settle(w: ArmWeights, starts: Iterable[Flat], L: int, idx: Tuple[int, ...], work: _Work, budget: Budget,
            pol: Optional[Policy] = None) -> Tuple[Flat, ...]:
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
                improved, _eq, t = _scan(w, s, L, idx, pol)
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
            improved, eq, t = _scan(w, s, L, idx, pol)
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
                work: _Work, budget: Budget, pol: Optional[Policy] = None) -> List[Flat]:
    """L-64 for one unit: into EVERY base, at the empty seatable seats of best gain; ties branch (all kept)."""
    lay, earm = _lay(L), _earm(L)
    starts: Dict[Flat, None] = {}
    for st in sorted(bases, key=_fk):
        work.tick()
        empties = [e for e in idx if st[e] is None]
        if pol is not None and not pol.free:
            ok = pol.allowed(unit, L)
            empties = [e for e in empties if e in ok]
        work.moves(len(empties))
        if not empties:
            raise _Over("no_seat")
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


# ---- the per-axis search (L-582): a move is improving when no axis worsens and one improves (Pareto) -------------------
def _swap_dvec(w: ArmWeights, flat: Flat, lay: _Layout, earm: Tuple[int, ...], i: int, j: int) -> Vec:
    es = tuple(lay.inc[i]) + tuple(x for x in lay.inc[j] if x not in lay.inc[i])
    old = _edge_vec(w, flat, lay, earm, es)
    f = list(flat)
    f[i], f[j] = f[j], f[i]
    return _vsub(_edge_vec(w, f, lay, earm, es), old)


def _scan_pa(w: ArmWeights, s: Flat, L: int, idx: Tuple[int, ...], pol: Optional[Policy] = None) -> Tuple[List[Flat], List[Flat], int]:
    """Per-axis `_scan`: (results of the improving moves whose axis-delta is not dominated by another improving move's, results
    of the moves that change no axis, moves tested).  Improving = some axis improves and none worsens; a move that improves one
    axis and worsens another is neither improving nor equal."""
    lay, earm = _lay(L), _earm(L)
    imp: List[Tuple[Vec, int, int]] = []
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
            if pol is not None and not pol.free and not _swap_legal(pol, s, L, i, j):
                continue
            tested += 1
            d = _swap_dvec(w, s, lay, earm, i, j)
            pos, neg = _vflags(d)
            if pos and not neg:
                imp.append((d, i, j))
            elif not pos and not neg:
                equal[_swapped(s, i, j)] = None
    top = set(_maximal(d for d, _i, _j in imp))
    improved = sorted({_swapped(s, i, j): None for d, i, j in imp if d in top}, key=_fk)
    return improved, sorted(equal, key=_fk), tested


def _settle_pa(w: ArmWeights, starts: Iterable[Flat], L: int, idx: Tuple[int, ...], work: _Work, budget: Budget,
               pol: Optional[Policy] = None) -> Tuple[Flat, ...]:
    """Per-axis L-71: climb by the improving moves, keep the terminals whose axis-key is not dominated by another terminal's
    (the class may hold several incomparable keys), close each key's terminals under the moves that change no axis, climb again
    from the improving escapes of a class that has any.  The result is the union of the closed classes whose key is not
    dominated by another closed class's.  Raises placement._Over (max_states / max_moves / max_class)."""
    cur = sorted(set(starts), key=_fk)
    stable: Dict[Vec, Dict[Flat, None]] = {}
    while cur:
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
                improved, _eq, t = _scan_pa(w, s, L, idx, pol)
                work.moves(t)
                if not improved:
                    terminals[s] = None
                else:
                    for x in improved:
                        if x not in seen:
                            nxt[x] = None
            level = sorted(nxt, key=_fk)
        tk = {t: score_vec(w, t, L) for t in terminals}
        pending: Dict[Flat, None] = {}
        for k in _maximal(tk.values()):
            comp: Dict[Flat, None] = {t: None for t in sorted(terminals, key=_fk) if tk[t] == k}
            queue = list(comp)
            escapes: Dict[Flat, None] = {}
            qi = 0
            while qi < len(queue):
                s = queue[qi]
                qi += 1
                work.tick()
                improved, eq, t = _scan_pa(w, s, L, idx, pol)
                work.moves(t)
                for x in improved:
                    escapes[x] = None
                for x in eq:
                    if x not in comp:
                        comp[x] = None
                        queue.append(x)
                        if len(comp) > budget.max_class:
                            raise _Over("max_class")
            if escapes:
                pending.update(escapes)
            else:
                stable.setdefault(k, {}).update(comp)
        cur = sorted(pending, key=_fk)
    keep = _maximal(stable)
    out: Dict[Flat, None] = {}
    for k in keep:
        out.update(stable[k])
    return tuple(sorted(out, key=_fk))


def _insert_one_pa(w: ArmWeights, bases: Sequence[Flat], L: int, unit: str, idx: Tuple[int, ...],
                   work: _Work, budget: Budget, pol: Optional[Policy] = None) -> List[Flat]:
    """Per-axis L-64 for one token: into EVERY base, at the empty allowed seats whose gain (a 6-vector) is not dominated by
    another seat's; ties branch (all kept)."""
    lay, earm = _lay(L), _earm(L)
    starts: Dict[Flat, None] = {}
    for st in sorted(bases, key=_fk):
        work.tick()
        empties = [e for e in idx if st[e] is None]
        if pol is not None and not pol.free:
            ok = pol.allowed(unit, L)
            empties = [e for e in empties if e in ok]
        work.moves(len(empties))
        if not empties:
            raise _Over("no_seat")
        gains: Dict[int, Vec] = {}
        for e in empties:
            tmp = list(st)
            tmp[e] = unit
            gains[e] = _edge_vec(w, tmp, lay, earm, lay.inc[e])
        top = set(_maximal(gains.values()))
        for e in empties:
            if gains[e] in top:
                f = list(st)
                f[e] = unit
                starts[tuple(f)] = None
        if len(starts) > budget.max_states:
            raise _Over("max_states")
    return sorted(starts, key=_fk)


def tradeoff_counts(w: ArmWeights, flat: Flat, L: int, arms: Tuple[int, ...], pol: Optional[Policy] = None) -> dict:
    """Diagnostic of one arrangement (L-582): the single moves that are NOT Pareto-improving but improve some axis while another
    worsens, counted per axis improved ("the strict reading would take these"), and the Pareto-improving moves (0 in a fixed
    point)."""
    lay, earm = _lay(L), _earm(L)
    idx = seat_idx(L, arms)
    per = {a: 0 for a in AXES}
    both = pareto = tested = 0
    for a in range(len(idx)):
        i = idx[a]
        for b in range(a + 1, len(idx)):
            j = idx[b]
            if flat[i] == flat[j] or (i == 0 and flat[j] is None):
                continue
            if pol is not None and not pol.free and not _swap_legal(pol, flat, L, i, j):
                continue
            tested += 1
            d = _swap_dvec(w, flat, lay, earm, i, j)
            pos, neg = _vflags(d)
            if pos and neg:
                both += 1
                for k, ax in enumerate(AXES):
                    if (d[2 * k], d[2 * k + 1]) > ZERO2:
                        per[ax] += 1
            elif pos:
                pareto += 1
    return {"moves_tested": tested, "improve_one_worsen_another": both, "improved_axis": per, "pareto_improving": pareto}


@dataclass(frozen=True)
class SStep:
    unit: str
    side: str                           # "this" | "next" | "both": the sentence(s) of the window that hold the unit
    status: str                         # "stable" | "budget"
    explored: int                       # distinct states handled
    size_after: Optional[int]
    class_size: Optional[int]
    reason: Optional[str] = None        # max_class | max_states | max_moves | no_seat
    sid: Optional[int] = None           # seats="unit_sid": the sentence of the seat (None under seats="unit": the unit's)

    def doc(self) -> dict:
        d = {"unit": self.unit, "side": self.side, "status": self.status, "explored": self.explored,
             "size_after": self.size_after, "class_size": self.class_size, "reason": self.reason}
        if self.sid is not None:
            d["sid"] = self.sid
        return d


@dataclass(frozen=True)
class Grown:
    L: int
    members: Tuple[Flat, ...]
    steps: Tuple[SStep, ...]
    stop: str                           # "exhausted" | "budget" | "empty"
    broke_on: Optional[SStep]
    left: Tuple[str, ...]               # units not inserted (the breaking one included)
    size: int


def grow(w: ArmWeights, order: Sequence[Tuple[str, str]], budget: Budget, arms: Tuple[int, ...], *,
         stability: str = "sum", z_reserved: bool = False, info: Optional[Mapping[str, Tuple[str, int]]] = None) -> Grown:
    """The F1 stop growth of one window cross.  `order` = ((token, side), ...) in insertion order (distinct tokens); a token is
    a unit (seats="unit") or unit + SEP + sid (a unit of both sentences under seats="unit_sid"); `info` = {token: (unit, sid)}
    labels the steps and `left`.  Defaults = the G3-c behaviour (stability "sum", no reservation)."""
    if stability not in STABILITIES:
        raise ValueError("stability must be one of %r" % (STABILITIES,))
    if len({u for u, _ in order}) != len(order):
        raise ValueError("a unit twice in the insertion order")
    if not order:
        return Grown(1, ((None,) * 7,), (), "empty", None, (), 0)

    def lab(tok: str) -> Tuple[str, Optional[int]]:
        return info[tok] if info is not None else (tok, None)

    pol = Policy(arms, z_reserved, {t: sd for t, sd in order})
    insert, settle = (_insert_one_pa, _settle_pa) if stability == "per_axis" else (_insert_one, _settle)
    L = 1
    t0, s0 = order[0]
    state: Tuple[Flat, ...] = ((t0,) + (None,) * 6,)                    # L-77: the lone unit sits at the centre only
    size = 1
    typ = {"this": 0, "next": 0, "both": 0}
    typ[s0] += 1
    steps: List[SStep] = [SStep(lab(t0)[0], s0, "stable", 0, 1, 1, None, lab(t0)[1])]
    stop, broke, left = "exhausted", None, ()
    bound = len(order) + 2
    for pos in range(1, len(order)):
        u, side = order[pos]
        typ2 = dict(typ)
        typ2[side] += 1
        work = _Work(budget)
        try:
            if pol.free:
                L2 = min_L(size + 1, len(arms))
                if L2 is None:
                    raise _Over("no_seat")
                L2 = max(L2, L)
            else:
                L2 = pol.need_L(L, (typ2["this"], typ2["next"], typ2["both"]), bound)
                if L2 is None:
                    raise _Over("no_seat")
            while True:
                bases = [extend_flat(s, L, L2) if L2 > L else s for s in state]
                if pol.free:
                    break
                ok = pol.allowed(u, L2)
                if all(any(st[e] is None for e in ok) for st in bases):
                    break
                L2 += 1
                if L2 > bound:
                    raise _Over("no_seat")
            idx = seat_idx(L2, arms)
            starts = insert(w, bases, L2, u, idx, work, budget, pol)
            new = settle(w, starts, L2, idx, work, budget, pol)
        except _Over as e:
            broke = SStep(lab(u)[0], side, "budget", work.n, None, None, str(e), lab(u)[1])
            steps.append(broke)
            stop, left = "budget", tuple(lab(x)[0] for x, _ in order[pos:])
            break
        state, L, size, typ = new, L2, size + 1, typ2
        steps.append(SStep(lab(u)[0], side, "stable", work.n, size, len(new), None, lab(u)[1]))
    return Grown(L, state, tuple(steps), stop, broke, left, size)


# --------------------------------------------------------------------------------------------------------------
# independent verification (I-05, L-74 for the per-axis key): geometry's edges / swap / rotate and the counts' accessors,
# not the search's flat layout or ArmWeights (L-564)
# --------------------------------------------------------------------------------------------------------------
def counts_weight_fn(counts: SL.WindowCounts, tier: str):
    """w(arm name, outer, inner) -> (n, omega) read through the WindowCounts accessors (the verifier's own route).  Seat tokens
    of seats="unit_sid" are read as their units."""
    def fn(arm: str, o: str, i: str) -> Score:
        o, i = unit_of(o), unit_of(i)
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


def _pareto_better(new: Mapping[str, Score], old: Mapping[str, Score]) -> bool:
    """Every axis of `new` is >= that of `old` (lexicographic on (n, omega)) and one is >.  Written on the per-axis dicts."""
    return all(new[a] >= old[a] for a in AXES) and any(new[a] > old[a] for a in AXES)


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
    swaps_improving: int                # must be 0 (sum: the summed key rises; per_axis: Pareto, see `stability`)
    swaps_equal_key_different: int
    is_fixed_point: bool
    stability: str = "sum"
    swaps_tradeoff: int = 0             # per_axis: swaps that improve one axis and worsen another (neither improving nor equal)


def _seat_ok(seat: geo.Seat, y_seats: bool) -> bool:
    return seat == geo.CENTER or y_seats or seat.arm[1] != "y"


def _legal_seat(seat: geo.Seat, token: str, y_seats: bool, arm_names: Optional[Sequence[str]], sides: Optional[Mapping[str, str]],
                z_reserved: bool) -> bool:
    """May `token` sit on `seat`?  Seatable arms = arm_names, or every arm but y (unless y_seats); under z_reserved a token of
    side "this" may not sit on a z arm and a token of side "next" not on an x arm (written from the rule, not from Policy)."""
    if seat == geo.CENTER:
        return True
    if arm_names is not None:
        if seat.arm not in arm_names:
            return False
    elif not (y_seats or seat.arm[1] != "y"):
        return False
    if z_reserved and sides is not None:
        side = sides.get(token, "both")
        if seat.arm[1] == "x" and side == "next":
            return False
        if seat.arm[1] == "z" and side == "this":
            return False
    return True


def _move_ok(cross: geo.Cross, p: geo.Seat, q: geo.Seat, y_seats, arm_names, sides, z_reserved) -> bool:
    cp, cq = cross.get(p), cross.get(q)
    return ((cp is None or _legal_seat(q, str(cp), y_seats, arm_names, sides, z_reserved))
            and (cq is None or _legal_seat(p, str(cq), y_seats, arm_names, sides, z_reserved))
            and _legal_seat(p, "", y_seats, arm_names, None, False) and _legal_seat(q, "", y_seats, arm_names, None, False))


def verify_fixed_point_slide(wfn, cross: geo.Cross, y_seats: bool = False, *, stability: str = "sum",
                             arm_names: Optional[Sequence[str]] = None, sides: Optional[Mapping[str, str]] = None,
                             z_reserved: bool = False) -> SlideFixedPointReport:
    """I-05 for the key: no rotation changes the key and no swap of two seatable seats improves it.  stability "sum": the
    summed key rises; "per_axis": the move is Pareto-improving (no axis worsens, one rises).  `arm_names` = the arms that have
    seats (default: all but y), `sides`/`z_reserved` = the seating rule of growth z_reserved."""
    base, base_ax = cross_key(wfn, cross)
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
    total = noop = improving = trade = 0
    plateau = set()
    for p, q in geo.moves_swap(cross.L):
        if not (_seat_ok(p, True) and _seat_ok(q, True)):
            continue
        if not _move_ok(cross, p, q, y_seats, arm_names, sides, z_reserved):
            continue
        total += 1
        if cross.get(p) == cross.get(q):
            noop += 1
            continue
        c2 = geo.swap(cross, p, q)
        if c2.center is None:
            continue                                       # L-77
        s2, ax2 = cross_key(wfn, c2)
        if stability == "per_axis":
            if _pareto_better(ax2, base_ax):
                improving += 1
            elif ax2 == base_ax:
                if _flat_of(c2) != here:
                    plateau.add(_flat_of(c2))
            elif any(ax2[a] > base_ax[a] for a in AXES):
                trade += 1
        elif s2 > base:
            improving += 1
        elif s2 == base and _flat_of(c2) != here:
            plateau.add(_flat_of(c2))
    return SlideFixedPointReport(len(geo.moves_rotate()), rot_changed, follow, total, noop, improving, len(plateau),
                                 rot_changed == 0 and follow and improving == 0, stability, trade)


@dataclass(frozen=True)
class SlideClassReport:
    size: int
    one_key: bool                       # every member has the same total key (sum) / the same per-axis key (per_axis)
    members_fixed_points: bool
    closed: bool                        # every equal-key swap of a member stays in the class
    swaps_tested: int
    centres_nonempty: bool
    no_unit_on_unseatable_arm: bool
    labels_follow_rotation: bool
    is_stable_class: bool
    stability: str = "sum"
    keys: int = 1                       # distinct keys in the class (per_axis: > 1 when incomparable maximal keys are kept)
    antichain: bool = True              # per_axis: no member's per-axis key is dominated by another member's
    members_checked: int = 0            # members whose swaps were all tested (all, unless `sample` was given)


def verify_class_slide(wfn, members: Sequence[geo.Cross], y_seats: bool = False, *, stability: str = "sum",
                       arm_names: Optional[Sequence[str]] = None, sides: Optional[Mapping[str, str]] = None,
                       z_reserved: bool = False, sample: Optional[int] = None) -> SlideClassReport:
    """L-70/L-74 for the key, independent of the search.  per_axis: every member is a Pareto fixed point, the class is closed
    under the swaps that change no axis, and no member's per-axis key is dominated by another member's (the keys of a class
    may be incomparable, so `one_key` need not hold).  `sample=k`: test the swaps of only k members, evenly spread over the
    class; keys, antichain, non-empty centres and seat legality are still read for EVERY member, but the fixed-point and the
    closure checks cover the checked members only (`members_checked` says how many)."""
    here = {_flat_of(c) for c in members}
    kk = {_flat_of(c): cross_key(wfn, c) for c in members}
    keys = {k[0] for k in kk.values()}
    axkeys = {tuple(k[1][a] for a in AXES) for k in kk.values()}
    kset = axkeys if stability == "per_axis" else keys
    fixed = closed = follow = True
    tested = 0
    if sample is None or sample >= len(members):
        pick = set(range(len(members)))
    else:
        pick = {(r * len(members)) // sample for r in range(sample)} | {0}
    checked = 0
    for ci, c in enumerate(members):
        base, base_ax = kk[_flat_of(c)]
        if ci not in pick:
            continue
        checked += 1
        for p, q in geo.moves_swap(c.L):
            if not (_seat_ok(p, True) and _seat_ok(q, True)):
                continue
            if not _move_ok(c, p, q, y_seats, arm_names, sides, z_reserved):
                continue
            if c.get(p) == c.get(q):
                continue
            c2 = geo.swap(c, p, q)
            if c2.center is None:
                continue
            tested += 1
            s2, ax2 = cross_key(wfn, c2)
            if stability == "per_axis":
                if _pareto_better(ax2, base_ax):
                    fixed = False
                elif ax2 == base_ax and _flat_of(c2) not in here:
                    closed = False
            elif s2 > base:
                fixed = False
            elif s2 == base and _flat_of(c2) not in here:
                closed = False
        rep = verify_fixed_point_slide(wfn, c, y_seats, stability=stability, arm_names=arm_names, sides=sides,
                                       z_reserved=z_reserved) if c is members[0] else None
        if rep is not None:
            follow = rep.labels_follow_rotation
            if rep.rotations_changing_key:
                fixed = False
        elif any(cross_key(wfn, geo.rotate(c, r))[0] != base for r in geo.moves_rotate()):
            fixed = False
    nonempty = all(c.center is not None for c in members)
    if arm_names is not None:
        free = all(c.get(s) is None for c in members for s in geo.seats(c.L) if s != geo.CENTER and s.arm not in arm_names)
    else:
        free = all(c.get(s) is None for c in members for s in geo.seats(c.L) if not _seat_ok(s, y_seats))
    if z_reserved and sides is not None:
        free = free and all(_legal_seat(s, str(c.get(s)), y_seats, arm_names, sides, True)
                            for c in members for s in geo.seats(c.L) if c.get(s) is not None)
    one = len(kset) == 1
    anti = True
    if stability == "per_axis":
        def dom(a, b):
            return a != b and all(x >= y for x, y in zip(a, b))
        anti = not any(dom(a, b) for a in axkeys for b in axkeys)
    ok_keys = anti if stability == "per_axis" else one
    return SlideClassReport(len(here), one, fixed, closed, tested, nonempty, free, follow,
                            ok_keys and fixed and closed and nonempty and free and follow, stability, len(kset), anti, checked)


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
    stability: str = DEFAULTS["stability"]
    seat_key: str = DEFAULTS["seat_key"]
    seat_empty_axis: str = DEFAULTS["seat_empty_axis"]
    growth: str = DEFAULTS["growth"]

    def __post_init__(self) -> None:
        if self.scope not in SL.SCOPES:
            raise ValueError("scope must be one of %r" % (SL.SCOPES,))
        if self.tier not in SL.TIERS:
            raise ValueError("tier must be one of %r" % (SL.TIERS,))
        if self.padding not in PADDINGS:
            raise ValueError("padding must be one of %r" % (PADDINGS,))
        if self.mode not in MODES:
            raise ValueError("mode must be one of %r" % (MODES,))
        for name, allowed in (("stability", STABILITIES), ("seat_key", SEAT_KEYS), ("seat_empty_axis", SEAT_EMPTY), ("growth", GROWTHS)):
            if getattr(self, name) not in allowed:
                raise ValueError("%s must be one of %r" % (name, allowed))

    def switches(self) -> Dict[str, str]:
        return {"stability": self.stability, "seat_key": self.seat_key, "seat_empty_axis": self.seat_empty_axis,
                "growth": self.growth}

    @property
    def is_legacy(self) -> bool:
        return self.switches() == LEGACY

    def doc(self) -> dict:
        d = {"format": FORMAT, "kind": "place_spec", "slide_spec_sha256": self.slide_spec_sha, "corpus_sha256": self.corpus_sha,
             "scope": self.scope, "tier": self.tier, "padding": self.padding, "padding_rule": PADDING_TEXT[self.padding],
             "y_arms": "seats" if self.y_seats else "no seats (one tier: no y edge exists)",
             "mode": self.mode, "key": KEY_TEXT, "growth": GROWTH_TEXT, "on_collapse": "stop",
             "budget": self.budget.to_json_obj(), "budget_level": level_name(self.budget)}
        if not self.is_legacy:                                       # L-580: the G3-c spec keeps its bytes and its sha
            d["switches"] = self.switches()
            d["rules"] = {"stability": STABILITY_TEXT[self.stability], "seat_key": SEAT_KEY_TEXT[self.seat_key],
                          "seat_empty_axis": SEAT_EMPTY_TEXT[self.seat_empty_axis], "growth": GROWTH_TEXTS[self.growth]}
        return d

    def to_bytes(self) -> bytes:
        return SL.canonical(self.doc())

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()

    def short(self) -> str:
        """The 12 hex digits of a cache key (`_slideplace-<sha12>`)."""
        return self.sha256()[:12]


def make_spec(slide: SL.Slide, *, scope: str = "corpus", tier: str = "RUN", padding: str = "none", level: str = "mid",
              y_seats: bool = False, mode: str = "search", stability: Optional[str] = None, seat_key: Optional[str] = None,
              seat_empty_axis: Optional[str] = None, growth: Optional[str] = None) -> PlaceSpec:
    """A switch left at None takes the module default (DEFAULTS: the owner's configuration); `LEGACY` is the G3-c behaviour."""
    sw = {"stability": stability, "seat_key": seat_key, "seat_empty_axis": seat_empty_axis, "growth": growth}
    sw = {k: (DEFAULTS[k] if v is None else v) for k, v in sw.items()}
    return PlaceSpec(slide.spec.sha256(), slide.spec.corpus_sha, scope, tier, padding, y_seats, mode, budget_level(level), **sw)


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
class Item:
    """One seat to insert: its token (the unit, or unit + SEP + sid for a unit of both sentences under seats="unit_sid"), the
    unit, the side of the window it belongs to ("this" / "next" / "both") and its sentence id (seats="unit": the sentence where
    the unit is first read)."""
    token: str
    unit: str
    side: str
    sid: int


def seat_items(slide: SL.Slide, window: SL.Window, tier: str, seat_key: str = "unit_sid", growth: str = "n_then_n1") -> Tuple[Item, ...]:
    """The seats of a window in insertion order (L-584, L-585).  Each sentence's distinct units in word order (first occurrence);
    growth "n_then_n1" / "z_reserved": all of N, then all of N+1; "interleave": N's first, N+1's first, N's second, ...
    seats "unit": a unit is seated once (at its first read, side "both" if it is in both sentences) -- with n_then_n1 this is
    `insertion_order`; "unit_sid": a unit in both sentences gets one seat per sentence (side "this" and "next")."""
    if seat_key not in SEAT_KEYS or growth not in GROWTHS:
        raise ValueError("unknown seat_key / growth")
    lists = []
    for sid in window.sids:
        seen = set()
        us = []
        for u in slide.space.tiers[tier].sentence_units[sid]:
            if u not in seen:
                seen.add(u)
                us.append(u)
        lists.append((sid, us))
    in_this = set(lists[0][1])
    in_next = set(lists[1][1]) if len(lists) == 2 else set()
    seq: List[Tuple[int, str]] = []
    if growth == "interleave" and len(lists) == 2:
        a, b = lists[0][1], lists[1][1]
        for k in range(max(len(a), len(b))):
            if k < len(a):
                seq.append((lists[0][0], a[k]))
            if k < len(b):
                seq.append((lists[1][0], b[k]))
    else:
        for sid, us in lists:
            seq.extend((sid, u) for u in us)
    out: List[Item] = []
    read = set()
    for sid, u in seq:
        if seat_key == "unit":
            if u in read:
                continue
            read.add(u)
            side = "both" if (u in in_this and u in in_next) else ("this" if u in in_this else "next")
            out.append(Item(u, u, side, sid))
        else:
            side = "this" if sid == window.sids[0] else "next"
            shared = u in in_this and u in in_next
            out.append(Item(u + SEP + str(sid) if shared else u, u, side, sid))
    return tuple(out)


def next_seat_items(items: Sequence[Item], seated: Iterable[str]) -> "NextSeat":
    """`next_seat` on seat tokens.  A shared unit's N+1 seat (token with SEP) is a loose, not an exclusive, N+1 seat."""
    pairs = [(it.token, "both" if (SEP in it.token and it.side == "next") else it.side) for it in items]
    return next_seat(pairs, seated)


def axes_with_evidence(counts: SL.WindowCounts, tier: str) -> Dict[str, bool]:
    """Does the window hold any count of the axis for pairs of the tier's units (x: a shared sentence, y: a containment, z: a
    unit of N with a unit of N+1)?  In S1 (one tier) y never does; a one-sentence window has no z (L-583)."""
    return {"x": any(k[0] == tier for k in counts.x),
            "y": any(k[0] == tier and k[2] == tier for k in counts.y),
            "z": any(k[0] == tier and k[2] == tier for k in counts.z)}


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
    seatless_arms: Tuple[str, ...]                          # arms that exist and hold no seat (the y arms in S1, denied arms)
    L: int
    members: Tuple[Flat, ...]
    centres: Tuple[str, ...]
    size: int
    key: Score                                              # the SUMMED key of the representative (recorded; per_axis does not decide by it)
    axis_key: Tuple[Tuple[str, int, int], ...]              # of the representative
    axis_splits: int                                        # distinct per-axis splits over the class
    axis_split_set: Tuple[Tuple[int, ...], ...]             # (x n, x omega, y n, y omega, z n, z omega, members), sorted
    order_log: Tuple[Tuple[str, str], ...]
    steps: Tuple[SStep, ...]
    stop: str
    broke_on: Optional[SStep]
    left: Tuple[str, ...]
    budget: Budget
    z_self: Tuple[Tuple[str, int], ...]                     # seated units with n_z(u, u) > 0
    next_seat: Optional[NextSeat]                           # None for a one-sentence window (nothing to seat)
    # ---- G3-c2 (L-580..L-590); every field below is new, the ones above are the G3-c record ------------------------------
    switches: Tuple[Tuple[str, str], ...] = ()              # (stability, seat_key, seat_empty_axis, growth) values
    items: Tuple[Item, ...] = ()                            # the seats in insertion order
    axis_evidence: Tuple[Tuple[str, bool], ...] = ()        # does the window hold any count of x / y / z
    seat_rows: Tuple[dict, ...] = ()                        # the representative's seats with provenance (property `seats`)
    self_links: Tuple[dict, ...] = ()                       # units with two seats: n_z(u, u), both seated, directly linked
    tradeoffs: Optional[dict] = None                        # moves of the representative that improve one axis and worsen another

    @property
    def class_size(self) -> int:
        return len(self.members)

    @property
    def cross(self) -> geo.Cross:
        return to_cross(self.members[0], self.L)

    def crosses(self) -> Tuple[geo.Cross, ...]:
        return tuple(to_cross(m, self.L) for m in self.members)

    @property
    def axis_keys(self) -> Dict[str, List[int]]:
        """{x: [n, omega], y: [...], z: [...]}: the key of each axis of the representative member (a label; the members of a
        per_axis class may hold several incomparable keys, listed in `axis_split_set`)."""
        return {a: [n, o] for a, n, o in self.axis_key}

    @property
    def seats(self) -> List[dict]:
        """The seats of the representative member: [{unit, sid, arm, position, depth, side, token, sources}] in flat order (the
        centre first, then +x, -x, +y, -y, +z, -z, outermost seat first).  arm = "centre" or an arm name; position = the index
        on the arm (0 = outermost); depth = L - position (1 = next to the centre); sid = the corpus sentence id of the seat;
        sources = {"occ": [tier, sid, k, unit, start, end] (the unit's first occurrence in that sentence), "edge": the edge to
        the seat's inner neighbour, {axis, arm, with: {unit, sid}, n, omega, sources: [[...]]} or None (empty neighbour)}."""
        return [dict(r) for r in self.seat_rows]

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
             "next_seat": None if self.next_seat is None else self.next_seat.doc(),
             # G3-c2
             "switches": {k: v for k, v in self.switches}, "axis_keys": self.axis_keys,
             "axis_evidence": {a: e for a, e in self.axis_evidence},
             "seat_order": [[it.unit, it.sid] for it in self.items],
             "items": [{"token": it.token, "unit": it.unit, "side": it.side, "sid": it.sid} for it in self.items],
             "seats": self.seats, "self_links": list(self.self_links),
             "tradeoffs": self.tradeoffs}
        if members:
            d["members"] = [list(m) for m in self.members]
        return d

    def to_bytes(self) -> bytes:
        return SL.canonical(self.doc(True))


# the fields G3-c2 adds to the record (a record of the LEGACY configuration equals the G3-c record without them)
NEW_RECORD_FIELDS: Tuple[str, ...] = ("switches", "axis_keys", "axis_evidence", "seat_order", "items", "seats", "self_links", "tradeoffs")


def _edge_evidence(counts: SL.WindowCounts, tier: str, arm: str, uo: str, ui: str) -> dict:
    """The evidence (n, omega, source rows) of the edge (outer uo, inner ui) on `arm`, read through the counts' own tables."""
    if arm[1] == "x":
        b, a = counts.x.get((tier, uo, ui), ((), ()))
        return {"axis": "x", "arm": arm, "n": len(b) + len(a), "omega": len(b) if arm == "+x" else len(a),
                "sources": [list(t) for t in b] + [list(t) for t in a]}
    if arm[1] == "z":
        z = counts.z.get((tier, uo, tier, ui) if arm == "+z" else (tier, ui, tier, uo), ())
        return {"axis": "z", "arm": arm, "n": len(z), "omega": len(z), "sources": [list(t) for t in z]}
    return {"axis": "y", "arm": arm, "n": 0, "omega": 0, "sources": []}


def _seat_rows(slide: SL.Slide, pw: PlaceWindow, counts: SL.WindowCounts, tier: str, flat: Flat, L: int,
               items: Sequence[Item]) -> Tuple[dict, ...]:
    by_tok = {it.token: it for it in items}
    first: Dict[Tuple[str, int, str], SL.Occ] = {}
    for o in slide.pack(pw.window):
        first.setdefault((o.tier, o.sid, o.unit), o)
    rows: List[dict] = []
    for ix, tok in enumerate(flat):
        if tok is None:
            continue
        it = by_tok[tok]
        if ix == 0:
            arm, pos, inner = "centre", 0, None
        else:
            arm, pos = ARM_NAMES[(ix - 1) // L], (ix - 1) % L
            inner = ix + 1 if pos + 1 < L else 0
        occ = first.get((tier, it.sid, it.unit))
        edge = None
        if inner is not None and flat[inner] is not None:
            it2 = by_tok[flat[inner]]
            edge = _edge_evidence(counts, tier, arm, it.unit, it2.unit)
            edge["with"] = {"unit": it2.unit, "sid": it2.sid}
        rows.append({"unit": it.unit, "sid": it.sid, "arm": arm, "position": pos, "depth": 0 if ix == 0 else L - pos,
                     "side": it.side, "token": tok, "sources": {"occ": None if occ is None else occ.row(), "edge": edge}})
    return tuple(rows)


def _self_links(counts: SL.WindowCounts, tier: str, flat: Flat, L: int, items: Sequence[Item]) -> Tuple[dict, ...]:
    """For every unit that has two seats: its self-link count n_z(u, u), whether both seats are placed and whether they are
    the two ends of one cross edge (the z self-edge made real) and on which arm."""
    byu: Dict[str, List[Item]] = {}
    for it in items:
        byu.setdefault(it.unit, []).append(it)
    lay = _lay(L)
    where = {c: ix for ix, c in enumerate(flat) if c is not None}
    out = []
    for u in sorted(k for k, v in byu.items() if len(v) == 2):
        t1, t2 = byu[u][0].token, byu[u][1].token
        both = t1 in where and t2 in where
        linked, arm = False, None
        if both:
            a, b = where[t1], where[t2]
            for o, i in lay.edges:
                if (o, i) in ((a, b), (b, a)):
                    linked, arm = True, ARM_NAMES[(o - 1) // L]
        out.append({"unit": u, "n_z_self": counts.n_z(tier, u, tier, u), "both_seated": both, "linked": linked, "arm": arm})
    return tuple(out)


def _finish(spec: PlaceSpec, slide: SL.Slide, pw: PlaceWindow, counts: SL.WindowCounts, w: ArmWeights, arms: Tuple[int, ...],
            items: Sequence[Item], g: Grown, pol: Optional[Policy]) -> SlidePlacement:
    members = tuple(sorted(g.members, key=_fk))
    rep = members[0]
    seated = sorted({unit_of(u) for u in rep if u is not None})
    cent = tuple(sorted({unit_of(m[0]) for m in members if m[0] is not None}))
    akey = axis_key_flat(w, rep, g.L) if g.size else tuple((a, 0, 0) for a in AXES)
    split_n: Dict[Tuple[int, ...], int] = {}
    for m in members:                                    # an empty window: one member, all zeros
        t = tuple(v for _a, n, o in axis_key_flat(w, m, g.L) for v in (n, o))
        split_n[t] = split_n.get(t, 0) + 1
    split_set = tuple(sorted(t + (c,) for t, c in split_n.items()))
    splits = len(split_set)
    ns = next_seat_items(items, [c for c in rep if c is not None]) if len(pw.window.sids) == 2 else None
    zself = tuple((u, counts.n_z(spec.tier, u, spec.tier, u)) for u in seated if counts.n_z(spec.tier, u, spec.tier, u) > 0)
    fnd = slide.spec.foundation
    ev = axes_with_evidence(counts, spec.tier)
    rows: Tuple[dict, ...] = ()
    links: Tuple[dict, ...] = ()
    trade = None
    if g.size:
        rows = _seat_rows(slide, pw, counts, spec.tier, rep, g.L, items)
        links = _self_links(counts, spec.tier, rep, g.L, items)
        if spec.mode == "search":
            trade = tradeoff_counts(w, rep, g.L, arms, pol)
    return SlidePlacement(
        spec.sha256(), slide.spec.sha256(), spec.scope, spec.tier, spec.mode, pw,
        tuple(fnd.arms), tuple((a, fnd.arm_weight(a)) for a in ARM_NAMES),
        tuple(ARM_NAMES[a] for a in range(geo.N_ARMS) if a not in arms), g.L, members, cent, g.size,
        score_flat(w, rep, g.L) if g.size else ZERO2, akey, splits, split_set, tuple((it.unit, it.side) for it in items), g.steps,
        g.stop, g.broke_on, g.left, spec.budget, zself, ns,
        tuple(sorted(spec.switches().items())), tuple(items), tuple((a, ev[a]) for a in AXES), rows, links, trade)


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
    """Place the cross of one window (mode "search": the growth above; mode "line": the diagnostic line, no search; the line
    is the G3-c line: it ignores the G3-c2 switches)."""
    if spec.slide_spec_sha != slide.spec.sha256() or spec.corpus_sha != slide.spec.corpus_sha:
        raise ValueError("the place spec was made for another slide spec / corpus")
    counts = slide.counts(pw.window, spec.scope)
    w = ArmWeights.from_counts(counts, spec.tier)
    arms = arms_ok(spec.y_seats)
    if spec.mode == "line":
        items = seat_items(slide, pw.window, spec.tier, "unit", "n_then_n1")
        la = _line_arrangement([(it.token, it.side) for it in items])
        if la is None:
            g = Grown(1, ((None,) * 7,), (), "empty", None, (), 0)
        else:
            L, flat = la
            g = Grown(L, (flat,), (), "line", None, (), sum(1 for c in flat if c is not None))
        return _finish(spec, slide, pw, counts, w, arms, items, g, None)
    if spec.seat_empty_axis == "deny":                                         # L-583
        ev = axes_with_evidence(counts, spec.tier)
        arms = tuple(a for a in arms if ev[ARM_NAMES[a][1]])
    items = seat_items(slide, pw.window, spec.tier, spec.seat_key, spec.growth)
    zres = spec.growth == "z_reserved"
    g = grow(w, [(it.token, it.side) for it in items], spec.budget, arms, stability=spec.stability, z_reserved=zres,
             info={it.token: (it.unit, it.sid) for it in items} if spec.seat_key == "unit_sid" else None)
    pol = Policy(arms, zres, {it.token: it.side for it in items})
    return _finish(spec, slide, pw, counts, w, arms, items, g, pol)
