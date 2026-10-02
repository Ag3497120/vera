"""Run each spec of mine one at a time; report wall and CPU (self + children).  Scratch only."""
import sys, time, tempfile, os, resource
from pathlib import Path
W = os.environ["W"]
sys.path.insert(0, W + "/tests")
import test_conduct_run_support as s
import test_conduct_verify, test_conduct_verify_settings  # noqa
specs = {k: v for k, v in s._SPECS.items() if k.split(":")[0] in {"verify", "vset"}}
tmp = Path(tempfile.mkdtemp(prefix="w2b-r2-serial-", dir=os.environ["SCR"]))
rows = []
for i, (k, fn) in enumerate(specs.items()):
    b = tmp / f"{i}-{k.replace(chr(58), chr(45))[:20]}"; b.mkdir()
    r0 = resource.getrusage(resource.RUSAGE_SELF); c0 = resource.getrusage(resource.RUSAGE_CHILDREN); t = time.monotonic()
    try: fn(b)
    except BaseException as e: print("ERR", k, repr(e)[:100])
    wall = time.monotonic() - t
    r1 = resource.getrusage(resource.RUSAGE_SELF); c1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime) + (c1.ru_utime - c0.ru_utime) + (c1.ru_stime - c0.ru_stime)
    rows.append((wall, cpu, k, (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)))
for wall, cpu, k, own in sorted(rows, reverse=True):
    print(f"wall {wall:5.2f}  cpu {cpu:5.2f}  own(python) {own:5.2f}  {k}")
print(f"SUM wall {sum(r[0] for r in rows):.1f} cpu {sum(r[1] for r in rows):.1f} own {sum(r[3] for r in rows):.1f}")
