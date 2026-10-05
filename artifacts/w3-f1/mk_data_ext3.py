"""W3-f1 拡張 第 3 ラウンド: 撥音便の丁寧形の禁止の検査データ。使い方: mk_data_ext3.py OUT_DIR [DROP_FILE]
verantyx は import しない（期待は実行結果から作らない）。DROP_FILE は基点の空振り（main_polar が ANSWER にならない行）の id 一覧。"""
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
drop = set(Path(sys.argv[2]).read_text(encoding="utf-8").split()) if len(sys.argv) > 2 else set()
# (主語, 目的語句, 撥音便の語幹, 辞書形, ない形)
VERBS = [("運転手", "酒を", "飲ん", "飲む", "飲まない"), ("作業員", "荷物を", "運ん", "運ぶ", "運ばない"),
         ("生徒", "手紙を", "読ん", "読む", "読まない"), ("受付", "友人を", "呼ん", "呼ぶ", "呼ばない"),
         ("委員", "候補者を", "選ん", "選ぶ", "選ばない"), ("店員", "財布を", "盗ん", "盗む", "盗まない"),
         ("医者", "薬を", "頼ん", "頼む", "頼まない")]
FORMS = [("んではいけません", "では", "いけません"), ("んではなりません", "では", "なりません"),
         ("んでもいけません", "でも", "いけません"), ("んではいけませんでした", "では", "いけませんでした"),
         ("んではなりませんでした", "では", "なりませんでした")]
rows = []
for vi, (s, o, stem, dic, nai) in enumerate(VERBS):
    for fi, (fname, part, aux) in enumerate(FORMS):
        if (vi + fi) % 5 == 4 and vi % 2: continue      # 全組ではなく、主語・形の組を間引いて散らす
        doc = f"{s}は{o}{stem}{fname[1:]}。"
        rows.append({"id": f"nde-main-{vi}-{fi}", "kind": "main_polar", "form": fname, "document": doc, "question": f"{s}は{o}{dic}？"})
        if fi % 2 == 0:
            rows.append({"id": f"nde-aux-{vi}-{fi}", "kind": "aux_polar", "form": fname, "document": doc, "question": f"{s}は{aux}？"})
for vi, (s, o, stem, dic, nai) in enumerate(VERBS):
    rows.append({"id": f"nde-ctl-{vi}", "kind": "control", "form": "ない", "document": f"{s}は{o}{nai}。", "question": f"{s}は{o}{dic}？", "expect_values": ["いいえ"]})
rows = [r for r in rows if r["id"] not in drop]
(out / "w3f1_prohibition_nde.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
from collections import Counter
print(len(rows), dict(Counter(r["kind"] for r in rows)))
