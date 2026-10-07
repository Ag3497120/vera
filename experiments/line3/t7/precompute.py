"""T7: build the S300 index (space + the crosses of every unit of RUN / WORD / CHAR at level mid, function-word
filter on) and cache it.  usage: precompute.py [DATA=experiments/line3/data/S300.jsonl] [CACHE=<scratch>/line3/t7] [WORKERS=9] [TIERS]"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A                                   # noqa: E402

SCRATCH = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
           "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t7")
data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "experiments/line3/data/S300.jsonl")
cache = sys.argv[2] if len(sys.argv) > 2 else SCRATCH
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 9
tiers = sys.argv[4] if len(sys.argv) > 4 else "RUN,WORD,CHAR"
os.makedirs(cache, exist_ok=True)
t0 = time.time()
idx = A.Index.from_jsonl(data, None, "mid", tiers)
t_space = time.time() - t0
print("space + facts: %.1f s" % t_space, flush=True)
rep = idx.precompute(cache, workers, log=lambda s: print(s, flush=True))
rep["_space_seconds"] = round(t_space, 2)
rep["_workers"] = workers
rep["_total_wall"] = round(time.time() - t0, 1)
json.dump(rep, open(os.path.join(HERE, "precompute_timing.json"), "w"), indent=1, sort_keys=True)
print(json.dumps(rep, sort_keys=True))
