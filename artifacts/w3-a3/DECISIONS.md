# W3-a3 判断記録（時系列。実装役 Claude Sonnet 5.5）

## D1 順序（Q1）
- 事前登録 `prereg_time.txt`: before 2026-10-03 18:49:53 +0900 / after 18:51:03 +0900。docs §12 の登録部分は `<!-- w3a3-prereg:begin -->` 〜 `end`、同じ本文が `PREREG.md`。
- 検査データの凍結 `FROZEN.json` の `frozen_at` = 2026-10-03 18:55:35 +0900（> 登録時刻）。凍結時に `git diff --stat -- verantyx tools` は空（`product_code_diff_stat_at_freeze`）。
- 製品コードの最初の変更は凍結の後（この記録の D3 以降）。測定スクリプト `measure_w3a3.py`・`dev_frame_legacy.py` は製品コードではない（`artifacts/w3-a3/`）。

## D2 `frame_decides`（2.4。測る前に決め方を書いた＝docs §12.7 の登録。結果）
- 規則（登録済み）: dev の動詞で、R5 の `decided_by` に `frame@` を含む direct の語の正答が誤決定の 3 倍以上なら True、そうでなければ False（どちらも 0 → False）。
- 結果（`dev_frame_legacy.txt`、`dev_runs/001`＝R5 を dev_verbs で測った出力）: 23 語、正答 10・誤決定 11・その他 2。10 < 33 → **`frame_decides = False`**。
- 帰結: r6 では `frame@src` は `met=False`・`why="FRAME_NOT_DECIDING"`。`DEFAULT_CONFIG` の既定は True のまま（古い配置 R5 の保存された判定を再現するため）。`PRED_FRAME_RULES` は直していない。

## D3 設計上の判断（指示書にあるもの・無いもの）
（実装の進行に合わせて追記）

### D3-1 食い違いは `MULTIPLE` でなく `estimated(generated)`（2.6）
`DISTRIBUTION_DISAGREES` の語は、生成の型 T を `estimated(generated)` で返し、分布の票（別の K62 の型）は `axes` に見せるだけにした。理由: 分布の腕は単独で決めない腕（`AGREEMENT_ONLY`）なので、直接の候補として並べて `MULTIPLE` にすると、決めない腕が答えを作ることになる（配置は情報を増やさない）。登録（docs §12.6）どおり。

### D3-2 時と場所の数え方（2.7）
- `TIME` は印が ∅（読点）か に の 2 つを **1 つの型の数にまとめた**（述語が過去の印つきのときだけ）。`PLACE` は印が で か に の 2 つを **1 つの型の数にまとめた**（述語の段 1 の型が `P_MOVE`／`P_EXIST` のときだけ）。型をまたいでは足していない（`TIME` と `PLACE` は別の行、`QUANTITY` も別）。
- `PLACE` の述語は **配置の型 id** で決めている（`SLOT_PLACE_PTYPES`）。動詞の語は書いていない。
- `QUANTITY` の数は既存の `counters`（算用数字の直後の 1 形態素）をそのまま使った。数詞で始まる連続は `pos` に語として数えないので、単位の語の「名詞の使用数」は 0 に近い。そこで行の `base` は `max(名詞の使用数, 数)` にした（割合の判定が破綻しないため。持ち上げの判定は数と基準率の比なので影響しない）。

### D3-3 充填物の型の取り方（2.3）
連続全体の語が段 1 で型を持てばそれ、無ければ最後の名詞の型、どちらも無ければ型なし（`untyped_arguments` に数えて票にしない）。この順は固定（同点の解消ではない）。段 1 = 新しい腕を足す前の判定。段 1 で `DECIDED`・`direct`・生成の腕なしの語だけが型の源。

### D3-4 指示書の細部の実装上の選択
- 「直前が名詞の する（サ変）は数えない」: 項の連なりを辿る規則では、動詞の直前は助詞か読点なので、文字どおりの条件には当たらない。**名詞の連続の直後がそのまま する のとき**（`勉強する` の形）を `sahen` として数えず、理由に数えた（`勉強をする` は を の項として数える）。
- `frame_dup_particle`（同じ助詞が 1 語の frame に 2 回）: その語は `ptype` を残し、frame を空にする（どの助詞の組を採るかを順で選ばない）。結果、その語は `estimated(generated)` までで格上げされない。
- `frame_unconfirmed` は `CONFIRMED` の答えにだけ付ける。ほかの答えには付けない（`frame_status` と `frame` はすべての答えにある）。
- 抽出段の理由に、指示書の 3 つ（`chain_broken`・`too_many_args`・`no_verb`）のほか `sahen`・`voice`・`numeral_start`・`no_filler` を足して数えた（数えなかった理由を隠さないため）。`no_filler` は連続の語も最後の名詞の原形も取れない（長すぎる・表記の規則に当たる・接尾辞で終わる）場合。
- `needs --kind pred` は抽出段の cache（約 700MB の pickle）を読む。cache が無ければ型つきで止まる（終了コード 2）。
- `needs` の meta に `kind` の欄を足した（名詞の形のプロンプト・schema・argv は 1 バイトも変えていない。名詞のプロンプトの sha256 は `ded30f48…` のまま）。
- 既存の source rules の検査（検査語を製品コードに引用しない）を新しい動詞データにも掛けた。動詞データの 2 語（`あり`・`在る`）が、既存の `hypernym_phrases` が文末の コピュラ ある の綴りとして引用している語と同じ綴りだった。その 2 語はその関数の中だけに限って許した（`tests/coarse_place/test_coarse_place_w3a3_source_rules.py` の `COPULA_SPELLINGS`。型の決定には使っていない文法の引用）。
- `GEN_ARM` の残り（P7）: `decide_word` の中の W3-a2 の規則（`_apply_gen_definition`）と、builder の名詞の生成の行（`ev.append((w, ct.GEN_ARM, …))`）と stat だけが `GEN_ARM` を直接見る。`placed_single`・`_estimate` の head の段・`_stage2` の型の源は `GEN_ARMS` を見る。単位の族と donor は `placed_single`／`plain` を通るので、`gen_frame` で決めた述語は入らない（`test_a_predicate_placed_by_a_generated_frame_is_not_lent_to_a_longer_word`）。

### D3-5 生成（Q2）
- 一覧: `needs --kind pred --n 5000`。境界の同点を全部入れて 5,022 語（`needs_pred.meta.json`）。その動詞の絞りは、抽出段の cache の品詞の数で V の使用が A+S の使用より多い語（出所の和。型の票ではない）。
- 試し呼び出し 1 回（`gen_pred_trial_1.log`）: `--slots 1 --limit-batches 1`、`--extra-config 'mcp_servers.vera.enabled=false'` と `'mcp_servers.node_repl.enabled=false'` つき。台帳の `end` は `ok`、40 語が読めた。**`--extra-config` を外す再試行は要らなかった**（設定は誤っていなかった）。試し 2 回のうち使ったのは 1 回。この 1 回は本番と同じ台帳（`$R6/gen_pred/ledger.jsonl`）に入っており、呼び出し数に入る。試しのあとでプロンプトは変えていない（同じ束 `b00000` を本番がそのまま採用する）。
- 本番: `--slots 12 --max-calls 1500 --deadline-sec 6600`（`gen_pred_run_1.log`。開始 `gen_pred_run_1.started`）。台帳の呼び出しは試し 1 回 ＋ 本番 125 回 ＝ **126 回**（上限 1,500 の内）、126 束すべて 1 回目で `ok`（失敗・再試行 0、`ok_rate` 1.0）。台帳の最初の start から最後の end まで 431.7 秒（試し呼び出しと本番の間の空きを含む。本番の `run` の壁時計は 365.7 秒）。1 語あたりの呼び出し 126/5,022 = 0.02509。棄権（`ptype` null）234 語、同じ助詞が 2 回の frame 5 語、重複・束の外・範囲外 0。
- `frames.jsonl` sha256 = `9a7e8decfc85d2dde8a0209cf983491cc6d4d0257697ab19ff18828b9ae89717`、`ledger.jsonl` sha256 = `d21fe1e3064f6363440d75f3807c1ed3954fa5a03e70326a753586f46d13a0c4`（`gen_pred_sha256.txt`）。以後この 2 つを変えない。述語のプロンプトの sha256 = `1509fd30…`、schema の sha256 = `68551a6a…`（`gen_pred_summary.json`）。

### D4 dev の格子と設定の凍結（凍結データは見ていない）
- dev の配置 `r6/dev/d1`（`--stage-cache` の抽出 cache ＋ `--generated-frames`。`build_dev_d1.log`）の保存された evidence から、`dev_grid.py` が §12.8 の格子（述語 72 行・slot 9 行）を全部評価した（`dev_grid.txt`）。読んだ検査データは dev の動詞（`dev_verbs.jsonl`）と dev の語彙（`dev_vocab.jsonl`）だけ。
- 述語: **誤決定 0 の設定は無かった**（新しい腕を全部外しても、dev の動詞に `alias`・`definition`・`paren_alias`（Wikipedia の見出し・別名が同じ綴りの名詞のもの）で direct に決まる語が 3 語あり、その 3 語は誤決定。これは基線の挙動で、新しい腕のせいではない）。そこで登録した規則の後段（誤決定が最少の設定のうち direct の正答が最多）に従った。誤決定は全 72 行で 3、direct の正答が最多（3）の行は 2 行（格子の 51 と 63）、direct の答えの数も同じ（6）なので、格子の並びで先の **51 行目**: `rd_min_total=20, rd_particle_min=10, rd_particle_share_pct=30, rd_type_share_pct=50, rd_min_sources=1`。
- slot: slot の行を外した判定（段 1）の dev 語彙（L2、種を除く 580 語）での direct の誤決定は 25。9 行すべて誤決定 25（増えない）、direct の正答は同数（248）、direct の答えも同数（303）。並びで先の **0 行目**: `slot_min=20, slot_share_pct=30`。
- `config_w3a3.json` に全設定を書いた（`frame_decides=false`・上の値・`rd_store_min=20`・`slot_lift_pct=300`）。凍結の時刻は `config_frozen_time.txt`、sha256 は `config_w3a3.sha256`。**ここから先、設定を変えていない**。
- 注意（隠さない）: 述語の選択は dev の 3 語の差で決まっている（格子の 72 行のうち 26 行が direct の正答 1 以上、3 に届くのは 2 行）。最も緩い側の値が選ばれたので、dev に無い動詞での誤格上げの割合は、凍結データの測定で初めて分かる。
- 補正（設定は変えていない）: d2 を dev で測ったところ、L2 の dev の数が `dev_grid.txt`（最初の版）と 1 つずれた。原因は格子の採点が、問い合わせの入口が最初に読む **綴りの規則（表記）** と **NFKC の引き直し** を通していなかったこと（表記で direct になる語が 51 語ある）。`dev_grid.py` の採点を入口と同じ経路に直して同じ d1 で格子を取り直したところ、**選択は変わらなかった**（`SELECTED_JSON` が同じ。選択に効く差は無い。表記の語は設定に依らず同じ数）。取り直した `dev_grid.txt` の選んだ行は d2 の入口での数と一致する: 述語の dev の動詞 direct 正答 3・誤決定 3・direct の答え 6（`dev_runs/002`）、slot の dev 語彙 direct 正答 299・誤決定 24（`dev_runs/003`）。参考に R5 を dev で測った数（`dev_runs/006〜008`）と並べて、L1 の dev のトークンの被覆は 0.7896 → 0.8069、L2 の dev の誤決定は同じ（24）。

### D4-2 時の語の slot（2.7 の確かめ。満たせなかった目標の小項目）
- d2 の dev 語彙で、slot の行で direct になった語は 1 語だけ（数量の語、正答。`dev_time_place.txt`）。dev の TIME の語（51 語。種を除く）で slot により direct になった語は **0**。理由（`evidence` を見た）: dev の TIME の語は、表記の規則（日付・時刻）で決まる語のほか、未来や習慣と使われる語（述語が過去でない）が多く、「述語が過去の印つき」の数が閾値に届かない。
- チケットの「`昨日` のような語が direct になる」は、**登録した設定では満たせなかった**。`昨日`（dev の語彙には無い。入口に直接問い合わせた）は `estimated(generated)` の TIME のまま。診断（設定を変えたのではない。保存された evidence を別の `slot_share_pct` で決め直しただけ）: `昨日` の slot の行は 出所 `codex:paraphrase_entail` で 364 / 4110 = 8.9%（ほかは 1.3%・1.9%）。`slot_share_pct` が 8 以下なら direct（`gen_definition` ＋ `slot@codex:paraphrase_entail`）、10 以上なら推定のまま。登録した格子（30 / 20 / 10）はこの値に届かず、dev の語彙には 昨日 のような過去の時の語が無いので、dev の数では格子の下側を選べない（9 行すべて同数）。**dev の標本を足して設定を選び直すことはしなかった**（1 語に合わせた調整になるため）。報告の「既知の穴」に書く。

### D5 実行後に見つけた・直したこと（隠さない）
- **監査スクリプトの誤り**: `audit_w3a3.py` の最初の版は、格上げの腕の並びを比べるときに `gen_frame` を末尾に置いて比べていたため、48 語の格上げすべてを「規則違反」と数えた（保存された `by` は `sorted(...)` で `gen_frame` が先）。比べ方を `sorted` 同士に直して再実行し、違反 0 になった。決定のコードではなく監査側の誤りで、直した後の出力が `audit_w3a3.txt`。
- **抽出段の cache の理由の数だけが古い**: `r6/stage/extract.pkl`（base・d1・d2 が使った）は、サ変（名詞の連続の直後がそのまま する）を `chain_broken` に数えた版で作った。そのあとサ変を別の理由 `sahen` として数える変更をした。数えた項の連なり（`counted`）は全出所で同じ（確かめた: base と run1 の `counted` が出所ごとに一致）。cache なしで作った run1・run2 の manifest の理由別の数は新しい数え方。`content_sha256` は d2（cache あり）と run1（cache なし）で同じ（`5c969d45…`）。
- `verantyx/coarse_place.py` の `query` は、W5-b4 が触る問い合わせの正規化・表記の段の行を **1 行も変えない**ために、`query` の本体を `_query_inner`（`def` の 1 行の改名だけ）に移し、新しい `query` を薄い包みにした（包みは答えの最後に `frame_status`・`frame` を足すだけ）。`git diff -U0` の `query` の塊は、包みの挿入と `def` の改名だけ。
- 全体テストの基線外の失敗は 2 件で、どちらも環境由来（`new_failures_explained.txt`。基点の untouched な書き出しでも同じ 2 件が失敗する）。

### D6 Q6 と門 4 の申し送り（0.4。監査役へ）
1. **Q6 は配置の側の変更では動かない**: `PLACEMENT_PREDICATE_UNIDENTIFIED` を出すのは `origin/integ-w3b1:verantyx/semantic_read.py` の **760 行目だけ**で、英語の入力で、どの語も既知の動詞の閉じた一覧に無いときに、配置を一度も問い合わせずに足される（`_read_en`、758〜760 行）。日本語の経路にこの理由は無い。英語の述語を配置に置かず、読解器にも触れなかった。件数 31 は、この変更では原理的に減らない。
2. **門 4 を `gen_frame` は通る**: 門 4 は `'gen_definition' in decided_by`（`semantic_reader.py` 1794 行）の文字列だけを見る。述語の生成の腕を `gen_frame` にしたので、格上げした述語（r6/run1 で 48 語）は門 4 を通る。読解器が direct として使うかは W3-b2 で決める。答えに `generated_frame: true` を付けて機械的に区別できる。
3. 上の 48 語のうち 30 語は、票を出した分布の腕がすべて codex コーパスの出所（jawiki 無し）。

### D7 手順からの逸脱
- 指示書 手順 0-4 の基線のテスト、手順 1〜11 の順序は守った。
- 逸脱: (a) 述語の選択の格子で誤決定 0 の設定が無かった（dev の動詞に基線から direct で誤る語が 3 語ある）ので、登録した規則の後段（誤決定が最少のうち正答が最多）を使った（D4）。(b) 時の語の slot で「`昨日` のような語が direct」は満たせなかった（D4-2）。(c) 指示書 2.7 の `QUANTITY` の行の `base` は `max(名詞の使用数, 数)`（D3-2）。(d) `needs --kind pred` が抽出段の cache を読む（指示書のコマンドどおり。cache の読み込みに約 20 秒）。
- 凍結データの測定のあとに規則・設定を変えていない。`dev_grid.py` の採点の直し（D4 の補正）は、設定の凍結（19:27:52）のあと、d2 を dev で測って 1 つずれに気づいたときに行った。選択は変わらず、`config_w3a3.json` は書き換えていない（sha256 を全量 r6 の作成の前に `shasum -c` で確かめた。`config_w3a3.sha256`）。
