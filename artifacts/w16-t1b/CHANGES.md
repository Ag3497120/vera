# 差分の分類（全件。実測の出力から）

型: (a) 読める／答える → 棄権（K800。reason に `MODALITY_NOT_READ`、または法の文を材料にした後段の答えが消える）／(b) 切れた値 → 全体の値（K801）／(c) 答える → AMBIGUOUS・棄権（K801 の表記の不一致）／(d) 棄権 → 棄権で理由だけ変化（チケットの 2 方向の外。申し送り）／(d2) 答え同じ・副次の欄だけ変化／(e) それ以外（0 であるべき）。

## 1. W3-c4 の凍結データ（K342 と同じ 4 本。`k342_summary.txt`・`k342_changed.tsv`・`k342_classified.tsv`）
- aq（111）・w3c2（185）: マスク後 byte 不変（差 0）。対照 before 対 before2: aq・extra2 とも 0（`k342_control_summary.txt`）。
- extra2（42）・b2like（47）のマスク後の差は 34 行（`k342_classified.tsv` は「ANSWER 以外どうし」の 24 行を含め全行）。
  - 内訳: {'d': 24, 'a': 6, 'd2': 3, 'b': 1}（マスクして比べた全 34 行）。
  - (a) X008・X009・X010: 文書 X01〜X03 の願望の文に「誰が…読んだ？」と問う行。基点は `ANSWER`（`agent: 先生` 等。truth は NONE）→ `UNKNOWN_UNSUPPORTED_EVIDENCE`（reason `MODALITY_NOT_READ:desire`）。正しい方向の変化。
  - (a) X011・X012・X014: 「先生は何を読みたかった？」等（truth ONE。問の述語と文の述語が同じ書き方）。基点は後段 question_cross が `ANSWER`（本・魚・地図。score の class `CORRECT`）→ `UNKNOWN_UNREAD`（`ABSTAINED`）。**能力の喪失**（K815。K800 の裏返し）。
  - (b) b2like BQ002: `森田` → `森田課長`（`agent: 森田課長`）。K801 の対象そのもの（`docs/OBSERVATION.md` 1437 行の既知の穴）。
  - (d) 24 行: extra2 の UNKNOWN_UNREAD どうしの 24 行（id は `k342_classified.tsv` の class d）。願望の文を含む文書で、後段の `question_cross` の `structure.unread` が増え（1→7 等）、理由が `PREDICATE_FORM_DIFFERS`/`UNREAD_SENTENCES:1` → `NO_MATCHING_CROSS_IN_READ_SENTENCES`/`UNREAD_SENTENCES:7` 等に変わる。verdict は UNKNOWN_UNREAD のまま。
  - (d2) X028・X029・X030: 答え（論文・歌・米）は同じ。後段の `structure.unread` が 1→2、`crossed` 6→5（文書内の法の文が未読として数えられる）。
  - (c) と (e): 0 件。
  - extra2 の score（`before/extra2_score.json` → `after/extra2_score.json`）: CORRECT 19→23・ABSTAINED 16→12・WRONG 0→0。X011・X012・X014 が CORRECT→ABSTAINED、X001〜X003・X005〜X007・X035 の 7 行（truth NONE）が ABSTAINED→CORRECT（NONE に棄権が正解として数えられる）。

## 2. 入口 4,149 文（`entry_none_diff.txt`・`entry_r9_diff.txt`・`*_diff.tsv`）
- 配置なし・r9 とも `{'same': 4143, 'abstain_reason_changed': 6}`、`other` 0、読める→棄権 0。読める数は 286→286（`entry_none.*.log`）・377→377（`entry_r9.*.log`）。
- (d) 6 行（全件）: 子供が野菜を食べられた。／兄が弟に名乗りたい。／兄が湖へ歩きたい。／弟が橋へ走りたかった。／妹が町へ飛びたかった。／先生が課長に申告したい。 いずれも `UNDETERMINED_VOICE…`・`RECIPIENT_TYPE_UNDETERMINED:…` → `NO_SUPPORTED_CLAUSE`＋unsupported に `MODALITY_NOT_READ:potential|desire`。棄権→棄権（中間職の試作と同じ 6 行。実測で取り直した）。

## 3. バンクの公開の写し（`bs_B*_compare.txt`・`bs_semantic_compare.txt`）
- B1・B2・B3 とも `results.jsonl` は前後で一致、差は `run_meta.json` の時間の欄と `verantyx_untouched`（ツリーを変えたので false）だけ。件数（`bs_B*_before.txt` 対 `bs_B*_after.txt`）も同一。

## 4. 関係テスト（`related_diff.txt`・`EXISTING_TEST_CONFLICTS.md`）
- 新しい失敗 26 件（全て K800 由来）、消えた失敗 0、K801 由来 0。全件と改訂案は `EXISTING_TEST_CONFLICTS.md`。

## 5. 自作の範囲の集合（`range_changed.tsv`。合否に入れない）
- modal 40 行（ANSWER→UNKNOWN_UNSUPPORTED_EVIDENCE。(a)）、title 30 行（短縮が直った。(b)）、title_mixed 6 行（ANSWER→AMBIGUOUS。(c)）、range 5 行（4 行 (a): 並列の同じ主語・2 文の文書の願望側、1 行 (b): `加藤社長` が `山本さん` に…）。modal_control・title_control は 0 行変化。

# 第 2 ラウンドの差分の分類（M1〜M4 の後に K802 を取り直した。全件。上の第 1 ラウンドの節は古い数を含む）
型: (a) 答える → 棄権（K800。K818 の可能動詞を含む）／(b) 切れた値 → 全体の値（K801）／(c) 答える → AMBIGUOUS・棄権（K801 の表記の不一致）／(d) 棄権 → 棄権（理由だけ変化）／(e) それ以外 = 0。

## 1. W3-c4 の凍結データ 4 本（`k342_summary_r2.txt`・`k342_changed_r2.tsv`）
- aq（111）0 行・w3c2（185）0 行（マスク後 byte 不変）。b2like（47）1 行: BQ002 `森田` → `森田課長`（(b)）。extra2（42）33 行: 第 1 ラウンドと同じ分類（(a) X008〜X010・X011・X012・X014 の 6 行、(d) 24 行、(d2) X028〜X030 の 3 行）。X011・X012・X014（「先生は何を読みたかった？」等。後段の答えが消える）は答え→棄権（裁定 1 で許した向き）。extra2 の score: CORRECT 19→23・ABSTAINED 16→12・WRONG 0→0（`before/extra2_score.json`・`after_r2/extra2_score.json`）。対照 before 対 before2 の差 0（`k342_control_summary.txt`）。
- 可能動詞（K818）による新しい差は、この 4 本には無い（入口にだけ出た）。

## 2. 入口 4,149 文（`entry_none_diff_r2.txt`・`entry_r9_diff_r2.txt`・`*_diff_r2.tsv`。配置なし・r9 とも同じ）
- `{'same': 4130, 'abstain_reason_changed': 19}`、読める→棄権 0、棄権→読める 0、other 0。読める数は 286（配置なし）・377（r9）で前後同じ（`entry_*.after_r2.log` の `inputs=4149`）。
- (d) 19 行（全件）: 第 1 ラウンドの 6 行（願望 5: 兄が弟に名乗りたい。・兄が湖へ歩きたい。・弟が橋へ走りたかった。・妹が町へ飛びたかった。・先生が課長に申告したい。と 子供が野菜を食べられた。）に、**K818 の可能動詞 13 行**: 歩ける（弟が公園へ歩けた。・馬が村へ歩けない。・兄が寺へ歩けなかった。）、行ける（妹が病院へ行けた。・母が港へ行けない。・姉が空港へ行けなかった。）、戻れる（兄が部屋へ戻れた。・弟が台所へ戻れない。・父が工場へ戻れなかった。）、向かえる（姉が駅から空港へ向かえた。・祖父が夜に病院へ向かえない。・弟が橋へ向かえなかった。）、移れる（母が台所から部屋へ移れた。）。理由は `RECIPIENT_TYPE_UNDETERMINED:…`・`UNDETERMINED_MODALITY:possible potential form`・`UNDETERMINED_VOICE…` → `NO_SUPPORTED_CLAUSE`＋unsupported の `MODALITY_NOT_READ:desire`／`potential`。基点でも棄権している文（可能動詞は基点の既存の門がこの形で棄権していた）なので誤答の増減は無い。
- **K818 が「答え→棄権」にした文（本物の読み取り）は入口 4,149 文には無い**（可能動詞は入口で既に棄権）。「答え→棄権」の例は自作の範囲（下 3）の `次郎は報告書を書けた。` 型。

## 3. 自作データ（`range_before_r2.tsv`・`range_after_r2.tsv`・`range_changed_r2.tsv`。基点の木で前、第 2 ラウンドで後）
- converse_modal: ANSWER 24 → `UNKNOWN_UNSUPPORTED_EVIDENCE`（(a)）、`UNKNOWN_NO_EVIDENCE` 4 は同じ。modal: ANSWER 40 → 棄権（(a)）、残りは基点のまま。title 36: ANSWER のまま全体の値（(b)）。title_mixed 6: ANSWER → AMBIGUOUS（(c)）。対照（modal_control 42・passive_control 6・ichidan_control 9・title_control 11）は全て ANSWER のまま同じ値。
- range 30 行（問いの数）のうち変わった行: 並列の同じ主語 2・2 文の文書の願望側 2・`花子は先生に本を届けられた。`・title の `加藤社長` の 1 行（(b)）。`花子は先生に本を届けられた。`→`['先生']` が棄権になる（二重目的語の受身。K820）。

## 4. バンクの公開の写し（`bs_B*_compare_r2.txt`）
- B1・B2・B3 とも差は `run_meta.json` の時間の欄だけ（`results.jsonl` は前後で一致）。

## 5. 関係テスト（`related_diff_r2.txt`・`revised_tests_table.tsv`）
- 基点の失敗 55（`related_before.txt`）= 第 2 ラウンドの最終 55。新しい失敗 0・消えた失敗 0。改訂した既存テスト 34 件（全件の前後は `revised_tests_table.tsv`）は全て通る。
