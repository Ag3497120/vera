"""W3-a3 12.7: on the dev verbs, how do the words decided by the old `frame` arm fare in R5?
Rule (registered before measuring): frame_decides = True iff correct >= 3 * wrong_single
(both 0 -> False).  Reads a dev_runs/<NNN>/items.jsonl written by measure_w3a3.py verbs on R5."""
import json
import sys

run = sys.argv[1]
items = [json.loads(l) for l in open(run + "/items.jsonl", encoding="utf-8")]
fr = [i for i in items if i["kind"] == "typed" and i["origin"] == "direct" and "frame@" in i["decided_by"]]
c = sum(i["cls"] == "correct" for i in fr)
w = sum(i["cls"] == "wrong_single" for i in fr)
o = len(fr) - c - w
dec = (c >= 3 * w) and not (c == 0 and w == 0)
print("run:", run)
print("typed dev verbs decided direct with a frame@ arm in decided_by: %d" % len(fr))
print("  correct %d / wrong_single %d / other %d" % (c, w, o))
print("rule: correct >= 3 * wrong_single (both 0 -> False)  ->  frame_decides = %s" % dec)
print("words:")
for i in fr:
    print("  %s gold=%s top=%s cls=%s by=%s" % (i["term"], ",".join(i["gold"]), ",".join(i["top"]), i["cls"], i["decided_by"]))
