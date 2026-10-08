"""T6y 3: ask_tier(raise_budget="on_demand") on the 9 questions that have a budget-stopped cross read (t6x diag).
Records per question: the budget_raise info (from the thought), verdict, states, items (plain / merged), gold in path."""
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

PK = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
      "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t6v/placements_V2_S300_RUN_mid.pkl")
IDS = ["a06", "a10", "a14", "a19", "a23", "a30", "a32", "a42", "a57"]
G = {}


def _init():
    G["t"] = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"))).tiers["RUN"]
    G["pl"] = cy.PlacementStore(pickle.load(open(PK, "rb"))["placements"])
    G["f"] = cy.TierFacts(G["t"])
    G["w"] = pl.Weights(G["t"])
    G["rows"] = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")}


def work(qid):
    t, f = G["t"], G["f"]
    row = G["rows"][qid]
    t0 = time.time()
    r = cy.ask_tier(t, row[3], G["pl"], facts=f, budget=cy.QueryBudget(64, 8), raise_budget="on_demand", weights=G["w"])
    secs_ask = time.time() - t0
    rec = {"id": qid, "question": row[3], "gold": row[4], "budget_raise": r.thought_obj()["variant"]["budget_raise"],
           "verdict": r.verdict, "states": len(r.candidates), "secs_ask": round(secs_ask, 1)}
    if r.candidates:
        golds = [g.casefold() for g in row[4].split("|") if g]
        for name, mg in (("plain", False), ("merged", True)):
            a = ro.read_out_result(t, r, f, merge_sections=mg)
            o = a.answer_obj()
            texts = ["".join(p["words"]).casefold() for it in o["items"] for p in it["paths"]]
            rec[name] = {"verdict": a.verdict, "items": len(o["items"]), "gold_in_path": any(g in x for g in golds for x in texts),
                         "trace_ok": tc.trace_readout(t, a)[1].ok}
    return rec


if __name__ == "__main__":
    out = []
    with mp.Pool(9, initializer=_init) as pool:
        for rec in pool.imap_unordered(work, IDS):
            out.append(rec)
            print(json.dumps(rec, ensure_ascii=False), flush=True)
    out.sort(key=lambda r: r["id"])
    json.dump(out, open(os.path.join(HERE, "results", "budget_raise.json"), "w"), ensure_ascii=False, indent=1)
