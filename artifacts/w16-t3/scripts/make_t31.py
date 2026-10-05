"""T3-1 の集合を作る（W14 の公開データを読むだけ）。規則は docs/FUSION.md §9.2（事前登録）。"""
import collections
import json
import os
import sys

W14 = "/Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S"
sys.path.append(W14)
from benchmarks.public_v1 import data as D  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "t31", "items.jsonl")


def line_text(doc, line):
    return D.read_lines(doc)[line - 1]


def main():
    qs = D.load_questions()
    ans = sorted([q for q in qs if q["cat"] == "ANS"], key=lambda q: q["id"])
    none = sorted([q for q in qs if q["cat"] == "NONE"], key=lambda q: q["id"])
    none_sel = []
    for ds in ("S1", "S2", "S3", "S4"):
        none_sel += [q for q in none if q["docset"] == ds][:5]
    items = []
    ans_by_ds = collections.defaultdict(list)
    for q in ans:
        ans_by_ds[q["docset"]].append(q)
    for i, q in enumerate(ans):
        ev = q["evidence"][0]
        text = line_text(ev["doc"], ev["line"])
        good = {"answer": q["answer"], "quotes": [{"source": ev["doc"], "line": ev["line"], "text": text}]}
        wrong_i = i % 2 == 0
        if not wrong_i:
            cand, typ = good, "OK"
        else:
            val = q["distractors"][0]["value"]
            if (i // 2) % 2 == 0:
                typ, cand = "W1", {"answer": val, "quotes": good["quotes"]}
            else:
                typ = "W2"
                cand = {"answer": val, "quotes": [{"source": ev["doc"], "line": ev["line"], "text": text.replace(q["answer"], val)}]}
        items.append({"id": q["id"], "cat": "ANS", "docset": q["docset"], "type": typ, "wrong": wrong_i, "question": q["question"], "candidate": cand})
    for i, q in enumerate(none_sel):
        wrong_i = i % 2 == 0
        if not wrong_i:
            items.append({"id": q["id"], "cat": "NONE", "docset": q["docset"], "type": "OK", "wrong": False, "question": q["question"],
                          "candidate": {"answer": D.ABSTAIN_TEXT, "quotes": []}})
            continue
        rank = [x["id"] for x in none if x["docset"] == q["docset"]].index(q["id"])
        borrowed = ans_by_ds[q["docset"]][rank]["distractors"][0]
        val = borrowed["value"]
        if (i // 2) % 2 == 0:
            typ = "N1"
            cand = {"answer": val, "quotes": [{"source": borrowed["doc"], "line": borrowed["line"], "text": line_text(borrowed["doc"], borrowed["line"])}]}
        else:
            typ = "N2"
            qq = q["question"]
            fab = (qq[:-1] + val + "。") if qq.endswith("。") else qq + val
            cand = {"answer": val, "quotes": [{"source": borrowed["doc"], "line": borrowed["line"], "text": fab}]}
        items.append({"id": q["id"], "cat": "NONE", "docset": q["docset"], "type": typ, "wrong": True, "question": q["question"], "candidate": cand})
    items.sort(key=lambda r: r["id"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in items:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print("items", len(items), "wrong", sum(r["wrong"] for r in items))
    print("types", dict(collections.Counter(r["type"] for r in items)))
    print("cat", dict(collections.Counter(r["cat"] for r in items)))


if __name__ == "__main__":
    main()
