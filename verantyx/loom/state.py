"""LOOM-a: the loom state (docs/LINE3_LOOM_DESIGN.md 3.1-3.3).

  Unit        a side registry entry; cross cells hold the uid, never the surface (L-LOOM-03).  record / constructed.
  LoomCross   centre + six arms of L cells along geometry.AXES; k = 0 is the OUTER end, k = L-1 the seat next to the centre
              (geometry.Seat).  A PROSE cross is always seated (D-1): its innermost seat k = L-1 holds the foundation token of the
              arm's particle (foundation.DEFAULT_SPEC), so its data seats are k = 0 .. L-2.  A CODE cross has no foundation
              (OP-LOOM-2 (a)): data seats k = 0 .. L-1.
  LoomState   units, crosses, one thread (L-LOOM-04), the closure, the counters.

uid / cid are creation-order counters ("u1", "c1", ...): labels, never ranks (L-LOOM-02).  Nothing here touches a foundation
seat (OP-G1-4): every mutator refuses `seat_is_foundation` before it looks at anything else of the seat.

Typed refusals are exceptions (`Refuse`) raised BEFORE any mutation, so a refused operation never leaves a half-changed state.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple

from verantyx.line3 import foundation as fd
from verantyx.line3 import geometry as geo

SPEC = fd.DEFAULT_SPEC
AXES: Tuple[str, ...] = geo.AXES
CENTRE = "centre"
PROSE, CODE = "prose", "code"
LANGS = (PROSE, CODE)
PROSE_TIERS: Tuple[str, ...] = ("RUN", "WORD", "CHAR")
CODE_TIER = "CODE"
ALL_TIERS: Tuple[str, ...] = PROSE_TIERS + (CODE_TIER,)
RECORD, CONSTRUCTED = "record", "constructed"
MODES = ("record_only", "constructed_allowed")
ABSTAIN_TYPES = ("no_record", "cannot_weave", "unknown")

# design 3.1 / 4: the limits and caps (L-LOOM-08).  A run has at most one successful emit, so a per-run cap bounds the ops behind it.
CAPS: Dict[str, Dict[str, int]] = {
    PROSE: {"ops": 120, "lookups": 30, "reads": 20, "emit_attempts": 5, "constructed": 12, "unit_chars": 8,
            "max_L": 5, "crosses": 24, "max_depth": 8},
    CODE: {"ops": 400, "lookups": 60, "reads": 40, "emit_attempts": 8, "constructed": 60, "unit_chars": 40,
           "max_L": 8, "crosses": 60, "max_depth": 8},
}
COUNTERS: Tuple[str, ...] = ("ops", "lookups", "reads", "emit_attempts", "constructed")
# L-LOOM-44: what a refused call may cost the ledger.  The argument of a call is stored only while it is small (the design's unit-size
# limits: lookup text 32, constructed unit 8 / 40, model id 64); and the calls that no cap of 4 / 3.2 counts are themselves counted.
ARG_STR_CAP = 64               # chars of any string (value or key) in the arguments of one call
ARGS_CHARS_CAP = 512           # chars of the canonical JSON of the arguments of one call
GUARD_CAPS: Dict[str, int] = {"abstain_refused": 5, "closed_calls": 20}
GUARDS: Tuple[str, ...] = ("abstain_refused", "closed_calls")


class Refuse(Exception):
    """A typed refusal (never a free-text error).  `type` is the closed refusal name, `detail` a JSON-able dict."""

    def __init__(self, type: str, detail: Optional[dict] = None) -> None:
        super().__init__(type)
        self.type = type
        self.detail = dict(detail or {})


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------------
# seats
# ------------------------------------------------------------------------------------------------------------
_SEAT_RX = re.compile(r"^([+-][xyz])(?::(0|[1-9][0-9]*))?$")


def parse_seat(s) -> Tuple[Optional[str], Optional[int]]:
    """"centre" -> (None, None); "+x:0" -> ("+x", 0); a bare arm "+x" -> ("+x", None).  Anything else: `bad_seat`."""
    if s == CENTRE:
        return None, None
    m = _SEAT_RX.match(s) if isinstance(s, str) else None
    if not m:
        raise Refuse("bad_seat", {"seat": s if isinstance(s, str) else None})
    return m.group(1), (None if m.group(2) is None else int(m.group(2)))


def fmt_seat(arm: Optional[str], k: Optional[int] = None) -> str:
    return CENTRE if arm is None else (arm if k is None else "%s:%d" % (arm, k))


def is_foundation_cell(c: Optional[str]) -> bool:
    return fd.is_constructed(c)


# ------------------------------------------------------------------------------------------------------------
# units
# ------------------------------------------------------------------------------------------------------------
class Unit:
    __slots__ = ("uid", "surface", "kind", "tier", "prov", "seated")

    def __init__(self, uid: str, surface: str, kind: str, tier: Optional[str], prov: dict) -> None:
        self.uid = uid
        self.surface = surface
        self.kind = kind
        self.tier = tier
        self.prov = prov
        self.seated: Optional[List[str]] = None            # [cid, seat] or None

    def to_obj(self) -> dict:
        return {"uid": self.uid, "surface": self.surface, "kind": self.kind, "tier": self.tier, "prov": self.prov,
                "seated": None if self.seated is None else list(self.seated)}


# ------------------------------------------------------------------------------------------------------------
# crosses
# ------------------------------------------------------------------------------------------------------------
class LoomCross:
    """geometry.Cross + {cid, tier, lang, topic, depth, linked}.  Cells: uid | foundation token | None."""
    __slots__ = ("cid", "tier", "lang", "L", "depth", "topic", "linked", "centre", "arms")

    def __init__(self, cid: str, tier: str, lang: str, L: int, depth: int = 0) -> None:
        self.cid = cid
        self.tier = tier
        self.lang = lang
        self.L = L
        self.depth = depth
        self.topic = False
        self.linked = False
        self.centre: Optional[str] = None
        self.arms: List[List[Optional[str]]] = [[None] * L for _ in AXES]
        if lang == PROSE:
            for ai, p in enumerate(SPEC.arms):
                self.arms[ai][L - 1] = fd.token(p)

    # -- shape ---------------------------------------------------------------------------------------------------
    @property
    def inner_k(self) -> int:
        """The innermost DATA seat of every arm: prose L-2 (L-1 is the foundation), code L-1.  -1 = no data seat on the arms."""
        return self.L - 2 if self.lang == PROSE else self.L - 1

    def arm_index(self, arm: str) -> int:
        return AXES.index(arm)

    def is_foundation_seat(self, arm: Optional[str], k: Optional[int]) -> bool:
        return self.lang == PROSE and arm is not None and k == self.L - 1

    def get(self, arm: Optional[str], k: Optional[int]) -> Optional[str]:
        return self.centre if arm is None else self.arms[self.arm_index(arm)][k]

    def put(self, arm: Optional[str], k: Optional[int], v: Optional[str]) -> None:
        if arm is None:
            self.centre = v
        else:
            self.arms[self.arm_index(arm)][k] = v

    def check_seat(self, arm: Optional[str], k: Optional[int]) -> None:
        """Refuse a seat that is not a DATA seat of this cross: out of range first, then foundation (the two are disjoint: the foundation
        seat k = L-1 is in range), so the order cannot change which refusal a call gets (L-LOOM-50, which corrects the earlier wording)."""
        if arm is None:
            return
        if k is None or not (0 <= k < self.L):
            raise Refuse("seat_out_of_range", {"cid": self.cid, "seat": fmt_seat(arm, k), "L": self.L})
        if self.is_foundation_seat(arm, k):
            raise Refuse("seat_is_foundation", {"cid": self.cid, "seat": fmt_seat(arm, k)})

    def data_seats(self) -> List[str]:
        """Every data seat name: centre, then the arms in AXES order, k ascending (outer -> inner)."""
        out = [CENTRE]
        for arm in AXES:
            out.extend(fmt_seat(arm, k) for k in range(0, self.inner_k + 1))
        return out

    def bare_arm_seat(self, arm: str) -> int:
        """`seat` with a bare arm: the innermost EMPTY data seat of the arm (L-LOOM-23); `seat_out_of_range` when the arm is full."""
        ai = self.arm_index(arm)
        for k in range(self.inner_k, -1, -1):
            if self.arms[ai][k] is None:
                return k
        raise Refuse("seat_out_of_range", {"cid": self.cid, "seat": arm, "reason": "no_data_seat" if self.inner_k < 0 else "arm_full",
                                           "L": self.L})

    def uids(self) -> List[str]:
        """Seated unit ids in seat order (centre, then AXES order, k ascending)."""
        out = []
        if self.centre is not None:
            out.append(self.centre)
        for ai in range(len(AXES)):
            for c in self.arms[ai]:
                if c is not None and not is_foundation_cell(c):
                    out.append(c)
        return out

    def extend(self, L2: int) -> None:
        """L-LOOM-23: prepend empty OUTER seats to every arm.  Loom-local: placement.extend would call placement.canon."""
        pad = [None] * (L2 - self.L)
        self.arms = [pad + a for a in self.arms]
        self.L = L2

    def to_obj(self) -> dict:
        return {"cid": self.cid, "tier": self.tier, "lang": self.lang, "L": self.L, "depth": self.depth, "topic": self.topic,
                "linked": self.linked, "centre": self.centre, "arms": [list(a) for a in self.arms]}


# ------------------------------------------------------------------------------------------------------------
# the state
# ------------------------------------------------------------------------------------------------------------
class LoomState:
    def __init__(self, lang: str) -> None:
        if lang not in LANGS:
            raise ValueError("lang must be prose or code")
        self.lang = lang
        self.units: Dict[str, Unit] = {}
        self.crosses: Dict[str, LoomCross] = {}
        self.thread: List[str] = []
        self.closed: Optional[List[str]] = None            # ["emitted", output_sha] | ["abstained", type] | ["abandoned", reason]
        self.counters: Dict[str, int] = {k: 0 for k in COUNTERS}
        self.guards: Dict[str, int] = {k: 0 for k in GUARDS}     # refused `abstain` calls; calls after the run is closed (L-LOOM-44)

    # -- registry ------------------------------------------------------------------------------------------------
    def new_unit(self, surface: str, kind: str, tier: Optional[str], prov: dict) -> Unit:
        uid = "u%d" % (len(self.units) + 1)
        u = self.units[uid] = Unit(uid, surface, kind, tier, prov)
        return u

    def new_cross(self, tier: str, L: int, depth: int = 0) -> LoomCross:
        cid = "c%d" % (len(self.crosses) + 1)
        c = self.crosses[cid] = LoomCross(cid, tier, self.lang, L, depth)
        return c

    def unit(self, uid) -> Unit:
        u = self.units.get(uid) if isinstance(uid, str) else None
        if u is None:
            raise Refuse("unknown_uid", {"uid": uid if isinstance(uid, str) else None})
        return u

    def cross(self, cid) -> LoomCross:
        c = self.crosses.get(cid) if isinstance(cid, str) else None
        if c is None:
            raise Refuse("unknown_cid", {"cid": cid if isinstance(cid, str) else None})
        return c

    # -- seating primitives (callers validate first) ---------------------------------------------------------------
    def place(self, cross: LoomCross, arm: Optional[str], k: Optional[int], uid: str) -> None:
        cross.put(arm, k, uid)
        self.units[uid].seated = [cross.cid, fmt_seat(arm, k)]

    def lift(self, cross: LoomCross, arm: Optional[str], k: Optional[int]) -> str:
        uid = cross.get(arm, k)
        cross.put(arm, k, None)
        self.units[uid].seated = None
        return uid

    def swap(self, cross: LoomCross, a: Tuple[Optional[str], Optional[int]], b: Tuple[Optional[str], Optional[int]]) -> None:
        va, vb = cross.get(*a), cross.get(*b)
        cross.put(a[0], a[1], vb)
        cross.put(b[0], b[1], va)
        if vb is not None:
            self.units[vb].seated = [cross.cid, fmt_seat(*a)]
        if va is not None:
            self.units[va].seated = [cross.cid, fmt_seat(*b)]

    def extend_cross(self, cross: LoomCross, L2: int) -> None:
        """Grow a cross (L-LOOM-23) and bring the seat NAMES in the registry up to date: k is counted from the outer end, so every
        arm unit's k moves by L2 - L while it stays next to the same neighbours."""
        cross.extend(L2)
        for ai, ax in enumerate(AXES):
            for k, cell in enumerate(cross.arms[ai]):
                if cell is not None and not is_foundation_cell(cell):
                    self.units[cell].seated = [cross.cid, fmt_seat(ax, k)]

    def pool(self) -> List[str]:
        return [uid for uid, u in self.units.items() if u.seated is None]

    # -- bytes -----------------------------------------------------------------------------------------------------
    def to_obj(self) -> dict:
        return {"units": {uid: u.to_obj() for uid, u in self.units.items()},
                "crosses": {cid: c.to_obj() for cid, c in self.crosses.items()},
                "thread": list(self.thread), "closed": None if self.closed is None else list(self.closed),
                "counters": dict(self.counters), "guards": dict(self.guards)}

    def sha(self) -> str:
        return sha256_text(canonical(self.to_obj()))
