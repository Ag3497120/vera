"""G3-f: the sliding-window placements read as FLAT crosses (ticket G3-f; docs/LINE3_LOCAL_DECISIONS.md section "G3-f", L-700..).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md, 「S1（G3-e2）の測定後の決定」, verbatim):
  「窓を「平らな十字」として読む（軸ごとではなく十字全体で一致を判定）」 -- the window placements stay; the reading is T10's: the three ratios
  (section walk / edge flow / placement binding) over the WHOLE cross (all arms, the arm labels play no part in the agreement), agreement =
  I-11 (one unit over the whole cross), the candidates = the path words of the adopted states; the per-axis answers of slide_ratios are attached
  as LABELS only.
Binding from before: decision 7 (the three ratios agree = stable), I-11, I-12 (moves), I-14/N-20 (a list is never shortened, no winner by order),
I-15 (stability), I-16 (the tier is read on its own), M-2 / N-18 (the user's amount of inference, counted here in WINDOWS), the evaluation
principle (candidates for users to grade, typed abstention), P-4 (every output word traces to the structure), OP-G3-1/2 (the window).

What this module is.  The thin adapter between the window index of slide_query (the placement records of slide_place, their intake, read order and
cap) and the flat reader of T5/T6/T7b, which is used UNCHANGED:  each strictly stable member of a window's class becomes a START (a flat tuple of
units, centre + 6 arms, exactly the world-view state of cycle.py); the starts of one window are the "members" of one cross `FlatCross`
(a duck-typed carrier: seed, L, members, twin_sets); `cycle._ask_tier_once(..., plan_override=...)` settles every start (moves = the 23 rotations
and the seat swaps, key I-12), pools the end states of the answering starts and adopts by the V3 rule (most sentences shared with the question),
`readout.read_out_result` reads the path words of the adopted states into T7b entries (merged sections, entries = word sets), and
`trace_check.trace_answer` traces every word.  Nothing of cycle / readout / trace_check / slide_* is changed; slide_query is only imported (its
window index, question intake, read order / cap, member choice, member cross).  Judgement points are numbered from L-700 (`members` "all" costs a start per member: L-715).
The pair count the flat reader reads on every edge is `evidence` "plain" (DEFAULT: the corpus tier's n_pair, which IS the slide's corpus-scope x count;
L-701) or "window" (the window's label-blind sum of the x, y and z counts, L-714).  Starts: the strictly stable members, pad cut, canonical legs (L-702);
a unit of both sentences keeps both seats ("both", default) or one ("n_only", L-703).
All numbers are int / Fraction (written "n/d"); there is no floating-point number and no random number; the canonical bytes are slide.canonical's.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import ask as A
from verantyx.line3 import cycle as cy
from verantyx.line3 import grammar as gr
from verantyx.line3 import readout as ro
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_place as SP
from verantyx.line3 import slide_query as SQ
from verantyx.line3 import slide_ratios as SR
from verantyx.line3 import trace_check as TC
from verantyx.line3.placement import Flat, canon
from verantyx.line3.space import TierSpace

FORMAT = "line3.slide_flat.v1"
TIER = SQ.TIER                                              # S1: RUN
MEMBERS: Tuple[str, ...] = SQ.MEMBERS                       # "all" | "representative"
STRICT_POLICIES: Tuple[str, ...] = SQ.STRICT_POLICIES       # "abstain" | "mark"
TWO_SEATS: Tuple[str, ...] = ("both", "n_only")             # L-703
EVIDENCES: Tuple[str, ...] = ("plain", "window")            # L-701 / L-714: the pair count the flat reader reads on every edge
READ_ORDERS: Tuple[str, ...] = SQ.READ_ORDERS
DEFAULT_BUDGET = cy.QueryBudget()                           # L-705: cycle's own search budget (512, 64); T7b's 64/8 ends every start of a window unsettled

ANSWER = cy.ANSWER
CHOICE = cy.CHOICE
UNKNOWN_NO_WINDOW = SQ.UNKNOWN_NO_WINDOW
UNKNOWN_NOT_READ = SQ.UNKNOWN_NOT_READ
UNKNOWN_NO_PATH = ro.UNKNOWN_NO_PATH

# the typed abstentions of one window (L-709): the member kinds of the flat cycle (L-106) + the three this module adds
RATIO_DISAGREEMENT = SR.RATIO_DISAGREEMENT
SECTION_DISAGREEMENT = SR.SECTION_DISAGREEMENT
POINTS_NOWHERE = SR.POINTS_NOWHERE
NOT_GROUNDED = SQ.NOT_GROUNDED
AMBIGUOUS_KIND = "ambiguous"
NO_FIXED_POINT_KIND = "no_fixed_point"
NO_PATH_KIND = "no_path"
MEMBER_CAP = "member_cap"           # starts of a window that `member_cap` left unsettled (a count in the tally / members_not_read, not an outcome)
UNSTABLE = SQ.UNSTABLE
NO_QUESTION_UNIT = SQ.NO_QUESTION_UNIT
MIXED = SQ.MIXED
_STATUS_KIND = {"ratio_disagreement": RATIO_DISAGREEMENT, "section_disagreement": SECTION_DISAGREEMENT,
                "points_nowhere": POINTS_NOWHERE, "ungrounded": NOT_GROUNDED, "mixed": MIXED}


def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


# --------------------------------------------------------------------------------------------------------------
# (1) a window member as a flat start  (L-701, L-702, L-703)
# --------------------------------------------------------------------------------------------------------------
def _sid_of_token(tok: str) -> Optional[int]:
    """The sentence a seat token names: unit + SEP + sid (a unit of both sentences, one seat per sentence), else None."""
    if SP.SEP not in tok:
        return None
    return int(tok.split(SP.SEP, 1)[1])


def member_flat(w: SQ.WindowRec, member: int, two_seat: str = "both") -> Tuple[int, Flat]:
    """(L_m, flat) of one member of the window's class, as the flat reader's state.
    * the record pads a member to the longest arm length L of the class (`member_pad` empty OUTER seats per arm, G3-c3 L-623); the pad is cut,
      the member is read at the length it was grown (and is stable) at, as slide_query.member_cross does (L-702);
    * a seat token `unit SEP sid` (a unit of both sentences has one seat per sentence) is read as the unit: `two_seat` "both" (default, L-703) keeps
      BOTH seats as the same string on two cells, which cycle's Reader takes natively (energy.py L-56: F and B of a unit sum over its cells, the pair
      of two cells of one unit adds nothing); "n_only" keeps one seat per unit: the one in the centre if that unit is at the centre, else the seat
      of the window's first sentence N, and empties the other."""
    if two_seat not in TWO_SEATS:
        raise ValueError("two_seat: %s" % " | ".join(TWO_SEATS))
    rec = w.doc
    L = int(rec["L"])
    pad = w.member_pad(member)
    f = rec["members"][member]
    lm = L - pad
    cut = [f[0]]
    for a in range(len(SR.ARM_NAMES)):
        cut.extend(f[1 + a * L + pad: 1 + (a + 1) * L])
    if two_seat == "n_only":
        first = w.window.sids[0]
        centre_unit = None if cut[0] is None else SP.unit_of(cut[0])
        out: List[Optional[str]] = []
        for i, t in enumerate(cut):
            if t is None:
                out.append(None)
                continue
            u = SP.unit_of(t)
            if _sid_of_token(t) is None:
                out.append(u)                                  # a unit of one sentence only: its one seat
            elif u == centre_unit:
                out.append(u if i == 0 else None)              # the unit at the centre keeps the centre seat
            elif _sid_of_token(t) == first:
                out.append(u)                                  # the seat of sentence N
            else:
                out.append(None)
        flat = tuple(out)
    else:
        flat = tuple(None if t is None else SP.unit_of(t) for t in cut)
    return lm, flat


@dataclass(frozen=True)
class Start:
    """One start of the flat cycle: the arm length, the canonical flat, and the members of the window's class that read as it (L-702)."""
    L: int
    flat: Flat
    members: Tuple[int, ...]


def _flat_sort_key(f: Flat) -> Tuple[str, ...]:
    return tuple("" if c is None else "x" + c for c in f)


def starts_of(w: SQ.WindowRec, selected: Sequence[int], qset: frozenset, two_seat: str = "both") -> Tuple[Tuple[Start, ...], int]:
    """(the starts, the number of members dropped by the member-level V1 gate).  Members that read as the same flat after the legs are put in
    the canonical order (placement.canon, the leg-to-arm assignment is a label of the flat reader, L-61 / L-111) are ONE start that remembers
    all of them.  A start that holds no question unit on any seat is not read (V1 at the level of the member, L-704)."""
    by: Dict[Tuple[int, Flat], List[int]] = {}
    gated = 0
    for i in selected:
        lm, flat = member_flat(w, i, two_seat)
        if qset and not (qset & {c for c in flat if c is not None}):
            gated += 1
            continue
        by.setdefault((lm, canon(flat, lm)), []).append(i)
    sts = [Start(lm, fl, tuple(ms)) for (lm, fl), ms in by.items()]
    sts.sort(key=lambda s: (s.L, _flat_sort_key(s.flat)))
    return tuple(sts), gated


@dataclass(frozen=True)
class FlatCross:
    """What cycle.read_cross / members_of read of a placement: seed, L, members (flats), twin_sets (none), expanded_size.  One per arm length
    of a window (a placement has one L, L-702)."""
    seed: str
    L: int
    members: Tuple[Flat, ...]
    twin_sets: Tuple[Tuple[str, ...], ...] = ()

    @property
    def expanded_size(self) -> int:
        return len(self.members)

    def expanded_members(self) -> Tuple[Flat, ...]:
        return self.members


class _Store:
    """cycle._ask_tier_once's `placements`: cross_for(seed)."""

    def __init__(self, crosses: Mapping[str, FlatCross]) -> None:
        self._c = dict(crosses)

    def cross_for(self, seed: str) -> FlatCross:
        return self._c[seed]


# --------------------------------------------------------------------------------------------------------------
# (2) the local space: the corpus RUN tier  (L-701)
# --------------------------------------------------------------------------------------------------------------
def flat_facts(index: SQ.WindowIndex) -> cy.TierFacts:
    """The facts the flat reader reads (evidence "plain", the default).  The window's local space is the corpus RUN tier itself: the slide's corpus-scope x
    count of a pair of seated units IS the tier's same-sentence count n_pair and its `before_x` IS p_pair (slide.verify_counts; tested here on the toy),
    n(u) and N are the corpus postings, E_Q is the facts' (cycle.Reader.enq).  Only what the cycle cannot read stays out: the slide (z) and grain (y)
    counts are properties of an ARM LABEL; the flat reader has no labels (L-701)."""
    f = index.__dict__.get("_flat_facts")
    if f is None:
        f = index.__dict__["_flat_facts"] = cy.TierFacts(index.space.tiers[index.tier])
    return f


@dataclass(frozen=True)
class WindowTier(TierSpace):
    """evidence "window" (L-714): the corpus RUN tier with ONE change, n_pair of two units of the window's pack = the window's evidence summed over the
    three axes and both directions, label-blind: n_x(u, v) + n_y(u, v) + n_y(v, u) + n_z(u, v) + n_z(v, u) of slide.counts (corpus scope).  A pair
    outside the pack, and n(u) = n_pair(u, u), are the corpus tier's.  The flat reader reads ONE pair function, so E_Q (n_pair of a question unit and a
    unit) carries the slide terms of the pairs inside the pack too (the per-axis reader's E_Q is the corpus one).  postings / sentence_units are the
    corpus tier's (the V3 adoption and the read-out's sentence ids stay on real sentences)."""
    base: Optional[TierSpace] = field(default=None, compare=False, repr=False)
    ev: Mapping[Tuple[str, str], int] = field(default_factory=dict, compare=False, repr=False)

    def n_pair(self, u: str, v: str) -> int:
        if u == v:
            return self.base.n(u)
        r = self.ev.get((u, v) if u <= v else (v, u))
        return r if r is not None else self.base.n_pair(u, v)

    def p_pair(self, u: str, v: str) -> int:
        raise NotImplementedError("the flat reader does not read the order count p")


def window_evidence(counts: SL.WindowCounts, tier: str) -> Dict[Tuple[str, str], int]:
    """The label-blind pair evidence of a window's pack (L-714): for each unordered pair of distinct units of `tier`, n_x + n_y(both ways) + n_z(both
    ways); pairs with none are absent (the corpus count, 0 or n_x, is then the fallback of WindowTier.n_pair)."""
    out: Dict[Tuple[str, str], int] = {}

    def put(a: str, b: str, n: int) -> None:
        if a != b and n:
            k = (a, b) if a <= b else (b, a)
            out[k] = out.get(k, 0) + n

    for (t, o, i), (bf, af) in counts.x.items():
        if t == tier and o < i:
            put(o, i, len(bf) + len(af))
    for (to, o, ti, i), src in counts.y.items():
        if to == tier and ti == tier:
            put(o, i, len(src))
    for (tu, u, tv, v), src in counts.z.items():
        if tu == tier and tv == tier:
            put(u, v, len(src))
    return out


class WindowFacts(cy.TierFacts):
    """cycle.TierFacts over a WindowTier that shares n, N, D and dq with the corpus facts (the postings are the same)."""

    def __init__(self, tier: WindowTier, base: cy.TierFacts) -> None:
        self.tier, self.N, self.n, self.D, self.dq = tier, base.N, base.n, base.D, base.dq
        self._np = {}


def window_tier(index: SQ.WindowIndex, w: SQ.WindowRec) -> WindowTier:
    t = index.space.tiers[index.tier]
    return WindowTier(t.name, t.sentence_units, t.postings, t.unit_filter, t, window_evidence(index.counts(w), index.tier))


def trace_tier(index: SQ.WindowIndex) -> TierSpace:
    """The tier trace_check reads for evidence "window" (L-714): the corpus tier plus one appended "pair sentence" per adjacent pair of the corpus
    (units of sentence N then of N+1; sid >= N), so that an edge evidenced by the slide (u in N, v in N+1) has "a sentence that holds both", as
    trace_check's rule (c) asks.  Real sentences come first, so the first sid of a unit and the first common sentence of a pair are real whenever one
    exists.  Used for the trace only; the reading never sees it."""
    t = index.__dict__.get("_flat_trace_tier")
    if t is None:
        base = index.space.tiers[index.tier]
        extra = []
        for pw in index.slide.pairs():
            a, b = pw.sids
            extra.append(tuple(base.sentence_units[a]) + tuple(base.sentence_units[b]))
        post = {u: list(p) for u, p in base.postings.items()}
        for j, us in enumerate(extra):
            for u in dict.fromkeys(us):
                post[u].append(base.N + j)
        t = index.__dict__["_flat_trace_tier"] = TierSpace(base.name, tuple(base.sentence_units) + tuple(extra),
                                                           {u: tuple(p) for u, p in post.items()}, base.unit_filter)
        index.__dict__["_flat_trace_pairs"] = tuple(tuple(pw.sids) for pw in index.slide.pairs())
    return t


# --------------------------------------------------------------------------------------------------------------
# (3) reading one window  (L-704 .. L-711)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class WindowFlatRead:
    window: int
    members_read: int                  # members of the class that became starts
    class_size: int
    starts: int                        # distinct canonical starts settled
    entries: Tuple[dict, ...]
    abstentions: Tuple[dict, ...]      # (window) with no entry, typed; at most one
    tally: Tuple[Tuple[str, int], ...] # member kinds of the flat cycle (candidate / none:<status> / ambiguous / no_fixed_point) + skips
    trace_checks: int
    trace_ok: bool
    digest: Optional[str]              # cycle's digest of the full search state of this window
    ms: int = 0


def _axis_label_of(read: SR.SlideRatios, ax: str) -> Tuple[str, Optional[str]]:
    """("answer", unit) | (abstention kind, None) for one axis of one member's per-axis read (a LABEL, never read back)."""
    a = read.answer(ax)
    if a is not None:
        return "answer", a.unit
    return read.abstention(ax).kind, None


def _axis_labels(index: SQ.WindowIndex, w: SQ.WindowRec, it: SQ.Intake, members: Sequence[int], cache: Dict[int, SR.SlideRatios],
                 agreement: str) -> dict:
    """The per-axis answers of slide_ratios on the placed members behind one entry, as labels (L-708): axis -> {"agreed": members whose axis
    agrees, "of": members, "units": {agreed unit: members}, "abstained": {kind: members}}.  Computed on the START member (the placement as
    seated on its arms), not on the end state: a move of the flat cycle takes a unit off the arm its axis label sits on."""
    ev = None
    tsp = index.space.tiers[index.tier]
    out: Dict[str, dict] = {}
    for i in members:
        r = cache.get(i)
        if r is None:
            if ev is None:
                ev = SR.counts_evidence(index.counts(w), index.tier)
            r = cache[i] = SR.read_axes(SQ.member_cross(w, i), ev, tsp, it.ctx, index.foundation, z_self_edges=True, agreement=agreement)
        for ax in SR.AXES:
            kind, u = _axis_label_of(r, ax)
            d = out.setdefault(ax, {"agreed": 0, "of": 0, "units": {}, "abstained": {}})
            d["of"] += 1
            if kind == "answer":
                d["agreed"] += 1
                d["units"][u] = d["units"].get(u, 0) + 1
            else:
                d["abstained"][kind] = d["abstained"].get(kind, 0) + 1
    return {ax: {"agreed": out[ax]["agreed"], "of": out[ax]["of"],
                 "units": {u: out[ax]["units"][u] for u in sorted(out[ax]["units"])},
                 "abstained": {k: out[ax]["abstained"][k] for k in sorted(out[ax]["abstained"])}} for ax in sorted(out)}


def _kind_of_count(key: str) -> Optional[str]:
    """cycle.TierResult.counts key -> a typed abstention kind (None: not a member outcome)."""
    if key == "candidate":
        return None
    if key.startswith("none:"):
        return _STATUS_KIND.get(key[5:], key[5:])
    if key in (cy.AMBIG, cy.NOFIX):
        return AMBIGUOUS_KIND if key == cy.AMBIG else NO_FIXED_POINT_KIND
    return None


def read_window_flat(index: SQ.WindowIndex, w: SQ.WindowRec, it: SQ.Intake, *, members: str = "all", strict: str = "abstain",
                     budget: cy.QueryBudget = DEFAULT_BUDGET, two_seat: str = "both", labels: bool = True,
                     label_agreement: str = "three", member_cap: Optional[int] = None, evidence: str = "plain") -> WindowFlatRead:
    """One window read flat.  (1) the members to read: the strictly stable members of the class (`strict` "abstain", the owner's rule, L-648) or all
    ("mark"), or the first member of each growth ("representative"; the count of members it stands for is in the entry, L-702); (2) their starts
    (`starts_of`); (3) `cycle._ask_tier_once` over one FlatCross per arm length (the window is one cross; the V3 adoption pools the end states of all
    its starts, both growths together); (4) `readout.read_out_result`; (5) T7b-shaped entries with the window labels; (6) the trace of every word.
    Nothing is selected between windows."""
    if members not in MEMBERS or strict not in STRICT_POLICIES or two_seat not in TWO_SEATS or evidence not in EVIDENCES:
        raise ValueError("members: %s; strict: %s; two_seat: %s; evidence: %s" % (MEMBERS, STRICT_POLICIES, TWO_SEATS, EVIDENCES))
    t0 = time.monotonic_ns()
    if evidence == "window":                                   # L-714: the pair count is the window's, label-blind
        tsp = window_tier(index, w)
        facts = WindowFacts(tsp, flat_facts(index))
        ttier = trace_tier(index)
    else:
        tsp = index.space.tiers[index.tier]
        facts = flat_facts(index)
        ttier = tsp
    sel, skipped = SQ.choose_members(w, members, strict)
    sts, gated = starts_of(w, sel, it.qset, two_seat)
    growth: Dict[str, int] = {}                               # the members each growth has among those that may be read (what a representative stands for)
    for i in range(w.class_size):
        if strict == "mark" or w.readable(i):
            growth[w.centre_side(i)] = growth.get(w.centre_side(i), 0) + 1
    growth = {sd: growth[sd] for sd in sorted(growth)}
    tally: Dict[str, int] = {}
    if skipped:
        tally[UNSTABLE] = skipped
    if gated:
        tally[NO_QUESTION_UNIT] = gated
    entries: List[dict] = []
    abst: List[dict] = []
    checks, ok, digest = 0, True, None
    read_members = sum(len(s.members) for s in sts)
    if sts:
        groups: Dict[int, List[Start]] = {}
        for s in sts:
            groups.setdefault(s.L, []).append(s)
        seeds: Dict[str, FlatCross] = {}
        origin: Dict[Tuple[str, int], Tuple[int, ...]] = {}
        for lm in sorted(groups):
            seed = "W%d/L%d" % (w.n, lm)
            seeds[seed] = FlatCross(seed, lm, tuple(s.flat for s in groups[lm]))
            for k, s in enumerate(groups[lm]):
                origin[(seed, k)] = s.members
        names = tuple(sorted(seeds))
        plan = cy.ReadPlan((("window", names),), names, (), len(names), None, False, 0)
        res = cy._ask_tier_once(tsp, it.question, _Store(seeds), units=it.units, facts=facts, plan_override=plan, budget=budget,
                                member_cap=member_cap, observe=False)
        digest = res.state_digest
        if res.counts["members_total"] > res.counts["members_read"]:   # `member_cap` (per arm length) left starts unsettled: counted, never silent
            tally[MEMBER_CAP] = res.counts["members_total"] - res.counts["members_read"]
        for k, v in res.counts.items():
            if k in ("candidate", "ambiguous", "no_fixed_point") or k.startswith("none:"):
                tally[k] = tally.get(k, 0) + v
        if res.candidates:
            ans = ro.read_out_result(tsp, res, facts)
            if ans.entries:
                _tr, rep = TC.trace_answer(ttier, ans)
                checks, ok = rep.words_checked, rep.ok
                # words whose edge is evidenced ONLY by a constructed pair sentence (evidence "window"; a real sentence always sorts first, L-714)
                edge_words = sum(1 for t in _tr if t.ok and t.edge_sid is not None)            # path words that close an edge (all states' paths)
                constructed = sum(1 for t in _tr if t.ok and t.edge_sid is not None and t.edge_sid >= tsp.N) if evidence == "window" else 0
                cache: Dict[int, SR.SlideRatios] = {}
                for e in ans.entries:
                    om = sorted({m for si in e.origins for m in origin[(ans.states[si].ref.seed, ans.states[si].ref.member)]})
                    sides: Dict[str, int] = {}
                    for m in om:
                        sd = w.centre_side(m)
                        sides[sd] = sides.get(sd, 0) + 1
                    cs = "both" if len(sides) > 1 else next(iter(sides))
                    sids = set(e.source_sids)
                    if evidence == "window":                       # L-714: an edge the slide evidences cites the sentence pairs it counts
                        cz = index.counts(w).z
                        for arr in e.arrangements:
                            for p in arr.paths:
                                for x, y, _ss in p.edges:
                                    for row in cz.get((index.tier, x, index.tier, y), ()) + cz.get((index.tier, y, index.tier, x), ()):
                                        sids.update(row[:2])
                    entries.append({
                        "tier": index.tier, "structure": "slide_flat", "label": "slide:flat", "words": list(e.words),
                        "arrangements": e.count, "centres": list(e.centres), "stability": _fs(e.stability),
                        "source_sids": sorted(sids),
                        "window": {"n": w.n, "title": w.window.title, "sids": list(w.window.sids), "idx": list(w.window.idx),
                                   "constructed": w.constructed},
                        "centre_sentence": cs, "centre_sentences": {sd: sides[sd] for sd in sorted(sides)},
                        "stable_strict": all(w.readable(m) for m in om),
                        "origin_members": om, "members_read": read_members, "class_size": w.class_size, "starts": len(sts), "growth_members": growth,
                        "members_not_read": {kd: tally[kd] for kd in sorted(tally) if kd in (UNSTABLE, NO_QUESTION_UNIT, MEMBER_CAP)}, "evidence": evidence,
                        "axis_labels": _axis_labels(index, w, it, om, cache, label_agreement) if labels else None,
                        "trace": {"ok": ok, "words_checked": rep.words_checked, "words_traced": rep.words_traced,
                                  "edge_words": edge_words, "constructed_edge_words": constructed}})
            else:
                tally[NO_PATH_KIND] = 1
    if not entries:
        kinds: Dict[str, int] = {}
        for k, v in tally.items():
            kd = k if k in (UNSTABLE, NO_QUESTION_UNIT, NO_PATH_KIND) else _kind_of_count(k)
            if kd is not None:
                kinds[kd] = kinds.get(kd, 0) + v
        kinds = {k: kinds[k] for k in sorted(kinds)}
        abst.append({"window": w.n, "label": "slide:flat", "kind": next(iter(kinds)) if len(kinds) == 1 else MIXED, "kinds": kinds,
                     "members": w.class_size, "starts": len(sts)})
    return WindowFlatRead(w.n, read_members, w.class_size, len(sts), tuple(entries), tuple(abst),
                          tuple(sorted(tally.items())), checks, ok, digest, (time.monotonic_ns() - t0) // 1000000)


# --------------------------------------------------------------------------------------------------------------
# (4) the result: entries, typed abstentions, the verdict, the bytes  (L-709 .. L-712)
# --------------------------------------------------------------------------------------------------------------
def verdict_of(n_entries: int, plan: SQ.Plan, abstentions: Sequence[Mapping]) -> str:
    """ANSWER = exactly one entry, CHOICE = a list (as ask.combine / slide_query.verdict_of).  No entry: UNKNOWN_NO_WINDOW (no window holds a
    question unit), UNKNOWN_NOT_READ (the cap read none), else typed by the abstention kinds met, in cycle._verdict_from's reporting precedence
    (not a winner choice): ambiguous, no fixed point, ratio disagreement (with cycle's member status "mixed", as _verdict_from reads
    "none:mixed"), section disagreement, then slide_query's unstable (strict), no path, no evidence (L-709)."""
    if n_entries == 1:
        return ANSWER
    if n_entries > 1:
        return CHOICE
    if plan.candidates == 0:
        return UNKNOWN_NO_WINDOW
    if not plan.read:
        return UNKNOWN_NOT_READ
    met = {k for a in abstentions for k in a["kinds"]}
    if AMBIGUOUS_KIND in met:
        return cy.AMBIGUOUS
    if NO_FIXED_POINT_KIND in met:
        return cy.UNKNOWN_NO_FIXED_POINT
    if RATIO_DISAGREEMENT in met or MIXED in met:          # cycle._verdict_from: "none:mixed" is typed with the ratio disagreement
        return cy.UNKNOWN_RATIO_DISAGREEMENT
    if SECTION_DISAGREEMENT in met:
        return cy.UNKNOWN_SECTION_DISAGREEMENT
    if UNSTABLE in met:
        return SQ.UNKNOWN_UNSTABLE
    if NO_PATH_KIND in met:
        return UNKNOWN_NO_PATH
    return cy.UNKNOWN_NO_EVIDENCE


@dataclass(frozen=True)
class FlatAnswer:
    question: str
    intake: SQ.Intake
    plan: SQ.Plan
    reads: Tuple[WindowFlatRead, ...]               # every window read, in read order
    entries: Tuple[dict, ...]                       # in read order: window, then the readout's order (word set)
    abstentions: Tuple[dict, ...]
    verdict: str
    config: Mapping[str, object]
    spec: Mapping[str, str]
    sentences: Mapping[int, Tuple[str, str]]
    effort: Optional[str]
    ms: int = 0

    @property
    def windows_read(self) -> int:
        return len(self.reads)

    @property
    def partial(self) -> bool:
        return self.plan.partial

    def read_obj(self) -> dict:
        o = self.plan.read_obj()
        o.update({"effort": self.effort, "windows_read": len(self.reads), "candidate_windows_read": len(self.plan.read)})
        return o

    def abstention_counts(self) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for a in self.abstentions:
            c[a["kind"]] = c.get(a["kind"], 0) + 1
        return {k: c[k] for k in sorted(c)}

    def answer_obj(self) -> dict:
        one = self.verdict == ANSWER
        ents = list(self.entries)
        sids = sorted({s for e in ents for s in e["source_sids"]})
        return {"verdict": self.verdict, "structure": "slide_flat", "tiers": [TIER], "listed": len(ents),
                "windows_read": len(self.reads), "partial": self.plan.partial, "grammar_form": self.intake.form_obj(),
                "read": self.read_obj(),
                "answer": ({"tier": TIER, "label": ents[0]["label"], "path_words": list(ents[0]["words"]), "window": ents[0]["window"],
                            "source_sids": ents[0]["source_sids"], "reference_centres": ents[0]["centres"]} if one else None),
                "entries": ents, "abstentions": list(self.abstentions), "abstention_counts": self.abstention_counts(),
                "sources": [{"sid": s, "text": self.sentences[s][0], "source": self.sentences[s][1]} for s in sids]}

    def thought_obj(self) -> dict:
        it = self.intake
        reads = [{"window": r.window, "members_read": r.members_read, "class_size": r.class_size, "starts": r.starts,
                  "trace_checks": r.trace_checks, "trace_ok": r.trace_ok, "state_digest": r.digest, "tally": {k: n for k, n in r.tally}}
                 for r in self.reads]
        return {"format": FORMAT, "question": self.question, "units_cut": list(it.all_units), "units": list(it.units),
                "first_layer": list(it.ctx.qcross.units), "grammar": it.reading.to_obj(), "grammar_form": it.form_obj(),
                "config": dict(self.config), "spec": dict(self.spec),
                "rule": ("windows that hold a question unit are read in the read order of the config; each strictly stable member of a window's "
                         "class is a start of the flat cycle (the cycle of T5, unchanged: moves, the three ratios over the WHOLE cross, agreement = "
                         "one unit, V3 adoption of the end states, path words as T7b entries); the per-axis answers of slide_ratios on the placed "
                         "members are attached as labels and decide nothing; entries are never merged across windows; what is not admitted is a "
                         "typed abstention"),
                "plan": {"read": self.plan.read_obj(), "blocks": [b.to_obj() for b in self.plan.blocks],
                         "read_windows": list(self.plan.read), "unread_windows": list(self.plan.unread)},
                "windows": reads, "abstentions": list(self.abstentions)}

    def to_json_obj(self) -> dict:
        return json.loads(self.to_bytes().decode("utf-8"))

    def to_bytes(self) -> bytes:
        return SL.canonical({"answer": self.answer_obj(), "thought": self.thought_obj()})


def ask_flat(index, question: str, *, effort: Optional[str] = None, nodes: Optional[int] = None, windows: Optional[SQ.WindowIndex] = None,
             members: str = "all", strict: str = "abstain", budget: cy.QueryBudget = DEFAULT_BUDGET, two_seat: str = "both",
             read_order: str = "qcount_first", labels: bool = True, label_agreement: str = "three", member_cap: Optional[int] = None,
             evidence: str = "plain", cache_dir: Optional[str] = None, workers: int = 1, place_kw: Optional[Mapping] = None, z_deep: Optional[str] = None) -> FlatAnswer:
    """The flat read of the windows that hold a question unit (V1), in the read order and under the cap (windows) of slide_query / T7b.
    `index` is an ask.Index (its window index is built / loaded like slide_query.ask_slide's) or a slide_query.WindowIndex.  Defaults: members
    "all" (every strictly stable member: slow, see L-715; "representative" = the first member of each growth), search budget cycle's QueryBudget() (512, 64),
    both seats of a shared unit, read order qcount_first, evidence "plain" (the corpus tier's n_pair; "window" = the window's label-blind counts, L-714)."""
    if members not in MEMBERS or strict not in STRICT_POLICIES or two_seat not in TWO_SEATS or read_order not in READ_ORDERS:
        raise ValueError("members: %s; strict: %s; two_seat: %s; read_order: %s" % (MEMBERS, STRICT_POLICIES, TWO_SEATS, READ_ORDERS))
    if evidence not in EVIDENCES:
        raise ValueError("evidence: %s" % " | ".join(EVIDENCES))
    if label_agreement not in SR.AGREEMENTS:
        raise ValueError("label_agreement must be one of %r" % (SR.AGREEMENTS,))
    if z_deep is not None and z_deep not in SQ.Z_DEEPS:
        raise ValueError("z_deep must be one of %r" % (SQ.Z_DEEPS,))
    t0 = time.monotonic_ns()
    wi = windows if windows is not None else SQ.window_index_for(index, cache_dir=cache_dir, workers=workers, place_kw=place_kw,
                                                                 z_deep=z_deep or "slide")
    if z_deep is not None and wi.z_deep != z_deep:
        raise ValueError("the window index was placed with z_deep %r, not %r (a different slide spec: build another index)" % (wi.z_deep, z_deep))
    name, cap, _lv = A.resolve_effort(effort, nodes)
    it = SQ.intake(wi, question)
    plan = SQ.plan_windows(wi, it, hold="seats", standins="off", within="qcount", cap=cap, read_order=read_order)
    kw = dict(members=members, strict=strict, budget=budget, two_seat=two_seat, labels=labels, label_agreement=label_agreement,
              member_cap=member_cap, evidence=evidence)
    reads = tuple(read_window_flat(wi, wi.by_n[n], it, **kw) for n in plan.read)
    entries = tuple(e for r in reads for e in r.entries)
    abst = tuple(a for r in reads for a in r.abstentions)
    cited = sorted({s for e in entries for s in e["source_sids"]})
    cfg = {"members": members, "strict": strict, "two_seat": two_seat, "read_order": read_order, "tier": TIER, "effort": name,
           "node_budget": cap, "budget": {"max_states": budget.max_states, "max_ends": budget.max_ends}, "member_cap": member_cap,
           "label_agreement": label_agreement, "labels": labels, "z_deep": wi.z_deep, "evidence": evidence,
           "state_rule": "query_share", "member_rule": "stable_any"}
    spec = {"corpus_sha256": wi.space.sha256(), "slide_spec_sha256": wi.slide.spec.sha256(), "place_spec_sha256": wi.spec.sha256(),
            "grammar_foundation_sha256": gr.foundation_sha()}
    return FlatAnswer(question, it, plan, reads, entries, abst, verdict_of(len(entries), plan, abst), cfg, spec,
                      {s: wi.space.sentences[s] for s in cited}, name, (time.monotonic_ns() - t0) // 1000000)
