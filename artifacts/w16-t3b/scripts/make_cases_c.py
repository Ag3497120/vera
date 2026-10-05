"""cases_c.jsonl（第 2 ラウンドの凍結。事前登録 docs/FUSION.md §10.12）を作る。
= cases.jsonl の 27 件（RO-02 だけ cases_b の訂正版。元の SP-05 は元の期待のまま） + cases_b の SP-05 訂正版（id SP-05b） + 問いの語の繰り返しの型の SP を新しく 4 件。H-05 は入れない。
期待は規則から手で決めた（コードを流して決めていない）。使い方: make_cases_c.py <cases.jsonl> <cases_b.jsonl> <cases_c.jsonl>"""
import json
import sys

A = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
B = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()}
out = []
for c in A:
    out.append(B["RO-02"] if c["id"] == "RO-02" else c)
sp5b = dict(B["SP-05"])
sp5b["id"] = "SP-05b"
out.append(sp5b)


def sp(i, docs, question, answer, quotes, expect, reason, note):
    return {"id": i, "type": "SP", "docs": {"doc.txt": docs}, "question": question, "answer": answer,
            "quotes": [{"source": "doc.txt", "line": n, "text": t} for n, t in quotes],
            "expect": expect, "expect_reason_prefix": reason, "note": note, "expect_found": None, "expect_source_record": None}


D1 = "倉庫は来月から使える。\n事務所は先月に閉まった。"
out.append(sp("SP-06", D1, "倉庫はどうなりますか", "倉庫は先月に閉まった。", [(1, "倉庫は来月から使える。"), (2, "事務所は先月に閉まった。")],
              "unanchored", "ANSWER_SPLIT_ACROSS_QUOTES", "問いの語の繰り返し（普通名詞の主語 倉庫）。主語は引用 1、述語の中身は引用 2 にしかない合成。R15（第 2 ラウンドの項目の定義）。"))
D2 = "食堂は平日のみ営業する。\n売店は土曜も営業する。"
out.append(sp("SP-07", D2, "食堂の営業日について教えてください", "食堂は土曜も営業する。", [(1, "食堂は平日のみ営業する。"), (2, "売店は土曜も営業する。")],
              "unanchored", "ANSWER_SPLIT_ACROSS_QUOTES", "問いの語（食堂・営業）の繰り返し。食堂 は引用 1、土曜 は引用 2 だけ。R15。"))
D3 = "図書館は午後9時に閉まる。\n体育館は午前8時に開く。"
out.append(sp("SP-08", D3, "図書館はいつ開きますか", "図書館は午前8時に開く。", [(1, "図書館は午後9時に閉まる。"), (2, "体育館は午前8時に開く。")],
              "unanchored", "ANSWER_SPLIT_ACROSS_QUOTES", "問いの語（図書館・開く）の繰り返し。主語は引用 1、時刻は引用 2。R15。"))
D4 = "窓口は午前9時に開く。\n駐車場は無料だ。"
out.append(sp("SP-09", D4, "受付は何時に開きますか", "受付は午前9時に開く。", [(1, "窓口は午前9時に開く。"), (2, "駐車場は無料だ。")],
              "anchored", None, "正しい対照。問いの語（受付）がどの引用にも無く、答えの残りは引用 1 が全部支える（問いの語がどの引用にも無ければ項目に入れない）。"))
with open(sys.argv[3], "w", encoding="utf-8") as f:
    for c in out:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print(len(out))
