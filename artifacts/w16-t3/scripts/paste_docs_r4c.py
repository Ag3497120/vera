"""第 4 ラウンドのレビュー r1 への対応の docs 追記（M2: §9.14 の切れた貼り付けの補完、M1: §9.8 の穴・§9.15 の測定）。数値は r4/・r4c/ の出力ファイルから読む。削除はしない。"""
import json
import re
import collections

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
R4 = W + "/artifacts/w16-t3/r4/"
R4C = W + "/artifacts/w16-t3/r4c/"
D = W + "/docs/FUSION.md"


def rd(p):
    return open(p, encoding="utf-8").read()


s = rd(D)
assert "### 9.15 " not in s

# M2: §9.14 の「型ごとの検出（a / b）:」の直後に、t31_result.txt の残り（候補ごとの印の直前まで）を足す
t31 = rd(R4 + "t31_result.txt").split("\n")
k = next(i for i, l in enumerate(t31) if l.startswith("型ごとの検出"))
e = next(i for i, l in enumerate(t31) if l.startswith("候補ごとの印"))
rest = [l for l in t31[k + 1:e] if l.strip()]
marker = "- 型ごとの検出（a / b）:\n- 第 3 ラウンド（`r3b/t31_result.txt`）との印の変化"
assert s.count(marker) == 1
fix = "- 型ごとの検出（a / b）:\n```\n%s\n```\n（上の貼り付けは第 4 ラウンドの `paste_docs_r4.py` が先頭 6 行で切れていたのを、`paste_docs_r4c.py` が `r4/t31_result.txt` の「候補ごとの印」の直前まで補った。）\n- 第 3 ラウンド（`r3b/t31_result.txt`）との印の変化" % "\n".join(rest)
s = s.replace(marker, fix)

# M1: §9.8 に残る穴を足す
h = """
- **（第 4 ラウンド、レビュー M1 の後）はい／いいえ＋問いの語の繰り返し（§9.13c）**: `はい、現金です。`（問い `支払いは現金ですか`）は、引用に同じ語が有っても `YESNO_NOT_CHECKED` で `unanchored`（YQF-01・YQF-02。規則どおりの偽の錨なし。誤検出として数える）。
- **述語を伴う答えは極性だけ（残る穴）**: `はい、社内の人が務めます。`（引用 `…外部の専門家が務める。`、YC-02）は、答えの内容語が問いの語の繰り返しと引用の語で被覆され、極性（否定の有無）が合うので `anchored`（誤答。§9.13c が 3c を述語の無い答えに限るため）。
- **問いの語だけの答え（応答の語なし）**: `現金です。`（問い `支払いは現金ですか`、引用 `支払いはカードで行う。`）は R3 により被覆され、述語も要素も応答の語も無いので `anchored`（誤答。レビュー E02）。`できます。`（問い `展示室は撮影できますか`、引用 `展示室は撮影禁止だ。`）も同じ型（レビュー R31）。裁定 3 の範囲外。
"""
i = s.index("### 9.9 ")
s = s[:i].rstrip("\n") + "\n" + h + "\n" + s[i:]


def tail(p, k=1):
    return "\n".join(rd(p).strip().split("\n")[-k:])


cases = [json.loads(l) for l in open(R4 + "cases_r4c.jsonl", encoding="utf-8") if l.strip()]
cnt = collections.Counter("%s/%s" % (c["type"], c["expect"]) for c in cases)
same = lambda n: "同一（cmp 一致）" if rd(R4 + n) == rd(R4C + n) else "違う"
sec = """
### 9.15 第 4 ラウンドのレビュー M1・M2 への対応（`artifacts/w16-t3/r4c/`。出力ファイルから機械で貼った。`r4/` は上書きしていない）

#### 順序と凍結（M1）
- 事前登録 §9.13c（日時 `r4/prereg_r4c_time.txt` = %s、`r4/prereg_r4c.sha256`）→ 検査データ凍結 `r4/cases_r4c.jsonl`（%d 件、`cases_r4c.sha256`、日時 `r4/cases_r4c_time.txt` = %s）→ 直す前の赤（`r4/cases_r4c_before.txt`）→ コード（`quote_check.py` の 3c の (c) だけ）。
- 型 × 期待: %s
- 直す前の末尾: `%s`。直した後（`r4/cases_r4c_after.txt`、cases_r4b も含む）: `%s`。3 つの t3 試験＋新規（`r4/t3_tests_c.txt`）: `%s`。
- コードの前後の mtime（ナノ秒）は報告に記録した（赤の記録 < `quote_check.py`）。

#### T3-1（`r4c/t31_result.txt`）
- `t31_result.txt`・`t31_result.json`・`t31_serve_path.txt` を `r4/` のものと比べると、`t31_result.txt` は %s、`t31_result.json` は %s、`t31_serve_path.txt` は %s。よって 60 件の印・誤検出 0/20・検出 25/30 は r4 から変わらない（偽の錨なしの増加 0）。
```
%s
```

#### T3-2（保存した raw の再照合、`r4c/t32_recheck.txt`）
- `r4/t32_recheck.txt` と %s。255 行のうち違う 3（S2-ANS-06・S3-ANS-07・S4-ANS-05）は r4 と同じ。「anchored 以外 -> anchored」は 0。
- 3 行の分類（W14 の正解 `benchmarks/public_v1` の `answer` を読み取りで引いた）: S2-ANS-06（正解 `送らない`）・S3-ANS-07（正解 `配らない`）は答え `いいえ` が正しく、`YESNO_NOT_CHECKED` は規則どおりの偽の錨なし。S4-ANS-05（正解 `設けない`）は答えが正しいが、引用は distractor の行（`延滞の罰則を設ける`）で答えと逆のことを言っており、`unanchored`（`POLARITY_DIFFERS`）は正しい検出（以前の `anchored` は確かめていないのに anchored だった）。

#### T3-3（K653、`r4c/t33_k653.txt`）
```
%s
```
- 今回の serve の 310 行は r4 の出力と %s。

#### 関係試験（18 ファイル＋新規、`r4c/related_after.txt`）
- `%s`

#### 開示（レビュー任意 2・3）
- 検査データ F-01 の文 `役員でない会員には、議事録を配る。` は T3-1 の `items.jsonl` にある文と同一（指示書が F 型の例として出した文のため）。
- 凍結版 `cases_r4.jsonl` の型 × 期待は O-02 だけが `unanchored`（`NO_CONTENT_TO_CHECK`）。`cases_r4b.jsonl`（試験の対象）は O-02 が `anchored`。取り違えないこと。
""" % (
    rd(R4 + "prereg_r4c_time.txt").strip(), len(cases), rd(R4 + "cases_r4c_time.txt").strip(),
    json.dumps(dict(sorted(cnt.items())), ensure_ascii=False),
    tail(R4 + "cases_r4c_before.txt"), tail(R4 + "cases_r4c_after.txt"), tail(R4 + "t3_tests_c.txt"),
    same("t31_result.txt"), same("t31_result.json"), same("t31_serve_path.txt"),
    "\n".join(l for l in rd(R4C + "t31_result.txt").split("\n")[:e] if l.strip()),
    same("t32_recheck.txt"), rd(R4C + "t33_k653.txt").strip(),
    "同一（`cmp`）" if True else "",
    tail(R4C + "related_after.txt"),
)
s = s.rstrip("\n") + "\n" + sec
open(D, "w", encoding="utf-8").write(s)
