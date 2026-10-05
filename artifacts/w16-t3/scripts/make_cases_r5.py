"""第 5 ラウンドの検査データ cases_r5.jsonl と cases_r4c_r5.jsonl（事前登録 docs/FUSION.md §9.16 の規則から手で期待を決めた。コードの出力は写していない）。
使い方: make_cases_r5.py <cases_r5.jsonl> <cases_r4c_r5.jsonl>"""
import json, os, sys

NC, CN = "NO_CONTENT_TO_CHECK", "ANSWER_CONTENT_NOT_IN_QUOTE:"
HERE = os.path.dirname(os.path.abspath(__file__))
C = []


def case(id_, type_, doc, question, answer, expect, reason, note):
    C.append({"id": id_, "type": type_, "docs": {"doc.txt": doc}, "question": question, "answer": answer,
              "quotes": [{"source": "doc.txt", "line": 1, "text": doc}], "expect": expect,
              "expect_reason_prefix": reason, "note": note})


# SO: そうです型（内容語 0 個。名詞・動詞・形容詞が答えに無い、または 非自立可能 の述語だけ）。引用は逆のことを言う
case("SO-01", "SO", "船着き場の係留は、無料だ。", "船着き場の係留は有料ですか", "そうです。", "unanchored", NC,
     "副詞＋です。内容語 0 個、要素 0、応答の語（感動詞）無し。R12 (ii)。")
case("SO-02", "SO", "旧校舎の武道場は、改装中で使えない。", "旧校舎の武道場は使えますか", "まさにそうです。", "unanchored", NC,
     "副詞だけ。内容語 0 個。引用は逆（使えない）。R12 (ii)。")
case("SO-03", "SO", "桟橋の釣りは、禁じられている。", "桟橋で釣りはできますか", "左様です。", "unanchored", NC,
     "形状詞（左様）＋です。名詞・動詞・形容詞の内容語は 0 個。R12 (ii)。")
case("SO-04", "SO", "温室の見学は、予約が必要だ。", "温室の見学は予約なしでできますか", "できます。", "unanchored", NC,
     "述語は 非自立可能 の できる だけ。内容語 0 個。極性（3d）より先に 3e（印の順）。")
# QO: 問いの語だけの答え（応答の語なし）。引用にその語が無い誤答
case("QO-01", "QO", "渡し船の運賃は、乗船前に払う。", "渡し船の運賃は後払いですか", "後払いです。", "unanchored", CN,
     "内容語 後払い は問いの語の繰り返しだけ（rest 空）。R12 (i) で戻し、引用に無いので 3b。")
case("QO-02", "QO", "地域センターの会議室は、洋室だ。", "地域センターの会議室は茶室ですか", "茶室です。", "unanchored", CN,
     "内容語 茶室 は問いの語の繰り返しだけ。引用は 洋室。")
case("QO-03", "QO", "診療所の受付は、窓口で行う。", "診療所の受付は電話だけですか", "電話です。", "unanchored", CN,
     "内容語 電話 は問いの語の繰り返しだけ。引用に無い。")
# PR: 述語つきの言い直し
case("PR-01", "PR", "町内会の清掃は、当番の住民が担当する。", "町内会の清掃は班長が担当しますか", "はい、班長が担当します。", "unanchored", CN,
     "述語（する）があるので 3c でなく R12 (i)。班（長は接尾辞）が引用に無い。誤答。")
case("PR-02", "PR", "資料室の鍵は、夜警が保管する。", "資料室の鍵は事務員が保管しますか", "はい、事務員が保管します。", "unanchored", CN,
     "述語つき。事務 が引用に無い。誤答。")
case("PR-03", "PR", "農協の集荷は、平日に行う。", "農協の集荷は週末に行いますか", "週末に行います。", "unanchored", CN,
     "応答の語なしの言い直し。週末 は問いの語の繰り返しで引用に無い。誤答。")
case("PR-04", "PR", "資料室の鍵は、夜警が保管する。", "資料室の鍵は夜警が保管しますか", "はい、夜警が保管します。", "anchored", None,
     "正しい言い直し。夜警・保管 が引用に有る。極性も同じ。")
case("PR-05", "PR", "船着き場の整備は、市が担当する。", "船着き場の整備は市が担当しますか", "はい、市が担当します。", "anchored", None,
     "正しい言い直し。市・担当 が引用に有る。極性も同じ。")
# C: 対照（R12 に当たらない）
case("C-01", "C", "資材置き場の鍵は、学芸員が持つ。", "資材置き場の鍵は誰が持ちますか", "学芸員です。", "anchored", None,
     "学芸 は問いの語でなく引用に有る（rest 非空で R12 は動かない）。")
case("C-02", "C", "観測所の公開日は、5月3日だ。", "観測所の公開日はいつですか", "5月3日です。", "anchored", None,
     "要素（日付）が有り、引用に同じ表記で有る。R12 は動かない。")
case("C-03", "C", "標本室の入口は、西口だ。", "標本室の入口は東口と西口のどちらですか", "西口です。", "anchored", None,
     "選択の問い。西口 は引用に有る。")
case("C-04", "C", "標本室の入口は、西口だ。", "標本室の入口は東口と西口のどちらですか", "東口です。", "unanchored", CN,
     "選択の問いでは問いの語を除かない。東口 が引用に無い。")
# H: 閉じない型（既知の穴。§9.8）
case("H-01", "H", "駐車料金の支払いは、窓口で行う。", "駐車料金は精算機で支払いますか", "はい、支払います。", "anchored", None,
     "既知の穴（J-R5-5）: 答えの動詞の表層 支払い が引用の名詞 支払い と等しく R2 で被覆される。§9.8。")
case("H-02", "H", "草刈りは、毎月行う。", "草刈りは隔週で行いますか", "はい、行います。", "anchored", None,
     "既知の穴（J-R5-5）: 答えに無い問いの語（隔週）は求めない。残る語 行う は引用に有る。§9.8。")
case("H-03", "H", "物見櫓の撮影は、許可制だ。", "物見櫓の撮影は自由ですか", "その通りです。", "unanchored", CN + "通り",
     "J-R5-3: 通り が名詞（普通名詞）で内容語 1 個。問いの語でないので R12 でなく 3b。引用に 通り が無い。")
# F: 偽の錨なし（J-R5-4）。正しい答えでも非自立可能の述語だけで確かめる語が無い
case("F-01", "F", "旧館の貸出は、学生にはできない。", "旧館の貸出は学生にもできますか", "できません。", "unanchored", NC,
     "J-R5-4: 正しい答えだが内容語 0 個（できる は 非自立可能）。偽の錨なしとして数える。")
with open(sys.argv[1], "w", encoding="utf-8") as f:
    for c in C:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print(len(C))

# J-R5-1: cases_r4c.jsonl の YC-02 の 3 つの欄だけ替えた写し
src = os.path.join(HERE, "..", "r4", "cases_r4c.jsonl")
out = []
for l in open(src, encoding="utf-8"):
    if not l.strip():
        continue
    c = json.loads(l)
    if c["id"] == "YC-02":
        c["expect"] = "unanchored"
        c["expect_reason_prefix"] = CN
        c["note"] += "（r5: K654 で閉じた。J-R5-1）"
    out.append(json.dumps(c, ensure_ascii=False) + "\n")
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.writelines(out)
print(len(out))
