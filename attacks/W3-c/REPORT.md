# W3-c 攻撃結果

## 1. 対象

- `docs/OBSERVATION.md` 事前登録 P2・P3（座標、全経路の座標を保持）、P4・P8（近傍と同点）、P9（台帳の payload と追記）、P11（観測出力）。
- 同文書の「同じ（構造・視点・状態）には同じ出力」（105行）、再観測手順（139〜144行）、D14 の配置・近傍。
- `verantyx/observe.py` の `FilePlacement`、経路展開、`run_entry`。
- `verantyx/salience.py` の JSONL 台帳検証。

## 2. 命中した攻撃

### W3C-A1 — 近傍リストの並べ替えで JSON の byte が変わる

- 観点: **(a)** 実際の出力の不変性。攻撃対象 (b) の配置ファイル近傍順。
- 再現コマンド:

  ```sh
  PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-c/test_attack_observe.py::test_neighbor_file_order_does_not_change_the_output
  ```

- 入力: 同じ近傍集合 `{"太郎": ["花子", "次郎"]}` と `{"太郎": ["次郎", "花子"]}`。どちらも CLI に同じ錨・`FACE_SWAP:agent` を渡す。
- 実際の出力（失敗時の診断）:

  ```text
  focus/ranks equal=True
  placement ids=('file:aedd4bc744c95134eeeed44b9b543e54692a6fcf7fc9e24152fa2c58d962ac74', 'file:cb29d5983ff29d313c6187de08bf14e2255480bf175c7e836ba9e5ac1513d85e')
  neighbor ids=('file:aedd4bc744c95134eeeed44b9b543e54692a6fcf7fc9e24152fa2c58d962ac74', 'file:cb29d5983ff29d313c6187de08bf14e2255480bf175c7e836ba9e5ac1513d85e')
  ```

- 期待との差: `NeighborResult.items` は集合として正規化され、近傍順は順位・勝者を決めない約束だが、出力 JSON 全体は byte 不一致。今回は焦点・順位・候補列は同じで、差は配置ソース ID に限られる。`FilePlacement` が近傍をソートする一方、ID は順序を含む元ファイル byte の SHA-256 なので差が出る。
- 該当箇所: `verantyx/observe.py:155`（近傍をソート）、`verantyx/observe.py:168`（raw byte の SHA-256）、`verantyx/observe.py:320-322`（ID を出力）。

### W3C-A2 — 合流した升の座標を次のレベルで引き継がない

- 観点: **(a)** P3 の全経路座標という出力約束。
- 再現コマンド:

  ```sh
  PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-c/test_attack_observe.py::test_all_paths_are_carried_through_a_merged_cell
  ```

- 実際の出力:

  ```text
  C paths=[['anchor', 'structure-bc-1'], ['anchor', 'structure-bc-2']]
  D paths=[['anchor', 'structure-bc-1', 'structure-cd']]
  the incomplete coordinate still reports {'status': 'REOBSERVED', 'reason': None}
  ```

- 期待との差: `A→B` には anchor 読みと `structure-ab` の 2 経路、`B→C` には `structure-bc-1/2` の 2 経路があるため、`話す` とその子 `笑う` は各 4 経路を `coords` に持つべき。実際はそれぞれ 2 経路と 1 経路だけ。さらに、残った 1 経路だけを検査する `reobserve` は `REOBSERVED` を返すため、欠落した経路を検出しない。
- 該当箇所: `verantyx/observe.py:551-557`（複数座標を保持する `Cell` と先頭座標 accessor）、`verantyx/observe.py:680`（次の EDGE 座標を `cell.coord` だけから作成）、`verantyx/observe.py:872-874`（同レベルの経路を合流）。FACE_SWAP も `verantyx/observe.py:649` で同じ先頭座標だけを使う。

### W3C-A3 — 不正な台帳 payload を受理し、追記してしまう

- 観点: **(a)** P9/D16 の実出力。攻撃対象 (g) の終了コードと副作用。
- 再現コマンド:

  ```sh
  PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-c/test_attack_observe.py::test_malformed_ledger_is_rejected_without_appending
  ```

- 入力台帳: `kind="utterance"` なのに `payload.text` が文字列でなく `[]` の JSONL 1 行。
- 実際の出力（失敗時の診断）:

  ```text
  returncode=0, appended_lines=2, stdout_is_json=True, stderr=''
  ```

- 期待との差: P9 の utterance payload は錨の文（文字列）を要求し、破損台帳なら終了コード 3 `LEDGER_INVALID` で追記なしのはず。実際は正常終了し、既存行を残したまま `utterance` と `observation` の 2 行を書き足した。
- 該当箇所: `verantyx/salience.py:93-95` は payload が Mapping かしか検証しない。`verantyx/observe.py:1098-1103` の読み込み時に拒否されず、`verantyx/observe.py:1109-1111` で追記される。

## 3. 外れた攻撃

- 近傍の順序を入れ替えて同点の勝者・候補順が変わるかを試した。**焦点と順位は等しい**（`focus/ranks equal=True`）ため、順序で勝者を選ぶ攻撃は外れ。上記 A1 は byte 出力のソース ID だけが変わる別の実害として記録した。

## 4. 数

- 命中: **3**
- 外れ: **1**
