"""W3-a3 step 4-5: the new ``decide_word`` must give an OLD placement (R5) the answers it stored.

Every headword of R5 is decided again from its stored evidence rows with R5's own config laid over
DEFAULT_CONFIG (how the query opens a placement); state / top / by / origin are compared with the
stored headword row.  Output: the counts and every difference (should be none)."""
import json
import sqlite3
import sys
import time

sys.path.insert(0, "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S")
from verantyx import coarse_types as ct  # noqa: E402

PL = sys.argv[1] if len(sys.argv) > 1 else "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1"
con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % PL, uri=True)
cfg = dict(ct.DEFAULT_CONFIG)
cfg.update(json.loads(con.execute("SELECT v FROM meta WHERE k='config'").fetchone()[0]))
t0 = time.time()
n = diff = 0
examples = []
heads = {r[0]: r[1:] for r in con.execute("SELECT word, state, origin, top, by FROM headwords")}
cur = con.execute("SELECT word, arm, src, type, n, base FROM evidence ORDER BY word")
cur_w, rows = None, []


def check(w, rows):
    global n, diff
    state, origin, top, by = heads[w]
    d = ct.decide_word([(a, s, t, k, b) for (_w, a, s, t, k, b) in rows], cfg)
    got = (d["state"], d.get("origin"), ",".join(d["tops"]), "+".join(d["by"]))
    n += 1
    if got != (state, origin, top, by):
        diff += 1
        if len(examples) < 20:
            examples.append({"word": w, "stored": [state, origin, top, by], "now": list(got)})


for row in cur:
    if row[0] != cur_w:
        if cur_w is not None and cur_w in heads:
            check(cur_w, rows)
        cur_w, rows = row[0], []
    rows.append(row)
if cur_w is not None and cur_w in heads:
    check(cur_w, rows)
# a headword without any evidence row is decided from nothing: UNPLACED, no origin, no top, no arm
seen_ev = {r[0] for r in con.execute("SELECT DISTINCT word FROM evidence")}
no_ev = [w for w in heads if w not in seen_ev]
no_ev_bad = [w for w in no_ev if heads[w][:1] != ("UNPLACED",) or heads[w][1] is not None or heads[w][2] or heads[w][3]]
print(json.dumps({"placement": PL, "headwords": len(heads), "words_with_evidence_decided_again": n,
                  "words_without_evidence": len(no_ev), "words_without_evidence_not_unplaced": len(no_ev_bad),
                  "differences": diff, "examples": examples, "seconds": round(time.time() - t0, 1)},
                 ensure_ascii=False, indent=1))
