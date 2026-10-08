"""T8b summary: candidate quality of the upper layers when a candidate = the PATH WORDS read under the question (L-251),
against T8's bags and against layers off.  Candidate quality first (owner's principle 2026-10-07), then time, trace, rule B.
usage: summarize.py OUT.md EFFORT=T8B_FILE=T8_FILE [...]"""
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


def load(path):
    return {r["id"]: r for r in map(json.loads, open(path, encoding="utf-8"))}


def golds(r):
    return [x.casefold() for x in r["gold"].split("|") if x]


def hit(r, e):
    return any(g in w.casefold() for g in golds(r) for w in e["words"])


def lst(r, t8, cfg):
    """cfg = ("off",) | ("t8", gran, variants) | ("t8b", name, variants).  [(tier, layer, variant, entry)]"""
    es = [(t, 0, None, e) for t in TIERS for e in r["layer0"][t]["entries"]]
    if cfg[0] == "t8":
        for t, d in t8[r["id"]]["on"][cfg[1]]["tiers"].items():
            for run in d["runs"]:
                if run["variant"] in cfg[2]:
                    es.extend((t, run["k"], run["variant"], e) for e in run["entries"])
    elif cfg[0] == "t8b":
        for t, d in r["on"][cfg[1]]["tiers"].items():
            for run in d["runs"]:
                if run["variant"] in cfg[2]:
                    es.extend((t, run["k"], run["variant"], e) for e in run["entries"])
    return es


def upper(r, t8, cfg):
    return [x for x in lst(r, t8, cfg) if x[1] > 0]


for effort, p8b, p8, *rest in SRC:
    d, t8 = load(p8b), load(p8)
    if rest:                                   # the seed+question lower read (L-252), measured in a separate sweep
        for i, r in load(rest[0]).items():
            d[i]["on"].update(r["on"])
    ids = sorted(d)
    A_ = [i for i in ids if i.startswith("a")]
    U_ = [i for i in ids if not i.startswith("a")]
    has_same = "sA" in d[ids[0]]["on"]
    CFGS = [("layers off (layer 0 = T7b)", ("off",)),
            ("T8 bag, compress, A (previous default candidate)", ("t8", "compress", ("A",))),
            ("T8b PATH words, compress, A  [new default]", ("t8b", "cA", ("A",))),
            ("T8b PATH words, compress, B", ("t8b", "cB", ("B",))),
            ("T8b PATH words, compress, A+B", ("t8b", "cA", ("A",)))]   # placeholder replaced below
    CFGS = CFGS[:4]
    if "cAs" in d[ids[0]]["on"]:
        CFGS.append(("T8b PATH words, compress, A, lower read = seed + question", ("t8b", "cAs", ("A",))))
        CFGS.append(("T8b PATH words, compress, B, lower read = seed + question", ("t8b", "cBs", ("B",))))
    if has_same:
        CFGS.append(("T8b PATH words, same, A", ("t8b", "sA", ("A",))))
    out("# T8b path-word candidates -- effort %s (S300, %d questions: %d answerable, %d unanswerable)" % (effort, len(ids), len(A_), len(U_)))
    out()
    out("The list = every layer-0 entry of the three tiers + the upper-layer entries of the configuration, each labelled; nothing merged. "
        "'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b / T8). Upper-layer candidates of T8 were "
        "bags (N-19 expanded every bundle to all words of the lower state); T8b shows only the path words read under the question from the "
        "lower crosses packed in the bundles.")
    out()
    out("## Candidate quality: answerable questions (%d)" % len(A_))
    out()
    out("| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold held only by an UPPER candidate: its words median |")
    out("|---|---|---|---|---|---|---|---|---|")
    off_hit = {i: any(hit(d[i], e) for *_, e in lst(d[i], t8, ("off",))) for i in A_}
    for name, cfg in CFGS:
        g = one = ls = none = wrong = 0
        sizes, gained, up_sz = [], [], []
        for i in A_:
            es = lst(d[i], t8, cfg)
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
            if h and not off_hit[i]:
                gained.append(i)
                up_sz.extend(len(e["words"]) for _, k, _, e in es if k > 0 and hit(d[i], e))
        out("| %s | %d | %d | %d | %d | %d | %s (%s) | %d | %s |" % (name, g, one, ls, none, wrong, f1(med(sizes)),
                                                                 max(sizes) if sizes else "-", len(gained), f1(med(up_sz))))
    out()
    out("## Unanswerable questions (%d): can a user reject what is shown?" % len(U_))
    out()
    out("| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |")
    out("|---|---|---|---|")
    for name, cfg in CFGS:
        c = [len(lst(d[i], t8, cfg)) for i in U_]
        out("| %s | %d | %d | %d |" % (name, sum(x == 0 for x in c), sum(x >= 2 for x in c), sum(x == 1 for x in c)))
    out()
    out("## Size of the UPPER-layer candidates (words per candidate), answerable questions")
    out()
    out("| configuration | upper candidates | words median | p90 | max | holding gold: count | words per gold-holding candidate: median / max | upper candidates per question (median / max) |")
    out("|---|---|---|---|---|---|---|---|")
    l0 = [len(e["words"]) for i in A_ for t in TIERS for e in d[i]["layer0"][t]["entries"]]
    out("| layer 0 (for scale) | %d | %s | %s | %s | - | - | - |" % (len(l0), f1(med(l0)), f1(pct(l0, .9)), max(l0)))
    for name, cfg in CFGS[1:]:
        ups = [(i, e) for i in A_ for _, k, _, e in upper(d[i], t8, cfg)]
        n = [len(e["words"]) for _, e in ups]
        gh = [len(e["words"]) for i, e in ups if hit(d[i], e)]
        per = [len(upper(d[i], t8, cfg)) for i in A_]
        out("| %s | %d | %s | %s | %s | %d | %s / %s | %s / %s |" % (name, len(n), f1(med(n)), f1(pct(n, .9)), max(n) if n else "-", len(gh),
                                                                    f1(med(gh)), max(gh) if gh else "-", f1(med(per)), max(per)))
    out()
    out("## Path-word upper candidates: what the read gave (compress, A)")
    out()
    for cname in [n for n in ("cA", "cAs") if n in d[ids[0]]["on"]]:
      runs = [(i, t, run) for i in ids for t, dd in d[i]["on"][cname]["tiers"].items() for run in dd["runs"]]
      ents = [e for _, _, run in runs for e in run["entries"]]
      out("- [%s] upper runs: %d; upper entries: %d; upper entries dropped because the lower crosses read no path under the question: %d" % (
        cname, len(runs), len(ents), sum(run["without_path_words"] for _, _, run in runs)))
      out("- [%s] every word of every entry has a source sentence: %d / %d entries; lower crosses read per entry median %s max %s; source sentences per entry median %s" % (
        cname, sum(e["all_words_sourced"] for e in ents), len(ents), f1(med([e["reads"] for e in ents])),
        max([e["reads"] for e in ents] or [0]), f1(med([e["sources"] for e in ents]))))
    out()
    out("## Time per question (seconds; other measurements ran at the same time: inflated by contention)")
    out()
    out("| | median | mean | p90 | max |")
    out("|---|---|---|---|---|")
    t0 = [d[i]["ms_layer0"] / 1000 for i in ids]
    out("| layer 0 (layers off) | %s | %s | %s | %s |" % (f1(med(t0)), f1(sum(t0) / len(t0)), f1(pct(t0, .9)), f1(max(t0))))
    for name in d[ids[0]]["on"]:
        tl = [d[i]["on"][name]["ms"] / 1000 for i in ids]
        out("| layers added, path %s | %s | %s | %s | %s |" % (name, f1(med(tl)), f1(sum(tl) / len(tl)), f1(pct(tl, .9)), f1(max(tl))))
    for gran in ("compress",):
        tl = [t8[i]["on"][gran]["ms"] / 1000 for i in ids if i in t8]
        out("| layers added, T8 bag %s (T8 run, A+B both variants; other load) | %s | %s | %s | %s |" % (gran, f1(med(tl)), f1(sum(tl) / len(tl)), f1(pct(tl, .9)), f1(max(tl))))
    out()
    out("## Trace through the layers")
    out()
    for name in d[ids[0]]["on"]:
        rr = [run for i in ids for dd in d[i]["on"][name]["tiers"].values() for run in dd["runs"]]
        out("- path %s: %d upper runs, every word traced (trace_ok): %d / %d" % (name, len(rr), sum(r["trace_ok"] for r in rr), len(rr)))
        bad = [(r["trace"], r["trace_failures"]) for r in rr if not r["trace_ok"]][:3]
        if bad:
            out("  failures: %r" % (bad,))
    out()
    out("## Reference only: rule-B scores (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)")
    out()
    out("| configuration | right | wrong | abstain |")
    out("|---|---|---|---|")
    for name, cfg in CFGS:
        rt = wr = ab = 0
        for i in ids:
            es = lst(d[i], t8, cfg)
            if len(es) == 1:
                if i.startswith("a") and hit(d[i], es[0][3]):
                    rt += 1
                else:
                    wr += 1
            else:
                ab += 1
        out("| %s | %d | %d | %d |" % (name, rt, wr, ab))
    out()
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
