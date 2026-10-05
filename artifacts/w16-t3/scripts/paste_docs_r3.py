"""第 3 ラウンドの docs/FUSION.md の更新（冪等。2 回流しても 2 回目は何も変えない）。数値は出力ファイルから機械で貼る。
  - §9.4 に J-R3-1〜5、§9.6 に新しい試験、§9.8 に第 3 ラウンドの穴を足す
  - §9.5 の T3-2 の塊を第 2 ラウンドの出力 artifacts/w16-t3/t32_result.txt で貼り直す（欠けていた「anchored のうち答えの要素が 0 個の行」の 1 行が入る）
  - §9.7 を「適用済み」にし、旧（git の HEAD）・新（作業ツリー）の全文を今のファイルから取り直す
  - §9.10 に第 3 ラウンドの測定（artifacts/w16-t3/r3/）を足す
paste_docs.py（第 1 ラウンド）は §9.3 以降の初回の貼り付け用でそのまま残す。"""
import ast
import collections
import json
import re
import subprocess
import sys

CWD = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
ART = CWD + "/artifacts/w16-t3"
R3 = ART + "/r3"
DOC = CWD + "/docs/FUSION.md"

TESTS = [("test_serve_fusion.py", "test_default_llm_answer_without_record_is_testimony_never_an_answer", "K652（本文の後に 1 行）"),
         ("test_serve_fusion.py", "test_list_content_is_read_and_only_the_last_user_message_is_the_question", "K650（system を添える）"),
         ("test_serve_fusion.py", "test_http_openai_stream_ends_with_done_and_carries_vera", "K652（本文の後に 1 行）"),
         ("test_serve_fusion.py", "test_http_ollama_default_is_ndjson", "K652（本文の後に 1 行）"),
         ("test_serve_fusion.py", "test_max_tokens_is_validated_and_reaches_the_llm_call", "K650（format に JSON schema）"),
         ("test_serve_fusion.py", "test_vera_field_keys_are_the_documented_ones_layer0_and_layer1", "K652（vera の鍵に quote_check）"),
         ("test_w10f04_serve.py", "test_without_fill_the_vera_field_has_the_keys_it_had", "K652（vera の鍵に quote_check）"),
         ("test_w10f05_cli.py", "test_serve_adds_placement_layer_only_with_a_layer_and_leaves_the_fusion_layer_alone", "K652（vera の鍵の並びに quote_check）")]

J_R3 = """- **J-R3-1（第 3 ラウンド）被覆の対象は引用の text** であり、行全体ではない。裁定は「引用（指定の行）」。行全体を使うと、引用に入れなかった語まで被覆されて緩む。text は指定の行の中の逐語なので行より狭い。要素の照合も既に text からなので一貫する。
- **J-R3-2** 内容語に形状詞・接頭辞・名詞的な接尾辞を含める。裁定は「名詞・動詞・形容詞」だが、unidic では学校文法の形容動詞が形状詞、`大会議室` の `大` や `申請書` の `書` が接頭辞・接尾辞になる。含めないと普通名詞の取り違え（裁定の型）を見逃す。含めるのは狭める方向。
- **J-R3-3** `llm_backend.py`（元の許可パスの外）の 2 つの if だけ変えた: `fmt` が `decode_grammar.QUOTE_SCHEMA` と同一のオブジェクトのとき、`format`／`response_format` に加えて `num_predict`／`max_tokens` を送る（裁定 3）。文法の経路（別の dict）の送信は変わらない。format を落とす箇所はここだけ。
- **J-R3-4** 基名が同じ別ファイルは同じ文書として扱う。記録の `source` は basename で、`cli._qc_records`（T2 の範囲・未修正）が基名の同じ別ファイルの 2 つ目の本文を `where.setdefault` で失う。(ii) は立たない（狭める）側に倒れる。`line_bodies` は同じ id の記録を 1 度だけ連結する（これまで 2 度連結していた）。
- **J-R3-5** `question=None` は何も除外しない（厳しい側）。serve の経路は必ず問いを渡す（`_attach_quote_check` の引数に足した）。
- **J-R3-6** 答えが文字列でないときの `unanchored` は `reason` の文字列比較ではなく局所の真偽値で決める（第 2 ラウンドのレビューの任意改善 2）。形態素解析の呼び出しと品詞・見出し語の読み出しは同じ try の中（同改善 3）。"""

HOLES = """
- **（第 3 ラウンド）要素の無い誤答の一部は検出できるようになった**（内容語の被覆）が、被覆は「答えの内容語が引用の text に現れるか」までで、引用が問いに答えているかは見ない。無関係だが実在する行を引き、その行の語だけで答える誤答（N1 の型）は `anchored` のまま残る（`artifacts/w16-t3/r3/t31_result.txt`）。
- **表記揺れ・言い換えは偽の錨なしになる**: 名詞は表層だけで比べる（R2。固有名詞の見出し語は読みなので同音の別人を同一視しないため）。`打ち合わせ`／`打合せ`、`申込み`／`申し込み`、`開く`／`開催する` は正しい言い換えでも `unanchored`（`cases.jsonl` の C4-b。4/4 が偽の錨なし）。動詞・形容詞の活用の違いだけが見出し語で吸収される。
- **引用の text だけを見る**: 同じ行にあっても引用に入れなかった語は被覆されない（J-R3-1）。
- **基名が同じ別ファイル**（`a/doc.txt` と `b/doc.txt`）は記録の層で同じ id になり、2 つ目の本文が失われる（`cli._qc_records`。T2 の範囲で未修正。J-R3-4）。2 つ目の文書だけにある引用は `fabricated` になる。
- **問いの語は被覆の対象から外す**（R3）。問いと同じ語を繰り返すだけの答えは、引用に無くても被覆される（意図した動作）。
- **num_predict は送るようにしたが、所要も TIMEOUT も変わらなかった**（I6 は解消。裁定 3）: T3-2 の wall は `r3/t32_result.txt` のとおり run1・第 2 ラウンド・今回の 3 つで並べてあり、第 2 ラウンドとほぼ同じ。`TIMEOUT` の 1 行も残る。所要が約 2 倍になる原因（文書を system に載せた長い入力か）の切り分けは未実施。`REPLY_NOT_JSON` は 0 行。
- **内容語の解析は unidic の品詞に頼る**: 同じ語でも文脈で品詞（非自立可能など）が変わると、被覆の対象になったり外れたりする。"""


def type_counts(cases):
    """件数は型ごとに出す（expect != anchored を「誤答」と呼ばない。C4b は正しい言い換えの偽の錨なし、R6 は文書の決め方の確かめ）。"""
    wrong = [c for c in cases if c["type"] in ("C1", "C2", "C3", "N1", "N2", "N3") and c["expect"] != "anchored"]
    c4b = [c for c in cases if c["type"] == "C4b"]
    r6 = [c for c in cases if c["type"] == "R6"]
    anch = [c for c in cases if c["expect"] == "anchored" and c["type"] != "R6"]
    return "誤答（C1〜C3 と N1〜N3 のうち期待が anchored でないもの）%d・正しい言い換えで期待が unanchored（C4b。偽の錨なし）%d・R6 の確かめ %d・期待が anchored の正しい対照 %d" % (len(wrong), len(c4b), len(r6), len(anch))


def func_src(src, name):
    tree = ast.parse(src)
    lines = src.splitlines()
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            start = n.decorator_list[0].lineno if n.decorator_list else n.lineno
            return "\n".join(lines[start - 1:n.end_lineno])
    raise KeyError(name)


def read(p):
    return open(p, encoding="utf-8").read().rstrip("\n")


def git_head(path):
    return subprocess.run(["git", "-C", CWD, "show", "HEAD:" + path], capture_output=True, text=True, check=True).stdout


def section(doc, start_pat, end_pat):
    a = doc.index(start_pat)
    b = doc.index(end_pat, a + 1)
    return a, b


def main():
    doc = open(DOC, encoding="utf-8").read()

    # §9.4: J-R3-*（I8 の行の後ろ、§9.5 の前）
    if "J-R3-1" not in doc:
        a = doc.index("### 9.5 測定結果")
        doc = doc[:a].rstrip("\n") + "\n" + J_R3 + "\n\n" + doc[a:]

    # §9.5: T3-2 の塊を第 2 ラウンドの出力で貼り直す
    a = doc.index("#### T3-2（実機 qwen3.5:4b、温度 0、W14 の C 系）— `artifacts/w16-t3/t32_result.txt`")
    f0 = doc.index("```\n", a) + 4
    f1 = doc.index("\n```", f0)
    doc = doc[:f0] + read(ART + "/t32_result.txt") + doc[f1:]

    # §9.6
    if "test_w16t3_content.py" not in doc:
        a = doc.index("### 9.6 新しい試験")
        b = doc.index("### 9.7 ")
        doc = doc[:a] + ("### 9.6 新しい試験\n\n`tests/test_w16t3_quote_check.py`・`tests/test_w16t3_serve.py`（`artifacts/w16-t3/t3_tests.txt` に第 3 ラウンドの合計）。"
                         "第 3 ラウンドで足したもの: `tests/test_w16t3_content.py`（凍結した `artifacts/w16-t3/r3/cases.jsonl` の 51 件。1 件 1 試験）、"
                         "`tests/test_w16t3_serve.py` の num_predict／max_tokens の 3 試験。\n\n") + doc[b:]

    # §9.7: 今のファイルから取り直す
    a, b = section(doc, "### 9.7 ", "### 9.8 ")
    head = subprocess.run(["date", "+%Y-%m-%d %H:%M:%S %z"], capture_output=True, text=True).stdout.strip()
    m = re.search(r"適用済み\*\*。監査役の第 3 ラウンド裁定 4、([0-9: +\-]+)", doc[a:b])
    stamp = m.group(1) if m else head
    out = ["### 9.7 既存試験との衝突（**適用済み**。監査役の第 3 ラウンド裁定 4、%s）\n" % stamp,
           "K650・K652 は「文書が読み込まれた層 0 の事実の問い」の出力を仕様として変える。次の 8 試験は基点では通り、この変更で落ちる（第 2 ラウンドの `artifacts/w16-t3/related_new_failures.txt`）。監査役の第 3 ラウンド裁定 4（docs §9.7 の新しい期待を採用してよい。名前不変、前後の全文と理由を docs に）に従い、**名前を変えず、同じ厳しさ（完全一致は完全一致のまま）で適用した**。変更は 8 関数の中だけ（`git diff -U0 -- tests/`、`artifacts/w16-t3/r3/proposed_diff.txt`）。第 3 ラウンドの変更（規則 3b・num_predict）でこの 8 試験の期待はこれ以上変わらなかった。適用後の関係試験の新しい失敗は 0（`artifacts/w16-t3/r3/related_new_failures.txt`）。\n"]
    for fn, name, why in TESTS:
        old = func_src(git_head("tests/" + fn), name)
        new = func_src(open(CWD + "/tests/" + fn, encoding="utf-8").read(), name)
        out.append("##### tests/%s::%s\n\n衝突する K: %s\n\n旧（基点 `HEAD` の全文）:\n\n```python\n%s\n```\n\n新（作業ツリーの全文）:\n\n```python\n%s\n```\n" % (fn, name, why, old, new))
    out.append("§9.7 の補足: 旧 `VERA_KEYS` の定数（`tests/test_serve_fusion.py`）は他の試験も使うので、定数を変えず、層 0 の事実の問い（文書あり・LLM を呼ぶ）の試験でだけ `VERA_KEYS | {'quote_check'}` と書いた。層 1 の `set(l1) == VERA_KEYS` は変わらない。\n")
    doc = doc[:a] + "\n".join(out) + doc[b:]

    # §9.8
    if "要素の無い誤答の一部は検出できるようになった" not in doc:
        a = doc.index("### 9.9 ")
        doc = doc[:a].rstrip("\n") + "\n" + HOLES + "\n\n" + doc[a:]

    # §9.10（§9.11 以降は paste_docs_r3b.py と手書きの訂正の節なので残す）
    tail = ""
    if "### 9.11 " in doc:
        tail = doc[doc.index("### 9.11 "):]
        doc = doc[:doc.index("### 9.11 ")]
    if "### 9.10 " in doc:
        doc = doc[:doc.index("### 9.10 ")].rstrip("\n") + "\n"
    cases = [json.loads(l) for l in open(R3 + "/cases.jsonl", encoding="utf-8")]
    dist = collections.Counter((c["type"], c["expect"]) for c in cases)
    t31 = read(R3 + "/t31_result.txt").split("\n\n候補ごとの印:")[0]
    parts = ["### 9.10 第 3 ラウンドの測定（`artifacts/w16-t3/r3/`。出力ファイルから機械で貼った。第 2 ラウンドの出力は上書きしていない）\n",
             "#### 自作の検査（規則 R1〜R6 から手で期待を決め、コードを直す前に凍結した）\n",
             "- 凍結: `cases.jsonl`（%d 件。内訳は型ごと: %s）、`cases.sha256`、日時 `cases_time.txt`（%s）は事前登録 `prereg_r3_time.txt`（%s）より後、`verantyx/quote_check.py` の更新より前。" % (
                 len(cases), type_counts(cases), read(R3 + "/cases_time.txt"), read(R3 + "/prereg_r3_time.txt")),
             "- 型 × 期待: " + json.dumps({"%s/%s" % k: v for k, v in sorted(dist.items())}, ensure_ascii=False),
             "- 直す前（`content_before.txt`）: `" + read(R3 + "/content_before.txt").splitlines()[-1] + "`（`check` が `question=` を受け付けず TypeError）。直した後（`content_after.txt`）: `" + read(R3 + "/content_after.txt").splitlines()[-1] + "`。",
             "- 自作の検査の既存の期待（`test_w16t3_quote_check.py`・`test_w16t3_serve.py`）は 1 つも変えていない（第 3 ラウンドの前後で通る）。anchored から unanchored に変わった既存の期待: 0 件。",
             "- 自作の検査で期待が「偽の錨なし」になる型（正しい言い換えを錨なしにする）: C4-b の 4 件（隠さない）。\n",
             "#### T3-1（自作の集合。T3-4 の伏せた集合が本番）— `r3/t31_result.txt`・`r3/t31_serve_path.txt`\n",
             "```\n" + t31 + "\n```\n", "```\n" + read(R3 + "/t31_serve_path.txt").split("\n")[0] + "\n```\n",
             "#### T3-2（実機 qwen3.5:4b、温度 0、W14 の C 系）— `r3/t32_result.txt`\n",
             "```\n" + read(R3 + "/t32_result.txt") + "\n```\n",
             "#### T3-3（K653 の byte 一致）— `r3/t33_k653.txt`\n",
             "```\n" + read(R3 + "/t33_k653.txt") + "\n```\n"]
    doc = doc.rstrip("\n") + "\n\n" + "\n".join(parts)
    if tail:
        doc = doc.rstrip("\n") + "\n\n" + tail
    open(DOC, "w", encoding="utf-8").write(doc)
    print("ok")


if __name__ == "__main__":
    main()
