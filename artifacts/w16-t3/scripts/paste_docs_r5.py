"""第 5 ラウンドの docs 追記（§9.4 J-R5、§9.8、§9.16b、§9.17）。数値・出力は r5/ のファイルから貼る。予想は書かない。"""
import collections
import json
import os

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
R5 = W + "/artifacts/w16-t3/r5/"
D = W + "/docs/FUSION.md"
BENCH = "/Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S/benchmarks/public_v1/data/questions.jsonl"


def rd(p):
    return open(p, encoding="utf-8").read()


def tail(p, n=1):
    return "\n".join([l for l in rd(p).split("\n") if l.strip()][-n:])


s = rd(D)
assert "### 9.17 " not in s and "### 9.16b " not in s

# --- §9.4: J-R5-1〜5 ---
a = "- **J-R4-5** "
i = s.index(a)
j = s.index("\n", i) + 1
j4 = """- **J-R5-1（第 5 ラウンド。裁定 3 との衝突）** 裁定 2 は R28（そうです。）・E07／G13（はい、支払います。）の型を閉じることを求め、裁定 3 は「ほかの既存の試験の期待は変えない」と定める。第 4 ラウンドの凍結データの O-02（`cases_r4b.jsonl`、`そうです。` → `anchored`）と YC-02（`cases_r4c.jsonl`、`はい、社内の人が務めます。` → `anchored`）はこの 2 つの型を既知の穴として `anchored` と書いたもので、K654 を入れると必ず赤になる。裁定 2 の目的を優先し、期待を強める側（anchored → unanchored）だけ替えた。凍結済みのファイルは書き換えていない: O-02 は `tests/test_w16t3_r4.py` の読み先を `cases_r4.jsonl`（最初に凍結した版。O-02 の期待は `unanchored`／`NO_CONTENT_TO_CHECK`）に戻し、YC-02 は `r5/cases_r4c_r5.jsonl`（YC-02 の `expect`・`expect_reason_prefix`・`note` だけ替えた写し。他の 10 件は byte 一致）を読む。**監査役への申し送り: この 2 件の期待を替えたことの確認をお願いする。**
- **J-R5-2** `そう（です）` は 3c の応答の語に入れない（§9.16）。
- **J-R5-3** `その通りです。` は `通り` が名詞（普通名詞）で内容語 1 個なので 3b に落ちる（§9.16、H-03）。
- **J-R5-4** `非自立可能` の述語だけの答え（`できません。`）は内容語 0 個で、正しい答えでも `NO_CONTENT_TO_CHECK`（F-01。偽の錨なし）。
- **J-R5-5** R2（名詞と動詞の表層一致）は変えない。閉じない型は §9.8 に開示（H-01・H-02）。
"""
s = s[:j] + j4 + s[j:]

# --- §9.8: 3 行の行末と新しい穴 ---
suffix = "（第 5 ラウンドで閉じた。§9.16）"
for head in ("- **`そうです` は確かめないまま `anchored`（J-R4-1 の撤回の帰結）**", "- **述語を伴う答えは極性だけ（残る穴）**", "- **問いの語だけの答え（応答の語なし）**"):
    i = s.index(head)
    j = s.index("\n", i)
    assert s[i:j].endswith("。")
    s = s[:j] + suffix + s[j:]
i = s.index("- **問いの語だけの答え（応答の語なし）**")
j = s.index("\n", i) + 1
h98 = """- **（第 5 ラウンド）閉じたもの**: `そうです` 型・問いの語だけの答え・述語つきの言い直しは R12（K654）で閉じた（O-02・YC-02・E02 型・R31 型。検査データ `cases_r5` の SO・QO・PR）。
- **（第 5 ラウンド）残る穴（J-R5-3〜5）**: (1) `その通りです。` は `通り` が名詞なので R12 でなく 3b に落ち、引用に `通り` があれば `anchored`（裁定の例との違い。H-03 は引用に無い場合）。(2) `できません。`・`あります。` など `非自立可能` の述語だけの正しい答えは内容語 0 個で `NO_CONTENT_TO_CHECK`（偽の錨なし。F-01。T3-2 の再照合では S4-ANS-06 の 1 行）。(3) R2 により、答えの動詞と引用の名詞の表層が等しければ被覆される（`はい、支払います。` + 引用に名詞 `支払い`。H-01）。(4) 答えが問いの要の語を落とした言い直し（`はい、行います。`、問い `…隔週で行いますか`。H-02）は、答えに無い問いの語は求めないので閉じない。いずれも `anchored` になりうる（確かめていないのに確かめたと言う型）。
"""
s = s[:j] + h98 + s[j:]

# --- §9.16b ---
if not s.endswith("\n"):
    s += "\n"
t0 = rd(R5 + "cases_r5_time.txt").strip()
tb = rd(R5 + "cases_r5b_time.txt").strip()
tc = rd(R5 + "mtime_order.txt").strip().split("\n")
s += f"""
### 9.16b SO-03 の理由の訂正（記録 {tb}。コードを書いた後の訂正であることを隠さない）

`cases_r5.jsonl`（凍結 {t0}）の SO-03（答え `左様です。`）の期待を、私は §9.16 の規則から `NO_CONTENT_TO_CHECK` と決めたが、`左様` は形状詞で、R1′（§9.9 R1）の内容語に **入る**（`pos1 ∈ {{名詞, 動詞, 形容詞, 形状詞, …}}`）。内容語は 1 個で、問いの語でないので R12 でなく既存の 3b が動き、理由は `ANSWER_CONTENT_NOT_IN_QUOTE:左様` になる（印は `unanchored` で期待どおり）。期待を決めるときに内容語の定義を読み違えた（品詞は見たが、形状詞が内容語かを §9.9 で確かめなかった）。`cases_r5.jsonl` は書き換えず、SO-03 の `expect_reason_prefix` と `note` だけ替えた `cases_r5b.jsonl`（`make_cases_r5b.py`。他の 19 件は byte 一致）を凍結し、`tests/test_w16t3_r5.py` はこれを読む（凍結の検査は両方）。SO の「内容語 0 個」の型は SO-01・SO-02・SO-04 の 3 件。事前登録の順序: 事前登録 → cases_r5 凍結 → 試験の変更と赤 → コード → **cases_r5b の凍結（コードより後）**。
"""
s += "\n### 9.17 第 5 ラウンドの測定（`artifacts/w16-t3/r5/`。出力ファイルから機械で貼った。`r3/`〜`r4c/` は上書きしていない）\n\n"
s += "#### 順序と凍結\n```\nprereg: %s\ncases_r5/cases_r4c_r5: %s\ncases_r5b: %s\n```\n" % (rd(R5 + "prereg_r5_time.txt").strip(), t0, tb)
s += "mtime（`mtime_order.txt`。事前登録 → cases_r5 → 直す前の赤 → quote_check.py）:\n```\n%s\n```\n" % "\n".join(tc)
s += "凍結 sha（`cases_r5.sha256`・`cases_r5b.sha256`）:\n```\n%s%s```\n" % (rd(R5 + "cases_r5.sha256"), rd(R5 + "cases_r5b.sha256"))
C = [json.loads(l) for l in open(R5 + "cases_r5b.jsonl", encoding="utf-8") if l.strip()]
cnt = collections.Counter("%s/%s" % (c["type"], c["expect"]) for c in C)
s += "#### 検査データ（cases_r5b。%d 件）の型 × 期待\n```\n%s\n```\n" % (len(C), json.dumps(dict(sorted(cnt.items())), ensure_ascii=False))
s += "#### 直す前／後（`cases_before.txt`・`cases_after.txt`。w16t3_r5・w16t3_r4・w16t3_quote_check）\n```\n直す前:\n%s\n直した後:\n%s\n```\n" % (
    "\n".join(l[:120] for l in rd(R5 + "cases_before.txt").split("\n") if l.startswith("FAILED") or " passed" in l or " failed" in l),
    tail(R5 + "cases_after.txt"))
s += "#### w16t3 の試験（`t3_tests.txt`）\n```\n%s\n```\n" % tail(R5 + "t3_tests.txt")
s += "#### T3-1（`t31_result.txt` の先頭・`t31_diff.txt` 全文）\n```\n%s\n--- t31_diff.txt ---\n%s\n```\n" % (
    "\n".join(rd(R5 + "t31_result.txt").split("\n")[:6]), rd(R5 + "t31_diff.txt").strip())
# T3-2
rc = rd(R5 + "t32_recheck.txt").split("\n")
sel = [l for l in rc if l.startswith("今の QC.check") or l.startswith("違う行") or l.startswith("保存の印") or l.startswith("今の印") or l.startswith("anchored 以外") or l.startswith("reason の分布") or "->" in l and l.startswith("S")]
s += "#### T3-2（保存した raw の再照合。`t32_recheck.txt`）\n```\n%s\n```\n" % "\n".join(l[:260] for l in sel)
s += "r4c との差（`t32_recheck_vs_r4c.diff`）:\n```\n%s\n```\n" % rd(R5 + "t32_recheck_vs_r4c.diff").strip()
# 分類
r4c_rows = {l.split()[0] for l in rd(W + "/artifacts/w16-t3/r4c/t32_recheck.txt").split("\n") if "->" in l and l.startswith("S")}
new_rows = [l for l in rc if "->" in l and l.startswith("S") and l.split()[0] not in r4c_rows]
bench = {}
for l in open(BENCH, encoding="utf-8"):
    if l.strip():
        b = json.loads(l)
        bench[b["id"]] = b
s += "r4c から増えた行（%d 行）の分類（W14 公開バンクの正解 `answer` を引いた。読み取りのみ）:\n" % len(new_rows)
for l in new_rows:
    i = l.split()[0]
    b = bench[i]
    ans = l.split("答え=")[1].split(" 引用=")[0]
    s += "- `%s` 答え `%s`、W14 の正解 `%s`（distractors %s）。答えは正解と同じ内容（否定）で正しい → **正しい答えの偽の錨なし**（J-R5-4。分類は私が正解の文字列を読んで判断した）。\n" % (
        i, ans, b["answer"], json.dumps(b["distractors"], ensure_ascii=False))
# K653
s += "#### K653（`t33_k653.txt`・`t33_vs_r4c.txt`）\n```\n%s\n--- t33_vs_r4c.txt ---\n%s\n```\n" % (
    "\n".join(l.replace("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/", "$SC/") for l in rd(R5 + "t33_k653.txt").strip().split("\n")),
    rd(R5 + "t33_vs_r4c.txt").strip())
s += "#### 関係試験（`related_before.txt`・`related_after.txt`・`related_new_failures.txt`）\n```\n変更前: %s\n変更後: %s\n新しい失敗: %d byte\n```\n" % (
    tail(R5 + "related_before.txt"), tail(R5 + "related_after.txt"), os.path.getsize(R5 + "related_new_failures.txt"))
open(D, "w", encoding="utf-8").write(s)
print("ok")
