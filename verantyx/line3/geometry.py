"""T2 geometry of the line-3 cross: 6-arm cross, 24 cube rotations, cell swaps, sections.

Binding decisions (ops/decisions/2026-10-06_line3_faithful_build.md):
  I-03  cross = centre + 6 arms x seats along each arm. Arm length L is a
        parameter; DEFAULT_L = 4 is only a test default (L-04; capacity is to be
        re-measured, I-18 / N-09).
  decision 5 (both)  moves are cell swaps AND true cube rotations (the 24 proper
        rotations of the cube acting on the 6 arms).
  I-09 / decision 4  sections are the current windows, reproduced from
        verantyx/consensus.py:143-158 (visible_axes, ring mode, window=1).

Everything here is immutable, deterministic, and free of floats/randomness.
Cell contents are opaque: int | str | None (None = empty seat). Placing
semantics (e.g. L-09 packing empty seats toward the centre) belong to T4.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from typing import Iterable, List, NamedTuple, Optional, Tuple, Union

# L-01/I-03: same arm labels and order as verantyx/cross.py:6 (AXES). Equality is
# asserted in tests/line3/test_geometry.py.
AXES: Tuple[str, ...] = ("+x", "-x", "+y", "-y", "+z", "-z")
N_ARMS = len(AXES)
DEFAULT_L = 4          # L-04: test default only, not a measured capacity (N-09)
DEFAULT_WINDOW = 1     # I-09: consensus.py:63 ConsensusConfig.window default
Cell = Union[int, str, None]


# --------------------------------------------------------------------------
# Rotations (decision 5)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Rotation:
    """A permutation of the 6 arm indices; perm[i] = image index of AXES[i].

    Composition convention (L-15, local): (g*h)(a) = g(h(a)), i.e. h acts first.
    """

    perm: Tuple[int, ...]

    def __call__(self, arm: int) -> int:
        return self.perm[arm]

    def compose(self, other: "Rotation") -> "Rotation":
        return Rotation(tuple(self.perm[other.perm[i]] for i in range(N_ARMS)))

    def inverse(self) -> "Rotation":
        inv = [0] * N_ARMS
        for i, j in enumerate(self.perm):
            inv[j] = i
        return Rotation(tuple(inv))

    def preserves_opposites(self) -> bool:
        # arms 2j and 2j+1 are the two poles of one axis (AXES order).
        return all(self.perm[i ^ 1] == self.perm[i] ^ 1 for i in range(N_ARMS))


def _build_group() -> Tuple[Rotation, ...]:
    """The 24 proper rotations as signed-permutation matrices with det = +1.

    Deterministic enumeration (itertools order). The tuple is then sorted by
    `perm` so indices are stable (L-16: G24 index order = lexicographic perm; an
    index is a label, never a tie-break winner).
    """
    out = []
    for pi in itertools.permutations(range(3)):
        # parity of pi
        inv = sum(1 for a in range(3) for b in range(a + 1, 3) if pi[a] > pi[b])
        psign = -1 if inv % 2 else 1
        for signs in itertools.product((1, -1), repeat=3):
            if psign * signs[0] * signs[1] * signs[2] != 1:
                continue
            perm = [0] * N_ARMS
            for i in range(3):
                for s_idx, sigma in ((0, 1), (1, -1)):  # arm 2i = +, 2i+1 = -
                    img_sign = sigma * signs[i]
                    perm[2 * i + s_idx] = 2 * pi[i] + (0 if img_sign == 1 else 1)
            out.append(Rotation(tuple(perm)))
    out.sort(key=lambda r: r.perm)
    return tuple(out)


G24: Tuple[Rotation, ...] = _build_group()  # I-03 / decision 5
IDENTITY = Rotation(tuple(range(N_ARMS)))


def legacy_shift(k: int) -> Rotation:
    """Legacy 'rotation' of consensus.py:244-250 / :146: section->axis offset
    shifted by k along the AXES ring, as a permutation i -> (i+k) % 6. NOT
    necessarily a cube rotation (F1: only k = 0, 2, 4 are)."""
    return Rotation(tuple((i + k) % N_ARMS for i in range(N_ARMS)))


def in_group(r: Rotation) -> bool:
    return r in set(G24)


def moves_rotate() -> Tuple[Rotation, ...]:
    """I-12 move set, rotation part: the 23 non-identity rotations (§4.5)."""
    return tuple(r for r in G24 if r != IDENTITY)


# --------------------------------------------------------------------------
# Seats and graph (I-03)
# --------------------------------------------------------------------------
class Seat(NamedTuple):
    """Intrinsic seat: (arm label, k) with k=0 outer end .. L-1 next to centre,
    or CENTER. Orientation-independent (I-03: k=0 is the section side)."""

    arm: str
    k: int


CENTER = Seat("center", 0)


def seats(L: int = DEFAULT_L) -> Tuple[Seat, ...]:
    """All 6L+1 seats in a fixed order: centre, then arms in AXES order, k=0..L-1."""
    return (CENTER,) + tuple(Seat(a, k) for a in AXES for k in range(L))


def edges(L: int = DEFAULT_L) -> Tuple[Tuple[Seat, Seat], ...]:
    """I-03: arms[a][k]-arms[a][k+1] and arms[a][L-1]-centre."""
    out: List[Tuple[Seat, Seat]] = []
    for a in AXES:
        for k in range(L - 1):
            out.append((Seat(a, k), Seat(a, k + 1)))
        out.append((Seat(a, L - 1), CENTER))
    return tuple(out)


def neighbours(seat: Seat, L: int = DEFAULT_L) -> Tuple[Seat, ...]:
    """Seats adjacent on the cross (the 'neighbours on the cross' of §4.4)."""
    _check_seat(seat, L)
    if seat == CENTER:
        return tuple(Seat(a, L - 1) for a in AXES)
    out = []
    if seat.k > 0:
        out.append(Seat(seat.arm, seat.k - 1))
    out.append(Seat(seat.arm, seat.k + 1) if seat.k < L - 1 else CENTER)
    return tuple(out)


def _check_seat(seat: Seat, L: int) -> None:
    if seat == CENTER:
        return
    if seat.arm not in AXES or not (0 <= seat.k < L):
        raise ValueError(f"bad seat {seat!r} for L={L}")


# --------------------------------------------------------------------------
# Cross (immutable value)
# --------------------------------------------------------------------------
def _check_cell(c: object) -> Cell:
    if c is None or (isinstance(c, (int, str)) and not isinstance(c, bool)):
        return c  # type: ignore[return-value]
    # L-17 (local): opaque cell values limited to int|str|None so that the
    # serialization is exact and hash-seed independent (L-02: no floats).
    raise TypeError(f"cell must be int|str|None, got {type(c).__name__}")


@dataclass(frozen=True)
class Cross:
    """I-03 cross. `arms[i]` is the tuple of L cells of AXES[i] (intrinsic
    labelling); `orientation` g in G24 says where each arm points in the world
    (arm i points to world direction g(i)). Contents are not moved by a
    rotation; the orientation is (L-18, per design §3.3 `orientation : g`)."""

    L: int
    center: Cell
    arms: Tuple[Tuple[Cell, ...], ...]
    orientation: Rotation = IDENTITY

    def __post_init__(self) -> None:
        if not isinstance(self.L, int) or self.L < 1:
            raise ValueError("L must be a positive int")
        if len(self.arms) != N_ARMS or any(len(a) != self.L for a in self.arms):
            raise ValueError("arms must be 6 sequences of length L")
        _check_cell(self.center)
        for a in self.arms:
            for c in a:
                _check_cell(c)
        if self.orientation not in set(G24):
            raise ValueError("orientation must be one of G24")

    # construction copies, so no aliasing with caller-owned lists (acceptance)
    @staticmethod
    def make(L: int = DEFAULT_L, center: Cell = None,
             arms: Optional[Iterable[Iterable[Cell]]] = None,
             orientation: Rotation = IDENTITY) -> "Cross":
        if arms is None:
            tup = tuple(tuple(None for _ in range(L)) for _ in range(N_ARMS))
        else:
            tup = tuple(tuple(a) for a in arms)
        return Cross(L, center, tup, orientation)

    def get(self, seat: Seat) -> Cell:
        _check_seat(seat, self.L)
        return self.center if seat == CENTER else self.arms[AXES.index(seat.arm)][seat.k]

    def world_arms(self) -> Tuple[Tuple[Cell, ...], ...]:
        """Arm contents indexed by WORLD direction w: world[w] = arms[g^-1(w)]."""
        ginv = self.orientation.inverse()
        return tuple(self.arms[ginv(w)] for w in range(N_ARMS))

    def serialize(self) -> bytes:
        """Exact, deterministic bytes including orientation (L-19)."""
        return json.dumps(
            {"L": self.L, "c": self.center, "a": self.arms,
             "g": self.orientation.perm},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")

    def canonical_key(self) -> bytes:
        """L-06: representative of the 24-rotation orbit = the minimum, over all
        r in G24, of the serialized WORLD view of rotate(self, r). Orientation is
        excluded (it is what the orbit varies). Equal serializations are the
        same state, so a tie here is not a winner-by-order."""
        best: Optional[bytes] = None
        for r in G24:
            w = rotate(self, r).world_arms()
            s = json.dumps({"L": self.L, "c": self.center, "w": w},
                           sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True).encode("ascii")
            if best is None or s < best:
                best = s
        assert best is not None
        return best


# --------------------------------------------------------------------------
# Moves (decision 5; I-12 move set)
# --------------------------------------------------------------------------
def rotate(cross: Cross, r: Rotation) -> Cross:
    """True cube rotation: new orientation r*g. Returns a new Cross (decision 5)."""
    if r not in set(G24):
        raise ValueError("not a cube rotation")
    return Cross(cross.L, cross.center, cross.arms, r.compose(cross.orientation))


def swap(cross: Cross, p: Seat, q: Seat) -> Cross:
    """Cell swap of any two seats, centre included (§4.5). swap(swap(c,p,q),p,q)==c.
    p == q is the identity (L-20, local: allowed, so the move is total)."""
    _check_seat(p, cross.L)
    _check_seat(q, cross.L)
    vp, vq = cross.get(p), cross.get(q)
    cen = cross.center
    arms = [list(a) for a in cross.arms]  # private copy; never exposed
    for seat, val in ((p, vq), (q, vp)):
        if seat == CENTER:
            cen = val
        else:
            arms[AXES.index(seat.arm)][seat.k] = val
    return Cross(cross.L, cen, tuple(tuple(a) for a in arms), cross.orientation)


def moves_swap(L: int = DEFAULT_L) -> Tuple[Tuple[Seat, Seat], ...]:
    """All unordered pairs of distinct seats, in `seats(L)` order: C(6L+1, 2)
    (§4.5 'any 2 seats, centre included'). Pairs holding equal contents give a
    no-op; filtering them is the caller's (T5) business and must be counted."""
    s = seats(L)
    return tuple((s[i], s[j]) for i in range(len(s)) for j in range(i + 1, len(s)))


# --------------------------------------------------------------------------
# Sections (decision 4 / I-09)
# --------------------------------------------------------------------------
def visible_arms(orientation: Rotation, section: int,
                 window: int = DEFAULT_WINDOW, widened: bool = False) -> Tuple[str, ...]:
    """Arms in front of world section `section` (0..5) for a cross with the given
    orientation. Window semantics are consensus.py:143-158 (ring mode):
      - widened -> every arm (:144-145);
      - world positions p = (section + off) % 6 for off = -window..window, in
        that order, duplicates dropped (:153-158);
      - [consensus.py:146 adds a legacy `rotation` shift to the index; here the
        shift is replaced by the orientation g (I-09, design §4.3): the arm in
        front of world position p is g^-1(AXES[p])].
    The geometric_visibility variant (:147-152) is not used (I-09: 'ring')."""
    if not 0 <= section < N_ARMS:
        raise ValueError("section must be 0..5")
    if widened:
        return tuple(AXES)
    ginv = orientation.inverse()
    out: List[str] = []
    for off in range(-window, window + 1):
        a = AXES[ginv((section + off) % N_ARMS)]
        if a not in out:
            out.append(a)
    return tuple(out)
