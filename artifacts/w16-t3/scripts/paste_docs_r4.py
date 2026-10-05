"""第 4 ラウンドの docs 追記（§9.4・§9.7・§9.8 に追記、§9.14 を末尾に足す）。数値は r4/ の出力ファイルから読む。削除はしない。"""
import collections
import json
import re

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
R4 = W + "/artifacts/w16-t3/r4/"
D = W + "/docs/FUSION.md"


def rd(n):
    return open(R4 + n, encoding="utf-8").read()


s = open(D, encoding="utf-8").read()
assert "### 9.14 " not in s

j = """- **J-R4-1（第 4 ラウンド。撤回）** 応答の語を含まない答え（`そうです。`）を `NO_CONTENT_TO_CHECK` で `unanchored` にする案は、既存の試験 `test_no_elements_with_a_real_quote_is_anchored`（答え `そうです` → `anchored`）と衝突したので撤回した（§9.13b）。3c は応答の語（感動詞・`違う`）を含む答えだけ。
- **J-R4-2** `tests/test_w10f05_cli.py` 154 行目を dev `a7507b3` の行に戻した（§9.7 の末尾。T2 の merge で記録が答える経路になり、`quote_check` が作られないため。`git diff a7507b3 -- tests/test_w10f05_cli.py` は空）。
- **J-R4-3** `違う`（動詞）を応答の語に入れた。裁定の文（はい・いいえ・ええ・違う 等）の名指しどおりで、他の語は足していない。
- **J-R4-4** 3c に当たる答えでは、3b の未被覆が `違う` だけのとき理由は `YESNO_NOT_CHECKED` を優先する（verdict は同じ）。
- **J-R4-5** 3c・3d の判定に使う解析は、答えの全文（`_analyze(answer)`）と各実在引用の text。問いは選択の問いかどうかの判定（R11）にだけ使う。
"""
i = s.index("### 9.5 ")
s = s[:i].rstrip("\n") + "\n" + j + "\n" + s[i:]

before = "    assert 'placement_layer' not in base['vera'] and list(base['vera']) == ['schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'timing']"
after = before.replace("'outcome', 'timing']", "'outcome', 'quote_check', 'timing']")
k = """
##### （第 4 ラウンド）tests/test_w10f05_cli.py の同じ試験の 154 行目を dev の期待に戻した

第 3 ラウンドの裁定 4 で足した `'quote_check'` を外し、154 行目は dev `a7507b3` の行と byte 一致（`git diff a7507b3 -- tests/test_w10f05_cli.py` は 0 行）。理由: 統合した T2 の変更で、この試験の問い（記録が `QUESTION_CROSS` で答える）は LLM を呼ばなくなり、`quote_check` の鍵は作られない。`-vv` の出力 `r4/w10f05_vv.txt`（戻す前）は `At index 10 diff: 'timing' != 'quote_check'`。期待は弱まらない（完全一致の assert のまま）。名前・他の行は変えていない。

戻す前の全文（154 行目）:

%s

戻した後の全文（154 行目）:

%s
""" % (after, before)
i = s.index("### 9.8 ")
s = s[:i].rstrip("\n") + "\n" + k + "\n" + s[i:]

h = """
- **（第 4 ラウンド）極性・はい／いいえ・選択の問いは閉じた（ただし範囲つき）**: 答えに述語があるときの否定の有無の食い違い（3d）、応答の語だけの答え（3c）、選択の問いでの問いの語の被覆（R11）。以下は残る穴。
- **F 型の偽の錨なし（規則どおり。誤検出として数える）**: 否定は有無だけを見るので、引用の連体修飾・条件の中の否定（`役員でない会員には、議事録を配る。`／`雨天でない場合は…`）に対して肯定の正しい答え（`配ります`）は `POLARITY_DIFFERS` で `unanchored` になる（F-01・F-02）。選択の問いでは問いの語（`会場は`）を繰り返す正しい答えも、引用に無ければ `ANSWER_CONTENT_NOT_IN_QUOTE` で `unanchored`（F-03）。直すために「問いと同じ否定は除く」などの語の規則を足していない（安全側で残す）。
- **`AかBですか`（`か` が 1 か所）は選択の問いにならない**: R11 は `どちら`／`どっち`、または 名詞・接尾辞 の直後の `か` が 2 か所以上。`会議は東館か西館ですか` の取り違えは、問いの語として被覆から外れるため見逃す。語を足して直さない。
- **否定は有無だけで数を数えない**: 二重否定（`行わないわけではない`）も「有り」。引用が否定、答えも否定の二重否定なら比べて一致する。
- **述語の無い答えの否定は比べない**: `月曜日です`（名詞＋です）は述語でないので、引用が `月曜日は休まない` でも `anchored`（O-01）。
- **`そうです` は確かめないまま `anchored`（J-R4-1 の撤回の帰結）**: 要素・述語・内容語が無く、応答の語も無い答えは、実在する引用があれば `anchored`（既存の試験 `test_no_elements_with_a_real_quote_is_anchored` と同じ型。O-02 は `cases_r4b.jsonl` で `anchored`）。「anchored = 確かめた」の主張に穴が残る。
- **偽の conflict（P16／P17 の型。第 3 ラウンドのレビューの申し送り 2。裁定 5 で残す）**: 実在する 2 つの引用の同じ種類の要素（固有名・数値）が文書間で違うと、答えに関係なく `conflict` になる。安全側。
- **偽の錨なし（P03 の型。R1′ の帰結。裁定 5 で残す）**: `第7窓口` と `第七窓口` のように、表記が違うだけの正しい答えは数詞が内容語として比べられ `unanchored` になる。
- **形態素解析の分割が文脈で揺れる**: 同じ語 `東館` が `、` の直後では `東`＋`館`、`は` の直後では `東館` の 1 語になる（unidic。自作の検査データの作成中に確認）。語の表層で比べるので、引用と答えで分割が違うと正しい答えでも未被覆になりうる（偽の錨なし）。
"""
i = s.index("### 9.9 ")
s = s[:i].rstrip("\n") + "\n" + h + "\n" + s[i:]


def tail(n, k=1):
    return "\n".join(rd(n).strip().split("\n")[-k:])


cases = [json.loads(l) for l in open(R4 + "cases_r4b.jsonl", encoding="utf-8") if l.strip()]
cnt = collections.Counter("%s/%s" % (c["type"], c["expect"]) for c in cases)
t31 = rd("t31_result.txt").split("\n")
sp = rd("t31_serve_path.txt").split("\n")[0]
spb = rd("t31_serve_path_before.txt").strip()
t32 = rd("t32_recheck.txt").strip()
k653 = rd("t33_k653.txt").strip()
related = tail("related_after.txt")
related_before = tail("related_before.txt")
sec = """
### 9.14 第 4 ラウンドの測定（`artifacts/w16-t3/r4/`。出力ファイルから機械で貼った。`r3/`・`r3b/` は上書きしていない）

#### 順序と凍結
- 事前登録 §9.13（日時 `r4/prereg_r4_time.txt` = %s、`prereg_r4.sha256`）→ 検査データ凍結 `cases_r4.jsonl`（29 件、`cases_r4.sha256`、日時 `cases_r4_time.txt` = %s）→ 直す前の赤（`cases_before.txt`）→ コード。コードを書いた後に J-R4-1 を撤回した（§9.13b。`cases_r4b.jsonl`、`cases_r4b.sha256`、日時 `cases_r4b_time.txt` = %s。O-02 の期待だけ違う）。
- 型 × 期待（`cases_r4b.jsonl`）: %s
- 直す前（`cases_before.txt`）の末尾: `%s`（赤 21 件 = P 8・Y 4・YP-02・S 4・F 3・O-02 のほか、対照（PC・SC・YP-01・O-01）と凍結の試験は通った）。直した後（`cases_after.txt`）: `%s`。
- 3 つの t3 試験＋新規（`t3_tests.txt`）: `%s`。

#### T3-1（自作の集合。T3-4 の伏せた集合が本番）— `r4/t31_result.txt`・`r4/t31_diff.txt`・`r4/t31_serve_path.txt`
%s
- 第 3 ラウンド（`r3b/t31_result.txt`）との印の変化（全件。`t31_diff.txt`）:

```
%s
```
- serve の経路（`t31_serve_path.txt` の 1 行目）: %s。変更前（`t31_serve_path_before.txt`）: %s。第 3 ラウンドの 60 件「同じ 60」から「記録が答えた 5」に変わったのは、統合した W16-t2 で記録が `QUESTION_CROSS` で答える問いが増えたため（T3 の規則の効果ではない。S1-ANS-04/08/09・S3-ANS-03/04）。

#### T3-2（実機は流し直さず、保存した raw を再照合）— `r4/t32_recheck.txt`
```
%s
```

#### T3-3（K653 の byte 一致。基線は dev `a7507b3` の写し）— `r4/t33_k653.txt`
```
%s
```
- 基線を基点 `3a1677c` から dev `a7507b3` に替えた理由: T2 の merge で serve の出力が変わり、古い基線では「外」の 35 行が変わって見える。基線は `git archive a7507b3` の写しで取り直した（中間職の写しと `cmp` 一致）。
- 第 3 ラウンド後の写し（`serve_head.jsonl`）と今回の 310 行を比べると、違う行は 0（`r4/t33_verdict_changes.txt`）。

#### 関係試験（18 ファイル＋新規）
- 変更前（`related_before.txt`）: `%s`（落ちた 1 件は `test_w10f05_cli.py` の 154 行目。§9.7 の第 4 ラウンドの項）。
- 変更後（`related_after.txt`）: `%s`。新しい失敗 0（`related_new_failures.txt` が 0 byte）。
- 監査役の「関係テスト 236 passed」の集合には `test_w10f05_cli.py` が入っていなかったと見られる（上の 18 ファイルでは変更前に 1 件落ちた）。
""" % (
    rd("prereg_r4_time.txt").strip(), rd("cases_r4_time.txt").strip(), rd("cases_r4b_time.txt").strip(),
    json.dumps(dict(sorted(cnt.items())), ensure_ascii=False),
    tail("cases_before.txt"), tail("cases_after.txt"), tail("t3_tests.txt"),
    "\n".join("- " + l for l in t31[:6] if l.strip()), rd("t31_diff.txt").strip(), sp, spb, t32, k653, related_before, related,
)
s = s.rstrip("\n") + "\n" + sec
open(D, "w", encoding="utf-8").write(s)
