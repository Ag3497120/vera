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
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3.space import TierSpace

LEDGER_FORMAT = "line3.carry.ledger.v1"                       # design 3.7
ORIGIN_NEW, ORIGIN_INHERITED = "new", "inherited"             # design 3.2 (origin of an element)
ORIGINS: Tuple[str, ...] = (ORIGIN_NEW, ORIGIN_INHERITED)
STATUS_OPEN, STATUS_CLOSED = "open", "closed"                 # design 3.1 (C2/C3 hook: unit status)
ORDER_KINDS: Tuple[str, ...] = ("file", "shuffle", "reverse")  # design 3.7 header.order.kind
EVENT_KINDS: Tuple[str, ...] = ("admit", "rollback", "close", "pack", "open", "activate", "carry",
                                "split", "activation_deferred")   # L-331
EVENT_FIELDS: Tuple[str, ...] = ("seq", "kind", "level", "unit", "item", "occ", "group", "activated",
                                 "class_size", "L", "stop", "budget_reason", "work")   # design 3.7
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
    extra = [k for k in h if k not in HEADER_FIELDS]
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
