"""docs/FUSION.md §9 の 9.3 以降を追記する。数値は出力ファイルから貼る（手で写さない）。旧・新案の試験の全文は試験ファイルと検証済みの写し（SC/proposed）から機械で取り出す。"""
import ast
import os
import re
import sys

CWD = "/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S"
ART = CWD + "/artifacts/w16-t3"
SC = "/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3"
MARK = "### 9.3 実装した仕様"

TESTS = [("test_serve_fusion.py", "test_default_llm_answer_without_record_is_testimony_never_an_answer", "K652（本文の後に 1 行）"),
         ("test_serve_fusion.py", "test_list_content_is_read_and_only_the_last_user_message_is_the_question", "K650（system を添える）"),
         ("test_serve_fusion.py", "test_http_openai_stream_ends_with_done_and_carries_vera", "K652（本文の後に 1 行）"),
         ("test_serve_fusion.py", "test_http_ollama_default_is_ndjson", "K652（本文の後に 1 行）"),
         ("test_serve_fusion.py", "test_max_tokens_is_validated_and_reaches_the_llm_call", "K650（format に JSON schema）"),
         ("test_serve_fusion.py", "test_vera_field_keys_are_the_documented_ones_layer0_and_layer1", "K652（vera の鍵に quote_check）"),
         ("test_w10f04_serve.py", "test_without_fill_the_vera_field_has_the_keys_it_had", "K652（vera の鍵に quote_check）"),
         ("test_w10f05_cli.py", "test_serve_adds_placement_layer_only_with_a_layer_and_leaves_the_fusion_layer_alone", "K652（vera の鍵の並びに quote_check）")]


def func_src(path, name):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    lines = src.splitlines()
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            start = n.decorator_list[0].lineno if n.decorator_list else n.lineno
            return "\n".join(lines[start - 1:n.end_lineno])
    raise KeyError(name)


def read(p):
    return open(p, encoding="utf-8").read().rstrip("\n")


def main():
    doc = open(CWD + "/docs/FUSION.md", encoding="utf-8").read()
    if MARK in doc:
        print("already pasted")
        return
    out = []
    out.append(MARK + """（本文の 1 行と鍵）

- **quote_mode**（\`decode_grammar.quote_mode\`）: 層 0・FACTUAL・LLM を呼ぶ・記録が答えない・文書が 1 つ以上読み込まれている。偽の経路（層 1・非 factual・文書なし・LLM を呼ばない・記録が答える）は基点と byte 一致（K653）。
- **K650**: \`llm_messages\` は quote_mode のとき、クライアントの会話の先頭に system を 1 つ足す（\`[文書名:行番号] 行の本文\`。同じ行の文は 1 行にまとめる）。\`vera_server.fusion_turn\` が \`fmt = G.quote_format(turn, records)\`（\`G.QUOTE_SCHEMA\`）を LLM に渡す。Ollama は \`format\`、OpenAI 互換は \`response_format\`（strict）。
- **K651**: \`verantyx/quote_check.py: check(answer, quotes, records) -> QuoteCheck\`（§9.1 の規則）。
- **K652**: \`vera.quote_check = {verdict, quotes[{source,line,text,found,(relocated_to)}], elements[{kind,value,found_in}], conflicts[...], (reason)}\`。\`outcome\` の直後・\`timing\` の前（\`conclude\` の最後の鍵）。本文は \`MARK_TESTIMONY + "\\n" + answer\` の後に 1 行: 錨あり \`（引用の出典: <source>:<line>、…）\`／錨なし \`（記録で確かめられません）\`／食い違い \`（記録と食い違います: <source>:<line>「<値>」／…）\`。固定文（\`LLM_EMPTY\` など）には足さない。錨ありのとき、\`provenance\` の記録でない文に \`anchored_testimony: {quotes: [source:line, …]}\` を足す（\`origin\`・\`sentence_kind\`・\`arms\`・\`evidence\` は変えない。\`abstain_policy\` を呼んだ後に足す）。\`outcome\` は \`TESTIMONY\` のまま。
- LLM の答えは証言のまま。錨ありでも事実の問いの ANSWER の根拠は引用（人の記録）であり、LLM の文ではない。「読んだ」「正しい」とは書かない。
""")
    out.append("""### 9.4 判断の記録

- **J1** 「日付・時刻（年月日・曜日・相対語は除く）」は「年月日と曜日は取る、相対語は取らない」と読む。
- **J2** \`anchored_testimony\` は記録でない文の項目に足す鍵。\`origin\` の値は増やさない（\`basis_policy.DECLARED_ORIGINS\` は閉じた一覧で許可パスの外）。
- **J3** \`MARK_TESTIMONY\` は錨ありでも残す。
- **J4** format を LLM に渡すために \`vera_server.fusion_turn\` の 1 行を変えた（\`fmt = ... else G.quote_format(turn, cfg.records)\`）。チケットの「追記だけ」を 1 行越える。K650 を満たす唯一の箇所。
- **J5** 既存試験との衝突は書き換えず、§9.7 に旧・新案の全文を残して監査役に渡す。
- **J6** 複数行に一致する引用は \`relocated\` にして全部を残す（勝者を選ばない）。
- **実装役の判断 I1** 日付は 1 組（数＋年／月／日／時／分）ごとに 1 要素にした（\`2026年4月1日\` → \`2026年\`・\`4月\`・\`1日\`）。答えが「4月1日」だけでも、引用の「2026年4月1日」と照合できる。
- **I2** 数値の値は「数の値＋単位」の文字列（\`3万円\` は \`3万円\`。30000 に直さない）。漢数字は数の値に直す。読めない並びは要素にせず \`QuoteCheck.skipped\` に数える（\`to_dict\` には入れない。鍵を足さないため）。
- **I3** 形態素解析は \`typed_edges._tagger\`（fugashi）を直接使う（\`semantic_reader\` は import しない。指示書のレビュー項目の grep を空にするため）。
- **I4** (ii) 文書間の食い違いは、名前にも適用する（チケットの文どおり）。2 文書から引用した答えは、名前の集合が違えばほぼ必ず \`conflict\` になる。これは既知の穴（§9.8）。
- **I5** quote_mode でも、LLM の返答が空（\`answer\` が空文字）で \`LLM_EMPTY\` になったときは \`quote_check\` の鍵を作らない（固定文の経路）。
- **I6** format を渡すと Ollama は \`num_predict\` を送らない（\`llm_backend._ollama_chat\`。許可パスの外）。W14 の \`max_tokens=256\` は quote_mode では効かない。
- **I7** 事前登録の文より前に \`verantyx/quote_check.py\` の初版を書いていた（規則は指示書のとおりで、事前登録の文と同じ）。検査データ（T3-1 の集合）は事前登録（\`artifacts/w16-t3/prereg_time.txt\`）より後に作り、凍結した（\`data_freeze_time.txt\`）。関係試験の基線は、最初の取得が実装中の木と重なったため、基点 \`3a1677c\` の \`git archive\` の写しで取り直した（\`related_before.txt\`）。
""")
    out.append("### 9.5 測定結果（出力ファイルから機械で貼った）\n")
    out.append("#### T3-1（自作の集合。T3-4 の伏せた集合が本番）— \`artifacts/w16-t3/t31_result.txt\`・\`t31_serve_path.txt\`\n")
    t31 = read(ART + "/t31_result.txt").split("\n\n候補ごとの印:")[0]
    out.append("```\n" + t31 + "\n```\n\n" + "```\n" + read(ART + "/t31_serve_path.txt").split("\n")[0] + "\n```\n")
    out.append("#### T3-2（実機 qwen3.5:4b、温度 0、W14 の C 系）— \`artifacts/w16-t3/t32_result.txt\`\n")
    out.append("```\n" + read(ART + "/t32_result.txt") + "\n```\n")
    out.append("#### T3-3（K653 の byte 一致）— \`artifacts/w16-t3/t33_k653.txt\`\n")
    out.append("```\n" + read(ART + "/t33_k653.txt") + "\n```\n")
    out.append("""### 9.6 新しい試験

\`tests/test_w16t3_quote_check.py\`・\`tests/test_w16t3_serve.py\`（\`artifacts/w16-t3/t3_tests.txt\`）。

""")
    out.append("""### 9.7 既存試験との衝突（未適用・監査役の判断待ち）

K650・K652 は「文書が読み込まれた層 0 の事実の問い」の出力を仕様として変える。次の 8 試験は基点では通り、この変更で落ちる（\`artifacts/w16-t3/related_new_failures.txt\`）。どれも許可パスの外にあり、**書き換えていない**。変更案は「名前を変えず、同じ厳しさ（完全一致は完全一致のまま）」で書いた。案は \`SC/proposed\` に写した試験ファイルに当てて、この 8 試験が通ることを確かめた（本体の木には当てていない）。

""")
    for fn, name, why in TESTS:
        old = func_src(CWD + "/tests/" + fn, name)
        new = func_src(SC + "/proposed/" + fn, name)
        out.append("##### tests/%s::%s（変更案・未適用）\n\n衝突する K: %s\n\n旧（現在のファイルの全文）:\n\n```python\n%s\n```\n\n新案（全文）:\n\n```python\n%s\n```\n" % (fn, name, why, old, new))
    out.append("""§9.7 の補足: 旧 \`VERA_KEYS\` の定数（\`tests/test_serve_fusion.py\` 748 行）は他の試験も使うので、新案では定数を変えず、層 0 の事実の問い（文書あり・LLM を呼ぶ）の試験でだけ \`VERA_KEYS | {'quote_check'}\` と書いた。層 1 の \`set(l1) == VERA_KEYS\` は変わらない。
""")
    open(CWD + "/docs/FUSION.md", "a", encoding="utf-8").write("\n" + "\n".join(out))
    print("pasted")


if __name__ == "__main__":
    main()
