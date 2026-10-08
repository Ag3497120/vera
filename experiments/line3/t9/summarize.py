"""T9 summary: all systems + B1/B2 on bank2.  usage: summarize.py [RESULTS_DIR=results]  -> results/summary.md (+ prints)
Inputs: results/ask_<corpus>_<preset>.jsonl (flat + layers path + layers stable-seats-path), results/carry_<corpus>_<po>_<path|index>_<preset>.jsonl.
Grading: scorer.py (normalised oracle rule: gold in a word of an entry); B1/B2 candidate = a sentence, same normalisation."""
import glob, json, os, statistics, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "bank2"))
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402

RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results")
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
def f1(x): return "-" if x is None else "%.1f" % x
def f2(x): return "-" if x is None else "%.2f" % x


# ---------- load systems: name -> {id: rec(cands, secs, trace_ok)} ----------
SYS = {}    # name -> {id: dict}
ORDER = []


def add(name, rec):
    if name not in SYS:
        SYS[name] = {}; ORDER.append(name)
    SYS[name][rec["id"]] = rec


for p in sorted(glob.glob(os.path.join(RES, "ask_*.jsonl"))):
    for l in open(p, encoding="utf-8"):
        r = json.loads(l); pre = r["preset"]
        flat = [("L0", 0, e["words"]) for t in TIERS if t in r["layer0"] for e in r["layer0"][t]["entries"]]
        base = dict(id=r["id"], gold=r["gold"], kind=r["kind"], corpus=r["corpus"])
        add("flat-%s" % pre, dict(base, cands=flat, secs=r["ms_layer0"] / 1000, trace_ok=None))
        for cfg, nm in (("path", "layers-path"), ("seatsPath", "layers-ssp")):
            up, ok = [], True
            for t, d in r["on"][cfg]["tiers"].items():
                for run in d["runs"]:
                    up += [(t, run["k"], e["words"]) for e in run["entries"]]
                    ok = ok and bool(run["trace_ok"])
            add("%s-%s" % (nm, pre), dict(base, cands=flat + up, secs=(r["ms_layer0"] + r["on"][cfg]["ms"]) / 1000, trace_ok=ok,
                                         triggered=any(d["triggered"] for d in r["on"][cfg]["tiers"].values())))
for p in sorted(glob.glob(os.path.join(RES, "carry_*.jsonl"))):
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        nm = "carry-%s-%s-%s" % (r["po"], "index" if r["fallback"] == "index" else "path", r["preset"])
        add(nm, dict(id=r["id"], gold=r["gold"], kind=r["kind"], corpus=r["corpus"], cands=[("C", 0, e["words"]) for e in r["entries"]],
                     secs=r["ms"] / 1000, trace_ok=bool(r["trace"]["ok"]), verdict=r["verdict"]))
ORDER.sort(key=lambda n: (n.split("-")[0] != "flat", n.split("-")[0] != "layers", n))

# ---------- baselines ----------
units = BL.load()
toks = BL.make_tokenizers()
index = {c: {(t, i): k for k, (t, i, _) in enumerate(u)} for c, u in units.items()}
titles = sorted({t for t, _, _ in units["s3000"] if len(t) >= 2}, key=len, reverse=True)
BASE = {}   # name -> {id: dict}
for tn, tok in toks.items():
    for nm in ("B1", "B2"):
        BASE["%s-%s" % (nm, tn)] = {}
    for qid, r in bank.items():
        u = units[r["corpus"]]
        best, c1 = BL.b1(u, tok(r["question"]))
        c2 = BL.b2(u, c1, r["corpus"], index[r["corpus"]], titles)
        for nm, cs in (("B1", c1), ("B2", c2)):
            BASE["%s-%s" % (nm, tn)][qid] = dict(id=qid, gold=r["gold"], kind=r["kind"], corpus=r["corpus"], secs=None, trace_ok=None,
                                                 cands=[("S", 0, [u[k][2]]) for k in cs], text=True)


def hit(rec, cand):
    w = cand[2]
    return S.hits_words(rec["gold"], w)


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


def kind_ids(sysd, kind):
    return sorted(i for i in sysd if sysd[i]["kind"] == kind)


NAMES = ORDER + [n for n in BASE]
ALL = dict(SYS); ALL.update(BASE)

out("# T9 -- bank2 (cross-sentence bank) measured on Vera line 3 systems, with keyword baselines")
out()
out("Grading: `scorer.py` (NFKC, casefold, no spaces / thousands commas / middle dots, 万 and kanji digits to ASCII; gold alternative a substring of ONE word of an entry; for B1/B2 a candidate is one sentence). 'Gold in a candidate' = any candidate holds the gold. Single right / wrong = exactly one candidate holds / does not hold the gold; list = >= 2 candidates; none = no candidate. List size = number of candidates (entries over the 3 tiers + upper-layer entries). Times are wall seconds per question inside a worker (several workers ran at once, so times include contention; tower build not included). B1/B2 = baselines.py with MeCab ('-mecab') and character bigrams ('-bigram').")
out()
out("Systems: `flat-P` = layers off (ask, 3 tiers, preset P); `layers-path-P` = layers on, default path candidates; `layers-ssp-P` = layers on, stable-seats-path; `carry-{close|defer}-{path|index}-P` = RUN low carry tower + carry_query, path descent (design) or index descent (fallback=index).")
out()

for corpus_kind in (("intra2", "fulllead"), ("cross2", "s3000")):
    kind, corpus = corpus_kind
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

out("## unans (n = 50: fulllead 25, s3000 25): can a user reject what is shown?")
out()
out("Correct behaviour = abstain. B1/B2 never abstain (candidates for every question). 'list only' = rejectable by a user; 'single answer' = confident wrong.")
out()
out("| system | corpus | n run | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size median / max |")
out("|---|---|---|---|---|---|---|")
for nm in NAMES:
    d = ALL[nm]
    for corpus in ("fulllead", "s3000"):
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


def item_table(title, ids, extra=None):
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


item_table("## cross2, per item (n = 9, s3000; report per item, not a rate)", sorted(i for i, r in bank.items() if r["kind"] == "cross2"))
item_table("## The 9 B2-hard items (missed by B2 with both tokenizers), per system", HARD)

out("## System vs B2 (MeCab), answerable questions: overlap of 'gold in a candidate'")
out()
out("both = system and B2 hit; system only; B2 only; neither. Per kind. (B2-bigram in the last column: system hits that B2-bigram also misses = gold neither B2 holds.)")
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
        sh = {i: grade(d[i])[0] in ("single_right", "list_gold") for i in ids}
        bh = {i: grade(b2m[i])[0] in ("single_right", "list_gold") for i in ids}
        bbh = {i: grade(b2b[i])[0] in ("single_right", "list_gold") for i in ids}
        both = [i for i in ids if sh[i] and bh[i]]; so = [i for i in ids if sh[i] and not bh[i]]
        bo = [i for i in ids if bh[i] and not sh[i]]; ne = [i for i in ids if not sh[i] and not bh[i]]
        nb = [i for i in ids if sh[i] and not bh[i] and not bbh[i]]
        out("| %s | %s | %d | %d | %d | %d | %d | %s | %s |" % (nm, kind, len(ids), len(both), len(so), len(bo), len(ne), ",".join(so) or "-", ",".join(nb) or "-"))
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
        cells.append("%d -> %d (of %d)" % (a, b, len(ids)))
    out("| %s | %s |" % (nm, " | ".join(cells)))
out()
open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
