"""T11 summary: bank3 fulllead through ask(structure="combined"), graded per kind with the t9 scorer, B1/B2 (bank3/baselines.txt) alongside.
usage: summarize.py [PRESET ...]   (default: every results/ask_fulllead_<preset>.jsonl found)  ->  results/summary.md  (+ stdout)
Needs only the t9 scorer and the raw records; baselines are parsed from ../bank3/baselines.txt (no MeCab)."""
import json, os, re, statistics, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
L3 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(L3, "t9"))
import scorer as S                                         # noqa: E402

RES = os.path.join(HERE, "results")
BANK = os.path.join(L3, "bank3", "bank3.tsv")
BLOCKS = ["flat/RUN", "flat/WORD", "flat/CHAR", "layers", "window/plain", "window/window-evidence"]
FAM = {"flat": ["flat/RUN", "flat/WORD", "flat/CHAR"], "layers": ["layers"], "windows": ["window/plain", "window/window-evidence"]}
KINDS = ["two-facts", "paraphrase", "unknown-word", "summary-choice", "unans-kind"]
OUT = []


def out(s=""):
    OUT.append(s); print(s)


def med(x): return statistics.median(x) if x else None
def f1(x): return "-" if x is None else ("%.1f" % x)
def jl(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


bank = {}
for l in open(BANK, encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = dict(zip("id kind corpus subject question gold evidence notes audit".split(), l.rstrip("\n").split("\t")))
    bank[r["id"]] = r

# ---- baselines (bank3/baselines.txt) ------------------------------------------------------------------------------------------------
BL = {"mecab": {}, "bigram": {}}
tok = None
for l in open(os.path.join(L3, "bank3", "baselines.txt"), encoding="utf-8"):
    m = re.match(r"### tokenizer=(\w+)", l)
    if m:
        tok = m.group(1); continue
    m = re.match(r"  (mecab|bigram) (b3_\w+) (two-facts|paraphrase|unknown-word) B1=(\d) B2=(\d) \|c1\|=(\d+) \|c2\|=(\d+)", l)
    if m:
        BL[m.group(1)][m.group(2)] = dict(b1=int(m.group(4)), b2=int(m.group(5)), c1=int(m.group(6)), c2=int(m.group(7)))
    m = re.match(r"  (mecab|bigram) (b3_sc\d+) summary-choice option-lookup=([\d.]+)", l)
    if m:
        BL[m.group(1)][m.group(2)] = dict(ol=float(m.group(3)))
    m = re.match(r"  (mecab|bigram) (b3_uk\d+) unans returned=(\d+)", l)
    if m:
        BL[m.group(1)][m.group(2)] = dict(ret=int(m.group(3)))


def bl(tok, kind, key):
    ids = [i for i in bank if bank[i]["kind"] == kind and bank[i]["corpus"] == "fulllead"]
    return sum(BL[tok][i][key] for i in ids if i in BL[tok]), len(ids)


def hits(e, gold): return S.hits_words(gold, e["words"])


def gold_text(r):
    """gold alternatives to look for: summary-choice 'LETTER|text' -> the option text (the letter cannot be in a candidate)."""
    g = bank[r["id"]]["gold"]
    return g.split("|", 1)[1] if r["kind"] == "summary-choice" else g


def grade(r):
    ents = r["answer"]["entries"]
    if r["kind"] == "unans-kind":
        return "none" if not ents else ("single" if r["verdict"] == "ANSWER" else "list")
    if not ents:
        return "none"
    h = any(hits(e, gold_text(r)) for e in ents)
    if r["verdict"] == "ANSWER":
        return "single_right" if h else "single_wrong"
    return "list_gold" if h else "list_nogold"


def first_gold(r):
    seen = Counter()
    for i, e in enumerate(r["answer"]["entries"], 1):
        seen[e["block"]] += 1
        if hits(e, gold_text(r)):
            return i, e["block"], seen[e["block"]]
    return None


def blocks_with_gold(r):
    return {e["block"] for e in r["answer"]["entries"] if hits(e, gold_text(r))}


def fams_with_gold(r):
    b = blocks_with_gold(r)
    return {f for f, bs in FAM.items() if b & set(bs)}


SID = {}
for _i, _l in enumerate(open(os.path.join(L3, "bank2", "data", "fulllead_sents.jsonl"), encoding="utf-8")):
    SID[json.loads(_l)["source"]] = _i                      # 'title#i' -> sentence id (the order of the file = the space's sids)


def ev_sids(r):
    return {SID[x] for x in bank[r["id"]]["evidence"].split(";") if x in SID}


def cites(r, fam=None):
    """(gold string in a sentence the entry cites, an evidence sentence of the bank cited) over the entries of the family (None = all)."""
    txt = {c["sid"]: c["text"] for c in r["answer"]["cited"]}
    ev = ev_sids(r)
    g = ev_ = False
    for e in r["answer"]["entries"]:
        if fam and e["block"] not in FAM[fam]:
            continue
        if ev & set(e["source_sids"]):
            ev_ = True
        if any(S.hits_text(gold_text(r), txt[s]) for s in e["source_sids"] if s in txt):
            g = True
    return g, ev_


def options(q):
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"([ABC])\.\s*(.+?)(?=\s+[ABC]\.|$)", q)}


def block_sizes(r):
    return Counter(e["block"] for e in r["answer"]["entries"])


for P in (sys.argv[1:] or [p for p in ("fast", "standard") if os.path.exists(os.path.join(RES, "ask_fulllead_%s.jsonl" % p))]):
    recs = {r["id"]: r for r in jl(os.path.join(RES, "ask_fulllead_%s.jsonl" % P)) if "error" not in r}
    errs = [r for r in jl(os.path.join(RES, "ask_fulllead_%s.jsonl" % P)) if "error" in r]
    ids = {k: sorted(i for i in recs if recs[i]["kind"] == k) for k in KINDS}
    expect = {k: sum(1 for b in bank.values() if b["kind"] == k and b["corpus"] == "fulllead") for k in KINDS}
    out("# T11 -- bank3 fulllead through ask(structure=\"combined\"), %s" % P)
    out()
    out("Records: %d questions (%s); worker errors: %d. s3000 items (compare 14, unans-kind 1) are NOT run: they need an S3000 ordered cache that does not exist." % (
        len(recs), ", ".join("%s %d/%d" % (k, len(ids[k]), expect[k]) for k in KINDS), len(errs)))
    heads = sorted({r.get("head") for r in recs.values()})
    out("Code: snapshot of line3 HEAD %s (see README for md5s)." % ", ".join(h[:8] if h else "?" for h in heads))
    out()
    # ------------------------------------------------------------------------------------------------ headline per kind
    out("## Per kind (gold = any gold alternative in a candidate word of ONE entry, t9 scorer; summary-choice: the option text after 'LETTER|')")
    out()
    out("| kind | n | gold in a candidate | single right / wrong | list with gold / without | no candidate | list size median / mean / max (lists >= 2) | first-gold position overall median / max | within its block median / max | B1 mecab / bigram | B2 mecab / bigram |")
    out("|---|---|---|---|---|---|---|---|---|---|---|")
    for k in KINDS[:4]:
        rs = [recs[i] for i in ids[k]]
        if not rs:
            continue
        cnt = Counter(grade(r) for r in rs)
        sizes = [len(r["answer"]["entries"]) for r in rs if len(r["answer"]["entries"]) >= 2]
        fg = [first_gold(r) for r in rs]; fg = [x for x in fg if x]
        po, pb = [x[0] for x in fg], [x[2] for x in fg]
        gold = cnt["single_right"] + cnt["list_gold"]
        if k == "summary-choice":
            b1 = "option-lookup %.1f/%d (mecab), %.1f/%d (bigram)" % (sum(BL["mecab"][i]["ol"] for i in ids[k]), len(ids[k]), sum(BL["bigram"][i]["ol"] for i in ids[k]), len(ids[k]))
            b2 = "-"
        else:
            a, n = bl("mecab", k, "b1"); b, _ = bl("bigram", k, "b1"); c, _ = bl("mecab", k, "b2"); d, _ = bl("bigram", k, "b2")
            b1 = "%d (%d%%) / %d (%d%%)" % (a, round(100 * a / n), b, round(100 * b / n)); b2 = "%d (%d%%) / %d (%d%%)" % (c, round(100 * c / n), d, round(100 * d / n))
        out("| %s | %d | %d (%d%%) | %d / %d | %d / %d | %d | %s / %s / %s | %s / %s | %s / %s | %s | %s |" % (
            k, len(rs), gold, round(100 * gold / len(rs)), cnt["single_right"], cnt["single_wrong"], cnt["list_gold"], cnt["list_nogold"], cnt["none"],
            f1(med(sizes)), f1(statistics.mean(sizes)) if sizes else "-", max(sizes) if sizes else "-",
            f1(med(po)), max(po) if po else "-", f1(med(pb)), max(pb) if pb else "-", b1, b2))
    out()
    # unans
    rs = [recs[i] for i in ids["unans-kind"]]
    cnt = Counter(grade(r) for r in rs)
    sizes = [len(r["answer"]["entries"]) for r in rs]
    out("**Comparability.** The grade above is the t9 rule: the gold must sit inside ONE WORD of an entry (entries are sets of short corpus words). The baselines B1/B2 are graded 'gold in a candidate SENTENCE' (a far easier unit for phrase golds such as 鳳珠郡能登町 or a whole option text), and return 1-3 sentences, whereas a combined list has tens of entries. So the table is NOT apples to apples; the nearer comparison is the looser sentence-citing table below (gold in a sentence cited by a flat or window entry), which is still a list of tens against B1/B2's 1-3 sentences.")
    out()
    out("**unans-kind (fulllead, n = %d)**: abstained (no candidate) %d / list %d / single (ANSWER, wrong by definition) %d; list size median %s max %s. B1/B2 baseline: candidates returned for every one (keyword lookup never abstains, mecab %d/%d)." % (
        len(rs), cnt["none"], cnt["list"], cnt["single"], f1(med(sizes)), max(sizes) if sizes else "-",
        sum(1 for i in ids["unans-kind"] if BL["mecab"][i]["ret"] > 0), len(ids["unans-kind"])))
    out()
    out("unknown-word extra baseline: B1 after NFKC + MeCab-reading normalisation 17/18 (94%) mecab, 14/18 bigram (baselines.txt).")
    out()
    out("summary-choice: **the model cannot pick the letter** -- ask() returns candidate word sets from the corpus (no option is scored, no letter is produced), so 'letter correct' is not defined for any system here. The hit above only says the gold option's text is in a candidate. Discrimination (the user sees the options in the question and could compare): see the per-item rows below; a candidate that also holds a wrong option's text does not discriminate.")
    out()
    # ------------------------------------------------------------------------------------------------ per origin
    out("## Gold per origin (questions whose list holds the gold in an entry of that origin)")
    out()
    out("| kind | n | any | " + " | ".join(FAM) + " | " + " | ".join(BLOCKS) + " | only windows (no flat/layers entry holds it) | only flat (no layers/window) |")
    out("|---|---|---|" + "---|" * (len(FAM) + len(BLOCKS) + 2))
    for k in KINDS[:4]:
        rs = [recs[i] for i in ids[k]]
        if not rs:
            continue
        bw = [blocks_with_gold(r) for r in rs]; fw = [fams_with_gold(r) for r in rs]
        out("| %s | %d | %d | %s | %s | %d | %d |" % (k, len(rs), sum(1 for b in bw if b), " | ".join(str(sum(1 for f in fw if fam in f)) for fam in FAM),
            " | ".join(str(sum(1 for b in bw if blk in b)) for blk in BLOCKS), sum(1 for f in fw if f == {"windows"}), sum(1 for f in fw if f == {"flat"})))
    out()
    out("## Looser view: the sentences an entry CITES (source_sids), not its words (flat and windows only)")
    out()
    out("The primary grade needs the gold inside ONE word of an entry; entries are sets of short corpus words (a phrase gold such as 鳳珠郡能登町 is rarely one word), so a list can point at the evidence sentence without holding the gold string. Here: 'gold in a cited sentence' = a gold alternative is a substring of a sentence cited by some entry of the family (t9 normalisation); 'evidence cited' = some entry cites a sentence of the bank's evidence column; 'all evidence' = every evidence sentence is cited (flat or windows union). NOT the t9 rule; for reading the headroom only. The layers are left out: each layers entry cites a corpus-wide union (median ~255 of 592 sentences), so citing says nothing there.")
    out()
    out("| kind | n | gold in a cited sentence: flat | windows | flat or windows | evidence cited: flat | windows | flat or windows | all evidence cited (flat+windows) | distinct sentences cited per question flat / windows: median, max |")
    out("|---|---|---|---|---|---|---|---|---|---|")
    for k in KINDS[:4]:
        rs = [recs[i] for i in ids[k]]
        if not rs:
            continue
        c = {f: [cites(r, f) for r in rs] for f in ("flat", "windows")}
        def cs(r, f):
            return {x for e in r["answer"]["entries"] if e["block"] in FAM[f] for x in e["source_sids"]}
        allev = sum(1 for r in rs if ev_sids(r) <= (cs(r, "flat") | cs(r, "windows")))
        both = lambda j: sum(1 for a_, b_ in zip(c["flat"], c["windows"]) if a_[j] or b_[j])
        out("| %s | %d | %d | %d | %d | %d | %d | %d | %d | %s, %d / %s, %d |" % (k, len(rs), sum(1 for x in c["flat"] if x[0]), sum(1 for x in c["windows"] if x[0]), both(0),
            sum(1 for x in c["flat"] if x[1]), sum(1 for x in c["windows"] if x[1]), both(1), allev,
            f1(med([len(cs(r, "flat")) for r in rs])), max(len(cs(r, "flat")) for r in rs), f1(med([len(cs(r, "windows")) for r in rs])), max(len(cs(r, "windows")) for r in rs)))
    out()
    # ------------------------------------------------------------------------------------------------ verdict / lists
    out("## Verdict and list shape per kind")
    out()
    out("| kind | n | ANSWER | CHOICE | UNKNOWN (no candidate) | entries total median / max | entries per block (median over questions that list it) |")
    out("|---|---|---|---|---|---|---|")
    for k in KINDS:
        rs = [recs[i] for i in ids[k]]
        if not rs:
            continue
        vc = Counter(r["verdict"] for r in rs)
        tot = [len(r["answer"]["entries"]) for r in rs]
        pb = []
        for blk in BLOCKS:
            xs = [block_sizes(r)[blk] for r in rs if block_sizes(r)[blk]]
            pb.append("%s %s (%d q)" % (blk.replace("window/", "w/"), f1(med(xs)), len(xs)))
        out("| %s | %d | %d | %d | %d | %s / %s | %s |" % (k, len(rs), vc["ANSWER"], vc["CHOICE"], len(rs) - vc["ANSWER"] - vc["CHOICE"], f1(med(tot)), max(tot), "; ".join(pb)))
    out()
    # ------------------------------------------------------------------------------------------------ per-item tables
    def item_table(kind, extra=False):
        out("| id | B1 m/b | B2 m/b | verdict | entries | per block (RUN/WORD/CHAR/lay/wP/wE) | gold | first gold: pos (block, in-block) | blocks holding gold | gold in a cited sentence / evidence cited (flat+windows) | s |")
        out("|---|---|---|---|---|---|---|---|---|---|---|")
        for i in ids[kind]:
            r = recs[i]; g = grade(r); fg = first_gold(r); bs = block_sizes(r)
            b1 = "%d/%d" % (BL["mecab"][i]["b1"], BL["bigram"][i]["b1"]); b2 = "%d/%d" % (BL["mecab"][i]["b2"], BL["bigram"][i]["b2"])
            cf, cw = cites(r, "flat"), cites(r, "windows")
            cg, ce = cf[0] or cw[0], cf[1] or cw[1]
            out("| %s | %s | %s | %s | %d | %s | %s | %s | %s | %s / %s | %.0f |" % (
                i, b1, b2, r["verdict"], len(r["answer"]["entries"]), "/".join(str(bs[b]) for b in BLOCKS),
                {"single_right": "single right", "single_wrong": "single WRONG", "list_gold": "list+gold", "list_nogold": "list, no gold", "none": "none"}[g],
                "%d (%s, %d)" % fg if fg else "-", ", ".join(b.replace("window/", "w/") for b in BLOCKS if b in blocks_with_gold(r)) or "-", "yes" if cg else "no", "yes" if ce else "no", r["ms"] / 1000))
        out()
    out("## Per item: paraphrase (the kind with headroom: B1/B2 30-60%)")
    out()
    item_table("paraphrase")
    out("## Per item: two-facts")
    out()
    item_table("two-facts")
    out("## Per item: unknown-word")
    out()
    item_table("unknown-word")
    out("## Per item: summary-choice")
    out()
    out("| id | gold | options whose text is in some candidate | B-option-lookup m/b | verdict | entries | gold option in a candidate (blocks) |")
    out("|---|---|---|---|---|---|---|")
    disc = 0
    for i in ids["summary-choice"]:
        r = recs[i]; op = options(r["question"]); gl = bank[i]["gold"].split("|")[0]
        inc = sorted(L for L, t in op.items() if any(S.hits_words(t, e["words"]) for e in r["answer"]["entries"]))
        disc += inc == [gl]
        out("| %s | %s | %s | %.2f/%.2f | %s | %d | %s |" % (i, gl, ",".join(inc) or "-", BL["mecab"][i]["ol"], BL["bigram"][i]["ol"], r["verdict"], len(r["answer"]["entries"]),
            ", ".join(sorted(blocks_with_gold(r))) or "-"))
    out()
    out("Items where only the gold option's text is in a candidate: %d / %d. The letter is never produced." % (disc, len(ids["summary-choice"])))
    out()
    out("## Per item: unans-kind")
    out()
    out("| id | outcome | entries | per block (RUN/WORD/CHAR/lay/wP/wE) | what is missing (bank notes) | mecab B1 returned |")
    out("|---|---|---|---|---|---|")
    for i in ids["unans-kind"]:
        r = recs[i]; bs = block_sizes(r)
        out("| %s | %s | %d | %s | %s | %d |" % (i, grade(r), len(r["answer"]["entries"]), "/".join(str(bs[b]) for b in BLOCKS), bank[i]["notes"], BL["mecab"][i]["ret"]))
    out()
    out("## Per-source header: how many sources list something, answerable (62) against unans-kind (14)")
    out()
    out("| source | answerable: listed | unans-kind: listed | typed abstentions when not listed (answerable / unans) |")
    out("|---|---|---|---|")
    ans_ids = [i for k in KINDS[:4] for i in ids[k]]
    for b in BLOCKS:
        def cnt(idl):
            lst, kd = 0, Counter()
            for i in idl:
                h = next(x for x in recs[i]["answer"]["header"] if x["source"] == b)
                if h["listed"]:
                    lst += 1
                else:
                    kd[h["kind"]] += 1
            return lst, kd
        la, ka = cnt(ans_ids); lu, ku = cnt(ids["unans-kind"])
        out("| %s | %d / %d | %d / %d | %s / %s |" % (b, la, len(ans_ids), lu, len(ids["unans-kind"]), ", ".join("%s %d" % kv for kv in sorted(ka.items())) or "-", ", ".join("%s %d" % kv for kv in sorted(ku.items())) or "-"))
    out()
    out("unans-kind questions where EVERY source lists nothing: %d / %d; where at least one source abstains with a type: %d / %d." % (
        sum(1 for i in ids["unans-kind"] if all(h["listed"] == 0 for h in recs[i]["answer"]["header"])), len(ids["unans-kind"]),
        sum(1 for i in ids["unans-kind"] if any(h["listed"] == 0 for h in recs[i]["answer"]["header"])), len(ids["unans-kind"])))
    out()
    # ------------------------------------------------------------------------------------------------ time
    ms = [r["ms"] / 1000 for r in recs.values()]
    ld = [r["load1"] for r in recs.values()]
    out("## Time (%s)" % P)
    out()
    out("seconds per question (end to end ask(structure=\"combined\"), several questions in parallel on a loaded machine): median %.0f, mean %.0f, max %.0f, total CPU-ish sum %.0f s over %d questions; 1-min load at the question ends: median %.1f, max %.1f." % (
        med(ms), statistics.mean(ms), max(ms), sum(ms), len(ms), med(ld), max(ld)))
    out()
    open(os.path.join(RES, "summary.md" if len(sys.argv) <= 1 else "summary_%s.md" % "_".join(sys.argv[1:])), "w", encoding="utf-8").write("\n".join(OUT) + "\n")
    break
