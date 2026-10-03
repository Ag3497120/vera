# W3-b 攻撃報告

## 1. 攻撃対象

- `docs/EVENT_CROSS.md` §「型の定義」`PlaceResult.types`: 型候補は順位のない集合で辞書順に並べる。
- `docs/EVENT_CROSS.md` §「変換の規則」3: 関係は読解器の件数・順・向きを保って写す。
- `docs/EVENT_CROSS.md` §「変換の規則」4: 同じ入力・同じ lookup の `to_dict()` は同じバイト列。
- `docs/EVENT_CROSS.md` §「型一致の決め方」および事前登録の規則 6: `MULTIPLE` は `NOT_CHECKED(MULTIPLE)` として割れを保つ。

## 2. 命中した攻撃

### W3B-A1 — 偽 PlacementLookup が返す MULTIPLE の型順をそのまま出す

- 観点: (a) 文書の型順約束に反する実出力。
- 再現コマンド:

  ```sh
  PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-b/test_attack_placement_type_order.py
  ```

- 実際の出力: 失敗箇所は `placement["types"] == ["PERSON", "PLACE"]`。実値は `['PLACE', 'PERSON']`。
- 期待との差: 同じ候補集合を辞書順に直列化する約束に反し、 lookup のタプル順がそのまま出力に漏れる。型判定自体は `NOT_CHECKED(MULTIPLE)` だが、保存する `place.types` が規約どおりでない。
- コード: [`verantyx/event_cross.py`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-b/verantyx/event_cross.py:102) の `invariant_problems()` は並びを検査せず、同ファイル:328 がそのまま有効値として返す。直列化は同ファイル:136。
- 攻撃テスト: [`test_attack_placement_type_order.py`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-b/attacks/W3-b/test_attack_placement_type_order.py:21)

### W3B-A2 — 等しい Mapping の関係キー順だけで JSON バイト列が変わる

- 観点: (a) 同一の意味入力に対する決定的直列化の約束に反する実出力。
- 再現コマンド: 上記と同じ。
- 実際の出力: `reordered == base` は通るが `assert a == b` が失敗。JSON の差分は関係要素のキー順だけで、片方が `{"type":"sequence","from":0,"to":1}`、もう片方が `{"to":1,"from":0,"type":"sequence"}`。
- 期待との差: 入力 Mapping は等しく、関係の種類・向き・添字も同じなのに、辞書の挿入順だけで `to_dict()` のバイト列が変わる。十字をそのまま探索キーにするという決定性の約束を満たさない。
- コード: [`verantyx/event_cross.py`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-b/verantyx/event_cross.py:237) が各 relation mapping をキー順を保った `dict` として複写する。
- 攻撃テスト: [`test_attack_placement_type_order.py`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-b/attacks/W3-b/test_attack_placement_type_order.py:47)

実行結果の末尾: `2 failed in 0.08s`。

## 3. 外れた攻撃

1. `--events` を `--text` の前に置く、`--text VALUE` の形にする、同じ `--events` を重ねる。各ケースで出力・終了コードが単独の `--events` と一致した（`True`）。
2. 偽 lookup で `agent` に `ARTIFACT` を返し `DISAGREE` を作る。既存テスト `test_agreement_direct_outside_the_table_is_disagree_and_the_role_does_not_change` が通り、役割と値は変わらない。
3. 3 節と 3 関係を与える。`test_three_clauses_relations_are_copied_exactly` が通り、十字番号・関係数・順・向きは維持された。
4. `from_coarse_query` に `top` の逆順配列を渡す。`test_from_coarse_query_copies_the_documented_shape` が通り、候補は辞書順になった。
5. `--events` 無しのバイト一致、略記 argv、空・長すぎ・制御文字入力の拒否出力を確認。関連既存テスト 315 件が通り、差は再現しなかった。

関連既存テストの実行結果: `315 passed in 4.93s`。

## 4. 数

- 命中: **2**
- 外れ: **5**
