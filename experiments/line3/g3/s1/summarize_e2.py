"""G3-e2 summary: the nine S1 fast runs of sweep_e2.sh ({answer_shape unit, path} x {agreement three, two_if_single_edge} x {z_deep slide, order} with the
read order qcount_first, plus path + three + slide with the old read order grammar_first), graded with t9/scorer.py as S1's summarize.py does, with S1's
G3-c2 rows, the G3-c4 rows (old read order, unit shape, G3-c3 placements), T10 and B1/B2 beside them.
usage: summarize_e2.py [CACHE_ROOT]   -> results/summary_e2.md (+ prints); needs fugashi (the Pro vera-wiring env) for B1/B2.
CACHE_ROOT (slide/ and order/ window caches) adds the reach rows (the gold is a seated unit of a candidate window / of a window actually read at fast)."""
import glob, json, os, statistics, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
G3 = os.path.dirname(HERE)
LINE3 = os.path.dirname(G3)
ROOT = os.path.dirname(os.path.dirname(LINE3))
sys.path.insert(0, os.path.join(LINE3, "t9")); sys.path.insert(0, os.path.join(LINE3, "bank2")); sys.path.insert(0, ROOT)
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402

RES = os.path.join(HERE, "results")
C4RES = os.path.join(G3, "c4", "results")
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
        add(name, dict(id=r["id"], gold=r["gold"], kind=r["kind"], cands=[(e["axis"], e["words"], e.get("unit", e["words"][-1])) for e in r["entries"]],
                       secs=r["ms"] / 1000, rec=r))


ROWS = []
for zd in ("slide", "order"):
    for ag in ("three", "two_if_single_edge"):
        for sh in ("unit", "path"):
            ROWS.append(("E2 z=%s %s %s" % (zd, ag, sh), os.path.join(RES, "e2_z%s-%s-%s.jsonl" % (zd, ag, sh))))
ROWS.append(("E2 z=slide three path, OLD read order", os.path.join(RES, "e2_zslide-three-path-gfirst.jsonl")))
REF = [("ref c2 (S1, G3-c2 placements, old order) three", os.path.join(RES, "ask_fulllead_fast_three.jsonl")),
       ("ref c2 (S1, G3-c2 placements, old order) two_if_single_edge", os.path.join(RES, "ask_fulllead_fast_two_if_single_edge.jsonl"))]
for zd in ("slide", "order"):
    for ag in ("three", "two_if_single_edge"):
        REF.append(("ref c4 (G3-c3 placements, old order, unit) z=%s %s" % (zd, ag), os.path.join(C4RES, "ask_fulllead_fast_z%s-%s.jsonl" % (zd, ag))))
for nm, p in ROWS + REF:
    load_slide(p, nm)
SLN = [n for n, _ in ROWS + REF if n in SYS]
E2N = [n for n, _ in ROWS if n in SYS]

for p in sorted(glob.glob(os.path.join(T10RES, "ask_fulllead_fast_ordered-stop.jsonl"))):
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        if "error" in r or r["kind"] not in ("intra2", "unans"):
            continue
        flat = [(t, e["words"], e["words"][0] if e["words"] else None) for t in ("RUN", "WORD", "CHAR") if t in r["layer0"] for e in r["layer0"][t]["entries"]]
        base = dict(id=r["id"], gold=r["gold"], kind=r["kind"], secs=r["ms_layer0"] / 1000)
        add("T10 flat-fast (3 tiers)", dict(base, cands=flat))
        add("T10 flat-fast RUN tier only", dict(base, cands=[c for c in flat if c[0] == "RUN"]))
        if "seatsPath" in r.get("on", {}):
            up = [(t, e["words"], None) for t, d in r["on"]["seatsPath"]["tiers"].items() for run_ in d["runs"] for e in run_["entries"]]
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
            add("%s-%s" % (nm, tn), dict(id=qid, gold=r["gold"], kind=r["kind"], cands=[("S", [u[k][2]], u[k][2]) for k in cs], secs=None))
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


out("# G3-e2 -- the answer shape (end unit | walked path), the read order (more question units first | grammar first) and z_deep, on S1 fast")
out()
out("fulllead RUN, windows placed with the G3-c3 defaults (centre both growths, arm_cap budget, strict judgement) under z_deep slide / order (the G3-c4 window "
    "caches), fast = 4 windows read per question, tier RUN, t9 scorer (the gold is a substring of ONE word of a candidate).  A candidate = one entry "
    "(window, axis, agreed unit [, path under shape path]); `words` of an entry = the end unit (unit) or the units of the walked path (path).  "
    "Gold in a candidate = some candidate has the gold in one of its words; single right / wrong = exactly one candidate (does / does not); list = >= 2.  "
    "`E2` rows are this ticket; `ref` rows are earlier runs (old read order, unit shape).")
out()
out("## intra2 (fulllead, n = 69)")
out()
out("| system | n | gold in a candidate | via x / z | gold in the END unit / only in path words | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | words per entry median / max | first-gold pos median | windows read median / max | s/question median (max) |")
out("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
ids_ref = ids_of(bank, "intra2")
for nm in NAMES:
    d = SYS[nm]
    ids = [i for i in ids_ref if i in d]
    if not ids:
        continue
    cnt = defaultdict(int); sizes = []; wsz = []; wpe = []; pos = []; secs = []; wr = []; vx = vz = 0; end_ = only = 0
    for i in ids:
        c, n, p = grade(d[i]); cnt[c] += 1
        if n >= 2:
            sizes.append(n); wsz.append(sum(len(cc[1]) for cc in d[i]["cands"]))
        wpe.extend(len(cc[1]) for cc in d[i]["cands"])
        if p: pos.append(p)
        if d[i]["secs"] is not None: secs.append(d[i]["secs"])
        if "rec" in d[i]:
            wr.append(d[i]["rec"]["read"]["windows_read"])
        ax = {cc[0] for cc in d[i]["cands"] if S.hits_words(d[i]["gold"], cc[1])}
        vx += "x" in ax; vz += "z" in ax
        if c in ("single_right", "list_gold") and nm.startswith(("E2", "ref")):
            if any(S.hits_words(d[i]["gold"], [cc[2]]) for cc in d[i]["cands"]):
                end_ += 1
            else:
                only += 1
    g = cnt["single_right"] + cnt["list_gold"]
    slide = nm.startswith(("E2", "ref"))
    out("| %s | %d | %s | %s | %s | %d | %d | %d | %d | %d | %s / %s | %s / %s | %s / %s | %s | %s | %s (%s) |" % (
        nm, len(ids), pct(g, len(ids)), ("%d / %d" % (vx, vz)) if slide else "-", ("%d / %d" % (end_, only)) if slide else "-",
        cnt["single_right"], cnt["single_wrong"], cnt["list_gold"], cnt["list_nogold"], cnt["none"],
        f1(med(sizes)), max(sizes) if sizes else "-", f1(med(wsz)), max(wsz) if wsz else "-", f1(med(wpe)), max(wpe) if wpe else "-",
        f1(med(pos)), ("%s / %s" % (f1(med(wr)), max(wr))) if wr else "-", f2(med(secs)), f2(max(secs)) if secs else "-"))
out()
out("## unans (fulllead, n = 25): can a user reject what is shown?")
out()
out("| system | n | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size: entries median / max | words in the list median / max | verdicts |")
out("|---|---|---|---|---|---|---|---|")
for nm in NAMES:
    d = SYS[nm]
    ids = ids_of(d, "unans")
    if not ids:
        continue
    cnt = defaultdict(int); sizes = []; wsz = []; vs = Counter()
    for i in ids:
        c, n, _ = grade(d[i]); cnt[c] += 1
        if n >= 2:
            sizes.append(n); wsz.append(sum(len(cc[1]) for cc in d[i]["cands"]))
        if "rec" in d[i]: vs[d[i]["rec"]["verdict"].replace("UNKNOWN_", "U_")] += 1
    out("| %s | %d | %d | %d | %d | %s / %s | %s / %s | %s |" % (nm, len(ids), cnt["none"], cnt["list"], cnt["single"], f1(med(sizes)), max(sizes) if sizes else "-",
                                                             f1(med(wsz)), max(wsz) if wsz else "-", ", ".join("%s %d" % kv for kv in sorted(vs.items())) or "-"))
out()
out("## Entries and where the questions end (slide systems; both kinds): entries x / z, words in them, typed abstentions summed over (window, axis)")
out()
kinds = ["points_nowhere", "section_disagreement", "ratio_disagreement", "no_edges", "not_grounded", "unstable_axis_improvable", "no_question_unit", "mixed"]
out("| system | kind | n | entries x / z | words in entries (distinct) | entries with > 1 word | " + " | ".join(kinds) + " |")
out("|---|---|---|---|---|---|" + "---|" * len(kinds))
for nm in SLN:
    d = SYS[nm]
    for kind in ("intra2", "unans"):
        ids = ids_of(d, kind)
        c = Counter(); ex = ez = 0; nw = 0; dist = set(); multi = 0
        for i in ids:
            for k, v in d[i]["rec"]["abstention_counts"].items():
                c[k] += v
            for a, w, _u in d[i]["cands"]:
                ex += a == "x"; ez += a == "z"; nw += len(w); multi += len(w) > 1; dist.update((i, x) for x in w)
        out("| %s | %s | %d | %d / %d | %d (%d) | %d | " % (nm, kind, len(ids), ex, ez, nw, len(dist), multi) + " | ".join(str(c.get(k, 0)) for k in kinds) + " |")
out()
out("## Verdicts of the answerable questions and the reading cap (slide systems)")
out()
out("| system | verdicts (intra2) | partial questions | questions that read nothing (first block larger than the cap) | windows read: 0 / 1-3 / 4 |")
out("|---|---|---|---|---|")
for nm in SLN:
    d = SYS[nm]
    ids = ids_of(d, "intra2")
    vs = Counter(d[i]["rec"]["verdict"].replace("UNKNOWN_", "U_") for i in ids)
    part = sum(1 for i in ids if d[i]["rec"]["read"]["partial"])
    zero = sum(1 for i in ids if d[i]["rec"]["read"]["windows_read"] == 0 and d[i]["rec"]["read"]["candidate_windows"] > 0)
    wr = Counter(min(d[i]["rec"]["read"]["windows_read"], 4) if d[i]["rec"]["read"]["windows_read"] in (0, 4) else 2 for i in ids)
    out("| %s | %s | %d | %d | %d / %d / %d |" % (nm, ", ".join("%s %d" % kv for kv in sorted(vs.items())), part, zero, wr[0], wr[2], wr[4]))
out()
if CACHE:
    from verantyx.line3 import slide_query as Q
    out("## Reach (window level, intra2): the gold is a seated RUN unit of a window that holds a question unit")
    out()
    out("`all candidates` = no cap (40 / 69 on the G3-c2 placements); `read at fast` = of the windows the plan actually reads at fast (4 windows, whole blocks), per read order.")
    out()
    out("| placements | all candidates | read at fast, qcount_first | read at fast, grammar_first | windows read at fast median (qcount_first / grammar_first) | questions that read nothing (qcount_first / grammar_first) |")
    out("|---|---|---|---|---|---|")
    golds = {i: bank[i]["gold"] for i in ids_of(bank, "intra2")}
    for zd in ("slide", "order"):
        wi = Q.WindowIndex.from_jsonl(os.path.join(LINE3, "bank2", "data", "fulllead_sents.jsonl"), os.path.join(CACHE, zd), build=False, z_deep=zd)
        allc = 0; rq = Counter(); nr = {"qcount_first": [], "grammar_first": []}; zero = Counter()
        for i in ids_of(bank, "intra2"):
            it = Q.intake(wi, bank[i]["question"])
            full = Q.plan_windows(wi, it)
            seated = set().union(*[wi.by_n[n].seated for n in full.read]) if full.read else set()
            allc += any(S.hits_words(golds[i], [u]) for u in seated)
            for ro in ("qcount_first", "grammar_first"):
                pl = Q.plan_windows(wi, it, cap=4, read_order=ro)
                sd = set().union(*[wi.by_n[n].seated for n in pl.read]) if pl.read else set()
                rq[ro] += any(S.hits_words(golds[i], [u]) for u in sd)
                nr[ro].append(len(pl.read)); zero[ro] += (not pl.read) and pl.candidates > 0
        out("| z_deep %s | %d / 69 | %d / 69 | %d / 69 | %s / %s | %d / %d |" % (zd, allc, rq["qcount_first"], rq["grammar_first"], f1(med(nr["qcount_first"])),
                                                                              f1(med(nr["grammar_first"])), zero["qcount_first"], zero["grammar_first"]))
    out()
pc = os.path.join(RES, "path_ceiling.md")
if os.path.exists(pc):
    out("## What the path shape could reach if the agreement did not decide (path_ceiling.py, intra2, windows read at fast, every readable member, agreement three's walks)")
    out()
    for l in open(pc, encoding="utf-8").read().splitlines():
        out(l)
    out()
nt = os.path.join(RES, "notes_e2.md")
if os.path.exists(nt):
    for l in open(nt, encoding="utf-8").read().splitlines():
        out(l)
open(os.path.join(RES, "summary_e2.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
