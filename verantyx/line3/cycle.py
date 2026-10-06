"""T5 query cycle of the line-3 build: whole-space read, moves to a fixed point, agreement,
class-member choice, typed verdict, `answer` / `thought` output.  Exact arithmetic only.

Binding decisions (ops/decisions/2026-10-06_line3_faithful_build.md):
  I-06 / N-01 / decision 3,7   a unit's energy = r0 + share of sentences shared with the query
        units (energy.py); the query changes it.
  I-07   the query units, in order, sit on the outer ends of the 6 arms (unit i on world
        section i); sections without a query unit read with the whole (set) query.
  N-21 + M-5   a query of more than 6 units is nested as query crosses (QueryCross): the
        FIRST layer answers (M-5(c) recommended default, not an owner answer), the inner
        layers are recorded and are added when passing to the next layer (T8).
  I-08   the WHOLE space is read every query: every cross of the tier (one per unit) is read,
        every member of its class (placement class, owner after T4b/T4c).
  M-2    the amount of inference is counted in nodes = crosses read; default = all.  A reduced
        read follows M-2(a) (query units' crosses -> crosses holding a unit that shares a
        sentence with a query unit -> the rest; within a group by E_Q of the cross's unit,
        large first, equal values read together or not at all) and is marked partial with
        counts.  (M-2 recommended default; the owner picked "number of nodes etc.")
  decision 5 / N-04   moves = the 23 non-identity rotations + swaps of two seats inside ONE
        cross (empty seats included; a swap leaving the centre empty is not a move, L-77).
  I-12   moves are compared lexicographically by (fewer disagreements, more working
        sections, more energy flowing into the centre unit).
  decision 6 / I-05   stop at a fixed point: no single move gives a strictly better key;
        the end state must also agree (I-11) for an answer.
  I-11   agreement = the three ratios (section / edge / placement) point to the same single
        unit; a tie abstains and is typed, never broken by order.
  N-03   an answer needs at least one working section with a (grounded) query unit attached.
  decision after T4b/T4c  every member of a placement class is read and the one most stable
        after the query is adopted; equal -> a list (CHOICE).  Stability inv = share of single
        moves that leave the result unchanged (I-15).
  N-11   (T8 owns layers) a start that cannot reach a fixed point within the budget is typed
        NO_FIXED_POINT and recorded as a place where stacking would occur.
  N-08/N-10  output = `answer` (verdict, unit, trace) and `thought` (search steps, energy log,
        state version); the search state is emitted in a storable form (M-3; T10/T11 store it).

Local decisions (docs/LINE3_LOCAL_DECISIONS.md, L-100..):
  L-100 Search state = the world view as a flat tuple (centre, arm0 k=0..L-1, ...) with identity
        orientation; a rotation permutes the six world legs by the table taken from
        geometry.rotate (new[w] = old[r^-1(w)]); a swap exchanges two flat entries.
  L-101 Key = (-(distinct votes - 1), working sections, F(centre unit)) with votes = the units the
        working sections point to + the edge unit + the placement unit; a ratio that points
        nowhere counts as its own distinct vote, so disagreements == 0 <=> three-ratio AGREE.
        F(centre unit) is the edge flow (energy.edge_flow) under E_Q into the unit at the centre.
  L-102 Exact integer scale: N*E as ints, F and B scaled by D = lcm of all n(u); compared as ints.
        Equal (as Fractions) to energy.three_ratios (differentially tested).
  L-103 Result of a state = its agreed unit when the three ratios agree AND N-03 holds, else None.
        inv = (moves whose resulting state differs and whose result equals the current result) /
        (moves whose resulting state differs); moves that leave the state identical are not
        counted (else a lone seed would be 100% stable).  No such move at all: inv = 1.
  L-104 Grounding (N-03): a section counts as "with a query unit attached" iff its query unit is
        in the space (n >= 1); an absent unit is neither error nor evidence (L-52).
  L-105 Search = all tied best improving moves branch (design 4.5); distinct states only.
        Budget per start QueryBudget(max_states=512 expansions, max_ends=64 fixed points; the design's L-05
        default 64/8 turned ~1/3 of RUN class members into NO_FIXED_POINT in a measurement) (design L-05).  Exceeded -> NO_FIXED_POINT with counts.  Expansion order is by sorted state
        (a label; the set of fixed points does not depend on it unless the budget is hit, and
        then the whole start is NO_FIXED_POINT).
  L-106 Outcome of one class member = CANDIDATE (all fixed points give the same grounded answer;
        stability = the minimum over them), NONE (no answer; typed by the fixed points' status),
        AMBIGUOUS (fixed points of tied branches give different results), NO_FIXED_POINT.
  L-107 Member choice (flag `member_rule`): "stable_any" (default; literal "adopt the most stable
        member", over members that reached a fixed point) or "answering_only" (only members that
        answer).  Equal best stability with different results -> CHOICE: the answering results
        enter the question's pool.
  L-108 Question level: pool = adopted candidates; the best stability wins; one unit -> ANSWER,
        several units at the best stability -> CHOICE (list, no cap, I-14/N-20).  Without a
        candidate: AMBIGUOUS if any start is ambiguous, else the most specific failure seen
        (reporting precedence; not a winner choice): NO_FIXED_POINT, RATIO_DISAGREEMENT,
        SECTION_DISAGREEMENT, NO_EVIDENCE.
  L-109 Query scope for energies: the first layer's units (scope "first_layer", default) or all
        units ("whole").  Section i with no attached unit reads with the set of that scope.
  L-110 A tier is read separately (I-16); combining tiers is T7.
  L-112 Neighbours of a state are evaluated incrementally (only the changed legs' sections and the
        cells around the two seats; rotations keep F and B); differentially tested equal to evaluate().
  L-111 Class members are read as the expanded class (placement.crosses()), each in canonical leg
        order; a cap `member_cap` (default None = all) is reported (members read / total).  The
        leg-to-arm assignment of a member is its canonical order (see open points).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from fractions import Fraction
from math import gcd
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import energy as en
from verantyx.line3.geometry import (
    AXES, DEFAULT_WINDOW, N_ARMS, Cross, moves_rotate, moves_swap, rotate, seats,
)
from verantyx.line3.placement import Placement, Flat, canon, from_cross, to_cross
from verantyx.line3.space import TierSpace, _SPLITTERS

# ---- verdict types (design 4.8) ----
ANSWER = "ANSWER"
CHOICE = "CHOICE"
AMBIGUOUS = "AMBIGUOUS"
UNKNOWN_NO_EVIDENCE = "UNKNOWN_NO_EVIDENCE"
UNKNOWN_SECTION_DISAGREEMENT = "UNKNOWN_SECTION_DISAGREEMENT"
UNKNOWN_RATIO_DISAGREEMENT = "UNKNOWN_RATIO_DISAGREEMENT"
UNKNOWN_NO_FIXED_POINT = "UNKNOWN_NO_FIXED_POINT"

# member outcome kinds (L-106)
CANDIDATE, NONE_, AMBIG, NOFIX = "candidate", "none", "ambiguous", "no_fixed_point"

STATE_FORMAT = "line3.search_state.v1"


# --------------------------------------------------------------------------
# query and query cross (I-07, N-21, M-5)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class QueryCross:
    """N-21: one layer of the nested query cross: up to 6 units, unit i on the outer end of
    world section i (I-07); `inner` holds the units from the 7th on (next layer)."""
    layer: int
    units: Tuple[str, ...]
    inner: Optional["QueryCross"] = None

    def layers(self) -> Tuple["QueryCross", ...]:
        out, c = [], self
        while c is not None:
            out.append(c)
            c = c.inner
        return tuple(out)

    def all_units(self) -> Tuple[str, ...]:
        return tuple(u for c in self.layers() for u in c.units)

    def as_cross(self) -> Cross:
        """The layer as a geometry Cross: centre empty, unit i on the outer end (k=0) of arm i."""
        return Cross.make(L=1, center=None,
                          arms=[[self.units[i] if i < len(self.units) else None] for i in range(N_ARMS)])

    def to_json_obj(self) -> dict:
        return {"layers": [list(c.units) for c in self.layers()]}


def build_query_cross(units: Sequence[str]) -> QueryCross:
    """N-21: units in order, 6 per layer; the first layer is the outermost."""
    units = tuple(units)
    chunks = [units[i:i + N_ARMS] for i in range(0, max(len(units), 1), N_ARMS)] or [()]
    inner = None
    for j in range(len(chunks) - 1, -1, -1):
        inner = QueryCross(j, chunks[j], inner)
    assert inner is not None
    return inner


def split_question(tier_name: str, question: str) -> Tuple[str, ...]:
    """The question cut like the data of that tier (design 3.1)."""
    return tuple(_SPLITTERS[tier_name](question))


# --------------------------------------------------------------------------
# exact arithmetic helpers (L-102)
# --------------------------------------------------------------------------
def _lcm(a: int, b: int) -> int:
    return a // gcd(a, b) * b


class TierFacts:
    """Per-tier integers shared by every evaluation (pure caches; results never depend on them)."""

    def __init__(self, tier: TierSpace) -> None:
        self.tier = tier
        self.N = tier.N
        self.n: Dict[str, int] = {u: len(p) for u, p in tier.postings.items()}
        D = 1
        for v in sorted(set(self.n.values())):
            D = _lcm(D, v)
        self.D = D
        self.dq: Dict[str, int] = {u: D // c for u, c in self.n.items()}
        self._np: Dict[Tuple[str, str], int] = {}

    def npair(self, u: str, v: str) -> int:
        """n(u,v) with n(u,u) = n(u) (L-50) and 0 outside the space (L-52)."""
        if u not in self.n or v not in self.n:
            return 0
        k = (u, v) if u <= v else (v, u)
        r = self._np.get(k)
        if r is None:
            r = self._np[k] = self.tier.n_pair(u, v)
        return r


_ROT_CACHE: Dict[int, Tuple[Tuple[int, ...], ...]] = {}
_SWAP_CACHE: Dict[int, Tuple[Tuple[int, int], ...]] = {}


def rotation_tables() -> Tuple[Tuple[int, ...], ...]:
    """L-100: for each of the 23 non-identity rotations the source world position of every
    position: new_world[w] = old_world[src[w]] (taken from geometry.rotate)."""
    if 0 not in _ROT_CACHE:
        marker = Cross.make(L=1, arms=[[i] for i in range(N_ARMS)])
        _ROT_CACHE[0] = tuple(tuple(w[0] for w in rotate(marker, r).world_arms())
                              for r in moves_rotate())
    return _ROT_CACHE[0]


def swap_pairs(L: int) -> Tuple[Tuple[int, int], ...]:
    """Flat index pairs (i < j) of every swap, in geometry.moves_swap order."""
    if L not in _SWAP_CACHE:
        idx = {s: i for i, s in enumerate(seats(L))}
        _SWAP_CACHE[L] = tuple((idx[p], idx[q]) for p, q in moves_swap(L))
    return _SWAP_CACHE[L]


def apply_rotation(flat: Flat, L: int, src: Sequence[int]) -> Flat:
    legs = [flat[1 + a * L: 1 + (a + 1) * L] for a in range(N_ARMS)]
    out: List[Optional[str]] = [flat[0]]
    for w in range(N_ARMS):
        out.extend(legs[src[w]])
    return tuple(out)


def apply_swap(flat: Flat, i: int, j: int) -> Flat:
    f = list(flat)
    f[i], f[j] = f[j], f[i]
    return tuple(f)


def flat_key(f: Flat) -> Tuple[str, ...]:
    return tuple("" if c is None else "x" + c for c in f)


# --------------------------------------------------------------------------
# evaluation of one state (L-101, L-102)
# --------------------------------------------------------------------------
class Eval(tuple):
    """(key, status, agreed, answer, sections, r2, r3, working, grounded) -- a tuple."""
    __slots__ = ()

    key = property(lambda s: s[0])
    status = property(lambda s: s[1])
    agreed = property(lambda s: s[2])
    answer = property(lambda s: s[3])
    sections = property(lambda s: s[4])
    r2 = property(lambda s: s[5])
    r3 = property(lambda s: s[6])
    working = property(lambda s: s[7])
    grounded = property(lambda s: s[8])


def _uargmax(d: Mapping[str, int]) -> Optional[str]:
    """I-11 / L-58: the strictly greatest positive value if unique; never order-dependent."""
    best = None
    bu = None
    tie = False
    for u, v in d.items():
        if best is None or v > best:
            best, bu, tie = v, u, False
        elif v == best:
            tie = True
    if best is None or best <= 0 or tie:
        return None
    return bu



_NBR: Dict[int, tuple] = {}


def _nbr_idx(L: int):
    """Flat-index neighbours: [0] = the six arm ends; arm seat idx -> (prev or None, next)."""
    if L not in _NBR:
        lay: List[object] = [tuple(1 + a * L + L - 1 for a in range(N_ARMS))]
        for a in range(N_ARMS):
            for k in range(L):
                idx = 1 + a * L + k
                lay.append((idx - 1 if k > 0 else None, idx + 1 if k < L - 1 else 0))
        _NBR[L] = tuple(lay)
    return _NBR[L]


@dataclass
class Base:
    flat: Flat
    L: int
    legs: list
    sec: list
    gr: list
    fc: list
    bc: list
    fl: list
    bl: list
    r2: Optional[str]
    r3: Optional[str]
    eval: Eval
    unique: bool            # every unit on one seat only (else the incremental path is not used)


class Reader:
    """Evaluates states of one tier under one query context.  Pure caches inside."""

    def __init__(self, facts: TierFacts, attached: Sequence[Optional[str]],
                 qset: Iterable[str], window: int = DEFAULT_WINDOW) -> None:
        self.f = facts
        self.attached = tuple(attached) + (None,) * (N_ARMS - len(attached))
        self.qset = tuple(sorted(set(qset)))
        self.pos = tuple(
            tuple(dict.fromkeys((s + off) % N_ARMS for off in range(-window, window + 1)))
            for s in range(N_ARMS))
        self._enq: Dict[str, int] = {}
        self._enc: Dict[Tuple[str, str], int] = {}
        self._walk_c: Dict[tuple, Optional[str]] = {}
        self._cell_c: Dict[tuple, Tuple[int, int]] = {}
        self._eval_c: Dict[Flat, Eval] = {}
        self.evals = 0
        self.last_kinds: Dict[Flat, set] = {}

    # N*E_Q(u): n(u) + sum_{q in Q} n(q,u)   (E_Q = r0 + sum n(q,u)/N)
    def enq(self, u: str) -> int:
        v = self._enq.get(u)
        if v is None:
            f = self.f
            v = self._enq[u] = f.n.get(u, 0) + sum(f.npair(q, u) for q in self.qset)
        return v

    def en(self, u: str, qa: Optional[str]) -> int:
        """N*E of u as read by a section with attached unit qa (None: the whole query)."""
        if qa is None:
            return self.enq(u)
        k = (qa, u)
        v = self._enc.get(k)
        if v is None:
            v = self._enc[k] = self.f.n.get(u, 0) + self.f.npair(qa, u)
        return v

    def _walk(self, leg: Tuple[Optional[str], ...], centre: Optional[str], qa: Optional[str]) -> Optional[str]:
        """energy.walk_arm: terminus of one arm (outer end -> centre), L-55."""
        k = (leg, centre, qa)
        if k in self._walk_c:
            return self._walk_c[k]
        cells = leg + (centre,)
        cur = cells[0]
        if cur is not None:
            for nxt in cells[1:]:
                if nxt is None or self.f.npair(cur, nxt) <= 0 or self.en(nxt, qa) < self.en(cur, qa):
                    break
                cur = nxt
        self._walk_c[k] = cur
        return cur

    def _cell(self, v: str, nbrs: Tuple[Optional[str], ...]) -> Tuple[int, int]:
        k = (v, nbrs)
        r = self._cell_c.get(k)
        if r is None:
            f = self.f
            fv = bv = 0
            dv = f.dq.get(v, 0)
            for u in nbrs:
                if u is None or u == v:
                    continue
                m = f.npair(u, v)
                if f.n.get(u, 0):
                    fv += self.enq(u) * m * f.dq[u]
                bv += m * dv
            r = self._cell_c[k] = (fv, bv)
        return r

    def evaluate(self, flat: Flat, L: int) -> Eval:
        e = self._eval_c.get(flat)
        if e is not None:
            return e
        self.evals += 1
        centre = flat[0]
        legs = [flat[1 + a * L: 1 + (a + 1) * L] for a in range(N_ARMS)]
        # (1) sections
        sec: List[Optional[str]] = []
        grounded = 0
        for s in range(N_ARMS):
            qa = self.attached[s]
            cand: Dict[str, int] = {}
            for p in self.pos[s]:
                t = self._walk(legs[p], centre, qa)
                if t is not None and t not in cand:
                    cand[t] = self.en(t, qa)
            u = _uargmax(cand)
            sec.append(u)
            if u is not None and qa is not None and self.f.n.get(qa, 0) > 0:
                grounded += 1                                   # L-104
        working = sum(1 for u in sec if u is not None)
        sunits = {u for u in sec if u is not None}
        # (2),(3) edge flow and placement binding
        F: Dict[str, int] = {}
        B: Dict[str, int] = {}
        if centre is not None:
            nb = tuple(legs[a][L - 1] for a in range(N_ARMS))
            fv, bv = self._cell(centre, nb)
            F[centre] = F.get(centre, 0) + fv
            B[centre] = B.get(centre, 0) + bv
        for a in range(N_ARMS):
            leg = legs[a]
            for k in range(L):
                v = leg[k]
                if v is None:
                    continue
                prev = leg[k - 1] if k > 0 else None
                nxt = leg[k + 1] if k < L - 1 else centre
                fv, bv = self._cell(v, (prev, nxt))
                F[v] = F.get(v, 0) + fv
                B[v] = B.get(v, 0) + bv
        r2 = _uargmax(F)
        r3 = _uargmax(B)
        r1 = next(iter(sunits)) if len(sunits) == 1 else None
        if len(sunits) > 1:
            status = en.SECTION_DISAGREEMENT
        elif r1 is None or r2 is None or r3 is None:
            status = en.POINTS_NOWHERE
        elif r1 == r2 == r3:
            status = en.AGREE
        else:
            status = en.RATIO_DISAGREEMENT
        votes = set(sunits)
        if not sunits:
            votes.add(("nowhere", 1))
        votes.add(r2 if r2 is not None else ("nowhere", 2))
        votes.add(r3 if r3 is not None else ("nowhere", 3))
        key = (-(len(votes) - 1), working, F.get(centre, 0) if centre is not None else 0)
        agreed = r1 if status == en.AGREE else None
        answer = agreed if (agreed is not None and grounded >= 1) else None
        e = Eval((key, status, agreed, answer, tuple(sec), r2, r3, working, grounded))
        self._eval_c[flat] = e
        return e


    # ---- incremental evaluation of the neighbours of one base state (L-112) ----
    def _tail(self, centre, sec, grounded, r2, r3, fcen) -> Eval:
        """Shared last step of evaluate(): key, status, agreed unit, answer."""
        working = sum(1 for u in sec if u is not None)
        sunits = {u for u in sec if u is not None}
        r1 = next(iter(sunits)) if len(sunits) == 1 else None
        if len(sunits) > 1:
            status = en.SECTION_DISAGREEMENT
        elif r1 is None or r2 is None or r3 is None:
            status = en.POINTS_NOWHERE
        elif r1 == r2 == r3:
            status = en.AGREE
        else:
            status = en.RATIO_DISAGREEMENT
        votes = set(sunits)
        if not sunits:
            votes.add(("nowhere", 1))
        votes.add(r2 if r2 is not None else ("nowhere", 2))
        votes.add(r3 if r3 is not None else ("nowhere", 3))
        key = (-(len(votes) - 1), working, fcen if centre is not None else 0)
        agreed = r1 if status == en.AGREE else None
        answer = agreed if (agreed is not None and grounded >= 1) else None
        return Eval((key, status, agreed, answer, tuple(sec), r2, r3, working, grounded))

    def _sections(self, legs, centre, base_sec=None, base_gr=None, changed=None):
        """Section pointers (and grounded flags); a section whose legs are all unchanged and
        whose centre is unchanged keeps the base's pointer."""
        sec: List[Optional[str]] = []
        gr: List[int] = []
        for s in range(N_ARMS):
            if base_sec is not None and not any(p in changed for p in self.pos[s]):
                sec.append(base_sec[s])
                gr.append(base_gr[s])
                continue
            qa = self.attached[s]
            cand: Dict[str, int] = {}
            for p in self.pos[s]:
                t = self._walk(legs[p], centre, qa)
                if t is not None and t not in cand:
                    cand[t] = self.en(t, qa)
            u = _uargmax(cand)
            sec.append(u)
            gr.append(1 if (u is not None and qa is not None and self.f.n.get(qa, 0) > 0) else 0)
        return sec, gr

    def make_base(self, flat: Flat, L: int) -> "Base":
        lay = _nbr_idx(L)
        legs = [flat[1 + a * L: 1 + (a + 1) * L] for a in range(N_ARMS)]
        centre = flat[0]
        sec, gr = self._sections(legs, centre)
        fc: List[Optional[int]] = [None] * len(flat)
        bc: List[Optional[int]] = [None] * len(flat)
        units = [c for c in flat if c is not None]
        for idx, v in enumerate(flat):
            if v is None:
                continue
            fc[idx], bc[idx] = self._cell(v, self._nbr_cells(flat, idx, lay))
        fl = sorted(((x, i) for i, x in enumerate(fc) if x is not None), reverse=True)
        bl = sorted(((x, i) for i, x in enumerate(bc) if x is not None), reverse=True)
        r2 = flat[fl[0][1]] if fl and fl[0][0] > 0 and (len(fl) < 2 or fl[1][0] < fl[0][0]) else None
        r3 = flat[bl[0][1]] if bl and bl[0][0] > 0 and (len(bl) < 2 or bl[1][0] < bl[0][0]) else None
        fcen = fc[0] if fc[0] is not None else 0
        ev = self._tail(centre, sec, sum(gr), r2, r3, fcen)
        return Base(flat, L, legs, sec, gr, fc, bc, fl, bl, r2, r3, ev, len(set(units)) == len(units))

    @staticmethod
    def _nbr_cells(flat, idx, lay):
        if idx == 0:
            return tuple(flat[k] for k in lay[0])
        nb = lay[idx]
        prev, nxt = nb
        return (None if prev is None else flat[prev], flat[nxt])

    def neighbour_rotation(self, b: "Base", src: Sequence[int], st2: Flat) -> Eval:
        """Rotation: only the sections change (F, B and the centre flow are intrinsic)."""
        L = b.L
        legs = [st2[1 + a * L: 1 + (a + 1) * L] for a in range(N_ARMS)]
        sec, gr = self._sections(legs, b.flat[0])
        return self._tail(b.flat[0], sec, sum(gr), b.r2, b.r3, b.fc[0] if b.fc[0] is not None else 0)

    def neighbour_swap(self, b: "Base", i: int, j: int) -> Eval:
        """Swap of flat seats i < j (contents differ, centre stays non-empty)."""
        L, flat = b.L, b.flat
        lay = _nbr_idx(L)
        ci, cj = flat[j], flat[i]            # new content of i and of j

        def content(k):
            return ci if k == i else (cj if k == j else flat[k])

        centre = content(0)
        changed = set()
        legs = list(b.legs)
        edit: Dict[int, list] = {}
        for k, c in ((i, ci), (j, cj)):
            if k:
                a, t = divmod(k - 1, L)
                changed.add(a)
                if a not in edit:
                    edit[a] = list(b.legs[a])
                edit[a][t] = c
        for a, lst in edit.items():
            legs[a] = tuple(lst)
        if i == 0:
            changed = set(range(N_ARMS))
        sec, gr = self._sections(legs, centre, b.sec, b.gr, changed)
        # affected cells: the two seats and their neighbours
        aff = {i, j}
        for k in (i, j):
            if k == 0:
                aff.update(lay[0])
            else:
                prev, nxt = lay[k]
                if prev is not None:
                    aff.add(prev)
                aff.add(nxt)
        newf: Dict[int, int] = {}
        newb: Dict[int, int] = {}
        for k in aff:
            v = content(k)
            if v is None:
                continue
            if k == 0:
                nbc = tuple(content(x) for x in lay[0])
            else:
                prev, nxt = lay[k]
                nbc = (None if prev is None else content(prev), content(nxt))
            newf[k], newb[k] = self._cell(v, nbc)
        r2 = self._top(b.fl, aff, newf, content)
        r3 = self._top(b.bl, aff, newb, content)
        fcen = newf[0] if 0 in newf else (b.fc[0] if b.fc[0] is not None else 0)
        return self._tail(centre, sec, sum(gr), r2, r3, fcen)

    @staticmethod
    def _top(sorted_base, skip, newvals, content):
        """The unit with the strictly greatest positive value among the base values (cells
        outside `skip`) and the new values; None on a tie / no positive value."""
        first = None
        second = None
        for v, idx in sorted_base:
            if idx in skip:
                continue
            if first is None:
                first = (v, idx)
            else:
                second = v
                break
        best = None
        for k in sorted(newvals):
            if best is None or newvals[k] > best[0]:
                best = (newvals[k], k)
        pool = []
        if first is not None:
            pool.append(first[0])
        if second is not None:
            pool.append(second)
        pool.extend(newvals.values())
        if not pool:
            return None
        m = max(pool)
        if m <= 0 or sum(1 for x in pool if x == m) != 1:
            return None
        if first is not None and first[0] == m:
            return content(first[1])
        for k, v in newvals.items():
            if v == m:
                return content(k)
        return None

    def f_scale(self) -> int:
        """F integers are scaled by N * D."""
        return self.f.N * self.f.D


# --------------------------------------------------------------------------
# search (decision 5, I-12, I-05, I-15)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class QueryBudget:
    """L-105: per start, explicit, never silent."""
    max_states: int = 512
    max_ends: int = 64


@dataclass(frozen=True)
class EndState:
    flat: Flat
    key: Tuple[int, int, int]
    status: str
    agreed: Optional[str]
    answer: Optional[str]
    inv: Fraction
    moves: int                 # moves whose resulting state differs (L-103)
    unchanged: int             # of those, the result equals the current result
    noop: int                  # moves that leave the state identical (not counted)
    blocked: int               # swaps that would leave the centre empty (L-77)


@dataclass(frozen=True)
class Settled:
    """The result of climbing from one start."""
    start: Flat
    L: int
    ends: Tuple[EndState, ...]       # fixed points (empty iff budget)
    expanded: int                    # states expanded (each is one full scan of all moves)
    accepted: int                    # improving moves followed (edges of the search)
    budget_hit: Optional[str]        # "max_states" | "max_ends" | None
    rotations_taken: int = 0         # of those, rotations
    swaps_taken: int = 0             # of those, seat swaps


def _scan(reader: Reader, st: Flat, L: int):
    b = reader.make_base(st, L)
    cur = reader.evaluate(st, L) if not b.unique else b.eval
    if b.unique:
        reader._eval_c[st] = cur
    moves = unchanged = noop = blocked = 0
    best_key = None
    best: List[Flat] = []
    kinds: Dict[Flat, set] = {}
    ca, ck = cur[3], cur[0]

    def consider(e: Eval, build, kind):
        nonlocal moves, unchanged, best_key, best, kinds
        moves += 1
        if e[3] == ca:
            unchanged += 1
        if e[0] > ck:
            st2 = build()
            reader._eval_c[st2] = e
            if best_key is None or e[0] > best_key:
                best_key, best, kinds = e[0], [st2], {st2: {kind}}
            elif e[0] == best_key:
                if st2 not in best:
                    best.append(st2)
                kinds.setdefault(st2, set()).add(kind)

    for src in rotation_tables():
        st2 = apply_rotation(st, L, src)
        if st2 == st:
            noop += 1
            continue
        e = reader.neighbour_rotation(b, src, st2) if b.unique else reader.evaluate(st2, L)
        consider(e, lambda st2=st2: st2, "rotation")
    for i, j in swap_pairs(L):
        a, c = st[i], st[j]
        if a == c:
            noop += 1
            continue
        if i == 0 and c is None:
            blocked += 1                      # L-77: the centre must hold a unit
            continue
        e = reader.neighbour_swap(b, i, j) if b.unique else reader.evaluate(apply_swap(st, i, j), L)
        consider(e, lambda i=i, j=j: apply_swap(st, i, j), "swap")
    reader.last_kinds = kinds
    return cur, moves, unchanged, noop, blocked, best


def settle(reader: Reader, start: Flat, L: int, budget: QueryBudget = QueryBudget()) -> Settled:
    """Climb from `start` by strictly improving single moves (I-12); every tied best move is a
    branch (design 4.5); the ends are the fixed points (I-05) reached, each with its
    stability inv (I-15, L-103)."""
    if start[0] is None:
        raise ValueError("an arrangement with an empty centre is not a state (L-77)")
    seen = {start}
    frontier = [start]
    ends: List[EndState] = []
    expanded = accepted = nrot = nswap = 0
    while frontier:
        frontier.sort(key=flat_key)
        st = frontier.pop(0)
        expanded += 1
        if expanded > budget.max_states:
            return Settled(start, L, (), expanded - 1, accepted, "max_states", nrot, nswap)
        cur, moves, unchanged, noop, blocked, best = _scan(reader, st, L)
        if best:
            for s2 in best:
                accepted += 1
                ks = reader.last_kinds.get(s2, set())
                nrot += 1 if "rotation" in ks else 0
                nswap += 1 if "swap" in ks else 0
                if s2 not in seen:
                    seen.add(s2)
                    frontier.append(s2)
        else:
            inv = Fraction(unchanged, moves) if moves else Fraction(1)
            ends.append(EndState(st, cur[0], cur[1], cur[2], cur[3], inv, moves, unchanged, noop, blocked))
            if len(ends) > budget.max_ends:
                return Settled(start, L, (), expanded, accepted, "max_ends", nrot, nswap)
    ends.sort(key=lambda e: flat_key(e.flat))
    return Settled(start, L, tuple(ends), expanded, accepted, None, nrot, nswap)


# --------------------------------------------------------------------------
# independent verification of a fixed point (I-05): the slow path via energy.three_ratios
# --------------------------------------------------------------------------
def slow_key(tier: TierSpace, cross: Cross, query: Iterable[str],
             attached: Mapping[int, str]) -> Tuple[Tuple[int, int, Fraction], en.Verdict]:
    """L-101 computed from energy.three_ratios / edge_flow (independent of Reader)."""
    q = tuple(sorted(set(query)))
    v = en.three_ratios(tier, cross, q, attached)
    votes = {s.unit for s in v.sections if s.unit is not None}
    if not votes:
        votes.add(("nowhere", 1))
    votes.add(v.edge_unit if v.edge_unit is not None else ("nowhere", 2))
    votes.add(v.placement_unit if v.placement_unit is not None else ("nowhere", 3))
    cen = None if cross.center is None else str(cross.center)
    F = en.edge_flow(tier, cross, q)
    return (-(len(votes) - 1), v.working, F.get(cen, Fraction(0)) if cen is not None else Fraction(0)), v


@dataclass(frozen=True)
class QueryFixedPointReport:
    rotations_tested: int
    swaps_tested: int
    swaps_noop: int
    swaps_blocked: int
    improving: int
    is_fixed_point: bool
    agree: bool


def verify_query_fixed_point(tier: TierSpace, cross: Cross, query: Iterable[str],
                             attached: Mapping[int, str]) -> QueryFixedPointReport:
    """I-05: no single move (23 rotations, every pair of seats) strictly improves the key,
    computed with geometry.rotate / geometry.swap and energy.three_ratios only."""
    from verantyx.line3.geometry import swap as g_swap
    base, v0 = slow_key(tier, cross, query, attached)
    imp = rt = st = noop = blocked = 0
    for r in moves_rotate():
        rt += 1
        k, _ = slow_key(tier, rotate(cross, r), query, attached)
        if k > base:
            imp += 1
    for p, q_ in moves_swap(cross.L):
        if cross.get(p) == cross.get(q_):
            noop += 1
            continue
        c2 = g_swap(cross, p, q_)
        if c2.center is None:
            blocked += 1
            continue
        st += 1
        k, _ = slow_key(tier, c2, query, attached)
        if k > base:
            imp += 1
    return QueryFixedPointReport(rt, st, noop, blocked, imp, imp == 0, v0.status == en.AGREE)


# --------------------------------------------------------------------------
# query context
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class QueryContext:
    query: Tuple[str, ...]                 # the whole question's units in order
    qcross: QueryCross
    attached: Tuple[Optional[str], ...]    # section -> unit of the first layer (I-07)
    energy_units: Tuple[str, ...]          # the set the energies read (L-109)
    scope: str

    def attached_map(self) -> Dict[int, str]:
        return {s: u for s, u in enumerate(self.attached) if u is not None}


def make_context(query: Sequence[str], scope: str = "first_layer") -> QueryContext:
    if scope not in ("first_layer", "whole"):
        raise ValueError("scope must be first_layer or whole")
    qc = build_query_cross(query)
    first = qc.units
    att = tuple(first[i] if i < len(first) else None for i in range(N_ARMS))
    eu = tuple(sorted(set(first if scope == "first_layer" else qc.all_units())))
    return QueryContext(tuple(query), qc, att, eu, scope)


# --------------------------------------------------------------------------
# read order and amount of inference (M-2)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ReadPlan:
    order_groups: Tuple[Tuple[str, Tuple[str, ...]], ...]   # (group name, seeds of equal E_Q), read order
    read: Tuple[str, ...]                                   # seeds read, in read order
    unread: Tuple[str, ...]
    total: int
    amount: Optional[int]
    partial: bool
    boundary: int                                           # seeds of the first unread equal-value group (tie not split)


def plan_read(tier: TierSpace, facts: TierFacts, ctx: QueryContext,
              placements, amount: Optional[int] = None, query_crosses_only: bool = False,
              share_crosses: bool = False) -> ReadPlan:
    """I-08 / M-2(a): all crosses by default; with an amount, the order is: crosses of query
    units, crosses holding a unit that shares a sentence with a query unit, the rest; inside a
    group by E_Q(seed) descending; equal values are read together or not at all."""
    q = set(ctx.energy_units)
    seeds = tier.units()
    if query_crosses_only:
        # T6v V1 (option; default off = I-08 whole space): only the crosses that hold at least one
        # query unit (centre or any seat, twins included).  `amount` is not combined with it.
        if amount is not None:
            raise ValueError("query_crosses_only cannot be combined with amount")
        keep = []
        shared = []
        for s_ in seeds:
            p = placements.cross_for(s_)
            units = {c for c in from_cross(p.cross) if c is not None}
            for t in p.twin_sets:
                units.update(t)
            if units & q:
                keep.append(s_)
            elif share_crosses and any(facts.npair(x, u) > 0 for x in q for u in units):
                # T6x (M-2 group 2): a cross that holds a unit sharing >= 1 sentence with a query unit
                shared.append(s_)
        ks = set(keep) | set(shared)
        unread = tuple(s_ for s_ in seeds if s_ not in ks)
        groups = (("contains_query_unit", tuple(keep)),) + ((("shares_sentence_with_query_unit", tuple(shared)),)
                                                           if share_crosses else ())
        return ReadPlan(groups, tuple(keep) + tuple(shared), unread, len(seeds), None, bool(unread), 0)
    reader_q = lambda u: facts.n[u] + sum(facts.npair(x, u) for x in ctx.energy_units)
    groups: Dict[str, Dict[int, List[str]]] = {"query_unit": {}, "shares_with_query": {}, "rest": {}}
    for s in seeds:
        if s in q:
            g = "query_unit"
        else:
            g = "rest"
            p = placements.cross_for(s)
            units = {c for c in from_cross(p.cross) if c is not None}
            for t in p.twin_sets:
                units.update(t)
            if any(sum(facts.npair(x, u) for x in ctx.energy_units) > 0 for u in units):
                g = "shares_with_query"
        groups[g].setdefault(reader_q(s), []).append(s)
    ordered: List[Tuple[str, Tuple[str, ...]]] = []
    for g in ("query_unit", "shares_with_query", "rest"):
        for val in sorted(groups[g], reverse=True):
            ordered.append((g, tuple(sorted(groups[g][val]))))
    read: List[str] = []
    boundary = 0
    cut = False
    for g, ss in ordered:
        if amount is not None and len(read) + len(ss) > amount:
            cut = True
            boundary = len(ss)
            break
        read.extend(ss)
    rs = set(read)
    unread = tuple(s for s in seeds if s not in rs)
    return ReadPlan(tuple(ordered), tuple(read), unread, len(seeds), amount, bool(unread) or cut, boundary)


# --------------------------------------------------------------------------
# one cross (all members of its class)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class MemberOutcome:
    member: int
    kind: str                         # CANDIDATE | NONE_ | AMBIG | NOFIX
    unit: Optional[str]               # the answer (CANDIDATE)
    status: Optional[str]             # typed reason (NONE_) / budget name (NOFIX)
    inv: Optional[Fraction]
    settled: Settled


def member_outcome(i: int, s: Settled) -> MemberOutcome:
    """L-106."""
    if s.budget_hit is not None:
        return MemberOutcome(i, NOFIX, None, s.budget_hit, None, s)
    answers = {e.answer for e in s.ends}
    inv = min(e.inv for e in s.ends)
    if len(answers) > 1:
        return MemberOutcome(i, AMBIG, None, None, None, s)
    (a,) = answers
    if a is not None:
        return MemberOutcome(i, CANDIDATE, a, en.AGREE, inv, s)
    sts = sorted({_nonanswer_status(e) for e in s.ends})
    return MemberOutcome(i, NONE_, None, sts[0] if len(sts) == 1 else "mixed", inv, s)


def _nonanswer_status(e: EndState) -> str:
    if e.status == en.AGREE:
        return "ungrounded"           # N-03: agreed but no working section with a query unit
    return e.status


@dataclass(frozen=True)
class SeedRead:
    seed: str
    members_total: int
    members: Tuple[MemberOutcome, ...]    # the members read


def members_of(placement: Placement, cap: Optional[int] = None):
    """L-111: the members of the class (expanded), canonical order, at most `cap`; returns
    (flats, total)."""
    total = placement.expanded_size
    if placement.twin_sets:
        flats = placement.expanded_members()
    else:
        flats = placement.members
    if cap is not None:
        flats = flats[:cap]
    return tuple(flats), total


def read_cross(reader: Reader, placement: Placement, budget: QueryBudget = QueryBudget(),
               member_cap: Optional[int] = None) -> SeedRead:
    flats, total = members_of(placement, member_cap)
    outs = tuple(member_outcome(i, settle(reader, f, placement.L, budget)) for i, f in enumerate(flats))
    return SeedRead(placement.seed, total, outs)


# --------------------------------------------------------------------------
# aggregation (I-14, L-107, L-108)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Candidate:
    unit: str
    inv: Fraction
    seed: str
    member: int
    end: EndState


def adopt_members(sr: SeedRead, rule: str = "stable_any") -> List[Candidate]:
    """L-107: among the members that reached a fixed point (all, or only answering ones) the
    most stable are adopted; their answering results are the seed's candidates (several
    different ones = a list, the CHOICE of this cross)."""
    if rule not in ("stable_any", "answering_only"):
        raise ValueError(rule)
    pool = [m for m in sr.members if m.kind == CANDIDATE or (rule == "stable_any" and m.kind == NONE_)]
    if not pool:
        return []
    best = max(m.inv for m in pool)
    out: List[Candidate] = []
    for m in pool:
        if m.inv == best and m.kind == CANDIDATE:
            e = min(m.settled.ends, key=lambda x: (x.inv, flat_key(x.flat)))
            out.append(Candidate(m.unit, best, sr.seed, m.member, e))
    return out


# --------------------------------------------------------------------------
# result
# --------------------------------------------------------------------------
def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


@dataclass(frozen=True)
class TierResult:
    tier: str
    question: str
    ctx: QueryContext
    plan: ReadPlan
    verdict: str
    units: Tuple[str, ...]                    # the answer unit (ANSWER) or the listed units (CHOICE)
    stability: Optional[Fraction]
    candidates: Tuple[Candidate, ...]         # the adopted candidates at the best stability
    reads: Tuple[SeedRead, ...]
    counts: Dict[str, int]
    members_read: int
    members_total: int
    stack_points: Tuple[dict, ...]            # N-11: starts that hit the budget
    energy_logs: Tuple[dict, ...]
    member_rule: str
    alt_verdict: Tuple[str, Tuple[str, ...]]  # the other member rule's verdict (reporting)
    budget: QueryBudget
    state_digest: str
    state_version: int = 0
    ms: int = 0                               # wall time in milliseconds (not part of the output bytes)
    state: Optional[dict] = None              # M-3: the full search state (only when asked for)
    variant: Optional[dict] = None            # T6v: set only when a variant option is on (else None: bytes unchanged)

    def answer_obj(self) -> dict:
        part = None
        if self.plan.partial:
            part = {"read": len(self.plan.read), "unread": len(self.plan.unread),
                    "total": self.plan.total, "amount": self.plan.amount,
                    "tied_group_not_split": self.plan.boundary}
        trace = [{"tier": self.tier, "seed": c.seed, "member": c.member, "unit": c.unit,
                  "stability": _fs(c.inv), "state": list(c.end.flat), "key": list(c.end.key)[:2] + [c.end.key[2]],
                  "sentences": None} for c in self.candidates]
        return {"verdict": self.verdict, "units": list(self.units), "stability": _fs(self.stability),
                "partial_read": part, "candidates": len(self.candidates), "trace": trace}

    def thought_obj(self) -> dict:
        p = self.plan
        return {
            "tier": self.tier, "question": self.question, "query": self.ctx.qcross.to_json_obj(),
            "query_first_layer": list(self.ctx.qcross.units), "energy_scope": self.ctx.scope,
            "inner_layers_pending": [list(c.units) for c in self.ctx.qcross.layers()[1:]],
            "read": {"crosses_read": len(p.read), "crosses_unread": len(p.unread), "total": p.total,
                     "amount": p.amount, "members_read": self.members_read,
                     "members_total": self.members_total,
                     "groups": [[g, len(s)] for g, s in p.order_groups]},
            "search": dict(sorted(self.counts.items())), "budget": {"max_states": self.budget.max_states,
                                                                      "max_ends": self.budget.max_ends},
            "member_rule": self.member_rule,
            "alt_member_rule_verdict": {"verdict": self.alt_verdict[0], "units": list(self.alt_verdict[1])},
            "stacking": {"would_stack": bool(self.stack_points), "points": list(self.stack_points)},
            "energy_log": list(self.energy_logs),
            "state_version": self.state_version,
            "search_state_digest": self.state_digest,
            **({"variant": self.variant} if self.variant is not None else {}),
        }

    def to_json_obj(self) -> dict:
        return {"answer": self.answer_obj(), "thought": self.thought_obj()}

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json_obj(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def search_state_obj(tier: str, ctx: QueryContext, reads: Sequence[SeedRead]) -> dict:
    """M-3: the search state in a storable form (T10/T11 store it; nothing is stored here)."""
    recs = []
    for sr in sorted(reads, key=lambda r: r.seed):
        ms = []
        for m in sr.members:
            ms.append({"i": m.member, "kind": m.kind, "unit": m.unit, "status": m.status,
                       "inv": _fs(m.inv), "expanded": m.settled.expanded, "accepted": m.settled.accepted,
                       "start": list(m.settled.start),
                       "ends": [{"state": list(e.flat), "key": list(e.key), "status": e.status,
                                 "answer": e.answer, "inv": _fs(e.inv), "moves": e.moves} for e in m.settled.ends]})
        recs.append({"seed": sr.seed, "members_total": sr.members_total, "members": ms})
    return {"format": STATE_FORMAT, "tier": tier, "query": list(ctx.query),
            "first_layer": list(ctx.qcross.units), "scope": ctx.scope, "records": recs}


def _digest(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _verdict_from(reads: Sequence[SeedRead], rule: str, grounded_possible: bool = True):
    """L-108.  Returns (verdict, units, stability, candidates, counts)."""
    cands: List[Candidate] = []
    for sr in reads:
        cands.extend(adopt_members(sr, rule))
    if cands:
        best = max(c.inv for c in cands)
        top = [c for c in cands if c.inv == best]
        units = tuple(sorted({c.unit for c in top}))
        top.sort(key=lambda c: (c.unit, c.seed, c.member))
        return (ANSWER if len(units) == 1 else CHOICE), units, best, tuple(top)
    if not grounded_possible:
        return UNKNOWN_NO_EVIDENCE, (), None, ()       # N-03: no query unit is in the space at all
    kinds: Dict[str, int] = {}
    for sr in reads:
        for m in sr.members:
            k = m.kind if m.kind != NONE_ else "none:" + str(m.status)
            kinds[k] = kinds.get(k, 0) + 1
    if kinds.get(AMBIG):
        return AMBIGUOUS, (), None, ()
    if kinds.get(NOFIX):
        return UNKNOWN_NO_FIXED_POINT, (), None, ()
    if kinds.get("none:" + en.RATIO_DISAGREEMENT) or kinds.get("none:mixed"):
        return UNKNOWN_RATIO_DISAGREEMENT, (), None, ()
    if kinds.get("none:" + en.SECTION_DISAGREEMENT):
        return UNKNOWN_SECTION_DISAGREEMENT, (), None, ()
    return UNKNOWN_NO_EVIDENCE, (), None, ()


def _verdict_query_share(reads: Sequence[SeedRead], facts: TierFacts, ctx: QueryContext):
    """T6v V3 (option): the candidate states = the end states (fixed points) of every answering
    member of every cross read; the adopted ones are those sharing the most sentences with the
    query units (|sentences holding a unit of the state  AND  sentences holding a query unit|,
    exact integers), instead of the post-query stability rule.  Ties -> all kept (a list).
    The same flat state reached from several crosses is one candidate (first origin in seed /
    member order is kept as its Candidate).  Verdict: one answer unit -> ANSWER, several ->
    CHOICE, no candidate -> the L-108 failure typing.  Returns (verdict, units, stability, cands,
    info) with stability = the best stability among the adopted states (reporting only)."""
    post = facts.tier.postings
    mask: Dict[str, int] = {}

    def m(u: str) -> int:
        v = mask.get(u)
        if v is None:
            v = 0
            for sid in post.get(u, ()):
                v |= 1 << sid
            mask[u] = v
        return v

    qm = 0
    for u in ctx.energy_units:
        qm |= m(u)
    seen: Dict[Flat, Tuple[int, Candidate]] = {}
    for sr in sorted(reads, key=lambda r: r.seed):
        for mo in sr.members:
            if mo.kind != CANDIDATE:
                continue
            for e in mo.settled.ends:
                if e.answer is None or e.flat in seen:
                    continue
                sm = 0
                for u in set(c for c in e.flat if c is not None):
                    sm |= m(u)
                seen[e.flat] = (bin(sm & qm).count("1"), Candidate(e.answer, e.inv, sr.seed, mo.member, e))
    if not seen:
        v = _verdict_from(reads, "stable_any", True)
        return v[0], v[1], v[2], v[3], {"states": 0, "best_share": None}
    best = max(sc for sc, _ in seen.values())
    top = [c for sc, c in seen.values() if sc == best]
    units = tuple(sorted({c.unit for c in top}))
    top.sort(key=lambda c: (c.unit, c.seed, c.member))
    stab = max(c.inv for c in top)
    return (ANSWER if len(units) == 1 else CHOICE), units, stab, tuple(top), \
        {"states": len(seen), "best_share": best, "tied_states": len(top)}


def _ask_tier_once(tier: TierSpace, question: str, placements, *, units: Optional[Sequence[str]] = None,
             facts: Optional[TierFacts] = None, amount: Optional[int] = None,
             budget: QueryBudget = QueryBudget(), member_cap: Optional[int] = None,
             scope: str = "first_layer", member_rule: str = "stable_any",
             with_state: bool = False, clock=None,
             read_rule: Optional[str] = None, state_rule: str = "query_share",
             unit_filter="default") -> TierResult:
    """One question on one tier: read the crosses that hold a query unit (V1; `read_rule="whole"`
    = I-08, every cross, or `amount` crosses marked partial), every member of every cross, settle,
    adopt the states by the sentences they share with the query (V3; `state_rule="stability"` =
    the post-query stability rule).  Function / question words of the question are dropped (V2;
    `unit_filter=None` = keep them; a predicate = own rule).  Since L-150 these three are the
    defaults; the old behaviour stays available as the explicit options.  `placements` has
    cross_for(seed).  `read_rule=None` = "query_crosses", except that an explicit `amount` (M-2
    amount of inference, an ordered partial read of the whole space) selects "whole"."""
    import time
    t0 = time.monotonic_ns()
    facts = facts or TierFacts(tier)
    if read_rule is None:
        read_rule = "whole" if amount is not None else "query_crosses"
    if read_rule not in ("whole", "query_crosses", "query_share_crosses") or state_rule not in ("stability", "query_share"):
        raise ValueError("read_rule: whole | query_crosses | query_share_crosses; state_rule: stability | query_share")
    q = tuple(units) if units is not None else split_question(tier.name, question)
    if isinstance(unit_filter, str):                 # "default": the function-word rule of this tier (L-150)
        if unit_filter != "default":
            raise ValueError("unit_filter: a predicate, None, or 'default'")
        from verantyx.line3.funcwords import default_filter
        unit_filter = default_filter(tier.name)
    if unit_filter is not None:                      # T6v V2: question words / function words are not units either
        q = tuple(u for u in q if not unit_filter(u))
    ctx = make_context(q, scope)
    reader = Reader(facts, ctx.attached, ctx.energy_units)
    plan = plan_read(tier, facts, ctx, placements, amount, read_rule in ("query_crosses", "query_share_crosses"),
                     read_rule == "query_share_crosses")
    reads: List[SeedRead] = []
    for seed in sorted(plan.read):                  # canonical order; the result never depends on it
        reads.append(read_cross(reader, placements.cross_for(seed), budget, member_cap))
    gp = any(facts.n.get(u, 0) > 0 for u in ctx.attached if u is not None)
    vinfo = None
    if state_rule == "query_share":
        verdict, vunits, stab, cands, vinfo = _verdict_query_share(reads, facts, ctx)
    else:
        verdict, vunits, stab, cands = _verdict_from(reads, member_rule, gp)
    other = "answering_only" if member_rule == "stable_any" else "stable_any"
    av = _verdict_from(reads, other, gp)
    variant = None
    if read_rule != "whole" or state_rule != "stability" or unit_filter is not None:
        variant = {"read_rule": read_rule, "state_rule": state_rule, "unit_filter": unit_filter is not None,
                   "query_after_filter": list(q), "state_choice": vinfo}
    counts: Dict[str, int] = {"crosses_read": len(reads)}
    mread = mtot = 0
    stack: List[dict] = []
    for sr in reads:
        mtot += sr.members_total
        mread += len(sr.members)
        for m in sr.members:
            k = m.kind if m.kind != NONE_ else "none:" + str(m.status)
            counts[k] = counts.get(k, 0) + 1
            counts["states_expanded"] = counts.get("states_expanded", 0) + m.settled.expanded
            counts["moves_accepted"] = counts.get("moves_accepted", 0) + m.settled.accepted
            if m.kind == NOFIX:
                stack.append({"seed": sr.seed, "member": m.member, "reason": m.status,
                              "expanded": m.settled.expanded, "state": list(m.settled.start)})
            if m.kind == CANDIDATE:
                counts["fixed_points_answering"] = counts.get("fixed_points_answering", 0) + len(m.settled.ends)
    counts["members_read"] = mread
    counts["members_total"] = mtot
    # observation record L-20 on the adopted end states
    logs: List[dict] = []
    from verantyx.line3.placement import energy_log
    for c in cands:
        cr = to_cross(c.end.flat, _L_of(c.end.flat))
        logs.append({"seed": c.seed, "member": c.member, **energy_log(tier, cr, ctx.energy_units).to_json_obj()})
    sobj = search_state_obj(tier.name, ctx, reads)
    return TierResult(tier.name, question, ctx, plan, verdict, vunits, stab, cands, tuple(reads), counts,
                      mread, mtot, tuple(stack), tuple(logs), member_rule, (av[0], av[1]), budget,
                      _digest(sobj), 0, (time.monotonic_ns() - t0) // 1000000, sobj if with_state else None,
                      variant)


class _OverlayPlacements:
    """L-171: the stored placements with some crosses replaced (rebuilt at a higher budget level)."""

    def __init__(self, base, repl: Mapping[str, Placement]) -> None:
        self._base, self._repl = base, dict(repl)

    def cross_for(self, seed: str) -> Placement:
        return self._repl[seed] if seed in self._repl else self._base.cross_for(seed)


RAISE_LEVELS_DEFAULT = ("high", "max")


def ask_tier(tier: TierSpace, question: str, placements, *, raise_budget: Optional[str] = None,
             raise_levels: Sequence[str] = RAISE_LEVELS_DEFAULT, weights=None, **kw) -> TierResult:
    """`_ask_tier_once` (all its keywords) plus T6y option `raise_budget="on_demand"` (L-171, owner:
    "問いで必要になったときだけ上げる"): the placement budget of a cross is raised only when a query needs
    it.  "Needs" = the question has no adopted state and a cross it read stopped by budget (stop ==
    "budget"; an "exhausted" cross cannot grow).  Those crosses are rebuilt (placement.build_cross) at
    each level of `raise_levels` above their own, in order, and the question is asked again with the
    rebuilt crosses in place of the stored ones, until a state is adopted or the levels run out.  What
    was raised is recorded in thought_obj()["variant"]["budget_raise"] (the stored placements are
    not changed).  Default None: exactly `_ask_tier_once`."""
    res = _ask_tier_once(tier, question, placements, **kw)
    if raise_budget is None:
        return res
    if raise_budget != "on_demand":
        raise ValueError("raise_budget: None | on_demand")
    from verantyx.line3 import placement as pl
    order = pl.LEVEL_ORDER
    for lv in raise_levels:
        if lv not in order:
            raise ValueError("raise_levels: names of placement levels")
    steps: List[dict] = []
    repl: Dict[str, Placement] = {}
    cur = res
    w = weights
    for lv in raise_levels:
        if cur.candidates:
            break
        def lvl(sd: str) -> int:        # level index of the cross now in place (a custom budget counts as below "low")
            nm = pl.level_name(repl.get(sd, placements.cross_for(sd)).budget)
            return order.index(nm) if nm is not None else -1

        limited = sorted(sd for sd in cur.plan.read
                         if repl.get(sd, placements.cross_for(sd)).stop == "budget" and lvl(sd) < order.index(lv))
        if not limited:
            break
        w = w or pl.Weights(tier)
        rec = []
        for sd in limited:
            before = repl.get(sd, placements.cross_for(sd))
            nb = pl.build_cross(tier, sd, w, budget=pl.budget_level(lv))
            repl[sd] = nb
            rec.append({"seed": sd, "capacity_before": before.capacity, "capacity_after": nb.capacity,
                        "stop_after": nb.stop})
        cur = _ask_tier_once(tier, question, _OverlayPlacements(placements, repl), **kw)
        steps.append({"level": lv, "raised": rec, "verdict": cur.verdict, "states_adopted": len(cur.candidates),
                      "crosses_read": len(cur.plan.read)})
    info = {"mode": "on_demand", "levels": list(raise_levels), "needed": bool(steps), "steps": steps,
            "final_level": steps[-1]["level"] if steps else None}
    var = dict(cur.variant or {})
    var["budget_raise"] = info
    return replace(cur, variant=var)


def _L_of(flat: Flat) -> int:
    return (len(flat) - 1) // N_ARMS


class PlacementStore:
    """A read-only mapping seed -> Placement (e.g. loaded from the precompute cache)."""

    def __init__(self, placements: Mapping[str, Placement]) -> None:
        self._p = dict(placements)

    def cross_for(self, seed: str) -> Placement:
        return self._p[seed]
