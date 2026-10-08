"""T6z: the new state of example questions (entries = word sets, with arrangement counts, centres, gold marks).
usage: make_examples.py QID [QID ...]   (reads results/S300_RUN_t6z_defaults.jsonl)"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = {}
for l in open(os.path.join(HERE, "results", "S300_RUN_t6z_defaults.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    R[r["id"]] = r
SHOW = 30
esc = lambda s: s.replace("|", "\\|")


def write(qid):
    r = R[qid]
    a = r["answer"]
    golds = [g for g in r["gold"].split("|") if g]
    ents = a.get("entries", [])
    n = len(ents)
    mark = lambda e: any(g.casefold() in t.casefold() for g in golds for t in ["".join(p["words"]) for ar in e["arrangements"] for p in ar["paths"]])
    inword = lambda e: any(g.casefold() in w.casefold() for g in golds for w in e["words"])
    idx = list(range(n)) if n <= SHOW else sorted({round(i * (n - 1) / (SHOW - 1)) for i in range(SHOW)})
    L = []
    w = L.append
    w("# %s: %s" % (qid, r["question"]))
    w("")
    w("- 正解: %s" % "、".join(golds))
    w("- 結果の種別: %s（サイクルの結果: %s）、採用状態 %d" % (a.get("verdict"), r["cycle"]["verdict"], r["states_adopted"]))
    if not ents:
        w("- 項目なし")
    else:
        w("- 並べ方（断面の割り当てだけ違うものを統合した後）: %d、一覧の項目（語の集合が同じものをまとめた後）: **%d**、正解を含む項目: %d" % (
            a["arrangements"], n, sum(mark(e) for e in ents)))
        if a.get("verdict") == "ANSWER":
            e = ents[0]
            w("- **答え**（一覧が 1 項目になったので答え）: 語の集合 = %s ／ 並べ方 %d 通り ／ 参考の中心 = %s ／ 出典の文 %d 件" % (
                "、".join(e["words"]), e["count"], "、".join(e["centres"]), len(e["source_sids"])))
        if n <= SHOW:
            w("- 表示: 全 %d 項目（語の集合の辞書順 = 並びは印であり優劣ではない）" % n)
        else:
            w("- 表示: 一覧（%d 項目、語の集合の辞書順）から等間隔に %d 項目（正解の有無は見ずに選んだ）。# は一覧全体の番号" % (n, len(idx)))
        w("- 「並べ方」= その語の集合を使う、断面の割り当てを除いて異なる項目の数（代表は選ばず全部を持つ）。「中心」= 並べ方の参考の中心（複数なら全部）。◎ = 並べ方のどれかの経路の文字列に正解を含む")
        w("")
        w("| # | 語の集合 | 並べ方 | 中心 | 出典の文 | 正解 |")
        w("|---|---|---|---|---|---|")
        for i in idx:
            e = ents[i]
            w("| %d | %s | %d | %s | %d | %s |" % (i + 1, esc("、".join(e["words"])), e["count"], esc("、".join(e["centres"])),
                                                    len(e["source_sids"]), "◎" if mark(e) else ("(語の一部)" if inword(e) else "")))
    open(os.path.join(HERE, "examples", qid + ".md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(qid, a.get("verdict"), a.get("arrangements"), n)


for q in sys.argv[1:]:
    write(q)
