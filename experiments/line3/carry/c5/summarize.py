"""C5 summary: candidate quality of the tower's list (owner's principle: candidates are for real users to grade; the oracle
rule 'a gold string occurs in a word of an entry' of T6ab / T7b / T8), time, units read, trace.
usage: summarize.py OUT.md NAME=C5_FILE [NAME=C5_FILE ...] [--t7b FILE]   (C5_FILE: measure.py output;
       --t7b: experiments/line3/t7b/results/S300_fast.jsonl, shown as flat references: RUN only and the 3 tiers pooled)"""
import json
import statistics
import sys

args = sys.argv[1:]
OUT = args.pop(0)
t7b = None
if "--t7b" in args:
    i = args.index("--t7b")
    t7b = args[i + 1]
    del args[i:i + 2]
SRC = [a.split("=", 1) for a in args]
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


med = lambda xs: statistics.median(xs) if xs else None
f1 = lambda x: "-" if x is None else ("%.1f" % x)


def golds(r):
    return [x.casefold() for x in r["gold"].split("|") if x]


def stats_of(rows, entries_of):
    ids = sorted(rows)
    A_ = [i for i in ids if i.startswith("a")]
    U_ = [i for i in ids if not i.startswith("a")]
    hit = lambda r, e: any(g in w.casefold() for g in golds(r) for w in e["words"])
    g = one = lst = none = wrong = 0
    sizes = []
    for i in A_:
        es = entries_of(rows[i])
        h = any(hit(rows[i], e) for e in es)
        if not es:
            none += 1
        elif h:
            g += 1
            one += len(es) == 1
            lst += len(es) >= 2
        else:
            wrong += 1
        if len(es) >= 2:
            sizes.append(len(es))
    uc = [len(entries_of(rows[i])) for i in U_]
    return dict(n=len(ids), a=len(A_), u=len(U_), gold=g, one=one, lst=lst, none=none, wrong=wrong,
                lsz=(med(sizes), max(sizes) if sizes else None), un_none=sum(x == 0 for x in uc),
                un_list=sum(x >= 2 for x in uc), un_single=sum(x == 1 for x in uc),
                all_sizes=[len(entries_of(rows[i])) for i in ids])


data = {n: load(p) for n, p in SRC}
out("# C5 -- question answering over the carry tower (S300 RUN tower, 90 questions)")
out()
out("Oracle rule: a gold string occurs in a word of an entry of the list (T6ab / T7b / T8). The tower's entries hold own words only; an inherited pack is named, never expanded. Time = wall seconds of one question (one process, other jobs on the machine).")
out()
rows_tbl = []
for n in data:
    rows_tbl.append((n, stats_of(data[n], lambda r: r["entries"])))
if t7b:
    t = load(t7b)
    rows_tbl.append(("flat T7b fast, RUN only", stats_of(t, lambda r: r["tiers"]["RUN"]["entries"])))
    rows_tbl.append(("flat T7b fast, 3 tiers pooled (as shown)", stats_of(t, lambda r: [e for k in ("RUN", "WORD", "CHAR") for e in r["tiers"][k]["entries"]])))
out("## Candidate quality: answerable questions (60)")
out()
out("| system | a candidate holds the gold | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds the gold | list size median (max) of lists >= 2 |")
out("|---|---|---|---|---|---|---|")
for n, s in rows_tbl:
    out("| %s | %d | %d | %d | %d | %d | %s (%s) |" % (n, s["gold"], s["one"], s["lst"], s["none"], s["wrong"], f1(s["lsz"][0]), s["lsz"][1] if s["lsz"][1] else "-"))
out()
out("## Unanswerable questions (30): can a user reject what is shown?")
out()
out("| system | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |")
out("|---|---|---|---|")
for n, s in rows_tbl:
    out("| %s | %d | %d | %d |" % (n, s["un_none"], s["un_list"], s["un_single"]))
out()
out("## List sizes (entries per question, all 90)")
out()
out("| system | median | p90 | max | questions with >= 1 entry |")
out("|---|---|---|---|---|")
for n, s in rows_tbl:
    a = s["all_sizes"]
    out("| %s | %s | %s | %d | %d |" % (n, f1(med(a)), f1(pct(a, .9)), max(a), sum(x >= 1 for x in a)))
out()
out("## Time, units read, trace (tower systems)")
out()
out("| system | time median s | mean | p90 | max | questions > 10 s | units read per question (median / max) | partial | reads at level 0 / 1 / 2 / 3 (sum) | exact skips (sum) | trace ok / questions | words traced / checked |")
out("|---|---|---|---|---|---|---|---|---|---|---|---|")
for n, d in data.items():
    rs = list(d.values())
    t = [r["ms"] / 1000 for r in rs]
    nread = [r["read"]["per_tier"]["RUN"]["crosses_read"] if "RUN" in r["read"]["per_tier"] else sum(v["crosses_read"] for v in r["read"]["per_tier"].values()) for r in rs]
    lv = {k: sum(r["read"]["reads_per_level"].get(k, 0) for r in rs) for k in "0123"}
    out("| %s | %s | %s | %s | %s | %d | %s / %d | %d | %s | %d | %d / %d | %d / %d |" % (
        n, f1(med(t)), f1(sum(t) / len(t)), f1(pct(t, .9)), f1(max(t)), sum(x > 10 for x in t), f1(med(nread)), max(nread),
        sum(r["read"]["partial"] for r in rs), " / ".join(str(lv[k]) for k in "0123"), sum(r["read"]["exact_skips"] for r in rs),
        sum(r["trace"]["ok"] for r in rs), len(rs), sum(r["trace"]["traced"] for r in rs), sum(r["trace"]["checked"] for r in rs)))
out()
out("## Verdicts (all 90)")
out()
for n, d in data.items():
    c = {}
    for r in d.values():
        c[r["verdict"]] = c.get(r["verdict"], 0) + 1
    out("- %s: %s" % (n, ", ".join("%s %d" % kv for kv in sorted(c.items()))))
out()
out("## Where does the gold come from? (answerable questions with a gold candidate)")
out()
for n, d in data.items():
    hit = lambda r, e: any(g in w.casefold() for g in golds(r) for w in e["words"])
    lat = ent = 0
    lvl = {}
    for i, r in sorted(d.items()):
        if not i.startswith("a"):
            continue
        hs = [e for e in r["entries"] if hit(r, e)]
        if not hs:
            continue
        origins = {o for e in hs for o in e["origins"]}
        for o in origins:
            lvl[o] = 1
        ent_units = {x[0] for x in r["entrance"]}
        if origins & ent_units:
            ent += 1
        if any(ch["lateral"] for e in hs for ch in e["chains"]):
            lat += 1
    out("- %s: gold in a black that is itself an entrance unit (the newest black): %d; gold reached through a lateral link (inherited pack): %d" % (n, ent, lat))
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
