"""T6v: queue worker.  One process = one worker; launch as many as there are free cores (more can be
added or stopped at any time).  Each question is claimed by creating results/claims/<key>_<qid>
(O_EXCL), so no question is computed twice.  Reuses run_family's per-question work (memo of
read_cross shared by the variants of one family).

usage: run_queue.py FAMILY TIER VARIANTS [prio]
  prio: every 3rd question first (the T5 WORD sample), then the rest.
Output: results/S300_<TIER>_<VARIANT>.q<pid>.jsonl ; log lines on stdout.
"""
import json
import os
import sys
import time

fam, tn, variants = sys.argv[1], sys.argv[2], sys.argv[3]
prio = len(sys.argv) > 4 and sys.argv[4] == "prio"
sys.argv = [sys.argv[0], fam, tn, "1", "0/1", variants]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_family as R                                           # noqa: E402

if __name__ == "__main__":
    C = R.C
    vs = variants.split(",")
    rows = C.questions()
    if tn == "WORD":
        rows = rows[::3]
    elif tn == "CHAR":
        rows = rows[::9]
    if prio:
        rows = rows[::3] + [r for i, r in enumerate(rows) if i % 3]
    od = os.path.join(C.HERE, "results")
    cd = os.path.join(od, "claims")
    os.makedirs(cd, exist_ok=True)
    key = "%s_%s_%s" % (fam, tn, "+".join(vs))
    # questions already finished (any file of the first variant) are not redone
    import glob
    done = set()
    for p in glob.glob(os.path.join(od, "%s_%s_%s.*jsonl" % (R.COND, tn, vs[0]))):
        for l in open(p, encoding="utf-8"):
            if l.strip():
                done.add(json.loads(l)["id"])
    R._init()
    fs = {v: open(os.path.join(od, "%s_%s_%s.q%d.jsonl" % (R.COND, tn, v, os.getpid())), "a", encoding="utf-8") for v in vs}
    t0 = time.time()
    n = 0
    for row in rows:
        qid = row[0]
        if qid in done:
            continue
        try:
            os.close(os.open(os.path.join(cd, "%s_%s" % (key, qid)), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            continue
        out = R._work(tuple(row[:5]))
        for v, rec in out.items():
            fs[v].write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            fs[v].flush()
        n += 1
        print(qid, {v: (r["secs"], r["cycle"]["verdict"], r["readout"].get("verdict")) for v, r in out.items()}, flush=True)
    print("QUEUE_DONE worker", os.getpid(), "questions", n, "wall", round(time.time() - t0, 1), flush=True)
