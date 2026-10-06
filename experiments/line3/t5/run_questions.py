"""T5: run the fixed questions (experiments/line3/questions.tsv) through the query cycle, one
tier of one condition, in parallel over questions.  Writes results/<COND>_<TIER>_<LEVEL>_<MS>x<ME>.jsonl
(one line per question: id, kind, question, secs, answer, thought).  NO grading here (T6/T13).

usage: run_questions.py COND TIER LEVEL MAX_STATES MAX_ENDS [WORKERS] [QUESTION_IDS comma-separated]
Needs the cache written by precompute.py (placements_<COND>_<TIER>_<LEVEL>.pkl in the scratchpad).
"""
import json
import multiprocessing as mp
import os
import pickle
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from verantyx.line3 import cycle as cy                           # noqa: E402
from verantyx.line3.space import build_space, load_jsonl        # noqa: E402

SCRATCH = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
           "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t5")
cond, tn, level = sys.argv[1], sys.argv[2], sys.argv[3]
ms, me = int(sys.argv[4]), int(sys.argv[5])
workers = int(sys.argv[6]) if len(sys.argv) > 6 else 9
only = set(sys.argv[7].split(",")) if len(sys.argv) > 7 else None
G = {}


def _init():
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/%s.jsonl" % cond)), unit_filter=None)
    t = sp.tiers[tn]
    d = pickle.load(open(os.path.join(SCRATCH, "placements_%s_%s_%s.pkl" % (cond, tn, level)), "rb"))
    G["t"], G["facts"], G["pl"] = t, cy.TierFacts(t), cy.PlacementStore(d["placements"])


def _work(row):
    qid, kind, _subj, question = row[0], row[1], row[2], row[3]
    t0 = time.time()
    r = cy.ask_tier(G["t"], question, G["pl"], facts=G["facts"], budget=cy.QueryBudget(ms, me),
                    read_rule="whole", state_rule="stability", unit_filter=None)   # the T5 behaviour (explicit since L-150)
    return {"id": qid, "kind": kind, "question": question, "secs": round((time.time() - t0) * 100) / 100,
            "answer": r.answer_obj(), "thought": r.thought_obj()}


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    rows = [r for r in rows if only is None or r[0] in only]
    out = os.path.join(ROOT, "experiments/line3/t5/results/%s_%s_%s_%dx%d.jsonl" % (cond, tn, level, ms, me))
    t0 = time.time()
    done = {}
    with mp.Pool(workers, initializer=_init) as pool, open(out, "w", encoding="utf-8") as f:
        for res in pool.imap(_work, rows):
            done[res["id"]] = res
            f.write(json.dumps(res, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            print(res["id"], res["secs"], res["answer"]["verdict"], res["answer"]["units"], flush=True)
    print("TOTAL wall", round(time.time() - t0, 1), "s; sum per-question", round(sum(r["secs"] for r in done.values()), 1), flush=True)
