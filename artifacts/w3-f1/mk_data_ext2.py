"""W3-f1 拡張 第 2 ラウンド: 時の語＋接尾辞の場所の検査データを作る。使い方: mk_data_ext2.py OUT_DIR
verantyx は import しない（期待は実行結果から作らない）。"""
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
PEOPLE = ["山田さん", "田中", "佐藤さん", "鈴木", "高橋さん", "中村"]
TIMES = ["来週", "毎朝", "明後日", "今夜", "来月", "先週", "去年", "翌朝", "毎晩", "明日"]
PLACES = ["港", "店", "館", "庁", "室", "園", "院", "城"]    # v2: 湖・街 は基点が時の語なしでも答えない（v1 の対照が落ちた）ので外した
PAST = {"先週", "去年"}
PRED = [("で働く", "で働いた", "どこで働く？"), ("で新聞を買う", "で新聞を買った", "{P}はどこで新聞を買う？"),
        ("で昼食を食べる", "で昼食を食べた", "{P}はどこで昼食を食べる？"), ("で本を読む", "で本を読んだ", "{P}はどこで本を読む？"),
        ("で写真を撮る", "で写真を撮った", "{P}はどこで写真を撮る？"), ("で資料を作る", "で資料を作った", "{P}はどこで資料を作る？")]
PASTQ = [("働く", "働いた"), ("買う", "買った"), ("食べる", "食べた"), ("読む", "読んだ"), ("撮る", "撮った"), ("作る", "作った")]
def question(pi, t, p):
    q = PRED[pi][2].format(P=p)
    if t in PAST:
        for a, b in PASTQ: q = q.replace(a, b)
    return q
rows = []; n = 0
for ti, t in enumerate(TIMES):
    for k in range(3):
        p = PEOPLE[(ti + k) % len(PEOPLE)]
        l = PLACES[(ti * 2 + k * 4) % len(PLACES)]
        if t == "明日": l = ["園", "館", "院"][k]    # 明日港・明日海 は 名詞と付き既存の検査で棄権される。接尾辞と付く形だけを検査に入れる
        pi = (ti + k) % len(PRED)
        verb = PRED[pi][1] if t in PAST else PRED[pi][0]
        rows.append({"id": f"sfx-fused-{n:02d}", "kind": "fused", "time_word": t, "place": l,
                     "document": f"{p}が{t}{l}{verb}。", "question": question(pi, t, p)})
        n += 1
for ci, l in enumerate(PLACES):
    p = PEOPLE[ci % len(PEOPLE)]; pi = ci % len(PRED)
    rows.append({"id": f"sfx-ctl-plain-{ci}", "kind": "control", "time_word": "", "place": l,
                 "document": f"{p}が{l}{PRED[pi][0]}。", "question": PRED[pi][2].format(P=p), "expect_values": [l]})
for ci in range(6):
    p = PEOPLE[ci]; l = PLACES[(ci * 2) % len(PLACES)]; t = ["明日", "来週", "毎朝", "今夜", "来月", "明後日"][ci]
    rows.append({"id": f"sfx-ctl-comma-{ci}", "kind": "control", "time_word": t, "place": l,
                 "document": f"{t}、{p}が{l}{PRED[ci][0]}。", "question": PRED[ci][2].format(P=p), "expect_values": [l]})
(out / "w3f1_time_place_suffix.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print(len(rows), sum(r["kind"] == "fused" for r in rows))
