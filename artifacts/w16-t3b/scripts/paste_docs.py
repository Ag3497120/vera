"""docs/FUSION.md の「### 10.9」から末尾までを、artifacts/w16-t3b/ の出力ファイルから機械で作り直す（第 2 ラウンド。第 1 ラウンドの版は artifacts/w16-t3b/round1/ に残してある）。
§10.12（事前登録 prereg2.txt）はそのまま挟み、その後に §10.13（第 2 ラウンドの測定）を貼る。使い方: cd <W> && paste_docs.py"""
import collections
import json
import os
import sys

W = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
A = os.path.join(W, "artifacts", "w16-t3b")


def rd(name, maxlines=None):
    t = open(os.path.join(A, name), encoding="utf-8").read().rstrip("\n")
    if maxlines:
        t = "\n".join(t.split("\n")[:maxlines])
    return t


def blk(t):
    return "```\n" + t + "\n```\n"


def tail(name):
    return rd(name).split("\n")[-1]


S = []
S.append("### 10.9 測定結果（`artifacts/w16-t3b/` の出力を機械で貼った）\n")

def table():
    out = []
    for name in ("cases.jsonl", "cases_b.jsonl", "cases_c.jsonl"):
        C = [json.loads(l) for l in open(os.path.join(A, name), encoding="utf-8") if l.strip()]
        n = collections.Counter((c["type"], c["expect"]) for c in C)
        tot = collections.Counter(c["type"] for c in C)
        out.append("%s（凍結版）: %d 件、RO+TE+SP+SR = %d 件" % (name, len(C), sum(tot[t] for t in ("RO", "TE", "SP", "SR"))))
        for t in ("RO", "TE", "SP", "SR", "H"):
            out.append("  %-2s 合計 %2d  %s" % (t, tot[t], dict(collections.Counter(c["expect"] for c in C if c["type"] == t))))
    return "\n".join(out)


S.append("#### 順序と凍結（第 1 ラウンド: `mtime_order.txt`・`prereg_time.txt`・`cases_time.txt`・`cases_b_time.txt`）\n" + blk(rd("mtime_order.txt") + "\nprereg_time: " + rd("prereg_time.txt") + "\ncases_time:  " + rd("cases_time.txt") + "\ncases_b_time: " + rd("cases_b_time.txt")))
S.append("凍結 sha（`prereg.sha256`・`cases.sha256`・`cases_b.sha256`。第 2 ラウンドの `prereg2.sha256`・`cases_c.sha256` は §10.13）:\n" + blk(rd("prereg.sha256") + "\n" + rd("cases.sha256") + "\n" + rd("cases_b.sha256")))
S.append("#### Q1 の件数: 型 × 期待 × 凍結版（チケットの文「4 つの型で 24 件以上」は RO・TE・SP・SR の合計。H は数えに入れない。表は機械で出した）\n" + blk(table()) +
         "cases.jsonl は 23 件（RO 6・TE 6・SP 5・SR 6）で 24 件に 1 件足りなかった（第 1 ラウンドのレビューの指摘。事前登録 §10.7 は H を含めた合計 24 と読み替えていた）。cases_c は第 2 ラウンドで SP を足して 28 件（H を数えに入れない）。試験 `test_cases_counts` は cases_c でこの合計を assert する。\n")
S.append("#### 直す前の赤・直した後（第 1 ラウンド: `cases_before.txt`・`cases_b_before.txt`・`cases_after.txt`）\n"
         "- `cases_before.txt`（凍結の cases.jsonl × 基点のコード）の末尾: `" + tail("cases_before.txt") + "`\n"
         "- `cases_b_before.txt`（cases_b × 基点のコード。`git archive HEAD` の写しで流した）の末尾: `" + tail("cases_b_before.txt") + "`\n"
         "- cases_b_before の失敗:\n" + blk("\n".join(l.split(" - ")[0] for l in rd("cases_b_before.txt").split("\n") if l.startswith("FAILED"))))
S.append("#### 攻撃の 4 形（`attack_four.txt`。期待は unanchored／unanchored／unanchored／relocated）\n" + blk(rd("attack_four.txt")))
S.append("#### T3-1（`t31/t31_result.txt` の先頭と `t31_diff.txt`）\n" + blk(rd("t31/t31_result.txt", 6)) + blk(rd("t31_diff.txt")))
S.append("#### T3-2（保存した raw の再照合。`t32_recheck.txt`）\n" + blk(rd("t32_recheck.txt")))
S.append("#### K653（`t33_k653.txt`）\n" + blk(rd("t33_k653.txt")))
S.append("#### 関係試験（`related_before.txt`・`related_after.txt`・`related_new_failures.txt`）\n" + blk("変更前: " + tail("related_before.txt") + "\n変更後: " + tail("related_after.txt") + "\n新しい失敗:\n" + rd("related_new_failures.txt")))
S.append("""#### 10.10 既存試験との衝突（3 件。書き換えていない。監査役への申し送り）
許可パス（`verantyx/quote_check.py`・`tests/test_w16t3b_*.py`・本節・`artifacts/w16-t3b/**`）の外にある既存試験 3 件が、チケットの規則と正面から衝突して赤になる。名前の変更・skip・xfail・期待の弱化はしていない。W16-t3 の J-R5-1 の先例にならい、許可されたら当てる差分を `artifacts/w16-t3b/proposed_existing_tests.diff`（ツリーには当てていない）に、写しで通ることの確認を `proposed_check.txt` に残した。
1. `tests/test_w16t3_quote_check.py::test_source_is_matched_by_basename_and_nfkc` の 1 行目: `q("docs/D1.txt", 1, "貸出は70日以内とする。")` に `found == "exact"` を求める。**R16（§10.5）と衝突**: 記録の source は `D1.txt`（ディレクトリの部分なし）、与えられた `docs/D1.txt` はディレクトリの部分を持つので `relocated`。新案: `found == "relocated"` と `source_record == ["D1.txt"]` にし、ファイル名だけの `D1.txt` は exact のまま（試験の名前は変えない）。
2. `tests/test_w16t3_content.py::test_case[C4-a3]`（凍結 `artifacts/w16-t3/r3b/cases_r3b.jsonl`）: 引用 `書類を受け取った。`・答え `書類を受け取ります。` に `anchored` を求める。**R14（§10.4）と衝突**: 同じ見出し語 `受け取る` で過去と非過去が食い違う。正しい言い換えが落ちる偽の錨なし（既知の穴の節）。新案: `unanchored`／`TENSE_DIFFERS:受け取る`。
3. `tests/test_w16t3_content.py::test_case[C4-a4]`: 引用 `部会を設ける。`・答え `部会を設けました。` に `anchored` を求める。**R14 と衝突**: `設ける` で非過去と過去。新案: `unanchored`／`TENSE_DIFFERS:設ける`。
新案の 2・3 は凍結データを書き換えず、2 件の `expect`・`expect_reason_prefix`・`note` だけ替えた写し `artifacts/w16-t3b/proposed_apply/cases_r3b_t3b.jsonl`（他の行は byte 一致）を `tests/test_w16t3_content.py` が読む形にする。**差分はこの写しを新しいファイルとして自分で作る**ので、`git archive HEAD` の木に `patch -p1 < artifacts/w16-t3b/proposed_existing_tests.diff` だけで当てられる（第 2 ラウンドで、第 1 ラウンドの差分が `proposed/` の置き場所と合っていなかったのを直した。`artifacts/w16-t3b/proposed/cases_r3b_t3b.jsonl` は参照用の写しで同じ内容）。いずれも「正しい答えが落ちる」側への変更で、誤答を通す変更ではない。**監査役への申し送り: この 3 件の期待を替えることの承認をお願いする。**
旧・新の全文（`proposed_existing_tests.diff` 全文）:
""" + blk(rd("proposed_existing_tests.diff")))
S.append("`proposed_check.txt` の末尾（`git archive HEAD` の写しに新しいコードと `artifacts/w16-t3b/` を重ね、差分を `patch -p1 <` だけで当て、T3 の `tests/test_w16t3_*.py` と本件の `tests/test_w16t3b_*.py` を流した）: `" + tail("proposed_check.txt") + "`\n")
S.append("""#### 10.11 既知の穴（隠さない）
例はすべて実際に流した出力（`artifacts/w16-t3b/holes_probe.txt`。作るスクリプトは `artifacts/w16-t3b/scripts/holes_probe.py`）から機械で貼った。各行の正誤（correct／wrong）は手で決め、分類（閉じない型・偽の錨なし）は出力から機械で付けた。いずれも規則どおりの動きで、広げて直さない（語の一覧を足さない）。
- **正しい言い換えが落ちる（偽の錨なし）**: R13 は受け身・目的語の主題化（は／を）・対称な と・に と へ（H-01〜H-03、N-01）、R14 は連用中止形（N-02。連なりが空なので非過去と数える）・丁寧形の時制違い（N-03、既存の C4-a3・C4-a4。§10.10）。理由の見出し語は unidic のもの（`為る` など）。
- **閉じない型（誤答が anchored のまま）**: R14 は て で終わる連なりを比べない（N-04。引用が非過去で答えが過去の誤答が通る）、名詞＋だ の述語は対象外（N-05）。H-04（`鍵を開けた。` × `鍵を開けて、点検した。`）は引用が過去なので **正しい答えの対照**（anchored が正しい。閉じない型ではない）。
- 名詞の連なりの切れ方が答えと引用で違う語（N-06）は R13 の対象にならず、既存の 3b が先に落とす（誤答は落ちる）。R13 は 連なり ＋ 直後の助詞の 1 語だけを見る（係り受けは見ない）。
- R15（第 2 ラウンドの改訂後）: 問いの語の繰り返しでも、実在した引用のどれかに現れる語は項目に入れるので、N-08・N-09 は ANSWER_SPLIT_ACROSS_QUOTES で落ちる。問いの語がどの引用にも無い答えは項目に入れず、1 つの引用で支えられれば anchored（N-07、SP-09）。
- R16 は印を変えない（`found` と鍵だけ）。記録の source はファイル名だけなので、ディレクトリの部分を持つ source（`./x`・絶対パス含む）はすべて relocated。
- 数値の根拠は出力ファイルだけ。T3 の伏せた集合・基線は監査役が測る（実装役は流していない）。

#### holes_probe.txt（全文）
""" + blk(rd("holes_probe.txt")))
prereg2 = open(os.path.join(A, "prereg2.txt"), encoding="utf-8").read().rstrip("\n")
S.append("\n" + prereg2 + "\n")
S.append("### 10.13 第 2 ラウンドの測定（`artifacts/w16-t3b/` の出力を機械で貼った）\n")
S.append("#### 順序と凍結（`mtime_order_r2.txt`・`prereg2_time.txt`・`cases_c_time.txt`）\n" + blk(rd("mtime_order_r2.txt") + "\nprereg2_time: " + rd("prereg2_time.txt") + "\ncases_c_time: " + rd("cases_c_time.txt") + "\n" + rd("prereg2.sha256") + "\n" + rd("cases_c.sha256")))
S.append("#### cases_c の型 × 期待（`cases_c_types.txt`）\n" + blk(rd("cases_c_types.txt")))
S.append("#### 直す前の赤・直した後（第 1 ラウンドのコード × cases_c = `cases_c_before.txt`、改訂後 = `cases_c_after.txt`）\n"
         "- 失敗の件数（`grep -c '^FAILED' cases_c_before.txt`）と末尾: `" + tail("cases_c_before.txt") + "`\n- 直す前の失敗:\n" + blk("\n".join(l.split(" - ")[0] for l in rd("cases_c_before.txt").split("\n") if l.startswith("FAILED"))) +
         "- 直した後（cases_c と rules）の末尾: `" + tail("cases_c_after.txt") + "`\n")
S.append("#### 攻撃の 4 形（改訂後。`attack_four.txt`。期待は unanchored／unanchored／unanchored／relocated）\n" + blk(rd("attack_four.txt")))
S.append("#### T3-1（改訂後。`t31/t31_result.txt` の先頭と `t31_diff.txt`。基点 = ecde332 の写し）\n" + blk(rd("t31/t31_result.txt", 6)) + blk(rd("t31_diff.txt")))
S.append("#### T3-2（改訂後。`t32_recheck.txt`）\n" + blk(rd("t32_recheck.txt")))
S.append("#### K653（改訂後。`t33_k653.txt`）\n" + blk(rd("t33_k653.txt")))
S.append("#### 関係試験（改訂後。`related_before.txt`・`related_after.txt`・`related_new_failures.txt`）\n" + blk("変更前: " + tail("related_before.txt") + "\n変更後: " + tail("related_after.txt") + "\n新しい失敗:\n" + rd("related_new_failures.txt")))
S.append("既存試験 3 件との衝突の提案（§10.10）は第 2 ラウンドで差分を自己完結に作り直した。写しの確認: `" + tail("proposed_check.txt") + "`\n")
fp = os.path.join(W, "docs", "FUSION.md")
doc = open(fp, encoding="utf-8").read()
cut = doc.index("\n### 10.9 ")
open(fp, "w", encoding="utf-8").write(doc[:cut].rstrip("\n") + "\n\n" + "\n".join(S))
print("ok")
