<!-- prereg:begin -->
# 根拠の方針（basis policy）— 事前登録

登録日時: 2026-10-03 17:21:59 +0900
`TABLE_VERSION = 1`、`SCHEMA = "verantyx.basis_policy/1"`
この節（`prereg:begin` から `prereg:end` まで）は、`tests/test_basis_policy*.py` を書く前に確定した。以後この節の表・式・規則を変えるときは、`TABLE_VERSION` を上げ、旧版の全文を残す（削除しない）。

## 1. オーナーの決定（2026-10-03 17:10。事前登録として扱う。チケットの写し）

| 案 | 内容 | 扱い |
|---|---|---|
| A | 事実を問う依頼で、人が書いた出所に無ければ型付きで棄権 | 既定（変えない） |
| C | 事実の中身は人が書いた出所から。言い回しだけ生成コーパスの言い換えを使ってよい。中身が無ければ出さない | 既定 |
| E | 事実を主張しない依頼（創作・言い換え・文体・例文）では生成コーパスを材料にしてよい。型は「構成」 | 既定 |
| D | 人が居る場面で、生成コーパスにしか根拠が無いときは「生成コーパスにはこうある。正しいですか？」と問いとして返す。利用者が「はい」と言えば、その文は人が書いた記録としてソブリンに同意つきで保存され、以後は事実として答える | 追加（人が居る場面で有効） |
| B | 「参考: 生成コーパス由来（事実の証拠ではない）」の別の欄で、出所つきで見せる。記憶に入れず、指揮者は根拠にしない | 設定で OFF 既定。利用者が明示的に ON にしたときだけ |
| F | 実行して確かめられる生成物（コード・数式）は検証器が証人 | 今回は対象外（別チケット） |

## 2. 方針の表（24 行。中間職による決定 A〜E の写し方の導出であり、オーナーの決定そのものではない）

鍵は（依頼の類、根拠、人が居る、参考 ON）。F は偽、T は真。「形の借用が検証済みのとき」の列は、C の借用が 1 つに決まったときの結果。

| 依頼の類 | 根拠 | 人が居る | 参考 ON | 結果 | 形の借用が検証済みのとき | 由来 |
|---|---|---|---|---|---|---|
| FACTUAL | HUMAN | F | F | ANSWER_HUMAN_BASIS | ANSWER_FORM_FROM_GENERATED | A の反対側＋C |
| FACTUAL | HUMAN | F | T | ANSWER_HUMAN_BASIS | ANSWER_FORM_FROM_GENERATED | A の反対側＋C |
| FACTUAL | HUMAN | T | F | ANSWER_HUMAN_BASIS | ANSWER_FORM_FROM_GENERATED | A の反対側＋C |
| FACTUAL | HUMAN | T | T | ANSWER_HUMAN_BASIS | ANSWER_FORM_FROM_GENERATED | A の反対側＋C |
| FACTUAL | GENERATED | F | F | ABSTAIN | ABSTAIN | A |
| FACTUAL | GENERATED | F | T | REFERENCE_GENERATED | REFERENCE_GENERATED | B |
| FACTUAL | GENERATED | T | F | CONFIRM_REQUEST | CONFIRM_REQUEST | D |
| FACTUAL | GENERATED | T | T | CONFIRM_REQUEST | CONFIRM_REQUEST | D（参考欄も出る） |
| FACTUAL | NONE | F | F | ABSTAIN | ABSTAIN | A |
| FACTUAL | NONE | F | T | ABSTAIN | ABSTAIN | A |
| FACTUAL | NONE | T | F | ABSTAIN | ABSTAIN | A |
| FACTUAL | NONE | T | T | ABSTAIN | ABSTAIN | A |
| NON_FACTUAL | HUMAN | F | F | CONSTRUCTED | CONSTRUCTED | E |
| NON_FACTUAL | HUMAN | F | T | CONSTRUCTED | CONSTRUCTED | E |
| NON_FACTUAL | HUMAN | T | F | CONSTRUCTED | CONSTRUCTED | E |
| NON_FACTUAL | HUMAN | T | T | CONSTRUCTED | CONSTRUCTED | E |
| NON_FACTUAL | GENERATED | F | F | CONSTRUCTED | CONSTRUCTED | E |
| NON_FACTUAL | GENERATED | F | T | CONSTRUCTED | CONSTRUCTED | E |
| NON_FACTUAL | GENERATED | T | F | CONSTRUCTED | CONSTRUCTED | E |
| NON_FACTUAL | GENERATED | T | T | CONSTRUCTED | CONSTRUCTED | E |
| NON_FACTUAL | NONE | F | F | ABSTAIN | ABSTAIN | 材料なし |
| NON_FACTUAL | NONE | F | T | ABSTAIN | ABSTAIN | 材料なし |
| NON_FACTUAL | NONE | T | F | ABSTAIN | ABSTAIN | 材料なし |
| NON_FACTUAL | NONE | T | T | ABSTAIN | ABSTAIN | 材料なし |

- 「1 対 1」は、24 の鍵のどれもがちょうど 1 つの結果（の組）に写り、鍵はこの 24 だけ、と読む（P1）。表に無い入力は `ABSTAIN`（`in_table = false`）。
- 依頼の種類は閉じた 5 種 `factual / creative / paraphrase / style / example`。`factual` だけが `FACTUAL`、ほかの 4 つは `NON_FACTUAL`。
- 表の根拠の鍵は `HUMAN / GENERATED / NONE` の 3 つ。人と生成が両方ある `MIXED` は表に無い（`ABSTAIN`、理由 `BASIS_MIXED_NOT_IN_TABLE`）。
- 参考欄 `reference_generated` は、`show_reference` が真なら結果に関係なく出す（空なら `[]` と `reference_state`）。偽なら鍵ごと出さない。これは表の分岐ではなく表示の規則。
- 分岐は表だけ。`decide` は表を引くだけで、結果を `if` の連鎖で決めない。

## 3. 根拠の分類 `classify_sources(sources)`（上から順に最初に当たったもの）

1. dict でない → `unreadable`（数える。根拠に数えない）
2. `origin == "generated"` → `generated`
3. `origin == "human_confirmed"` → `human`
4. `origin` の鍵があり値が `None` 以外（`constructed`・`testimony`・未知の文字列）→ `non_evidence`（値ごとに数える。根拠に数えない）
5. `family == "user"` → `request_text`（依頼文そのものの引用。数えて除く）
6. それ以外 → `human`

`basis`: human が 1 以上かつ generated が 0 → `HUMAN`、generated が 1 以上かつ human が 0 → `GENERATED`、両方 1 以上 → `MIXED`、両方 0 → `NONE`。
`cited = human + generated + non_evidence + unreadable`（依頼文を除いた出典の数）。`counts` は全部の分類の数を出す（0 も出す）。

## 4. 結果ごとの出力の形（`vera ask` の入口）

| 結果 | 出力 |
|---|---|
| ANSWER_HUMAN_BASIS（元の答え） | 元の dict そのまま＋`basis_policy` |
| ANSWER_HUMAN_BASIS（記録由来） | 新しい dict: `kind:"answer"`, `verdict:"ANSWER"`, `text: claim`, `values:[claim]`, `evidence:[claim]`, `sources:[{"family":"memory_sovereign","source":<event_id>,"text":claim,"origin":"human_confirmed","store_id","confirm_id"}]`, `door`, `trace`。`basis_origin` は付けない |
| ANSWER_FORM_FROM_GENERATED | 元の dict＋`form_text`＋`form_source:"generated"`＋`form_witnesses`。`sources`・`text` は変えない |
| CONSTRUCTED | 元の dict＋`constructed: true`（`kind`/`verdict` は変えない） |
| CONFIRM_REQUEST | 新しい dict: `kind:"unknown"`, `verdict:"CONFIRM_REQUEST"`, `text`: 問いの文, `sources:[]`, `evidence:[]`, `confirm:{...}`, `withheld:{...}`, `door`, `trace` |
| REFERENCE_GENERATED | 新しい dict: `kind:"unknown"`, `verdict:"UNKNOWN_GENERATED_BASIS_ONLY"`, `sources:[]`, `evidence:[]`, `withheld`, `door`, `trace`（＋参考欄） |
| ABSTAIN（元が棄権） | 元の dict そのまま＋`basis_policy` |
| ABSTAIN（元が答え） | REFERENCE_GENERATED と同じ形で参考欄なし。`verdict` は理由で: 生成だけ `UNKNOWN_GENERATED_BASIS_ONLY`、MIXED `UNKNOWN_BASIS_NOT_IN_TABLE`、いいえ済み `UNKNOWN_GENERATED_REJECTED_BY_USER`、出典が根拠外だけ `UNKNOWN_NO_HUMAN_BASIS`、記録の割れ `AMBIGUOUS_CONFIRMED_RECORDS` |

- 答えを引っ込めた結果は `kind:"unknown"`（`kind:"answer"` を残さない）。
- `withheld = {verdict, kind, door, basis_origin, generated_source_count, families}`。文の本文を入れない。
- 生成文の本文が出てよい場所は `confirm`（D）・`reference_generated`（B が ON）・`form_witnesses`（C）だけ。
- `basis_policy` は結果の最後の鍵。

## 5. D の確認の id

`confirm_id = sha256(json.dumps({"query": query, "claim": claim, "generated": generated}, sort_keys=True, ensure_ascii=False, separators=(",", ":")))` の先頭 24 桁。`claim` は元の結果の `text`、`generated` は元の結果の生成の出典の `(family, source_file, line, sha)` を昇順に並べた列。時刻・乱数・dict の挿入順に依らない。

## 6. C の形の借用の門と決め方

前提: 元の答えの `sources` の文がちょうど 1 種類。人の十字 `H`（`read_events(source_text)`）が `CROSSED`・十字 1・全腕 FILLER・充填物 1 つずつ。検索語は述語の先頭から続く「ひらがなでない文字」の並び（空なら `FORM_NOT_SEARCHED`）。系列は `ability_corpus.FAMILIES` の宣言の順に 1 系列ずつ `limit + 1` 件まで引く。どれかが `limit` を超えたら `FORM_SEARCH_TRUNCATED` で借用全体を中止する。候補 1 行ごとの門（全部通ったものだけ候補。落ちた理由ごとに数える）:

1. `CAND_NOT_ONE_CROSS`: 生成文が `CROSSED`・十字 1・全腕 FILLER・充填物 1 つずつ
2. `CAND_CENTER_DIFFERS`: center の 5 鍵（述語・極性・時制・モダリティ・態）が `H` と一致
3. `CAND_ROLES_DIFFER`: 役割の集合が `H` と同じ（人の出所に無い役割を生成文から足さない）
4. `CAND_FILLER_SPAN_AMBIGUOUS`: 生成側の各充填物の表記が生成文にちょうど 1 回現れ、区間が重ならない
5. 区間で同時に置き換えて `new_text` を作る（`str.replace` を順に使わない）
6. `CAND_REREAD_DIFFERS`: `read_events(new_text)` が十字 1 で、center と「役割 → 充填物の表記」が `H` と一致
7. `CAND_CONTENT_DIFFERS`: 形態素の品詞大分類が `助詞` `助動詞` `補助記号` `記号` `空白` 以外のものの `(pos1, lemma)` の集合が `new_text` と `source_text` で等しい

決め方: 通った候補の `new_text` の異なり数が 1 → 借用、0 → `FORM_NO_CANDIDATE`、2 以上 → `FORM_TIE`（同点は棄権）。
<!-- prereg:end -->

<!-- prereg-w5c:begin -->
# 根拠の方針 — 事前登録の追記（W5-c、攻撃第 3 波の A1・A2）

登録日時: 2026-10-03 19:27:14 +0900
上の節（`prereg:begin` から `prereg:end` まで）は 1 文字も変えない。この節はその **追記** で、`tests/test_basis_policy_w5c.py` を書く前に確定した。24 行の表（節 2）は変えないので `TABLE_VERSION = 1`・`SCHEMA = "verantyx.basis_policy/1"` のまま。変わるのは「根拠の分類の規則」と「確認 id の式」で、これらには表とは別の版を付ける: `CLASSIFY_VERSION = 2`、`CONFIRM_ID_VERSION = 2`。旧版（節 3・節 5）は上に残してある（削除しない）。上の節の「この節を変えるときは `TABLE_VERSION` を上げる」は、表・式・規則を **書き換える** ときの約束。ここでは書き換えず、版の別の定数を付けて追記した。

## W5-c-1. 分類の規則 v2 `classify_sources`（上から順に最初に当たったもの）

閉じた語彙 `DECLARED_ORIGINS = ("generated", "human_confirmed", "constructed", "testimony")`（`origin` に製品が書く値の型の申告。語の一覧ではない）。

1. dict でない → `unreadable`
2. `origin == "generated"` → `generated`
3. `origin == "human_confirmed"` → `human`
4. （新）`family` が `ability_corpus.FAMILIES` のどれかと **文字列として完全一致** し、`origin` が `constructed`・`testimony` でない（鍵なし・`None`・`""`・`"GENERATED"`・未知の値・文字列でない値すべて）→ `unknown_origin`（出所不明。生成とも人とも言わない）
5. `origin` の鍵があり値が `None` 以外 → `non_evidence`（値ごとに数える）
6. `family == "user"` → `request_text`
7. それ以外 → `human`

`FAMILIES` は import して参照する（写さない。系列名の大文字・空白の揺れを直す処理は足さない）。

別の述語 `_unknown_value(src)`: dict で、`origin` が `None` 以外かつ `DECLARED_ORIGINS` の外（文字列でない値も外）。規則 5 で `non_evidence` に数えた出典のうち、値が閉じた語彙の外のものを数える。

数え方:
- 規則 4 は `SourceClass.unknown_origin`（数）と `unknown_origin_by_family`（系列ごと）に数える。`counts`（5 鍵: `human / generated / non_evidence / request_text / unreadable`）には **入れない**（鍵の集合は変えない）。`cited` には足す（足さないと出典なしとして素通しになる）。
- `_unknown_value` が真の出典は、従来どおり `counts["non_evidence"]`・`non_evidence_by_origin` に数え、加えて `unknown_origin_values`（値ごと）に写す。
- `SourceClass.basis`: 規則 4 が 1 つ以上なら `"UNKNOWN_ORIGIN"`。それ以外は従来（`HUMAN / GENERATED / MIXED / NONE`。`_unknown_value` だけでは `basis` を変えない）。
- 方針が使う根拠 `policy_basis`: 規則 4 が 1 つ以上、または `_unknown_value` が真の出典が 1 つ以上なら `"UNKNOWN_ORIGIN"`、それ以外は `basis`。

## W5-c-2. `UNKNOWN_ORIGIN` の列（表の外の扱い。24 行の表には足さない）

`decide` は根拠 `"UNKNOWN_ORIGIN"` を受ける。表を引かず、次のとおり決める（`MIXED` と同じ「表に無い根拠」の扱い）。`"UNKNOWN"` など他の不正な根拠は従来どおり `NOT_IN_TABLE:basis`。

| 依頼の類 | 根拠 | 人が居る | 参考 ON | 結果 | `in_table` | 理由 |
|---|---|---|---|---|---|---|
| 事実の問い（FACTUAL） | UNKNOWN_ORIGIN | 偽・真のどちらでも | 偽・真のどちらでも | ABSTAIN | 偽 | `NOT_IN_TABLE:UNKNOWN_ORIGIN_SOURCE` |
| 事実を主張しない依頼（NON_FACTUAL） | UNKNOWN_ORIGIN | 偽・真のどちらでも | 偽・真のどちらでも | 表の `GENERATED` の行の結果（`CONSTRUCTED`） | 偽 | `UNKNOWN_ORIGIN_READ_AS_GENERATED` |

- 事実の問いでは、人が居ても `CONFIRM_REQUEST` を出さず、参考 ON でも `REFERENCE_GENERATED` にしない。出所の分からない文を「生成コーパスにはこうある」と言えないため（中身が生成とも限らない）。
- 事実を主張しない依頼では、チケットの「生成と同じ側」に従う（材料としてのみ。型は `constructed`）。
- 参考欄・`confirm` の生成文・`_generated_sources` は `origin == "generated"` だけ（出所不明の文は出さない）。

## W5-c-3. 出力

- 事実の問いで出所不明の答えを引っ込めた結果: `kind: "unknown"`、`verdict: "UNKNOWN_ORIGIN_SOURCE"`、`text`: 定型文（`出所の分からない出典があるため、答えません。`）、`sources: []`、`evidence: []`、`withheld`、`door`、`trace`。
- 棄権の結果が出所不明の出典を持つとき: 生成の出典を持つときと同じく本文を落として組み直す。元の `text` が出所不明の出典の本文を引用していれば、定型文に置き換える。
- 根拠が出所不明のとき、ソブリンの はい の記録で `HUMAN` に格上げしない（格上げは従来どおり `GENERATED`・`NONE` のときだけ）。
- 出所不明の結果に `--confirm` を付けると、確認 id が存在しないので `UNKNOWN_CONFIRM_ID`（何も書かない、終了コード 1）。

## W5-c-4. 確認 id v2 と宛先の束縛

- `confirm_id = sha256(json.dumps({"query", "claim", "generated", "destination"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")))` の先頭 24 桁。`destination = {"store_id", "structure_ref"}`（`structure_ref` は宛先のソブリンがある root の構造の台帳の最初の行から決まる、決定的で動かない識別子）。宛先が無いときは鍵 `destination` を **入れない**（W6-a の式と同じ値になる）。桁数は 24 のまま。
- 宛先を持つのは、確認の時点でソブリンが `ACTIVE_CONSENTED` か `ACTIVE_NO_CONSENT` のときだけ。それ以外（ソブリン無し・設定が半端・DETACHED・読めない）は宛先なし。
- 問い返しは何も書かない（台帳を作らない）。確認要求の「どこに出したか」は、(1) id の入力、(2) 保存するときの記録の payload の `destination`（追記専用の `event_log` に残る）、(3) ソブリンの口が自分以外の `destination` を拒むこと、で持つ。
- `--confirm ID yes|no` の判定の順（最初に当たったもので終わる。どれも書かない点は同じ。書くのは最後だけ）:
  1. いまの問いに確認 id が無い（根拠が `GENERATED` でない、または本文が無い）→ `UNKNOWN_CONFIRM_ID`、rc 1
  2. 渡された id が、いまの問いで作りうる id（宛先の候補: いまの宛先・宛先なし・いまの root に登録された全ストア × その root の `structure_ref`）のどれとも一致しない → `UNKNOWN_CONFIRM_ID`、rc 1（別の root の id は宛先を特定できないのでここに入る。分からないことを「別の宛先」と言わない）。2 つ以上の別の宛先に一致したら `UNKNOWN_CONFIRM_ID`（同点は棄権）
  3. いまのソブリンが `ACTIVE_*` でない → 従来の `CONFIRM_REQUEST`、rc 1
  4. いまのソブリンが `ACTIVE_NO_CONSENT` → `NO_CONSENT`、rc 1（口は呼ばない）
  5. 一致した宛先がいまの宛先でない → `CONFIRM_TARGET_MISMATCH`、rc 1
  6. 書く（`CONFIRMED_HUMAN_RECORD` か `REJECTED_GENERATED_RECORDED`、rc 0）。記録の payload に `destination` を入れる
- 3・4 を 5 より先にするのは、既存の期待（`tests/test_basis_policy_entry.py`・`tests/test_basis_policy_confirm.py`）が固定しているため。

## W5-c-5. ソブリンの口の検査

`append_basis_confirmation` は、同意の検査と形の検査の後、書く前に、payload に鍵 `destination` があれば: `Mapping` で鍵がちょうど `{"store_id", "structure_ref"}` でなければ `BAD_PAYLOAD`、自分（`store_id` と、その root の `structure_ref`）と等しくなければ `CONFIRM_TARGET_MISMATCH`（何も書かない）。`destination` の無い payload は従来どおり受ける。宛先を読む 2 つの口は構造の台帳を **読み取り専用** で開き、台帳が無い root に何も作らない。

## W5-c-6. 版

`TABLE_VERSION = 1`（変えない）、`SCHEMA`（変えない）、`CLASSIFY_VERSION = 2`、`CONFIRM_ID_VERSION = 2`。`basis_policy` の注記に `classify_version`・`confirm_id_version` を足す。
<!-- prereg-w5c:end -->

<!-- prereg-w5c-r3:begin -->
# 根拠の方針 — 事前登録の追記（W5-c 第 3 ラウンド、監査役の判断の反映）

登録日時: 2026-10-03 21:07:31 +0900
監査役の判断の日時: 2026-10-03 20:40（チケットの末尾の節「監査役の判断」。第 2 ラウンドの申し送りへの回答）。
この節は `tests/test_basis_policy_w5c_r3.py` を書く前、既存テストを改訂する前、製品コードを直す前に確定した。上の 2 つの節（`prereg:begin`〜`prereg:end` と `prereg-w5c:begin`〜`prereg-w5c:end`）は 1 文字も変えない。**W5-c-1 の規則 7 と W5-c-3 の 3 つ目の項目（記録による格上げ）は、この節で置き換える。** 置き換えない部分（規則 1〜6、W5-c-2 の `UNKNOWN_ORIGIN` の列、W5-c-4 の確認 id v2、W5-c-5）は今も有効。

## W5-c-r3-1. 分類の規則 v3 `classify_sources`（上から順に最初に当たったもの）

入力に 1 つ増える: `user_documents`（真偽）。`apply_to_ask` は `mode == "round5"` かつ `documents` が空でないときだけ真にする（ファイル名の照合はしない。`classify_sources` 単独の呼び出しの既定は偽）。

1. dict でない → `unreadable`
2. `origin == "generated"` → `generated`
3. `origin == "human_confirmed"` → `human`
4. `family` が `ability_corpus.FAMILIES` のどれかと文字列として完全一致し、`origin` が `constructed`・`testimony` でない → `unknown_origin`（W5-c-1 の規則 4 のまま）
5. `origin` の鍵があり値が `None` 以外 → `non_evidence`（W5-c-1 の規則 5 のまま）
6. `family == "user"` → `request_text`（W5-c-1 の規則 6 のまま。依頼文は `cited` に入れない）
7. （新）`user_documents` が真で `family == "document"`（完全一致）→ `human`。ここに来るのは `origin` が鍵なしか `None` のものだけ（`origin` に値があれば規則 5 まで）
8. （変更。W5-c-1 の規則 7 の「それ以外 → `human`」を置き換える）それ以外 → `unknown_origin`（欠落・`None` の `origin` で、規則 4 の系列でも `family: "user"` でも、利用者がこの呼び出しで渡した文書でもないもの。系列の鍵が無い・文字列でない出典も含む）

理由: 原則「分からないことと偽であることを混ぜない。出所の分からない出典は人が書いたものではない」を、索引の系列でない出典にも当てる。人の出典は、`origin` が明示的に人の値（今は `human_confirmed` だけ）のときか、`family == "user"` と、利用者がこの呼び出しで渡した文書だけ。監査役の判断は「`family == "user"`（利用者が渡した文書・会話）」と利用者が渡した文書を人と明記している。製品は利用者の文書の出典を `family: "document"` で出す（`family: "user"` は依頼文の断片）。CLI で `--document` を受けるのは `--mode round5` だけで、その mode の文書は `load_documents(documents)` で渡したものだけなので、「round5 で documents を渡した呼び出しの `family: "document"`」は来歴が分かっている。規則 7 の例外を消すだけで字面どおりに戻る。

数え方（W5-c-1 と同じ。規則 8 は規則 4 と同じ列に数える）: `unknown_origin`（数）と `unknown_origin_by_family`（系列ごと。系列が文字列でなければ `"(none)"`）に数え、`counts` の 5 鍵には入れず、`cited` には足す。`policy_basis` は `unknown_origin` か `unknown_origin_values` が 1 つでもあれば `UNKNOWN_ORIGIN`。

## W5-c-r3-2. 記録による格上げ（W5-c-3 の 3 つ目の項目を置き換える）

ソブリンの はい の記録（`human_confirmed`）で `ANSWER_HUMAN_BASIS` に格上げするのは、**元の結果の根拠が `GENERATED`**（元の結果が棄権でなく、根拠が生成の出典だけ）で、同意ありのソブリンに同じ問いの はい の記録があり、出所不明の出典が混じらない（`UNKNOWN_ORIGIN` でない）ときだけ。元の結果が棄権の場合・出典が無い場合（`NONE`）・`UNKNOWN_ORIGIN` が混じる場合・`MIXED` は格上げしない（元の棄権・素通しのまま。記録は `confirmed_records_not_used` に数える）。判断の「その生成文と確認済みの文が一致するとき」は今回は入れない（記録の claim と今の claim の照合は、既存の `tests/test_basis_policy_confirm.py` の 2 件の期待と衝突するため。判断記録 R3-J5）。

## W5-c-r3-3. 版

`CLASSIFY_VERSION = 3`。`TABLE_VERSION = 1`・`SCHEMA`・`CONFIRM_ID_VERSION = 2` は変えない（表と id の式は変わらない）。格上げの条件の変更に新しい定数は作らない。`basis_policy` の注記の `classify_version` は 3。
<!-- prereg-w5c-r3:end -->

# 根拠の方針（basis policy）

この文書の上の節（prereg）は、テストを書く前に確定した事前登録。下は、実装した形・入口の既定・判断記録・既知の穴・測り方。数値は `artifacts/w6-a/` の出力ファイルを出典にした。

## 1. 目的

生成コーパスの文（`origin == "generated"`。モデルが書いた文で、世界についての証言ではない）が **だけ** 根拠のとき、何を・どの型で利用者に見せるかを、1 か所の型付きの方針にした（`verantyx/basis_policy.py`）。入口 `vera ask` はそれに従う。

実装前の dev では、事実を問う依頼に、生成の文だけを根拠にした `ANSWER` が入口から出た（作り物の索引・「雨の日に傘を持たずに外出すると、どうなりますか？」で `kind: answer`、`verdict: ANSWER`、`basis_origin: generated`。`artifacts/w6-a/before_p2_repro.json`）。実装後は同じ入力が `kind: unknown`、`verdict: UNKNOWN_GENERATED_BASIS_ONLY`、`basis_policy.outcome: ABSTAIN` になる（`artifacts/w6-a/after_p2_repro.json`）。

## 2. 入力と結果の型

- 入力 4 つ: 依頼の種類（`factual` と、事実を主張しない `creative / paraphrase / style / example`）、根拠の出所の集合（`HUMAN / GENERATED / NONE`。両方あるのは `MIXED` で表に無い）、人が居るか、参考の表示の設定。
- 結果は閉じた 6 種: `ANSWER_HUMAN_BASIS / ANSWER_FORM_FROM_GENERATED / CONSTRUCTED / CONFIRM_REQUEST / REFERENCE_GENERATED / ABSTAIN`。
- `decide(request_kind, bases, human_present, show_reference) -> BasisDecision` は表（`TABLE`、24 鍵）を引くだけ。表に無い入力は例外にせず `ABSTAIN`、`in_table = false`、理由 `NOT_IN_TABLE:<何が>`。
- `classify_sources(sources)`: prereg 節 3 の閉じた規則。宣言された `origin` だけを見て、系列名から生成と推測しない。

- **W5-c（根拠 `UNKNOWN_ORIGIN`）**: 入力の根拠には 4 つ目 `UNKNOWN_ORIGIN` がある（出典の `origin` が出所の分かる値でない集合。規則は prereg-w5c 節 W5-c-1）。24 行の表には足さない（`TABLE_VERSION = 1` のまま）。`decide` は小さな別の表 `_UNKNOWN_ORIGIN_COLUMN` を引く: 事実の問いは `ABSTAIN`（`in_table = false`、理由 `NOT_IN_TABLE:UNKNOWN_ORIGIN_SOURCE`。人が居ても `CONFIRM_REQUEST` にならず、参考 ON でも `REFERENCE_GENERATED` にならない）、事実を主張しない依頼は表の `GENERATED` の行（`CONSTRUCTED`、理由 `UNKNOWN_ORIGIN_READ_AS_GENERATED`）。`classify_sources` の規則の版は `CLASSIFY_VERSION = 2`。
- **W5-c（分類 v2 の要点）**: `origin` が `generated`・`human_confirmed` の出典はこれまでどおり。`ability_corpus.FAMILIES`（import して参照）のどれかを `family` に名乗る出典で、`origin` が `constructed`・`testimony` でないもの（鍵なし・`None`・`""`・`"GENERATED"`・未知の値）は `unknown_origin`（人とも生成とも言わない）。索引の系列でない出典で `origin` が閉じた語彙（`generated / human_confirmed / constructed / testimony`）の外のものは `non_evidence`（従来どおり）で、加えて `unknown_origin_values` に写し、方針の根拠は `UNKNOWN_ORIGIN` になる。索引の系列でなく `origin` が欠落・`None` の出典は **従来どおり人**（既知の穴 1）。

## 3. 入口ごとの既定

| 入口 | 依頼の種類 | 参考の表示 | 人が居る | 状態 |
|---|---|---|---|---|
| `vera ask` | `factual`（`--request-kind` で変える） | off（`--show-generated-reference` で on） | 居ない（`--human-present` で居る。`--confirm` は居ることを含む） | 接続済み。legacy・`--engine`・`--mode round5` の 3 経路すべてに 1 回だけ当てる |
| `vera observe`（種の錨） | `creative`（`basis_policy.ENTRY_REQUEST_KIND`） | — | — | **未接続**。`observe.py` は W5-b が変更中。接続は W5-b 統合後の別チケット（判断記録 J13） |

依頼文の読みから種類を決めるのは別チケット（W3-c2 の質問の十字が入ったら、疑問文は factual）。

## 4. 結果ごとの出力の形

prereg 節 4 の表のとおり。要点:

- 答えを引っ込めた結果は `kind: "unknown"` にする（`kind: "answer"` を残すと採点器は answer と読む）。`verdict` と `kind` の両方が棄権側。`vera ask` の終了コードは `--confirm` と引数の誤り以外すべて 0。
- 引っ込めた結果は `sources: []`、`evidence: []`、`withheld`（verdict・kind・door・basis_origin・生成の出典の数・系列）だけを持ち、元の `lines`・`semantic`・`trace` の本文は持ち越さない。`trace` は各項目の `part` と `status` だけ残し、最後に `basis_policy.apply` の 1 項目を足す。
- 生成文の本文が出てよい場所は `confirm`（D）・`reference_generated`（B が ON のとき）・`form_witnesses`（C）だけ。E（`CONSTRUCTED`）は元の結果に `constructed: true` を足すだけなので、元の `sources`・`lines` がそのまま残る。
- `basis_policy` は常に最後の鍵。`schema`・`table_version`・`applied`・`request_kind`・`kind_class`・`basis`・`basis_original`・`human_present`・`show_reference`・`outcome`・`in_table`・`counts`・`sovereign`・`form`（`--confirm` のときは `confirm`）を持つ。
- 出典を 1 つも宣言しない答え（依頼文だけを引く社交・理解など）は適用外として素通しし、`basis_policy.applied: false`、`reason: NO_CITED_SOURCES` を付ける（数えて記録する）。生成の出典を 1 つでも持つ結果は必ず適用される。

- **W5-c（`UNKNOWN_ORIGIN` の出力）**: 事実の問いで出所不明の出典を持つ答えは、`kind: "unknown"`・`verdict: "UNKNOWN_ORIGIN_SOURCE"`・`text: "出所の分からない出典があるため、答えません。"`・`sources: []`・`evidence: []`・`withheld`（`unknown_origin_source_count` を足した）・`door`・`trace`。棄権の結果が出所不明の出典を持つときも、生成の出典のときと同じく本文を落として組み直す（元の `text` が出所不明の出典の本文を引用していれば定型文に置き換える。元の `verdict` は棄権の型なのでそのまま）。`basis_policy.counts` に `unknown_origin`・`unknown_origin_by_family`・`unknown_origin_values` を足し（`counts` の 5 鍵の側は変えない）、注記に `classify_version`・`confirm_id_version` を足す。参考欄・`confirm` は `origin == "generated"` の出典だけを出す（出所不明の文を「生成コーパスにはこうある」と言わない）。

## 5. D: 問い返しと保存の形

- `CONFIRM_REQUEST` は `confirm` を持つ: `id`・`question`・`claim`・`generated_sentences`・`draft_record`・`destination`・`how_to_answer`。
- `confirm.id` は prereg 節 5 の式（時刻・乱数・dict の挿入順に依らない）。保留中の問いはどこにも保存しない。`--confirm <id> yes|no` は同じ問いを同じ入口でもう一度計算し、出る id と一致したときだけ追記する。一致しなければ `UNKNOWN_CONFIRM_ID`（何も書かず、終了コード 1）。
- ソブリンの場所は環境変数 `VERA_SOVEREIGN_ROOT` と `VERA_SOVEREIGN_STORE`（`VERA_P4_INDEX` と同じ流儀）。両方無し `UNKNOWN_NO_SOVEREIGN`、片方 `UNKNOWN_SOVEREIGN_CONFIG_INCOMPLETE`、読めない型はそのまま（`DETACHED`・`UNKNOWN_STORE` など）、同意なし `ACTIVE_NO_CONSENT`。
- 新しい口 `sovereign.append_basis_confirmation(root, store_id, payload)`: 現在の `consent.promote` が真のときだけ `decision` の事件を 1 件追記する（`APPENDED`）。同意が無ければ何も書かない（`NO_CONSENT`）。payload の形が違えば `BAD_PAYLOAD`。
- 記録の payload（全鍵）: `record: "basis_confirmation"`、`status`（`HUMAN_CONFIRMED` か `REJECTED_GENERATED`）、`origin`（はい のときだけ `"human_confirmed"`）、`witness: "user_confirmation"`、`confirm_id`、`query`、`claim`、`generated_sources: [{family, source_id, sha}]`、`table_version`。`phrase`・`cell`・`occupied`・`corrects` は入れない（昇格の候補・訂正にしない）。
- いいえ は削除でなく追記（`REJECTED_GENERATED`）。同じ `confirm_id` の記録が複数あれば seq の最後の 1 件が効く（訂正は前進の追記）。同じ問い（`query` の完全一致。正規化しない）に効いている `HUMAN_CONFIRMED` の `claim` が 2 種類以上なら `AMBIGUOUS_CONFIRMED_RECORDS` で棄権。記録を答えに使うのは、ソブリンが ACTIVE で現在の `consent.promote` が真のときだけ（撤回後は使わない）。
- はい の後の同じ問いは `kind: answer`、`verdict: ANSWER`、`sources[0].origin == "human_confirmed"`（`family: memory_sovereign`）で返り、`basis_origin` は付かない。

- **W5-c（確認 id v2 と宛先）**: `confirm.id` の入力に宛先 `{"store_id", "structure_ref"}`（`structure_ref` はそのソブリンがある root の構造の台帳の最初の行から決まる識別子）を含める（`CONFIRM_ID_VERSION = 2`）。宛先を持つのは、問いを出す時点でソブリンが `ACTIVE_CONSENTED` か `ACTIVE_NO_CONSENT` のときだけで、それ以外は宛先なし（宛先なしの id は W6-a の式と同じ値）。`confirm.destination` は `{state, store_id, structure_ref}`、`draft_record.payload` には `destination` が入る。問い返しは何も書かない（台帳を作らない。判断 J6）。
- **W5-c（`--confirm` の判定の順）**: (1) いまの問いに id が無い → `UNKNOWN_CONFIRM_ID`、(2) 渡された id が、いまの問いで作りうる id（宛先の候補: いまの宛先・宛先なし・いまの root に登録された全ストア）のどれとも一致しない（または 2 つ以上の別の宛先に一致する）→ `UNKNOWN_CONFIRM_ID`（別の root で出した id もここ）、(3) いまのソブリンが ACTIVE でない → `CONFIRM_REQUEST`、(4) 同意なし → `NO_CONSENT`（口は呼ばない）、(5) 一致した宛先がいまの宛先でない → `CONFIRM_TARGET_MISMATCH`（rc 1、何も書かない。出力は `confirm.issued_for`・`confirm.destination` に両方の宛先）、(6) 書く（記録の payload に `destination` を入れる）。どれも書かないのは (6) 以外。
- **W5-c（口の検査）**: `sovereign.append_basis_confirmation` は、同意と形の検査の後、payload に `destination` があれば `Mapping` で鍵がちょうど `{"store_id", "structure_ref"}` であること（でなければ `BAD_PAYLOAD`）と、自分の宛先（`sovereign.basis_confirmation_destination`）と等しいこと（でなければ `CONFIRM_TARGET_MISMATCH`、`expected`・`given` を返す）を確かめる。`destination` の無い payload は従来どおり受ける。宛先を読む口 2 つ（`basis_confirmation_destination`・`basis_confirmation_store_ids`）は構造の台帳を読み取り専用で開き、何も作らない。

## 6. B: 参考欄の制限

- 既定は OFF。`--show-generated-reference` のときだけ、`reference_generated: [{text, family, source_id, model, effort, rejected_by_user}]` と `reference_state`（`FOUND` / `NO_GENERATED_SOURCES`）を別の鍵で出す。出すのは元の結果が引いた生成の出典だけで、新しく索引を引かない。
- 記憶・索引・指揮者の判断には使わない。ON でも `--store`・索引・ソブリンのファイルの一覧と sha256 は実行前後で同じ（`tests/test_basis_policy_entry.py`）。
- `model` と `effort` は行にも索引の meta にも記録が無いので、`UNKNOWN_NOT_RECORDED` と型で書く（推測の値は書かない）。利用者が いいえ と言った文は消さず `rejected_by_user: true` を付ける。

## 7. C: 形の借用の門と限界

- prereg 節 6 の門 7 つ。落ちた理由ごとに `basis_policy.form.reasons` に数える。人の出所に無い役割の充填物は回答文に入らない（役割の集合が同じものだけを借りる）。
- 置き換えは区間で同時に行う（`次郎→花子` と `花子→太郎` が連鎖しない）。借りた文は `read_events` で読み直して中身を照合する。
- 出力は `text`（検証済みの値）と `sources` を変えず、`form_text`・`form_source: "generated"`・`form_witnesses` を足す。`form_witnesses` は内容の出典ではないので `sources` に入らず、`basis_origin` も付かない。
- 初期版は `vera ask --mode round5 --document` の回答だけ。ほかの経路は `form.state = NOT_ATTEMPTED_ROUTE`。検索のどれかが `limit`（200）を超えたら `FORM_SEARCH_TRUNCATED` で借用全体を中止する。

## 8. 測り方（監査役向け）

- 新しい分類: 事実の問いで、生成だけが根拠のとき `ANSWER` が出たら誤答。人が居る場面では `verdict == "CONFIRM_REQUEST"` が正解の型。
- 採点器の現行の状態写像（`docs/BANK_SCORE.md` §3）では、`kind: unknown` の `CONFIRM_REQUEST` は abstain になる。問い返しの率は `basis_policy.outcome` を数えること。
- 事実の問いで `basis_policy.outcome` が `ANSWER_` で始まるのは、人が書いた出所（`HUMAN`）か、人が はい と答えた記録のときだけ。
- P6（隠しバンク B7 と、B1・B2・B5 の誤答 0 の維持）は監査役が測る。実装役は開いていない・測っていない。

## 9. 実行結果（出典: `artifacts/w6-a/`）

| 受入基準 | 結果 | 出力ファイル |
|---|---|---|
| P1（表 24 組・表外 ABSTAIN・文書の表との一致） | 35 件成功 | `p1_pytest.txt` |
| P2・P5・E（入口） | 1086 件成功（`main()` 4 通りのフラグ × ソブリン有無、subprocess、合成の結果、索引なしの素通し、参考欄、E、第 2 ラウンドの片方だけ棄権側の型 × 出典の形 × mode 3 × 人 × 参考・採点器の状態 `_state`） | `p2_p5_pytest.txt` |
| P3（借用の中身の照合・負の例） | 29 件成功 | `p3_pytest.txt` |
| P4（はい／いいえ／同意なし／ソブリンなし／撤回／割れ） | 30 件成功 | `p4_pytest.txt` |
| item 6（指揮者・経路づけ） | 41 件成功 | `item6_pytest.txt` |
| 関係する既存テスト | 変更前 455 件成功（`before_related.txt`）、変更後 454 件成功・1 件失敗（`after_related.txt`。失敗は `test_s6_…`。下記） | `before_related.txt`, `after_related.txt` |
| P7（全体） | 116 件失敗・10,210 件成功（第 2 ラウンドの再実行。第 1 ラウンドは 9,690 件）（`pytest_full.txt`）。基線 114 件に対する新しい失敗は 2 件（`pytest_new_failures.txt`）: `test_s6_two_runs_agree_except_timing_and_recount_matches`（`verantyx/` に未コミットの変更がある間だけ落ちる環境由来）と `test_p4_abilities::test_speech_act_drafts_fill_new_roles_and_reread`（基線のコミット 2732274 を取り出しただけの木でも落ちる: `speech_act_on_base_tree.txt`。チケットが環境由来と明記）。どちらも方針の変更と無関係 | `pytest_full.txt`, `pytest_failures.txt`, `pytest_new_failures.txt` |
| 決め打ち検査 | 固有名・数値・英語名の欄は空（追加行のうち追跡対象の変更分 75 行。新規ファイルは `git diff` に入らない） | `check_hardcode.txt` |
| P2 の再現（変更前に破れ、変更後に塞がる） | 変更前: `kind: answer`・`verdict: ANSWER`・`basis_origin: generated`。変更後: `kind: unknown`・`UNKNOWN_GENERATED_BASIS_ONLY`・`outcome: ABSTAIN` | `before_p2_repro.json`, `after_p2_repro.json` |
| 入口の実演 | ABSTAIN → 参考 → 問い返し → はい → 同じ問いが `ANSWER_HUMAN_BASIS` → 同意なしで `NO_CONSENT` → E → round5＋文書の C | `cli_demo.txt` |
| 素通し・壁時計の確認 | 出典を引かない社交 2 件は `applied: false` で `basis_policy` 以外は元と同じ。出典を引かない棄権 2 件は `applied: true`・`ABSTAIN` で同じく元と同じ。同じ文書の問いを 2 回実行して違うのは `elapsed_ms`・`ingest_ms` の 2 欄だけ | `passthrough_and_clock_check.txt` |
| 事前登録の順序 | 事前登録（`prereg.txt`）がどのテストファイルの作成時刻より前 | `prereg_order.txt`, `frozen_tests.sha256` |

### W5-c の実行結果（出典: `artifacts/w5-c/`）

| 受入基準 | 結果 | 出力ファイル |
|---|---|---|
| N1 攻撃テスト 33 件 | 基点 25 件失敗・8 件成功 → 33 件成功。写しの 2 行目以降の sha256 は攻撃役が凍結した値（`3b355b5d…e2f3`）と一致 | `attack_before.txt`, `n1_attack_after.txt`, `n1_attack_copy_sha.txt` |
| N1 出所不明の全組合せ（実装役のテスト） | 197 件成功。系列 9 × `origin` 7 通り × 元の結果の型 8 × mode 3 × 人 2 × 参考 2 × 同伴 4 = 24,192 の組合せを 63 本の中で流し、どれも `ANSWER_*`・`CONFIRM_REQUEST` が出ず、採点器の状態は abstain | `n1_tests_after.txt` |
| N2 確認 id の宛先の束縛 | 26 件成功（別のストア・宛先なし・別の root・DETACHED・同意なし・正しい宛先・口の直接の検査・`main()` の入口） | `n2_tests_after.txt` |
| 新しいテスト全体（`tests/test_basis_policy_w5c.py`） | 実装前 288 件失敗・7 件成功 → 295 件成功（実装前に通った 7 件は基点で既に成り立つ性質: 一覧は `w5c_tests_before_passed.txt`） | `w5c_tests_before.txt`, `w5c_tests_after.txt`, `frozen_tests.sha256` |
| N3 既存の `tests/test_basis_policy*.py` 5 本 | 1221 件成功。基点との差分（`git diff --stat`）は 0 | `n3_existing_after.txt`, `n3_existing_diffstat.txt` |
| ソブリンのテスト 7 本 | 178 件成功（基点と同数） | `n3_sovereign_after.txt` |
| N4 全体 | 116 件失敗・10,977 件成功・37 件 skip・75 xfailed・75 xpassed（308.56 秒。第 3 ラウンドの全体テスト。`after_pytest.txt` の最後の行）。基線 114 件に対し、新しい失敗は 2 件（`new_failures.txt`）で、どちらも環境由来: `test_s6_two_runs_agree_except_timing_and_recount_matches`（`verantyx/` に未コミットの変更がある間だけ落ちる）と `test_speech_act_drafts_fill_new_roles_and_reread`（基点の木でも落ちる: `speech_act_on_base_tree.txt`）。基線から直った失敗は 0 件 | `after_pytest.txt`, `after_failures.txt`, `new_failures.txt`, `fixed_failures.txt` |
| 採点器の見本 B2（25 問） | 前後とも `over_abstain=17 correct_abstain=6 unreachable=2 wrong=0 correct=0`。`compare` はバイトで 24 件不一致（`elapsed_ms` と、`basis_policy` の注記に W5-c が足した鍵のため）、時計と追加の鍵を除いて比べると差 0 | `bs_B2_before.txt`, `bs_B2_after.txt`, `bs_B2_compare.txt`, `bs_B2_semantic_compare.txt` |
| 入口の実演（subprocess） | `UNKNOWN_ORIGIN_SOURCE`（NULL の索引。3 通りのフラグ: 無し・`--human-present`・`--human-present --show-generated-reference`。ほかに `--request-kind creative` が `CONSTRUCTED`）・`CONFIRM_TARGET_MISMATCH`（rc 1、ファイルの変化 0）・`CONFIRMED_HUMAN_RECORD`（正しい宛先、rc 0）・同じ問いが `ANSWER_HUMAN_BASIS` | `cli_demo.txt` |
| W5-a の 3 文 | 基点 `2732274^` で 3 文とも読めていた。今は 3 文とも `AGENT_EVIDENCE_MISSING` で棄権（コードは変えていない） | `w5a_k64_three.txt`, `w5a_r4_attack.txt` |
| 挙動が変わる入口 | 採点器の見本 B2 は変化なし。CLI の入口（legacy・`--mode round5`）に挨拶 4 文を流した出力は、基点と今で `basis_policy` 注記の新しい鍵（`classify_version`・`confirm_id_version`・`counts.unknown_origin*`）を除いて同じ（8 件中 8 件。`greeting_entrances.txt`）。規則で作る社交の返事（`round3.py` の `_social_frame`）の出力を `apply_to_ask` に直接通すと `ANSWER_HUMAN_BASIS` から `UNKNOWN_ORIGIN_SOURCE` に変わる（F1。`round3_social_frame_probe.txt`）が、方針を当てる CLI の入口からこの関数には届かない（F1 の本文）。`build/round3` のある環境の入口は `UNMEASURED_NO_ROUND3_BUILD` | `bs_B2_semantic_compare.txt`, `greeting_entrances.txt`, `round3_social_frame_probe.txt`, `families_literal_sites.txt`, `unmarked_family_sites.txt` |
| 決め打ち検査 | 製品の追加行に攻撃テストの入力・id は無い（空） | `check_hardcode.txt` |
| 事前登録の順序 | 事前登録 2026-10-03 19:27:14 +0900 が、新しいテストの凍結 19:30:01 より前 | `prereg.txt`, `frozen_tests.sha256` |

### W5-c 第 3 ラウンドの実行結果（出典: `artifacts/w5-c/`。第 2 ラウンドの表の値のうち第 3 ラウンドで変わるのは「挙動が変わる入口」「入口の実演」「棄権・出典なしの結果の記録による格上げ」で、他は同じ件数で通る。第 2 ラウンドの行は消していない）

| 受入基準・項目 | 結果 | 出力ファイル |
|---|---|---|
| 開始時（今の木・第 2 ラウンドの実装） | 6 本（table・w5c・entry・confirm・form・conductor）＋ `tests/test_one_request_goal_route.py` の 7 ファイルで 1,529 件成功。ツリーの状態の sha1 は指示書の `99ed76e7…53c8` と一致。隔離（読み込まれた `verantyx*`・`tools*` が木の外のもの）は `[]` | `r3_start_tests.txt`, `r3_status_start.txt`, `r3_isolation.txt` |
| 事前登録の順序 | 事前登録 2026-10-03 21:07:31 +0900（節の取り出しの記録は 21:07:58）→ 新しいテストの凍結 21:09:48（`EXTENDED`）→ 既存テストの改訂 21:10:55（`AMENDED`）→ 製品コードの変更（`basis_policy.py` の変更はこの後）。prereg 節の sha1 は基点と同じ `1e948526…ab66`、prereg-w5c 節は書き換えていない。節を足した時点の削除行は 0 | `r3_prereg.txt`, `frozen_tests.sha256` |
| R-a・R-b の新しいテスト（`tests/test_basis_policy_w5c_r3.py`） | 実装前 128 件失敗・10 件成功 → 138 件成功。実装前に通った 10 件は基点で既に成り立つ性質（利用者の文書の答え・生成の答えの記録による格上げ・組合せの数の足し算・`main()` の利用者の文書の答え。一覧は `r3_tests_before_passed.txt`）。凍結の後に補助関数 `_family_key` の誤りを 1 つ直した（`AMENDED` 行、R3-E3） | `r3_tests_before.txt`, `r3_tests_before_passed.txt`, `r3_tests_after.txt`, `frozen_tests.sha256` |
| 既存テストの改訂（実装前） | W6-a の 7 関数（11 件の test id）と W5-c の 5 関数を改訂。改訂後の 4 ファイルを実装前に流して 6 件失敗・1,439 件成功（失敗は (ii) の 2 関数と w5c の 4 関数。R3-E2） | `r3_revised_tests_before.txt`, `r3_revised_tests_after.txt`, `r3_revised_tests.sha256`, `r3_revised_before_impl.txt` |
| N1 攻撃テスト 33 件 | 33 件成功。写しの 2 行目以降の sha256 は `3b355b5d…e2f3` のまま | `n1_attack_after.txt` |
| N1 実装役のテスト | `tests/test_basis_policy_w5c.py` 295 件成功（`-k n1_` 197 件、`-k n2_` 26 件）。`tests/test_basis_policy_w5c_r3.py` 138 件成功。規則 8 の出典（系列 12 通り × `origin` 鍵なし・`None`）の入口の関数の組合せは 11,360（`family` が `document` のときは round5・documents ありの 80 通りを別の関数で確かめる） | `w5c_tests_after.txt`, `n1_tests_after.txt`, `n2_tests_after.txt`, `r3_tests_after.txt` |
| N1 合成（`scripts/r3_synth.py`。ソブリン 4 状態を含む） | 系列 19（索引の 9 ＋ `document`・`general`・`x`・`jawiki`・`conversation_form`・`code_parts`・`pun_lexicon`・`user`・鍵なし・`3`）× `origin` 6（鍵なし・`None`・`""`・`"zzz"`・`"human"`・`3`）× 元の型 5 × mode 3 × documents 2 × 人 2 × 参考 2 × 同伴 4 × ソブリン 4（無し・同意あり・同意あり＋同じ問いの はい の記録・同意なし）= 218,880 組合せ。出所不明の出典を持つ組合せ（スクリプトの中の独立した定義）214,400 はすべて `ABSTAIN`。`ANSWER_*`・`CONFIRM_REQUEST`・`REFERENCE_GENERATED`・素通し・出典の残り・確認の欄・記録の文の漏れ・入力の変更・ソブリンのファイルの変化（3 つのソブリンの全ファイルの sha256）は 0。出所不明を持たない 4,480 組合せの `ANSWER_HUMAN_BASIS` 1,008 は、依頼文・`human_confirmed` の同伴、利用者の文書（round5＋documents＋`family: "document"`）、同意あり＋はい の記録＋生成の同伴のどれかで説明がつく（説明のつかないもの 0） | `r3_synth.txt` |
| N2 | 第 2 ラウンドの `n2_` 26 件が変わらず成功（`sovereign.py`・`cli.py` は変えていない: `git diff 6d20016 --stat` で `sovereign.py` 44 行・`cli.py` なし・`READING_SOUNDNESS.md` 1 行は第 2 ラウンドと同じ）。`n2_check.py` の流し直しは中間職のレビューで行う | `n2_tests_after.txt` |
| N3 既存 5 本 | 1,221 件成功（件数は基点と同じ）。`git diff 6d20016 --stat` は `test_basis_policy_confirm.py`・`test_basis_policy_conductor.py`・`test_one_request_goal_route.py` が 0 バイト、`table`・`entry`・`form` の差分は 7 つの hunk（改訂した 7 関数）だけ。ソブリン 7 本 178 件成功、`tests/test_one_request_goal_route.py` 13 件成功 | `n3_existing_after.txt`, `r3_existing_diffstat.txt`, `n3_sovereign_after.txt`, `r3_request_goal_route.txt` |
| N4 全体 | 116 件失敗・10,977 件成功・37 件 skip・75 xfailed・75 xpassed（308.56 秒）。基線 114 件に対し、新しい失敗は 2 件（`new_failures.txt`）で第 2 ラウンドと同じ環境由来の 2 件、基線から直った失敗は 0 件 | `after_pytest.txt`, `after_failures.txt`, `new_failures.txt`, `fixed_failures.txt` |
| R-b 記録による格上げ | `j5_refused_probe.txt`（記録の claim を元の `text` と違う文にした）: 出所不明 3 行は `ABSTAIN`・used 0・not_used 1、生成の `answer/ANSWER` だけ `ANSWER_HUMAN_BASIS`・used 1、生成の棄権 2 行は `ABSTAIN`・used 0・not_used 1。基点との並置（`r3_record_probe.txt`）: 出典なしの `answer/ANSWER` は基点で `ANSWER_HUMAN_BASIS`（記録の文に置き換わる）→ 今は素通し（`applied: false`）、出典なし `unknown/UNKNOWN_X`・生成の `unknown/UNKNOWN_X` は基点で `ANSWER_HUMAN_BASIS` → 今は元の棄権のまま、legacy の文書・round5 で documents なしの文書は基点で `ANSWER_HUMAN_BASIS` → 今は `UNKNOWN_ORIGIN_SOURCE`、round5＋documents の文書は変わらず `ANSWER_HUMAN_BASIS` | `j5_refused_probe.txt`, `r3_record_probe.txt` |
| 採点器の見本 B2（25 問）・B3（24 問） | 前後とも B2 は `over_abstain=17 correct_abstain=6 unreachable=2 wrong=0 correct=0`、B3 は `over_abstain=19 correct_abstain=5 wrong=0 correct=0 unreachable=0`。時計の鍵（`elapsed_ms`・`ingest_ms`・`ms`）と W5-c の追加の鍵を除いて比べると、B2・B3 とも差 0（取り除いた鍵の数は `r3_bs_<B>_compare.txt` に出している。B3 の `ms` は両側で 2 か所）。B1 は既定の入口で Vera を呼ばず、B5 は `--frames` が必須で（`docs/BANK_SCORE.md` の入口の表）、どちらも Vera を呼ばないので流していない | `r3_bs_B2_before.txt`, `r3_bs_B2_after.txt`, `r3_bs_B2_compare.txt`, `r3_bs_B3_before.txt`, `r3_bs_B3_after.txt`, `r3_bs_B3_compare.txt` |
| 入口の実演（subprocess） | 基点と今を並べた。(a) round5＋`--document` の文書の答えは `ANSWER_HUMAN_BASIS`（基点と同じ）、(b) 同じ形の文書で `資料の出来事を一文で言い換えてください。` は `PARTIAL`（基点と同じ）、(c) NULL の索引 3 通りのフラグは、基点では `ANSWER_HUMAN_BASIS`（攻撃 A1 の再現）→ 今は `UNKNOWN_ORIGIN_SOURCE` | `r3_cli_demo.txt` |
| 挙動が変わる入口（測ったものだけ） | 測った: B2・B3 の入口（round5＋文書。差 0）、挨拶 4 文 × legacy・round5（8 件中 8 件が `basis_policy` 注記の新しい鍵を除いて同じ）、`tests/test_one_request_goal_route.py` 13 件、全体テスト（新しい失敗は環境由来の 2 件）、上の実演（NULL の索引の legacy `ask`: `ANSWER_HUMAN_BASIS` → `UNKNOWN_ORIGIN_SOURCE`）。`origin` の印を付けずに `family` を書く製品の箇所は 36 か所（うち系列名が索引の系列と同名のもの 4、`family: "user"` 9、`family: "document"` 6）。**どの入口で棄権に変わるかを測っていない箇所は `UNMEASURED_ENTRANCE`**（推定の件数は書かない） | `r3_family_sites.txt`, `r3_greeting_entrances.txt`, `r3_cli_demo.txt` |
| 利用者の文書の例外・記録の照合の代価（スクラッチの写しでの実測） | 例外なし（字面どおり）にすると 13 件失敗: W6-a の 5 件（`test_basis_policy_entry.py` 1・`test_basis_policy_form.py` 4）、W5-c の新しいテスト 7 件、許可パス外の `tests/test_one_request_goal_route.py::test_cli_explicit_round5_document_entry_uses_same_python_route` 1 件。記録の claim の照合（R3-J5）を入れると `tests/test_basis_policy_confirm.py` の 2 件が失敗（ほかは、記録の claim を元の `text` と違う文にした W5-c の新しいテストが落ちる） | `r3_variant_costs.txt` |
| 決め打ち検査 | 製品の追加行に試験の入力・id は無い（空） | `check_hardcode.txt` |

## 10. 判断記録（中間職の指示書 J1〜J13。そのまま実装した）

- **J1（適用点）**: 方針は `basis_policy.py` に置き、`cli.cmd_ask` が 3 つの経路（round5 / `--engine` / legacy）の戻り値すべてに 1 回だけ当てる。`cli.py` の変更は `ask` の parser の 4 引数と `cmd_ask` の配線に限る。チケットの「`cli.py`（`ask` の引数のみ）」を「引数とそれを方針へ渡す `cmd_ask` の配線」と読んだ。
- **J2（semantic.py）**: 変更しない。`semantic.answer` の出典は `origin` を持たず、門は死んだ分岐になる。適用点は J1 の 1 か所。
- **J3（根拠の 3 種）**: 表の根拠は `HUMAN / GENERATED / NONE`。人と生成の両方（`MIXED`）は表に無く `ABSTAIN`（`UNKNOWN_BASIS_NOT_IN_TABLE`）。C の借用文は内容の出典ではなく、C の答えは `HUMAN`。
- **J4（方針の及ぶ範囲）**: 依頼文以外の出典を 1 つも宣言しない（かつ引っ込められていない）答えは適用外として素通しし、`applied: false` を付ける。生成の出典を持つ結果は必ず適用。計算の答えの証人は F（別チケット）。
- **J5（round3 の系列）**: 出所の分類は宣言された `origin` だけを見る。`semantic_qa`（round5・文書なし）の `general_qa / local / pro` の出典が生成物かどうかは印が無く未実測 → 既知の穴 `ORIGIN_UNMARKED_ROUND3_EVIDENCE`。
- **J6（C の出力）**: `text` を変えず `form_text` を足す。借用は `--mode round5` かつ `--document` があり、結果が `ANSWER_HUMAN_BASIS` のときだけ試す。
- **J7（型と終了コード）**: 引っ込めた結果は `kind: "unknown"`、`verdict` は `UNKNOWN_*` / `AMBIGUOUS_*` / `CONFIRM_REQUEST`。終了コードは `--confirm` 以外すべて 0。
- **J8（ソブリンの場所）**: 環境変数 `VERA_SOVEREIGN_ROOT` / `VERA_SOVEREIGN_STORE`。
- **J9（状態を持たない作り）**: 保留中の問いを保存せず、確認のたびに同じ計算をやり直して id の一致で判定する。
- **J10（記録の種類）**: `kind: "decision"`、`payload.record = "basis_confirmation"`。
- **J11（記録の効き方）**: 同じ `confirm_id` は seq の最後が効く。同じ問いに `claim` が 2 種類以上なら棄権。同意の撤回後は記録を使わない。
- **J12（B の中身）**: 元の結果が引いた生成の出典だけ。`model` / `effort` は `UNKNOWN_NOT_RECORDED`。いいえ の文は消さず `rejected_by_user: true`。
- **J13（`vera observe`）**: 定数 `ENTRY_REQUEST_KIND = {"ask": "factual", "observe": "creative"}` を置くだけ。観測の経路への接続は W5-b 統合後の別チケット。

### 実装役が自分で決めたこと

- **E1**: 出典を 1 つも引かない棄権（例: `-5 と 3 の和は？` が `UNKNOWN_COMMONSENSE_NO_STRUCTURE`、`りんごとは何ですか？` が `UNKNOWN_NOT_PRESENT`）は、指示書 §3.4 の 3 のとおり「引っ込められていない」ではないので素通しではなく適用（`applied: true`、`outcome: ABSTAIN`）。辞書は元のまま（`basis_policy` を除いて同じ）。素通しの `applied: false` になるのは、答えとして出る社交（`こんにちは`・`ありがとう。`）などの出典なしの結果。
- **E2**: 出典は最上位の `sources` に加えて、`lines[*].sources` のうち最上位に無いものも集める。`basis_origin: "generated"` を宣言しているのに生成の出典が見えない結果には、見えない生成の出典を 1 つ足して判定する（`(declared basis_origin)`）。生成の根拠が置き場所で見えなくなる抜け道を塞ぐため。
- **E3**（第 2 ラウンドで改訂）: 棄権の結果が生成の出典を持つとき、本文（`lines`・`evidence`・`trace` の詳細・`sources`・`status`）を落として組み直す。組み直す dict の型は **両半分を棄権側に正規化** する: `kind` は元が棄権の種類（`unknown`・`not_yet`・`cannot`・`unreadable`）のときだけそのまま、そうでなければ `unknown`。`verdict` は元が棄権の接頭辞（`UNKNOWN`・`ABSTAIN`・`AMBIGUOUS`・`NOT_IN_DOCS`・`UNCONFIRMED`・`TIED`・`UNGROUNDED`・`DOCUMENT_NOT_SPECIFIED`）で始まるときだけそのまま、そうでなければ方針の理由の `UNKNOWN_*`（`ANSWER`・`CREATED`・`PARTIAL`・`None` は残らない）。片方だけ棄権側の元の結果（例 `kind: answer` ＋ `verdict: UNKNOWN_X`）でも、採点器（`docs/BANK_SCORE.md` §3 は答え側を先に見る）が answer と読む出力は出ない。`_unknown_dict` を通る全経路と `--confirm` の失敗の dict（`kind: unknown`、`verdict` が文字列でないときは `UNKNOWN_CONFIRM_NOT_SAVED`）が同じ規則。不変条件: `basis_policy.outcome` が `ANSWER_*`・`CONSTRUCTED` でなく、元の結果が生成の出典を持つ出力は、`tools.bank_score.adapters._state` が `abstain`（テスト: `tests/test_basis_policy_entry.py` の「round 2」節）。
- **E4**: 問い返しの元の結果に `text`（claim にする文）が無いときは、問い返さず `ABSTAIN`（`basis_policy.downgraded: CONFIRM_NOT_POSSIBLE_NO_CLAIM_TEXT`）。
- **E5**: `append_basis_confirmation` は `phrase`・`cell`・`occupied`・`corrects` を持つ payload を `BAD_PAYLOAD` で断る（昇格の候補・訂正の対象に化けさせない）。
- **E6**: ソブリンを読めないとき、予期しない例外も `UNKNOWN_SOVEREIGN_UNREADABLE`（`detail` に例外の型名）として型で返し、`ask` を落とさない。
- **E7**: `how_to_answer` の問いの部分は `<query>`（実際の問いはシェルの引用が要るので書かない）。id は実際の値。
- **E8**: テストを凍結した後に直したもの: `tests/test_basis_policy_entry.py` で、(1) 2 回の実行で必ず違う壁時計の欄（`ingest_ms`・`elapsed_ms`）を比較から除いた（実測: 同じ入力を 2 回実行すると 2 欄だけが違う）、(2) 出典を引かない棄権は E1 のとおり素通しでなく適用という読みに直した、(3) 場所による抜け道（E2）と読めないソブリン（E6）のテストを足した。凍結と修正の sha256 は `artifacts/w6-a/frozen_tests.sha256`（`AMENDED` / `EXTENDED` の行）。期待値を弱めた修正は無い。
- **E9**（第 2 ラウンド）: 棄権の結果の `text` が生成の出典の本文を含むときは、その `text` を持ち越さず方針の理由の定型文（`_WITHDRAWN_TEXT`）に置き換える（B OFF のとき本文がどこにも出ないことの維持）。含まないときは元の `text` のまま。

### W5-c の判断記録（中間職の指示書 J1〜J13。E1〜E6 は実装役）

W5-c は攻撃第 3 波の命中 2 件（A1: 出典の `origin` の欠落・NULL が生成文を人の根拠にする。A2: 確認 id を別のソブリンへ持ち出せる）を直した。数値は `artifacts/w5-c/` の出力ファイルを出典にした。事前登録は prereg-w5c 節（登録日時 2026-10-03 19:27:14 +0900。新しいテストファイルの凍結 19:30:01 より前: `artifacts/w5-c/prereg.txt`、`artifacts/w5-c/frozen_tests.sha256`）。

- **J1（A1 の範囲）**: `UNKNOWN_ORIGIN` に倒すのは (a) `family` が `ability_corpus.FAMILIES`（import して参照。写さない）のどれかで、`origin` が `generated`・`human_confirmed` 以外の出典、(b) どの系列でも `origin` が `None` 以外で、閉じた語彙 `generated / human_confirmed / constructed / testimony` の外の出典。系列が索引のものでなく `origin` が欠落・`None` の出典は **従来どおり人**（既存テストの期待が固定している。N3。既知の穴 1）。(a) は系列名から生成と推測することではなく、「生成の索引の系列を名乗るのに印が無い」ので人とは言えない、と型で返すだけ。
- **J2（数え方）**: (a) は `SourceClass.unknown_origin`・`unknown_origin_by_family` に数え、`counts`（5 鍵）には入れない。`cited` には足す（足さないと出典なしの素通しになる）。(b) は従来どおり `non_evidence` に数え、加えて `unknown_origin_values`。`SourceClass.basis` は (a) があれば `"UNKNOWN_ORIGIN"`、方針が使う `policy_basis` は (a) か (b) があれば `"UNKNOWN_ORIGIN"`。
- **J3（表との関係）**: 24 行の表は変えない。`decide` は `UNKNOWN_ORIGIN` を別の小さな表で扱う（事実の問いは `ABSTAIN`、事実を主張しない依頼は `GENERATED` の行）。`"UNKNOWN"` など他の不正な値は従来どおり `NOT_IN_TABLE:basis`。
- **J4（出力）**: 事実の問いで出所不明の答えを引っ込めた結果は `UNKNOWN_ORIGIN_SOURCE`。棄権の結果が出所不明の出典を持つときは本文を落として組み直し、元の `text` が本文を引用していれば定型文に置き換える。
- **J5（記録の格上げ）**: 根拠が `UNKNOWN_ORIGIN` のとき、はい の記録で `HUMAN` に格上げしない。
- **J6（台帳）**: 問い返しの時点では何も書かない（`test_no_pending_question_is_stored_anywhere`・`test_p5_no_file_is_written_by_asking…` が固定している）。「どこに出したか」は (1) id の入力、(2) 保存する記録の payload の `destination`（追記専用の `event_log` に残る）、(3) ソブリンの口が自分以外の `destination` を拒むこと、で持つ。`destination` の無い payload は従来どおり受ける（`test_basis_policy_confirm.py` の口の直接の検査）。
- **J7（id の束縛）**: id の入力に宛先 `{"store_id", "structure_ref"}` を足す。宛先を持つのは `ACTIVE_CONSENTED`・`ACTIVE_NO_CONSENT` のときだけ。宛先なしの id は W6-a の式と同じ値（`_confirm_id` の 3 引数の呼び出しが同じ値）。
- **J8（`--confirm` の順）**: prereg-w5c 節 W5-c-4 のとおり。(3)(4) を (5) より先にするのは、既存の期待（`tests/test_basis_policy_entry.py` の同意なしのソブリンで `NO_CONSENT`、`tests/test_basis_policy_confirm.py` の `ACTIVE` でない状態の `confirm.destination.state`）が固定しているため。
- **J9（別 root）**: 別の root で出した id は宛先を特定できないので `UNKNOWN_CONFIRM_ID`。`CONFIRM_TARGET_MISMATCH` は宛先を特定できたときだけ（分からないことを「別の宛先」と言わない）。
- **J10（W5-c 以前の記録）**: 宛先なしの id で保存された いいえ の記録は、宛先つきの id とは一致しないので、もう いいえ済みとして効かない（もう一度問い返す。誤答にならない側）。はい の記録は問い（`query`）で効くので変わらない。
- **J11（版）**: 24 行の表は変わらないので `TABLE_VERSION = 1`・`SCHEMA` は変えない。変わる規則に別の版を付けた: `CLASSIFY_VERSION = 2`・`CONFIRM_ID_VERSION = 2`。prereg 節の本文は 1 文字も変えず（`git diff` の削除行は 0）、その直後に新しい事前登録の節を日時つきで足した。prereg 節の「この節を変えるときは `TABLE_VERSION` を上げる」は表・式・規則の書き換えの約束で、ここでは書き換えず、旧版（節 3・節 5）を残して追記し、別の版の定数を付けた。
- **J12（W5-a の 3 文）**: コードは変えない。`docs/READING_SOUNDNESS.md` K64 の損失の記録に追記した（`artifacts/w5-c/w5a_k64_three.txt`: 基点 `2732274^` で 3 文とも `readable=true`、今は 3 文とも `readable=false`・`AGENT_EVIDENCE_MISSING`。`artifacts/w5-c/w5a_r4_attack.txt`: 攻撃試験は 1 件失敗のまま。誤読ではなく過剰棄権）。
- **J13（`cli.py`）**: 変えなかった（`--confirm` の終了コードは `apply_to_ask` が返す。`git diff` に `verantyx/cli.py` が無い）。
- **E1（実装役。規則 4 の例外）**: 索引の系列を名乗る出典でも、`origin` が `constructed`・`testimony`（宣言された非証拠）のものは `unknown_origin` にせず従来どおり `non_evidence`。出所が分からないのではなく、証拠でないと宣言されているため（指示書の試験 3「`constructed`・`testimony` だけの出典は従来どおり `UNKNOWN_NO_HUMAN_BASIS`」と同じ側）。どちらも事実の問いでは `ABSTAIN` で、安全側の差は無い。
- **E2（実装役）**: `sovereign.basis_confirmation_destination` は、構造の台帳が無い root だけでなく、その root が登録していない `store_id` にも `UnknownStore` を投げる（指示書は台帳が無いときだけ）。登録の無いストアの宛先は意味を持たず、呼び手（`_read_sovereign`・候補の列挙・口）は登録済みのストアしか渡さないので、挙動の差は出ない。
- **E3（実装役）**: 棄権の結果が出所不明の出典を持つとき、本文を落とした定型文の理由を `UNKNOWN_ORIGIN_SOURCE` にした（指示書の規則では `UNKNOWN_NO_HUMAN_BASIS` になる）。元の `verdict` は棄権の型のままなので、見えるのは定型文の文言だけ。
- **E4（実装役）**: `decide` は `SourceClass` を渡されたとき `policy_basis` を読む（`basis` ではなく）。指示書は `decide` に文字列の根拠を渡す形だけを書いていたが、`test_decide_accepts_a_classification_result_as_the_basis` が `SourceClass` を渡す。
- **E5（実装役）**: `unknown_origin_values` は規則 5（`non_evidence`）で数えた出典のうち値が語彙の外のものだけで、規則 4 の出典は `unknown_origin`・`unknown_origin_by_family` にだけ数える（二重に数えない）。
- **E6（実装役）**: 宛先の候補の列挙が完了しなかったとき（`UNKNOWN_CANDIDATES_PARTIAL`・`UNKNOWN_CANDIDATES_UNREADABLE`）、`UNKNOWN_CONFIRM_ID` の出力に `candidates_state` を型で書く。
- **F1（実装役が見つけた挙動の変化。判断でなく発見）**: `verantyx/round3.py` の規則で作る社交の返事（`GeneralRouter._social_frame`。固定の返事で、出典は `family: "conversation"`・`origin` なし）は、基点では `ANSWER_HUMAN_BASIS` で通り、今は `UNKNOWN_ORIGIN_SOURCE` で棄権になる（`artifacts/w5-c/round3_social_frame_probe.txt`: 基点と今の木で同じ関数が作った dict を `apply_to_ask` に通した実測）。`conversation` は `ability_corpus.FAMILIES` の系列名なので、指示書の規則 4 の字面どおりの結果。直すなら上流（`round3.py` が人の出所でない出典に `origin` を付ける）で、許可パス外。ただし **方針を当てる CLI の入口からはこの関数に届かない**（第 1 ラウンドのレビュー M2 で訂正。読んだこと: `apply_to_ask` の呼び手は `verantyx/cli.py` の legacy・`--mode round5`・`--engine` の 3 枝だけ。`GeneralRouter` を作るのは `one.py` の `_round3_answer` だけで、その呼び手は `Vera.ask` の legacy 経路（`one.py:801-812`。経路が `code_qa`・`live` のとき、または `self.general is None or self.round3_root is not None` のとき）と `chat`。`_social_frame` は `GeneralRouter.answer` が社交の経路（`round3.py:27-38`）で呼ぶので、その枝のうち届きうるのは後者（`one.py:811-812`）。`--engine` は `engine_compat=True` で後者に入らない。CLI の legacy は `Vera().load_store(_load(...))` で `general` を `None` にせず（`cli.py:57,313`）`round3_root` も渡さない。`--mode round5` は `Vera.ask` が `_ask_round5` で先に返り、`_round3_answer` を呼ばない（`one.py:785-796`））。測ったこと: `artifacts/w5-c/greeting_entrances.txt`（`scripts/greeting_entrances.py`。採点器と同じ子プロセスの環境で、基点の写しと今の木に `こんにちは`・`ありがとう。`・`さようなら`・`ごめんなさい` を legacy・`--mode round5` で流した 8 件）は、legacy が `kind=social`・`applied=False` の素通し、round5 が `UNKNOWN_SOURCE_ASSET`・`UNKNOWN_UNREAD` の棄権で、基点と今で `basis_policy` 注記の新しい鍵を除いて同じ。`Vera()`（`general=None`）の `ask` は基点でも今でも `_social_frame` の出力（`kind=social`・`ANSWER`・出典の系列 `conversation`/`user`）を返すが、そこには方針が掛からない（同ファイルの最後の 2 行）。`build/round3` がある環境で `GeneralRouter` に届く入口が別にあるかは未測定（`UNMEASURED_NO_ROUND3_BUILD`）。

### W5-c 第 3 ラウンドで改訂したテスト（監査役の判断 2026-10-03 20:40 による。名前は変えず、前後の全文をここに残す）

件数: **W6-a のテスト 7 関数・11 件の test id**（`tests/test_basis_policy_table.py` 4 関数 4 件、`tests/test_basis_policy_entry.py` 2 関数 5 件、`tests/test_basis_policy_form.py` 1 関数 2 件）、**W5-c のテスト 5 関数**（`tests/test_basis_policy_w5c.py`。凍結の sha256 は `artifacts/w5-c/frozen_tests.sha256` の `AMENDED` 行）。これ以外の W6-a のテスト（`tests/test_basis_policy_confirm.py`・`tests/test_basis_policy_conductor.py` は全部、ほか 3 本の残り全部）と `tests/test_one_request_goal_route.py` は 1 文字も変えていない。直し方は 2 種類: (i) その関数の主張（名前）が今も成り立つものは、入力の人の出典を明示の人（`origin: "human_confirmed"`）にして期待は変えない、(ii) 主張そのものが判断で変わったもの（「それ以外は人」「`origin None` は後の規則に落ちて人」）は入力を変えず期待を新しい規則にする。assert は消していない・緩めていない。各関数の改訂の直前の行に、変えた理由の 1 行のコメントを足した（`# W5-c r3（監査役の判断 2026-10-03 20:40）: …`）。前後の全文の抜き出しは `artifacts/w5-c/r3_revised_tests_before.txt`・`r3_revised_tests_after.txt`（4 ファイルの sha256 は `r3_revised_tests.sha256` の `BEFORE`・`AFTER`）。

#### R1. `tests/test_basis_policy_table.py` の `test_decide_accepts_a_classification_result_as_the_basis`

- 直し方: (i) 入力の人の出典を明示の人（`origin: "human_confirmed"`）にし、期待は同じ
- 改訂前（117〜120 行）:

```python
def test_decide_accepts_a_classification_result_as_the_basis():
    sc = bp.classify_sources([{"family": "doc", "text": "x"}])
    assert sc.basis == "HUMAN"
    assert bp.decide("factual", sc, False, False).outcome == "ANSWER_HUMAN_BASIS"
```

- 改訂後（117〜121 行）:

```python
def test_decide_accepts_a_classification_result_as_the_basis():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    sc = bp.classify_sources([{"family": "memory_sovereign", "origin": "human_confirmed", "text": "x"}])
    assert sc.basis == "HUMAN"
    assert bp.decide("factual", sc, False, False).outcome == "ANSWER_HUMAN_BASIS"
```

#### R2. `tests/test_basis_policy_table.py` の `test_rule4_origin_none_falls_through_to_the_later_rules`

- 直し方: (ii) 入力は同じ。期待を新しい規則 8 にした（`origin: None` の `doc` は後の規則に落ちて人、ではなく出所不明）
- 改訂前（153〜155 行）:

```python
def test_rule4_origin_none_falls_through_to_the_later_rules():
    sc = bp.classify_sources([{"origin": None, "family": "user"}, {"origin": None, "family": "doc"}])
    assert sc.counts["request_text"] == 1 and sc.counts["human"] == 1
```

- 改訂後（154〜157 行）:

```python
def test_rule4_origin_none_falls_through_to_the_later_rules():
    sc = bp.classify_sources([{"origin": None, "family": "user"}, {"origin": None, "family": "doc"}])
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力は同じ。later rule の「それ以外」は人でなく出所不明（規則 8）
    assert sc.counts["request_text"] == 1 and sc.counts["human"] == 0 and sc.unknown_origin == 1
```

#### R3. `tests/test_basis_policy_table.py` の `test_rule6_anything_else_is_human`

- 直し方: (ii) 入力は同じ。期待を新しい規則 8 にした（それ以外は人、ではなく出所不明）
- 改訂前（163〜165 行）:

```python
def test_rule6_anything_else_is_human():
    sc = bp.classify_sources([{"family": "document", "source": "memo.txt", "text": "花子は来た。"}])
    assert sc.counts["human"] == 1 and sc.basis == "HUMAN" and sc.cited == 1
```

- 改訂後（165〜168 行）:

```python
def test_rule6_anything_else_is_human():
    sc = bp.classify_sources([{"family": "document", "source": "memo.txt", "text": "花子は来た。"}])
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力は同じ。origin の無い出典は、利用者が渡した文書と分かっていなければ出所不明
    assert sc.counts["human"] == 0 and sc.unknown_origin == 1 and sc.basis == "UNKNOWN_ORIGIN" and sc.cited == 1
```

#### R4. `tests/test_basis_policy_table.py` の `test_human_and_generated_together_is_mixed`

- 直し方: (i) 入力の人の出典を明示の人にし、期待は同じ
- 改訂前（174〜176 行）:

```python
def test_human_and_generated_together_is_mixed():
    sc = bp.classify_sources([{"family": "document"}, {"family": "local", "origin": "generated"}])
    assert sc.basis == "MIXED" and sc.cited == 2
```

- 改訂後（177〜180 行）:

```python
def test_human_and_generated_together_is_mixed():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    sc = bp.classify_sources([{"family": "memory_sovereign", "origin": "human_confirmed"}, {"family": "local", "origin": "generated"}])
    assert sc.basis == "MIXED" and sc.cited == 2
```

#### R5. `tests/test_basis_policy_entry.py` の `test_a_mix_of_human_and_generated_sources_abstains`

- 直し方: (i) 入力の人の出典を明示の人にし、期待は同じ（4 件の test id）
- 改訂前（174〜182 行）:

```python
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_a_mix_of_human_and_generated_sources_abstains(human, ref):
    result = _synthetic("answer", "ANSWER", [HUMAN, GEN])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref),
                              query="q", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_BASIS_NOT_IN_TABLE"
    assert out["basis_policy"]["basis"] == "MIXED" and out["basis_policy"]["in_table"] is False
    assert out["basis_policy"]["outcome"] == "ABSTAIN"
```

- 改訂後（174〜183 行）:

```python
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_a_mix_of_human_and_generated_sources_abstains(human, ref):
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    result = _synthetic("answer", "ANSWER", [{**HUMAN, "origin": "human_confirmed"}, GEN])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref),
                              query="q", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_BASIS_NOT_IN_TABLE"
    assert out["basis_policy"]["basis"] == "MIXED" and out["basis_policy"]["in_table"] is False
    assert out["basis_policy"]["outcome"] == "ABSTAIN"
```

#### R6. `tests/test_basis_policy_entry.py` の `test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note`

- 直し方: (i) 入力の人の出典を明示の人にし、期待は同じ
- 改訂前（201〜205 行）:

```python
def test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note():
    result = _synthetic("answer", "ANSWER", [USER, HUMAN])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert rc == 0 and _without(out, "basis_policy") == result
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["applied"] is True
```

- 改訂後（202〜207 行）:

```python
def test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    result = _synthetic("answer", "ANSWER", [USER, {**HUMAN, "origin": "human_confirmed"}])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert rc == 0 and _without(out, "basis_policy") == result
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["applied"] is True
```

#### R7. `tests/test_basis_policy_form.py` の `test_other_routes_do_not_attempt_the_borrowing`

- 直し方: (i) 入力の人の出典を明示の人にし、期待は同じ（2 件の test id）
- 改訂前（216〜222 行）:

```python
@pytest.mark.parametrize("mode, docs", [("legacy", []), ("round5", [])])
def test_other_routes_do_not_attempt_the_borrowing(tmp_path, monkeypatch, mode, docs):
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    out, _rc = bp.apply_to_ask(_doc_answer(), bp.AskPolicy(), query="q", mode=mode, documents=docs)
    assert "form_text" not in out and out["basis_policy"]["form"]["state"] == "NOT_ATTEMPTED_ROUTE"
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
```

- 改訂後（216〜224 行）:

```python
@pytest.mark.parametrize("mode, docs", [("legacy", []), ("round5", [])])
def test_other_routes_do_not_attempt_the_borrowing(tmp_path, monkeypatch, mode, docs):
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    ans = _doc_answer(); ans["sources"] = [{**s, "origin": "human_confirmed"} for s in ans["sources"]]
    out, _rc = bp.apply_to_ask(ans, bp.AskPolicy(), query="q", mode=mode, documents=docs)
    assert "form_text" not in out and out["basis_policy"]["form"]["state"] == "NOT_ATTEMPTED_ROUTE"
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
```

#### R8. `tests/test_basis_policy_w5c.py` の `test_w5c_the_versions_and_the_table_are_as_registered`

- 直し方: `CLASSIFY_VERSION == 3`
- 改訂前（278〜283 行）:

```python
def test_w5c_the_versions_and_the_table_are_as_registered():
    assert bp.TABLE_VERSION == 1 and bp.SCHEMA == "verantyx.basis_policy/1"
    assert bp.CLASSIFY_VERSION == 2 and bp.CONFIRM_ID_VERSION == 2
    assert len(bp.TABLE) == 24 and bp.BASES == ("HUMAN", "GENERATED", "NONE")
    assert bp.DECLARED_ORIGINS == ("generated", "human_confirmed", "constructed", "testimony")
    assert bp.UNKNOWN_ORIGIN == "UNKNOWN_ORIGIN"
```

- 改訂後（278〜284 行）:

```python
def test_w5c_the_versions_and_the_table_are_as_registered():
    assert bp.TABLE_VERSION == 1 and bp.SCHEMA == "verantyx.basis_policy/1"
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 規則 7・8 が変わったので CLASSIFY_VERSION は 3（prereg-w5c-r3 節）
    assert bp.CLASSIFY_VERSION == 3 and bp.CONFIRM_ID_VERSION == 2
    assert len(bp.TABLE) == 24 and bp.BASES == ("HUMAN", "GENERATED", "NONE")
    assert bp.DECLARED_ORIGINS == ("generated", "human_confirmed", "constructed", "testimony")
    assert bp.UNKNOWN_ORIGIN == "UNKNOWN_ORIGIN"
```

#### R9. `tests/test_basis_policy_w5c.py` の `test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them`

- 直し方: (i) 入力の `HUMAN` を `{**HUMAN, "origin": "human_confirmed"}` にし、期待は同じ
- 改訂前（297〜305 行）:

```python
def test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them():
    sc = bp.classify_sources([_src("local", None), _src("x", "zzz"), GEN, HUMAN, USER, "junk"])
    assert set(sc.counts) == {"human", "generated", "non_evidence", "request_text", "unreadable"}
    assert sc.counts == {"human": 1, "generated": 1, "non_evidence": 1, "request_text": 1, "unreadable": 1}
    assert sc.unknown_origin == 1 and sc.unknown_origin_values == {"zzz": 1}
    assert sc.cited == 5 and sc.policy_basis == "UNKNOWN_ORIGIN" and sc.basis == "UNKNOWN_ORIGIN"
    d = sc.to_dict()
    assert d["unknown_origin"] == 1 and d["unknown_origin_by_family"] == {"local": 1}
    assert d["unknown_origin_values"] == {"zzz": 1}
```

- 改訂後（298〜307 行）:

```python
def test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の HUMAN を明示の人（origin: human_confirmed）にした。期待は同じ
    sc = bp.classify_sources([_src("local", None), _src("x", "zzz"), GEN, {**HUMAN, "origin": "human_confirmed"}, USER, "junk"])
    assert set(sc.counts) == {"human", "generated", "non_evidence", "request_text", "unreadable"}
    assert sc.counts == {"human": 1, "generated": 1, "non_evidence": 1, "request_text": 1, "unreadable": 1}
    assert sc.unknown_origin == 1 and sc.unknown_origin_values == {"zzz": 1}
    assert sc.cited == 5 and sc.policy_basis == "UNKNOWN_ORIGIN" and sc.basis == "UNKNOWN_ORIGIN"
    d = sc.to_dict()
    assert d["unknown_origin"] == 1 and d["unknown_origin_by_family"] == {"local": 1}
    assert d["unknown_origin_values"] == {"zzz": 1}
```

#### R10. `tests/test_basis_policy_w5c.py` の `test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis`

- 直し方: (i) 最後の行の入力を明示の人にし、`[HUMAN]` が `UNKNOWN_ORIGIN` になる assert を 1 行足した（強める側）
- 改訂前（308〜315 行）:

```python
def test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis():
    sc = bp.classify_sources([_src("x", "zzz")])
    assert sc.basis == "NONE" and sc.policy_basis == "UNKNOWN_ORIGIN"
    assert sc.counts["non_evidence"] == 1 and sc.non_evidence_by_origin == {"zzz": 1}
    assert bp.classify_sources([_src("x", "constructed")]).policy_basis == "NONE"
    assert bp.classify_sources([_src("x", "testimony")]).policy_basis == "NONE"
    assert bp.classify_sources([GEN]).policy_basis == "GENERATED"
    assert bp.classify_sources([HUMAN]).policy_basis == "HUMAN"
```

- 改訂後（310〜319 行）:

```python
def test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis():
    sc = bp.classify_sources([_src("x", "zzz")])
    assert sc.basis == "NONE" and sc.policy_basis == "UNKNOWN_ORIGIN"
    assert sc.counts["non_evidence"] == 1 and sc.non_evidence_by_origin == {"zzz": 1}
    assert bp.classify_sources([_src("x", "constructed")]).policy_basis == "NONE"
    assert bp.classify_sources([_src("x", "testimony")]).policy_basis == "NONE"
    assert bp.classify_sources([GEN]).policy_basis == "GENERATED"
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 最後の行の入力を明示の人にした（期待は同じ）。強める側の assert を 1 行足した
    assert bp.classify_sources([{**HUMAN, "origin": "human_confirmed"}]).policy_basis == "HUMAN"
    assert bp.classify_sources([HUMAN]).policy_basis == "UNKNOWN_ORIGIN"
```

#### R11. `tests/test_basis_policy_w5c.py` の `test_w5c_the_policy_note_carries_the_new_versions_and_numbers`

- 直し方: 注記の `classify_version == 3`
- 改訂前（342〜349 行）:

```python
def test_w5c_the_policy_note_carries_the_new_versions_and_numbers():
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src("pro", "")]), bp.AskPolicy(), query="窓は？",
                               mode="legacy", documents=[])
    note = out["basis_policy"]
    assert note["schema"] == "verantyx.basis_policy/1" and note["table_version"] == 1
    assert note["classify_version"] == 2 and note["confirm_id_version"] == 2
    assert note["counts"]["unknown_origin"] == 1 and note["counts"]["unknown_origin_by_family"] == {"pro": 1}
    assert out["withheld"]["unknown_origin_source_count"] == 1
```

- 改訂後（346〜354 行）:

```python
def test_w5c_the_policy_note_carries_the_new_versions_and_numbers():
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src("pro", "")]), bp.AskPolicy(), query="窓は？",
                               mode="legacy", documents=[])
    note = out["basis_policy"]
    assert note["schema"] == "verantyx.basis_policy/1" and note["table_version"] == 1
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 注記の classify_version は 3
    assert note["classify_version"] == 3 and note["confirm_id_version"] == 2
    assert note["counts"]["unknown_origin"] == 1 and note["counts"]["unknown_origin_by_family"] == {"pro": 1}
    assert out["withheld"]["unknown_origin_source_count"] == 1
```

#### R12. `tests/test_basis_policy_w5c.py` の `test_w5c_known_hole_a_source_outside_the_index_families_without_origin_is_still_human`

- 直し方: (ii) 穴が閉じたので期待を反転（名前は変えない）
- 改訂前（352〜357 行）:

```python
def test_w5c_known_hole_a_source_outside_the_index_families_without_origin_is_still_human():
    """Pinned on purpose (docs/BASIS_POLICY.md section 11, hole 1): existing tests fix this reading."""
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [HUMAN]), bp.AskPolicy(), query="窓は？",
                               mode="legacy", documents=[])
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["basis"] == "HUMAN"
    assert bp.classify_sources([{"family": "x", "text": "t"}]).policy_basis == "HUMAN"
```

- 改訂後（357〜365 行）:

```python
def test_w5c_known_hole_a_source_outside_the_index_families_without_origin_is_still_human():
    """Closed in round 3 (docs/BASIS_POLICY.md section 11, hole 1; the auditor's decision of 2026-10-03 20:40):
    a source outside the index families with no origin is an unknown origin, not a human one. The name is kept
    on purpose (the auditor's rule: an existing test's name is never changed; the before/after text is in the docs)."""
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [HUMAN]), bp.AskPolicy(), query="窓は？",
                               mode="legacy", documents=[])
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and out["basis_policy"]["basis"] == "UNKNOWN_ORIGIN"
    assert out["verdict"] == "UNKNOWN_ORIGIN_SOURCE"
    assert bp.classify_sources([{"family": "x", "text": "t"}]).policy_basis == "UNKNOWN_ORIGIN"
```


### W5-c 第 3 ラウンドの判断記録（中間職の指示書 R3-J1〜R3-J9。R3-E は実装役）

監査役の判断（2026-10-03 20:40）と第 2 ラウンドの必須 M1・M2 を反映した。事前登録は prereg-w5c-r3 節（登録日時 2026-10-03 21:07:31 +0900）で、新しいテストの凍結（`EXTENDED`、21:09:48）・既存テストの改訂（`AMENDED`、21:10:55）・製品コードの変更より前: `artifacts/w5-c/r3_prereg.txt`、`artifacts/w5-c/frozen_tests.sha256`。数値は `artifacts/w5-c/` の出力ファイルを出典にした。

- **R3-J1（規則 7 の置き換え。最重要）**: 規則 7「それ以外 → `human`」を **`unknown_origin`**（新しい規則 8）に変えた。例外は 1 つだけ（新しい規則 7）: `apply_to_ask` の `mode == "round5"` かつ `documents` が空でないとき（= 利用者がこの呼び出しで文書を渡した）、`family == "document"` で `origin` が鍵なしか `None` の出典は `human`。理由 1: 監査役の判断は「人の出典は `family == "user"`（利用者が渡した文書・会話）か…」と利用者が渡した文書を人と明記している。製品は利用者の文書の出典を `family: "document"` で出す（`one.py:1180`・`answer.py:1481,1508`・`request_goal_route.py:309`。`family: "user"` は依頼文の断片）。CLI で `--document` を受けるのは `--mode round5` だけで、その mode の文書は渡したものだけなので、来歴が分かっている（出所不明ではない）。理由 2: 例外なしの字面どおりにすると、許可パス外で改訂の許可の外の `tests/test_one_request_goal_route.py::test_cli_explicit_round5_document_entry_uses_same_python_route` が落ち、C（形の借用）が CLI の入口から届かなくなる。範囲の狭さ: legacy・`--engine`・round5 で documents なしの `family: "document"`、`general`・`jawiki`・`conversation_form`・`code_parts`・`pun_lexicon`・系列名の揺れ・系列の鍵なしの出典は `origin` が欠落・`None` なら **すべて出所不明**。`family: "document"` でも `origin` に値（`""`・`"zzz"`・`"human"`・`3`）があれば規則 5（`non_evidence`）で、語彙の外の値は `unknown_origin_values` に数えて `policy_basis = UNKNOWN_ORIGIN`。**字面どおりに戻す方法**: `_class_of` の「`if user_documents and src.get("family") == "document": return "human"`」の 2 行を消す（引数 `user_documents` は残してよい）。そのときの代価の実測は §11（第 3 ラウンドで更新した既知の穴）の (f)。
- **R3-J2（`family == "user"`）**: 従来どおり `request_text`（依頼文。`cited` に入れない）。「利用者が渡した」と「依頼文そのものを事実の根拠に数える」は別の問いで、W6-a の J4・既存テストが固定している。
- **R3-J3（人の `origin` の値）**: 判断が挙げた「枠・利用者の記録」の `origin` の値は製品がまだ一度も書かないので、語彙 `DECLARED_ORIGINS` に名前を作って足していない。人の明示の値は今は `human_confirmed` だけ。上流で値を決めるチケットがその値を事前登録して足す。
- **R3-J4（記録による格上げ。review.r2 M2）**: `if b0 == "GENERATED" and mine and not has_unknown:`。元の結果が棄権・出典なし（`NONE`）・`UNKNOWN_ORIGIN` の混じる・`MIXED` のときは格上げしない（`elif mine:` の枝で `confirmed_records_not_used` に数える）。review.r2 M2 の「`b0 in ("GENERATED","NONE") and mine and not has_unknown`」より狭い（監査役の判断が後なので判断に従った）。生成の出典の棄権 3 型も、元の棄権のまま（`ABSTAIN`、used 0・not_used 1）。出典なしの答え（`answer/ANSWER`）は素通し（`applied: false`）になり、基点のように記録の文に置き換わらない。
- **R3-J5（判断の「その生成文と確認済みの文が一致するときだけ」）**: **入れていない**。記録の claim を今の claim と照合する形は、改訂の許可の外の `tests/test_basis_policy_confirm.py` の 2 件（`test_two_confirmed_records_with_different_claims_abstain`・`test_two_confirmed_records_with_the_same_claim_are_not_a_split`）を落とす（実測は §11 の (c)）。入れ方: `mine` の条件に `e["payload"]["claim"] == claim` の 1 行を足す。許可を得て 2 件を改訂するときに入れる。
- **R3-J6（既存テストの改訂）**: W6-a の 7 関数（11 件の test id）だけ。名前は変えない。前後の全文は上の「W5-c 第 3 ラウンドで改訂したテスト」。
- **R3-J7（凍結済みの `tests/test_basis_policy_w5c.py`）**: 期待が判断で変わる 5 関数だけ改訂し、`frozen_tests.sha256` に `AMENDED` 行を足した。
- **R3-J8（版）**: 分類の規則が変わったので `CLASSIFY_VERSION = 3`。`TABLE_VERSION = 1`・`SCHEMA`・`CONFIRM_ID_VERSION = 2` は変えない。格上げの条件の変更に新しい定数は作らない。
- **R3-J9（事前登録）**: prereg-w5c 節は書き換えず、その直後に prereg-w5c-r3 節を足した。W5-c-1 の規則 7 と W5-c-3 の 3 つ目の項目はその節で置き換える。
- **R3-E1（実装役）**: `_family_of` を `src.get("family")` で書き直した（`src["family"]` の字面を 0 件にするため。挙動は同じ: 文字列でなければ `"(none)"`）。
- **R3-E2（実装役）**: 改訂後の `test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis` は、指示書どおり (i) に加えて `[HUMAN]` が `UNKNOWN_ORIGIN` になる assert を足したので、実装前にも落ちる。指示書は「実装前に落ちるのは (ii) の 2 関数と w5c の (ii)・版の 3 関数」と書いたが、実測は 6 件（table 2・w5c 4。`r3_revised_before_impl.txt`）。
- **R3-E3（実装役）**: `tests/test_basis_policy_w5c_r3.py` を凍結（`EXTENDED`）した後、実装後の実行で補助関数 `_family_key` が鍵なし（番兵 `"MISSING"`）を `"(none)"` に写していない誤りに気づき、その 1 関数だけ直した（assert は変えていない。期待の弱体化ではなく仕様 prereg-w5c-r3 のとおりへの訂正）。`frozen_tests.sha256` に `AMENDED` 行（理由つき）を足した。
- **R3-E4（実装役）**: 新しいテストに指示書の列挙にない関数を足した: 規則 7 が `origin` に値のある文書に当たらないこと、`user_documents` に依らない `family: "user"`・`human_confirmed`、系列 `document` 以外は規則 7 の対象でないこと、`withheld` の 10 通り、出典なし・利用者の文書の答えの記録との関係。
- **R3-E5（実装役）**: `_withheld` と `_unknown_dict` に `n_unknown` を渡す呼び手は 4 か所（`apply_to_ask` の 3 か所と `_settle_confirmation` の 1 か所）で、どれも `sc` から数える。`_quoted` の判定（元の `text` が出所不明の本文を引用しているか）も `user_documents` を渡す。

## 11. 既知の穴（隠さない）

- **`ORIGIN_UNMARKED_ROUND3_EVIDENCE`**: `semantic_qa`（`--mode round5` で文書なし）などの round3 の系列（`general_qa / local / pro / jawiki`）の出典には `origin` の印が付かず、この環境には `build/round3` が無いので生成物かどうか実測できない。分類は印だけを見るので、印の無い生成物は `HUMAN` に数えられうる。上流（`semantic_retrieve` / `evidence_library`）で `origin` を付けるのが筋で、許可パス外。
- **方針を通らない入口**: `vera chat`、MCP の扉、`engine.ask` と `Vera.ask` の Python API は方針を通らない（`vera ask` の 3 経路だけ）。`vera observe` も未接続（J13）。
- **C は実物の索引ではほとんど打ち切りになりうる**: 検索語は述語の先頭の漢字の並び（例 `渡す` → `渡`）で、実物の索引での行数・打ち切りの率は未測定（この環境には実物の索引を使った測定が無い）。打ち切りのときは借用しない（安全側）。
- **既定（factual）の入口では、生成コーパスから出た社交・生成の返事（`compose` など）も引っ込められる**: 例えば会話の供給（`ありがとう。` → 生成の応答文）の答えは、`--request-kind` を `factual` のままにすると `ABSTAIN` になる。指示書の P2（`kind` が `answer / compose / social` のどれでも生成だけなら ANSWER を出さない）の帰結。事実を主張しない依頼は `--request-kind creative` などで明示する。
- **D の記録は問いの完全一致だけで効く**: 言い換えた問いには効かない（正規化しない）。記録の `claim` は元の結果の `text`（システムが生成の文から組んだ文）であり、利用者が はい と言うのはその文。
- **記録を読む条件に `consent.promote` を使っている**: 昇格の同意とは別に「確認の記録を答えに使う同意」を持たない（W4-m の同意の型をそのまま使った）。同意の撤回後は記録を使わない（保守側）。
- **`--confirm` の id は人が書き写す文字列**: 問いを出した入口と同じ環境変数・同じ索引で再計算するので、索引が変わると id が変わり `UNKNOWN_CONFIRM_ID` になる。
- **出典なしの答え（計算など）は素通し**: 計算の答えの証人は F（別チケット）。
- **元の結果が生成の出典を引かない棄権は、元のまま素通し（第 2 ラウンドで判断）**: 生成の出典を 1 つも持たない棄権（例 `kind: answer` ＋ `verdict: UNKNOWN_X` のように上流の型が片方だけ棄権側）は、方針が型を直さずそのまま出す（`basis_policy.outcome` は `ABSTAIN`）。生成物が根拠に入っていないので P2 の対象ではなく、上流の型を方針が書き換えると既存の採点（B1・B5）を実測なしに変えるため。上流が片方だけ棄権側の型を返すなら上流で直す（現行の製品にこの形を返す箇所は見つけていない）。
- **`--confirm` が成功したときの出力（`kind: confirmation`）は採点器の状態が `unmapped`**: 採点器は `--confirm` を呼ばない設計なので、E3 の不変条件（`ANSWER_*`・`CONSTRUCTED` でない出力は abstain）の対象外。失敗した確認の出力は `kind: unknown` で abstain（テストあり）。
- **`tests/bank_score/test_bs_end_to_end.py::test_s6_…`** は、`verantyx/` に未コミットの変更がある間だけ落ちる（採点器の `verantyx_untouched` が `git status --porcelain -- verantyx` の空を要求する）。チケットが環境由来と明記しているもの。コミット後は通る見込みだが、コミット前なので実測していない。
- **P6 は未測定**: 隠しバンクは開いていない。
- **`python -m verantyx.cli` は現在のディレクトリの `verantyx` を先に読む**: 作業ツリー以外から実行すると別の `verantyx` が読まれる（実演の最初の試行で起きた。`cd <ツリー>` してから実行する）。

### W5-c で更新した既知の穴（追記。上の穴は消していない）

1. **索引の系列でない出典の `origin` 欠落は今も人**: 系列が `ability_corpus.FAMILIES` に無く `origin` が欠落・`None` の出典（`abilities.py` の `general`・`code_compose.py` の `code_parts`・`pun_lexicon`・`one.py` の `conversation_form`・`jawiki`・利用者の文書の答えの出典 `family: "document"` など）は、規則 7 で `human` のまま。理由: 製品は人の出所に `origin` の値を一度も付けておらず（文書の答えの出典に `origin` の鍵が無い）、既存テストの期待がこの読みを固定している: `tests/test_basis_policy_table.py` の `test_decide_accepts_a_classification_result_as_the_basis`（117 行）・`test_rule4_origin_none_falls_through_to_the_later_rules`（153 行）・`test_rule6_anything_else_is_human`（163 行）・`test_human_and_generated_together_is_mixed`（174 行）、`tests/test_basis_policy_entry.py`（201〜205 行、実物の round5 文書の答え 278 行付近）、`tests/test_basis_policy_form.py`（185〜246 行。文書の答えで C の借用が起きる）。上流で人の出所に `origin` を付けるか、監査役が該当テストの期待を変える許可を出すまで閉じない。W5-c の試験 `test_w5c_known_hole_a_source_outside_the_index_families_without_origin_is_still_human` がこの穴を固定している（穴が閉じたら期待を直す）。
2. **`ORIGIN_UNMARKED_ROUND3_EVIDENCE`（一部だけ前進、実データで未測定）**: round3 の出典のうち系列名が `ability_corpus.FAMILIES` と同名のもの（`general_qa`・`local`・`pro`・`conversation`・`paraphrase_entail`・`code`）は印が無くても `UNKNOWN_ORIGIN` に倒れる。`jawiki` は同名でないので人のまま。この環境には `build/round3` が無く、入口での件数は測れない（`UNMEASURED_NO_ROUND3_BUILD`）。この系列名を `origin` なしで出す製品の箇所: `artifacts/w5-c/families_literal_sites.txt`（10 件。`abilities.py`・`round3.py`）。
3. **別の root への id の持ち出しは `UNKNOWN_CONFIRM_ID`（J9）**: 宛先を特定できないので「別の宛先」と言わない。
4. **`append_basis_confirmation` の直接の呼び手は `destination` を省けば束縛されない（J6）**: `vera ask --confirm` の入口は必ず `destination` を付けるが、ソブリンの口を直接呼ぶコードは省ける（口は `destination` が無い payload を従来どおり受ける。既存テストが固定）。
5. **W5-c 以前の いいえ の記録は効かない（J10）**: 宛先なしの id で保存された `REJECTED_GENERATED` は、宛先つきの id と一致しないので、同じ問いは もう一度 `CONFIRM_REQUEST` になる（誤答にならない側）。
6. **同意なしの宛先への持ち出しは `NO_CONSENT` が先に出る（J8）**: 別の宛先を指していても、宛先が同意なしなら `CONFIRM_TARGET_MISMATCH` でなく `NO_CONSENT`（どちらも何も書かない。rc 1）。
7. **規則で作る社交の返事（F1）**: `GeneralRouter._social_frame`（固定の返事）の出力を `apply_to_ask` に直接通すと、`family: "conversation"` に `origin` が無いので、事実の問い（既定）では `UNKNOWN_ORIGIN_SOURCE` で棄権になる（基点では `ANSWER_HUMAN_BASIS`。`artifacts/w5-c/round3_social_frame_probe.txt`）。事実を主張しない依頼（`--request-kind creative` など）なら `CONSTRUCTED`。ただし、方針を当てる CLI の入口（legacy・`--mode round5`）からはこの関数に届かない（コードの読みと実測は §10 の F1 と `artifacts/w5-c/greeting_entrances.txt`）。`Vera()` を `general=None` で直接使う呼び手には `_social_frame` が届くが、そこには方針が掛からない。隠しバンクの B1・B2・B5 は開いていない・測っていない（採点器の子プロセスの環境で挨拶 4 文を CLI に流した出力は基点と同じ: `greeting_entrances.txt`）。`build/round3` のある環境の入口は未測定（`UNMEASURED_NO_ROUND3_BUILD`）で、監査役が測ること。
8. **事実を主張しない依頼で出所不明の出典の答えは、生成と同じ側（`CONSTRUCTED`）で元の本文が残る**: チケットの「生成と同じ側」に従った。出所不明の文を材料に使うことが許されるかは別の判断（棄権に倒すこともできる）。
9. **P6 の隠しバンク（B1・B2・B5）は開いていない・測っていない**: 採点器の見本 B2（25 問）は前後で意味が同じ（`artifacts/w5-c/bs_B2_semantic_compare.txt`）。
10. **元の結果が棄権で出所不明の出典を持ち、同じ問いに はい の記録があると `ANSWER_HUMAN_BASIS` になる（J5 との非対称。第 1 ラウンドのレビュー任意 1 を受けて追記）**: 答えの側（`answer/ANSWER`）の出所不明は J5 で棄権のままだが、元が棄権（`unknown/UNKNOWN_X`・`refusal/UNKNOWN_Y`）のときは `b0 = "NONE"` なので記録で格上げされ、本文はソブリンの記録の `claim`（出所不明の本文は出ない）。生成の出典のときも同じ振る舞い（基点から）。出所不明の文を人の根拠にしているのではなく、記録（人の はい）を根拠にしている。実測: `artifacts/w5-c/j5_refused_probe.txt`（`scripts/j5_refused_probe.py`）。不具合とは扱わず、監査役の合成で驚かないよう記す。
11. **系列名の揺れ（`"LOCAL"`・`" local"` など `ability_corpus.FAMILIES` と完全一致しない名）で `origin` が欠落・`None` の出典も人のまま**: 定義上は穴 1 に含まれる。製品の `Corpus` は `FAMILIES` 以外の系列を `ValueError` で拒むので、索引からは出ない。系列名を正規化して拾う処理は足していない（語の一覧を足して直さない）。

### W5-c 第 3 ラウンドで更新した既知の穴（追記。上の穴は消していない）

**閉じたもの**
- **穴 1（索引の系列でない出典の `origin` 欠落は今も人）は第 3 ラウンドで閉じた**: `origin` が欠落・`None` の出典は、`family == "user"`（依頼文）と、round5 で documents を渡した呼び出しの `family: "document"` だけを除いて出所不明（規則 8）。`general`・`jawiki`・`conversation_form`・`code_parts`・`pun_lexicon`・系列名の揺れ・系列の鍵なしも含む。合成（`r3_synth.txt`）で出所不明の組合せの `ANSWER_*` は 0。
- **穴 11（系列名の揺れ）も閉じた**: `"LOCAL"`・`" local"` などで `origin` が欠落・`None` の出典は出所不明。
- **穴 10（棄権の結果・出所不明の結果が はい の記録で格上げされる）は第 3 ラウンドで閉じた**: 格上げは元の結果の根拠が生成のときだけ（R3-J4）。前後の実測は `j5_refused_probe.txt`・`r3_record_probe.txt`。
- W6-a の §11 の最初の項目（`ORIGIN_UNMARKED_ROUND3_EVIDENCE`: 印の無い生成物は `HUMAN` に数えられうる）は、**印の無い出典が利用者の文書以外では人に数えられなくなった**ことで、危険な向き（誤って人にする）は閉じた。印を足す上流の作業（round3 系列・枠の記録）はこのチケットでは行っていない。

**新しい・残る穴**
- (a) **利用者の文書は入口の来歴（round5＋documents）で人とし、出典の本文が渡した文書に本当にあるかは方針が確かめない**。`apply_to_ask` は `mode == "round5" and bool(documents)` だけを見る（ファイル名・本文の照合はしない。R3-J1）。`apply_to_ask` を直接呼ぶ呼び手が `documents=["x"]` を渡して `family: "document"` を名乗る出典を載せれば人になる。CLI の入口で `--document` を受けるのは round5 だけ。
- (b) **正しい答えの損失（上流で `origin` を付けるまで）**: legacy・`--engine`（ストアに入れた利用者の文書 `.documents.json` を含む）・round5 で documents なしの `family: "document"`、`general`・`jawiki`・`conversation_form`・`code_parts`・`pun_lexicon` などの出典の答えは、事実の問いでは `UNKNOWN_ORIGIN_SOURCE` で棄権になる。`origin` を付けずに `family` を書く製品の箇所は 36 か所（`r3_family_sites.txt`）。どの入口で何件が棄権に変わるかは、測ったもの（B2・B3・挨拶 8 件・`tests/test_one_request_goal_route.py`・全体テスト・入口の実演）以外は `UNMEASURED_ENTRANCE`。
- (c) **R3-J5 の照合は入れていない**: 判断の「その生成文と確認済みの文が一致するとき」。入れ方は `mine` の条件に `e["payload"]["claim"] == claim` を足す 1 行。入れると、改訂の許可の外の `tests/test_basis_policy_confirm.py::test_two_confirmed_records_with_different_claims_abstain` と `::test_two_confirmed_records_with_the_same_claim_are_not_a_split` の 2 件が落ちる（`r3_variant_costs.txt`）。許可を得て 2 件を改訂するときに入れる。入れていない間は、記録の claim が今の生成の claim と違っても（同じ問いで はい の記録があれば）格上げする。
- (d) **棄権の結果・出典なしの結果は はい の記録で格上げしなくなった**（誤答にならない側の損失）: 基点では出典なしの `answer/ANSWER` や、生成の出典の棄権が はい の記録の文に置き換わっていた（`r3_record_probe.txt`）。出典なしの答えは素通し（元の答えのまま、記録は `confirmed_records_not_used`）、生成の出典の棄権は元の棄権のまま。
- (e) **判断の「枠・利用者の記録」の `origin` の値は語彙に無い**（R3-J3）。製品がまだ書かない値に名前を作っていない。人の明示の値は `human_confirmed` だけ。
- (f) **字面どおり（R3-J1 の例外なし）に戻すときの代価**: `_class_of` の 2 行を消すと、スクラッチの写しで 13 件失敗（W6-a の 5 件: `test_basis_policy_entry.py::test_a_document_answer_keeps_its_text_and_is_typed_human_basis`・`test_basis_policy_form.py` の 4 件、W5-c の新しいテスト 7 件、許可パス外の `tests/test_one_request_goal_route.py::test_cli_explicit_round5_document_entry_uses_same_python_route` 1 件）。CLI の入口からは利用者の文書の答えが `UNKNOWN_ORIGIN_SOURCE` になり、C（形の借用）は CLI から届かなくなる（`r3_variant_costs.txt`）。戻すなら、W6-a のその 5 件と許可パス外の 1 件の改訂の許可が要る。
- (g) 事実を主張しない依頼（`--request-kind creative` など）で出所不明の出典は、今も「生成と同じ側」（`CONSTRUCTED`）で元の本文が残る（W5-c の穴 8 のまま）。第 3 ラウンドの合成・テストは事実の問いが中心。
- (h) 実装前に通った 10 件（`r3_tests_before_passed.txt`）は基点で既に成り立つ性質で、新しい能力の証拠ではない。
- (i) `ORIGIN_UNMARKED_ROUND3_EVIDENCE` の実データでの件数は、この環境に `build/round3` が無いので `UNMEASURED_NO_ROUND3_BUILD` のまま。

## W5-d の事前登録: 文書の出典の本文の照合・確認記録の文面の一致
<!-- w5d-prereg:begin -->
事前登録の時刻: 2026-10-03 23:07:22 +0900（`date '+%F %T %z'` の出力）。

- **B-J1（A1）**: `apply_to_ask` で `mode == "round5" and documents` のとき、渡された文書を `one.py` の `load_documents` と同じ読み込み（`document_loaders.load_directory`／`load_paths`）で読み、本文の列を作る。`family == "document"` で `origin` が無い出典は、(a) `text` が空白でない文字列で `NFKC(text)` が渡した文書のどれかの `NFKC(本文)` の部分文字列、または (b) `text` の鍵が無く `sha256` が文字列で渡した文書のどれかの本文の sha256 と等しい、のときだけ `human`。それ以外は `unknown_origin`（文書が読めない・存在しないときも）。`classify_sources`・`_class_of`・`_unknown_origin_sources` に `document_texts` を足し、`apply_to_ask` は全部の呼び出しで同じ本文の列を渡す。`document_texts is None` は旧い契約（呼び手が自分で確かめた）のまま。`CLASSIFY_VERSION` は 3 のまま（既存テストが `== 3` を固定しているため。申し送り）。
- **B-J2（D1）**: 同じ問いの はい の記録 `mine` の claim が 2 種類以上 → 今どおり `AMBIGUOUS_CONFIRMED_RECORDS`（照合より先に見る）。1 種類でその claim が今の `claim` と **文字列として完全に等しい（正規化しない）** → 格上げ。1 種類で等しくない → 格上げせず、`notes` に `confirmed_records_claim_differs` を足す。**チケットの「NFKC 正規化後の完全一致」から外れる**: NFKC で比べると `コードはＡＢＣです。` と `コードはABCです。` が等しくなり攻撃 `[nfkc]` が落ちるため、より狭い（棄権側の）「正規化しない完全一致」にする。
- **B-J3 改訂（許可の範囲）**: `tests/test_basis_policy_confirm.py::test_two_confirmed_records_with_the_same_claim_are_not_a_split` だけを、名前を変えず、記録の claim を今の生成の claim にして改訂する。前後の全文は測定の節に写す。K4（`test_r3_a_recorded_yes_still_lifts_a_generated_answer`）は当てず、改訂案の全文を測定の節に書く。

### 宣言する規則どうしの衝突（実装役は解かずに宣言する。判断は監査役）
チケットの規則を字面どおりに入れると、旧い振る舞いをそのまま固定した既存テストが落ちる。実装役はチケットの規則どおりに作り、テストの期待は変えず（改訂が許された 1 関数を除く）、落ちた id を全部宣言する。

| # | 衝突 | 落ちる見込みのもの |
|---|---|---|
| K1 | W3-c2「型を確かめられない充填物は候補から外す」 × 配置なしで FILLED/TIE を期待する既存テスト・攻撃の外れ | `tests/test_question_cross_observe.py` の一部、攻撃の写しの 2 件 |
| K2 | R1「配置が無い日本語の名前は命名の文で導入されたものだけ」 × 配置なし（スタブ）の名前で振る既存テスト・R2 の攻撃テスト | `tests/test_routing_from_text*.py` の多数、攻撃の写しの R2 の 1 件 |
| K3 | A1「出典の本文が渡した文書の中にある」 × 存在しない文書を渡して `family: document` を人とする既存テスト | `tests/test_basis_policy_form.py`・`tests/test_basis_policy_w5c_r3.py` の一部 |
| K4 | D1「文面が同じときだけ格上げ」 × 別の文の記録で格上げすることを固定した既存テスト（改訂許可の 2 件の外） | `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer` |
| K5 | W3-a3 A1「枠の確認は助詞ごとの型の一致」 × 攻撃の写しの不変条件「gen_frame の格上げ語は全部 CONFIRMED」 | `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades` |
| D1-改訂 | 許可された 2 件のうち設計上落ちる 1 件 | `tests/test_basis_policy_confirm.py::test_two_confirmed_records_with_the_same_claim_are_not_a_split`（名前不変で改訂。前後の全文は BASIS_POLICY の測定の節） |

### 受入基準の測り方（G1〜G7。測る前に固定）
- G1: 攻撃の写し 5 本（`tests/attack/w3c2`・`test_attack_w5b_wave2.py`・`test_attack_w5c_*.py` 2 本・`tests/attack/w3a3/test_attack_w3a3_r6.py`）。落ちてよいのは宣言した K1(2)・K2(1)・K5(1) の 4 id だけ。A02・R2・W3-a3 A1 は新しいテストで確かめる。
- G2: `artifacts/w5-d/scripts/run_questions_both.py`（実装役の 185 問、配置あり／なし）。誤答 0、型未確認の充填物を持つ FILLED/TIE 0。正答の減少は変更前（`artifacts/w5-d/before/q185_*.json`）との差を数で。
- G3: 経路づけの凍結 4 本（`run_bank.py`、配置なし・r7）の misroutes と、自作の合成（`artifacts/w5-d/g3_synth/`、入力と期待を先に書き sha256 を凍結）。
- G4: `artifacts/w5-d/scripts/g4_probe.py`（入力を先に凍結）。自己申告の文書・文面違いの確認記録から `ANSWER_*` が 0。対照（本当に渡した文書の文・完全一致の記録）では答えが出ること。
- G5: r7 を cache なしで 2 回作り `verify` が両方 OK、`content_sha256` が run1 = run2 = r6（`5c969d45…`）。L1〜L3・動詞 300 語を `measure_w5d.py` で r6 と r7 で測り同じ。
- G7: `pytest tests`（最後に 1 回）の失敗集合が基線 `dev_c875ed3_failures.txt` から増えない。増えた分は 1 件ずつ K1〜K5 または環境由来に当てる。当たらないものはコードを直す。
- 基線（変更前）の測定は `artifacts/w5-d/before/` に保存済み（この事前登録より前）。製品コードの差分はこの時点で空。

<!-- w5d-prereg:end -->

## W5-d の測定: 文書の出典の本文の照合・確認記録の文面の一致
<!-- w5d-measured:begin -->

測定の時刻: 2026-10-03 23:34:53 +0900。出典はすべて `artifacts/w5-d/` のファイル（下に名前を書く）。全体テスト: `pytest_full.txt` の最終行 `198 failed, 11889 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 341.39s (0:05:41)`。基線 `dev_c875ed3_failures.txt` に無い新しい失敗は 83 件（`new_failures.txt`）で、1 件ずつ `new_failures_explained.txt` に K1〜K5・改訂・環境由来のどれかを書いた。どれにも当たらないものは 0 件（`grep -v -E 'K[1-5]|D1-改訂|環境由来' new_failures_explained.txt` が空）。基線から直った失敗は 0 件（`fixed_failures.txt`）。

### 方針（G4。`g4_inputs.json`・`g4_inputs.sha256`（先に凍結）・`scripts/g4_probe.py`・`g4_result.json`）
- 自己申告の文書 16 通り（存在しない文書・本文に無い文・空のファイル・言い換え・sha256 不一致・空白だけ・数値や配列の text・別の文書の本文・round5 以外のモード ほか）から `ANSWER_*` が **0**（変更前の木では 14。変更前は空白だけの text で `borrow_form` が例外を出す 1 件を含む。`before/g4_at_base.json`）。対照（本当に渡した文書の文・NFKC だけ違う文・ディレクトリの中の文・本文の sha256）4 通りは全部が答えになる（4）。
- 文面違いの確認記録 15 通り（空白・全角空白・NBSP・末尾の空白と改行・タブ・句読点・ゼロ幅空白・BOM・NFKC・全角数字ほか）から `ANSWER_*` が **0**、旧い文が回答された数 0（変更前の木では 15 と 15）。対照（完全一致・同じ文の記録が 2 件）2 通りは答えになる（2）。
- 本物の入口 `vera ask --mode round5 --document`（`a1_cli.txt`）: 答えのある文書（ファイル・ディレクトリ）は `ANSWER_HUMAN_BASIS` のまま、答えの無い文書・存在しないパスは棄権。

### 改訂した 1 件（B-J3。`tests/test_basis_policy_confirm.py::test_two_confirmed_records_with_the_same_claim_are_not_a_split`。名前は不変。`frozen_tests_amended.txt`）
改訂前の全文（`amended_before.txt`）:
```python
def test_two_confirmed_records_with_the_same_claim_are_not_a_split(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="aaa", claim="主張A"))
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="bbb", claim="主張A"))
    rc, out = _ask(tmp_path, capsys)
    assert rc == 0 and out["verdict"] == "ANSWER" and out["text"] == "主張A"
```
改訂後の全文（`amended_after.txt`）:
```python
def test_two_confirmed_records_with_the_same_claim_are_not_a_split(tmp_path, monkeypatch, capsys):
    root, sid = _world(tmp_path, monkeypatch)
    claim = _ask(tmp_path, capsys, "--human-present")[1]["confirm"]["claim"]    # W5-d (D1, amended): the sentence generated now
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="aaa", claim=claim))
    sov.append_basis_confirmation(root, sid, _payload(confirm_id="bbb", claim=claim))
    rc, out = _ask(tmp_path, capsys)
    assert rc == 0 and out["verdict"] == "ANSWER" and out["text"] == claim
```
理由: 同じ claim の記録が 2 件あっても割れない、という意図は変えず、記録の claim を「今の生成の claim」にした（D1 は今の文と一致しない記録では格上げしない）。

### 宣言した衝突 K3（文書の出典の本文の照合）の実際の失敗 id（10 件）
- `tests/test_basis_policy_form.py::test_a_document_answer_gets_a_borrowed_form_and_keeps_its_text_and_sources`
- `tests/test_basis_policy_form.py::test_a_failed_borrowing_leaves_the_human_answer_as_it_was`
- `tests/test_basis_policy_form.py::test_the_borrowing_takes_no_role_from_the_generated_sentence_end_to_end`
- `tests/test_basis_policy_w5c_r3.py::test_r3_a_document_the_user_handed_over_is_answered_unchanged[origin-'MISSING']`
- `tests/test_basis_policy_w5c_r3.py::test_r3_a_document_the_user_handed_over_is_answered_unchanged[origin-None]`
- `tests/test_basis_policy_w5c_r3.py::test_r3_a_generated_sentence_next_to_the_users_document_is_mixed_not_unknown_origin`
- `tests/test_basis_policy_w5c_r3.py::test_r3_the_users_own_document_answer_is_kept_and_the_record_is_not_used`
- `tests/test_basis_policy_w5c_r3.py::test_r3_the_withheld_count_is_the_classified_count[round5-documents4-sources4]`
- `tests/test_basis_policy_w5c_r3.py::test_r3_the_withheld_count_is_the_classified_count[round5-documents5-sources5]`
- `tests/test_basis_policy_w5c_r3.py::test_r3_the_withheld_count_is_the_classified_count[round5-documents7-sources7]`

### 宣言した衝突 K4（確認記録の文面の一致）の実際の失敗 id（4 件）
- `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer[False-False]`
- `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer[False-True]`
- `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer[True-False]`
- `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer[True-True]`

K4 の改訂案（**当てていない**。監査役が許可すれば当てる。`k4_proposal.diff`）: `test_r3_a_recorded_yes_still_lifts_a_generated_answer` は「別の文（`OTHER_CLAIM`）の記録で生成の答えが格上げされる」ことを固定しており D1 そのものと矛盾する。確認した claim を今の結果が持つ文にする:
```diff
229c229
< def _sovereign_with_yes(tmp_path, monkeypatch, query=Q):
---
> def _sovereign_with_yes(tmp_path, monkeypatch, query=Q, claim=OTHER_CLAIM):
234c234
<               "confirm_id": "abc", "query": query, "claim": OTHER_CLAIM, "generated_sources": [],
---
>               "confirm_id": "abc", "query": query, "claim": claim, "generated_sources": [],
277c277,279
<     root = _sovereign_with_yes(tmp_path, monkeypatch)
---
>     # W5-d (D1) proposal: the human confirmed THE SENTENCE the result now carries (the claim of the result is its ``text``)
>     claim = _synthetic("answer", "ANSWER", [])["text"]
>     root = _sovereign_with_yes(tmp_path, monkeypatch, claim=claim)
281c283
<     assert out["text"] == OTHER_CLAIM and out["kind"] == "answer"
---
>     assert out["text"] == claim and out["kind"] == "answer"
```
K3・K4 が、文書が本文に実際にその文を持つ／確認した文が今の文であれば通ることの証拠: `k3k4_probe.txt`。
```
K3/K4 probe (scratchpad copy of c875ed3 + the changed verantyx files):
 K3: the test files are NOT changed; tests/conftest.py of the copy gets an autouse fixture that makes the cwd of each test hold a real memo.txt containing the sentences the tests give as the document's text (k3_probe_rewrite.diff).
 K4: tests/test_basis_policy_w5c_r3.py of the copy gets the revision proposed in k4_proposal.diff (the confirmed claim is the sentence the result now carries); the real tree's file is NOT changed.

result: tests/test_basis_policy_form.py + tests/test_basis_policy_w5c_r3.py: 167 passed, 0 failed.
   => the 10 K3 tests (form 3 + w5c_r3 documents 7) and the 4 K4 tests all pass once the document really holds the sentence / the confirmed sentence is the present one.

Also in the real tree: the two end-to-end tests that hand over a real memo.txt through main() pass unchanged:
   tests/test_basis_policy_form.py::test_from_the_command_line_a_document_answer_carries_the_borrowed_form
   tests/test_basis_policy_w5c_r3.py::test_r3_through_main_the_users_document_is_still_a_human_basis
```

### 既知の穴（隠さない）
1. **`document_texts=None` の直接呼び**: `classify_sources(..., user_documents=True)` だけを渡す直接の呼び手は、旧い契約のまま自己申告が通る（製品の中でそう呼ぶ所は無い。`tests/test_basis_policy_w5c_r3.py` の直接呼び 5 件を守るため）。
2. **改行をまたぐ文は見つからない**: 出典の `text` が文書の改行をまたぐ（部分文字列にならない）と `unknown_origin` に倒れる（棄権側の損失。`tests/test_basis_policy_w5d.py::test_a1_a_sentence_across_a_line_break_is_not_found_a_loss_on_the_safe_side`）。
3. **`CLASSIFY_VERSION` は 3 のまま**: 規則 7 の条件が狭くなったが版は上げていない（既存テストが `== 3` を固定）。出力に版が残らないので、A1 の前後を版で見分けられない（監査役への申し送り）。
4. **D1 は NFKC 正規化をしない**: チケットの文言（NFKC 正規化後の完全一致）より狭い（正規化しない完全一致）。NFKC で比べると攻撃 `[nfkc]` が落ちるため。`コードはＡＢＣです。` と `コードはABCです。` は別の文として再確認を求める（格上げしない）。

<!-- w5d-measured:end -->

## W5-d 第 2 ラウンド（W5-d2）の事前登録
<!-- w5d2-prereg:begin -->
事前登録の時刻: 2026-10-04 00:31:06 +0900（`date '+%F %T %z'` の出力。第 2 ラウンドの製品コード・テストの変更より前）。ベースは `dev` = `c875ed3`。第 1 ラウンドの `w5d-prereg`・`w5d-measured` 区間は 1 文字も変えない（第 1 ラウンドの記録）。この節が置き換えるものは、後ろの `w5d2-measured` 区間の「置き換わった記述」に列挙する。

**監査役の裁定（2026-10-04 00:05）**: B1 規則の衝突で落ちる既存テスト 78 件＋攻撃の写し 4 件は改訂を許可（K1・K2 は偽の `PlacementLookup` の注入、K3・K4・K5 は期待の改訂。名前は変えず、前後の全文を docs に）。B2 D1 の比較は正規化しない完全一致を追認（チケットの文言「NFKC 正規化後」は撤回）。B3 `recompute_q.py --check` と `w3c2-entry` 区間の例は、配置を与えた例に取り直してよい（区間の規則の本文は変えない）。追加 9 質問の観測が `VERA_PLACEMENT` を読まないのは、この後では「本番では質問がほぼ全部棄権」を意味するので、`observe.py` の question の経路で、`--placement` が無く `VERA_PLACEMENT` があるときは `event_cross.default_lookup()` の lookup を使う（収まらなければ既知の穴として次のチケットへ）。

**第 2 ラウンドの判断（中間職の指示書 D2-1〜D2-8）**
- D2-1 K1（質問の十字 15 件）: 配置の JSON（穴の充填物だけに direct の型。穴の型と食い違う型は付けない）または `O.FilePlacement` を注入する。例外 1 件（`test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun`）は「配置なしで FILLED」が主題で新しい契約と正反対なので、期待を新しい契約（配置なし → `NO_TYPED_CANDIDATE`・`TYPE_UNCHECKED`・`hole_type_check` が `NOT_CHECKED/NO_PLACEMENT`）に改訂。配置あり／なしの対のテストを足す。
- D2-2 K2（自由文→記録 52 件）: テストの中だけの `FakePlacement`（固定の名前は `UNPLACED`、列挙した普通名詞は direct の型）を注入。配置なしが主題の 3 件は期待を新しい契約（配置なし → 棄権）に改訂。**裁定の申し送り（並列の名前の過剰棄権は直さず既知の穴）からの逸脱**: 偽の配置（全語 UNPLACED）を注入しても 11 件は `ハルとセキは同じ会社だ。` の部分名 `ハル`・`セキ` に配置の答えが無く `NAME_UNVERIFIED` → `INCOMPLETE_READING` で通らない。期待を書き換えれば「弱体化」になるので、`routing_from_text.py` だけで、日本語の並列の充填物の部分名それぞれを同じ lookup に問う（R-J1 の同じ規則を部分名の配置の答えに当てるだけ。新しい規則は足さない。英語は変えない）。配置が無ければ今どおり `NAME_UNVERIFIED`。
- D2-3 K3（10 件）: 期待の値は変えず、渡した文書を実在させる（`tmp_path` の `memo.txt` に出典の `text` を書く）。K4: `artifacts/w5-d/k4_proposal.diff` をそのまま当てる。K5: 48 語の導出・バイト一致・各条件は不変、`frame_status` は `CONFIRMED` か `NOT_CONFIRMED`（後者は `frame is None`・`frame_disagreement`・助詞ごとの型が交わらない）、数は assert せず出力に一覧。
- D2-4 攻撃の写し 3 本の先頭行を `revised in W5-d2` に。G1-b は「先頭行と改訂した関数を除いて同一」。`data/` は同一。
- D2-5 D1: コードは変えない（正規化しない完全一致）。BASIS_POLICY に追認の理由を書く。
- D2-6 B3: `recompute_q.py` の `EXAMPLES` を 4 つ組（期待, 文書, 問い, 配置ファイル名）にし、`QD02`『どの人が客に切符を渡した？』（FILLED）と `QD01`『誰が生徒に地図を渡した？』（TIE）を `placement_q.json` つきに、`NO_ATTESTED_CELL` の例は今のまま。`--write` は 1 回だけ。凍結データは変えない。
- D2-7 追加 9: 製品の変更は `observe.py` の `_observe_question` の中だけ。`--placement` が無い（`StubLookup`）ときだけ `EC.default_lookup()`。充填物の型の確かめは同じ lookup に `surface` を問い直した答え。出力の `structure.placement` は実際に使った lookup の id。新しい鍵は足さない。**門**（どれか 1 つでも破れたらこの変更だけを戻して既知の穴に書く）: (1) r7 で 185 問の誤答 0・型未確認の FILLED/TIE 0、攻撃 120 問でも型未確認 0 で A01 が FILLED/TIE にならない、(2) `VERA_PLACEMENT` なしの 185 問の出力が第 1 ラウンドと byte 一致、(3) 平叙文の観測（`o1_bytes.py --child`）が基点と byte 一致（配置なしと r7 の 2 通り）。FALSE_NONE の増分と TIE が FILLED に縮む件は数えて書くが門にしない。
- D2-8 置き場所: 本区間（事前登録）、`w5d2-measured`（測定）、`w5d2-amended`（改訂したテストの前後の全文。`artifacts/w5-d/r2/scripts/amended_texts.py` で生成）。K1・B3・D2-7 → OBSERVATION、K2・D2-2 → ROUTING_FROM_TEXT、K3・K4・D1 → BASIS_POLICY、K5 → COARSE_PLACEMENT、EVENT_CROSS には穴の型の節への 1 段落。

**測り方（測る前に固定。出力はすべて `artifacts/w5-d/r2/`）**
- G1: 攻撃の写し 36 本が全部通る（`tests/attack/w3c2`・`test_attack_w5b_wave2.py`・`test_attack_w5c_*.py` 2 本・`tests/attack/w3a3/test_attack_w3a3_r6.py`）、K の 82 id が全部通る、G1-b は上のとおり。
- G2: 実装役の 185 問を（配置なしの環境 × place/noplace）と（`VERA_PLACEMENT=r7` × place/noplace）、攻撃 120 問を r7 で。誤答 0、型未確認の充填物を持つ FILLED/TIE 0。
- G3: 経路づけの凍結 4 本（配置なし）と 2 本（r7）の misroutes 0、合成 `g3_synth` を同じ入力で流し直して配置なしで誤って振った数 0。r7 は第 1 ラウンドの 1 から増えない。D2-2 の影響として r7 の 2 本の単位ごとの状態を第 1 ラウンドと比べる。
- G4: `g4_probe` の写しを流し、入力の sha256 と `summary` が第 1 ラウンドと同じ（`basis_policy.py` は第 2 ラウンドで変えない）。
- G5: r7 は作り直さない。`verify` が `OK`、`content_sha256` が第 1 ラウンドと同じ。
- G7: `pytest tests`（最後に 1 回）の失敗集合が基線から増えない。基線に無い失敗は環境由来だけ。K の id が残れば改訂を見直す。

**この文書の担当**: K3・K4・D1（B2）。

**B2 の追認**: 監査役は D1 の比較を **正規化しない完全一致** と追認した（2026-10-04 00:05）。チケットの文言「NFKC 正規化後の完全一致」は撤回する。理由: 攻撃 `tests/attack/test_attack_w5c_confirmation_text_binding.py` の `[nfkc]` の反例（`コードはＡＢＣです。` の確認で `コードはABCです。` を格上げすると、表記が違う＝別の文を人が確かめたことになる）。安全側に倒す。第 1 ラウンドの `w5d-prereg` 区間の B-J2 の文言は残し、この節が置き換える。コードは変えない。

<!-- w5d2-prereg:end -->

<!-- w5d2-amended:begin -->
#### `tests/test_basis_policy_form.py` (before = git show c875ed3:tests/test_basis_policy_form.py)

Added (helpers / tests, not amendments): `_hand_over_memo`

##### `test_a_document_answer_gets_a_borrowed_form_and_keeps_its_text_and_sources` — before

```python
def test_a_document_answer_gets_a_borrowed_form_and_keeps_its_text_and_sources(tmp_path, monkeypatch):
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    monkeypatch.delenv("VERA_SOVEREIGN_ROOT", raising=False)
    monkeypatch.delenv("VERA_SOVEREIGN_STORE", raising=False)
    original = _doc_answer()
    out, rc = bp.apply_to_ask(original, bp.AskPolicy(), query="花子は太郎に資料を渡しましたか？",
                              mode="round5", documents=["memo.txt"])
    assert rc == 0
    assert out["text"] == "可否: はい" and out["sources"] == original["sources"]
    assert out["form_text"] == FORM and out["form_source"] == "generated"
    assert out["form_witnesses"][0]["origin"] == "generated"
    assert "basis_origin" not in out
    assert ac.basis_origin(out["sources"]) is None
    assert out["basis_policy"]["outcome"] == "ANSWER_FORM_FROM_GENERATED"
    assert out["basis_policy"]["form"]["state"] == "FORM_BORROWED"
    assert out["basis_policy"]["basis"] == "HUMAN"
```

##### `test_a_document_answer_gets_a_borrowed_form_and_keeps_its_text_and_sources` — after

```python
def test_a_document_answer_gets_a_borrowed_form_and_keeps_its_text_and_sources(tmp_path, monkeypatch):
    _hand_over_memo(tmp_path, monkeypatch, HUMAN)      # W5-d2 (K3)
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    monkeypatch.delenv("VERA_SOVEREIGN_ROOT", raising=False)
    monkeypatch.delenv("VERA_SOVEREIGN_STORE", raising=False)
    original = _doc_answer()
    out, rc = bp.apply_to_ask(original, bp.AskPolicy(), query="花子は太郎に資料を渡しましたか？",
                              mode="round5", documents=["memo.txt"])
    assert rc == 0
    assert out["text"] == "可否: はい" and out["sources"] == original["sources"]
    assert out["form_text"] == FORM and out["form_source"] == "generated"
    assert out["form_witnesses"][0]["origin"] == "generated"
    assert "basis_origin" not in out
    assert ac.basis_origin(out["sources"]) is None
    assert out["basis_policy"]["outcome"] == "ANSWER_FORM_FROM_GENERATED"
    assert out["basis_policy"]["form"]["state"] == "FORM_BORROWED"
    assert out["basis_policy"]["basis"] == "HUMAN"
```

##### `test_a_failed_borrowing_leaves_the_human_answer_as_it_was` — before

```python
def test_a_failed_borrowing_leaves_the_human_answer_as_it_was(tmp_path, monkeypatch):
    _index(tmp_path, {"local": ["次郎が花子に本を渡さなかった。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    original = _doc_answer()
    out, rc = bp.apply_to_ask(original, bp.AskPolicy(), query="q", mode="round5", documents=["memo.txt"])
    assert rc == 0 and "form_text" not in out and "form_source" not in out
    assert {k: v for k, v in out.items() if k != "basis_policy"} == original
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["basis_policy"]["form"]["state"] == "FORM_NO_CANDIDATE"
    assert out["basis_policy"]["form"]["reasons"]["CAND_CENTER_DIFFERS"] == 1
```

##### `test_a_failed_borrowing_leaves_the_human_answer_as_it_was` — after

```python
def test_a_failed_borrowing_leaves_the_human_answer_as_it_was(tmp_path, monkeypatch):
    _hand_over_memo(tmp_path, monkeypatch, HUMAN)      # W5-d2 (K3)
    _index(tmp_path, {"local": ["次郎が花子に本を渡さなかった。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    original = _doc_answer()
    out, rc = bp.apply_to_ask(original, bp.AskPolicy(), query="q", mode="round5", documents=["memo.txt"])
    assert rc == 0 and "form_text" not in out and "form_source" not in out
    assert {k: v for k, v in out.items() if k != "basis_policy"} == original
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["basis_policy"]["form"]["state"] == "FORM_NO_CANDIDATE"
    assert out["basis_policy"]["form"]["reasons"]["CAND_CENTER_DIFFERS"] == 1
```

##### `test_the_borrowing_takes_no_role_from_the_generated_sentence_end_to_end` — before

```python
def test_the_borrowing_takes_no_role_from_the_generated_sentence_end_to_end(tmp_path, monkeypatch):
    # the human document has two roles; the only generated row has three: nothing is added
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    human = "花子は資料を渡した。"
    out, _rc = bp.apply_to_ask(_doc_answer(human), bp.AskPolicy(), query="q", mode="round5",
                               documents=["memo.txt"])
    assert "form_text" not in out and out["basis_policy"]["form"]["reasons"]["CAND_ROLES_DIFFER"] == 1
```

##### `test_the_borrowing_takes_no_role_from_the_generated_sentence_end_to_end` — after

```python
def test_the_borrowing_takes_no_role_from_the_generated_sentence_end_to_end(tmp_path, monkeypatch):
    # the human document has two roles; the only generated row has three: nothing is added
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    human = "花子は資料を渡した。"
    _hand_over_memo(tmp_path, monkeypatch, human)      # W5-d2 (K3)
    out, _rc = bp.apply_to_ask(_doc_answer(human), bp.AskPolicy(), query="q", mode="round5",
                               documents=["memo.txt"])
    assert "form_text" not in out and out["basis_policy"]["form"]["reasons"]["CAND_ROLES_DIFFER"] == 1
```

#### `tests/test_basis_policy_w5c_r3.py` (before = git show c875ed3:tests/test_basis_policy_w5c_r3.py)

Added (helpers / tests, not amendments): `_hand_over_memo`

##### `test_r3_a_document_the_user_handed_over_is_answered_unchanged` — before

```python
@pytest.mark.parametrize("origin", ORIGINS_UNSET, ids=lambda o: f"origin-{o!r}")
def test_r3_a_document_the_user_handed_over_is_answered_unchanged(origin):
    src = _fsrc("document", origin, source="memo.txt")
    result = _synthetic("answer", "ANSWER", [src], text=BODY)
    before = copy.deepcopy(result)
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query=Q, mode="round5", documents=MEMO_ARG)
    assert rc == 0 and result == before
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["basis"] == "HUMAN"
    assert out["basis_policy"]["counts"]["human"] == 1 and out["basis_policy"]["counts"]["unknown_origin"] == 0
    assert {k: v for k, v in out.items() if k != "basis_policy"} == before
    assert out["kind"] == "answer" and out["verdict"] == "ANSWER"
```

##### `test_r3_a_document_the_user_handed_over_is_answered_unchanged` — after

```python
@pytest.mark.parametrize("origin", ORIGINS_UNSET, ids=lambda o: f"origin-{o!r}")
def test_r3_a_document_the_user_handed_over_is_answered_unchanged(origin, tmp_path, monkeypatch):
    _hand_over_memo(tmp_path, monkeypatch, BODY)      # W5-d2 (K3): the document exists and holds the source's text
    src = _fsrc("document", origin, source="memo.txt")
    result = _synthetic("answer", "ANSWER", [src], text=BODY)
    before = copy.deepcopy(result)
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query=Q, mode="round5", documents=MEMO_ARG)
    assert rc == 0 and result == before
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["basis"] == "HUMAN"
    assert out["basis_policy"]["counts"]["human"] == 1 and out["basis_policy"]["counts"]["unknown_origin"] == 0
    assert {k: v for k, v in out.items() if k != "basis_policy"} == before
    assert out["kind"] == "answer" and out["verdict"] == "ANSWER"
```

##### `test_r3_a_generated_sentence_next_to_the_users_document_is_mixed_not_unknown_origin` — before

```python
def test_r3_a_generated_sentence_next_to_the_users_document_is_mixed_not_unknown_origin():
    out, _rc = bp.apply_to_ask(_doc_result(extra=[GEN]), bp.AskPolicy(), query=Q, mode="round5", documents=MEMO_ARG)
    assert out["basis_policy"]["basis"] == "MIXED" and out["verdict"] == "UNKNOWN_BASIS_NOT_IN_TABLE"
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and _state(out) == "abstain"
    assert out["withheld"]["unknown_origin_source_count"] == 0
```

##### `test_r3_a_generated_sentence_next_to_the_users_document_is_mixed_not_unknown_origin` — after

```python
def test_r3_a_generated_sentence_next_to_the_users_document_is_mixed_not_unknown_origin(tmp_path, monkeypatch):
    _hand_over_memo(tmp_path, monkeypatch, BODY)      # W5-d2 (K3)
    out, _rc = bp.apply_to_ask(_doc_result(extra=[GEN]), bp.AskPolicy(), query=Q, mode="round5", documents=MEMO_ARG)
    assert out["basis_policy"]["basis"] == "MIXED" and out["verdict"] == "UNKNOWN_BASIS_NOT_IN_TABLE"
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and _state(out) == "abstain"
    assert out["withheld"]["unknown_origin_source_count"] == 0
```

##### `test_r3_the_withheld_count_is_the_classified_count` — before

```python
@pytest.mark.parametrize("mode, documents, sources", [
    ("legacy", [], [_fsrc("local", None)]),
    ("legacy", [], [_fsrc("local", "zzz")]),
    ("legacy", [], [_fsrc("general", None), _fsrc("jawiki", "MISSING")]),
    ("legacy", [], [_fsrc("document", None), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), _fsrc("general", None)]),
    ("round5", MEMO_ARG, [_fsrc("document", ""), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), _fsrc("document", "zzz"), _fsrc("local", None)]),
    ("round5", [], [_fsrc("document", None), GEN]),
    ("engine", MEMO_ARG, [_fsrc("document", None), _fsrc("MISSING", None)]),
], ids=lambda v: None)
def test_r3_the_withheld_count_is_the_classified_count(mode, documents, sources):
    result = _synthetic("answer", "ANSWER", copy.deepcopy(sources))
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query=Q, mode=mode, documents=list(documents))
    user_documents = mode == "round5" and bool(documents)
    assert "withheld" in out
    assert out["withheld"]["unknown_origin_source_count"] == len(bp._unknown_origin_sources(sources, user_documents))
    sc = bp.classify_sources(sources, user_documents=user_documents)
    assert out["withheld"]["unknown_origin_source_count"] == sc.unknown_origin + sum(sc.unknown_origin_values.values())
```

##### `test_r3_the_withheld_count_is_the_classified_count` — after

```python
@pytest.mark.parametrize("mode, documents, sources", [
    ("legacy", [], [_fsrc("local", None)]),
    ("legacy", [], [_fsrc("local", "zzz")]),
    ("legacy", [], [_fsrc("general", None), _fsrc("jawiki", "MISSING")]),
    ("legacy", [], [_fsrc("document", None), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), _fsrc("general", None)]),
    ("round5", MEMO_ARG, [_fsrc("document", ""), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), _fsrc("document", "zzz"), _fsrc("local", None)]),
    ("round5", [], [_fsrc("document", None), GEN]),
    ("engine", MEMO_ARG, [_fsrc("document", None), _fsrc("MISSING", None)]),
], ids=lambda v: None)
def test_r3_the_withheld_count_is_the_classified_count(mode, documents, sources, tmp_path, monkeypatch):
    if documents:      # W5-d2 (K3): the document that is handed over exists and holds the text of each document source (the comparison side below keeps the self-reporting call)
        _hand_over_memo(tmp_path, monkeypatch, *[s["text"] for s in sources if s.get("family") == "document"])
    result = _synthetic("answer", "ANSWER", copy.deepcopy(sources))
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query=Q, mode=mode, documents=list(documents))
    user_documents = mode == "round5" and bool(documents)
    assert "withheld" in out
    assert out["withheld"]["unknown_origin_source_count"] == len(bp._unknown_origin_sources(sources, user_documents))
    sc = bp.classify_sources(sources, user_documents=user_documents)
    assert out["withheld"]["unknown_origin_source_count"] == sc.unknown_origin + sum(sc.unknown_origin_values.values())
```

##### `_sovereign_with_yes` — before

```python
def _sovereign_with_yes(tmp_path, monkeypatch, query=Q):
    root = tmp_path / "sov"
    assert sov.create(str(root), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
    _use(monkeypatch, root, "s1")
    record = {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation",
              "confirm_id": "abc", "query": query, "claim": OTHER_CLAIM, "generated_sources": [],
              "table_version": 1, "origin": "human_confirmed"}
    assert sov.append_basis_confirmation(str(root), "s1", record)["verdict"] == "APPENDED"
    return root
```

##### `_sovereign_with_yes` — after

```python
def _sovereign_with_yes(tmp_path, monkeypatch, query=Q, claim=OTHER_CLAIM):
    root = tmp_path / "sov"
    assert sov.create(str(root), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
    _use(monkeypatch, root, "s1")
    record = {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation",
              "confirm_id": "abc", "query": query, "claim": claim, "generated_sources": [],
              "table_version": 1, "origin": "human_confirmed"}
    assert sov.append_basis_confirmation(str(root), "s1", record)["verdict"] == "APPENDED"
    return root
```

##### `test_r3_a_recorded_yes_still_lifts_a_generated_answer` — before

```python
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_r3_a_recorded_yes_still_lifts_a_generated_answer(tmp_path, monkeypatch, human, ref):
    root = _sovereign_with_yes(tmp_path, monkeypatch)
    before = _snapshot(root)
    out, rc = _ask_with_record([GEN], "answer", "ANSWER", human=human, ref=ref)
    assert rc == 0 and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["text"] == OTHER_CLAIM and out["kind"] == "answer"
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 1
    assert out["basis_policy"]["sovereign"]["confirmed_records_not_used"] == 0
    assert _snapshot(root) == before
```

##### `test_r3_a_recorded_yes_still_lifts_a_generated_answer` — after

```python
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_r3_a_recorded_yes_still_lifts_a_generated_answer(tmp_path, monkeypatch, human, ref):
    # W5-d (D1) proposal: the human confirmed THE SENTENCE the result now carries (the claim of the result is its ``text``)
    claim = _synthetic("answer", "ANSWER", [])["text"]
    root = _sovereign_with_yes(tmp_path, monkeypatch, claim=claim)
    before = _snapshot(root)
    out, rc = _ask_with_record([GEN], "answer", "ANSWER", human=human, ref=ref)
    assert rc == 0 and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["text"] == claim and out["kind"] == "answer"
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 1
    assert out["basis_policy"]["sovereign"]["confirmed_records_not_used"] == 0
    assert _snapshot(root) == before
```

##### `test_r3_the_users_own_document_answer_is_kept_and_the_record_is_not_used` — before

```python
def test_r3_the_users_own_document_answer_is_kept_and_the_record_is_not_used(tmp_path, monkeypatch):
    root = _sovereign_with_yes(tmp_path, monkeypatch)
    before = _snapshot(root)
    out, rc = _ask_with_record([DOC], "answer", "ANSWER", human=False, ref=False, mode="round5", documents=MEMO_ARG)
    assert rc == 0 and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["text"] == "窓が光ります。" and OTHER_CLAIM not in json.dumps(out, ensure_ascii=False)
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 0
    assert out["basis_policy"]["sovereign"]["confirmed_records_not_used"] == 1
    assert _snapshot(root) == before
```

##### `test_r3_the_users_own_document_answer_is_kept_and_the_record_is_not_used` — after

```python
def test_r3_the_users_own_document_answer_is_kept_and_the_record_is_not_used(tmp_path, monkeypatch):
    root = _sovereign_with_yes(tmp_path, monkeypatch)
    _hand_over_memo(tmp_path, monkeypatch, BODY)      # W5-d2 (K3)
    before = _snapshot(root)
    out, rc = _ask_with_record([DOC], "answer", "ANSWER", human=False, ref=False, mode="round5", documents=MEMO_ARG)
    assert rc == 0 and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["text"] == "窓が光ります。" and OTHER_CLAIM not in json.dumps(out, ensure_ascii=False)
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 0
    assert out["basis_policy"]["sovereign"]["confirmed_records_not_used"] == 1
    assert _snapshot(root) == before
```

<!-- w5d2-amended:end -->

## W5-d 第 2 ラウンド（W5-d2）の測定
<!-- w5d2-measured:begin -->
測定の時刻: 2026-10-04 01:22:30 +0900。出力はすべて `artifacts/w5-d/r2/`（ファイル名を添える）。中間職のレビュー r1（`review-impl/W5-d2/review.r1.md`）の M1〜M4（改訂したテストの前後の全文・測定の区間・失敗集合のファイル・報告）に応えてこの区間と `w5d2-amended` 区間を書いた。製品とテストのコードはレビューのあとに変えていない（`code_sha_r2b_start.txt` と `code_sha_r2b_end.txt` が同じ）。受入の測定はこのとき全部流し直した（`g1_rerun_r2b.txt`・`g2_rerun_r2b.txt`・`g3_rerun_r2b.txt`・`q1_observe_cmp_r2b.txt`・`g4_compare_r2b.txt`・`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`。出力は前の流しと byte 一致。違いが無かったことの確認なので前の流しのファイルも残す）。

**受入基準**（第 2 ラウンド）
- **G1**（`g1_rerun_r2b.txt`）: 攻撃の写し 36 本が `36 passed`、K の 72 関数（82 id）が全部通る（`102 passed`）、新しいテスト（第 1 ラウンドの 5 本＋第 2 ラウンドの追記）が `113 passed`。G1-b: 写しと原本の差は先頭行と改訂した関数・足したヘルパの中だけ（`g1b_hunks.txt`、`attack_copy_revisions.diff`。w5c の 2 本は原本と同一、`data/` も同一）。
- **G2**（`g2_185_*.json(l)`・`g2_attack120_r7.json(l)`・`g2_rerun_r2b.txt`）: `VERA_PLACEMENT` なしの 185 問は第 1 ラウンドの出力と byte 一致（place: 正答/誤答/FALSE_NONE/棄権 = 38 / 0 / 4 / 143、noplace: 26 / 0 / 4 / 155）。`VERA_PLACEMENT=r7`: place 73 / 0 / 6 / 106、noplace 66 / 0 / 8 / 111。誤答 0、型未確認の FILLED/TIE 0（4 通りとも `unchecked_fillers_in_FILLED_TIE` は 0・0・0・0）。正答は減っていない（第 1 ラウンドと同じか、r7 で増える）。攻撃の 120 問（r7、116 問は正解なしで採点されない）: FILLED 29・TIE 5、型未確認の FILLED/TIE 0、`wrong` 0 件。A01（`EN08-01`）は `NO_TYPED_CANDIDATE`（`letter`・`note` は `TYPE_UNCHECKED`）で FILLED/TIE にならない（`g2_r7_notes.txt`）。中間職の凍結 64 問・56 問は実装役が開かない約束なので測っていない（中間職が測る）。
- **G3**（`g3_rerun_r2b.txt`・`g3_*`）: 経路づけの凍結 4 本（配置なし）の misroutes は 0, 0, 0, 0、r7 の 2 本は 0, 0。合成 `g3_synth`（入力の sha256 は `g3_synth_inputs_check.txt` で第 1 ラウンドの凍結と一致）: 配置なし misroutes 0・普通名詞に振った数 0、r7 misroutes 1（第 1 ラウンドと同じ 1 件。`委員会` が推定の GROUP_ORG で通る既知の穴）、基点 1（`g3_synth_results/g3_synth_counts.json`）。D2-2 の影響: r7 の 2 本の 118 件を、D2-2 の呼び出しを外した写しと単位ごとに比べて変化した件数は 0（`g3_r7_diff.txt`）。
- **G4**（`g4_result.json`・`g4_compare_r2b.txt`）: 入力の sha256 と `summary` が第 1 ラウンドと同じ（自己申告の文書 16 件で `ANSWER` 0、文面違いの確認記録 15 件で `ANSWER` 0・旧文が返った 0、対照は 4/4 と 2/2 で答える）。`verantyx/basis_policy.py` は第 2 ラウンドで変えていない（sha256 が `files_start.sha256` と同じ）。
- **G5**（`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`）: r7 は作り直していない。`verify` が run1・run2 とも `OK`、`content_sha256` は第 1 ラウンドと同じ。`coarse_place.py`・`tools/build_coarse_placement.py` は第 2 ラウンドで変えていない。K5 の写しが通り、r6_audit_summary.json not_confirmed: 13 words; invariant_errors [] byte_differences []、第 1 ラウンドの 13 語と同じ集合（`命じる` を含む）。
- **平叙文の観測**（`q1_observe_cmp_r2b.txt`）: `o1_bytes.py --child` の出力が、配置なしと `VERA_PLACEMENT=r7` の 2 通りとも基点と byte 一致（`same: base vs now` が 2 行。この流しは前の流しとも byte 一致）。
- **G7**（`pytest_full.txt`・`after_failures.txt`・`new_failures.txt`・`fixed_failures.txt`・`new_failures_explained.txt`）: 全体テストの最終行 `117 failed, 11981 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 362.65s (0:06:02)`。失敗は一意に 117 件、基線に無い失敗は 2 件（`tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches`、`tests/test_gen_coarse_evidence.py::test_the_stop_signal_ends_the_run_with_an_interrupted_record`）、基線にあって今は通る失敗は 0 件。基線に無い失敗の理由は `new_failures_explained.txt`（環境由来だけ）。K の id は失敗集合に 0 件。

**K3（存在しない文書を人の出典にする 10 件）の改訂**（裁定 B1。前後の全文は上の `w5d2-amended` 区間。`changed_functions_k3k4k5.txt`）: `tests/test_basis_policy_form.py` の 3 関数と `tests/test_basis_policy_w5c_r3.py` の 4 関数（パラメタ化を含めて 10 id）。期待の値は変えていない。「存在しない `memo.txt` を人の出典にする」こと自体が退役した振る舞い（A1: 出典の本文が実際に渡した文書の中にあること）で、期待を `unknown_origin` に変えると攻撃 A1 と同じテストになって主題「ユーザーが渡した文書の答えは保たれる」が消えるので、渡した文書を実在させた: 各モジュールに足したヘルパ `_hand_over_memo(tmp_path, monkeypatch, *texts)` が `tmp_path/memo.txt` に出典の `text` を 1 行ずつ書いて `monkeypatch.chdir(tmp_path)` する（conftest の autouse にはしていない。木の中に `memo.txt` は作らない）。memo の中身は出典の `text` だけで、余計な文は入れていない。

**K4（別の文の記録で格上げ 4 件）の改訂**: `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer`（パラメタ 4 id）の補助関数 `_sovereign_with_yes` に、既定 `OTHER_CLAIM` の `claim` 引数を足し、関数の中で今の生成文を claim にした（`artifacts/w5-d/k4_proposal.diff` を `patch -p0` でそのまま当てた。`k4_patch_output.txt`）。D1 の規則（確認済みの文と現在の生成文が違えば格上げしない）の下で「確認記録が今の文を確かめたもの」になる。

**D1（B2）の追認**: 監査役は D1 の比較を正規化しない完全一致と追認した（2026-10-04 00:05。上の `w5d2-prereg` 区間）。チケットの文言「NFKC 正規化後の完全一致」は撤回。理由: 攻撃 `tests/attack/test_attack_w5c_confirmation_text_binding.py` の `[nfkc]` の反例（`コードはＡＢＣです。` の確認で `コードはABCです。` を格上げすると、表記が違う＝別の文を人が確かめたことになる）。安全側に倒す。コードは変えていない（`basis_policy.py` の sha256 は第 1 ラウンドの終わりと同じ）。確かめ: W5-c の写し 2 本（`[nfkc]` を含む）が通る（`g1_rerun_r2b.txt`）、`tests/test_basis_policy_w5d.py` の `nfkc` の変種が格上げしない（既存）。

**G4**（`g4_result.json`・`g4_compare_r2b.txt`）: 入力の sha256 と `summary` が第 1 ラウンドと同じ。自己申告の文書の `ANSWER` 0（16 件）、文面違いの確認記録の `ANSWER` 0（15 件、旧文が返った 0）。

**第 2 ラウンドで置き換わった第 1 ラウンドの記述**（第 1 ラウンドの `w5d-*` 区間の中は 1 文字も変えていない。元の行は残し、この一覧が上書きする）
- 「B-J2 / チケットの文言: D1 は NFKC 正規化後の完全一致」と、第 1 ラウンドの既知の穴 4 の書きぶり「チケットの文言より狭い」→ 裁定 B2 でチケットの文言のほうが撤回された（正規化しない完全一致が正）。
- 「K3・K4 は宣言した衝突」→ 裁定 B1 で改訂が許可され、上のとおり改訂した。

**既知の穴**: 確認済みの文と現在の生成文が表記だけ違うとき（空白・句読点・NFKC の違い）は格上げされず、再確認を求める（安全側の過剰棄権）。
**この文書の担当の測定は上のとおり。全体の受入と判断は `artifacts/w5-d/DECISIONS.md` の「第 2 ラウンド（W5-d2）」と `artifacts/w5-d/r2/`。**
<!-- w5d2-measured:end -->

## W5-e の事前登録: A-3 自己申告の `human_confirmed`（分類の規則 v4）
<!-- w5e-a3-prereg:begin -->
事前登録の時刻: 2026-10-04 03:45:31 +0900（`date '+%F %T %z'` の出力）。この節は A-3 の攻撃の写しと新しいテスト（`tests/test_basis_policy_w5e.py`・`artifacts/w5-e/h4_inputs.json`）を書く前、製品コード（`verantyx/basis_policy.py`）を直す前に確定した。上の節は 1 文字も変えない。

**命中（W5-d の攻撃 A-3、`tests/attack/test_attack_w5d.py::test_a1_self_declared_human_origin_cannot_replace_missing_document_text`）**: `family == "document"`・`origin == "human_confirmed"` を **自己申告** した出典は、`_class_of` の `if origin == "human_confirmed": return "human"` の早期 return が `_document_text_holds`（A1 の本文照合）の前に来るため、本文に無い text でも `human` になり `HUMAN → ANSWER` になる。

### 規則 v4（`_class_of`。上から最初に当たったもの）
1. dict でない → `unreadable`（今どおり）
2. `origin == "generated"` → `generated`（今どおり。生成と名乗るものは格上げしない）
3. `family == "document"` かつ `origin == "human_confirmed"` → A1 と同じ本文照合: `user_documents` が真で、`document_texts is None` または `_document_text_holds(src, document_texts)` なら `human`、それ以外は `unknown_origin`
4. `origin == "human_confirmed"` かつ `family == "memory_sovereign"` → `human`（ソブリンの記録由来。docs の説明: この出典は `store_id`・`confirm_id` を持つ。**それを条件にはしない**: 持たない `memory_sovereign` を人とする既存テストがあり、文字列は自己申告もできるので守りとして強くならない）
5. `origin == "human_confirmed"`（それ以外の `family`: `local`・`web`・`user`・未知・鍵なし）→ `unknown_origin`（棄権側）
6. 以降は今どおり（索引の系列 → `unknown_origin`、`origin` の値あり → `non_evidence`、`family == "user"` → `request_text`、`user_documents` が真の document → A1 の照合、それ以外 → `unknown_origin`）

- 「origin に関わらず本文照合」は **「どの origin を名乗っても、本文照合なしには人にならない」**（下げる向きだけ）と読む。`document` ＋ `generated`・`constructed`・`testimony` は今どおり `generated`／`non_evidence`（照合で人に上げない）。
- `CLASSIFY_VERSION = 4`（3 から）。`TABLE_VERSION`・`CONFIRM_ID_VERSION`・`SCHEMA` は変えない。`basis_policy` の注記の `classify_version` は 4。
- ソブリン由来の `human_confirmed`（W6-a の D の格上げ。`apply_to_ask` が記録から作る `family: "memory_sovereign"` の出典）は従来どおり `ANSWER_HUMAN_BASIS`（新しいテストで確かめる）。

### 旧版 v3 の `_class_of`（変更前の全文。直す前に貼る）
```python
def _class_of(src: Any, user_documents: bool = False, document_texts: Optional[Sequence[str]] = None) -> str:
    """The class of one source: the rules of docs/BASIS_POLICY.md section prereg-w5c-r3 (the earliest rule that applies wins).

    A human source is one whose origin is declared human (``human_confirmed``), the request text itself
    (``family == "user"``) and, only when ``user_documents`` is true (the caller handed these documents over in
    this very call), a ``family == "document"`` source with no origin WHOSE TEXT IS IN THOSE DOCUMENTS (W5-d: with
    ``document_texts``, the bodies of the documents handed over, it must be found in them -- ``_document_text_holds``;
    a document source not found there is ``unknown_origin``). ``document_texts is None`` is the older contract: the
    caller has checked it himself (the product never calls it so: ``apply_to_ask`` always passes the bodies).
    Everything else with no origin is ``unknown_origin``: it is not a human source and it is not known to be a
    generated one either (absent, ``None``, ``""``, a different spelling of a declared value, any unknown value,
    a family outside the index)."""
    if not isinstance(src, dict):
        return "unreadable"
    origin = src.get("origin")
    if origin == "generated":
        return "generated"
    if origin == "human_confirmed":
        return "human"
    if _is_index_family(src) and not (isinstance(origin, str) and origin in DECLARED_NON_EVIDENCE):
        return "unknown_origin"
    if origin is not None:
        return "non_evidence"
    if src.get("family") == "user":
        return "request_text"
    if user_documents and src.get("family") == "document":
        if document_texts is None or _document_text_holds(src, document_texts):
            return "human"
        return "unknown_origin"
    return "unknown_origin"
```
（v3 の規則表は上の「W5-c-r3-1」と W5-d の B-J1。`CLASSIFY_VERSION = 3`）

### 宣言する規則どうしの衝突 K-A3（実装役は解かずに宣言する。判断は監査役）
W5-c 第 3 ラウンドの裁定は「document の出典に `human_confirmed` を足して人にする」テストを固定している。A-3 はこれを退役させる（自己申告の `human_confirmed` は本文照合を通る）。落ちる見込み: `tests/test_basis_policy_w5c_r3.py`・`tests/test_basis_policy_*.py` の該当テスト（実測の一覧は測定の節）と、版を 3 と固定した 4 件（`test_basis_policy_w5c_r3.py::test_r3_the_versions_are_as_registered`・`::test_r3_the_policy_note_carries_the_classify_version_3`、`test_basis_policy_w5c.py::test_w5c_the_versions_and_the_table_are_as_registered`・`::test_w5c_the_policy_note_carries_the_new_versions_and_numbers`）。**実装役はテストを書き換えず**、落ちた id を宣言する。

### 既知の穴（先に書く）
- 自己申告の `family: "memory_sovereign"` ＋ `origin: "human_confirmed"` は、`store_id`・`confirm_id` が無くても人になる（上記のとおり条件にしない）。呼び出し側の dict を信じる契約の限界。
- `generated` と名乗る出典は `document` の本文照合の対象にもならず `generated` のまま（下げる向きなので安全側）。

### 受入（H4。測る前に固定）
- 凍結の反例 31 件（`b_check.py`、W5-c・W5-d）で自己申告からの `ANSWER_*` が 0（`SUMMARY {"n": 31, "fails": []}`）。
- 自己申告の `human_confirmed` の反例 5 件（`artifacts/w5-e/h4_inputs.json`。入力は先に凍結し sha256 を残す）で `ANSWER_*` が 0。
- ソブリン由来の \`human_confirmed\` は従来どおり ANSWER（テスト）。
<!-- w5e-a3-prereg:end -->


## W5-e の測定: A-3 自己申告の `human_confirmed`（分類の規則 v4）
<!-- w5e-a3-measured:begin -->
測定の時刻: 2026-10-04 04:10:06 +0900。出力はすべて `artifacts/w5-e/`（ファイル名を添える）。製品の変更は `verantyx/basis_policy.py` の `CLASSIFY_VERSION`（3 → 4）・`_class_of` の `human_confirmed` の分岐・docstring だけ。

- **凍結と「直す前に落ちる」記録**: 入力 `h4_inputs.json`（6 件）の sha256 とテスト `tests/test_basis_policy_w5e.py`・攻撃の写し `tests/attack/test_attack_w5d.py`（原本とバイト一致。`attack_copies.sha256`）は `frozen_a3.sha256`（時刻 `frozen_a3_at.txt`）。直す前の木で新しいテストと攻撃 A-3 が失敗: `a3_before_fail.txt`（`18 failed, 8 passed`）。
- **H4**: 凍結の反例 31 件（`b_check.py`、W5-c・W5-d）は直す前も後も `SUMMARY {"n": 31, "fails": []}`（`h4_b_check.txt`、`before/h4_b_check.txt`）。自己申告の `human_confirmed` の反例 6 件（document＋本文に無い text・document＋文書を渡さない・local・web・未知の系列・user）で `ANSWER_*` は 0。対照 2 件（本文にある document の自己申告・`memory_sovereign`）は従来どおり答える。ソブリンの確認記録で格上げした答えの出典（`family: memory_sovereign`・`store_id`・`confirm_id`）は v4 でも `human` で `ANSWER_HUMAN_BASIS`（`tests/test_basis_policy_w5e.py` が通る。`new_tests_run.txt`: `25 passed`）。攻撃 A-3（`test_a1_self_declared_human_origin_cannot_replace_missing_document_text`）は通る（`h1_attack.txt`）。
- **宣言した衝突 K-A3**（書き換えていない。`a3_new_failures.txt`、基線に無い失敗は 13 件）:
- `tests/test_basis_policy_entry.py::test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note`
- `tests/test_basis_policy_entry.py::test_a_mix_of_human_and_generated_sources_abstains[False-False]`
- `tests/test_basis_policy_entry.py::test_a_mix_of_human_and_generated_sources_abstains[False-True]`
- `tests/test_basis_policy_entry.py::test_a_mix_of_human_and_generated_sources_abstains[True-False]`
- `tests/test_basis_policy_entry.py::test_a_mix_of_human_and_generated_sources_abstains[True-True]`
- `tests/test_basis_policy_form.py::test_other_routes_do_not_attempt_the_borrowing[legacy-docs0]`
- `tests/test_basis_policy_form.py::test_other_routes_do_not_attempt_the_borrowing[round5-docs1]`
- `tests/test_basis_policy_w5c.py::test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis`
- `tests/test_basis_policy_w5c.py::test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them`
- `tests/test_basis_policy_w5c.py::test_w5c_the_policy_note_carries_the_new_versions_and_numbers`
- `tests/test_basis_policy_w5c.py::test_w5c_the_versions_and_the_table_are_as_registered`
- `tests/test_basis_policy_w5c_r3.py::test_r3_the_policy_note_carries_the_classify_version_3`
- `tests/test_basis_policy_w5c_r3.py::test_r3_the_versions_are_as_registered`
  内訳: `human_confirmed` を document 以外の系列で自己申告して人にしていたテスト 9 件＋版を 3 と固定した 4 件。基線 115 件に含まれるものは 0 件。
- **既知の穴**: 自己申告の `family: "memory_sovereign"` ＋ `origin: "human_confirmed"` は、`store_id`・`confirm_id` が無くても人になる（条件にしていない。`test_basis_policy_table.py` などが `store_id` の無い `memory_sovereign` の出典を人としているため）。呼び出し側の dict を信じる契約の限界。
<!-- w5e-a3-measured:end -->

## W5-e 第 2 ラウンド: K-A3 の改訂（監査役の判断 2026-10-04 04:42）
<!-- w5e2-ka3:begin -->
監査役の判断: 「K-A3（13）: W5-c r3 の「document 以外の系列に `human_confirmed` を付けて人とする」テスト 9 件と `CLASSIFY_VERSION == 3` の固定 4 件は、退役させた振る舞い（出所の申告を信じる）の固定なので改訂を許可（名前不変・前後の全文を docs。版は 4）」。A-3 は `human_confirmed` を人と分類するのを `family == "memory_sovereign"` のときだけにした（`family == "document"` は本文照合、それ以外の family の自己申告は `unknown_origin`）。

- **人の出典の入力 5 箇所（9 件）**: 入力の `{**HUMAN, "origin": "human_confirmed"}`（`HUMAN` は `family: general` の自己申告）を `{**HUMAN, "family": "memory_sovereign", "origin": "human_confirmed"}` にする（ソブリンの記録由来の人の出典）。**期待は 1 文字も変えない**。9 件 = `test_basis_policy_entry.py` の 2 関数（`test_a_mix_…` は `human`×`ref` の 4 引数・`test_a_human_answer_…` は 1）、`test_basis_policy_w5c.py` の 2 関数、`test_basis_policy_form.py::test_other_routes_do_not_attempt_the_borrowing`（`mode` の引数）。
- **版 4 件**: `CLASSIFY_VERSION`／`classify_version` の `3` を `4` に（関数名の `_3` は変えない。`CONFIRM_ID_VERSION`・`TABLE_VERSION` は不変）。

### 改訂前の全文（各関数は、この追記の直前の作業ツリー。第 1 ラウンドでは変えていない＝基点 ca66d3e と同じ）

#### `tests/test_basis_policy_entry.py::test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note` — 改訂前
```python
def test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    result = _synthetic("answer", "ANSWER", [USER, {**HUMAN, "origin": "human_confirmed"}])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert rc == 0 and _without(out, "basis_policy") == result
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["applied"] is True
```

#### `tests/test_basis_policy_entry.py::test_a_mix_of_human_and_generated_sources_abstains` — 改訂前
```python
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_a_mix_of_human_and_generated_sources_abstains(human, ref):
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    result = _synthetic("answer", "ANSWER", [{**HUMAN, "origin": "human_confirmed"}, GEN])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref),
                              query="q", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_BASIS_NOT_IN_TABLE"
    assert out["basis_policy"]["basis"] == "MIXED" and out["basis_policy"]["in_table"] is False
    assert out["basis_policy"]["outcome"] == "ABSTAIN"
```

#### `tests/test_basis_policy_w5c.py::test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them` — 改訂前
```python
def test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の HUMAN を明示の人（origin: human_confirmed）にした。期待は同じ
    sc = bp.classify_sources([_src("local", None), _src("x", "zzz"), GEN, {**HUMAN, "origin": "human_confirmed"}, USER, "junk"])
    assert set(sc.counts) == {"human", "generated", "non_evidence", "request_text", "unreadable"}
    assert sc.counts == {"human": 1, "generated": 1, "non_evidence": 1, "request_text": 1, "unreadable": 1}
    assert sc.unknown_origin == 1 and sc.unknown_origin_values == {"zzz": 1}
    assert sc.cited == 5 and sc.policy_basis == "UNKNOWN_ORIGIN" and sc.basis == "UNKNOWN_ORIGIN"
    d = sc.to_dict()
    assert d["unknown_origin"] == 1 and d["unknown_origin_by_family"] == {"local": 1}
    assert d["unknown_origin_values"] == {"zzz": 1}
```

#### `tests/test_basis_policy_w5c.py::test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis` — 改訂前
```python
def test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis():
    sc = bp.classify_sources([_src("x", "zzz")])
    assert sc.basis == "NONE" and sc.policy_basis == "UNKNOWN_ORIGIN"
    assert sc.counts["non_evidence"] == 1 and sc.non_evidence_by_origin == {"zzz": 1}
    assert bp.classify_sources([_src("x", "constructed")]).policy_basis == "NONE"
    assert bp.classify_sources([_src("x", "testimony")]).policy_basis == "NONE"
    assert bp.classify_sources([GEN]).policy_basis == "GENERATED"
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 最後の行の入力を明示の人にした（期待は同じ）。強める側の assert を 1 行足した
    assert bp.classify_sources([{**HUMAN, "origin": "human_confirmed"}]).policy_basis == "HUMAN"
    assert bp.classify_sources([HUMAN]).policy_basis == "UNKNOWN_ORIGIN"
```

#### `tests/test_basis_policy_form.py::test_other_routes_do_not_attempt_the_borrowing` — 改訂前
```python
@pytest.mark.parametrize("mode, docs", [("legacy", []), ("round5", [])])
def test_other_routes_do_not_attempt_the_borrowing(tmp_path, monkeypatch, mode, docs):
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    ans = _doc_answer(); ans["sources"] = [{**s, "origin": "human_confirmed"} for s in ans["sources"]]
    out, _rc = bp.apply_to_ask(ans, bp.AskPolicy(), query="q", mode=mode, documents=docs)
    assert "form_text" not in out and out["basis_policy"]["form"]["state"] == "NOT_ATTEMPTED_ROUTE"
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
```

#### `tests/test_basis_policy_w5c.py::test_w5c_the_versions_and_the_table_are_as_registered` — 改訂前
```python
def test_w5c_the_versions_and_the_table_are_as_registered():
    assert bp.TABLE_VERSION == 1 and bp.SCHEMA == "verantyx.basis_policy/1"
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 規則 7・8 が変わったので CLASSIFY_VERSION は 3（prereg-w5c-r3 節）
    assert bp.CLASSIFY_VERSION == 3 and bp.CONFIRM_ID_VERSION == 2
    assert len(bp.TABLE) == 24 and bp.BASES == ("HUMAN", "GENERATED", "NONE")
    assert bp.DECLARED_ORIGINS == ("generated", "human_confirmed", "constructed", "testimony")
    assert bp.UNKNOWN_ORIGIN == "UNKNOWN_ORIGIN"
```

#### `tests/test_basis_policy_w5c.py::test_w5c_the_policy_note_carries_the_new_versions_and_numbers` — 改訂前
```python
def test_w5c_the_policy_note_carries_the_new_versions_and_numbers():
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src("pro", "")]), bp.AskPolicy(), query="窓は？",
                               mode="legacy", documents=[])
    note = out["basis_policy"]
    assert note["schema"] == "verantyx.basis_policy/1" and note["table_version"] == 1
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 注記の classify_version は 3
    assert note["classify_version"] == 3 and note["confirm_id_version"] == 2
    assert note["counts"]["unknown_origin"] == 1 and note["counts"]["unknown_origin_by_family"] == {"pro": 1}
    assert out["withheld"]["unknown_origin_source_count"] == 1
```

#### `tests/test_basis_policy_w5c_r3.py::test_r3_the_versions_are_as_registered` — 改訂前
```python
def test_r3_the_versions_are_as_registered():
    assert bp.CLASSIFY_VERSION == 3 and bp.CONFIRM_ID_VERSION == 2 and bp.TABLE_VERSION == 1
    assert bp.SCHEMA == "verantyx.basis_policy/1" and len(bp.TABLE) == 24
```

#### `tests/test_basis_policy_w5c_r3.py::test_r3_the_policy_note_carries_the_classify_version_3` — 改訂前
```python
def test_r3_the_policy_note_carries_the_classify_version_3():
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_fsrc("general", None)]), bp.AskPolicy(), query=Q,
                               mode="legacy", documents=[])
    assert out["basis_policy"]["classify_version"] == 3 and out["basis_policy"]["confirm_id_version"] == 2
    assert out["basis_policy"]["table_version"] == 1
```

### 改訂後の全文（名前不変。変えたのは各関数の中の入力 1 箇所（または版の数字）と、その直前の注釈 1 行だけ）

#### `tests/test_basis_policy_entry.py::test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note` — 改訂後
```python
def test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 人の出典の入力を memory_sovereign（ソブリンの記録由来）にした（自己申告の human_confirmed は人にしない）。期待は同じ
    result = _synthetic("answer", "ANSWER", [USER, {**HUMAN, "family": "memory_sovereign", "origin": "human_confirmed"}])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert rc == 0 and _without(out, "basis_policy") == result
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["applied"] is True
```

#### `tests/test_basis_policy_entry.py::test_a_mix_of_human_and_generated_sources_abstains` — 改訂後
```python
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_a_mix_of_human_and_generated_sources_abstains(human, ref):
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 人の出典の入力を memory_sovereign（ソブリンの記録由来）にした（自己申告の human_confirmed は人にしない）。期待は同じ
    result = _synthetic("answer", "ANSWER", [{**HUMAN, "family": "memory_sovereign", "origin": "human_confirmed"}, GEN])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref),
                              query="q", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_BASIS_NOT_IN_TABLE"
    assert out["basis_policy"]["basis"] == "MIXED" and out["basis_policy"]["in_table"] is False
    assert out["basis_policy"]["outcome"] == "ABSTAIN"
```

#### `tests/test_basis_policy_w5c.py::test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them` — 改訂後
```python
def test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の HUMAN を明示の人（origin: human_confirmed）にした。期待は同じ
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 人の出典の入力を memory_sovereign（ソブリンの記録由来）にした（自己申告の human_confirmed は人にしない）。期待は同じ
    sc = bp.classify_sources([_src("local", None), _src("x", "zzz"), GEN, {**HUMAN, "family": "memory_sovereign", "origin": "human_confirmed"}, USER, "junk"])
    assert set(sc.counts) == {"human", "generated", "non_evidence", "request_text", "unreadable"}
    assert sc.counts == {"human": 1, "generated": 1, "non_evidence": 1, "request_text": 1, "unreadable": 1}
    assert sc.unknown_origin == 1 and sc.unknown_origin_values == {"zzz": 1}
    assert sc.cited == 5 and sc.policy_basis == "UNKNOWN_ORIGIN" and sc.basis == "UNKNOWN_ORIGIN"
    d = sc.to_dict()
    assert d["unknown_origin"] == 1 and d["unknown_origin_by_family"] == {"local": 1}
    assert d["unknown_origin_values"] == {"zzz": 1}
```

#### `tests/test_basis_policy_w5c.py::test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis` — 改訂後
```python
def test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis():
    sc = bp.classify_sources([_src("x", "zzz")])
    assert sc.basis == "NONE" and sc.policy_basis == "UNKNOWN_ORIGIN"
    assert sc.counts["non_evidence"] == 1 and sc.non_evidence_by_origin == {"zzz": 1}
    assert bp.classify_sources([_src("x", "constructed")]).policy_basis == "NONE"
    assert bp.classify_sources([_src("x", "testimony")]).policy_basis == "NONE"
    assert bp.classify_sources([GEN]).policy_basis == "GENERATED"
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 最後の行の入力を明示の人にした（期待は同じ）。強める側の assert を 1 行足した
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 人の出典の入力を memory_sovereign（ソブリンの記録由来）にした（自己申告の human_confirmed は人にしない）。期待は同じ
    assert bp.classify_sources([{**HUMAN, "family": "memory_sovereign", "origin": "human_confirmed"}]).policy_basis == "HUMAN"
    assert bp.classify_sources([HUMAN]).policy_basis == "UNKNOWN_ORIGIN"
```

#### `tests/test_basis_policy_form.py::test_other_routes_do_not_attempt_the_borrowing` — 改訂後
```python
@pytest.mark.parametrize("mode, docs", [("legacy", []), ("round5", [])])
def test_other_routes_do_not_attempt_the_borrowing(tmp_path, monkeypatch, mode, docs):
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 人の出典の入力を memory_sovereign（ソブリンの記録由来）にした（自己申告の human_confirmed は人にしない）。期待は同じ
    ans = _doc_answer(); ans["sources"] = [{**s, "family": "memory_sovereign", "origin": "human_confirmed"} for s in ans["sources"]]
    out, _rc = bp.apply_to_ask(ans, bp.AskPolicy(), query="q", mode=mode, documents=docs)
    assert "form_text" not in out and out["basis_policy"]["form"]["state"] == "NOT_ATTEMPTED_ROUTE"
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
```

#### `tests/test_basis_policy_w5c.py::test_w5c_the_versions_and_the_table_are_as_registered` — 改訂後
```python
def test_w5c_the_versions_and_the_table_are_as_registered():
    assert bp.TABLE_VERSION == 1 and bp.SCHEMA == "verantyx.basis_policy/1"
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 規則 7・8 が変わったので CLASSIFY_VERSION は 3（prereg-w5c-r3 節）
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: CLASSIFY_VERSION は 4（A-3: human_confirmed を人と分類するのは family == memory_sovereign のときだけ。prereg の節 W5-e A-3）
    assert bp.CLASSIFY_VERSION == 4 and bp.CONFIRM_ID_VERSION == 2
    assert len(bp.TABLE) == 24 and bp.BASES == ("HUMAN", "GENERATED", "NONE")
    assert bp.DECLARED_ORIGINS == ("generated", "human_confirmed", "constructed", "testimony")
    assert bp.UNKNOWN_ORIGIN == "UNKNOWN_ORIGIN"
```

#### `tests/test_basis_policy_w5c.py::test_w5c_the_policy_note_carries_the_new_versions_and_numbers` — 改訂後
```python
def test_w5c_the_policy_note_carries_the_new_versions_and_numbers():
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src("pro", "")]), bp.AskPolicy(), query="窓は？",
                               mode="legacy", documents=[])
    note = out["basis_policy"]
    assert note["schema"] == "verantyx.basis_policy/1" and note["table_version"] == 1
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 注記の classify_version は 3
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 注記の classify_version は 4
    assert note["classify_version"] == 4 and note["confirm_id_version"] == 2
    assert note["counts"]["unknown_origin"] == 1 and note["counts"]["unknown_origin_by_family"] == {"pro": 1}
    assert out["withheld"]["unknown_origin_source_count"] == 1
```

#### `tests/test_basis_policy_w5c_r3.py::test_r3_the_versions_are_as_registered` — 改訂後
```python
def test_r3_the_versions_are_as_registered():
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: CLASSIFY_VERSION は 4（A-3）。関数名の 3 は W5-c r3 の版の名前なので変えない
    assert bp.CLASSIFY_VERSION == 4 and bp.CONFIRM_ID_VERSION == 2 and bp.TABLE_VERSION == 1
    assert bp.SCHEMA == "verantyx.basis_policy/1" and len(bp.TABLE) == 24
```

#### `tests/test_basis_policy_w5c_r3.py::test_r3_the_policy_note_carries_the_classify_version_3` — 改訂後
```python
def test_r3_the_policy_note_carries_the_classify_version_3():
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_fsrc("general", None)]), bp.AskPolicy(), query=Q,
                               mode="legacy", documents=[])
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 注記の classify_version は 4（A-3）。関数名の 3 は W5-c r3 の版の名前なので変えない
    assert out["basis_policy"]["classify_version"] == 4 and out["basis_policy"]["confirm_id_version"] == 2
    assert out["basis_policy"]["table_version"] == 1
```
<!-- w5e2-ka3:end -->
