"""G3-c4 summary: the four configurations {z_deep slide, order} x {agreement three, two_if_single_edge} at fast on the 94 fulllead questions of bank2
(69 intra2 + 25 unans), graded with t9/scorer.py as S1's summarize.py does, with S1's G3-c2 rows, T10 and B1/B2 beside them.
usage: c4_summary.py [CACHE_ROOT]      -> results/summary.md (+ prints); needs fugashi (the Pro vera-wiring env) for B1/B2.
Inputs: results/ask_fulllead_fast_z<rule>-<agreement>.jsonl (measure_c4.py), ../s1/results/ask_fulllead_fast_{three,two_if_single_edge}.jsonl
(S1: the G3-c2 placements), ../../t10/results/ask_fulllead_fast_ordered-stop.jsonl, results/cache_stats.md (written by cache_stats.py).
With CACHE_ROOT the reach rows are added (the gold is a seated unit of a candidate window)."""
import glob
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
G3 = os.path.dirname(HERE)
LINE3 = os.path.dirname(G3)
ROOT = os.path.dirname(os.path.dirname(LINE3))
sys.path.insert(0, os.path.join(LINE3, "t9")); sys.path.insert(0, os.path.join(LINE3, "bank2")); sys.path.insert(0, ROOT)
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402

RES = os.path.join(HERE, "results")
S1RES = os.path.join(G3, "s1", "results")
T10RES = os.path.join(LINE3, "t10", "results")
CACHE = sys.argv[1] if len(sys.argv) > 1 else None
BANK = os.path.join(LINE3, "bank2", "bank2.tsv")
bank = {}
for l in open(BANK, encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = dict(zip(BL.FIELDS, l.rstrip("\n").split("\t")))
    if r["corpus"] == "fulllead":
        bank[r["id"]] = r
L = []


def out(s=""):
    L.append(s); print(s)


def med(x): return statistics.median(x) if x else None
def f1(x): return "-" if x is None else "%.1f" % x
def f2(x): return "-" if x is None else "%.2f" % x
def pct(a, b): return "%d (%d%%)" % (a, round(100 * a / b)) if b else "-"


SYS, ORDER = {}, []


def add(name, rec):
    if name not in SYS:
        SYS[name] = {}; ORDER.append(name)
    SYS[name][rec["id"]] = rec


def load_slide(path, name):
    if not os.path.exists(path):
        out("MISSING %s" % path); return
    for l in open(path, encoding="utf-8"):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if "error" in r:
            out("ERROR %s %s: %s" % (path, r["id"], r["error"].strip().splitlines()[-1])); continue
        add(name, dict(id=r["id"], gold=r["gold"], kind=r["kind"], cands=[(e["axis"], e["words"]) for e in r["entries"]], secs=r["ms"] / 1000, rec=r))


ROWS = [("c2 (S1, G3-c2 placements) three", os.path.join(S1RES, "ask_fulllead_fast_three.jsonl")),
        ("c2 (S1, G3-c2 placements) two_if_single_edge", os.path.join(S1RES, "ask_fulllead_fast_two_if_single_edge.jsonl"))]
for zd in ("slide", "order"):
    for ag in ("three", "two_if_single_edge"):
        ROWS.append(("c3 placements, z_deep %s, %s" % (zd, ag), os.path.join(RES, "ask_fulllead_fast_z%s-%s.jsonl" % (zd, ag))))
for nm, p in ROWS:
    load_slide(p, nm)
SLN = [n for n, _ in ROWS if n in SYS]

for p in sorted(glob.glob(os.path.join(T10RES, "ask_fulllead_fast_ordered-stop.jsonl"))):
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        if "error" in r or r["kind"] not in ("intra2", "unans"):
            continue
        flat = [(t, e["words"]) for t in ("RUN", "WORD", "CHAR") if t in r["layer0"] for e in r["layer0"][t]["entries"]]
        base = dict(id=r["id"], gold=r["gold"], kind=r["kind"], secs=r["ms_layer0"] / 1000)
        add("T10 flat-fast (3 tiers)", dict(base, cands=flat))
        add("T10 flat-fast RUN tier only", dict(base, cands=[(t, w) for t, w in flat if t == "RUN"]))
        if "seatsPath" in r.get("on", {}):
            up = [(t, e["words"]) for t, d in r["on"]["seatsPath"]["tiers"].items() for run_ in d["runs"] for e in run_["entries"]]
            add("T10 layers-ssp-fast", dict(base, cands=flat + up, secs=(r["ms_layer0"] + r["on"]["seatsPath"]["ms"]) / 1000))
units = BL.load()
toks = BL.make_tokenizers()
index = {c: {(t, i): k for k, (t, i, _) in enumerate(u)} for c, u in units.items()}
titles = sorted({t for t, _, _ in units["s3000"] if len(t) >= 2}, key=len, reverse=True)
for tn, tok in toks.items():
    for qid, r in bank.items():
        u = units["fulllead"]
        _best, c1 = BL.b1(u, tok(r["question"]))
        c2 = BL.b2(u, c1, "fulllead", index["fulllead"], titles)
        for nm, cs in (("B1", c1), ("B2", c2)):
            add("%s-%s" % (nm, tn), dict(id=qid, gold=r["gold"], kind=r["kind"], cands=[("S", [u[k][2]]) for k in cs], secs=None))
NAMES = SLN + [n for n in ORDER if n.startswith("T10")] + [n for n in ORDER if n.startswith("B")]


def grade(rec):
    cs = rec["cands"]
    h = [n for n, c in enumerate(cs, 1) if S.hits_words(rec["gold"], c[1])]
    n = len(cs)
    if rec["kind"] == "unans":
        return ("none" if n == 0 else "single" if n == 1 else "list"), n, None
    if n == 0:
        return "none", 0, None
    if n == 1:
        return ("single_right" if h else "single_wrong"), 1, (1 if h else None)
    return ("list_gold" if h else "list_nogold"), n, (h[0] if h else None)


def ids_of(d, kind): return sorted(i for i in d if d[i]["kind"] == kind)


out("# G3-c4 -- the deeper z-arm edges: evidence rule `slide` (n_z) vs `order` (the pair's word order, as x) on the question path over sliding windows")
out()
out("fulllead RUN, windows placed with the G3-c3 defaults (centre both growths, arm_cap budget, strict judgement), fast = 4 windows read per question, tier RUN, "
    "t9 scorer; `c2` rows = S1's committed run on the G3-c2 placements (before G3-c3); `c3 placements, z_deep slide` = the G3-c3 defaults unchanged. "
    "A candidate = one entry (window, axis, agreed unit).  Gold in a candidate = some candidate holds the gold (a WORD substring, NFKC); single right / wrong = exactly one candidate (does / does not); list = >= 2.")
out()
out("## intra2 (fulllead, n = 69)")
out()
out("| system | n | gold in a candidate | via x / via z | single right | single wrong | list with gold | list without gold | no candidate | list size median / max | first-gold pos median | windows read median / max | s/question median (max) |")
out("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
ids_ref = ids_of(bank, "intra2")
for nm in NAMES:
    d = SYS[nm]
    ids = [i for i in ids_ref if i in d]
    if not ids:
        continue
    cnt = defaultdict(int); sizes = []; pos = []; secs = []; wr = []; vx = vz = 0
    for i in ids:
        c, n, p = grade(d[i]); cnt[c] += 1
        if n >= 2: sizes.append(n)
        if p: pos.append(p)
        if d[i]["secs"] is not None: secs.append(d[i]["secs"])
        if "rec" in d[i]:
            wr.append(d[i]["rec"]["read"]["windows_read"])
        ax = {a for a, w in d[i]["cands"] if S.hits_words(d[i]["gold"], w)}
        vx += "x" in ax; vz += "z" in ax
    g = cnt["single_right"] + cnt["list_gold"]
    slide = nm.startswith("c2") or nm.startswith("c3")
    out("| %s | %d | %s | %s | %d | %d | %d | %d | %d | %s / %s | %s | %s | %s (%s) |" % (
        nm, len(ids), pct(g, len(ids)), ("%d / %d" % (vx, vz)) if slide else "-", cnt["single_right"], cnt["single_wrong"], cnt["list_gold"], cnt["list_nogold"], cnt["none"],
        f1(med(sizes)), max(sizes) if sizes else "-", f1(med(pos)), ("%s / %s" % (f1(med(wr)), max(wr))) if wr else "-", f2(med(secs)), f2(max(secs)) if secs else "-"))
out()
out("## unans (fulllead, n = 25): can a user reject what is shown?")
out()
out("| system | n | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size median / max | verdicts |")
out("|---|---|---|---|---|---|---|")
for nm in NAMES:
    d = SYS[nm]
    ids = ids_of(d, "unans")
    if not ids:
        continue
    cnt = defaultdict(int); sizes = []; vs = Counter()
    for i in ids:
        c, n, _ = grade(d[i]); cnt[c] += 1
        if n >= 2: sizes.append(n)
        if "rec" in d[i]: vs[d[i]["rec"]["verdict"].replace("UNKNOWN_", "U_")] += 1
    out("| %s | %d | %d | %d | %d | %s / %s | %s |" % (nm, len(ids), cnt["none"], cnt["list"], cnt["single"], f1(med(sizes)), max(sizes) if sizes else "-",
                                                     ", ".join("%s %d" % kv for kv in sorted(vs.items())) or "-"))
out()
out("## Where the questions end (slide systems): typed abstentions summed over (window, axis) of the questions answered, and the entries")
out()
kinds = ["points_nowhere", "section_disagreement", "ratio_disagreement", "no_edges", "not_grounded", "unstable_axis_improvable", "no_question_unit", "mixed"]
out("| system | kind | n | entries x / z | " + " | ".join(kinds) + " |")
out("|---|---|---|---|" + "---|" * len(kinds))
for nm in SLN:
    d = SYS[nm]
    for kind in ("intra2", "unans"):
        ids = ids_of(d, kind)
        c = Counter(); ex = ez = 0
        for i in ids:
            for k, v in d[i]["rec"]["abstention_counts"].items():
                c[k] += v
            ex += sum(1 for a, _ in d[i]["cands"] if a == "x"); ez += sum(1 for a, _ in d[i]["cands"] if a == "z")
        out("| %s | %s | %d | %d / %d | " % (nm, kind, len(ids), ex, ez) + " | ".join(str(c.get(k, 0)) for k in kinds) + " |")
out()
if CACHE:
    from verantyx.line3 import slide as SL
    import functools
    from verantyx.line3 import slide_query as Q
    out("## Reach (window level, intra2): the gold is a seated RUN unit of a window that holds a question unit (every candidate window, no cap)")
    out()
    out("| placements | reach / 69 | candidate windows median / max | windows read without the cap (plan_windows cap=None), median |")
    out("|---|---|---|---|")
    orig = SL.default_spec
    golds = {i: bank[i]["gold"] for i in ids_of(bank, "intra2")}
    for zd in ("slide", "order"):
        SL.default_spec = functools.partial(orig, z_deep=zd)
        wi = Q.WindowIndex.from_jsonl(os.path.join(LINE3, "bank2", "data", "fulllead_sents.jsonl"), os.path.join(CACHE, zd), build=False)
        reach = 0; nc = []; nr = []
        for i in ids_of(bank, "intra2"):
            it = Q.intake(wi, bank[i]["question"])
            pl = Q.plan_windows(wi, it)
            seated = set().union(*[wi.by_n[n].seated for n in pl.read]) if pl.read else set()
            reach += any(S.hits_words(golds[i], [u]) for u in seated)
            nc.append(pl.candidates); nr.append(len(pl.read))
        out("| z_deep %s | %d / 69 | %s / %d | %s |" % (zd, reach, f1(med(nc)), max(nc), f1(med(nr))))
    SL.default_spec = orig
    out()
    out("(S1 on the G3-c2 placements: reach 40 / 69.)")
    out()
cs = os.path.join(RES, "cache_stats.md")
if os.path.exists(cs):
    out("## The window caches (292 pair windows)")
    out()
    for l in open(cs, encoding="utf-8").read().splitlines()[2:]:
        out(l)
    out()
for fn, title in (("gold_diag.md", "## The members of the windows that seat the gold (gold_diag.py)"), ("verify_order.md", "## The independent verifier on real windows (verify_order.py)")):
    pth = os.path.join(RES, fn)
    if os.path.exists(pth):
        out(title)
        out()
        for l in open(pth, encoding="utf-8").read().splitlines()[2:]:
            out(l.replace("## agreement", "### agreement"))
        out()
open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
