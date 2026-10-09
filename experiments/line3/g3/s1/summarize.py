"""G3-e / S1 summary: the t9/t10 tables for the sliding-window question path, with the T10 rows and B1/B2 alongside.
usage: summarize.py [RESULTS_DIR=results] [T10_RESULTS_DIR=../../t10/results] [--cache DIR]   -> RESULTS_DIR/summary.md (+ prints)
Inputs: RESULTS_DIR/ask_fulllead_<preset>_<tag>.jsonl (measure_slide.py; <tag> names the configuration, e.g. three, two_if_single_edge,
two_if_single_edge-wnone), and T10_RESULTS_DIR/ask_fulllead_<preset>_ordered-stop.jsonl (the T10 flat / layers sweeps whose rows are recomputed
here from their raw records with the same grading).  Grading is t9/scorer.py's (gold alternative a substring of ONE word of an entry, NFKC ...).
With --cache the window cache is loaded for the reach rows (the gold is a seated unit of a candidate window: the upper bound of a unit-valued
entry).  Needs fugashi (MeCab) for B1/B2: the Pro vera-wiring env."""
import glob, json, os, statistics, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
G3 = os.path.dirname(HERE)
LINE3 = os.path.dirname(G3)
ROOT = os.path.dirname(os.path.dirname(LINE3))
sys.path.insert(0, os.path.join(LINE3, "t9")); sys.path.insert(0, os.path.join(LINE3, "bank2")); sys.path.insert(0, ROOT)
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
CACHE = None
if "--cache" in sys.argv:
    CACHE = sys.argv[sys.argv.index("--cache") + 1]
    args = [a for a in args if a != CACHE]
RES = args[0] if len(args) > 0 else os.path.join(HERE, "results")
T10RES = args[1] if len(args) > 1 else os.path.join(LINE3, "t10", "results")
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


# ---------- systems: name -> {id: rec}; rec = {id, gold, kind, cands: [(label, words)], secs, ...} ----------
SYS, ORDER = {}, []


def add(name, rec):
    if name not in SYS:
        SYS[name] = {}; ORDER.append(name)
    SYS[name][rec["id"]] = rec


def load_slide():
    for p in sorted(glob.glob(os.path.join(RES, "ask_fulllead_*.jsonl"))):
        base = os.path.basename(p)[:-6].split("_", 3)            # ask fulllead <preset> <tag>
        preset, tag = base[2], base[3]
        for l in open(p, encoding="utf-8"):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if "error" in r:
                out("ERROR %s %s: %s" % (p, r["id"], r["error"].strip().splitlines()[-1])); continue
            name = "slide %s [%s]" % (preset, tag)
            cands = [(e["axis"], e["words"]) for e in r["entries"]]
            add(name, dict(id=r["id"], gold=r["gold"], kind=r["kind"], cands=cands, secs=r["ms"] / 1000, rec=r, preset=preset, tag=tag,
                           cands_path=[(e["axis"], sorted(set(e["words"]) | set(e["path_words"]))) for e in r["entries"]]))
            if tag in ("three", "two_if_single_edge"):         # derived: only the entries on which EVERY member of the window's class agrees
                un = [e for e in r["entries"] if e["members_agreeing"] == e["members_read"]]
                add("slide %s [%s] unanimous members only (derived)" % (preset, tag),
                    dict(id=r["id"], gold=r["gold"], kind=r["kind"], cands=[(e["axis"], e["words"]) for e in un], secs=r["ms"] / 1000, rec=r,
                         preset=preset, tag=tag, cands_path=[(e["axis"], sorted(set(e["words"]) | set(e["path_words"]))) for e in un]))


def load_t10():
    for p in sorted(glob.glob(os.path.join(T10RES, "ask_fulllead_*_ordered-stop.jsonl"))):
        preset = os.path.basename(p).split("_")[2]
        for l in open(p, encoding="utf-8"):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if "error" in r or r["kind"] not in ("intra2", "unans"):
                continue
            flat = [(t, e["words"]) for t in ("RUN", "WORD", "CHAR") if t in r["layer0"] for e in r["layer0"][t]["entries"]]
            run = [(t, w) for t, w in flat if t == "RUN"]
            base = dict(id=r["id"], gold=r["gold"], kind=r["kind"], secs=r["ms_layer0"] / 1000, preset=preset)
            add("T10 flat-%s (3 tiers) [ordered-stop]" % preset, dict(base, cands=flat))
            add("T10 flat-%s RUN tier only [ordered-stop]" % preset, dict(base, cands=run))
            if "seatsPath" in r.get("on", {}):
                up = [(t, e["words"]) for t, d in r["on"]["seatsPath"]["tiers"].items() for run_ in d["runs"] for e in run_["entries"]]
                add("T10 layers-ssp-%s [ordered-stop]" % preset, dict(base, cands=flat + up, secs=(r["ms_layer0"] + r["on"]["seatsPath"]["ms"]) / 1000))


def load_baselines():
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


load_slide(); load_t10(); load_baselines()


def hit(rec, cand): return S.hits_words(rec["gold"], cand[1])


def grade(rec, key="cands"):
    cs = rec[key]
    h = [n for n, c in enumerate(cs, 1) if hit(rec, c)]
    n = len(cs)
    if rec["kind"] == "unans":
        return ("none" if n == 0 else "single" if n == 1 else "list"), n, None
    if n == 0:
        return "none", 0, None
    if n == 1:
        return ("single_right" if h else "single_wrong"), 1, (1 if h else None)
    return ("list_gold" if h else "list_nogold"), n, (h[0] if h else None)


def ids_of(d, kind): return sorted(i for i in d if d[i]["kind"] == kind)
NAMES = sorted([n for n in ORDER if n.startswith("slide")], key=lambda n: (SYS[n][next(iter(SYS[n]))]["preset"] != "fast", n)) + \
    [n for n in ORDER if n.startswith("T10")] + [n for n in ORDER if n.startswith("B")]

out("# G3-e / S1 -- bank2 fulllead through the question path over sliding windows (`structure=\"slide\"`, tier RUN), with the T10 rows and B1/B2")
out()
out("Systems: `slide P [tag]` = ask_slide, preset P (fast 4 / standard 10 / full unbounded WINDOWS), tag = configuration (`three` = agreement R1=R2=R3; `two_if_single_edge` = an axis with one evidenced edge judged on R2, R3 only; suffixes: `-wnone` grouping by kind only (no question-unit count inside a group), `-sent` windows hold = units of the sentences, `-rep` representative of each class only, `-standins` stand-in units make a window a candidate). A candidate = one entry (window, axis, agreed unit; `words` = [unit]). `T10 flat-P` = the T10 flat sweep (3 tiers; candidates = entries over the 3 tiers) and its RUN tier only; `T10 layers-ssp-P` = flat + stable-seats-path layers. B1/B2 = baselines.py (MeCab / bigram).")
out()
out("Grading = t9/scorer.py (gold alternative a substring of one WORD of an entry; NFKC, casefold, ...). 'Gold in a candidate' = any candidate holds the gold. Single right / wrong = exactly one candidate (holds / does not hold) the gold; list = >= 2 candidates; none = no candidate. List size = number of entries (duplicates across windows / axes are separate entries, never merged; `distinct` = distinct unit sets).")
out()

for kind, n_exp in (("intra2", 69),):
    ids_ref = ids_of(bank, kind)
    out("## %s (fulllead, n = %d)" % (kind, len(ids_ref)))
    out()
    out("| system | n run | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max (lists) | distinct units median | first-gold pos median / max | windows read median / max | candidate windows median | partial (0 read) | s/question median (max) |")
    out("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for nm in NAMES:
        d = SYS[nm]
        ids = [i for i in ids_ref if i in d]
        if not ids:
            continue
        cnt = defaultdict(int); sizes = []; pos = []; secs = []; wr = []; cw = []; part = 0; zero = 0; dist = []
        for i in ids:
            c, n, p = grade(d[i]); cnt[c] += 1
            if n >= 2: sizes.append(n)
            if p: pos.append(p)
            if d[i]["secs"] is not None: secs.append(d[i]["secs"])
            dist.append(len({tuple(w) for _, w in d[i]["cands"]}))
            if "rec" in d[i]:
                rd = d[i]["rec"]["read"]
                wr.append(rd["windows_read"]); cw.append(rd["candidate_windows"])
                part += rd["partial"]; zero += (rd["partial"] and rd["candidate_windows_read"] == 0)
        g = cnt["single_right"] + cnt["list_gold"]
        out("| %s | %d | %s | %d | %d | %d | %d | %d | %s / %s | %s | %s / %s | %s | %s | %s | %s (%s) |" % (
            nm, len(ids), pct(g, len(ids)), cnt["single_right"], cnt["single_wrong"], cnt["list_gold"], cnt["list_nogold"], cnt["none"],
            f1(med(sizes)), max(sizes) if sizes else "-", f1(med(dist)), f1(med(pos)), max(pos) if pos else "-",
            ("%s / %s" % (f1(med(wr)), max(wr))) if wr else "-", f1(med(cw)) if cw else "-", ("%d (%d)" % (part, zero)) if wr else "-",
            f2(med(secs)), f2(max(secs)) if secs else "-"))
    out()

out("## unans (fulllead, n = 25): can a user reject what is shown?")
out()
out("Correct behaviour = abstain. 'no candidate' = typed abstention; 'list only' = rejectable by a user; 'single answer' = confident wrong.")
out()
out("| system | n run | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size median / max | verdicts |")
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
        if "rec" in d[i] and "(derived)" not in nm: vs[d[i]["rec"]["verdict"].replace("UNKNOWN_", "U_")] += 1
    out("| %s | %d | %d | %d | %d | %s / %s | %s |" % (nm, len(ids), cnt["none"], cnt["list"], cnt["single"], f1(med(sizes)), max(sizes) if sizes else "-",
                                                     ", ".join("%s %d" % kv for kv in sorted(vs.items())) or "-"))
out()

SL = [n for n in NAMES if n.startswith("slide")]
SLB = [n for n in SL if "(derived)" not in n]
out("## Per axis (slide systems, intra2): where the gold is found")
out()
out("'x only' / 'z only' / 'both' = the gold is in an entry of that axis only / of both axes; `y` never answers in S1 (RUN-only windows have no y edge). `unit+path` = the same count with the entry's path words (the units of the walk steps and edge partners, diagnostic: wider than the headline `words = [unit]`). `distinct windows` = windows with an entry, median.")
out()
out("| system | gold in an entry | x only | z only | both | gold in unit+path | entries x / z (total) | windows with an entry median | questions with an entry |")
out("|---|---|---|---|---|---|---|---|---|")
for nm in SL:
    d = SYS[nm]
    ids = ids_of(d, "intra2")
    if not ids:
        continue
    xo = zo = bo = up = ex = ez = qe = 0; wn = []
    for i in ids:
        r = d[i]
        ax = {a for a, w in r["cands"] if S.hits_words(r["gold"], w)}
        if ax == {"x"}: xo += 1
        elif ax == {"z"}: zo += 1
        elif ax >= {"x", "z"}: bo += 1
        up += any(S.hits_words(r["gold"], w) for _, w in r["cands_path"])
        ex += sum(1 for a, _ in r["cands"] if a == "x"); ez += sum(1 for a, _ in r["cands"] if a == "z")
        qe += bool(r["cands"]); wn.append(len({e["window"] for e in r["rec"]["entries"]}))
    out("| %s | %d | %d | %d | %d | %d | %d / %d (%d) | %s | %d |" % (nm, xo + zo + bo, xo, zo, bo, up, ex, ez, ex + ez, f1(med(wn)), qe))
out()

out("## Typed abstentions, summed over (window, axis) of the questions answered (slide systems)")
out()
kinds = ["points_nowhere", "section_disagreement", "ratio_disagreement", "no_edges", "not_grounded", "unstable_axis_improvable", "no_question_unit", "mixed"]
out("| system | kind | n | " + " | ".join(kinds) + " |")
out("|---|---|---|" + "---|" * len(kinds))
for nm in SLB:
    d = SYS[nm]
    for kind in ("intra2", "unans"):
        ids = ids_of(d, kind)
        c = Counter()
        for i in ids:
            for k, v in d[i]["rec"]["abstention_counts"].items():
                c[k] += v
        out("| %s | %s | %d | " % (nm, kind, len(ids)) + " | ".join(str(c.get(k, 0)) for k in kinds) + " |")
out()
out("Verdicts (all 94):")
out()
for nm in SLB:
    out("- %s: %s" % (nm, ", ".join("%s %d" % kv for kv in sorted(Counter(r["rec"]["verdict"] for r in SYS[nm].values()).items()))))
out()
out("Grammar forms of the 94 questions: " + ", ".join("%s %d" % kv for kv in sorted(Counter(
    r["rec"]["form"]["form"] for r in SYS[SL[0]].values()).items())) if SL else "")
out()

if CACHE:
    from verantyx.line3 import slide_query as Q
    wi = Q.WindowIndex.from_jsonl(os.path.join(LINE3, "bank2", "data", "fulllead_sents.jsonl"), CACHE, build=False)
    reach = 0; reach_read = {nm: 0 for nm in SL}; chance = []; ncand = []
    golds = {i: bank[i]["gold"] for i in ids_of(bank, "intra2")}
    for i in ids_of(bank, "intra2"):
        it = Q.intake(wi, bank[i]["question"])
        pl = Q.plan_windows(wi, it)
        seated = set().union(*[wi.by_n[n].seated for n in pl.read]) if pl.read else set()
        reach += any(S.hits_words(golds[i], [u]) for u in seated)
        ncand.append(pl.candidates)
    out("## Reach (window level, intra2)")
    out()
    out("The gold is a seated RUN unit of a window that holds a question unit (every candidate window, no cap): **%d / 69** (candidate windows per question: median %s, max %d). This is the upper bound of a unit-valued entry (`words = [unit]`) before the agreement, the cap or the tier of the gold (18 of the 69 golds are not one unit of any tier)." % (reach, f1(med(ncand)), max(ncand)))
    out()
    # chance: the golds of OTHER questions hit by the candidates of a question (over answered questions)
    if SL:
        out("## Chance hits (diagnostic): how often the gold of ANOTHER question is held by an entry")
        out()
        out("| system | questions with entries | mean entries | other golds held per question (mean x 100 / 68) |")
        out("|---|---|---|---|")
        for nm in SL:
            d = SYS[nm]
            tot = 0; q = 0; ne = 0
            for i in ids_of(d, "intra2"):
                if not d[i]["cands"]:
                    continue
                q += 1; ne += len(d[i]["cands"])
                tot += sum(1 for j, g in golds.items() if j != i and any(S.hits_words(g, w) for _, w in d[i]["cands"]))
            out("| %s | %d | %s | %s |" % (nm, q, f1(ne / q if q else None), f1(100 * tot / (68 * q) if q else None)))
        out()

out("## Time (wall seconds per question inside a worker; several workers at once on the shared machine)")
out()
out("| system | n | median / mean / max s | load median / max |")
out("|---|---|---|---|")
for nm in SLB:
    rs = list(SYS[nm].values())
    ts = [r["secs"] for r in rs]
    ld = [r["rec"]["load1"] for r in rs]
    out("| %s | %d | %s / %s / %s | %s / %s |" % (nm, len(rs), f2(med(ts)), f2(statistics.mean(ts)), f2(max(ts)), f1(med(ld)), f1(max(ld))))
out()
open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
