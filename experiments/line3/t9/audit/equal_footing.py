"""T9 audit, question 1: grade Vera and the keyword baselines on equal footing, both ways (intra2, fulllead, n = 69;
cross2 on s3000 when its re-run exists).
(a) baselines at Vera's granularity: the candidate list = the distinct units (words) of the B1 / B2 sentences; hit = a
    normalised gold alternative inside ONE unit (scorer.hits_words, Vera's rule).  Units: MeCab (fugashi) surface tokens,
    and Vera's own RUN / WORD / CHAR tier units of those sentences (space.py), and all three tiers together.
(b) Vera at sentence granularity: every entry is replaced by its source sentences (source_sids recorded by
    rerun_ask.py / rerun_carry.py: path-edge evidence for layer 0 and carry, step sentences + word_sources for layer
    entries); hit = a normalised gold alternative inside the text of one of those sentences (scorer.hits_text).
    List size = distinct sentences.  Shown with all tiers and without the CHAR tier (CHAR entries cite hundreds of
    sentences, which makes the sentence list near the whole corpus).
usage: equal_footing.py  -> prints markdown, writes equal_footing.md"""
import glob, json, os, statistics, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
T9 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(T9)))
sys.path.insert(0, ROOT); sys.path.insert(0, T9); sys.path.insert(0, os.path.join(T9, "..", "bank2"))
import scorer as S                       # noqa: E402
import baselines as BL                   # noqa: E402
from verantyx.line3 import space as sp   # noqa: E402

RAW = os.path.join(HERE, "raw")
L = []


def out(s=""):
    L.append(s); print(s)


def med(x):
    return ("%.0f" % statistics.median(x)) if x else "-"


bank = {}
for l in open(os.path.join(T9, "..", "bank2", "bank2.tsv"), encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = dict(zip(BL.FIELDS, l.rstrip("\n").split("\t")))
    bank[r["id"]] = r
units = BL.load()
toks = BL.make_tokenizers()
index = {c: {(t, i): k for k, (t, i, _) in enumerate(u)} for c, u in units.items()}
titles = sorted({t for t, _, _ in units["s3000"] if len(t) >= 2}, key=len, reverse=True)

# Vera spaces (for sentence texts by sid and for tier units of a sentence)
FL = os.path.join(T9, "..", "bank2", "data", "fulllead_sents.jsonl")
S3 = os.path.join(T9, "..", "data", "S3000.jsonl")
spaces = {"fulllead": sp.build_space(sp.load_jsonl(FL))}
if glob.glob(os.path.join(RAW, "ask_s3000_*.jsonl")):
    spaces["s3000"] = sp.build_space(sp.load_jsonl(S3))
# baseline unit k -> Vera sid (fulllead: source title#i; s3000: row order)
sid_of = {}
for c, spc in spaces.items():
    if c == "fulllead":
        by_src = {src: i for i, (_t, src) in enumerate(spc.sentences)}
        sid_of[c] = [by_src["%s#%d" % (t, i)] for (t, i, _s) in units[c]]
        for k, (t, i, s) in enumerate(units[c]):          # same sentence text (baselines strip the 「。」)
            assert spc.sentences[sid_of[c][k]][0].rstrip("。").strip() == s, (t, i)
    else:
        sid_of[c] = list(range(len(units[c])))
        for k, (t, i, s) in enumerate(units[c]):
            assert spc.sentences[k][0].strip() == s
_gc = {}


def gold_count(corpus, gold):
    k = (corpus, gold)
    if k not in _gc:
        _gc[k] = sum(1 for t, _src in spaces[corpus].sentences if S.hits_text(gold, t))
    return _gc[k]


def chance(N, g, s):
    """P(a list of s sentences drawn at random from N holds one of the g gold sentences)."""
    p = 1.0
    for i in range(s):
        if N - i <= 0:
            return 1.0
        p *= max(0.0, (N - g - i) / (N - i))
    return 1.0 - p


import fugashi                                            # noqa: E402
tagger = fugashi.Tagger()


def mecab_units(text):
    return [w.surface for w in tagger(text) if w.surface.strip()]


def tier_units(corpus, k, tier):
    return list(spaces[corpus].tiers[tier].sentence_units[sid_of[corpus][k]])


# ---------------- (a) baselines at word granularity ----------------
KINDS = [("intra2", "fulllead"), ("cross2", "s3000")]
WORDKINDS = ["MeCab", "RUN", "WORD", "CHAR", "RUN+WORD+CHAR"]
out("## (a) Keyword baselines graded at Vera's granularity (gold inside ONE word of the candidate sentences' words)")
out()
out("Candidate list = the distinct words of the B1 / B2 sentences (MeCab surface tokens, or Vera's own tier units of "
    "those sentences); hit = gold inside one word (Vera's rule). Size = number of distinct words.")
out()
for kind, corpus in KINDS:
    if corpus not in spaces:
        continue
    ids = sorted(i for i, r in bank.items() if r["kind"] == kind)
    out("### %s (%s, n = %d)" % (kind, corpus, len(ids)))
    out()
    out("| baseline | sentence-level hits (T9 rule) | median sentences | chance at same sizes | " + " | ".join("%s words: hits (median size)" % w for w in WORDKINDS) + " |")
    out("|---|---|---|---|" + "---|" * len(WORDKINDS))
    for tn, tok in toks.items():
        for nm in ("B1", "B2"):
            sent_hits = 0; nsent = []; chs = 0.0
            wh = defaultdict(int); ws = defaultdict(list)
            for qid in ids:
                r = bank[qid]; u = units[corpus]
                best, c1 = BL.b1(u, tok(r["question"]))
                cs = c1 if nm == "B1" else BL.b2(u, c1, corpus, index[corpus], titles)
                sent_hits += any(S.hits_text(r["gold"], u[k][2]) for k in cs)
                nsent.append(len(cs)); chs += chance(len(u), gold_count(corpus, r["gold"]), len(cs))
                for wk in WORDKINDS:
                    words = set()
                    for k in cs:
                        if wk == "MeCab":
                            words.update(mecab_units(u[k][2]))
                        elif wk == "RUN+WORD+CHAR":
                            for t in ("RUN", "WORD", "CHAR"):
                                words.update(tier_units(corpus, k, t))
                        else:
                            words.update(tier_units(corpus, k, wk))
                    wh[wk] += S.hits_words(r["gold"], words)
                    ws[wk].append(len(words))
            out("| %s-%s | %d | %s | %.1f | %s |" % (nm, tn, sent_hits, med(nsent), chs, " | ".join("%d (%s)" % (wh[w], med(ws[w])) for w in WORDKINDS)))
    out()

# ---------------- (b) Vera at sentence granularity ----------------
SYS = {}   # name -> {id: [(tier, words, sids)]}
for p in sorted(glob.glob(os.path.join(RAW, "ask_*.jsonl"))):
    corpus = os.path.basename(p).split("_")[1]
    for l in open(p, encoding="utf-8"):
        r = json.loads(l); pre = r["preset"]
        flat = [(t, e["words"], e["sids"]) for t, d in r["layer0"].items() for e in d["entries"]]
        SYS.setdefault("flat-%s" % pre, {})[r["id"]] = (corpus, r["gold"], flat)
        for cfg, nm in (("path", "layers-path"), ("seatsPath", "layers-ssp")):
            up = [(t, e["words"], e["sids"]) for t, d in r["on"][cfg]["tiers"].items() for run in d["runs"] for e in run["entries"]]
            SYS.setdefault("%s-%s" % (nm, pre), {})[r["id"]] = (corpus, r["gold"], flat + up)
for p in sorted(glob.glob(os.path.join(RAW, "carry_*.jsonl"))):
    b = os.path.basename(p)[:-6].split("_")       # carry_<corpus>_<po>_<path|index>_<preset>
    corpus = b[1]
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        SYS.setdefault("carry-%s-%s-%s" % (b[2], b[3], b[4]), {})[r["id"]] = (corpus, r["gold"], [("RUN", e["words"], e["sids"]) for e in r["entries"]])


def order(n):
    return (n.split("-")[0] != "flat", n.split("-")[0] != "layers", n)


out("## (b) Vera graded at sentence granularity (gold inside the text of a source sentence of a candidate)")
out()
out("Word rule = T9 headline rule, recomputed on the re-run (must equal summary.md). Sentence rule: every entry -> its "
    "source sentences; size = distinct sentences per question (median over questions with >= 1 sentence). "
    "'no CHAR' drops the CHAR tier's entries (their source lists cover most of the corpus). 'best' maps each entry to "
    "only those of its source sentences that hold the most of its words (ties kept): the sentence a user would read the "
    "entry back to. 'chance' = expected hits of a list of the same number of sentences drawn at random from the corpus "
    "(per question, from the number of corpus sentences holding the gold), summed over questions.")
out()
for kind, corpus in KINDS:
    ids = sorted(i for i, r in bank.items() if r["kind"] == kind)
    names = sorted([n for n in SYS if any(i in SYS[n] for i in ids)], key=order)
    if not names:
        continue
    out("### %s (%s, n = %d)" % (kind, corpus, len(ids)))
    out()
    out("| system | n run | word rule hits | sentence rule hits (all tiers) | median sentences (all tiers) | chance hits, same sizes (all tiers) | sentence rule hits (no CHAR) | median sentences (no CHAR) | chance (no CHAR) | best-sentence rule hits (all tiers) | median sentences (best) | chance (best) |")
    out("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n in names:
        d = SYS[n]; run = [i for i in ids if i in d]
        wh = sh = shn = shb = 0; sz = []; szn = []; szb = []; ch = chn = chb = 0.0
        for i in run:
            corpus_, gold, ents = d[i]
            spc_ = spaces[corpus_]
            texts = spc_.sentences
            g = gold_count(corpus_, gold)
            wh += any(S.hits_words(gold, w) for _t, w, _s in ents)
            sa = {s for _t, _w, ss in ents for s in ss}
            sn = {s for t, _w, ss in ents if t != "CHAR" for s in ss}
            sb = set()
            for t, w, ss in ents:          # best sentence(s) of an entry: its source sentences holding most of its words
                if not ss:
                    continue
                tn = t.split("/")[0]
                ov = {s: len(set(w) & set(spc_.tiers[tn].sentence_units[s])) for s in ss}
                m = max(ov.values())
                sb.update(s for s, v in ov.items() if v == m)
            sh += any(S.hits_text(gold, texts[s][0]) for s in sa)
            shn += any(S.hits_text(gold, texts[s][0]) for s in sn)
            shb += any(S.hits_text(gold, texts[s][0]) for s in sb)
            N = len(texts)
            ch += chance(N, g, len(sa)); chn += chance(N, g, len(sn)); chb += chance(N, g, len(sb))
            if sa: sz.append(len(sa))
            if sn: szn.append(len(sn))
            if sb: szb.append(len(sb))
        out("| %s | %d | %d | %d | %s | %.1f | %d | %s | %.1f | %d | %s | %.1f |" % (n, len(run), wh, sh, med(sz), ch, shn, med(szn), chn,
                                                                         shb, med(szb), chb))
    out()
open(os.path.join(HERE, "equal_footing.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
