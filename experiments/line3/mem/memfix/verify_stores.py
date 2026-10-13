"""MEM-fix: do the STORED ledgers still replay IDENTICAL under this code?  (offline; nothing is written)

  python experiments/line3/mem/memfix/verify_stores.py --loom      every loom run ledger under experiments/line3/loom (chain + replay: `ledger.verify`)
  python experiments/line3/mem/memfix/verify_stores.py --mem       every store / answer run / baseline ledger of experiments/line3/mem/meter_v1
Prints one line per group and exits 1 if anything is not OK.  The change of MEM-fix is behind a new profile / rule version (mem.v3, memanswer.v2, membase.v2, notes mem.v2), so an old
ledger is replayed by the code of the version it records."""
from __future__ import annotations

import argparse
import collections
import os
import sys
from typing import Dict, List, Optional, Sequence

import memfix_common as C
from verantyx.loom import ledger as lg
from verantyx.loom import memanswer as ma
from verantyx.loom import memdoor as md
from verantyx.loom import memory as mem


def loom_run_dirs() -> List[str]:
    base = os.path.join(C.ROOT, "experiments", "line3", "loom")
    out = []
    for dp, dn, fn in os.walk(base):
        if "ops.jsonl" in fn and "HEAD" in fn and "meta.json" in fn:
            out.append(dp)
            dn[:] = []
    return sorted(out)


def verify_loom() -> int:
    groups: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    bad: List[str] = []
    for d in loom_run_dirs():
        grp = os.path.relpath(d, os.path.join(C.ROOT, "experiments", "line3", "loom")).split(os.sep)[0]
        if grp == "baseline_scripted":
            grp = "baseline_scripted/" + os.path.relpath(d, os.path.join(C.ROOT, "experiments", "line3", "loom", "baseline_scripted")).split(os.sep)[0]
        v = lg.verify(d)
        st = v["status"] if v["status"] != "OK" else ("OK" if v.get("replay", {}).get("status") in (None, "IDENTICAL") else v["replay"]["status"])
        groups[grp][st] += 1
        if st != "OK":
            bad.append("%s %s" % (os.path.relpath(d, C.ROOT), st))
    for g, c in sorted(groups.items()):
        print("%-34s %s" % (g, dict(c)))
    print("loom ledgers: %d, not OK: %d" % (sum(sum(c.values()) for c in groups.values()), len(bad)))
    for b in bad[:20]:
        print("  ", b)
    return 1 if bad else 0


def verify_mem(meter: str) -> int:
    n = collections.Counter()
    bad: List[str] = []
    for arm in ("blind", "notes"):
        for d in sorted(__import__("glob").glob(os.path.join(meter, "*", arm, "r*"))):
            store = os.path.join(d, "store")
            r = mem.replay_store(store, mem.FROM_HEADER)
            v = mem.verify_store(store, mem.FROM_HEADER)
            ok = r.identical and v["status"] == "OK"
            n["store"] += 1
            n["store_ok"] += ok
            if not ok:
                bad.append("%s store %s" % (C.label(d), v["status"]))
            for a in sorted(os.listdir(os.path.join(store, "answers"))):
                va = ma.verify_answer(os.path.join(store, "answers", a), store)
                n["answer"] += 1
                n["answer_ok"] += va["status"] == "OK"
                if va["status"] != "OK":
                    bad.append("%s %s %s" % (C.label(d), a, va["status"]))
    for arm in ("context", "log"):
        for d in sorted(__import__("glob").glob(os.path.join(meter, "*", arm, "r*"))):
            store = os.path.join(d, "store")
            for sub in ("sessions", "answers"):
                for x in sorted(os.listdir(os.path.join(store, sub))):
                    vb = md.verify_baseline(os.path.join(store, sub, x))
                    n["baseline"] += 1
                    n["baseline_ok"] += vb["status"] == "OK"
                    if vb["status"] != "OK":
                        bad.append("%s %s/%s %s" % (C.label(d), sub, x, vb["status"]))
    print("meter stores %d ok %d | answer runs %d ok %d | baseline ledgers %d ok %d" % (n["store"], n["store_ok"], n["answer"], n["answer_ok"], n["baseline"], n["baseline_ok"]))
    for b in bad[:20]:
        print("  ", b)
    return 1 if bad else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--loom", action="store_true")
    ap.add_argument("--mem", action="store_true")
    ap.add_argument("--meter", default=C.METER_V1)
    ns = ap.parse_args(argv)
    rc = 0
    if ns.mem:
        rc |= verify_mem(ns.meter)
    if ns.loom:
        rc |= verify_loom()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
