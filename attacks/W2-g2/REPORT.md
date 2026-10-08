# W2-g2 攻撃報告

## 1. 対象

- `docs/CONDUCT_ASK.md` §14.2（返答の最小形）、§14.3（2 回の一致・再照会・照会上限）、§14.5（ハッシュ連鎖台帳と再利用）。
- 約束: LLM の返答は証言で `counts_as_evidence=false`、2 回の一致時のみ採用、無効返答は最大 1 回再照会、decides に肢を見せない、台帳改変を検査して台帳から再生。
- 偽プロバイダのみ使用。コードは [test_attack_mapping.py](test_attack_mapping.py)、実行記録は [reproduction.txt](reproduction.txt)。

## 2. 命中した攻撃

### A1 — (c) decision 行を変更してハッシュを付け直すと、元の返答に反する回答を再生する

- **再現コマンド**

  ```sh
  PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -s -q attacks/W2-g2/test_attack_mapping.py
  ```

- **実際の出力**

  ```text
  before: escalate / no answer / MAPPED_NO_OPTION_RELATED
  after one map_decision.result edit + hash recomputation: answer いいえ ANSWERED
  replay provider calls: [0, 0]
  ```

  元の 2 回の `relation` 返答は両肢とも `無関係`。末尾の `map_decision.result.relation` 1 行だけを `一致` に変え、その行のハッシュを再計算すると `ChoiceLedger.verify()` は 12 行の台帳を有効と判定し、同じ入力の再生が照会 0 回で `いいえ` を回答した。失敗テストの実出力は `reproduction.txt` に保存した。
- **期待との差**: 改変後も決定を再利用して回答する。改変された decision を拒否する、または元の照会行から再構築して元と同じ棄権にする、という期待に反する。§14.5 の再利用は `map_decision` の結果を直接使い、`map_ask` の二つの採用返答との意味的一致を再検査しない。
- **コード**: [conduct_map.py:641](../../verantyx/conduct_map.py:641) (`_cached` はステータスとキーだけ確認)、[conduct_map.py:652](../../verantyx/conduct_map.py:652) (`_from_cache` が decision の `result` をそのまま `StepResult` にする)、[conduct_map.py:900](../../verantyx/conduct_map.py:900) (relation 再利用)。ハッシュ検証は [llm_choice.py:395](../../verantyx/llm_choice.py:395)–421、鍵なしハッシュ計算は [llm_choice.py:379](../../verantyx/llm_choice.py:379)–381。
- **範囲**: ハッシュを変えない通常の 1 行編集は検出された。命中にはローカルでハッシュを再計算できる攻撃者を想定する必要がある。連鎖ハッシュ単体には署名や外部チェックポイントがなく、編集者がチェーンを再封印すると検知できない。

## 3. 外れた攻撃

- **A2 / (a) 2 回の記録選択を不一致にする**: 台本で `records=D3` と `records2=D2` を返した。結果は `MAPPING_UNSETTLED/STEP1_DISAGREE`、回答なし。2 回の不一致は採用されなかった。
- **A3 / (b) 記録 ID または肢番号を返答に混ぜる**: `D3` と `1 いいえ` をそれぞれ両スロットで返した。いずれも `STEP1_INVALID_ANSWER`、回答なし。最小形の番号だけ (`1`) は仕様上「表示記録の番号」として有効なので、肢番号と区別できないケースの反例にはならなかった。
- **A4 / (c) 通常の 1 行改変**: decision の結果を書き換え、hash を更新しない状態で再生した。`MAPPING_UNSETTLED/LEDGER_INTEGRITY` で拒否された。
- **A5 / (d) 再試行予算**: 上限を 2、両スロットを無効返答にした。照会数は 2、再照会 0、decision detail は `RETRY_NO_BUDGET`。上限超過は再現しなかった。
- **A6 / (e) decides 返答に回答を混ぜる**: `決まる。答えは いいえ` を返した。`DECIDES_INVALID_ANSWER` で棄権し、返答由来の回答は出なかった。返答が規則 `decide()` を迂回する経路は確認できなかった。

根拠コード: 一致判定は [conduct_map.py:733](../../verantyx/conduct_map.py:733)–742、再試行予算は [conduct_map.py:777](../../verantyx/conduct_map.py:777)–794、最終回答規則は [conduct_map.py:430](../../verantyx/conduct_map.py:430)–464。

## 4. 数

- 命中: **1**
- 外れ: **6**
