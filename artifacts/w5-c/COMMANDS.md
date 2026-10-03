# W5-c: 流したコマンド（順に）

記号（各 Bash 呼び出しの先頭で定義し直した）:

```bash
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-c-S
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
A=$W/artifacts/w5-c
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W5c-impl
```

Python は常に `cd $W && env PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 $PY ...`、pytest は `-p no:cacheprovider --basetemp=$S/bt_<名前>` 付き。

## S0 環境と基線
1. `mkdir -p $A/scripts $S`、`uptime`（5.36）。
2. 索引: `python -m verantyx.cli index search "確認 id 宛先"`・`"出典 origin 不明"`・`"ソブリン 台帳 確認"` → `$A/index_search.txt`（3 件とも `UNKNOWN_NOT_FOUND`）。
3. 隔離: `python -c "import sys, verantyx.cli, verantyx.basis_policy, verantyx.sovereign, verantyx.ability_corpus; print(sorted(... not startswith('$W/')))"` → `$A/isolation.txt`（`[]`）。
4. dev の写し: `git -C $W archive 6d20016 | tar -x -C $S/dev`。
5. 攻撃テストの基点: `pytest -q -rf attacks/W6-a/test_attack_basis_policy.py` → `$A/attack_before.txt`（`25 failed, 8 passed`）。
6. 採点器の見本の前: `cd $S/dev && python -m tools.bank_score --bank B2 --items tests/bank_score/fixtures/B2/items.jsonl --tree $S/dev --out $S/bs_B2_before` → `$A/bs_B2_before.txt`（rc 0。over_abstain=17 correct_abstain=6 unreachable=2 wrong=0）。

## S1 攻撃テストの取り込み
7. 先頭に出典の 1 行を足して `tests/attack/test_attack_basis_policy.py` に写した。`tail -n +2 ... | shasum -a 256` = `3b355b5d…e2f3`（`$A/n1_attack_copy_sha.txt`）。写しを実装前に流して `25 failed, 8 passed`。

## S2 事前登録（テストより前）
8. `docs/BASIS_POLICY.md` の `<!-- prereg:end -->` の直後に prereg-w5c 節を挿入（登録日時 2026-10-03 19:27:14 +0900。`date` の実出力をスクリプトで埋めた）。`sed -n '/prereg-w5c:begin/,/prereg-w5c:end/p'` と `date` → `$A/prereg.txt`。
9. `pytest tests/test_basis_policy_table.py` → 35 passed（基点と同数）。`git diff 6d20016 -- docs/BASIS_POLICY.md | grep -cE '^-[^-]'` → 0。

## S3 新しいテストを書いて凍結
10. `tests/test_basis_policy_w5c.py` を書き、`shasum -a 256 ... > $A/frozen_tests.sha256; date >> ...`（19:30:01）。
11. 実装前に流した: `pytest tests/test_basis_policy_w5c.py` → `$A/w5c_tests_before.txt`（`288 failed, 7 passed`）。通った 7 件: `$A/w5c_tests_before_passed.txt`。

## S4〜S6 実装
12. `verantyx/basis_policy.py`（A1: 分類・`decide`・出力・版。A2: id・`_SovereignView`・`_payload`・`_confirm_block`・`_settle_confirmation`）、`verantyx/sovereign.py`（`basis_confirmation_destination`・`basis_confirmation_store_ids`・`append_basis_confirmation` の `destination` 検査）を編集。
13. 段階ごとの確認（出力は最終の実行で `$A/` に保存）: `-k "n1_ or w5c_"` 269 passed → 既存 5 本 1221 passed → ソブリン 178 passed → `-k "mouth or readers"`（1 件落ちたので E2 で直して通した）→ w5c 全部＋既存 5 本 1516 passed → 攻撃テスト 33 passed。
14. `git diff 6d20016 -- verantyx/ | grep -E '^\+' | grep -nE '窓|光った|first|second|owner-|730bf04d'` → 初回は英語のコメント 4 行に当たったので語を言い換えて空にした（`$A/check_hardcode.txt`）。

## S7 入口の前後比較
15. `python -m tools.bank_score --bank B2 ... --tree $W --out $S/bs_B2_after` → `$A/bs_B2_after.txt`（同じ数）。
16. `python -m tools.bank_score.compare $S/bs_B2_before $S/bs_B2_after` → `$A/bs_B2_compare.txt`（rc 1: 24 件がバイト不一致）。原因を `scripts/b2_semantic_compare.py`（時計と W5-c の追加キーを除いて比較）で確かめた → `$A/bs_B2_semantic_compare.txt`（差 0）。
17. `grep -rn --include='*.py' "family" verantyx/evidence_library.py verantyx/round3.py verantyx/semantic_retrieve.py` → `$A/unmarked_family_sites.txt`。系列名のリテラルを書く箇所: `scripts/families_literal_sites.py` → `$A/families_literal_sites.txt`（10 件）。
18. 社交の返事の挙動の差: `scripts/round3_social_frame_probe.py` を基点の写しと今の木で流した → `$A/round3_social_frame_probe.txt`。
19. 入口の実演: `scripts/cli_demo.py $W $S/demo_run1` → `$A/cli_demo.txt`。

## S8 W5-a の 3 文
20. `git -C $W archive 2732274^ | tar -x -C $S/pre_w5a`。`scripts/w5a_k64_three.py` を両方の木で流した → `$A/w5a_k64_three.txt`。`pytest attacks/W5-a/test_attack_w5a_wave2_r4.py` → `$A/w5a_r4_attack.txt`（`1 failed`）。`git diff 6d20016 --stat -- verantyx/semantic_read.py verantyx/semantic_reader.py` は空。
21. `docs/READING_SOUNDNESS.md` K64 の損失の段落の直後に 1 段落を追記（追加 1 行・削除 0）。

## S9 受入基準の最終実行・全体テスト・報告
22. N1: `pytest tests/attack/test_attack_basis_policy.py` → `$A/n1_attack_after.txt`（33 passed）。`-k "n1_"` → `$A/n1_tests_after.txt`（197 passed）。N2: `-k "n2_"` → `$A/n2_tests_after.txt`（26 passed）。w5c 全部 → `$A/w5c_tests_after.txt`（295 passed）。
23. N3: 既存 5 本 → `$A/n3_existing_after.txt`（1221 passed）、`git diff --stat 6d20016 -- <5 本>` → `$A/n3_existing_diffstat.txt`（0 バイト）、ソブリン 7 本 → `$A/n3_sovereign_after.txt`（178 passed）。
24. 隔離の取り直し → `$A/isolation_after.txt`（`[]`）。
25. N4: 全体テスト（`uptime` の 1 分平均 8.21 だったので 5 分待ってから、バックグラウンドで）→ `$A/after_pytest.txt`、`$A/after_failures.txt`、`$A/new_failures.txt`、`$A/fixed_failures.txt`（詳細は報告）。
26. 範囲: `git status --short --untracked-files=all` → `$A/status_end.txt`。

## 第 2 ラウンド（レビュー r1 の M1・M2 と任意 1・2 への対応。製品コード・テストは変えていない）
27. M1: `grep -c "verdict=UNKNOWN_ORIGIN_SOURCE" $A/cli_demo.txt` → 3。`docs/BASIS_POLICY.md` §9 の「入口の実演」の行を「3 通りのフラグ（無し・`--human-present`・`--human-present --show-generated-reference`）」に直した（案 (a)）。
28. M2: `scripts/greeting_entrances.py $S/dev $W $S/greet_r2`（子プロセスは採点器と同じ環境: HOME と VERA_CORPUS_ROOT を空の一時、VERA_P4_INDEX・VERA_SOVEREIGN_* なし）→ `$A/greeting_entrances.txt`。挨拶 4 文 × legacy・`--mode round5` × 基点と今 = 8 件すべて、`basis_policy` 注記の新しい鍵を除いて同じ。`Vera()` 直の `ask` は両方の木で `_social_frame` の出力を返し、方針は掛からない。`docs/BASIS_POLICY.md` §9・§10 F1・§11 の 7 を測ったことと読んだことに分けて直した。
29. 任意 1: `scripts/j5_refused_probe.py $S/j5_r2` → `$A/j5_refused_probe.txt`。§11 に 10・11 を追記（任意 2 を含む）。
30. 第 2 ラウンドの再実行: N1・N2・N3・ソブリン 7 本を `$S/r2_accept.sh`（各 pytest をそのままの引数で）で流し直し、`$A/n1_attack_after.txt` `n1_tests_after.txt` `n2_tests_after.txt` `w5c_tests_after.txt` `n3_existing_after.txt` `n3_sovereign_after.txt` を上書き。N4 の全体テストは `$S/r2_full.sh`（バックグラウンド。`uptime` 1 分平均 6.99）で `$A/after_pytest.txt` ほかを上書き。

## 第 3 ラウンド（W5-c3。監査役の判断 2026-10-03 20:40 の反映と、第 2 ラウンドの M1・M2）
以降 `E="env -u VERA_P4_INDEX -u VERA_SOVEREIGN_ROOT -u VERA_SOVEREIGN_STORE PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1"`、pytest は `-p no:cacheprovider --basetemp=$S/bt_<名前>`。シェルのスクリプトは `$S`（scratchpad の `W5c-impl3`）に置いて bash で流した。
31. S0: `git status --porcelain --untracked-files=all --ignored`（自分の出力ファイルを除く）→ `r3_status_start.txt`（sha1 `99ed76e7…53c8`）。`python -m verantyx.cli index search "出典 origin 利用者の文書"` → `index_search.txt` に追記。隔離 → `r3_isolation.txt`（`[]`）。開始時の 7 ファイル（table・w5c・entry・confirm・form・conductor・`test_one_request_goal_route`）→ `r3_start_tests.txt`（1529 passed）。
32. S1: `docs/BASIS_POLICY.md` の `<!-- prereg-w5c:end -->` の直後に prereg-w5c-r3 節を挿入（登録 21:07:31）。`sed -n '/prereg-w5c-r3:begin/,/prereg-w5c-r3:end/p'` と `date` → `r3_prereg.txt`。`pytest table w5c` 330 passed、`git diff 6d20016 -- docs/BASIS_POLICY.md | grep -E '^-[^-]'` 0 行、prereg 節の sha1 `1e948526…ab66`。
33. S2: `tests/test_basis_policy_w5c_r3.py` を書き、`shasum -a 256 … | sed 's/^/EXTENDED /' >> frozen_tests.sha256` ＋ `date`（21:09:48）。実装前に流した → `r3_tests_before.txt`（128 failed, 10 passed）、通った 10 件 → `r3_tests_before_passed.txt`（`-rp`）。
34. S3: `$S/dumpfuncs.py`（ast で関数の全文を抜き出す）→ `r3_revised_tests_before.txt`（12 関数）・4 ファイルの `BEFORE` sha256 → `r3_revised_tests.sha256`。`$S/revise.py` で 7＋5 関数を改訂 → `r3_revised_tests_after.txt`・`AFTER` sha256・`frozen_tests.sha256` に `AMENDED`（21:10:55）。改訂後の 4 ファイルを実装前に流した → `r3_revised_before_impl.txt`（6 failed, 1439 passed）。`git diff 6d20016 --stat -- confirm conductor goal_route` 空。
35. S4: `$S/impl.py` で `verantyx/basis_policy.py` を編集（`CLASSIFY_VERSION = 3`・`_class_of(src, user_documents)`・`classify_sources(..., user_documents)`・`_unknown_origin_sources(sources, user_documents)`・`_n_unknown`・`_withheld`/`_unknown_dict` の `n_unknown`・格上げの条件・`apply_to_ask` の `user_documents`）。`_family_of` を `.get` で書き直し。w5c_r3 の補助関数 `_family_key` を 1 つ直し `AMENDED` を足した（R3-E3）。確認 → `r3_tests_after.txt`（138）・`w5c_tests_after.txt`（295）・`n3_existing_after.txt`（1221）・`n1_attack_after.txt`（33）・`n3_sovereign_after.txt`（178）・`r3_request_goal_route.txt`（13）・`n1_tests_after.txt`（197）・`n2_tests_after.txt`（26）。
36. S5: `scripts/j5_refused_probe.py` を改訂して流した → `j5_refused_probe.txt`。`scripts/r3_record_probe.py` を基点（`git archive 6d20016` の写し）と今の木で流した → `r3_record_probe.txt`。採点器 B2・B3 を `$DEV` と `$W` で流した → `r3_bs_<B>_{before,after}.txt`、`scripts/bank_semantic_compare.py` → `r3_bs_<B>_compare.txt`。`scripts/r3_cli_demo.py`（基点と今）→ `r3_cli_demo.txt`。`scripts/r3_family_sites.py $W` → `r3_family_sites.txt`（36 か所）。`scripts/greeting_entrances.py $DEV $W $S/greet_r3` → `r3_greeting_entrances.txt`。
37. 自分の合成: `scripts/r3_synth.py $S/synth_run` → `r3_synth.txt`（218,880 組合せ）。代価の実測: 基点の写しに今の `basis_policy.py` などを重ね、(f) 規則 7 の 2 行を消したもの・(c) 格上げに claim の照合を足したものを別の写しで流した → `r3_variant_costs.txt`。
38. S7: 全体テスト（`uptime` 1 分平均 2.90）→ `after_pytest.txt`（最後の行 `116 failed, 10977 passed, 37 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 308.56s (0:05:08)`）。`comm` で `after_failures.txt`・`new_failures.txt`（2 行）・`fixed_failures.txt`（0 行）。M1: §9 の N4 の行の `321.81` を最後の行の値に書き換え。`pytest table w5c w5c_r3 entry` → `r3_docs_recheck.txt`（1554 passed）。`check_hardcode.txt`（初回は docstring の英語 "first match wins" 1 行に当たったので言い換えて空にした）・`status_end.txt`・`isolation_after.txt`（`[]`）。docstring の言い換えの後に S4 の 8 本を流し直し。全体テストはこの言い換えの前の実行（コメントだけの変更）。
