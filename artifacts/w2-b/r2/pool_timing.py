"""Time every registered spec (mine and W2-a's), alone and in an 8-thread pool.  Scratch only."""
import sys, time, tempfile, json, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
W = os.environ["W"]
sys.path.insert(0, W + "/tests")
import test_conduct_run_support as s
import test_conduct_verify, test_conduct_verify_settings  # noqa
mode = sys.argv[1]
if mode in ("all", "w2a"):
    import test_conduct_run, test_conduct_run_policy, test_conduct_run_settings  # noqa
prefixes = {"verify", "vset"} if mode == "mine" else (None if mode == "all" else {"run", "policy"})
specs = {k: v for k, v in s._SPECS.items() if prefixes is None or k.split(":")[0] in prefixes}
tmp = Path(tempfile.mkdtemp(prefix="w2b-r2-timing-", dir=os.environ["SCR"]))
times = {}
def timed(key, fn, base):
    t = time.monotonic()
    try:
        fn(base)
    except BaseException as e:  # noqa
        times[key] = (time.monotonic() - t, repr(e)[:80])
        return
    times[key] = (time.monotonic() - t, "")
bases = {k: tmp / f"{i}-{k.replace(chr(58), chr(45))[:20]}" for i, k in enumerate(specs)}
for b in bases.values(): b.mkdir()
t0 = time.monotonic()
with ThreadPoolExecutor(max_workers=8) as pool:
    for k, fn in specs.items():
        pool.submit(timed, k, fn, bases[k])
total = time.monotonic() - t0
for k, (d, e) in sorted(times.items(), key=lambda kv: -kv[1][0]):
    print(f"{d:6.2f}  {k} {e}")
print(f"POOL TOTAL {total:.2f}s  n={len(specs)}  sum={sum(d for d,_ in times.values()):.1f}")
