"""What the owner's rule 「最初の類にも max_class をかける」 (L-G4-47) changes in a cache of foundation-OFF placements, without rebuilding the cache.

  python experiments/line3/g4/replay_explored.py --cache /Users/motonisihikoudai/Projects/vera-impl/cache/f1b [--tiers RUN,WORD,CHAR] [--level mid]
                                                  [--data experiments/line3/bank2/data/fulllead_sents.jsonl] [--replay K|all] [--workers 2]

The rule: `placement._settle` raises "max_class" as soon as the class built from the terminal arrangements holds more than max_class arrangements; before, it
checked max_class only when a class GREW, so such a class was either kept (never checked) or refused one tick later (at its first growth).  The "number of
states handled" (`Step.explored`, `Work.n`) of a refusal therefore drops: the old code ticked queue states until the first one that added an equal-key
arrangement (usually the first, so 1, but a class whose first states add nothing costs more ticks: measured 1 mostly, 3 once), the new check raises before the
first tick.  The owner accepted that counting difference (no byte-preserving tick).

Two parts.
 1. FROM THE STORED RECORDS (instant, exact for what the records say), per tier:
    * kept classes: every kept step has class_size <= max_class (and the final class too).  Then NO kept class of the cache is refused by the rule, so
      `members`, `size`, `score`, `L`, `centres`, `steps` before the break are unchanged;
    * the placements that CAN change = those that stopped by the budget with reason max_class (their break is the only thing the rule moves; the change, when
      there is one, is `explored` of broke_on and of the last step, lower by 1) and those with reason max_moves (the rule could turn a max_moves into a
      max_class if the first class was already over max_class); max_states breaks happen during the insertion, before the check, and cannot change.
      These are upper bounds: whether the first class of a given break was over max_class is not stored.
 2. BY REPLAY of the breaking batch only (--replay K|all; default 0 = skip): the last kept class (stored `members`) is extended by the breaking member, inserted and
    settled with the CURRENT placement.py under the stored budget, exactly as build_cross does for that step (a batch of one: group_insert ordered), and compared with
    the stored broke_on.  Outcomes: same (reason, explored); explored lower (by 1 or a few: a histogram `delta`) with the same reason max_class; reason moved max_moves -> max_class (explored
    may differ); anything else -- a refusal that no longer happens, a higher explored, another reason -- is asserted to be none.  K = that many candidates per tier, evenly spaced over the seed-sorted candidates (`i*(m-1)//(K-1)`), or all.
    Only the one breaking step of each placement is replayed, never the whole cross.
Never opens vera-impl/hidden.  No network.  PYTHONHASHSEED=0 for the recorded runs; at most 4 processes.
"""
import argparse
import json
import multiprocessing as mp
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from verantyx.line3 import placement as pl           # noqa: E402
from verantyx.line3 import space as sp               # noqa: E402

DATA = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")
GROUP_INSERT, ORDER = "ordered", "forward"
_G: dict = {}


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(cache, data_sha, tier, level):
    path = os.path.join(cache, "placements_%s_%s_%s_%s-%s.pkl" % (data_sha[:12], tier, level, GROUP_INSERT, ORDER))
    with open(path, "rb") as f:
        d = pickle.load(f)
    return d["placements"], path


def from_records(ps):
    """Part 1: counts from the stored records only."""
    c = {"placements": len(ps), "stopped_by_budget": 0, "by_reason": {}, "kept_steps_over_max_class": 0, "final_class_over_max_class": 0,
         "max_kept_class": 0, "on_collapse_not_stop": 0, "break_is_last_step": 0}
    for p in ps.values():
        if p.on_collapse != "stop" or p.group_insert != GROUP_INSERT:
            c["on_collapse_not_stop"] += 1
        mx = p.budget.max_class
        for st in p.steps:
            if st.status == pl.STABLE and st.class_size is not None:
                c["max_kept_class"] = max(c["max_kept_class"], st.class_size)
                if st.class_size > mx:
                    c["kept_steps_over_max_class"] += 1
        if len(p.members) > mx:
            c["final_class_over_max_class"] += 1
        if p.stop == pl.BUDGET:
            c["stopped_by_budget"] += 1
            r = p.broke_on.reason if p.broke_on else "?"
            c["by_reason"][r] = c["by_reason"].get(r, 0) + 1
            if p.steps and p.steps[-1] == p.broke_on:
                c["break_is_last_step"] += 1
    c["by_reason"] = dict(sorted(c["by_reason"].items()))
    c["can_change_explored"] = c["by_reason"].get("max_class", 0)          # upper bound: explored lower by 1 where the first class was over max_class
    c["can_change_reason"] = c["by_reason"].get("max_moves", 0)           # upper bound: max_moves -> max_class where the first class was over max_class
    c["unchanged_for_certain"] = c["placements"] - c["can_change_explored"] - c["can_change_reason"]
    return c


def _replay(seed):
    ts, w, budget, ps = _G["ts"], _G["w"], _G["budget"], _G["ps"]
    p = ps[seed]
    groups = pl._groups(ts, seed)
    pool = [seed] + [u for _, g in groups for u in g]
    rep = pl.find_twins(w, pool)
    qw = pl.QWeights(w, rep)
    state = tuple(sorted({pl.canon(tuple(None if x is None else rep[x] for x in f), p.L) for f in p.members}, key=pl._flat_sort_key))
    batch = p.broke_on.units
    L2 = pl.min_L(p.size + len(batch))
    bases = [pl.extend(s, p.L, L2) if L2 > p.L else s for s in state]
    work = pl._Work(budget)
    try:
        starts = pl._insert_group(qw, bases, L2, [rep[u] for u in batch], work, budget)
        pl._settle(qw, starts, L2, work, budget)
    except pl._Over as e:
        return seed, str(e), work.n
    return seed, None, work.n                                             # no longer breaks (asserted to be none)


def pick(seeds, k):
    if k == "all" or int(k) >= len(seeds):
        return list(seeds)
    k = int(k)
    if k <= 0:
        return []
    if k == 1 or len(seeds) == 1:
        return seeds[:1]
    return [seeds[i * (len(seeds) - 1) // (k - 1)] for i in range(k)]


def by_replay(ts, ps, level, k, workers):
    cand = sorted(s for s, p in ps.items() if p.stop == pl.BUDGET and p.broke_on and p.broke_on.reason in ("max_class", "max_moves"))
    chosen = pick(cand, k)
    _G.update(ts=ts, w=pl.Weights(ts), budget=pl.budget_level(level), ps=ps)
    t0 = time.time()
    if workers <= 1 or len(chosen) < 2:
        res = [_replay(s) for s in chosen]
    else:
        with mp.get_context("fork").Pool(workers) as pool:
            res = list(pool.imap_unordered(_replay, chosen, chunksize=1))
    out = {"candidates": len(cand), "replayed": len(res), "same": 0, "explored_lower": 0, "delta": {}, "explored_lower_seeds": [],
           "reason_max_moves_to_max_class": 0, "other": [], "secs": round(time.time() - t0)}
    for seed, reason, n in sorted(res):
        b = ps[seed].broke_on
        if reason == b.reason and n == b.explored:
            out["same"] += 1
        elif reason == b.reason == "max_class" and n < b.explored:
            out["explored_lower"] += 1
            out["delta"][str(b.explored - n)] = out["delta"].get(str(b.explored - n), 0) + 1
            out["explored_lower_seeds"].append(seed)
        elif b.reason == "max_moves" and reason == "max_class":
            out["reason_max_moves_to_max_class"] += 1
        else:
            out["other"].append([seed, b.reason, b.explored, reason, n])
    out["explored_lower_seeds"] = out["explored_lower_seeds"][:10]
    assert not out["other"], out["other"][:10]                            # nothing else may change
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", required=True)
    ap.add_argument("--data", default=DATA, help="the data file the cache was built from (its sha256[:12] names the cache files)")
    ap.add_argument("--tiers", default="RUN,WORD,CHAR")
    ap.add_argument("--level", default="mid")
    ap.add_argument("--replay", default="0", help="K candidates per tier (evenly spaced), 'all', or 0 = records only")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args(argv)
    if a.workers > 4:
        raise SystemExit("at most 4 processes")
    tiers = [t for t in a.tiers.split(",") if t]
    sha = sha256_file(a.data)
    space = sp.build_space(sp.load_jsonl(a.data)) if a.replay != "0" else None
    report = {"cache": a.cache, "data_sha256": sha, "level": a.level, "tiers": {}}
    for t in tiers:
        ps, path = load(a.cache, sha, t, a.level)
        e = {"file": os.path.basename(path), "records": from_records(ps)}
        r = e["records"]
        assert r["kept_steps_over_max_class"] == 0 and r["final_class_over_max_class"] == 0, r        # no kept class is refused by the rule
        assert r["on_collapse_not_stop"] == 0 and r["break_is_last_step"] == r["stopped_by_budget"], r
        if a.replay != "0":
            e["replay"] = by_replay(space.tiers[t], ps, a.level, a.replay, a.workers)
        report["tiers"][t] = e
        print(t, json.dumps(e, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
