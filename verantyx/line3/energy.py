"""T3 energy and the three ratios of the line-3 build.  Exact Fractions only (L-02).

Binding decisions (ops/decisions/2026-10-06_line3_faithful_build.md):
  I-06 + N-01  a unit's energy = initial ratio r0(v) = n(v)/N  +  the share of
               sentences it has in common with the query units, sum_q n(q,v)/N.
  I-10         three separate quantities: (1) section (walk toward the centre while
               energy does not drop), (2) edge (energy flowing in along cross edges),
               (3) placement (how tightly the placement binds each unit).
  I-11         "the three agree" = all three point to the same single unit.  A tie
               (or no evidence) points nowhere; there is no threshold.
  I-09         sections are the current windows: geometry.visible_arms.
  I-03         edges = adjacency on the cross (geometry.neighbours).

Local choices (new, listed in the T3 report; design leaves the detail open):
  L-50  n(q,q) = n(q): a query unit shares every sentence with itself, so a placed
        query unit gets +n(q)/N (literal reading of the N-01 formula).
  L-51  The query is a set: repeated query units count once.
  L-52  Query units or placed units absent from the space have n = 0 (energy 0,
        no shared sentences); they are neither errors nor evidence.
  L-53  Placed unit absent from the space: r0 = 0 (same rule as L-52).
  L-54  A section looks along every arm visible in its window (I-09); each arm is
        walked separately; the section points to the terminus with the strictly
        greatest energy (same unit from several arms is one candidate; a tie
        between different units, or no terminus, points nowhere).
  L-55  Walk (design 4.4 R1): outer end k=0 -> ... -> k=L-1 -> centre.  A step
        x -> y is taken iff y is not an empty seat, the edge is evidenced
        (n(x,y) > 0) and E_s(y) >= E_s(x) ("does not drop").  The unit where the
        walk stops is the terminus (the centre unit if the centre is reached).
        A walk starting on an empty seat has no terminus.
  L-56  A unit placed on several seats gets the sum of its per-seat F and B.
        Pairs of seats holding the same unit contribute nothing.
  L-57  A "working" section is one whose pointer is not None.  The section ratio
        R1 points to u iff there is at least one working section and all working
        sections point to u.  Working sections that point to different units give
        status "section_disagreement" (design 4.8); R1 is then None.
  L-58  A maximum must be strictly positive to point at a unit: an all-zero
        quantity carries no evidence and points nowhere.
  L-59  A section's energy is E_q when a query unit q is attached to it (I-07,
        design 4.1) and E_Q otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from verantyx.line3.geometry import (
    AXES, CENTER, DEFAULT_WINDOW, Cross, Seat, neighbours, visible_arms,
)
from verantyx.line3.space import TierSpace

ZERO = Fraction(0)

AGREE = "agree"
POINTS_NOWHERE = "points_nowhere"              # I-11: tie / no evidence / no working section
RATIO_DISAGREEMENT = "ratio_disagreement"      # design 4.8
SECTION_DISAGREEMENT = "section_disagreement"  # design 4.8


# --------------------------------------------------------------------------
# counts (guarded for units outside the space; L-52, L-53)
# --------------------------------------------------------------------------
def _n(t: TierSpace, u: str) -> int:
    """n(u), 0 if u is not in the space (L-52)."""
    return len(t.postings[u]) if u in t.postings else 0


def _n_pair(t: TierSpace, u: str, v: str) -> int:
    """n(u,v); n(u,u) = n(u) (L-50); 0 if either is outside the space (L-52)."""
    if u not in t.postings or v not in t.postings:
        return 0
    return t.n_pair(u, v)


def _query_set(query: Iterable[str]) -> Tuple[str, ...]:
    """L-51: the query as a set of distinct units (canonical order only for stable output)."""
    return tuple(sorted(set(query)))


# --------------------------------------------------------------------------
# energy (I-06, N-01)
# --------------------------------------------------------------------------
def r0(t: TierSpace, u: str) -> Fraction:
    """I-06: initial ratio n(u)/N (0 outside the space, L-53)."""
    return Fraction(_n(t, u), t.N) if t.N else ZERO


def shared_share(t: TierSpace, u: str, q: str) -> Fraction:
    """N-01: share of sentences u has in common with query unit q = n(q,u)/N (L-50)."""
    return Fraction(_n_pair(t, q, u), t.N) if t.N else ZERO


def energy(t: TierSpace, u: str, query: Iterable[str] = ()) -> Fraction:
    """I-06 + N-01: E_Q(u) = r0(u) + sum_{q in Q} n(q,u)/N.  No query: E = r0."""
    return r0(t, u) + sum((shared_share(t, u, q) for q in _query_set(query)), ZERO)


def energies(t: TierSpace, units: Iterable[str], query: Iterable[str] = ()) -> Dict[str, Fraction]:
    """I-06 + N-01: E_Q for each given unit."""
    q = _query_set(query)
    return {u: energy(t, u, q) for u in units}


# --------------------------------------------------------------------------
# I-11: unique maximum, ties point nowhere
# --------------------------------------------------------------------------
def unique_argmax(values: Mapping[str, Fraction]) -> Optional[str]:
    """I-11: the unit with the strictly greatest value, if there is exactly one and
    it is > 0 (L-58); a tie or an empty/zero mapping points nowhere (None).  The
    result never depends on iteration order."""
    if not values:
        return None
    best = max(values.values())
    if best <= ZERO:
        return None
    winners = [u for u, v in values.items() if v == best]
    return winners[0] if len(winners) == 1 else None


# --------------------------------------------------------------------------
# (1) section ratio (I-10, I-09)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ArmWalk:
    arm: str
    path: Tuple[str, ...]            # units visited, outer end first
    terminus: Optional[str]          # None iff the walk could not start
    stop: str                        # "centre" | "end" | "gap" | "unproven" | "drop" | "empty"


@dataclass(frozen=True)
class SectionPointer:
    section: int
    arms: Tuple[str, ...]            # I-09 visible arms
    walks: Tuple[ArmWalk, ...]
    unit: Optional[str]              # None = points nowhere


def _arm_cells(cross: Cross, arm: str) -> List[Tuple[Seat, object]]:
    """I-03, L-55: the cells of one arm from the outer end (k=0) to the centre."""
    i = AXES.index(arm)
    cells = [(Seat(arm, k), cross.arms[i][k]) for k in range(cross.L)]
    cells.append((CENTER, cross.center))
    return cells


def walk_arm(t: TierSpace, cross: Cross, arm: str, query: Iterable[str] = (),
             attached: Optional[str] = None) -> ArmWalk:
    """I-10 (1), L-55, L-59: walk one arm from its outer end toward the centre while
    the edge is evidenced and the energy does not drop.  Energy is E_{attached}
    if a query unit is attached to the section, else E_Q."""
    q = (attached,) if attached is not None else _query_set(query)
    cells = [c for _, c in _arm_cells(cross, arm)]
    if cells[0] is None:
        return ArmWalk(arm, (), None, "empty")
    path = [cells[0]]
    stop = "end"
    for nxt in cells[1:]:
        cur = path[-1]
        if nxt is None:
            stop = "gap"
            break
        if _n_pair(t, cur, nxt) <= 0:
            stop = "unproven"
            break
        if energy(t, nxt, q) < energy(t, cur, q):
            stop = "drop"
            break
        path.append(nxt)
    else:
        stop = "centre"
    return ArmWalk(arm, tuple(path), path[-1], stop)


def section_pointer(t: TierSpace, cross: Cross, section: int, query: Iterable[str] = (),
                    attached: Optional[str] = None,
                    window: int = DEFAULT_WINDOW) -> SectionPointer:
    """I-10 (1), I-09, L-54: the unit a section points to (strictly greatest energy
    among the walk termini of its visible arms), or None."""
    arms = visible_arms(cross.orientation, section, window)
    walks = tuple(walk_arm(t, cross, a, query, attached) for a in arms)
    q = (attached,) if attached is not None else _query_set(query)
    cand = {w.terminus: energy(t, w.terminus, q) for w in walks if w.terminus is not None}
    return SectionPointer(section, arms, walks, unique_argmax(cand))


# --------------------------------------------------------------------------
# (2) edge ratio and (3) placement ratio (I-10, I-03)
# --------------------------------------------------------------------------
def _placed(cross: Cross) -> List[Tuple[Seat, str]]:
    """I-03: every occupied seat (centre first, then AXES order, k ascending)."""
    out = [(CENTER, cross.center)] if cross.center is not None else []
    for a in AXES:
        for k in range(cross.L):
            c = cross.arms[AXES.index(a)][k]
            if c is not None:
                out.append((Seat(a, k), c))
    return [(s, str(c)) for s, c in out]


def edge_flow(t: TierSpace, cross: Cross, query: Iterable[str] = ()) -> Dict[str, Fraction]:
    """I-10 (2), L-56: F(v) = sum over cross neighbours u of E_Q(u) * n(u,v)/n(u)."""
    q = _query_set(query)
    out: Dict[str, Fraction] = {}
    for seat, v in _placed(cross):
        total = out.get(v, ZERO)
        for nb in neighbours(seat, cross.L):
            u = cross.get(nb)
            if u is None or str(u) == v or _n(t, str(u)) == 0:
                continue
            u = str(u)
            total += energy(t, u, q) * Fraction(_n_pair(t, u, v), _n(t, u))
        out[v] = total
    return out


def placement_binding(t: TierSpace, cross: Cross) -> Dict[str, Fraction]:
    """I-10 (3), L-56: B(v) = sum over cross neighbours u of n(u,v)/n(v)."""
    out: Dict[str, Fraction] = {}
    for seat, v in _placed(cross):
        total = out.get(v, ZERO)
        nv = _n(t, v)
        if nv:
            for nb in neighbours(seat, cross.L):
                u = cross.get(nb)
                if u is None or str(u) == v:
                    continue
                total += Fraction(_n_pair(t, str(u), v), nv)
        out[v] = total
    return out


# --------------------------------------------------------------------------
# agreement (I-11)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Verdict:
    sections: Tuple[SectionPointer, ...]
    working: int                     # sections whose pointer is not None (L-57)
    working_attached: int            # of those, sections with a query unit attached (N-03 input for T5)
    section_unit: Optional[str]      # R1
    edge_unit: Optional[str]         # R2
    placement_unit: Optional[str]    # R3
    status: str
    unit: Optional[str]              # the agreed unit iff status == AGREE


def three_ratios(t: TierSpace, cross: Cross, query: Iterable[str] = (),
                 attached: Optional[Mapping[int, str]] = None,
                 window: int = DEFAULT_WINDOW) -> Verdict:
    """I-10, I-11: compute the three separate ratios and decide agreement.

    attached maps world section (0..5) -> query unit attached to it (I-07; T5 supplies
    it).  AGREE iff R1, R2, R3 each point to a unit and it is the same unit; any
    ratio pointing nowhere gives POINTS_NOWHERE (abstain-type, no threshold)."""
    q = _query_set(query)
    att = dict(attached or {})
    secs = tuple(section_pointer(t, cross, s, q, att.get(s), window) for s in range(len(AXES)))
    working = [s for s in secs if s.unit is not None]
    units = {s.unit for s in working}
    r1 = next(iter(units)) if len(units) == 1 else None
    r2 = unique_argmax(edge_flow(t, cross, q))
    r3 = unique_argmax(placement_binding(t, cross))
    if len(units) > 1:
        status = SECTION_DISAGREEMENT
    elif r1 is None or r2 is None or r3 is None:
        status = POINTS_NOWHERE
    elif r1 == r2 == r3:
        status = AGREE
    else:
        status = RATIO_DISAGREEMENT
    return Verdict(secs, len(working), sum(1 for s in working if att.get(s.section) is not None),
                   r1, r2, r3, status, r1 if status == AGREE else None)
