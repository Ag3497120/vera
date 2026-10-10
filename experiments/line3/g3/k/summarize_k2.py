"""G3-k2 summary: the flat plane's read order eq_first (E_Q first; the original units held, the stand-ins held and the grammar kind only inside an exact E_Q tie).

usage: summarize_k2.py   (PYTHONPATH=. ; reads results/*.jsonl of G3-k and G3-k2, no search is run; prints the section and writes results/summary_k2.md; it also puts the same section
at the END of results/summary.md, replacing an earlier G3-k2 section of that file, so that `summarize_k.py` (which rewrites summary.md) is run first)
Records: off (bank3_uwpa_fast_off), order-only under G3-k's order (..._on_order_only), on-qcount_first (..._on), on-eq_first (..._on_eq_first), and, as the same-order attribution,
order-only under eq_first (..._on_order_only_eq_first); bank2 intra2: off (bank2_fast_off), on-qcount_first (bank2_fast_on), on-eq_first (bank2_intra2_fast_on_eq_first).
Headline (the owner, 「代役の印と見出し」): on-eq_first minus the ORDER-ONLY run (the stand-ins' effect); against off is reported next to it."""
import json, os, statistics, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
L3 = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(L3, "t9"))
import scorer as S                                         # noqa: E402

RES = os.path.join(HERE, "results")
ASSEMBLED = "flat/assembled"
OUT = []


def out(s=""):
    OUT.append(s); print(s)


def jl(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
def med(x): return statistics.median(x) if x else None
def f1(x): return "-" if x is None else ("%.1f" % x)


def load_bank(path):
    b = {}
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or not l.strip():
            continue
        r = dict(zip("id kind corpus subject question gold evidence notes audit".split(), l.rstrip("\n").split("\t")))
        b[r["id"]] = r
    return b


bank3, bank2 = load_bank(os.path.join(L3, "bank3", "bank3.tsv")), load_bank(os.path.join(L3, "bank2", "bank2.tsv"))


def recs(name):
    p = os.path.join(RES, name)
    return {r["id"]: r for r in jl(p) if "error" not in r} if os.path.exists(p) else {}


def ents(r): return [e for e in r["answer"]["entries"] if e["origins"] != [ASSEMBLED]]
def hit(g, e): return S.hits_words(g, e["words"])
def gold_of(r, bank):
    g = bank[r["id"]]["gold"]
    return g.split("|", 1)[1] if r["kind"] == "summary-choice" else g
def has_gold(r, bank): return any(hit(gold_of(r, bank), e) for e in ents(r))
def is_vs(e): return "via_standin" in e["marks"]
def is_rvs(e): return "read_via_standin" in e["marks"]
def nrun(d, i): return sum(1 for e in ents(d[i]) if "flat/RUN" in e["origins"])
def nwin(d, i): return sum(1 for e in ents(d[i]) if any(x.startswith("window/") for x in e["origins"]))


def entry_class(e):
    if is_vs(e):
        return "via_standin"
    if is_rvs(e):
        return "read_via_standin"
    if all(x.startswith("layers") for x in e["origins"]):
        return "layers (unmarked by design)"
    return "neither"


def gold_classes(r, bank):
    g = gold_of(r, bank)
    return [(",".join(e["origins"]), entry_class(e)) for e in ents(r) if hit(g, e)]


def meta(name):
    p = os.path.join(RES, name + ".meta.json")
    return json.load(open(p)) if os.path.exists(p) else {}


off3, oo3 = recs("bank3_uwpa_fast_off.jsonl"), recs("bank3_uwpa_fast_on_order_only.jsonl")
qc3, eq3 = recs("bank3_uwpa_fast_on.jsonl"), recs("bank3_uwpa_fast_on_eq_first.jsonl")
ooe3 = recs("bank3_uwpa_fast_on_order_only_eq_first.jsonl")
KINDS = ["unknown-word", "paraphrase"]
ids3 = sorted(i for i in eq3 if i in off3 and i in qc3 and i in oo3)

out("# G3-k2 -- the flat plane's read order eq_first (「E_Q が先、単位数は同点内」), both marks, the headline over the order-only run")
out()
m = meta("bank3_uwpa_fast_on_eq_first.jsonl")
if m:
    out("Code: line3 HEAD `%s` + the uncommitted G3-k2 work; bank3 sweep started %s (python %s, PYTHONHASHSEED=%s, 10 workers, fast); code sha256: %s." % (
        (m.get("head") or "?")[:12], m.get("started"), m.get("python"), m.get("pyhashseed"), ", ".join("%s %s" % (k, v[:10]) for k, v in sorted(m.get("code_sha256", {}).items()))))
    out()

# ---- 1. gold per kind --------------------------------------------------------------------------------------------------------------------------
out("## 1. bank3 fulllead, unknown-word 18 + paraphrase 20, combined fast: gold in a candidate (t9 rule; the assembled strings do not count)")
out()
cols = [("off", off3), ("order-only (G3-k order = qcount_first)", oo3), ("on, qcount_first (G3-k)", qc3), ("**on, eq_first**", eq3)]
if ooe3:
    cols.insert(2, ("order-only, eq_first (same-order attribution)", ooe3))
G = lambda d, ids: {i for i in ids if has_gold(d[i], bank3)}
out("| kind | n | " + " | ".join(n for n, _ in cols) + " | **headline: on-eq_first minus order-only** | on-eq_first minus off |")
out("|---|---|" + "---|" * (len(cols) + 2))
rows_ids = {k: [i for i in ids3 if bank3[i]["kind"] == k] for k in KINDS}
for kind in KINDS + ["all"]:
    ids = ids3 if kind == "all" else rows_ids[kind]
    cnt = [len(G(d, ids)) for _n, d in cols]
    oo, eq, off = G(oo3, ids), G(eq3, ids), G(off3, ids)
    out("| %s | %d | %s | **%+d** (%s) | %+d (%s) |" % (kind, len(ids), " | ".join(str(c) for c in cnt), len(eq) - len(oo), " ".join("+" + i.replace("b3_", "") for i in sorted(eq - oo)) + (" " + " ".join("-" + i.replace("b3_", "") for i in sorted(oo - eq)) if oo - eq else ""),
                                          len(eq) - len(off), " ".join("+" + i.replace("b3_", "") for i in sorted(eq - off)) + (" " + " ".join("-" + i.replace("b3_", "") for i in sorted(off - eq)) if off - eq else "")))
out()
out("Question-level differences, on-eq_first against on-qcount_first: gained %s; lost %s." % (
    " ".join(i.replace("b3_", "") for i in sorted(G(eq3, ids3) - G(qc3, ids3))) or "none", " ".join(i.replace("b3_", "") for i in sorted(G(qc3, ids3) - G(eq3, ids3))) or "none"))
if ooe3:
    out("Order-only under eq_first against order-only under qcount_first: gained %s; lost %s (the order alone, without stand-ins, now reads the tie by the original count only)." % (
        " ".join(i.replace("b3_", "") for i in sorted(G(ooe3, ids3) - G(oo3, ids3))) or "none", " ".join(i.replace("b3_", "") for i in sorted(G(oo3, ids3) - G(ooe3, ids3))) or "none"))
out()
vs = lambda d: sum(len(ents(d[i])) for i in ids3)
out("List size (non-assembled entries) median / max, off %s / %d, order-only %s / %d, on-qcount_first %s / %d, **on-eq_first %s / %d**; ANSWER verdicts off %d, order-only %d, on-qcount_first %d, on-eq_first %d." % (
    f1(med([len(ents(off3[i])) for i in ids3])), max(len(ents(off3[i])) for i in ids3), f1(med([len(ents(oo3[i])) for i in ids3])), max(len(ents(oo3[i])) for i in ids3),
    f1(med([len(ents(qc3[i])) for i in ids3])), max(len(ents(qc3[i])) for i in ids3), f1(med([len(ents(eq3[i])) for i in ids3])), max(len(ents(eq3[i])) for i in ids3),
    *[sum(1 for i in ids3 if d[i]["verdict"] == "ANSWER") for d in (off3, oo3, qc3, eq3)]))
out()

# ---- 2. the collapse questions -----------------------------------------------------------------------------------------------------------------
collapse = [i for i in ids3 if nrun(off3, i) >= 10 and nrun(qc3, i) * 4 < nrun(off3, i)]
out("## 2. The %d questions whose flat/RUN block collapsed under G3-k (off >= 10 entries, on-qcount_first under a quarter): flat/RUN entries per order" % len(collapse))
out()
hdr = ["off", "order-only (qcount_first)"] + (["order-only (eq_first)"] if ooe3 else []) + ["on qcount_first", "**on eq_first**"]
dd = [off3, oo3] + ([ooe3] if ooe3 else []) + [qc3, eq3]
out("| question | stand-in units added | " + " | ".join("flat/RUN " + h for h in hdr) + " | window entries off / on-qcount / **on-eq** | gold off / on-qcount / on-eq |")
out("|---|---|" + "---|" * (len(hdr) + 2))
for i in collapse:
    out("| %s | %d | %s | %d / %d / %d | %s / %s / %s |" % (i.replace("b3_", ""), sum(len(w["added"]) for w in eq3[i]["answer"].get("standins", [])), " | ".join(str(nrun(d, i)) for d in dd),
                                                        nwin(off3, i), nwin(qc3, i), nwin(eq3, i), *["Y" if has_gold(d[i], bank3) else "-" for d in (off3, qc3, eq3)]))
tot = lambda d: sum(nrun(d, i) for i in collapse)
out("| **total (%d questions)** | | %s | %d / %d / %d | |" % (len(collapse), " | ".join(str(tot(d)) for d in dd), sum(nwin(off3, i) for i in collapse), sum(nwin(qc3, i) for i in collapse), sum(nwin(eq3, i) for i in collapse)))
out()
still = [i for i in collapse if nrun(eq3, i) * 4 < nrun(off3, i)]
out("Still under a quarter of off under eq_first: %s.  flat/RUN entries over ALL %d questions: off %d, order-only %d, on-qcount_first %d, **on-eq_first %d**; questions where flat/RUN lists nothing: off %d, on-qcount_first %d, on-eq_first %d." % (
    " ".join(i.replace("b3_", "") for i in still) or "none", len(ids3), *[sum(nrun(d, i) for i in ids3) for d in (off3, oo3, qc3, eq3)],
    *[sum(1 for i in ids3 if nrun(d, i) == 0) for d in (off3, qc3, eq3)]))
out()

# ---- 3. the marks and the gained golds -----------------------------------------------------------------------------------------------------------
out("## 3. The marks (on-eq_first) and where the gained golds came from")
out()
tm = sum(1 for i in ids3 for e in ents(eq3[i]) if is_vs(e))
rv = [e for i in ids3 for e in ents(eq3[i]) if is_rvs(e) and not is_vs(e)]
out("Entries marked `via_standin`: %d of %d (on-qcount_first %d); marked `read_via_standin` and not `via_standin`: %d in %d questions (on-qcount_first %d); both: %d.  The combined header's grammar row carries both counts per question (L-821)." % (
    tm, vs(eq3), sum(1 for i in ids3 for e in ents(qc3[i]) if is_vs(e)), len(rv), len({i for i in ids3 for e in ents(eq3[i]) if is_rvs(e) and not is_vs(e)}),
    sum(1 for i in ids3 for e in ents(qc3[i]) if is_rvs(e) and not is_vs(e)), sum(1 for i in ids3 for e in ents(eq3[i]) if is_vs(e) and is_rvs(e))))
hdrchk = [i for i in ids3 if (eq3[i]["answer"]["header"][0].get("via_standin"), eq3[i]["answer"]["header"][0].get("read_via_standin")) !=
          (sum(1 for e in eq3[i]["answer"]["entries"] if is_vs(e)), sum(1 for e in eq3[i]["answer"]["entries"] if is_rvs(e)))]
out("Header grammar-row counts equal the counts of the marks over the list for %d of %d questions%s." % (len(ids3) - len(hdrchk), len(ids3), "" if not hdrchk else " (differs: %s)" % " ".join(hdrchk)))
out()


def gain_table(title, ids, d, base, bank, base_name):
    gained = [i for i in ids if has_gold(d[i], bank) and not has_gold(base[i], bank)]
    out("**%s**: %d questions gained." % (title, len(gained)))
    out()
    out("| question | gold entries on-eq_first: origin (mark class) |")
    out("|---|---|")
    for i in gained:
        out("| %s | %s |" % (i.replace("b3_", ""), "; ".join("%s (%s)" % x for x in gold_classes(d[i], bank))))
    out()
    cl = {i: {c for _o, c in gold_classes(d[i], bank)} for i in gained}
    n = lambda c: sum(1 for i in gained if c in cl[i])
    only = lambda c: sum(1 for i in gained if cl[i] == {c})
    out("By mark (a question counts once per class it has): `via_standin` %d; `read_via_standin` (not `via_standin`) %d; layers entry (unmarked by design) %d; neither %d.  Exactly one class: via_standin %d, read_via_standin %d, layers %d, neither %d.  With any stand-in mark: %d of %d." % (
        n("via_standin"), n("read_via_standin"), n("layers (unmarked by design)"), n("neither"), only("via_standin"), only("read_via_standin"), only("layers (unmarked by design)"), only("neither"),
        sum(1 for i in gained if cl[i] & {"via_standin", "read_via_standin"}), len(gained)))
    out()


gain_table("bank3, on-eq_first against the ORDER-ONLY run (the headline)", ids3, eq3, oo3, bank3, "order-only")
if ooe3:
    gain_table("bank3, on-eq_first against the order-only run UNDER eq_first (same order, stand-ins dropped)", ids3, eq3, ooe3, bank3, "order-only eq_first")
gain_table("bank3, on-eq_first against off", ids3, eq3, off3, bank3, "off")
lost = [i for i in ids3 if has_gold(oo3[i], bank3) and not has_gold(eq3[i], bank3)]
lost_off = [i for i in ids3 if has_gold(off3[i], bank3) and not has_gold(eq3[i], bank3)]
out("Golds lost: against order-only %s; against off %s." % (" ".join(i.replace("b3_", "") for i in lost) or "none", " ".join(i.replace("b3_", "") for i in lost_off) or "none"))
out()

# ---- 4. bank2 intra2 ---------------------------------------------------------------------------------------------------------------------------
off2, qc2, eq2 = recs("bank2_fast_off.jsonl"), recs("bank2_fast_on.jsonl"), recs("bank2_intra2_fast_on_eq_first.jsonl")
if eq2:
    out("## 4. bank2 fulllead intra2 (n = %d), combined fast" % len([i for i in eq2 if bank2[i]["kind"] == "intra2"]))
    out()
    intra = sorted(i for i in eq2 if bank2[i]["kind"] == "intra2" and i in off2 and i in qc2)
    isflat = lambda x: x.startswith("flat/") and x != ASSEMBLED

    def sets_of(d, i):
        g = bank2[i]["gold"]
        fl = any(hit(g, e) and any(isflat(x) for x in e["origins"]) for e in ents(d[i]))
        ly = any(hit(g, e) and any(x.startswith("layers/") for x in e["origins"]) for e in ents(d[i]))
        wi_ = any(hit(g, e) and any(x.startswith("window/") for x in e["origins"]) for e in ents(d[i]))
        return fl, fl or ly, fl or ly or wi_
    out("| system (intra2, n = %d) | flat block | flat + layers | combined (all blocks) |" % len(intra))
    out("|---|---|---|---|")
    S2 = {}
    for name, d in (("grammar off, this tree (stored)", off2), ("on, qcount_first (stored, G3-k)", qc2), ("**on, eq_first**", eq2)):
        S2[name] = {i: sets_of(d, i) for i in intra}
        out("| %s | %d | %d | %d |" % (name, *[sum(v[k] for v in S2[name].values()) for k in range(3)]))
    out()
    a, b, c = (S2[k] for k in S2)
    comb = lambda x: {i for i in intra if x[i][2]}
    out("Combined gold: on-eq_first gained against off %s, lost %s; against on-qcount_first gained %s, lost %s." % (
        " ".join(sorted(comb(c) - comb(a))) or "none", " ".join(sorted(comb(a) - comb(c))) or "none", " ".join(sorted(comb(c) - comb(b))) or "none", " ".join(sorted(comb(b) - comb(c))) or "none"))
    cls = Counter()
    for i in sorted(comb(c) - comb(a)):
        for _o, k in set(gold_classes(eq2[i], bank2)):
            cls[k] += 1
    out("Gained against off (%d questions), mark classes of their gold entries (a question counts once per class): %s.  There is no bank2 order-only run, so `neither` also holds what the order alone brings." % (
        len(comb(c) - comb(a)), ", ".join("%s %d" % kv for kv in sorted(cls.items())) or "-"))
    out("Entries marked via_standin %d, read_via_standin and not via_standin %d (on-qcount_first %d / %d); list size median / max off %s / %d, on-qcount_first %s / %d, on-eq_first %s / %d; ANSWER verdicts off %d / on-qcount_first %d / on-eq_first %d, of them without the gold off %d / %d / %d." % (
        sum(1 for i in intra for e in ents(eq2[i]) if is_vs(e)), sum(1 for i in intra for e in ents(eq2[i]) if is_rvs(e) and not is_vs(e)),
        sum(1 for i in intra for e in ents(qc2[i]) if is_vs(e)), sum(1 for i in intra for e in ents(qc2[i]) if is_rvs(e) and not is_vs(e)),
        f1(med([len(ents(off2[i])) for i in intra])), max(len(ents(off2[i])) for i in intra), f1(med([len(ents(qc2[i])) for i in intra])), max(len(ents(qc2[i])) for i in intra),
        f1(med([len(ents(eq2[i])) for i in intra])), max(len(ents(eq2[i])) for i in intra),
        *[sum(1 for i in intra if d[i]["verdict"] == "ANSWER") for d in (off2, qc2, eq2)],
        *[sum(1 for i in intra if d[i]["verdict"] == "ANSWER" and not has_gold(d[i], bank2)) for d in (off2, qc2, eq2)]))
    un_eq = recs("bank2_unans_fast_on_eq_first.jsonl")
    if un_eq:
        un_off, un_qc = recs("bank2_fast_off.jsonl"), recs("bank2_fast_on.jsonl")
        uid = sorted(i for i in un_eq if bank2[i]["kind"] == "unans")
        out("Unanswerable (unans, n = %d): a single (ANSWER) verdict off %d / on-qcount_first %d / on-eq_first %d; abstained (no candidate) off %d / %d / %d." % (
            len(uid), *[sum(1 for i in uid if d[i]["verdict"] == "ANSWER") for d in (un_off, un_qc, un_eq)], *[sum(1 for i in uid if not ents(d[i])) for d in (un_off, un_qc, un_eq)]))
    out()

sec = "\n".join(OUT) + "\n"
open(os.path.join(RES, "summary_k2.md"), "w", encoding="utf-8").write(sec)
p = os.path.join(RES, "summary.md")
if os.path.exists(p):
    s = open(p, encoding="utf-8").read()
    k = s.find("\n# G3-k2 ")
    s = (s[:k] if k >= 0 else s.rstrip("\n")) + "\n\n" + sec.replace("\n", "\n", 1)
    open(p, "w", encoding="utf-8").write(s)
