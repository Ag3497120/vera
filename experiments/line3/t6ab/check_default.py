"""T6ab (1): the default read-out equals the stored T6z answer object (sha256) on every read-out."""
import sys
from common import *      # noqa
t, facts = tier_and_facts()
n = bad = 0
for r in stored_rows():
    a = readout_default(t, facts, r)
    if a is None:
        continue
    n += 1
    if sha(a.answer_obj()) != sha(r["answer"]):
        bad += 1
        print("MISMATCH", r["id"])
print("default answer object == stored T6z (sha256): %d / %d read-outs" % (n - bad, n))
sys.exit(1 if bad else 0)
