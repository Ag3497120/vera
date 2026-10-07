"""T6aa: the common answer of example lists (intersection, what was removed, how many entries hold a gold string).
usage: make_examples.py QID [QID ...]   (reads results/S300_RUN_t6aa_common.jsonl; writes examples/QID.md)"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = {}
for l in open(os.path.join(HERE, "results", "S300_RUN_t6aa_common.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    R[r["id"]] = r


def write(qid):
    r = R[qid]
    a = r["answer"]
    golds = [g for g in r["gold"].split("|") if g]
    ents = a["entries"]
    c = a["common"]
    ge = sum(any(g.casefold() in w.casefold() for g in golds for w in e["words"]) for e in ents)
    L = ["# %s: %s" % (qid, r["question"]), "",
         "- 正解: %s" % ("、".join(golds) or "(なし: 答えられない問い)"),
         "- 一覧の項目数: %d（並べ方 %d）、正解の語を含む項目: %d" % (len(ents), a["arrangements"], ge),
         "- 問いの語（サイクルで断面に付いた語）: %s" % "、".join(c["query_units"]),
         "- 全項目に共通する語（積集合）: %s" % ("、".join(c["intersection"]) or "(なし)"),
         "- 参考の中心（全項目の中心の和、%d 語）: %s" % (len(c["centres"]), "、".join(c["centres"])),
         "- **共通の答え**（積集合 − 問いの語 − 中心）: **%s**" % ("、".join(c["words"]) or "(空: 一覧のまま = 棄権)"),
         "- 正解が共通の答えに含まれる: %s" % ("はい" if any(g.casefold() in w.casefold() for g in golds for w in c["words"]) else "いいえ")]
    if c["words"]:
        L += ["", "共通の語ごとの出典の文（項目ごとの件数）:", ""]
        for w, per in c["sources"].items():
            L.append("- %s: %s" % (w, " / ".join(str(len(ss)) for ss in per)))
        L += ["", "出典の文の例（最初の項目の最初の 3 文）:", ""]
        w0 = c["words"][0]
        for sid in c["sources"][w0][0][:3]:
            L.append("- [%d] %s" % (sid, a["sentences"].get(str(sid), "")))
    open(os.path.join(HERE, "examples", qid + ".md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    print()


for q in sys.argv[1:]:
    write(q)
