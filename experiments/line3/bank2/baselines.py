#!/usr/bin/env python3
"""Trivial keyword baselines for bank2.tsv (final bank: audited round 1 + audited round 2).

B1 keyword lookup: score every unit of the question's corpus by the number of distinct
   question terms it contains (substring match); candidates = all units with the top score
   (ties kept). Success = any gold alternative occurs in a candidate.
B2 two-hop keyword: B1 candidates plus
   fulllead: the next sentence of the same article for each candidate sentence;
   s3000:    the sentence of every article whose title (len>=2) occurs in a candidate sentence.

Units: fulllead = every sentence of every article (lead split on 「。」); s3000 = each article's
first sentence. Two tokenizers: MeCab via fugashi (content words, question words removed) when
importable, and character bigrams of the question minus question-word characters.
Run with /Users/motonisihikoudai/vera-wiring/env/bin/python for MeCab.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent / "data"
FIELDS = ["id", "kind", "corpus", "subject", "question", "gold", "evidence", "audit"]

QWORDS = ["何", "なに", "なん", "どこ", "いつ", "誰", "だれ", "どの", "どのよう", "どのような",
          "どんな", "どう", "いくら", "いくつ", "何年", "何月", "何日", "何色", "何人", "何位",
          "何柱", "何代目", "何メートル", "何機", "ですか", "ますか", "でしたか", "ましたか",
          "ですか", "か", "は", "の", "を", "に", "で", "が", "と", "も", "へ", "から", "まで",
          "する", "れる", "られる", "いる", "ある", "なる", "こと", "もの", "呼ぶ", "いう"]
QSTRIP = ["ですか", "ましたか", "でしたか", "ますか", "どのような", "どのように", "どのよう",
          "どんな", "どこ", "いつ", "誰", "何", "どの", "どう", "いくら"]


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


def make_tokenizers():
    toks = {}
    try:
        import fugashi
        tagger = fugashi.Tagger()

        def mecab(q):
            out = set()
            for w in tagger(q):
                if w.feature.pos1 in ("名詞", "動詞", "形容詞", "形状詞") or \
                        (w.feature.pos1 not in ("助詞", "助動詞", "代名詞", "補助記号") and len(w.surface) > 1):
                    s = w.surface
                    if s in QWORDS or len(s.strip()) == 0:
                        continue
                    out.add(s)
            return out
        toks["mecab"] = mecab
    except Exception as exc:  # pragma: no cover
        print(f"# fugashi unavailable ({exc}); MeCab baseline skipped", file=sys.stderr)

    def bigram(q):
        for w in QSTRIP:
            q = q.replace(w, " ")
        q = q.replace("「", " ").replace("」", " ").replace("、", " ")
        return {q[i:i + 2] for i in range(len(q) - 1) if " " not in q[i:i + 2]}
    toks["bigram"] = bigram
    return toks


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


def run(bank_file, units, toks, lines, label="all", keep=lambda r: True):
    rows = []
    with open(bank_file, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            r = dict(zip(FIELDS, line.rstrip("\n").split("\t")))
            if keep(r):
                rows.append(r)
    index = {c: {(t, i): k for k, (t, i, _) in enumerate(u)} for c, u in units.items()}
    titles = sorted({t for t, _, _ in units["s3000"] if len(t) >= 2}, key=len, reverse=True)
    lines.append(f"## {bank_file.name} [{label}]  ({len(rows)} items)")
    per_item = []
    for tname, tok in toks.items():
        stats = defaultdict(lambda: {"n": 0, "b1": 0, "b2": 0, "c1": 0, "c2": 0, "ret1": 0, "ret2": 0})
        for r in rows:
            u = units[r["corpus"]]
            terms = tok(r["question"])
            best, c1 = b1(u, terms)
            c2 = b2(u, c1, r["corpus"], index[r["corpus"]], titles)
            golds = [g for g in r["gold"].split("|") if g]
            key = r["kind"] if r["kind"] != "unans" else f"unans-{r['corpus']}"
            st = stats[key]
            st["n"] += 1
            st["c1"] += len(c1)
            st["c2"] += len(c2)
            st["ret1"] += bool(c1)
            st["ret2"] += bool(c2)
            h1 = any(g in u[k][2] for k in c1 for g in golds)
            h2 = any(g in u[k][2] for k in c2 for g in golds)
            st["b1"] += h1
            st["b2"] += h2
            if r["kind"] != "unans":
                per_item.append((tname, r["id"], int(h1), int(h2), len(c1), len(c2), best))
        lines.append(f"### tokenizer={tname}")
        lines.append("kind            n   B1 gold-in-cand   B2 gold-in-cand   mean|cand| B1/B2   returned B1/B2")
        for key in ["intra2", "cross2", "unans-fulllead", "unans-s3000"]:
            st = stats.get(key)
            if not st:
                continue
            n = st["n"]
            g1 = f"{st['b1']}/{n} ({100*st['b1']/n:.0f}%)" if not key.startswith("unans") else "-"
            g2 = f"{st['b2']}/{n} ({100*st['b2']/n:.0f}%)" if not key.startswith("unans") else "-"
            lines.append(f"{key:14s} {n:3d}   {g1:16s}  {g2:16s}  {st['c1']/n:5.1f}/{st['c2']/n:5.1f}    "
                         f"{st['ret1']}/{n} , {st['ret2']}/{n}")
        lines.append("")
    lines.append("per-item (tokenizer id B1 B2 |c1| |c2| topscore) for answerable items:")
    for p in per_item:
        lines.append("  " + " ".join(str(x) for x in p))
    lines.append("")


def main():
    units = load()
    toks = make_tokenizers()
    lines = ["# Trivial keyword baselines (see baselines.py docstring)",
             f"# units: fulllead sentences={len(units['fulllead'])}, s3000 sentences={len(units['s3000'])}",
             "# unans: every query returns a non-empty candidate set (keyword lookup never abstains).", ""]
    run(OUT / "bank2.tsv", units, toks, lines, "all")
    run(OUT / "bank2.tsv", units, toks, lines, "round 1", lambda r: not r["id"].startswith("R2-"))
    run(OUT / "bank2.tsv", units, toks, lines, "round 2", lambda r: r["id"].startswith("R2-"))
    (OUT / "baselines.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # print summaries only
    print("\n".join(l for l in lines if not l.startswith("  ")))


if __name__ == "__main__":
    main()
