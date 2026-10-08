"""T10 summary: the t9 tables for the new placement sweep, with the t9 rows of the same configs and B1/B2 alongside.
usage: summarize.py [RESULTS_DIR=results] [T9_RESULTS_DIR=../t9/results]   -> RESULTS_DIR/summary.md (+ prints)
Inputs: RESULTS_DIR/ask_<corpus>_<preset>_<tag>.jsonl (written by measure_ask.py; the system label's tag is read from the records:
gi-oc, e.g. ordered-stop), and, for every (corpus, preset) found there, T9_RESULTS_DIR/ask_<corpus>_<preset>.jsonl (the t9 whole-group
baseline sweep, label tag "t9 whole").  Grading, tables and baselines are t9/summarize.py's (scorer.py, ../bank2/baselines.py);
tables whose corpus has no T10 data are left out.  Needs fugashi (MeCab): the Pro vera-wiring env or the Air python3.11."""
import glob, json, os, statistics, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "t9")); sys.path.insert(0, os.path.join(HERE, "..", "bank2"))
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402

RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results")
T9RES = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "t9", "results")
TIERS = ("RUN", "WORD", "CHAR")
BANK = os.path.join(HERE, "..", "bank2", "bank2.tsv")
bank = {}
for l in open(BANK, encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = dict(zip(BL.FIELDS, l.rstrip("\n").split("\t")))
    bank[r["id"]] = r
HARD = ["I2-011", "I2-014", "I2-029", "I2-031", "I2-033", "I2-039", "R2-I003", "R2-I006", "R2-I013"]
L = []


def out(s=""):
    L.append(s); print(s)


def med(x): return statistics.median(x) if x else None
def mean(x): return statistics.mean(x) if x else None
def f1(x): return "-" if x is None else "%.1f" % x
def f2(x): return "-" if x is None else "%.2f" % x


# ---------- load systems: label -> {id: rec} ----------
SYS = {}; ORDER = []; META = {}
ERRORS = []
T9TAG = "t9 whole"


def label(cfg, pre, tag):
    return "%s-%s [%s]" % (cfg, pre, tag)


def add(name, rec):
    if name not in SYS:
        SYS[name] = {}; ORDER.append(name)
    SYS[name][rec["id"]] = rec


def load_ask(path, tag_of):
    n = 0
    for l in open(path, encoding="utf-8"):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if "error" in r:
            ERRORS.append((os.path.basename(path), r["id"], r["error"].strip().splitlines()[-1]))
            continue
        pre = r["preset"]; tag = tag_of(r); n += 1
        flat = [("L0", 0, e["words"]) for t in TIERS if t in r["layer0"] for e in r["layer0"][t]["entries"]]
        base = dict(id=r["id"], gold=r["gold"], kind=r["kind"], corpus=r["corpus"], tag=tag, pre=pre, ms0=r["ms_layer0"] / 1000,
                    load1=r.get("load1"), verdict0=r.get("verdict0"))
        add(label("flat", pre, tag), dict(base, cands=flat, secs=r["ms_layer0"] / 1000, extra=None, trace_ok=None, cfg="flat"))
        for cfg, nm in (("path", "layers-path"), ("seatsPath", "layers-ssp")):
            if cfg not in r["on"]:
                continue
            up, ok = [], True
            for t, d in r["on"][cfg]["tiers"].items():
                for run in d["runs"]:
                    up += [(t, run["k"], e["words"]) for e in run["entries"]]
                    ok = ok and bool(run["trace_ok"])
            add(label(nm, pre, tag), dict(base, cands=flat + up, secs=(r["ms_layer0"] + r["on"][cfg]["ms"]) / 1000, extra=r["on"][cfg]["ms"] / 1000,
                                         trace_ok=ok, cfg=nm, first=(r.get("layer_order") or [None])[0],
                                         triggered=any(d["triggered"] for d in r["on"][cfg]["tiers"].values())))
    return n


T10_FILES = sorted(glob.glob(os.path.join(RES, "ask_*.jsonl")))
PRESETS, CORPORA, T10TAGS = [], [], []
for p in T10_FILES:
    tag_seen = []
    load_ask(p, lambda r: (tag_seen.append("%s-%s%s" % (r["gi"], r["oc"], "" if r.get("order", "forward") == "forward" else "-" + r["order"])) or tag_seen[-1]))
    base = os.path.basename(p)[:-6].split("_")
    corpus, pre = base[1], base[2]
    META[p] = tag_seen[0] if tag_seen else "?"
    if corpus not in CORPORA: CORPORA.append(corpus)
    if pre not in PRESETS: PRESETS.append(pre)
    for t in tag_seen[:1]:
        if t not in T10TAGS: T10TAGS.append(t)
for p in T10_FILES:
    base = os.path.basename(p)[:-6].split("_")
    t9p = os.path.join(T9RES, "ask_%s_%s.jsonl" % (base[1], base[2]))
    if os.path.exists(t9p):
        load_ask(t9p, lambda r: T9TAG)
PRESETS.sort(key=lambda p: ({"fast": 0, "standard": 1, "full": 2}.get(p, 3), p))
CFGS = ("flat", "layers-path", "layers-ssp")
ORDER = [label(c, p, t) for p in PRESETS for c in CFGS for t in sorted(T10TAGS) + [T9TAG] if label(c, p, t) in SYS]

# ---------- baselines ----------
units = BL.load()
toks = BL.make_tokenizers()
index = {c: {(t, i): k for k, (t, i, _) in enumerate(u)} for c, u in units.items()}
titles = sorted({t for t, _, _ in units["s3000"] if len(t) >= 2}, key=len, reverse=True)
BASE = {}
for tn, tok in toks.items():
    for nm in ("B1", "B2"):
        BASE["%s-%s" % (nm, tn)] = {}
    for qid, r in bank.items():
        if r["corpus"] not in CORPORA:
            continue
        u = units[r["corpus"]]
        best, c1 = BL.b1(u, tok(r["question"]))
        c2 = BL.b2(u, c1, r["corpus"], index[r["corpus"]], titles)
        for nm, cs in (("B1", c1), ("B2", c2)):
            BASE["%s-%s" % (nm, tn)][qid] = dict(id=qid, gold=r["gold"], kind=r["kind"], corpus=r["corpus"], secs=None, trace_ok=None,
                                                 cands=[("S", 0, [u[k][2]]) for k in cs], text=True)
BNAMES = list(BASE)


def hit(rec, cand):
    return S.hits_words(rec["gold"], cand[2])


def grade(rec):
    """-> (category, size, first_gold_pos)"""
    cs = rec["cands"]
    h = [n for n, c in enumerate(cs, 1) if hit(rec, c)]
    n = len(cs)
    if rec["kind"] == "unans":
        return ("none" if n == 0 else "single" if n == 1 else "list"), n, None
    if n == 0:
        return "none", 0, None
    if n == 1:
        return ("single_right" if h else "single_wrong"), 1, (1 if h else None)
    return ("list_gold" if h else "list_nogold"), n, (h[0] if h else None)


def gold_hit(rec): return grade(rec)[0] in ("single_right", "list_gold")
def kind_ids(sysd, kind): return sorted(i for i in sysd if sysd[i]["kind"] == kind)


NAMES = ORDER + BNAMES
ALL = dict(SYS); ALL.update(BASE)
CORPUS_KIND = [("intra2", "fulllead"), ("cross2", "s3000")]

out("# T10 -- bank2 under the new initial placement (ordered group insertion), measured on Vera line 3, with the t9 rows and keyword baselines")
out()
out("Systems: `flat-P [tag]` = layers off (ask, 3 tiers, preset P); `layers-path-P [tag]` = layers on, default path candidates; `layers-ssp-P [tag]` = layers on, stable-seats-path; tag `%s` = the T10 placement (group_insert-on_collapse; `ordered-stop` = tied share-groups inserted one member at a time in sentence word order, growth stops just before the member that breaks the budget, L-460..L-463); tag `%s` = the T9 sweep with the whole-group insertion (L-72), copied from t9/results/summary.md's configs (same questions, same scorer; recomputed here from t9's raw per-question records, so the numbers equal t9/results/summary.md). Placement cache = the complete ordered cache of fulllead_sents (level mid); presets fast / standard; layers variant A, compress, no feedback." % ("`, `".join(sorted(T10TAGS)) or "?", T9TAG))
out()
out("Grading (as t9): `scorer.py` (NFKC, casefold, no spaces / thousands commas / middle dots, 万 and kanji digits to ASCII; gold alternative a substring of ONE word of an entry; for B1/B2 a candidate is one sentence). 'Gold in a candidate' = any candidate holds the gold. Single right / wrong = exactly one candidate holds / does not hold the gold; list = >= 2 candidates; none = no candidate. List size = number of candidates (entries over the 3 tiers + upper-layer entries). B1/B2 = baselines.py with MeCab ('-mecab') and character bigrams ('-bigram').")
out()
out("Times: wall seconds per question inside a worker, several workers at once on one shared machine (the sweep's argv and cache are in results/*.meta.json; the 1-min load at each question's finish is in the time table), so times include heavy contention (load 20-40 with 10 workers on 10 cores). The t9 times come from another machine and load (4 workers, load 5-15). Times of the two sweeps are NOT comparable; they only show the order of magnitude. In T10 the layers configs run on top of ONE layer-0 read; the first config run (`ssp`) and the second (`path`) each build their own layer-1 crosses (measured: the second config is NOT warm, its extra is about 0.5-1x the first's), so `layers-X` seconds = layer 0 + that config's own layers time. Tower build time is not included.")
out()
if ERRORS:
    out("**Questions that raised an error (not in the tables):** " + "; ".join("%s %s: %s" % e for e in ERRORS))
    out()

for kind, corpus in CORPUS_KIND:
    if corpus not in CORPORA:
        continue
    ids_ref = sorted(i for i, r in bank.items() if r["kind"] == kind)
    out("## %s (%s, n = %d)" % (kind, corpus, len(ids_ref)))
    out()
    out("| system | n run | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max (lists) | first-gold pos median / max | s/question median (max) | trace ok |")
    out("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for nm in NAMES:
        d = ALL[nm]
        ids = [i for i in ids_ref if i in d]
        if not ids:
            continue
        cnt = defaultdict(int); sizes = []; pos = []; secs = []; tr = []
        for i in ids:
            c, n, p = grade(d[i]); cnt[c] += 1
            if n >= 2: sizes.append(n)
            if p: pos.append(p)
            if d[i]["secs"] is not None: secs.append(d[i]["secs"])
            if d[i]["trace_ok"] is not None: tr.append(d[i]["trace_ok"])
        g = cnt["single_right"] + cnt["list_gold"]
        out("| %s | %d | %d (%.0f%%) | %d | %d | %d | %d | %d | %s / %s | %s / %s | %s (%s) | %s |" % (
            nm, len(ids), g, 100 * g / len(ids), cnt["single_right"], cnt["single_wrong"], cnt["list_gold"], cnt["list_nogold"], cnt["none"],
            f1(med(sizes)), max(sizes) if sizes else "-", f1(med(pos)), max(pos) if pos else "-",
            f2(med(secs)), f2(max(secs)) if secs else "-", ("%d/%d" % (sum(tr), len(tr))) if tr else "n/a"))
    out()

out("## unans (fulllead%s): can a user reject what is shown?" % (", s3000" if "s3000" in CORPORA else ""))
out()
out("Correct behaviour = abstain. B1/B2 never abstain (candidates for every question). 'list only' = rejectable by a user; 'single answer' = confident wrong.")
out()
out("| system | corpus | n run | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size median / max |")
out("|---|---|---|---|---|---|---|")
for nm in NAMES:
    d = ALL[nm]
    for corpus in CORPORA:
        ids = [i for i in d if d[i]["kind"] == "unans" and d[i]["corpus"] == corpus]
        if not ids:
            continue
        cnt = defaultdict(int); sizes = []
        for i in ids:
            c, n, _ = grade(d[i]); cnt[c] += 1
            if n >= 2: sizes.append(n)
        out("| %s | %s | %d | %d | %d | %d | %s / %s |" % (nm, corpus, len(ids), cnt["none"], cnt["list"], cnt["single"], f1(med(sizes)), max(sizes) if sizes else "-"))
out()


def mark(rec):
    if rec is None: return "."
    c, n, p = grade(rec)
    return {"single_right": "S", "list_gold": "L%d" % n, "single_wrong": "w", "list_nogold": "x%d" % n, "none": "-"}[c]


def item_table(title, ids):
    out(title)
    out()
    out("Cell: S = single answer holds gold; Ln = list of n holds gold; w = single answer without gold; xn = list of n without gold; - = no candidate; . = not run. B1/B2 cells: S/Ln as for a sentence list (n = number of sentences).")
    out()
    cols = [n for n in NAMES if any(i in ALL[n] for i in ids)]
    out("| item | gold | " + " | ".join(cols) + " |")
    out("|---|---|" + "---|" * len(cols))
    for i in ids:
        out("| %s | %s | " % (i, bank[i]["gold"]) + " | ".join(mark(ALL[n].get(i)) for n in cols) + " |")
    out()


if "s3000" in CORPORA:
    item_table("## cross2, per item (n = 9, s3000; report per item, not a rate)", sorted(i for i, r in bank.items() if r["kind"] == "cross2"))
item_table("## The 9 B2-hard items (missed by B2 with both tokenizers), per system", HARD)

out("## System vs B2 (MeCab), answerable questions: overlap of 'gold in a candidate'")
out()
out("both = system and B2 hit; system only; B2 only; neither. Per kind. (Last column: system hits that B2-bigram also misses = gold neither B2 holds.)")
out()
out("| system | kind | n | both | system only | B2 only | neither | system-only ids | system hit, both B2 tokenizers miss |")
out("|---|---|---|---|---|---|---|---|---|")
b2m, b2b = BASE["B2-mecab"], BASE["B2-bigram"]
for nm in ORDER + ["B1-mecab"]:
    d = ALL[nm]
    for kind in ("intra2", "cross2"):
        ids = [i for i in kind_ids(d, kind) if i in b2m]
        if not ids:
            continue
        sh = {i: gold_hit(d[i]) for i in ids}
        bh = {i: gold_hit(b2m[i]) for i in ids}
        bbh = {i: gold_hit(b2b[i]) for i in ids}
        both = [i for i in ids if sh[i] and bh[i]]; so = [i for i in ids if sh[i] and not bh[i]]
        bo = [i for i in ids if bh[i] and not sh[i]]; ne = [i for i in ids if not sh[i] and not bh[i]]
        nb = [i for i in ids if sh[i] and not bh[i] and not bbh[i]]
        out("| %s | %s | %d | %d | %d | %d | %d | %s | %s |" % (nm, kind, len(ids), len(both), len(so), len(bo), len(ne), ",".join(so) or "-", ",".join(nb) or "-"))
out()

out("## T10 vs t9, same config: which answerable questions changed 'gold in a candidate'")
out()
out("gained = hit under T10, no hit in t9; lost = hit in t9, none under T10.")
out()
out("| config | kind | n | t9 hits | T10 hits | gained | lost | gained ids | lost ids |")
out("|---|---|---|---|---|---|---|---|---|")
for p in PRESETS:
    for c in CFGS:
        for t in sorted(T10TAGS):
            a, b = label(c, p, t), label(c, p, T9TAG)
            if a not in SYS or b not in SYS:
                continue
            for kind in ("intra2", "cross2"):
                ids = [i for i in kind_ids(SYS[a], kind) if i in SYS[b]]
                if not ids:
                    continue
                ga = [i for i in ids if gold_hit(SYS[a][i]) and not gold_hit(SYS[b][i])]
                lo = [i for i in ids if gold_hit(SYS[b][i]) and not gold_hit(SYS[a][i])]
                out("| %s-%s [%s] | %s | %d | %d | %d | %d | %d | %s | %s |" % (c, p, t, kind, len(ids), sum(gold_hit(SYS[b][i]) for i in ids),
                    sum(gold_hit(SYS[a][i]) for i in ids), len(ga), len(lo), ",".join(ga) or "-", ",".join(lo) or "-"))
out()

out("## Time per question, T10 systems (wall seconds)")
out()
out("`layer 0` = A.ask (all 3 tiers); `layers extra` = ask_layered on top of that layer 0 (each layers config builds its own layer-1 crosses; they ran in the order of the record's `layer_order`: ssp, then path); `total` = layer 0 + extra. load = the 1-min load average of the machine when the question finished. All questions of the sweep (answerable and unans).")
out()
out("| system | n | layer 0 median / mean / max | layers extra median / mean / max | total median / mean / max | questions over 300 s total | load median / max |")
out("|---|---|---|---|---|---|---|")
for nm in ORDER:
    d = SYS[nm]
    if nm.endswith("[%s]" % T9TAG):
        continue
    rs = list(d.values())
    l0 = [r["ms0"] for r in rs]; ex = [r["extra"] for r in rs if r["extra"] is not None]; tt = [r["secs"] for r in rs]
    ld = [r["load1"] for r in rs if r["load1"] is not None]

    def tri(x): return ("%s / %s / %s" % (f1(med(x)), f1(mean(x)), f1(max(x)))) if x else "-"
    out("| %s | %d | %s | %s | %s | %d | %s / %s |" % (nm, len(rs), tri(l0), tri(ex), tri(tt), sum(1 for x in tt if x > 300), f1(med(ld)), f1(max(ld)) if ld else "-"))
out()

out("## Layer-0 verdicts of the flat T10 systems")
out()
vs = sorted({r.get("verdict0") for nm in ORDER if nm.startswith("flat-") and not nm.endswith("[%s]" % T9TAG) for r in SYS[nm].values()}, key=str)
out("| system | kind | " + " | ".join(str(v) for v in vs) + " |")
out("|---|---|" + "---|" * len(vs))
for nm in ORDER:
    if not nm.startswith("flat-") or nm.endswith("[%s]" % T9TAG):
        continue
    for kind in ("intra2", "unans"):
        rs = [r for r in SYS[nm].values() if r["kind"] == kind]
        out("| %s | %s | " % (nm, kind) + " | ".join(str(sum(1 for r in rs if r.get("verdict0") == v)) for v in vs) + " |")
out()

out("## Normalisation effect")
out()
out("Items where a system's gold hit exists only after normalisation (verbatim words do not hold the gold):")
out()
chg = defaultdict(set)
for nm in ORDER:
    for i, rec in SYS[nm].items():
        if rec["kind"] == "unans": continue
        nv = any(S.verbatim_words(rec["gold"], c[2]) for c in rec["cands"])
        nn = any(hit(rec, c) for c in rec["cands"])
        if nn and not nv: chg[nm].add(i)
for nm in ORDER:
    out("- %s: %s" % (nm, ", ".join(sorted(chg[nm])) or "none"))
out()
out("## Diagnostic: looser rule (gold inside the concatenation of ALL words of one entry), answerable questions")
out()
out("Not the headline rule (the concatenation of a word set is not text of the corpus); shown to see whether the word-level rule hides hits for multi-word golds.")
out()
out("| system | intra2 word-level -> joined | cross2 word-level -> joined |")
out("|---|---|---|")
for nm in ORDER:
    cells = []
    for kind in ("intra2", "cross2"):
        ids = kind_ids(SYS[nm], kind)
        a = sum(any(hit(SYS[nm][i], c) for c in SYS[nm][i]["cands"]) for i in ids)
        b = sum(any(S.hits_text(SYS[nm][i]["gold"], "".join(c[2])) for c in SYS[nm][i]["cands"]) for i in ids)
        cells.append("%d -> %d (of %d)" % (a, b, len(ids)) if ids else "-")
    out("| %s | %s |" % (nm, " | ".join(cells)))
out()
os.makedirs(RES, exist_ok=True)
open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
