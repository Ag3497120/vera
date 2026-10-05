"""cases_r5.jsonl の SO-03 の理由の訂正（§9.16b）。cases_r5.jsonl は書き換えず、SO-03 の expect_reason_prefix と note だけ替えた写しを cases_r5b.jsonl に書く。
使い方: make_cases_r5b.py <cases_r5.jsonl> <cases_r5b.jsonl>"""
import json, sys

out = []
for l in open(sys.argv[1], encoding="utf-8"):
    if not l.strip():
        continue
    c = json.loads(l)
    if c["id"] == "SO-03":
        c["expect_reason_prefix"] = "ANSWER_CONTENT_NOT_IN_QUOTE:"
        c["note"] = ("形状詞（左様）＋です。形状詞は R1′ の内容語に入る（quote_check.py の docstring「名詞・動詞・形容詞・形状詞…」）ので内容語は 1 個。"
                     "問いの語でないので 3b（R12 でなく既存の規則）で ANSWER_CONTENT_NOT_IN_QUOTE。（r5b: 事前登録の期待 NO_CONTENT_TO_CHECK は R1′ の読み違い。§9.16b）")
    out.append(json.dumps(c, ensure_ascii=False) + "\n")
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.writelines(out)
print(len(out))
