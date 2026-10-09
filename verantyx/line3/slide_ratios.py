"""G3-d: the three ratios PER AXIS of a window cross and the labelled per-axis answer
(docs/LINE3_G3_SLIDING_PACKS.md 3.3 - 3.5, 7.3; ticket G3-d).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md; the binding words, verbatim):
  decision 7 「断面から中心の経路、…辺を伝った時、配置自体で空間のエネルギー比率の３つで一致した時に安定」
        -> (1) section walk from the cross-section to the centre, (2) the edge flow along the edges, (3) the placement
           binding; "stable" = the three agree (I-11: all three point to the same ONE unit).
  G2 3  「エネルギー比を軸ごとに計算する」                       -> every ratio is computed per axis a in {x, y, z}
  G3 4  「軸ごとに判定し、一致した軸がそれぞれラベル付きの答えを出す」 -> agreement per axis; an agreeing axis gives an answer
           labelled with its axis, a non-agreeing axis gives a typed abstention
  G3 6  「梯子の順に x、y、z へ。重みは辺の流れと配置の結合と読む順に」 -> the Fibonacci weights of the arm labels enter THREE
           places and no other:  (a) the edge flow, (b) the placement binding, (c) the read order of the answers
  I-04 key (not touched here), I-06 + N-01 query energy E_Q (energy.py, unchanged), I-07 question attachment (cycle.make_context,
  reused), I-09 sections = arm windows (geometry.visible_arms), I-10 three separate quantities, I-11 one unit, L-54..L-59 (energy.py).

What this module is.  A reader of ONE window cross (the placement record of slide_place, or any list of seats keyed by
(unit, sid)) with the per-axis counts of slide.counts.  Nothing is searched, nothing is placed, nothing is hooked into ask /
cycle (G3-e).  All numbers are int / Fraction; no float, no randomness, nothing taken from a set or dict without an order.

  axis of an edge   = the axis of the ARM the edge lies on (the arm of its OUTER seat; the inner end of an arm's last seat is
                      the centre).  Every edge lies on exactly one arm, so the axes PARTITION the edges (L-601).
  evidence n_a      = +x/-x n_x(o,i) (symmetric); +y n_y(o,i), -y n_y(i,o); +z n_z(o,i), -z n_z(i,o), with o the OUTER and i the
                      INNER seat of the edge; both ends of an edge see the same number (L-602).
  R1_a section walk = for each section s (arm windows, geometry.visible_arms) only the arms of axis a among the visible ones are
                      walked, outer end -> centre, a step needs n_a(edge) > 0 and "the energy does not drop" (L-55, L-59: E_q of
                      the query unit attached to the section by I-07, else E_Q); a section points to the strict maximum of its
                      termini; sections that see no arm of axis a are not sections of a; R1_a = the one unit all working
                      sections of a point to (L-603).  NO weight.
  R2_a edge flow    = F_a(v) = sum over a-edges e = (u, v) of  w(arm e) * E_Q(u) * n_a(e) / n(u)
  R3_a binding      = B_a(v) = sum over a-edges e = (u, v) of  w(arm e) * n_a(e) / n(v)
                      w(arm) = the Fibonacci weight of the foundation label ON THAT ARM (+x の 144/377, -x に 89/377, +y で 55/377,
                      -y と 34/377, +z を 21/377, -z が 13/377).  THE WEIGHT MULTIPLIES THE WHOLE EDGE TERM, once per edge,
                      identically at both ends of the edge, in F_a and in B_a and nowhere else: not in R1, not in E_Q / n / N / r0,
                      not in n_a, not in the key (I-G3-2).  The unweighted F_a / B_a are computed beside them and recorded
                      (`edge_flow_plain`, `binding_plain`): they are what the merged check of 7.3 compares (L-604, L-605).
  agreement         = per axis: AGREE iff R1_a = R2_a = R3_a = one unit (R2, R3 decided by the WEIGHTED values); otherwise a typed
                      abstention (points_nowhere / section_disagreement / ratio_disagreement / no_edges) (L-606).
  answers           = one per agreeing axis, `slide:x` / `slide:y` / `slide:z`, in READ ORDER = axis weight (w(+a) + w(-a)) descending,
                      the third place of the weights (L-608).  Each carries its unit, the three ratio values (exact Fractions),
                      the seats of the unit keyed (unit, sid), the contributing edges with their counts' sources, the sections'
                      walk steps with their sources, and `grounded` (L-104: working sections of the axis with an in-space query unit;
                      N-03 is NOT applied here, G3-e does it, L-607).
G3-d addendum (owner decisions after G3-d): `agreement` "three" (default) | "two_if_single_edge" (L-615) and `z_self_edges`
default ON (L-616); the weights stay per arm.
Seats are keyed by (unit, sid) from the start: the current record seats a unit once (a unit of both sentences gets sid of N);
the two-seat format of G3-c2 (a unit of both sentences has one seat per sentence, linked by z) comes in through `record.seats` / `record.items`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from verantyx.line3 import cycle as cy
from verantyx.line3 import energy as en
from verantyx.line3 import geometry as geo
from verantyx.line3 import slide as SL
from verantyx.line3.space import TierSpace

FORMAT = "line3.slide_ratios.v1"
ZERO = Fraction(0)
ONE = Fraction(1)
AXES: Tuple[str, ...] = SL.AXES                            # ("x", "y", "z")
ARM_NAMES: Tuple[str, ...] = geo.AXES                      # ("+x", "-x", "+y", "-y", "+z", "-z")
UNIT_WEIGHTS: Mapping[str, Fraction] = {a: ONE for a in ARM_NAMES}      # the unweighted reading (merged check, 7.3)

AGREE = en.AGREE
POINTS_NOWHERE = en.POINTS_NOWHERE
SECTION_DISAGREEMENT = en.SECTION_DISAGREEMENT
RATIO_DISAGREEMENT = en.RATIO_DISAGREEMENT
AGREEMENTS: Tuple[str, ...] = ("three", "two_if_single_edge")      # L-615: the agreement rule (a spec switch of the reading)
NO_EDGES = "no_edges"             # L-606: the axis has no edge with both ends seated (y in S1): structure, not evidence

SeatKey = Tuple[str, int]         # (unit, sid)
Evidence = Callable[[str, str, str], Tuple[int, tuple]]      # (arm, outer unit, inner unit) -> (n_a, sources)

WEIGHTS_ENTER_TEXT = ("the weight w(arm) multiplies the whole edge term of F_a and of B_a (once per edge, both ends alike) and "
                      "orders the answers (axis weight descending); it is in no other quantity")


def axis_of_arm(arm: str) -> str:
    return arm[1]


# --------------------------------------------------------------------------------------------------------------
# seats keyed (unit, sid), and the window cross
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class SeatRec:
    """One seat: the unit, the sentence it is read in, the arm ("center" for the centre) and the position (k = 0 the outer end
    .. L-1 next to the centre; 0 for the centre), and the sources of the unit's occurrence (rows; may be empty)."""
    unit: str
    sid: int
    arm: str
    position: int
    sources: Tuple[tuple, ...] = ()

    @property
    def key(self) -> SeatKey:
        return (self.unit, self.sid)

    @property
    def seat(self) -> geo.Seat:
        return geo.CENTER if self.arm == geo.CENTER.arm else geo.Seat(self.arm, self.position)

    def doc(self) -> dict:
        return {"unit": self.unit, "sid": self.sid, "arm": self.arm, "position": self.position,
                "sources": [list(s) for s in self.sources]}


@dataclass(frozen=True)
class WindowCross:
    L: int
    seats: Tuple[SeatRec, ...]                        # in geometry.seats(L) order
    tier: str
    sids: Tuple[int, ...]
    orientation: geo.Rotation = geo.IDENTITY
    meta: Tuple[Tuple[str, object], ...] = ()         # what the record said about itself (spec shas, window, scope, pad flag)

    def __post_init__(self) -> None:
        seen = set()
        keys = set()
        for s in self.seats:
            if s.arm != geo.CENTER.arm and s.arm not in ARM_NAMES:
                raise ValueError("bad arm %r" % (s.arm,))
            if s.arm != geo.CENTER.arm and not 0 <= s.position < self.L:
                raise ValueError("seat %r out of range for L=%d" % (s.seat, self.L))
            if s.seat in seen:
                raise ValueError("two units on seat %r" % (s.seat,))
            if s.key in keys:
                raise ValueError("(unit, sid) %r on two seats" % (s.key,))
            seen.add(s.seat)
            keys.add(s.key)

    def by_seat(self) -> Dict[geo.Seat, SeatRec]:
        return {s.seat: s for s in self.seats}

    def units(self) -> Tuple[str, ...]:
        """The distinct units, in seat order."""
        return tuple(dict.fromkeys(s.unit for s in self.seats))

    def to_cross(self) -> geo.Cross:
        """The same cells as a geometry.Cross (a unit on two seats is the same string on two cells: energy.py's L-56)."""
        by = self.by_seat()
        arms = [[(by[geo.Seat(a, k)].unit if geo.Seat(a, k) in by else None) for k in range(self.L)] for a in ARM_NAMES]
        c = by.get(geo.CENTER)
        return geo.Cross.make(L=self.L, center=None if c is None else c.unit, arms=arms, orientation=self.orientation)

    def doc(self) -> dict:
        return {"L": self.L, "tier": self.tier, "sids": list(self.sids), "orientation": list(self.orientation.perm),
                "seats": [s.doc() for s in self.seats], "record": {k: v for k, v in self.meta}}


def _get(x, k, default=None):
    return x.get(k, default) if isinstance(x, Mapping) else getattr(x, k, default)


def _norm_sources(src) -> Tuple[tuple, ...]:
    """A seat's sources as rows.  G3-c2's `sources` is {"occ": [tier, sid, k, unit, start, end] | None, "edge": {axis, arm, with:
    {unit, sid}, n, omega, sources} | None} -> ("occ", tier, sid, k, unit, start, end) and ("edge", axis, arm, unit, sid, n, omega);
    a list of rows stays a list of rows; nothing -> ()."""
    if not src:
        return ()
    if isinstance(src, Mapping):
        rows = []
        occ = src.get("occ")
        if occ:
            rows.append(("occ",) + tuple(occ))
        e = src.get("edge")
        if e:
            w = e.get("with") or {}
            rows.append(("edge", e.get("axis"), e.get("arm"), w.get("unit"), w.get("sid"), e.get("n"), e.get("omega")))
        return tuple(rows)
    return tuple(tuple(r) if isinstance(r, (list, tuple)) else (r,) for r in src)


def _arm_name(arm: str) -> str:
    return geo.CENTER.arm if arm in ("centre", "center") else str(arm)


def window_cross(record, member: int = 0, *, orientation: geo.Rotation = geo.IDENTITY,
                 pack: Optional[Sequence[SL.Occ]] = None) -> WindowCross:
    """Read a window placement record into seats keyed (unit, sid) (L-600).
    * member 0 of a record with `seats` (G3-c2: a list of {unit, sid, arm ("centre" or an arm name), position (0 = the outermost
      seat of the arm), sources}): used as given;
    * another member of a record with `items` (the seats in insertion order, token -> (unit, sid)): the member's flat read through
      the tokens (index 0 = centre, 1 + a*L + k = arm a of geometry.AXES at position k); no seat sources;
    * the G3-c record (`members`, `L`, `order_log`): a unit has ONE seat; its sid is the first sentence it is read in: sids[0]
      for "this" and "both", sids[1] for "next" (order_log).  `pack` (slide.pack(window)) then gives the seat's sources: the
      unit's occurrence rows (a unit of both sentences: in both)."""
    tier = _get(record, "tier")
    pw = _get(record, "window")
    win = _get(pw, "window", pw)
    sids = tuple(_get(win, "sids"))
    meta = tuple((k, v) for k, v in (       # an object has spec_sha / slide_spec_sha, its doc (a jsonl line) spec_sha256 / ...
        ("spec_sha256", _get(record, "spec_sha", _get(record, "spec_sha256"))),
        ("slide_spec_sha256", _get(record, "slide_spec_sha", _get(record, "slide_spec_sha256"))),
        ("scope", _get(record, "scope")), ("window_n", _get(win, "n")), ("title", _get(win, "title")),
        ("constructed", _get(pw, "constructed", False)), ("member", member)) if v is not None)
    given = _get(record, "seats")
    items = _get(record, "items")
    if given is not None and member == 0:
        recs = [SeatRec(str(_get(s, "unit")), int(_get(s, "sid")), _arm_name(_get(s, "arm")), int(_get(s, "position")),
                        _norm_sources(_get(s, "sources"))) for s in given]
        L = _get(record, "L")
        if L is None:
            L = max([r.position for r in recs if r.arm != geo.CENTER.arm] + [0]) + 1
        order = {s: i for i, s in enumerate(geo.seats(L))}
        recs.sort(key=lambda r: order[r.seat])
        return WindowCross(L, tuple(recs), tier, sids, orientation, meta)
    members = _get(record, "members")
    if members is None or not 0 <= member < len(members):
        raise ValueError("member %d: the record has no such member (a record with `seats` only carries member 0)" % member)
    flat = members[member]
    L = _get(record, "L")
    tok = {_get(it, "token"): (_get(it, "unit"), int(_get(it, "sid"))) for it in items} if items else None
    side = dict(_get(record, "order_log")) if tok is None else {}
    recs = []
    for st in geo.seats(L):
        i = 0 if st == geo.CENTER else 1 + ARM_NAMES.index(st.arm) * L + st.k
        c = flat[i]
        if c is None:
            continue
        pos = st.k if st != geo.CENTER else 0
        if tok is not None:
            u, sid = tok[c]
            recs.append(SeatRec(u, sid, st.arm, pos, ()))
            continue
        u = c
        sd = side.get(u, "this")
        sid = sids[1] if (sd == "next" and len(sids) == 2) else sids[0]
        src: Tuple[tuple, ...] = ()
        if pack is not None:
            use = sids if sd == "both" else (sid,)
            src = tuple(tuple(o.row()) for o in pack if o.tier == tier and o.unit == u and o.sid in use)
        recs.append(SeatRec(u, sid, st.arm, pos, src))
    return WindowCross(L, tuple(recs), tier, sids, orientation, meta)


def window_crosses(record, *, orientation: geo.Rotation = geo.IDENTITY,
                   pack: Optional[Sequence[SL.Occ]] = None) -> Tuple[WindowCross, ...]:
    """Every member of the record's class (L-613).  A record with `seats` but without `items` has its representative only."""
    if _get(record, "seats") is not None and not _get(record, "items"):
        return (window_cross(record, 0, orientation=orientation, pack=pack),)
    return tuple(window_cross(record, m, orientation=orientation, pack=pack) for m in range(len(_get(record, "members"))))


# --------------------------------------------------------------------------------------------------------------
# the evidence of an edge, per arm (L-602)
# --------------------------------------------------------------------------------------------------------------
def counts_evidence(counts: SL.WindowCounts, tier: str) -> Evidence:
    """n_a(arm, outer, inner) read from slide.counts: the count and the counts' own source rows."""
    def ev(arm: str, o: str, i: str) -> Tuple[int, tuple]:
        if arm == "+x" or arm == "-x":
            b, a = counts.x.get((tier, o, i), ((), ()))
            s = tuple(b) + tuple(a)
        elif arm == "+y":
            s = tuple(counts.y.get((tier, o, tier, i), ()))      # one tier: the key is absent (L-G3-5)
        elif arm == "-y":
            s = tuple(counts.y.get((tier, i, tier, o), ()))
        elif arm == "+z":
            s = tuple(counts.z.get((tier, o, tier, i), ()))
        else:
            s = tuple(counts.z.get((tier, i, tier, o), ()))
        return len(s), s
    return ev


def table_evidence(table: Mapping[Tuple[str, str, str], int]) -> Evidence:
    """A hand table: table[(arm, outer, inner)] = n_a (a missing key is 0).  Its sources are synthetic rows
    ("table", arm, outer, inner, k), so that the trace check (len(sources) == n) is the same."""
    def ev(arm: str, o: str, i: str) -> Tuple[int, tuple]:
        n = int(table.get((arm, o, i), 0))
        return n, tuple(("table", arm, o, i, k) for k in range(n))
    return ev


def label_blind_evidence(tier_space: TierSpace) -> Evidence:
    """The evidence of today's cycle: n_a(arm, o, i) = n_pair(o, i) on every arm, labels ignored (7.3, the merged check)."""
    def ev(arm: str, o: str, i: str) -> Tuple[int, tuple]:
        n = en._n_pair(tier_space, o, i)
        return n, tuple(("pair", o, i, k) for k in range(n))
    return ev


def foundation_weights(f: SL.Foundation) -> Dict[str, Fraction]:
    """w(arm): the weight of the label on each arm (exact Fractions)."""
    return {a: f.arm_weight(a) for a in ARM_NAMES}


# --------------------------------------------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EdgeTerm:
    """One edge of axis a read from the side of `this`: its count, sources and the two sums' terms."""
    axis: str
    arm: str
    this: SeatKey
    other: SeatKey
    n: int
    sources: Tuple[tuple, ...]
    weight: Fraction
    n_this: int
    n_other: int
    e_other: Fraction                     # E_Q(other)

    @property
    def flow_plain(self) -> Fraction:
        return self.e_other * Fraction(self.n, self.n_other) if self.n_other else ZERO

    @property
    def binding_plain(self) -> Fraction:
        return Fraction(self.n, self.n_this) if self.n_this else ZERO

    def doc(self) -> dict:
        return {"axis": self.axis, "arm": self.arm, "this": list(self.this), "other": list(self.other), "n": self.n,
                "sources": [list(s) for s in self.sources], "weight": self.weight, "n_this": self.n_this,
                "n_other": self.n_other, "e_other": self.e_other}


@dataclass(frozen=True)
class WalkStep:
    arm: str
    frm: SeatKey
    to: SeatKey
    n: int
    sources: Tuple[tuple, ...]

    def doc(self) -> dict:
        return {"arm": self.arm, "from": list(self.frm), "to": list(self.to), "n": self.n,
                "sources": [list(s) for s in self.sources]}


@dataclass(frozen=True)
class AxisWalk:
    arm: str
    path: Tuple[SeatKey, ...]             # outer end first
    terminus: Optional[SeatKey]
    stop: str                             # "centre" | "end" | "gap" | "unproven" | "drop" | "empty"
    steps: Tuple[WalkStep, ...]

    def doc(self) -> dict:
        return {"arm": self.arm, "path": [list(p) for p in self.path], "terminus": None if self.terminus is None else list(self.terminus),
                "stop": self.stop, "steps": [s.doc() for s in self.steps]}


@dataclass(frozen=True)
class AxisSection:
    section: int
    attached: Optional[str]
    arms: Tuple[str, ...]                 # the visible arms of this axis
    walks: Tuple[AxisWalk, ...]
    unit: Optional[str]                   # None = points nowhere
    energy: Optional[Fraction]            # the energy of `unit` that decided (E_q if attached, else E_Q)

    def doc(self) -> dict:
        return {"section": self.section, "attached": self.attached, "arms": list(self.arms), "unit": self.unit,
                "energy": self.energy, "walks": [w.doc() for w in self.walks]}


@dataclass(frozen=True)
class AxisRatios:
    axis: str
    sections: Tuple[AxisSection, ...]     # the sections that see an arm of this axis (R1 range), in section order
    working: int
    grounded: int                         # working sections with an attached query unit that is in the space (L-104)
    section_unit: Optional[str]           # R1_a
    edge_flow: Mapping[str, Fraction]     # F_a, WEIGHTED (decides)
    binding: Mapping[str, Fraction]       # B_a, WEIGHTED (decides)
    edge_flow_plain: Mapping[str, Fraction]
    binding_plain: Mapping[str, Fraction]
    edge_unit: Optional[str]              # R2_a
    binding_unit: Optional[str]           # R3_a
    seated_edges: int                     # edges of the axis with both ends seated
    status: str
    unit: Optional[str]                   # the agreed unit iff status == AGREE
    section_applicable: bool = True       # False: agreement "two_if_single_edge" on an axis with one evidenced edge (L-615)
    evidenced_edges: int = 0              # edges of the axis with both ends seated, n_a > 0, not a same-unit pair (L-615)

    def doc(self) -> dict:
        return {"axis": self.axis, "section_applicable": self.section_applicable, "evidenced_edges": self.evidenced_edges,
                "working": self.working, "grounded": self.grounded, "section_unit": self.section_unit,
                "edge_unit": self.edge_unit, "binding_unit": self.binding_unit, "seated_edges": self.seated_edges,
                "status": self.status, "unit": self.unit, "sections": [s.doc() for s in self.sections],
                "edge_flow": dict(self.edge_flow), "binding": dict(self.binding),
                "edge_flow_plain": dict(self.edge_flow_plain), "binding_plain": dict(self.binding_plain)}


@dataclass(frozen=True)
class AxisAnswer:
    axis: str
    label: str                            # "slide:x"
    unit: str
    section: Optional[Fraction]           # None: the section walk was not applicable (L-615); else the energy at which the working sections' walks ended on the unit (max over them)
    edge_flow: Fraction                   # F_a(unit), weighted
    binding: Fraction                     # B_a(unit), weighted
    edge_flow_plain: Fraction
    binding_plain: Fraction
    seats: Tuple[SeatRec, ...]            # every seat of the unit
    edges: Tuple[EdgeTerm, ...]           # the axis' edges at those seats (n > 0): the terms of F_a, B_a
    walk_steps: Tuple[WalkStep, ...]      # the steps of the working sections' walks that ended on the unit
    grounded: int
    sources: Tuple[tuple, ...]            # (axis,) + each source row of `edges` and `walk_steps`, deduplicated, in order

    def doc(self) -> dict:
        return {"axis": self.axis, "label": self.label, "unit": self.unit,
                "ratios": {"section": self.section, "edge_flow": self.edge_flow, "binding": self.binding},
                "ratios_plain": {"edge_flow": self.edge_flow_plain, "binding": self.binding_plain},
                "seats": [s.doc() for s in self.seats], "edges": [e.doc() for e in self.edges],
                "walk_steps": [w.doc() for w in self.walk_steps], "grounded": self.grounded,
                "sources": [list(s) for s in self.sources]}


@dataclass(frozen=True)
class Abstention:
    axis: str
    label: str
    kind: str                             # points_nowhere | section_disagreement | ratio_disagreement | no_edges
    nowhere: Tuple[str, ...]              # which of "section" / "edge" / "binding" point nowhere
    units: Tuple[Optional[str], Optional[str], Optional[str]]     # (R1, R2, R3)
    section_units: Tuple[str, ...]        # the distinct units the working sections point to

    def doc(self) -> dict:
        return {"axis": self.axis, "label": self.label, "kind": self.kind, "nowhere": list(self.nowhere),
                "units": list(self.units), "section_units": list(self.section_units)}


@dataclass(frozen=True)
class SlideRatios:
    cross: WindowCross
    query: Tuple[str, ...]                # the units E_Q reads (cycle.QueryContext.energy_units)
    attached: Tuple[Tuple[int, str], ...]
    weights: Tuple[Tuple[str, Fraction], ...]
    window_arms: int
    z_self_edges: bool
    axes: Tuple[AxisRatios, ...]          # x, y, z
    answers: Tuple[AxisAnswer, ...]       # agreeing axes, read order
    abstentions: Tuple[Abstention, ...]   # the other axes, read order
    read_order: Tuple[str, ...]
    agreement: str = "three"

    def axis(self, a: str) -> AxisRatios:
        return self.axes[AXES.index(a)]

    def answer(self, a: str) -> Optional[AxisAnswer]:
        return next((x for x in self.answers if x.axis == a), None)

    def abstention(self, a: str) -> Optional[Abstention]:
        return next((x for x in self.abstentions if x.axis == a), None)

    def doc(self) -> dict:
        return {"format": FORMAT, "kind": "slide_ratios", "cross": self.cross.doc(), "query": list(self.query),
                "attached": {str(s): u for s, u in self.attached}, "weights": {a: w for a, w in self.weights},
                "weights_enter": WEIGHTS_ENTER_TEXT, "window_arms": self.window_arms, "z_self_edges": self.z_self_edges,
                "agreement": self.agreement, "read_order": list(self.read_order), "axes": [a.doc() for a in self.axes],
                "answers": [a.doc() for a in self.answers], "abstentions": [a.doc() for a in self.abstentions]}

    def to_bytes(self) -> bytes:
        return SL.canonical(self.doc())

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()


# --------------------------------------------------------------------------------------------------------------
# the reading
# --------------------------------------------------------------------------------------------------------------
class _Reader:
    def __init__(self, wc: WindowCross, evidence: Evidence, t: TierSpace, q: Tuple[str, ...], attached: Mapping[int, str],
                 weights: Mapping[str, Fraction], window: int, z_self_edges: bool, agreement: str = "three") -> None:
        self.agreement = agreement
        self.wc, self.ev, self.t, self.q, self.att = wc, evidence, t, q, dict(attached)
        self.w, self.window, self.zself = weights, window, z_self_edges
        self.by = wc.by_seat()
        self._e: Dict[Tuple[str, Tuple[str, ...]], Fraction] = {}

    def E(self, u: str, q: Tuple[str, ...]) -> Fraction:
        k = (u, q)
        v = self._e.get(k)
        if v is None:
            v = self._e[k] = en.energy(self.t, u, q)
        return v

    def n(self, u: str) -> int:
        return en._n(self.t, u)

    # ---- edges -------------------------------------------------------------------------------------------------
    def edges_of(self, axis: str) -> List[Tuple[SeatRec, SeatRec, str, int, tuple]]:
        """The axis' edges with both ends seated, in geometry.edges order: (outer, inner, arm, n_a, sources)."""
        out = []
        for o, i in geo.edges(self.wc.L):
            if axis_of_arm(o.arm) != axis:
                continue
            so, si = self.by.get(o), self.by.get(i)
            if so is None or si is None:
                continue
            n, src = self.ev(o.arm, so.unit, si.unit)
            out.append((so, si, o.arm, n, src))
        return out

    def _skip_pair(self, axis: str, a: SeatRec, b: SeatRec) -> bool:
        """L-56: two seats of one unit contribute nothing, unless z_self_edges (default on, L-616) and the edge is a z edge (L-604)."""
        return a.unit == b.unit and not (self.zself and axis == "z")

    # ---- (2), (3) ------------------------------------------------------------------------------------------------
    def flows(self, axis: str, edges) -> Tuple[Dict[str, Fraction], ...]:
        units = self.wc.units()
        F = {u: ZERO for u in units}
        B = {u: ZERO for u in units}
        Fp = {u: ZERO for u in units}
        Bp = {u: ZERO for u in units}
        for so, si, arm, n, _src in edges:
            if n <= 0 or self._skip_pair(axis, so, si):
                continue
            w = self.w[arm]
            for v, u in ((so, si), (si, so)):
                nu, nv = self.n(u.unit), self.n(v.unit)
                if nu:
                    t = self.E(u.unit, self.q) * Fraction(n, nu)
                    Fp[v.unit] += t
                    F[v.unit] += w * t
                if nv:
                    t = Fraction(n, nv)
                    Bp[v.unit] += t
                    B[v.unit] += w * t
        return F, B, Fp, Bp

    # ---- (1) -----------------------------------------------------------------------------------------------------
    def walk(self, arm: str, q: Tuple[str, ...]) -> AxisWalk:
        cells = [self.by.get(geo.Seat(arm, k)) for k in range(self.wc.L)] + [self.by.get(geo.CENTER)]
        if cells[0] is None:
            return AxisWalk(arm, (), None, "empty", ())
        path = [cells[0]]
        steps: List[WalkStep] = []
        stop = "end"
        for nxt in cells[1:]:
            cur = path[-1]
            if nxt is None:
                stop = "gap"
                break
            n, src = self.ev(arm, cur.unit, nxt.unit)
            if n <= 0:
                stop = "unproven"
                break
            if self.E(nxt.unit, q) < self.E(cur.unit, q):
                stop = "drop"
                break
            path.append(nxt)
            steps.append(WalkStep(arm, cur.key, nxt.key, n, src))
        else:
            stop = "centre"
        return AxisWalk(arm, tuple(p.key for p in path), path[-1].key, stop, tuple(steps))

    def section(self, axis: str, s: int) -> Optional[AxisSection]:
        vis = geo.visible_arms(self.wc.orientation, s, self.window)
        arms = tuple(a for a in vis if axis_of_arm(a) == axis)
        if not arms:
            return None
        att = self.att.get(s)
        q = (att,) if att is not None else self.q
        walks = tuple(self.walk(a, q) for a in arms)
        cand = {w.terminus[0]: self.E(w.terminus[0], q) for w in walks if w.terminus is not None}
        u = en.unique_argmax(cand)
        return AxisSection(s, att, arms, walks, u, None if u is None else cand[u])

    # ---- one axis -------------------------------------------------------------------------------------------------
    def axis(self, axis: str) -> AxisRatios:
        edges = self.edges_of(axis)
        F, B, Fp, Bp = self.flows(axis, edges)
        evidenced = sum(1 for so, si, _arm, n, _src in edges if n > 0 and not self._skip_pair(axis, so, si))
        applicable = not (self.agreement == "two_if_single_edge" and evidenced == 1)       # L-615
        secs = tuple(x for x in (self.section(axis, s) for s in range(geo.N_ARMS)) if x is not None) if applicable else ()
        working = [s for s in secs if s.unit is not None]
        sunits = tuple(dict.fromkeys(s.unit for s in working))
        r1 = sunits[0] if len(sunits) == 1 else None
        r2, r3 = en.unique_argmax(F), en.unique_argmax(B)
        grounded = sum(1 for s in working if s.attached is not None and self.n(s.attached) > 0)
        if not edges:
            status = NO_EDGES
        elif not applicable:                                   # one evidenced edge: R2 and R3 decide, the walk is skipped
            status = POINTS_NOWHERE if (r2 is None or r3 is None) else (AGREE if r2 == r3 else RATIO_DISAGREEMENT)
            r1 = r2 if status == AGREE else None
        elif len(sunits) > 1:
            status = SECTION_DISAGREEMENT
        elif r1 is None or r2 is None or r3 is None:
            status = POINTS_NOWHERE
        elif r1 == r2 == r3:
            status = AGREE
        else:
            status = RATIO_DISAGREEMENT
        return AxisRatios(axis, secs, len(working), grounded, None if not applicable else r1, F, B, Fp, Bp, r2, r3, len(edges),
                          status, (r2 if not applicable else r1) if status == AGREE else None, applicable, evidenced)

    # ---- the labelled answer and its trace -----------------------------------------------------------------------
    def answer(self, ar: AxisRatios) -> AxisAnswer:
        u = ar.unit
        edges = self.edges_of(ar.axis)
        terms: List[EdgeTerm] = []
        for so, si, arm, n, src in edges:
            if n <= 0 or self._skip_pair(ar.axis, so, si):
                continue
            for v, o in ((so, si), (si, so)):
                if v.unit == u:
                    terms.append(EdgeTerm(ar.axis, arm, v.key, o.key, n, src, self.w[arm], self.n(v.unit), self.n(o.unit),
                                          self.E(o.unit, self.q)))
        steps: List[WalkStep] = []
        sec_e: List[Fraction] = []
        for s in ar.sections:
            if s.unit == u:
                sec_e.append(s.energy)
                for w in s.walks:
                    if w.terminus is not None and w.terminus[0] == u:
                        steps.extend(w.steps)
        rows: Dict[tuple, None] = {}
        for t in terms:
            for r in t.sources:
                rows[(ar.axis,) + tuple(r)] = None
        for st in steps:
            for r in st.sources:
                rows[(ar.axis,) + tuple(r)] = None
        return AxisAnswer(ar.axis, "slide:" + ar.axis, u, max(sec_e) if sec_e else None, ar.edge_flow[u], ar.binding[u], ar.edge_flow_plain[u],
                          ar.binding_plain[u], tuple(s for s in self.wc.seats if s.unit == u), tuple(terms), tuple(steps),
                          ar.grounded, tuple(rows))


def read_order(weights: Mapping[str, Fraction]) -> Tuple[str, ...]:
    """The third place of the weights (L-608): axes by axis weight w(+a) + w(-a), larger first; equal weights keep the ladder
    order x, y, z (a label, not a winner)."""
    return tuple(a for _w, _i, a in sorted(((-(weights["+" + a] + weights["-" + a]), i, a) for i, a in enumerate(AXES))))


def read_axes(wc: WindowCross, evidence: Evidence, tier_space: TierSpace,
              question: Union[Sequence[str], "cy.QueryContext"] = (), foundation: Optional[SL.Foundation] = None, *,
              weights: Optional[Mapping[str, Fraction]] = None, window: int = geo.DEFAULT_WINDOW,
              z_self_edges: bool = True, agreement: str = "three") -> SlideRatios:
    """The three ratios per axis of one window cross, their per-axis agreement and the labelled answers.

    question: the question's units of the cross's tier (a sequence; cycle.split_question cuts it) or a cycle.QueryContext.  I-07
    is cycle.make_context's: the first-layer units, unit i attached to world section i; E_Q reads the context's energy_units.
    foundation: the slide spec's foundation (weights of the arm labels); `weights` (arm -> Fraction) overrides it, e.g. UNIT_WEIGHTS.
    z_self_edges (default ON, owner after G3-d): the z edge between the two seats of one unit counts in F_z and B_z (L-616).
    agreement: "three" (default; R1 = R2 = R3) or "two_if_single_edge" (an axis with exactly one evidenced edge is judged on R2 and
    R3 only, the section walk is skipped and recorded as not applicable; L-615)."""
    if agreement not in AGREEMENTS:
        raise ValueError("agreement must be one of %r" % (AGREEMENTS,))
    if weights is None:
        if foundation is None:
            raise ValueError("a foundation or an explicit weights mapping is needed")
        weights = foundation_weights(foundation)
    if set(weights) != set(ARM_NAMES) or any(not isinstance(v, Fraction) or v <= 0 for v in weights.values()):
        raise ValueError("weights: six positive Fractions, one per arm")
    ctx = question if isinstance(question, cy.QueryContext) else cy.make_context(tuple(question))
    q = tuple(sorted(set(ctx.energy_units)))
    rd = _Reader(wc, evidence, tier_space, q, ctx.attached_map(), weights, window, z_self_edges, agreement)
    axes = tuple(rd.axis(a) for a in AXES)
    order = read_order(weights)
    answers, abst = [], []
    for a in order:
        ar = axes[AXES.index(a)]
        if ar.status == AGREE:
            answers.append(rd.answer(ar))
        else:
            nowhere = tuple(n for n, v in (("section", ar.section_unit), ("edge", ar.edge_unit), ("binding", ar.binding_unit))
                            if v is None and (n != "section" or ar.section_applicable))
            sec_units = tuple(dict.fromkeys(s.unit for s in ar.sections if s.unit is not None))
            abst.append(Abstention(a, "slide:" + a, ar.status, nowhere, (ar.section_unit, ar.edge_unit, ar.binding_unit),
                                   sec_units))
    return SlideRatios(wc, q, tuple(sorted(ctx.attached_map().items())), tuple((a, weights[a]) for a in ARM_NAMES), window,
                       z_self_edges, axes, tuple(answers), tuple(abst), order, agreement)


# --------------------------------------------------------------------------------------------------------------
# the merged check of 7.3 (L-609)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class MergedReport:
    edge_flow_sum: Mapping[str, Fraction]        # sum over x, y, z of the UNWEIGHTED F_a, label-blind evidence
    binding_sum: Mapping[str, Fraction]
    edge_flow_today: Mapping[str, Fraction]      # energy.edge_flow on the same cross
    binding_today: Mapping[str, Fraction]
    edge_equal: bool
    binding_equal: bool

    @property
    def equal(self) -> bool:
        return self.edge_equal and self.binding_equal


def merged_check(wc: WindowCross, tier_space: TierSpace, question: Union[Sequence[str], "cy.QueryContext"] = (), *,
                 window: int = geo.DEFAULT_WINDOW) -> MergedReport:
    """7.3: with n_a = n_pair on every arm (labels ignored) and no weights, the per-axis edge flow and binding summed over
    x, y, z equal the single-axis quantities energy.edge_flow / placement_binding of today's cycle on the same cross.  The
    edges are partitioned by the arm they lie on, so each edge term is counted exactly once."""
    res = read_axes(wc, label_blind_evidence(tier_space), tier_space, question, weights=UNIT_WEIGHTS, window=window,
                    z_self_edges=False)
    fs = {u: ZERO for u in wc.units()}
    bs = {u: ZERO for u in wc.units()}
    for ar in res.axes:
        for u, v in ar.edge_flow_plain.items():
            fs[u] += v
        for u, v in ar.binding_plain.items():
            bs[u] += v
    q = res.query
    f0 = en.edge_flow(tier_space, wc.to_cross(), q)
    b0 = en.placement_binding(tier_space, wc.to_cross())
    return MergedReport(fs, bs, f0, b0, fs == f0, bs == b0)


# --------------------------------------------------------------------------------------------------------------
# trace: every answer unit maps to seats and sources (L-610)
# --------------------------------------------------------------------------------------------------------------
def check_trace(res: SlideRatios) -> int:
    """ValueError at the first answer whose trace does not hold; returns the number of checks.  Holds iff: the unit has a
    seat (keyed (unit, sid)); every edge term and walk step has n > 0 and exactly n source rows; the terms re-add to the
    answer's values (sum w * E(other) * n / n(other) = edge_flow, sum w * n / n(this) = binding); the answer has sources."""
    k = 0
    w = dict(res.weights)
    seat_keys = {s.key for s in res.cross.seats}
    for a in res.answers:
        if not a.seats or any(s.unit != a.unit for s in a.seats):
            raise ValueError("answer %s: no seat of the unit" % a.label)
        if not a.sources:
            raise ValueError("answer %s: no sources" % a.label)
        f = b = ZERO
        for t in a.edges:
            if t.n <= 0 or len(t.sources) != t.n or t.this not in seat_keys or t.other not in seat_keys:
                raise ValueError("answer %s: an edge term without its sources / seats" % a.label)
            if t.weight != w[t.arm] or t.this[0] != a.unit:
                raise ValueError("answer %s: an edge term of another unit or weight" % a.label)
            f += t.weight * t.flow_plain
            b += t.weight * t.binding_plain
            k += 1
        for s in a.walk_steps:
            if s.n <= 0 or len(s.sources) != s.n or s.frm not in seat_keys or s.to not in seat_keys:
                raise ValueError("answer %s: a walk step without its sources / seats" % a.label)
            k += 1
        if f != a.edge_flow or b != a.binding:
            raise ValueError("answer %s: the edge terms do not add to the ratio values" % a.label)
    return k


# --------------------------------------------------------------------------------------------------------------
# every member of a record's class (L-613)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class MemberReads:
    reads: Tuple[SlideRatios, ...]
    agreed: Tuple[Tuple[str, Tuple[str, ...]], ...]       # per axis: the distinct units its agreeing members agree on (no tie broken)
    agreeing: Tuple[Tuple[str, int], ...]                 # per axis: members that agree

    def doc(self) -> dict:
        return {"format": FORMAT, "kind": "member_reads", "members": len(self.reads),
                "agreed": {a: list(u) for a, u in self.agreed}, "agreeing": {a: n for a, n in self.agreeing},
                "reads": [r.doc() for r in self.reads]}

    def to_bytes(self) -> bytes:
        return SL.canonical(self.doc())


def read_members(crosses: Iterable[WindowCross], evidence: Evidence, tier_space: TierSpace, question=(),
                 foundation: Optional[SL.Foundation] = None, **kw) -> MemberReads:
    """Run read_axes on every member; list, per axis, the units the agreeing members agree on (member choice by stability is
    G3-e, L-107: nothing is chosen here)."""
    reads = tuple(read_axes(c, evidence, tier_space, question, foundation, **kw) for c in crosses)
    agreed, cnt = [], []
    for a in AXES:
        us = [r.axis(a).unit for r in reads if r.axis(a).status == AGREE]
        agreed.append((a, tuple(sorted(set(us)))))
        cnt.append((a, len(us)))
    return MemberReads(reads, tuple(agreed), tuple(cnt))
