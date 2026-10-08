# W4-m 攻撃報告

## 1. 対象

- `docs/SOVEREIGN.md` §「階層」・「形の検査」・操作・同意の意味・退役・限界。
- `artifacts/w4-m/PREREG_W4m_promotion.md` §5（同意の窓）、§6（分類と等式）、§7 S1〜S5。
- 実行した攻撃テスト: `attacks/W4-m/test_attack_sovereign.py`。
- 既存テストの基準確認: `tests/test_sovereign_store.py`、`test_sovereign_ledger.py`、`test_sovereign_units.py`、`test_sovereign_promote.py`、`test_sovereign_cli.py`。

攻撃テストのコマンド:

```sh
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W4-m/test_attack_sovereign.py
```

実行結果は `attacks/W4-m/pytest.txt` に保存した（4 failed, 6 passed）。既存の関連テストは 160 passed。結果は `attacks/W4-m/related_pytest.txt`。

## 2. 命中した攻撃

### H1 — 同意を撤回した後、進行中の promote が昇格を書き込む

- 観点: (a)。攻撃対象 (e)、事前登録 S4 / §5。
- 再現テスト: `test_revoking_consent_while_promote_is_in_flight_stops_writes`。
- 再現コマンド: 上記の攻撃テストコマンド。
- 実際の出力:

  ```text
  assert sov.describe(tmp_path, "s1").consent["promote"] is False
  assert result[0]["verdict"] == "NO_CONSENT", result[0]
  AssertionError: {'verdict': 'PROMOTED', ...}
  assert 'PROMOTED' == 'NO_CONSENT'
  ```

- 期待との差: `promote` が同意 `true` を読み、候補を解析した直後に同意を `false` に追記し、その後に続行させると、現在の同意は `false` なのに `PROMOTED` と両側への書き込みが起きた。同意を再確認しないため、撤回が進行中の処理に反映されない。
- 場所: `verantyx/sovereign.py:1663-1675` で同意を一度だけ取得し、`1701-1711` で後から追記する。

### H2 — release と promote の競合で、release 後も昇格が active に残る

- 観点: (a)。攻撃対象 (f)、事前登録 S5 / docs §「退役」。
- 再現テスト: `test_release_racing_with_promote_leaves_no_active_promotion`。
- 再現コマンド: 上記の攻撃テストコマンド。
- 実際の出力:

  ```text
  release(...) -> {"verdict": "RELEASED", ...}
  promotions_answer(..., include_retired=False)
    -> {"verdict": "ANSWER", "promotions": [{"seq": 1, "promotion_id": "60615ad34c223a0cbc9d2932", ...}]}
  AssertionError: active promotions は空でなく 1 件
  ```

- 期待との差: promote が候補を確定して構造側へ書く直前で停止し、release を完了してから再開すると、release の退役走査には候補がまだ無い。再開した promote は構造側の行を追加した後、RELEASED 状態で back-link を拒否される。その結果、退役されていない構造側の行が残り `active_promotions` に出る。
- 場所: `verantyx/sovereign.py:1331-1343` の退役処理と `1375-1382` の RELEASE 追記の間に、`promote` の `1682-1691` の in-progress 判定と `1709-1711` の二段追記が原子的に連携していない。

### H3 — 2 プロセスの同時 promote が同じ候補を二重登録する

- 観点: (a)。同時実行 (c)、事前登録 §6 の `already_promoted` と S4 の昇格記録。
- 再現テスト: `test_two_process_promotions_do_not_duplicate_the_same_candidate`。両プロセスを解析完了位置で barrier 同期する。
- 再現コマンド: 上記の攻撃テストコマンド。
- 実際の出力:

  ```text
  2 子プロセスとも verdict=PROMOTED
  active promotions: 同じ promotion_id=60615ad34c223a0cbc9d2932 が seq 1 と seq 2 に存在
  AssertionError: assert 2 == 1
  ```

- 期待との差: 両方が `existing` を空として解析し、その後にそれぞれ同じ決定的 `promotion_id` の構造側行を追加した。候補 1 件に対し active な昇格が 2 件となる。
- 場所: `verantyx/sovereign.py:1677-1702` で既存昇格の確認と候補解析を済ませた後、`1703-1711` で再確認なしに追記する。

## 3. 外れた攻撃

1. export 済みファイルの event payload を raw SQLite で変更し、`event_log_no_update` を元と同じ SQL で作り直して attach。実出力は `ATTACHED`、読み出しは `forged`。ただし docs §「限界」には、持ち主がトリガを外せることと payload 改変は検出しないことが明記されているため、約束違反の命中には数えない（テスト上の期待は外れ）。
2. スレッドから append を同時実行。seq は `1, 2`、ID と行が一致し、seq の穴・重複なし。
3. barrier で揃えた別プロセス 2 個から append。seq は `1, 2`、両方成功し、seq の穴・重複なし。
4. raw SQLite から `seq=-1` を INSERT。`IntegrityError` で拒否され、行数は 0 のまま。
5. 同意前の3事件を後から同意して promote。`NOTHING_TO_PROMOTE`、`outside_consent_window=3`、active 昇格なし。
6. 通常の順序で promote → release → promote / attach。後続 promote は `RELEASED`、同じ root での file attach は `REFUSED_RELEASED`、active 昇格なし。
7. raw SQLite の `ALTER TABLE event_log ADD COLUMN ...`。次の `open_ledger` は `SchemaMismatch`。
8. 同じ秒に同じ持ち出しファイルを別 root へ attach する structure_ref 衝突。既存の `test_structure_ref_differs_for_the_same_file_attached_in_two_new_roots_at_the_same_time` と移動後の back-link 検査を含む関連テストで拒否・分離を確認（関連テスト全体 160 passed）。

## 4. 数

命中 3、外れ 8。
