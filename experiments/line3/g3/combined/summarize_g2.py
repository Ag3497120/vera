"""G3-g2 summary: the combined list WITHOUT merging across sources (merge="none", the default), in per-origin blocks, with the per-source typed
abstentions first, on bank2 fulllead (69 intra2 + 25 unans), fast and standard.

Same inputs as summarize_combined.py: the flat cross and the layers REPLAYED from T10's records (replay.py), the windows read LIVE by measure_windows.py
(records results/g2_win_{preset}_{plain,window}.jsonl, a re-run at the G3-g2 code state; results/win_*.jsonl are the G3-g ones).  Each list is the output of
verantyx.line3.combined.combine, the very combiner `ask(structure="combined")` uses, with merge="none" (and merge="word_set" for the comparison with G3-g).
Grading: t9's scorer for 'gold in a candidate'; single / list / none follow the combined VERDICT.

usage: summarize_g2.py [RESULTS_DIR=results] [WIN_PREFIX=g2_win_]  -> RESULTS_DIR/summary_g2.md (+ prints).  Needs the Pro vera-wiring env."""
import dataclasses, json, os, statistics, subprocess, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
L3 = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(L3))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(L3, "t9")); sys.path.insert(0, os.path.join(L3, "bank2"))
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402
from verantyx.line3 import combined as CB   # noqa: E402
sys.path.insert(0, HERE)
from replay import flat_src, layers_src, win_src   # noqa: E402

RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results")
WPRE = sys.argv[2] if len(sys.argv) > 2 else "g2_win_"
T10RES = os.path.join(L3, "t10", "results")
PRESETS = ("fast", "standard")
BANK = os.path.join(L3, "bank2", "bank2.tsv")
BLOCKS = ["flat/RUN", "flat/WORD", "flat/CHAR", "layers", "window/plain", "window/window-evidence"]
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
def jl(path): return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def head():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        return "?"


def hits(e, gold): return S.hits_words(gold, e.words)


def first_gold(c, gold):
    """(overall position, block, position inside the block) of the first entry holding the gold, 1-based; None if there is none."""
    seen = Counter()
    for i, e in enumerate(c.entries, 1):
        seen[e.block] += 1
        if hits(e, gold):
            return i, e.block, seen[e.block]
    return None


def gold_per_block(c, gold):
    """block -> position inside the block of its first entry holding the gold."""
    seen, res = Counter(), {}
    for e in c.entries:
        seen[e.block] += 1
        if hits(e, gold) and e.block not in res:
            res[e.block] = seen[e.block]
    return res


def grade(c, kind, gold):
    n = len(c.entries)
    if kind == "unans":
        return "none" if n == 0 else "single" if c.verdict == CB.ANSWER else "list"
    if n == 0:
        return "none"
    h = any(hits(e, gold) for e in c.entries)
    if c.verdict == CB.ANSWER:
        return "single_right" if h else "single_wrong"
    return "list_gold" if h else "list_nogold"


# ---------------------------------------------------------------------------------------------------------------------
T10, WIN = {}, {}
for P in PRESETS:
    T10[P] = {r["id"]: r for r in jl(os.path.join(T10RES, "ask_fulllead_%s_ordered-stop.jsonl" % P)) if "error" not in r}
    for ev in ("plain", "window"):
        WIN[(P, ev)] = {r["id"]: r for r in jl(os.path.join(RES, "%s%s_%s.jsonl" % (WPRE, P, ev))) if "error" not in r}
ids_all = sorted(i for i in bank if bank[i]["corpus"] == "fulllead")
ROWS = {}                                  # preset -> list of dict(id, kind, gold, none=CombinedAnswer, ws=CombinedAnswer, secs)
for P in PRESETS:
    rows = []
    for i in ids_all:
        if i not in T10[P] or any(i not in WIN[(P, ev)] for ev in ("plain", "window")):
            continue
        rec = T10[P][i]
        srcs = [flat_src(rec), layers_src(rec), win_src(WIN[(P, "plain")][i], "plain"), win_src(WIN[(P, "window")][i], "window")]
        q = bank[i]["question"]
        nost = [dataclasses.replace(x, cands=tuple(dataclasses.replace(c, stability=None) for c in x.cands)) for x in srcs]
        rows.append(dict(id=i, kind=bank[i]["kind"], gold=bank[i]["gold"], none=CB.combine(q, srcs), ws=CB.combine(q, srcs, merge="word_set"),
                         srcord=CB.combine(q, nost),
                         srcs=srcs, wsecs=(WIN[(P, "plain")][i]["ms"] / 1000, WIN[(P, "window")][i]["ms"] / 1000)))
    ROWS[P] = rows

out("# G3-g2 -- the combined list without merging across sources, per-origin blocks, typed abstentions first (bank2 fulllead)")
out()
out("Code state: line3 HEAD %s plus the uncommitted G3-g2 work (verantyx/line3/combined.py `merge`, `also_in`, `header`, `blocks`; cli.py `--merge`)." % head())
out()
out("Inputs: flat cross (3 tiers) and layers (stable-seats-path) REPLAYED from T10's raw records (as G3-g, no re-run); windows LIVE (`measure_windows.py`, representative members, evidence plain and window, z_deep slide, %d questions per preset read at the G3-g2 code state, records `results/%s*`). Lists: `combine(...)` with `merge=\"none\"` (the default; every candidate its own entry, blocks flat/RUN, flat/WORD, flat/CHAR, layers, window/plain, window/window-evidence, each block most stable first with the source's order breaking ties, L-749; a block whose candidates hold no stability stays in the source's order and is marked order=source: the layers replayed from T10), `merge=\"none\" in the source's order` (the L-743 arrangement before L-749, stability stripped from the sources) and `merge=\"word_set\"` (G3-g). Position = 1-based index in the whole list; within-block position = index among the entries of that block. List size = entries of the lists with >= 2 entries (intra2), as in G3-g." % (len(ROWS["fast"]), WPRE))
out()

# ---------------------------------------------------------------------------------------------------------------------
out("## Headline (intra2 n = 69, unans n = 25)")
out()
out("| merge | preset | gold in a candidate | single right / wrong | list with gold / without | none | list size median / max | first-gold position median / max (overall) | first-gold position median / max (within its block) | unans: abstained / list / single wrong |")
out("|---|---|---|---|---|---|---|---|---|---|")
for key, lab in (("none", "none, blocks by stability (G3-g2 default, L-749)"), ("srcord", "none, blocks in the source's order (before L-749)"),
                 ("ws", "word_set (G3-g, recomputed)")):
    for P in PRESETS:
        cnt = Counter(); sizes = []; pos = []; bpos = []; un = Counter()
        for r in ROWS[P]:
            c = r[key]
            g = grade(c, r["kind"], r["gold"])
            if r["kind"] == "unans":
                un[g] += 1
                continue
            cnt[g] += 1
            if len(c.entries) >= 2:
                sizes.append(len(c.entries))
            fg = first_gold(c, r["gold"])
            if fg:
                pos.append(fg[0]); bpos.append(fg[2])
        gold = cnt["single_right"] + cnt["list_gold"]
        out("| %s | %s | %d | %d / %d | %d / %d | %d | %s / %s | %s / %s | %s / %s | %d / %d / %d |" % (
            lab, P, gold, cnt["single_right"], cnt["single_wrong"], cnt["list_gold"], cnt["list_nogold"], cnt["none"],
            f1(med(sizes)), max(sizes) if sizes else "-", f1(med(pos)), max(pos) if pos else "-", f1(med(bpos)), max(bpos) if bpos else "-",
            un["none"], un["list"], un["single"]))
out()
out("Unans: a list of ONE window-only entry counts as a list; ANSWER (one entry some non-window origin gives) counts as single. The verdict rule is L-724 applied to the entries as listed.")
out()

# merge vs none: the verdict flips and sizes
out("## What not merging changes (word_set -> none)")
out()
out("| preset | kind | questions | entries word_set median / max | entries none median / max | questions whose verdict changes | of which ANSWER -> CHOICE | gold in a candidate word_set / none |")
out("|---|---|---|---|---|---|---|---|")
for P in PRESETS:
    for kind in ("intra2", "unans"):
        rs = [r for r in ROWS[P] if r["kind"] == kind]
        a = [len(r["ws"].entries) for r in rs if r["ws"].entries]; b = [len(r["none"].entries) for r in rs if r["none"].entries]
        ch = [r for r in rs if r["ws"].verdict != r["none"].verdict]
        af = [r for r in ch if r["ws"].verdict == CB.ANSWER and r["none"].verdict == CB.CHOICE]
        gw = sum(any(hits(e, r["gold"]) for e in r["ws"].entries) for r in rs); gn = sum(any(hits(e, r["gold"]) for e in r["none"].entries) for r in rs)
        out("| %s | %s | %d | %s / %s | %s / %s | %d (%s) | %d (%s) | %d / %d |" % (P, kind, len(rs), f1(med(a)), max(a) if a else "-", f1(med(b)), max(b) if b else "-",
            len(ch), ", ".join(r["id"] for r in ch) or "-", len(af), ", ".join(r["id"] for r in af) or "-", gw, gn))
out()

# ---------------------------------------------------------------------------------------------------------------------
out("## Blocks whose order changed (stability order against the source's order)")
out()
out("Per block and question that lists the block: the block's sequence under L-749 (stability, ties in the source's order) against the source's own sequence. `order=source` blocks (no stability recorded: the layers replayed from T10) are not sorted and cannot change. Counted over the 94 questions.")
out()
out("| preset | block | questions listing the block | block sorted by stability (order=stability) | order changed by the sort | block with a tie of equal stability | first entry changed |")
out("|---|---|---|---|---|---|---|")
for P in PRESETS:
    tot = Counter()
    for b in BLOCKS:
        n = ns = ch = ties = first = 0
        for r in ROWS[P]:
            a = [(e.words, e.origins[0]) for e in r["none"].entries if e.block == b]
            o = [(e.words, e.origins[0]) for e in r["srcord"].entries if e.block == b]
            if not a:
                continue
            n += 1
            bk = next(x for x in r["none"].blocks() if x["block"] == b)
            if bk["order"] == "stability":
                ns += 1
                st = [e.members[0].stability for e in r["none"].entries if e.block == b]
                if len(set(st)) < len(st):
                    ties += 1
            if a != o:
                ch += 1
                if a[0] != o[0]:
                    first += 1
        tot.update(n=n, ns=ns, ch=ch, ties=ties, first=first)
        out("| %s | %s | %d | %d | %d | %d | %d |" % (P, b, n, ns, ch, ties, first))
    out("| %s | all blocks | %d | %d | %d | %d | %d |" % (P, tot["n"], tot["ns"], tot["ch"], tot["ties"], tot["first"]))
out()

# ---------------------------------------------------------------------------------------------------------------------
out("## Where the first gold stands, per block (intra2, merge none)")
out()
out("'first gold in this block' = questions where some entry of the block holds the gold; position = index of the first such entry inside the block (the block's order: most stable first, ties in the source's order); block size = entries of the block in those questions. 'first gold of the whole list is in this block' = the block that holds the earliest gold entry of the list.")
out()
out("| preset | block | questions with the gold in the block | position in block median / max | block size median / max (those questions) | questions where the whole list's first gold is here | block lists something (of 69) | block lists something and holds no gold |")
out("|---|---|---|---|---|---|---|---|")
for P in PRESETS:
    rs = [r for r in ROWS[P] if r["kind"] == "intra2"]
    for b in BLOCKS:
        ps, sz, first_here, listed, nogold = [], [], 0, 0, 0
        for r in rs:
            c = r["none"]
            n = sum(1 for e in c.entries if e.block == b)
            if n:
                listed += 1
            gp = gold_per_block(c, r["gold"])
            if b in gp:
                ps.append(gp[b]); sz.append(n)
            elif n:
                nogold += 1
            fg = first_gold(c, r["gold"])
            if fg and fg[1] == b:
                first_here += 1
        out("| %s | %s | %d | %s / %s | %s / %s | %d | %d | %d |" % (P, b, len(ps), f1(med(ps)), max(ps) if ps else "-", f1(med(sz)), max(sz) if sz else "-", first_here, listed, nogold))
out()

# ---------------------------------------------------------------------------------------------------------------------
out("## The abstention header: how often each source lists and how often it abstains with which type (all 94 questions)")
out()
out("A cell is a number of questions (of 94 = 69 intra2 + 25 unans). `listed` = the source gave candidates; a type = the source gave none and the header says why (the tier's own verdict for flat/<tier>; the source's verdict for the layers and the windows). The last column counts questions where the source listed AND some part of it (a layer run, a window) abstained with the given types.")
out()
for P in PRESETS:
    rs = ROWS[P]
    out("**%s** (n = %d)" % (P, len(rs)))
    out()
    kinds = sorted({h["kind"] for r in rs for h in r["none"].header() if h["kind"]})
    out("| source | listed | " + " | ".join(kinds) + " | listed with part-abstentions (types: questions) |")
    out("|---|---|" + "---|" * (len(kinds) + 1))
    for b in BLOCKS:
        cnt = Counter(); part = Counter()
        for r in rs:
            h = next((x for x in r["none"].header() if x["source"] == b), None)
            if h is None:
                cnt["(not read)"] += 1
                continue
            cnt["listed" if h["listed"] else h["kind"]] += 1
            if h["listed"] and h["kinds"]:
                for k in h["kinds"]:
                    part[k] += 1
        out("| %s | %d | %s | %s |" % (b, cnt["listed"], " | ".join(str(cnt[k]) for k in kinds), ", ".join("%s: %d" % kv for kv in sorted(part.items())) or "-"))
    out()
    # by kind of question
    out("unans only (n = %d): sources that list something: %s" % (sum(1 for r in rs if r["kind"] == "unans"),
        "; ".join("%s %d" % (b, sum(1 for r in rs if r["kind"] == "unans" and any(x["source"] == b and x["listed"] for x in r["none"].header()))) for b in BLOCKS)))
    out()
    allabs = sum(1 for r in rs if all(h["listed"] == 0 for h in r["none"].header()))
    anyabs = sum(1 for r in rs if any(h["listed"] == 0 for h in r["none"].header()))
    allsix = sum(1 for r in rs if all(h["listed"] > 0 for h in r["none"].header()))
    out("Questions where every source abstains: %d; where at least one source abstains: %d; where every source lists: %d." % (allabs, anyabs, allsix))
    out()

# ---------------------------------------------------------------------------------------------------------------------
out("## `also_in`: the agreement mark between origins (merge none)")
out()
out("An entry with `also_in` has other origins that give the same word set (the mark only: nothing is summed, ranked or chosen by it). Counted over entries of the 94 questions.")
out()
out("| preset | entries | entries with also_in | word sets given by >= 2 origins | pairs of origins that agree (unordered, by word set) |")
out("|---|---|---|---|---|")
for P in PRESETS:
    ents = [(r, e) for r in ROWS[P] for e in r["none"].entries]
    marked = [x for x in ents if x[1].also_in]
    sets, pairs = set(), Counter()
    for r in ROWS[P]:
        by = defaultdict(set)
        for e in r["none"].entries:
            by[e.words].add(e.origins[0])
        for k, bs in by.items():
            if len(bs) > 1:
                sets.add((r["id"], k))
                bl = sorted(bs, key=CB.origin_key)
                for i in range(len(bl)):
                    for j in range(i + 1, len(bl)):
                        pairs[(bl[i], bl[j])] += 1
    out("| %s | %d | %d | %d | %s |" % (P, len(ents), len(marked), len(sets), "; ".join("%s + %s: %d" % (a, b, n) for (a, b), n in sorted(pairs.items(), key=lambda kv: (CB.origin_key(kv[0][0]), CB.origin_key(kv[0][1])))) or "-"))
out()
out("Word sets given by two or more windows of ONE origin (twin windows, no `also_in`, two entries each): %s." % "; ".join(
    "%s %d" % (P, sum(1 for r in ROWS[P] for k, n in Counter((e.words, e.origins[0]) for e in r["none"].entries if CB.family(e.origins[0]) == CB.WINDOW).items() if n > 1)) for P in PRESETS))
out()

# ---------------------------------------------------------------------------------------------------------------------
out("## Golds that only windows find (intra2): where they stand now")
out()
out("Found ONLY by windows = the gold is in no entry of the flat and layers blocks. Position in the whole list (list size), block of the first gold entry and position inside it; G3-g (word_set) position for comparison; and the position inside each window block.")
out()
out("| preset | item | first gold: overall (list size) | block, position inside | G3-g word_set position (list size) | window/plain: position inside / block size | window/window-evidence: position inside / block size |")
out("|---|---|---|---|---|---|---|")
for P in PRESETS:
    for r in ROWS[P]:
        if r["kind"] != "intra2":
            continue
        c = r["none"]
        if not any(hits(e, r["gold"]) for e in c.entries):
            continue
        if any(hits(e, r["gold"]) for e in c.entries if e.block in ("flat/RUN", "flat/WORD", "flat/CHAR", "layers")):
            continue
        fg = first_gold(c, r["gold"]); g2 = first_gold(r["ws"], r["gold"]); gp = gold_per_block(c, r["gold"])
        sz = Counter(e.block for e in c.entries)
        out("| %s | %s | %d (%d) | %s, %d | %d (%d) | %s | %s |" % (P, r["id"], fg[0], len(c.entries), fg[1], fg[2], g2[0], len(r["ws"].entries),
            ("%d / %d" % (gp["window/plain"], sz["window/plain"])) if "window/plain" in gp else "-",
            ("%d / %d" % (gp["window/window-evidence"], sz["window/window-evidence"])) if "window/window-evidence" in gp else "-"))
out()

# ---------------------------------------------------------------------------------------------------------------------
out("## Gold per block (intra2)")
out()
out("A block 'finds' a question when one of its entries holds the gold (the blocks are the owner's origins; layers = all layers/... origins).")
out()
out("| preset | " + " | ".join(BLOCKS) + " | any block |")
out("|---|" + "---|" * (len(BLOCKS) + 1))
for P in PRESETS:
    rs = [r for r in ROWS[P] if r["kind"] == "intra2"]
    cells = [sum(1 for r in rs if b in gold_per_block(r["none"], r["gold"])) for b in BLOCKS]
    out("| %s | %s | %d |" % (P, " | ".join(str(x) for x in cells), sum(1 for r in rs if gold_per_block(r["none"], r["gold"]))))
out()

# ---------------------------------------------------------------------------------------------------------------------
out("## Notes")
out()
out("* The candidates and their order are G3-g's; `merge=\"none\"` only stops joining equal word sets and groups the flat tiers in the fixed block order, so 'gold in a candidate' is the same as G3-g (checked in the first table: none, none in the source's order and word_set agree). The list is longer by the entries the merge had joined (mostly the two window variants giving the same word set).")
out("* Position is a property of the fixed block order, not a ranking: the user reads a block most stable first (ties in the source's order; the layers replayed from T10 carry no stability and stay in the source's order); nothing is ordered across blocks.")
open(os.path.join(RES, "summary_g2.md"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
