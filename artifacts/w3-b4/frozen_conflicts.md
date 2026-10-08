# W3-b4: 凍結した既存テストが、このチケットの目的と衝突する 5 件（既存テストは変えていない。第 3 ラウンドで書き直した）

第 3 ラウンド（表の変更記録 3: P_ACT・P_CREATE・P_EMOTION の `place/で/PLACE` の 3 行を外した）の状態での申告。前の版は `artifacts/w3-b4/r3/frozen_conflicts.md.before_r3`（第 2 ラウンドまでの版。そこでは で の行で「読む」としていた）。

基線（`dev_c875ed3_failures.txt`）に無い新しい失敗は、関係するテスト 3,580 件（この木。成功 3,573・失敗 7）（`artifacts/w3-b4/r3/pytest_related_after.txt`。基点の同じ選び方は `artifacts/w3-b4/pytest_related_base.txt`: 失敗 2）で
**この 5 件だけ**（`r3/pytest_related_new.txt`）。テスト名は第 2 ラウンドと同じだが、**中身が変わった**:

| # | テスト | 凍結した期待 | 今の出力（第 3 ラウンド） | 行の `expect` との判定 | 理由 |
|---|---|---|---|---|---|
| 1 | `tests/test_semantic_read_w3b1.py::test_every_row_of_the_new_data_with_the_fixture[W3B1-U-090]` | `entry_expect: abstain`（W3-b1 の理由 FRAME_NOT_READ。述語 送り出す=P_ACT） | 読む: `agent 兄 / goal 駅`（goal/へ/PLACE、P_ACT の行） | `correct`（行の `expect` は goal） | P_ACT は v2 の読む型で、へ/goal の行が残っている |
| 2 | 同 `[W3B1-U-091]` | 同上（踏み出す=P_ACT） | 読む: `agent 弟 / goal 港` | `correct` | 同上 |
| 3 | 同 `[W3B1-U-092]` | 同上（踏み込む=P_ACT） | 読む: `agent 母 / goal 庭` | `correct` | 同上 |
| 4 | `tests/test_semantic_read_w3b2.py::test_u3_does_not_read_when_the_predicate_is_not_of_a_type_the_table_reads_or_is_split` | 「兄が校庭で遊んだ。」（遊ぶ=P_ACT）が診断 `PLACEMENT_FRAME_NOT_READ:P_ACT`、出力が基点と同じ | **読まない**（出力は基点と同じ。`NO_SUPPORTED_CLAUSE`）。**診断だけが変わる**: `PLACEMENT_PARTICLE_NOT_IN_FRAME:P_ACT:で`。同じテストの P_EXIST（眠る）・割れた述語の部分は成り立つ | 入口の挙動は凍結どおり。理由の文字列だけが違う | P_ACT は v2 の読む型になったが、で の行（place）は表に無い |
| 5 | `tests/test_semantic_read_w3b2.py::test_the_new_data_rows_are_read_and_refused_as_registered_and_judged_correct_when_read` | `w3b2_frame`・`w3b2_multiple` の 11 行（FRAME-063・064・065・066・070・071・073・074・075、MULTIPLE-060・061）が `entry_expect: abstain`・`w3b2_expect: PLACEMENT_FRAME_NOT_READ:*` | **11 行とも棄権のまま**（`entry_expect: abstain` どおり。誤読ではない: 判定 `abstain`）。診断だけが変わる: 10 行が `PLACEMENT_PARTICLE_NOT_IN_FRAME:<型>:で`（063・064・065・066・MULTIPLE-060・061 が P_ACT、070・071 が P_EMOTION、074・075 が P_CREATE）、073（姉が校舎で窓を拭いた。）だけ `PLACEMENT_MULTIPLE:を:窓` | 11 行とも `abstain`（凍結した `entry_expect` と一致。理由 `w3b2_expect` だけが不一致） | 第 2 ラウンドでは「10 行が読める」だった。で の行を外したので読まなくなった |

要点: 4 と 5 は、第 2 ラウンドまでは「読む側に変わった」衝突だったが、第 3 ラウンドでは **入口の出力は凍結した期待どおり（棄権）で、理由の文字列だけが `FRAME_NOT_READ:<型>` から v2 の理由に変わる** 衝突になった。1〜3 だけが「読む」に変わる（P_ACT の へ/goal の 3 行。`correct`）。

## 監査役が統合時に当てる差分 `proposed_test_changes.diff`

名前は変えず、期待を弱めない案。第 2 ラウンドまでの版（4 で「兄が校庭で遊んだ。」を P_ACT として **読む** ことを要求していた）は、第 3 ラウンドでは誤りになったので **書き直した**（前の版は `r3/proposed_test_changes.diff.before_r3`）:

1. `test_semantic_read_w3b1.py`: 3 行（U-090〜092）は「読む・`correct`」を要求する（`W3B4_NOW_READ`）。前と同じ。
2. `test_semantic_read_w3b2.py::test_u3_does_not_read_when_…`: 期待の理由だけを `PLACEMENT_PARTICLE_NOT_IN_FRAME:P_ACT:で` に替える（`new == base and not new['readable']` はそのまま）。**「P_ACT として読む」の検査は消した**。
3. `test_semantic_read_w3b2.py::test_the_new_data_rows_…`: 11 行の観測を **行ごとに固定** する（`W3B4_REASON`: 入口は棄権・判定 `abstain`・`w3b2` は 10 行が `PLACEMENT_PARTICLE_NOT_IN_FRAME:<型>:で`、073 が `PLACEMENT_MULTIPLE:を:窓`）。「読めるなら correct」の緩い許しは無い。

差は `patch -p1` で当たる（`rsync -a $T/ <写し>/`（`.git` 込み）→ `cd <写し> && patch -p1 < artifacts/w3-b4/proposed_test_changes.diff` → `PYTHONPATH=<写し> pytest -q -p no:cacheprovider tests/test_semantic_read_w3b1.py tests/test_semantic_read_w3b2.py tests/test_semantic_read_w3b4.py`: **770 件すべて成功**。出力 `artifacts/w3-b4/r3/proposed_diff_check.txt`）。
