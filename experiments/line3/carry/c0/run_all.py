import subprocess, os
from concurrent.futures import ThreadPoolExecutor
D = "experiments/line3/carry/c0"; PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
jobs = [(m, t, l) for m in ("stream", "single") for t in ("CHAR", "WORD", "RUN") for l in ("high", "mid", "low")]
def go(j):
    m, t, l = j
    with open(f"{D}/logs/{m}_{t}_{l}.log", "w") as f:
        subprocess.run([PY, f"{D}/c0.py", m, t, l, "300", f"{D}/results/{m}_{t}_{l}.json"], stdout=f, stderr=subprocess.STDOUT)
with ThreadPoolExecutor(6) as ex: list(ex.map(go, jobs))
