"""G3-g summary: the combined labelled candidate list on bank2 fulllead (69 intra2 + 25 unans), fast and standard.

The combined list is built by verantyx.line3.combined.combine (the very combiner `ask(structure="combined")` uses) from
  * the flat cross (3 tiers) and the layers (stable-seats-path) REPLAYED from T10's raw per-question records
    (../../t10/results/ask_fulllead_{fast,standard}_ordered-stop.jsonl; the same questions, the same ordered cache; the records hold words, centres,
    stability and counts only, so a replayed candidate has no source sentences and no per-word provenance), and
  * the windows read LIVE by measure_windows.py (evidence plain and window, representative members, G3-c3 default placements, z_deep slide), records in
    results/win_{fast,standard}_{plain,window}.jsonl.
Grading is t9's (scorer.py) for 'gold in a candidate'; the SINGLE / LIST / NONE columns of the COMBINED rows follow the combined VERDICT (owner decision 3:
a candidate only windows give is never a single answer): ANSWER = single, CHOICE (also a list of one) = list, no entry = none.  All other rows keep t9's
count rule (exactly one candidate = single), so they equal the published tables.

usage: summarize_combined.py [RESULTS_DIR=results]  -> RESULTS_DIR/summary.md (+ prints).  Needs fugashi (MeCab) for B1/B2 (the Pro vera-wiring env)."""
import json, os, statistics, subprocess, sys
from collections import defaultdict
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
L3 = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(L3))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(L3, "t9")); sys.path.insert(0, os.path.join(L3, "bank2"))
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402
from verantyx.line3 import combined as CB   # noqa: E402
sys.path.insert(0, HERE)
from replay import flat_src, layers_src, win_src, frac   # noqa: E402

RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results")
T10RES = os.path.join(L3, "t10", "results")
TIERS = ("RUN", "WORD", "CHAR")
PRESETS = ("fast", "standard")
BANK = os.path.join(L3, "bank2", "bank2.tsv")
HARD = ["I2-011", "I2-014", "I2-029", "I2-031", "I2-033", "I2-039", "R2-I003", "R2-I006", "R2-I013"]
ORIGINS = ["flat/RUN", "flat/WORD", "flat/CHAR", "layers", "window/plain", "window/window-evidence"]
bank = {}
for l in open(BANK, encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = dict(zip(BL.FIELDS, l.rstrip("\n").split("\t")))
    bank[r["id"]] = r
OUT = []


def out(s=""):
    OUT.append(s); print(s)


def med(x): return statistics.median(x) if x else None
def f1(x): return "-" if x is None else "%.1f" % x
def f2(x): return "-" if x is None else "%.2f" % x
def jl(path): return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def code_sha():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        return "?"


# ---------------------------------------------------------------------------------------------------------------------
# systems: label -> {id: row}; row = dict(kind, gold, entries=[(words, origins)], verdict, before, secs)
# ---------------------------------------------------------------------------------------------------------------------
def row_from_sources(rec_meta, srcs, rule):
    q = rec_meta["question"]
    c = CB.combine(q, srcs) if rule == "verdict" else None
    if c is not None:
        ents = [(e.words, set(e.origins)) for e in c.entries]
        verdict, before = c.verdict, c.listed_before_merge
    else:                                           # t9's count rule on the unmerged candidates of the sources, in the sources' order
        ents = [(cd.words, {cd.origin}) for s in sorted(srcs, key=lambda s: CB._source_rank(s.name)) for cd in s.cands]
        verdict, before = (CB.ANSWER if len(ents) == 1 else CB.CHOICE if ents else "NONE"), len(ents)
    return dict(id=rec_meta["id"], kind=rec_meta["kind"], gold=rec_meta["gold"], entries=ents, verdict=verdict, before=before, comb=c)


def grade(r):
    n = len(r["entries"])
    h = [i for i, (w, _o) in enumerate(r["entries"], 1) if S.hits_words(r["gold"], w)]
    if r["kind"] == "unans":
        return ("none" if n == 0 else "single" if r["verdict"] == CB.ANSWER else "list"), n, None
    if n == 0:
        return "none", 0, None
    if r["verdict"] == CB.ANSWER:
        return ("single_right" if h else "single_wrong"), n, (1 if h else None)
    return ("list_gold" if h else "list_nogold"), n, (h[0] if h else None)


def gold_hit(r): return grade(r)[0] in ("single_right", "list_gold")


def origin_hit(r, o):
    """some entry that holds the gold has this origin (o = a family label 'layers' covers every layers/..., 'flat' every flat/...)"""
    for w, os_ in r["entries"]:
        if S.hits_words(r["gold"], w) and any(x == o or (o == "layers" and x.startswith("layers/")) or (o in ("flat", "window") and x.startswith(o + "/"))
                                              for x in os_):
            return True
    return False


# ---------------------------------------------------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------------------------------------------------
T10, WIN, SECS, META = {}, {}, {}, {}
for P in PRESETS:
    p = os.path.join(T10RES, "ask_fulllead_%s_ordered-stop.jsonl" % P)
    T10[P] = {r["id"]: r for r in jl(p) if "error" not in r}
    META[("t10", P)] = json.load(open(p + ".meta.json"))
    for ev in ("plain", "window"):
        wp = os.path.join(RES, "win_%s_%s.jsonl" % (P, ev))
        WIN[(P, ev)] = {r["id"]: r for r in jl(wp) if "error" not in r}
        META[("win", P, ev)] = json.load(open(wp + ".meta.json"))
ids_all = sorted(i for i in bank if bank[i]["corpus"] == "fulllead")
HEAD = code_sha()

SYS, ORDER = {}, []


def add(name, rows):
    SYS[name] = rows
    ORDER.append(name)


for P in PRESETS:
    flat, ssp, wpl, wev = {}, {}, {}, {}
    fl_only, fl_lay = {}, {}
    cb_pl, cb_ev, cb_both = {}, {}, {}
    w_both = {}
    for i in ids_all:
        if i not in T10[P] or any(i not in WIN[(P, ev)] for ev in ("plain", "window")):
            continue
        rec = T10[P][i]
        meta = dict(id=i, kind=bank[i]["kind"], gold=bank[i]["gold"], question=bank[i]["question"])
        f_s, l_s = flat_src(rec), layers_src(rec)
        wp_s, we_s = win_src(WIN[(P, "plain")][i], "plain"), win_src(WIN[(P, "window")][i], "window")
        secs_t10_flat = rec["ms_layer0"] / 1000
        secs_layers = rec["on"]["seatsPath"]["ms"] / 1000
        secs_pl, secs_ev = WIN[(P, "plain")][i]["ms"] / 1000, WIN[(P, "window")][i]["ms"] / 1000
        # rows
        r = row_from_sources(meta, [f_s], "count"); r["secs"] = secs_t10_flat; flat[i] = r
        r = row_from_sources(meta, [f_s, l_s], "count"); r["secs"] = secs_t10_flat + secs_layers; ssp[i] = r
        r = row_from_sources(meta, [wp_s], "count"); r["secs"] = secs_pl; wpl[i] = r
        r = row_from_sources(meta, [we_s], "count"); r["secs"] = secs_ev; wev[i] = r
        r = row_from_sources(meta, [f_s, l_s], "verdict"); r["secs"] = secs_t10_flat + secs_layers; fl_lay[i] = r
        r = row_from_sources(meta, [wp_s, we_s], "verdict"); r["secs"] = secs_pl + secs_ev; w_both[i] = r
        r = row_from_sources(meta, [f_s, l_s, wp_s], "verdict"); r["secs"] = secs_t10_flat + secs_layers + secs_pl; cb_pl[i] = r
        r = row_from_sources(meta, [f_s, l_s, we_s], "verdict"); r["secs"] = secs_t10_flat + secs_layers + secs_ev; cb_ev[i] = r
        r = row_from_sources(meta, [f_s, l_s, wp_s, we_s], "verdict"); r["secs"] = secs_t10_flat + secs_layers + secs_pl + secs_ev; cb_both[i] = r
        r["win_secs"] = (secs_pl, secs_ev); r["t10_secs"] = (secs_t10_flat, secs_layers)
    add("T10 flat-%s (3 tiers, T10 replayed)" % P, flat)
    add("T10 layers-ssp-%s (flat + layers, T10 replayed)" % P, ssp)
    add("windows alone plain-%s (live)" % P, wpl)
    add("windows alone window-evidence-%s (live)" % P, wev)
    add("flat + layers, merged by word set, verdict rule (%s)" % P, fl_lay)
    add("windows alone, both variants merged, verdict rule (%s)" % P, w_both)
    add("COMBINED plain-%s (flat + layers + window/plain)" % P, cb_pl)
    add("COMBINED window-evidence-%s (flat + layers + window/window-evidence)" % P, cb_ev)
    add("COMBINED both-%s (flat + layers + both window variants)" % P, cb_both)

# baselines (as T10's summarize)
units = BL.load()
toks = BL.make_tokenizers()
index = {c: {(t, i): k for k, (t, i, _) in enumerate(u)} for c, u in units.items()}
titles = sorted({t for t, _, _ in units["s3000"] if len(t) >= 2}, key=len, reverse=True)
BNAMES = []
for tn, tok in toks.items():
    for nm in ("B1", "B2"):
        BNAMES.append("%s-%s" % (nm, tn))
        SYS[BNAMES[-1]] = {}
    for qid, r in bank.items():
        if r["corpus"] != "fulllead":
            continue
        u = units["fulllead"]
        best, c1 = BL.b1(u, tok(r["question"]))
        c2 = BL.b2(u, c1, "fulllead", index["fulllead"], titles)
        for nm, cs in (("B1", c1), ("B2", c2)):
            ents = [([u[k][2]], {"sentence"}) for k in cs]
            SYS["%s-%s" % (nm, tn)][qid] = dict(id=qid, kind=r["kind"], gold=r["gold"], entries=ents, verdict=(CB.ANSWER if len(ents) == 1 else CB.CHOICE),
                                                before=len(ents), secs=None)
ORDER += BNAMES


def ids_of(d, kind): return sorted(i for i in d if d[i]["kind"] == kind)


def words_in_list(r): return sum(len(w) for w, _o in r["entries"])


# ---------------------------------------------------------------------------------------------------------------------
out("# G3-g -- the combined labelled candidate list (flat cross + layers + windows), bank2 fulllead")
out()
out("Code state: line3 HEAD %s plus the uncommitted G3-g work (verantyx/line3/combined.py, ask.py / cli.py hooks, slide_flat.py `word_sources`). The combiner is `verantyx.line3.combined.combine`, the one `ask(structure=\"combined\")` calls." % HEAD)
out()
out("## What is replayed and what is live")
out()
out("* **Flat cross (3 tiers) and layers (stable-seats-path) are REPLAYED records**, not re-run: T10's raw per-question records (`experiments/line3/t10/results/ask_fulllead_{fast,standard}_ordered-stop.jsonl`), same 94 questions, same ordered placement cache (`/Users/motonisihikoudai/Projects/vera-impl/cache/f1b`, group_insert ordered, order forward, on_collapse stop), layers variant A / compress / no feedback. T10's code sha: `%s` (fast) and `%s` (standard) (T10 `head` = line3 be92351 + the F1c work in progress of that moment, run from `t10_snapshot`; the flat / layers code path has not changed since: tests/line3/test_ask*.py and test_matryoshka.py are the goldens, and `equiv_check.py` re-ran the live `ask_combined` flat + layers parts on cheap questions and compared them with the records, results below). Their raw times (load 20-40, 10 workers) are T10's. A replayed candidate holds the words, centres, stability and counts T10 recorded: **no source sentences and no per-word provenance, no P-4 trace flag for the flat part** (the layers' run trace flag is recorded and used)." % (META[("t10", "fast")]["head"], META[("t10", "standard")]["head"]))
out("* **Windows are LIVE**: `measure_windows.py`, slide_flat.ask_flat, members representative, evidence plain and window, z_deep slide (the G3-c3 default placements, window cache `slidewin_725d5ac1a8d2_RUN_3df141b12327_07db87511ff1.pkl` in the scratch caches), the windows' own search budget (512 / 64), `effort` fast = 4 windows, standard = 10 windows; 6 workers; the 1-min load at the questions' end was 2.9-8.6 (median 6.1), the goldens ran on the same machine at the same time. Window records carry the per-word sentences (`word_sources`).")
out("* The combined row is the combiner's output on those sources, so everything that is not 'gold in a candidate' (single / list / none) follows the **combined verdict** (windows alone never a single answer); all other rows keep t9's count rule (exactly one candidate = single), so they equal the published tables (T10 flat / ssp rows are checked against `t10/results/summary.md` and the window rows against `g3/s1flat/results/summary_flat.md` below).")
out("* Order of the list: flat (RUN, WORD, CHAR), layers (tier, layer), window/plain, window/window-evidence; equal word sets are one entry placed at its first candidate. T10's own tables list the layers' tiers alphabetically (the records were written with sorted keys); the replay uses the live order RUN, WORD, CHAR.")
out()

# ---------------------------------------------------------------------------------------------------------------------
def main_table(P):
    return [n for n in ORDER if (("-%s " % P) in n or n.endswith("(%s)" % P))]


for P in PRESETS:
    names = main_table(P) + BNAMES if P == "fast" else main_table(P)
    out("## intra2 (fulllead, n = 69), %s" % P)
    out()
    out("Single / list columns: rows named COMBINED, 'flat + layers, merged' and 'windows alone, both variants merged' follow the combined VERDICT (a list of one entry that only windows give is a LIST); the other rows are t9's count rule. List size = entries of the shown lists (>= 2 entries; COMBINED rows: also the number of entries before the merge). 'words' = words in the list.")
    out()
    out("| system | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max | entries before merge median / max | words in list median / max | first-gold pos median / max | s/question median (max) |")
    out("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for nm in names:
        d = SYS[nm]
        ids = [i for i in ids_of(d, "intra2")]
        if not ids:
            continue
        cnt = defaultdict(int); sizes = []; before = []; wl = []; pos = []; secs = []
        for i in ids:
            c, n, p = grade(d[i]); cnt[c] += 1
            if n >= 2: sizes.append(n); before.append(d[i]["before"]); wl.append(words_in_list(d[i]))
            if p: pos.append(p)
            if d[i]["secs"] is not None: secs.append(d[i]["secs"])
        g = cnt["single_right"] + cnt["list_gold"]
        out("| %s | %d (%.0f%%) | %d | %d | %d | %d | %d | %s / %s | %s / %s | %s / %s | %s / %s | %s (%s) |" % (
            nm, g, 100 * g / len(ids), cnt["single_right"], cnt["single_wrong"], cnt["list_gold"], cnt["list_nogold"], cnt["none"],
            f1(med(sizes)), max(sizes) if sizes else "-", f1(med(before)), max(before) if before else "-", f1(med(wl)), max(wl) if wl else "-",
            f1(med(pos)), max(pos) if pos else "-", f2(med(secs)), f2(max(secs)) if secs else "-"))
    out()
    out("### unans (fulllead, n = 25), %s: can a user reject what is shown?" % P)
    out()
    out("Correct behaviour = abstain. 'list' = rejectable by a user (for COMBINED rows a list of one window-only entry counts here); 'single answer' = confident wrong.")
    out()
    out("| system | no candidate (abstained) | list only (rejectable) | of which a list of ONE window-only entry | single answer (confident wrong) | list size median / max (lists) |")
    out("|---|---|---|---|---|---|")
    for nm in names:
        d = SYS[nm]
        ids = ids_of(d, "unans")
        if not ids:
            continue
        cnt = defaultdict(int); sizes = []; one_w = 0
        for i in ids:
            c, n, _ = grade(d[i]); cnt[c] += 1
            if n >= 2: sizes.append(n)
            if c == "list" and n == 1 and all(x.startswith("window/") for x in d[i]["entries"][0][1]): one_w += 1
        out("| %s | %d | %d | %d | %d | %s / %s |" % (nm, cnt["none"], cnt["list"], one_w, cnt["single"], f1(med(sizes)), max(sizes) if sizes else "-"))
    out()

# ---------------------------------------------------------------------------------------------------------------------
# checks against the published tables
# ---------------------------------------------------------------------------------------------------------------------
out("## Replay checks against the published tables")
out()
out("The replayed T10 rows and the live window rows, recomputed here, against the numbers printed in `t10/results/summary.md` and `g3/s1flat/results/summary_flat.md` (intra2 gold in a candidate / single wrong in unans).")
out()
PUB = {"fast": {"T10 flat": (16, 1), "T10 ssp": (21, 1), "windows plain": (9, None), "windows evidence": (19, None)},
       "standard": {"T10 flat": (19, None), "T10 ssp": (27, None), "windows plain": (10, None), "windows evidence": (21, None)}}
out("| row | preset | gold in a candidate here | published | single wrong in unans here |")
out("|---|---|---|---|---|")
for P in PRESETS:
    for lab, nm, pk in (("T10 flat", "T10 flat-%s (3 tiers, T10 replayed)" % P, "T10 flat"), ("T10 layers-ssp", "T10 layers-ssp-%s (flat + layers, T10 replayed)" % P, "T10 ssp"),
                       ("windows plain", "windows alone plain-%s (live)" % P, "windows plain"), ("windows window-evidence", "windows alone window-evidence-%s (live)" % P, "windows evidence")):
        d = SYS[nm]
        g = sum(gold_hit(d[i]) for i in ids_of(d, "intra2"))
        sw = sum(1 for i in ids_of(d, "unans") if grade(d[i])[0] == "single")
        out("| %s | %s | %d | %s | %d |" % (lab, P, g, PUB[P][pk][0], sw))
out()

# ---------------------------------------------------------------------------------------------------------------------
# per origin
# ---------------------------------------------------------------------------------------------------------------------
out("## Gold in a candidate, per origin (intra2, n = 69)")
out()
out("An origin 'finds' a question when some entry that holds the gold lists that origin (an entry with several origins counts for each). The combined-both list of the preset; flat/<tier> and layers/ are T10's replayed, window/ is live.")
out()
out("| preset | " + " | ".join(ORIGINS) + " | flat (any tier) | flat + layers | flat + layers + window/plain | all (combined both) | found ONLY by windows | found ONLY by flat + layers |")
out("|---|" + "---|" * (len(ORIGINS) + 6))
ONLYW = {}
for P in PRESETS:
    d = SYS["COMBINED both-%s (flat + layers + both window variants)" % P]
    ids = ids_of(d, "intra2")
    cells = [sum(origin_hit(d[i], o) for i in ids) for o in ORIGINS]
    fl = [i for i in ids if origin_hit(d[i], "flat")]
    fll = [i for i in ids if origin_hit(d[i], "flat") or origin_hit(d[i], "layers")]
    flp = [i for i in ids if i in fll or origin_hit(d[i], "window/plain")]
    allh = [i for i in ids if gold_hit(d[i])]
    onlyw = [i for i in ids if gold_hit(d[i]) and i not in fll]
    onlyf = [i for i in ids if i in fll and not (origin_hit(d[i], "window/plain") or origin_hit(d[i], "window/window-evidence"))]
    ONLYW[P] = (onlyw, onlyf)
    out("| %s | %s | %d | %d | %d | %d | %d (%s) | %d (%s) |" % (P, " | ".join(str(c) for c in cells), len(fl), len(fll), len(flp), len(allh),
                                                                len(onlyw), ", ".join(onlyw) or "-", len(onlyf), ", ".join(onlyf) or "-"))
out()

# the B2-hard items per origin
out("## The 9 B2-hard items, per origin (combined both)")
out()
out("Cell per origin: Y = some entry holding the gold lists that origin, . = no. Last columns: the combined verdict mark (S = single answer holds gold; Ln = list of n entries holds gold; w = single answer without gold; xn = list of n without gold; - = no candidate) and the position of the first entry holding the gold.")
out()
for P in PRESETS:
    d = SYS["COMBINED both-%s (flat + layers + both window variants)" % P]
    out("**%s**" % P)
    out()
    out("| item | gold | " + " | ".join(ORIGINS) + " | combined | first-gold pos |")
    out("|---|---|" + "---|" * (len(ORIGINS) + 2))
    for i in HARD:
        r = d.get(i)
        if r is None:
            continue
        c, n, p = grade(r)
        mark = {"single_right": "S", "list_gold": "L%d" % n, "single_wrong": "w", "list_nogold": "x%d" % n, "none": "-"}[c]
        out("| %s | %s | " % (i, bank[i]["gold"]) + " | ".join("Y" if origin_hit(r, o) else "." for o in ORIGINS) + " | %s | %s |" % (mark, p or "-"))
    out()
    bd = [i for i in HARD if i in d and gold_hit(d[i])]
    out("B2-hard items with the gold in some candidate: %d of 9 (%s); T10 layers-ssp %s: %d of 9; windows alone (plain / evidence): %d / %d."
        % (len(bd), ", ".join(bd) or "-", P, sum(gold_hit(SYS["T10 layers-ssp-%s (flat + layers, T10 replayed)" % P][i]) for i in HARD),
           sum(gold_hit(SYS["windows alone plain-%s (live)" % P][i]) for i in HARD), sum(gold_hit(SYS["windows alone window-evidence-%s (live)" % P][i]) for i in HARD)))
    out()

# ---------------------------------------------------------------------------------------------------------------------
# the merge and the verdicts
# ---------------------------------------------------------------------------------------------------------------------
out("## The merge and the verdicts (combined both)")
out()
out("| preset | kind | n | UNKNOWN (no entry) | ANSWER (one entry, a non-window origin) | of which holds the gold | CHOICE | of which one entry only windows give | entries before merge median / max | entries after merge median / max | entries with several origins | with origins in several families | ANSWER only because of the merge (>= 2 candidates, 1 entry) |")
out("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for P in PRESETS:
    d = SYS["COMBINED both-%s (flat + layers + both window variants)" % P]
    for kind in ("intra2", "unans"):
        ids = ids_of(d, kind)
        unk = [i for i in ids if not d[i]["entries"]]
        ans = [i for i in ids if d[i]["verdict"] == CB.ANSWER]
        ansg = [i for i in ans if S.hits_words(d[i]["gold"], d[i]["entries"][0][0])]
        ch = [i for i in ids if d[i]["verdict"] == CB.CHOICE and d[i]["entries"]]
        ch1w = [i for i in ch if len(d[i]["entries"]) == 1 and all(x.startswith("window/") for x in d[i]["entries"][0][1])]
        bef = [d[i]["before"] for i in ids if d[i]["entries"]]
        aft = [len(d[i]["entries"]) for i in ids if d[i]["entries"]]
        multi = sum(1 for i in ids for _w, os_ in d[i]["entries"] if len(os_) > 1)
        fams = sum(1 for i in ids for _w, os_ in d[i]["entries"] if len({x.split("/")[0] for x in os_}) > 1)
        ob = [i for i in ans if d[i]["before"] > 1]
        out("| %s | %s | %d | %d | %d | %d | %d | %d | %s / %s | %s / %s | %d | %d | %d (%s) |" % (P, kind, len(ids), len(unk), len(ans), len(ansg), len(ch), len(ch1w),
            f1(med(bef)), max(bef) if bef else "-", f1(med(aft)), max(aft) if aft else "-", multi, fams, len(ob), ", ".join(ob) or "-"))
out()

# the owner's decision 3, in numbers
out("## What decision 3 changes (a candidate only windows give is never a single answer)")
out()
out("Under the count rule (t9 / G3-f: exactly one candidate = a single answer) every window read that ended with one entry was a single answer; under the verdict rule a window-only entry is a list. The windows-alone rows (one evidence variant, entries never merged across windows) counted both ways, and the same count on the combined lists:")
out()
out("| preset | row | kind | single answers under the count rule (right / wrong) | single answers under the verdict rule |")
out("|---|---|---|---|---|")
for P in PRESETS:
    for nm in ("windows alone plain-%s (live)" % P, "windows alone window-evidence-%s (live)" % P, "COMBINED both-%s (flat + layers + both window variants)" % P):
        d = SYS[nm]
        for kind in ("intra2", "unans"):
            ids = ids_of(d, kind)
            one = [i for i in ids if len(d[i]["entries"]) == 1]
            right = [i for i in one if S.hits_words(d[i]["gold"], d[i]["entries"][0][0])]
            verd = [i for i in one if not all(x.startswith("window/") for x in d[i]["entries"][0][1])]
            out("| %s | %s | %s | %d (%d / %d) | %d |" % (P, nm.split(" (")[0], kind, len(one), len(right), len(one) - len(right), len(verd)))
out()

# where the windows' candidates stand in the combined list
out("## Where the windows' candidates stand in the combined list (combined both)")
out()
out("The list is flat, then layers, then windows (L-720); a gold that only windows find stands after the flat and layers entries. Position = first entry holding the gold; list = size of the combined list.")
out()
out("| preset | gold found only by windows | first-gold position in the combined list (list size) | first-gold position inside the windows' own entries |")
out("|---|---|---|---|")
for P in PRESETS:
    d = SYS["COMBINED both-%s (flat + layers + both window variants)" % P]
    wd = SYS["windows alone, both variants merged, verdict rule (%s)" % P]
    for i in ONLYW[P][0]:
        out("| %s | %s | %s (%d) | %s |" % (P, i, grade(d[i])[2], len(d[i]["entries"]), grade(wd[i])[2]))
out()

# times
out("## Time per question (wall seconds)")
out()
out("The flat + layers parts are T10's recorded times (10 workers, load 20-40, not comparable with a quiet machine); the window parts are this run's (6 workers, load 2.9-8.6, median 6.1). 'both variants' = the windows read twice (plain, then window evidence). The combined list is the union of all parts, so its cost is their sum.")
out()
out("| preset | flat layer 0 (T10) median / max | layers extra (T10) median / max | windows plain (live) median / max | windows window-evidence (live) median / max | windows both median / max | combined total median / max |")
out("|---|---|---|---|---|---|---|")
for P in PRESETS:
    d = SYS["COMBINED both-%s (flat + layers + both window variants)" % P]
    a = [d[i]["t10_secs"][0] for i in d]; b = [d[i]["t10_secs"][1] for i in d]
    c = [d[i]["win_secs"][0] for i in d]; e = [d[i]["win_secs"][1] for i in d]; w = [x + y for x, y in zip(c, e)]; t = [d[i]["secs"] for i in d]
    out("| %s | %s / %s | %s / %s | %s / %s | %s / %s | %s / %s | %s / %s |" % (P, f1(med(a)), f1(max(a)), f1(med(b)), f1(max(b)), f2(med(c)), f2(max(c)), f2(med(e)), f2(max(e)),
                                                                          f2(med(w)), f2(max(w)), f1(med(t)), f1(max(t))))
out()

# trace
out("## P-4 (trace)")
out()
out("| preset | window/plain entries | traced ok | window/window-evidence entries | traced ok | with a word whose edge only a constructed pair sentence evidences | layers runs with entries (T10) | trace ok |")
out("|---|---|---|---|---|---|---|---|")
for P in PRESETS:
    cnt = {}
    for ev in ("plain", "window"):
        es = [e for r in WIN[(P, ev)].values() for e in r["entries"]]
        cnt[ev] = (len(es), sum(1 for e in es if e["trace"]["ok"]), sum(1 for e in es if e["trace"]["constructed_edge_words"] > 0))
    runs = [run for r in T10[P].values() for t, dd in r["on"]["seatsPath"]["tiers"].items() for run in dd["runs"] if run["entries"]]
    out("| %s | %d | %d | %d | %d | %d | %d | %d |" % (P, cnt["plain"][0], cnt["plain"][1], cnt["window"][0], cnt["window"][1], cnt["window"][2], len(runs), sum(1 for x in runs if x["trace_ok"])))
out()

out("## Notes")
out()
out("* Same questions, same gold and the same scorer as T10 / G3-f; intra2 n = 69, unans n = 25; cross2 and s3000 were not run.")
out("* A combined list is long: it holds the union of the flat cross's 3 tiers (median 26 / 44 entries at fast / standard in T10), the layers' and the windows' entries; the merge only joins equal word sets. The table above gives the sizes.")
out("* The gold-in-a-candidate counts of the combined rows are unions of independently read sources and equal the union of what each origin finds; a larger union with a longer list is the trade the owner chose (candidates for users to grade).")
open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
