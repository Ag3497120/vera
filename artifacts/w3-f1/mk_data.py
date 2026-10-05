"""W3-f1 検査データの生成。verantyx を import しない。出力: tests/reading_soundness/w3f1_kinship.jsonl"""
import json, sys
NOUNS = "父 母 祖父 祖母 叔父 叔母 伯父 伯母 兄 姉 弟 妹 息子 娘 夫 妻 孫 友人 同僚 上司 部下 先輩 後輩 店主 教師".split()
T = {
    "agent": ("{X}が肥料を運んだ。", "誰が肥料を運んだ？"),
    "recipient": ("店員が{X}に本を渡した。", "店員は誰に本を渡した？"),
    "patient": ("医師が{X}を診察した。", "医師が誰を診察した？"),
}
rows = []
for n in NOUNS:
    for role, (d, q) in T.items():
        rows.append({"id": f"{role}-{n}", "kind": "role", "noun": n, "role": role,
                     "document": d.format(X=n), "question": q, "expect_values": [n]})
for a, b in [("叔父","叔母"),("叔母","叔父"),("祖父","祖母"),("祖母","祖父"),("伯父","伯母"),("伯母","伯父")]:
    rows.append({"id": f"polar-{a}-{b}", "kind": "polar", "noun": a, "role": "agent", "pair": [a, b],
                 "document": f"{b}が肥料を運んだ。", "question": f"{a}は肥料を運んだ？"})
with open(sys.argv[1], "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(rows))
