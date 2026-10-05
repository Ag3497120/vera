"""cases.jsonl（凍結済み・書き換えない）の 2 件の期待の読み違いを訂正した写しを cases_b.jsonl に書く（W16-t3 §9.16b と同じやり方）。
- RO-02: 係長 は引用側で 係＋長 に分かれ（形態素解析の読み。前もって確かめなかった）、答えの 係長 が内容語の被覆（既存の規則 3b）で先に落ちる。verdict は unanchored のままだが reason が ANSWER_CONTENT_NOT_IN_QUOTE で、R13 を確かめる項目になっていなかった。1 語に解析される 部長 に替えた別の文にする。
- SP-05: 問いに 営業課 が入っていて、R3（問いの語は被覆から除く）で答えの 営業・課 が 照合する項目から外れ、鈴木 だけが残り引用 2 が支える。規則どおり anchored。問いを替えて R15 の項目にする。
  元の問い（営業課の課長について教えてください）の形は規則どおり anchored になる「閉じない型」として H-05 に残す。
使い方: make_cases_b.py <cases.jsonl> <cases_b.jsonl>"""
import json
import sys

out = []
for l in open(sys.argv[1], encoding="utf-8"):
    if not l.strip():
        continue
    c = json.loads(l)
    if c["id"] == "RO-02":
        c["docs"] = {"doc.txt": "課長が部長に書類を渡した。"}
        c["answer"] = "部長が課長に書類を渡した。"
        c["quotes"] = [{"source": "doc.txt", "line": 1, "text": "課長が部長に書類を渡した。"}]
        c["note"] = "主語と間接目的語の入れ替え（が／に）。書類 は同じ を。R13。（b: 元の 係長 は引用側で 係＋長 に分かれ 3b で先に落ちたので 部長 に替えた）"
    if c["id"] == "SP-05":
        c["question"] = "課長の名前を教えてください"
        c["note"] = "和集合では全部の語が引用にあるが、1 つの引用では揃わない。R15。（b: 元の問いは 営業課 を含み R3 で項目から外れた。H-05 に残す）"
    out.append(c)
h = {"id": "H-05", "type": "H", "docs": {"doc.txt": "営業課の課長は田中だ。\n経理課の課長は鈴木だ。"}, "question": "営業課の課長について教えてください", "answer": "営業課の課長は鈴木だ。",
     "quotes": [{"source": "doc.txt", "line": 1, "text": "営業課の課長は田中だ。"}, {"source": "doc.txt", "line": 2, "text": "経理課の課長は鈴木だ。"}],
     "expect": "anchored", "expect_reason_prefix": None, "note": "開示（閉じない型）: 答えが問いの語（営業課・課長）を繰り返すと R3 でそれらは照合する項目から外れ、鈴木 だけを持つ引用 2 が支えになる。誤答だが anchored。",
     "expect_found": None, "expect_source_record": None}
out.append(h)
with open(sys.argv[2], "w", encoding="utf-8") as f:
    for c in out:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print(len(out))
