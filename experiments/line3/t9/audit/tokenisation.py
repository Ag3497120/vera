"""T9 audit, cause (i): is the gold one unit of a tier?  For every intra2 question: in the evidence sentence, is a
normalised gold alternative inside ONE unit of RUN / WORD / CHAR (Vera's hit rule), and if not, how many consecutive
units does it span?  Also: is it inside one unit anywhere in the corpus.  Writes tokenisation.jsonl + prints counts."""
import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
T9 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(T9)))
sys.path.insert(0, ROOT); sys.path.insert(0, T9)
import scorer as S                       # noqa: E402
from verantyx.line3 import space as sp   # noqa: E402

FL = os.path.join(T9, "..", "bank2", "data", "fulllead_sents.jsonl")
spc = sp.build_space(sp.load_jsonl(FL))
by_src = {src: i for i, (_t, src) in enumerate(spc.sentences)}
rows = [dict(zip("id kind corpus subject question gold evidence audit".split(), l.rstrip("\n").split("\t")))
        for l in open(os.path.join(T9, "..", "bank2", "bank2.tsv"), encoding="utf-8") if not l.startswith("#") and l.strip()]
rows = [r for r in rows if r["kind"] == "intra2"]


def span(units, gs):
    """min number of consecutive units whose normalised concatenation holds a gold alternative (None = never)."""
    nu = [S.norm(u) for u in units]
    best = None
    for i in range(len(nu)):
        acc = ""
        for j in range(i, len(nu)):
            acc += nu[j]
            if any(g in acc for g in gs):
                n = j - i + 1
                best = n if best is None else min(best, n)
                break
    return best


out = []
for r in rows:
    sid = by_src[r["evidence"]]
    gs = S.golds(r["gold"])
    rec = {"id": r["id"], "gold": r["gold"], "sid": sid, "text": spc.sentences[sid][0]}
    for t in ("RUN", "WORD", "CHAR"):
        ts = spc.tiers[t]
        us = ts.sentence_units[sid]
        one = [u for u in us if any(g in S.norm(u) for g in gs)]
        anywhere = [u for u in ts.units() if any(g in S.norm(u) for g in gs)]
        rec[t] = {"one_unit": one, "span": span(us, gs), "units_anywhere": anywhere[:10], "n_anywhere": len(anywhere),
                  "gold_in_text": any(g in S.norm(spc.sentences[sid][0]) for g in gs),
                  "ev_units": list(us)}
    out.append(rec)
with open(os.path.join(HERE, "tokenisation.jsonl"), "w", encoding="utf-8") as f:
    for rec in out:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
for t in ("RUN", "WORD", "CHAR"):
    c = Counter("one" if rec[t]["one_unit"] else ("span%d" % rec[t]["span"] if rec[t]["span"] else "absent") for rec in out)
    print(t, sorted(c.items()), "anywhere-one-unit:", sum(1 for rec in out if rec[t]["n_anywhere"]))
print("one unit in some tier (evidence sentence):", sum(1 for rec in out if any(rec[t]["one_unit"] for t in ("RUN", "WORD", "CHAR"))))
print("one unit in RUN or WORD:", sum(1 for rec in out if rec["RUN"]["one_unit"] or rec["WORD"]["one_unit"]))
for rec in out:
    if not rec["RUN"]["one_unit"]:
        print(rec["id"], rec["gold"], "RUN span", rec["RUN"]["span"], "WORD span", rec["WORD"]["span"],
              [u for u in rec["RUN"]["ev_units"]][:25])
