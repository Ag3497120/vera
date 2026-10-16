"""PUB-M2 / M3 / M4: the memory crosses, the nests and the slide order (docs/LINE3_PUBLIC_DESIGN.md 4.3-4.5; owner OP-PUB-1..8; local decisions L-PUB-24..).

`MemIndex` is a PURE FUNCTION of H (the memory rows, in order) and the topic declarations of the ledger (+ the supersede marks the model made): `build_index(rows, decls, superseded)`.  It is derived, never
stored as truth, and a replay must rebuild it identically (`index_sha`).  It reads the shape exchanger (`memshape.exchange`, table shape.v2) and, for the KEY of a seat and the ORIGIN of its words, the
memory corpus of the sentences BEFORE the one that wrote the seat (the history rule L-MEM-06: a sentence never confirms itself).

TANKS (M2).  One tank per shape: F1 attribute (「X の Y は A」), F2 topic-value (「Y は A」), F3 event, F4 an event clause that no nest could complete (kept uncompleted, see M3).  The F0 tank holds the
sentences the model chose to keep unshaped (OP-PUB-2): they are in H and searchable as text; their F0 clauses enter no cross, their F1-F4 clauses do (designer decision L-PUB-42).  In each tank ONE CROSS per CENTRE PHRASE (the phrase as written: 開催地, 認証モジュール担当; for an
event the predicate: a verb's dictionary form, or the サ変 noun).  A cross has the arms of the foundation (の に で と を が, the ladder order of `foundation.LADDER`), the centre relation は = the VALUE seats, and the
two seats the exchanger names besides (`quantity`, `object_bare`).  A SEAT is (phrase, units, provenance), provenance = (sid, turn, session, origin record | constructed, surface, clause).  A chain 「X の Y の Z」 nests:
Z's の-arm seat Y carries Y's own の-arm seat X (a path).  FAITHFUL: no seat is ever dropped.  An arm that holds m seats needs m data rings and the foundation ring (the innermost seat of an arm is the particle,
`foundation.contract`): its cross has L = 1 + m rings; when an arm outgrows the rings an OUTER ring is added (L + 1), exactly as the geometry does (N_ARMS = 6 arms of L seats, the foundation seat innermost).  Nothing is
closed by a budget (stack.py's crosses are).  The seats of an arm are ORDERED by the key (n, p, a) of the seat against the history of ITS write (`read.loom_key` of the cross {centre; the seat on its arm; the foundation
tokens}), larger first, ties by the earlier sid; the first seat sits in ring 1 (next to the foundation ring), the next one outside it.  The key is computed once, at the commit, against C_<sid and is frozen with the seat.
A superseded seat only gains a MARK (history kept).

NESTS (M3).  `declare(session, at, topic)` opens the nest of the topic: its centre is the head phrase of the topic (「A社のB事業」: centre B事業 with the の-arm A社; a topic with particles is allowed, OP-PUB-3).
An F4 clause written while a nest is open is COMPLETED structurally: it is placed in the F3 tank, its が arm is filled by the nest's centre seat (`via` = "nest", the nest id); NOTHING is prepended to any text.  A cross
whose centre, or whose の-arm path, holds the nest centre is also a member (kind `centre` / `path`, `exact` = the nest's own arms are also in the clause).  Other clauses written while the nest was open are listed as `under`
(not members; the owner's open point).

SLIDE ORDER (M4).  The order edges sentence N -> N+1 (by sid, a session boundary is flagged).  A POSITION is (tank, centre, path) with path = the clause's arm tree as ((particle, phrase), ...); its VALUES, in slide
order, are the value seats of that position.  `history(position)` -> [(value, sid, kind)], kind = first | update | other; an UPDATE is a later value written by a change clause (memshape's change forms) or one the model
superseded explicitly.  Detection itself (same seat / different value, reversal, enumeration) is ticket M5; this module only keeps what M5 needs (every value with its change, marks and provenance).

PUB-M5 / M6 (this file's additions).  A seat remembers the SCOPE it was written in (the nest that was open: None = no nest); a clause written while a nest is open is a MEMBER of it (kind `context`
when it is neither completed, nor on the nest centre, nor under it: designer decision L-PUB-39), so the list `under` is gone.  The index holds the NOTES of the detections (memdetect: SAME_SEAT, UPDATE,
REVERSAL_X, ENUMERATION; they are made by the same fold and are part of `index_sha`) and the BRIDGES the model added (`bridge`: a question word -> a memory phrase, constructed, marked, ledgered).

THE INDEX IS INCREMENTAL (designer decision L-PUB-40).  The builder keeps, per cross, per position, per nest, per clause and per note, the view and the canonical JSON of that part; a write dirties only
the parts it touched, and `index_sha` is the sha256 of the parts joined in the order `MemIndex.to_obj()` serialises them -- byte for byte the sha256 of `canonical(MemIndex.to_obj())`, which is what the
full rebuild (`build_index`, run at replay / verify) computes; a test compares the two.

Pure and deterministic: no clock, float, process, environment, no set / dict iteration order in any output (lists are built and sorted explicitly).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from verantyx.line3 import foundation as fd
from verantyx.line3 import geometry as geo
from verantyx.loom import memdetect as mdt
from verantyx.loom import memshape as ms
from verantyx.loom import read as rd
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import parse_source
from verantyx.loom.state import SPEC, canonical, sha256_text

CROSS_VERSION = "cross.v2"      # cross.v1 (PUB-M2..M4) + seat scope, `context` members, notes, bridges (no cross.v1 data was ever recorded with a model)
FLAT_VERSION = "flat.v1"        # PUB-M8 (A3f): the FLAT TABLE index -- the same exchanger, tanks, seats, provenance, notes and answer path, with the geometry taken out (see `IndexBuilder(flat=True)`)
GEOMETRY_VERSION = "geo.v1"     # ABLATE (ticket C): the geometry PROFILE -- six independent switches, each OFF = the flat table's behaviour for that component only (see `Geometry`)
GEO_COMPONENTS: Tuple[str, ...] = ("nests", "slide", "key", "swap", "ladder", "arms")
TANKS: Tuple[str, ...] = ("F1", "F2", "F3", "F4")
F0_TANK = "F0"
ARMS: Tuple[str, ...] = tuple(SPEC.arms)                  # の に で と を が: the ladder order of foundation.LADDER[1:]
VALUE = SPEC.centre                                       # は: the centre relation = the value seat
EXTRA: Tuple[str, ...] = ("quantity", "object_bare")
SLOTS: Tuple[str, ...] = ARMS + (VALUE,) + EXTRA
NEST_ARM = "が"                                            # the subject role an F4 clause gets from the nest centre
NEST_VIA = "nest"
KINDS = ("first", "update", "other")
MARK_SUPERSEDED = "superseded"

Path = Tuple[Tuple[str, str], ...]
Position = Tuple[str, str, Path]


# ------------------------------------------------------------------------------------------------------------
# the key of a seat, the origin of its words (against the history before its sentence)
# ------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------
# the geometry profile (ticket C, docs/LINE3_PUBLIC_DESIGN.md 4.10)
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Geometry:
    """Which parts of the cross geometry the index uses.  ALL ON = the crosses (cross.v2, A3, the default, byte for byte as before); ALL OFF = the flat table (flat.v1, A3f, byte for byte as before).
    Each switch changes ONE component and nothing else:
      nests   the topic nest (declare, F4 completion by the nest centre, seat scope = nest id)  | OFF: a plain topic column (scope = the topic string, no completion)
      slide   the order edges [sid-1, sid, session flag] of the slide order                    | OFF: no edge (a position lists its values in sid order, which it does in both)
      key     the (n, p, a) key that orders the seats of an arm (and a seat's frozen key)       | OFF: key (0, 0, 0): sid order, ties by clause, then sequence
      swap    the key swap on a REVERSAL_X note and the loom's old REVERSAL (key route) note   | OFF: the pair direction is compared, `key` null, the old note is not shown
      ladder  the golden / Fibonacci weight of the arm in `a` of the key                        | OFF: weight 1 for every arm.  Used only when `key` is on.
      arms    the particle -> arm assignment: a seat is read on the arm of ITS particle         | OFF: one unordered arm list: the seat's adhesion is pooled over the six arm particles.  Used only when `key` is on.
    The version string is canonical: cross.v2 (all on), flat.v1 (all off), else geo.v1:-<switch>-<switch>... (the OFF ones, in GEO_COMPONENTS order)."""
    nests: bool = True
    slide: bool = True
    key: bool = True
    swap: bool = True
    ladder: bool = True
    arms: bool = True

    @staticmethod
    def of_off(off: Iterable[str]) -> "Geometry":
        off = tuple(off)
        for x in off:
            if x not in GEO_COMPONENTS:
                raise ValueError("unknown geometry component %r (one of %s)" % (x, ", ".join(GEO_COMPONENTS)))
        return Geometry(**{c: c not in off for c in GEO_COMPONENTS})

    @staticmethod
    def flat_table() -> "Geometry":
        return Geometry.of_off(GEO_COMPONENTS)

    @staticmethod
    def parse(version: Optional[str]) -> "Geometry":
        """None / cross.v2 -> all on; flat.v1 -> all off; the canonical geo.v1:-a-b string -> those off.  ValueError for anything else (and for a non-canonical spelling)."""
        if version is None or version == CROSS_VERSION:
            return Geometry()
        if version == FLAT_VERSION:
            return Geometry.flat_table()
        pre = GEOMETRY_VERSION + ":"
        if isinstance(version, str) and version.startswith(pre + "-"):
            g = Geometry.of_off(version[len(pre) + 1:].split("-"))
            if g.version() == version:
                return g
        raise ValueError("not a geometry version: %r" % (version,))

    @property
    def off(self) -> Tuple[str, ...]:
        return tuple(c for c in GEO_COMPONENTS if not getattr(self, c))

    @property
    def flat(self) -> bool:
        return len(self.off) == len(GEO_COMPONENTS)

    @property
    def crosses(self) -> bool:
        return not self.off

    def version(self) -> str:
        if self.crosses:
            return CROSS_VERSION
        if self.flat:
            return FLAT_VERSION
        return GEOMETRY_VERSION + ":" + "".join("-" + c for c in self.off)

    def header(self) -> Optional[dict]:
        """The `header.index` block of a begin row: None for the crosses (absent, as before), {"version": flat.v1} for the flat table (as before), else the version and the switches that are off."""
        if self.crosses:
            return None
        if self.flat:
            return {"version": FLAT_VERSION}
        return {"version": self.version(), "off": list(self.off)}


KEY_ONLY: Tuple[str, ...] = ("ladder", "arms")          # read only by the key: their add-one-in variants switch the key on as well


def variant_geometry(name: str) -> Optional[Geometry]:
    """The geometry of a named arm of the ablation (ticket C): A3 (all on), A3f (all off), `A3-no<component>` (A3 with one switch off, leave-one-out), `A3f-plus<component>` (the flat table with one switch on,
    add-one-in; for `ladder` and `arms`, which only the key reads, the key is switched on too, so that the variant is the key with that component alone).  None for any other name."""
    if name == "A3":
        return Geometry()
    if name == "A3f":
        return Geometry.flat_table()
    for pre, loo in (("A3-no", True), ("A3f-plus", False)):
        if name.startswith(pre) and name[len(pre):] in GEO_COMPONENTS:
            c = name[len(pre):]
            if loo:
                return Geometry.of_off([c])
            on = (c, "key") if c in KEY_ONLY else (c,)
            return Geometry.of_off([x for x in GEO_COMPONENTS if x not in on])
    return None


def ablation_variants() -> Tuple[str, ...]:
    """A3, A3f, then the six leave-one-out arms and the six add-one-in arms, in GEO_COMPONENTS order."""
    return ("A3", "A3f") + tuple("A3-no" + c for c in GEO_COMPONENTS) + tuple("A3f-plus" + c for c in GEO_COMPONENTS)


def as_geometry(geometry: Any = None, flat: bool = False) -> Geometry:
    """A Geometry from a Geometry, a version string, or (legacy) the `flat` bool."""
    if isinstance(geometry, Geometry):
        return geometry
    if geometry is not None:
        return Geometry.parse(geometry)
    return Geometry.flat_table() if flat else Geometry()


def seat_key(corpus: Any, slot: str, centre_head: str, seat_head: str, ladder: bool = True, arms_on: bool = True) -> Tuple[int, int, int]:
    """(n, p, a) of a seat against `corpus` = C_<sid.  An arm: `read.loom_key` of the cross L = 2 {centre; the seat outermost on its arm; the six foundation tokens innermost} -- the very key the loom reads a
    woven cross with (n, p from the contracted cross's edges, a = numerator(particle) * adj(seat, particle); the centre's は term is the topic mark's and is not counted).  は (a value): (n, p) of the pair
    in READING ORDER (the centre first) and a = numerator(は) * adj(centre, は).  quantity / object_bare: (n, p) of the pair (seat first, then the centre), a = 0.  A word that is not in the space has weight 0
    (L-52): an event's centre is a dictionary form, which is a surface in the space only if it was written so.
    ABLATE: `ladder` False = every arm weighs 1 in `a` (no golden / Fibonacci weight); `arms_on` False = no particle -> arm assignment: the seat's adhesion is pooled over the six arm particles (an unordered list).
    (n, p) are the same either way (after the contraction of the foundation they do not depend on the arm); with both True this is the key as it always was."""
    t, adh, w = corpus.tier("WORD"), corpus.adhesion["WORD"], corpus.weights("WORD")
    if not (ladder and arms_on) and (slot in ARMS or slot == VALUE):
        n, p, _ = seat_key(corpus, slot, centre_head, seat_head)
        if slot == VALUE:
            return (n, p, int((SPEC.numerator(VALUE) if ladder else 1) * adh.adj(centre_head, VALUE)))
        return (n, p, int(sum((SPEC.numerator(q) if ladder else 1) * adh.adj(seat_head, q) for q in (SPEC.arms if not arms_on else (slot,)))))
    if slot in ARMS:
        arms: List[List[Optional[str]]] = [[None, fd.token(p)] for p in SPEC.arms]
        arms[SPEC.arms.index(slot)][0] = seat_head
        g = geo.Cross.make(L=2, center=centre_head, arms=arms)
        k = rd.loom_key(t, adh, g, w, False)
        return (int(k[0]), int(k[1]), int(k[2]))
    if slot == VALUE:
        n, p = w(centre_head, seat_head)
        return (int(n), int(p), int(SPEC.numerator(VALUE) * adh.adj(centre_head, VALUE)))
    n, p = w(seat_head, centre_head)
    return (int(n), int(p), 0)


def origin_of(corpus: Any, units: Sequence[str]) -> str:
    """`record` iff every unit of the phrase was in the history (C_<sid), else `constructed` (the model brought a word the structure lacked: L-MEM-16)."""
    t = corpus.tier("WORD")
    return "record" if units and all(len(t.postings.get(u, ())) > 0 for u in units) else "constructed"


def _rows_bytes(rows: Sequence[dict]) -> bytes:
    return "".join(canonical({"kind": r.get("kind", "base"), "sent": r["sent"], "source": r["source"]}) + "\n" for r in rows).encode("utf-8")


# ------------------------------------------------------------------------------------------------------------
# the views (frozen)
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Prov:
    sid: int
    turn: Optional[str]
    session: int
    origin: str                                  # record | constructed
    surface: str                                 # as written (an event centre: 開いた for the centre 開く)
    clause: int                                  # index of the clause in its sentence

    def to_obj(self) -> dict:
        return {"sid": self.sid, "turn": self.turn, "session": self.session, "origin": self.origin, "surface": self.surface, "clause": self.clause}


@dataclass(frozen=True)
class Mark:
    kind: str                                    # superseded
    by: int
    reason: str
    session: int

    def to_obj(self) -> dict:
        return {"kind": self.kind, "by": self.by, "reason": self.reason, "session": self.session}


@dataclass(frozen=True)
class ChangeRec:
    old: Optional[str]
    old_units: Tuple[str, ...]
    new: str
    form: str

    def to_obj(self) -> dict:
        return {"old": self.old, "old_units": list(self.old_units), "new": self.new, "form": self.form}


@dataclass(frozen=True)
class Seat:
    slot: str                                    # の に で と を が | は (a value) | quantity | object_bare
    phrase: str
    units: Tuple[str, ...]
    prov: Prov
    key: Tuple[int, int, int]                    # frozen at the commit
    rank: int                                    # 0-based place in its arm, by key (larger first), then the earlier sid
    ring: int                                    # rank + 1 on the six arms (ring 0 is the foundation ring), 0 on the others
    path: Path                                   # an arm seat: its ancestors ((の, Y),) ; a value seat: the clause's arm tree = the position
    arms: Tuple[Tuple[str, "Seat"], ...]         # own arms (the chain 「X の Y の Z」: Y carries (の, X))
    via: Optional[str]                           # "nest": the seat is the nest centre that completed an F4 clause
    nest: Optional[str]
    change: Optional[ChangeRec]                  # a value written by a change clause
    marks: Tuple[Mark, ...]
    scope: Optional[str] = None                  # PUB-M5: the nest that was open when the clause was written (None: no nest)
    written: str = ""                            # PUB-M6d (shape.v4): the particle as written when it was read as `slot` (「へ」 on the arm 「に」); "" for every older table

    def to_obj(self) -> dict:
        d = {"slot": self.slot, "phrase": self.phrase, "units": list(self.units), "prov": self.prov.to_obj(), "key": list(self.key), "rank": self.rank, "ring": self.ring,
             "path": [list(p) for p in self.path], "arms": [[p, s.to_obj()] for p, s in self.arms], "via": self.via, "nest": self.nest,
             "change": None if self.change is None else self.change.to_obj(), "marks": [m.to_obj() for m in self.marks], "scope": self.scope}
        if self.written:
            d["written"] = self.written
        return d


@dataclass(frozen=True)
class Cross:
    tank: str
    centre: str
    centre_units: Tuple[str, ...]
    L: int                                       # 1 + the longest arm (>= 1); an arm of m seats has m data rings + the foundation ring
    slots: Tuple[Tuple[str, Tuple[Seat, ...]], ...]      # the non-empty slots, in SLOTS order, the seats in rank order
    occurrences: Tuple[Prov, ...]                # the centre's own provenance, one per clause that put a seat here (sid order)

    def seats_of(self, slot: str) -> Tuple[Seat, ...]:
        for s, seats in self.slots:
            if s == slot:
                return seats
        return ()

    def n_seats(self) -> int:
        return sum(1 + _count_children(s) for _, seats in self.slots for s in seats)

    def to_obj(self) -> dict:
        return {"tank": self.tank, "centre": self.centre, "centre_units": list(self.centre_units), "L": self.L,
                "slots": [[s, [x.to_obj() for x in seats]] for s, seats in self.slots], "occurrences": [o.to_obj() for o in self.occurrences]}


def _count_children(s: Seat) -> int:
    return sum(1 + _count_children(c) for _, c in s.arms)


@dataclass(frozen=True)
class ClauseRec:
    sid: int
    k: int
    session: int
    turn: Optional[str]
    shape: str                                   # the exchanger's shape (F0 = not placed)
    tank: Optional[str]                          # where it went (an F4 clause a nest completed: F3); None = not placed
    centre: Optional[str]
    text: str
    via: Optional[str]
    nest: Optional[str]                          # the nest that completed it
    open_nest: Optional[str]                     # the nest open when it was written
    path: Path
    value: Optional[str]
    change: Optional[ChangeRec]
    adverbial: Tuple[str, ...]
    reason: Optional[str]                        # an F0 clause: why

    def to_obj(self) -> dict:
        return {"sid": self.sid, "k": self.k, "session": self.session, "turn": self.turn, "shape": self.shape, "tank": self.tank, "centre": self.centre, "text": self.text,
                "via": self.via, "nest": self.nest, "open_nest": self.open_nest, "path": [list(p) for p in self.path], "value": self.value,
                "change": None if self.change is None else self.change.to_obj(), "adverbial": list(self.adverbial), "reason": self.reason}


@dataclass(frozen=True)
class F0Entry:
    sid: int
    session: int
    turn: Optional[str]
    text: str
    shapes: Tuple[str, ...]
    reasons: Tuple[str, ...]

    def to_obj(self) -> dict:
        return {"sid": self.sid, "session": self.session, "turn": self.turn, "text": self.text, "shapes": list(self.shapes), "reasons": list(self.reasons)}


@dataclass(frozen=True)
class Member:
    sid: int
    k: int
    tank: str
    centre: str
    kind: str                                    # completed | centre | path | context
    exact: bool

    def to_obj(self) -> dict:
        return {"sid": self.sid, "k": self.k, "tank": self.tank, "centre": self.centre, "kind": self.kind, "exact": self.exact}


MEMBER_KINDS: Tuple[str, ...] = ("completed", "centre", "path", "context")


@dataclass(frozen=True)
class Nest:
    id: str
    topic: str
    centre: str
    centre_units: Tuple[str, ...]
    arms: Path                                   # the topic's own arms ((の, A社),): the nest's centre seat carries them
    prefix: str                                  # the text of the topic before its head phrase when it is not a の chain (kept, never dropped)
    declared: Tuple[Tuple[int, int], ...]        # (session, at) of every declaration that opened it
    members: Tuple[Member, ...]                  # every placed clause that belongs to it: completed by it, on its centre, under its centre in a の chain, or written while it was open (`context`)

    def to_obj(self) -> dict:
        return {"id": self.id, "topic": self.topic, "centre": self.centre, "centre_units": list(self.centre_units), "arms": [list(a) for a in self.arms], "prefix": self.prefix,
                "declared": [list(d) for d in self.declared], "members": [m.to_obj() for m in self.members]}


@dataclass(frozen=True)
class Bridge:
    """PUB-M6: a mapping the model added: the question word / phrase `qword` stands for the memory phrase `phrase` (a centre the memory holds).  Constructed (the structure did not have it), marked, ledgered."""
    qword: str
    phrase: str
    session: int
    at: int                                      # |H| when it was added
    origin: str = "constructed"

    def to_obj(self) -> dict:
        return {"qword": self.qword, "phrase": self.phrase, "session": self.session, "at": self.at, "origin": self.origin}


@dataclass(frozen=True)
class Entry:
    """One value at a position, in slide order (M4)."""
    value: str
    sid: int
    k: int
    session: int
    turn: Optional[str]
    kind: str                                    # first | update | other
    change: Optional[ChangeRec]
    old_matches: Optional[bool]                  # a change clause: does its old value equal the value before it at this position (None: no old value named / no earlier value)
    marks: Tuple[Mark, ...]
    scope: Optional[str] = None                  # PUB-M5: the nest open when it was written
    units: Tuple[str, ...] = ()                  # PUB-M6: the WORD units of the value phrase (recall quotes the stretch of the sentence they make)

    def to_obj(self) -> dict:
        return {"units": list(self.units), "value": self.value, "sid": self.sid, "k": self.k, "session": self.session, "turn": self.turn, "kind": self.kind,
                "change": None if self.change is None else self.change.to_obj(), "old_matches": self.old_matches, "marks": [m.to_obj() for m in self.marks], "scope": self.scope}


# ------------------------------------------------------------------------------------------------------------
# the topic as a nest head
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TopicHead:
    centre: str
    centre_units: Tuple[str, ...]
    arms: Tuple[ms.Arm, ...]
    prefix: str


def topic_head(topic: str) -> Optional[TopicHead]:
    """The head phrase of a declared topic and its arms: 「展示会準備」 -> centre 展示会準備; 「A社のB事業」 -> centre B事業, の-arm A社 (a chain nests).  A particle other than の before the head (「東京での会議」) cannot
    be an arm of the head: the text before the head phrase is kept as `prefix`.  None: the topic has no unit."""
    text = unicodedata.normalize("NFC", topic)
    toks = ms._tokens(text)
    units = [t for t in toks if not t.fn]
    if not units:
        return None
    gaps = ["".join(t.s for t in toks if units[k].b <= t.a and t.b <= units[k + 1].a) for k in range(len(units) - 1)]
    segs, cs = ms._segments_v2(units, gaps)
    last = segs[-1]

    def seat(ph: Sequence[int]) -> ms.Seat:
        a, b = units[ph[0]].a, units[ph[-1]].b
        return ms.Seat(text[a:b], tuple(units[i].s for i in ph), (a, b))

    def nest(seg: Sequence[Sequence[int]]) -> Tuple[ms.Arm, ...]:
        if len(seg) < 2:
            return ()
        return (ms.Arm("の", seat(seg[-2]), nest(seg[:-1])),)

    head = seat(last[-1])
    prefix = text[:units[last[0][0]].a] if cs else ""
    return TopicHead(head.text, head.units, nest(last), prefix)


def _flatten(arms: Sequence[ms.Arm]) -> Path:
    out: List[Tuple[str, str]] = []
    for a in arms:
        out.append((a.particle, a.seat.text))
        out.extend(_flatten(a.arms))
    return tuple(out)


# ------------------------------------------------------------------------------------------------------------
# the builder (a fold over the sentences, incremental)
# ------------------------------------------------------------------------------------------------------------
class _Rec:
    __slots__ = ("slot", "phrase", "units", "sid", "k", "seq", "turn", "session", "origin", "key", "path", "children", "via", "nest", "change", "surface", "scope", "written")

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class _CrossRec:
    __slots__ = ("tank", "centre", "centre_units", "recs", "occ", "view", "json", "arm_n")

    def __init__(self, tank: str, centre: str, centre_units: Tuple[str, ...]) -> None:
        self.tank, self.centre, self.centre_units = tank, centre, centre_units
        self.recs: List[_Rec] = []
        self.occ: List[Prov] = []
        self.view: Optional[Cross] = None
        self.json: Optional[str] = None
        self.arm_n: Dict[str, int] = {}


class _NestRec:
    __slots__ = ("id", "topic", "head", "declared", "apx", "members", "mjson", "view", "json")

    def __init__(self, id_: str, topic: str, head: TopicHead) -> None:
        self.id, self.topic, self.head = id_, topic, head
        self.declared: List[Tuple[int, int]] = []
        self.apx: Tuple[str, ...] = tuple(ph for _, ph in _flatten(head.arms))
        self.members: List[Member] = []
        self.mjson: List[str] = []
        self.view: Optional[Nest] = None
        self.json: Optional[str] = None


class _PosRec:
    __slots__ = ("pos", "recs", "entries", "json")

    def __init__(self, pos: Position) -> None:
        self.pos = pos
        self.recs: List[_Rec] = []
        self.entries: Tuple[Entry, ...] = ()
        self.json: Optional[str] = None


def _change_rec(c: ms.Change) -> ChangeRec:
    return ChangeRec(None if c.old is None else c.old.text, () if c.old is None else tuple(c.old.units), c.new.text, c.form)


def _entries_of(recs: Sequence[_Rec], marks: Dict[int, Mark]) -> Tuple[Entry, ...]:
    """The values of a position in slide order (sid, then clause), each with its kind (first | update | other), whether a change clause's old value is the value before it, and the mark of its sentence."""
    ents: List[Entry] = []
    replaced_by: Dict[int, bool] = {}                      # the sentences that replaced an earlier value of this position (looked up, never iterated)
    for j, r in enumerate(recs):
        m = marks.get(r.sid)
        superseded_here = r.sid in replaced_by
        if j == 0:
            kind = "first"
        elif r.change is not None or superseded_here:
            kind = "update"
        else:
            kind = "other"
        om: Optional[bool] = None
        if r.change is not None and r.change.old is not None and j > 0:
            om = r.change.old == ents[-1].value
        ents.append(Entry(r.phrase, r.sid, r.k, r.session, r.turn, kind, r.change, om, () if m is None else (m,), r.scope, r.units))
        if m is not None:
            replaced_by[m.by] = True
    return tuple(ents)


def pair_head(corpus: Any, units: Sequence[str]) -> str:
    """The unit that stands for a phrase in the key swap: the RAREST unit of the phrase in the history C_<sid (fewest sentences, at least one), the earliest on a tie; the last unit if none of them is in the
    history.  (The last unit is a suffix too often: 甲社 / 乙社 would both be 社.)"""
    t = corpus.tier("WORD")
    best: Optional[Tuple[int, int]] = None
    for i, u in enumerate(units):
        n = len(t.postings.get(u, ()))
        if n > 0 and (best is None or n < best[0]):
            best = (n, i)
    return units[best[1]] if best is not None else units[-1]


def pair_key(corpus: Any, particle: str, first_units: Sequence[str], second_units: Sequence[str]) -> dict:
    """The EXISTING key swap (`read.loom_key`, the move of `geometry.moves_swap` between the centre and its only arm unit) for a pair of phrases, against the memory corpus `corpus` = C_<sid: the cross as the
    sentence wrote it (arm unit = the phrase written first, on `particle`; centre = the phrase written second; each phrase by its `pair_head`) against the cross with centre and arm unit swapped.  `agrees` =
    the swap improves (n, p): the history holds the pair in the other order (the REVERSAL of mem.v1, here asked of the pair the structure found in opposite roles)."""
    t, adh, w = corpus.tier("WORD"), corpus.adhesion["WORD"], corpus.weights("WORD")
    first_head, second_head = pair_head(corpus, first_units), pair_head(corpus, second_units)

    def mk(centre: str, seat: str) -> Any:
        arms: List[List[Optional[str]]] = [[None, fd.token(p)] for p in SPEC.arms]
        arms[SPEC.arms.index(particle)][0] = seat
        return geo.Cross.make(L=2, center=centre, arms=arms)

    base = rd.loom_key(t, adh, mk(second_head, first_head), w, False)
    swapped = rd.loom_key(t, adh, mk(first_head, second_head), w, False)
    return {"base": [int(x) for x in base], "swapped": [int(x) for x in swapped], "agrees": bool(rd._cmp_key(swapped, "strict_np") > rd._cmp_key(base, "strict_np"))}


def _split_units(units: Sequence[str], text: str, cut: int) -> Optional[int]:
    """How many of `units` lie in text[:cut] (their lengths add up to exactly `cut` characters once the function characters of the gap are left out); None if no such prefix."""
    n = 0
    total = 0
    for i, u in enumerate(units):
        total += len(u)
        if total == cut:
            return i + 1
        if total > cut:
            return None
    return None


class IndexBuilder:
    """The fold.  `declare` / `add_row` / `supersede` / `bridge` are called in the order of the ledger; `index()` is the derived `MemIndex` (cached until the next call).  Everything is kept per part with its
    cached view and canonical JSON, so a call dirties only what it touched."""

    def __init__(self, shape_version: str = ms.SHAPES_V2, flat: bool = False, geometry: Any = None) -> None:
        self.shape_version = shape_version
        self.geo = as_geometry(geometry, flat)               # ABLATE: the geometry profile; all on = the crosses (byte for byte as before), all off = the flat table of PUB-M8 (A3f, byte for byte as before)
        self.flat = self.geo.flat
        self._topic: Dict[int, str] = {}                     # flat only: session -> the topic declared in it, a PLAIN COLUMN (it is the scope of the seats, nothing more)
        self.n = 0
        self._sessions: List[int] = []
        self._sess: List[List[int]] = []
        self._edges: List[str] = []
        self._nests: List[_NestRec] = []
        self._open: Dict[int, _NestRec] = {}                 # session -> the nest open in it (looked up, never iterated)
        self._by_topic: Dict[str, _NestRec] = {}             # looked up, never iterated
        self._crosses: Dict[Tuple[str, str], _CrossRec] = {}  # looked up, never iterated
        self._cross_order: List[Tuple[str, str]] = []
        self._tank_cross: Dict[str, List[Tuple[str, str]]] = {t: [] for t in TANKS}
        self._sid_cross: Dict[int, List[Tuple[str, str]]] = {}
        self._seat_n: Dict[str, int] = {t: 0 for t in TANKS}
        self._max_L: Dict[str, int] = {t: 0 for t in TANKS}
        self._clauses: List[ClauseRec] = []
        self._clause_json: List[str] = []
        self._f0: List[F0Entry] = []
        self._f0_json: List[str] = []
        self._marks: Dict[int, Mark] = {}                    # looked up, never iterated
        self._pos: Dict[Position, _PosRec] = {}              # looked up, never iterated
        self._pos_order: List[Position] = []
        self._sid_pos: Dict[int, List[Position]] = {}
        self._det = mdt.Detector()
        self._notes: List[dict] = []
        self._note_json: List[str] = []
        self._bridges: List[Bridge] = []
        self.last_notes: List[dict] = []                     # the notes the last add_row made
        self._seq = 0
        self._ver = 0
        self._cache: Optional[Tuple[int, "MemIndex"]] = None
        self._exch: Dict[str, ms.Exchange] = {}

    # -- declarations, bridges and marks -----------------------------------------------------------------------------
    def declare(self, session: int, at: int, topic: str) -> dict:
        head = topic_head(topic)
        if head is None:
            raise ValueError("a topic needs a word unit")
        if not self.geo.nests:                               # PUB-M8: no nest.  The topic is a plain column: the scope of the seats written after it in this session (a string, no structure)
            reopened = self._topic.get(session) == topic
            self._topic[session] = topic
            self._ver += 1
            return {"id": None, "topic": topic, "centre": None, "arms": [], "prefix": "", "reopened": reopened, "flat": True}
        nr = self._by_topic.get(topic)
        reopened = nr is not None
        if nr is None:
            nr = _NestRec("N%d" % (len(self._nests) + 1), topic, head)
            self._nests.append(nr)
            self._by_topic[topic] = nr
            for c in self._clauses:                          # the clauses written before it that sit on its centre / under it
                m = self._member(c, nr)
                if m is not None:
                    nr.members.append(m)
                    nr.mjson.append(canonical(m.to_obj()))
        nr.declared.append((session, at))
        nr.view = nr.json = None
        self._open[session] = nr
        self._ver += 1
        return {"id": nr.id, "topic": topic, "centre": head.centre, "arms": [list(a) for a in _flatten(head.arms)], "prefix": head.prefix, "reopened": reopened}

    def bridge(self, session: int, at: int, qword: str, phrase: str) -> bool:
        """Add the bridge (qword -> phrase).  False if it is already there (nothing changes)."""
        for b in self._bridges:
            if b.qword == qword and b.phrase == phrase:
                return False
        self._bridges.append(Bridge(qword, phrase, session, at))
        self._ver += 1
        return True

    def has_centre(self, phrase: str) -> bool:
        return any((t, phrase) in self._crosses for t in TANKS)

    def supersede(self, sid: int, by: int, reason: str, session: int) -> None:
        self._marks[sid] = Mark(MARK_SUPERSEDED, by, reason, session)
        for key in self._sid_cross.get(sid, ()):
            cr = self._crosses[key]
            cr.view = cr.json = None
        for s in (sid, by):
            for pos in self._sid_pos.get(s, ()):
                pr = self._pos[pos]
                pr.entries = _entries_of(pr.recs, self._marks)
                pr.json = None
        self._ver += 1

    # -- one sentence -----------------------------------------------------------------------------------------------
    def _exchange(self, text: str) -> ms.Exchange:
        e = self._exch.get(text)
        if e is None:
            e = self._exch[text] = ms.exchange(text, self.shape_version)
        return e

    def open_nest_id(self, session: int) -> Optional[str]:
        if not self.geo.nests:
            return None                                      # PUB-M8: there is no nest to prefer
        nr = self._open.get(session)
        return None if nr is None else nr.id

    def _member(self, c: ClauseRec, nr: _NestRec) -> Optional[Member]:
        if c.tank is None:
            return None
        if c.via == NEST_VIA and c.nest == nr.id:
            kind = "completed"
        elif c.centre == nr.head.centre:
            kind = "centre"
        elif any(p == "の" and ph == nr.head.centre for p, ph in c.path):
            kind = "path"
        elif c.open_nest == nr.id:
            kind = "context"                                 # L-PUB-39: written while the nest was open, no other tie
        else:
            return None
        if kind == "completed":
            exact = True
        elif kind == "context":
            exact = False
        else:
            have = [ph for _, ph in c.path] + [c.centre or ""]
            exact = all(a in have for a in nr.apx)
        return Member(c.sid, c.k, c.tank, c.centre or "", kind, exact)

    def add_row(self, sid: int, row: dict, corpus_before: Any) -> Tuple[ClauseRec, ...]:
        """Place the sentence `sid` (the next one).  `corpus_before` = the memory corpus of the sentences before it (C_<sid).  -> the clause records it made; the notes it fired are in `last_notes`."""
        if sid != self.n:
            raise ValueError("sentences are added in order: expected %d, got %d" % (self.n, sid))
        p = parse_source(row["source"])
        if p is None:
            raise ValueError("not a memory row")
        session = p[1]
        turn = row.get("turn")
        self.n += 1
        self._sessions.append(session)
        if self._sess and self._sess[-1][0] == session:
            self._sess[-1][2] = sid
        else:
            self._sess.append([session, sid, sid])
        if sid > 0 and self.geo.slide:                        # PUB-M8: the flat table has no slide order (updates are read by sid order only)
            self._edges.append("[%d,%d,%d]" % (sid - 1, sid, 1 if self._sessions[sid - 1] != session else 0))
        self._ver += 1
        self.last_notes = []
        ex = self._exchange(row["sent"])
        if row.get("unshaped") is True:                       # the F0 tank: in H, searchable as text.  Designer decision L-PUB-42: its F1-F4 clauses are still indexed (below); only the F0 clause itself stays unshaped
            e = F0Entry(sid, session, turn, row["sent"], ex.shapes(), tuple(c.reason or "" for c in ex.clauses if c.shape == "F0"))
            self._f0.append(e)
            self._f0_json.append(canonical(e.to_obj()))
        nr = self._open.get(session)
        open_id = None if nr is None else nr.id
        if not self.geo.nests:
            nr, open_id = None, self._topic.get(session)      # PUB-M8: the topic column is the scope; no nest completes an F4 clause
        out: List[ClauseRec] = []
        notes: List[dict] = []
        for k, c in enumerate(ex.clauses):
            cr, nn = self._place(sid, k, session, turn, c, nr, open_id, corpus_before)
            out.append(cr)
            notes += nn
        for cr in out:
            self._clauses.append(cr)
            self._clause_json.append(canonical(cr.to_obj()))
            for n_ in self._nests:
                m = self._member(cr, n_)
                if m is not None:
                    n_.members.append(m)
                    n_.mjson.append(canonical(m.to_obj()))
                    n_.view = n_.json = None
        notes = mdt.order_notes(notes)
        for n in notes:
            self._notes.append(n)
            self._note_json.append(canonical(n))
        self.last_notes = notes
        return tuple(out)

    def _touch(self, key: Tuple[str, str], cr: _CrossRec, sid: int) -> None:
        cr.view = cr.json = None
        lst = self._sid_cross.setdefault(sid, [])
        if not lst or lst[-1] != key:
            lst.append(key)

    def _place(self, sid: int, k: int, session: int, turn: Optional[str], c: ms.Clause, nr: Optional[_NestRec], open_id: Optional[str], corpus: Any) -> Tuple[ClauseRec, List[dict]]:
        if c.shape == "F0":
            return ClauseRec(sid, k, session, turn, "F0", None, None, c.text, None, None, open_id, (), None, None, tuple(a.text for a in c.adverbial), c.reason), []
        tank, via, nest_id = c.shape, None, None
        arms: Tuple[ms.Arm, ...] = c.arms
        if c.shape == "F4" and nr is not None:               # M3: completed structurally by the nest: nothing is prepended to the text
            tank, via, nest_id = "F3", NEST_VIA, nr.id
            subject = ms.Arm(NEST_ARM, ms.Seat(nr.head.centre, nr.head.centre_units, (0, 0)), nr.head.arms)
            arms = tuple(sorted(arms + (subject,), key=lambda a: ms.READ_ORDER.index(a.particle)))
        key = (tank, c.centre or "")
        cr = self._crosses.get(key)
        if cr is None:
            cr = self._crosses[key] = _CrossRec(tank, c.centre or "", tuple(c.centre_units))
            self._cross_order.append(key)
            self._tank_cross[tank].append(key)
        self._touch(key, cr, sid)
        head = c.centre_units[-1] if c.centre_units else (c.centre or "")
        ch = None if c.change is None else _change_rec(c.change)
        surface = c.surface if c.surface is not None else (c.centre or "")
        cr.occ.append(Prov(sid, turn, session, origin_of(corpus, c.centre_units), surface, k))
        path = _flatten(arms)

        def rec(slot: str, phrase: str, units: Tuple[str, ...], centre_head: str, sub: Sequence[ms.Arm], v: Optional[str], nid: Optional[str], change: Optional[ChangeRec], p: Path, written: str = "") -> _Rec:
            """One seat (and, below it, the seats of its own arms: the chain).  `p` = its path: an arm seat's ancestors, a value seat's position."""
            self._seq += 1
            self._seat_n[tank] += 1
            seat_head = units[-1] if units else phrase
            r = _Rec(slot=slot, phrase=phrase, units=tuple(units), sid=sid, k=k, seq=self._seq, turn=turn, session=session, origin=origin_of(corpus, units),
                     key=seat_key(corpus, slot, centre_head, seat_head, self.geo.ladder, self.geo.arms) if self.geo.key else (0, 0, 0), path=p, children=[], via=v, nest=nid, change=change, surface=phrase, scope=open_id, written=written)
            for a in sub:
                r.children.append((a.particle, rec(a.particle, a.seat.text, a.seat.units, seat_head, a.arms, v, nid, None, p + ((slot, phrase),), a.written)))
            return r

        def top(r: _Rec) -> None:
            cr.recs.append(r)
            if r.slot in ARMS:
                cr.arm_n[r.slot] = cr.arm_n.get(r.slot, 0) + 1
                self._max_L[tank] = max(self._max_L[tank], 1 + max(cr.arm_n.values()))
            else:
                self._max_L[tank] = max(self._max_L[tank], 1)

        for a in arms:
            is_nest = via == NEST_VIA and a.particle == NEST_ARM
            top(rec(a.particle, a.seat.text, a.seat.units, head, a.arms, via if is_nest else None, nest_id if is_nest else None, None, (), a.written))
        notes: List[dict] = []
        if c.value is not None:
            vr = rec(VALUE, c.value.text, c.value.units, head, (), None, None, ch, path)
            top(vr)
            pos: Position = (tank, c.centre or "", path)
            pr = self._pos.get(pos)
            if pr is None:
                pr = self._pos[pos] = _PosRec(pos)
                self._pos_order.append(pos)
            pr.recs.append(vr)
            pr.entries = _entries_of(pr.recs, self._marks)
            pr.json = None
            lst = self._sid_pos.setdefault(sid, [])
            if pos not in lst:
                lst.append(pos)
            notes += self._det.observe_value(tank=tank, centre=c.centre or "", path=path, scope=open_id, value=c.value.text, sid=sid, k=k, turn=turn,
                                             change=None if ch is None else {"old": ch.old, "form": ch.form})
        if c.quantity is not None:
            top(rec("quantity", c.quantity.text, c.quantity.units, head, (), None, None, None, ()))
        if c.object_bare is not None:
            top(rec("object_bare", c.object_bare.text, c.object_bare.units, head, (), None, None, None, ()))
        if tank in ("F3", "F4") and c.value is None:
            notes += self._det.observe_event(tank=tank, centre=c.centre or "", arms=[(a.particle, a.seat.text) for a in arms], scope=open_id, sid=sid, k=k, turn=turn)
        for rl in _relations(c, arms, tank):
            notes += self._det.observe_relation(kind=rl[0], label=rl[1], first=rl[2], second=rl[3], particle=rl[4], first_units=rl[5], second_units=rl[6], sid=sid, k=k, turn=turn,
                                                judge=(lambda particle, fu, su: pair_key(corpus, particle, fu, su) if fu and su else None) if self.geo.swap else None)
        return (ClauseRec(sid, k, session, turn, c.shape, tank, c.centre, c.text, via, nest_id, open_id, path, None if c.value is None else c.value.text, ch,
                          tuple(a.text for a in c.adverbial), None), notes)

    # -- the derived index -------------------------------------------------------------------------------------------
    def index(self) -> "MemIndex":
        if self._cache is not None and self._cache[0] == self._ver:
            return self._cache[1]
        idx = self._snapshot()
        self._cache = (self._ver, idx)
        return idx

    def _seat_view(self, r: _Rec, rank: int, ring: int) -> Seat:
        m = self._marks.get(r.sid)
        kids = tuple((p, self._seat_view(ch, 0, 1)) for p, ch in r.children)
        return Seat(r.slot, r.phrase, r.units, Prov(r.sid, r.turn, r.session, r.origin, r.surface, r.k), r.key, rank, ring, r.path, kids, r.via, r.nest, r.change,
                    () if m is None else (m,), r.scope, r.written)

    def _cross_view(self, cr: _CrossRec) -> Cross:
        if cr.view is not None:
            return cr.view
        slots: List[Tuple[str, Tuple[Seat, ...]]] = []
        longest = 0
        for slot in SLOTS:
            recs = [r for r in cr.recs if r.slot == slot]
            if not recs:
                continue
            recs.sort(key=lambda r: (-r.key[0], -r.key[1], -r.key[2], r.sid, r.k, r.seq))
            on_arm = slot in ARMS
            slots.append((slot, tuple(self._seat_view(r, i, i + 1 if on_arm else 0) for i, r in enumerate(recs))))
            if on_arm:
                longest = max(longest, len(recs))
        occ = tuple(sorted(cr.occ, key=lambda o: (o.sid, o.clause)))
        cr.view = Cross(cr.tank, cr.centre, cr.centre_units, 1 + longest, tuple(slots), occ)
        return cr.view

    def _cross_json(self, cr: _CrossRec) -> str:
        if cr.json is None:
            cr.json = canonical(self._cross_view(cr).to_obj())
        return cr.json

    def _nest_view(self, nr: _NestRec) -> Nest:
        if nr.view is None:
            nr.view = Nest(nr.id, nr.topic, nr.head.centre, nr.head.centre_units, _flatten(nr.head.arms), nr.head.prefix, tuple(nr.declared), tuple(nr.members))
        return nr.view

    def _nest_json(self, nr: _NestRec) -> str:
        if nr.json is None:
            nr.json = '{"arms":%s,"centre":%s,"centre_units":%s,"declared":%s,"id":%s,"members":[%s],"prefix":%s,"topic":%s}' % (
                canonical([list(a) for a in _flatten(nr.head.arms)]), canonical(nr.head.centre), canonical(list(nr.head.centre_units)), canonical([list(d) for d in nr.declared]),
                canonical(nr.id), ",".join(nr.mjson), canonical(nr.head.prefix), canonical(nr.topic))
        return nr.json

    def _pos_json(self, pos: Position) -> str:
        pr = self._pos[pos]
        if pr.json is None:
            pr.json = canonical([pos[0], pos[1], [list(p) for p in pos[2]], [e.to_obj() for e in pr.entries]])
        return pr.json

    def _assemble(self) -> str:
        """The canonical JSON of the index, assembled from the cached parts in the order (sorted keys) `MemIndex.to_obj()` has: byte for byte `canonical(to_obj())`."""
        tanks = "[" + ",".join("[%s,[%s]]" % (canonical(t), ",".join(self._cross_json(self._crosses[k]) for k in self._tank_cross[t])) for t in TANKS) + "]"
        return '{"bridges":[%s],"clauses":[%s],"edges":[%s],"f0":[%s],"n":%d,"nests":[%s],"notes":[%s],"positions":[%s],"sessions":%s,"shape":%s,"tanks":%s,"v":%s}' % (
            ",".join(canonical(b.to_obj()) for b in self._bridges), ",".join(self._clause_json), ",".join(self._edges), ",".join(self._f0_json), self.n,
            ",".join(self._nest_json(nr) for nr in self._nests), ",".join(self._note_json), ",".join(self._pos_json(p) for p in self._pos_order), canonical(self._sess),
            canonical(self.shape_version), tanks, canonical(self.geo.version()))

    def _snapshot(self) -> "MemIndex":
        crosses = tuple(self._cross_view(self._crosses[k]) for k in self._cross_order)
        nests = tuple(self._nest_view(nr) for nr in self._nests)
        counts = {t: {"crosses": len(self._tank_cross[t]), "seats": self._seat_n[t], "max_L": self._max_L[t]} for t in TANKS}
        sha = sha256_text(self._assemble())
        return MemIndex(self.shape_version, self.n, tuple(self._sessions), crosses, tuple(self._f0), nests, tuple(self._clauses), dict(self._marks),
                        hist={p: self._pos[p].entries for p in self._pos_order}, positions=tuple(self._pos_order), notes=tuple(self._notes), bridges=tuple(self._bridges),
                        counts=counts, sha=sha, geometry=self.geo)


def _relations(c: ms.Clause, arms: Sequence[ms.Arm], tank: str) -> List[tuple]:
    """The relations a clause writes, each (kind, label, first, second, particle, first_units, second_units) with `first` written before `second`: the two ends of every の link (「X の Y」: X, Y), the
    が / を pair of an event (label: the centre), and 「A は P の Q」 (label Q; A = the centre, P = the part of the value before の)."""
    out: List[tuple] = []

    def links(owned_text: str, owned_units: Tuple[str, ...], sub: Sequence[ms.Arm]) -> None:
        for a in sub:
            if a.particle == "の":
                out.append(("の", "", a.seat.text, owned_text, "の", tuple(a.seat.units), tuple(owned_units)))
                links(a.seat.text, tuple(a.seat.units), a.arms)

    if c.shape in ("F1", "F2") and c.centre:
        links(c.centre, tuple(c.centre_units), arms)
    if c.shape == "F2" and c.centre and c.value is not None and c.change is None:
        v = c.value
        i = v.text.find("の")
        if 0 < i < len(v.text) - 1 and v.text.count("の") == 1:
            n_p = _split_units(v.units, v.text, i)
            if n_p is not None and n_p < len(v.units):
                out.append(("value", v.text[i + 1:], c.centre, v.text[:i], "の", tuple(c.centre_units), tuple(v.units[:n_p])))
    if tank in ("F3", "F4") and c.value is None:
        subj = [a for a in arms if a.particle == "が"]
        obj = [a for a in arms if a.particle == "を"]
        if len(subj) == 1 and len(obj) == 1:
            out.append(("event", c.centre or "", subj[0].seat.text, obj[0].seat.text, "が", tuple(subj[0].seat.units), tuple(obj[0].seat.units)))
    return out


# ------------------------------------------------------------------------------------------------------------
# the index
# ------------------------------------------------------------------------------------------------------------
class MemIndex:
    """The derived index: tanks, nests, clauses, the slide order, the notes, the bridges.  A snapshot, immutable after construction; `index_sha` is the sha256 of its canonical serialisation."""

    def __init__(self, shape_version: str, n: int, sessions: Tuple[int, ...], crosses: Tuple[Cross, ...], f0: Tuple[F0Entry, ...], nests: Tuple[Nest, ...],
                 clauses: Tuple[ClauseRec, ...], marks: Dict[int, Mark], *, hist: Dict[Position, Tuple[Entry, ...]], positions: Tuple[Position, ...], notes: Tuple[dict, ...] = (),
                 bridges: Tuple[Bridge, ...] = (), counts: Optional[dict] = None, sha: Optional[str] = None, flat: bool = False, geometry: Any = None) -> None:
        self.geo = as_geometry(geometry, flat)
        self.flat = self.geo.flat
        self.shape_version, self.n, self.sessions = shape_version, n, sessions
        self.crosses, self.f0, self.nests, self.clauses = crosses, f0, nests, clauses
        self.notes, self.bridges = notes, bridges
        self._marks = marks                                  # looked up only
        self._hist = hist
        self.positions = positions
        self._counts = counts
        self._by_key: Optional[Dict[Tuple[str, str], Cross]] = None
        self._edges: Optional[Tuple[Tuple[int, int, int], ...]] = None
        self._by_centre: Optional[Dict[str, List[Position]]] = None
        self._flat: Optional[Dict[str, List[Position]]] = None
        self._text: Optional[Dict[str, List[Position]]] = None
        self._clause_at: Optional[Dict[Tuple[int, int], ClauseRec]] = None
        self._sha: Optional[str] = sha

    # -- M2 queries -------------------------------------------------------------------------------------------------
    def tank(self, tank: str) -> Tuple[Cross, ...]:
        return tuple(c for c in self.crosses if c.tank == tank)

    def cross(self, tank: str, centre: str) -> Optional[Cross]:
        if self._by_key is None:
            self._by_key = {(c.tank, c.centre): c for c in self.crosses}
        return self._by_key.get((tank, centre))

    @property
    def edges(self) -> Tuple[Tuple[int, int, int], ...]:
        if self._edges is None:
            self._edges = () if not self.geo.slide else tuple((i, i + 1, 1 if self.sessions[i] != self.sessions[i + 1] else 0) for i in range(self.n - 1))
        return self._edges

    def seats(self, cross: Cross, arm_path: Any) -> Tuple[Seat, ...]:
        """The seats on an arm of `cross`, in rank order.  `arm_path`: "の" (the の arm), or a sequence of steps to go through the arms of the seats on the way, each step a particle or
        (particle, phrase-or-None): (("の", "Y"), ("の", None)) = the の-arm seats of the seats Y that sit on the cross's の arm.  The last step names the arm that is listed."""
        steps = _steps(arm_path)
        if not steps:
            return ()
        level = cross.seats_of(steps[0][0])
        for (_, ph_prev), (p, _ph) in zip(steps, steps[1:]):
            level = tuple(c for s in level if ph_prev is None or s.phrase == ph_prev for q, c in s.arms if q == p)
        if steps[-1][1] is not None:
            level = tuple(s for s in level if s.phrase == steps[-1][1])
        return level

    def value_seats(self, cross: Cross, arm_path: Optional[Sequence[Tuple[str, str]]] = None) -> Tuple[Seat, ...]:
        """The value seats (the は slot) of `cross` in rank order; with `arm_path` only those written under that clause path (the position)."""
        v = cross.seats_of(VALUE)
        if arm_path is None:
            return v
        want = tuple((p, ph) for p, ph in arm_path)
        return tuple(s for s in v if s.path == want)

    def centres_with(self, phrase: str) -> Tuple[Tuple[str, str, str], ...]:
        """Every cross that holds `phrase`: (tank, centre, where), where = "centre" | "<slot>" (a seat on that arm / value / quantity / object_bare, a nested seat as "の>の").  Cross order, then slot order."""
        out: List[Tuple[str, str, str]] = []
        for c in self.crosses:
            if c.centre == phrase:
                out.append((c.tank, c.centre, "centre"))
            for slot, seats in c.slots:
                found: List[str] = []
                for s in seats:
                    _holds(s, phrase, slot, found)
                for w in found:
                    if (c.tank, c.centre, w) not in out:
                        out.append((c.tank, c.centre, w))
        return tuple(out)

    # -- M3 queries -------------------------------------------------------------------------------------------------
    def nest(self, topic: str) -> Optional[Nest]:
        for n in self.nests:
            if n.topic == topic:
                return n
        return None

    def nests_of(self, centre: str) -> Tuple[Nest, ...]:
        return tuple(n for n in self.nests if n.centre == centre)

    def nest_by_id(self, nid: Optional[str]) -> Optional[Nest]:
        if nid is None:
            return None
        for n in self.nests:
            if n.id == nid:
                return n
        return None

    # -- M4 queries -------------------------------------------------------------------------------------------------
    def history(self, position: Any) -> List[Tuple[str, int, str]]:
        """[(value, sid, kind)] of a position (tank, centre, path) in slide order; kind = first | update | other.  An unknown position: []."""
        return [(e.value, e.sid, e.kind) for e in self.history_full(position)]

    def history_full(self, position: Any) -> Tuple[Entry, ...]:
        return self._hist.get(_position(position), ())

    # -- M6 queries -------------------------------------------------------------------------------------------------
    def positions_of(self, centre: str, tanks: Sequence[str] = TANKS) -> Tuple[Position, ...]:
        """Every position whose centre is `centre`, in the order the positions got their first value."""
        if self._by_centre is None:
            d: Dict[str, List[Position]] = {}
            for p in self.positions:
                d.setdefault(p[1], []).append(p)
            self._by_centre = d
        return tuple(p for p in self._by_centre.get(centre, ()) if p[0] in tanks)

    def positions_flat(self, flat: str) -> Tuple[Position, ...]:
        """The positions of F1 / F2 whose phrase read as ONE string equals `flat`: the owner phrases from the outermost to the centre, joined (「認証モジュール」「担当」 -> 認証モジュール担当).  This is what lets a
        question 「認証モジュール担当」 meet the sentence 「認証モジュールの担当は…」 and the other way round."""
        if self._flat is None:
            d: Dict[str, List[Position]] = {}
            for p in self.positions:
                f = flat_of(p)
                if f is not None:
                    d.setdefault(f, []).append(p)
            self._flat = d
        return tuple(self._flat.get(flat, ()))

    def positions_text(self, text: str) -> Tuple[Position, ...]:
        """PUB-M6c: the F1 / F2 positions whose phrase is `text`, written with 「の」 (`position_text`) or without (`flat_of`), in the order the positions got their first value."""
        if self._text is None:
            d: Dict[str, List[Position]] = {}
            for p in self.positions:
                for t in (position_text(p), flat_of(p)):
                    if t is not None and (t not in d or p not in d[t]):
                        d.setdefault(t, []).append(p)
            self._text = d
        return tuple(self._text.get(text, ()))

    def clause_rec(self, sid: int, k: int) -> Optional[ClauseRec]:
        if self._clause_at is None:
            self._clause_at = {(c.sid, c.k): c for c in self.clauses}
        return self._clause_at.get((sid, k))

    def mark_of(self, sid: int) -> Optional[Mark]:
        return self._marks.get(sid)

    @property
    def marks(self) -> Dict[int, Mark]:
        return dict(self._marks)

    # -- numbers ----------------------------------------------------------------------------------------------------
    def stats(self) -> dict:
        out: Dict[str, Any] = {}
        for t in TANKS:
            if self._counts is not None:
                out[t] = dict(self._counts[t])
            else:
                cs = self.tank(t)
                out[t] = {"crosses": len(cs), "seats": sum(c.n_seats() for c in cs), "max_L": max([c.L for c in cs], default=0)}
        out[F0_TANK] = {"sentences": len(self.f0)}
        out["nests"] = len(self.nests)
        out["positions"] = len(self.positions)
        return out

    def note_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {t: 0 for t in mdt.CROSS_NOTE_TYPES}
        for n in self.notes:
            out[n["type"]] += 1
        return out

    # -- serialisation ----------------------------------------------------------------------------------------------
    def to_obj(self) -> dict:
        sess: List[List[int]] = []
        for i, s in enumerate(self.sessions):
            if not sess or sess[-1][0] != s:
                sess.append([s, i, i])
            else:
                sess[-1][2] = i
        return {"v": self.geo.version(), "shape": self.shape_version, "n": self.n, "sessions": sess,
                "tanks": [[t, [c.to_obj() for c in self.tank(t)]] for t in TANKS], "f0": [e.to_obj() for e in self.f0], "nests": [n.to_obj() for n in self.nests],
                "clauses": [c.to_obj() for c in self.clauses], "edges": [list(e) for e in self.edges],
                "positions": [[t, c, [list(p) for p in path], [e.to_obj() for e in self._hist[(t, c, path)]]] for t, c, path in self.positions],
                "notes": list(self.notes), "bridges": [b.to_obj() for b in self.bridges]}

    @property
    def index_sha(self) -> str:
        if self._sha is None:
            self._sha = sha256_text(canonical(self.to_obj()))
        return self._sha

    def render(self, cross: Cross) -> str:
        return render_cross(cross)


def position_text(position: Position) -> Optional[str]:
    """PUB-M6c: the phrase of an F1 / F2 position as the memory writes it, owners outermost first, joined by 「の」 (認証モジュールの担当; an F2 position: its centre); None for an event position or a path
    that holds a particle other than の.  What `recall` shows as a candidate and what `bridge(question_phrase, memory_phrase)` takes."""
    tank, centre, path = position
    if tank not in ("F1", "F2") or any(p != "の" for p, _ in path):
        return None
    return "の".join([ph for _, ph in reversed(path)] + [centre])


def flat_of(position: Position) -> Optional[str]:
    """The phrase of an F1 / F2 position as one string (owners outermost first, then the centre); None for an event position or a path that holds a particle other than の."""
    tank, centre, path = position
    if tank not in ("F1", "F2") or any(p != "の" for p, _ in path):
        return None
    return "".join(ph for _, ph in reversed(path)) + centre


def _steps(arm_path: Any) -> List[Tuple[str, Optional[str]]]:
    if isinstance(arm_path, str):
        return [(arm_path, None)]
    out: List[Tuple[str, Optional[str]]] = []
    for s in arm_path:
        if isinstance(s, str):
            out.append((s, None))
        else:
            out.append((s[0], s[1]))
    return out


def _position(position: Any) -> Position:
    t, c, path = position[0], position[1], position[2]
    return (t, c, tuple((p, ph) for p, ph in path))


def _holds(s: Seat, phrase: str, where: str, out: List[str]) -> None:
    if s.phrase == phrase:
        out.append(where)
    for p, c in s.arms:
        _holds(c, phrase, where + ">" + p, out)


def _seat_text(s: Seat) -> str:
    t = "%s(s%d)" % (s.phrase, s.prov.sid)
    if s.arms:
        t += "{" + ", ".join("%s:%s" % (p, _seat_text(c)) for p, c in s.arms) + "}"
    if s.change is not None:
        t += "<%s%s>" % ("" if s.change.old is None else s.change.old + "->", s.change.form)
    if s.via:
        t += "[via %s]" % s.via
    if s.marks:
        t += "[superseded by s%d]" % s.marks[0].by
    return t


def render_cross(c: Cross) -> str:
    """A cross as text: the centre, L, and the seats of every arm in ring order with their sids."""
    lines = ["[%s] %s  (L=%d, written %d times)" % (c.tank, c.centre, c.L, len(c.occurrences))]
    for slot, seats in c.slots:
        lines.append("  %s: %s" % (slot, " | ".join(_seat_text(s) for s in seats)))
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------
# the pure function of H (the FULL REBUILD: replay / verify run it and require it to equal the incremental index byte for byte)
# ------------------------------------------------------------------------------------------------------------
def build_index(rows: Sequence[dict], decls: Sequence[dict] = (), superseded: Optional[Dict[int, dict]] = None, shape_version: str = ms.SHAPES_V2,
                bridges: Sequence[dict] = (), flat: bool = False, geometry: Any = None) -> MemIndex:
    """The index of the memory rows `rows` (each {sent, source, kind?, turn?, unshaped?}), the topic declarations `decls` ([{session, at, topic}]: `at` = how many sentences H held when it was declared),
    the supersede marks `superseded` ({sid: {by, reason, session}}) and the bridges `bridges` ([{session, at, qword, phrase}]).  Builds the memory corpus of every prefix itself (Corpus, never Corpus.load)."""
    b = IndexBuilder(shape_version, flat, geometry)
    order = sorted(range(len(decls)), key=lambda i: (decls[i]["at"], i))
    di = 0
    prev = Corpus(b"")
    for t, row in enumerate(rows):
        while di < len(order) and decls[order[di]]["at"] <= t:
            d = decls[order[di]]
            b.declare(d["session"], d["at"], d["topic"])
            di += 1
        b.add_row(t, row, prev)
        prev = Corpus(_rows_bytes(rows[:t + 1]))
    while di < len(order):
        d = decls[order[di]]
        b.declare(d["session"], d["at"], d["topic"])
        di += 1
    for sid in sorted(superseded or {}):
        v = (superseded or {})[sid]
        b.supersede(sid, v["by"], v["reason"], v["session"])
    for br in bridges:
        b.bridge(br["session"], br["at"], br["qword"], br["phrase"])
    return b.index()


# -- module-level query functions (the same as the methods) ------------------------------------------------------
def cross(index: MemIndex, tank: str, centre: str) -> Optional[Cross]:
    return index.cross(tank, centre)


def seats(index: MemIndex, c: Cross, arm_path: Any) -> Tuple[Seat, ...]:
    return index.seats(c, arm_path)


def value_seats(index: MemIndex, c: Cross, arm_path: Optional[Sequence[Tuple[str, str]]] = None) -> Tuple[Seat, ...]:
    return index.value_seats(c, arm_path)


def centres_with(index: MemIndex, phrase: str) -> Tuple[Tuple[str, str, str], ...]:
    return index.centres_with(phrase)


def nest(index: MemIndex, topic: str) -> Optional[Nest]:
    return index.nest(topic)


def nests_of(index: MemIndex, centre: str) -> Tuple[Nest, ...]:
    return index.nests_of(centre)


def history(index: MemIndex, position: Any) -> List[Tuple[str, int, str]]:
    return index.history(position)
