# W3-b3: 凍結したデータの予想と実測の食い違い（全件。データは変えていない）

出典: `data_entry_check.txt`（live、配置 r6）と `data_entry_check_fixture.txt`（fixture）。食い違いの種類:
- `entry_expect`（入口の出力の予想）の食い違い: **0 件**（203 行）。
- `structure_expect`（て形・連用中止の 2 つの節と辺）の食い違い: **0 件**（15 行）。
- `w3b3_expect`（診断の理由の予想。先頭が一致するかで照合）の食い違い: **7 件**。下の表。どれも **入口の出力は予想どおり棄権**（`entry_expect: abstain` は満たされた）で、違うのは、どの門が先に止めたかだけ。

| id | 文 | 予想 | 実測 | 理由（観測） |
|---|---|---|---|---|
| W3B3-REL-018 | 兄が歌った歌を姉が聞いた。 | `HEAD_ROLE_UNDETERMINED:frame_not_read` | `CLAUSE_UNREAD:1:PREDICATE_NORMALIZED:伝える<-聞く` | 主節の述語 聞く は、入口が逆の動詞 伝える に正規化するので読まない（`NOT_PRODUCED` の predicate:converse verbs）。K122 の順では節の読み（7）が主辞の腕（9）より先。予想は 聞く が読めると思っていた誤り。 |
| W3B3-REL-028 | 母が弟に話した知らせを兄が聞いた。 | `HEAD_ROLE_UNDETERMINED:type` | `CLAUSE_UNREAD:1:PREDICATE_NORMALIZED:伝える<-聞く` | 同じ（聞く）。 |
| W3B3-REL-039 | 母が弟に話した問題を兄が聞いた。 | `HEAD_ROLE_UNDETERMINED:outer_relation_type` | `CLAUSE_UNREAD:1:PREDICATE_NORMALIZED:伝える<-聞く` | 同じ（聞く）。 |
| W3B3-REL-043 | 母が弟に話した理由を兄が聞いた。 | `HEAD_ROLE_UNDETERMINED:outer_relation_type` | `CLAUSE_UNREAD:1:PREDICATE_NORMALIZED:伝える<-聞く` | 同じ（聞く）。 |
| W3B3-REL-053 | 母が弟に話した兄の友達を先生が呼んだ。 | `HEAD_ROLE_UNDETERMINED:head_not_simple` | `CLAUSE_UNREAD:1:UNSUPPORTED_CLAUSE` | 主節の文字列「兄の友達を先生が呼んだ。」を入口が読まない（X の Y の枠は配置なしの規則では読めない）。主辞の句の門（9）の前の節の読み（7）で止まる。`head_not_simple` は純粋関数 `w3b3_head` の単体テストで確かめている。 |
| W3B3-REL-054 | 母が弟に話した三人の客を兄が呼んだ。 | `HEAD_ROLE_UNDETERMINED:head_not_simple` | `CLAUSE_UNREAD:1:UNSUPPORTED_CLAUSE` | 同じ（数詞つきの主節）。 |
| W3B3-PAR-027 | 兄が静かに本を読み、弟が歌を歌った。 | `CLAUSE_UNREAD` | `W3B3_NOT_TRIGGERED:groups=3` | 静かに（形状詞）を `semantic_read._is_predicate_token` が述語のトークンと数えるので、述語のまとまりが 3 つになり引き金に当たらない。予想は節の読みで止まると思っていた。 |

データの期待（`expect`・`entry_expect`・`structure_expect`）は変えていない。診断の理由の予想の外れは、判断記録 H に書いた。
