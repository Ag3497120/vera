# 実現器の規則と形の表（W3-d1）

## 1. 状態

- 2026-10-02 版（`docs/REALIZE_2026-10-02.md`）の実現器（`verantyx/semantic_realize.py`）を引き継ぐ。その文書は書き換えない。
- このチケット（W3-d1、基点 dev `6bc410d`）が足すもの: 形の表 `verantyx/data/realize_forms_ja.json`、層の形の表（`--forms`・`VERA_REALIZE_FORMS`）、型つきの十字の受け取り、同じ配置での再読、`vera realize`、`tools/fusion/evaluate_model.py`。
- 設計の前提: `ops/decisions/2026-10-04_VERA_BASE_V1.md` §1.5・§2 A8・§5。J10（W10-f04 の `fill_candidates` の門 (b) が実現器に拒まれる穴）を閉じる。
- このファイルの §2・§3 は **コードに触る前** に書いた事前登録。時刻と sha は `artifacts/w3-d1/prereg_time.txt`・`prereg.sha256`。§4（結果）は測定の後に追記する。

## 2. 規則（事前登録）

### K310 規則と形の境界
コードが決めるのは (a) 十字に必要な役割が揃っているか、(b) 役割を助詞つきで並べる順、(c) 述語を活用させる位置、(d) 読み戻しの検査。表が決めるのは (a') 役割→助詞の対応、(b') 役割の既定の順、(c') 文体ごとの語尾と活用の形、(d') 主題の助詞の候補。

表の鍵と K310 の対応（鍵の名前は実装で確定し §4 に実際の一覧を書く）:

| 表の鍵 | 区分 |
|---|---|
| `role_particle` | (a') 役割→助詞。frame で agent 以外の役割が実現できるかは「表に在るか」で決まる |
| `role_order` | (b') 役割の既定の順。表に無い役割は後ろに名前順（現行どおり） |
| `topic_particles` | (d') 主題の助詞の候補。順序に意味があり、1 番目が既定 |
| `styles.<名前>` | (c') 動詞の語尾（肯定・否定 × 非過去・過去、どの語幹に付くか）、繋辞の語尾、measure の語尾、句点 |
| `conjugation` | (c') 活用の形（五段の行の表、する・来る の語幹、行く の特例） |
| `copula` | (c') 主題の助詞と、属性・物質をつなぐ の |

コードに残す形（規則として凍結し、表に出さない）: 読み戻しの検査（`check_round_trip`・`check_term_lineage`・`check_observed_lineage` と、閉じた集合 `_PARTICLES`・`_AUX_LEMMAS`・`_NEG_AUX_SURFACES`・`_PUNCT`・`_CONTENT_POS`）、`summarize_entity` の `また、`、`realize_refusal` の `：「」`。

### K311 層の表
層の表は語尾・文体・語順の **追加** だけ。役割→助詞の対応と、読み戻しの規則は上書きできない。上書きを含む表は `FORMS_OVERRIDE_REFUSED` で層全体を読み込まない。
- できること: `styles` に新しい文体名を足す（足す文体は全部の鍵を持つこと。欠けは `FORMS_INVALID`）、`role_particle` に新しい役割を足す、`role_order`・`topic_particles` の末尾に新しい要素を足す。
- 既存の鍵に違う値（`role_particle` の既存の役割の助詞、既存の文体の値、`topic_particles` の順や既存要素、`version`）→ `FORMS_OVERRIDE_REFUSED`。同じ値の重複は無害として許す。
- 読み戻しの規則に当たる鍵や知らない鍵を持つ層 → `FORMS_INVALID`。無いパス → `FORMS_NOT_FOUND`。
- 読み込みの順: 基底の表（パッケージ内）→ 環境変数 `VERA_REALIZE_FORMS`（`os.pathsep` 区切り、複数可、空は無し）→ 明示の `forms=`／`--forms`。環境変数は **呼び出しのたびに** 読む。
- 例外 `FormsError(reason, detail)`。ライブラリ関数は例外を上げる。`cross_tokens.realize_tokens` と CLI は型つきの `{"status":"REFUSED","reason":<型>}` にし、CLI の終了コードは 2。
- 層で足した助詞が `_PARTICLES` に無ければ、その文は語の系譜の検査で落ちる（読み戻しの規則は凍結）。

### K312 再読一致
実現した文を **同じ配置** で読み、役割の集合・各充填物の表記（NFKC）・極性・時制・述語の辞書形が一致するときだけ `REALIZED`。段 R や型の再読が元の十字と違う経路で同じ十字に至ってもよい（経路は比べない: `role_basis`・`predicate_basis`・型は比べない）。1 つでも違えば `REFUSED:REREAD_MISMATCH:<差分>`。拒否の型は既存の `ROUNDTRIP_MISMATCH`（`detail` を `REREAD_MISMATCH:<差分>` で始める）で、`REFUSAL_REASONS` に新しい理由は足さない（`observe` の数え上げに「起きない理由の 0」を増やさないため）。

### K313 不変
既定の表で、既存の実現のテストと `realize_variants`・`observed_variants` の出力は byte 不変。配置なしの呼び出し（`placement=None`）は従来どおり（`_observed_roundtrip` の呼び方も含めて）。

### K314 型つきの十字
**規則の扱い（レビュー 第 1 ラウンド M1 の修正）**: 型つきの十字は読解器の規則が `frame` のものだけを実現する。EventCross は `provenance["rule"]`、clause dict は鍵 `rule`（呼び出し側が `semantic_read.read` の `clause_meta[i]["rule"]` を入れる）で規則を渡す。規則が `frame` でなければ `UNSUPPORTED_RULE`、規則が無ければ（既定値を置かず）`UNSUPPORTED_RULE`（`a typed cross carries no reader rule`）で棄権する。`verify_sentence` も同じで、`REFUSED:REREAD_MISMATCH:RULE_NOT_FRAME`（frame でない）／`RULE_UNKNOWN`（規則なし）。dict の経路は呼び出し側が渡した `rule` を信じる。

配置の情報（`role_basis`・`predicate_basis`・型）は実現では使わず（文の形は変えない）、再読の検査にだけ使う。配置で読まれた十字（`role_basis`・`predicate_basis` が配置の由来）が `placement` なしで渡されたら `REREAD_MISMATCH:NEEDS_PLACEMENT` で棄権する。

### K315 主題の候補（事前登録の追加）
`placement` が渡されたときだけ、主題の助詞を表の `topic_particles` の順に試し、**出す文そのもの** が K312 と語の系譜の両方を通った最初の候補を出す。通らなかった候補は `checks["topic_attempts"]` に（候補・理由）で全部記録する。どれも通らなければ最後の理由で棄権する。どの候補も同じ十字に戻ることを検査で確かめたものだけが出るので、順は内容の勝者を作らない（形の選好は表＝データ）。別の文（は→が に書き換えた文）を検査して元の文を出すことはしない。`placement=None` のときは従来どおり 1 番目（は）だけを出す（K313）。`realize_variants`・`observed_variants` は全候補を並べ、選ばない。

## 3. 測定の設計（事前登録）

- **T1（K313 byte 一致）**: 凍結入力 = (a) `results/realize/realize_measure_2026-10-02.jsonl` の `source_text`（重複なし）、(b) `tests/event_cross/data/sentences_ja*.jsonl` と `tests/observe/data/seeds_ja.jsonl` の `text`。各文を `semantic_reader.document_view` で読み、各節に `realize_clause`（plain・polite）と `realize_variants`、(b) には配置なしの十字に `realize_observed`・`observed_variants`、さらに `realize.conjugate` の 8 組合せを、旧い API の呼び方だけで正準 JSON にする。実装前に `t1_before.jsonl` を作り sha を凍結、実装後に同じスクリプトで `t1_after.jsonl` を作り `cmp` する。加えて `tests/observe/realize_parity.py --base 6bc410d` の mismatch 数。表引きの活用と `realize.conjugate` の違いの数も数える。
- **T2（型つきの十字 100 件）**: 母集団 = `artifacts/w10-f04/entry_r8.after.jsonl` の `text`（重複なし）のうち、配置 r9 で `semantic_read.read` が読め、`build_crosses` が CROSSED かつ十字が 1 つのもの。`sha256(text.encode())` の昇順で先頭 100。除外は理由別に数える（言語違い・ReadError・CROSSED でない・十字が複数）。各行を `realize_clause(d, "plain", placement=r9)` と `cross_tokens.realize_tokens(tokens, "ja", placement=r9)` に掛ける。REALIZED になった文は測定スクリプト自身が同じ配置で読み直し、K312 の 5 項目を独立に比べる。数えるもの: REALIZED 数、棄権数と理由の分布、独立再読での不一致の REALIZED 数（0 でなければ不合格）、主題 は／が の内訳、polite での同じ数（参考）。
- **T3（層の表）**: 丁寧体の語尾を 1 つ足す層（新しい文体名）で `realize_variants` の出力が増える／変わること、`role_particle` の既存の値の上書き・既存の文体の値の上書きが `FORMS_OVERRIDE_REFUSED` で拒まれること（環境変数と `--forms` の両方）。層の表は実装前に作って sha を凍結する。
- **T4（門 (b)）**: W10-f04 の台本と同じ型（r8、`F._gate_b(..., require_realize=True)`）で、通る行 5 以上・落ちる行 5 以上。期待は実装前に書いて凍結する。`require_realize=False` では通る行 `(None,'REALIZED')`・落ちる行 `(None,'REFUSED')`。`ask_and_gate` の既定 `require_realize=False` が変わらないこと。
- **T5（中間職）**: 実装役は何もしない。
- **T7**: 全体テストの失敗が基線 `dev_6bc410d_failures.txt` から増えない。J10 の閉鎖で `tests/test_w10f04_fill.py::test_realize_is_recorded_and_can_be_required` の期待が変わる 1 件は、`artifacts/w3-d1/j10_expectation_change.md` に旧期待・新期待・実測を残し、監査役の判断待ちとして別に数える。

## 4. 結果

すべて 2026-10-05 の測定。出力ファイルは `artifacts/w3-d1/`。事前登録（§1〜§3）の時刻と sha は `prereg_time.txt`・`prereg.sha256`、検査データ（T1 の凍結・T2 の母集団・T3 の層の表・T4 の台本）の凍結は `data_freeze_time.txt`・`data_freeze.sha256`（製品の差分より前）。

### 4.1 表の鍵と K310 の対応（実装で確定した鍵）

| 鍵 | 区分 | 中身（既定の表 `verantyx/data/realize_forms_ja.json`、版 `REALIZE_FORMS_VERSION` = 1） |
|---|---|---|
| `role_particle` | (a') | recipient に・goal へ・patient を・origin から・location で。frame で agent 以外の役割が実現できるかは「この鍵に在るか」 |
| `role_order` | (b') | recipient, goal, patient, origin, location（表に無い役割は後ろに名前順） |
| `topic_particles` | (d') | は, が（順序に意味がある。1 番目が既定） |
| `styles.<名前>.verb` | (c') | 肯定／否定 × 非過去／過去の 4 つの `[語幹, 語尾]`。語幹は `dict`（辞書形）・`i`（連用）・`a`（未然）・`ta`（た形） |
| `styles.<名前>.copula` | (c') | 繋辞の語尾: `affirmative`・`affirmative_adjective`・`affirmative_aru`・`negative` |
| `styles.<名前>.measure`・`.period` | (c') | measure の語尾、句点 |
| `conjugation` | (c') | 五段の行の表（`a`・`i`・`ta`）、`行く` の特例（`ta_special`）、一段・する・来る の語幹の作り方 |
| `copula` | (c') | 主題の助詞 `topic`、属性・物質をつなぐ `attribute_link`・`substance_link` |

コードに残した形（表に出していない。規則として凍結）: 活用の位置と語の種類の判定（`realize._class`）、必要な役割の判定、並べる順の規則、読み戻しの検査（`check_round_trip`・`check_term_lineage`・`check_observed_lineage` と `_PARTICLES`・`_AUX_LEMMAS`・`_NEG_AUX_SURFACES`・`_PUNCT`・`_CONTENT_POS`）、`summarize_entity` の `また、`、`realize_refusal`・`refusal_sentence` の `：「」`。層で足した助詞が `_PARTICLES` に無ければ、その文は語の系譜の検査で落ちる。

### 4.2 T1 K313 byte 一致

- 凍結 `t1_before.jsonl`（sha256 `t1_before.sha256`）と実装後 `t1_after.jsonl` は `cmp` が無出力で一致（`t1_compare.txt`）。入力は 4493 文（measure 由来と W3-b/W3-c の日本語データ）、`clause`＋`cross` の行 5089、活用の行 4488。
- 表引きの活用 `conjugate_by_style` と `realize.conjugate` は 561 語 × 8 組合せ = 4488 通りで違い 0（`t1_conjugate_parity.txt`）。
- `tests/observe/realize_parity.py --base 6bc410d`: `checked 134, mismatch 0`（`t1_parity_w3c.txt`）。
- `VERA_PLACEMENT`（r8）を立てた状態でも、base 6bc410d の複製と本ツリーの出力が一致（`t1_env_parity.txt`）。

### 4.3 T2 型つきの十字 100 件（配置 r9 で実現し、同じ配置で再読）

母集団（`t2_pool_meta.json`）: `entry_r8.after.jsonl` の重複なしの文 4149、除外 = 言語違い（`LANG_MISMATCH`）245・CROSSED でない 3585、残り 319（十字が複数のものは 0）。sha256 昇順の先頭 100（`t2_pool.jsonl`）。結果は `t2_result.jsonl`・`t2_summary.json`（測定スクリプトが自分で再読して K312 の 5 項目を比較）。

| 経路 | REALIZED | 棄権 | 独立再読で不一致の REALIZED | 主題 は／が |
|---|---|---|---|---|
| `realize_clause(dict + rule, "plain", placement=r9)` | 46 | 54 | **0** | 33／13 |
| `cross_tokens.realize_tokens(..., placement=r9)` | 46 | 54 | **0** | （上と同じ文 46 件） |
| 参考: polite | 36 | 64 | 0 | 33／3 |

`plain` の棄権 54 の理由（`t2_summary.json`）: 役割 time が実現できない 23、役割 result が実現できない 10、agent の腕が無い 4、規則が frame でない 11（`UNSUPPORTED_RULE`。二重否定など。M1 の修正前の分類は 量化・範囲・比較 7・agent の腕なし 6 で、うち 9 件は規則の検査が先に棄権させる分類に移り、残る 2 件は二重否定が肯定文で出ていたもの）、能動でない 4、再読不一致（`REREAD_MISMATCH:roles`）2。再読不一致の 2 件はどちらも `もらった` の文で、実現した文を同じ配置で読むと agent と recipient が入れ替わる十字だった（`妹が兄から本をもらった。`・`生徒は先生に花をもらった。`）。再読の検査が誤りを出さなかった例にあたる。`realize_tokens` の棄権も同じ 54 で、plain と tokens は 46 件が同じ文、`plain だけ REALIZED` は 0（`plain_vs_tokens_text`: 同じ文 46・どちらかが棄権 54）。T2 の測定スクリプトは各行の原文を r9 で読み直し `clause_meta[0].rule` を dict に入れて渡す（母集団 `t2_pool.jsonl` は凍結のまま作り直していない）。修正前の測定は plain 48 REALIZED だった（二重否定 2 件が `先生は作文を直す。`・`母は犬を飼う。` と出ていた）。polite の棄権のうち 10 は `REREAD_MISMATCH:NOT_CROSSED`（r9 は丁寧体をしばしば読めない。これは棄権として正しい）。

### 4.4 T3 層の表

`tests/test_w3d1_forms.py`（57 件、`t3_pytest.txt`）が通る。丁寧体の語尾を足す層（`t3_layer_add_style.json`）で、`マキがリオに青鍵を渡さない。` の変種が 8 文から 12 文に増える（`polite_casual`: `…渡さないです。` の 4 文。`t3_result.txt`）。上書きを含む 2 つの層は `FORMS_OVERRIDE_REFUSED`（環境変数でも `--forms` でも、CLI の終了コード 2）。

### 4.5 T4 門 (b)

`tests/test_w3d1_gate_b.py`（15 件、`t4_pytest.txt`）が通る。通る行 7（`(None,'REALIZED')`）・落ちる行 6（`require_realize=True` で `('GATE_B_REALIZE_REFUSED','REFUSED')`、役割 time を持つ 5 行と `母がホテルで勝利を願った。`）。`require_realize=False` では通る行は `(None,'REALIZED')`、落ちる行は `(None,'REFUSED')`。`ask_and_gate`・`_gate_b`・`FillConfig` の既定 `require_realize` は False のまま。J10 の閉鎖で `tests/test_w10f04_fill.py::test_realize_is_recorded_and_can_be_required` の期待が変わる（`j10_expectation_change.md`）。

### 4.6 (e) `vera realize`

`e_cli.txt`（`--help` と、T2 の 1 行目の token 列を `--placement r9` で）。`tests/test_w3d1_cli.py`（8 件）・`tests/test_w3d1_evaluate.py`（6 件）。

### 4.7 T7

`pytest tests`: 117 失敗、基線 116 に対し増えた 2 件（`new_failures.txt`、理由は `new_failures_explained.txt`）: J10 の期待の変化 1 件（監査役の判断待ち）と、未コミットの間だけ落ちる `test_s6_…` 1 件。基線にあって落ちなくなったのは `test_one_trace` の 1 件（環境由来）。
