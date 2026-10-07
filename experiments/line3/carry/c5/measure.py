"""C5 first measurement: the S300 RUN tower (default rule, low, stream order = data file order) answers the 90 T0 questions.
usage: measure.py TIER LEVEL PRESET OUT.jsonl [WORKERS=1] [FALLBACK=none|index] [IDS=all]
       (run from the repo root with PYTHONPATH=.; PRESET fast | standard | full | an integer node budget)
The tower is built once per process run (stream CPU time printed), then the questions are asked, optionally by forked
workers (the tower is inherited, never changed).  Per question: verdict, entries (words, inherited, centres, count,
stability, source sids, chains), units read per level, exact skips, partial counts, wall ms, P-4 trace.
No gold-based decision is made here (summarize.py grades by the oracle rule 'gold in a candidate')."""
import json
import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, os.getcwd())
from verantyx.line3 import carry as C                                  # noqa: E402
from verantyx.line3 import carry_query as CQ                           # noqa: E402
from verantyx.line3 import placement as pl                             # noqa: E402
from verantyx.line3 import space as sp                                 # noqa: E402

tier, level, preset, OUT = sys.argv[1:5]
workers = int(sys.argv[5]) if len(sys.argv) > 5 else 1
fb = sys.argv[6] if len(sys.argv) > 6 else "none"
ids = sys.argv[7] if len(sys.argv) > 7 else "all"
po = sys.argv[8] if len(sys.argv) > 8 else "close"      # carry.build_tower pack_overflow: close (default) | defer
G = {}


def _ask(row):
    qid, kind, subj, question, gold = row[:5]
    kw = {"nodes": int(preset)} if preset.isdigit() else {"effort": preset}
    a = CQ.ask(G["tw"], question, tier_space=G["ts"], fallback=None if fb == "none" else fb, **kw)
    tr = CQ.trace(G["tw"], a, G["ts"])
    o = a.answer_obj()
    return {"id": qid, "kind": kind, "question": question, "gold": gold, "subject": subj, "preset": preset,
            "query": list(a.query), "verdict": a.verdict, "listed": o["listed"],
            "entries": [{k: e[k] for k in ("words", "centres", "arrangements", "stability", "source_sids", "inherited")}
                        | {"chains": [{"entrances": c["entrances"], "links": len(c["links"]), "lateral": c["lateral"]} for c in e["chain"]],
                                                                  "origins": [c["unit"] for c in e["chain"]]}
                        for e in o["entries"]],
            "read": o["read"], "entrance": [list(x) for x in a.entrance],
            "reads": [[r.unit, r.level, r.rq, r.verdict, r.ms] for r in a.reads],
            "ms": a.ms, "bytes_sha": __import__("hashlib").sha256(a.to_bytes()).hexdigest(),
            "trace": {"checked": tr.words_checked, "traced": tr.words_traced, "ok": tr.ok, "local": [tr.local_ok, tr.local_checked],
                      "failures": list(tr.failures[:5])}}


if __name__ == "__main__":
    rows = [json.loads(l) for l in open("experiments/line3/data/S300.jsonl", encoding="utf-8")]
    space = sp.build_space(rows)
    G["ts"] = space.tiers[tier]
    budget = pl.budget_level(level)
    t0 = time.process_time()
    G["tw"] = C.build_tower(tier, G["ts"], list(range(len(rows))), budget, unit_filter="default", **({} if po == "close" else {"pack_overflow": po}))
    print("tower %s %s: levels %s, units %d, packs %d, build %.0f s cpu, sha %s" % (
        tier, level, G["tw"].level_sizes(), len(G["tw"].units()), len(G["tw"].packs), time.process_time() - t0,
        G["tw"].sha256()[:12]), file=sys.stderr, flush=True)
    qs = [l.rstrip("\n").split("\t") for l in open("experiments/line3/questions.tsv", encoding="utf-8")][1:]
    if ids != "all":
        qs = [r for r in qs if r[0] in ids.split(",")]
    t0 = time.time()
    if workers <= 1:
        it, pool = map(_ask, qs), None
    else:
        pool = mp.get_context("fork").Pool(workers)
        it = pool.imap_unordered(_ask, qs)
    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for rec in it:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            n += 1
            print("%d/%d %s %s %d ms" % (n, len(qs), rec["id"], rec["verdict"], rec["ms"]), file=sys.stderr, flush=True)
    print("done %d in %.0f s" % (n, time.time() - t0), file=sys.stderr)
