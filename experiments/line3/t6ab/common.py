"""T6ab shared: rebuild the T6z default read-outs of the 90 S300 RUN questions from the STORED cycle states
(no search, no network), so the default answer object can be compared with the stored T6z one."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3"))
from verantyx.line3 import cycle as cy, readout as ro                              # noqa: E402
from verantyx.line3.space import build_space, load_jsonl                          # noqa: E402

STORED = os.path.join(ROOT, "experiments/line3/t6z/results/S300_RUN_t6z_defaults.jsonl")


def sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def stored_rows():
    return sorted((json.loads(l) for l in open(STORED, encoding="utf-8")), key=lambda r: r["id"])


def tier_and_facts():
    t = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl"))).tiers["RUN"]
    return t, cy.TierFacts(t)


def readout_default(t, facts, r, **kw):
    """The default read-out (nothing passed but the question context) of a stored row, or None (no state)."""
    states = ro.states_from_answer_obj(r["cycle"])
    if not states:
        return None
    ctx = cy.make_context(r["query_used"])
    return ro.read_out(facts, ctx, states, question=r["question"], **kw)
