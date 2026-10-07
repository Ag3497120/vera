"""T8 summary: layers OFF vs ON (same granularity / compress; query passed A / not passed B / both) at an effort preset.
Candidate quality first (owner's principle 2026-10-07): does a candidate hold the gold, how long are the lists, can an
unanswerable question be rejected; then how many questions stack, layers built, partial marks, time; rule-B scores last,
for reference only.  The list the user sees = every layer-0 entry (all tiers) + the upper-layer entries of the chosen
variants, each labelled; nothing merged.
usage: summarize.py OUT.md EFFORT=FILE [EFFORT=FILE ...]"""
import json
import statistics
import sys

OUT = sys.argv[1]
SRC = [a.split("=", 1) for a in sys.argv[2:]]
TIERS = ("RUN", "WORD", "CHAR")
L = []
SMALL = 21          # the largest layer-0 entry of any run has 21 words: a candidate no bigger than any layer-0 one


def out(s=""):
    L.append(s)
    print(s)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q * len(xs) + 0.5)) - 1))] if xs else None


med = lambda xs: statistics.median(xs) if xs else None
f1 = lambda x: "-" if x is None else ("%.1f" % x)


def load(path):
    rows = {}
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        rows[r["id"]] = r
    return rows


def golds(r):
    return [x.casefold() for x in r["gold"].split("|") if x]


def hit(r, e):
    return any(g in w.casefold() for g in golds(r) for w in e["words"])


def lst(r, cfg):
    """cfg = ("off",) | ("on", gran, variants).  Returns [(tier, layer, variant, entry)]."""
    es = [(t, 0, None, e) for t in TIERS for e in r["layer0"][t]["entries"]]
    if cfg[0] == "on":
        _, gran, vs = cfg
        for t, d in r["on"][gran]["tiers"].items():
            for run in d["runs"]:
                if run["variant"] in vs:
                    es.extend((t, run["k"], run["variant"], e) for e in run["entries"])
    return es


CFGS = [("layers off (layer 0 = T7b)", ("off",))]
for gran in ("same", "compress"):
    for name, vs in (("A", ("A",)), ("B", ("B",)), ("A+B", ("A", "B"))):
        CFGS.append(("layers on, %s, query %s" % (gran, name), ("on", gran, vs)))

for effort, path in SRC:
    d = load(path)
    ids = sorted(d)
    A_ = [i for i in ids if i.startswith("a")]
    U_ = [i for i in ids if not i.startswith("a")]
    out("# T8 layers -- effort %s (S300, %d questions: %d answerable, %d unanswerable)" % (effort, len(ids), len(A_), len(U_)))
    out()
    out("The list = every layer-0 entry of the three tiers + the upper-layer entries of the variants named, each labelled "
        "(tier, layer, variant); nothing merged or summed. 'Gold in a candidate' = a gold string occurs in a word of an entry "
        "(oracle rule of T6ab / T7b). NOTE an upper-layer entry's words are the base words under the bundled lower states (N-19), so an "
        "upper entry is a larger bag of words than a layer-0 entry: see the size rows.")
    out()
    out("## Candidate quality: answerable questions (%d)" % len(A_))
    out()
    out("| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold in a candidate of <= %d words |" % SMALL)
    out("|---|---|---|---|---|---|---|---|---|")
    off_hit = {i: any(hit(d[i], e) for *_, e in lst(d[i], ("off",))) for i in A_}
    for name, cfg in CFGS:
        g = one = ls = none = wrong = 0
        sizes = []
        gained = []
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
            if h and not off_hit[i]:
                gained.append(i)
        gs = sum(any(hit(d[i], e) and len(e["words"]) <= SMALL for *_, e in lst(d[i], cfg)) for i in A_)
        out("| %s | %d | %d | %d | %d | %d | %s (%s) | %d (%s) | %d |" % (name, g, one, ls, none, wrong, f1(med(sizes)),
                                                                       max(sizes) if sizes else "-", len(gained), ",".join(gained), gs))
    out()
    out("## Unanswerable questions (%d): can a user reject what is shown?" % len(U_))
    out()
    out("| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |")
    out("|---|---|---|---|")
    for name, cfg in CFGS:
        c = [len(lst(d[i], cfg)) for i in U_]
        out("| %s | %d | %d | %d |" % (name, sum(x == 0 for x in c), sum(x >= 2 for x in c), sum(x == 1 for x in c)))
    out()
    out("## Size of the entries (words per entry)")
    out()
    out("| entries | count | words per entry median | p90 | max | holding gold: count | words per gold-holding entry median |")
    out("|---|---|---|---|---|---|---|")
    groups = {"layer 0 (all tiers)": [], "layer 1+, same, A": [], "layer 1+, same, B": [], "layer 1+, compress, A": [], "layer 1+, compress, B": []}
    for i in A_:
        r = d[i]
        for t in TIERS:
            for e in r["layer0"][t]["entries"]:
                groups["layer 0 (all tiers)"].append((len(e["words"]), hit(r, e)))
        for gran in ("same", "compress"):
            for t, dd in r["on"][gran]["tiers"].items():
                for run in dd["runs"]:
                    groups["layer 1+, %s, %s" % (gran, run["variant"])].extend((len(e["words"]), hit(r, e)) for e in run["entries"])
    for k, v in groups.items():
        n = [x for x, _ in v]
        gh = [x for x, h in v if h]
        out("| %s | %d | %s | %s | %s | %d | %s |" % (k, len(v), f1(med(n)), f1(pct(n, .9)), max(n) if n else "-", len(gh), f1(med(gh))))
    out()
    out("## How many questions stack, and why")
    out()
    out("| granularity | questions with a layer (any tier) | by tier RUN / WORD / CHAR | caused by a full cross (growth budget) | caused by a query-time collapse (no fixed point) | both | layer 2+ built | needed another layer but the effort bound stopped it | upper reads marked partial |")
    out("|---|---|---|---|---|---|---|---|---|")
    for gran in ("same", "compress"):
        stack = bt = {t: 0 for t in TIERS}
        n_any = n_g = n_q = n_b = n_k2 = n_lim = n_part = 0
        for i in ids:
            r = d[i]["on"][gran]
            tiers = r["tiers"]
            anyt = False
            g = q = False
            k2 = lim = part = False
            for t, dd in tiers.items():
                if dd["triggered"]:
                    bt[t] += 1
                    anyt = True
                    g |= dd["growth_budget"] > 0
                    q |= dd["query_no_fixed_point"] > 0
                    for run in dd["runs"]:
                        k2 |= run["k"] >= 2
                        lim |= run["limit"]
                        part |= run["partial"]
            n_any += anyt
            n_g += g and not q
            n_q += q and not g
            n_b += g and q
            n_k2 += k2
            n_lim += lim
            n_part += part
        out("| %s | %d | %d / %d / %d | %d | %d | %d | %d | %d | %d |" % (gran, n_any, bt["RUN"], bt["WORD"], bt["CHAR"], n_g, n_q, n_b, n_k2, n_lim, n_part))
    out()
    out("## Time per question (seconds, 6 worker processes ran at once: inflated by contention)")
    out()
    out("| | median | mean | p90 | max |")
    out("|---|---|---|---|---|")
    t0 = [d[i]["ms_layer0"] / 1000 for i in ids]
    out("| layer 0 (layers off) | %s | %s | %s | %s |" % (f1(med(t0)), f1(sum(t0) / len(t0)), f1(pct(t0, .9)), f1(max(t0))))
    for gran in ("same", "compress"):
        tl = [d[i]["on"][gran]["ms"] / 1000 for i in ids]
        tt = [a + b for a, b in zip(t0, tl)]
        out("| layers added, %s | %s | %s | %s | %s |" % (gran, f1(med(tl)), f1(sum(tl) / len(tl)), f1(pct(tl, .9)), f1(max(tl))))
        out("| total layer 0 + layers, %s | %s | %s | %s | %s |" % (gran, f1(med(tt)), f1(sum(tt) / len(tt)), f1(pct(tt, .9)), f1(max(tt))))
    out()
    out("## Trace through the layers")
    out()
    for gran in ("same", "compress"):
        runs = [run for i in ids for dd in d[i]["on"][gran]["tiers"].values() for run in dd["runs"]]
        out("- %s: %d upper-layer runs, every word traced (trace_ok): %d / %d" % (gran, len(runs), sum(r["trace_ok"] for r in runs), len(runs)))
    out()
    out("## Reference only: rule-B scores of the list (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)")
    out()
    out("| configuration | right | wrong | abstain |")
    out("|---|---|---|---|")
    for name, cfg in CFGS:
        rt = wr = ab = 0
        for i in ids:
            es = lst(d[i], cfg)
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
