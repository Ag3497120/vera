#!/usr/bin/env python3
"""Trivial keyword baselines for bank 3 (audited). Adapted from bank2/baselines.py (same B1/B2, same tokenizers).

B1 keyword lookup: score every unit of the question's corpus by the number of distinct question terms it
   contains (substring match); candidates = all units with the top score (ties kept).
B2 two-hop keyword: B1 candidates plus
   fulllead: the next sentence of the same article for each candidate sentence;
   s3000:    the sentence of every article whose title (len>=2) occurs in a candidate sentence.
Units: fulllead = every sentence of every article (lead split on 「。」, 0-based); s3000 = each article's sentence.
Tokenizers: MeCab via fugashi (content words, question words removed) and character bigrams.

Per kind:
  two-facts / paraphrase / unknown-word: gold-in-candidate (any gold alternative in a candidate unit);
     two-facts also: both evidence sentences among the B2 candidates.
  compare: (a) gold article's sentence among B1 candidates; (b) lookup+year solver: split the question's
     「XとYのうち」 at each 「と」, run B1 on both halves, keep the split with the best weaker half, take the
     first year stated in each half's top candidate (first in unit order on ties), answer the article with the
     earlier year (all items ask 早い); (c) position heuristic "answer the first-described entity".
  summary-choice: option lookup: units = sentences of the article whose title occurs in the question; each option
     is scored by the best fraction of its terms found in one sentence; pick the max (ties -> expected 1/k).
     Also always-A / always-B / always-C.
  unans-kind: keyword lookup never abstains (candidate set non-empty for every item).
  unknown-word, diagnostic: B1 with the subject surface deleted from the question (is the subject needed?).
  unknown-word, extra B1-kana: question and every unit normalised NFKC, then rewritten as the concatenation of
     MeCab katakana readings (tokens without a reading keep their surface; spaces dropped). B1 is then run on
     these kana strings, with (i) MeCab content-word readings and (ii) bigrams of the kana question as terms.
Run with /Users/motonisihikoudai/vera-wiring/env/bin/python (fugashi + unidic-lite).
"""
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if (HERE / "bank3.tsv").exists() and (HERE.parent / "data" / "S3000.jsonl").exists():
    BANK, ROOT, OUTF = HERE / "bank3.tsv", HERE.parent / "data", HERE / "baselines.txt"
else:
    BANK, ROOT, OUTF = HERE / "bank3_audited.tsv", HERE.parent, HERE / "baselines3.txt"

QWORDS = ["何", "なに", "なん", "どこ", "いつ", "誰", "だれ", "どの", "どのよう", "どのような",
          "どんな", "どう", "いくら", "いくつ", "何年", "何月", "何日", "何色", "何人", "何位",
          "何柱", "何代目", "何メートル", "何機", "ですか", "ますか", "でしたか", "ましたか",
          "ですか", "か", "は", "の", "を", "に", "で", "が", "と", "も", "へ", "から", "まで",
          "する", "れる", "られる", "いる", "ある", "なる", "こと", "もの", "呼ぶ", "いう",
          "どちら", "うち", "正しい", "どれ"]
QSTRIP = ["ですか", "ましたか", "でしたか", "ますか", "どのような", "どのように", "どのよう",
          "どんな", "どこ", "いつ", "誰", "何", "どの", "どう", "いくら", "どちら", "どれ"]
KINDS = ["two-facts", "paraphrase", "unknown-word", "compare", "summary-choice", "unans-kind"]


def sentences(text):
    return [p.strip() for p in text.split("。") if p.strip()]


def load():
    units = {"fulllead": [], "s3000": []}  # (title, idx, text)
    with open(ROOT / "S300_fulllead.jsonl", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            for i, s in enumerate(sentences(d["text"])):
                units["fulllead"].append((d["title"], i, s))
    with open(ROOT / "S3000.jsonl", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            units["s3000"].append((d["title"], 0, d["sent"].strip()))
    return units


import fugashi  # noqa: E402  (required: this bank's baselines are defined with MeCab)
TAGGER = fugashi.Tagger()


def mecab(q):
    out = set()
    for w in TAGGER(q):
        if w.feature.pos1 in ("名詞", "動詞", "形容詞", "形状詞") or \
                (w.feature.pos1 not in ("助詞", "助動詞", "代名詞", "補助記号") and len(w.surface) > 1):
            s = w.surface
            if s in QWORDS or len(s.strip()) == 0:
                continue
            out.add(s)
    return out


def bigram(q):
    for w in QSTRIP:
        q = q.replace(w, " ")
    for ch in "「」、？?。":
        q = q.replace(ch, " ")
    return {q[i:i + 2] for i in range(len(q) - 1) if " " not in q[i:i + 2]}


TOKS = {"mecab": mecab, "bigram": bigram}


def kana(s):
    s = unicodedata.normalize("NFKC", s)
    return "".join((w.feature.kana if w.feature.kana not in (None, "*") else w.surface)
                   for w in TAGGER(s) if w.surface.strip())


def mecab_kana(q):
    out = set()
    for w in TAGGER(unicodedata.normalize("NFKC", q)):
        if w.surface in QWORDS or not w.surface.strip():
            continue
        if w.feature.pos1 in ("名詞", "動詞", "形容詞", "形状詞") or \
                (w.feature.pos1 not in ("助詞", "助動詞", "代名詞", "補助記号") and len(w.surface) > 1):
            out.add(w.feature.kana if w.feature.kana not in (None, "*") else w.surface)
    return out


def b1(units, terms):
    best, cands = -1, []
    for k, (_, _, s) in enumerate(units):
        sc = sum(1 for t in terms if t in s)
        if sc > best:
            best, cands = sc, [k]
        elif sc == best:
            cands.append(k)
    return best, cands


def b2(units, cands, corpus, index, titles_by_len):
    out = set(cands)
    for k in cands:
        title, i, s = units[k]
        if corpus == "fulllead":
            nxt = index.get((title, i + 1))
            if nxt is not None:
                out.add(nxt)
        else:
            for t in titles_by_len:
                if t != title and t in s:
                    out.add(index[(t, 0)])
    return sorted(out)


def read_bank():
    with open(BANK, encoding="utf-8", newline="") as f:
        rd = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        hdr = [h.lstrip("#") for h in next(rd)]
        return [dict(zip(hdr, v)) for v in rd if v]


def ev_keys(r):
    out = []
    for e in r["evidence"].split(";"):
        if r["corpus"] == "s3000":
            out.append((e, 0))
        else:
            t, i = e.rsplit("#", 1)
            out.append((t, int(i)))
    return out


def first_year(s):
    m = re.search(r"(1[0-9]{3}|20[0-9]{2})年", s)
    return int(m.group(1)) if m else None


def compare_solver(r, units, tok):
    left = r["question"].split("のうち")[0]
    best = None
    for m in re.finditer("と", left):
        a, b = left[:m.start()].strip("、 "), left[m.end():].strip("、 ")
        if not a or not b:
            continue
        sa, ca = b1(units, tok(a))
        sb, cb = b1(units, tok(b))
        key = min(sa, sb)
        if best is None or key > best[0]:
            best = (key, ca, cb)
    if best is None:
        return None
    _, ca, cb = best
    ta, tb = units[ca[0]], units[cb[0]]
    ya, yb = first_year(ta[2]), first_year(tb[2])
    if ya is None or yb is None or ya == yb:
        return None
    return ta[0] if ya < yb else tb[0]


def sc_solver(r, units, tok):
    q = r["question"]
    marks = list(re.finditer(r"(?<!\S)([ABC])\.\s*", q))
    opts = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(q)
        opts[m.group(1)] = q[m.end():end].strip()
    stem = q[:marks[0].start()]
    titles = {t for t, _, _ in units}
    subj = max((t for t in titles if t in stem), key=len, default=None)
    sents = [s for t, _, s in units if t == subj]
    scores = {}
    for L, o in opts.items():
        terms = tok(o)
        scores[L] = max((sum(1 for t in terms if t in s) / max(1, len(terms)) for s in sents), default=0)
    top = max(scores.values())
    winners = [L for L, v in scores.items() if v == top]
    letter = r["gold"].split("|")[0]
    return (1.0 / len(winners)) if letter in winners else 0.0, winners


def main():
    units = load()
    rows = read_bank()
    index = {c: {(t, i): k for k, (t, i, _) in enumerate(u)} for c, u in units.items()}
    titles = sorted({t for t, _, _ in units["s3000"] if len(t) >= 2}, key=len, reverse=True)
    L = ["# Trivial keyword baselines for bank 3 (see baselines docstring)",
         f"# bank: {BANK.name} ({len(rows)} rows); units: fulllead sentences={len(units['fulllead'])}, "
         f"s3000 sentences={len(units['s3000'])}", ""]
    per = []
    summary = {}
    for tname, tok in TOKS.items():
        st = defaultdict(lambda: defaultdict(float))
        for r in rows:
            k, u = r["kind"], units[r["corpus"]]
            s = st[k]
            s["n"] += 1
            golds = [g for g in r["gold"].split("|") if g]
            terms = tok(r["question"])
            best, c1 = b1(u, terms)
            c2 = b2(u, c1, r["corpus"], index[r["corpus"]], titles)
            s["c1"] += len(c1)
            s["c2"] += len(c2)
            s["ret"] += bool(c1)
            if k in ("two-facts", "paraphrase", "unknown-word"):
                h1 = any(g in u[x][2] for x in c1 for g in golds)
                h2 = any(g in u[x][2] for x in c2 for g in golds)
                s["b1"] += h1
                s["b2"] += h2
                extra = ""
                if k == "two-facts":
                    ek = {index[r["corpus"]][e] for e in ev_keys(r)}
                    both = ek <= set(c2)
                    s["both2"] += both
                    extra = f" both-ev-in-B2={int(both)}"
                per.append(f"  {tname} {r['id']} {k} B1={int(h1)} B2={int(h2)} |c1|={len(c1)} |c2|={len(c2)} top={best}{extra}")
            elif k == "compare":
                gk = index["s3000"][(r["gold"], 0)]
                h1 = gk in c1
                ans = compare_solver(r, u, tok)
                ok = ans == r["gold"]
                first = ev_keys(r)[0][0] == r["gold"]
                s["b1"] += h1
                s["solve"] += ok
                s["first"] += first
                per.append(f"  {tname} {r['id']} compare gold-sent-in-B1={int(h1)} lookup+year={int(ok)} (answered {ans}) first-described={int(first)}")
            elif k == "summary-choice":
                sc, win = sc_solver(r, units["fulllead"], tok)
                s["solve"] += sc
                letter = r["gold"].split("|")[0]
                for X in "ABC":
                    s["always" + X] += letter == X
                per.append(f"  {tname} {r['id']} summary-choice option-lookup={sc:.2f} (max options {''.join(win)}, gold {letter})")
            else:
                per.append(f"  {tname} {r['id']} unans returned={len(c1)} top={best}")
        summary[tname] = st
        L.append(f"### tokenizer={tname}")
        for k in KINDS:
            s = st.get(k)
            if not s:
                continue
            n = int(s["n"])
            if k in ("two-facts", "paraphrase", "unknown-word"):
                line = (f"{k:15s} n={n:3d}  B1 {int(s['b1'])}/{n} ({100*s['b1']/n:.0f}%)  "
                        f"B2 {int(s['b2'])}/{n} ({100*s['b2']/n:.0f}%)  mean|cand| {s['c1']/n:.1f}/{s['c2']/n:.1f}")
                if k == "two-facts":
                    line += f"  both-evidence-in-B2 {int(s['both2'])}/{n}"
            elif k == "compare":
                line = (f"{k:15s} n={n:3d}  gold-sentence-in-B1 {int(s['b1'])}/{n}  lookup+year solver "
                        f"{int(s['solve'])}/{n} ({100*s['solve']/n:.0f}%)  first-described {int(s['first'])}/{n}  chance 50%")
            elif k == "summary-choice":
                line = (f"{k:15s} n={n:3d}  option-lookup {s['solve']:.1f}/{n} ({100*s['solve']/n:.0f}%)  "
                        f"always-A {int(s['alwaysA'])}/{n} always-B {int(s['alwaysB'])}/{n} always-C {int(s['alwaysC'])}/{n}  chance 33%")
            else:
                line = f"{k:15s} n={n:3d}  candidates returned for {int(s['ret'])}/{n} (keyword lookup never abstains)"
            L.append(line)
        L.append("")

    # unknown-word: B1 on kana-normalised question and units
    L.append("### unknown-word: B1 after NFKC + MeCab-reading (kana) normalisation of question and units")
    kunits = {c: [(t, i, kana(s)) for t, i, s in u] for c, u in units.items()}
    uw = [r for r in rows if r["kind"] == "unknown-word"]
    ktoks = {"mecab-kana": mecab_kana, "bigram-kana": lambda q: bigram(kana(q))}
    for kname, ktok in ktoks.items():
        hit = 0
        for r in uw:
            golds = [kana(g) for g in r["gold"].split("|") if g]
            best, c1 = b1(kunits[r["corpus"]], ktok(r["question"]))
            h = any(g in kunits[r["corpus"]][x][2] for x in c1 for g in golds)
            hit += h
            per.append(f"  {kname} {r['id']} unknown-word B1kana={int(h)} |c1|={len(c1)} top={best} surface={r['subject']}")
        L.append(f"{kname:12s} n={len(uw)}  B1-kana {hit}/{len(uw)} ({100*hit/len(uw):.0f}%)")
    # diagnostic: is the altered subject needed at all? B1 with the subject surface deleted from the question
    for tname, tok in TOKS.items():
        hit = 0
        for r in uw:
            golds = [g for g in r["gold"].split("|") if g]
            best, c1 = b1(units[r["corpus"]], tok(r["question"].replace(r["subject"], " ")))
            h = any(g in units[r["corpus"]][x][2] for x in c1 for g in golds)
            hit += h
            per.append(f"  {tname}-nosubject {r['id']} unknown-word B1-without-subject={int(h)} |c1|={len(c1)} top={best}")
        L.append(f"{tname + '-nosubj':12s} n={len(uw)}  B1 with the subject surface deleted {hit}/{len(uw)} ({100*hit/len(uw):.0f}%)")
    L.append("")
    L.append("per-item:")
    L += per
    OUTF.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(l for l in L if not l.startswith("  ")))


if __name__ == "__main__":
    main()
