"""T6v shared helpers (experiment side only).  The function-word rule is T6's L-130 `func_pos`
(experiments/line3/t6/run_readout.py), imported, not re-written."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
for p in (ROOT, os.path.join(ROOT, "experiments", "line3"), os.path.join(ROOT, "experiments", "line3", "t6")):
    if p not in sys.path:
        sys.path.insert(0, p)
_argv = sys.argv
sys.argv = [sys.argv[0]]                       # run_readout reads argv at import (COND/LEVEL only)
import run_readout as RR                       # noqa: E402  (T6: func_pos, hira_only)
sys.argv = _argv
from verantyx.line3.space import build_space, load_jsonl     # noqa: E402

SCRATCH = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
           "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t6v")
os.makedirs(SCRATCH, exist_ok=True)


def unit_filter():
    """V2: per-tier predicate 'is a function word' = T6 L-130."""
    return {tn: (lambda u, tn=tn: RR.func_pos(u, tn)) for tn in ("RUN", "WORD", "CHAR")}


def data_rows(cond):
    return load_jsonl(os.path.join(ROOT, "experiments/line3/data/%s.jsonl" % cond))


def space_for(cond, v2):
    return build_space(data_rows(cond), unit_filter() if v2 else None)


def questions():
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    return rows
