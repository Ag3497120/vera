"""C1 of the line-3 "carry" build (docs/LINE3_CARRY_DESIGN.md, plan 2): types, ledger, local space.

Scope of this module (ticket C1 only): the data types of the tower, the canonical-JSON order ledger
(design 3.7) and the LOCAL SPACE of one unit (design 3.5).  Nothing here accepts, closes, carries or
reads: C2 (black acceptance / closing, OP-2, OP-3), C3 (tower, copy, activation, OP-1) and the later
tickets add behaviour on top of the extension points named "C2 hook" / "C3 hook" below.  Nothing in
placement.py, cycle.py, readout.py or matryoshka.py is changed; `LocalSpace.to_tier()` produces a
`TierSpace` so that placement's `Weights` (the I-04 key) can be run on a local space unchanged.

Binding decisions used (owner's answers: ops/decisions/2026-10-06_line3_faithful_build.md):
  C-1 / C-2  plan 2: the compressed pack of a closed unit is copied to the next unit.
  OP-1 (a)   the copy (carry) is a set of packs that stay ASLEEP; a pack seats only when a new
             occurrence of one of its words arrives.  Here: `Element.origin` = "new" | "inherited";
             activation itself is C3.
  OP-2 (b)   a black closes only at sentence boundaries (C2).  Here: an occurrence belongs to one
             unit's scope; a sentence may be split across scopes (positions stay global).
  OP-3 (a)   unstable = no settled class within the budget (C2).  Here: the ledger records the
             instability choice in its header.
  Condition 1 (provenance) / condition 2 (an inherited element is NOT counted again as evidence) /
  condition 3 (the stream order is fixed and recorded in the ledger).

Local choices (design numbers where the design already numbered them; new ones from L-322):
  L-301 ids are labels only ("U{k}:{j}", "P{k+1}:{j}"); they never decide a winner.
  L-302 an occurrence = the FIRST position of a unit in a sentence (`occurrences_of`).
  L-311 equal positions are compared strictly: p(x,y) counts neither side.
  L-319 ledger = JSONL of canonical JSON (sorted keys, minimal separators, UTF-8, no floats).
  L-322 An element is (id, kind, vocab, origin).  A word is the element with vocab = {itself}; a pack
        is an element whose vocab is a set of words.  One rule serves both (design 3.5): an element is
        in a sentence iff a scope occurrence of that sentence has a unit in the element's vocab; its
        position is the smallest such position.
  L-323 The local sentences are the sids that have an occurrence in the scope, numbered 0.. in the
        order of their first occurrence in the scope stream (the recorded stream order).  `sids`
        maps a local index back to the global sid.
  L-324 An occurrence (sid, pos, unit) whose (sid, unit) is already in the scope raises ValueError
        (the caller applies L-302; nothing is skipped silently).  pos must be an int >= 0.
  L-325 Element ids are unique, vocabs are non-empty, and a pack id must not equal a word surface
        that occurs in the scope or in another element's vocab (ValueError, no silent shadowing).
  L-326 An element that no scope occurrence touches is allowed (n = 0, no sentence).
  L-327 N_U = 0 (empty scope): r0 and E_Q are 0 (no sentence, no evidence; same idea as L-53).
  L-328 Within one local sentence the element list is ordered by (position, id); that is a LISTING
        label.  No count uses it: counts use the exact first positions.
  L-329 `LocalSpace.to_bytes()` = canonical JSON of the scope (stream order), the elements (sorted
        by id, a label), N, n, r0 (as "a/b"), and n(x,y), p(x,y) for every ordered pair.  The
        incremental space and the from-scratch space must give identical bytes (I-1).
  L-330 `with_occurrences` / `with_elements` return a NEW immutable LocalSpace (like L-41); an
        earlier object is never changed.
  L-331 Ledger events are numbered seq = 1, 2, ... without gaps.  The accepted event kinds are the
        design's (admit, rollback, close, pack, open, activate, carry) plus `split` (design 4.2) and
        `activation_deferred` (design 4.3 L-308).  Unknown kind / unknown field raises ValueError.
  L-332 `Ledger.from_bytes` accepts only bytes that are exactly what `to_bytes` would write
        (canonical), so a hand-edited or re-ordered file is rejected, not normalised.
  L-333 `order_sha256(sids)` = sha256 of the canonical JSON list of the sids in stream order.
  L-334 `LocalSpace.to_tier()` gives `LocalTier`, a TierSpace subclass over local sentence indices
        (strict first-position p_pair, r0 = 0 when N = 0 as L-327), so placement's `Weights` (the
        I-04 key) runs on a local space; placement.py is not modified.
  L-335 Ledger values are dict / list / str / int / bool / None only; floats and Fractions raise.
  L-336 `pack()` has no default origin: the caller states "new" (a child pack in its parent unit)
        or "inherited" (a woken carry), so a pack is never marked by a default (design 3.2).

C2 (black unit acceptance and closing; new local choices from L-350; docs/LINE3_LOCAL_DECISIONS.md "C2"):
  L-350 `Black` = one open unit as an immutable value (local space, settled class, L, budget).  `admit`
        returns a NEW Black or raises `Collapse`; a failed admission therefore changes nothing and the
        restore point is simply the earlier value (N-05).  The stream driver `BlackStream` holds the
        mutable parts (open black, ledger, closed blacks).
  L-351 The first element of an empty black, and any black that holds exactly one element after the
        admission, is placed WITHOUT search (a one-element cross is trivially a fixed point, centre
        non-empty L-77) and is never charged to the budget.  This is the progress guarantee L-308.
  L-352 One `_Work` per admission, shared by the re-settle (L-71) and the insertion (L-64) (L-306); the
        ledger records its two counters (states, moves).
  L-353 An occurrence of a word that already sits in the black is an admission too: the scope grows, the
        weights change, the class is re-settled (design 3.6 step 2).  (C0 skipped it, so its closed
        classes were not always fixed points for the final scope.)
  L-354 A `backup` event is written at the start of every sentence (the stable boundary the black can go
        back to, owner's T8b answer); every collapse writes one `rollback` event whose `to` is the seq of
        the restore point (the sentence's `backup`, or, for a split, the last `admit`); seq numbers every
        event (owner after C1).  New field `to`; new kind `backup`.
  L-355 Collapse on a sentence whose black held earlier sentences: restore the sentence boundary, close,
        pack, open, replay the WHOLE sentence into the new black (OP-2 b).  Collapse inside an empty-at-
        sentence-start black: `split` event, restore the last stable state, close from it, continue the
        sentence in the new black from the word that did not fit.
  L-356 Pack vocab = the union of the vocabs of the elements that are NEW in the black when it closes,
        frozen at that moment (owner after C1); inherited elements add no words (L-312).
  L-357 First group of two or more elements into an empty black (C3 carry hook): each element in turn is
        the centre (L-304), the rest is inserted order-free, the results are pooled and settled together.
        If that collapses and some of the group is an activation, the activation is deferred
        (`activation_deferred` event, L-308) and the occurrence is admitted alone.
  L-358 An admission that fails in a black that holds no element cannot happen (L-351); if it ever does,
        RuntimeError, never a silent skip.  A sentence without any unit writes no event.
  L-359 The time of every SUCCESSFUL admission (by the caller's `clock`; c2.py passes CPU time) is kept in
        `BlackStream.event_secs` (admit seq, seconds) OUTSIDE the ledger, so the ledger stays byte-identical
        across runs.  A collapsed attempt has no admit seq and its time is not in `event_secs`.
  L-360 `stream_header` builds the ledger header (admission = OP-2 b, instability = OP-3 a); a custom
        budget is written as "max_class=..,max_states=..,max_moves=..".

C3 (the tower: carry-up, copying, waking; new local choices from L-370; docs/LINE3_LOCAL_DECISIONS.md "C3"):
  L-370 `CarryTower(BlackStream)` adds levels k >= 1.  A level-k unit is a `Black` of level k fed one CHILD
        PACK at a time (the item); its scope = the own_occ of its new children in arrival order; the
        restore point is the state after the previous item.  Same budget at every level (L-305).
  L-371 Frontier F(k) = the NEW packs of the open units of levels > k (level ascending, arrival order inside
        a unit).  When a unit opens (after the carry-up that its own closing caused) it gets a copy of
        F(k): a tuple of immutable `Pack` objects stored under the unit id and never changed (L-309).
        # OP-1 (a): all levels are copied.
  L-372 Dormant = carry minus the ids seated in the black: DERIVED from the black's elements, no mutable
        state, so a rollback needs no repair.  An item wakes a carried pack iff one of the item's scope
        units (an occurrence's unit at level 0; the units of the child pack's own_occ at level k) is in the
        carried pack's FROZEN vocab.  Nothing else wakes a pack.  # OP-1 (a), condition 2
  L-373 Event order: close, pack, open (new unit), [carry-up of the pack, recursively], carry (group = the
        copied pack ids, possibly empty; exactly one per `open`, before the unit's first admit), then the
        admit of the item.  A level-k admit has item = child pack id, group = [pack] + woken ids,
        activated = woken ids; rollback / activation_deferred likewise.  There is no separate `activate`
        event (the woken ids are in `admit.activated`).
  L-374 The first unit of a new level is created when the level below closes a unit; its carry is empty
        (F of the top level is empty).
  L-375 `Pack` gets provenance fields with defaults: `children` (ids of its new child packs; () at level 1),
        `inherited` (woken carried packs seated when it closed), `carry` (ids copied at its unit's opening).
        vocab = union of the vocab of the NEW children = the units of own_occ (L-356 at every level).
  L-376 Test-only injection `inject(level, unit, item) -> reason | None` (constructor argument): a reason
        string forces a collapse of a NON-EMPTY black before the real admission (an empty black always
        accepts its first element, L-351); the reason is written as the ledger's budget_reason and must start
        with "injected" (ValueError otherwise), so an injected ledger is never taken for a budget one.  Default
        none; used to fix the collapse points of the design 4.5 example instead of the budget.
  L-377 `replay_ledger(ledger)` rebuilds every unit (scope, new elements, woken, carry, status, pack) from
        the ledger alone: a rollback undoes the unit's admits with seq greater than its `to`.
        `ledger_mismatches(tower)` compares it with the tower (O-2, net of rollbacks), and each pack's vocab
        with its `pack` event and with the units of its unit's replayed scope.
  L-378 Cache key (L-320): `check_cache_key(header, ...)` raises ValueError unless tier, order_sha256,
        build_level and (when given) data_sha256 agree; `replay_tower` rebuilds and compares bytes (O-1, O-3).
  L-379 `CarryTower.to_bytes()` = canonical JSON of every unit (carry ids, elements with origin, scope,
        class, L, local-space sha) and every pack plus the ledger sha: the byte string O-1 compares.
  L-380 A deferred activation (L-357 / L-308) at a level >= 1 behaves as at level 0.
  L-381 `ordered_sids(sids, kind, seed)`: file (as given) / reverse / shuffle (random.Random(seed), which does
        not depend on the hash seed); the header records kind and seed (condition 3).
  L-382 The end of the stream closes nothing (L-310): every level keeps its open unit.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import placement as pl
from verantyx.line3.space import TierSpace

LEDGER_FORMAT = "line3.carry.ledger.v1"                       # design 3.7
ORIGIN_NEW, ORIGIN_INHERITED = "new", "inherited"             # design 3.2 (origin of an element)
ORIGINS: Tuple[str, ...] = (ORIGIN_NEW, ORIGIN_INHERITED)
STATUS_OPEN, STATUS_CLOSED = "open", "closed"                 # design 3.1 (C2/C3 hook: unit status)
ORDER_KINDS: Tuple[str, ...] = ("file", "shuffle", "reverse")  # design 3.7 header.order.kind
EVENT_KINDS: Tuple[str, ...] = ("admit", "rollback", "close", "pack", "open", "activate", "carry",
                                "split", "activation_deferred", "backup")   # L-331, L-354 (backup)
EVENT_FIELDS: Tuple[str, ...] = ("seq", "kind", "level", "unit", "item", "occ", "group", "activated",
                                 "class_size", "L", "stop", "budget_reason", "work", "to")   # design 3.7; "to" = L-354
HEADER_FIELDS: Tuple[str, ...] = ("format", "data_sha256", "tier", "unit_filter", "order", "order_sha256",
                                  "build_level", "admission", "copy", "instability", "code_commit")


# --------------------------------------------------------------------------
# canonical JSON (L-319)
# --------------------------------------------------------------------------
def _plain(x, path: str = "$"):                                # L-335
    """Copy of `x` made of dict / list / str / int / bool / None only.  Floats and anything else
    raise (no float anywhere in a ledger; exact values are written as strings)."""
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float):
        raise ValueError("float at %s: ledgers carry no floats" % path)
    if isinstance(x, Fraction):
        raise ValueError("Fraction at %s: write it as a string" % path)
    if isinstance(x, (list, tuple)):
        return [_plain(v, "%s[%d]" % (path, i)) for i, v in enumerate(x)]
    if isinstance(x, Mapping):
        out = {}
        for k, v in x.items():
            if not isinstance(k, str):
                raise ValueError("non-string key at %s" % path)
            out[k] = _plain(v, "%s.%s" % (path, k))
        return out
    raise ValueError("unsupported value %r at %s" % (type(x).__name__, path))


def canonical_json(obj) -> bytes:                              # L-319
    return json.dumps(_plain(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def order_sha256(sids: Iterable[int]) -> str:                  # L-333
    return hashlib.sha256(canonical_json(list(sids))).hexdigest()


# --------------------------------------------------------------------------
# ledger (condition 3, design 3.7)
# --------------------------------------------------------------------------
def _check_header(h: Mapping) -> dict:
    h = _plain(h)
    if not isinstance(h, dict):
        raise ValueError("header must be an object")
    if h.get("format") != LEDGER_FORMAT:
        raise ValueError("header.format must be %r" % LEDGER_FORMAT)
    miss = [k for k in HEADER_FIELDS if k not in h]
    extra = [k for k in h if k not in HEADER_FIELDS and k != "pack_overflow"]       # L-401: optional, only "defer"
    if h.get("pack_overflow", "defer") != "defer":
        raise ValueError("header.pack_overflow is written only for 'defer'")
    if miss or extra:
        raise ValueError("header fields: missing %s, unknown %s" % (miss, extra))
    o = h["order"]
    if not isinstance(o, dict) or set(o) != {"kind", "seed"} or o["kind"] not in ORDER_KINDS:
        raise ValueError("header.order must be {kind in %s, seed}" % (ORDER_KINDS,))
    if o["seed"] is not None and (isinstance(o["seed"], bool) or not isinstance(o["seed"], int)):
        raise ValueError("header.order.seed must be an int or null")
    return h


def _check_event(e: Mapping, expect_seq: int) -> dict:
    e = _plain(e)
    if not isinstance(e, dict):
        raise ValueError("event must be an object")
    extra = [k for k in e if k not in EVENT_FIELDS]
    if extra:
        raise ValueError("unknown event fields %s" % extra)
    if e.get("kind") not in EVENT_KINDS:
        raise ValueError("unknown event kind %r" % (e.get("kind"),))
    if e.get("seq") != expect_seq or isinstance(e.get("seq"), bool):
        raise ValueError("seq must be %d (no gaps, L-331)" % expect_seq)
    if "occ" in e:
        o = e["occ"]
        if not (isinstance(o, list) and len(o) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in o)):
            raise ValueError("occ must be [sid, pos]")
    return e


class Ledger:
    """Append-only order ledger.  Lines are stored as canonical bytes, so a line can never change
    after it was appended and a rebuild is compared byte for byte (I-1, O-1).

    C2 / C3 hook: the build appends events with `append(kind, **fields)`; replaying a ledger into
    scopes and elements (O-2) is a later ticket and only needs `events()`."""

    def __init__(self, header: Mapping) -> None:
        self._header = canonical_json(_check_header(header))
        self._lines: List[bytes] = []

    @property
    def header(self) -> dict:
        return json.loads(self._header.decode("utf-8"))

    def __len__(self) -> int:
        return len(self._lines)

    def append(self, kind: str, **fields) -> int:
        """Add one event; returns its seq.  Raises ValueError on an unknown kind / field / float."""
        seq = len(self._lines) + 1
        e = _check_event(dict(fields, kind=kind, seq=seq), seq)
        self._lines.append(canonical_json(e))
        return seq

    def events(self) -> Tuple[dict, ...]:
        return tuple(json.loads(l.decode("utf-8")) for l in self._lines)

    def to_bytes(self) -> bytes:
        return b"".join(l + b"\n" for l in [self._header] + self._lines)

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ledger":
        """L-332: only canonical bytes are accepted."""
        if not data.endswith(b"\n"):
            raise ValueError("ledger must end with a newline")
        lines = data[:-1].split(b"\n")
        led = cls(json.loads(lines[0].decode("utf-8")))
        for raw in lines[1:]:
            e = json.loads(raw.decode("utf-8"))
            if e.get("seq") != len(led) + 1:
                raise ValueError("seq must be %d (no gaps, L-331)" % (len(led) + 1))
            led.append(e.pop("kind", None), **{k: v for k, v in e.items() if k != "seq"})
        if led.to_bytes() != data:
            raise ValueError("ledger bytes are not canonical (L-332)")
        return led


# --------------------------------------------------------------------------
# types (design 3.1 - 3.3; fields that C2 / C3 fill are declared here, not used yet)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Occ:
    """One occurrence (design 3.1): a unit at a position of a sentence.  `pos` is the position in the
    sentence's unit list (global, so a sentence split over two scopes keeps comparable positions)."""
    sid: int
    pos: int
    unit: str

    def __post_init__(self) -> None:
        for v in (self.sid, self.pos):
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError("sid and pos must be ints >= 0 (L-324)")
        if not isinstance(self.unit, str) or not self.unit:
            raise ValueError("unit must be a non-empty string")


@dataclass(frozen=True)
class Element:
    """A seat-able thing (L-322): a word (vocab = {word}) or a pack (vocab = words of its scope).
    `origin` = "new" or "inherited" (design 3.2); an inherited element is not counted from its own
    past, only through the scope of the unit it sits in (condition 2)."""
    id: str
    vocab: frozenset
    kind: str = "word"                  # "word" | "pack"
    origin: str = ORIGIN_NEW

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("element id must be a non-empty string")
        object.__setattr__(self, "vocab", frozenset(self.vocab))
        if not self.vocab:
            raise ValueError("element %r has an empty vocab (L-325)" % self.id)
        if self.kind not in ("word", "pack"):
            raise ValueError("element kind: word | pack")
        if self.origin not in ORIGINS:
            raise ValueError("element origin: %s" % " | ".join(ORIGINS))
        if self.kind == "word" and self.vocab != frozenset((self.id,)):
            raise ValueError("a word element has vocab == {itself}")


def word(u: str, origin: str = ORIGIN_NEW) -> Element:
    return Element(u, frozenset((u,)), "word", origin)


def pack(pid: str, vocab: Iterable[str], origin: str) -> Element:        # L-336: origin is explicit
    return Element(pid, frozenset(vocab), "pack", origin)


def occurrences_of(tier: TierSpace, sid: int) -> Tuple[Occ, ...]:
    """L-302: the occurrences of one sentence = each distinct unit at its FIRST position, in order."""
    out, seen = [], set()
    for pos, u in enumerate(tier.sentence_units[sid]):
        if u not in seen:
            seen.add(u)
            out.append(Occ(sid, pos, u))
    return tuple(out)


# --------------------------------------------------------------------------
# local space (design 3.5)
# --------------------------------------------------------------------------
def _frac(x: Fraction) -> str:
    return "%d/%d" % (x.numerator, x.denominator)


@dataclass(frozen=True)
class LocalSpace:
    """The only place where a unit's counts are made (design 3.5, conditions 1-2).  It is a function of
    (scope occurrences in stream order, elements) and of nothing else: no global space, no sentence
    outside the scope, no earlier unit.  Immutable (L-330)."""
    tier: str
    scope: Tuple[Occ, ...]                                   # stream order (condition 3)
    elements: Tuple[Element, ...]                            # arrival order
    sids: Tuple[int, ...]                                    # L-323: local index -> global sid
    word_first: Mapping[str, Mapping[int, int]] = field(compare=False, repr=False)      # word -> {local: min pos}
    first_pos: Mapping[str, Mapping[int, int]] = field(compare=False, repr=False)       # element id -> {local: pos}
    vocab_index: Mapping[str, Tuple[str, ...]] = field(compare=False, repr=False)       # word -> element ids

    # -- construction -------------------------------------------------------
    @staticmethod
    def empty(tier: str = "") -> "LocalSpace":
        return LocalSpace(tier, (), (), (), {}, {}, {})

    @staticmethod
    def build(scope: Iterable[Occ], elements: Iterable[Element], tier: str = "") -> "LocalSpace":
        """From scratch, straight from the definition (L-322): the reference for I-1."""
        scope, elements = tuple(scope), tuple(elements)
        _check_inputs(scope, elements, (), ())
        sids: List[int] = []
        local: Dict[int, int] = {}
        for o in scope:
            if o.sid not in local:
                local[o.sid] = len(sids)
                sids.append(o.sid)
        wf: Dict[str, Dict[int, int]] = {}
        for o in scope:
            d = wf.setdefault(o.unit, {})
            li = local[o.sid]
            d[li] = o.pos if li not in d else min(d[li], o.pos)
        fp: Dict[str, Dict[int, int]] = {}
        vi: Dict[str, List[str]] = {}
        for e in elements:
            d: Dict[int, int] = {}
            for w in e.vocab:
                vi.setdefault(w, []).append(e.id)
                for li, p in wf.get(w, {}).items():
                    d[li] = p if li not in d else min(d[li], p)
            fp[e.id] = d
        return LocalSpace(tier, scope, elements, tuple(sids), wf, fp, {w: tuple(v) for w, v in vi.items()})

    def with_occurrences(self, occs: Iterable[Occ]) -> "LocalSpace":
        """Incremental append of scope occurrences (L-330).  Old counts that the new occurrences do not
        touch are carried over unchanged; the result is byte-identical to `build` on the full input."""
        occs = tuple(occs)
        if not occs:
            return self
        _check_inputs(self.scope, self.elements, occs, ())
        sids = list(self.sids)
        local = {s: i for i, s in enumerate(sids)}
        wf = {w: dict(d) for w, d in self.word_first.items()}
        fp = {k: dict(d) for k, d in self.first_pos.items()}
        for o in occs:
            if o.sid not in local:
                local[o.sid] = len(sids)
                sids.append(o.sid)
            li = local[o.sid]
            d = wf.setdefault(o.unit, {})
            d[li] = o.pos if li not in d else min(d[li], o.pos)
            for eid in self.vocab_index.get(o.unit, ()):
                f = fp[eid]
                f[li] = o.pos if li not in f else min(f[li], o.pos)
        return LocalSpace(self.tier, self.scope + occs, self.elements, tuple(sids), wf, fp, self.vocab_index)

    def with_elements(self, elements: Iterable[Element]) -> "LocalSpace":
        """Incremental add of seat elements (e.g. an inherited pack woken by a new occurrence; C3 hook)."""
        elements = tuple(elements)
        if not elements:
            return self
        _check_inputs(self.scope, self.elements, (), elements)
        local = {s: i for i, s in enumerate(self.sids)}
        fp = dict(self.first_pos)
        vi = {w: list(v) for w, v in self.vocab_index.items()}
        for e in elements:
            d: Dict[int, int] = {}
            for w in e.vocab:
                vi.setdefault(w, []).append(e.id)
                for li, p in self.word_first.get(w, {}).items():
                    d[li] = p if li not in d else min(d[li], p)
            fp[e.id] = d
        return LocalSpace(self.tier, self.scope, self.elements + elements, self.sids, self.word_first, fp,
                          {w: tuple(v) for w, v in vi.items()})

    # -- counts (design 3.5; exact integers and Fractions) -------------------
    @property
    def N(self) -> int:
        return len(self.sids)

    def element(self, eid: str) -> Element:
        for e in self.elements:
            if e.id == eid:
                return e
        raise KeyError(eid)

    def n(self, x: str) -> int:
        return len(self.first_pos[x])

    def n_pair(self, x: str, y: str) -> int:
        """n_U(x,y); n_U(x,x) = n_U(x) (L-50 of the flat space)."""
        a, b = self.first_pos[x], self.first_pos[y]
        if len(a) > len(b):
            a, b = b, a
        return sum(1 for li in a if li in b)

    def p_pair(self, x: str, y: str) -> int:
        """p_U(x,y): sentences where x's first position is STRICTLY before y's (L-311).  Equal
        positions count for neither side."""
        a, b = self.first_pos[x], self.first_pos[y]
        return sum(1 for li, pa in a.items() if li in b and pa < b[li])

    def r0(self, x: str) -> Fraction:
        if self.N == 0:
            return Fraction(0)                                   # L-327
        return Fraction(self.n(x), self.N)

    def n_query(self, q: str, x: str) -> int:
        """n_U(q,x) for a question word q (not necessarily an element): local sentences that hold x
        and have a scope occurrence of q.  A q outside the scope has 0 (like L-52)."""
        wq = self.word_first.get(q)
        if not wq:
            return 0
        fx = self.first_pos[x]
        return sum(1 for li in wq if li in fx)

    def energy(self, x: str, query: Iterable[str] = ()) -> Fraction:
        """E_Q,U(x) = r0_U(x) + sum_q n_U(q,x)/N_U   (I-06, N-01).  The query is a set (L-51 of energy.py)."""
        if self.N == 0:
            return Fraction(0)                                   # L-327
        tot = self.n(x)
        for q in set(query):
            tot += self.n_query(q, x)
        return Fraction(tot, self.N)

    def sentence_elements(self, li: int) -> Tuple[str, ...]:
        """L-328: the elements in local sentence `li`, listed by (position, id); a listing only."""
        rows = [(f[li], eid) for eid, f in self.first_pos.items() if li in f]
        return tuple(eid for _, eid in sorted(rows))

    # -- bridges -------------------------------------------------------------
    def to_tier(self) -> "LocalTier":
        """A TierSpace over the local sentences so that placement.Weights (I-04 key) runs on it.
        C2 hook: the black's settling calls `placement` on this object."""
        post = {eid: tuple(sorted(f)) for eid, f in self.first_pos.items()}
        su = tuple(self.sentence_elements(li) for li in range(self.N))
        return LocalTier(self.tier, su, post, None, {k: dict(v) for k, v in self.first_pos.items()})

    def to_bytes(self) -> bytes:                                 # L-329
        ids = sorted(e.id for e in self.elements)               # a label order; nothing is decided by it
        doc = {
            "format": "line3.carry.localspace.v1",
            "tier": self.tier,
            "scope": [[o.sid, o.pos, o.unit] for o in self.scope],
            "sids": list(self.sids),
            "elements": [{"id": e.id, "kind": e.kind, "origin": e.origin, "vocab": sorted(e.vocab)}
                         for e in sorted(self.elements, key=lambda e: e.id)],
            "N": self.N,
            "n": {x: self.n(x) for x in ids},
            "r0": {x: _frac(self.r0(x)) for x in ids},
            "pairs": {x: {y: [self.n_pair(x, y), self.p_pair(x, y)] for y in ids} for x in ids},
        }
        return canonical_json(doc)

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()


@dataclass(frozen=True)
class LocalTier(TierSpace):                                       # L-334
    """TierSpace view of a LocalSpace: postings are over local sentence indices.  p_pair uses the exact
    first positions with a strict comparison (L-311), as matryoshka.BundleTier does."""
    first_pos: Mapping[str, Mapping[int, int]] = field(default_factory=dict, compare=False, repr=False)

    def p_pair(self, u: str, v: str) -> int:
        fu, fv = self.first_pos[u], self.first_pos[v]
        return sum(1 for li, pu in fu.items() if li in fv and pu < fv[li])

    def r0(self, u: str) -> Fraction:
        if self.N == 0:
            return Fraction(0)                                   # L-327 (same as LocalSpace.r0)
        return Fraction(len(self.postings[u]), self.N)


def _check_inputs(scope: Sequence[Occ], elements: Sequence[Element], new_occs: Sequence[Occ],
                  new_elems: Sequence[Element]) -> None:
    """L-324 / L-325 on (old + new).  Cheap: runs on every build / append."""
    seen = set((o.sid, o.unit) for o in scope)
    for o in new_occs:
        k = (o.sid, o.unit)
        if k in seen:
            raise ValueError("occurrence (sid=%d, unit=%r) already in the scope (L-324)" % k)
        seen.add(k)
    if not new_occs and not new_elems and len(seen) != len(scope):
        raise ValueError("duplicate (sid, unit) in the scope (L-324)")
    ids = set()
    for e in tuple(elements) + tuple(new_elems):
        if e.id in ids:
            raise ValueError("duplicate element id %r (L-325)" % e.id)
        ids.add(e.id)
    words = {u for _, u in seen}
    for e in tuple(elements) + tuple(new_elems):
        words.update(e.vocab)
    for e in tuple(elements) + tuple(new_elems):
        if e.kind == "pack" and e.id in words:
            raise ValueError("pack id %r equals a word surface (L-325)" % e.id)


# ==========================================================================
# C2: black unit acceptance and closing (design 3.6, 4.1, 4.2; OP-2 b, OP-3 a)
# ==========================================================================
# The only contact with placement's search is this adapter layer (`_settle`, `_insert_group`, `_Work`,
# `canon`, `extend`, `min_L`, `Weights`, `verify_class` are placement's; placement.py is not modified).
_NOCENTRE = (None,) * 6                                        # six empty arm seats at L = 1


class Collapse(Exception):
    """OP-3 (a): the black cannot settle to a tied class within the budget (L-72).  `reason` is the
    budget limit that was exceeded ("max_states" | "max_moves" | "max_class"); states / moves are the
    work counters at that moment."""

    def __init__(self, reason: str, states: int, moves: int) -> None:
        super().__init__(reason)
        self.reason, self.states, self.moves = reason, states, moves


def _injected(reason) -> str:
    """L-376: a test-only forced collapse must say so in the ledger (budget_reason starts with "injected"), so
    an injected ledger can never pass for a budget one (a budget reason is max_states / max_moves / max_class)."""
    if not isinstance(reason, str) or not reason.startswith("injected"):
        raise ValueError("an injected collapse reason must start with 'injected' (L-376), got %r" % (reason,))
    return reason


def _work_obj(states: int, moves: int) -> dict:
    return {"states": states, "moves": moves}


@dataclass(frozen=True)
class Black:                                                    # L-350
    """One open unit of level `level`: its local space, the settled class (`state`: canonical flats of
    element ids, the whole tied class, no twin quotient L-303), the arm length `L`."""
    unit: str
    level: int
    space: LocalSpace
    state: Tuple[pl.Flat, ...]
    L: int
    budget: pl.Budget

    @staticmethod
    def new(unit: str, tier: str, budget: pl.Budget, level: int = 0) -> "Black":
        return Black(unit, level, LocalSpace.empty(tier), (), 1, budget)

    @property
    def n_elements(self) -> int:
        return len(self.space.elements)

    @property
    def is_empty(self) -> bool:
        return not self.space.elements

    def admit(self, occs: Iterable[Occ], elements: Iterable[Element] = ()) -> Tuple["Black", dict]:
        """Design 3.6 steps 1-3 for one item: add the occurrences to the scope (step 1), re-settle the
        class under the new weights (step 2), insert the new elements as one group and settle (step 3).
        Returns (new Black, work) or raises `Collapse` (step 4).  Nothing is changed on failure (L-350)."""
        occs, elements = tuple(occs), tuple(elements)
        space = self.space.with_occurrences(occs).with_elements(elements)
        group = tuple(sorted(e.id for e in elements))           # a label order; the insert is order-free
        work = pl._Work(self.budget)
        try:
            state, L = self._settle_into(space, group, work)
        except pl._Over as e:
            raise Collapse(str(e.args[0]) if e.args else "budget", work.n, work.tested) from None
        return Black(self.unit, self.level, space, state, L, self.budget), _work_obj(work.n, work.tested)

    def _settle_into(self, space: LocalSpace, group: Tuple[str, ...], work) -> Tuple[Tuple[pl.Flat, ...], int]:
        size, total = self.n_elements, self.n_elements + len(group)
        if total == 0:
            raise ValueError("an admission must bring at least one element")
        if total == 1:                                           # L-351: trivially stable, no budget
            only = group[0] if group else space.elements[0].id
            return (pl.canon((only,) + _NOCENTRE, 1),), 1
        w = pl.Weights(space.to_tier())
        b = self.budget
        if size == 0:                                            # L-357 (L-304): first group, >= 2 elements
            L = pl.min_L(len(group))
            pool: Dict[pl.Flat, None] = {}
            for c in group:
                rest = tuple(g for g in group if g != c)
                base = pl.extend(pl.canon((c,) + _NOCENTRE, 1), 1, L)
                for f in pl._insert_group(w, [base], L, rest, work, b):
                    pool[f] = None
            return pl._settle(w, list(pool), L, work, b), L
        base = list(pl._settle(w, list(self.state), self.L, work, b))   # step 2 (L-71)
        L = self.L
        if group:                                                # step 3 (L-64): one group, order-free
            L3 = pl.min_L(total)
            if L3 > L:
                base = [pl.extend(x, L, L3) for x in base]
            base = list(pl._settle(w, pl._insert_group(w, base, L3, group, work, b), L3, work, b))
            L = L3
        return tuple(base), L

    def crosses(self):
        return tuple(pl.to_cross(f, self.L) for f in self.state)

    def verify(self) -> "pl.ClassReport":
        """Independent check (placement.verify_class: geometry's moves, not the search's code) that the
        settled class is one key, a fixed point at every member and closed under equal-key moves."""
        return pl.verify_class(self.space.to_tier(), self.crosses())


@dataclass(frozen=True)
class Pack:                                                     # design 3.3 (level k+1 element of a closed unit k)
    id: str
    unit: str                                                   # the unit it was made from (condition 1)
    level: int                                                  # level of the pack (= unit level + 1)
    own_occ: Tuple[Occ, ...]                                    # provenance: the scope of `unit`
    vocab: frozenset                                            # L-356: frozen at close time
    state: Tuple[pl.Flat, ...]
    L: int
    close_seq: int
    closed_by: str                                              # the budget reason that collapsed the black
    children: Tuple[str, ...] = ()                              # L-375: ids of the new child packs (level >= 2 packs)
    inherited: Tuple[str, ...] = ()                             # L-375: woken carried packs seated at close time
    carry: Tuple[str, ...] = ()                                 # L-375: ids copied when the unit opened

    def as_element(self, origin: str) -> Element:               # L-336: the caller states the origin
        return pack(self.id, self.vocab, origin)


@dataclass(frozen=True)
class ClosedBlack:
    black: Black
    pack: Pack
    close_seq: int
    pack_seq: int
    reason: str

    @property
    def unit(self) -> str:
        return self.black.unit

    def verify(self) -> "pl.ClassReport":
        return self.black.verify()


def stream_header(tier: str, sids: Sequence[int], budget: pl.Budget, *, data_sha256: Optional[str] = None,
                  unit_filter: Optional[str] = None, order_kind: str = "file", order_seed: Optional[int] = None,
                  code_commit: Optional[str] = None, copy: Optional[str] = None,
                  pack_overflow: str = "close") -> dict:   # L-360, L-401
    lv = pl.level_name(budget)
    hdr = {"format": LEDGER_FORMAT, "data_sha256": data_sha256, "tier": tier, "unit_filter": unit_filter,
            "order": {"kind": order_kind, "seed": order_seed}, "order_sha256": order_sha256(sids),
            "build_level": lv if lv is not None else "max_class=%d,max_states=%d,max_moves=%d" % (
                budget.max_class, budget.max_states, budget.max_moves),
            "admission": "OP-2(b): close only at sentence boundaries; a sentence that does not fit an empty black is split",
            "copy": copy if copy is not None else "OP-1(a): carried packs stay asleep (C3)",
            "instability": "OP-3(a): no tied class within the budget",
            "code_commit": code_commit}
    if pack_overflow != "close":                              # L-401: the default leaves the header bytes unchanged
        hdr["pack_overflow"] = pack_overflow
    return hdr


class BlackStream:
    """The stream feed of level 0 (design 4.2 `admit_sentence`).  Sentences are fed in the recorded
    order; the black accepts one occurrence at a time (a word); it closes only at sentence boundaries
    (OP-2 b) when an admission collapses (OP-3 a), after restoring the last stable state (N-05, owner's
    T8b answer).  C3 hooks: `wake(black, occ)` (elements to wake with an occurrence; default none) and
    `_after_close(closed)` (carry / carry-up; default nothing)."""

    def __init__(self, tier: str, budget: pl.Budget, ledger: Ledger,
                 wake=None, clock=None, inject=None, pack_overflow: str = "close") -> None:
        if pack_overflow not in PACK_OVERFLOW:
            raise ValueError("pack_overflow: %s" % " | ".join(PACK_OVERFLOW))
        self.tier, self.budget, self.ledger = tier, budget, ledger
        self.pack_overflow = pack_overflow                       # L-400
        self.wake = wake
        self.inject = inject                                     # L-376: test-only forced collapse
        self.clock = clock                                       # L-359: e.g. time.process_time
        self.event_secs: List[Tuple[int, float]] = []
        self.closed: List[ClosedBlack] = []
        self.split_sids: List[int] = []                          # a sid per `split` event (a sentence split twice appears twice)
        self._j = 0
        self.black = Black.new("U0:0", tier, budget)
        self._stable_seq = self.ledger.append("open", level=0, unit=self.black.unit, L=1, class_size=0)

    # -- one sentence ------------------------------------------------------
    def feed_sentence(self, sid: int, occs: Iterable[Occ]) -> None:
        occs = tuple(occs)
        if not occs:                                             # L-358
            return
        if any(o.sid != sid for o in occs):
            raise ValueError("every occurrence must belong to sentence %d" % sid)
        mark = self.black
        self._stable_seq = self.ledger.append("backup", level=0, unit=mark.unit, item=sid,
                                              class_size=len(mark.state), L=mark.L)
        mark_seq = self._stable_seq
        k, why = self._run(occs, 0)
        if k is not None and not mark.is_empty:                  # OP-2 (b): back to the sentence boundary, close
            self.black = mark
            self._stable_seq = mark_seq
            self.ledger.append("rollback", level=0, unit=mark.unit, occ=[occs[k].sid, occs[k].pos],
                               item=occs[k].unit, stop="budget", budget_reason=why[0], work=why[1], to=mark_seq,
                               class_size=len(mark.state), L=mark.L)
            self._close(why[0], occs[k])
            k, why = self._run(occs, 0)                          # the whole sentence into the new black
        while k is not None:                                     # does not fit an empty black: split here
            o = occs[k]
            if self.black.is_empty:
                raise RuntimeError("an empty black refused an element (L-308 violated)")   # L-358
            self.ledger.append("rollback", level=0, unit=self.black.unit, occ=[o.sid, o.pos], item=o.unit,
                               stop="budget", budget_reason=why[0], work=why[1], to=self._stable_seq,
                               class_size=len(self.black.state), L=self.black.L)
            self.ledger.append("split", level=0, unit=self.black.unit, occ=[o.sid, o.pos], item=o.unit,
                               budget_reason=why[0])
            self.split_sids.append(sid)
            self._close(why[0], o)
            k, why = self._run(occs, k)

    def feed_tier(self, tier: TierSpace, sids: Iterable[int]) -> None:
        for s in sids:
            self.feed_sentence(s, occurrences_of(tier, s))

    # -- one occurrence ----------------------------------------------------
    def _run(self, occs: Tuple[Occ, ...], start: int):
        """Admit occs[start:] one by one into the open black.  Returns (None, None) when all went in, or
        (index, (reason, work)) of the first occurrence that collapsed the black (nothing of it kept)."""
        for k in range(start, len(occs)):
            o = occs[k]
            known = {e.id for e in self.black.space.elements}
            new = [] if o.unit in known else [word(o.unit)]
            act = tuple(self.wake(self.black, o)) if self.wake is not None else ()
            t0 = self.clock() if self.clock else 0.0
            try:
                forced = False
                try:
                    inj = self.inject(0, self.black.unit, o) if (self.inject is not None and not self.black.is_empty) else None
                    if inj is not None:                          # L-376
                        forced = True
                        raise Collapse(_injected(inj), 0, 0)
                    nb, work = self.black.admit([o], new + list(act))
                except Collapse as c:
                    if not (act and (self.black.is_empty or (self.pack_overflow == "defer" and not forced))):   # L-401
                        raise
                    # L-308 / L-357: deferred activation; the occurrence alone is trivially stable
                    self.ledger.append("activation_deferred", level=0, unit=self.black.unit, occ=[o.sid, o.pos],
                                       item=o.unit, group=sorted(e.id for e in act), budget_reason=c.reason)
                    act = ()
                    nb, work = self.black.admit([o], new)
            except Collapse as c:
                return k, (c.reason, _work_obj(c.states, c.moves))
            self.black = nb
            self._stable_seq = self.ledger.append(
                "admit", level=0, unit=nb.unit, item=o.unit, occ=[o.sid, o.pos],
                group=sorted(e.id for e in new) + sorted(e.id for e in act),
                activated=sorted(e.id for e in act), class_size=len(nb.state), L=nb.L, stop="stable", work=work)
            if self.clock:
                self.event_secs.append((self._stable_seq, self.clock() - t0))
        return None, None

    # -- closing (design 4.2 close_and_carry, level 0 part) ----------------
    def _close(self, reason: str, occ: Occ) -> None:
        b = self.black
        vocab = frozenset(w for e in b.space.elements if e.origin == ORIGIN_NEW for w in e.vocab)   # L-356
        cseq = self.ledger.append("close", level=0, unit=b.unit, occ=[occ.sid, occ.pos], class_size=len(b.state),
                                  L=b.L, stop="budget", budget_reason=reason, to=self._stable_seq)
        inh = tuple(e.id for e in b.space.elements if e.origin == ORIGIN_INHERITED)
        pk = Pack("P1:%d" % self._j, b.unit, b.level + 1, b.space.scope, vocab, b.state, b.L, cseq, reason,
                  (), inh, self._carry_ids(b.unit))
        pseq = self.ledger.append("pack", level=1, unit=b.unit, item=pk.id, group=sorted(vocab),
                                  class_size=len(b.state), L=b.L)
        cb = ClosedBlack(b, pk, cseq, pseq, reason)
        self.closed.append(cb)
        self._j += 1
        self.black = Black.new("U0:%d" % self._j, self.tier, self.budget)
        self._stable_seq = self.ledger.append("open", level=0, unit=self.black.unit, L=1, class_size=0)
        self._after_close(cb)

    def _after_close(self, closed: ClosedBlack) -> None:
        """C3 hook: carry-up of the pack to level 1 and the carry copy into the new black.  Nothing in C2."""
        return None

    def _carry_ids(self, unit: str) -> Tuple[str, ...]:
        """C3 hook (L-375): the ids copied into `unit` when it opened.  Nothing in C2."""
        return ()


# ==========================================================================
# C3: the tower (design 3.4, 4.2; OP-1 a; conditions 1-3)
# ==========================================================================
PACK_OVERFLOW = ("close", "defer")                              # L-400
TOWER_COPY = ("OP-1(a): the frontier of all levels is copied; packs sleep and seat only when a new "
              "sentence contains a word of their vocab (frozen at copy time)")


def ordered_sids(sids: Sequence[int], kind: str = "file", seed: Optional[int] = None) -> List[int]:   # L-381
    sids = list(sids)
    if kind == "file":
        return sids
    if kind == "reverse":
        return sids[::-1]
    if kind == "shuffle":
        if seed is None:
            raise ValueError("shuffle needs a seed")
        random.Random(seed).shuffle(sids)
        return sids
    raise ValueError("order kind: %s" % " | ".join(ORDER_KINDS))


class _Upper:
    """A level k >= 1: the open unit, the closed ones, the next unit number, the restore point (seq)."""
    __slots__ = ("level", "black", "closed", "j", "stable_seq")

    def __init__(self, level: int, black: Black, stable_seq: int) -> None:
        self.level, self.black, self.closed, self.j, self.stable_seq = level, black, [], 0, stable_seq


class CarryTower(BlackStream):
    """The whole tower (design 4.2 `build`): level 0 is `BlackStream`; a closed unit's pack is admitted as one
    item into the open unit of the next level (carry-up, recursive); a unit that opens gets an immutable copy
    of the frontier (OP-1 a) whose packs wake only through new sentences (condition 2)."""

    def __init__(self, tier: str, budget: pl.Budget, ledger: Ledger, clock=None, inject=None,
                 pack_overflow: str = "close") -> None:
        self.carry: Dict[str, Tuple[Pack, ...]] = {}              # L-371: unit id -> copied packs (immutable)
        self.packs: Dict[str, Pack] = {}                          # pack id -> Pack (all levels)
        self.uppers: List[_Upper] = []                            # uppers[k-1] = level k
        self.upper_secs: List[Tuple[int, float]] = []             # (admit seq, seconds) of successful upper admits
        self.upper_attempt_secs: Dict[int, float] = {}            # level -> seconds of every attempt (also collapsed)
        super().__init__(tier, budget, ledger, wake=self._wake, clock=clock, inject=inject, pack_overflow=pack_overflow)
        self._new_carry(self.black)                               # U0:0 opens with an empty copy

    # -- frontier and copy (L-371) -------------------------------------------
    def frontier(self, k: int) -> Tuple[Pack, ...]:
        out: List[Pack] = []
        for st in self.uppers[k:]:                                # levels k+1 ..
            for e in st.black.space.elements:
                if e.origin == ORIGIN_NEW:
                    out.append(self.packs[e.id])
        return tuple(out)

    def _new_carry(self, black: Black) -> None:
        fr = self.frontier(black.level)
        self.carry[black.unit] = fr
        self.ledger.append("carry", level=black.level, unit=black.unit, group=[p.id for p in fr])

    def _carry_ids(self, unit: str) -> Tuple[str, ...]:
        return tuple(p.id for p in self.carry.get(unit, ()))

    # -- waking (L-372) -------------------------------------------------------
    def _woken(self, black: Black, units) -> List[Element]:
        seated = {e.id for e in black.space.elements}
        return [p.as_element(ORIGIN_INHERITED) for p in self.carry.get(black.unit, ())
                if p.id not in seated and any(u in p.vocab for u in units)]

    def _wake(self, black: Black, occ: Occ) -> List[Element]:       # BlackStream.wake hook (level 0)
        return self._woken(black, (occ.unit,))

    # -- level 0 closed: carry up, then copy to the new black ----------------
    def _after_close(self, closed: ClosedBlack) -> None:
        self.packs[closed.pack.id] = closed.pack
        self._carry_up(0, closed.pack)
        self._new_carry(self.black)

    def _carry_up(self, k: int, pk: Pack) -> None:
        lv = k + 1
        if len(self.uppers) < lv:                                  # L-374: a new top level
            b = Black.new("U%d:0" % lv, self.tier, self.budget, level=lv)
            seq = self.ledger.append("open", level=lv, unit=b.unit, L=1, class_size=0)
            self.uppers.append(_Upper(lv, b, seq))
            self._new_carry(b)
        self._admit_item(lv, pk)

    # -- one item into a level >= 1 unit (design 3.6, 4.2 `admit` / `close_and_carry`) ----
    def _admit_item(self, lv: int, pk: Pack) -> None:
        st = self.uppers[lv - 1]
        units = frozenset(o.unit for o in pk.own_occ)
        for _ in range(2):                                         # a collapse closes the unit; the new one accepts
            b = st.black
            act = self._woken(b, units)
            el = pk.as_element(ORIGIN_NEW)
            t0 = self.clock() if self.clock else 0.0
            forced = False
            try:
                try:
                    inj = self.inject(lv, b.unit, pk.id) if (self.inject is not None and not b.is_empty) else None
                    if inj is not None:                            # L-376
                        forced = True
                        raise Collapse(_injected(inj), 0, 0)
                    nb, work = b.admit(pk.own_occ, [el] + act)
                except Collapse as c:
                    if not (act and (b.is_empty or (self.pack_overflow == "defer" and not forced))):   # L-401
                        raise
                    self.ledger.append("activation_deferred", level=lv, unit=b.unit, item=pk.id,    # L-380
                                       group=sorted(e.id for e in act), budget_reason=c.reason)
                    act = []
                    nb, work = b.admit(pk.own_occ, [el])
            except Collapse as c:
                if self.clock:
                    self.upper_attempt_secs[lv] = self.upper_attempt_secs.get(lv, 0.0) + (self.clock() - t0)
                if b.is_empty:
                    raise RuntimeError("an empty unit refused an element (L-308 violated)") from None
                self.ledger.append("rollback", level=lv, unit=b.unit, item=pk.id, stop="budget",
                                   budget_reason=c.reason, work=_work_obj(c.states, c.moves), to=st.stable_seq,
                                   class_size=len(b.state), L=b.L)
                self._close_upper(st, c.reason)
                continue
            st.black = nb
            st.stable_seq = self.ledger.append(
                "admit", level=lv, unit=nb.unit, item=pk.id, group=[pk.id] + sorted(e.id for e in act),
                activated=sorted(e.id for e in act), class_size=len(nb.state), L=nb.L, stop="stable", work=work)
            if self.clock:
                dt = self.clock() - t0
                self.upper_secs.append((st.stable_seq, dt))
                self.upper_attempt_secs[lv] = self.upper_attempt_secs.get(lv, 0.0) + dt
            return
        raise RuntimeError("an empty unit refused an element twice (L-308 violated)")

    def _close_upper(self, st: _Upper, reason: str) -> None:
        b, lv = st.black, st.level
        cseq = self.ledger.append("close", level=lv, unit=b.unit, class_size=len(b.state), L=b.L, stop="budget",
                                  budget_reason=reason, to=st.stable_seq)
        news = [e for e in b.space.elements if e.origin == ORIGIN_NEW]
        vocab = frozenset(w for e in news for w in e.vocab)         # L-356 at every level
        inh = tuple(e.id for e in b.space.elements if e.origin == ORIGIN_INHERITED)
        pk = Pack("P%d:%d" % (lv + 1, st.j), b.unit, lv + 1, b.space.scope, vocab, b.state, b.L, cseq, reason,
                  tuple(e.id for e in news), inh, self._carry_ids(b.unit))
        pseq = self.ledger.append("pack", level=lv + 1, unit=b.unit, item=pk.id, group=sorted(vocab),
                                  class_size=len(b.state), L=b.L)
        st.closed.append(ClosedBlack(b, pk, cseq, pseq, reason))
        self.packs[pk.id] = pk
        st.j += 1
        st.black = Black.new("U%d:%d" % (lv, st.j), self.tier, self.budget, level=lv)
        st.stable_seq = self.ledger.append("open", level=lv, unit=st.black.unit, L=1, class_size=0)
        self._carry_up(lv, pk)                                      # recursion: the pack goes one level up
        self._new_carry(st.black)                                   # the copy is taken AFTER the carry-up

    # -- views ------------------------------------------------------------------
    def units(self) -> List[Tuple[Black, str]]:
        """Every unit as (black, "closed"|"open"): level 0 closed then open, then level 1, ..."""
        out = [(cb.black, STATUS_CLOSED) for cb in self.closed] + [(self.black, STATUS_OPEN)]
        for st in self.uppers:
            out += [(cb.black, STATUS_CLOSED) for cb in st.closed] + [(st.black, STATUS_OPEN)]
        return out

    def level_sizes(self) -> List[int]:
        return [len(self.closed) + 1] + [len(st.closed) + 1 for st in self.uppers]

    def covered_occurrences(self) -> List[Tuple[int, int, str]]:
        """P-1: the open level-0 black's scope plus the own_occ of every packs of F(0).  After a sentence is
        fed this lists every fed occurrence exactly once."""
        occ = [(o.sid, o.pos, o.unit) for p in self.frontier(0) for o in p.own_occ]
        return occ + [(o.sid, o.pos, o.unit) for o in self.black.space.scope]

    def level_covered(self, k: int) -> List[Tuple[int, int, str]]:
        """P-1 per level: the scopes of every unit of level k plus the scopes of the open units BELOW level k
        (their packs have not been carried up yet).  Every event exactly once, after a sentence is fed."""
        occ = []
        for b, st in self.units():
            if b.level == k or (st == STATUS_OPEN and b.level < k):
                occ += [(o.sid, o.pos, o.unit) for o in b.space.scope]
        return occ

    def to_bytes(self) -> bytes:                                     # L-379
        units = []
        for b, status in self.units():
            units.append({"id": b.unit, "level": b.level, "status": status,
                          "carry": [p.id for p in self.carry.get(b.unit, ())],
                          "elements": [[e.id, e.origin] for e in b.space.elements],
                          "scope": [[o.sid, o.pos, o.unit] for o in b.space.scope],
                          "state": [list(f) for f in b.state], "L": b.L, "space": b.space.sha256()})
        packs = [{"id": p.id, "unit": p.unit, "level": p.level, "vocab": sorted(p.vocab), "children": list(p.children),
                  "inherited": list(p.inherited), "carry": list(p.carry), "close_seq": p.close_seq,
                  "closed_by": p.closed_by, "own_occ": [[o.sid, o.pos, o.unit] for o in p.own_occ]}
                 for p in self.packs.values()]
        return canonical_json({"format": "line3.carry.tower.v1", "units": units, "packs": packs,
                               "ledger": self.ledger.sha256()})

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()


def build_tower(tier: str, tier_space: TierSpace, sids: Sequence[int], budget: pl.Budget, *, data_sha256=None,
                unit_filter=None, order_kind: str = "file", order_seed: Optional[int] = None, code_commit=None,
                clock=None, inject=None, after_sentence=None,
                pack_overflow: str = "close") -> CarryTower:
    """Feed `sids` (the recorded stream order) into a new tower.  `after_sentence(tower, sid)` is called after
    each sentence (P-1 checks etc.)."""
    sids = list(sids)
    led = Ledger(stream_header(tier, sids, budget, data_sha256=data_sha256, unit_filter=unit_filter,
                               order_kind=order_kind, order_seed=order_seed, code_commit=code_commit, copy=TOWER_COPY,
                               pack_overflow=pack_overflow))
    tw = CarryTower(tier, budget, led, clock=clock, inject=inject, pack_overflow=pack_overflow)
    for s in sids:
        tw.feed_sentence(s, occurrences_of(tier_space, s))
        if after_sentence is not None:
            after_sentence(tw, s)
    return tw


# --------------------------------------------------------------------------
# cache key and replay (O-1, O-3), ledger-only reconstruction (O-2)
# --------------------------------------------------------------------------
def check_cache_key(header: Mapping, tier: str, sids: Sequence[int], budget: pl.Budget,
                    data_sha256: Optional[str] = None, order_kind: Optional[str] = None,
                    order_seed: Optional[int] = None, pack_overflow: str = "close") -> None:       # L-378, L-320, L-401
    want = stream_header(tier, sids, budget, data_sha256=data_sha256, order_kind=order_kind or header["order"]["kind"],
                         order_seed=order_seed if order_kind is not None else header["order"]["seed"], copy=TOWER_COPY,
                         pack_overflow=pack_overflow)
    bad = [k for k in ("tier", "order_sha256", "build_level", "copy", "admission", "instability")
           if header.get(k) != want[k]]
    if header.get("pack_overflow", "close") != pack_overflow:      # L-401: absent key = "close"
        bad.append("pack_overflow")
    if data_sha256 is not None and header.get("data_sha256") != data_sha256:
        bad.append("data_sha256")
    if order_kind is not None and header.get("order") != want["order"]:
        bad.append("order")
    if bad:
        raise ValueError("cache key mismatch (%s): refusing to reuse this ledger / tower" % ", ".join(bad))


def replay_tower(ledger_bytes: bytes, tier_space: TierSpace, tier: str, sids: Sequence[int],
                 budget: pl.Budget, **kw) -> CarryTower:               # O-1 + O-3
    """Check the key, rebuild the tower from (data, order, budget) and require the same ledger bytes."""
    led = Ledger.from_bytes(ledger_bytes)
    po = kw.get("pack_overflow", "close")
    check_cache_key(led.header, tier, sids, budget, kw.get("data_sha256"), pack_overflow=po)
    tw = build_tower(tier, tier_space, sids, budget, data_sha256=led.header["data_sha256"],
                     unit_filter=led.header["unit_filter"], order_kind=led.header["order"]["kind"],
                     order_seed=led.header["order"]["seed"], code_commit=led.header["code_commit"],
                     pack_overflow=po)
    if tw.ledger.to_bytes() != ledger_bytes:
        raise ValueError("replay does not reproduce the ledger bytes (O-1)")
    return tw


def replay_ledger(led: Ledger) -> Dict[str, dict]:                  # L-377
    """Every unit rebuilt from the ledger alone: {unit: {level, status, carry, scope, new, active, pack}}.
    A rollback removes the unit's admits whose seq is greater than its `to`; `activation_deferred` and
    `split` change nothing by themselves."""
    units: Dict[str, dict] = {}
    packs: Dict[str, dict] = {}
    for e in led.events():
        k, u = e["kind"], e.get("unit")
        if k == "open":
            units[u] = {"level": e["level"], "status": STATUS_OPEN, "carry": None, "adm": [], "pack": None}
        elif k == "carry":
            units[u]["carry"] = list(e["group"])
        elif k == "admit":
            units[u]["adm"].append(e)
        elif k == "rollback":
            units[u]["adm"] = [a for a in units[u]["adm"] if a["seq"] <= e["to"]]
        elif k == "close":
            units[u]["status"] = STATUS_CLOSED
        elif k == "pack":
            packs[e["item"]] = {"unit": u, "vocab": list(e["group"]), "level": e["level"]}
            units[u]["pack"] = e["item"]
    for u in sorted(units, key=lambda x: (units[x]["level"], int(x.split(":")[1]))):   # label order of a dependency walk
        d = units[u]
        if d["level"] == 0:
            d["scope"] = [[a["occ"][0], a["occ"][1], a["item"]] for a in d["adm"]]
            d["new"] = [g for a in d["adm"] for g in a["group"] if g not in a["activated"]]
        else:
            d["new"] = [a["item"] for a in d["adm"]]
            d["scope"] = [o for pid in d["new"] for o in units[packs[pid]["unit"]]["scope"]]
        d["active"] = sorted({g for a in d["adm"] for g in a["activated"]})
    for u in units.values():
        del u["adm"]
    return units


def ledger_mismatches(tw: CarryTower) -> List[str]:                 # O-2
    """Differences between the tower and what `replay_ledger` rebuilds from its ledger (empty = complete)."""
    rep = replay_ledger(tw.ledger)
    bad: List[str] = []
    live = {b.unit: (b, st) for b, st in tw.units()}
    if set(rep) != set(live):
        bad.append("unit sets differ")
    for u, (b, st) in live.items():
        d = rep.get(u)
        if d is None:
            continue
        if d["level"] != b.level or d["status"] != st:
            bad.append("%s level/status" % u)
        if d["scope"] != [[o.sid, o.pos, o.unit] for o in b.space.scope]:
            bad.append("%s scope" % u)
        if d["new"] != [e.id for e in b.space.elements if e.origin == ORIGIN_NEW]:
            bad.append("%s new elements" % u)
        if d["active"] != sorted(e.id for e in b.space.elements if e.origin == ORIGIN_INHERITED):
            bad.append("%s woken" % u)
        if d["carry"] != [p.id for p in tw.carry.get(u, ())]:
            bad.append("%s carry" % u)
    pack_ev = {e["item"]: e for e in tw.ledger.events() if e["kind"] == "pack"}
    for p in tw.packs.values():
        if rep.get(p.unit, {}).get("pack") != p.id:
            bad.append("%s pack" % p.id)
        # L-356 / L-375: the vocab written in the ledger = the pack's vocab = the units of its unit's replayed scope
        pe, d = pack_ev.get(p.id), rep.get(p.unit)
        if pe is None or pe["group"] != sorted(p.vocab) or pe["level"] != p.level:
            bad.append("%s pack event" % p.id)
        if d is not None and sorted({o[2] for o in d["scope"]}) != sorted(p.vocab):
            bad.append("%s vocab vs replayed scope" % p.id)
    return bad
