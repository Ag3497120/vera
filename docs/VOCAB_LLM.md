# 語彙外の語を LLM に「一番近い語彙はどれか」と聞く（W1-e）

枠（`ProjectFrame`）の語彙に無い語を、閉じた候補の中から LLM に選ばせる実接続。
有限表の内側は構造で解き、外側の「この語はどの語彙に近いか」だけを LLM に聞く。
LLM の答えは**票ではなく手渡し**で、証言として型を付け、台帳に残す。

- 実装: `verantyx/llm_choice.py`（選択器・プロバイダ・台帳）、`verantyx/conductor_vocab.py`（差し込み口）
- 既定は**使わない**。`ConductorVocabulary(frame, chooser=...)` の引数か、`frame.vocab_chooser` を設定したときだけ有効（`VocabularyResolution.chooser_source` に出どころを残す）。無効なときの挙動は従来と同じ（`memory.resolver` があれば従来の閉じた選択、無ければ「no closed-choice asker is configured」で棄権）。
- 台帳の検証入口（照会はしない）: `python -m verantyx.llm_choice verify <ledger.jsonl>`

## 入力と出力

入力は「質問の語」「候補（閉じたリスト。各候補に、その語が枠で使われている文を添える）」「質問文」。
出力は「候補のうち 1 つ」か「どれも近くない」だけ。回答形式は既存の閉じた選択と同じ
`{"choice": 表示番号}` / `{"choice": null}`（解析は `memory_frame.parse_choice`）。
次はすべて**無効回答**として採用しない: 候補に無い語、範囲外の番号、説明文つき、コードフェンスつき、複数選択、余計なキー、JSON でないもの。
無効の理由は `NOT_JSON` / `NOT_CHOICE_OBJECT` / `NOT_INTEGER` / `OUT_OF_RANGE` の型で台帳に残る。

プロンプトに入れる信頼できない文字列（語・質問文・候補・使われた文）は、すべて 1 行の JSON 文字列に閉じ込める。候補行は正確に `番号: {json}` の形で、`U+2028/2029`・`U+0085`・Cf・Cc 文字は `\uXXXX` に置き換える。プロンプトに内部の参照名や指示文は混ぜない。

## 判定の型

| 判定 | 理由 | 意味 |
|---|---|---|
| `ADOPTED` | `ADOPTED` | 2 回の照会がどちらも `PICK` で、**同じ候補**を選んだ（この 1 本だけ） |
| `ABSTAINED` | `DISAGREE` | 2 回が別の候補を選んだ |
| | `NONE_SELECTED` | どちらかが「どれも近くない」 |
| | `INVALID_ANSWER` | どちらかが無効回答 |
| `FAILED` | 失敗の型（下表） | 回答が得られなかった。「どれも近くない」には潰さない |
| `REFUSED` | `TOO_MANY_CANDIDATES` / `NO_CANDIDATES` / `LEDGER_INTEGRITY` | 照会せずに断った |

同点崩し・多数決・スコア合算は無い。1 回目が候補の 1 つでなければ（なし・無効・失敗）、2 回目は照会せず、台帳に `SKIPPED_DECIDED` の行を残す（読み飛ばしも記録する）。

### 失敗の型（プロバイダ）

`TIMEOUT` / `NONZERO_EXIT` / `EMPTY_OUTPUT` / `LIMIT_REACHED` / `NOT_FOUND`（実行ファイルが無い）/ `OS_ERROR`。
上限到達（例: 「You've hit your session limit」「You've hit your usage limit」。`’` も当たる）は、終了コードに関係なく stdout・stderr・出力ファイルのどれかにパターンがあれば `LIMIT_REACHED`（他の判定より先）。パターンは設定（`limit_patterns`）。
プロバイダの `__call__(prompt) -> str`（`ClosedChoiceAsker` と同じ呼び出し形）は、失敗を空文字に潰さず `ProviderError` を投げる。

## プロバイダ

コマンド組み立ては `command_builder` で差し替えられる。引数は常にリスト、stdin は `DEVNULL`、タイムアウトあり、プロンプトは `--` の後ろの最後の要素。
- `CodexProvider(model, effort, binary, timeout, service_tier=None)`: `codex exec --ignore-user-config --ignore-rules -m MODEL -c model_reasoning_effort="EFFORT" --skip-git-repo-check --ephemeral -s read-only --color never -C TMP -o OUT -- PROMPT`。返答は `-o` のファイル。`service_tier` は正しい値を確かめられていないので、設定したときだけ `-c service_tier="…"` を渡す。
- `ClaudeProvider(model, effort, binary, timeout)`: `claude -p --model MODEL --effort EFFORT --output-format text --tools "" --no-session-persistence --safe-mode --strict-mcp-config -- PROMPT`。`--tools` は可変長引数なので `--` が必須。
- 既定値（モデル名・effort・`timeout=240` 秒）は**設定値**であり、測定値ではない。

## 2 回の照会と並び順

候補の並び順を変えた 2 回の独立な照会（問いの文面も 2 種類）を行う。別プロバイダ同士の 2 回も可（`providers=(a, b)`）。
並びは `random.SystemRandom` による置換（`order_source` で注入可）。候補が 2 つ以上なら 2 回目は 1 回目と必ず異なる並びになる（同じになったら 1 つずらす）。固定 seed・辞書順は使わない。候補が 1 つのときも 2 回聞き、文面の違いで独立性を作る。照会ごとに、与えた順（番号列 `order` と表示した語の列 `shown`）を台帳に記録する。

## 型: 証言による対応（構成・非証拠）

採用した対応は `LLMMapping`（`mapping_type="LLM_TESTIMONY_MAPPING"`, `support="testimony"`, `constructed=True`, `counts_as_evidence=False`）。
`conductor_vocab` 経由で ALIAS 記録に書く witness は `kind="testimony"`, `by="llm-choice"`, `counts_as_evidence=False`, `mapping_type`, `ledger_decision_id`, `asks` を持つ。`Memory.ask(..., evidence_only=True)` ではこの記録は答えの根拠から外れる（テストで、同じ枠の証拠つき FACT は残ることと対で確かめている）。
`adopt_alias(by="llm-choice")` は、台帳を引いて「その decision が `ADOPTED` で、語・選択・候補集合が一致し、背後の 2 つの ask 行がどちらも同じ語の `PICK`」であることを確かめられたときだけ通る。chooser が無い、台帳に無い、一致しない場合は `WriteRejected`。既存の `llm-closed-choice` と `human:` の検証は変えていない。

## 台帳

JSONL・追記専用・ハッシュ連鎖。各行は `seq`, `prev`, `hash`（`hash = sha256(prev + 正規化 JSON(hash を除いた行))`、計算は `_chain_hash` の 1 関数）を持つ。更新・削除の API は無い。追記は `fcntl.flock` で排他し、追記のたびに全行を検証してから足す（壊れた台帳には足さない）。`path=None` のときは同じ連鎖をメモリ上に持つ（ファイルを作らない）。

行の種類:
- `ask`: `id, decision_id, ask_index, word, question, candidates, contexts, order, shown, variant, provider, model, effort, prompt, prompt_sha256, raw_reply, raw_truncated, raw_len, raw_sha256, verdict(PICK/NONE/INVALID/FAILED/SKIPPED_DECIDED), picked_term, invalid_reason, failure, failure_detail, returncode, skip_reason, ts`
- `decision`: `decision_id, key, word, candidates, merged_duplicates, status, reason, choice, ask_ids, failure, detail, mapping_type, counts_as_evidence(false), ts`
- `reuse`: キャッシュから答えた記録（`reused_decision_id`, `key`）。自動で解決したものも数える。

検出する破損: 行の書き換え・並べ替え・途中行の削除・先頭行の削除・途中で切れた最終行・JSON でない行・UTF-8 として読めないバイト（`LedgerIntegrityError` の `kind`: `HASH_MISMATCH` / `CHAIN_BROKEN` / `SEQ_GAP` / `TRUNCATED_LINE` / `NOT_JSON` / `NOT_UTF8`、行番号つき。`NOT_UTF8` の行番号は壊れたバイトの前の改行数 + 1。`UnicodeDecodeError` のまま外に出さず、開く・検証・追記・`verify_adoption`・CLI `verify`（rc=2、`chain: BROKEN`）のすべてがこの型を受ける）。壊れた台帳では選択器は照会せず `REFUSED/LEDGER_INTEGRITY` を返す（このとき台帳には書けないので `chooser.unrecorded_refusals` に数えるだけ）。

### 限界（隠さない）
- **末尾行をまるごと消す切り詰め（改行の境界での切断）は連鎖だけでは検出できない。** 最終行をハッシュを再計算して書き換えることも、台帳ファイル全体を作り直すことも検出できない（外部に最終ハッシュを控える仕組みは無い。`verify` の出力の `last_hash` を別に保存すれば比べられる）。
- 台帳の `model` は**設定したモデル名**であり、実際に応答したモデルを確かめる手段は無い。
- 上限到達の判定は文字列パターンなので、プロンプトの echo などに同じ文言が混ざると、有効な答えでも `LIMIT_REACHED`（採用しない側）に倒れる。パターンに無い言い回しの上限メッセージは、非ゼロ終了なら `NONZERO_EXIT`、終了コード 0 で答えが無ければ `EMPTY_OUTPUT` として別の型に分類される（上限とは判別できない）。
- 返答のコードフェンスは無効回答として扱うので、フェンスを付けがちなモデルでは棄権が増えうる（未測定）。

## キャッシュ

別ファイルに持たない。台帳を開いたときに `decision` 行から再構成する。キーは「正規化した語 + 正規化した候補の**集合**（並び順は入れない）」。`ADOPTED` と `ABSTAINED` はキャッシュする（聞き直して都合のよい答えが出るまで続けることを防ぐ）。`FAILED` と `REFUSED` はキャッシュしない（回答が無いので）。使ったときは `reuse` 行を追記する。候補集合が変われば別のキー。

## 接続（`conductor_vocab`）

- 解決の順序は従来どおり: 完全一致 → 既存の証言別名 → (chooser があれば) LLM 経路。完全一致は聞かない。
- 候補の絞り込み（構造のみ）: 質問種別ごとの閉じた役割表 `_OPTION_ROLES`。`CHOICE` / `DESIGN_PREFERENCE` / `FEATURE_SELECTION` は `{("DECISION","choice"), ("POLICY","answer")}`（`conductor._answer_choice` が選択肢の語を照合する先）。それ以外の種別は対応づけの役割が無いので、照会せず棄権（`NO_ROLE_CANDIDATES`）。質問種別は `resolve(..., question_kind=...)` の明示が優先、無ければ `conductor.classify_question` で決める（どちらで決めたかを `question_kind_source` に残す）。
- 候補が 1 つでも LLM の確認（2 回）を省かない。候補数が `max_candidates` を超えたら照会せず棄権（`REFUSED/TOO_MANY_CANDIDATES`）。**`max_candidates=16` は未測定の設定値**。
- `ADOPTED` は ALIAS 記録（上の型）と alias イベントを書く。`ABSTAINED` は alias イベントを書き、以後その語は「prior alias attempt」で再照会されない（従来の規則どおり）。`FAILED` / `REFUSED` は alias イベントを書かない（一時的な失敗で語が使えなくならないように。台帳には残る）。
- `VocabularyResolution` に `support` / `outcome` / `ledger_ids` / `chooser_source` / `question_kind` / `question_kind_source` を（既存フィールドの後ろに）足した。

## 実プロバイダでの確認（V5）

`tests/test_llm_choice_live.py` は `VERA_LLM_LIVE=1` のときだけ動く（既定では `ENVIRONMENT_MISSING` として skip と分類）。台帳の ask 行が合計 6 を超えないことを、照会の前にコードで守る（既存の台帳に 6 行ある状態で再実行すると、照会せずに失敗する）。モデルの答えの中身は検査せず、型・記録・連鎖だけを検査する。
このチケットの作業中に `codex exec`（モデル `gpt-6-luna`、effort `low`）で 3 語（`出版`, `アーカイブ`, `天気`）を 1 回実行した。結果は `artifacts/w1-e/live_summary.json`、台帳は `artifacts/w1-e/live_ledger.jsonl`、pytest の出力は `artifacts/w1-e/live_pytest.txt`:
- ask 行 6（うちプロバイダを起動したもの 5、`SKIPPED_DECIDED` 1）、失敗 0。
- 判定: `ADOPTED` 2、`ABSTAINED` 1（`NONE_SELECTED`）、`FAILED` 0、`REFUSED` 0。
- 件数は 3 語 1 回の結果であり、精度や再現性の主張ではない。

`ClaudeProvider` は実照会していない（コマンド組み立てと、作り物の実行ファイルでのプロセス検査のみ）。

## テストと再現

- `tests/test_llm_choice.py`（V1・V3・V4）、`tests/test_conductor_vocab_llm.py`（V2 と接続）、`tests/test_llm_choice_live.py`（V5）、`tools/demo_vocab.py`（V6。実の `LLMChooser` に作り物のプロバイダを差し込む）。
- 出力ファイルは `artifacts/w1-e/` に保存した（`v1.txt` `v2_wiring.txt` `v3.txt` `v4.txt` `new_tests.txt` `demo.txt` `after_pytest.txt` など）。
- 既存テストとの比較（V7）: 変更前の失敗集合 `baseline_failures.txt` と変更後 `after_failures.txt` の差は `new_failures.txt`（0 行）。
- `verantyx/memory_revalidate.py` は import 時に `Memory.ask` を差し替えて `evidence_only` 引数を落とす。他のテストがそれを import したあとの全体実行では、`Memory.ask(..., evidence_only=True)` が `TypeError` になる。このチケットの許可パスの外なので直していない。`tests/test_conductor_vocab_llm.py` は、そのテストの間だけ元の `Memory.ask` に戻す fixture で回避している。
