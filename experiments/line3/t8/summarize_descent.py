"""T8 descent summary: coarse -> fine search vs the flat read (T7b results as the flat references; flat times were measured
with the same worker setup). usage: summarize_descent.py OUT.md"""
import json, statistics, sys
HERE = "experiments/line3/"
T = ("RUN", "WORD", "CHAR")
L = []
def out(s=""):
    L.append(s); print(s)
def load(p):
    return {json.loads(l)["id"]: json.loads(l) for l in open(p, encoding="utf-8")}
med = statistics.median
def hit(r, e):
    g = [x.casefold() for x in r["gold"].split("|") if x]
    return any(x in w.casefold() for x in g for w in e["words"])
flat = {"fast": load(HERE + "t7b/results/S300_fast.jsonl"), "standard": load(HERE + "t7b/results/S300_standard.jsonl"),
        "full": load(HERE + "t7b/results/S300_full_T7.jsonl")}
desc = {}
for e in ("fast", "standard", "full"):
    try:
        desc[e] = load(HERE + "t8/results/descent_%s.jsonl" % e)
    except OSError:
        pass
ids = sorted(next(iter(desc.values())))
A_ = [i for i in ids if i.startswith("a")]; U_ = [i for i in ids if not i.startswith("a")]
out("# T8 descent (coarse -> fine) vs the flat read, S300 90 questions")
out()
out("Descent = the question is read on the packed upper crosses (one cross per question unit), then ONLY the lower crosses under the elements of the selected path are read (capped by the preset's node budget). Flat = the T7b read of the same preset (fast 4 / standard 10 crosses per tier, full = every cross holding a question unit). Candidates are pooled over the three tiers as in T7b.")
out()
out("| search | answerable: gold in a candidate | no candidate | unanswerable: no candidate / list / single | crosses read per question (sum of 3 tiers) median / mean | wall s per question median / p90 |")
out("|---|---|---|---|---|---|")
def row(name, ents, crosses, secs):
    g = none = 0
    for i in A_:
        es = ents[i]
        g += any(hit(ids_r[i], e) for e in es); none += not es
    c = [len(ents[i]) for i in U_]
    sm = sorted(secs)
    out("| %s | %d | %d | %d / %d / %d | %.1f / %.1f | %.1f / %.1f |" % (name, g, none, sum(x == 0 for x in c), sum(x >= 2 for x in c), sum(x == 1 for x in c),
        med(crosses), sum(crosses) / len(crosses), med(secs), sm[int(len(sm) * .9)]))
ids_r = next(iter(desc.values()))
for e in ("fast", "standard", "full"):
    f = flat[e]
    row("flat %s" % e, {i: [x for t in T for x in f[i]["tiers"][t]["entries"]] for i in ids},
        [sum(f[i]["tiers"][t].get("crosses_read", 0) for t in T) for i in ids], [f[i].get("secs_total", 0) for i in ids])
    if e in desc:
        d = desc[e]
        row("descent (bounds of %s)" % e, {i: [x for t in T for x in d[i]["tiers"][t]["entries"]] for i in ids},
            [sum(d[i]["tiers"][t]["crosses"]["total"] for t in T) for i in ids],
            [sum(d[i]["tiers"][t]["ms_coarse"] + d[i]["tiers"][t]["ms_fine"] for t in T) / 1000 for i in ids])
out()
out("Whole-flat crosses (every cross holding a question unit) vs crosses the descent read, sum over the 90 questions: ")
for e in desc:
    d = desc[e]
    out("- descent %s: upper %d + lower %d = %d crosses vs %d for the whole flat read" % (e,
        sum(d[i]["tiers"][t]["crosses"]["upper"] for i in ids for t in T), sum(d[i]["tiers"][t]["crosses"]["lower"] for i in ids for t in T),
        sum(d[i]["tiers"][t]["crosses"]["total"] for i in ids for t in T), sum(d[i]["tiers"][t]["crosses"]["flat"] for i in ids for t in T)))
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(L) + "\n")
