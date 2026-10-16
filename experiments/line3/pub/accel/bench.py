"""L-PUB-160..: seconds per write at 100..1000 sentences, VERA_ACCEL=py|inc|c (the synthetic story of experiments/line3/pub/m5m6/perf.py: the same sentences, the same 200 writes per session).

  PYTHONPATH=. PYTHONHASHSEED=0 VERA_ACCEL=c nice -n 10 python experiments/line3/pub/accel/bench.py [--n 1000] [--session 200] [--out FILE]

One process per mode (the mode is read from the environment).  Prints the table and, with --out, writes {mode, n, batches: [{writes_so_far, seconds_per_write}], total_seconds, index_sha,
store_sha} where store_sha is the sha256 over every store file except timing.jsonl (a wall-clock log that is never hashed): the three modes must print the same index_sha and store_sha.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3", "pub", "m5m6"))

import perf  # noqa: E402
from common import mem  # noqa: E402


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


def run(n: int, per: int) -> dict:
    tmp = tempfile.mkdtemp(prefix="accel_bench_")
    try:
        st = mem.MemStore(tmp + "/store", "p")
        batches, written, s = [], 0, None
        t_batch = 0.0
        t_all = time.perf_counter()
        while written < n:
            if s is not None:
                s.commit()
            s = st.begin("perf", profile=mem.PROFILE_V4)
            s.call("declare_topic", {"text": "基盤整備%d" % (written // per + 1)})
            for _ in range(per):
                if written >= n:
                    break
                t0 = time.perf_counter()
                s.call("write", {"text": perf.sentence(written)})
                t_batch += time.perf_counter() - t0
                written += 1
                if written % 100 == 0 or written == n:
                    k = 100 if written % 100 == 0 else written % 100
                    batches.append({"writes_so_far": written, "seconds_per_write": round(t_batch / k, 4)})
                    t_batch = 0.0
        s.commit()
        total = time.perf_counter() - t_all
        return {"mode": os.environ.get("VERA_ACCEL", "py"), "n": n, "batches": batches, "total_seconds": round(total, 1), "index_sha": st.index().index_sha, "store_sha": store_sha(tmp + "/store")}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def kernels(n_sent: int = 1000, pairs: int = 4000) -> dict:
    """The C kernels against TierSpace.n_pair / p_pair alone (no store): a synthetic tier of `n_sent` sentences over a Zipf-like vocabulary, `pairs` random pairs, microseconds per pair."""
    import random
    from verantyx.accel import cbind
    from verantyx.line3 import space as sp
    rng = random.Random(5)
    vocab = ["w%d" % i for i in range(600)]
    weights = [1.0 / (i + 1) for i in range(600)]
    units = tuple(tuple(rng.choices(vocab, weights, k=rng.randint(4, 14))) for _ in range(n_sent))
    post = {}
    for sid, us in enumerate(units):
        for u in dict.fromkeys(us):
            post.setdefault(u, []).append(sid)
    tier = sp.TierSpace("WORD", units, {u: tuple(v) for u, v in post.items()}, None)
    m = cbind.mirror_of(tier)
    L = cbind.lib()
    qs = [(rng.choice(vocab[:80]), rng.choice(vocab[:80])) for _ in range(pairs)]       # the popular units: long postings, the case a cold cache pays for
    qs = [(x, y) for x, y in qs if x in tier.postings and y in tier.postings]
    t0 = time.perf_counter()
    py = [(tier.n_pair(x, y), tier.p_pair(x, y)) for x, y in qs]
    t_py = time.perf_counter() - t0
    t0 = time.perf_counter()
    cc = [(int(L.vx_n_pair(m.h.p, m.ids[x], m.ids[y], n_sent)), int(L.vx_p_pair(m.h.p, m.ids[x], m.ids[y], n_sent))) for x, y in qs]
    t_c = time.perf_counter() - t0
    return {"pairs": len(qs), "equal": py == cc, "python_us_per_pair": round(1e6 * t_py / len(qs), 2), "c_us_per_pair": round(1e6 * t_c / len(qs), 2), "ratio": round(t_py / t_c, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--session", type=int, default=200)
    ap.add_argument("--out", default=None)
    ap.add_argument("--kernels", action="store_true", help="only the microbenchmark of the C kernels")
    ns = ap.parse_args()
    if ns.kernels:
        print(json.dumps(kernels(), sort_keys=True))
        return 0
    res = run(ns.n, ns.session)
    print(json.dumps(res, sort_keys=True, indent=1))
    if ns.out:
        with open(ns.out, "w", encoding="utf-8") as f:
            f.write(json.dumps(res, sort_keys=True, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
