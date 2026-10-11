"""G3-k3 summary: the stand-in seeds' crosses in the group holds_query_unit (eq_first + group), compared with the G3-k2 records.

usage: PYTHONPATH=. summarize_k3.py   (reads results/*.jsonl of G3-k / G3-k2 / G3-k3, no search is run; prints the section and APPENDS it to results/summary_k2.md and to results/summary.md,
replacing an earlier "# G3-k3" section of those files; run summarize_k.py / summarize_k2.py first, they rewrite their files)
Records: off (bank3_uwpa_fast_off), order-only under eq_first (..._on_order_only_eq_first; the group changes nothing without stand-ins), on-qcount_first (..._on, G3-k),
on-eq_first (..._on_eq_first, G3-k2), on-eq_first+group (..._on_eq_first_group, this); bank2 intra2 / unans: off (bank2_fast_off), on-qcount_first (bank2_fast_on),
on-eq_first (bank2_intra2_fast_on_eq_first, bank2_unans_fast_on_eq_first), on-eq_first+group (bank2_*_fast_on_eq_first_group).
Headline (the owner, G3-k2 「代役の印と見出し」): the stand-ins' effect = the gain over the ORDER-ONLY run (under the same order eq_first)."""
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
def sid(i): return i.replace("b3_", "")


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


def diff(a, b):
    return " ".join("+" + sid(i) for i in sorted(a - b)) + (" " if a - b and b - a else "") + " ".join("-" + sid(i) for i in sorted(b - a))


off3, qc3 = recs("bank3_uwpa_fast_off.jsonl"), recs("bank3_uwpa_fast_on.jsonl")
ooe3, eq3, gp3 = recs("bank3_uwpa_fast_on_order_only_eq_first.jsonl"), recs("bank3_uwpa_fast_on_eq_first.jsonl"), recs("bank3_uwpa_fast_on_eq_first_group.jsonl")
KINDS = ["unknown-word", "paraphrase"]
ids3 = sorted(i for i in gp3 if i in off3 and i in qc3 and i in ooe3 and i in eq3)

out("# G3-k3 -- the stand-in seeds' crosses in the group holds_query_unit (eq_first + group; 「代役の種は holds_query_unit の群へ」)")
out()
m = meta("bank3_uwpa_fast_on_eq_first_group.jsonl")
if m:
    out("Code: line3 HEAD `%s` + the uncommitted G3-k3 work; bank3 sweep started %s (python %s, PYTHONHASHSEED=%s, 10 workers, fast); code sha256: %s." % (
        (m.get("head") or "?")[:12], m.get("started"), m.get("python"), m.get("pyhashseed"), ", ".join("%s %s" % (k, v[:10]) for k, v in sorted(m.get("code_sha256", {}).items()))))
    out()

# ---- 1. gold per kind -------------------------------------------------------------------------------------------------------------------------
out("## 1. bank3 fulllead, unknown-word 18 + paraphrase 20, combined fast: gold in a candidate (t9 rule; the assembled strings do not count)")
out()
cols = [("off", off3), ("order-only (eq_first)", ooe3), ("on-eq_first (G3-k2)", eq3), ("**on-eq_first + group (G3-k3)**", gp3)]
G = lambda d, ids: {i for i in ids if has_gold(d[i], bank3)}
out("| kind | n | " + " | ".join(n for n, _ in cols) + " | **headline: this minus order-only (eq_first)** | this minus off | this minus G3-k2 |")
out("|---|---|" + "---|" * (len(cols) + 3))
for kind in KINDS + ["all"]:
    ids = ids3 if kind == "all" else [i for i in ids3 if bank3[i]["kind"] == kind]
    oo, gp, off, eq = G(ooe3, ids), G(gp3, ids), G(off3, ids), G(eq3, ids)
    out("| %s | %d | %s | **%+d** (%s) | %+d (%s) | %+d (%s) |" % (kind, len(ids), " | ".join(str(len(G(d, ids))) for _n, d in cols), len(gp) - len(oo), diff(gp, oo),
                                                              len(gp) - len(off), diff(gp, off), len(gp) - len(eq), diff(gp, eq)))
out()
out("For reference, stored G3-k records: order-only (qcount_first) %d, on-qcount_first %d (all 38).  Headline as the owner first stated it (this minus order-only under qcount_first): %+d (%s)." % (
    len(G(recs("bank3_uwpa_fast_on_order_only.jsonl"), ids3)), len(G(qc3, ids3)), len(G(gp3, ids3)) - len(G(recs("bank3_uwpa_fast_on_order_only.jsonl"), ids3)),
    diff(G(gp3, ids3), G(recs("bank3_uwpa_fast_on_order_only.jsonl"), ids3))))
out()
dr = lambda d: "%s / %d" % (f1(med([len(ents(d[i])) for i in ids3])), max(len(ents(d[i])) for i in ids3))
out("List size (non-assembled entries) median / max: off %s, order-only(eq) %s, on-qcount_first %s, on-eq_first %s, **eq_first + group %s**; ANSWER verdicts off %d, order-only(eq) %d, on-qcount_first %d, on-eq_first %d, eq_first + group %d." % (
    *[dr(d) for d in (off3, ooe3, qc3, eq3, gp3)], *[sum(1 for i in ids3 if d[i]["verdict"] == "ANSWER") for d in (off3, ooe3, qc3, eq3, gp3)]))
out()

# ---- 2. the collapse questions ---------------------------------------------------------------------------------------------------------------
collapse = [i for i in ids3 if nrun(off3, i) >= 10 and nrun(qc3, i) * 4 < nrun(off3, i)]
out("## 2. The %d questions whose flat/RUN block collapsed under G3-k (off >= 10 entries, on-qcount_first under a quarter): flat/RUN entry counts" % len(collapse))
out()
hdr = [("off", off3), ("order-only (eq_first)", ooe3), ("on qcount_first (G3-k)", qc3), ("on eq_first (G3-k2)", eq3), ("**on eq_first + group (G3-k3)**", gp3)]
out("| question | stand-in units added | " + " | ".join("flat/RUN " + h for h, _ in hdr) + " | window entries off / G3-k2 / **G3-k3** | gold off / G3-k2 / G3-k3 |")
out("|---|---|" + "---|" * (len(hdr) + 2))
for i in collapse:
    out("| %s | %d | %s | %d / %d / %d | %s / %s / %s |" % (sid(i), sum(len(w["added"]) for w in gp3[i]["answer"].get("standins", [])), " | ".join(str(nrun(d, i)) for _h, d in hdr),
                                                        nwin(off3, i), nwin(eq3, i), nwin(gp3, i), *["Y" if has_gold(d[i], bank3) else "-" for d in (off3, eq3, gp3)]))
out("| **total (%d questions)** | | %s | %d / %d / %d | |" % (len(collapse), " | ".join(str(sum(nrun(d, i) for i in collapse)) for _h, d in hdr),
                                                            sum(nwin(off3, i) for i in collapse), sum(nwin(eq3, i) for i in collapse), sum(nwin(gp3, i) for i in collapse)))
out()
still = [i for i in collapse if nrun(gp3, i) * 4 < nrun(off3, i)]
out("Still under a quarter of off with the group: %s.  flat/RUN entries over ALL %d questions: off %d, order-only(eq) %d, on-qcount_first %d, on-eq_first %d, **eq_first + group %d**; questions where flat/RUN lists nothing: off %d, on-eq_first %d, eq_first + group %d." % (
    " ".join(sid(i) for i in still) or "none", len(ids3), *[sum(nrun(d, i) for i in ids3) for d in (off3, ooe3, qc3, eq3, gp3)], *[sum(1 for i in ids3 if nrun(d, i) == 0) for d in (off3, eq3, gp3)]))
out()

# ---- 3. the marks and the gained golds -------------------------------------------------------------------------------------------------------
out("## 3. The marks (eq_first + group) and where the gained golds came from")
out()
tot = lambda d: sum(len(ents(d[i])) for i in ids3)
vsn = lambda d: sum(1 for i in ids3 for e in ents(d[i]) if is_vs(e))
rvn = lambda d: sum(1 for i in ids3 for e in ents(d[i]) if is_rvs(e) and not is_vs(e))
out("Entries marked `via_standin`: %d of %d (G3-k2 %d of %d, on-qcount_first %d); marked `read_via_standin` and not `via_standin`: %d in %d questions (G3-k2 %d, on-qcount_first %d); both: %d." % (
    vsn(gp3), tot(gp3), vsn(eq3), tot(eq3), vsn(qc3), rvn(gp3), len({i for i in ids3 for e in ents(gp3[i]) if is_rvs(e) and not is_vs(e)}), rvn(eq3), rvn(qc3),
    sum(1 for i in ids3 for e in ents(gp3[i]) if is_vs(e) and is_rvs(e))))
hdrchk = [i for i in ids3 if (gp3[i]["answer"]["header"][0].get("via_standin"), gp3[i]["answer"]["header"][0].get("read_via_standin")) !=
          (sum(1 for e in gp3[i]["answer"]["entries"] if is_vs(e)), sum(1 for e in gp3[i]["answer"]["entries"] if is_rvs(e)))]
out("Header grammar-row counts equal the counts of the marks over the list for %d of %d questions%s." % (len(ids3) - len(hdrchk), len(ids3), "" if not hdrchk else " (differs: %s)" % " ".join(hdrchk)))
out()


def gain_table(title, ids, d, base, bank):
    gained = [i for i in ids if has_gold(d[i], bank) and not has_gold(base[i], bank)]
    out("**%s**: %d questions gained." % (title, len(gained)))
    out()
    if gained:
        out("| question | gold entries: origin (mark class) |")
        out("|---|---|")
        for i in gained:
            out("| %s | %s |" % (sid(i), "; ".join("%s (%s)" % x for x in gold_classes(d[i], bank))))
        out()
    cl = {i: {c for _o, c in gold_classes(d[i], bank)} for i in gained}
    n = lambda c: sum(1 for i in gained if c in cl[i])
    only = lambda c: sum(1 for i in gained if cl[i] == {c})
    out("By mark (a question counts once per class it has): `via_standin` %d; `read_via_standin` (not `via_standin`) %d; layers entry (unmarked by design) %d; neither %d.  Exactly one class: via_standin %d, read_via_standin %d, layers %d, neither %d.  With any stand-in mark: %d of %d." % (
        n("via_standin"), n("read_via_standin"), n("layers (unmarked by design)"), n("neither"), only("via_standin"), only("read_via_standin"), only("layers (unmarked by design)"), only("neither"),
        sum(1 for i in gained if cl[i] & {"via_standin", "read_via_standin"}), len(gained)))
    out()


gain_table("bank3, eq_first + group against the ORDER-ONLY run under eq_first (the headline)", ids3, gp3, ooe3, bank3)
gain_table("bank3, eq_first + group against off", ids3, gp3, off3, bank3)
lost = [i for i in ids3 if has_gold(ooe3[i], bank3) and not has_gold(gp3[i], bank3)]
lost_off = [i for i in ids3 if has_gold(off3[i], bank3) and not has_gold(gp3[i], bank3)]
out("Golds lost: against order-only(eq) %s; against off %s; against G3-k2 %s (gained against G3-k2: %s)." % (
    " ".join(sid(i) for i in lost) or "none", " ".join(sid(i) for i in lost_off) or "none",
    " ".join(sid(i) for i in sorted(G(eq3, ids3) - G(gp3, ids3))) or "none", " ".join(sid(i) for i in sorted(G(gp3, ids3) - G(eq3, ids3))) or "none"))
out()

# ---- 4. bank2 intra2 ------------------------------------------------------------------------------------------------------------------------
off2, qc2 = recs("bank2_fast_off.jsonl"), recs("bank2_fast_on.jsonl")
eq2, gp2 = recs("bank2_intra2_fast_on_eq_first.jsonl"), recs("bank2_intra2_fast_on_eq_first_group.jsonl")
if gp2:
    intra = sorted(i for i in gp2 if bank2[i]["kind"] == "intra2" and i in off2 and i in qc2 and i in eq2)
    out("## 4. bank2 fulllead intra2 (n = %d), combined fast" % len(intra))
    out()
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
    for name, d in (("grammar off (stored)", off2), ("on, qcount_first (stored, G3-k)", qc2), ("on, eq_first (stored, G3-k2)", eq2), ("**on, eq_first + group (G3-k3)**", gp2)):
        S2[name] = {i: sets_of(d, i) for i in intra}
        out("| %s | %d | %d | %d |" % (name, *[sum(v[k] for v in S2[name].values()) for k in range(3)]))
    out()
    a, b, c, g_ = (S2[k] for k in S2)
    comb = lambda x: {i for i in intra if x[i][2]}
    out("Combined gold, eq_first + group: against off gained %s, lost %s; against G3-k2 gained %s, lost %s; against on-qcount_first gained %s, lost %s." % (
        " ".join(sorted(comb(g_) - comb(a))) or "none", " ".join(sorted(comb(a) - comb(g_))) or "none", " ".join(sorted(comb(g_) - comb(c))) or "none", " ".join(sorted(comb(c) - comb(g_))) or "none",
        " ".join(sorted(comb(g_) - comb(b))) or "none", " ".join(sorted(comb(b) - comb(g_))) or "none"))
    cls = Counter()
    for i in sorted(comb(g_) - comb(a)):
        for _o, k in set(gold_classes(gp2[i], bank2)):
            cls[k] += 1
    out("Gained against off (%d questions), mark classes of their gold entries (a question counts once per class): %s.  There is no bank2 order-only run, so `neither` also holds what the order alone brings." % (
        len(comb(g_) - comb(a)), ", ".join("%s %d" % kv for kv in sorted(cls.items())) or "-"))
    vs2 = lambda d: sum(1 for i in intra for e in ents(d[i]) if is_vs(e))
    rv2 = lambda d: sum(1 for i in intra for e in ents(d[i]) if is_rvs(e) and not is_vs(e))
    dr2 = lambda d: "%s / %d" % (f1(med([len(ents(d[i])) for i in intra])), max(len(ents(d[i])) for i in intra))
    out("Entries marked via_standin %d, read_via_standin and not via_standin %d (G3-k2 %d / %d, on-qcount_first %d / %d); list size median / max off %s, on-qcount_first %s, G3-k2 %s, **eq_first + group %s**; ANSWER verdicts off %d / on-qcount_first %d / G3-k2 %d / eq_first + group %d, of them without the gold %d / %d / %d / %d." % (
        vs2(gp2), rv2(gp2), vs2(eq2), rv2(eq2), vs2(qc2), rv2(qc2), dr2(off2), dr2(qc2), dr2(eq2), dr2(gp2),
        *[sum(1 for i in intra if d[i]["verdict"] == "ANSWER") for d in (off2, qc2, eq2, gp2)],
        *[sum(1 for i in intra if d[i]["verdict"] == "ANSWER" and not has_gold(d[i], bank2)) for d in (off2, qc2, eq2, gp2)]))
    un_gp, un_eq = recs("bank2_unans_fast_on_eq_first_group.jsonl"), recs("bank2_unans_fast_on_eq_first.jsonl")
    if un_gp:
        uid = sorted(i for i in un_gp if bank2[i]["kind"] == "unans" and i in off2 and i in qc2 and i in un_eq)
        out("Unanswerable (unans, n = %d): a single (ANSWER) verdict -- a wrong answer, nothing is answerable -- off %d / on-qcount_first %d / on-eq_first (G3-k2) %d / **eq_first + group %d**; abstained (no candidate) %d / %d / %d / %d." % (
            len(uid), *[sum(1 for i in uid if d[i]["verdict"] == "ANSWER") for d in (off2, qc2, un_eq, un_gp)], *[sum(1 for i in uid if not ents(d[i])) for d in (off2, qc2, un_eq, un_gp)]))
    out()

sec = "\n".join(OUT) + "\n"
for fn in ("summary_k2.md", "summary.md"):
    p = os.path.join(RES, fn)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8").read()
    k = s.find("\n# G3-k3 ")
    s = (s[:k] if k >= 0 else s.rstrip("\n")) + "\n\n" + sec
    open(p, "w", encoding="utf-8").write(s)
