"""T8 layers (matryoshka) of the line-3 build: stack when the energy is no longer stable, at query time.

Binding decisions (ops/decisions/2026-10-06_line3_faithful_build.md; line 3 of vera1.txt):
  line 3   "第一層で推論を終えて答えが出たものを次の層に流して次の層で付け足しや探索などを行いそれを繰り返して
        拡張推論を行えるようにする。その際に初期のクエリをつけるかどうかが焦点でもある".
  I-20   build BOTH (the initial query passed on = variant A / not passed = variant B) and measure.
  decision 9 / I-18 / N-08 / N-11   stack when the energy is no longer stable; the check (and the optimisation) happens
        WHEN A QUESTION IS ASKED (no background process); when the stability collapses in the middle of a question,
        stack on the spot and go on answering in the upper layer; the internal state is shown (thought.layers).
  N-05   when stacking, the state that was stable just before is restored and adopted: placement.build_cross never
        keeps the step that broke (stop == "budget"), so Placement.members IS that restored state; a query-time
        collapse (a member without a fixed point) stacks that member's pre-query stable state, which is the same state.
  N-06 / N-07 / I-19 / M-1(c)   every stable state goes up; "full" = capacity reached or unstable; the upper layer holds
        many lower stable states arranged as ONE large stereo cross by the SAME stability rule (the same
        placement.build_cross run on the space of bundles); a bundled state's quantity = the UNION of the sentences of
        the words on it (TierSpace.postings_union); pre-collapse states line up side by side; when an upper cross is
        about to overflow (stop == "budget") the crosses that were needed are bundled again into a larger cross
        (the next layer; 「十字が宇宙」).
  N-12   re-read the lower layers until no layer changes (fixed point across layers) or a typed budget stop.
  N-19   an upper layer reads out the elements (lower crosses) along its path: a path of bundles is expanded into the
        words of the lower crosses on it; the trace goes down to the base sentence.
  M-2    the user is offered "compress the lower-structure results (faster)" vs "stack at the same granularity (higher
        precision)" (LayerOptions.granularity, shown in thought.layers.choice with both sizes).
  M-5(c) the inner query crosses (units from the 7th on) are added when passing to the next layer.
  T7b    the effort presets bound the layer work too (LAYER_EFFORTS) and the layers' reads are marked partial.
  owner's principle (2026-10-07)   candidates are shown so that real users can grade them: the entries are
        LABELLED by layer (and variant) and never merged, summed or ranked across layers.

Local decisions (docs/LINE3_LOCAL_DECISIONS.md, L-230..): see there.  Everything is exact, deterministic and independent
of the hash seed.  `ask.ask` is layer 0 only (T7b, untouched); `ask_layered` and the command (layers ON by default since T8b, L-250) add the layers.
Upper-layer candidates show only the path words read under the question (L-251); the T8 bags stay as candidate='bag'.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import ask as A
from verantyx.line3 import cycle as cy
from verantyx.line3 import placement as pl
from verantyx.line3 import readout as ro
from verantyx.line3 import trace_check as tc
from verantyx.line3.placement import Flat, from_cross
from verantyx.line3.space import TierSpace

LAYER_FORMAT = "line3.layers.v1"
VARIANTS = ("A", "B")                       # I-20: A = initial query + the lower answer, B = the lower answer only
GRANULARITIES = ("same", "compress")        # M-2
DOWN_QUERIES = ("question", "seed+question")  # L-252: what the lower cross is read under
CANDIDATES = ("path", "bag")                # L-250: what an upper-layer candidate shows (path words read under the question / N-19 bag)
FEEDBACKS = ("none", "down")                # N-12 re-read: see L-239
UNKNOWN_NOTHING_TO_PASS = "UNKNOWN_NOTHING_TO_PASS"
UNKNOWN_NO_FIXED_POINT_LAYERS = "UNKNOWN_NO_FIXED_POINT_LAYERS"


def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


# --------------------------------------------------------------------------
# bounds (T7b: the effort bounds the layer work, L-238)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LayerBounds:
    max_layers: int                    # upper layers built at most (a further need is reported, not built)
    nodes: Optional[int]               # upper crosses read per layer (None = every query bundle)
    pass_cap: Optional[int]            # bundles passed up per layer (None = all)
    pool_groups: Optional[int]         # share-groups in the pool of an upper cross (None = all)
    members: Optional[int]             # members of an upper cross's class read (None = all; a prefix, marked partial)
    level: str                         # placement budget level of an upper cross
    rounds: int                        # re-read rounds (N-12), a typed stop when exceeded

    def to_json_obj(self) -> dict:
        return {"max_layers": self.max_layers, "nodes": self.nodes, "pass_cap": self.pass_cap,
                "pool_groups": self.pool_groups, "members": self.members, "level": self.level, "rounds": self.rounds}


LAYER_EFFORTS: Dict[str, LayerBounds] = {
    "fast": LayerBounds(1, 4, 8, 3, 8, "low", 2),
    "standard": LayerBounds(2, 10, 16, 6, 24, "mid-low", 4),
    "full": LayerBounds(3, 24, 32, 12, 64, "mid", 16),
}


def bounds_for(effort: Optional[str] = None, nodes: Optional[int] = None) -> LayerBounds:
    """L-238: the layer bounds that go with the lower effort.  An explicit node budget N keeps the `fast` shape with
    N upper crosses; no effort (the whole read) = `full`.  Even `full` bounds the upper layers (24 crosses, 64 class
    members each): the twin-expanded class of an upper cross can hold thousands of members (a measured 2016 members =
    3.5 minutes for ONE cross) and a bound that the user cannot lift keeps a question from running for hours; the read
    is marked partial with the counts."""
    if nodes is not None:
        b = LAYER_EFFORTS["fast"]
        return LayerBounds(b.max_layers, nodes, max(nodes, b.pass_cap or 0), b.pool_groups, b.members, b.level, b.rounds)
    return LAYER_EFFORTS[effort if effort in LAYER_EFFORTS else "full"]


@dataclass(frozen=True)
class LayerOptions:
    variants: Tuple[str, ...] = ("A",)            # I-20; L-250: the owner's default is A (B stays an option)
    granularity: str = "compress"                 # M-2; L-250: the owner's default is compress ("same" stays an option)
    feedback: str = "none"                        # N-12 (L-239)
    bounds: LayerBounds = LAYER_EFFORTS["standard"]
    candidate: str = "path"                       # L-251: "path" = only the path words read under the question; "bag" = T8's
    down_query: str = "question"                  # L-252: "question" = the upper layer's own question units; "seed+question" = the bundle's seed first

    def __post_init__(self) -> None:
        if not self.variants or any(v not in VARIANTS for v in self.variants):
            raise ValueError("variants: a non-empty subset of %s" % (VARIANTS,))
        if self.granularity not in GRANULARITIES:
            raise ValueError("granularity: %s" % " | ".join(GRANULARITIES))
        if self.feedback not in FEEDBACKS:
            raise ValueError("feedback: %s" % " | ".join(FEEDBACKS))
        if self.down_query not in DOWN_QUERIES:
            raise ValueError("down_query: %s" % " | ".join(DOWN_QUERIES))
        if self.candidate not in CANDIDATES:
            raise ValueError("candidate: %s" % " | ".join(CANDIDATES))
        if self.bounds.max_layers < 1 or self.bounds.rounds < 1:
            raise ValueError("bounds: max_layers and rounds must be >= 1")


# --------------------------------------------------------------------------
# the space of bundles (M-1(c): quantity = union of the sentences of the words on the bundled state)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class BundleTier(TierSpace):
    """A TierSpace whose units are bundled stable states.  postings[b] = the UNION of the sentences of every word of
    the state b; the order of a sentence is by the earliest position of a word of b in it.  p_pair is computed from
    those earliest positions with a STRICT comparison (two bundles that both hold the first word do not count
    for either side), so no order label can bias a key."""
    first_pos: Mapping[str, Mapping[int, int]] = field(default_factory=dict, compare=False, repr=False)

    def p_pair(self, u: str, v: str) -> int:
        fu, fv = self.first_pos[u], self.first_pos[v]
        if len(fu) > len(fv):
            c = 0
            for sid, pv in fv.items():
                pu = fu.get(sid)
                if pu is not None and pu < pv:
                    c += 1
            return c
        return sum(1 for sid, pu in fu.items() if sid in fv and pu < fv[sid])


def bundle_id(k: int, lower: str) -> str:
    return "⟦%d:%s⟧" % (k, lower)


def placed_units(p: pl.Placement) -> Tuple[str, ...]:
    """The units a stable state holds (representative arrangement plus every twin), sorted (a label)."""
    s = {c for c in from_cross(p.cross) if c is not None}
    for t in p.twin_sets:
        s.update(t)
    return tuple(sorted(s))


def build_bundle_tier(base: TierSpace, wordsets: Mapping[str, frozenset], pos_of: Callable[[str], Mapping[int, int]]) -> BundleTier:
    post: Dict[str, Tuple[int, ...]] = {}
    fpos: Dict[str, Dict[int, int]] = {}
    per_sid: Dict[int, List[Tuple[int, str]]] = {}
    for b in sorted(wordsets):
        fp: Dict[int, int] = {}
        for w in sorted(wordsets[b]):
            for sid, ps in pos_of(w).items():
                if sid not in fp or ps < fp[sid]:
                    fp[sid] = ps
        post[b] = tuple(sorted(fp))
        fpos[b] = fp
        for sid, ps in fp.items():
            per_sid.setdefault(sid, []).append((ps, b))
    su = tuple(tuple(b for _, b in sorted(per_sid.get(sid, ()))) for sid in range(base.N))
    return BundleTier(base.name, su, post, None, fpos)


class Layer:
    """An upper layer k >= 1 of one tier: the space of bundles, its facts and weights, and the on-demand upper crosses
    (cached; the result never depends on the cache, L-07).  `lower_units[b]` = the units of the lower layer on the
    bundled state b; `words[b]` = the base words under b."""

    def __init__(self, k: int, base: TierSpace, lower_units: Mapping[str, Tuple[str, ...]],
                 words: Mapping[str, frozenset], pos_of, bounds: LayerBounds) -> None:
        self.k = k
        self.lower_units = dict(lower_units)
        self.words = dict(words)
        self.space = build_bundle_tier(base, self.words, pos_of)
        self.facts = cy.TierFacts(self.space)
        self.w = pl.Weights(self.space)
        self.bounds = bounds
        self.budget = pl.budget_level(bounds.level)
        self._cross: Dict[str, pl.Placement] = {}
        self._down: Dict[tuple, Tuple[Optional[ro.PathAnswer], tuple]] = {}      # L-251: reads of this layer's crosses
        self.builds = 0

    def cross_for(self, seed: str) -> pl.Placement:
        p = self._cross.get(seed)
        if p is None:
            self.builds += 1
            p = self._cross[seed] = pl.build_cross(self.space, seed, self.w, budget=self.budget,
                                                   pool_groups=self.bounds.pool_groups)
        return p

    def n_bundles(self) -> int:
        return len(self.words)


class LayerStack:
    """Caches of one tier of one index: the base word positions and the all-states layer 1 ("same granularity")."""

    def __init__(self, base: TierSpace, store, facts: Optional[cy.TierFacts] = None) -> None:
        self.base, self.store = base, store
        self.facts = facts if facts is not None else cy.TierFacts(base)
        self._down: Dict[tuple, Tuple[Optional[ro.PathAnswer], tuple]] = {}      # L-251: reads of lower crosses (a pure cache)
        self._pos: Dict[str, Dict[int, int]] = {}
        self._layer1: Dict[Tuple[str, str, int, Optional[int]], Layer] = {}
        self.layer1_build_ms: Dict[str, int] = {}

    def pos_of(self, w: str) -> Mapping[int, int]:
        r = self._pos.get(w)
        if r is None:
            su = self.base.sentence_units
            r = self._pos[w] = {sid: su[sid].index(w) for sid in self.base.postings[w]}
        return r

    def layer1(self, granularity: str, seeds: Iterable[str], bounds: LayerBounds) -> Layer:
        """Layer 1 over the stable states of `seeds` (compress) or of every unit (same granularity, cached)."""
        if granularity == "same":
            key = ("same", bounds.level, bounds.pool_groups or -1, None)
            lay = self._layer1.get(key)
            if lay is None:
                t0 = time.monotonic_ns()
                lay = self._layer1[key] = self._make1(self.base.units(), bounds)
                self.layer1_build_ms["same"] = (time.monotonic_ns() - t0) // 1000000
            return lay
        return self._make1(sorted(set(seeds)), bounds)

    def _make1(self, seeds: Sequence[str], bounds: LayerBounds) -> Layer:
        lower, words = {}, {}
        for s in seeds:
            us = placed_units(self.store.cross_for(s))
            lower[bundle_id(1, s)] = us
            words[bundle_id(1, s)] = frozenset(us)
        return Layer(1, self.base, lower, words, self.pos_of, bounds)

    def layer_above(self, k: int, lower: Layer, read_seeds: Sequence[str], bounds: LayerBounds) -> Layer:
        """Layer k from the upper crosses of `lower` that were read (the stable states this question needed)."""
        lu, words = {}, {}
        for b in sorted(read_seeds):
            us = placed_units(lower.cross_for(b))
            lu[bundle_id(k, b)] = us
            words[bundle_id(k, b)] = frozenset().union(*(lower.words[u] for u in us))
        return Layer(k, self.base, lu, words, self.pos_of, bounds)


def stack_of(index: "A.Index", tier: str) -> LayerStack:
    d = getattr(index, "_t8_stacks", None)
    if d is None:
        d = index._t8_stacks = {}
    s = d.get(tier)
    if s is None:
        s = d[tier] = LayerStack(index.space.tiers[tier], index.stores[tier], index.facts[tier])
    return s


# --------------------------------------------------------------------------
# energy order and node budget of a layer (M-2(a))
# --------------------------------------------------------------------------
def take_by_energy(units: Sequence[str], rq: Callable[[str], int], cap: Optional[int]) -> Tuple[Tuple[str, ...], int, int]:
    """Order by rq descending; equal values are taken together or not at all.  Returns (taken in that order, left,
    size of the first tied group that did not fit)."""
    by: Dict[int, List[str]] = {}
    for u in dict.fromkeys(units):
        by.setdefault(rq(u), []).append(u)
    out: List[str] = []
    total = sum(len(v) for v in by.values())
    for val in sorted(by, reverse=True):
        g = sorted(by[val])
        if cap is not None and len(out) + len(g) > cap:
            return tuple(out), total - len(out), len(g)
        out.extend(g)
    return tuple(out), 0, 0


# --------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LayerEntry:
    """One candidate of an upper layer: the bundles on the section paths / centre (the layer's own words) and the BASE
    words under them (N-19), labelled by tier, layer and variant."""
    tier: str
    layer: int
    variant: str
    words: Tuple[str, ...]                 # base words under the bundles, sorted
    bundles: Tuple[str, ...]               # the bundles of the entry (path words + centre), sorted
    centres: Tuple[str, ...]               # the base seed word of each centre bundle (a reference)
    stability: Fraction
    arrangements: int
    source_sids: Tuple[int, ...]           # sentences evidencing a step between bundles
    # L-251 (candidate="path"): `words` are the path words read under the question from the lower crosses packed in the
    # bundles (never the whole lower state); word_sources = per word the base sentences of the steps into/out of it;
    # path_from = which lower cross was read for which bundle.  None / () in "bag" mode (the bytes of T8 are unchanged).
    word_sources: Optional[Tuple[Tuple[str, Tuple[int, ...]], ...]] = None
    path_from: Tuple[dict, ...] = ()
    path_answers: Tuple[Tuple[int, ro.PathAnswer], ...] = field(default=(), compare=False, repr=False)   # (layer, read) for the trace

    def key(self) -> Tuple[str, int, str, Tuple[str, ...], Tuple[str, ...]]:
        return (self.tier, self.layer, self.variant, self.words, self.bundles)

    def to_json_obj(self) -> dict:
        o = {"tier": self.tier, "layer": self.layer, "variant": self.variant, "words": list(self.words),
             "bundles": list(self.bundles), "centres": list(self.centres), "stability": _fs(self.stability),
             "arrangements": self.arrangements, "source_sids": list(self.source_sids)}
        if self.word_sources is not None:
            o["candidate"] = "path"
            o["word_sources"] = {w: list(ss) for w, ss in self.word_sources}
            o["path_from"] = [dict(d) for d in self.path_from]
        return o


@dataclass(frozen=True)
class LayerRun:
    """One layer of one variant for one tier."""
    tier: str
    variant: str
    k: int
    granularity: str
    n_bundles: int                          # bundles in the layer (the other granularity's size is in `choice`)
    query_units: Tuple[str, ...]            # the bundles on the query cross (attached order)
    passed_words: Tuple[str, ...]           # the lower answer's units passed up (before the cap)
    passed_left: int                        # passed units dropped by the pass cap
    read: Tuple[str, ...]
    left_unread: int
    partial: bool
    verdict: str
    members_read: int
    members_total: int
    result: Optional[cy.TierResult]
    answer: Optional[ro.PathAnswer]
    entries: Tuple[LayerEntry, ...]
    full_crosses: Tuple[str, ...]           # upper crosses read whose growth stopped by the budget (capacity reached)
    no_fixed_point: int                     # members without a fixed point (query-time collapse at this layer)
    layer_limit: bool                       # the next layer is needed but the effort's bound stopped it
    trace: dict
    ms: int = 0
    up_bundles: Optional[Tuple[str, ...]] = None     # L-251: the bundles of the answer passed to the next layer (path mode)
    candidate: str = "bag"
    without_path_words: int = 0                       # L-251: upper entries from whose lower crosses the question read no path

    def to_json_obj(self) -> dict:
        o = self._json()
        if self.candidate == "path":
            o["candidate"] = "path"
            o["entries_without_path_words"] = self.without_path_words
        return o

    def _json(self) -> dict:
        return {"tier": self.tier, "variant": self.variant, "layer": self.k, "granularity": self.granularity,
                "bundles": self.n_bundles, "query_bundles": list(self.query_units),
                "passed": {"words": list(self.passed_words), "dropped_by_pass_cap": self.passed_left},
                "read": {"crosses_read": len(self.read), "left_unread": self.left_unread, "partial": self.partial,
                         "members_read": self.members_read, "members_total": self.members_total,
                         "seeds": list(self.read)},
                "verdict": self.verdict, "entries": [e.to_json_obj() for e in self.entries],
                "full_crosses": list(self.full_crosses), "no_fixed_point": self.no_fixed_point,
                "layer_limit": self.layer_limit, "trace": self.trace}


@dataclass(frozen=True)
class TierLayers:
    tier: str
    triggered: bool
    triggers: dict
    runs: Tuple[LayerRun, ...]
    choice: dict
    fixed_point: dict
    ms: int = 0

    @property
    def entries(self) -> Tuple[LayerEntry, ...]:
        return tuple(e for r in self.runs for e in r.entries)

    def to_json_obj(self) -> dict:
        return {"tier": self.tier, "triggered": self.triggered, "triggers": self.triggers, "choice": self.choice,
                "fixed_point": self.fixed_point, "runs": [r.to_json_obj() for r in self.runs],
                "layers_built": sorted({r.k for r in self.runs})}


# --------------------------------------------------------------------------
# triggers: when has the stability been lost?  (decision 9, N-08, N-11)
# --------------------------------------------------------------------------
def find_triggers(store, res0: cy.TierResult) -> dict:
    """(a) a cross that this question read is FULL: its growth stopped by the budget (capacity reached / unstable;
    the state that was stable just before is the restored one, N-05); (b) a member of a cross could not reach a fixed
    point under the question (the stability collapsed in the middle of the question, N-11)."""
    full = sorted(s for s in res0.plan.read if store.cross_for(s).stop == "budget")
    nofix = [{"seed": p["seed"], "member": p["member"], "reason": p["reason"]} for p in res0.stack_points]
    return {"growth_budget": full, "query_no_fixed_point": nofix, "crosses_read": len(res0.plan.read),
            "any": bool(full or nofix)}


def _answer_units(ans: Optional[ro.PathAnswer]) -> Tuple[str, ...]:
    """The lower answer's units in a fixed order: every word of every listed entry (path words and centre), without
    repeats; entry order then the entry's own word order (sorted)."""
    if ans is None:
        return ()
    out: Dict[str, None] = {}
    for e in ans.entries:
        for w in e.words:
            out.setdefault(w, None)
    return tuple(out)


def _centre_word(layer: Layer, b: str) -> str:
    """Reference: the base seed word under a bundle id ⟦k:...⟦1:seed⟧...⟧ = the innermost seed."""
    s = b
    while s.startswith("⟦"):
        s = s[s.index(":") + 1:-1]
    return s


def _expand(layer: Layer, bundles: Iterable[str]) -> Tuple[str, ...]:
    ws = set()
    for b in bundles:
        ws.update(layer.words[b])
    return tuple(sorted(ws))



# --------------------------------------------------------------------------
# L-251: an upper-layer candidate = the PATH WORDS read under the question from the lower crosses packed in its bundles
# (owner 2026-10-07; N-19 "read out the elements along the path").  No bundle is expanded into all its words.
# --------------------------------------------------------------------------
def _strip(b: str) -> str:
    """⟦k:X⟧ -> X (the unit of the lower layer whose cross is packed in the bundle)."""
    return b[b.index(":") + 1:-1]


def lower_units(units: Iterable[str]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(_strip(u) for u in units))


class _Acc:
    def __init__(self) -> None:
        self.words: Dict[str, set] = {}
        self.reads: List[dict] = []
        self.answers: List[Tuple[int, ro.PathAnswer]] = []
        self.seen: set = set()


def down_read(stack: "LayerStack", chain: Sequence[Layer], k: int, b: str, ul: Sequence[Tuple[str, ...]],
              bounds: LayerBounds, budget: cy.QueryBudget, acc: _Acc, down_query: str = "question") -> None:
    """Read the lower cross packed in the bundle b (layer k) UNDER THE QUESTION (the units ul[k-1] that the upper layer's
    own question maps to, so the same question the upper layer was asked), exactly as layer 0 reads a cross.  At layer 1
    the cross is the base cross of the seed and its path words are base words; above, the lower layer's cross is read and
    each bundle on its paths is read down again, until base words."""
    j = k - 1
    X = _strip(b)
    if j == 0:
        space, facts, plc, cache = stack.base, stack.facts, stack.store, stack._down
    else:
        lay = chain[j - 1]
        space, facts, plc, cache = lay.space, lay.facts, lay, lay._down
    units = tuple(ul[j])
    if down_query == "seed+question":                 # L-252: the bundle's own seed first (so it attaches), then the question
        units = (X,) + tuple(u for u in units if u != X)
    key = (X, units, bounds.members, repr(budget))
    hit = cache.get(key)
    if hit is None:
        plan = cy.ReadPlan((("under_the_bundle", (X,)),), (X,), (), 1, None, False, 0, None, 0, 1)
        res = cy._ask_tier_once(space, "", plc, units=units, facts=facts, budget=budget, scope="whole", unit_filter=None,
                                plan_override=plan, member_cap=bounds.members, observe=False, lazy_members=True)
        ans = ro.read_out_result(space, res, facts) if res.candidates else None
        if len(cache) > 4000:
            cache.clear()
        hit = cache[key] = (ans, (res.members_read, res.members_total))
    ans, mem = hit
    if (j, X) not in acc.seen:
        acc.seen.add((j, X))
        acc.reads.append({"bundle": b, "layer": j, "seed": X, "units": len(units),
                          "listed": len(ans.entries) if ans is not None else 0,
                          "members_read": mem[0], "members_total": mem[1],
                          "words": sorted({w for e in ans.entries for w in e.words}) if ans is not None else []})
        if ans is not None:
            acc.answers.append((j, ans))
    if ans is None:
        return
    for e in ans.entries:
        for w in e.words:
            if j == 0:
                acc.words.setdefault(w, set()).update(ro.entry_word_sources(e, w))
            else:
                down_read(stack, chain, j, w, ul, bounds, budget, acc, down_query)


# --------------------------------------------------------------------------
# trace through the layers (100%)
# --------------------------------------------------------------------------
def trace_run(tier_space: TierSpace, chain: Sequence[Layer], layer: Layer, answer: Optional[ro.PathAnswer],
              entries: Sequence[LayerEntry], store) -> dict:
    """Every word of every entry traces (a) at bundle level: tc.trace_answer on the layer's space (seat, edge sentence),
    (b) down: the base word belongs to a bundle of the entry, which holds it through a lower unit of every layer under it,
    down to a unit placed in the stable state of a base seed that shares a sentence with it (or is it)."""
    checked = traced = 0
    failures: List[str] = []
    rep = None
    if answer is not None:
        _, rep = tc.trace_answer(layer.space, answer)
        checked += rep.words_checked
        traced += rep.words_traced
        failures.extend("bundle-level: " + f for f in rep.failures)
    post = tier_space.postings
    seen_reads: set = set()
    for e in entries:
        for j, pa in e.path_answers:                  # L-251: every lower read an entry's words came from is traced too
            if id(pa) in seen_reads:
                continue
            seen_reads.add(id(pa))
            _, prep = tc.trace_answer(tier_space if j == 0 else chain[j - 1].space, pa)
            checked += prep.words_checked
            traced += prep.words_traced
            failures.extend("lower read (layer %d): %s" % (j, f) for f in prep.failures)
        if e.word_sources is not None:
            ws = {w for w, _ in e.word_sources}
            if ws != set(e.words):
                failures.append("path words and the words of an entry differ")
            for w, ss in e.word_sources:
                if not ss or any(sid not in tier_space.postings.get(w, ()) for sid in ss):
                    failures.append("word %r has no (or a foreign) source sentence" % w)
    for e in entries:
        for w in e.words:
            checked += 1
            ok = False
            for b in e.bundles:
                if w not in layer.words.get(b, ()):
                    continue
                if _descends(chain, layer.k, b, w, tier_space, store):
                    ok = True
                    break
            if ok and w in post and len(post[w]) > 0:
                traced += 1
            else:
                failures.append("word %r of an entry of layer %d has no path down to a base state" % (w, e.layer))
    f = Fraction(traced, checked) if checked else Fraction(1)
    return {"words_checked": checked, "words_traced": traced, "fraction": _fs(f), "ok": f == 1 and not failures,
            "failures": failures[:5]}


def _descends(chain: Sequence[Layer], k: int, b: str, w: str, tier_space: TierSpace, store) -> bool:
    """Is the base word w held by the bundle b of layer k (chain[k-1]) through the lower units, down to a base state?"""
    layer = chain[k - 1]
    for u in layer.lower_units.get(b, ()):
        if k == 1:
            if u != w:
                continue
            s = _centre_word(layer, b)
            if w == s or tier_space.n_pair(s, w) > 0:
                return w in placed_units(store.cross_for(s))
        elif w in chain[k - 2].words.get(u, ()) and _descends(chain, k - 1, u, w, tier_space, store):
            return True
    return False


# --------------------------------------------------------------------------
# the layered read of one tier
# --------------------------------------------------------------------------
QB = cy.QueryBudget(64, 8)


def _read_layer(tier: str, variant: str, layer: Layer, chain: Sequence[Layer], attached_order: Sequence[str],
                passed_words: Sequence[str], passed_left: int, bounds: LayerBounds, tier_space: TierSpace, store,
                budget: cy.QueryBudget, granularity: str, candidate: str = "bag",
                stack: Optional[LayerStack] = None, down_query: str = "question") -> LayerRun:
    t0 = time.monotonic_ns()
    units = tuple(dict.fromkeys(attached_order))
    facts = layer.facts
    qs = set(units)
    rq = lambda u: facts.n[u] + sum(facts.npair(x, u) for x in qs)
    read, left, boundary = take_by_energy(units, rq, bounds.nodes)
    if not units:
        return LayerRun(tier, variant, layer.k, granularity, layer.n_bundles(), (), tuple(passed_words), passed_left, (), 0,
                        False, UNKNOWN_NOTHING_TO_PASS, 0, 0, None, None, (), (), 0, False,
                        {"words_checked": 0, "words_traced": 0, "fraction": "1/1", "ok": True, "failures": []},
                        (time.monotonic_ns() - t0) // 1000000)
    plan = cy.ReadPlan((("query_bundle", read),), tuple(sorted(read)), (), len(units), None, left > 0, boundary,
                       bounds.nodes, left, len(units))
    res = cy._ask_tier_once(layer.space, "", layer, units=units, facts=facts, budget=budget, scope="whole",
                            unit_filter=None, plan_override=plan, member_cap=bounds.members, observe=False,
                            lazy_members=True)
    ans = ro.read_out_result(layer.space, res, facts) if res.candidates else None
    entries: List[LayerEntry] = []
    up_bundles: Optional[Tuple[str, ...]] = None
    without = 0
    if ans is not None and candidate == "path":
        if stack is None:
            raise ValueError("candidate='path' needs the layer stack")
        ul: List[Tuple[str, ...]] = [()] * layer.k            # ul[j] = the question's units in layer j (0 = base words)
        cur = units
        for j in range(layer.k - 1, -1, -1):
            cur = lower_units(cur)
            ul[j] = cur
        grp = {}
        order: Dict[str, None] = {}
        for e in ans.entries:
            for b in e.words:
                order.setdefault(b, None)
            acc = _Acc()
            for b in e.words:
                down_read(stack, chain, layer.k, b, ul, bounds, budget, acc, down_query)
            if not acc.words:
                without += 1
                continue
            ws = tuple(sorted(acc.words))
            le = LayerEntry(tier, layer.k, variant, ws, tuple(sorted(e.words)),
                            tuple(sorted({_centre_word(layer, c) for c in e.centres})), e.stability, e.count,
                            tuple(sorted({sid for ss in acc.words.values() for sid in ss})),
                            tuple((w, tuple(sorted(acc.words[w]))) for w in ws), tuple(acc.reads),
                            tuple(acc.answers))
            grp.setdefault(ws, []).append(le)
        up_bundles = tuple(order)
        for ws in sorted(grp):                       # entries whose path-word SET is the same are one entry (L-235)
            g = grp[ws]
            src = {w: set() for w in ws}
            for x in g:
                for w, ss in x.word_sources:
                    src[w].update(ss)
            pf: List[dict] = []
            pa: List[Tuple[int, ro.PathAnswer]] = []
            for x in g:
                for d in x.path_from:
                    if d not in pf:
                        pf.append(d)
                for it in x.path_answers:
                    if not any(it[1] is y[1] for y in pa):
                        pa.append(it)
            entries.append(LayerEntry(tier, layer.k, variant, ws, tuple(sorted({b for x in g for b in x.bundles})),
                                      tuple(sorted({c for x in g for c in x.centres})), max(x.stability for x in g),
                                      sum(x.arrangements for x in g), tuple(sorted({s_ for ss in src.values() for s_ in ss})),
                                      tuple((w, tuple(sorted(src[w]))) for w in ws), tuple(pf), tuple(pa)))
    elif ans is not None:
        grp = {}
        for e in ans.entries:
            le = LayerEntry(tier, layer.k, variant, _expand(layer, e.words), tuple(e.words),
                            tuple(sorted({_centre_word(layer, c) for c in e.centres})), e.stability, e.count,
                            e.source_sids)
            grp.setdefault(le.words, []).append(le)
        for ws in sorted(grp):                       # L-235: entries whose base words are the same SET are one entry
            g = grp[ws]
            entries.append(LayerEntry(tier, layer.k, variant, ws, tuple(sorted({b for x in g for b in x.bundles})),
                                      tuple(sorted({c for x in g for c in x.centres})), max(x.stability for x in g),
                                      sum(x.arrangements for x in g), tuple(sorted({s for x in g for s in x.source_sids}))))
    full = tuple(sorted(s for s in read if layer.cross_for(s).stop == "budget"))
    verdict = ans.verdict if ans is not None else res.verdict
    tr = trace_run(tier_space, list(chain) + [layer], layer, ans, entries, store)
    return LayerRun(tier, variant, layer.k, granularity, layer.n_bundles(), units, tuple(passed_words), passed_left,
                    tuple(sorted(read)), left, left > 0 or res.members_read < res.members_total, verdict,
                    res.members_read, res.members_total, res, ans, tuple(entries), full,
                    len(res.stack_points), False, tr, (time.monotonic_ns() - t0) // 1000000, up_bundles, candidate, without)


def _variant_chain(stack: LayerStack, res0: cy.TierResult, ans0: Optional[ro.PathAnswer], variant: str,
                   opts: LayerOptions, tier: str, budget: cy.QueryBudget, layer1: Layer) -> List[LayerRun]:
    bounds = opts.bounds
    q_words = tuple(res0.ctx.query)
    ans_words = _answer_units(ans0)
    # L-233: the units passed to layer 1 (A: the initial query first, then the answer; B: the answer only).
    # The inner query crosses (units from the 7th on, M-5(c)) are part of the initial query: A adds them, B does not.
    lower_q = (q_words if variant == "A" else ()) + tuple(w for w in ans_words if variant == "B" or w not in q_words)
    runs: List[LayerRun] = []
    chain: List[Layer] = []
    layer = layer1
    k = 1
    cur_q = lower_q                     # units of the lower layer to pass up (base words at k = 1)
    first_q = tuple(q_words) if variant == "A" else ()
    while True:
        mapped_q = [bundle_id(k, u) for u in cur_q if bundle_id(k, u) in layer.words]
        # question bundles first (in question order), then the answer's by energy (L-234)
        qb = [bundle_id(k, u) for u in first_q if bundle_id(k, u) in layer.words]
        ab_all = [bundle_id(k, u) for u in cur_q if u not in first_q and bundle_id(k, u) in layer.words]
        fac = layer.facts
        allq = set(qb) | set(ab_all)
        rq = lambda u: fac.n[u] + sum(fac.npair(x, u) for x in allq)
        room = None if bounds.pass_cap is None else max(0, bounds.pass_cap - len(qb))
        ab, dropped, _ = take_by_energy(ab_all, rq, room)
        dropped_words = len(cur_q) - len(mapped_q) + dropped
        run = _read_layer(tier, variant, layer, chain, tuple(qb) + tuple(ab), cur_q, dropped_words, bounds,
                          stack.base, stack.store, budget, opts.granularity, opts.candidate, stack, opts.down_query)
        chain.append(layer)
        need_next = bool(run.full_crosses or run.no_fixed_point)
        if need_next and k >= bounds.max_layers:
            run = _replace_run(run, layer_limit=True)
        runs.append(run)
        if not need_next or k >= bounds.max_layers or not run.read:
            break
        # stack again: the upper crosses this question read are the stable states that go up (N-06, N-07)
        nxt = stack.layer_above(k + 1, layer, run.read, bounds)
        ans_k = _answer_units_bundle(run)
        first_q = tuple(run.query_units) if variant == "A" else ()
        cur_q = first_q + tuple(u for u in ans_k if variant == "B" or u not in first_q)
        layer = nxt
        k += 1
    return runs


def _answer_units_bundle(run: LayerRun) -> Tuple[str, ...]:
    if run.up_bundles is not None:
        return run.up_bundles
    out: Dict[str, None] = {}
    for e in run.entries:
        for b in e.bundles:
            out.setdefault(b, None)
    return tuple(out)


def _replace_run(run: LayerRun, **kw) -> LayerRun:
    from dataclasses import replace
    return replace(run, **kw)


def run_layers(stack: LayerStack, res0: cy.TierResult, ans0: Optional[ro.PathAnswer], opts: LayerOptions, *,
               budget: cy.QueryBudget = QB, reask: Optional[Callable[[Sequence[str]], Tuple[cy.TierResult, Optional[ro.PathAnswer]]]] = None
               ) -> TierLayers:
    """Check the stability at the moment of the question (N-08) and, if it was lost, stack and go on answering in the
    upper layers.  `reask(units)` re-reads layer 0 with the given question units (the N-12 re-read, feedback "down")."""
    t0 = time.monotonic_ns()
    tier = res0.tier
    trig = find_triggers(stack.store, res0)
    n_all = len(stack.base.postings)
    n_cmp = len(set(res0.plan.read) | set(res0.ctx.query))
    choice = {"options": {"compress": "bundle only the stable states this question touched (faster)",
                          "same": "bundle every stable state at the same granularity (higher precision)"},
              "chosen": opts.granularity, "bundles_if_compress": n_cmp, "bundles_if_same": n_all}
    if not trig["any"]:
        return TierLayers(tier, False, trig, (), choice,
                          {"rounds": 0, "reached": True, "feedback": opts.feedback, "stop": "no layer was needed"},
                          (time.monotonic_ns() - t0) // 1000000)
    cur_res, cur_ans = res0, ans0
    prev_sig = None
    rounds = 0
    fp: dict
    while True:
        rounds += 1
        runs: List[LayerRun] = []
        for v in opts.variants:
            seeds = set(cur_res.plan.read) | set(cur_res.ctx.query) | set(_answer_units(cur_ans))
            seeds = {s for s in seeds if s in stack.base.postings}
            l1 = stack.layer1(opts.granularity, seeds, opts.bounds)
            runs.extend(_variant_chain(stack, cur_res, cur_ans, v, opts, tier, budget, l1))
        sig = (_entry_sig(cur_ans), tuple((r.variant, r.k, tuple(e.key() for e in r.entries)) for r in runs))
        if opts.feedback == "none":
            fp = {"rounds": 1, "reached": True, "feedback": "none",
                  "stop": "feed-forward only: a second sweep reads the same inputs, so no layer can change"}
            break
        if prev_sig is not None and sig == prev_sig:
            fp = {"rounds": rounds, "reached": True, "feedback": "down", "stop": "no layer changed in the last round"}
            break
        if rounds >= opts.bounds.rounds:
            fp = {"rounds": rounds, "reached": False, "feedback": "down", "stop": UNKNOWN_NO_FIXED_POINT_LAYERS,
                  "budget_rounds": opts.bounds.rounds}
            break
        prev_sig = sig
        if reask is None:
            raise ValueError("feedback='down' needs reask")
        up = tuple(dict.fromkeys(w for r in runs for e in r.entries for w in e.words))
        extra = tuple(w for w in up if w not in res0.ctx.query)
        cur_res, cur_ans = reask(tuple(res0.ctx.query) + extra)
    chain_info = {"max_layers": opts.bounds.max_layers}
    trig = dict(trig, **chain_info)
    return TierLayers(tier, True, trig, tuple(runs), choice, fp, (time.monotonic_ns() - t0) // 1000000)


def _entry_sig(ans: Optional[ro.PathAnswer]):
    return tuple((e.words, e.stability) for e in ans.entries) if ans is not None else ()


# --------------------------------------------------------------------------
# the descent: coarse -> fine (owner 2026-10-07: going up is a search SHORTCUT against combinatorial explosion)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Descent:
    """The question is searched on the packed upper crosses first; only the lower crosses packed under the elements
    on the selected paths are then searched (L-243).  `flat_crosses` = the crosses the flat read (V1, whole) would read."""
    tier: str
    coarse: LayerRun
    fine_seeds: Tuple[str, ...]
    fine_left: int
    fine: Optional[cy.TierResult]
    answer: Optional[ro.PathAnswer]
    flat_crosses: int
    ms_coarse: int
    ms_fine: int

    @property
    def entries(self) -> Tuple[ro.AnswerEntry, ...]:
        return self.answer.entries if self.answer is not None else ()

    @property
    def crosses_read(self) -> dict:
        up = len(self.coarse.read)
        lo = len(self.fine.plan.read) if self.fine is not None else 0
        return {"upper": up, "lower": lo, "total": up + lo, "flat": self.flat_crosses}

    def to_json_obj(self) -> dict:
        return {"tier": self.tier, "crosses_read": self.crosses_read, "fine_seeds": list(self.fine_seeds),
                "fine_left_unread": self.fine_left, "coarse": self.coarse.to_json_obj(),
                "entries": [{"words": list(e.words), "centres": list(e.centres), "stability": _fs(e.stability)}
                            for e in self.entries]}


def descend_tier(index: "A.Index", tier: str, question: str, opts: LayerOptions,
                 budget: cy.QueryBudget = A.DEFAULT_BUDGET) -> Descent:
    from verantyx.line3.funcwords import default_filter
    t0 = time.monotonic_ns()
    st = stack_of(index, tier)
    ts, facts, store = index.space.tiers[tier], index.facts[tier], index.stores[tier]
    flt = default_filter(tier)
    units = tuple(u for u in cy.split_question(tier, question) if not flt(u))
    bounds = opts.bounds
    layer = st.layer1(opts.granularity, set(units) & set(ts.postings), bounds)
    qb = tuple(bundle_id(1, u) for u in units if bundle_id(1, u) in layer.words)
    run = _read_layer(tier, "A", layer, [], qb, units, 0, bounds, ts, store, budget, opts.granularity)
    t1 = time.monotonic_ns()
    seeds = tuple(sorted({_centre_word(layer, b) for e in run.entries for b in e.bundles}))
    ctx = cy.make_context(units, "first_layer")
    rq = lambda u: facts.n[u] + sum(facts.npair(x, u) for x in ctx.energy_units)
    cap = bounds.nodes
    take, left, bnd = take_by_energy(seeds, rq, cap)
    fine = ans = None
    if take:
        plan = cy.ReadPlan((("under_the_path", take),), tuple(sorted(take)), (), len(seeds), None, left > 0, bnd,
                           cap, left, len(seeds))
        fine = cy._ask_tier_once(ts, question, store, units=units, facts=facts, budget=budget, plan_override=plan,
                                 unit_filter=None)
        ans = ro.read_out_result(ts, fine, facts) if fine.candidates else None
    t2 = time.monotonic_ns()
    fp = cy.plan_read(ts, facts, ctx, store, None, True, False, None)
    return Descent(tier, run, take, left, fine, ans, len(fp.read), (t1 - t0) // 1000000, (t2 - t1) // 1000000)


# --------------------------------------------------------------------------
# the command / library entrance
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LayeredCombined:
    """Layer 0 (the T7b result, unchanged) plus the layers of every tier.  The list shown to the user = every layer-0
    entry (as in T7b) followed by every upper-layer entry, each labelled (tier, layer, variant); nothing is merged."""
    base: A.Combined
    layers: Tuple[TierLayers, ...]
    options: LayerOptions
    ms: int = 0
    extra_sentences: Mapping = field(default_factory=dict, compare=False, repr=False)   # L-251: sources of path words

    @property
    def question(self) -> str:
        return self.base.question

    def listed(self) -> Tuple[dict, ...]:
        out: List[dict] = []
        for t, e in self.base.entries:
            out.append({"tier": t, "layer": 0, "variant": None, "words": list(e.words), "centres": list(e.centres),
                        "stability": _fs(e.stability), "arrangements": e.count, "source_sids": list(e.source_sids),
                        "bundles": []})
        for tl in self.layers:
            for e in tl.entries:
                out.append(e.to_json_obj())
        return tuple(out)

    @property
    def verdict(self) -> str:
        n = len(self.listed())
        if n == 0:
            return self.base.verdict if self.base.verdict not in (A.ANSWER, A.CHOICE) else A.UNKNOWN_NO_STATE
        return A.ANSWER if n == 1 else A.CHOICE

    @property
    def stacked(self) -> bool:
        return any(tl.triggered for tl in self.layers)

    def answer_obj(self) -> dict:
        ent = self.listed()
        sids = sorted({s for e in ent for s in e["source_sids"]})
        return {"verdict": self.verdict, "layers": "on", "listed": len(ent), "stacked": self.stacked,
                "per_tier_layer_listed": {tl.tier: {"0": len(self.base.outcome(tl.tier).entries),
                                                    **{"%d%s" % (r.k, r.variant): len(r.entries) for r in tl.runs}}
                                          for tl in self.layers},
                "entries": list(ent), "layer0": self.base.answer_obj(),
                "sources": [{"sid": s, "text": (self.base.sentences[s] if s in self.base.sentences else self.extra_sentences[s])[0]}
                            for s in sids if s in self.base.sentences or s in self.extra_sentences]}

    def thought_obj(self) -> dict:
        o = {"variants": list(self.options.variants), "granularity": self.options.granularity,
             "feedback": self.options.feedback, "bounds": self.options.bounds.to_json_obj()}
        if self.options.candidate != "bag":          # "bag" = T8: the bytes are the same as before the option existed
            o["candidate"] = self.options.candidate
            o["down_query"] = self.options.down_query
        return {"layers": {"format": LAYER_FORMAT, "options": o,
                           "stacked": self.stacked,
                           "per_tier": {tl.tier: tl.to_json_obj() for tl in self.layers}},
                "layer0": self.base.thought_obj()}

    def to_json_obj(self) -> dict:
        return {"answer": self.answer_obj(), "thought": self.thought_obj()}

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json_obj(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def memory_record(self, which: Optional[int] = None) -> dict:
        """The user's choice among the labelled list (layer 0 then upper layers).  A layer-0 entry gives the T7b record;
        an upper entry a record that carries its layer, variant and bundles."""
        n0 = len(self.base.entries)
        if which is None:
            if len(self.listed()) != 1:
                raise ValueError("nothing to adopt automatically: %d entries" % len(self.listed()))
            if n0 == 1:                      # the single entry is layer 0's own ANSWER: its automatic adoption
                rec = self.base.memory_record(None)
                rec.update({"layer": 0, "variant": None})
                return rec
            which = 0
        if not 0 <= which < len(self.listed()):
            raise IndexError("choice %d outside the list of %d" % (which, len(self.listed())))
        if which < n0:
            rec = self.base.memory_record(which)
            rec.update({"layer": 0, "variant": None, "offered": len(self.listed()), "choice_index": which})
            return rec
        e = self.listed()[which]
        return {"kind": ro.RECORD_KIND, "source": "user_choice", "tier": e["tier"], "layer": e["layer"],
                "variant": e["variant"], "words": e["words"], "bundles": e["bundles"], "centres": e["centres"],
                "stability": e["stability"], "source_sids": e["source_sids"], "offered": len(self.listed()),
                "choice_index": which, "base_changed": False}


def ask_layered(index: "A.Index", question: str, tiers: Optional[Sequence[str]] = None,
                budget: cy.QueryBudget = A.DEFAULT_BUDGET, *, options: Optional[LayerOptions] = None,
                view: str = "all", effort: Optional[str] = None, nodes: Optional[int] = None,
                base: Optional[A.Combined] = None, **kw) -> LayeredCombined:
    """ask() with the layers on: layer 0 exactly as ask() gives it, then, per tier, the stability is checked at this
    question and the layers are stacked when it was lost.  `base` = a layer-0 result already computed for the same
    arguments (the experiments reuse it to compare layers off / on without reading layer 0 twice)."""
    t0 = time.monotonic_ns()
    opts = options or LayerOptions(bounds=bounds_for(effort, nodes))
    c0 = base if base is not None else A.ask(index, question, tiers, budget, view=view, effort=effort, nodes=nodes, **kw)
    name, cap, lv = A.resolve_effort(effort, nodes)
    akw = dict(kw)
    if cap is not None:
        akw["read_cap"] = cap
    if lv != cy.RAISE_LEVELS_DEFAULT:
        if lv:
            akw["raise_levels"] = lv
        else:
            akw["raise_budget"] = None
    out: List[TierLayers] = []
    for o in c0.outcomes:
        st = stack_of(index, o.tier)

        def reask(units, o=o):
            ts, facts, store = index.space.tiers[o.tier], index.facts[o.tier], index.stores[o.tier]
            r = cy.ask_tier(ts, question, store, facts=facts, budget=budget, weights=store.w, units=tuple(units), **akw)
            return r, (ro.read_out_result(ts, r, facts) if r.candidates else None)

        out.append(run_layers(st, o.result, o.answer, opts, budget=budget, reask=reask))
    extra: Dict[int, tuple] = {}
    if opts.candidate == "path":
        for tl in out:
            for e in tl.entries:
                for sid in e.source_sids:
                    if sid not in c0.sentences and 0 <= sid < len(index.space.sentences):
                        extra[sid] = index.space.sentences[sid]
    return LayeredCombined(c0, tuple(out), opts, (time.monotonic_ns() - t0) // 1000000, extra)


def format_layers_text(c: LayeredCombined, show_thought: bool = False) -> str:
    L: List[str] = [A.format_text(c.base, False)]
    if not c.stacked:
        L.append("層: 積み上げなし（読んだ十字はどれも安定が保たれた）")
    else:
        up = [e for tl in c.layers for e in tl.entries]
        L.append("層: 安定が崩れたので上の層を積みました（上の層の候補 %d 件。層・問いの渡し方の印つき。足したり束ねたりしていません）:" % len(up))
        n0 = len(c.base.entries)
        for i, e in enumerate(up):
            L.append("  [%d] (%s 第%d層 %s) %s  中心: %s  並べ方 %d  安定度 %s%s" % (
                n0 + i, e.tier, e.layer, "問いを渡した(A)" if e.variant == "A" else "答えだけ(B)", " / ".join(e.words),
                ", ".join(e.centres), e.arrangements, _fs(e.stability),
                ("  経路の語のみ・出典文 %s" % ",".join(str(x) for x in e.source_sids)) if e.word_sources is not None else ""))
        for tl in c.layers:
            if tl.triggered:
                ch = tl.choice
                L.append("  [%s] 圧縮(速い)なら束ねる状態 %d 本、同じ粒度(高精度)なら %d 本。選択中: %s" % (
                    tl.tier, ch["bundles_if_compress"], ch["bundles_if_same"], "同じ粒度" if ch["chosen"] == "same" else "圧縮"))
                for r in tl.runs:
                    if r.partial or r.layer_limit:
                        L.append("      第%d層 %s: 【部分読み】%d 本読み・%d 本は未読%s" % (
                            r.k, r.variant, len(r.read), r.left_unread, "（次の層が要るが努力量の上限で止めた）" if r.layer_limit else ""))
    if show_thought:
        L.append("--- 層の思考過程 ---")
        for tl in c.layers:
            L.append("  [%s] 崩れ: 成長で予算止め %d 本 / 問いの最中に不動点なし %d 件 / 読み直し: %s" % (
                tl.tier, len(tl.triggers["growth_budget"]), len(tl.triggers["query_no_fixed_point"]), tl.fixed_point["stop"]))
            for r in tl.runs:
                L.append("      第%d層 %s: 束ね %d 個 判定 %s 候補 %d 痕跡 %s (%d ms)" % (
                    r.k, r.variant, r.n_bundles, r.verdict, len(r.entries), r.trace["fraction"], r.ms))
    return "\n".join(L)
