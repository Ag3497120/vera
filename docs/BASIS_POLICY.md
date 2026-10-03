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

## 5. D: 問い返しと保存の形

- `CONFIRM_REQUEST` は `confirm` を持つ: `id`・`question`・`claim`・`generated_sentences`・`draft_record`・`destination`・`how_to_answer`。
- `confirm.id` は prereg 節 5 の式（時刻・乱数・dict の挿入順に依らない）。保留中の問いはどこにも保存しない。`--confirm <id> yes|no` は同じ問いを同じ入口でもう一度計算し、出る id と一致したときだけ追記する。一致しなければ `UNKNOWN_CONFIRM_ID`（何も書かず、終了コード 1）。
- ソブリンの場所は環境変数 `VERA_SOVEREIGN_ROOT` と `VERA_SOVEREIGN_STORE`（`VERA_P4_INDEX` と同じ流儀）。両方無し `UNKNOWN_NO_SOVEREIGN`、片方 `UNKNOWN_SOVEREIGN_CONFIG_INCOMPLETE`、読めない型はそのまま（`DETACHED`・`UNKNOWN_STORE` など）、同意なし `ACTIVE_NO_CONSENT`。
- 新しい口 `sovereign.append_basis_confirmation(root, store_id, payload)`: 現在の `consent.promote` が真のときだけ `decision` の事件を 1 件追記する（`APPENDED`）。同意が無ければ何も書かない（`NO_CONSENT`）。payload の形が違えば `BAD_PAYLOAD`。
- 記録の payload（全鍵）: `record: "basis_confirmation"`、`status`（`HUMAN_CONFIRMED` か `REJECTED_GENERATED`）、`origin`（はい のときだけ `"human_confirmed"`）、`witness: "user_confirmation"`、`confirm_id`、`query`、`claim`、`generated_sources: [{family, source_id, sha}]`、`table_version`。`phrase`・`cell`・`occupied`・`corrects` は入れない（昇格の候補・訂正にしない）。
- いいえ は削除でなく追記（`REJECTED_GENERATED`）。同じ `confirm_id` の記録が複数あれば seq の最後の 1 件が効く（訂正は前進の追記）。同じ問い（`query` の完全一致。正規化しない）に効いている `HUMAN_CONFIRMED` の `claim` が 2 種類以上なら `AMBIGUOUS_CONFIRMED_RECORDS` で棄権。記録を答えに使うのは、ソブリンが ACTIVE で現在の `consent.promote` が真のときだけ（撤回後は使わない）。
- はい の後の同じ問いは `kind: answer`、`verdict: ANSWER`、`sources[0].origin == "human_confirmed"`（`family: memory_sovereign`）で返り、`basis_origin` は付かない。

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

