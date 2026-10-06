"""T6w: all 90 fixed questions on S300 RUN with the NEW DEFAULTS (V1 query crosses, V2 function words
not units, V3 adopt by shared sentences) and the new answer form (agreed centre + section-path
words).  Parallel over questions (multiprocessing pool, longest-first by the T6v V123 time, which is a
schedule only).  Per question: ask_tier time, read-out time, trace-check time are recorded.

usage: run_all.py [WORKERS=9] [TIER=RUN] [OUT=results/S300_RUN_new_defaults.jsonl]
"""
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
from verantyx.line3 import readout as ro                     # noqa: E402
from verantyx.line3 import trace_check as tc                 # noqa: E402
from verantyx.line3.space import build_space, load_jsonl     # noqa: E402

COND = "S300"
workers = int(sys.argv[1]) if len(sys.argv) > 1 else 9
TN = sys.argv[2] if len(sys.argv) > 2 else "RUN"
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "results", "S300_%s_new_defaults.jsonl" % TN)
PK = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
      "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t6v/placements_V2_%s_%s_mid.pkl" % (COND, TN))
BUDGET = cy.QueryBudget(64, 8)
G = {}


def _init():
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/%s.jsonl" % COND)))   # DEFAULT space (V2)
    t = sp.tiers[TN]
    d = pickle.load(open(PK, "rb"))
    assert set(d["placements"]) == set(t.units()), "placements are not those of the default space"
    G["t"], G["facts"], G["pl"] = t, cy.TierFacts(t), cy.PlacementStore(d["placements"])


def _work(row):
    qid, kind, subj, question, gold = row[:5]
    t, facts = G["t"], G["facts"]
    t0 = time.time()
    res = cy.ask_tier(t, question, G["pl"], facts=facts, budget=BUDGET)          # all defaults
    t1 = time.time()
    rec = {"id": qid, "kind": kind, "question": question, "gold": gold, "subject": subj,
           "cycle": res.answer_obj(), "variant": res.variant, "query_used": list(res.ctx.query),
           "crosses_read": len(res.plan.read), "members_read": res.members_read,
           "states_adopted": len(res.candidates), "secs_ask": round(t1 - t0, 3)}
    if res.candidates:
        ans = ro.read_out_result(t, res, facts)
        t2 = time.time()
        _, rep = tc.trace_readout(t, ans)
        t3 = time.time()
        rec["answer"] = ans.answer_obj()
        rec["counts"] = ans.thought_obj()["counts"]
        rec["trace"] = rep.to_json_obj()
        rec["trace_ok"] = rep.ok
        rec["secs_readout"] = round(t2 - t1, 3)
        rec["secs_trace"] = round(t3 - t2, 3)
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
        rec["answer"] = {"form": "centre_paths", "verdict": None}
        rec["core"] = ""
    rec["secs_total"] = round(time.time() - t0, 3)
    return rec


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    prev = {}
    for fn in os.listdir(os.path.join(ROOT, "experiments/line3/t6v/results")):
        if fn.startswith("S300_%s_V123." % TN):
            for l in open(os.path.join(ROOT, "experiments/line3/t6v/results", fn), encoding="utf-8"):
                r = json.loads(l)
                prev[r["id"]] = r["secs"]
    rows.sort(key=lambda r: -prev.get(r[0], 0))
    t0 = time.time()
    n = 0
    with open(OUT, "w", encoding="utf-8") as fo, mp.Pool(workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(_work, rows):
            fo.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            fo.flush()
            n += 1
            print(rec["id"], rec["cycle"]["verdict"], rec["answer"].get("verdict"), rec["secs_total"], flush=True)
    print("TOTAL wall", round(time.time() - t0, 1), "s", n, "questions", workers, "workers", flush=True)
