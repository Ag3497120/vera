"""G3-h: the twelve window caches of the grid side by side (fulllead RUN, mid, padding one, centre both, strict, z_reserved, unit_sid).
usage: cache_stats_h.py CACHE_DIR [OUT.md]
Reads the pickles (placement records, members=True form) and reports, over the 292 pair windows (and the 300 one-sentence windows where it matters), with exact integer
arithmetic (shares as k/n and a rounded percentage): the centre sentence of the representative, the units seated, the other sentence (N+1 for a centre in N) seated and
strict, the real N<->N+1 edges and how many carry a count, the deeper z edges and their counts, the stops (budget / cap / never), the unseated units of arm_cap x, the strictly
stable members, class sizes, and -- for seat_empty_axis allow against deny -- how many windows (pair / one-sentence) differ in their placement.  The statistics reuse
g3/c4/cache_stats.py's `stats` (one definition for both tickets)."""
import glob
import importlib.util
import itertools
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
spec = importlib.util.spec_from_file_location("c4_cache_stats", os.path.join(os.path.dirname(HERE), "c4", "cache_stats.py"))
C4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(C4)
pct, med = C4.pct, C4.med
CAPS, ZDS, SEATS = ("budget", "x"), ("slide", "order", "order_window"), ("allow", "deny")
CELLS = list(itertools.product(CAPS, ZDS, SEATS))
# a record's fields that name the spec or the switches; everything else is the placement
SPECY = {"spec_sha256", "slide_spec_sha256", "place_spec_sha256", "switches", "switches3", "ms", "wall_ms", "cpu_ms", "elapsed_ms"}


PLACE = ("seats", "members", "size", "class_size", "L", "items", "axis_keys", "key", "stop", "steps", "unseated", "centre_search", "judgement", "other_seat")


def find(cache_dir, cap, zd, seat):
    """The cache of a cell, loaded through the window index (build=False: a missing or mismatching file stops): the file names carry only shas and the
    header's `switches` lists the four G3-c switches, so the cell is named by the place_kw the index is made with."""
    sys.path.insert(0, ROOT)
    from verantyx.line3 import slide_query as Q
    wi = Q.WindowIndex.from_jsonl(DATA, cache_dir, build=False, place_kw={"arm_cap": cap, "seat_empty_axis": seat}, z_deep=zd)
    name = "slidewin_%s_RUN_%s_%s.pkl" % (wi.space.sha256()[:12], wi.slide.spec.sha256()[:12], wi.spec.sha256()[:12])
    return name, dict(wi.header, windows=[w.doc for w in wi.windows])


def extra(d):
    docs = [x for x in d["windows"] if len(x["window"]["sids"]) == 2 and not x["window"]["constructed"]]
    cap_stops = sum(1 for x in docs if x["stop"] == "cap")
    unseated = sum(len(x.get("unseated") or []) for x in docs)
    deep = [0, 0, 0]                                   # deeper z edges (both ends seated): total / with a count (n > 0) / with the direction (omega > 0)
    for x in docs:
        for s in x["seats"]:
            e = s["sources"]["edge"]
            if s["arm"] in ("+z", "-z") and s["depth"] > 1 and e is not None:
                deep[0] += 1; deep[1] += e["n"] > 0; deep[2] += e["omega"] > 0
    return dict(cap_stops=cap_stops, unseated=unseated, deep=deep)


def main():
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "results", "cache_stats.md")
    cols = {}
    for cell in CELLS:
        name, d = find(root, *cell[:1], cell[1], cell[2])
        cols[cell] = (name, d, C4.stats(d), extra(d))
    L = ["# G3-h window caches: arm_cap x z_deep x seat_empty_axis (fulllead, RUN, level mid, padding one, centre both, strict, z_reserved, unit_sid; the 292 pair windows)", ""]
    for cell in CELLS:
        name, d, st, ex = cols[cell]
        L.append("- %s: `%s`; slide spec %s, place spec %s; %d windows (%d pairs); build wall %.0f s, cpu %.0f s" % (
            " / ".join(cell), name, d["slide_spec_sha256"][:12], d["place_spec_sha256"][:12], len(d["windows"]), st["windows"],
            d.get("wall_ms", 0) / 1000.0, d.get("cpu_ms", 0) / 1000.0))
    L.append("")

    def table(cells, title):
        L.append("### " + title)
        L.append("")
        L.append("| per run (292 pair windows) | " + " | ".join("/".join(c) for c in cells) + " |")
        L.append("|---|" + "---|" * len(cells))

        def row(label, f):
            L.append("| %s | %s |" % (label, " | ".join(f(cols[c][2], cols[c][3], cols[c][1]) for c in cells)))
        row("centre of the representative in N / in N+1", lambda s, e, d: "%d / %d" % s["centre"])
        row("growths kept (single N / single N+1 / both)", lambda s, e, d: "%d / %d / %d" % (s["choice"].get("this", 0), s["choice"].get("next", 0),
                                                                                           s["choice"].get("both_equal", 0) + s["choice"].get("both_incomparable", 0)))
        row("other sentence seated, strict (N+1 seated for a centre in N)", lambda s, e, d: pct(s["other_strict"], s["windows"]))
        row("units seated / units of the pairs", lambda s, e, d: pct(*s["seated"]))
        row("real N<->N+1 edges per window, median / max", lambda s, e, d: "%s / %d" % (med(s["real"]), max(s["real"])))
        row("windows with none / exactly one / two such edges", lambda s, e, d: "%d / %d / %d" % (
            sum(1 for r in s["real"] if r == 0), sum(1 for r in s["real"] if r == 1), sum(1 for r in s["real"] if r >= 2)))
        row("... of those edges, with a count", lambda s, e, d: pct(sum(s["real_ev"]), sum(s["real"])))
        row("deeper z edges with both ends seated: with a count (n > 0)", lambda s, e, d: pct(e["deep"][1], e["deep"][0]))
        row("... with the arm's direction (omega > 0)", lambda s, e, d: pct(e["deep"][2], e["deep"][0]))
        row("z-arm seats with evidence on the inner edge, all", lambda s, e, d: pct(sum(v[1] for v in s["z"].values()), sum(v[0] for v in s["z"].values())))
        row("budget stops", lambda s, e, d: str(s["budget_stops"]))
        row("cap stops (arm_cap x) / units unseated by the cap", lambda s, e, d: "%d / %d" % (e["cap_stops"], e["unseated"]))
        row("stopped: inside the centre's / inside the other sentence / cap / never", lambda s, e, d: " / ".join(str(s["stops"].get(k, 0)) for k in (
            "inside the centre's sentence", "inside the other sentence", "cap", "never")))
        row("representative strictly stable", lambda s, e, d: pct(s["rep_stable"], s["windows"]))
        row("members strictly stable (all members of all classes)", lambda s, e, d: pct(s["members_ok"], s["members_total"]))
        row("windows with at least one strictly stable member", lambda s, e, d: pct(s["windows_some_member_ok"], s["windows"]))
        row("class size median / max", lambda s, e, d: "%s / %d" % (med(s["class"]), max(s["class"])))
        row("arm length L median / max", lambda s, e, d: "%s / %d" % (med(s["L"]), max(s["L"])))
        L.append("")
    table([c for c in CELLS if c[2] == "allow"], "seat_empty_axis allow")
    table([c for c in CELLS if c[2] == "deny"], "seat_empty_axis deny")

    L.append("### allow against deny: windows whose record differs (the spec / switches fields aside, which differ in every window)")
    L.append("")
    L.append("`record` = any other field differs; `seats` = the representative's seats, the members, the size or the class size differ (the placement itself); a window "
             "that differs only in `seatless_arms` (the arms denied for lack of evidence) has the same seats and members.")
    L.append("")
    L.append("| arm_cap / z_deep | pair windows: record differs | pair windows: seats / members differ | one-sentence (padded) windows: record differs | ... seats / members differ |")
    L.append("|---|---|---|---|---|")
    for cap, zd in itertools.product(CAPS, ZDS):
        a, b = cols[(cap, zd, "allow")][1]["windows"], cols[(cap, zd, "deny")][1]["windows"]
        assert len(a) == len(b)
        pair = one = pair_s = one_s = 0
        npair = none = 0
        for x, y in zip(a, b):
            two = len(x["window"]["sids"]) == 2
            diff = {k: v for k, v in x.items() if k not in SPECY} != {k: v for k, v in y.items() if k not in SPECY}
            sdiff = any(x.get(k) != y.get(k) for k in PLACE)
            npair += two; none += not two
            pair += diff and two; one += diff and not two
            pair_s += sdiff and two; one_s += sdiff and not two
        L.append("| %s / %s | %s | %s | %s | %s |" % (cap, zd, pct(pair, npair), pct(pair_s, npair), pct(one, none), pct(one_s, none)))
    L.append("")
    L.append("(\"evidence\" of a z-arm edge: n > 0 of the rule the edge used: n_z for the innermost edge (depth 1) and, under slide, for every edge; n_x of the pair under order and the one "
             "window sentence's order under order_window (n is 0 or 1) for the deeper edges.  A real N<->N+1 edge = a cross edge whose two ends are seats of different sentences.  The "
             "z-axis keys of the three z_deep rules are not comparable with one another.)")
    text = "\n".join(L) + "\n"
    open(out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
