"""W5-d2 (round 2, after review r1 M2): write the <!-- w5d2-measured --> region of the five docs (after the w5d2-amended region, or after w5d2-prereg when a doc has none).
Every number is read at run time from a file under artifacts/w5-d/r2/ (the file name is written next to it). Idempotent: an existing region is replaced.
Usage: write_w5d2_measured.py <tree>    (run with the tree's python)"""
import json, re, subprocess, sys
W = sys.argv[1].rstrip('/')
A2 = W + '/artifacts/w5-d/r2'
def rd(name): return open(f'{A2}/{name}', encoding='utf-8').read()
def lastjson(name): return json.loads([l for l in rd(name).splitlines() if l.startswith('{')][-1])
def cls(d): c = d['cls']; return '%d / %d / %d / %d' % (c.get('CORRECT', 0), c.get('WRONG', 0), c.get('FALSE_NONE', 0), c.get('ABSTAINED', 0))
now = subprocess.run(['date', '+%F %T %z'], capture_output=True, text=True).stdout.strip()
g = {k: lastjson(k + '.json') for k in ('g2_185_place', 'g2_185_noplace', 'g2_185_place_r7', 'g2_185_noplace_r7', 'g2_attack120_r7')}
atk = g['g2_attack120_r7']
full = [l for l in rd('pytest_full.txt').strip().splitlines() if ' passed' in l][-1].strip()
after = len([l for l in rd('after_failures.txt').splitlines() if l])
newf = [l for l in rd('new_failures.txt').splitlines() if l]
fixed = len([l for l in rd('fixed_failures.txt').splitlines() if l])
g3 = {}
for name in ('g3_noplace_items', 'g3_noplace_items_mid', 'g3_noplace_items_reader_shaped', 'g3_noplace_items_mid_reader_shaped', 'g3_r7_items', 'g3_r7_items_mid'):
    g3[name] = re.search(r'misroutes: (\d+)', rd(name + '/summary.txt')).group(1)
sy = json.loads(rd('g3_synth_results/g3_synth_counts.json'))
g4 = json.loads(rd('g4_result.json'))['summary']
o1_same = rd('q1_observe_cmp_r2b.txt').count('same: base vs now')
k5 = rd('k5_check_r2b.txt').splitlines()[0]
reg = {l.split()[0] + ' ' + l.split()[1]: l.split()[2] for l in rd('docs_regions_start.txt').splitlines() if l.strip()}
entry_before = reg['OBSERVATION.md w3c2-entry']
entry_after = [l.split()[2] for l in rd('docs_regions_now.txt').splitlines() if l.startswith('OBSERVATION.md w3c2-entry')][0]
write_time = rd('recompute_write_time.txt').strip()
newf_ids = '、'.join(f'`{x}`' for x in newf) if newf else 'なし'

COMMON = f"""測定の時刻: {now}。出力はすべて `artifacts/w5-d/r2/`（ファイル名を添える）。中間職のレビュー r1（`review-impl/W5-d2/review.r1.md`）の M1〜M4（改訂したテストの前後の全文・測定の区間・失敗集合のファイル・報告）に応えてこの区間と `w5d2-amended` 区間を書いた。製品とテストのコードはレビューのあとに変えていない（`code_sha_r2b_start.txt` と `code_sha_r2b_end.txt` が同じ）。受入の測定はこのとき全部流し直した（`g1_rerun_r2b.txt`・`g2_rerun_r2b.txt`・`g3_rerun_r2b.txt`・`q1_observe_cmp_r2b.txt`・`g4_compare_r2b.txt`・`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`。出力は前の流しと byte 一致。違いが無かったことの確認なので前の流しのファイルも残す）。

**受入基準**（第 2 ラウンド）
- **G1**（`g1_rerun_r2b.txt`）: 攻撃の写し 36 本が `36 passed`、K の 72 関数（82 id）が全部通る（`102 passed`）、新しいテスト（第 1 ラウンドの 5 本＋第 2 ラウンドの追記）が `113 passed`。G1-b: 写しと原本の差は先頭行と改訂した関数・足したヘルパの中だけ（`g1b_hunks.txt`、`attack_copy_revisions.diff`。w5c の 2 本は原本と同一、`data/` も同一）。
- **G2**（`g2_185_*.json(l)`・`g2_attack120_r7.json(l)`・`g2_rerun_r2b.txt`）: `VERA_PLACEMENT` なしの 185 問は第 1 ラウンドの出力と byte 一致（place: 正答/誤答/FALSE_NONE/棄権 = {cls(g['g2_185_place'])}、noplace: {cls(g['g2_185_noplace'])}）。`VERA_PLACEMENT=r7`: place {cls(g['g2_185_place_r7'])}、noplace {cls(g['g2_185_noplace_r7'])}。誤答 0、型未確認の FILLED/TIE 0（4 通りとも `unchecked_fillers_in_FILLED_TIE` は {g['g2_185_place']['unchecked_fillers_in_FILLED_TIE']}・{g['g2_185_noplace']['unchecked_fillers_in_FILLED_TIE']}・{g['g2_185_place_r7']['unchecked_fillers_in_FILLED_TIE']}・{g['g2_185_noplace_r7']['unchecked_fillers_in_FILLED_TIE']}）。正答は減っていない（第 1 ラウンドと同じか、r7 で増える）。攻撃の 120 問（r7、116 問は正解なしで採点されない）: FILLED {atk['status'].get('FILLED', 0)}・TIE {atk['status'].get('TIE', 0)}、型未確認の FILLED/TIE {atk['unchecked_fillers_in_FILLED_TIE']}、`wrong` {len(atk['wrong'])} 件。A01（`EN08-01`）は `NO_TYPED_CANDIDATE`（`letter`・`note` は `TYPE_UNCHECKED`）で FILLED/TIE にならない（`g2_r7_notes.txt`）。中間職の凍結 64 問・56 問は実装役が開かない約束なので測っていない（中間職が測る）。
- **G3**（`g3_rerun_r2b.txt`・`g3_*`）: 経路づけの凍結 4 本（配置なし）の misroutes は {', '.join(g3[k] for k in list(g3)[:4])}、r7 の 2 本は {', '.join(g3[k] for k in list(g3)[4:])}。合成 `g3_synth`（入力の sha256 は `g3_synth_inputs_check.txt` で第 1 ラウンドの凍結と一致）: 配置なし misroutes {sy['noplace']['misroutes']}・普通名詞に振った数 {sy['noplace']['common_noun_routed']}、r7 misroutes {sy['r7']['misroutes']}（第 1 ラウンドと同じ 1 件。`委員会` が推定の GROUP_ORG で通る既知の穴）、基点 {sy['base']['misroutes']}（`g3_synth_results/g3_synth_counts.json`）。D2-2 の影響: r7 の 2 本の 118 件を、D2-2 の呼び出しを外した写しと単位ごとに比べて変化した件数は 0（`g3_r7_diff.txt`）。
- **G4**（`g4_result.json`・`g4_compare_r2b.txt`）: 入力の sha256 と `summary` が第 1 ラウンドと同じ（自己申告の文書 {g4['self_reported_cases']} 件で `ANSWER` {g4['self_reported_ANSWER']}、文面違いの確認記録 {g4['record_variant_cases']} 件で `ANSWER` {g4['record_variant_ANSWER']}・旧文が返った {g4['record_variant_old_sentence_returned']}、対照は {g4['self_reported_controls_answered']}/{g4['self_reported_controls']} と {g4['record_controls_answered']}/{g4['record_controls']} で答える）。`verantyx/basis_policy.py` は第 2 ラウンドで変えていない（sha256 が `files_start.sha256` と同じ）。
- **G5**（`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`）: r7 は作り直していない。`verify` が run1・run2 とも `OK`、`content_sha256` は第 1 ラウンドと同じ。`coarse_place.py`・`tools/build_coarse_placement.py` は第 2 ラウンドで変えていない。K5 の写しが通り、{k5}、第 1 ラウンドの 13 語と同じ集合（`命じる` を含む）。
- **平叙文の観測**（`q1_observe_cmp_r2b.txt`）: `o1_bytes.py --child` の出力が、配置なしと `VERA_PLACEMENT=r7` の 2 通りとも基点と byte 一致（`same: base vs now` が {o1_same} 行。この流しは前の流しとも byte 一致）。
- **G7**（`pytest_full.txt`・`after_failures.txt`・`new_failures.txt`・`fixed_failures.txt`・`new_failures_explained.txt`）: 全体テストの最終行 `{full}`。失敗は一意に {after} 件、基線に無い失敗は {len(newf)} 件（{newf_ids}）、基線にあって今は通る失敗は {fixed} 件。基線に無い失敗の理由は `new_failures_explained.txt`（環境由来だけ）。K の id は失敗集合に 0 件。
"""

REPLACED_HEADER = """**第 2 ラウンドで置き換わった第 1 ラウンドの記述**（第 1 ラウンドの `w5d-*` 区間の中は 1 文字も変えていない。元の行は残し、この一覧が上書きする）"""

SPEC = {}

SPEC['OBSERVATION.md'] = f"""
**K1（質問の十字 15 件）の改訂**（裁定 B1。前後の全文は上の `w5d2-amended` 区間。`changed_functions_k1k2.txt`）: 既存 13 関数（`tests/test_question_cross_observe.py`）と攻撃の写し 2 関数（`tests/attack/w3c2/test_attack_w3c2_question_cross.py::test_tied_agent_witnesses_remain_a_tie`・`test_negative_question_does_not_match_affirmative_crosses`）。名前は変えていない。直し方は 3 種類: (1) 穴の充填物だけに direct の型を付けた配置の JSON（`write_placement`）、(2) `O.FilePlacement`（足したヘルパ `person_placement`・`PERSONS`）、(3) 子プロセスの CLI は `--placement` を引数に足した。穴の型と食い違う型は付けていない。攻撃の写しは `tmp_path` に `校長`・`先生` = PERSON の JSON を書いて渡した（`data/` は触っていない）。例外 1 件 `test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun` は主題が「配置なしで FILLED」で新しい契約と正反対なので、期待を新しい契約（配置なし → `NO_TYPED_CANDIDATE`・`excluded` の理由 `TYPE_UNCHECKED`・`hole_type_check` が `NOT_CHECKED/NO_PLACEMENT`）に改訂した（assert は 2 → 3 に増えた。名前は旧い契約のものなので関数の先頭に注記）。**配置なしの棄権を表すテスト**: この関数と、足した `tests/test_question_cross_w5d.py::test_w5d2_k1_the_same_question_with_and_without_a_placement`（同じ問いで配置あり = `TIE`、なし = `NO_TYPED_CANDIDATE`）。

**D2-7（`VERA_PLACEMENT` を質問の経路につなぐ）の門**（3 つとも通った。戻していない）:
1. r7 で 185 問の `WRONG` 0・型未確認の FILLED/TIE 0、攻撃 120 問でも型未確認 0 で A01 が FILLED/TIE にならない（`g2_185_*_r7.json`・`g2_attack120_r7.json`）。
2. `VERA_PLACEMENT` なしの 185 問の出力が第 1 ラウンドの `g2_185_{{place,noplace}}.jsonl` と byte 一致（`g2_rerun_r2b.txt`）。
3. 平叙文の観測（`o1_bytes.py --child`）が基点と byte 一致（配置なし・r7。`q1_observe_cmp_r2b.txt`）。
製品の変更は `observe.py` の `_observe_question` の中だけ（`git diff c875ed3 -- verantyx/observe.py`）。足したテスト（`tests/test_question_cross_w5d.py`、r7 が無ければ失敗する。skip にしない）: `test_w5d2_vera_placement_types_the_hole_filler_of_a_question`（`誰が生徒に地図を渡した？`: `先生` → FILLED・`先生`＋`校長` → TIE・`花子`〔MULTIPLE ANIMAL/PERSON〕→ `NO_TYPED_CANDIDATE`、`structure.placement` が `coarse-placement:` で始まる）・`test_w5d2_the_placement_file_wins_over_vera_placement`・`test_w5d2_an_empty_vera_placement_is_as_before_no_typed_candidate`・`test_w5d2_the_command_line_with_vera_placement_gives_the_same_bytes_for_two_hash_seeds`。

**申し送りとして数えたもの**（門にしない。`g2_r7_notes.txt`）:
- FALSE_NONE の増分（r7）: 185 問の noplace で 4 → 8（Q094・Q130・Q131・Q136）、place で 4 → 6（Q094・Q136）。Q094 は `会社` が r7 で GROUP_ORG の direct（`どこ` の穴は PLACE → `HOLE_TYPE_DISAGREE`）、Q130・Q131 は `医者` が MULTIPLE（PERSON/PLACE）で which+N の `HOLE_TYPE_NOT_CHECKED`（以前からの規則で `TYPE_EXCLUDED_ALL` に数えられる）、Q136 は `X` が r7 で INFO_LANGUAGE の direct。どれも誤答（WRONG）ではない。
- TIE が FILLED に縮む形（既知の穴）: r7 で型未確認の充填物を横に持つ FILLED は攻撃 120 問では `JA02-01`（`花子は何を読んだ？` → FILLED [本]、`新聞`・`毎日本` は `TYPE_UNCHECKED`）の 1 件。185 問では 0。中間職のレビュー r1 の申し送り 1 は、第 1 ラウンドの凍結の反例を r7 で流すと同じ形（W01）と、読解器が文を読めないための欠け（W08・W18。`UNREAD_SENTENCES`）が出ると書いている（実装役は未測定）。

**B3（`recompute_q.py` の例の取り直し）**: `EXAMPLES` を 4 つ組 `(期待, 文書, 問い, 配置ファイル名 or None)` にし、`entry_block()` は配置ファイル名があれば `--placement tests/observe/question/<名>` を引数に足す。採用した例: `FILLED`（`QD02`・`どの人が客に切符を渡した？`・`placement_q.json`。凍結の Q037）、`TIE`（`QD01`・`誰が生徒に地図を渡した？`・`placement_q.json`。`先生`・`校長` が PERSON の direct）、`NO_ATTESTED_CELL`（`QD01`・`誰が生徒に手紙を送った？`・配置なし。今のまま）。`QD05` の `母は台所で何を作った？` は `料理` が `placement_q.json` に無く `NO_TYPED_CANDIDATE` になるので使っていない。凍結データ（`placement_q.json`・`questions.jsonl`）は変えていない。`--write` は 1 回だけ（`recompute_write_time.txt`）、`--check` は exit 0（`doc_checks.txt`）。前後の全文（`EXAMPLES`・`entry_block`）は上の `w5d2-amended` 区間、`recompute_q.py` の前は `recompute_q_before.py`。

**`w3c2-entry` 区間の変更記録**（区間の規則の本文・`w3c2-measured` 区間は変えていない）: {write_time}（`recompute_q.py --write` 実行時）。区間の sha256（内側のテキスト）: 前 `{entry_before}`、後 `{entry_after}`。理由: 配置を渡さない旧い例（`QD05` の FILLED・`QD01` の TIE）は、W5-d の規則（型を確かめられない充填物は候補にしない）では `NO_TYPED_CANDIDATE` になり、`--check` が `AssertionError: ('FILLED', 'NO_TYPED_CANDIDATE')` で落ちた（第 1 ラウンドの `doc_checks.txt` の追加の帰結）。例は測定の出力なので、配置を与えた例に取り直した（裁定 B3）。`w3c2-measured` 区間の sha256 は前後で同じ（`docs_regions_end.txt`）。

{REPLACED_HEADER}
- 「Q-J4 言語・配置: …質問の観測は `VERA_PLACEMENT` を読まない」→ 第 2 ラウンドで読む。`--placement` が無く `VERA_PLACEMENT` があるときは、読解器・事象の十字と同じ `event_cross.default_lookup()` の lookup を使う（`--placement` や呼び手が渡した lookup があればそれが勝つ。`VERA_PLACEMENT` が空・未設定なら今までどおり）。
- 「K1 は宣言した衝突（15 件）」→ 裁定 B1 で改訂が許可され、上のとおり改訂した（`k_ids.txt` の 82 id は全部通る）。
- 「K1 の追加の帰結: `recompute_q.py --check` が落ちる」→ 裁定 B3 で例を取り直し、`--check` は exit 0。
- 第 1 ラウンドの測定の節にある、質問の観測の数（配置なし 185 問）は今も有効（byte 一致）。`VERA_PLACEMENT=r7` の数はこの区間が初出。

**既知の穴**: (a) TIE が FILLED に縮む（上）。(b) r7 では FALSE_NONE が増える（上。r7 の型による `TYPE_EXCLUDED_ALL`）。(c) 攻撃 120 問の 116 問には正解が無いので、r7 の FILLED 29・TIE 5 は型こそ全部 AGREE だが正しさは採点されていない（監査役の G6 で見る）。
"""

SPEC['ROUTING_FROM_TEXT.md'] = f"""
**K2（自由文→記録 52 件）の改訂**（裁定 B1。前後の全文は上の `w5d2-amended` 区間。`changed_functions_k1k2.txt`）: 既存 51 件と攻撃の写し R2 の 1 件（K の id の内訳は `k_ids.txt`: `test_routing_from_text.py` 36・`_w5b` 12・`_regress` 2・`_entry` 1・攻撃の写し 1）。名前は変えていない。直し方: テストの中だけの `FakePlacement`（固定の名前は `UNPLACED`、列挙した普通名詞は direct の型。製品には入っていない: `git diff c875ed3 -- verantyx/` に `fake` の語は無い）を `tests/test_routing_from_text.py` に 1 つ足し、`explain_lines(..., lookup=None)` と、それを経由する補助関数（`two_rules_and_a_precedence`・`one_unit_status`・`run`・`statuses`）に既定 None の `lookup` 引数を足し、module スコープの fixture `std` は変えずに `std_placed`（同じ STD を `FakePlacement()` で）を足して、K2 の関数だけを切り替えた。

**配置なしそのものが主題の改訂 3 件**（期待を新しい契約「配置なし → 棄権」に）: `test_routing_from_text_w5b.py::test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden`（単位は `NAME_UNRESOLVED`・`NAME_UNVERIFIED:ソラ:NO_PLACEMENT`）、`test_routing_from_text_entry.py::test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader`（本物の読解器・配置なしの子プロセスの今の出力に合わせた。`entry()` は子プロセスの env を `dict(os.environ)` から作るので `VERA_PLACEMENT` を外す 1 行を足した。期待の弱体化ではなく、漏れを防ぐため）、`test_routing_from_text.py::test_output_keys_order_and_basis_kinds`（主題は鍵の並びなので `std_placed` に切り替え、`reading.lookup == "test-fake-placement/1"`）。配置なしの棄権を表すテスト（足した）: `tests/test_routing_from_text_w5d.py::test_w5d2_k2_the_standard_explanation_with_and_without_a_placement`（STD を偽の配置ありで流すと第 1 ラウンド前と同じ判断、配置なしは `INCOMPLETE_READING`・単位に `NAME_UNVERIFIED:…:NO_PLACEMENT`）と `test_w5d2_without_a_placement_a_part_of_a_parallel_name_is_unverified_as_before`。攻撃の写し R2（`test_yappari_sonomama_does_not_turn_an_addendum_into_replacement`）は `lookup=` に全語 UNPLACED の偽の配置（`_AllUnplaced`）を渡し、期待を R-J2 の結果 `{{"statuses": ["MAPPED", "AMBIGUOUS_RELATION"], "auto_resolved": 0, "superseded_by": [None], "additions_kept": 0}}` に改訂した（攻撃の偽 reader は断片「そのまま」も肯定の「任せる」に読むので未確定。主旨＝置き換えにならない、は保たれる）。

**D2-2 並列の名前の部分（製品の変更。裁定の申し送り「並列の名前の過剰棄権は直さず既知の穴」からの逸脱）**: 理由と実測。(1) 裁定の K2 の形（偽の `PlacementLookup` の注入）・G7・「期待を弱めない」は、並列の部分に配置の答えが無いと同時には満たせない。偽の配置（全語 UNPLACED）を入れても、標準の説明文 STD の `ハルとセキは同じ会社だ。` で配置の答えが充填物 `ハルとセキ` 全体にしか付かず、部分 `ハル`・`セキ` に答えが無いので R-J1 が `NAME_UNVERIFIED:ハル:NO_PLACEMENT` で止め、関門が `INCOMPLETE_READING` で全部を棄権にする。中間職の試作の実測でこの 11 件が通らない（`test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop`・`test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous`・`test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record`・`test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called`・`test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions`・`test_router_call_passes_used_agents_only_no_chooser_and_the_first_names`・`test_router_reasons_are_written_through_from_the_routers_types`・`test_router_unknown_task_names_abstain_with_their_own_type`・`test_constraint_prohibition_veto_does_not_try_the_next_agent`・`test_constraint_human_and_wait_scopes_and_residual_and_conflict`・`test_constraint_independence_veto_for_two_other_roles`。出典: `plan_evidence/proto_numbers.txt` §1）。実装役も同じ測定をした: D2-2 の呼び出し 1 行だけを外した写しで K2 のテスト一式を流すと 12 failed（上の 11 件と、`std_placed` に切り替えた `test_output_keys_order_and_basis_kinds`。`d22_without_the_call.txt`、`scripts/run_k2_without_d22.py`）、D2-2 を入れた木では 0 件。期待を書き換えれば「弱体化」、失敗のままなら G7 に反する。(2) 直し方は R-J1 の同じ規則を部分の名前それぞれの配置の答えに当てるだけ（新しい規則は足さない）: `read_units` で `lookup is None` なら最初に 1 回 `event_cross.default_lookup()` に解決し、`UnitReading.part_places`（既定値つきの新しい欄）に、日本語の `CROSSED` の単位の各充填物を `_split_parallel` で切った群を同じ lookup に問い、契約に合う答え（`invariant_problems()` が空）だけ `setdefault` で入れ、`_places_of` は充填物自身の答えを先にして `part_places` を後に足す。日本語だけ（英語の並列は問わない）。(3) 実測: 偽の配置なしで、routing の関係テスト一式＋攻撃の写し R2 の失敗集合は K2 の 52 id と完全に同じ（差 0。`k2_after_product_raw.txt`＝製品の変更だけを入れて、偽の配置を入れる前のテストを流した）＝この変更は新しい失敗を作らない。偽の配置ありで K2 の関数は全部通る（`g1_rerun_r2b.txt` の K の `102 passed`）。G3: 配置なし 4 本・r7 2 本とも misroutes 0、r7 の 2 本は D2-2 を外した写しと単位ごとに比べて 118 件中 0 件が変化（`g3_rerun_r2b.txt`・`g3_r7_diff.txt`）。足したテスト（`tests/test_routing_from_text_w5d.py`）: `test_w5d2_a_parallel_name_is_routed_when_the_placement_answers_for_each_part`（全語 UNPLACED で `ハルとセキは同じ会社だ。` が MAPPED・INDEPENDENCE(same)）、`test_w5d2_a_part_of_a_parallel_name_that_the_placement_types_as_a_common_noun_stops_the_unit`（部分の 1 つが direct の GROUP_ORG → `COMMON_NOUN_SUBJECT`）、`test_w5d2_without_a_placement_a_part_of_a_parallel_name_is_unverified_as_before`、`test_w5d2_an_english_parallel_name_is_not_asked_part_by_part`（spy の lookup で英語の部分が問われない）、`test_w5d2_the_parts_that_are_asked_are_exactly_the_groups_of_the_parallel_split`。

{REPLACED_HEADER}
- 「既知の穴 1: 並列の名前は配置があっても止まる」→ 第 2 ラウンドで、配置があれば部分の名前も配置の答えで引く（上）。配置が部分を UNPLACED と答えれば名前として通る（単独の名前と同じ扱い。下の穴 3）。配置が無ければ今までどおり `NAME_UNVERIFIED`。
- 「K2 は宣言した衝突」→ 裁定 B1 で改訂が許可され、上のとおり改訂した。

**既知の穴**（直していない。次の攻撃と W3-b3 のあとで見る）:
1. r7 でも、推定・UNPLACED の普通名詞の主語が名前として通る（第 1 ラウンドの探りで 60 文中 8 文。合成 `g3_synth` の r7 で `委員会` が 1 件。`g3_synth_results/g3_synth_counts.json`）。
2. R2 の「維持」（`やっぱりそのまま`）は、本物の読解器ではほぼ到達しない（断片を節に読めず `AMBIGUOUS_RELATION` に倒れる。到達するのは断片を読む偽 reader のテストだけ。第 1 ラウンドのまま）。
3. D2-2 は「部分の名前それぞれの配置の答え」を見るだけで、配置が部分を UNPLACED と答えれば名前として通る。
4. 並列の部分を問う `lookup.lookup(名)` は `_read_one` の `try` の外にあり、部分を問われたときだけ例外を投げる lookup では `explain` 全体が例外で止まる（中間職のレビュー r1 の任意の改善 1。本番の `StubLookup`・`CoarseLookup` は例外を投げない作りなので実害は今のところ無い。レビューが製品・テストの変更を範囲外としたので直していない）。
5. r7 の説明文で `ハル` は MULTIPLE（ANIMAL・GROUP_ORG・PERSON）の direct なので `COMMON_NOUN_SUBJECT` で止まる（中間職のレビュー r1 の申し送り 2）。D2-2 は偽の配置では効くが、本番の r7 で `ハル` を名前として通さない（実装役も `r7_lookups.txt` で確かめた: `ハル` は MULTIPLE・direct・ANIMAL/GROUP_ORG/PERSON、`セキ` は UNPLACED、`チーム` は DECIDED・direct・GROUP_ORG、`委員会` は DECIDED・estimated・GROUP_ORG）。安全側の過剰棄権で、G3 の r7 で「正しく振った 0」はこれと読解器による。
"""

SPEC['BASIS_POLICY.md'] = f"""
**K3（存在しない文書を人の出典にする 10 件）の改訂**（裁定 B1。前後の全文は上の `w5d2-amended` 区間。`changed_functions_k3k4k5.txt`）: `tests/test_basis_policy_form.py` の 3 関数と `tests/test_basis_policy_w5c_r3.py` の 4 関数（パラメタ化を含めて 10 id）。期待の値は変えていない。「存在しない `memo.txt` を人の出典にする」こと自体が退役した振る舞い（A1: 出典の本文が実際に渡した文書の中にあること）で、期待を `unknown_origin` に変えると攻撃 A1 と同じテストになって主題「ユーザーが渡した文書の答えは保たれる」が消えるので、渡した文書を実在させた: 各モジュールに足したヘルパ `_hand_over_memo(tmp_path, monkeypatch, *texts)` が `tmp_path/memo.txt` に出典の `text` を 1 行ずつ書いて `monkeypatch.chdir(tmp_path)` する（conftest の autouse にはしていない。木の中に `memo.txt` は作らない）。memo の中身は出典の `text` だけで、余計な文は入れていない。

**K4（別の文の記録で格上げ 4 件）の改訂**: `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer`（パラメタ 4 id）の補助関数 `_sovereign_with_yes` に、既定 `OTHER_CLAIM` の `claim` 引数を足し、関数の中で今の生成文を claim にした（`artifacts/w5-d/k4_proposal.diff` を `patch -p0` でそのまま当てた。`k4_patch_output.txt`）。D1 の規則（確認済みの文と現在の生成文が違えば格上げしない）の下で「確認記録が今の文を確かめたもの」になる。

**D1（B2）の追認**: 監査役は D1 の比較を正規化しない完全一致と追認した（2026-10-04 00:05。上の `w5d2-prereg` 区間）。チケットの文言「NFKC 正規化後の完全一致」は撤回。理由: 攻撃 `tests/attack/test_attack_w5c_confirmation_text_binding.py` の `[nfkc]` の反例（`コードはＡＢＣです。` の確認で `コードはABCです。` を格上げすると、表記が違う＝別の文を人が確かめたことになる）。安全側に倒す。コードは変えていない（`basis_policy.py` の sha256 は第 1 ラウンドの終わりと同じ）。確かめ: W5-c の写し 2 本（`[nfkc]` を含む）が通る（`g1_rerun_r2b.txt`）、`tests/test_basis_policy_w5d.py` の `nfkc` の変種が格上げしない（既存）。

**G4**（`g4_result.json`・`g4_compare_r2b.txt`）: 入力の sha256 と `summary` が第 1 ラウンドと同じ。自己申告の文書の `ANSWER` {g4['self_reported_ANSWER']}（{g4['self_reported_cases']} 件）、文面違いの確認記録の `ANSWER` {g4['record_variant_ANSWER']}（{g4['record_variant_cases']} 件、旧文が返った {g4['record_variant_old_sentence_returned']}）。

{REPLACED_HEADER}
- 「B-J2 / チケットの文言: D1 は NFKC 正規化後の完全一致」と、第 1 ラウンドの既知の穴 4 の書きぶり「チケットの文言より狭い」→ 裁定 B2 でチケットの文言のほうが撤回された（正規化しない完全一致が正）。
- 「K3・K4 は宣言した衝突」→ 裁定 B1 で改訂が許可され、上のとおり改訂した。

**既知の穴**: 確認済みの文と現在の生成文が表記だけ違うとき（空白・句読点・NFKC の違い）は格上げされず、再確認を求める（安全側の過剰棄権）。
"""

SPEC['COARSE_PLACEMENT.md'] = f"""
**K5（攻撃の写し 1 件）の改訂**（裁定 B1。前後の全文は上の `w5d2-amended` 区間。`changed_functions_k3k4k5.txt`）: `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades`。48 語の導出・2 回の問い合わせのバイト一致・`state`/`origin`/`generated_frame`/`namespace`/`top` の条件・`generated_type_differs`・`arm_top_differs` は変えていない。`frame_status` は `CONFIRMED` か `NOT_CONFIRMED`: `CONFIRMED` の語は今までどおり `frame_projection_differs`・`frame_conflicts` が空であること。`NOT_CONFIRMED` の語は `frame is None`・`frame_disagreement` が空でない辞書・その各助詞で `generated` と（どれかの腕の）`distribution` の型の集合が交わらないこと・`frame_unconfirmed` の鍵が無いこと（違えば `invariant_errors`）。数（13）は assert せず、出力 `r6_audit_summary.json` の `not_confirmed` に語の一覧を書いた。`assert len(words) == 48` は元のまま。この写しは実行のたびに隣に 3 ファイル（`r6_48_queries.jsonl`・`r6_audit_summary.json`・`state_probes.json`）を書く。最後の実行のものを残してある（sha256: `r6_48_queries.jsonl` 213856af…、`r6_audit_summary.json` 962492c2…、`state_probes.json` c27484e4…）。

**G5**（`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`）: r7 は作り直していない。`verify` が run1・run2 とも `OK`、`content_sha256` は `5c969d454b39d39ac0e394191b5e985b4e0a10099591bb7b12fcc559e7d77ff1`（第 1 ラウンドと同じ）。`{k5}`、第 1 ラウンドの `r6_query_after.txt` の 13 語と同じ集合。`NOT_CONFIRMED` の 13 語は `うたう`・`たたえる`・`みせる`・`交わす`・`命じる`・`問い合わせる`・`潜める`・`示せる`・`薦める`・`見せ合う`・`言い換える`・`訴える`・`謳う`。`coarse_place.py`・`tools/build_coarse_placement.py` は第 2 ラウンドで変えていない。

{REPLACED_HEADER}
- 「K5 は宣言した衝突（攻撃の写し 1 件）」→ 裁定 B1 で改訂が許可され、上のとおり改訂した。第 1 ラウンドの記述の `frame_status` は全部 `CONFIRMED` という不変条件は、`CONFIRMED` か `NOT_CONFIRMED` に置き換わった。
"""

SPEC['EVENT_CROSS.md'] = f"""
**質問の穴の型の確かめと `VERA_PLACEMENT`（第 2 ラウンド）**: 上の「穴の型による候補の判定」と W5-d の節の穴の型の確かめ（`observe._hole_type_check`）は、`--placement` が無いとき、読解器・事象の十字と同じ `event_cross.default_lookup()`（`VERA_PLACEMENT` の粗い配置。空・未設定なら配置なし）の lookup で充填物の `surface` を問い直して行う。`--placement` や呼び手が渡した lookup があればそれが勝つ。新しい規則は足していない（質問の観測の出力 `structure.placement` が実際に使った lookup の id になるだけ）。`event_cross.py` には触れていない。測定と門は `docs/OBSERVATION.md` の `w5d2-measured`。

**第 2 ラウンドで置き換わった記述**: 第 1 ラウンドの `OBSERVATION.md` の「Q-J4: 質問の観測は `VERA_PLACEMENT` を読まない」。
"""
SPEC['EVENT_CROSS.md'] = SPEC['EVENT_CROSS.md'] + "\n" + COMMON.split('**受入基準**')[0].strip() + "\n"

DOCS = ['OBSERVATION.md', 'EVENT_CROSS.md', 'ROUTING_FROM_TEXT.md', 'BASIS_POLICY.md', 'COARSE_PLACEMENT.md']
for d in DOCS:
    p = f'{W}/docs/{d}'
    text = open(p, encoding='utf-8').read()
    if d == 'EVENT_CROSS.md':
        body = '\n' + SPEC[d].strip() + '\n'
    else:
        body = '\n' + COMMON.strip() + '\n' + SPEC[d] + '**この文書の担当の測定は上のとおり。全体の受入と判断は `artifacts/w5-d/DECISIONS.md` の「第 2 ラウンド（W5-d2）」と `artifacts/w5-d/r2/`。**\n'
    pat = re.compile(r'(<!-- w5d2-measured:begin -->)(.*?)(<!-- w5d2-measured:end -->)', re.S)
    m = pat.search(text)
    if m:
        text = text[:m.start(2)] + body + text[m.end(2):]
    else:
        text = text.rstrip('\n') + '\n\n## W5-d 第 2 ラウンド（W5-d2）の測定\n<!-- w5d2-measured:begin -->' + body + '<!-- w5d2-measured:end -->\n'
    open(p, 'w', encoding='utf-8').write(text)
    print('wrote', d, len(body))
