# W3-b 再計算手順書（コマンドと要約出力の記録）

PY=artifacts/w3-b/py.sh（W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-b-S 基準）

## 手順 0
- `$PY -c "import verantyx, sys; print(verantyx.__file__)"` -> /Users/motonisihikoudai/Projects/vera-impl/wt/W3-b-S/verantyx/__init__.py
- `$PY -m verantyx.cli index search "事象の十字" > artifacts/w3-b/index_before.txt`（既存: cross.py / cross_store.py / events.py などが出る。event_cross は無い）
- `$PY -m verantyx.cli index search "役割と型の一致" > artifacts/w3-b/index_before_agreement.txt` -> UNKNOWN_NOT_FOUND

## 手順 1
- docs/EVENT_CROSS.md の事前登録節を書いた。`artifacts/w3-b/prereg.txt` に sha256 と日時、tests/event_cross/data が空であることを記録。

## 手順 2〜4（実装）
- `verantyx/event_cross.py` 新規。`semantic_read.py` に `--events`、`cli.py` に `read-events`。
- `$PY -m pytest -q -p no:cacheprovider tests/test_event_cross.py` -> 55 passed
- `$PY -m pytest -q -p no:cacheprovider tests/test_event_cross_entry.py` -> 39 passed

## 手順 5（検査データの文。凍結した時点で semantic_read には 1 度も通していない）
- `tests/event_cross/data/sentences_ja.jsonl`（82 文）・`sentences_en.jsonl`（81 文）を手で書いた。
- 件数・タグ・重なり・固有名の確認は読解器を呼ばない `tests/event_cross/` の外のスクラッチの短いスクリプトで行った（日本語 82・英語 81、各タグは下の表）。
- 既存の文との重なり: 初版で 5 文（挨拶 3・英語 2）が既存の文と同じだったので、凍結の前に別の文に差し替えた（再度の確認で重なり 0）。
- `FROZEN.json` に sha256 と日時を書いた。

## 手順 6（期待を手で書いて凍結 -> 初めて読解器に通す）
- 期待を `tests/event_cross/data/expected_{ja,en}.jsonl` に手で書き、FROZEN.json の `expected` に sha256 と日時（2026-10-03 09:43:28 +0900）を記録。そのあとで初めて読解器に通した（最初の通しは 2026-10-03 09:43:53 +0900）。
- `$PY tests/event_cross/classify.py --obs artifacts/w3-b/reader_obs.jsonl --out artifacts/w3-b/e2_classes.json --disagreements-md artifacts/w3-b/reader_disagreements.draft.md --disagreements-json tests/event_cross/data/reader_disagreements.json`
  1 回目（163 文）: 読解器が読んだ 39 文 / 163 文（4 分の 1 未満）。(a) 124・(b) 35・(c) 4。出力を `reader_obs_set1.jsonl`・`e2_classes_set1.json`・`reader_disagreements_set1.json` に残した。
- 計画書の指示（読める文が 4 分の 1 未満なら読める型の文を新しい id で追記してよい）に従い、`*_add1.jsonl`（日 21・英 20 文）を、期待を書いて凍結（2026-10-03 09:45:13 +0900）してから読解器に通した。
  2 回目（204 文）: (a) 134・(b) 65・(c) 5。
- `$PY -m pytest -q -p no:cacheprovider tests/test_event_cross_data.py` -> 208 passed

## 手順 7（測定物。再生成のコマンド）
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-b-S, PY=$W/artifacts/w3-b/py.sh, A=$W/artifacts/w3-b
```
$PY tests/event_cross/collect_inputs.py --out $A/e1_inputs.jsonl                      # wrote 775 inputs (754 from texts, 21 edge)
$PY tests/event_cross/e1_parity.py --mode base    --inputs $A/e1_inputs.jsonl --out $A/e1_base.out    --codes $A/e1_base.codes --base-sha $A/e1_base.sha
$PY tests/event_cross/e1_parity.py --mode current --inputs $A/e1_inputs.jsonl --out $A/e1_current.out --codes $A/e1_current.codes
$PY tests/event_cross/e1_parity.py --mode current --events --inputs $A/e1_inputs.jsonl --out $A/e1_events_1.out --codes $A/e1_events_1.codes
$PY tests/event_cross/e1_parity.py --mode current --events --inputs $A/e1_inputs.jsonl --out $A/e1_events_2.out --codes $A/e1_events_2.codes
$PY tests/event_cross/e1_parity.py --mode current --events --strip-events --inputs $A/e1_inputs.jsonl --out $A/e1_stripped.out --codes $A/e1_stripped.codes
( cmp $A/e1_base.out $A/e1_current.out && cmp $A/e1_base.codes $A/e1_current.codes && echo E1a_OK
  cmp $A/e1_events_1.out $A/e1_events_2.out && cmp $A/e1_events_1.codes $A/e1_events_2.codes && echo E1b_OK
  cmp $A/e1_stripped.out $A/e1_current.out && cmp $A/e1_stripped.codes $A/e1_current.codes && echo E1c_OK
  head -1 $A/e1_subprocess.txt; echo "inputs: $(wc -l < $A/e1_inputs.jsonl)"; cat $A/e1_base.sha ) | tee $A/e1_cmp.txt
$PY tests/event_cross/e1_subprocess.py --inputs $A/e1_inputs.jsonl --base-out $A/e1_base.out --base-codes $A/e1_base.codes --out $A/e1_subprocess.txt   # 先に実行（e1_cmp.txt が読む）
$PY tests/event_cross/events_parity.py --field input --inputs tests/bank_score/fixtures/B1_v2/items.jsonl tests/bank_score/fixtures/B1_v2_r2/items.jsonl tests/bank_score/fixtures/B1_v2_r3/items.jsonl | tee $A/e5_selfmade_parity.txt
$PY tests/event_cross/measure.py --out $A/events_all.jsonl --ids $A/events_all_ids.txt --summary $A/e2_summary.json
$PY tests/event_cross/measure.py --timing $A/timing.json                               # 負荷 8 未満のときだけ測る
$PY tests/event_cross/classify.py --obs $A/reader_obs.jsonl --out $A/e2_classes.json --disagreements-md $A/reader_disagreements.draft.md --disagreements-json tests/event_cross/data/reader_disagreements.json
```
第 2 ラウンドで端の入力に `--e`・`--ev`・`--eve`・`--event` を足した（`--events` を argparse に登録しない形に直した。docs/EVENT_CROSS.md の判断記録）。
結果の要約: E1a_OK・E1b_OK・E1c_OK、サブプロセス 35 入力で不一致 0、自作バンク 118 問で `checked 118, mismatch 0`。base の本文は `git show b471f5a:verantyx/semantic_read.py` の sha256（e1_base.sha）= `git show ... | shasum -a 256` の出力と一致（3b7faaad...）。

## 手順 8（文書）と E 系の確認
- `$PY tests/event_cross/recompute.py --write`（文書の区間と出力例を artifacts から作る）→ `--check` が 0。`--audit`（区間の外の数字の点検）は 0 行。
- 共通・E3・E4・到達性の確認は `artifacts/w3-b/e_misc.txt`（読み込まれた verantyx が作業ツリー配下: `outside []`、E3: 9 passed と relations equal on 204、E4: 18 passed、`index search "事象の十字"` が event_cross を返す）。
- E6: 全体テスト（1 台）は `artifacts/w3-b/pytest_full.txt`（`116 failed, 7093 passed ...`（第 2 ラウンドで流し直した。第 1 ラウンドは 7080 passed））、失敗集合の差は `pytest_new_failures.txt`（2 件。説明は `pytest_new_failures.explained.md`・文書）。
  `$PY tests/reading_soundness/check_hardcode.py --base b471f5a` -> `check_hardcode.txt`（失敗欄は両方 `[]`、終了コード 0）。
  git の差分は未追跡の新規ファイルを含まないので、event_cross.py の全行を追加行に足して同じ検査を流した出力（`$PY artifacts/w3-b/check_hardcode_with_new_file.py`）も `check_hardcode_with_new_file.txt`（失敗欄は両方 `[]`、終了コード 0）。
