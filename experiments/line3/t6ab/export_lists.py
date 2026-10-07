"""T6ab (2): blind files for a simulated user, one per question whose T6z default answer is a list (CHOICE).
user_lists/<qid>.json: ONLY {"question", "entries": [{"index", "words", "arrangements", "sentence"}]}.
No gold, no grading info.  The file NAME is the qid (as specified) and the qid prefix (a/u) tells answerable
from unanswerable, so a blind user agent should be given the NEUTRAL copies user_lists/blind/Q<nn>.json and
user_lists/ALL.md (neutral numbers, order fixed by a hash of the qid); the map is blind_map.json, OUTSIDE user_lists/.
The displayed order is the stored entry order (word sets by code point; a label, never a ranking)."""
import hashlib
import json
import os
from common import *      # noqa

OUT = os.path.join(HERE, "user_lists")
os.makedirs(os.path.join(OUT, "blind"), exist_ok=True)
lists = [r for r in stored_rows() if r["answer"].get("verdict") == "CHOICE"]
body = {}
for r in lists:
    a = r["answer"]
    sents = a["sentences"]
    ents = []
    for i, e in enumerate(a["entries"]):
        # representative = the source sentence that holds the most of the entry's words (ties: smallest sid)
        cand = [s for s in e["source_sids"] if str(s) in sents]
        sid = min(cand, key=lambda s: (-sum(w in sents[str(s)] for w in e["words"]), s)) if cand else None
        ents.append({"index": i, "words": list(e["words"]), "arrangements": e["count"],
                     "sentence": sents[str(sid)] if sid is not None else ""})
    body[r["id"]] = {"question": r["question"], "entries": ents}
order = sorted(body, key=lambda q: hashlib.sha256(("t6ab" + q).encode()).hexdigest())
neutral = {q: "Q%02d" % (i + 1) for i, q in enumerate(order)}
dump = lambda o: json.dumps(o, ensure_ascii=False, indent=1) + "\n"
for q, b in body.items():
    open(os.path.join(OUT, q + ".json"), "w", encoding="utf-8").write(dump(b))
    open(os.path.join(OUT, "blind", neutral[q] + ".json"), "w", encoding="utf-8").write(dump(b))
json.dump(neutral, open(os.path.join(HERE, "blind_map.json"), "w"), indent=1, sort_keys=True)
L = ["# 利用者向け一覧（ALL）", "",
     "各問いは候補の一覧（項目）で返ります。項目 = 同じ語の集合を使う並べ方のまとまり。表示は語（コードポイント順の符号。順位ではありません）、並べ方の数、代表の出典文（語は単位の抽出後の文）です。",
     "問いごとに、答えを含むと思う項目の番号（index）を 1 つ選ぶか、どれにも答えがないと思えば none を選んでください。番号は 0 始まりです。", ""]
for q in order:
    b = body[q]
    L += ["## %s: %s" % (neutral[q], b["question"]), "", "項目数 %d" % len(b["entries"]), "",
          "| index | 語 | 並べ方 | 出典文（代表） |", "|---|---|---|---|"]
    for e in b["entries"]:
        L.append("| %d | %s | %d | %s |" % (e["index"], "、".join(e["words"]), e["arrangements"], e["sentence"].replace("|", "\\|")))
    L.append("")
open(os.path.join(OUT, "ALL.md"), "w", encoding="utf-8").write("\n".join(L))
print(len(body), "lists;", {q: len(b["entries"]) for q, b in sorted(body.items())})
