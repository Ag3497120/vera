"""PUB-M2 / M3 / M4: the memory crosses, the nests and the slide order (docs/LINE3_PUBLIC_DESIGN.md 4.3-4.5; owner OP-PUB-1..8; local decisions L-PUB-24..).

`MemIndex` is a PURE FUNCTION of H (the memory rows, in order) and the topic declarations of the ledger (+ the supersede marks the model made): `build_index(rows, decls, superseded)`.  It is derived, never
stored as truth, and a replay must rebuild it identically (`index_sha`).  It reads the shape exchanger (`memshape.exchange`, table shape.v2) and, for the KEY of a seat and the ORIGIN of its words, the
memory corpus of the sentences BEFORE the one that wrote the seat (the history rule L-MEM-06: a sentence never confirms itself).

TANKS (M2).  One tank per shape: F1 attribute (「X の Y は A」), F2 topic-value (「Y は A」), F3 event, F4 an event clause that no nest could complete (kept uncompleted, see M3).  The F0 tank holds the
sentences the model chose to keep unshaped (OP-PUB-2): they are in H and searchable as text, they enter no cross.  In each tank ONE CROSS per CENTRE PHRASE (the phrase as written: 開催地, 認証モジュール担当; for an
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

Pure and deterministic: no clock, float, process, environment, no set / dict iteration order in any output (lists are built and sorted explicitly).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from verantyx.line3 import foundation as fd
from verantyx.line3 import geometry as geo
from verantyx.loom import memshape as ms
from verantyx.loom import read as rd
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import parse_source
from verantyx.loom.state import SPEC, canonical, sha256_text

CROSS_VERSION = "cross.v1"
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
def seat_key(corpus: Any, slot: str, centre_head: str, seat_head: str) -> Tuple[int, int, int]:
    """(n, p, a) of a seat against `corpus` = C_<sid.  An arm: `read.loom_key` of the cross L = 2 {centre; the seat outermost on its arm; the six foundation tokens innermost} -- the very key the loom reads a
    woven cross with (n, p from the contracted cross's edges, a = numerator(particle) * adj(seat, particle); the centre's は term is the topic mark's and is not counted).  は (a value): (n, p) of the pair
    in READING ORDER (the centre first) and a = numerator(は) * adj(centre, は).  quantity / object_bare: (n, p) of the pair (seat first, then the centre), a = 0.  A word that is not in the space has weight 0
    (L-52): an event's centre is a dictionary form, which is a surface in the space only if it was written so."""
    t, adh, w = corpus.tier("WORD"), corpus.adhesion["WORD"], corpus.weights("WORD")
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

    def to_obj(self) -> dict:
        return {"slot": self.slot, "phrase": self.phrase, "units": list(self.units), "prov": self.prov.to_obj(), "key": list(self.key), "rank": self.rank, "ring": self.ring,
                "path": [list(p) for p in self.path], "arms": [[p, s.to_obj()] for p, s in self.arms], "via": self.via, "nest": self.nest,
                "change": None if self.change is None else self.change.to_obj(), "marks": [m.to_obj() for m in self.marks]}


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
    kind: str                                    # completed | centre | path
    exact: bool

    def to_obj(self) -> dict:
        return {"sid": self.sid, "k": self.k, "tank": self.tank, "centre": self.centre, "kind": self.kind, "exact": self.exact}


@dataclass(frozen=True)
class Nest:
    id: str
    topic: str
    centre: str
    centre_units: Tuple[str, ...]
    arms: Path                                   # the topic's own arms ((の, A社),): the nest's centre seat carries them
    prefix: str                                  # the text of the topic before its head phrase when it is not a の chain (kept, never dropped)
    declared: Tuple[Tuple[int, int], ...]        # (session, at) of every declaration that opened it
    members: Tuple[Member, ...]
    under: Tuple[Tuple[int, int, str, Optional[str]], ...]       # (sid, k, shape, centre) of the clauses written while it was open that are not members

    def to_obj(self) -> dict:
        return {"id": self.id, "topic": self.topic, "centre": self.centre, "centre_units": list(self.centre_units), "arms": [list(a) for a in self.arms], "prefix": self.prefix,
                "declared": [list(d) for d in self.declared], "members": [m.to_obj() for m in self.members], "under": [list(u) for u in self.under]}


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

    def to_obj(self) -> dict:
        return {"value": self.value, "sid": self.sid, "k": self.k, "session": self.session, "turn": self.turn, "kind": self.kind,
                "change": None if self.change is None else self.change.to_obj(), "old_matches": self.old_matches, "marks": [m.to_obj() for m in self.marks]}


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
# the builder (a fold over the sentences)
# ------------------------------------------------------------------------------------------------------------
class _Rec:
    __slots__ = ("slot", "phrase", "units", "sid", "k", "seq", "turn", "session", "origin", "key", "path", "children", "via", "nest", "change", "surface")

    def __init__(self, **kw: Any) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class _CrossRec:
    __slots__ = ("tank", "centre", "centre_units", "recs", "occ")

    def __init__(self, tank: str, centre: str, centre_units: Tuple[str, ...]) -> None:
        self.tank, self.centre, self.centre_units = tank, centre, centre_units
        self.recs: List[_Rec] = []
        self.occ: List[Prov] = []


class _NestRec:
    __slots__ = ("id", "topic", "head", "declared")

    def __init__(self, id_: str, topic: str, head: TopicHead) -> None:
        self.id, self.topic, self.head = id_, topic, head
        self.declared: List[Tuple[int, int]] = []


def _change_rec(c: ms.Change) -> ChangeRec:
    return ChangeRec(None if c.old is None else c.old.text, () if c.old is None else tuple(c.old.units), c.new.text, c.form)


class IndexBuilder:
    """The fold.  `declare` / `add_row` / `supersede` are called in the order of the ledger; `index()` is the derived `MemIndex` (cached until the next call)."""

    def __init__(self, shape_version: str = ms.SHAPES_V2) -> None:
        self.shape_version = shape_version
        self.n = 0
        self._sessions: List[int] = []
        self._nests: List[_NestRec] = []
        self._open: Dict[int, _NestRec] = {}                 # session -> the nest open in it (looked up, never iterated)
        self._by_topic: Dict[str, _NestRec] = {}             # looked up, never iterated
        self._crosses: Dict[Tuple[str, str], _CrossRec] = {}  # looked up, never iterated
        self._cross_order: List[Tuple[str, str]] = []
        self._clauses: List[ClauseRec] = []
        self._f0: List[F0Entry] = []
        self._marks: Dict[int, Mark] = {}                    # looked up, never iterated
        self._seq = 0
        self._ver = 0
        self._cache: Optional[Tuple[int, "MemIndex"]] = None
        self._exch: Dict[str, ms.Exchange] = {}

    # -- declarations and marks --------------------------------------------------------------------------------------
    def declare(self, session: int, at: int, topic: str) -> dict:
        head = topic_head(topic)
        if head is None:
            raise ValueError("a topic needs a word unit")
        nr = self._by_topic.get(topic)
        reopened = nr is not None
        if nr is None:
            nr = _NestRec("N%d" % (len(self._nests) + 1), topic, head)
            self._nests.append(nr)
            self._by_topic[topic] = nr
        nr.declared.append((session, at))
        self._open[session] = nr
        self._ver += 1
        return {"id": nr.id, "topic": topic, "centre": head.centre, "arms": [list(a) for a in _flatten(head.arms)], "prefix": head.prefix, "reopened": reopened}

    def supersede(self, sid: int, by: int, reason: str, session: int) -> None:
        self._marks[sid] = Mark(MARK_SUPERSEDED, by, reason, session)
        self._ver += 1

    # -- one sentence -----------------------------------------------------------------------------------------------
    def _exchange(self, text: str) -> ms.Exchange:
        e = self._exch.get(text)
        if e is None:
            e = self._exch[text] = ms.exchange(text, self.shape_version)
        return e

    def open_nest_id(self, session: int) -> Optional[str]:
        nr = self._open.get(session)
        return None if nr is None else nr.id

    def add_row(self, sid: int, row: dict, corpus_before: Any) -> Tuple[ClauseRec, ...]:
        """Place the sentence `sid` (the next one).  `corpus_before` = the memory corpus of the sentences before it (C_<sid).  -> the clause records it made."""
        if sid != self.n:
            raise ValueError("sentences are added in order: expected %d, got %d" % (self.n, sid))
        p = parse_source(row["source"])
        if p is None:
            raise ValueError("not a memory row")
        session = p[1]
        turn = row.get("turn")
        self.n += 1
        self._sessions.append(session)
        self._ver += 1
        ex = self._exchange(row["sent"])
        if row.get("unshaped") is True:                       # the F0 tank: in H, searchable as text, no cross
            self._f0.append(F0Entry(sid, session, turn, row["sent"], ex.shapes(), tuple(c.reason or "" for c in ex.clauses if c.shape == "F0")))
            return ()
        nr = self._open.get(session)
        open_id = None if nr is None else nr.id
        out: List[ClauseRec] = []
        for k, c in enumerate(ex.clauses):
            out.append(self._place(sid, k, session, turn, c, nr, open_id, corpus_before))
        self._clauses.extend(out)
        return tuple(out)

    def _place(self, sid: int, k: int, session: int, turn: Optional[str], c: ms.Clause, nr: Optional[_NestRec], open_id: Optional[str], corpus: Any) -> ClauseRec:
        if c.shape == "F0":
            return ClauseRec(sid, k, session, turn, "F0", None, None, c.text, None, None, open_id, (), None, None, tuple(a.text for a in c.adverbial), c.reason)
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
        head = c.centre_units[-1] if c.centre_units else (c.centre or "")
        ch = None if c.change is None else _change_rec(c.change)
        surface = c.surface if c.surface is not None else (c.centre or "")
        cr.occ.append(Prov(sid, turn, session, origin_of(corpus, c.centre_units), surface, k))
        path = _flatten(arms)

        def rec(slot: str, phrase: str, units: Tuple[str, ...], centre_head: str, sub: Sequence[ms.Arm], v: Optional[str], nid: Optional[str], change: Optional[ChangeRec], p: Path) -> _Rec:
            """One seat (and, below it, the seats of its own arms: the chain).  `p` = its path: an arm seat's ancestors, a value seat's position."""
            self._seq += 1
            seat_head = units[-1] if units else phrase
            r = _Rec(slot=slot, phrase=phrase, units=tuple(units), sid=sid, k=k, seq=self._seq, turn=turn, session=session, origin=origin_of(corpus, units),
                     key=seat_key(corpus, slot, centre_head, seat_head), path=p, children=[], via=v, nest=nid, change=change, surface=phrase)
            for a in sub:
                r.children.append((a.particle, rec(a.particle, a.seat.text, a.seat.units, seat_head, a.arms, v, nid, None, p + ((slot, phrase),))))
            return r

        for a in arms:
            is_nest = via == NEST_VIA and a.particle == NEST_ARM
            cr.recs.append(rec(a.particle, a.seat.text, a.seat.units, head, a.arms, via if is_nest else None, nest_id if is_nest else None, None, ()))
        if c.value is not None:
            cr.recs.append(rec(VALUE, c.value.text, c.value.units, head, (), None, None, ch, path))
        if c.quantity is not None:
            cr.recs.append(rec("quantity", c.quantity.text, c.quantity.units, head, (), None, None, None, ()))
        if c.object_bare is not None:
            cr.recs.append(rec("object_bare", c.object_bare.text, c.object_bare.units, head, (), None, None, None, ()))
        return ClauseRec(sid, k, session, turn, c.shape, tank, c.centre, c.text, via, nest_id, open_id, path, None if c.value is None else c.value.text, ch,
                         tuple(a.text for a in c.adverbial), None)

    # -- the derived index -------------------------------------------------------------------------------------------
    def index(self) -> "MemIndex":
        if self._cache is not None and self._cache[0] == self._ver:
            return self._cache[1]
        idx = self._finish()
        self._cache = (self._ver, idx)
        return idx

    def _seat_view(self, r: _Rec, rank: int, ring: int) -> Seat:
        m = self._marks.get(r.sid)
        kids = tuple((p, self._seat_view(ch, 0, 1)) for p, ch in r.children)
        return Seat(r.slot, r.phrase, r.units, Prov(r.sid, r.turn, r.session, r.origin, r.surface, r.k), r.key, rank, ring, r.path, kids, r.via, r.nest, r.change,
                    () if m is None else (m,))

    def _finish(self) -> "MemIndex":
        crosses: List[Cross] = []
        for key in self._cross_order:
            cr = self._crosses[key]
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
            crosses.append(Cross(cr.tank, cr.centre, cr.centre_units, 1 + longest, tuple(slots), occ))
        nests: List[Nest] = []
        for nr in self._nests:
            apx = tuple(ph for _, ph in _flatten(nr.head.arms))
            members: List[Member] = []
            under: List[Tuple[int, int, str, Optional[str]]] = []
            for c in self._clauses:
                kind: Optional[str] = None
                if c.tank is not None:
                    if c.via == NEST_VIA and c.nest == nr.id:
                        kind = "completed"
                    elif c.centre == nr.head.centre:
                        kind = "centre"
                    elif any(p == "の" and ph == nr.head.centre for p, ph in c.path):
                        kind = "path"
                if kind is not None:
                    have = [ph for _, ph in c.path] + [c.centre or ""]
                    members.append(Member(c.sid, c.k, c.tank or "", c.centre or "", kind, kind == "completed" or all(a in have for a in apx)))
                elif c.open_nest == nr.id:
                    under.append((c.sid, c.k, c.shape, c.centre))
            nests.append(Nest(nr.id, nr.topic, nr.head.centre, nr.head.centre_units, _flatten(nr.head.arms), nr.head.prefix, tuple(nr.declared), tuple(members), tuple(under)))
        return MemIndex(self.shape_version, self.n, tuple(self._sessions), tuple(crosses), tuple(self._f0), tuple(nests), tuple(self._clauses), dict(self._marks))


# ------------------------------------------------------------------------------------------------------------
# the index
# ------------------------------------------------------------------------------------------------------------
class MemIndex:
    """The derived index: tanks, nests, clauses, the slide order.  Immutable after construction; `index_sha` is the sha256 of its canonical serialisation."""

    def __init__(self, shape_version: str, n: int, sessions: Tuple[int, ...], crosses: Tuple[Cross, ...], f0: Tuple[F0Entry, ...], nests: Tuple[Nest, ...],
                 clauses: Tuple[ClauseRec, ...], marks: Dict[int, Mark]) -> None:
        self.shape_version, self.n, self.sessions = shape_version, n, sessions
        self.crosses, self.f0, self.nests, self.clauses = crosses, f0, nests, clauses
        self._marks = marks                                  # looked up only
        self._by_key: Dict[Tuple[str, str], Cross] = {(c.tank, c.centre): c for c in crosses}
        self.edges: Tuple[Tuple[int, int, int], ...] = tuple((i, i + 1, 1 if sessions[i] != sessions[i + 1] else 0) for i in range(n - 1))
        self._hist: Dict[Position, Tuple[Entry, ...]] = {}
        self.positions: Tuple[Position, ...] = self._positions()
        self._sha: Optional[str] = None

    # -- M2 queries -------------------------------------------------------------------------------------------------
    def tank(self, tank: str) -> Tuple[Cross, ...]:
        return tuple(c for c in self.crosses if c.tank == tank)

    def cross(self, tank: str, centre: str) -> Optional[Cross]:
        return self._by_key.get((tank, centre))

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

    # -- M4 queries -------------------------------------------------------------------------------------------------
    def _positions(self) -> Tuple[Position, ...]:
        order: List[Position] = []
        groups: List[List[Seat]] = []
        where: Dict[Position, int] = {}
        for c in self.crosses:
            for s in c.seats_of(VALUE):
                pos = (c.tank, c.centre, s.path)
                i = where.get(pos)
                if i is None:
                    where[pos] = len(order)
                    order.append(pos)
                    groups.append([])
                    i = len(order) - 1
                groups[i].append(s)
        for seats in groups:
            seats.sort(key=lambda s: (s.prov.sid, s.prov.clause))
        ranked = sorted(range(len(order)), key=lambda i: (groups[i][0].prov.sid, groups[i][0].prov.clause, order[i][0], order[i][1]))      # positions in the order they first got a value
        order, groups = [order[i] for i in ranked], [groups[i] for i in ranked]
        for pos, seats in zip(order, groups):
            ents: List[Entry] = []
            for j, s in enumerate(seats):
                superseded_here = any(self._marks.get(e.sid) is not None and self._marks[e.sid].by == s.prov.sid for e in ents)
                if j == 0:
                    kind = "first"
                elif s.change is not None or superseded_here:
                    kind = "update"
                else:
                    kind = "other"
                om: Optional[bool] = None
                if s.change is not None and s.change.old is not None and j > 0:
                    om = s.change.old == ents[-1].value
                ents.append(Entry(s.phrase, s.prov.sid, s.prov.clause, s.prov.session, s.prov.turn, kind, s.change, om, s.marks))
            self._hist[pos] = tuple(ents)
        return tuple(order)

    def history(self, position: Any) -> List[Tuple[str, int, str]]:
        """[(value, sid, kind)] of a position (tank, centre, path) in slide order; kind = first | update | other.  An unknown position: []."""
        return [(e.value, e.sid, e.kind) for e in self.history_full(position)]

    def history_full(self, position: Any) -> Tuple[Entry, ...]:
        return self._hist.get(_position(position), ())

    # -- numbers ----------------------------------------------------------------------------------------------------
    def stats(self) -> dict:
        out: Dict[str, Any] = {}
        for t in TANKS:
            cs = self.tank(t)
            out[t] = {"crosses": len(cs), "seats": sum(c.n_seats() for c in cs), "max_L": max([c.L for c in cs], default=0)}
        out[F0_TANK] = {"sentences": len(self.f0)}
        out["nests"] = len(self.nests)
        out["positions"] = len(self.positions)
        return out

    # -- serialisation ----------------------------------------------------------------------------------------------
    def to_obj(self) -> dict:
        sess: List[List[int]] = []
        for i, s in enumerate(self.sessions):
            if not sess or sess[-1][0] != s:
                sess.append([s, i, i])
            else:
                sess[-1][2] = i
        return {"v": CROSS_VERSION, "shape": self.shape_version, "n": self.n, "sessions": sess,
                "tanks": [[t, [c.to_obj() for c in self.tank(t)]] for t in TANKS], "f0": [e.to_obj() for e in self.f0], "nests": [n.to_obj() for n in self.nests],
                "clauses": [c.to_obj() for c in self.clauses], "edges": [list(e) for e in self.edges],
                "positions": [[t, c, [list(p) for p in path], [e.to_obj() for e in self._hist[(t, c, path)]]] for t, c, path in self.positions]}

    @property
    def index_sha(self) -> str:
        if self._sha is None:
            self._sha = sha256_text(canonical(self.to_obj()))
        return self._sha

    def render(self, cross: Cross) -> str:
        return render_cross(cross)


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
# the pure function of H
# ------------------------------------------------------------------------------------------------------------
def build_index(rows: Sequence[dict], decls: Sequence[dict] = (), superseded: Optional[Dict[int, dict]] = None, shape_version: str = ms.SHAPES_V2) -> MemIndex:
    """The index of the memory rows `rows` (each {sent, source, kind?, turn?, unshaped?}), the topic declarations `decls` ([{session, at, topic}]: `at` = how many sentences H held when it was declared) and the
    supersede marks `superseded` ({sid: {by, reason, session}}).  Builds the memory corpus of every prefix itself (Corpus, never Corpus.load)."""
    b = IndexBuilder(shape_version)
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
