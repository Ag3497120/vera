# K-A2: 申し送り（実装役 → 中間職・監査役。判断は監査役）

## 衝突
W5-d2 の裁定 K2 は、`tests/test_routing_from_text.py::FakePlacement`（固定の名前を `UNPLACED` と答える偽の配置）の下で、日本語の名前が担当者に振られることを前提にして既存のテストを書き直した。チケット W5-e の A-2（推定・`UNPLACED`・`UNKNOWN` は `COMMON_NOUN_SUBJECT_UNTYPED` で止める）と H3（r7 の普通名詞 60 文で振られる数 8 → 0）はその前提を退役させる。H3 を満たす規則とこの前提は両立しない。

## 落ちた id（実装役は書き換えていない）
`artifacts/w5-e/a2_declared.txt`（73 件。一覧と数は測定の出力のとおり）。名指しの改訂（`test_routing_from_text_w5b.py::test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop` の 3 引数）は含まない。ファイル別: `tests/test_routing_from_text.py` 36、`tests/test_routing_from_text_w5d.py` 20、`tests/test_routing_from_text_w5b.py` 13、`tests/test_routing_from_text_regress.py` 2、`tests/attack/test_attack_w5b_wave2.py` 1、`tests/attack/test_attack_w5d.py`（W5-d の写しの R2）1。
- 失敗の中身は大半が単位の状態 `NAME_UNRESOLVED`（期待は `MAPPED`・`AMBIGUOUS_RELATION`）、または追記の数・`superseded_by` の期待が崩れたもの（名前が止まって関係が作られない）。2 件（`EMPTY_TABLE`・`route takes a RoutingTable...`）は名前が止まって表が空になった連鎖。
- チケットの試作との差 1 件: `test_routing_from_text_w5d.py::test_r1_a_direct_type_among_the_noun_types_is_a_common_noun[types4]`（`("P_COMMUNICATE", "PERSON")` の MULTIPLE）。チケットの規則 A-2（MULTIPLE は全候補一致のときだけ typed、名詞型でない候補を含むものは `COMMON_NOUN_SUBJECT_UNTYPED:…:MULTIPLE`）どおりに作ると、単位の状態は `NAME_UNRESOLVED` のまま（止まる）で理由の文字列だけが `COMMON_NOUN_SUBJECT:…:PLACEMENT_DIRECT:…` から `COMMON_NOUN_SUBJECT_UNTYPED:…:MULTIPLE` に変わる。

## 改訂の方向（案。実装役は適用していない）
1. `FakePlacement` を「固定の名前を、名詞型でない direct の型（例 `P_COMMUNICATE`）で答える」ものに変える。規則 4（名詞型でない DECIDED direct は通す）で R-J1 の「17 型に無い型だけの direct は止めない」に乗り、K2 のテストの意図（名前が配置に答えられたうえで担当者になる）が保たれる。W5-d の攻撃の写し（R2）の `PredicateTypedName` が既にこの形。
2. または、各テストの名前を命名の文（「〜を〇〇と呼ぶ」）で導入する（導入された名前は配置の答えを見ない）。
3. 「UNPLACED／推定でも通る」ことそのものを主題にしたテスト（`test_routing_from_text_w5d.py::test_r1_a_placed_word_that_the_placement_cannot_type_still_passes` など）は、期待を `COMMON_NOUN_SUBJECT_UNTYPED` に反転して退役を記録する（名前不変・前後の全文を docs に残す標準の規則）。

## 案 1 の実測（scratchpad の複製。本ツリーのテストは変えていない）
`FakePlacement.lookup` の既定の返り値だけを `DECIDED direct P_COMMUNICATE` に変えた複製（`tests/test_routing_from_text.py`・`..._regress.py`・`..._w5b.py`・`..._w5d.py` の 4 ファイルのコピーと `conftest.py`・`_vera_env.py`）で、その 4 ファイルを流した出力が `artifacts/w5-e/proposals/k_a2_scratch_run.txt`（`28 failed, 139 passed`）。**この数は案 1 だけでは解決しない残りを示す**: 残り 28 件には、(a) 複製が本ツリーの `docs/` を見つけられないための失敗（`test_T4_*`・`test_M4_*` など、docs を読むテスト。複製の場所のせい）、(b) UNPLACED／推定を主題にしたテスト（案 3 が要る）が含まれる。攻撃の写し 2 件（`tests/attack/*`）はこの複製に入れていない（相対パスの依存）ので測っていない。案 1 だけで何件が直るかを知るには、本ツリーに適用した測定が要る（監査役の裁定の後）。
