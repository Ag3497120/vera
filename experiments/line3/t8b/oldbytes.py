"""T8b: print sha256 of the bytes of A.ask (layers off) and of ask_layered with the OLD flags (both variants, same granularity,
candidate bag) for a list of S300 questions at an effort preset.  Run once with PYTHONPATH = the T8 tree and once with the
T8b tree: the two outputs must be identical (L-250 / L-251: the old behaviour is reachable by explicit flags, byte for byte).
usage: oldbytes.py EFFORT ID[,ID...]"""
import hashlib
import os
import sys

from verantyx.line3 import ask as A
from verantyx.line3 import matryoshka as M

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ROOT = os.environ.get("T8B_DATA_ROOT", ROOT)
SCRATCH = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
           "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t7")
effort, ids = sys.argv[1], sys.argv[2].split(",")
idx = A.Index.from_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"), SCRATCH)
rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
h = lambda b: hashlib.sha256(b).hexdigest()[:16]
for r in rows:
    if r[0] not in ids:
        continue
    c0 = A.ask(idx, r[3], effort=effort)
    kw = dict(variants=M.VARIANTS, granularity="same", feedback="none", bounds=M.bounds_for(effort))
    if "candidate" in M.LayerOptions.__dataclass_fields__:
        kw["candidate"] = "bag"
    c = M.ask_layered(idx, r[3], effort=effort, options=M.LayerOptions(**kw), base=c0)
    print(r[0], "off", h(c0.to_bytes()), "on-old", h(c.to_bytes()), "stacked", c.stacked, len(c.listed()))
