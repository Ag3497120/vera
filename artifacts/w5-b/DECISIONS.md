# W5-b 判断記録（実装役 第 1 ラウンド）

指示書（`.claude/vera-audit/review-impl/W5-b/plan.md` §3）の D1〜D9 と、実装中に決めたこと。

## 指示書の判断（そのまま実施）

- **D1（C1）かな違いは別語**。`あざみ`・`アザミ` の `state` を揃える攻撃テスト `test_hiragana_katakana_variant_keeps_same_state` は取り込んだまま **落ちる**（宣言）。`spelling` で別表記の行を見せるだけで `state` `top` には効かせない。契約の試験は `test_contract_kana_distinct_*`。
- **D2（C2）** W4-m の外れ `test_tampered_export_cannot_be_attached` は直さず、消さず、skip しない。**落ちる**（宣言）。
- **D3（C3・C4）** チケットの挙げる挙動を実装し、矛盾する既存テスト 4 本（C3 の 3 本、C4 の 1 本）には触れず宣言する。C3: `test_relation_override_replaces_exactly_the_same_scope_and_counts_it`・`test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous`・`test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement`（`追記：` の標識なしの行が置き換わることを期待）。C4: `tests/test_conduct_ask_w2c2_view.py::test_markdown_and_jsonl_views_have_the_same_decisions_and_the_same_terms`（md と jsonl の差を `{...欠測の扱い...}` と固定）。
- **D4** W2-g2 の理由の名前は `LEDGER_INTEGRITY` のまま、`LEDGER_MISMATCH:<種類>` は手順の `detail` の型。取り込んだ攻撃テストが `ESCALATED:MAPPING_UNSETTLED/LEDGER_INTEGRITY` を、別の既存テストが `escalate_detail == "LEDGER_INTEGRITY"` を見ているため。
- **D5** W4-m: 書き込みの段の中で解析をやり直さない（重複は一意のトリガで止める）。release は 2 段のまま、RELEASE と同じトランザクションで残りを退役させる。
- **D6** W3-c: 座標の数に上限を設けていない。`measure.py --reobserve` の時間は変更前 約 4.46 秒、変更後 約 4.65 秒（2 倍を超えていない）。
- **D7** W2-c3 #1 は広い語句の経路だけ、属性語が取れないときは要求しない、名詞句が言及と重なるときは属性語なし。#2・#3 は `_builtin_protected_asked` の中だけを広げ、`ask` と新しい操作の語は足さない。
- **D8** W2-h2 A01 は限定詞（この木で効く）と配置（W3-b1 の後に効く）の 2 つの根拠。配置は `direct` だけを根拠にし、`estimated` は使わない。A02 の足す見出しは `追記` `追伸` `p.s.` `ps` `addendum`。
- **D9** `project_frame.py` は変えない（#4 は読む側 `conduct_ask._view_from_jsonl` で直る）。

## 既存物の索引（手順 0-1）

`python -m verantyx.cli index search` を 7 つの問い（指示書のもの）で引いた。7 つとも `UNKNOWN_NOT_FOUND`（`artifacts/w5-b/index_search.txt`）。似た既存物は出なかったので、この指示書との関係を書く行は無い。実際の既存物（`ChoiceLedger`・`conduct_map`・`sovereign`・`observe`・`routing_from_text`・`coarse_place`・`conduct_ask`）は指示書が名指ししたものを読んで使った。

## 実装中に決めたこと

1. **作業用ディレクトリ**: 監査役の指示どおり、自分用に `scratchpad/impl-r1/` を作った（dev の写し `dev/`、pytest の basetemp、試作は無い）。`scratchpad/W5b/` は中間職の試作の置き場で、既に在った。そこには書かず、試作のコード（`proto_*.diff`）は読んでいない。中間職の測定の道具は `scripts/` に次のとおり写した: `stress_w4m.py`（そのまま）、`q.py` → `coarse_probe_queries.py`（そのまま）。`kana_variant_effect.py`・`names_in_placement.py` は写していない（使っていない）。ほかの道具（`measure_coarse_w5b.py`・`count_time_head_counters.py`・`l4_merge_reobserve.py`・`routing_diff.py`・`routing_with_placement.py`）は自分で書いた。
2. **攻撃テストの変更前の記録**: 作業ツリーでは変更前の全体テスト（`before_pytest.txt`、115 件失敗）を流してから攻撃テストを取り込んだ。「変更前の 17 failed, 18 passed」は dev の写し（`$S/dev`）で、同じ 6 本（＋データ）を流した出力（`attack_before.txt`）。指示書の `attack_import_before_fix.txt` の名前では作っていない（同じ内容の dev の出力が `attack_before.txt`）。
3. **manifest の書き込みの順（W2-g2）**: `ChoiceLedger.append_manifested` が、ロックの中で「台帳へ 1 行 → manifest を一時ファイルから `os.replace`」の順に書く。台帳へ書いたあと manifest へ書く前に落ちると、その台帳は `ROW <seq>` で止まる（安全側）。manifest が読めない（json でない）ときは追記の前に拒否する（`ManifestUnreadable`）。`ChoiceLedger.append` は manifest に触れない。
4. **`LEDGER_INTEGRITY` の chain 失敗の detail**: 鎖の失敗（`line N kind`）の手順の `detail` は今までどおり空。`LEDGER_MISMATCH:` は manifest の食い違いのときだけ付ける。
5. **W3-c の A1（出所 id）**: 指示書は「出力に出所 id の列があれば辞書順」とも言うが、出力に出所 id の **列** は無い（`structure.placement` と `structure.neighbors` の 2 つの文字列だけ）。id を中身の正準形の sha256 にして直した（`docs/OBSERVATION.md` E26）。
6. **W3-c の A2**: 代表の十字は `min(座標の文字列)` が最小の升のもの。座標が同じなら同じ升なので 1 つに決まる（`sorted(...)[0]` の形は元のコードと同じ。勝者選びではなく表示のための代表）。`_levels` を `observe` から切り出して `reobserve` の完全性の検査も同じ関数を使う（台帳に依らないことは、`_levels` が `structure` と `viewpoint` と `lookup` `neighbors` だけを読むことを読んで確かめた）。
7. **W3-c の A3 で見る欄**: `docs/OBSERVATION.md` E29 の表。`decision` は `decided_cell` が文字列であること（必須）、すべての事件で `decided_cell` があれば文字列。`utterance` の `text` は必須とした（欄が無い発話は今まで黙って読み飛ばされていた。観測器が書く発話は必ず持つ）。
8. **W3-c の既存テストの名前の衝突**: `tests/test_observe_data.py` の 2 本（`test_o4_*`）は、ほかの観測のテストと同じ pytest の実行で集めると、モジュール名 `measure` の衝突で落ちる（dev の写しでも同じ。単独では通る）。`w3c_tests.txt` は 2 回に分けて流した。全体テストでは落ちない（`before_pytest.txt`・`after_pytest.txt`）。
9. **測定が追跡下のファイルを書き換えた**: `tests/observe/measure.py --reobserve` は `--workdir` を渡しても `artifacts/w3-c/index_small/pro.db` と `artifacts/w3-c/index_small_manifest.json`（追跡されたファイル）を作り直す。許可パス外なので、最後に `git checkout -- <その 2 ファイル>` で基点の内容に戻した。
10. **W4-m の promote の結果に足した欄**: `refused`、`counts.duplicate_promotion`、書き込みの段で止まったときの `analysed_candidates`（解析で決まった候補の数）。`CONSENT_CHANGED` の結果は `consent`（今の同意）と `consent_at_start` を持つ。
11. **W4-m: 構造の側のコミットの後に release が割り込んだとき**: back-link の追記が `RELEASED` の型つきの例外になり、`promote` の結果は `RELEASED` の dict になる（構造の側の行は書かれており、release の `RELEASE` の行と同じトランザクションまたはその前後で退役される。active は残らない）。結果に「構造の側へは書いた」を載せていない（既知の穴）。
12. **W2-h2 の `Unit.override` の意味**: 「行が上書きの印で始まった」のまま（既存テストが固定）。「実際に置き換えるか」は `extract` の `_replaces` が文ごとに決め、`UnitResult.override` と `Relation.override` に入れる。
13. **W2-h2: 標識の語の照合**: 英語は語全体の完全一致のみ（`replaced`・`replaces` は標識でない）。足す側に倒れ、2 人が候補なら同点で棄権する（安全側）。
14. **W2-c3 #4 の不変条件の id**: md の `I1` と jsonl の記録の id が違う。jsonl の記録に元の id を持つ欄が無く、`invariant I1` という主語の文字列から取り出すのは推測になるので揃えていない（`docs/CONDUCT_ASK.md` §11 の追記）。
15. **コードのコメントの語**: 製品コードの差分に攻撃文の語（`team`・`Luna`・`archive` など）を書かない約束（共通確認）に合わせ、コメントの例の語を別の語に替えた（差分の grep は 0 件）。
16. **（第 2 ラウンド）M1 依頼・丁寧形を「位置」で広げた**: 依頼の枠・使役の枠の主語と動詞の間に、冠詞・限定詞を除く語を 0〜2 個許す位置 `_BI_SLOT` を置いた（`kindly` `also` `mind` などの語を 1 つも書いていない）。冠詞・限定詞だけを除いたのは、その後ろが名詞句になるため（`Could you summarize the release plan?` を依頼にしない）。この位置は動詞の位置の語を限らないので、`Could you explain release notes?` のように保護された語が名詞の文も `HUMAN_APPROVAL_REQUIRED` に倒れる（上げる側の誤り。答えは出さない。`docs/CONDUCT_ASK.md` §11 に書いた）。`be able to` / `be willing to` は `can` と同じ構文として入れた。`ask` は入れない（既存テストの固定）。使役の動詞と保護された操作の動詞の -ing 形は同じ動詞の活用（`_BI_EN_OP` に新しい動詞は足していない）。
17. **（第 2 ラウンド）否定の依頼**（`Could you not delete …`）: 位置は否定の語も許すが、前の段が `QUESTION_UNREADABLE/NEGATED_QUESTION` で先に手を上げる。答えにならないことをテストで固定した。上げる側に倒す方針（レビュー M1 が許した側）。
18. **（第 2 ラウンド）日本語の依頼を構文 5 つに整理**: て形 ＋ 授受の動詞（`しておいて` を含む）、て形 ＋ `ください`、て形 ＋ `ほしい`、操作の名詞 ＋ 頼む動詞（`お願い|依頼|頼`）＋ 可能・疑問、て形だけ。名詞 ＋ 頼む動詞は、かなの活用の尾が続いて `か|でしょうか` で終わる形に限った（`削除依頼は誰に出しますか` のような手順の質問を依頼にしないため）。`て形 ＋ ほしい` の尾は `.*`（その文に手がかり `_PERM_CUE` か `_BI_REQUEST_CUE` があることが門）。保護された操作の語は足していない。`消す` は今も類に無い（既知の穴のまま）。
19. **（第 2 ラウンド）M2 属性語**: `what's` を `what is` と同じに読み、名詞句の終わりを助動詞に加えて前置詞（文法の閉じた類）にし、`how <形容詞> <助動詞>` の形容詞を属性語にした。日本語は `どの|どんな<語>` を足した。D7 の 3 つの限定（広い語句の経路だけ・言及と重なる名詞句は除く・取れなければ要求しない）は変えていない。前置詞で名詞句を切るので `what happens to …` の `happens` も属性語に取れ、記録の原文に無ければ上げる側に倒れる（広い語句の経路で対応づけが答えにしたときだけ）。
20. **（第 2 ラウンド）M3 `COORDS_DUPLICATED`**: 集合の比較の後に、渡された座標の数が集合の大きさと等しいことを要求する。理由の名前は `COORDS_EXTRA` を流用せず新しく置いた（「余分な経路」と「同じ経路の重なり」は別の型。分からないことと偽を混ぜない）。既存の理由の順・名前は変えていない。
21. **（第 2 ラウンド）任意の改善 1〜3**: (1) コメントの例の語を別の語に替えた（`archive` `report` `language` を製品の差分に書いていない）。(2) 許可の層に届かない文の理由（層の順序）を `docs/CONDUCT_ASK.md` §11 に追記。(3) `日分` `年ごと` `時間制` の意味の寄りを `docs/COARSE_PLACEMENT.md` §11.9.2 に追記。
22. **（第 3 ラウンド）M-A 既定の反転**: 広い語句の経路で対応づけが答えたとき、答えが立つのは (i) 属性語が読めて全根拠の原文にある、(ii) 構文で「語そのものを問う形」（Yes/No の選択肢で助動詞で始まる文、または `what|which|how` の直後が助動詞）と確かめられる、のどちらかだけ。読めない形は `FRAME_SILENT/TERM_IN_WIDER_PHRASE`、trace は `ATTRIBUTE_NOT_IN_RECORD:<語>`（読めて無かった）と `ATTRIBUTE_UNREAD`（読めなかった）で別の型。第 1・2 ラウンドの指示書 D7「取れなければ要求しない」は中間職が改めた（review.r2 M-A）。助動詞・前置詞・限定詞・接続詞・短縮の主語は文法の閉じた類で、属性や動詞の一覧は作っていない。
23. **（第 3 ラウンド）(ii) の助動詞で始まる文は Yes/No の選択肢のときだけ**: 凍結の既存試験（`Is the moon phase icon design in scope?` が答えになる）は (ii) を要るが、`Is the report archive in English?` のように選択肢が値の集合のとき、述語に別の属性が隠れる。選択肢が Yes/No でないときは (ii) にしない（`ATTRIBUTE_UNREAD`）。Yes/No の選択肢での同じ隠れ方は穴として残る（docs/CONDUCT_ASK.md §11）。
24. **（第 3 ラウンド）wh 名詞句が枠の語を含めば属性なし**: `Which confirmation channel setup should we go with` が答えになることを既存試験が固定しているため、`what|which` の名詞句は枠の語を 1 語でも含めば語そのもの（属性なし）とした。所有格と `the <語> of|for` の形は語ごとに照合する（厳しい側）。
25. **（第 3 ラウンド）日本語**: 属性を読む形は `の<語>は|が`（読点で閉じない）・`の<語>を教え…`・`どの|どんな<語>`。読点で閉じたトピック（`…の選択は、…どちらにしますか` を答えにすると既存試験が固定）は読まない。形が読めない日本語は答えのまま（(ii) を日本語には置いていない）。穴として docs §11 に書いた。日本語で枠の語が言及されない文は広い語句の経路でなく、この確認の対象でない。
26. **（第 3 ラウンド）M-B 構文の追加**: 依頼の手がかりと枠の主語を同じ閉じた代名詞の類にした（`someone|somebody|anyone|…`）、枠の法助動詞に `would|will`、可能の問い `is|would it be possible (for <語>) to`（`possible` は `ok|allowed` と同じ位置）、日本語の授受の動詞が可能・許可の問いの中にある形、頼む動詞の願望・平叙（かなの尾だけ）。**保護された操作の語・`_PERM_CUE` は変えていない。** `消す` の類への追加は、指示書 D7 とチケットの例 `代わりに消して` の食い違いとして監査役の判断に残す（変えていない）。
27. **（第 3 ラウンド）任意の改善 1 を採用**: `_BI_SLOT` から節を開く語（wh 語・`if`・`whether`・`before`・`after`・`because`・`while`・`until`・`unless`）を除いた。`Could you explain why deleting … is needed?` は dev と同じ `FRAME_SILENT/MAP_NONE` に戻る。任意の改善 2（`I'd like you to`・`Is there any chance you could`）は直さず穴として書いた。
28. **（第 3 ラウンド）M-C**: 全体テストを最後まで 1 回流して `after_pytest.txt` と `after_failures.txt`・`new_failures.txt`・`fixed_failures.txt`・`new_vs_official_baseline.txt` を作り直した（出力の集計行は `impl.r3.md`）。

## 宣言した衝突（実際に落ちる 6 本。テストには触れていない）

| # | 落ちるテスト | 内容 |
|---|---|---|
| C1 | `tests/attack/test_attack_w3a2_contract.py::test_hiragana_katakana_variant_keeps_same_state` | かなは別語（D1） |
| C2 | `tests/attack/test_attack_w4m_sovereign.py::test_tampered_export_cannot_be_attached` | 攻撃役の外れ（payload の書き換えは検出しない） |
| C3 | `tests/test_routing_from_text.py::test_relation_override_replaces_exactly_the_same_scope_and_counts_it` ほか 2 本 | `追記：` は足すのが既定（A02） |
| C4 | `tests/test_conduct_ask_w2c2_view.py::test_markdown_and_jsonl_views_have_the_same_decisions_and_the_same_terms` | md と jsonl の差を揃えた（#4）ので、差を固定する期待が食い違う |

## 第 4 ラウンド（レビュー r3 の M-D・M-E・M-F と監査役の裁定 C1〜C4。2026-10-03）

29. **（第 4 ラウンド）M-D (a)(b)**: `_ATTR_JA_TOPIC` の先読み `(?![、,])` を外し、一致の直後が読点のときだけ、(a) 選択肢が はい／いいえ、(b) 与えられた選択肢の文字列がすべてトピックの後ろにある、のどちらかなら属性語の無い形（語そのものを問う形）として扱う。字面（`と…のどちら`）ではなく選択肢という入力で判定する（指示書 D-r4-1）。代償: 別の属性を問いながら記録の値を名指しする文と、Yes/No で別の属性を問う日本語の文は答えになりうる（`documented_limit` の試験で固定、`docs/CONDUCT_ASK.md` §11・§16.6）。
30. **（第 4 ラウンド）M-E の 4 構文と定数**: (1) 形容詞の類 `_BI_OK_ADJ`（値は今の枠と同じ。足していない）を枠と門で共有、(2) `くださる` の活用（`くださ(い|る|います|いません)(か|でしょうか)?`、門は `てくださ`）、(3) 依頼の構文の可能の尾 `_BI_JA_CAN`（`_PJA_CAN` は変えない）、(4) 条件形で終わる平叙の依頼 2 つ（`…もらえ|いただけ|頂け|くれ` ＋ `れば|ると|たら`、`お願い|依頼` ＋ できれば等）、(5) 英語の `be <1〜3 語> to`（`able|willing` の一覧は消えた）。門と枠は別々の正規表現なので文ごとに両方で通ることを確かめた。
31. **（第 4 ラウンド）任意の改善 1（素の許可の問い `…することは可能でしょうか`）を採用**: `_BI_JA_ASKED_OP` の 2 つ目の尾を `_BI_JA_CAN` に、門に `(?:でき|可能)(?:ます|です)?でしょうか` を足した。副作用 0（`C1_changed_rows 0`、W2-c 系 20 ファイル `1252 passed`、`probe2` の OVER 9 文は第 3 ラウンドと差 0 行）。`_PERM_CUE`・`_PJA_CAN` は変えていない。
32. **（第 4 ラウンド）C1 の実施（裁定 2026-10-03）**: `coarse_place.query` の最後で `_borrow_kana_variant`。問うた表記が `UNPLACED`／`UNKNOWN`・仮名が 1 つの文字体系だけ・変種が `DECIDED` かつ `direct` のときだけ `origin estimated`・`estimate_basis kana_variant`・`constructed true` で返し、`spelling.why` は `ESTIMATED_FROM_KANA_VARIANT:<変種>`（D-r4-2: 仮名の混ざった表記は借りない。裁定より狭い側）。攻撃テスト `test_hiragana_katakana_variant_keeps_same_state` は名前を変えず assert を改訂（前後の全文は `docs/COARSE_PLACEMENT.md` §11.9.3）。D1 を固定していた新しい試験 2 本は新しい契約に書き換え、借りない場合（`MULTIPLE` の変種・`estimated` の変種・仮名の混在・自分の答えを持つ表記・`NO_PLACEMENT`）の試験を足した。測定: L2 の主指標は不変、非直接の内訳が `estimated/wrong_single 26 → 28`（`ロケット`・`モネ`）、L3 は変化 0 行、L1 の被覆は `0.7907 → 0.7957`（`coarse_items_r3_vs_r4.txt`）。
33. **（第 4 ラウンド）C2 の実施**: `tests/attack/test_attack_w4m_sovereign.py` から `test_tampered_export_cannot_be_attached` を取り除いた（skip・xfail にせず、関数ごと。原本 `attacks/W4-m/test_attack_sovereign.py` はそのまま）。先頭の出典コメントを書き換え、`docs/SOVEREIGN.md` の限界の節に 1 行追記。
34. **（第 4 ラウンド）C3 の実施**: `tests/test_routing_from_text.py` の 3 本は入力に `やっぱり` を足しただけ（名前・assert は不変、表の鍵も同じ文に）。標識なしの版は `tests/test_routing_from_text_w5b.py` に新しい 3 本（`test_C3_without_a_marker_…`）。期待は今の木で測った挙動。前後の全文は `docs/ROUTING_FROM_TEXT.md` §18「W5-b 第 4 ラウンド（監査役の裁定 C3）」。
35. **（第 4 ラウンド）C4 の実施**: `tests/test_conduct_ask_w2c2_view.py` の最後の 2 行を `known_differences == {}` に（期待を強める向き。前後の全文は `docs/CONDUCT_ASK.md` §16.6）。
36. **（第 4 ラウンド）D-r4-3（凍結 L2 との関係）**: 中間職の r1 の凍結反例のうち `test_l2_w3a2.py::test_c4_spelling_has_no_effect_and_nothing_else_moved` と `test_c5_kana_variant_why_is_consistent[ロケット]`・`[モネ]` は D1（spelling は答えを変えない）を固定した試験で、C1 が契約を置き換えたため落ちる。指示書どおり合わせて何もしていない。r1 の `test_l2_w2g2.py` の 4 本（試験の作りの誤り）と r2 の `代わりに生ログを消してもらえる？`（`消す` は閉じた類に無い）も第 3 ラウンドまでと同じ（`L2_frozen_on_impl_r4.txt`: `8 failed, 149 passed`）。
37. **（第 4 ラウンド）指示書のコマンドとの違い**: (a) `routing_with_placement.py` は引数に配置のディレクトリが要る（指示書の例は引数なし。`$PLC` を渡した）。(b) 写しと原本の比較 `diff <(sed 1d 原本) <(sed 1d 写し)` は原本に出典の行が無いので、原本全体と `sed 1d 写し` を比較した（L1 の指示のとおり）。(c) `stress_w4m.py` の作業ディレクトリは先に作る必要がある。
38. **（第 4 ラウンド）守った定数の確認**: 指示書の grep（`^[-+]_(PERM_CUE|PJA_CAN|BI_JA_OP|BI_EN_OP|BI_JA_CRED|BI_EN_CRED) =`）は `_BI_EN_OP` の行を 1 組出すが、これは第 2 ラウンドで足した `-ing` の活用（`deleting` など）の差分（基点 `a92a926` との差）で、**このラウンドでは `_BI_EN_OP` の行を 1 バイトも変えていない**（このラウンドの編集は `_BI_OK_ADJ` `_BI_JA_CAN` `_BI_MODAL_FRAMES` `_BI_JA_REQUEST` `_BI_REQUEST_CUE` `_BI_JA_ASKED_OP` だけ）。`_PERM_CUE`・`_PJA_CAN`・`_BI_JA_OP`・`_BI_JA_CRED`・`_BI_EN_CRED` は基点から変わっていない。
39. **（第 4 ラウンド）`check_invariants` と `ESTIMATE_BASES`**: `tests/coarse_place/test_coarse_place_build.py` の `check_invariants`（W3-a のもの）と `verantyx/event_cross.py` の `ESTIMATE_BASES` は `kana_variant` を知らない。どちらも触らない範囲なので触っていない（新しい試験は前者を借りた答えに当てていない。後者は `kana_variant_event_cross.txt` に `ESTIMATE_BASIS_UNKNOWN:kana_variant` が出る事実を残し、監査役への申し送り）。

### 宣言した衝突の表（上の表）の第 4 ラウンドでの扱い（表は消さない）
第 4 ラウンドで監査役の裁定により解消した:
- C1: 攻撃テストの assert を改訂して通る（裁定 C1）。
- C2: 攻撃テストの写しに取り込まない（裁定 C2。関数ごと取り除いた。原本は残す）。
- C3: 3 本の入力に標識を足して通る＋標識なしの新しい試験 3 本（裁定 C3）。
- C4: 期待を `{}` に改訂して通る（裁定 C4）。
