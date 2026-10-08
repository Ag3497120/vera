"""T8: the coarse -> fine descent (owner 2026-10-07) on the 90 S300 questions: crosses read and time against the flat read.
usage: descent.py EFFORT OUT [WORKERS] [IDS]    (EFFORT: fast | standard | full = the layer bounds of that preset)
Per question and tier: upper crosses read, lower crosses read (only those under the path), the crosses the whole flat V1 read
would read, entries (words), ms of the coarse and fine parts."""
import json, multiprocessing as mp, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A, matryoshka as M      # noqa: E402
SCRATCH = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
           "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t7")
EFFORT, OUT = sys.argv[1], sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 1
ids = sys.argv[4] if len(sys.argv) > 4 else "all"
G = {}


def _work(row):
    qid, kind, subj, question, gold = row[:5]
    opts = M.LayerOptions(variants=("A",), granularity="same", bounds=M.bounds_for(EFFORT))
    rec = {"id": qid, "gold": gold, "question": question, "effort": EFFORT, "tiers": {}}
    for t in ("RUN", "WORD", "CHAR"):
        d = M.descend_tier(G["idx"], t, question, opts)
        rec["tiers"][t] = {"crosses": d.crosses_read, "ms_coarse": d.ms_coarse, "ms_fine": d.ms_fine,
                           "fine_left": d.fine_left, "coarse_verdict": d.coarse.verdict,
                           "entries": [{"words": list(e.words), "centres": list(e.centres), "count": e.count} for e in d.entries]}
    return rec


def _init():
    G["idx"] = A.Index.from_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"), SCRATCH)


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    if ids != "all":
        rows = [r for r in rows if r[0] in ids.split(",")]
    pool = mp.get_context("fork").Pool(workers, initializer=_init)
    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for rec in pool.imap_unordered(_work, rows):
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); n += 1
            print(n, rec["id"], file=sys.stderr, flush=True)
