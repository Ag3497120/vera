"""T7b: the 90 S300 questions at a node budget (crosses read per tier), all three tiers, placements from the T7 cache.
usage: measure.py PRESET OUT [WORKERS=1] [IDS=all]      PRESET: fast | standard | full | an integer node budget (raise off)
Per question: per tier the verdict, entries, crosses read / left unread / would read in full, wall ms (single question
in a single process; with WORKERS > 1 the times are inflated by contention, so use WORKERS=1 for the times asked for);
the combined all-view list and its size.  No gold-based decision is made here (summarize.py grades)."""
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A                                   # noqa: E402

SCRATCH = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
           "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t7")
nodes = sys.argv[1]
OUT = sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 1
ids = sys.argv[4] if len(sys.argv) > 4 else "all"
DATA = os.path.join(ROOT, "experiments/line3/data/S300.jsonl")
G = {}


def _work(row):
    qid, kind, subj, question, gold = row[:5]
    t0 = time.time()
    c = A.ask(G["idx"], question, **({"nodes": int(nodes)} if nodes.isdigit() else {"effort": nodes}))
    rec = {"id": qid, "kind": kind, "question": question, "gold": gold, "subject": subj, "nodes": nodes, "tiers": {}}
    for o in c.outcomes:
        br = (o.result.thought_obj().get("variant") or {}).get("budget_raise")
        rec["tiers"][o.tier] = {
            "verdict": o.verdict, "stability": A._fs(o.stability), "states": len(o.result.candidates),
            "entries": [{"words": list(e.words), "centres": list(e.centres), "count": e.count,
                         "stability": A._fs(e.stability)} for e in o.entries],
            "raised": bool(br and br.get("needed")), "ms": o.ms, **o.read_counts}
    a = c.answer_obj()
    rec["combined"] = {"verdict": a["verdict"], "listed": a["listed"], "partial": a["read"]["partial"],
                       "entries": [{k: e[k] for k in ("tier", "words", "centres", "stability")} for e in a["entries"]]}
    rec["secs_total"] = round(time.time() - t0, 3)
    return rec


def _init():
    G["idx"] = A.Index.from_jsonl(DATA, SCRATCH)


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    if ids != "all":
        rows = [r for r in rows if r[0] in ids.split(",")]
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    t0 = time.time()
    if workers <= 1:
        _init()
        it, pool = map(_work, rows), None
    else:
        pool = mp.get_context("fork").Pool(workers, initializer=_init)
        it = pool.imap_unordered(_work, rows)
    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for rec in it:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            n += 1
            print("%d/%d %s %.1fs" % (n, len(rows), rec["id"], rec["secs_total"]), file=sys.stderr, flush=True)
    print("done %d in %.0fs" % (n, time.time() - t0), file=sys.stderr)
