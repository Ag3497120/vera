"""T6aa: all 90 fixed questions on S300 RUN under the NEW DEFAULTS (T6z defaults + common="intersection"); nothing is passed except the search budget.  Same parallel structure as t6x.
usage: run_all.py [WORKERS=9] [OUT=results/S300_RUN_t6aa_common.jsonl]"""
import hashlib
import json
import multiprocessing as mp
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import cycle as cy, placement as pl, readout as ro, trace_check as tc   # noqa: E402
from verantyx.line3.space import build_space, load_jsonl                                   # noqa: E402

workers = int(sys.argv[1]) if len(sys.argv) > 1 else 9
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "results", "S300_RUN_t6aa_common.jsonl")
PK = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
      "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t6v/placements_V2_S300_RUN_mid.pkl")
BUDGET = cy.QueryBudget(64, 8)
G = {}


def _init():
    t = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"))).tiers["RUN"]
    d = pickle.load(open(PK, "rb"))
    assert set(d["placements"]) == set(t.units())
    G["t"], G["facts"], G["pl"], G["w"] = t, cy.TierFacts(t), cy.PlacementStore(d["placements"]), pl.Weights(t)


def _work(row):
    qid, kind, subj, question, gold = row[:5]
    t, facts = G["t"], G["facts"]
    t0 = time.time()
    res = cy.ask_tier(t, question, G["pl"], facts=facts, budget=BUDGET, weights=G["w"])   # defaults otherwise
    t1 = time.time()
    br = (res.thought_obj().get("variant") or {}).get("budget_raise")
    rec = {"id": qid, "kind": kind, "question": question, "gold": gold, "subject": subj,
           "cycle": res.answer_obj(), "query_used": list(res.ctx.query), "crosses_read": len(res.plan.read),
           "states_adopted": len(res.candidates), "budget_raise": br, "secs_ask": round(t1 - t0, 3)}
    if res.candidates:
        ans = ro.read_out_result(t, res, facts)            # defaults: merge_sections, similar="word_set"
        t2 = time.time()
        _, rep = tc.trace_readout(t, ans)
        t3 = time.time()
        rec["answer"] = ans.answer_obj()
        # L-190: common=None must reproduce the stored T6z answer bytes exactly
        old = ro.read_out_result(t, res, facts, common=None).answer_obj()
        rec["legacy_answer_bytes_sha"] = hashlib.sha256(json.dumps(old, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        rec["trace_ok"] = rep.ok
        rec["trace"] = rep.to_json_obj()
        rec["secs_readout"], rec["secs_trace"] = round(t2 - t1, 3), round(t3 - t2, 3)
        core = ""
        for st in ans.states:
            for p in st.paths:
                if p.attached is not None and facts.n.get(p.attached, 0) > 0:
                    core = p.attached
                    break
            if core:
                break
        rec["core"] = core
    else:
        rec["answer"] = {"form": "path_words", "verdict": None}
        rec["core"] = ""
    rec["secs_total"] = round(time.time() - t0, 3)
    return rec


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    prev = {}
    for l in open(os.path.join(ROOT, "experiments/line3/t6x/results/S300_RUN_query_crosses.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        prev[r["id"]] = r["secs_total"]
    big = {"a06", "a19", "a32", "a10", "a14", "a23", "a30", "a42", "a57"}       # the budget-raise ones first
    rows.sort(key=lambda r: (r[0] not in big, -prev.get(r[0], 0)))
    t0 = time.time()
    with open(OUT, "w", encoding="utf-8") as fo, mp.Pool(workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(_work, rows):
            fo.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            fo.flush()
            print(rec["id"], rec["cycle"]["verdict"], rec["answer"].get("verdict"), rec["secs_total"], flush=True)
    print("TOTAL wall", round(time.time() - t0, 1), "s", flush=True)
