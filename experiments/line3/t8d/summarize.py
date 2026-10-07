"""T8d summary: stable-seats (L-390) and stable-seated (L-391) against T8c stable, T8b path, T8 bag and layers off.  Candidate quality first.
bag / path / stable A come from the T8c sweep (same code, byte-identical: checked), seated / seats from the T8d sweep, by question id.
usage: summarize.py OUT.md EFFORT=T8C_FILE:T8D_FILE [...]"""
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
    p8c, p8d = path.split(":")
    a = {r["id"]: r for r in map(json.loads, open(p8c, encoding="utf-8"))}
    b = {r["id"]: r for r in map(json.loads, open(p8d, encoding="utf-8"))}
    out = {}
    for i, r in b.items():
        r = dict(r)
        r["on"] = dict(r["on"])
        for n in ("bagA", "pathA", "stableA"):
            r["on"][n] = a[i]["on"][n]
        r["ms_c"] = {n: a[i]["on"][n]["ms"] for n in ("bagA", "pathA", "stableA")}
        out[i] = r
    return out


def golds(r):
    return [x.casefold() for x in r["gold"].split("|") if x]


def hit(r, e):
    return any(g in w.casefold() for g in golds(r) for w in e["words"])


def lst(r, t8, cfg):
    """cfg = ("off",) | ("on", name, variants).  [(tier, layer, variant, entry)]"""
    es = [(t, 0, None, e) for t in TIERS for e in r["layer0"][t]["entries"]]
    if cfg[0] == "on":
        for t, d in r["on"][cfg[1]]["tiers"].items():
            for run in d["runs"]:
                if run["variant"] in cfg[2]:
                    es.extend((t, run["k"], run["variant"], e) for e in run["entries"])
    return es


def upper(r, t8, cfg):
    return [x for x in lst(r, t8, cfg) if x[1] > 0]


for effort, p8b in SRC:
    d, t8 = load(p8b), {}
    ids = sorted(d)
    A_ = [i for i in ids if i.startswith("a")]
    U_ = [i for i in ids if not i.startswith("a")]
    CFGS = [("layers off (layer 0 = T7b)", ("off",)),
            ("T8 bag, compress, A", ("on", "bagA", ("A",))),
            ("T8b PATH words (full-question read), compress, A  [current default]", ("on", "pathA", ("A",))),
            ("T8c STABLE-state path words, compress, A", ("on", "stableA", ("A",))),
            ("T8d STABLE-SEATS (restored state laid out by seats), compress, A", ("on", "seatsA", ("A",))),
            ("T8d STABLE-SEATED (boundary only at seated units), path words, compress, A", ("on", "seatedA", ("A",)))]
    out("# T8d stable-seats / stable-seated candidates -- effort %s (S300, %d questions: %d answerable, %d unanswerable)" % (effort, len(ids), len(A_), len(U_)))
    out()
    out("The list = every layer-0 entry of the three tiers + the upper-layer entries of the configuration, each labelled; nothing merged. "
        "'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b / T8). Upper-layer candidates of T8 were "
        "bags (N-19 expanded every bundle to all words of the lower state); T8b shows the path words of the full-question read; T8c the path words of the last stable state while the question is applied unit by unit.")
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
    out("## What the lower reads gave")
    out()
    for cname in ("pathA", "stableA", "seatedA", "seatsA"):
      runs = [(i, t, run) for i in ids for t, dd in d[i]["on"][cname]["tiers"].items() for run in dd["runs"]]
      ents = [e for _, _, run in runs for e in run["entries"]]
      out("- [%s] upper runs: %d; upper entries: %d; upper entries dropped because the lower crosses gave no path words: %d; entries with every word sourced: %d / %d" % (
        cname, len(runs), len(ents), sum(run["without_path_words"] for _, _, run in runs), sum(e["all_words_sourced"] for e in ents), len(ents)))
    out()
    out("## Boundary records (per lower cross read down, over all questions; one record per (question, tier, layer, seed))")
    out()
    out("| config | lower reads | no restore (stable through the whole question) | restored | ... restored to STEP 0 (no unit applied) | ... restored at step >= 1 | state read has path words (listed > 0) / is shown (seats) | no break at a seated unit but the full-question state is unstable (energy-only break, not a boundary) |")
    out("|---|---|---|---|---|---|---|---|")
    for cname in ("stableA", "seatedA", "seatsA"):
        seen = {}
        for i in ids:
            for t, dd in d[i]["on"][cname]["tiers"].items():
                for run in dd["runs"]:
                    for b in run["boundaries"]:
                        seen[(i, t, run["k"], b["layer"], b["seed"])] = b
        bs = list(seen.values())
        rs = [b for b in bs if b["restored"]]
        en = sum(1 for b in bs if not b["restored"] and b.get("state_stable") is False)
        out("| %s | %d | %d | %d | %d | %d | %d | %s |" % (cname, len(bs), len(bs) - len(rs), len(rs),
              sum(b["last_stable_step"] == 0 for b in rs), sum(b["last_stable_step"] >= 1 for b in rs),
              sum(b["listed"] > 0 for b in bs), en if cname == "seatedA" else "-"))
        hist, first = {}, {}
        for b in rs:
            hist[b["last_stable_step"]] = hist.get(b["last_stable_step"], 0) + 1
            first[b["first_unstable_step"]] = first.get(b["first_unstable_step"], 0) + 1
        out()
        out("  [%s] restored: last stable step histogram %s; first unstable step histogram %s; units per read median %s; unstable unit attached (seated) in %d of %d restored; "
            "restored to step >= 7 (the boundary lies after the 6 seated units): %d" % (
                cname, dict(sorted(hist.items())), dict(sorted(first.items())), f1(med([b["query_units"] for b in bs])),
                sum(bool(b["unstable_unit_attached"]) for b in rs), len(rs), sum(b["last_stable_step"] >= 7 for b in rs)))
    out()
    # stable-seats specifics
    out("## T8d stable-seats: what a candidate is (all upper candidates, all 90 questions; answerable in brackets)")
    out()
    out("| tier | candidates | words median | p90 | max | seats median | p90 | max | arrangements in the state: median / max |")
    out("|---|---|---|---|---|---|---|---|---|")
    for T in TIERS + ("all",):
        es = [(i, e) for i in ids for t, dd in d[i]["on"]["seatsA"]["tiers"].items() if T in (t, "all") for run in dd["runs"] for e in run["entries"]]
        w = [len(e["words"]) for _, e in es]
        st_ = [e["n_seats"] for _, e in es]
        ar = [e["count"] for _, e in es]
        out("| %s | %d | %s | %s | %s | %s | %s | %s | %s / %s |" % (T, len(w), f1(med(w)), f1(pct(w, .9)), max(w) if w else "-",
              f1(med(st_)), f1(pct(st_, .9)), max(st_) if st_ else "-", f1(med(ar)), max(ar) if ar else "-"))
    out()
    out("Position of the first gold-holding candidate (answerable questions where some candidate holds gold; 1 = first). 'in the whole list' = layer-0 entries of the three tiers, then the upper entries; 'among upper' = counted over the upper candidates only; the list length is the number of candidates shown.")
    out()
    out("| configuration | questions with gold | position in the whole list: median / p90 / max | list length of those: median / max | position among upper candidates (gold held by an upper one): median / p90 / max | upper candidates of those: median / max | gold only in an upper candidate (not in off): count |")
    out("|---|---|---|---|---|---|---|")
    for name, cfg in CFGS:
        pos, ln, upos, uln, only = [], [], [], [], 0
        for i in A_:
            es = lst(d[i], t8, cfg)
            hs = [n for n, (_, k, _, e) in enumerate(es, 1) if hit(d[i], e)]
            if hs:
                pos.append(hs[0])
                ln.append(len(es))
            ups = [(n, x) for n, x in enumerate([x for x in es if x[1] > 0], 1)]
            uh = [n for n, (_, k, _, e) in ups if hit(d[i], e)]
            if uh:
                upos.append(uh[0])
                uln.append(len(ups))
                only += not off_hit[i]
        out("| %s | %d | %s / %s / %s | %s / %s | %s / %s / %s | %s / %s | %d |" % (name, len(pos), f1(med(pos)), f1(pct(pos, .9)), max(pos) if pos else "-",
              f1(med(ln)), max(ln) if ln else "-", f1(med(upos)), f1(pct(upos, .9)), max(upos) if upos else "-", f1(med(uln)), max(uln) if uln else "-", only))
    out()
    out("Gold-holding upper candidates of stable-seats: words median / max, seats median / max: %s" % (
        (lambda x: "%s / %s, %s / %s" % (f1(med([a for a, _ in x])), max(a for a, _ in x), f1(med([b for _, b in x])), max(b for _, b in x)) if x else "-")(
            [(len(e["words"]), e["n_seats"]) for i in A_ for _, k, _, e in upper(d[i], t8, ("on", "seatsA", ("A",))) if hit(d[i], e)])))
    out()
    out("## Time per question (seconds; other measurements ran at the same time: inflated by contention)")
    out()
    out("| | median | mean | p90 | max |")
    out("|---|---|---|---|---|")
    t0 = [d[i]["ms_layer0"] / 1000 for i in ids]
    out("| layer 0 (layers off) | %s | %s | %s | %s |" % (f1(med(t0)), f1(sum(t0) / len(t0)), f1(pct(t0, .9)), f1(max(t0))))
    for name in d[ids[0]]["on"]:
        tl = [d[i]["on"][name]["ms"] / 1000 for i in ids]
        out("| layers added, %s | %s | %s | %s | %s |" % (name, f1(med(tl)), f1(sum(tl) / len(tl)), f1(pct(tl, .9)), f1(max(tl))))
    out()
    out("## Trace through the layers")
    out()
    for name in d[ids[0]]["on"]:
        rr = [run for i in ids for dd in d[i]["on"][name]["tiers"].values() for run in dd["runs"]]
        out("- %s: %d upper runs, every word traced (trace_ok): %d / %d" % (name, len(rr), sum(r["trace_ok"] for r in rr), len(rr)))
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
