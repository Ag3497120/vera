"""T7b summary: per preset, wall time per question and candidate quality of the ALL-TIER list (the user is shown every
tier's entries, so the list = the pool of the three tiers).  Candidate quality is the owner's principle (2026-10-07):
does a candidate hold the gold, how long are the lists, can an unanswerable question be rejected.
usage: summarize.py OUT.md NAME=FILE [NAME=FILE ...]      (FILE: measure.py output, or T7's S300_all_tiers.jsonl for 'full')"""
import json
import statistics
import sys

OUT = sys.argv[1]
SRC = [a.split("=", 1) for a in sys.argv[2:]]
TIERS = ("RUN", "WORD", "CHAR")
L = []


def out(s=""):
    L.append(s)
    print(s)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q * len(xs) + 0.5)) - 1))] if xs else None


def load(path):
    rows = {}
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        rows[r["id"]] = r
    return rows


def entries_of(r):
    return [(t, e) for t in TIERS for e in r["tiers"][t]["entries"]]


data = {n: load(p) for n, p in SRC}
ids = sorted(set.intersection(*(set(d) for d in data.values())))
golds = lambda r: [x.casefold() for x in r["gold"].split("|") if x]
hit = lambda r, e: any(g in w.casefold() for g in golds(r) for w in e["words"])
A_ = [i for i in ids if i.startswith("a")]
U_ = [i for i in ids if not i.startswith("a")]
med = lambda xs: statistics.median(xs) if xs else None
f1 = lambda x: "-" if x is None else ("%.1f" % x)

out("# T7b -- amount of inference presets: time and candidate quality (S300, %d questions: %d answerable, %d unanswerable)" % (len(ids), len(A_), len(U_)))
out()
out("The list shown to the user = every tier's entries, each labelled with its tier (nothing summed or merged). 'Gold in a candidate' = a gold string occurs in a word of an entry (the oracle rule of T6ab). Time = wall seconds of one question, all three tiers, one process.")
out()
names = [n for n, _ in SRC]
out("## Time per question (seconds)")
out()
out("| preset | n | median | mean | p90 | max | sum RUN | sum WORD | sum CHAR | questions > 10 s | > 60 s |")
out("|---|---|---|---|---|---|---|---|---|---|---|")
for n in names:
    t = [data[n][i]["secs_total"] for i in ids]
    per = {k: sum(data[n][i]["tiers"][k]["ms"] for i in ids) / 1000 for k in TIERS}
    out("| %s | %d | %s | %s | %s | %s | %.0f | %.0f | %.0f | %d | %d |" % (
        n, len(t), f1(med(t)), f1(sum(t) / len(t)), f1(pct(t, .9)), f1(max(t)), per["RUN"], per["WORD"], per["CHAR"],
        sum(x > 10 for x in t), sum(x > 60 for x in t)))
out()
out("## How much was read (crosses per tier, per question)")
out()
out("| preset | questions marked partial | crosses read / would read in full (sum over the 90 questions) RUN | WORD | CHAR |")
out("|---|---|---|---|---|")
for n in names:
    d = data[n]
    part = sum(any(d[i]["tiers"][k].get("left_unread", 0) > 0 for k in TIERS) for i in ids)
    cells = []
    for k in TIERS:
        rd = sum(d[i]["tiers"][k].get("crosses_read", 0) for i in ids)
        fu = sum(d[i]["tiers"][k].get("would_read_in_full", d[i]["tiers"][k].get("crosses_read", 0)) for i in ids)
        cells.append("%d / %d" % (rd, fu))
    out("| %s | %d | %s |" % (n, part, " | ".join(cells)))
out()
out("## Candidate quality: answerable questions (%d)" % len(A_))
out()
out("| preset | a candidate holds the gold | ... as the single ANSWER | ... inside a list of >= 2 | no candidate at all | candidates, none holds the gold | list size median (max) of lists >= 2 | gold in RUN / WORD / CHAR |")
out("|---|---|---|---|---|---|---|---|")
for n in names:
    d = data[n]
    g = one = lst = none = wrong = 0
    sizes = []
    pt = {k: 0 for k in TIERS}
    for i in A_:
        r = d[i]
        es = entries_of(r)
        h = any(hit(r, e) for _, e in es)
        for k in TIERS:
            pt[k] += any(hit(r, e) for e in r["tiers"][k]["entries"])
        if not es:
            none += 1
        elif h:
            g += 1
            if len(es) == 1:
                one += 1
            else:
                lst += 1
        else:
            wrong += 1
        if len(es) >= 2:
            sizes.append(len(es))
    out("| %s | %d | %d | %d | %d | %d | %s (%s) | %d / %d / %d |" % (n, g, one, lst, none, wrong, f1(med(sizes)), max(sizes) if sizes else "-", pt["RUN"], pt["WORD"], pt["CHAR"]))
out()
out("## Unanswerable questions (%d): can a user reject what is shown?" % len(U_))
out()
out("| preset | no candidate (nothing to reject) | only a list (rejectable) | a single answer (looks confident: wrong) |")
out("|---|---|---|---|")
for n in names:
    d = data[n]
    c = [len(entries_of(d[i])) for i in U_]
    out("| %s | %d | %d | %d |" % (n, sum(x == 0 for x in c), sum(x >= 2 for x in c), sum(x == 1 for x in c)))
out()
out("## Per question: does the gold survive the smaller budget? (answerable, against full)")
out()
if "full" in data:
    for n in names:
        if n == "full":
            continue
        lost = [i for i in A_ if any(hit(data["full"][i], e) for _, e in entries_of(data["full"][i])) and not any(hit(data[n][i], e) for _, e in entries_of(data[n][i]))]
        gained = [i for i in A_ if not any(hit(data["full"][i], e) for _, e in entries_of(data["full"][i])) and any(hit(data[n][i], e) for _, e in entries_of(data[n][i]))]
        out("- %s: gold present at full but lost at %s: %d (%s); gained: %d (%s)" % (n, n, len(lost), ",".join(lost), len(gained), ",".join(gained)))
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
