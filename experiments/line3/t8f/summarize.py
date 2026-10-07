"""T8f summary: stable-seats-qpath (L-440) and stable-seats-qword (L-441) against T8e stable-seats-path, T8 bag and layers off.
layer 0 and qpath come from the qpath sweep, qword from the qword sweep, stable-seats-path from the T8e sweep, bag from the T8c sweep, by id.
usage: summarize.py OUT.md EFFORT=T8C_FILE:T8E_FILE:QPATH_FILE:QWORD_FILE [...]"""
import json
import statistics
import sys

OUT = sys.argv[1]
SRC = [a.split("=") for a in sys.argv[2:]]
TIERS = ("RUN", "WORD", "CHAR")
L = []


def out(s=""):
    L.append(s)
    print(s)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q * len(xs) + 0.5)) - 1))] if xs else None


med = lambda xs: statistics.median(xs) if xs else None
f1 = lambda x: "-" if x is None else ("%.1f" % x)
rd = lambda p: {r["id"]: r for r in map(json.loads, open(p, encoding="utf-8"))}


def load(path):
    a, b, c, q = map(rd, path.split(":"))
    d = {}
    for i, r in c.items():
        r = dict(r)
        r["on"] = dict(r["on"])
        r["on"]["bagA"] = a[i]["on"]["bagA"]
        r["on"]["seatsPathA"] = b[i]["on"]["seatsPathA"]
        r["on"]["qwordA"] = q[i]["on"]["qwordA"]
        d[i] = r
    return d


def golds(r):
    return [x.casefold() for x in r["gold"].split("|") if x]


def hit(r, e):
    return any(g in w.casefold() for g in golds(r) for w in e["words"])


def lst(r, cfg):
    es = [(t, 0, e) for t in TIERS for e in r["layer0"][t]["entries"]]
    if cfg:
        for t, d in r["on"][cfg]["tiers"].items():
            for run in d["runs"]:
                es.extend((t, run["k"], e) for e in run["entries"])
    return es


def upper(r, cfg):
    return [x for x in lst(r, cfg) if x[1] > 0]


CF = [("layers off", None), ("T8 bag A", "bagA"), ("T8e stable-seats-path A", "seatsPathA"),
      ("T8f Q1 stable-seats-qpath A", "qpathA"), ("T8f Q2 stable-seats-qword A", "qwordA")]
NEW = ("seatsPathA", "qpathA", "qwordA")
for effort, p in SRC:
    d = load(p)
    ids = sorted(d)
    A_ = [i for i in ids if i.startswith("a")]
    U_ = [i for i in ids if not i.startswith("a")]
    out("# T8f stable-seats-qpath / qword -- effort %s (S300, %d questions: %d answerable, %d unanswerable)" % (effort, len(ids), len(A_), len(U_)))
    out()
    out("List = every layer-0 entry of the three tiers + the upper entries of the configuration (nothing merged). Gold in a candidate = a gold string occurs in a word of an entry (oracle rule).")
    out()
    out("## Answerable (%d)" % len(A_))
    out()
    out("| configuration | gold in a candidate | single ANSWER | inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off |")
    out("|---|---|---|---|---|---|---|---|")
    off_hit = {i: any(hit(d[i], e) for *_, e in lst(d[i], None)) for i in A_}
    for name, cfg in CF:
        g = one = ls = none = wrong = gained = 0
        sizes = []
        for i in A_:
            es = lst(d[i], cfg)
            h = any(hit(d[i], e) for *_, e in es)
            if not es:
                none += 1
            elif h:
                g += 1
                one += len(es) == 1
                ls += len(es) >= 2
            else:
                wrong += 1
            if len(es) >= 2:
                sizes.append(len(es))
            gained += h and not off_hit[i]
        out("| %s | %d | %d | %d | %d | %d | %s (%s) | %d |" % (name, g, one, ls, none, wrong, f1(med(sizes)), max(sizes) if sizes else "-", gained))
    out()
    out("## Unanswerable (%d)" % len(U_))
    out()
    out("| configuration | no candidate | only a list (rejectable) | a single answer (wrong) |")
    out("|---|---|---|---|")
    for name, cfg in CF:
        c = [len(lst(d[i], cfg)) for i in U_]
        out("| %s | %d | %d | %d |" % (name, sum(x == 0 for x in c), sum(x >= 2 for x in c), sum(x == 1 for x in c)))
    out()
    out("## Upper candidates (answerable questions)")
    out()
    out("| configuration | upper cand. total | per question median / max | words median / p90 / max | bundles per cand. median / p90 / max | seats median / p90 / max | gold-holding: count, words median / max, bundles median / max |")
    out("|---|---|---|---|---|---|---|")
    for name, cfg in CF[1:]:
        ups = [(i, e) for i in A_ for _, k, e in upper(d[i], cfg)]
        w = [len(e["words"]) for _, e in ups]
        b = [e["bundles"] for _, e in ups]
        s = [e["n_seats"] for _, e in ups if e.get("n_seats") is not None]
        gh = [e for i, e in ups if hit(d[i], e)]
        per = [len(upper(d[i], cfg)) for i in A_]
        out("| %s | %d | %s / %s | %s / %s / %s | %s / %s / %s | %s / %s / %s | %d, %s / %s, %s / %s |" % (
            name, len(ups), f1(med(per)), max(per), f1(med(w)), f1(pct(w, .9)), max(w) if w else "-", f1(med(b)), f1(pct(b, .9)), max(b) if b else "-",
            f1(med(s)), f1(pct(s, .9)), max(s) if s else "-", len(gh), f1(med([len(e["words"]) for e in gh])), max([len(e["words"]) for e in gh] or [0]),
            f1(med([e["bundles"] for e in gh])), max([e["bundles"] for e in gh] or [0])))
    out()
    out("By tier (all 90 questions): candidates / words median p90 max / bundles median p90 max / seats median p90 max")
    out()
    out("| configuration | tier | candidates | words | bundles | seats |")
    out("|---|---|---|---|---|---|")
    for cfgname in NEW:
        for T in TIERS + ("all",):
            es = [e for i in ids for t, dd in d[i]["on"][cfgname]["tiers"].items() if T in (t, "all") for run in dd["runs"] for e in run["entries"]]
            trip = lambda xs: "%s / %s / %s" % (f1(med(xs)), f1(pct(xs, .9)), max(xs) if xs else "-")
            out("| %s | %s | %d | %s | %s | %s |" % (cfgname, T, len(es), trip([len(e["words"]) for e in es]), trip([e["bundles"] for e in es]),
                                                   trip([e["n_seats"] for e in es if e["n_seats"] is not None])))
    out()
    out("## Position of the first gold-holding candidate (answerable questions with gold; 1 = first; layer-0 entries come first)")
    out()
    out("| configuration | questions with gold | position in whole list: median / p90 / max | list length of those: median / max | position among UPPER candidates (gold held by an upper one): n, median / p90 / max | upper candidates of those: median / max |")
    out("|---|---|---|---|---|---|")
    for name, cfg in CF:
        pos, ln, upos, uln = [], [], [], []
        for i in A_:
            es = lst(d[i], cfg)
            hs = [n for n, (_, k, e) in enumerate(es, 1) if hit(d[i], e)]
            if hs:
                pos.append(hs[0])
                ln.append(len(es))
            ups = [x for x in es if x[1] > 0]
            uh = [n for n, (_, k, e) in enumerate(ups, 1) if hit(d[i], e)]
            if uh:
                upos.append(uh[0])
                uln.append(len(ups))
        out("| %s | %d | %s / %s / %s | %s / %s | %d, %s / %s / %s | %s / %s |" % (name, len(pos), f1(med(pos)), f1(pct(pos, .9)), max(pos) if pos else "-",
              f1(med(ln)), max(ln) if ln else "-", len(upos), f1(med(upos)), f1(pct(upos, .9)), max(upos) if upos else "-", f1(med(uln)), max(uln) if uln else "-"))
    out()
    out("## Time per question (seconds; other agents' work ran at the same time: inflated)")
    out()
    out("| | median | mean | p90 | max |")
    out("|---|---|---|---|---|")
    t0 = [d[i]["ms_layer0"] / 1000 for i in ids]
    out("| layer 0 | %s | %s | %s | %s |" % (f1(med(t0)), f1(sum(t0) / len(t0)), f1(pct(t0, .9)), f1(max(t0))))
    for name in ("bagA", "seatsPathA", "qpathA", "qwordA"):
        tl = [d[i]["on"][name]["ms"] / 1000 for i in ids]
        out("| layers added, %s | %s | %s | %s | %s |" % (name, f1(med(tl)), f1(sum(tl) / len(tl)), f1(pct(tl, .9)), f1(max(tl))))
    out("(bagA, seatsPathA times are from the earlier sweeps, run under other loads; qpathA / qwordA from the T8f sweeps, each config in its own sweep)")
    out()
    out("## Trace")
    out()
    for name in ("bagA", "seatsPathA", "qpathA", "qwordA"):
        rr = [run for i in ids for dd in d[i]["on"][name]["tiers"].values() for run in dd["runs"]]
        ents = [e for run in rr for e in run["entries"]]
        out("- %s: %d upper runs, trace_ok %d / %d; entries with every word sourced %d / %d; upper entries with no layout at all: %d; entries left with no kept bundle (no candidate): %d" % (
            name, len(rr), sum(r["trace_ok"] for r in rr), len(rr), sum(e["all_words_sourced"] for e in ents), len(ents), sum(r["without_path_words"] for r in rr), sum(r.get("without_kept", 0) for r in rr)))
    out()
    out("## Subset check: bundles per candidate against stable-seats-path (all questions, upper candidates)")
    out()
    for cfgname in NEW:
        es = [e for i in ids for dd in d[i]["on"][cfgname]["tiers"].values() for run in dd["runs"] for e in run["entries"]]
        out("- %s: %d candidates, %d bundles in total" % (cfgname, len(es), sum(e["bundles"] for e in es)))
    out()
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
