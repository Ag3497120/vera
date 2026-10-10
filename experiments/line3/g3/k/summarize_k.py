"""G3-k summary: the unknown-word stand-ins and the grammar read order in the combined list, grammar on vs off.

usage: summarize_k.py   (reads results/bank3_uwpa_fast_{on,off}.jsonl, results/bank2_fast_on.jsonl when present; writes results/summary.md and prints it)
Grading = t9's scorer (a gold alternative is a substring of ONE word of an entry); the entries of the block flat/assembled (G3-j) are display only and are left
out of every 'gold in a candidate' count.  Needs only the raw records, the banks and the T10 / G3-g / T11 records (no search is run)."""
import json, os, re, statistics, sys
from collections import Counter
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
L3 = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(L3, "t9"))
import scorer as S                                         # noqa: E402

RES = os.path.join(HERE, "results")
BANK3 = os.path.join(L3, "bank3", "bank3.tsv")
BANK2 = os.path.join(L3, "bank2", "bank2.tsv")
ASSEMBLED = "flat/assembled"
ORIGINS = ["flat/RUN", "flat/WORD", "flat/CHAR", "layers", "window/plain", "window/window-evidence"]
OUT = []


def out(s=""):
    OUT.append(s); print(s)


def med(x): return statistics.median(x) if x else None
def f1(x): return "-" if x is None else ("%.1f" % x)
def jl(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
def fr(n, d): return "%d/%d" % (n, d)


def load_bank(path):
    b = {}
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or not l.strip():
            continue
        r = dict(zip("id kind corpus subject question gold evidence notes audit".split(), l.rstrip("\n").split("\t")))
        b[r["id"]] = r
    return b


bank3, bank2 = load_bank(BANK3), load_bank(BANK2)


def recs(name):
    p = os.path.join(RES, name)
    return {r["id"]: r for r in jl(p) if "error" not in r} if os.path.exists(p) else {}


def ents(r):
    """the entries that count as candidates: not the assembled strings"""
    return [e for e in r["answer"]["entries"] if e["origins"] != [ASSEMBLED]]


def hit(gold, e): return S.hits_words(gold, e["words"])
def has_origin(e, o): return any(x == o or (o == "layers" and x.startswith("layers/")) for x in e["origins"])
def is_standin(e): return "via_standin" in e["marks"]
def is_read_standin(e): return "read_via_standin" in e["marks"]


def entry_class(e):
    """The mark class of one entry: via_standin (also read_via_standin) | read_via_standin (a cross / window that holds an original unit, read only through the tie-break) |
    layers (not marked per entry, by design) | neither (a flat / window entry whose crosses / windows the order alone also reads)."""
    if is_standin(e):
        return "via_standin"
    if is_read_standin(e):
        return "read_via_standin"
    if all(x.startswith("layers") for x in e["origins"]):
        return "layers (unmarked by design)"
    return "neither"


def gold_classes(r, bank):
    g = gold_of(r, bank)
    return [(",".join(e["origins"]), entry_class(e)) for e in ents(r) if hit(g, e)]


def gold_of(r, bank):
    g = bank[r["id"]]["gold"]
    return g.split("|", 1)[1] if r["kind"] == "summary-choice" else g


def first_gold(r, bank):
    g = gold_of(r, bank)
    for i, e in enumerate(ents(r), 1):
        if hit(g, e):
            return i
    return None


def has_gold(r, bank): return first_gold(r, bank) is not None
def origin_gold(r, bank, o): return any(hit(gold_of(r, bank), e) and has_origin(e, o) for e in ents(r))


def meta(name):
    p = os.path.join(RES, name + ".meta.json")
    p1 = os.path.join(RES, name.replace(".jsonl", ".run1.meta.json"))      # the off run was resumed once with nothing to do, which overwrote its meta: the first run's is kept
    if os.path.exists(p1):
        p = p1
    return json.load(open(p)) if os.path.exists(p) else {}


# ------------------------------------------------------------------------------------------------------------------------------------------
on3, off3 = recs("bank3_uwpa_fast_on.jsonl"), recs("bank3_uwpa_fast_off.jsonl")
oo3 = recs("bank3_uwpa_fast_on_order_only.jsonl")                      # grammar on, the stand-ins dropped from the intake: the ORDER alone (attribution)
t11 = {r["id"]: r for r in jl(os.path.join(L3, "t11", "results", "ask_fulllead_fast.jsonl")) if "error" not in r}
KINDS = ["unknown-word", "paraphrase"]
ids3 = sorted(i for i in on3 if i in off3)

out("# G3-k -- the unknown-word stand-ins and the grammar layer's read order in the combined list")
out()
mo, mf = meta("bank3_uwpa_fast_on.jsonl"), meta("bank3_uwpa_fast_off.jsonl")
if mo:
    out("Code: line3 HEAD `%s` + the uncommitted G3-k work; code sha256 of the changed modules (on run): %s." % (
        (mo.get("head") or "?")[:12], ", ".join("%s %s" % (k, v[:10]) for k, v in sorted(mo.get("code_sha256", {}).items()))))
    out("bank3 sweep: `%s`, started %s (on) / %s (off); python %s; PYTHONHASHSEED=%s; cache %s." % (
        mo["argv"][-1] if False else "measure_k.py fast ... --kinds unknown-word,paraphrase --workers 10", mo.get("started"), mf.get("started"), mo.get("python"),
        mo.get("pyhashseed"), mo.get("cache")))
    out()

# ---- 0. is the OFF path the committed one? ------------------------------------------------------------------------------------------------
out("## 0. The grammar-off run against the T11 records (same questions, same caches, fast)")
out()
same = diff = 0
diff_ids = []
for i in ids3:
    if i not in t11:
        continue
    a = [(tuple(e["origins"]), tuple(e["words"])) for e in ents(off3[i])]
    b = [(tuple(e["origins"]), tuple(e["words"])) for e in t11[i]["answer"]["entries"]]
    if a == b:
        same += 1
    else:
        diff += 1
        diff_ids.append(i)
out("The off run (this tree, HEAD + G3-k with `grammar=\"off\"`) and the T11 records (HEAD 2ef8531f, which is G3-i; before G3-j, so the assembled strings of G3-j are not in them and are left out here) give the same list (origins and words of every non-assembled entry, in order) for **%d of %d** questions%s." % (
    same, same + diff, "" if not diff else "; different: %s" % ", ".join(diff_ids)))
out()


leak = recs("bank3_uwpa_fast_on_layers_leak.jsonl")
if leak:
    out("Superseded first on run (`bank3_uwpa_fast_on_layers_leak.jsonl`, kept): the layers still carried the stand-ins up as question bundles (found at review, L-807; the layers' down-reads then read them as full query units): gold in a candidate unknown-word %d, paraphrase %d (gold lost against the off run: %s)." % (
        sum(1 for i in leak if bank3[i]["kind"] == "unknown-word" and has_gold(leak[i], bank3)), sum(1 for i in leak if bank3[i]["kind"] == "paraphrase" and has_gold(leak[i], bank3)),
        ", ".join(sorted(i.replace("b3_", "") for i in leak if i in off3 and has_gold(off3[i], bank3) and not has_gold(leak[i], bank3))) or "none"))
    out()
# ---- 1. headline ----------------------------------------------------------------------------------------------------------------------------
def kind_rows(kind):
    ids = [i for i in ids3 if bank3[i]["kind"] == kind]
    return ids


leak2 = recs("bank3_uwpa_fast_on_layer1_leak.jsonl")
if leak2:
    out("Superseded second on run (`bank3_uwpa_fast_on_layer1_leak.jsonl`, kept; 測定時に層の漏れあり, found at the second review, L-810): layer 1 was built from plan.read + ctx.query + the answer units, and ctx.query holds every stand-in, so every stand-in's cross became a layer-1 bundle whether or not it was read under the cap (up to 431). Gold in a candidate on that run: unknown-word %d, paraphrase %d; layers origin: unknown-word %d, paraphrase %d; questions whose gold list differs from the fixed run: %s." % (
        sum(1 for i in leak2 if bank3[i]["kind"] == "unknown-word" and has_gold(leak2[i], bank3)), sum(1 for i in leak2 if bank3[i]["kind"] == "paraphrase" and has_gold(leak2[i], bank3)),
        sum(1 for i in leak2 if bank3[i]["kind"] == "unknown-word" and origin_gold(leak2[i], bank3, "layers")), sum(1 for i in leak2 if bank3[i]["kind"] == "paraphrase" and origin_gold(leak2[i], bank3, "layers")),
        ", ".join(sorted(i.replace("b3_", "") for i in leak2 if i in on3 and has_gold(leak2[i], bank3) != has_gold(on3[i], bank3))) or "none"))
    out()
out("## 1. Gold in a candidate, grammar on vs off (bank3 fulllead, combined, fast; the t9 rule; the assembled strings do not count)")
out()
out("| kind | n | off: gold in a candidate | on: gold in a candidate | gold only on | gold only off | off: list size median / max | on: list size median / max | verdicts off / on (ANSWER) | flat/RUN gold off / on | flat/WORD | layers | window/plain | window/evidence |")
out("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for kind in KINDS:
    ids = kind_rows(kind)
    go = [i for i in ids if has_gold(on3[i], bank3)]
    gf = [i for i in ids if has_gold(off3[i], bank3)]
    only_on = sorted(set(go) - set(gf)); only_off = sorted(set(gf) - set(go))
    sz = lambda d: "%s / %s" % (f1(med([len(ents(d[i])) for i in ids])), max(len(ents(d[i])) for i in ids))
    ans = lambda d: sum(1 for i in ids if d[i]["verdict"] == "ANSWER")
    og = lambda d, o: sum(1 for i in ids if origin_gold(d[i], bank3, o))
    out("| %s | %d | %d | %d | %d (%s) | %d (%s) | %s | %s | %d / %d | %d / %d | %d / %d | %d / %d | %d / %d | %d / %d |" % (
        kind, len(ids), len(gf), len(go), len(only_on), " ".join(only_on), len(only_off), " ".join(only_off), sz(off3), sz(on3), ans(off3), ans(on3),
        og(off3, "flat/RUN"), og(on3, "flat/RUN"), og(off3, "flat/WORD"), og(on3, "flat/WORD"), og(off3, "layers"), og(on3, "layers"),
        og(off3, "window/plain"), og(on3, "window/plain"), og(off3, "window/window-evidence"), og(on3, "window/window-evidence")))
out()
out("(T11 published: unknown-word 6/18, paraphrase 3/20 for the off run at HEAD 2ef8531f.  B1 (keyword lookup, bank3/baselines.txt): unknown-word 16/18, paraphrase 8/20; B2 16/18, 12/20.)")
out()
tot_on = sum(1 for i in ids3 if has_gold(on3[i], bank3)); tot_off = sum(1 for i in ids3 if has_gold(off3[i], bank3))
out("All %d questions: gold in a candidate off %d, on %d." % (len(ids3), tot_off, tot_on))
out()
out("### 1b. What the new order does to the flat block under the fast cap (4 crosses per tier)")
out()
nrun = lambda d, i: sum(1 for e in ents(d[i]) if "flat/RUN" in e["origins"])
nw = lambda d, i, o: sum(1 for e in ents(d[i]) if o in e["origins"])
collapse = [i for i in ids3 if nrun(off3, i) >= 10 and nrun(on3, i) * 4 < nrun(off3, i)]
out("flat/RUN entries (all %d questions): off %d, on %d; questions where flat/RUN lists nothing: off %d, on %d; questions where flat/RUN falls to under a quarter (off >= 10 entries): **%d** (%s)." % (
    len(ids3), sum(nrun(off3, i) for i in ids3), sum(nrun(on3, i) for i in ids3), sum(1 for i in ids3 if nrun(off3, i) == 0), sum(1 for i in ids3 if nrun(on3, i) == 0),
    len(collapse), ", ".join("%s %d->%d" % (i.replace("b3_", ""), nrun(off3, i), nrun(on3, i)) for i in collapse)))
out("window entries (plain + evidence): off %d, on %d (questions listing: plain off %d / on %d, evidence off %d / on %d)." % (
    sum(nw(off3, i, "window/plain") + nw(off3, i, "window/window-evidence") for i in ids3), sum(nw(on3, i, "window/plain") + nw(on3, i, "window/window-evidence") for i in ids3),
    sum(1 for i in ids3 if nw(off3, i, "window/plain")), sum(1 for i in ids3 if nw(on3, i, "window/plain")),
    sum(1 for i in ids3 if nw(off3, i, "window/window-evidence")), sum(1 for i in ids3 if nw(on3, i, "window/window-evidence"))))
zero_st = [i for i in ids3 if sum(len(w["added"]) for w in on3[i]["answer"].get("standins", [])) == 0 and nrun(off3, i) >= 10 and nrun(on3, i) * 4 < nrun(off3, i)]
out("Of those, questions with NO stand-in unit added (the change is the order alone): %s." % (", ".join("%s %d->%d" % (i.replace("b3_", ""), nrun(off3, i), nrun(on3, i)) for i in zero_st) or "none"))
out()
if oo3:
    # L-811 (review fix 3): who made the flat/RUN block fall: the order alone (the order-only run) or the stand-ins on top of it
    both = [i for i in collapse if i in oo3]
    out("**Who made flat/RUN fall (the %d collapsed questions, read against the order-only run).** The fall is split in the part the ORDER ALONE makes (off -> order-only) and the part the stand-ins add on top (order-only -> on); a question is filed under the step that first took it under a quarter of its off entries." % len(both))
    out()
    out("| question | stand-in units added | flat/RUN off | order-only | on | fall by the order alone | fall by the stand-ins on top | under a quarter first at |")
    out("|---|---|---|---|---|---|---|---|")
    ord_alone, with_st = [], []
    for i in both:
        a_, o_, n_ = nrun(off3, i), nrun(oo3, i), nrun(on3, i)
        step = "the order alone" if o_ * 4 < a_ else "only once the stand-ins are added"
        (ord_alone if o_ * 4 < a_ else with_st).append(i)
        out("| %s | %d | %d | %d | %d | %d | %d | %s |" % (i.replace("b3_", ""), sum(len(w["added"]) for w in on3[i]["answer"].get("standins", [])), a_, o_, n_, a_ - o_, o_ - n_, step))
    out()
    out("* Under a quarter by the ORDER ALONE: %s.  Only once the stand-ins are added: %s.  A question whose fall is split (the order takes part of it, the stand-ins the rest) shows in both columns of the fall." % (
        ", ".join(i.replace("b3_", "") for i in ord_alone) or "none", ", ".join(i.replace("b3_", "") for i in with_st) or "none"))
    out()
if oo3:
    ids_oo = [i for i in ids3 if i in oo3]
    out("**Attribution (the order alone vs the order plus the stand-ins; %d questions with an order-only record).** `order-only` = grammar on with the stand-ins dropped from the intake (the read order of the crosses and of the windows, the form, the slot, the `grammar` row; no unit is added to any query)." % len(ids_oo))
    out()
    out("| kind | n | gold off | gold order-only | gold on (order + stand-ins) | gained by the order alone | gained by the stand-ins on top | lost by the order alone | lost by the stand-ins on top | flat/RUN entries off / order-only / on | window entries off / order-only / on |")
    out("|---|---|---|---|---|---|---|---|---|---|---|")
    for kind in KINDS:
        ids = [i for i in ids_oo if bank3[i]["kind"] == kind]
        G = lambda d: {i for i in ids if has_gold(d[i], bank3)}
        g0, g1, g2 = G(off3), G(oo3), G(on3)
        wn = lambda d: sum(nw(d, i, "window/plain") + nw(d, i, "window/window-evidence") for i in ids)
        out("| %s | %d | %d | %d | %d | %s | %s | %s | %s | %d / %d / %d | %d / %d / %d |" % (
            kind, len(ids), len(g0), len(g1), len(g2), " ".join(sorted(g1 - g0)) or "-", " ".join(sorted(g2 - g1)) or "-", " ".join(sorted(g0 - g1)) or "-", " ".join(sorted(g1 - g2)) or "-",
            sum(nrun(off3, i) for i in ids), sum(nrun(oo3, i) for i in ids), sum(nrun(on3, i) for i in ids), wn(off3), wn(oo3), wn(on3)))
    out()
    diffs = [i for i in ids_oo if [(tuple(e["origins"]), tuple(e["words"])) for e in ents(oo3[i])] != [(tuple(e["origins"]), tuple(e["words"])) for e in ents(on3[i])]]
    out("Questions whose list differs between order-only and on (i.e. the stand-ins changed something): %d of %d (%s)." % (len(diffs), len(ids_oo), " ".join(d.replace("b3_", "") for d in diffs)))
    out()

# ---- 2. where the stand-ins came in ----------------------------------------------------------------------------------------------------------
out("## 2. The stand-ins: how many, how many entries exist only through them, and whether the gold is in one")
out()
tbl = []
for i in ids3:
    a = on3[i]["answer"]
    st = a.get("standins", [])
    added = sum(len(w["added"]) for w in st)
    e_on = ents(on3[i])
    marked = [e for e in e_on if is_standin(e)]
    g = gold_of(on3[i], bank3)
    tbl.append((i, a["grammar_form"]["form"], a["grammar_form"]["slot"], st, added, len(e_on), len(marked), sum(1 for e in marked if hit(g, e)), a["header"][0]))
n_q_st = sum(1 for t in tbl if t[4] > 0)
out("Questions with at least one stand-in unit added: **%d of %d** (forms over all %d: %s)." % (
    n_q_st, len(tbl), len(tbl), ", ".join("%s %d" % kv for kv in sorted(Counter(t[1] for t in tbl).items()))))
sizes = sorted(t[4] for t in tbl if t[4] > 0)
if sizes:
    out("Stand-in units added per question (those with any): median %s, max %d, p90 %d." % (f1(med(sizes)), sizes[-1], sizes[(9 * len(sizes)) // 10]))
from verantyx.line3 import grammar as _GR
allw = [(i, w) for i in ids3 for w in on3[i]["answer"].get("standins", [])]
by_type = Counter(w["type"] for _i, w in allw)
out("Unknown content RUN words over the %d questions: %d (%s); stand-in units added per word: %s." % (
    len(ids3), len(allw), ", ".join("%s %d" % kv for kv in sorted(by_type.items())),
    "; ".join("%s median %s max %d" % (t, f1(med([len(w["added"]) for _i, w in allw if w["type"] == t and w["added"]])), max([len(w["added"]) for _i, w in allw if w["type"] == t] or [0])) for t in ("T2", "T3", "T4"))))
intw = [(i, w) for i, w in allw if any(q in w["word"] for q in _GR.INTERROG)]
out("Of them, words that CONTAIN an interrogative (何年, 何日, 何丁目, 最大何台, は何という ...: the thing asked, not an unknown subject; G1's 139 count them too): %d, with %d of the %d added stand-in units (e.g. the part 年 stands in 119 units)." % (
    len(intw), sum(len(w["added"]) for _i, w in intw), sum(len(w["added"]) for _i, w in allw)))
out()
tm = sum(t[6] for t in tbl)
out("Entries marked `via_standin` (flat + windows; the layers' entries are not marked per entry): **%d** of %d non-assembled entries over the %d questions; the gold is in one of them for **%d** questions." % (
    tm, sum(t[5] for t in tbl), len(tbl), sum(1 for t in tbl if t[7] > 0)))
rd_only = [e for i in ids3 for e in ents(on3[i]) if is_read_standin(e) and not is_standin(e)]
rd_q = [i for i in ids3 if any(is_read_standin(e) and not is_standin(e) for e in ents(on3[i]))]
rd_gold = [i for i in ids3 if any(is_read_standin(e) and not is_standin(e) and hit(gold_of(on3[i], bank3), e) for e in ents(on3[i]))]
out("Entries marked `read_via_standin` and NOT `via_standin` (they hold an original unit; their cross / window would not have been read under the cap by the same order without the stand-ins; L-810): **%d** entries in %d questions (flat/RUN %d, window %d); the gold is in one of them for **%d** questions (%s).  `via_standin` implies `read_via_standin` for crosses; %d of %d marked entries show both (a window entry can be `via_standin` through a member that holds only a stand-in in a window both orders read)." % (
    len(rd_only), len(rd_q), sum(1 for e in rd_only if "flat/RUN" in e["origins"]), sum(1 for e in rd_only if any(x.startswith("window/") for x in e["origins"])),
    len(rd_gold), " ".join(x.replace("b3_", "") for x in rd_gold) or "-", sum(1 for i in ids3 for e in ents(on3[i]) if is_standin(e) and is_read_standin(e)), tm))
out()

# ---- 2b. the gained golds and the marks ----------------------------------------------------------------------------------------------------
def gain_table(title, ids, d, base, bank, base_name):
    gained = [i for i in ids if has_gold(d[i], bank) and not has_gold(base[i], bank)]
    out("**%s** (gold in a candidate on, none %s): %d questions." % (title, base_name, len(gained)))
    out()
    out("| question | gold entries on: origin (mark class) |")
    out("|---|---|")
    for i in gained:
        out("| %s | %s |" % (i.replace("b3_", ""), "; ".join("%s (%s)" % x for x in gold_classes(d[i], bank))))
    out()
    cl = {i: {c for _o, c in gold_classes(d[i], bank)} for i in gained}
    n = lambda c: sum(1 for i in gained if c in cl[i])
    only = lambda c: sum(1 for i in gained if cl[i] == {c})
    marked_any = sum(1 for i in gained if cl[i] & {"via_standin", "read_via_standin"})
    out("By mark (a gold can sit in several entries; a question is counted once per class it has): with a `via_standin` gold entry %d; with a `read_via_standin` (not `via_standin`) gold entry %d; with a gold entry in the layers (unmarked by design) %d; with an unmarked flat / window gold entry (`neither`: reached through an order change among crosses / windows that the order alone also reads) %d.  Questions whose EVERY gold entry is of one class: via_standin %d, read_via_standin %d, layers %d, neither %d; questions with at least one marked gold entry %d of %d." % (
        n("via_standin"), n("read_via_standin"), n("layers (unmarked by design)"), n("neither"), only("via_standin"), only("read_via_standin"), only("layers (unmarked by design)"), only("neither"), marked_any, len(gained)))
    out()
    return gained


out("## 2b. Where the gained golds came from: the marks (L-810)")
out()
if oo3:
    ids_oo = [i for i in ids3 if i in oo3]
    gain_table("bank3, on against the ORDER ALONE", ids_oo, on3, oo3, bank3, "in the order-only run")
gain_table("bank3, on against off", ids3, on3, off3, bank3, "in the off run")

# ---- 2c. the exact diff of the read sets of the gained golds (gain_diff.py) ----------------------------------------------------------------------
gd_path = os.path.join(RES, "gain_diff.json")
if os.path.exists(gd_path):
    gd = json.load(open(gd_path, encoding="utf-8"))
    out("### 2c. The gained golds, diffed against the read sets of the order without the stand-ins (`gain_diff.py`, exact: the same ordering and cap with the stand-ins dropped from the intake)")
    out()
    out("| bank | question | against | gold entry (origin x count) -> path |")
    out("|---|---|---|---|")
    cnt = Counter()
    for r in gd:
        by = Counter((e["origin"], e.get("path", "?")) for e in r["entries"])
        for (o_, pth), n_ in sorted(by.items()):
            cnt[(r["bank"], r["baseline"], pth)] += 1
        out("| %s | %s | %s | %s |" % (r["bank"], r["id"].replace("b3_", ""), r["baseline"], "; ".join("%s x%d -> %s" % (o_, n_, pth) for (o_, pth), n_ in sorted(by.items()))))
    out()
    out("Counts of (question, origin, path) groups: " + "; ".join("%s vs %s: %s x%d" % (b_, bs, pth, n_) for (b_, bs, pth), n_ in sorted(cnt.items())) + ".")
    out()

# ---- 3. the chance control ------------------------------------------------------------------------------------------------------------------
out("## 3. The chance control (G1 3.2 / F2 L-492 form: another question's gold against this question's stand-in-derived candidates)")
out()
golds = {i: gold_of({"id": i, "kind": bank3[i]["kind"]}, bank3) for i in bank3 if bank3[i]["corpus"] == "fulllead" and bank3[i]["kind"] in ("two-facts", "paraphrase", "unknown-word") and bank3[i]["gold"]}
out("Pool of other golds: the %d fulllead bank3 items of kinds two-facts / paraphrase / unknown-word (gold alternatives as in the bank)." % len(golds))
out()
rows_ctl = []
tot_pairs = tot_hits = own_hit = own_n = 0
tot_pairs_u = tot_hits_u = own_hit_u = 0
for i in ids3:
    a = on3[i]["answer"]
    marked = [e for e in ents(on3[i]) if is_standin(e)]
    units = [u for w in a.get("standins", []) for u in w["added"]]
    cand_words = [w for e in marked for w in e["words"]]
    others = [j for j in golds if j != i]
    ch = sum(1 for j in others if S.hits_words(golds[j], cand_words)) if cand_words else 0
    chu = sum(1 for j in others if S.hits_words(golds[j], units)) if units else 0
    own = bool(cand_words) and S.hits_words(golds[i], cand_words)
    ownu = bool(units) and S.hits_words(golds[i], units)
    if cand_words:
        own_n += 1; own_hit += own; tot_pairs += len(others); tot_hits += ch
    if units:
        own_hit_u += ownu; tot_pairs_u += len(others); tot_hits_u += chu
    rows_ctl.append((i, len(units), len(marked), len(cand_words), own, ch, ownu, chu, len(others)))
n_units_q = sum(1 for r in rows_ctl if r[1] > 0)
out("* Candidates = the words of the entries marked `via_standin` (they exist only through a stand-in): questions with at least one: %d.  Own gold in them: **%d / %d**.  Other items' golds in them: **%s** of the pairs (%d questions x %d other golds), i.e. %s other golds per question on average." % (
    own_n, own_hit, own_n, fr(tot_hits, tot_pairs) if tot_pairs else "0/0", own_n, len(golds) - 1, ("%.2f" % (tot_hits / own_n)) if own_n else "-"))
own_list = []
for i in ids3:
    a = on3[i]["answer"]
    for w in a.get("standins", []):
        if any(S.hits_words(golds[i], [u]) for u in w["added"]):
            own_list.append((i.replace("b3_", ""), w["word"], [u for u in w["added"] if S.hits_words(golds[i], [u])][:2]))
out("* Where the gold is inside a stand-in unit: " + "; ".join("%s: %s -> %s" % x for x in own_list) + ".")
out("* Candidates = the stand-in units themselves (G1: 'granularity-derived, not evidence of the unknown word'): questions with at least one: %d.  Own gold inside a stand-in unit: **%d / %d**.  Other items' golds inside a stand-in unit: **%s** of the pairs, i.e. %s per question." % (
    n_units_q, own_hit_u, n_units_q, fr(tot_hits_u, tot_pairs_u) if tot_pairs_u else "0/0", ("%.2f" % (tot_hits_u / n_units_q)) if n_units_q else "-"))
# the whole list, off and on
wl_off = wl_on = 0
for i in ids3:
    others = [j for j in golds if j != i]
    for d, k in ((off3, "off"), (on3, "on")):
        ws = [w for e in ents(d[i]) for w in e["words"]]
        c = sum(1 for j in others if S.hits_words(golds[j], ws))
        if k == "off": wl_off += c
        else: wl_on += c
out("* The whole list (every non-assembled entry): other items' golds hit per question: off %s, on %s (sum over %d questions; the list is long, so this is the background rate that the gold of a question has to beat)." % (
    fr(wl_off, len(ids3)), fr(wl_on, len(ids3)), len(ids3)))
out()
out("Chance counts per unknown word (G1: the chance that a random RUN unit is a stand-in = stand-in units / RUN units of the corpus) are in the per-item table and in every answer (`standins[*].chance`).")
out()

# ---- 4. per item -----------------------------------------------------------------------------------------------------------------------------
for kind in KINDS:
    out("## 4. Per item: %s" % kind)
    out()
    out("| id | form (slot) | unknown words (type: stand-ins added / RUN units) | off: entries / gold (first pos) | on: entries / gold (first pos) | marked entries (gold in one) | flat/RUN off -> on | gold origins off | gold origins on | s off / on |")
    out("|---|---|---|---|---|---|---|---|---|---|")
    for i in kind_rows(kind):
        a = on3[i]["answer"]
        st = a.get("standins", [])
        uw = ", ".join("%s(%s: %d/%d)" % (w["word"], w["type"], len(w["added"]), w["pool"]) for w in st if w["type"] != "T1") or "-"
        fo, fn = first_gold(off3[i], bank3), first_gold(on3[i], bank3)
        mk = [e for e in ents(on3[i]) if is_standin(e)]
        g = gold_of(on3[i], bank3)
        runs = lambda d: sum(1 for e in ents(d[i]) if "flat/RUN" in e["origins"])
        og = lambda d: ",".join(o.replace("window/window-evidence", "w/ev").replace("window/plain", "w/pl").replace("flat/", "") for o in ORIGINS if origin_gold(d[i], bank3, o)) or "-"
        out("| %s | %s (%s) | %s | %d / %s | %d / %s | %d (%d) | %d -> %d | %s | %s | %.0f / %.0f |" % (
            i, a["grammar_form"]["form"], a["grammar_form"]["slot"] or "-", uw, len(ents(off3[i])), "yes (%d)" % fo if fo else "no", len(ents(on3[i])),
            "yes (%d)" % fn if fn else "no", len(mk), sum(1 for e in mk if hit(g, e)), runs(off3), runs(on3), og(off3), og(on3), off3[i]["ms"] / 1000, on3[i]["ms"] / 1000))
    out()

# ---- 5. time and partial ------------------------------------------------------------------------------------------------------------------
out("## 5. Time and the read")
out()
out("Seconds per question (10 workers, the machine shared with the test suites and the other sweep steps; load 4-17): off median %s max %s; on median %s max %s." % (
    f1(med([off3[i]["ms"] / 1000 for i in ids3])), f1(max(off3[i]["ms"] / 1000 for i in ids3)), f1(med([on3[i]["ms"] / 1000 for i in ids3])), f1(max(on3[i]["ms"] / 1000 for i in ids3))))
fl = lambda d, tier: sum(1 for i in ids3 if any(("flat/" + tier) in e["origins"] for e in ents(d[i])))
out("Questions whose flat tier lists something: RUN off %d / on %d; WORD off %d / on %d; CHAR off %d / on %d (of %d)." % (
    fl(off3, "RUN"), fl(on3, "RUN"), fl(off3, "WORD"), fl(on3, "WORD"), fl(off3, "CHAR"), fl(on3, "CHAR"), len(ids3)))
out()

# ---- 6. bank2 -----------------------------------------------------------------------------------------------------------------------------
on2 = recs("bank2_fast_on.jsonl")
if on2:
    sys.path.insert(0, os.path.join(L3, "g3", "combined"))
    t10 = {r["id"]: r for r in jl(os.path.join(L3, "t10", "results", "ask_fulllead_fast_ordered-stop.jsonl")) if "error" not in r}
    win = {ev: {r["id"]: r for r in jl(os.path.join(L3, "g3", "combined", "results", "win_fast_%s.jsonl" % ev)) if "error" not in r} for ev in ("plain", "window")}

    def base_sets(i):
        """T10 / G3-g off baseline per question: the words of the flat entries, the layers' entries and the window entries (both variants), recorded."""
        r = t10[i]
        flat = [e["words"] for t in ("RUN", "WORD", "CHAR") if t in r["layer0"] for e in r["layer0"][t]["entries"]]
        lay = [e["words"] for t in r["on"]["seatsPath"]["tiers"].values() for run in t["runs"] for e in run["entries"]]
        wins = [e["words"] for ev in ("plain", "window") if i in win[ev] for e in win[ev][i]["entries"]]
        return flat, lay, wins

    ids2 = sorted(i for i in on2 if i in t10)
    out("## 6. bank2 fulllead (intra2 69 + unans 25), combined fast, grammar on, against the off baselines")
    out()
    out("Baselines: (1) the recorded T10 flat + layers lists and the G3-g window lists (T10 flat 16, flat + layers 21, combined 29 of 69 at fast); their windows were read on the z_deep-slide placements while this tree reads the committed defaults (z_deep order, G3-i), so only the FLAT block (same ordered cache, equiv-checked: `equiv_off.txt` re-runs the off path on the cheapest questions against the T10 records) is strictly comparable with them; (2) the grammar-off run of THIS tree (same code, same window placements) when `bank2_fast_off.jsonl` is present, the clean comparison for the combined list.")
    out()
    intra = [i for i in ids2 if bank2[i]["kind"] == "intra2"]
    gold2 = lambda i: bank2[i]["gold"]
    off2 = recs("bank2_fast_off.jsonl")
    isflat = lambda x: x.startswith("flat/") and x != ASSEMBLED

    def sets_of(d, i):
        g = gold2(i)
        fl = any(hit(g, e) and any(isflat(x) for x in e["origins"]) for e in ents(d[i]))
        ly = any(hit(g, e) and any(x.startswith("layers/") for x in e["origins"]) for e in ents(d[i]))
        wi_ = any(hit(g, e) and any(x.startswith("window/") for x in e["origins"]) for e in ents(d[i]))
        return fl, fl or ly, fl or ly or wi_
    rec_flat = {i: any(S.hits_words(gold2(i), w) for w in base_sets(i)[0]) for i in intra}
    rec_fl = {i: any(S.hits_words(gold2(i), w) for w in base_sets(i)[0] + base_sets(i)[1]) for i in intra}
    rec_all = {i: any(S.hits_words(gold2(i), w) for w in sum(base_sets(i), [])) for i in intra}
    out("| system (intra2, n = 69) | flat block | flat + layers | combined (all blocks) |")
    out("|---|---|---|---|")
    out("| T10 / G3-g records (flat + layers T10, windows G3-g on z_deep slide) | %d | %d | %d |" % (sum(rec_flat.values()), sum(rec_fl.values()), sum(rec_all.values())))
    if off2:
        offs = {i: sets_of(off2, i) for i in intra if i in off2}
        out("| **grammar off, this tree, live** (n = %d) | %d | %d | %d |" % (len(offs), sum(v[0] for v in offs.values()), sum(v[1] for v in offs.values()), sum(v[2] for v in offs.values())))
    ons = {i: sets_of(on2, i) for i in intra}
    out("| **grammar on, live (layers fixed, L-810)** | %d | %d | %d |" % (sum(v[0] for v in ons.values()), sum(v[1] for v in ons.values()), sum(v[2] for v in ons.values())))
    leak22 = recs("bank2_fast_on_layer1_leak.jsonl")
    if leak22:
        lk = {i: sets_of(leak22, i) for i in intra if i in leak22}
        out("| grammar on, 測定時に層の漏れあり (superseded: layer 1 held every stand-in's cross; `bank2_fast_on_layer1_leak.jsonl`) (n = %d) | %d | %d | %d |" % (
            len(lk), sum(v[0] for v in lk.values()), sum(v[1] for v in lk.values()), sum(v[2] for v in lk.values())))
        lkf = {i for i in lk if lk[i][2] != ons[i][2]}
        out()
        out("Questions whose combined gold differs between the leaking run and the fixed run: %s." % (" ".join(sorted(lkf)) or "none"))
    out()
    og2 = lambda d, o: sum(1 for i in intra if i in d and origin_gold(d[i], bank2, o))
    out("Per origin: " + "; ".join("%s%s on %d" % (o, (" off %d," % og2(off2, o)) if off2 else "", og2(on2, o)) for o in ORIGINS) + ".")
    base_lbl, base_all, base_flat = ("the grammar-off run of this tree", {i: v[2] for i, v in offs.items()}, {i: v[0] for i, v in offs.items()}) if off2 else ("the T10 / G3-g records", rec_all, rec_flat)
    lost = [i for i in intra if base_all.get(i) and not ons[i][2]]
    gain = [i for i in intra if i in base_all and not base_all[i] and ons[i][2]]
    out("Against %s: combined gold lost %d (%s), gained %d (%s)." % (base_lbl, len(lost), " ".join(lost), len(gain), " ".join(gain)))
    flost = [i for i in intra if base_flat.get(i) and not ons[i][0]]
    fgain = [i for i in intra if i in base_flat and not base_flat[i] and ons[i][0]]
    out("Flat block alone: lost %d (%s), gained %d (%s).  Against the T10 flat records (same caches): lost %d (%s), gained %d (%s)." % (
        len(flost), " ".join(flost), len(fgain), " ".join(fgain),
        len([i for i in intra if rec_flat[i] and not ons[i][0]]), " ".join(i for i in intra if rec_flat[i] and not ons[i][0]),
        len([i for i in intra if not rec_flat[i] and ons[i][0]]), " ".join(i for i in intra if not rec_flat[i] and ons[i][0])))
    out()
    un = [i for i in ids2 if bank2[i]["kind"] == "unans"]
    for lbl, d in (("grammar off (this tree)", off2), ("grammar on", on2)):
        if not d:
            continue
        ui = [i for i in un if i in d]
        ii = [i for i in intra if i in d]
        out("* %s: unans (n = %d): abstained (no candidate) %d / list %d / single (ANSWER) %d, list size median %s max %s; intra2: ANSWER %d / CHOICE %d / none %d, confident wrong (ANSWER without the gold) %d; entries per question (intra2) median %s max %d; seconds per question median %s max %s." % (
            lbl, len(ui), sum(1 for i in ui if not ents(d[i])), sum(1 for i in ui if ents(d[i]) and d[i]["verdict"] != "ANSWER"), sum(1 for i in ui if d[i]["verdict"] == "ANSWER"),
            f1(med([len(ents(d[i])) for i in ui])), max([len(ents(d[i])) for i in ui] or [0]),
            sum(1 for i in ii if d[i]["verdict"] == "ANSWER"), sum(1 for i in ii if d[i]["verdict"] == "CHOICE"), sum(1 for i in ii if not ents(d[i])),
            sum(1 for i in ii if d[i]["verdict"] == "ANSWER" and not has_gold(d[i], bank2)),
            f1(med([len(ents(d[i])) for i in ii])), max([len(ents(d[i])) for i in ii] or [0]),
            f1(med([d[i]["ms"] / 1000 for i in ui + ii])), f1(max(d[i]["ms"] / 1000 for i in ui + ii))))
    out("* Forms over the %d questions: %s; questions with stand-ins: %d; T10 flat + layers recorded seconds per question: median %s." % (
        len(ids2), ", ".join("%s %d" % kv for kv in sorted(Counter(on2[i]["answer"]["grammar_form"]["form"] for i in ids2).items())),
        sum(1 for i in ids2 if on2[i]["answer"].get("standins") and sum(len(w["added"]) for w in on2[i]["answer"]["standins"]) > 0),
        f1(med([(t10[i]["ms_layer0"] + t10[i]["on"]["seatsPath"]["ms"]) / 1000 for i in ids2]))))
    un2 = [i for i in ids2 if bank2[i]["kind"] == "unans"]
    nmk = lambda ids, f: (sum(1 for i in ids for e in ents(on2[i]) if f(e)), sum(1 for i in ids if any(f(e) for e in ents(on2[i]))))
    f_via = is_standin
    f_rd = lambda e: is_read_standin(e) and not is_standin(e)
    a_, b_, c_, d_ = nmk(intra, f_via), nmk(un2, f_via), nmk(intra, f_rd), nmk(un2, f_rd)
    out("* Entries marked `via_standin` (flat + windows): **%d entries in %d intra2 questions + %d entries in %d unans questions (the unans questions get stand-in-only entries too: %d of %d have one)**; entries marked `read_via_standin` and not `via_standin`: %d in %d intra2 questions + %d in %d unans questions." % (
        a_[0], a_[1], b_[0], b_[1], b_[1], len(un2), c_[0], c_[1], d_[0], d_[1]))
    out()
    rdg = [i for i in intra if any(is_read_standin(e) and not is_standin(e) and hit(gold2(i), e) for e in ents(on2[i]))]
    out("* The gold is in a `via_standin` entry for %d intra2 questions (%s), in a `read_via_standin` (not `via_standin`) entry for %d (%s)." % (
        sum(1 for i in intra if any(is_standin(e) and hit(gold2(i), e) for e in ents(on2[i]))), " ".join(i for i in intra if any(is_standin(e) and hit(gold2(i), e) for e in ents(on2[i]))) or "-", len(rdg), " ".join(rdg) or "-"))
    out()
    if off2:
        out("### 6b. Where the gained golds came from (intra2, combined, on against the off run of this tree; there is no bank2 order-only run, so a `neither` gold also contains what the order alone brings)")
        out()
        gain_table("bank2 intra2, on against off", [i for i in intra if i in off2], on2, off2, bank2, "in the off run")
        lost2 = [i for i in intra if i in off2 and has_gold(off2[i], bank2) and not has_gold(on2[i], bank2)]
        out("Lost against off: %s." % (" ".join(lost2) or "none"))
        out()
    # the chance control on bank2: another intra2 gold against the stand-in-derived candidates of this question
    g2 = {i: gold2(i) for i in intra}
    mk_q = [i for i in intra if any(is_standin(e) for e in ents(on2[i]))]
    own = sum(1 for i in mk_q if any(is_standin(e) and hit(g2[i], e) for e in ents(on2[i])))
    pairs = sum(len(g2) - 1 for _i in mk_q)
    oth = sum(1 for i in mk_q for j in g2 if j != i and any(is_standin(e) and hit(g2[j], e) for e in ents(on2[i])))
    un_q = [i for i in intra if any(w["added"] for w in on2[i]["answer"].get("standins", []))]
    own_u = sum(1 for i in un_q if any(S.hits_words(g2[i], [u]) for w in on2[i]["answer"]["standins"] for u in w["added"]))
    pairs_u = sum(len(g2) - 1 for _i in un_q)
    oth_u = sum(1 for i in un_q for j in g2 if j != i and any(S.hits_words(g2[j], [u]) for w in on2[i]["answer"]["standins"] for u in w["added"]))
    def _int(w): return any(q in w["word"] for q in _GR.INTERROG)
    own_u_int = sum(1 for i in un_q if any(S.hits_words(g2[i], [u]) for w in on2[i]["answer"]["standins"] if _int(w) for u in w["added"]))
    own_u_non = sum(1 for i in un_q if any(S.hits_words(g2[i], [u]) for w in on2[i]["answer"]["standins"] if not _int(w) for u in w["added"]))
    out("* Own gold inside a stand-in unit by the kind of the unknown word: through a word that contains an interrogative %d questions, through another unknown word %d (a question can be in both)." % (own_u_int, own_u_non))
    out("* Chance control (intra2 golds): intra2 questions with a `via_standin` entry: %d, own gold in one: %d; other intra2 golds in them: %s of the pairs.  Questions with stand-in units: %d, own gold inside a stand-in unit: %d; other golds inside a stand-in unit: %s of the pairs." % (
        len(mk_q), own, fr(oth, pairs) if pairs else "0/0", len(un_q), own_u, fr(oth_u, pairs_u) if pairs_u else "0/0"))
    out()
    out("| id | form (slot) | stand-ins added | baseline combined gold (%s) | on gold (first pos) | flat baseline | flat on |" % base_lbl)
    out("|---|---|---|---|---|---|---|")
    for i in intra:
        a = on2[i]["answer"]
        add = sum(len(w["added"]) for w in a.get("standins", []))
        bg = (base_all[i] if i in base_all else rec_all[i])
        bf = (base_flat[i] if i in base_flat else rec_flat[i])
        of_ = any(hit(gold2(i), e) and any(x.startswith("flat/") and x != ASSEMBLED for x in e["origins"]) for e in ents(on2[i]))
        fg = first_gold(on2[i], bank2)
        out("| %s | %s (%s) | %d | %s | %s | %s | %s |" % (i, a["grammar_form"]["form"], a["grammar_form"]["slot"] or "-", add, "yes" if bg else "no",
                                                       "yes (%d)" % fg if fg else "no", "yes" if bf else "no", "yes" if of_ else "no"))
    out()

open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
