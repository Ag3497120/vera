"""T6ab (3): oracle upper bound.  A user who knows the gold picks an entry containing gold (rule B on that entry's words)
whenever one exists, else abstains; an unanswerable list is rejected (abstain)."""
import collections
from common import *      # noqa
import grade as G

rows = stored_rows()
L = []
out = lambda s="": (L.append(s), print(s))
golds = lambda r: [x.casefold() for x in r["gold"].split("|") if x]
contains = lambda r, e: any(g in w.casefold() for g in golds(r) for w in e["words"])
verdict = lambda r: r["answer"].get("verdict")
base = []      # T6z grading of every question (list = abstention)
for r in rows:
    ans = r["answer"]
    txt = "\n".join(ans["entries"][0]["words"]) if verdict(r) == "ANSWER" else ""
    g, hit, _ = G.grade(G.classify(verdict(r)), r["core"], txt, r["subject"], r["gold"])
    base.append(dict(qid=r["id"], kind=r["kind"], cls=G.classify(verdict(r)), grade=g, gold_hit=hit))
t0 = G.tally(base)
out("## T6ab oracle (S300 RUN; T6z default lists; rule B on an entry's words = a gold string occurs in a word)")
out()
out("| id | kind | entries | gold entries | first gold position (1-based) | positions of gold entries |")
out("|---|---|---|---|---|---|")
add_correct = 0
gl = []
for r in rows:
    if verdict(r) != "CHOICE":
        continue
    ents = r["answer"]["entries"]
    pos = [i + 1 for i, e in enumerate(ents) if contains(r, e)]
    ans_q = r["id"].startswith("a")
    if ans_q and pos:
        add_correct += 1
    if ans_q:
        gl.append((r["id"], len(ents), pos))
    out("| %s | %s | %d | %s | %s | %s |" % (r["id"], r["kind"], len(ents), len(pos) if ans_q else "- (unanswerable)",
                                              pos[0] if ans_q and pos else "-", ",".join(map(str, pos[:12])) + ("..." if len(pos) > 12 else "") if ans_q else "-"))
out()
n_ans_lists = len(gl)
with_gold = [x for x in gl if x[2]]
out("- lists on answerable questions: %d; with at least one gold entry: %d; without: %d; unanswerable lists (rejected): %d" % (
    n_ans_lists, len(with_gold), n_ans_lists - len(with_gold), sum(1 for r in rows if verdict(r) == "CHOICE") - n_ans_lists))
if with_gold:
    ps = sorted(x[2][0] for x in with_gold)
    out("- first gold position over lists with gold: %s (median %s); gold entries share of list: %s" % (
        ps, ps[len(ps) // 2], ["%d/%d" % (len(x[2]), x[1]) for x in with_gold]))
out()
c, w, a = t0["correct"], t0["wrong"], t0["abstain"]
assert c + w + a == 60 and t0["abstain"] >= add_correct
out("| system | correct/wrong/abstain (60 answerable) | unanswerable answered (fict+attr) |")
out("|---|---|---|")
out("| T0 legacy a1 | 45/7/8 | 11 |")
out("| T6z (list = abstention) | %d/%d/%d | %d |" % (c, w, a, t0["answered_unanswerable"]))
out("| **oracle (gold-knowing user picks a gold entry)** | %d/%d/%d | %d (a knowing user rejects unanswerable lists) |" % (
    c + add_correct, w, a - add_correct, t0["answered_unanswerable"]))
out()
out("(non-list abstentions of the 60 answerable stay abstentions: %d have no list at all (UNKNOWN / AMBIGUOUS / no state); oracle recovers %d of the %d list abstentions)" % (
    a - n_ans_lists, add_correct, n_ans_lists))
open(os.path.join(HERE, "results", "oracle.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
