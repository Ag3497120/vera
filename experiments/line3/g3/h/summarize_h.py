"""G3-h summary: the grid {arm_cap budget | x} x {z_deep slide | order | order_window} x {seat_empty_axis allow | deny} on bank2 fulllead RUN, the window-flat read
(slide_flat.ask_flat, members = the first member of each growth, search budget 512/64, read order qcount_first), both evidence variants (plain | window), fast and
standard, graded with t9/scorer.py exactly as g3/s1flat/summarize_flat.py grades (gold in a candidate = the gold is a substring of ONE word of a candidate; single =
exactly one candidate entry; list = >= 2).
usage: summarize_h.py [RESULTS_DIR=results]  -> RESULTS_DIR/summary.md (+ prints).  Needs the Pro vera-wiring env (scorer)."""
import itertools, json, os, statistics, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
G3 = os.path.dirname(HERE)
LINE3 = os.path.dirname(G3)
ROOT = os.path.dirname(os.path.dirname(LINE3))
sys.path.insert(0, os.path.join(LINE3, "t9")); sys.path.insert(0, ROOT)
import scorer as S                      # noqa: E402

RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results")
S1F = os.path.join(G3, "s1flat", "results")
CAPS, ZDS, SEATS = ("budget", "x"), ("slide", "order", "order_window"), ("allow", "deny")
CELLS = list(itertools.product(CAPS, ZDS, SEATS))
RUNS = [(p, e) for p in ("fast", "standard") for e in ("plain", "window")]
BANK = os.path.join(LINE3, "bank2", "bank2.tsv")
kinds = {}
for l in open(BANK, encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = l.rstrip("\n").split("\t")
    if r[2] == "fulllead":
        kinds[r[0]] = r[1]
OUT = []


def out(s=""):
    OUT.append(s); print(s)


def med(x): return statistics.median(x) if x else None
def f1(x): return "-" if x is None else "%.1f" % x
def f2(x): return "-" if x is None else "%.2f" % x


def load(path):
    d = {}
    if not os.path.exists(path):
        return None
    for l in open(path, encoding="utf-8"):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if "error" in r:
            continue
        d[r["id"]] = r
    return d


def grade(r):
    cs = [e["words"] for e in r["entries"]]
    n = len(cs)
    hit = any(S.hits_words(r["gold"], w) for w in cs)
    if r["kind"] == "unans":
        return ("none" if n == 0 else "single" if n == 1 else "list"), n
    if n == 0:
        return "none", 0
    if n == 1:
        return ("single_right" if hit else "single_wrong"), 1
    return ("list_gold" if hit else "list_nogold"), n


def key(preset, cell, ev): return "h_%s_%s_%s_%s_%s.jsonl" % ((preset,) + cell + (ev,))


DATA = {}
for preset, ev in RUNS:
    for cell in CELLS:
        d = load(os.path.join(RES, key(preset, cell, ev)))
        if d is not None:
            DATA[(preset, ev, cell)] = d


def stats(d):
    ii = sorted(i for i in d if d[i]["kind"] == "intra2")
    uu = sorted(i for i in d if d[i]["kind"] == "unans")
    cnt = defaultdict(int); sizes = []; secs = []; wsz = []; gold = set()
    for i in ii:
        c, n = grade(d[i]); cnt[c] += 1
        if c in ("single_right", "list_gold"):
            gold.add(i)
        if n >= 2:
            sizes.append(n); wsz.append(sum(len(e["words"]) for e in d[i]["entries"]))
    ucnt = defaultdict(int); usizes = []
    for i in uu:
        c, n = grade(d[i]); ucnt[c] += 1
        if n >= 2:
            usizes.append(n)
    for i in d:
        secs.append(d[i]["ms"] / 1000)
    return dict(n=len(ii), nu=len(uu), cnt=cnt, ucnt=ucnt, sizes=sizes, usizes=usizes, wsz=wsz, secs=secs, gold=gold,
                gc=cnt["single_right"] + cnt["list_gold"], loads=[d[i]["load1"] for i in d])


ST = {k: stats(v) for k, v in DATA.items()}


def label(cell): return "%s / %s / %s" % cell


out("# G3-h -- the window placements' \"measure both\" switches, measured through the window-flat read (bank2 fulllead RUN)")
out()
out("Grid: arm_cap {budget, x} x z_deep {slide, order, order_window} x seat_empty_axis {allow, deny}; centre_scope both, strict judgement, growth z_reserved, seat_key unit_sid, "
    "level mid, padding one (592 windows, 292 pairs) in every cell. Read: slide_flat.ask_flat, members = the first member of each growth, search budget 512/64, both seats of a "
    "shared unit, read order qcount_first, windows read: fast 4 / standard 10, tier RUN, the per-axis labels attached (labels only), evidence plain | window. Grading: t9 scorer, "
    "as g3/s1flat/summarize_flat.py (gold in a candidate = the gold is a substring of one word of one candidate; single = exactly one candidate entry; list = at least two). "
    "Times are wall seconds per question with 6 worker processes at the load stated in the meta files (not comparable to a quiet machine). The cell budget / slide / allow is "
    "the G3-f row; the check against the G3-f records is the last section.")
out()
out("Under the combined list (G3-g2) a window-only single entry never ANSWERs: the `single right / wrong` columns below are the flat grader's (one candidate), and the "
    "same questions are lists of one entry in the combined list.")
out()
for preset, ev in RUNS:
    out("## intra2 (n = 69), %s, evidence %s" % (preset, ev))
    out()
    out("| arm_cap / z_deep / seat_empty | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | s/question median (max) |")
    out("|---|---|---|---|---|---|---|---|---|---|")
    for cell in CELLS:
        s = ST.get((preset, ev, cell))
        if s is None:
            out("| %s | (not run) |||||||||" % label(cell)); continue
        c = s["cnt"]
        out("| %s | %d (%d%%) | %d | %d | %d | %d | %d | %s / %s | %s / %s | %s (%s) |" % (
            label(cell), s["gc"], round(100 * s["gc"] / s["n"]), c["single_right"], c["single_wrong"], c["list_gold"], c["list_nogold"], c["none"],
            f1(med(s["sizes"])), max(s["sizes"]) if s["sizes"] else "-", f1(med(s["wsz"])), max(s["wsz"]) if s["wsz"] else "-", f2(med(s["secs"])), f2(max(s["secs"]))))
    out()
    out("## unans (n = 25), %s, evidence %s" % (preset, ev))
    out()
    out("| arm_cap / z_deep / seat_empty | abstained (no candidate) | list only | single answer (confident wrong) | list size: entries median / max |")
    out("|---|---|---|---|---|")
    for cell in CELLS:
        s = ST.get((preset, ev, cell))
        if s is None:
            continue
        c = s["ucnt"]
        out("| %s | %d | %d | %d | %s / %s |" % (label(cell), c["none"], c["list"], c["single"], f1(med(s["usizes"])), max(s["usizes"]) if s["usizes"] else "-"))
    out()

# ---- the compact grid -------------------------------------------------------------------------------------------------
out("## The grid at a glance: gold in a candidate (of 69) | unans abstained / list / single wrong (of 25), per run")
out()
out("| arm_cap / z_deep / seat_empty | " + " | ".join("%s %s gold | %s %s unans" % (r + r) for r in RUNS) + " |")
out("|---|" + "---|---|" * len(RUNS))
for cell in CELLS:
    row = []
    for preset, ev in RUNS:
        s = ST.get((preset, ev, cell))
        row.append("-" if s is None else "%d | %d / %d / %d" % (s["gc"], s["ucnt"]["none"], s["ucnt"]["list"], s["ucnt"]["single"]))
    out("| %s | " % label(cell) + " | ".join("%s" % r for r in row) + " |")
out()

# ---- marginals --------------------------------------------------------------------------------------------------------
out("## One factor at a time: the sum over the other factors' cells (gold in a candidate summed over the cells of the factor value; answerable single wrong summed; unans abstained and unans single wrong summed). arm_cap and z_deep over the ALLOW cells only (deny seats the same units, so its cells would only double the sums); seat_empty over all twelve")
out()
out("| factor = value | cells | " + " | ".join("%s %s: gold / single wrong / unans abst. / unans single" % r for r in RUNS) + " |")
out("|---|---|" + "---|" * len(RUNS))
for fi, (fname, vals) in enumerate((("arm_cap", CAPS), ("z_deep", ZDS), ("seat_empty", SEATS))):
    for v in vals:
        cells = [c for c in CELLS if c[fi] == v and (fname == "seat_empty" or c[2] == "allow")]
        row = []
        for preset, ev in RUNS:
            ss = [ST[(preset, ev, c)] for c in cells if (preset, ev, c) in ST]
            row.append("%d / %d / %d / %d" % (sum(s["gc"] for s in ss), sum(s["cnt"]["single_wrong"] for s in ss), sum(s["ucnt"]["none"] for s in ss),
                                              sum(s["ucnt"]["single"] for s in ss)))
        out("| %s = %s | %d | " % (fname, v, len(cells)) + " | ".join(row) + " |")
out()

# ---- which questions move ------------------------------------------------------------------------------------------------
REF = ("budget", "slide", "allow")
out("## Which answerable questions have the gold in a candidate, against the reference cell budget / slide / allow (G3-f's configuration): gained / lost question ids")
out()
out("| run | cell | gold | gained | lost |")
out("|---|---|---|---|---|")
for preset, ev in RUNS:
    ref = ST.get((preset, ev, REF))
    if ref is None:
        continue
    for cell in CELLS:
        s = ST.get((preset, ev, cell))
        if s is None or cell == REF:
            continue
        out("| %s %s | %s | %d | %s | %s |" % (preset, ev, label(cell), s["gc"], ", ".join(sorted(s["gold"] - ref["gold"])) or "-", ", ".join(sorted(ref["gold"] - s["gold"])) or "-"))
out()

# ---- allow vs deny ------------------------------------------------------------------------------------------------------
out("## seat_empty_axis allow against deny: questions whose answer (the entries' words, the verdict) differs between the two, per run and (arm_cap, z_deep)")
out()
out("| run | " + " | ".join("%s / %s" % (c, z) for c, z in itertools.product(CAPS, ZDS)) + " |")
out("|---|" + "---|" * (len(CAPS) * len(ZDS)))
for preset, ev in RUNS:
    row = []
    for c, z in itertools.product(CAPS, ZDS):
        a, b = DATA.get((preset, ev, (c, z, "allow"))), DATA.get((preset, ev, (c, z, "deny")))
        if a is None or b is None:
            row.append("-"); continue
        diff = [i for i in a if i in b and (a[i]["verdict"] != b[i]["verdict"] or [e["words"] for e in a[i]["entries"]] != [e["words"] for e in b[i]["entries"]])]
        row.append("%d of %d" % (len(diff), len(a)))
    out("| %s %s | " % (preset, ev) + " | ".join(row) + " |")
out()

# ---- regression against G3-f -------------------------------------------------------------------------------------------
out("## Check against the G3-f records (g3/s1flat/results/flat_*): the cells budget / slide / allow and budget / order / allow must give the same answers")
out()
out("| run | cell | questions in both | same verdict and same entries (words, centres, window) | different |")
out("|---|---|---|---|---|")
for preset, ev in RUNS:
    for zd in ("slide", "order"):
        old = load(os.path.join(S1F, "flat_%s_z%s_rep%s.jsonl" % (preset, zd, "_ev-window" if ev == "window" else "")))
        new = DATA.get((preset, ev, ("budget", zd, "allow")))
        if old is None or new is None:
            out("| %s %s | budget / %s / allow | (missing) | | |" % (preset, ev, zd)); continue
        both = [i for i in new if i in old]
        sig = lambda r: (r["verdict"], [(e["window"], e["words"], e["centres"]) for e in r["entries"]])
        same = sum(1 for i in both if sig(old[i]) == sig(new[i]))
        out("| %s %s | budget / %s / allow | %d | %d | %d |" % (preset, ev, zd, len(both), same, len(both) - same))
out()
open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
