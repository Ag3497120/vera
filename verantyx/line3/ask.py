"""T7: the three tiers combined, and the entrance (docs/LINE3_DESIGN.md T7, I-16, I-17, I-25, N-08, N-10).

Binding (ops/decisions/2026-10-06_line3_faithful_build.md):
  I-16  "各段を別に回し、一番安定なもの": every tier (RUN, WORD, CHAR) is run SEPARATELY (its own cross
        placements, its own question units, its own read-out); the result taken is the most stable one.
        Tiers are never merged: no vote, no count and no word set is summed across tiers.  Whether
        tiers agree is only REPORTED (thought.agreement); it never selects anything.
  I-25  "すべて回す": all requested tiers are run; the search never stops at the first tier with an answer.
  I-14  one most stable result -> that result; a tie -> a list (the user chooses).  Between tiers: the
        tiers whose best stability is equal and highest give ONE list (entries kept apart, each labelled
        with its tier); a single winning tier gives its own result (a single entry or its own list).
  I-17  "入れない": no extra check is added here.  (The trace check of T6 is an acceptance tool, not a step.)
  N-08 / N-10  the output has two keys: `answer` (verdict, the path words with their sources, the list)
        and `thought` (what happened: per-tier verdicts, stabilities, the search and read-out records,
        the ranking, the agreement report).  The command line shows `thought` on request.
  Every tier runs with the CURRENT DEFAULTS of cycle.ask_tier / readout.read_out_result (T6z / T6ab):
        read only the crosses that hold a question unit (V1), function / question words are not units
        (V2), the state is the one sharing most sentences with the question (V3), items that differ
        only by section assignment are merged, entries with the same word set are one entry, the budget
        of a cross is raised only when a question needs it, the answer is the path words with the
        sentences they trace to, the centre is a reference.

T7b (owner, after T7: ops/decisions "T7 の測定後の決定"):
  view   the user is shown EVERY tier's candidates, each labelled with its tier, never summed or merged across
         tiers (view="all"); the I-16 "most stable tier only" view stays as view="stable".
  effort the amount of inference is the user's choice per question (M-2(a)): a node budget = the number of crosses
         read per tier (cycle read_cap); fast / standard are presets of that number (EFFORTS, set by measurement,
         docs L-222), full = the whole read.  When the budget leaves crosses unread the answer is marked partial
         with the counts (read / left unread / would read in full).

Local decisions (docs/LINE3_LOCAL_DECISIONS.md L-210..):
  the tier's stability = the best stability among its listed entries (exact Fraction); a tier that
  adopted states but whose states have no section path has no entry and takes no part in the ranking
  (it is named in thought); no tier with an entry -> UNKNOWN_NO_STATE (no tier adopted a state) or
  UNKNOWN_NO_PATH (states adopted, nothing readable).
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import pickle
import time
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import cycle as cy
from verantyx.line3 import placement as pl
from verantyx.line3 import readout as ro
from verantyx.line3.space import TIERS, Space, build_space, load_jsonl

ANSWER = cy.ANSWER
CHOICE = cy.CHOICE
UNKNOWN_NO_STATE = "UNKNOWN_NO_STATE"
UNKNOWN_NO_PATH = ro.UNKNOWN_NO_PATH

DEFAULT_LEVEL = "mid"                         # L-210: the level every S300 measurement of T5..T6ab used
DEFAULT_BUDGET = cy.QueryBudget(64, 8)        # L-210: the query budget of the T6z / T6ab runs
CACHE_FORMAT = "line3.placements.v1"
ON_COLLAPSES = ("stop", "skip")              # F1c (L-506): placement.build_cross(on_collapse=...); "stop" = L-463, the default
GROUP_INSERTS = ("whole", "ordered")          # F1b (L-470): placement.build_cross(group_insert=...); "whole" = L-72, the default
ORDERS = ("forward", "reverse")               # F1b: the recorded insertion order of a tied share-group (reverse = measurement probe)

# T7b: the amount of inference = (cap, raise_levels).  cap = crosses read PER TIER (a node budget, M-2(a)), None =
# the whole read.  raise_levels = the placement levels a cross may be REBUILT at when a question needs it (T6y
# on-demand raise; one rebuilt cross costs tens of seconds, far more than reading one), () = never.  fast / standard
# are set by measurement (experiments/line3/t7b, docs L-222); the user-facing command has NO default preset.
EFFORTS: Dict[str, Tuple[Optional[int], Tuple[str, ...]]] = {
    "fast": (4, ()), "standard": (10, ()), "full": (None, cy.RAISE_LEVELS_DEFAULT)}
VIEWS = ("all", "stable")


def resolve_effort(effort: Optional[str] = None, nodes: Optional[int] = None):
    """(name, cap, raise_levels).  `nodes` (an explicit node budget, crosses per tier) wins, is named "nodes" and
    never rebuilds a cross (raise off); neither given -> (None, None, default levels) = exactly what T7 did
    (library behaviour; the command line asks the user)."""
    if nodes is not None:
        if isinstance(nodes, bool) or not isinstance(nodes, int) or nodes < 0:
            raise ValueError("nodes must be an integer >= 0")
        return "nodes", nodes, ()
    if effort is None:
        return None, None, cy.RAISE_LEVELS_DEFAULT
    if effort not in EFFORTS:
        raise ValueError("unknown effort %r (%s)" % (effort, ", ".join(EFFORTS)))
    cap, lv = EFFORTS[effort]
    return effort, cap, lv


def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


def parse_tiers(spec) -> Tuple[str, ...]:
    """'RUN,CHAR' or a sequence -> the tiers in the fixed order RUN, WORD, CHAR, without repeats."""
    if spec is None:
        return TIERS
    names = [s.strip().upper() for s in (spec.split(",") if isinstance(spec, str) else spec) if str(s).strip()]
    for n in names:
        if n not in TIERS:
            raise ValueError("unknown tier %r (RUN, WORD, CHAR)" % n)
    if not names:
        raise ValueError("no tier given")
    return tuple(t for t in TIERS if t in names)


# --------------------------------------------------------------------------
# placements: build / cache / load  (L-211)
# --------------------------------------------------------------------------
def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_placement_options(group_insert: str = "whole", order: str = "forward",
                            on_collapse: str = "stop") -> Tuple[str, str]:
    """F1b / L-470: the placement options of an Index, validated like build_cross does.  `order` only means something
    for "ordered"; asking for order="reverse" with "whole" would record an option that has no effect, so it is refused."""
    if group_insert not in GROUP_INSERTS:
        raise ValueError("group_insert must be %s" % " or ".join(repr(g) for g in GROUP_INSERTS))
    if order not in ORDERS:
        raise ValueError("order must be %s" % " or ".join(repr(o) for o in ORDERS))
    if group_insert == "whole" and order != "forward":
        raise ValueError("order=%r needs group_insert='ordered' (the whole-group build has no order)" % order)
    if on_collapse not in ON_COLLAPSES:                  # F1c (L-506, L-500): returns the same pair as before
        raise ValueError("on_collapse must be %s" % " or ".join(repr(o) for o in ON_COLLAPSES))
    if on_collapse == "skip" and group_insert != "ordered":
        raise ValueError("on_collapse='skip' needs group_insert='ordered' (a whole group is one step: nothing to skip)")
    return group_insert, order


def placement_key(group_insert: str = "whole", order: str = "forward", on_collapse: str = "stop") -> str:
    """F1b / L-471: the part of the cache key that the placement options make.  "" for the default (whole / forward):
    the file name and the pickle of every cache written before F1b stay valid; otherwise "ordered-forward" /
    "ordered-reverse"; F1c (L-506): "-skip" is added for on_collapse="skip" (stop adds nothing: ordered caches stay valid)."""
    group_insert, order = check_placement_options(group_insert, order, on_collapse)
    return "" if group_insert == "whole" else "%s-%s%s" % (group_insert, order, "-skip" if on_collapse == "skip" else "")


def placement_obj(group_insert: str = "whole", order: str = "forward", on_collapse: str = "stop") -> dict:
    o = {"group_insert": group_insert, "order": order}
    if on_collapse != "stop":                            # F1c (L-507): only when not the default, F1b bytes unchanged
        o["on_collapse"] = on_collapse
    return o


def cache_path(cache_dir: str, data_sha: str, tier: str, level: str,
               group_insert: str = "whole", order: str = "forward", on_collapse: str = "stop") -> str:
    k = placement_key(group_insert, order, on_collapse)
    return os.path.join(cache_dir, "placements_%s_%s_%s%s.pkl" % (data_sha[:12], tier, level, "_" + k if k else ""))


_G: dict = {}                                   # set before the fork; the children inherit it


def _work(seeds):
    t, w, b = _G["tier"], _G["w"], _G["budget"]
    out = []
    for s in seeds:
        t0 = time.time()
        out.append((s, pl.build_cross(t, s, w, budget=b, group_insert=_G.get("group_insert", "whole"),
                                      order=_G.get("order", "forward"),
                                      on_collapse=_G.get("on_collapse", "stop")), time.time() - t0))
    return out


def precompute_tier(tier_space, level: str = DEFAULT_LEVEL, workers: int = 1, log=None,
                    group_insert: str = "whole", order: str = "forward", on_collapse: str = "stop"):
    """The cross of every unit of a tier at a budget level (L-211).  Returns (placements, secs per seed,
    wall seconds).  The placements do not depend on the worker count (every cross is built alone)."""
    check_placement_options(group_insert, order, on_collapse)
    b = pl.budget_level(level)
    w = pl.Weights(tier_space)
    units = tier_space.units()
    t0 = time.time()
    res: Dict[str, pl.Placement] = {}
    secs: Dict[str, float] = {}
    if workers <= 1:
        _G.update(tier=tier_space, w=w, budget=b, group_insert=group_insert, order=order, on_collapse=on_collapse)
        parts = [_work([u]) for u in units]
    else:
        _G.update(tier=tier_space, w=w, budget=b, group_insert=group_insert, order=order, on_collapse=on_collapse)
        chunks = [units[i:i + 4] for i in range(0, len(units), 4)]
        ctx = mp.get_context("fork")
        with ctx.Pool(workers) as pool:
            parts = list(pool.imap_unordered(_work, chunks))
    for part in parts:
        for s, p, dt in part:
            res[s] = p
            secs[s] = dt
    return {s: res[s] for s in sorted(res)}, secs, time.time() - t0


def save_placements(path: str, tier: str, level: str, data_sha: str, placements, secs, wall: float,
                    group_insert: str = "whole", order: str = "forward", on_collapse: str = "stop") -> None:
    check_placement_options(group_insert, order, on_collapse)
    tmp = path + ".part"
    rec = {"format": CACHE_FORMAT, "data_sha256": data_sha, "tier": tier, "level": level,
           "placements": dict(placements), "secs": dict(secs), "wall_s": wall}
    if placement_key(group_insert, order, on_collapse):  # F1b: the default file is byte-for-byte what it was
        rec.update({"group_insert": group_insert, "order": order})
        if on_collapse != "stop":                        # F1c (L-506): an ordered+stop file is what F1b wrote
            rec["on_collapse"] = on_collapse
    with open(tmp, "wb") as f:
        pickle.dump(rec, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def load_placements(path: str, tier_space, tier: str, level: str, data_sha: str,
                    group_insert: str = "whole", order: str = "forward", on_collapse: str = "stop") -> Dict[str, pl.Placement]:
    """Load a cache file; refuses one that is for other data, another tier or level, a different unit set, or
    (F1b, L-471) other placement options.  A file without the option keys is a whole / forward cache."""
    check_placement_options(group_insert, order, on_collapse)
    with open(path, "rb") as f:
        d = pickle.load(f)
    if d.get("format") != CACHE_FORMAT or d["data_sha256"] != data_sha or d["tier"] != tier or d["level"] != level:
        raise ValueError("placement cache %s is not for this data / tier / level" % path)
    if (d.get("group_insert", "whole"), d.get("order", "forward"), d.get("on_collapse", "stop")) != \
            (group_insert, order, on_collapse):
        raise ValueError("placement cache %s was built with group_insert=%s order=%s on_collapse=%s, not group_insert=%s order=%s on_collapse=%s"
                         % (path, d.get("group_insert", "whole"), d.get("order", "forward"), d.get("on_collapse", "stop"),
                            group_insert, order, on_collapse))
    if set(d["placements"]) != set(tier_space.units()):
        raise ValueError("placement cache %s does not cover exactly the units of the tier" % path)
    return d["placements"]


class _Store:
    """cross_for(seed): the loaded cross, else built on demand at the index's level (Placer, L-07)."""

    def __init__(self, tier_space, level: str, loaded: Optional[Mapping[str, pl.Placement]] = None,
                 group_insert: str = "whole", order: str = "forward", on_collapse: str = "stop") -> None:
        self._loaded = dict(loaded or {})
        self.group_insert, self.order, self.on_collapse = group_insert, order, on_collapse
        self.placer = pl.Placer(tier_space, pl.budget_level(level), group_insert=group_insert, order=order,
                                on_collapse=on_collapse)
        self.on_demand = 0

    @property
    def w(self):
        return self.placer.w

    def cross_for(self, seed: str) -> pl.Placement:
        p = self._loaded.get(seed)
        if p is None:
            self.on_demand += 1
            p = self.placer.cross_for(seed)
        return p


class Index:
    """The space with the stored placements of every requested tier."""

    def __init__(self, space: Space, data_sha: str = "", level: str = DEFAULT_LEVEL,
                 tiers: Sequence[str] = TIERS, loaded: Optional[Mapping[str, Mapping[str, pl.Placement]]] = None,
                 *, group_insert: str = "whole", order: str = "forward", on_collapse: str = "stop") -> None:
        pl.budget_level(level)
        self.group_insert, self.order = check_placement_options(group_insert, order, on_collapse)     # F1b (L-470), F1c (L-506)
        self.on_collapse = on_collapse
        self.space, self.data_sha, self.level = space, data_sha, level
        self.cache_dir: Optional[str] = None             # G3-e: where from_jsonl read its caches (the window index of structure="slide" uses it)
        self.tiers = parse_tiers(tiers)
        self.facts = {t: cy.TierFacts(space.tiers[t]) for t in self.tiers}
        self.stores = {t: _Store(space.tiers[t], level, (loaded or {}).get(t), self.group_insert, self.order,
                                 self.on_collapse)
                       for t in self.tiers}

    @property
    def placement_is_default(self) -> bool:
        return self.group_insert == "whole" and self.order == "forward" and self.on_collapse == "stop"

    @classmethod
    def from_jsonl(cls, path: str, cache_dir: Optional[str] = None, level: str = DEFAULT_LEVEL,
                   tiers: Sequence[str] = TIERS, *, group_insert: str = "whole", order: str = "forward",
                   on_collapse: str = "stop") -> "Index":
        check_placement_options(group_insert, order, on_collapse)
        sha = file_sha256(path)
        space = build_space(load_jsonl(path))
        loaded = {}
        for t in parse_tiers(tiers):
            if cache_dir:
                p = cache_path(cache_dir, sha, t, level, group_insert, order, on_collapse)    # F1b/F1c: the options are in the file name
                if os.path.exists(p):
                    loaded[t] = load_placements(p, space.tiers[t], t, level, sha, group_insert, order, on_collapse)
        ix = cls(space, sha, level, tiers, loaded, group_insert=group_insert, order=order, on_collapse=on_collapse)
        ix.cache_dir = cache_dir
        return ix

    def precompute(self, cache_dir: Optional[str] = None, workers: int = 1, log=None) -> Dict[str, dict]:
        """Build the crosses of every unit of every tier (replacing what was loaded) and, with a cache
        directory, write them.  Returns {tier: {units, seconds_wall, seconds_cpu}}."""
        rep = {}
        for t in self.tiers:
            ts = self.space.tiers[t]
            placements, secs, wall = precompute_tier(ts, self.level, workers, group_insert=self.group_insert,
                                                     order=self.order, on_collapse=self.on_collapse)
            self.stores[t]._loaded = dict(placements)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
                save_placements(cache_path(cache_dir, self.data_sha, t, self.level, self.group_insert, self.order,
                                           self.on_collapse),
                                t, self.level, self.data_sha, placements, secs, wall, self.group_insert, self.order,
                                self.on_collapse)
            rep[t] = {"units": len(placements), "seconds_wall": round(wall, 2),
                      "seconds_cpu": round(sum(secs.values()), 2)}
            if log:
                log("%s: %d crosses, %.1f s wall, %.1f s cpu" % (t, len(placements), wall, sum(secs.values())))
        return rep


# --------------------------------------------------------------------------
# combining the tiers  (L-212)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class TierOutcome:
    tier: str
    result: cy.TierResult
    answer: Optional[ro.PathAnswer]          # None when no state was adopted
    ms: int = 0                              # wall time (not part of the output bytes)
    raise_skipped: int = 0                   # T7b: budget-limited crosses read that were NOT rebuilt (no state, raise off)
    placement_order: Tuple[dict, ...] = ()   # F1b (L-473): the insertion order of every cross read, only when group_insert != "whole"
    via_standin: Optional[Tuple[bool, ...]] = None   # G3-k (L-805): per entry, True = it exists only through an unknown-word stand-in; None = grammar off
    read_via_standin: Optional[Tuple[bool, ...]] = None   # G3-k (L-811): per entry, True = every cross it came from would NOT have been read under the same cap and order without the stand-ins; None = grammar off

    @property
    def entries(self) -> Tuple[ro.AnswerEntry, ...]:
        return self.answer.entries if self.answer is not None else ()

    @property
    def stability(self) -> Optional[Fraction]:
        return max((e.stability for e in self.entries), default=None)

    @property
    def verdict(self) -> str:
        return self.answer.verdict if self.answer is not None else self.result.verdict

    @property
    def read_counts(self) -> dict:
        """crosses read / left unread by the node budget / would be read in full (the default read)."""
        p = self.result.plan
        if p.cap is None:
            return {"crosses_read": len(p.read), "left_unread": 0, "would_read_in_full": len(p.read)}
        return {"crosses_read": len(p.read), "left_unread": p.cap_unread, "would_read_in_full": p.cap_total}


@dataclass(frozen=True)
class Combined:
    question: str
    outcomes: Tuple[TierOutcome, ...]                    # in the order RUN, WORD, CHAR, one per tier run
    verdict: str
    shown: Tuple[str, ...]                               # the tiers whose entries are the answer
    entries: Tuple[Tuple[str, ro.AnswerEntry], ...]      # (tier, entry): kept apart, never merged across tiers
    tie_between_tiers: bool
    level: str
    budget: cy.QueryBudget
    sentences: Mapping[int, Tuple[str, str]]             # sid -> (original text, source) of every sentence cited
    ms: int = 0
    view: str = "all"                                    # T7b: "all" (every tier's entries, labelled) | "stable" (I-16)
    effort: Optional[str] = None                         # T7b: preset name / "nodes" / None (whole read)
    node_budget: Optional[int] = None                    # T7b: crosses read per tier, None = whole read
    raise_levels: Tuple[str, ...] = cy.RAISE_LEVELS_DEFAULT   # T7b: levels a cross may be rebuilt at ((): never)
    assembled: Optional[dict] = None                     # F2 (L-485): granularity.assemble_combined(); None = option off
    placement: Optional[dict] = None                     # F1b (L-472): {group_insert, order} of the placements; None = the default (whole)
    grammar: Optional[dict] = None                       # G3-k (L-805): {"form", "standins", "full"} of the grammar intake; None = grammar off (the bytes of before)

    # ---- reference helpers ----
    def outcome(self, tier: str) -> TierOutcome:
        for o in self.outcomes:
            if o.tier == tier:
                return o
        raise KeyError(tier)

    @property
    def all_entries(self) -> Tuple[Tuple[str, ro.AnswerEntry], ...]:
        """Every entry of every tier run (the pool; for measuring candidate quality only: the user is shown
        `entries`)."""
        return tuple((o.tier, e) for o in self.outcomes for e in o.entries)

    def agreement(self) -> dict:
        """REPORT ONLY (I-16): for every pair of tiers with entries, the word strings and centres they share
        literally.  Nothing is selected, counted or summed from it."""
        rows = []
        have = [o for o in self.outcomes if o.entries]
        for i, a in enumerate(have):
            for b in have[i + 1:]:
                wa = {w for e in a.entries for w in e.words}
                wb = {w for e in b.entries for w in e.words}
                ca = {c for e in a.entries for c in e.centres}
                cb = {c for e in b.entries for c in e.centres}
                rows.append({"tiers": [a.tier, b.tier], "shared_words": sorted(wa & wb),
                             "shared_centres": sorted(ca & cb)})
        return {"pairs": rows, "used_for_selection": False}

    @property
    def most_stable_tiers(self) -> Tuple[str, ...]:
        """Reference label only (I-16 ranking); it selects nothing in view="all"."""
        ranked = [o for o in self.outcomes if o.stability is not None]
        if not ranked:
            return ()
        best = max(o.stability for o in ranked)
        return tuple(o.tier for o in ranked if o.stability == best)

    def read_obj(self) -> dict:
        per = {o.tier: o.read_counts for o in self.outcomes}
        skipped = {o.tier: o.raise_skipped for o in self.outcomes if o.raise_skipped}
        o = {"effort": self.effort, "node_budget": self.node_budget, "rebuild_levels": list(self.raise_levels),
             "partial": any(v["left_unread"] > 0 for v in per.values()), "per_tier": per,
             "rebuild_skipped": skipped}
        if self.grammar is not None:                     # G3-k (L-804): named only with the grammar on, so the default bytes are unchanged
            o["order"] = "eq+grammar" if self.grammar.get("order", "qcount_first") == "eq_first" else "qcount+grammar"      # G3-k2 (L-819): the flat plane's order named
        return o

    def _locate(self, which: int) -> Tuple[TierOutcome, int]:
        if isinstance(which, bool) or not isinstance(which, int):
            raise TypeError("choice must be an index")
        if not 0 <= which < len(self.entries):
            raise IndexError("choice %d outside the list of %d" % (which, len(self.entries)))
        tier = self.entries[which][0]
        local = sum(1 for t, _ in self.entries[:which] if t == tier)     # position among that tier's shown entries
        return self.outcome(tier), local

    def memory_record(self, which: Optional[int] = None) -> dict:
        """The user's choice (or the automatic adoption of the single entry) as one memory record (M-4 (a)): the
        readout record of the chosen tier's entry (which carries `tier`), `choice_index` = the index in the list
        the user saw (all tiers, labelled), plus the view, the position inside the tier and how much was read."""
        if which is None:
            if len(self.entries) != 1 or self.verdict != ANSWER:
                raise ValueError("nothing to adopt automatically: verdict %s with %d entries" % (self.verdict, len(self.entries)))
            o, local = self._locate(0)
            ad = ro.adopt_item(o.answer)
        else:
            o, local = self._locate(which)
            ad = ro.choose_item(o.answer, local)         # a tier's entries are all shown, in the tier's own order
            ad = replace(ad, listed=len(self.entries), choice_index=which)
        rec = ad.memory_record()
        assert rec["tier"] == o.tier
        rec.update({"view": self.view, "tier_entry_index": local, "tiers_offered": list(self.shown),
                    "effort": self.effort, "node_budget": self.node_budget,
                    "partial_read": o.read_counts["left_unread"] > 0, "crosses": o.read_counts})
        if self.placement is not None:                   # F1b (L-472): the initial placement is part of what was chosen from
            rec["placement"] = dict(self.placement)
        return rec

    # ---- output (N-08, N-10) ----
    def answer_obj(self) -> dict:
        one = self.verdict == ANSWER
        ms_ = set(self.most_stable_tiers)
        ents = []
        pos: Dict[str, int] = {}
        for t, e in self.entries:
            ents.append({"tier": t, "words": list(e.words), "arrangements": e.count, "centres": list(e.centres),
                         "stability": _fs(e.stability), "source_sids": list(e.source_sids),
                         "tier_is_most_stable": t in ms_})
            if self.grammar is not None:                 # G3-k (L-805, L-815): the position among that tier's entries is counted (never found by value)
                o_ = self.outcome(t)
                i_ = pos.get(t, 0)
                pos[t] = i_ + 1
                ents[-1]["via_standin"] = o_.via_standin[i_] if o_.via_standin else False
                ents[-1]["read_via_standin"] = o_.read_via_standin[i_] if o_.read_via_standin else False
        sids = sorted({s for _, e in self.entries for s in e.source_sids})
        o = {"verdict": self.verdict, "view": self.view, "tiers": list(self.shown),
             "most_stable_tiers": list(self.most_stable_tiers), "tie_between_tiers": self.tie_between_tiers,
             "listed": len(self.entries), "per_tier_listed": {x.tier: len(x.entries) for x in self.outcomes},
             "read": self.read_obj(),
             "answer": ({"tier": ents[0]["tier"], "path_words": list(ents[0]["words"]),
                         "source_sids": ents[0]["source_sids"],
                         "reference_centres": ents[0]["centres"]} if one else None),
             "entries": ents,
             "sources": [{"sid": s, "text": self.sentences[s][0], "source": self.sentences[s][1]} for s in sids]}
        if self.assembled is not None:                   # F2: only with the option on, so default bytes are unchanged
            o["assembled"] = self.assembled
        if self.placement is not None:                   # F1b (L-472): only when not the default, so default bytes are unchanged
            o["placement"] = dict(self.placement)
        if self.grammar is not None:                     # G3-k (L-805): the form, the stand-ins with their chance counts
            o["grammar_form"] = self.grammar["form"]
            o["standins"] = self.grammar["standins"]
        return o

    def thought_obj(self) -> dict:
        per = {}
        for o in self.outcomes:
            d = {"verdict": o.verdict, "cycle_verdict": o.result.verdict, "stability": _fs(o.stability),
                 "states_adopted": len(o.result.candidates), "listed": len(o.entries),
                 "cycle": o.result.thought_obj()}
            if o.answer is not None:
                d["readout"] = o.answer.thought_obj()
                d["readout_answer"] = o.answer.answer_obj()
            if self.placement is not None:               # F1b (L-473): the recorded insertion order of the crosses read
                d["placement_order"] = list(o.placement_order)
            per[o.tier] = d
        ranked = sorted(((o.stability, o.tier) for o in self.outcomes if o.stability is not None),
                        key=lambda x: (-x[0], x[1]))
        th = {"question": self.question, "tiers_run": [o.tier for o in self.outcomes], "level": self.level,
                "query_budget": {"max_states": self.budget.max_states, "max_ends": self.budget.max_ends},
                "rule": ("T7b: each tier on its own; every tier's entries are shown, labelled by tier, nothing summed or merged"
                         if self.view == "all" else
                         "I-16: each tier on its own; the most stable result is taken; a tie between tiers is a list"),
                "view": self.view, "effort": self.effort, "node_budget": self.node_budget, "read": self.read_obj(),
                "ranking": [{"tier": t, "stability": _fs(s)} for s, t in ranked],
                "shown_tiers": list(self.shown), "tie_between_tiers": self.tie_between_tiers,
                "agreement": self.agreement(), "tiers": per}
        if self.placement is not None:                   # F1b (L-472)
            th["placement"] = dict(self.placement)
        if self.grammar is not None:                     # G3-k
            th["grammar"] = self.grammar["full"]
        return th

    def to_json_obj(self) -> dict:
        return {"answer": self.answer_obj(), "thought": self.thought_obj()}

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json_obj(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def combine(question: str, outcomes: Sequence[TierOutcome], space: Space, level: str = DEFAULT_LEVEL,
            budget: cy.QueryBudget = DEFAULT_BUDGET, view: str = "all", effort: Optional[str] = None,
            node_budget: Optional[int] = None, raise_levels: Tuple[str, ...] = cy.RAISE_LEVELS_DEFAULT,
            placement: Optional[dict] = None) -> Combined:
    """T7b view="all" (default): every tier's entries, in the order RUN, WORD, CHAR, each labelled with its tier,
    nothing summed or merged across tiers; a single entry in total is the ANSWER, otherwise a CHOICE.
    view="stable": I-16 / I-14 (the most stable tier(s) only).  On finished tier outcomes (testable without a search)."""
    if view not in VIEWS:
        raise ValueError("view: %s" % " | ".join(VIEWS))
    outs = tuple(sorted(outcomes, key=lambda o: TIERS.index(o.tier)))
    ranked = [o for o in outs if o.stability is not None]
    if ranked and view == "all":
        shown = tuple(o.tier for o in ranked)
        entries = tuple((o.tier, e) for o in ranked for e in o.entries)
        tie = False
        verdict = ANSWER if len(entries) == 1 else CHOICE
    elif not ranked:
        verdict = UNKNOWN_NO_PATH if any(o.result.candidates for o in outs) else UNKNOWN_NO_STATE
        shown: Tuple[str, ...] = ()
        entries: Tuple[Tuple[str, ro.AnswerEntry], ...] = ()
        tie = False
    else:
        best = max(o.stability for o in ranked)
        top = [o for o in ranked if o.stability == best]
        shown = tuple(o.tier for o in top)
        entries = tuple((o.tier, e) for o in top for e in o.entries)
        tie = len(top) > 1
        verdict = ANSWER if len(entries) == 1 else CHOICE
    sids = {s for _, e in entries for s in e.source_sids}
    sents = {s: space.sentences[s] for s in sorted(sids)}
    return Combined(question, outs, verdict, shown, entries, tie, level, budget, sents,
                    sum(o.ms for o in outs), view, effort, node_budget, tuple(raise_levels), None, placement)


def placement_kw(index: Index) -> dict:
    """F1b (L-474): the keywords that make cycle.ask_tier rebuild a cross (raise_budget) with the index's options."""
    kw = {"group_insert": index.group_insert, "order": index.order}
    if index.on_collapse != "stop":                      # F1c (L-507)
        kw["on_collapse"] = index.on_collapse
    return kw


def placement_order_records(store: "_Store", seeds) -> Tuple[dict, ...]:
    """F1b (L-473): per cross read (ascending seed), the recorded insertion order: the share-groups reached, each with its
    members in the order they were inserted, where growth stopped and what was left out.  A pure read of the stored
    (or on-demand) placements."""
    out = []
    for sd in sorted(seeds):
        p = store.cross_for(sd)
        rec = {"seed": sd, "stop": p.stop, "size": p.size, "left_in_group": p.left_in_group,
               "left_after": p.left_after, "groups": [[sh, list(us)] for sh, us in p.order_log]}
        if p.on_collapse != "stop":                      # F1c (L-507): the members skipped, with the budget that stopped each
            rec["skipped"] = [[sh, u, why] for sh, u, why in p.skipped]
        out.append(rec)
    return tuple(out)


def ask_tier_outcome(index: Index, tier: str, question: str, budget: cy.QueryBudget = DEFAULT_BUDGET,
                     **kw) -> TierOutcome:
    """One tier, separately: the search with the current defaults, then the default read-out."""
    t0 = time.monotonic_ns()
    ts, facts, store = index.space.tiers[tier], index.facts[tier], index.stores[tier]
    if not index.placement_is_default:                   # F1b (L-474): a rebuild at a higher level uses the same insertion order
        kw = dict(kw, **placement_kw(index))
    res = cy.ask_tier(ts, question, store, facts=facts, budget=budget, weights=store.w, **kw)
    ans = ro.read_out_result(ts, res, facts) if res.candidates else None
    skipped = 0
    if not res.candidates and not ((res.variant or {}).get("budget_raise") or {}).get("needed"):
        lv = kw.get("raise_levels", cy.RAISE_LEVELS_DEFAULT)
        if kw.get("raise_budget", "on_demand") is None or not lv:
            skipped = sum(1 for sd in res.plan.read if store.cross_for(sd).stop == "budget")
    po = () if index.placement_is_default else placement_order_records(store, res.plan.read)
    return TierOutcome(tier, res, ans, (time.monotonic_ns() - t0) // 1000000, skipped, po)


STRUCTURES = ("flat", "slide", "combined")           # G3-e (L-654): the structure the question is asked over; flat = everything above; G3-g (L-726): combined = one labelled list of flat + layers + windows


def ask(index: Index, question: str, tiers: Optional[Sequence[str]] = None,
        budget: cy.QueryBudget = DEFAULT_BUDGET, *, view: str = "all", effort: Optional[str] = None,
        nodes: Optional[int] = None, granularity: Optional[str] = None, structure: str = "flat", grammar: str = "off",
        grammar_intake=None, flat_order: Optional[str] = None, **kw) -> Combined:
    """I-25: every requested tier is run (none is skipped because another one answered).  `view`: every tier's
    entries labelled (default) or the I-16 most stable tier only.  `effort` (fast | standard | full) or `nodes`
    (crosses per tier): the amount of inference; neither = the whole read (what T7 did).  A budget that leaves
    crosses unread marks the answer partial, with counts.

    `structure="slide"` (G3-e, opt-in; default "flat" = this function as it was, byte for byte): the question is asked over the sliding
    windows of the corpus (verantyx.line3.slide_query, tier RUN) and a slide_query.SlideAnswer is returned (its own entries, labelled by
    axis and window; `**kw` are slide_query.ask_slide's options).  `effort` / `nodes` then count windows.

    `structure="combined"` (G3-g, opt-in): the flat cross, the layers (stable-seats-path) and the windows read flat, ONE list in which every candidate
    is labelled by its origin (verantyx.line3.combined; `**kw` are combined.ask_combined's options, e.g. window_evidence="plain"|"window"|"both").

    `grammar="on"` (G3-k, opt-in; "off" = every committed byte): the unknown RUN words of the question get their stand-ins as ADDITIONAL, marked query units
    (RUN tier) and the crosses read under the preset cap are ordered by E_Q first and, only inside an exact E_Q tie, by the question units they hold and the grammar layer's
    kind of the cross (the question's slot first) (`flat_order`, verantyx.line3.wiring; L-800.., L-819).  `grammar_intake` = a wiring.GrammarIntake made beforehand (combined shares one).
    `flat_order` (G3-k2, L-819; only with grammar "on"): the order of the crosses read under the cap: None / "eq_first" (default; the owner's 「E_Q が先、単位数は同点内」: T7b's
    energy order, the question units held and the grammar kind only inside an exact E_Q tie) | "qcount_first" (G3-k's: the question units held first).  Not a window order."""
    if structure not in STRUCTURES:
        raise ValueError("structure: %s" % " | ".join(STRUCTURES))
    if grammar not in ("off", "on"):
        raise ValueError("grammar: off | on")
    if structure == "combined":
        if granularity:
            raise ValueError("structure='combined' has no granularity option (G3-g, L-726)")
        from verantyx.line3 import combined as CB
        return CB.ask_combined(index, question, tiers, budget, view=view, effort=effort, nodes=nodes, grammar=grammar, grammar_intake=grammar_intake,
                               **({"flat_order": flat_order} if flat_order is not None else {}), **kw)
    if grammar == "on" and structure != "flat":
        raise ValueError("grammar='on' is built for structure 'flat' and 'combined' (G3-k, L-806)")
    if structure == "slide":
        if (tiers is not None and parse_tiers(tiers) != ("RUN",)) or granularity:
            raise ValueError("structure='slide' reads the RUN tier only and has no granularity option (G3-e, L-654)")
        from verantyx.line3 import slide_query as SQ
        return SQ.ask_slide(index, question, effort=effort, nodes=nodes, **kw)
    names = parse_tiers(tiers) if tiers is not None else index.tiers
    for n in names:
        if n not in index.stores:
            raise ValueError("tier %s is not in this index" % n)
    if view not in VIEWS:
        raise ValueError("view: %s" % " | ".join(VIEWS))
    name, cap, lv = resolve_effort(effort, nodes)
    if cap is not None:
        kw["read_cap"] = cap
    if lv != cy.RAISE_LEVELS_DEFAULT:
        if lv:
            kw["raise_levels"] = lv
        else:
            kw["raise_budget"] = None
    gi = None
    forder = None
    if grammar == "on":                                  # G3-k (L-801..L-805)
        from verantyx.line3 import wiring as W
        forder = W.flat_order_of(flat_order)             # G3-k2 (L-819, L-820)
        _ix, recs = W.context_of(index)
        gi = grammar_intake if grammar_intake is not None else W.intake(index.space, question, _ix)
        orig = frozenset(gi.units)
        outs = []
        for t in names:
            o = ask_tier_outcome(index, t, question, budget, **dict(kw, **W.tier_kw(gi, t, recs, forder)))
            outs.append(replace(o, via_standin=W.via_standin_of(o.answer, orig, index.stores[t]) if t == W.TIER else tuple(False for _ in o.entries),
                                read_via_standin=(W.read_via_standin_of(o.answer, o.result.plan.order_only_read) if t == W.TIER
                                                  else tuple(False for _ in o.entries))))
    else:
        outs = [ask_tier_outcome(index, t, question, budget, **kw) for t in names]
    c = combine(question, outs, index.space, index.level, budget, view, name, cap, lv,
                None if index.placement_is_default else placement_obj(index.group_insert, index.order, index.on_collapse))
    if gi is not None:
        c = replace(c, grammar={"form": gi.grammar_form(forder), "standins": gi.standins_obj(), "order": forder,
                                "full": {"form": gi.grammar_form(forder), "order": forder, "standins": gi.standins_obj(True), "reading": gi.reading.to_obj(),
                                         "stem": "whole_word", "foundation_sha256": W.gr.foundation_sha()}})
    if granularity:                                      # F2 (L-485), opt-in: granularity.SCOPES, or True = the default scope
        from verantyx.line3 import granularity as gr
        c = replace(c, assembled=gr.assemble_combined(
            c, index.space, gr.DEFAULT_SCOPE if granularity is True else granularity))
    return c


# --------------------------------------------------------------------------
# text form for the command line
# --------------------------------------------------------------------------
MARKS_TEXT = (("via_standin", "【未知語の代役のみ】"), ("read_via_standin", "【代役の並びで読んだ十字】"))     # G3-k2 (L-821): both marks (the words of combined.MARK_TEXT)


def _marks_text(e: dict) -> str:
    """Both marks of an entry (named in the dict only with the grammar on, so the grammar-off text is unchanged)."""
    return "".join(t for k, t in MARKS_TEXT if e.get(k))


def format_text(c: Combined, show_thought: bool = False) -> str:
    a = c.answer_obj()
    L: List[str] = []
    rd = a["read"]
    if c.grammar is not None:                            # G3-k (L-805)
        gf = c.grammar["form"]
        L.append("文法層: 形 %s / slot %s / 述語 %s / 未知語の代役 %d 件 (%s)" % (
            gf["form"], gf["slot"] or "なし", gf["predicate"] or "なし", gf["standin_units"],
            ", ".join("%s: %d/%d" % (w["word"], w["n_standins"], w["pool"]) for w in c.grammar["standins"]) or "未知語なし"))
        L.append("  印の件数 (一覧 %d 件): 未知語の代役のみ %d 件 (via_standin) / 代役の並びで読んだ十字 %d 件 (read_via_standin) / 平らな十字の読む順 %s" % (
            a["listed"], sum(1 for e in a["entries"] if e["via_standin"]), sum(1 for e in a["entries"] if e["read_via_standin"]), c.grammar["order"]))
    if a["verdict"] == ANSWER:
        L.append("答え (%s): %s" % (a["answer"]["tier"], " / ".join(a["answer"]["path_words"])))
        L.append("  参考の中心: %s" % ", ".join(a["answer"]["reference_centres"]))
        if a["entries"] and _marks_text(a["entries"][0]):                       # G3-k2 (L-821): the single entry's marks (grammar on only)
            L.append("  印:%s" % _marks_text(a["entries"][0]))
    elif a["verdict"] == CHOICE:
        if a["view"] == "all":
            L.append("候補 %d 件（全段の候補を段の印つきで並べています。段どうしの票は足していません。選んでください）:" % a["listed"])
        else:
            L.append("候補 %d 件%s (選んでください):" % (a["listed"], "（段どうしが同点）" if a["tie_between_tiers"] else ""))
        last = None
        for i, e in enumerate(a["entries"]):
            if a["view"] == "all" and e["tier"] != last:
                last = e["tier"]
                L.append(" -- 段 %s: %d 件%s" % (e["tier"], a["per_tier_listed"][e["tier"]],
                                               "（最も安定な段）" if e["tier_is_most_stable"] else ""))
            L.append("  [%d] (%s)%s %s  中心: %s  並べ方 %d  安定度 %s" % (
                i, e["tier"], _marks_text(e), " / ".join(e["words"]), ", ".join(e["centres"]), e["arrangements"], e["stability"]))
    else:
        L.append("答えなし: %s" % a["verdict"])
    if rd["partial"]:
        L.append("【部分読み】推論の量 %s（十字 %s 本まで/段）: %s" % (
            rd["effort"], rd["node_budget"],
            " ".join("%s=%d/%d 本読み・%d 本は未読" % (t, v["crosses_read"], v["would_read_in_full"], v["left_unread"])
                     for t, v in rd["per_tier"].items())))
        L.append("  未読の十字に正解があるかもしれません。時間をかけた答え（--effort full）で読み直せます。")
    if rd["rebuild_skipped"]:
        L.append("  配置の作り直しを省いた十字: %s（候補が出なかった段。--effort full なら作り直して再び読みます）" % " ".join(
            "%s=%d 本" % (t, n) for t, n in rd["rebuild_skipped"].items()))
    elif rd["effort"] is not None:
        L.append("推論の量 %s: 予算内で全て読みました（%s）" % (rd["effort"], " ".join(
            "%s=%d" % (t, v["crosses_read"]) for t, v in rd["per_tier"].items())))
    if c.placement is not None:                          # F1b (L-472)
        L.append("配置の入れ方: %s（同点の組は %s の順に 1 つずつ入れ、崩れたら%s）" % (
            c.placement["group_insert"], "文の語順の逆" if c.placement["order"] == "reverse" else "文の語順",
            "その 1 つだけ飛ばして続ける" if c.placement.get("on_collapse") == "skip" else "直前で止める"))
    if c.assembled is not None:                          # F2 (L-486)
        from verantyx.line3 import granularity as gr
        L.extend(gr.format_lines(c.assembled))
    for s in a["sources"]:
        L.append("  根拠 #%d: %s%s" % (s["sid"], s["text"], " [%s]" % s["source"] if s["source"] else ""))
    if show_thought:
        th = c.thought_obj()
        L.append("--- 思考過程 ---")
        L.append("段: %s  水準: %s  順位: %s" % (",".join(th["tiers_run"]), th["level"],
                                           ", ".join("%s=%s" % (r["tier"], r["stability"]) for r in th["ranking"]) or "なし"))
        for o in c.outcomes:
            cy_ = o.result.thought_obj()
            L.append("  [%s] 判定 %s / 状態 %d / 候補 %d / 十字 %d 読んだ (%d ms)" % (
                o.tier, o.verdict, len(o.result.candidates), len(o.entries),
                cy_["read"]["crosses_read"], o.ms))
            v = (cy_.get("variant") or {})
            br = v.get("budget_raise")
            if br and br.get("needed"):
                L.append("      予算を上げた: %s" % ", ".join(s["level"] for s in br["steps"]))
            L.append("      問いの単位: %s" % " ".join(cy_["query_first_layer"]))
        ag = th["agreement"]["pairs"]
        L.append("段の一致 (報告のみ): %s" % ("; ".join("%s=%s 共通の語 %s" % (p["tiers"][0], p["tiers"][1],
                                                                        ",".join(p["shared_words"]) or "なし") for p in ag) or "比べる対象なし"))
    return "\n".join(L)
