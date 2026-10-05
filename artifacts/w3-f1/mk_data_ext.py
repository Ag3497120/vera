"""W3-f1 拡張の検査データ生成。verantyx を import しない。正解は表から機械的に作る（実行結果から作らない）。
使い方: mk_data_ext.py OUT_DIR  → w3f1_prohibition.jsonl / w3f1_time_place.jsonl / w3f1_ext_range.jsonl"""
import json, sys
from pathlib import Path
out = Path(sys.argv[1])

# ---- 禁止 ----
SUBJ = ["エージェント", "社員", "学生", "患者", "子供", "職員"]
# (目的語句, て形語幹, で形語幹, 辞書形, ない形)
TE = [("評価バンクを", "開い"), ("鍵を", "持ち出し"), ("答えを", "見"), ("秘密を", "話し"), ("書類を", "捨て"), ("窓を", "開け")]
DE = [("本を", "読ん"), ("酒を", "飲ん"), ("友人を", "呼ん"), ("公園で", "遊ん")]
DICT = {"開い": "開く", "持ち出し": "持ち出す", "見": "見る", "話し": "話す", "捨て": "捨てる", "開け": "開ける",
        "読ん": "読む", "飲ん": "飲む", "呼ん": "呼ぶ", "遊ん": "遊ぶ"}
NAI = {"開い": "開かない", "持ち出し": "持ち出さない", "見": "見ない", "話し": "話さない", "捨て": "捨てない", "開け": "開けない",
       "読ん": "読まない", "飲ん": "飲まない", "呼ん": "呼ばない", "遊ん": "遊ばない"}
# (形, 助詞, 補助の語尾, 問いの補助)
FORMS = [("てはならない", "て", "はならない", "ならない"), ("てはいけない", "て", "はいけない", "いけない"),
         ("ではならない", "で", "はならない", "ならない"), ("ではいけない", "で", "はいけない", "いけない"),
         ("てはなりません", "て", "はなりません", "なりません"), ("てはいけません", "て", "はいけません", "いけません"),
         ("てはいけなかった", "て", "はいけなかった", "いけなかった")]
pro = []
i = 0
for s in SUBJ:
    for fname, kind_te, aux, qaux in FORMS:
        pool = TE if kind_te == "て" else DE
        obj, stem = pool[i % len(pool)]
        i += 1
        te = stem + ("て" if kind_te == "て" else "で")
        doc = f"{s}は{obj}{te}{aux}。"
        pro.append({"id": f"aux-{s}-{fname}", "kind": "aux_polar", "form": fname, "document": doc,
                    "question": f"{s}は{qaux}？"})
        if len(pro) % 3 == 0:
            pro.append({"id": f"main-{s}-{fname}", "kind": "main_polar", "form": fname, "document": doc,
                        "question": f"{s}は{obj}{DICT[stem]}？"})
for s, (obj, stem) in [("田中", ("本を", "読ん")), ("佐藤", ("鍵を", "持ち出し")), ("鈴木", ("答えを", "見")), ("高橋", ("書類を", "捨て"))]:
    doc = f"{s}は{obj}{NAI[stem]}。"
    pro.append({"id": f"ctl-neg-{s}", "kind": "control", "document": doc, "question": f"{s}は{obj}{DICT[stem]}？", "expect_values": ["いいえ"]})
    pro.append({"id": f"ctl-negq-{s}", "kind": "control", "document": doc, "question": f"{s}は{obj}{NAI[stem]}？", "expect_values": ["はい"]})
# ---- 時と場所 ----
PEOPLE = ["山田さん", "田中", "佐藤さん", "鈴木", "高橋さん", "中村"]
TIMES = ["明日", "今日", "昨日", "来週", "毎朝", "午後", "今朝", "夕方", "週末", "先月", "2030年"]
PLACES = ["東京", "大阪", "公園", "駅前", "会議室", "図書館", "食堂"]
# 基点が「時の語なし」で答えられる述語だけを使う（答えられない述語では検査が空振りになる）。
# (現在形の動詞句, 過去形の動詞句, 問い雛形)  {P} 人
PRED = [("で働く", "で働いた", "どこで働く？"), ("で新聞を買う", "で新聞を買った", "{P}はどこで新聞を買う？"),
        ("で昼食を食べる", "で昼食を食べた", "{P}はどこで昼食を食べる？"), ("で本を読む", "で本を読んだ", "{P}はどこで本を読む？"),
        ("で写真を撮る", "で写真を撮った", "{P}はどこで写真を撮る？"), ("で資料を作る", "で資料を作った", "{P}はどこで資料を作る？")]
PAST = {"昨日", "先月"}
def verb(pi, t):
    return PRED[pi][1] if t in PAST else PRED[pi][0]
def question(pi, t, p):
    q = PRED[pi][2].format(P=p)
    return q.replace("？", "").replace("働く", "働いた").replace("買う", "買った").replace("食べる", "食べた").replace("読む", "読んだ").replace("撮る", "撮った").replace("作る", "作った") + "？" if t in PAST else q
tp = []
n = 0
for ti, t in enumerate(TIMES):
    for k in range(4):
        p = PEOPLE[(ti + k) % len(PEOPLE)]
        l = PLACES[(ti * 3 + k * 2) % len(PLACES)]
        pi = (ti + k) % len(PRED)
        tp.append({"id": f"fused-{n:02d}", "kind": "fused", "time_word": t, "place": l,
                   "document": f"{p}が{t}{l}{verb(pi, t)}。", "question": question(pi, t, p)})
        n += 1
m = 0
for ci, (p, l) in enumerate([("山田さん", "東京"), ("田中", "駅前"), ("佐藤さん", "図書館"), ("鈴木", "食堂"), ("高橋さん", "会議室"), ("中村", "公園")]):
    q = PRED[ci][2]
    tp.append({"id": f"ctl-plain-{ci}", "kind": "control", "document": f"{p}が{l}{PRED[ci][0]}。", "question": q.format(P=p), "expect_values": [l], "time_word": "", "place": l})
    t = ["明日", "来週", "週末", "毎朝", "夕方", "今朝"][ci]
    tp.append({"id": f"ctl-comma-{ci}", "kind": "control", "document": f"{t}、{p}が{l}{PRED[ci][0]}。", "question": q.format(P=p), "expect_values": [l], "time_word": t, "place": l})
# ---- 範囲だけ ----
rg = []
def R(gid, g, d, q): rg.append({"id": gid, "kind": "range", "group": g, "document": d, "question": q})
for k, (s, o, v) in enumerate([("学生", "答えを", "見"), ("社員", "鍵を", "持ち出し"), ("患者", "薬を", "飲ん")]):
    te = v + ("で" if v.endswith("ん") else "て")
    R(f"temo-ika-{k}", "てもいけない", f"{s}は{o}{te}もいけない。", f"{s}はいけない？")
    R(f"temo-nara-{k}", "てもならない", f"{s}は{o}{te}もならない。", f"{s}はならない？")
for k, (s, o, v) in enumerate([("学生", "答えを", "見"), ("社員", "鍵を", "持ち出し")]):
    R(f"cha-{k}", "ちゃいけない", f"{s}は{o}{v}ちゃいけない。", f"{s}はいけない？")
for k, (s, o, v) in enumerate([("子供", "酒を", "飲ん"), ("学生", "本を", "読ん")]):
    R(f"ja-{k}", "じゃいけない", f"{s}は{o}{v[:-1]}んじゃいけない。", f"{s}はいけない？")
for k, (s, o, v) in enumerate([("田中", "本を", "読ま"), ("佐藤", "書類を", "出さ"), ("鈴木", "鍵を", "返さ")]):
    R(f"nakute-nara-{k}", "なくてはならない", f"{s}は{o}{v}なくてはならない。", f"{s}はならない？")
    R(f"nakute-ike-{k}", "なくてはいけない", f"{s}は{o}{v}なくてはいけない。", f"{s}はいけない？")
for k, (p, l, t, v, q) in enumerate([("田中", "東京", "明日", "働く", "どこで働く？"), ("山田さん", "大阪", "来週", "働く", "どこで働く？"),
                                     ("佐藤さん", "駅前", "毎朝", "新聞を買う", "佐藤さんはどこで新聞を買う？")]):
    R(f"place-time-{k}", "場所の後ろに時の語", f"{p}が{l}で{t}{v}。", q)
R("goal-fused-0", "着点（基点は時の語なしでも答えない）", "山田さんが明日東京に行く。", "山田さんはどこに行く？")
R("goal-plain-0", "着点（基点は時の語なしでも答えない）", "山田さんが東京に行く。", "山田さんはどこに行く？")
R("past-time-0", "過去の時の語＋現在形（基点が棄権する形）", "昨日、田中が駅前で新聞を買う。", "田中はどこで新聞を買う？")
R("multi-0", "複数文", "田中は本を読まない。社員は鍵を持ち出してはならない。", "田中は本を読む？")
R("multi-1", "複数文", "山田さんが明日東京で働く。田中が大阪で働く。", "田中はどこで働く？")
R("multi-2", "複数文", "山田さんが明日東京で働く。田中が大阪で働く。", "山田さんはどこで働く？")
R("multi-3", "複数文", "学生は答えを見てはいけない。田中は本を読まない。", "田中は本を読まない？")
for name, rows in [("w3f1_prohibition.jsonl", pro), ("w3f1_time_place.jsonl", tp), ("w3f1_ext_range.jsonl", rg)]:
    (out / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(name, len(rows))
