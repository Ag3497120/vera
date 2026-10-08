"""T7: the 90 fixed questions on S300, all three tiers combined (I-16 / I-25), placements from the cache.
usage: run_all.py [WORKERS=9] [OUT=results/S300_all_tiers.jsonl] [CACHE=<scratch>/line3/t7] [IDS=comma list or 'all']
Every record holds, per tier, the verdict, the stability, every entry (words, centres, arrangements, sources) and the time,
plus the combined answer object; nothing else (no gold-based decision is made here)."""
import hashlib
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
workers = int(sys.argv[1]) if len(sys.argv) > 1 else 9
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "results", "S300_all_tiers.jsonl")
cache = sys.argv[3] if len(sys.argv) > 3 else SCRATCH
ids = sys.argv[4] if len(sys.argv) > 4 else "all"
DATA = os.path.join(ROOT, "experiments/line3/data/S300.jsonl")
G = {}


def sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def core_of(o):
    """The core (T0 grade): the first attached question unit with n > 0 on a section path of the tier's states."""
    if o.answer is None:
        return ""
    facts = G["idx"].facts[o.tier]
    for st in o.answer.states:
        for p in st.paths:
            if p.attached is not None and facts.n.get(p.attached, 0) > 0:
                return p.attached
    return ""


def _work(row):
    qid, kind, subj, question, gold = row[:5]
    t0 = time.time()
    c = A.ask(G["idx"], question)
    rec = {"id": qid, "kind": kind, "question": question, "gold": gold, "subject": subj, "tiers": {}}
    for o in c.outcomes:
        br = (o.result.thought_obj().get("variant") or {}).get("budget_raise")
        rec["tiers"][o.tier] = {
            "verdict": o.verdict, "cycle_verdict": o.result.verdict, "stability": A._fs(o.stability),
            "states": len(o.result.candidates), "core": core_of(o),
            "entries": [{"words": list(e.words), "centres": list(e.centres), "count": e.count,
                         "stability": A._fs(e.stability), "source_sids": list(e.source_sids)} for e in o.entries],
            "readout_answer_sha": sha(o.answer.answer_obj()) if o.answer is not None else None,
            "raised": bool(br and br.get("needed")), "ms": o.ms, "crosses_read": len(o.result.plan.read),
            "query_units": list(o.result.ctx.qcross.units)}
    a = c.answer_obj()
    rec["combined"] = {"verdict": a["verdict"], "shown": a["tiers"], "tie_between_tiers": a["tie_between_tiers"],
                       "listed": a["listed"], "answer": a["answer"],
                       "entries": [{k: e[k] for k in ("tier", "words", "centres", "stability")} for e in a["entries"]]}
    rec["agreement"] = c.agreement()["pairs"]
    rec["secs_total"] = round(time.time() - t0, 3)
    return rec


def _init():
    G["idx"] = A.Index.from_jsonl(DATA, cache)


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    if ids != "all":
        rows = [r for r in rows if r[0] in ids.split(",")]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    t0 = time.time()
    if workers <= 1:
        _init()
        it = map(_work, rows)
        pool = None
    else:
        pool = mp.get_context("fork").Pool(workers, initializer=_init)
        it = pool.imap_unordered(_work, rows)
    with open(OUT, "w", encoding="utf-8") as fo:
        for rec in it:
            fo.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            fo.flush()
            print(rec["id"], rec["combined"]["verdict"], rec["combined"]["shown"], rec["secs_total"], flush=True)
    print("TOTAL wall", round(time.time() - t0, 1), "s", flush=True)
