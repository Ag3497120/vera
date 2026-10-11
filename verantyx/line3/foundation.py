"""G1-a: the foundation's seats and the adhesion it counts (docs/LINE3_G4_GROWTH_METER.md 4.2, docs/LINE3_G1_INITIAL_PLACEMENT.md 3.1).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md, quoted):
  OP-G1-4 「固定かつ継ぎ目」   the foundation seats are fixed (no move touches them; rotations stay); the key and the ratios see the
                               cross with the foundation seats removed and the data units on both sides taken as neighbours (the seam).
  OP-G1-5 「鍵の 3 番目 (n, p, a)」 the key gets a third component, the adhesion a; what the old definition told apart stays,
                               only the ties are split by a.
  OP-G1-9 「腕＝関係の札」     every data seat of an arm is bound, by adhesion, to the particle of that arm.
  D-1 「データの種を中心、助詞 6 語は最内環」 the centre is the data word found by search as today; の・に・で・と・を・が sit FIXED in the
                               innermost ring of the six arms (one per arm, in the ladder order grammar.foundation_cross defines);
                               は has no seat and attaches to the centre word with weight 233/377.

What is here (pure functions of their arguments; exact integers; no float; no hash-order dependence):
  Spec        the foundation's seats: arms (axis, particle, numerator), the centre relation, the denominator 377, the ladder ratios as
              Fractions (validated: Fraction only, positive, pairwise different -- a float or a tie raises), `seats_sha`.
  tokens      the constructed content of a foundation seat, "\\u0000F:" + particle (L-G4-20).  It never equals a data unit.
  Adhesion    adj_T(v, p) = the number of DISTINCT sentences (sids) of the space's base sentences in which an occurrence of the unit v
              ends where the particle p begins (right-attached, L-G1-1), with the evidence of every count (sid, start, end, p_start, p_end).
                RUN, WORD : from grammar.records_of_space (the WORD cut, punctuation skipped, L-542; a RUN unit followed by a gap
                            such as 「にある」 counts through the WORD 「に」 that starts the gap, L-G1-2)
                CHAR      : character by character on the attribution-stripped text, NO tokeniser, nothing skipped: the char at i is a
                            non-hiragana letter (a CHAR unit, V2) and the char at i+1 is one of the seven particles (L-G4-21)
  a_num       a(arrangement) as an INTEGER over 377 (L-G4-22): sum over the data units v on the arm of particle p of numerator(p) * adj(v, p),
              plus numerator(は) * adj(centre word, は).  The arm of a data unit is read from the innermost seat of its leg, never from
              the arm index.
  contract    the seam: drop the foundation seats (the innermost seat of every leg); what is left is a plain flat at L - 1.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.lang import strip_attribution
from verantyx.line3 import geometry as geo
from verantyx.line3 import space as sp
from verantyx.line3.funcwords import is_function_unit

# NOTE: this module is imported by placement.py, which slide_place / slide_ratios import: it must NOT import grammar (their isolation tests
# forbid it).  The hand-written particle list and the ladder are therefore copied here from grammar.py (G1 3.1.1, OP-G1-3 (a), OP-G3-6 (a))
# and tests/line3/test_foundation.py pins every one of them equal to grammar's (P7, LADDER, ARM_PARTICLES, WEIGHTS, FIB_DEN, foundation_obj).
# grammar is imported lazily, only by the functions that read its records.

GRAMMAR_FORMAT = "line3.grammar.v1"              # = grammar.FORMAT (pinned by a test): the "format" of grammar.foundation_obj()
SEATS_FORMAT = "line3.foundation_seats.v1"
FOUNDATIONS = ("off", "on")                      # the switch of the placement API (default "off")
TOKEN_PREFIX = "\u0000F:"                        # L-G4-20: no text unit contains NUL
P7: Tuple[str, ...] = ("は", "の", "に", "を", "が", "で", "と")          # G1 3.1.1: a hand-written list, not UniDic tags
LADDER: Tuple[str, ...] = ("は", "の", "に", "で", "と", "を", "が")      # OP-G1-3 (a) rank 1..7 (fulllead WORD share order)
CENTRE_PARTICLE = LADDER[0]
ARM_PARTICLES: Tuple[str, ...] = LADDER[1:]                              # +x -x +y -y +z -z (OP-G3-6 (a))
RECORD_TIERS: Tuple[str, ...] = (sp.RUN, sp.WORD)                        # L-541: CHAR has no grammar records
ATTACH_RULES = {sp.RUN: "records/straddle", sp.WORD: "records/straddle", sp.CHAR: "char_next"}   # L-G1-2, L-G4-21

Flat = Tuple[Optional[str], ...]


# ------------------------------------------------------------------------------------------------------------
# the switch
# ------------------------------------------------------------------------------------------------------------
def _fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


FIB_DEN = _fib(14)                                                       # 377
WEIGHTS: Mapping[str, Fraction] = {p: Fraction(_fib(14 - k), FIB_DEN) for k, p in enumerate(LADDER, 1)}   # 233/377 .. 13/377 (reduced)


def check_foundation(foundation: str) -> str:
    """The `foundation=` option of the placement API: "off" (default, every committed byte unchanged) or "on"."""
    if foundation not in FOUNDATIONS:
        raise ValueError("foundation must be 'off' or 'on'")
    return foundation


# ------------------------------------------------------------------------------------------------------------
# constructed tokens (L-G4-20)
# ------------------------------------------------------------------------------------------------------------
def token(particle: str) -> str:
    return TOKEN_PREFIX + particle


def is_constructed(x: Optional[str]) -> bool:
    return x is not None and x.startswith(TOKEN_PREFIX)


def particle_of(tok: Optional[str]) -> str:
    """The particle a constructed token stands for (ValueError for anything else)."""
    if not is_constructed(tok):
        raise ValueError("not a constructed foundation token: %r" % (tok,))
    return tok[len(TOKEN_PREFIX):]


# ------------------------------------------------------------------------------------------------------------
# the spec: particles, arm order, ladder ratios, sha
# ------------------------------------------------------------------------------------------------------------
def check_ratios(ratios: Mapping[str, Fraction]) -> Dict[str, Fraction]:
    """I-G1-3: ratios are exact Fractions, positive and pairwise different (a tie would leave the arm of a unit to an order).
    A float (or an int / bool, which would slip through as a number that is not a ratio) raises TypeError, a tie ValueError."""
    out: Dict[str, Fraction] = {}
    for p, r in ratios.items():
        if not isinstance(r, Fraction):
            raise TypeError("a ratio must be a Fraction, got %s for %r" % (type(r).__name__, p))
        if r <= 0:
            raise ValueError("a ratio must be positive: %r" % (p,))
        out[p] = r
    if len(set(out.values())) != len(out):
        raise ValueError("two particles have the same ratio (a tie leaves the order to the code)")
    return out


@dataclass(frozen=True)
class Spec:
    """The foundation's seats.  `centre` is the relation of the word at the centre (は: no seat, binds to the centre);
    `arms` are the six arm particles in the order of geometry.AXES (+x -x +y -y +z -z)."""
    centre: str
    arms: Tuple[str, ...]
    ratios: Tuple[Tuple[str, Fraction], ...]         # (particle, ratio) in ladder order: centre first, then the arms
    den: int                                         # the denominator of the ladder (377), recorded and never divided by

    @staticmethod
    def make(centre: str, arms: Sequence[str], ratios: Mapping[str, Fraction], den: int) -> "Spec":
        arms = tuple(arms)
        if len(arms) != geo.N_ARMS or len(set(arms)) != geo.N_ARMS or centre in arms:
            raise ValueError("the foundation needs six different arm particles, none of them the centre relation")
        for p in (centre,) + arms:
            if p not in P7:
                raise ValueError("%r is not one of the seven particles" % (p,))
        if set(ratios) != set((centre,) + arms):
            raise ValueError("ratios must cover exactly the centre relation and the six arm particles")
        r = check_ratios(ratios)
        if any((x * den).denominator != 1 for x in r.values()):
            raise ValueError("every ratio must be a whole number over the recorded denominator %d" % den)
        return Spec(centre, arms, tuple((p, r[p]) for p in (centre,) + arms), den)

    # -- the ladder ---------------------------------------------------------------------------------------------
    @property
    def ladder(self) -> Tuple[str, ...]:
        """(centre relation, arm particles in axis order): the column order of every adhesion row."""
        return (self.centre,) + self.arms

    def ratio(self, particle: str) -> Fraction:
        return dict(self.ratios)[particle]

    def numerator(self, particle: str) -> int:
        """r_F(p) * den, an integer (L-G4-22: a is held over the recorded denominator and never divided)."""
        n = self.ratio(particle) * self.den
        assert n.denominator == 1
        return n.numerator

    @property
    def numerators(self) -> Tuple[int, ...]:
        return tuple(self.numerator(p) for p in self.ladder)

    def arm_of_axis(self, axis: str) -> str:
        return self.arms[geo.AXES.index(axis)]

    # -- bytes --------------------------------------------------------------------------------------------------
    def foundation_obj(self) -> dict:
        """The ladder as grammar.foundation_obj writes it (equal to it for DEFAULT_SPEC; a test pins that)."""
        return {"format": GRAMMAR_FORMAT, "centre": [self.centre, str(self.ratio(self.centre))],
                "arms": [[geo.AXES[i], p, str(self.ratio(p))] for i, p in enumerate(self.arms)]}

    def to_obj(self) -> dict:
        return {"format": SEATS_FORMAT,
                "foundation": self.foundation_obj(),
                "arms": {geo.AXES[i]: p for i, p in enumerate(self.arms)},
                "centre_relation": self.centre,
                "position_rule": "ring1",
                "seam": "contract",
                "attach": dict(sorted(ATTACH_RULES.items())),
                "numerators": {p: self.numerator(p) for p in self.ladder},
                "den": self.den}

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_obj(), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()


# the spec grammar.py defines: centre は 233/377, then の に で と を が = 144 89 55 34 21 13 over 377 on +x -x +y -y +z -z
DEFAULT_SPEC: Spec = Spec.make(CENTRE_PARTICLE, ARM_PARTICLES, WEIGHTS, FIB_DEN)


def seats_sha(spec: Spec = DEFAULT_SPEC) -> str:
    """The sha256 of the canonical spec: the `seats_sha` that goes into a cache key and into every placement record."""
    return spec.sha256()


def foundation_key(spec: Spec = DEFAULT_SPEC) -> str:
    """The part of a placement cache key the foundation makes (L-G1-7): "found-<sha12>".  A cache for "off" has no such part
    (see placement_key_part), so every cache written before G1-b stays valid."""
    return "found-" + seats_sha(spec)[:12]


def placement_key_part(foundation: str = "off", spec: Spec = DEFAULT_SPEC) -> str:
    """"" for foundation "off"; "found-<sha12>" for "on".  The cache-key hook ask.placement_key will call (not wired here)."""
    return "" if check_foundation(foundation) == "off" else foundation_key(spec)


# ------------------------------------------------------------------------------------------------------------
# the seam: the cross without its foundation seats
# ------------------------------------------------------------------------------------------------------------
def foundation_flat(seed: str, spec: Spec = DEFAULT_SPEC) -> Flat:
    """The L = 1 start of a seated cross: the data seed at the centre (D-1) and one particle at the innermost seat of each arm."""
    return (seed,) + tuple(token(p) for p in spec.arms)


def contract(flat: Flat, L: int) -> Tuple[Flat, int]:
    """OP-G1-4 the seam.  Every leg's innermost seat is the foundation; dropping it leaves a plain flat at L - 1 in which the
    data seat next to each foundation seat is next to the centre (the data words on both sides are neighbours).
    L = 1 (the data centre and the six particles) contracts to the centre with six empty seats at L = 1 (the lone seed)."""
    if len(flat) != 6 * L + 1:
        raise ValueError("flat does not match L")
    for a in range(geo.N_ARMS):
        if not is_constructed(flat[1 + a * L + L - 1]):
            raise ValueError("the innermost seat of leg %d is not a foundation seat" % a)
    if L == 1:
        return (flat[0],) + (None,) * geo.N_ARMS, 1
    out: List[Optional[str]] = [flat[0]]
    for a in range(geo.N_ARMS):
        out.extend(flat[1 + a * L: 1 + a * L + L - 1])
    return tuple(out), L - 1


def arms_of(flat: Flat, L: int) -> Tuple[str, ...]:
    """The particle of each leg (read from its innermost seat), in leg order."""
    return tuple(particle_of(flat[1 + a * L + L - 1]) for a in range(geo.N_ARMS))


# ------------------------------------------------------------------------------------------------------------
# adhesion
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True, order=True)
class Record:
    """One adhesion occurrence: the unit `unit` (tier `tier`) at [start, end) of the attribution-stripped sentence `sid` is immediately
    followed by the particle `particle` at [p_start, p_end).  The same fields as grammar.Attachment (RUN / WORD records are converted)."""
    tier: str
    sid: int
    start: int
    end: int
    unit: str
    particle: str
    p_start: int
    p_end: int

    def as_list(self) -> list:
        return [self.tier, self.sid, self.start, self.end, self.unit, self.particle, self.p_start, self.p_end]


def _is_char_head(c: str) -> bool:
    return sp._letterlike(c) and not is_function_unit(c, sp.CHAR)       # V2 for CHAR: a hiragana character is a function unit


def char_records(items: Iterable[Tuple[int, str]]) -> List[Record]:
    """CHAR adhesion records (L-G4-21): on the attribution-stripped text of every (sid, raw sentence), character by character.
    The char at i is a CHAR unit v (a letter that is not hiragana) and the char at i+1 is a particle of P7: nothing is skipped
    and no tokeniser is used (this function imports neither fugashi nor unidic)."""
    out: List[Record] = []
    for sid, raw in items:
        t = strip_attribution(raw)
        for i in range(len(t) - 1):
            if t[i + 1] in P7 and _is_char_head(t[i]):
                out.append(Record(sp.CHAR, sid, i, i + 1, t[i], t[i + 1], i + 1, i + 2))
    return sorted(out)


def base_items(space: sp.Space) -> List[Tuple[int, str]]:
    """(sid, raw text) of the BASE sentences of a space (memory sentences are not corpus text, L-547)."""
    return [(sid, t) for sid, (t, _) in enumerate(space.sentences) if space.kinds[sid] == sp.BASE]


def adhesion_records(space: sp.Space, tier: str, records=None) -> List[Record]:
    """Every adhesion occurrence of a tier with its evidence (sid, start, end, p_start, p_end), sorted.  RUN / WORD from the
    grammar records (pass `records` to reuse one records_of_space for both tiers), CHAR character by character."""
    if tier == sp.CHAR:
        return char_records(base_items(space))
    if tier not in RECORD_TIERS:
        raise ValueError("unknown tier %r" % (tier,))
    if records is None:
        from verantyx.line3 import grammar as gr         # lazily: see the note at the top
        records = gr.records_of_space(space)
    return sorted(Record(a.tier, a.sid, a.start, a.end, a.unit, a.particle, a.p_start, a.p_end) for a in records.attachments if a.tier == tier)


def check_trace(records: Sequence[Record], sentence_text) -> List[str]:
    """I-G1-1: every record re-read against its sentence.  `sentence_text(sid)` = the stored sentence text (the attribution is
    stripped here).  [] = all consistent: the unit and the particle surfaces are what the spans say, the particle is in P7, the unit
    is a content unit, no letter lies between them (CHAR: nothing at all lies between them)."""
    bad: List[str] = []
    for a in records:
        t = strip_attribution(sentence_text(a.sid))
        if t[a.start:a.end] != a.unit:
            bad.append("unit surface %r != %r (sid %d)" % (t[a.start:a.end], a.unit, a.sid))
        if t[a.p_start:a.p_end] != a.particle or a.particle not in P7:
            bad.append("particle surface %r != %r (sid %d)" % (t[a.p_start:a.p_end], a.particle, a.sid))
        if a.p_start < a.end or sp._has_letter(t[a.end:a.p_start]):
            bad.append("a letter lies between unit and particle (sid %d, %r)" % (a.sid, a.unit))
        if a.tier == sp.CHAR and (a.p_start != a.end or a.end - a.start != 1):
            bad.append("CHAR adhesion must be adjacent single characters (sid %d)" % a.sid)
        if is_function_unit(a.unit, a.tier):
            bad.append("head is a function unit: %r" % a.unit)
    return bad


class Adhesion:
    """adj_T(v, p) for one tier: exact integers, each backed by evidence.

    `counts` maps (unit, particle) to the number of distinct sids.  Build one from a space (`adhesion_of_space`), from records, or from
    an explicit mapping (toys and tests).  Units that are not in the table have adj 0.  `weighted(v)` is the row the search uses:
    numerator(p) * adj(v, p) for p in the ladder (centre relation first, then the six arms in axis order)."""

    def __init__(self, tier: str, counts: Mapping[Tuple[str, str], int], spec: Spec = DEFAULT_SPEC,
                 evidence: Optional[Mapping[Tuple[str, str], Sequence[Record]]] = None) -> None:
        self.tier = tier
        self.spec = spec
        clean: Dict[Tuple[str, str], int] = {}
        for (u, p), n in counts.items():
            if isinstance(n, bool) or not isinstance(n, int):
                raise TypeError("an adhesion count is an exact integer (no float): %r" % (n,))
            if p not in spec.ladder:
                raise ValueError("%r is not a particle of the foundation" % (p,))
            if n < 0:
                raise ValueError("an adhesion count is not negative")
            if n:
                clean[(u, p)] = n
        self.counts: Dict[Tuple[str, str], int] = dict(sorted(clean.items()))
        self._ev: Dict[Tuple[str, str], Tuple[Record, ...]] = {k: tuple(v) for k, v in (evidence or {}).items()}
        self._rows: Dict[str, Tuple[int, ...]] = {}
        nums = spec.numerators
        by_unit: Dict[str, List[Tuple[str, int]]] = {}
        for (u, p), n in self.counts.items():
            by_unit.setdefault(u, []).append((p, n))
        for u, ps in by_unit.items():
            row = [0] * len(nums)
            for p, n in ps:
                i = spec.ladder.index(p)
                row[i] = nums[i] * n
            self._rows[u] = tuple(row)

    @classmethod
    def from_records(cls, tier: str, records: Iterable[Record], spec: Spec = DEFAULT_SPEC) -> "Adhesion":
        sids: Dict[Tuple[str, str], set] = {}
        ev: Dict[Tuple[str, str], List[Record]] = {}
        for a in sorted(records):
            if a.tier != tier:
                raise ValueError("record of tier %s in the table of %s" % (a.tier, tier))
            if a.particle not in spec.ladder:
                continue
            sids.setdefault((a.unit, a.particle), set()).add(a.sid)
            ev.setdefault((a.unit, a.particle), []).append(a)
        return cls(tier, {k: len(v) for k, v in sids.items()}, spec, ev)

    # -- reading -------------------------------------------------------------------------------------------------
    def adj(self, unit: Optional[str], particle: str) -> int:
        return 0 if unit is None else self.counts.get((unit, particle), 0)

    def weighted(self, unit: Optional[str]) -> Tuple[int, ...]:
        """numerator(p) * adj(unit, p), ladder order (centre relation first); all zero for a unit without adhesion."""
        return self._zero if unit is None else self._rows.get(unit, self._zero)

    @property
    def _zero(self) -> Tuple[int, ...]:
        return (0,) * len(self.spec.ladder)

    def rows(self) -> Dict[str, Tuple[int, ...]]:
        """unit -> weighted row (only units with some adhesion): the table the search reads."""
        return self._rows

    def evidence(self, unit: str, particle: str) -> Tuple[Record, ...]:
        """Every occurrence behind adj(unit, particle), sorted (sid, start, ...); () when there is none or none was kept."""
        return self._ev.get((unit, particle), ())

    def units(self) -> List[str]:
        return sorted({u for u, _ in self.counts})

    def to_obj(self) -> dict:
        return {"format": SEATS_FORMAT, "tier": self.tier, "seats": self.spec.sha256(),
                "counts": [[u, p, n] for (u, p), n in sorted(self.counts.items())]}

    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.to_obj(), sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()


def adhesions_of_space(space: sp.Space, tiers: Sequence[str] = sp.TIERS, spec: Spec = DEFAULT_SPEC) -> Dict[str, Adhesion]:
    """The adhesion table of each requested tier (one records_of_space shared by RUN and WORD)."""
    rec = None
    if any(t in RECORD_TIERS for t in tiers):
        from verantyx.line3 import grammar as gr         # lazily: see the note at the top
        rec = gr.records_of_space(space)
    return {t: Adhesion.from_records(t, adhesion_records(space, t, rec), spec) for t in tiers}


def adhesion_of_space(space: sp.Space, tier: str, spec: Spec = DEFAULT_SPEC) -> Adhesion:
    return adhesions_of_space(space, (tier,), spec)[tier]


# ------------------------------------------------------------------------------------------------------------
# a(arrangement)
# ------------------------------------------------------------------------------------------------------------
def a_num(adh: Adhesion, flat: Flat, L: int) -> int:
    """a over the denominator: sum over data units v on the arm of particle p of numerator(p) * adj(v, p), plus numerator(は) *
    adj(the centre word, は).  The arm of a unit is the particle at the innermost seat of its leg."""
    spec = adh.spec
    total = 0
    c = flat[0]
    if c is not None and not is_constructed(c):
        total += spec.numerator(spec.centre) * adh.adj(c, spec.centre)
    for a in range(geo.N_ARMS):
        leg = flat[1 + a * L: 1 + (a + 1) * L]
        p = particle_of(leg[-1])
        n = spec.numerator(p)
        for v in leg[:-1]:
            if v is not None:
                total += n * adh.adj(v, p)
    return total


def a_exact(adh: Adhesion, flat: Flat, L: int) -> Fraction:
    """a as the exact Fraction a_num / den (display; the search compares the integer)."""
    return Fraction(a_num(adh, flat, L), adh.spec.den)
