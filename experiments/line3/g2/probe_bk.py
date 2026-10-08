"""G2 probe 3 (trivial kind baseline B-K): question slot p = P7 particle after the interrogative phrase.
Candidates = content-token runs (consecutive content WORD tokens, punctuation not skipped inside) immediately followed by p
(punctuation skipped) in fulllead sentences that contain a content WORD token of the question.  Hit = a gold alternative inside a candidate."""
import json, os, sys, statistics as st
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_particles.py")).read().split("# (1) corpus")[0])
rows = [l.rstrip("\n").split("\t") for l in open(ROOT + "/experiments/line3/bank2/bank2.tsv", encoding="utf-8") if not l.startswith("#")]
rows = [r for r in rows if r[2] == "fulllead"]
TS = [(r["source"], toks(strip_attribution(r["sent"]))) for r in sents]
def runs_before(ts, p):
    out = []
    for j in range(len(ts)):
        if not is_content(ts[j][0]): continue
        if j + 1 < len(ts) and is_content(ts[j + 1][0]): continue       # end of a content run
        if nxt_p(ts, j) != p: continue
        i = j
        while i - 1 >= 0 and is_content(ts[i - 1][0]): i -= 1
        out.append("".join(t[0] for t in ts[i:j + 1]))
    return out
res = {"intra2": [], "unans": []}
for r in rows:
    qid, kind, _, subj, q, gold, ev = r[:7]
    qt = toks(q); qc = {s for s, a, b, p1 in qt if is_content(s)}
    slot = None
    for j, (s, a, b, p1) in enumerate(qt):
        if s in INTERROG:
            k = j
            while k + 1 < len(qt) and is_content(qt[k + 1][0]): k += 1
            slot = nxt_p(qt, k); break
    if slot not in P7: continue
    cands = []
    for src_, ts in TS:
        if qc & {t[0] for t in ts}:
            cands += runs_before(ts, slot)
    cands = sorted(set(cands))
    hit = bool(gold) and any(any(g in c for c in cands) for g in gold.split("|"))
    res[kind].append((qid, slot, len(cands), hit))
for k, v in res.items():
    if not v: continue
    print(k, "questions with a P7 slot", len(v), "hits", sum(1 for x in v if x[3]), "list size median/max", st.median(x[2] for x in v), max(x[2] for x in v), "empty lists", sum(1 for x in v if x[2] == 0))
    print("  ", v)
