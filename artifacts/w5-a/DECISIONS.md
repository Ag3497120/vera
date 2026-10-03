# W5-a 判断記録

索引（`index search` 4 件。`artifacts/w5-a/index_search.txt`）: 4 件とも `UNKNOWN_NOT_FOUND`。作り直しに当たる既存物は無かった。

## 指示書の判断 D1〜D8（実装役はこのとおりに実装した）
- D1 H1 は (a)（2c の廃止）。(b) は W3-b1 の配置が要るので採らない。T6（`tests/test_semantic_read_r4.py` の 5 件）が落ちる。許可パス外で、期待の書き換えは弱体化にあたるので触れず、宣言した（`new_failures.txt`）。`_SPONTANEOUS_PREDICATES` に語は足していない。
- D2 H2 は理由ごとの証拠。免除する理由は 3 つだけ（`copula value is a predicate phrase`・`causative frame: causer/causee unresolved`・`unrepresented source content`）。
- D3 H3 は複合動詞の構造＋人でない証拠＋場所の証拠の を。「人の証拠が無ければ棄権」には広げない（既存テスト 7 件が落ちる、と指示書にあり、この実装では試していない）。
- D4 H4 は書かれた形から閉じた一覧で一意に決める。同点は棄権。`en_frames.lemma` は触らない。
- D5 A1 は構築時に辞書順＋`invariant_problems` の検査（`TYPES_NOT_IN_ALPHABETICAL_ORDER`）。
- D6 A2 は関係を `type, from, to` の順、入力から写す入れ子の Mapping は辞書順。lookup の provenance は変えない。
- D7 A-01 は `choice_key` と決定行の `key` を変えず `reuse_key` を足す。`reuse_key` の無い古い決定行は再利用せず、`summary()["decisions_without_reuse_key"]` に数える。質問文は鍵に入れない。
- D8 `semantic_reader.py`・`agent_routing.py`・`en_frames.py` は変更しない。

## 作業中に実装役が決めたこと
- E1 `_canon` を `EventCross.to_dict` の `provenance` の値にも使った（指示書は `center`・`flags`・`abstain`・`relations` だけ）。`provenance` の鍵は `_cross` が固定の順で入れるので、ここで正規化するのは値（読解器の `clause_meta` から写す `rule`・`span`）が Mapping だったときの順だけ。通常の入力ではバイト列は変わらない（凍結データの試験が通る）。
- E2 K3 のテストは、1 つの Mapping が 9 鍵だと全順列が 362,880 通り（実測で 1 つの入力に 75 秒）になるので、最初の節の鍵を 8 個にして、`scope` を持つ入力と `comparison` を持つ入力に分けた（それぞれの Mapping の全順列を調べることは変わらない。`comparison` の入力は最初の節だけを調べる）。件数と秒数は `k3_permutations.txt`。
- E3 H4 の `k is None`（書かれた動詞のトークンが見つからない）の扱い: 以前の順序（先に `UNKNOWN_PREDICATE`、数量・所有・疑問の検査のあとに `UNDETERMINED_TENSE:verb token`）を保つため、`k` が無いときは以前の門をそのまま使い、`UNDETERMINED_TENSE:verb token` は元の位置で出す。入口の出力の変化が増えないようにするため。
- E4 H1 の理由の型: 主語に人でない正の証拠があるとき `UNDETERMINED_VOICE:passive or spontaneous`、無ければ `passive or honorific`（既存の T1〜T5・T7・T8 の理由の検査を保つ）。
- E5 H3 の複合動詞の判定（`_is_compound_path_verb`）は、後ろ半分が 1 語の動詞（タガー）で `_PATH_VERBS` にある、または前半が連用形の動詞で `_PATH_VERBS` にある、のどちらか。UniDic の語彙素のずれ（登る→上る）のため、表層と語彙素の両方を `_PATH_VERBS` と照らす。
- E6 製品コードの文言（コメント・docstring・`NOT_PRODUCED`）に攻撃文の語（駆け抜ける・repaired）が入っていると C-WORDS が 0 にならないので、別の語の例に書き換えた。
- E7 K4 の台本の確認で `tempfile` の既定が環境変数を空にした実行で `/tmp` を指し、`/tmp/k4_*`（台帳の小さなファイル 3 つほど）が木の外に残った。以後 `k4_counts.py` は引数の scratchpad を使う。消していない。
- E8 比較の基準（dev の写し）は scratchpad の `W5a/dev0e4`（`git archive 0e40954` の写し。tree の同一は `git write-tree` と `git rev-parse 0e40954^{tree}` が一致することで確認）。攻撃テスト 3 本の「直す前」の失敗を記録するため、そこにだけ攻撃テストを置いてコミットした（木の外）。

# 第 2 ラウンド（W5-a2。出力は `artifacts/w5-a/r2/`。第 1 ラウンドの測定ファイルは消さず・上書きしていない）

索引（`index search` 2 件。`r2/index_search.txt`）: 2 件とも `UNKNOWN_NOT_FOUND`。作り直しに当たる既存物は無かった。

## 指示書の判断 D-B1〜D-R2b（実装役はこのとおりに実装した）
- D-B1 T6 の改訂は監査役の許可の範囲だけ。関数名・パラメータ `T6` の 5 文は不変。期待は `abstains_on_voice` ＋ 理由の完全一致（`['UNDETERMINED_VOICE:passive or spontaneous']`）。凍結の sha256 ファイル（`artifacts/w1-a/w1a3_tests_freeze.sha256`）は許可パス外なので書き換えず、不一致を文書（K62）で宣言した。
- D-B2 免除は §9.2 の 1 の比較の例外 1 種だけ（`answered`）。r3 の 3 件はパラメータを変えず表 `W5A_R2_REVISED` で分けた（ノード ID を保つ）。期待は `['UNSUPPORTED_CLAUSE']` の完全一致。
- D-B2b `tests/test_observe.py` の 3 関数は監査役の見積もり（3〜4 件）の外。原因を `r2/observe_cause.txt` に取ってから改訂（原因は免除の除去だけ）。報告と K63 に「見積もりの外の 3 件」と明示。凍結データ（`test_observe_data.py`）は変えていない。
- D-B3 「述語の既知の枠」は 2 つの源だけ（`frames.transitivity == 'trans'`、読解器の を を patient とする枠の類）。乗り物の類は作らず、乗り物の証拠は無い扱い。`_MEANS_NOMINALS` は使っていない。監査役の B3 の主文と (ii) の衝突（表が `trans` とする経路の動詞）は (ii) を優先し、残る型を K64 に宣言した（監査役に判断を返す）。
- D-R2 `semantic_reader.py` は変えていない（`git diff 0e40954 --stat -- verantyx/semantic_reader.py` が空）。
- D-R2b 第 1 ラウンドの `before_failures.txt` を基準に使った。

## 作業中に実装役が決めたこと
- E9 `tests/test_observe.py` の `test_unoccupied_cells_...` の改訂: 指示書は「拒否された要素の `realization['provenance']` を測った値で完全一致」と書いたが、測った値では拒否された要素の `realization` に `provenance` の鍵が無かった（`{'status': 'REFUSED', 'reason': 'ROUNDTRIP_MISMATCH', 'detail': 'generated text was not read (ABSTAINED)'}` の 3 鍵だけ。`index` つきの観測で測定）。そこで、その要素の `realization` 全体を測った dict に完全一致させ、`provenance` の assert はほかの要素だけに課した。`claim == 'CONSTRUCTED_UNOCCUPIED'` は全要素のまま。期待を緩めてはいない（拒否された要素について、今までは `provenance` を求めていたが、その要素は realization が REFUSED で provenance を持たない）。
- E10 B3 のテストの文は自分で選び、`frames.transitivity` と `_object_frame_known` を測ってから決めた。(a) `雨が屋根を降った。`・`波が岸を上がった。`・`煙が空を上がった。`・`雲が空をたなびいた。`・`気球が丘を下がった。`（述語は表で `intrans`／`unknown`、類に無い）、(b) 同じ述語の人の主語、(c) 表で `trans` の 3 文、(d) 表で `trans` でなく類にある `保管する`・`設置する`、(e) 単体、(f) `空は雲がたなびいた。`（は の patient。この文自体の読み〔空が patient〕は誤りに近いが、この規則の対象外。既知の穴として報告）。`(b)` と `(f)` は `AGENT_EVIDENCE_MISSING` が理由に無いことだけを課し、読みの内容は課していない。
- E11 H2 の不変条件のテストは 26 文（比較・使役・普通の他動詞・なくもない・連体修飾・でを含む）で、`readable: false` は問わず、`readable: true` が 8 文以上あることだけ課した（何も読まずに満たすのを防ぐ）。
- E12 C-WORDS（攻撃文の語の検索）は 1 行ヒットした: `+ R._PROCESSING_PREDICATES, R._PRODUCT_PREDICATES, R._CONTAINMENT_PREDICATES, R._PLACEMENT_PREDICATES)`。検索語の `PLACE` が指示書どおりのコードの `_PLACEMENT_PREDICATES`（読解器の閉じた類の名前）に当たった偽陽性で、攻撃文の語ではない。類の名前を避けるために書き換えると指示書の仕様から外れるので、そのままにして報告する（`r2/attack_words_in_diff.txt`）。
- E13 `bank_cmp.py`（採点器の before/after の突き合わせ）と `classify7.py`・`h2_invariant.py` は `r2/` に置いた（実行した出力と同じ場所）。

# 第 3 ラウンド（W5-a3。出力は `artifacts/w5-a/r3/`。M1 の `r2/observe_after.txt` 1 ファイル以外、第 1・第 2 ラウンドの測定ファイルは消さず・上書きしていない）
索引（`index search` 1 件。`r3/index_search.txt`）: `UNKNOWN_NOT_FOUND`。作り直しに当たる既存物は無かった。

## 指示書の判断 D3-*（実装役はこのとおりに実装した）
- D3-B3 既知の枠は読解器の閉じた類 8 つだけ（監査役の (β) 変種 C）。`_object_frame_known` の引数から `transitivity` を外した（`(predicate, R)`）。条件の残り（主語に人の正の証拠が無い・を で示された patient がある）と理由の型・置き場所は第 2 ラウンドのまま。`_clause_ja` の先頭の `from .frames import transitivity` は `_voice_ja` が使うので残した。
- D3-EVID 人・動物・乗り物の証拠は `_is_person_phrase` だけ。`frames.is_role` などの新しい証拠の源は足していない（S-J21 の `会計係` や `子犬` の損失を語を足して戻していない）。W3-b1 への申し送り。
- D3-T1 test_T1 は、旧い期待（`route`・`ハル`・MAPPED 7）を、測った出力への完全一致（`undecided`・`ABSTAINED`・`gate:INCOMPLETE_READING`・`units`・`evidence`・`by_status` の dict 全体・`detail` の文字列）に変えた。名前は変えない。
- D3-SJ21 S-J21 の改訂は、凍結データを変えず、テストの側の表 `W5A_R3_REVISED` で分けた。パラメータの行は不変。期待は要約の完全一致 ＋ 入口の理由の完全一致 ＋「凍結の期待はもう成り立たない」ことの assert。
- D3-NEW 新規ファイル `tests/attack/test_w5a_reading_entry_rules.py` の B3 のテストは書き直し・改名した（既存の試験の改訂には数えない）。
- D3-M1 `r2/observe_after.txt` は監査役の指示で取り直した。抜けのある版は `r3/observe_after_r2_truncated.txt`。テストのファイルは変えていない。
- D3-R `semantic_reader.py` は変えていない。

## 作業中に実装役が決めたこと
- E14 新規ファイルの B3 のテストの旧名→新名: `test_b3_a_transitive_predicate_of_the_corpus_table_is_still_read`（3 パラメータ）→ 中身が反対になったので `test_b3_a_predicate_the_corpus_table_alone_calls_transitive_is_no_known_frame`（2 パラメータ `削る`・`壊す`）。第 2 ラウンドの 3 つ目のパラメータ（`機械が荷物を運んだ。`）は `test_b3_a_predicate_of_a_reader_class_is_read_with_a_subject_that_has_no_person_evidence` に分けた。人の主語の同じ述語の文は `test_b3_the_same_predicates_with_a_person_subject_are_read_as_an_agent_and_a_patient`（`職人が部品を削った。`・`職人が小屋を壊した。`）。`test_b3_object_frame_known_has_two_sources_and_no_other` → `test_b3_object_frame_known_has_one_source_the_reader_classes`（署名が `['predicate', 'R']` ちょうどであることも固定）。(a)・(b)・(d)・(f) は呼び出しの引数だけ直し、文と期待は変えていない。新しい文に指示書の禁止の動詞・攻撃文は使っていない。
- E15 C-LISTS: 第 2 ラウンドのコマンドが記録に残っていなかったので、`semantic_read`・`semantic_reader` の大文字（または `_` ＋ 大文字）の名前の set・frozenset・tuple・list・dict（`NOT_PRODUCED` を除く）99 個を JSON にして dev の写し（`W5a/dev0e4`）と `$W` で比べるスクリプト（`r3/lists_dump.py`）を新しく書いた。2 つの出力は同一（`r3/c_lists.txt`）。
- E16 採点器の before は、第 2 ラウンドの実装役が scratchpad に残した結果（`W5a2/bs_r2_<fx>`、dev は `W5a/bs_before_<fx>`）をそのまま使った（流し直していない）。after は今の木で流した。
- E17 `classify7.py` は、述語と主語を各行に書いた（棄権した文は節が無く、述語を取れないため）。
- E18 `r3/transitivity_values.txt`・`r3/person_phrase_probe.txt` は、K64 に書く数値と主張（表の値、`子犬`・`犬` などの人の証拠）の出典として足した測定。
