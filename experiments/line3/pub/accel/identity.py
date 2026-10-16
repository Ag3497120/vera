"""L-PUB-160..: the identity proof.  Every workload is run under VERA_ACCEL=py, inc and c, each under PYTHONHASHSEED 0, 1 and 12345; the stores (every file but the wall-clock log
timing.jsonl, which is never hashed), the index_sha, the verify / replay verdicts and the recall results must come out as ONE digest per workload.

Workloads (no model, no API; the held-out splits are never opened):
  dev:LS-D01, dev:LS-D02   the two bank_ls DEV stories as experiments/line3/pub/m5m6/bank_ls_dev.py writes them (one mem.v4 session per story session, the checkpoint questions asked of the
                           live index), plus the sha of the store directory.  `--verify` also replays the store (quadratic: minutes in py).
  meter                    the 36 meter v1 structure stores rebuilt as mem.v4 stores from the model's raw calls (experiments/line3/pub/m2/measure.py `drive`, with verify_store + replay), every
                           recorded question asked of the answer run (memanswer.v3 over the rebuilt store).
  perf:N                   the synthetic story of m5m6/perf.py (N writes, a change clause every 25th)

  PYTHONPATH=. nice -n 10 python experiments/line3/pub/accel/identity.py [--modes py,inc,c] [--seeds 0,1,12345] [--workloads dev:LS-D01,dev:LS-D02,meter,perf:300] [--verify] [--check] [--out DIR]
  (child, used by the parent)  python identity.py --child WORKLOAD
Exit 0 iff every workload has one digest.  Writes identity.json / identity.md into --out when given.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
M5M6 = os.path.join(ROOT, "experiments", "line3", "pub", "m5m6")
DROP = ("elapsed_s", "seconds_at_every_100_writes")


def store_sha(root: str) -> str:
    h = hashlib.sha256()
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            if f in ("timing.jsonl", ".lock"):
                continue
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, root).encode() + b"\0" + open(p, "rb").read() + b"\0")
    return h.hexdigest()


def sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------------
# children
# ------------------------------------------------------------------------------------------------------------
def child_dev(story_id: str, verify: bool) -> Dict[str, Any]:
    sys.path.insert(0, M5M6)
    sys.path.insert(0, ROOT)
    import bank_ls_dev as B
    with open(B.DEV, encoding="utf-8") as f:
        story = next(s for s in (json.loads(ln) for ln in f if ln.strip()) if s["id"] == story_id)
    caught: Dict[str, str] = {}
    real = B.shutil.rmtree

    def rm(path, *a, **k):                                           # run_story deletes its store at the end: hash it first
        if "store" not in caught and os.path.isdir(os.path.join(path, "store")):
            caught["store"] = store_sha(os.path.join(path, "store"))
        return real(path, *a, **k)

    B.shutil.rmtree = rm
    res = B.run_story((story, verify))
    res = {k: v for k, v in res.items() if k not in DROP}
    return {"store_sha": caught.get("store"), "index_sha": res["index_sha"], "verify": res["verify"], "writes": res["writes"], "result_sha": sha(res)}


def child_meter(verify: bool = True) -> Dict[str, Any]:
    sys.path.insert(0, M5M6)
    sys.path.insert(0, ROOT)
    import common as K
    from common import C, ma, mem
    m2 = K.load_m2()
    per: Dict[str, Any] = {}
    import shutil
    for run_dir in C.structure_runs():
        label = C.label(run_dir)
        r = C.load_result(run_dir)
        tmp = tempfile.mkdtemp(prefix="accel_meter_")
        try:
            store = os.path.join(tmp, "store")
            tally, ix, vstat, rstat = m2.drive(store, m2.meter_sessions(os.path.join(run_dir, "store")))
            snap = ma.write_snapshot(store, crosses=True, versions=False)
            qs = []
            for a in sorted(r["answers"], key=lambda a: a["index"]):
                ses = ma.AnswerSession(store, a["q"], "oracle", snapshot=snap, answer_version=ma.ANSWER_V3)
                res = ses.call("recall", {"question": a["q"]})
                qs.append(sha(res))
            per[label] = {"store_sha": store_sha(store), "index_sha": ix.index_sha, "verify": [vstat, rstat], "tally": sha(tally.to_obj()), "recall": sha(qs)}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return {"stores": len(per), "per_store": per, "result_sha": sha(per)}


def child_perf(n: int) -> Dict[str, Any]:
    sys.path.insert(0, M5M6)
    sys.path.insert(0, ROOT)
    import perf
    from common import mem
    import shutil
    tmp = tempfile.mkdtemp(prefix="accel_perf_")
    try:
        st = mem.MemStore(tmp + "/store", "p")
        s, w, sess = None, 0, 0
        while w < n:
            if s is not None:
                s.commit()
            s = st.begin("perf", profile=mem.PROFILE_V4)
            sess += 1
            s.call("declare_topic", {"text": "基盤整備%d" % sess})
            for _ in range(100):
                if w >= n:
                    break
                s.call("write", {"text": perf.sentence(w)})
                w += 1
        s.call("recall", {"question": "決済画面1の期限はいつですか"})
        s.commit()
        v = mem.verify_store(tmp + "/store", mem.FROM_HEADER)
        return {"store_sha": store_sha(tmp + "/store"), "index_sha": st.index().index_sha, "verify": [v["status"], v["replay"]["status"] if "replay" in v else None]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def child(workload: str, verify: bool) -> Dict[str, Any]:
    if workload.startswith("dev:"):
        return child_dev(workload[4:], verify)
    if workload == "meter":
        return child_meter(True)
    if workload.startswith("perf:"):
        return child_perf(int(workload[5:]))
    raise SystemExit("unknown workload %r" % workload)


# ------------------------------------------------------------------------------------------------------------
# the parent
# ------------------------------------------------------------------------------------------------------------
def run_child(workload: str, mode: str, seed: str, verify: bool, check: bool) -> Dict[str, Any]:
    env = dict(os.environ, PYTHONHASHSEED=seed, VERA_ACCEL=mode, PYTHONPATH=ROOT)
    if check and mode != "py":
        env["VERA_ACCEL_CHECK"] = "1"
    cmd = [sys.executable, os.path.abspath(__file__), "--child", workload] + (["--verify"] if verify else [])
    t0 = time.time()
    p = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if p.returncode != 0:
        raise SystemExit("child failed (%s %s seed %s):\n%s" % (workload, mode, seed, p.stderr[-3000:]))
    out = json.loads(p.stdout.strip().splitlines()[-1])
    out["_seconds"] = round(time.time() - t0, 1)
    return out


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--child", default=None)
    ap.add_argument("--modes", default="py,inc,c")
    ap.add_argument("--seeds", default="0,1,12345")
    ap.add_argument("--workloads", default="dev:LS-D01,dev:LS-D02,meter,perf:300")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--check", action="store_true", help="VERA_ACCEL_CHECK=1 in the inc / c children (every corpus and state sha is also compared with the plain code inside the run)")
    ap.add_argument("--out", default=None)
    ns = ap.parse_args(argv)
    if ns.child:
        print(json.dumps(child(ns.child, ns.verify), sort_keys=True))
        return 0
    results: Dict[str, Dict[str, Any]] = {}
    bad: List[str] = []
    for w in ns.workloads.split(","):
        digests: Dict[str, str] = {}
        results[w] = {}
        for seed in ns.seeds.split(","):
            for mode in ns.modes.split(","):
                r = run_child(w, mode, seed, ns.verify, ns.check)
                secs = r.pop("_seconds")
                key = "%s/seed%s" % (mode, seed)
                digests[key] = sha(r)
                results[w][key] = {"digest": digests[key], "seconds": secs, "index_sha": r.get("index_sha"), "store_sha": r.get("store_sha"), "verify": r.get("verify")}
                print("%-12s %-14s %s  %6.1fs" % (w, key, digests[key][:16], secs), flush=True)
        if len(set(digests.values())) != 1:
            bad.append(w)
    print("IDENTICAL for every workload" if not bad else "DIFFERENT: %s" % bad)
    if ns.out:
        os.makedirs(ns.out, exist_ok=True)
        with open(os.path.join(ns.out, "identity.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"modes": ns.modes, "seeds": ns.seeds, "check": ns.check, "verify": ns.verify, "identical": not bad, "results": results}, sort_keys=True, indent=1, ensure_ascii=False) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
