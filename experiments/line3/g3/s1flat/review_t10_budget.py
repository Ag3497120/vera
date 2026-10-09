"""G3-f review (budget, L-705 / open point 2): T10's flat ask, RUN tier only, on the T10 snapshot code (be923510) and the T10 placement cache, at a chosen query budget.
usage (from anywhere; PYTHONHASHSEED=0): review_t10_budget.py PRESET STATES,ENDS OUT.jsonl [WORKERS]
Run: fast 512,64 results/t10_run_fast_b512-64.jsonl 4 (control: the same code at 64,8 reproduced the T10 RUN entries of 6 of 6 questions whose lists changed)."""
import json, multiprocessing as mp, os, sys, time
SNAP = "/Users/motonisihikoudai/Projects/vera-impl/t10_snapshot"
sys.path.insert(0, SNAP)
from verantyx.line3 import ask as A, cycle as cy
assert A.__file__.startswith(SNAP), A.__file__
PRESET, BUD, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
W = int(sys.argv[4]) if len(sys.argv) > 4 else 4
ms_, me_ = (int(x) for x in BUD.split(","))
DATA = SNAP + "/experiments/line3/bank2/data/fulllead_sents.jsonl"
CACHE = "/Users/motonisihikoudai/Projects/vera-impl/cache/f1b"
BANK = SNAP + "/experiments/line3/bank2/bank2.tsv"
G = {}

def _do(row):
    qid, kind, _c, subj, question, gold = row[:6]
    t0 = time.monotonic()
    c = A.ask(G["idx"], question, tiers=("RUN",), budget=cy.QueryBudget(ms_, me_), effort=PRESET)
    o = c.outcomes[0]
    cnt = {k: v for k, v in o.result.counts.items()}
    return {"id": qid, "kind": kind, "gold": gold, "verdict": o.verdict, "ms": int((time.monotonic() - t0) * 1000),
            "entries": [{"words": list(e.words), "centres": list(e.centres), "count": e.count} for e in o.entries], "counts": cnt}

if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    rows = [r for r in rows if r[2] == "fulllead" and r[1] in ("intra2", "unans")]
    G["idx"] = A.Index.from_jsonl(DATA, CACHE, A.DEFAULT_LEVEL, ("RUN",), group_insert="ordered", order="forward")
    print("loaded; %d questions; budget %s; PYTHONHASHSEED=%s" % (len(rows), BUD, os.environ.get("PYTHONHASHSEED")), file=sys.stderr, flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for n, rec in enumerate(mp.get_context("fork").Pool(W).imap_unordered(_do, rows), 1):
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush()
            print("%d/%d %s %.1fs %s %d" % (n, len(rows), rec["id"], rec["ms"] / 1000, rec["verdict"], len(rec["entries"])), file=sys.stderr, flush=True)
