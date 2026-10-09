"""G3-f summary: S1-flat (the window cross read FLAT, slide_flat.py) on bank2 fulllead RUN, graded with t9/scorer.py exactly as S1's summarize_e2.py
does, beside S1 per-axis (the G3-e2 runs), T10 flat-fast / layers-ssp-fast and B1/B2.
usage: summarize_flat.py [CACHE_ROOT]   -> results/summary_flat.md (+ prints); needs fugashi (the Pro vera-wiring env) for B1/B2.
A candidate = one entry: a flat entry (window, the word set of the path words + centre, centres) or a per-axis entry (window, axis, unit / path words)."""
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
E2RES = os.path.join(G3, "s1", "results")
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


def load(path, name, flat):
    if not os.path.exists(path):
        out("MISSING %s" % path); return
    for l in open(path, encoding="utf-8"):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if "error" in r:
            out("ERROR %s %s: %s" % (path, r["id"], r["error"].strip().splitlines()[-1])); continue
        if flat:
            cands = [("F", e["words"], e["centres"][0] if e["centres"] else None) for e in r["entries"]]
        else:
            cands = [(e["axis"], e["words"], e.get("unit", e["words"][-1])) for e in r["entries"]]
        add(name, dict(id=r["id"], gold=r["gold"], kind=r["kind"], cands=cands, secs=r["ms"] / 1000, rec=r, flat=flat))


FLAT = []
for pre, nm in (("fast_zslide_rep", "FLAT rep z=slide fast"), ("fast_zorder_rep", "FLAT rep z=order fast"),
                ("standard_zslide_rep", "FLAT rep z=slide standard"), ("standard_zorder_rep", "FLAT rep z=order standard"),
                ("fast_zslide_rep_b64-8", "FLAT rep z=slide fast, budget 64/8"), ("fast_zslide_rep_b4096-512", "FLAT rep z=slide fast, budget 4096/512"),
                ("fast_zslide_rep_twoseat-n", "FLAT rep z=slide fast, one seat per shared unit"),
                ("fast_zslide_rep_ev-window", "FLAT rep z=slide fast, evidence window"), ("fast_zorder_rep_ev-window", "FLAT rep z=order fast, evidence window"),
                ("standard_zslide_rep_ev-window", "FLAT rep z=slide standard, evidence window"),
                ("standard_zorder_rep_ev-window", "FLAT rep z=order standard, evidence window"),
                ("fast_zslide_all_sub", "FLAT all z=slide fast (subset)"), ("fast_zslide_all_sub_ev-window", "FLAT all z=slide fast, evidence window (subset)")):
    p = os.path.join(RES, "flat_%s.jsonl" % pre)
    if os.path.exists(p):
        FLAT.append((nm, p))
for nm, p in FLAT:
    load(p, nm, True)
REF = []
for zd in ("slide", "order"):
    for ag in ("three", "two_if_single_edge"):
        REF.append(("S1 per-axis z=%s %s path" % (zd, ag), os.path.join(E2RES, "e2_z%s-%s-path.jsonl" % (zd, ag))))
for nm, p in REF:
    load(p, nm, False)
FLN = [n for n, _ in FLAT if n in SYS]
SLN = [n for n, _ in REF if n in SYS]

for pre in ("fast", "standard"):
    for p in sorted(glob.glob(os.path.join(T10RES, "ask_fulllead_%s_ordered-stop.jsonl" % pre))):
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            if "error" in r or r["kind"] not in ("intra2", "unans"):
                continue
            flat = [(t, e["words"], e["words"][0] if e["words"] else None) for t in ("RUN", "WORD", "CHAR") if t in r["layer0"] for e in r["layer0"][t]["entries"]]
            base = dict(id=r["id"], gold=r["gold"], kind=r["kind"], secs=r["ms_layer0"] / 1000)
            add("T10 flat-%s (3 tiers)" % pre, dict(base, cands=flat))
            add("T10 flat-%s RUN tier only" % pre, dict(base, cands=[c for c in flat if c[0] == "RUN"]))
            if "seatsPath" in r.get("on", {}):
                up = [(t, e["words"], None) for t, d in r["on"]["seatsPath"]["tiers"].items() for run_ in d["runs"] for e in run_["entries"]]
                add("T10 layers-ssp-%s" % pre, dict(base, cands=flat + up, secs=(r["ms_layer0"] + r["on"]["seatsPath"]["ms"]) / 1000))
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
NAMES = FLN + SLN + [n for n in ORDER if n.startswith("T10")] + [n for n in ORDER if n.startswith("B")]


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


out("# G3-f -- the sliding-window placements read as FLAT crosses (S1-flat), on bank2 fulllead RUN")
out()
out("fulllead RUN, windows placed with the G3-c3 defaults (centre both growths, arm_cap budget, strict judgement) under z_deep slide / order (the G3-c4 window "
    "caches), read order qcount_first, the cap in windows as T7b (fast 4 / standard 10), tier RUN, t9 scorer (the gold is a substring of ONE word of a candidate).  "
    "`FLAT` rows: every window that holds a question unit is read as T10 reads a cross (`rep` = the first member of each growth is the start, `all` = every strictly "
    "stable member; search budget 512/64 unless the row says; both seats of a shared unit); a candidate = one entry = the word set of the path words + the "
    "centre of the adopted states of one window (the per-axis answers of slide_ratios are only labels).  `S1 per-axis` rows are the G3-e2 runs with answer shape "
    "path (the best earlier shape).  Gold in a candidate = some candidate has the gold in one of its words; single right / wrong = exactly one candidate "
    "(does / does not); list = >= 2.")
out()
out("## intra2 (fulllead, n = 69)")
out()
out("| system | n | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | words per entry median / max | first-gold pos median | windows read median / max | s/question median (max) |")
out("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
ids_ref = ids_of(bank, "intra2")
for nm in NAMES:
    d = SYS[nm]
    ids = [i for i in ids_ref if i in d]
    if not ids:
        continue
    cnt = defaultdict(int); sizes = []; wsz = []; wpe = []; pos = []; secs = []; wr = []
    for i in ids:
        c, n, p = grade(d[i]); cnt[c] += 1
        if n >= 2:
            sizes.append(n); wsz.append(sum(len(cc[1]) for cc in d[i]["cands"]))
        wpe.extend(len(cc[1]) for cc in d[i]["cands"])
        if p: pos.append(p)
        if d[i]["secs"] is not None: secs.append(d[i]["secs"])
        if "rec" in d[i]:
            wr.append(d[i]["rec"]["read"]["windows_read"])
    g = cnt["single_right"] + cnt["list_gold"]
    out("| %s | %d | %s | %d | %d | %d | %d | %d | %s / %s | %s / %s | %s / %s | %s | %s | %s (%s) |" % (
        nm, len(ids), pct(g, len(ids)), cnt["single_right"], cnt["single_wrong"], cnt["list_gold"], cnt["list_nogold"], cnt["none"],
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
SUB = os.path.join(RES, "all_subset_ids.txt")
if os.path.exists(SUB) and "FLAT all z=slide fast (subset)" in SYS:
    ids_sub = set(open(SUB).read().strip().split(","))
    done_sub = set(SYS["FLAT all z=slide fast (subset)"]) & ids_sub
    out("## members=all against the representative, on the questions members=all was run for (z slide, fast; %d of the 94 questions: the ones whose windows read at fast hold <= 700 starts together, results/all_subset_ids.txt; %d of them finished)" % (len(ids_sub), len(done_sub)))
    out()
    out("| system | intra2 n | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | entries in the lists (sum) | unans n | abstained | list | single wrong |")
    out("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for nm in ("FLAT rep z=slide fast", "FLAT all z=slide fast (subset)", "FLAT rep z=slide fast, evidence window", "FLAT all z=slide fast, evidence window (subset)",
               "S1 per-axis z=slide two_if_single_edge path", "T10 flat-fast RUN tier only", "T10 flat-fast (3 tiers)", "T10 layers-ssp-fast", "B1-mecab", "B2-mecab"):
        if nm not in SYS:
            continue
        d = SYS[nm]
        ii = [i for i in ids_of(d, "intra2") if i in done_sub]; uu = [i for i in ids_of(d, "unans") if i in done_sub]
        cnt = defaultdict(int); ents = 0
        for i in ii:
            c, n, _ = grade(d[i]); cnt[c] += 1; ents += n
        uc = defaultdict(int)
        for i in uu:
            c, n, _ = grade(d[i]); uc[c] += 1
        out("| %s | %d | %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d |" % (nm, len(ii), pct(cnt["single_right"] + cnt["list_gold"], len(ii)), cnt["single_right"], cnt["single_wrong"],
                                                                                  cnt["list_gold"], cnt["list_nogold"], cnt["none"], ents, len(uu), uc["none"], uc["list"], uc["single"]))
    out()
out("## Where the flat questions end (FLAT rows; both kinds): the verdicts of the answerable questions, and the outcome of every start settled (summed over the windows read)")
out()
tk = ["candidate", "none:ratio_disagreement", "none:section_disagreement", "none:points_nowhere", "none:ungrounded", "ambiguous", "no_fixed_point",
      "unstable_axis_improvable", "no_question_unit"]
out("| system | verdicts (intra2) | questions with an entry | partial questions | questions that read nothing | windows read: 0 / 1-3 / 4+ | starts settled (windows read, summed) | " + " | ".join(tk) + " |")
out("|---|---|---|---|---|---|---|" + "---|" * len(tk))
for nm in FLN:
    d = SYS[nm]
    ids = ids_of(d, "intra2")
    vs = Counter(d[i]["rec"]["verdict"].replace("UNKNOWN_", "U_") for i in ids)
    part = sum(1 for i in ids if d[i]["rec"]["read"]["partial"])
    zero = sum(1 for i in ids if d[i]["rec"]["read"]["windows_read"] == 0 and d[i]["rec"]["read"]["candidate_windows"] > 0)
    wr = Counter(0 if d[i]["rec"]["read"]["windows_read"] == 0 else 4 if d[i]["rec"]["read"]["windows_read"] >= 4 else 2 for i in ids)
    tal = Counter(); starts = 0
    for i in list(d):
        for w in d[i]["rec"]["windows"]:
            starts += w["starts"]
            for k, v in w["tally"].items():
                tal[k] += v
    out("| %s | %s | %d | %d | %d | %d / %d / %d | %d | " % (nm, ", ".join("%s %d" % kv for kv in sorted(vs.items())), sum(1 for i in ids if d[i]["rec"]["entries"]),
                                                              part, zero, wr[0], wr[2], wr[4], starts) + " | ".join(str(tal.get(k, 0)) for k in tk) + " |")
out()
out("## The labels: per entry, how many axes of the placed members agree (slide_ratios, agreement three) -- labels only, nothing is decided by them")
out()
out("| system | entries (intra2 + unans) | entries with >= 1 axis agreed on some member | x agreed | y agreed | z agreed | entries holding the gold | ... of those with >= 1 axis agreed |")
out("|---|---|---|---|---|---|---|---|")
for nm in FLN:
    d = SYS[nm]
    ne = na = ax = ay = az = ng = ngl = 0
    for i, r in d.items():
        for e in r["rec"]["entries"]:
            ne += 1
            lab = e.get("axes") or {}
            anyl = any(v[0] > 0 for v in lab.values())
            na += anyl
            ax += bool(lab.get("x", [0])[0]); ay += bool(lab.get("y", [0])[0]); az += bool(lab.get("z", [0])[0])
            if r["kind"] == "intra2" and S.hits_words(r["gold"], e["words"]):
                ng += 1; ngl += anyl
    out("| %s | %d | %d | %d | %d | %d | %d | %d |" % (nm, ne, na, ax, ay, az, ng, ngl))
out()
out("## Trace (FLAT rows, windows with an entry): the trace of every path word holds (trace_ok), and how many path words rest on an edge that only a CONSTRUCTED pair sentence evidences (evidence window)")
out()
out("| system | windows with an entry | trace ok | path words with an edge evidenced only by a constructed pair sentence (summed over windows) |")
out("|---|---|---|---|")
for nm in FLN:
    d = SYS[nm]
    seen = {}
    for i, r in d.items():
        for e in r["rec"]["entries"]:
            seen[(i, e["window"])] = e
    tot = sum(1 for _ in seen)
    out("| %s | %d | %d | %d |" % (nm, tot, sum(1 for e in seen.values() if e["trace_ok"]), sum(e.get("constructed_edge_words", 0) for e in seen.values())))
out()
out("## Time (FLAT rows): seconds per question, and the starts per window")
out()
out("| system | questions | s/question median / p90 / max | CPU s total | windows read | starts per window median / max |")
out("|---|---|---|---|---|---|")
for nm in FLN:
    d = SYS[nm]
    secs = sorted(r["secs"] for r in d.values())
    ws = [w["starts"] for r in d.values() for w in r["rec"]["windows"]]
    out("| %s | %d | %s / %s / %s | %.0f | %d | %s / %s |" % (nm, len(secs), f1(med(secs)), f1(secs[int(len(secs) * 0.9)] if secs else None), f1(secs[-1] if secs else None),
                                                           sum(secs), len(ws), f1(med(ws)), max(ws) if ws else "-"))
out()
out("## Per-question overlap with T10 (review): which of the 69 intra2 golds each side finds (A = the window row, B = the T10 row)")
out()


def gold_ids(nm):
    d = SYS[nm]
    return {i for i in ids_of(bank, "intra2") if i in d and grade(d[i])[0] in ("single_right", "list_gold")}


T10N = [n for n in ("T10 flat-fast RUN tier only", "T10 flat-fast (3 tiers)", "T10 layers-ssp-fast", "T10 flat-standard RUN tier only",
                    "T10 flat-standard (3 tiers)", "T10 layers-ssp-standard") if n in SYS]
WINN = [n for n in ("FLAT rep z=slide fast", "FLAT rep z=slide standard", "FLAT rep z=slide fast, evidence window", "FLAT rep z=order fast, evidence window",
                    "FLAT rep z=slide standard, evidence window", "FLAT rep z=order standard, evidence window") if n in SYS]
out("| window row (A) | T10 row (B) | A | B | A only | both | B only | union |")
out("|---|---|---|---|---|---|---|---|")
for a in WINN:
    for b in T10N:
        A_, B_ = gold_ids(a), gold_ids(b)
        out("| %s | %s | %d | %d | %d | %d | %d | %d |" % (a, b, len(A_), len(B_), len(A_ - B_), len(A_ & B_), len(B_ - A_), len(A_ | B_)))
out()
if WINN and T10N:
    allw = set().union(*(gold_ids(a) for a in WINN))
    allt = set().union(*(gold_ids(b) for b in T10N))
    out("All six window rows together: %d golds; all six T10 rows together: %d; union %d; found by a window row and by no T10 row: %d (%s); "
        "found by a T10 row and by no window row: %d." % (len(allw), len(allt), len(allw | allt), len(allw - allt), " ".join(sorted(allw - allt)), len(allt - allw)))
    out()
nt = os.path.join(RES, "notes_flat.md")
if os.path.exists(nt):
    for l in open(nt, encoding="utf-8").read().splitlines():
        out(l)
open(os.path.join(RES, "summary_flat.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
