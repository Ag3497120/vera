#!/usr/bin/env python3
"""G4-b: a tiny timing of the frozen stack on the first N articles of fulllead (docs/LINE3_G4_GROWTH_METER.md 8: the per-document cost
for the plan's estimate).  One tier (default RUN), level mid, foundation on, 2 workers.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/g4/stack_timing.py [--articles 8] [--tiers RUN] [--level mid] [--foundation on]
        [--workers 2] [--data experiments/line3/bank2/data/fulllead_sents.jsonl] [--save-root DIR] [--json OUT]

Per document: sentences, new units, wall s, CPU s (this process + its worker processes, from getrusage), crosses opened / grown /
rearranged (narrowed) / closed in the step, the cumulative closed share.  The seconds are NOT part of any hashed byte (the state and the ledger
are the same for any worker count).  Never opens vera-impl/hidden.  No network.
"""
import argparse
import json
import os
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from verantyx.line3 import stack as st                      # noqa: E402


def cpu_s():
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--articles", type=int, default=8)
    ap.add_argument("--tiers", default="RUN")
    ap.add_argument("--level", default="mid")
    ap.add_argument("--foundation", default="on", choices=["on", "off"])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bank2", "data", "fulllead_sents.jsonl"))
    ap.add_argument("--save-root", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    docs = st.load_docs(a.data)[:a.articles]
    tiers = tuple(t for t in a.tiers.split(","))
    state = st.empty_state(a.foundation, tiers, a.level)
    rec = []
    print("articles=%d tiers=%s level=%s foundation=%s workers=%d  load1=%s" % (len(docs), ",".join(tiers), a.level, a.foundation, a.workers,
                                                                                 os.getloadavg()[0]))
    print("%4s %5s %5s %8s %8s | %s" % ("step", "sent", "units", "wall_s", "cpu_s", "per tier: crosses open/grow/narrow/closed(step) closed(total)"))
    t_all, c_all = time.time(), cpu_s()
    for doc in docs:
        stats = {}
        t0, c0 = time.time(), cpu_s()
        state = st.extend(state, doc, a.workers, stats)
        wall, cpu = time.time() - t0, cpu_s() - c0
        row = {"step": state.step, "title": doc[0].get("title"), "sentences": len(doc), "wall_s": round(wall, 2), "cpu_s": round(cpu, 2), "tiers": {}}
        parts = []
        for t in tiers:
            e = json.loads(state.ledger[t][-1])
            tot = len(state.crosses[t])
            closed_total = sum(1 for c in state.crosses[t].values() if c.closed)
            row["tiers"][t] = {"crosses": tot, "opened": len(e["opened"]), "grown": len(e["grown"]),
                               "filled": sum(len(g["filled"]) for g in e["grown"]), "narrowed": sum(1 for g in e["grown"] if g["narrowed"]),
                               "closed_in_step": len(e["closed"]), "closed_total": closed_total, "touched": e["touched"],
                               "left_after": sum(e["left_after"].values())}
            parts.append("%s %d %d/%d/%d/%d (%d) %d" % (t, tot, len(e["opened"]), len(e["grown"]), row["tiers"][t]["narrowed"], len(e["closed"]),
                                                       row["tiers"][t]["filled"], closed_total))
        row["new_units"] = sum(r["opened"] for r in row["tiers"].values())
        rec.append(row)
        print("%4d %5d %5d %8.1f %8.1f | %s" % (state.step, len(doc), row["new_units"], wall, cpu, " ; ".join(parts)), flush=True)
        if a.save_root:
            st.save(state, a.save_root)
    wall, cpu = time.time() - t_all, cpu_s() - c_all
    n_sent = sum(len(d) for d in docs)
    print("TOTAL wall %.1f s  cpu %.1f s  sentences %d  per document: wall %.1f s cpu %.1f s  per sentence: wall %.1f s cpu %.1f s" % (
        wall, cpu, n_sent, wall / len(docs), cpu / len(docs), wall / n_sent, cpu / n_sent))
    print("state_sha256 %s" % " ".join("%s=%s" % (t, state.shas[t][:16]) for t in tiers))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"args": vars(a), "rows": rec, "total": {"wall_s": round(wall, 1), "cpu_s": round(cpu, 1), "sentences": n_sent},
                       "state_sha256": {t: state.shas[t] for t in tiers}, "load1_end": os.getloadavg()[0]}, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
