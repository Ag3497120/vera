"""T6x B follow-up: for the questions that gain an adopted state at a higher budget level, read the answer
out (official form) and check whether a gold string is in the path words."""
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import cycle as cy, placement as pl, readout as ro      # noqa: E402
from verantyx.line3.space import build_space, load_jsonl                    # noqa: E402

PK = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
      "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t6v/placements_V2_S300_RUN_mid.pkl")
t = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"))).tiers["RUN"]
base = pickle.load(open(PK, "rb"))["placements"]
f = cy.TierFacts(t)
w = pl.Weights(t)
D = {d["id"]: d for d in json.load(open(os.path.join(HERE, "results", "capacity_diag_query_crosses.json")))}
rows = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")}
res = {}
for qid, lv in (("a19", "high"), ("a19", "max"), ("a06", "max"), ("a32", "max")):
    d = D[qid]
    pls = dict(base)
    for s in d["budget_limited"]:
        pls[s] = pl.build_cross(t, s, w, budget=pl.budget_level(lv))
    r = cy.ask_tier(t, rows[qid][3], cy.PlacementStore(pls), facts=f, budget=cy.QueryBudget(64, 8))
    a = ro.read_out_result(t, r, f)
    o = a.answer_obj()
    gold = [g.casefold() for g in rows[qid][4].split("|") if g]
    texts = ["".join(p["words"]).casefold() for it in o["items"] for p in it["paths"]]
    hit = any(g in x for g in gold for x in texts)
    first = o["items"][0]
    res[qid + "/" + lv] = {"cycle": r.verdict, "answer": a.verdict, "items": len(o["items"]), "gold": rows[qid][4], "gold_in_path": hit,
                           "subject": rows[qid][2], "example_item": {"centre": first["centre"],
                                                                    "paths": [(p["attached"], p["words"]) for p in first["paths"]]}}
    print(qid, lv, json.dumps(res[qid + "/" + lv], ensure_ascii=False), flush=True)
json.dump(res, open(os.path.join(HERE, "results", "budget_effect_gold.json"), "w"), ensure_ascii=False, indent=1)
