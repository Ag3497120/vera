# W3-c 再計算手順書（コマンドと要約出力の記録）

W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-c-S, PY=$W/artifacts/w3-c/py.sh, A=$W/artifacts/w3-c, D=$W/tests/observe/data, IDX=/Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c（索引は `mode=ro` でしか開かない）。基点 5cae978、コミットしていない。

## 手順 0（足場）
- `$PY -c "import verantyx; print(verantyx.__file__)"` -> $W/verantyx/__init__.py
- `$PY -m verantyx.cli index search "視点から構造を観測して生成" > $A/index_before.txt` -> UNKNOWN_NOT_FOUND（651 件を探索）。`index search "顕著さの場 台帳" > $A/index_before_salience.txt` -> UNKNOWN_NOT_FOUND。
- 作る前の索引で既存物は無かった（`verantyx/observation.py` は別物で、使わず変えていない）。

## 手順 1（事前登録。検査データより先）
- `docs/OBSERVATION.md` の「事前登録」節だけを最初に書いた。`$A/prereg.txt` に日時（12:20:51）・区間の sha256・`ls tests/observe` の出力（無い）を記録。
- 区間を切り出すコマンド: `awk '/<!-- prereg:begin -->/{f=1;next}/<!-- prereg:end -->/{f=0}f' docs/OBSERVATION.md | shasum -a 256`
- 事前登録の「登録日時」の行を、実際の `date` の出力に直した（初版は書き手が時刻を先に書いてしまった）。変更記録の 1 番。
- 事前登録の変更記録の 2 番: P10 の「代替」の判定に使う台帳の状態の明示（区間の本文は変えていない）。期待の凍結の直後、最初の観測の前に書いた。

## 手順 2（`verantyx/salience.py`）
- `$PY -m pytest -q -p no:cacheprovider tests/test_salience.py` -> 全部通る（最終: `$A/pytest_new_tests.txt`）。

## 手順 3（`verantyx/observe.py`）
- `$PY -m pytest -q -p no:cacheprovider tests/test_observe.py` -> 全部通る。

## 手順 4（`semantic_realize.py` への追加）
- `$PY -m pytest -q -p no:cacheprovider tests/test_observe_realize.py` -> 全部通る。
- `git diff --numstat 5cae978 -- verantyx/semantic_realize.py verantyx/cli.py` -> 削除の列が両方 0（`$A/common_additions_only.txt`）。
- `$PY tests/observe/realize_parity.py --base 5cae978 --out $A/o8_realize_parity.txt` -> `checked ..., mismatch 0`（数は docs の測定結果）。
- `tests/test_semantic_realize.py` の基線と同じ 2 失敗（`test_reader_case_roles_are_preserved[...location]` `[...origin]`）は、全体テストの失敗一覧に基線と同じ形で載っている。

## 手順 5（入口 `observe`）
- `$PY -m pytest -q -p no:cacheprovider tests/test_observe_entry.py` -> 全部通る（ハッシュ種 0・4242・random の byte 一致、終了コード 2・3、台帳の追記、再生）。

## 手順 6（検査データ。凍結の順）
1. 文・配置・台帳・コーパスの元・視点を書いて凍結（観測器にも読解器にも通していない）: `tests/observe/gen_data.py`（台帳と `corpus_root`）、種の文・配置・視点は手で書いた。`python3 tests/observe/freeze.py --stage inputs ...` で `FROZEN.json` に sha256 と日時（12:38:40）。
   - 既存の文との重なりの確認（読解器を呼ばない。`tests/` の本テスト・データと `docs/*.md` の全文に種の文を探した）: 初版で J27 の挨拶が既存のテストと同じだったので、凍結の前に別の文（ごきげんよう。）に差し替えた。再度の確認で重なり 0。
2. 読解器だけに通す: `$PY tests/observe/measure.py --reader-only --out $A/reader_seed_obs.jsonl`（12:39:02）。読めた種は全体の半分を超えたので、種の文は足さなかった。ただし「縁側で」を含む文が読めないと分かったので、文は足さず、読める文を錨にしたケース `viewpoints_add1.jsonl` を足して凍結（12:39:30）。
3. 期待を手で書いて凍結: `tests/observe/data/make_expected.py`（規則・凍結した入力・読解器の出力だけから書いた。観測器の出力は見ていない）-> `expected.jsonl` `expected_add1.jsonl`。凍結 12:41:30。
4. 最初の観測: 12:44:44（`FROZEN.json` の `first_observation`）。食い違いは期待を直さず `disagreements.json`（12:45:10）と `disagreements_o4.json`（12:47:46）に凍結した。
- `$PY -m pytest -q -p no:cacheprovider tests/test_observe_data.py` -> 全部通る。

## 手順 7（測定物）
```
$PY tests/observe/o1_bytes.py --cases $D/viewpoints.jsonl --seeds 0 4242 --out $A/o1_bytes.txt
$PY tests/observe/o1_replay.py --cases $D/viewpoints.jsonl --out $A/o1_replay.txt
$PY tests/observe/measure.py --reobserve --cases $D/viewpoints.jsonl --out $A/o2_reobserve.json
$PY -c "import json; d=json.load(open('$A/o2_reobserve.json')); assert d['mismatch']==0 and d['extra_content_words']==0 and d['reobserved']==d['elements']"
$PY tests/observe/measure.py --o4 --cases $D/viewpoints.jsonl --out $A/o4.json        # 終了コード 1（O4-e-L07 が事前登録の読みの反例）
$PY tests/observe/measure.py --o5 --cases $D/viewpoints.jsonl --out $A/o5.txt
$PY tests/observe/measure.py --summary --cases $D/viewpoints.jsonl --out $A/summary.json
$PY tests/observe/measure.py --compare --cases $D/viewpoints.jsonl --out $A/expected_compare.json
$PY tests/observe/check_prereg_order.py --prereg $A/prereg.txt --frozen $D/FROZEN.json --doc docs/OBSERVATION.md | tee $A/o6.txt
$PY tests/observe/check_no_data_words.py --base 5cae978 | tee $A/check_no_data_words.txt
$PY tests/reading_soundness/check_hardcode.py --base 5cae978 > $A/check_hardcode.txt
$PY $A/check_hardcode_with_new_files.py > $A/check_hardcode_with_new_files.txt        # 新しい 2 ファイルの行も追加行として数えた版
$PY tests/observe/run_bank.py --items tests/bank_score/fixtures/B3/items.jsonl --out $A/b3_selfmade.jsonl --summary $A/b3_selfmade_summary.json --no-index
$PY tests/observe/run_bank.py --items tests/bank_score/fixtures/B3/items.jsonl --out $A/b3_selfmade_idx.jsonl --summary $A/b3_selfmade_idx_summary.json --index $IDX
$PY -m verantyx.cli observe --anchor-record J09 --structure $D/seeds_ja.jsonl --placement $D/placement.json --direction FACE_SWAP:agent --index $A/index_small | tee $A/o5_example.json
```
- O3 の grep: `grep -nE "import random|...|PYTHONHASHSEED" verantyx/observe.py verantyx/salience.py | tee $A/o3_grep.txt`（該当は `MemoryLedger` の既定の時計の 1 行だけ）、`grep -nE "\bmin\(|\bmax\(|sorted\(|\[0\]|next\(iter|for .* in .*set\(|frozenset" ... | tee $A/o3_review_points.txt`（中間職が 1 行ずつ読む一覧）、`grep -n "ANSWER" verantyx/observe.py | tee $A/o5_grep.txt`（注釈の行だけ）。
- 共通: `$A/common_outside.txt`（読み込まれた verantyx が全部 $W 配下）、`$A/common_outside_paths.txt`（許可パスの外の変更は空）、`$A/common_additions_only.txt`。
- 索引の検索: 作ったあと `index search "視点から構造を観測して生成"` と `"顕著さの場 台帳"` が `observe` と `salience` を返す（`$A/index_after.txt` `$A/index_after_salience.txt`。モジュールの docstring の先頭行に日本語を入れて引けるようにした）。

## 手順 8（文書）
- `docs/OBSERVATION.md` の残りの節を書き、数値は `$PY tests/observe/recompute.py --write` で作った区間（`<!-- recompute:begin -->` 〜 `<!-- recompute:end -->`）だけに置いた。`$PY tests/observe/recompute.py --check` -> 終了コード 0。

## 手順 9（全体の確認）
```
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$W" TMPDIR=<scratchpad> /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider -rf --tb=no tests > $A/pytest_full.txt 2>&1
grep '^FAILED\|^ERROR' $A/pytest_full.txt | sed 's/ - .*//' | sort > $A/pytest_failures.txt
comm -13 /Users/motonisihikoudai/Projects/vera-impl/baselines/dev_5cae978_failures.txt $A/pytest_failures.txt | tee $A/pytest_new_failures.txt
```
- 全体テストは 1 回だけ流した（実行前の `uptime` は 1 分平均が 8 未満）。基線にない失敗は 2 件で、どちらも基点だけのクリーンなクローンでも落ちる（F9 は作業ツリーが未コミットのときの失敗で、スクラッチのコミット済みクローンでは通る）。説明は `$A/pytest_new_failures.explained.md`。
- 一時物（クローン・台帳の写し）は scratchpad か `$A/work_*`・`$A/tmp`・`$A/index_small` に作り、消していない。

## 第 2 ラウンド（レビュー r1 への対応。時刻は `date` の出力）

### 最初の観測の後のコード変更の記録（任意 4）
- 第 1 ラウンドで、最初の観測（12:44:44）の後に `verantyx/observe.py`（最終更新 12:49:33）と `verantyx/salience.py`（12:49:24）が変わっている。何をどう直したかの個別の記録は第 1 ラウンドでは残していない（残していなかったことをそのまま書く）。中間職の確認では、全 94 ケースの要約（`view.summarize`）は最初の観測の記録 `first_run_summaries.json` と一致していた。
- 第 2 ラウンドの変更（すべて下に時刻つき）。それぞれの前後で観測した範囲は、第 2 ラウンドの末尾の `compare_with_first_run.txt`（今の全ケースの要約を `first_run_summaries.json` と比べた結果。違うのは 2 ターンの 6 ケースだけ）。

### 必須 1 / 2（場の段 (ii) の `U`、O4 の判定）
1. 13:18:13〜13:18:31: 事前登録 P8 の `U` の定義を書き換え、変更記録 3 を書いた（`docs/OBSERVATION.md`）。区間の sha256 は `0e0aecea...` → `2243402b...`。`artifacts/w3-c/prereg.txt` に `sha256_current` / `logged_changes_current: 2` / `change3_recorded_at` を足した（最初の観測の後の変更であることを prereg.txt の見出しにも書いた）。
2. 13:19:40: `FROZEN.json` の `inputs_r2`（`ledgers/L11.jsonl` `ledgers/L12.jsonl` `viewpoints_r2.jsonl`。`tests/observe/gen_data_r2.py` が書いた。観測器には通していない）。
3. 13:19:43: `FROZEN.json` の `expected_r2`（`expected_r2.jsonl` と `make_expected_r2.py`。2 ターンの 6 行と LG11・LG12・LG13 の期待を規則から手で書いた。観測器の出力は見ていない）。`expected.jsonl` `expected_add1.jsonl` `disagreements*.json` は 1 byte も変えていない（`check_prereg_order.py` の `frozen_files_unchanged: ok`）。
4. この間（13:19〜13:21）にコードを書き換えた: `salience.build_context(ledger, neighbors, anchor_text)`、`observe._anchor_sentence`、`salience_trace.utterance`。観測器を新しい規則で流す前に、必須 4 の確認のための 1 回の CLI 実行（台帳なし）をした。
5. 13:21:27: `FROZEN.json` の `first_observation_r2`（新しい規則での最初の観測。上の台帳なしの 1 回を除く）。
6. `$PY tests/observe/measure.py --compare --cases $D/viewpoints.jsonl --out $A/expected_compare.json` → 1 ターンの期待のあるケース 91 のうち、そのまま一致 88・食い違い 3（第 1 ラウンドから凍結済みの 3 ケース）。2 ターンの 6 行は期待と一致 6/6。新しい期待の食い違いは 0（`disagreements_r2.json` は作らない）。
7. `$PY tests/observe/measure.py --o4 --cases $D/viewpoints.jsonl --out $A/o4.json` → 終了 0、両方の読みで `violations []`、L09/L10 は違う行 `[2]`。判定の確認: `$PY $A/o4_old_rule_check.py > $A/o4_old_rule_check.txt`（`build_context` を旧規則に差し替えて同じ判定を流す。反例が出る: 登録の読み `['O4-d-L01', 'O4-e-L07', 'O4-f-L08']`、もう一つの読み `['O4-c-L05', 'O4-d-L01', 'O4-f-L08']`、終了 1）。

### 必須 3 / 4（占有の型、拒否理由の 0 件）
- `verantyx/observe.py` の `_IndexReader.occupancy`（引いた surface が 0 のとき `UNKNOWN_QUERY_NOT_SEARCHED`）、`_new_counts`（拒否理由の閉じた一覧を整列して 0 で初期化。`REFUSAL_NOT_ON_THIS_PATH` の 2 つは除く: 判断記録 E22）。
- 確認: `$PY -m verantyx.cli observe --anchor-text "司書は学生に辞書を貸した。" --no-index | $PY -c "import json,sys; r=json.load(sys.stdin)['counts']['realization']['refused']; print(sorted(r)); assert 'NOT_REALIZABLE' in r and all(v == 0 for v in r.values())"` → 12 の理由が 0 で並ぶ。

### 任意の改善
- 1: `tests/observe/run_bank.py` を `observe.run_entry` 経由に変えた（自作の B3 の行は変更前と `cmp` 一致）。2: `--lang` の検査（`BAD_ARGUMENTS`）。4: この節。5: 判断記録 E25。3（`basis: anchor_input`）はしていない。

### 流し直したもの
`o1_bytes.py`（`checked 97, mismatch 0`。r2 の 3 ケースを含む）・`o1_replay.py`（`replayed 25`）・`measure.py --reobserve/--o5/--summary/--compare/--o4`・`check_prereg_order.py`・O3 の grep 2 本・`realize_parity.py`・`check_no_data_words.py`・`check_hardcode.py` と新しい 2 ファイルの版・`run_bank.py` 2 本・共通の 3 本・`recompute.py --write` → `--check`・新しいテスト 5 本（`285 passed`）・全体テスト 1 回（最後。結果は docs の測定結果）。
