"""cases_r4b.jsonl = cases_r4.jsonl（凍結済み・残す）の O-02 の期待だけを §9.13b の訂正（J-R4-1 の撤回）に合わせて変えたもの。"""
import json, sys
out = []
for l in open(sys.argv[1], encoding="utf-8"):
    c = json.loads(l)
    if c["id"] == "O-02":
        c["expect"], c["expect_reason_prefix"] = "anchored", None
        c["note"] = "（r4b）そうです は応答の語を含まず、要素・述語・内容語も無い。J-R4-1 の撤回により anchored（既知の穴。既存の試験 test_no_elements_with_a_real_quote_is_anchored と同じ型）。"
    out.append(c)
with open(sys.argv[2], "w", encoding="utf-8") as f:
    for c in out:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
