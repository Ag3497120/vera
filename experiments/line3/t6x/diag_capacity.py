"""T6x B: capacity diagnosis of the questions that have NO adopted state under the current default
(read_rule="query_crosses"), S300 RUN, default space (V2), placements at level mid.

For every such question (Q = the query units the energies read, after the function-word filter):
  (i)   no cross of the space holds any Q unit (a Q unit absent from the tier / filtered away, or not placed anywhere);
  (ii)  crosses holding a Q unit exist, but only the Q unit's OWN seed cross and that has capacity 1;
  (iii) crosses holding a Q unit exist and are more than that (the cycle ended without a fixed point / ambiguous).
Then, for the crosses involved that stopped by BUDGET (stop == "budget"; an "exhausted" cross cannot grow with any budget),
the cross is rebuilt at level high and max (placement.build_cross), put in place of the mid one, and the question is asked
again with the same rule: does the capacity / the verdict change?

usage: diag_capacity.py [WORKERS=8] [RULE=query_crosses]
"""
import collections
import json
import multiprocessing as mp
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import cycle as cy                       # noqa: E402
from verantyx.line3 import placement as pl                   # noqa: E402
from verantyx.line3.space import build_space, load_jsonl     # noqa: E402

workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
RULE = sys.argv[2] if len(sys.argv) > 2 else "query_crosses"
SCR = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
       "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t6x")
os.makedirs(SCR, exist_ok=True)
PK = "%s/../t6v/placements_V2_S300_RUN_mid.pkl" % SCR
SRC = os.path.join(HERE, "results", "S300_RUN_%s.jsonl" % RULE)
BUDGET = cy.QueryBudget(64, 8)
G = {}


def _init():
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl")))
    t = sp.tiers["RUN"]
    d = pickle.load(open(PK, "rb"))
    G["t"], G["facts"], G["base"], G["w"] = t, cy.TierFacts(t), d["placements"], pl.Weights(t)


def _build(task):
    seed, level = task
    t0 = time.time()
    p = pl.build_cross(G["t"], seed, G["w"], budget=pl.budget_level(level))
    return (seed, level), p, round(time.time() - t0, 2)


def _reask(task):
    qid, question, repl_key, repl = task
    pls = dict(G["base"])
    pls.update(repl)
    t0 = time.time()
    res = cy.ask_tier(G["t"], question, cy.PlacementStore(pls), facts=G["facts"], budget=BUDGET, read_rule=RULE)
    return qid, repl_key, res.verdict, len(res.candidates), len(res.plan.read), round(time.time() - t0, 2)


def units_of(p):
    us = {c for c in pl.from_cross(p.cross) if c is not None}
    for tw in p.twin_sets:
        us.update(tw)
    return us


if __name__ == "__main__":
    _init()
    t, base = G["t"], G["base"]
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    rows.sort(key=lambda r: r["id"])
    nostate = [r for r in rows if r["states_adopted"] == 0]
    inv = collections.defaultdict(set)
    for s, p in base.items():
        for u in units_of(p):
            inv[u].add(s)
    diag = []
    for r in nostate:
        Q = r["energy_units"]
        per_u = []
        for u in Q:
            own = base.get(u)
            per_u.append({"u": u, "in_tier": u in t.postings, "n": len(t.postings.get(u, ())),
                          "crosses_holding": sorted(inv.get(u, ())) if len(inv.get(u, ())) <= 8 else len(inv[u]),
                          "n_crosses_holding": len(inv.get(u, ())),
                          "own": None if own is None else {"capacity": own.capacity, "size": own.size, "stop": own.stop,
                                                           "candidates": own.candidates,
                                                           "reason": own.broke_on.reason if own.broke_on else None,
                                                           "own_contains_u": u in units_of(own)}})
        holding = sorted({s for u in Q for s in inv.get(u, ())})
        if not holding:
            cat = "i"
            sub = ("no query unit left after the filter" if not Q else
                   "all query units absent from the tier" if not any(u in t.postings for u in Q) else
                   "a query unit is in the tier but in no cross")
        else:
            only_own = all(base[s].capacity == 1 and s in Q for s in holding)
            cat, sub = ("ii", "") if only_own else ("iii", r["cycle"]["verdict"])
        caps = {s: (base[s].capacity, base[s].stop) for s in holding}
        diag.append({"id": r["id"], "kind": r["kind"], "question": r["question"], "verdict": r["cycle"]["verdict"], "Q": Q,
                     "category": cat, "sub": sub, "per_unit": per_u, "holding": holding if len(holding) <= 60 else len(holding),
                     "n_holding": len(holding), "caps": {k: list(v) for k, v in caps.items()} if len(holding) <= 60 else None,
                     "cap_hist": dict(sorted(collections.Counter(c for c, _ in caps.values()).items())),
                     "stop_hist": dict(collections.Counter(s for _, s in caps.values()))})
    # crosses to rebuild: involved crosses (holding a Q unit, or the own seed of an in-tier Q unit) stopped by budget
    tasks = set()
    for d in diag:
        inv_seeds = set(d["caps"] or []) if d["caps"] is not None else {s for u in d["Q"] for s in inv.get(u, ())}
        inv_seeds |= {u for u in d["Q"] if u in base}
        d["involved"] = sorted(inv_seeds)
        d["budget_limited"] = sorted(s for s in inv_seeds if base[s].stop == "budget")
        d["exhausted"] = sorted(s for s in inv_seeds if base[s].stop != "budget")
        for s in d["budget_limited"]:
            for lv in ("high", "max"):
                tasks.add((s, lv))
    tasks = sorted(tasks, key=lambda x: (x[1] != "max", x))
    print("crosses to rebuild:", len(tasks), flush=True)
    built = {}
    t0 = time.time()
    with mp.Pool(workers, initializer=_init) as pool:
        for k, p, secs in pool.imap_unordered(_build, tasks):
            built[k] = p
            print("built", k, "capacity", base[k[0]].capacity, "->", p.capacity, p.stop, secs, "s", flush=True)
        print("build wall", round(time.time() - t0, 1), flush=True)
        for d in diag:
            d["rebuilt"] = {s: {lv: {"capacity": built[(s, lv)].capacity, "stop": built[(s, lv)].stop,
                                     "size": built[(s, lv)].size, "contains_Q": bool(units_of(built[(s, lv)]) & set(d["Q"]))}
                                for lv in ("high", "max")} for s in d["budget_limited"]}
        qtasks = []
        for lv in ("high", "max"):
            for d in diag:
                if not d["budget_limited"]:
                    continue
                key = (d["id"], lv)
                qtasks.append((d["id"], d["question"], key, {s: built[(s, lv)] for s in d["budget_limited"]}))
    with mp.Pool(workers, initializer=_init) as pool:
        out = {}
        for qid, key, verdict, ns, nread, secs in pool.imap_unordered(_reask, qtasks):
            out[key] = (verdict, ns, nread, secs)
            print("reask", key, verdict, ns, nread, secs, flush=True)
    for d in diag:
        d["reask"] = {lv: dict(zip(("verdict", "states_adopted", "crosses_read", "secs"), out[(d["id"], lv)]))
                      for lv in ("high", "max") if (d["id"], lv) in out}
    json.dump(diag, open(os.path.join(HERE, "results", "capacity_diag_%s.json" % RULE), "w"), ensure_ascii=False, indent=1)
    print("done", flush=True)
