"""T9: build and cache the crosses (RUN/WORD/CHAR, level mid) of the fulllead sentence corpus (same call as t7/precompute.py,
but writes its timing into t9/results/).  usage: precompute.py DATA CACHE [WORKERS=5]"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
from verantyx.line3 import ask as A   # noqa: E402
data, cache = sys.argv[1], sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 5
os.makedirs(cache, exist_ok=True)
t0 = time.time()
idx = A.Index.from_jsonl(data, None, "mid", "RUN,WORD,CHAR")
rep = idx.precompute(cache, workers, log=lambda s: print(s, flush=True))
rep["_workers"] = workers; rep["_total_wall"] = round(time.time() - t0, 1)
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
json.dump(rep, open(os.path.join(HERE, "results", "precompute_timing_%s.json" % os.path.basename(data).split(".")[0]), "w"), indent=1, sort_keys=True)
print(json.dumps(rep, sort_keys=True))
