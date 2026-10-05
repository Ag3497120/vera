"""Paste the measurements into docs/INITIAL_LAYERS.md section M from the output files (nothing is typed by hand).
usage: paste_m.py   (cwd = the tree). Replaces the text between the line `## M. 測定...` and the line `## J. 判断記録`."""
import collections
import json
import os
import re

W = os.getcwd()
A = os.path.join(W, "artifacts/w12-c1")


def rj(p):
    return json.load(open(os.path.join(A, p), encoding="utf-8"))


def rt(p):
    return open(os.path.join(A, p), encoding="utf-8").read()


def judg(path, col):
    c = collections.Counter()
    for l in rt(path).split("\n")[2:]:
        if l.strip():
            c[l.split("\t")[col]] += 1
    return dict(c)


L = []
a = L.append
a("## M. 測定（出力ファイルから `artifacts/w12-c1/scripts/paste_m.py` が貼った。手で写していない）")
a("")
a("読み方の注意: 目視の表は正解データではない（実装役が見た判断）。数値の出所はそれぞれの出力ファイル（括弧内、`artifacts/w12-c1/` の下）。")
a("")
a("### X1 初期層なしの出力は基点（`5e7df09`）と byte 一致（K404）")
a("```")
for f in ("x1_entry.txt", "x1_serve.txt", "x1_query.txt"):
    a("# " + f)
    a(rt(f).strip())
a("```")
a("")
x2 = rj("x2_vocab.json")
a("### X2 語彙層（`x2_vocab.json`、`x2_sample60.tsv`）")
a("- 候補（極大の単一字種の連なり、文書内の集合）: jawiki 異なり %d、生成 heldout 異なり %d、合併 %d。" % (x2["candidates"]["distinct_jawiki"], x2["candidates"]["distinct_generated"], x2["candidates"]["distinct_union"]))
a("- 語彙層の語数（独立出現 ≥3、類をまたいで足さない）: 合計 **%d**、`origin_class` 別 %s、字種別 %s。" % (x2["words"]["total"], json.dumps(x2["words"]["by_class"]), json.dumps(x2["words"]["by_class_script"], ensure_ascii=False)))
a("- `OUT_OF_SCOPE_MIXED_SCRIPT`（混ざった字種。数えるだけ）: 異なり jawiki %d、生成 %d、合併 %d。" % (x2["OUT_OF_SCOPE_MIXED_SCRIPT"]["distinct_spans_jawiki"], x2["OUT_OF_SCOPE_MIXED_SCRIPT"]["distinct_spans_generated"], x2["OUT_OF_SCOPE_MIXED_SCRIPT"]["distinct_union"]))
b = x2["base_undecided"]
a("- r9 の UNPLACED %d・MULTIPLE %d のうち語彙層で確認できた語: **%d**（状態×類別 %s）。語彙層は「文に使える語である」ことの確認で、型は付けない。" % (b["UNPLACED_total"], b["MULTIPLE_total"], b["confirmed_total"], json.dumps(b["confirmed_by_state_class"])))
a("- 文書: jawiki %d 記事、生成 heldout %s。読めなかった行: %s。" % (x2["documents"]["jawiki"], json.dumps(x2["documents"]["generated"], ensure_ascii=False), json.dumps(x2["skipped"], ensure_ascii=False)))
a("- 処理: %s 秒（`/usr/bin/time -l` の出力は `build/initial-layers/vocab/build.log`）。出力 %d bytes、sha256 `%s`。" % (json.dumps(x2["seconds"]), x2["out_bytes"], x2["out_sha256"]))
a("- 目視 60 語（r9 の UNPLACED／MULTIPLE ∩ 語彙層から `random.Random(20261005)`）: %s（語＝語・名、断片＝長い語の途中、疑わしい＝句・不明）。**正解データではない。**" % json.dumps(judg("x2_sample60.tsv", 5), ensure_ascii=False))
p1 = rj("x2_vocab_pass1.json")
a("- 最初の版（pass1、欄の一覧が足りなかった）: 語数 %d、読めなかった行 %s（`x2_vocab_pass1.json`。§J）。" % (p1["words"]["total"], json.dumps(p1["skipped"], ensure_ascii=False)))
v1 = rj("x2_vocab_v1_iter_unfixed.json")
a("- **r2（レビュー M2 の直し）**: 旧版（踊り「々」が漢字の連なりに入っていない。`x2_vocab_v1_iter_unfixed.json`・`x2_sample60_v1_iter_unfixed.tsv`・`build/initial-layers/vocab/vocab_v1_iter_unfixed.sqlite`）は語数 %d、r9 の未決定のうち確認できた語 %d。直した版（上の数値）は語数 %d、確認できた語 %d。内訳・確認語は `x2_m2_counts.txt` と `x2_m2_check_words.txt`（`sqlite3 -readonly` の出力）:" % (v1["words"]["total"], v1["base_undecided"]["confirmed_total"], x2["words"]["total"], b["confirmed_total"]))
a("```")
a(rt("x2_m2_counts.txt").strip())
a("# x2_m2_check_words.txt（直した版。word|docs_human|origin_class。レビューの確認の SQL の出力）")
a(rt("x2_m2_check_words.txt").strip())
a("```")
a("  `木駅`（human 12 文書）は直した版にも残る: 原因は `鵜の木駅`・`柿ノ木駅`・`四ツ木駅` など「の・ノ・ツ」で切れた連なり（`grep -a` で jawiki の文脈を確認）で、踊り字ではない（§7、O6。直していない）。")
a("  目視 60 語は直した版から引き直した（語 42・疑わしい 18・断片 0。判定基準を旧版より厳しくした: 複合の句・語の一部かもしれないものは疑わしいにした。旧版の表と数は比べられない）。")
a("")
a("### X3 法令の分野層（builder の経路。LLM なし、`x3_law_k1.json`・`x3_law_k2.json`、`x3_sample60_k1.tsv`・`x3_sample60_k2.tsv`）")
a("| | 最初の版（r9 の設定、`def_min`=`alias_min`=`paren_alias_min`=1） | 直した版（閾値 2。**以後の測定はこちら**） |")
a("|---|---|---|")
for ver, key in (("k1", None), ("k2", None)):
    pass
k = {v: rj("x3_law_%s.json" % v) for v in ("k1", "k2")}
def row(label, f):
    a("| %s | %s | %s |" % (label, f(k["k1"]), f(k["k2"])))
row("素材（`法律と暮らし` の行）", lambda r: "%d 行（sha256 `%s…`）" % (r["law"]["domain_db"]["rows"], r["law"]["domain_db"]["rows_sha256"][:12]))
row("分野の配置の DECIDED/direct 語", lambda r: str(r["law"]["placement"]["headwords_by_state_origin"].get("DECIDED/direct")))
row("**層の direct 語数（法令）**", lambda r: str(r["law"]["layer"]["growth"]["words"]["direct"]))
row("対照（同じ行数のランダム）の層の direct 語数", lambda r: str(r["control"]["layer"]["growth"]["words"]["direct"]))
row("層に書かなかった理由別（法令）", lambda r: json.dumps(r["law"]["layer"]["not_written"]))
row("台帳の鎖（chain_ok）・`promoted_to_layer` 行", lambda r: "%s・%d" % (r["law"]["layer"]["growth"]["ledger"]["chain_ok"], r["law"]["layer"]["growth"]["ledger"]["promoted_to_layer"]))
row("`hierarchy._layers_for(V)`（V＝direct 語数、CAPACITY=24）", lambda r: str([v["layers_for_V"] for kk, v in r["capacity"]["layers"].items() if kk.startswith("law")][0]))
row("builder の秒・最大 RSS", lambda r: "%s 秒・%.1f GB" % (r["law"]["builder"]["seconds_real"], r["law"]["builder"]["max_rss_bytes"] / 1e9))
a("| 目視 60 語（正しい／疑わしい／誤り） | %s | %s |" % (json.dumps(judg("x3_sample60_k1.tsv", 4), ensure_ascii=False), json.dumps(judg("x3_sample60_k2.tsv", 4), ensure_ascii=False)))
a("")
c1, c2 = judg("x3_sample60_k1.tsv", 4), judg("x3_sample60_k2.tsv", 4)
a("- 誤りの割合: 最初の版 %d/60、直した版 %d/60。基準（1 割以下）に対し、最初の版は超え、直した版は届いた。**目視は正解データではない。**" % (c1.get("誤り", 0), c2.get("誤り", 0)))
a("- O10 目視の誤り: 実装役 %d/60、r1 の中間職の独立判定 6/60（10.0%%、境界上。出所: 中間職のレビュー r1）。" % c2.get("誤り", 0))
a("- 層の direct 語はすべて `layer_confirmed`（`material_origin: generated`、`model: null`）。基底（r9）が DECIDED の語は書いていない（K290）。層の `base_content_sha256` は r9 の `%s`。" % k["k2"]["law"]["layer"]["base_content_sha256"])
a("- 法令と対照の層の大きさがほぼ同じ（直した版 %d 対 %d）: 素材を部分集合に絞ったこと自体の効果で、法令の知識が増えたとは言えない（K409、§J）。" % (k["k2"]["law"]["layer"]["growth"]["words"]["direct"], k["k2"]["control"]["layer"]["growth"]["words"]["direct"]))
a("- 結合の層（法令の層＋自転車の利用者の層、`x4_combine_law_bicycle.json`）: %s" % json.dumps({"sources": rj("x4_combine_law_bicycle.json")["sources"], "words": rj("x4_combine_law_bicycle.json")["growth"]["words"], "conflict_words": rj("x4_combine_law_bicycle.json")["conflict_words"]}, ensure_ascii=False))
ov = rt("x3_overlap_law_control.txt").strip().split("\n")
a("- 法令の層と対照の層の重なり（r1 O1。`x3_overlap_law_control.txt`、直した版）: 法令の層 %s 行のうち **%s 行** が対照の層と (語, 型) で一致する。大きさが同じことより強い事実で、分野の内容を捉えた層ではない。" % (ov[1], ov[0]))
a("")
a("")
a("### X4 冷たい出発（`x4_score.txt`、`x4_qa_*.jsonl`、`x4_why_not_gained_*.txt`）")
a("`ask --mode round5`（W10-f05 と同じ経路）。`--layer none` と `--layer <直した版の法令の層>`（自転車は結合の層も）。**誤答は全ての走行で 0**。")
a("| 文書 | 層 | 正答 | 誤答 | 棄権（答えあり／答えなし） |")
a("|---|---|---|---|---|")
for d, name in (("x4_bicycle", "自転車（30 問）"), ("x4_pottery", "陶芸（15 問）")):
    for line in rt(d + "/qa_score.txt").split("\n"):
        if line.startswith("{"):
            r = json.loads(line)
            a("| %s | %s | %d | %d | %d／%d |" % (name, {"qa_none": "none", "qa_law": "law（直した版）", "qa_user": "law＋自転車の利用者の層（結合）"}[os.path.basename(r["file"]).replace(".jsonl", "")], r["correct"], r["wrong"], r["answerable"]["abstained"], r["unanswerable"]["abstained"]))
a("")
a("陶芸は答えありの 10 問がすべて基底（r9）だけで既に正答（`ALREADY_CORRECT`）で、増える余地が無かった。自転車の増分は 0（法令の層も結合の層も）。")
a("")
a("`why_not_gained.py` の型（r2: 誤答の型を足した）: GAINED／ALREADY_CORRECT／LAYER_WORD_NOT_IN_QUESTION／LAYER_NO_DIRECT／READER_NOT_REACHED と、誤答は **最優先で** WRONG_WITHOUT_LAYER／WRONG_WITH_LAYER／WRONG_BOTH（答えなしの問いに答えた場合も。判定は `score_qa.py` と同じ）。合成の入力での確認は `m4_synthetic/output.txt`（WRONG_BOTH 1・WRONG_WITHOUT_LAYER 1・GAINED 1）。足した後の自転車（法令層）の再実行の 1 行目は `m4_rerun_x4_bicycle_law.txt`（`wrong` 0、型の数は前と同じ）。")
a("")
a("増えなかった理由の型（`why_not_gained.py`。法令の層、`routed` ＝法令層の direct 語が問いか該当文に現れた、答えありの問いの数）:")
for f in ("x4_why_not_gained_bicycle.txt", "x4_why_not_gained_bicycle_combined.txt", "x4_why_not_gained_pottery.txt"):
    first = json.loads(rt(f).split("\n")[0])
    a("- `%s`: %s" % (f, json.dumps(first, ensure_ascii=False)))
a("")
s5 = rj("x5_summary.json")
a("### X5 `confidence_tiers`（`x5_tiers.jsonl`、`x5_summary.json`、`x5_consistency.txt`）")
a("50 問（自転車 30＋陶芸 15＋W10-f01 の 5 問）を製品の経路（`serve --no-llm` の `fusion_turn`、段つき）で。正答 %d・正しい棄権 %d・答えありの棄権 %d・**誤答 %d**。`vera.llm.called` は全件 false（`llm_called_any` = %s）。" % (s5["correct"], s5["correct_abstain"], s5["abstained_on_answerable"], s5["wrong"], s5["llm_called_any"]))
a("| `agree` | 問い | 正答 | 正しい棄権 | 答えありの棄権 | 誤答 | 正しかった割合 |")
a("|---|---|---|---|---|---|---|")
for r in s5["by_agree"]:
    a("| %d | %d | %d | %d | %d | %d | %s |" % (r["agree"], r["questions"], r["correct"], r["correct_abstain"], r["abstained_on_answerable"], r["wrong"], r["right_per_question"]))
a("")
a("- 単調（`agree` が大きいほど下がらない）か: **%s**。段の構成は変えていない（K403・X5）。" % ("はい" if s5["monotone_nondecreasing_by_agree"] else "いいえ"))
a("- ANSWER を示した問いだけで見ると（`shown_answers_by_agree`）: %s" % json.dumps(s5["shown_answers_by_agree"]))
a("- `counted` 別: %s" % json.dumps([{k_: r[k_] for k_ in ("counted", "questions", "correct", "correct_abstain", "abstained_on_answerable", "wrong")} for r in s5["by_counted"]]))
a("- 整合の門（同じ段を別プロセスで答えさせて byte 一致、timing 除く）: `%s`" % rt("x5_consistency.txt").strip().split("\n")[-1])
a("- `TIERS_CONFLICT`: %d 件。" % s5["conflicts"])
ac = [(r["vera"]["confidence_tiers"]["agree"], r["vera"]["confidence_tiers"]["answered"], r["vera"]["confidence_tiers"]["counted"], (r["vera"].get("outcome") or {}).get("outcome")) for r in (json.loads(l) for l in open(os.path.join(A, "x5_tiers.jsonl"), encoding="utf-8"))]   # integration (auditor, 2026-10-05, M7): the outcome is read from vera.outcome, not inferred from agree
a("- `answered` 別（`by_answered`）: %s" % json.dumps([{k_: r[k_] for k_ in ("answered", "questions", "correct", "correct_abstain", "abstained_on_answerable", "wrong")} for r in s5["by_answered"]]))
a("- 第 3 ラウンドの定義（`agree` = 答えた段のうち示す答えと署名が同じ段の数。棄権どうしの一致は数えない。示すのが棄権、または衝突なら 0）での (agree, answered, counted) の組の数え上げ: %s。示す答えが ANSWER の問いは %d 問（outcome から数えた。M7）、`agree == 0` の問いは %d 問。" % (json.dumps(dict(collections.Counter("%d,%d,%d" % t[:3] for t in ac))), sum(1 for x, y, z, o in ac if o is not None and str(o).startswith("ANSWER")), sum(1 for x, y, z, o in ac if x == 0)))
a("- 示す答えが ANSWER の問い %d 問のうち `agree == answered == counted` の問い %d 問。示すのが棄権の問い %d 問のうち `agree == 0` は %d 問（outcome から数えた。M7）。" % (sum(1 for x, y, z, o in ac if o is not None and str(o).startswith("ANSWER")), sum(1 for x, y, z, o in ac if o is not None and str(o).startswith("ANSWER") and x == y == z), sum(1 for x, y, z, o in ac if not (o is not None and str(o).startswith("ANSWER"))), sum(1 for x, y, z, o in ac if not (o is not None and str(o).startswith("ANSWER")) and x == 0)))
a("- 旧定義（`/1`、棄権の一致も数える）の出力は `x5_tiers_r2_agree_counts_abstain.jsonl`・`x5_summary_r2_agree_counts_abstain.json`。`x5_r2_vs_r3_agree.txt`: `%s`（`agree`・`answered`・`schema`・timing を除いて旧出力と同じ）。`x5_consistency.txt` は段ごとの答えの比較で `combine` を通らないため、流し直していない。" % rt("x5_r2_vs_r3_agree.txt").strip())
a("- r2: 語彙層を作り直したので X5・X6 を作り直した版の vocab で流し直した。旧版（旧 vocab）の出力は `x5_tiers_v1_vocab.jsonl`・`x5_summary_v1_vocab.json`・`x5_consistency_v1_vocab.txt`・`x6_latency_v1_vocab.json`。X5 の 50 行は vocab の sha256 と timing を除いて旧版と同じ（比較は `x5_v1_vs_v2_vocab.txt`: 50 行すべて一致）。")
a("")
x6 = rj("x6_latency.json")
a("### X6 `serve --no-llm` の遅延と最小構成（`x6_latency.json`、`x6_http_answer.json`）")
a("in-process（`fusion_turn`、HTTP なし）、50 問×3 回（1 回目は温めで除く）、`vera.timing.vera_ms`。")
a("| 構成 | p50 ms | p95 ms | max ms | 起動〜最初の答え ms（段の読み込み込み） | 最大 RSS（MB） |")
a("|---|---|---|---|---|---|")
for key, lab in (("base_only", "base だけ（段なし）"), ("base_law_user", "base＋法令層＋利用者の層")):
    r = x6[key]
    a("| %s | %s | %s | %s | %s | %.1f |" % (lab, r["vera_ms"]["p50"], r["vera_ms"]["p95"], r["vera_ms"]["max"], r["start_to_first_answer_ms_incl_stage_loading"], r["peak_rss_bytes"] / 1e6))
a("- 配る物の大きさ（bytes）: %s。" % json.dumps(x6["shipped_bytes"]))
a("- 「数十 ms 目標」: base だけで p50 が %s ms で **届いていない**（読解器の時間。読解器は触れない約束なので直しに行っていない）。" % x6["base_only"]["vera_ms"]["p50"])
a("- 計測時の負荷: `%s`。" % x6["uptime"])
a("- r2: 語彙層の作り直しの後に X6 も流し直した（旧版 `x6_latency_v1_vocab.json`。負荷 `x6_uptime_before_r2.txt`）。`x6_http_answer.json` は旧版の語彙層（sha256 `31a913dc…`）で立てた 1 回の応答のままで、流し直していない（正式な数ではない）。`x6_http_answer.json` は r2 以前の応答で、`confidence_tiers` も旧定義（`/1`）。")
a("- 実際に 127.0.0.1 で `vera serve --no-llm --tier vocab=… --tier law=…` を立てて POST した 1 回の応答は `x6_http_answer.json`（遅延の正式な数ではない）。")
a("")
a("### X8 基線から増えない（`pytest_full.txt`、`pytest_new_failures.txt`）")
tail = [l for l in rt("pytest_full.txt").split("\n") if l.strip()][-1]
a("- 全体（`pytest tests -p no:cacheprovider -q -rfE --tb=no`）: `%s`" % tail)
nf = [l for l in rt("new_failures.txt").split("\n") if l.strip()]
ff = [l for l in rt("fixed_failures.txt").split("\n") if l.strip()]
a("- 基線（`dev_bfb17b8_failures.txt`、115 件）との差（`compare_failure_sets.py`）: 基線に無い失敗 **%d 件**（`new_failures.txt`）%s、基線にあって今回は通った %d 件（`fixed_failures.txt`）%s。" % (len(nf), nf, len(ff), ff))
a("- 基線に無い失敗の %d 件は、基点の木（`5e7df09` を `git archive` したもの）で単独で流しても **同じく失敗する**（`pytest_new_failures_check_base.txt` と `pytest_new_failures_check_new.txt`）。チケットが環境由来と書いた失敗（`test_s6_…`・`test_p4_abilities::test_speech_act_drafts…`）に当たる。このチケットの差分が原因ではない。" % len(nf))
a("- 最初に `pytest`（引数なし）で流したら `artifacts/` の `test_*.py` の収集エラー 68 件で止まった（`pytest_full_rootcollect_errors.txt`）。W10-f05 と同じく `pytest tests` で流した。")
a("- 新しいテスト（`tests/test_w12c1_*.py`）: `%s`。既存の層・融合のテスト（`test_w10f05_*`・`test_serve_fusion`・`test_w10f04_serve`）: `%s`。" % (rt("pytest_w12c1.txt").strip().split("\n")[-1], rt("pytest_related.txt").strip().split("\n")[-1]))
a("")
a("### X7 中間職の未公開（別分野の文書 1 本と問い 15）")
a("- **読み替え**（監査役の裁定、2026-10-05 14:58:08 +0900）: X7 は「初期層が原因の誤答 0（層なしと層ありで同じ答え）」で判定する。実装役は X7 の入力を見ていない。以下の数の出所は中間職のレビュー r1／r2 の報告（実装役の測定ではない）。")
a("- r1（料理の文書 25 文・問い 15）: 層なしも法令の層ありも `correct 8 wrong 2 abstained 5`。誤答 2 件は期待 `祖母` に対して答え `[\"祖\"]`。")
a("- r2（園芸の文書 19 文・問い 15）: 層なしも法令の層ありも `correct 9 wrong 1 abstained 5`。誤答は期待 `叔父` に対して答え `[\"叔\"]`。")
a("- どちらの誤答も基点 `5e7df09` の木で同じ答えが出る（`ask --mode round5` の経路の切り出しの不具合。r9 の配置は `叔父 DECIDED PERSON`）。層の有無で答えは変わらない → **初期層が原因の誤答 0 で、読み替えた X7 は合格**。基点の誤答は **W3-f1**（監査役が起票）で直す。")
a("- 配る経路（`serve --no-llm`、base＋law）では r1 の 15 問で正答 1・誤答 0、r2 の 15 問で正答 4（`叔父` を含む）・誤答 0、`llm_calls 0`（中間職の参考の測定）。")
a("中間職がレビューで `artifacts/w12-c1/scripts/run_cold_start.sh <doc> <qa> <outdir> [<user layer>]` を新しい文書で走らせる（実装役は見ていない）。")
a("")
text = "\n".join(L) + "\n"
p = os.path.join(W, "docs/INITIAL_LAYERS.md")
doc = open(p, encoding="utf-8").read()
i = doc.index("## M. 測定")
j = doc.index("## J. 判断記録")
open(p, "w", encoding="utf-8").write(doc[:i] + text + doc[j:])
print("pasted", len(L), "lines")
