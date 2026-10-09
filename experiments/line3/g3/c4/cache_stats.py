"""G3-c4: the window caches (slide_query.WindowIndex, fulllead RUN mid, padding one, G3-c3 defaults: centre both, budget, strict) of the two
z_deep rules, side by side.
usage: cache_stats.py CACHE_ROOT [OUT.md]      (CACHE_ROOT/slide/*.pkl and CACHE_ROOT/order/*.pkl, built by sweep_c4.sh)
Reads the pickles (placement records, members=True form) and reports, over the two-sentence (pair) windows, with exact integer arithmetic
(shares as k/n and a rounded percentage): the centre of the representative, the z-arm seats with evidence on their inner edge by arm and
depth (the evidence of a deeper edge is the slide count n_z under "slide", the word-order count n_x under "order"), the cross edges between
the two sentences, the strictly stable members, class sizes and the build time (the only wall-clock numbers; not part of any record)."""
import glob
import json
import os
import pickle
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
HERE = os.path.dirname(os.path.abspath(__file__))


def pct(a, b):
    return "n/a" if b == 0 else "%d/%d = %d.%d%%" % (a, b, (1000 * a // b) // 10, (1000 * a // b) % 10)


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    if n % 2:
        return xs[n // 2]
    t = xs[n // 2 - 1] + xs[n // 2]
    return t // 2 if t % 2 == 0 else "%d.5" % (t // 2)


def load(cache_dir):
    files = sorted(glob.glob(os.path.join(cache_dir, "slidewin_*.pkl")))
    if len(files) != 1:
        raise SystemExit("%s: expected one cache file, found %d" % (cache_dir, len(files)))
    with open(files[0], "rb") as f:
        d = pickle.load(f)
    return os.path.basename(files[0]), d


def stats(d):
    docs = [x for x in d["windows"] if len(x["window"]["sids"]) == 2 and not x["window"]["constructed"]]
    st = {"windows": len(docs)}
    st["centre"] = (sum(1 for x in docs if x["centre_sentence"] == "this"), sum(1 for x in docs if x["centre_sentence"] == "next"))
    zs = {}
    rule_deep = {}
    real = []
    real_ev = []
    other_strict = 0
    stops = {}
    for x in docs:
        r = ev = 0
        for s in x["seats"]:
            e = s["sources"]["edge"]
            if e is not None and e["with"]["sid"] != s["sid"]:
                r += 1
                ev += e["n"] > 0
            if s["arm"] in ("+z", "-z"):
                k = (s["arm"], "depth 1" if s["depth"] == 1 else "deeper")
                tot, hit = zs.get(k, (0, 0))
                zs[k] = (tot + 1, hit + (e is not None and e["n"] > 0))
                if s["depth"] > 1 and e is not None:                     # a deeper edge with both ends seated
                    t2, h2 = rule_deep.get(s["arm"], (0, 0))
                    rule_deep[s["arm"]] = (t2 + 1, h2 + (e["n"] > 0))
        real.append(r)
        real_ev.append(ev)
        other_strict += bool(x["other_seat"] and x["other_seat"]["strict"])
        b = x["broke_on"]
        key = "cap" if x["stop"] == "cap" else ("never" if b is None else ("inside the centre's sentence" if b["side"] in (x["centre_sentence"], "both") else "inside the other sentence"))
        stops[key] = stops.get(key, 0) + 1
    st["z"] = zs
    st["z_deep_edges"] = rule_deep
    st["real"] = real
    st["real_ev"] = real_ev
    st["other_strict"] = other_strict
    st["stops"] = stops
    st["rep_stable"] = sum(1 for x in docs if x["stable_strict"])
    st["unstable"] = sum(1 for x in docs if x["unstable"])
    st["members_total"] = sum(x["judgement"]["members_total"] for x in docs)
    st["members_ok"] = sum(x["judgement"]["members_stable_strict"] for x in docs)
    st["windows_some_member_ok"] = sum(1 for x in docs if x["judgement"]["members_stable_strict"] > 0)
    st["class"] = [x["class_size"] for x in docs]
    st["L"] = [x["L"] for x in docs]
    st["seated"] = (sum(x["size"] for x in docs), sum(len(x["items"]) for x in docs))
    st["budget_stops"] = sum(1 for x in docs if x["stop"] == "budget")
    cs = {}
    for x in docs:
        c = x["centre_search"]["choice"]
        cs[c] = cs.get(c, 0) + 1
    st["choice"] = cs
    st["z_key"] = [x["axis_keys"]["z"][0] for x in docs]
    st["x_key"] = [x["axis_keys"]["x"][0] for x in docs]
    return st


def main():
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "results", "cache_stats.md")
    cols = {}
    for zd in ("slide", "order"):
        name, d = load(os.path.join(root, zd))
        cols[zd] = (name, d, stats(d))
    L = []

    def row(label, f):
        L.append("| %s | %s | %s |" % (label, f(cols["slide"][2], cols["slide"][1]), f(cols["order"][2], cols["order"][1])))
    L.append("# G3-c4 window caches: z_deep slide vs order (fulllead, RUN, level mid, padding one, centre both + budget + strict; the pair windows)")
    L.append("")
    for zd in ("slide", "order"):
        name, d, st = cols[zd]
        L.append("- %s: `%s`; slide spec %s, place spec %s; %d windows in the cache (%d pairs); build wall %.0f s, cpu %.0f s" % (
            zd, name, d["slide_spec_sha256"][:12], d["place_spec_sha256"][:12], len(d["windows"]), st["windows"], d.get("wall_ms", 0) / 1000.0, d.get("cpu_ms", 0) / 1000.0))
    L.append("")
    L.append("| per run (292 pair windows) | z_deep slide (G3-c3 run A) | z_deep order |")
    L.append("|---|---|---|")
    row("centre of the representative in N / in N+1", lambda s, d: "%d / %d" % s["centre"])
    row("growths kept (single N / single N+1 / both)", lambda s, d: "%d / %d / %d" % (s["choice"].get("this", 0), s["choice"].get("next", 0),
                                                                                     s["choice"].get("both_equal", 0) + s["choice"].get("both_incomparable", 0)))
    row("other sentence seated, strict", lambda s, d: pct(s["other_strict"], s["windows"]))
    row("units seated / units of the pairs", lambda s, d: pct(*s["seated"]))
    for arm in ("+z", "-z"):
        for dep in ("depth 1", "deeper"):
            row("z-arm seats with evidence on the inner edge: %s %s" % (arm, dep), lambda s, d, arm=arm, dep=dep: pct(s["z"].get((arm, dep), (0, 0))[1], s["z"].get((arm, dep), (0, 0))[0]))
    row("... all z-arm seats", lambda s, d: pct(sum(v[1] for v in s["z"].values()), sum(v[0] for v in s["z"].values())))
    row("... deeper seats (any arm)", lambda s, d: pct(sum(v[1] for k, v in s["z"].items() if k[1] == "deeper"), sum(v[0] for k, v in s["z"].items() if k[1] == "deeper")))
    row("deeper z edges with both ends seated: with a count", lambda s, d: pct(sum(v[1] for v in s["z_deep_edges"].values()), sum(v[0] for v in s["z_deep_edges"].values())))
    row("real N<->N+1 edges per window, median / max", lambda s, d: "%s / %d" % (med(s["real"]), max(s["real"])))
    row("windows with none / exactly one / two such edges", lambda s, d: "%d / %d / %d" % (sum(1 for r in s["real"] if r == 0), sum(1 for r in s["real"] if r == 1), sum(1 for r in s["real"] if r >= 2)))
    row("... of those edges, with a count", lambda s, d: pct(sum(s["real_ev"]), sum(s["real"])))
    row("stopped: inside the centre's / inside the other sentence / cap / never", lambda s, d: " / ".join(str(s["stops"].get(k, 0)) for k in (
        "inside the centre's sentence", "inside the other sentence", "cap", "never")))
    row("budget stops", lambda s, d: str(s["budget_stops"]))
    row("representative strictly stable", lambda s, d: pct(s["rep_stable"], s["windows"]))
    row("marked UNSTABLE_AXIS_IMPROVABLE", lambda s, d: str(s["unstable"]))
    row("members strictly stable (all members of all classes)", lambda s, d: pct(s["members_ok"], s["members_total"]))
    row("windows with at least one strictly stable member", lambda s, d: pct(s["windows_some_member_ok"], s["windows"]))
    row("class size median / max", lambda s, d: "%s / %d" % (med(s["class"]), max(s["class"])))
    row("arm length L median / max", lambda s, d: "%s / %d" % (med(s["L"]), max(s["L"])))
    row("z-axis key n of the representative, median / max", lambda s, d: "%s / %d" % (med(s["z_key"]), max(s["z_key"])))
    row("x-axis key n of the representative, median / max", lambda s, d: "%s / %d" % (med(s["x_key"]), max(s["x_key"])))
    L.append("")
    L.append("(\"evidence\" of a z-arm edge: n > 0 of the rule the edge used: n_z for the innermost edge (depth 1) and, under slide, for every edge; "
             "n_x of the pair under order for the deeper edges.  A real N<->N+1 edge = a cross edge whose two ends are seats of different sentences.  "
             "The z-axis key of the two runs is NOT comparable: under order it also sums word-order counts.)")
    text = "\n".join(L) + "\n"
    open(out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
