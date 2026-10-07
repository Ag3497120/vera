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
from dataclasses import dataclass
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


def cache_path(cache_dir: str, data_sha: str, tier: str, level: str) -> str:
    return os.path.join(cache_dir, "placements_%s_%s_%s.pkl" % (data_sha[:12], tier, level))


_G: dict = {}                                   # set before the fork; the children inherit it


def _work(seeds):
    t, w, b = _G["tier"], _G["w"], _G["budget"]
    out = []
    for s in seeds:
        t0 = time.time()
        out.append((s, pl.build_cross(t, s, w, budget=b), time.time() - t0))
    return out


def precompute_tier(tier_space, level: str = DEFAULT_LEVEL, workers: int = 1, log=None):
    """The cross of every unit of a tier at a budget level (L-211).  Returns (placements, secs per seed,
    wall seconds).  The placements do not depend on the worker count (every cross is built alone)."""
    b = pl.budget_level(level)
    w = pl.Weights(tier_space)
    units = tier_space.units()
    t0 = time.time()
    res: Dict[str, pl.Placement] = {}
    secs: Dict[str, float] = {}
    if workers <= 1:
        _G.update(tier=tier_space, w=w, budget=b)
        parts = [_work([u]) for u in units]
    else:
        _G.update(tier=tier_space, w=w, budget=b)
        chunks = [units[i:i + 4] for i in range(0, len(units), 4)]
        ctx = mp.get_context("fork")
        with ctx.Pool(workers) as pool:
            parts = list(pool.imap_unordered(_work, chunks))
    for part in parts:
        for s, p, dt in part:
            res[s] = p
            secs[s] = dt
    return {s: res[s] for s in sorted(res)}, secs, time.time() - t0


def save_placements(path: str, tier: str, level: str, data_sha: str, placements, secs, wall: float) -> None:
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        pickle.dump({"format": CACHE_FORMAT, "data_sha256": data_sha, "tier": tier, "level": level,
                     "placements": dict(placements), "secs": dict(secs), "wall_s": wall}, f,
                    protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def load_placements(path: str, tier_space, tier: str, level: str, data_sha: str) -> Dict[str, pl.Placement]:
    """Load a cache file; refuses one that is for other data, another tier or level, or a different unit set."""
    with open(path, "rb") as f:
        d = pickle.load(f)
    if d.get("format") != CACHE_FORMAT or d["data_sha256"] != data_sha or d["tier"] != tier or d["level"] != level:
        raise ValueError("placement cache %s is not for this data / tier / level" % path)
    if set(d["placements"]) != set(tier_space.units()):
        raise ValueError("placement cache %s does not cover exactly the units of the tier" % path)
    return d["placements"]


class _Store:
    """cross_for(seed): the loaded cross, else built on demand at the index's level (Placer, L-07)."""

    def __init__(self, tier_space, level: str, loaded: Optional[Mapping[str, pl.Placement]] = None) -> None:
        self._loaded = dict(loaded or {})
        self.placer = pl.Placer(tier_space, pl.budget_level(level))
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
                 tiers: Sequence[str] = TIERS, loaded: Optional[Mapping[str, Mapping[str, pl.Placement]]] = None) -> None:
        pl.budget_level(level)
        self.space, self.data_sha, self.level = space, data_sha, level
        self.tiers = parse_tiers(tiers)
        self.facts = {t: cy.TierFacts(space.tiers[t]) for t in self.tiers}
        self.stores = {t: _Store(space.tiers[t], level, (loaded or {}).get(t)) for t in self.tiers}

    @classmethod
    def from_jsonl(cls, path: str, cache_dir: Optional[str] = None, level: str = DEFAULT_LEVEL,
                   tiers: Sequence[str] = TIERS) -> "Index":
        sha = file_sha256(path)
        space = build_space(load_jsonl(path))
        loaded = {}
        for t in parse_tiers(tiers):
            if cache_dir:
                p = cache_path(cache_dir, sha, t, level)
                if os.path.exists(p):
                    loaded[t] = load_placements(p, space.tiers[t], t, level, sha)
        return cls(space, sha, level, tiers, loaded)

    def precompute(self, cache_dir: Optional[str] = None, workers: int = 1, log=None) -> Dict[str, dict]:
        """Build the crosses of every unit of every tier (replacing what was loaded) and, with a cache
        directory, write them.  Returns {tier: {units, seconds_wall, seconds_cpu}}."""
        rep = {}
        for t in self.tiers:
            ts = self.space.tiers[t]
            placements, secs, wall = precompute_tier(ts, self.level, workers)
            self.stores[t]._loaded = dict(placements)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
                save_placements(cache_path(cache_dir, self.data_sha, t, self.level), t, self.level, self.data_sha,
                                placements, secs, wall)
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

    @property
    def entries(self) -> Tuple[ro.AnswerEntry, ...]:
        return self.answer.entries if self.answer is not None else ()

    @property
    def stability(self) -> Optional[Fraction]:
        return max((e.stability for e in self.entries), default=None)

    @property
    def verdict(self) -> str:
        return self.answer.verdict if self.answer is not None else self.result.verdict


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

    # ---- output (N-08, N-10) ----
    def answer_obj(self) -> dict:
        one = self.verdict == ANSWER
        ents = []
        for t, e in self.entries:
            ents.append({"tier": t, "words": list(e.words), "arrangements": e.count, "centres": list(e.centres),
                         "stability": _fs(e.stability), "source_sids": list(e.source_sids)})
        sids = sorted({s for _, e in self.entries for s in e.source_sids})
        o = {"verdict": self.verdict, "tiers": list(self.shown), "tie_between_tiers": self.tie_between_tiers,
             "listed": len(self.entries),
             "answer": ({"tier": ents[0]["tier"], "path_words": list(ents[0]["words"]),
                         "source_sids": ents[0]["source_sids"],
                         "reference_centres": ents[0]["centres"]} if one else None),
             "entries": ents,
             "sources": [{"sid": s, "text": self.sentences[s][0], "source": self.sentences[s][1]} for s in sids]}
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
            per[o.tier] = d
        ranked = sorted(((o.stability, o.tier) for o in self.outcomes if o.stability is not None),
                        key=lambda x: (-x[0], x[1]))
        return {"question": self.question, "tiers_run": [o.tier for o in self.outcomes], "level": self.level,
                "query_budget": {"max_states": self.budget.max_states, "max_ends": self.budget.max_ends},
                "rule": "I-16: each tier on its own; the most stable result is taken; a tie between tiers is a list",
                "ranking": [{"tier": t, "stability": _fs(s)} for s, t in ranked],
                "shown_tiers": list(self.shown), "tie_between_tiers": self.tie_between_tiers,
                "agreement": self.agreement(), "tiers": per}

    def to_json_obj(self) -> dict:
        return {"answer": self.answer_obj(), "thought": self.thought_obj()}

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json_obj(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def combine(question: str, outcomes: Sequence[TierOutcome], space: Space, level: str = DEFAULT_LEVEL,
            budget: cy.QueryBudget = DEFAULT_BUDGET) -> Combined:
    """I-16 / I-14 on finished tier outcomes (separate so it can be tested without a search)."""
    outs = tuple(sorted(outcomes, key=lambda o: TIERS.index(o.tier)))
    ranked = [o for o in outs if o.stability is not None]
    if not ranked:
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
                    sum(o.ms for o in outs))


def ask_tier_outcome(index: Index, tier: str, question: str, budget: cy.QueryBudget = DEFAULT_BUDGET,
                     **kw) -> TierOutcome:
    """One tier, separately: the search with the current defaults, then the default read-out."""
    t0 = time.monotonic_ns()
    ts, facts, store = index.space.tiers[tier], index.facts[tier], index.stores[tier]
    res = cy.ask_tier(ts, question, store, facts=facts, budget=budget, weights=store.w, **kw)
    ans = ro.read_out_result(ts, res, facts) if res.candidates else None
    return TierOutcome(tier, res, ans, (time.monotonic_ns() - t0) // 1000000)


def ask(index: Index, question: str, tiers: Optional[Sequence[str]] = None,
        budget: cy.QueryBudget = DEFAULT_BUDGET, **kw) -> Combined:
    """I-25: every requested tier is run (none is skipped because another one answered); I-16: combine."""
    names = parse_tiers(tiers) if tiers is not None else index.tiers
    for n in names:
        if n not in index.stores:
            raise ValueError("tier %s is not in this index" % n)
    outs = [ask_tier_outcome(index, t, question, budget, **kw) for t in names]
    return combine(question, outs, index.space, index.level, budget)


# --------------------------------------------------------------------------
# text form for the command line
# --------------------------------------------------------------------------
def format_text(c: Combined, show_thought: bool = False) -> str:
    a = c.answer_obj()
    L: List[str] = []
    if a["verdict"] == ANSWER:
        L.append("答え (%s): %s" % (a["answer"]["tier"], " / ".join(a["answer"]["path_words"])))
        L.append("  参考の中心: %s" % ", ".join(a["answer"]["reference_centres"]))
    elif a["verdict"] == CHOICE:
        L.append("候補 %d 件%s (選んでください):" % (a["listed"], "（段どうしが同点）" if a["tie_between_tiers"] else ""))
        for i, e in enumerate(a["entries"]):
            L.append("  [%d] (%s) %s  中心: %s  並べ方 %d  安定度 %s" % (
                i, e["tier"], " / ".join(e["words"]), ", ".join(e["centres"]), e["arrangements"], e["stability"]))
    else:
        L.append("答えなし: %s" % a["verdict"])
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
