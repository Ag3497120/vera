登録日時: 2026-10-03 18:49:53 +0900 から 2026-10-03 18:51:03 +0900 の間（`date '+%F %T %z'` の出力。`artifacts/w3-a3/prereg_time.txt` の `before` と `after`。この節はその間に書いた）
この時点で `tests/coarse_place/data/dev_verbs.jsonl`・`verb_check_300.jsonl`・`artifacts/w3-a3/FROZEN.json`・`tests/coarse_place/test_coarse_place_w3a3_*.py`・`tests/test_gen_coarse_evidence_pred.py` は存在しない。製品コード（`verantyx/coarse_*.py`・`tools/*.py`）の差分は 0。
出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-a3/plan.md`（チケット W3-a3）。この節に **語の一覧は無い**（型の id・助詞・設定の名前と格子だけ）。

### 12.1 目的と、規則の形（変えるなら下の「変更記録」に日時つきで書く）
述語（動詞）の「型 ＋ 格の枠（助詞 → 期待する充填物の型）」と、時・場所・数量の語の直接の型を、**生成（モデルが書いたもの）と分布（材料の数え）の一致** で `direct` にする。生成だけで決まったものは `estimated(generated)` に留める。配置は情報を増やさない: 分布の腕と `slot` の腕は **単独では決めない**（`AGREEMENT_ONLY`）。読解器には触れない（契約と欄だけ。読解器は W3-b2）。

### 12.2 K62 の写し（`coarse_types.K62_FRAMES`）
出典は W3-b1 の `docs/READING_SOUNDNESS.md` §10 の K62 の表（`origin/integ-w3b1`、コミット `5d863dd`、blob `0d6233b20c6a1cd717f9a16bb6d96476422864ab`。§10A の K62 ではない）。表は 2 型 9 行。写しは型 id・助詞・名詞の型 id だけで、`artifacts/w3-a3/k62_source.md` に表をそのまま貼って機械で照合する。**表を広げない**。残り 11 型は枠が無い（「読まない型」）。
**区別の行**: 型 T の行の (助詞, 名詞の型) の組のうち、もう一方の型のどの行にも無い組。表から機械的に導く関数で求め、手で選ばない。

### 12.3 抽出段の新しい数え（`analyze`。読解器は使わない）
「項の連なり」の規則（隣接だけ。長距離は数えない）:
- 印 m は、名詞の連続（今の `analyze` の run と同じ切り方）の直後の格助詞 9 種（が を に で へ と から まで より）か、読点「、」（∅）。は・も・の は印にしない。
- 印の直後から右へ、次のどれかが来るまで見る。(1) 名詞の連続＋格助詞 9 種の組（ほかの項）。最大 3 組。4 組目が来たら数えない（`too_many_args`）。(2) 動詞（`pos1 == 動詞`）が来たらそれがこの項の述語。(3) 文末・句点に至っても動詞が無い（`no_verb`）、それ以外（読点・副詞・形容詞・連体詞・接続助詞・係助詞・の・名詞の連続のあとに助詞が無い・代名詞 等）が来たら数えない（`chain_broken`）。
- 述語は `orthBase`（無ければ表層）。直前が名詞の「する」は数えない（`sahen`）。動詞の直後に連続する助動詞の原形に れる・られる・せる・させる があれば数えない（`voice`。態を変えると助詞と役割の対応が変わるため。閉じた文法の類で、語の一覧ではない）。連続する助動詞の原形に た があれば「過去」の印を付ける。
- 充填物は `(連続全体の語, 最後の名詞の原形)`。数詞で始まる連続は数えない（`numeral_start`。数量は表記の規則と既存の counters で扱う）。
- 出所ごとに `acc["chain"]: Counter[(filler_run, filler_head, m, verb, past)]` に数える。出所をまたいで足さない。抽出段の cache に新しいキー `chain` が無いときは、型つきで止まる（`STAGE_CACHE_STALE`、終了コード 4）。理由別の数（`chain_broken`・`too_many_args`・`no_verb`・`sahen`・`voice`・`numeral_start`・数えた数）は manifest に出す。

### 12.4 述語の分布の腕 `role_distribution`（出所ごと。`ARMS_BY_SOURCE`）
決定は 2 段（循環を避ける）。**段 1** = 今の判定（新しい腕なし）を全語に行う。段 1 で `DECIDED`・`origin=direct`・名詞の型 1 つ・`decided_by` に生成の腕（`gen_definition`・`gen_frame`）を含まない語だけを「型の分かった充填物」とする。**段 2** で、新しい腕の行を足して、新しい行を持つ語だけを決め直す。新しい腕は単独では決めないので、段 2 で段 1 の型の源は変わらない。
- 充填物の型: 連続全体の語が段 1 で型を持てばそれ、無ければ最後の名詞の型、どちらも無ければ型なし（数えるが票にしない。`untyped` として manifest に）。この順は固定の規則（同点の解消ではない）。
- evidence の行: `(述語, "role_distribution", 出所, "<助詞>|<名詞の型>", n, base=その述語のその出所での型つきの項の総数)`。述語ごと出所ごとに `rd_store_min` 以上の型つきの項があるときだけ保存。∅（読点）は述語の腕に入れない（格助詞 9 種だけ）。
- `arm_verdict("role_distribution")`（判定は `coarse_types` の 1 か所。builder と問い合わせが同じ関数を使う）。K62 の逆引き:
  1. `base < rd_min_total` → 票なし。
  2. 有意な助詞 Sig: 助詞 p の型つきの数 n_p が `rd_particle_min` 以上、かつ n_p ≥ `rd_particle_share_pct`% × base。
  3. 各 p ∈ Sig の有意な型 Types(p): n_{p,t} ≥ `rd_type_share_pct`% × n_p。
  4. K62 の型 T が候補になるのは、(a) Sig のうち K62 の 6 助詞（が を に で へ から）に入るものが、すべて T の行の助詞に含まれ、(b) その各 p で Types(p) ⊆ T の行の型、(c) T の区別の行の少なくとも 1 つが有意（p ∈ Sig かつ t ∈ Types(p)）。と・まで・より は表に無い助詞なので候補の判定には使わない（数は見せる）。
  5. 候補がちょうど 1 つ → その型。0 または 2 → 票なし（割れは票にしない。同点は棄権）。
- この腕は単独では決めない（`threshold_met=True` でも `met=False`、`why="AGREEMENT_ONLY"`）。生成の型との一致だけに使う。
- 帰結: K62 の `P_MOVE` に に+PLACE の行は無いので、に+PLACE が有意な移動の動詞は (a)(b) で候補にならない。再現率は低く、精度を優先する設計である。

### 12.5 名詞の「時・場所・数量」の腕 `slot`（出所ごと。`ARMS_BY_SOURCE`）
- 12.3 の数えから、名詞の語ごとに出所ごとに、型ごとに別の数を数える（型をまたいで足さない）。`TIME`: 印が ∅ か に で、述語が「過去」の印つき。`PLACE`: 印が で か に で、述語の段 1 の型（`DECIDED`・direct・生成の腕なし）が `P_MOVE` か `P_EXIST`（**動詞の一覧を書かない。配置の型で決める**）。`QUANTITY`: 既存の `counters`（算用数字の直後の 1 形態素）のその語の数をそのまま使う（新しく数えない）。
- 行 `(語, "slot", 出所, 型, n, base=その出所での名詞の使用数)`。builder は出所ごとの基準率（その出所の全名詞の使用のうちその構文に出た割合）に対する持ち上げが `slot_lift_pct`%（= `ctx_min_lift_pct` と同じ 300）以上の型だけを行にする。
- `arm_verdict("slot")`: 最上位の型の数 ≥ `slot_min` かつ ≥ `slot_share_pct`% × base。同点は全部並べる。
- この腕も単独では決めない（`AGREEMENT_ONLY`）。W3-a2 の `gen_definition` の格上げ（生成でない腕で、自分の閾値を満たし、最上位がちょうど [T]）の相手にだけなる。したがって `slot` で direct になった語の `decided_by` には必ず `gen_definition` が入る（W3-b1 の門 4 に当たる。仕様どおり）。名詞の生成は W3-a2 の物をそのまま使う（作り直さない）。

### 12.6 生成の腕 `gen_frame` と格上げの規則（`coarse_types.decide_word` の 1 か所）
- 票の行 `(語, "gen_frame", "generated:<model>:<effort>", 述語の型, 1, None)`。枠の行（票でない。`NON_VOTE_ARMS`）`(語, "gen_frame_slot", 同じ出所, "<助詞>|<名詞の型>", 1, None)`。名前空間に P を含む語だけ（名詞には付けない）。
- `GEN_ARMS = (gen_definition, gen_frame)`。生成が決め手に入った語は、直接でも推定の材料（head の段・donor・単位の族）にしない。
- 判定（`gen_frame` の行がある語）: (1) 生成の腕と `role_distribution`・`slot` を除いて判定（`_decide_base`）。`DECIDED`／`MULTIPLE` ならそれが最終（`why="GENERATED_NOT_DECIDING"`）。(2) `UNPLACED` で `gen_frame` の型が 1 つ T のとき、`role_distribution` の腕のうち自分の閾値を満たした（票のある）ものを R とする。**格上げ（direct）**: |R| ≥ `rd_min_sources`、R のすべての腕の票が [T]、かつ R の各腕について「生成の枠の助詞の集合 ⊇ その腕の有意な助詞の集合（9 種全部。と・まで・より を含む）」→ `DECIDED`・`origin=direct`・`decided_by = sorted(R の腕 + ["gen_frame"])`。R の腕に T と違う型の票がある → `estimated(generated)`・`why="DISTRIBUTION_DISAGREES"`（MULTIPLE にはしない: 分布の腕は単独で決めない腕で、直接の候補として並べない）。型は一致するが助詞の包含が成り立たない → `estimated(generated)`・`why="FRAME_PARTICLES_NOT_COVERED"`。R が空、または |R| < `rd_min_sources` → `estimated(generated)`（`why` なし）。(3) 生成が棄権（null）・枠が採れない → 何もしない。
- 推定（生成）の答えの形は W3-a2 と同じ（`estimate_basis="generated"`）。`estimate_basis` に新しい値を作らない。
- 帰結: K62 は 2 型だけなので、生成と分布の一致で `direct` になる述語の型は `P_MOVE` と `P_COMMUNICATE` だけ。ほかの 11 型は `estimated(generated)` に留まる。
- 格上げのうち、票を出した分布の腕がすべて codex コーパスの出所（jawiki 無し）だった語の数を別に出す（codex が書いた枠と codex が書いたコーパスの一致であることを隠さない）。
- `gen_frame` で格上げした述語は、W3-b1 の門 4（`'gen_definition' in decided_by` の文字列だけを見る）を通る。読解器が使うかは W3-b2 で決める。答えに `generated_frame: true` を付けて機械的に区別できるようにする。

### 12.7 既存の `frame` 腕（`PRED_FRAME_RULES`）の扱い
削除しない。設定 `frame_decides`（`DEFAULT_CONFIG` の既定は True。古い配置で保存された判定を再現するため）で決め手に入れるかを切り替える。False のとき `frame@src` は `threshold_met` のまま `met=False`、`why="FRAME_NOT_DECIDING"`。
**決め方（dev の動詞を測る前に書く）**: dev の動詞（12.11）について、R5 で `decided_by` に `frame@` を含む語の正答・誤決定を数え、**正答が誤決定の 3 倍以上なら True、そうでなければ False**。どちらも 0 のときは False（決め手の無いものを決め手に入れない）。数は `dev_frame_legacy.txt` に。W3-a の凍結データの数字（決め手の 18 語のうち正答 2・誤決定 11）は根拠にしない。

### 12.8 設定・dev の格子・選び方
新しい設定（`DEFAULT_CONFIG` に追記。既存の設定の値は変えない。既定値は古い配置で今の判定を再現する値）と、dev で試す格子（厳しい側から並べる。この並びが最後の同数の解消の順）:

| 設定 | 意味 | 格子 |
|---|---|---|
| `frame_decides` | 既存の `frame` 腕を決め手にするか | 12.7 の規則で 1 つに決まる |
| `rd_store_min` | 分布の行を保存する床 | 固定 20（格子の `rd_min_total` の最小値以下） |
| `rd_min_total` | 分布の腕の型つきの項の最小 | 100 / 50 / 20 |
| `rd_particle_min` | 有意な助詞の最小数 | 10 / 5 |
| `rd_particle_share_pct` | 有意な助詞の割合 | 30 / 20 / 10 |
| `rd_type_share_pct` | 助詞の中で有意な型の割合 | 70 / 50 |
| `rd_min_sources` | 格上げに要る分布の腕の数 | 2 / 1 |
| `slot_min` | slot の最小数 | 20 / 10 / 5 |
| `slot_share_pct` | slot の割合 | 30 / 20 / 10 |
| `slot_lift_pct` | 基準率に対する持ち上げ | 固定 300（= `ctx_min_lift_pct`） |

**選び方**: 述語は dev の動詞で、`origin=direct` の誤決定が 0 の設定のうち、`origin=direct` の正答が最多のもの。誤決定が 0 の設定が無ければ、誤決定が最少の設定のうち同じ規則。同数なら direct の答えが少ない（より厳しい）もの、なお同数なら格子の並びで先のもの。名詞（slot）は dev の語彙（L2）で、`direct` の誤決定が slot なし（段 1 と同じ判定）より増えない設定のうち、direct の正答が最多のもの。同数の扱いは述語と同じ。格子の評価は **1 つの dev 配置の保存された evidence から `ct.decide_word` を設定を変えて呼び直す**（判定は evidence と設定だけの関数。保存の床と持ち上げは固定なので結果に効かない）。選んだ値で dev 配置を 1 回作り直し、問い合わせの入口で同じ数になることを確かめる。**凍結データを見て設定・規則を変えない**。

### 12.9 述語の枠の生成（`tools/gen_coarse_evidence.py --kind pred`）
- 名詞の形（プロンプト・schema・argv・sha256 `ded30f48c0a596575d061e75aa0768beb3008969a587a01d2ec39807af031f65`）は 1 バイトも変えない。述語は `--kind pred`（既定 `noun`）。台帳・再開・再試行・上限・並列・stdin を閉じる・`--codex-bin` 必須・道具の使用の棄却は既存の仕組みをそのまま使う。
- `needs --kind pred`: 見出し語のうち ns が P か NP、state が UNPLACED か MULTIPLE、かつ抽出段の cache の品詞の数で動詞（V）の使用が形容詞・形状詞（A+S）の使用より多い語（一覧を作るための絞りで、型の票ではない。全出所の和を使う）。`n_seen` の降順、境界の同点は全部入れる。検査データを読まない。上位 5,000 語。
- 呼び出し: `gpt-6-luna`・effort `low`・`--slots 12`・`--max-calls 1500`・`-s read-only`・stdin を閉じる・束 40 語。
- プロンプトは 13 の述語型 id と名詞 17 型の id を `coarse_types.PRED_TYPES`・`NOUN_TYPES` の説明つきで機械的に並べる（手で写さない）。助詞は 9 種。語ごとに `ptype`（13 の id か null）と `frame`（`[{"particle": 9 種, "types": [17 型 id…]}]`）。例に検査データの語を使わない。
- 出力の検査: 束に無い語は捨てて数える（`foreign`）、同じ語が 2 回返ったら採らない（`dup_dropped`）、同じ助詞が 1 語の frame に 2 回あればその語の frame を採らない（`frame_dup_particle`）、ptype が null なら棄権、enum の外は採らない（`invalid`）。

### 12.10 問い合わせの新しい欄（§11.6 の契約への追記）
すべての答えに、既存のキーの値と順を変えずに、最後に次のキーを足す。
- `frame_status`（**閉じた一覧**）: `CONFIRMED`（下の `frame` がある）・`NOT_CONFIRMED`（P の direct だが `gen_frame` の格上げで決まっていない）・`ESTIMATED`（推定）・`NOT_PREDICATE`（名前空間が P でない、または型が P_ でない）・`NO_ANSWER`（UNPLACED・UNKNOWN・MULTIPLE）・`NO_PLACEMENT`・`NO_FRAME_TABLE`（`generated_frames` 表の無い古い配置で、P の direct の答え）。
- `frame`: `CONFIRMED` のときだけ `{助詞: [名詞の型, …]}`、ほかは null。中身 = 格上げに加わった分布の腕の有意な助詞の和集合 S（集合の和で、数は足さない）の各 p について、生成の枠の p の型（ソート）。S に無い生成の助詞は `frame` に入れず `frame_unconfirmed`（表示用。`CONFIRMED` のときだけ付く。読解器は使わない）に出す。助詞の並びは `ROLE_PARTICLES` の順。
- `generated_frame`（直接の答えだけ）: `decided_by` に `gen_frame` があれば true。`gen_frame` の腕の `axes` に `provenance`（model・effort・batch_id）。
- `axes["role_distribution@…"]`・`axes["gen_frame"]` の `top` は `decide_word` の判定を出す（数の鍵が「助詞|型」なので最大の鍵は意味が無い）。ほかの腕の `top` の出し方は変えない。
- 不変条件: `frame` が null でない ⇔ `frame_status == CONFIRMED` ⇒ `namespace == "P"`・`state == DECIDED`・`origin == direct`・`gen_frame ∈ decided_by`・鍵はすべて格助詞 9 種・値は空でない 17 型のソート済みの並び。
- `why` の閉じた一覧（新規分）: `AGREEMENT_ONLY`・`FRAME_NOT_DECIDING`・`DISTRIBUTION_DISAGREES`・`FRAME_PARTICLES_NOT_COVERED`（既存の `GENERATED_NOT_DECIDING`・`GENERATED_SPLIT`・`SEEDED`・`OUTRANKED`・`ROLE_SINGLE_SOURCE`・`RECOVERED_NOT_DECIDING` はそのまま）。

### 12.11 検査データ・採点
- 抜き出しの枠: `artifacts/w3-a/pred_verb_freq.tsv`（材料の頻度の上位 3,000 の述語）の `class == V`、`seed == -`、`in_predicate_check == -` の行。**種と W3-a の述語の確認とは重ねない**。
- `tests/coarse_place/data/dev_verbs.jsonl`（dev、閾値を決める用）: 枠から `random.Random(20261004).sample` で 130 語に手で型を付ける。断片（語にならないもの）は `kind="unknown_fragment"`・`gold=[]`・`gold_unknown=true`。それに、材料に無い造語の動詞 20 語（`kind="unknown_coined"`）。
- `tests/coarse_place/data/verb_check_300.jsonl`（凍結の検査）: dev の 130 語を除いた残りから `random.Random(20261005).sample` で 260 語に型を付け、断片は unknown にし、造語の動詞を足して計 300 行（造語 40 語）。
- 行の形: `{"id","term","kind":"typed"|"unknown_fragment"|"unknown_coined","gold":[P_ 型,…],"gold_unknown":bool,"frame":{助詞:[名詞の型,…]}|null,"why":短い理由}`。`gold` は多義なら 2〜3 型まで。`frame` は `P_MOVE`・`P_COMMUNICATE` を gold に持つ語には必ず書く。frame の照合は報告だけ。
- 造語は配置 R5 の `headwords` に無いことを確かめて記録する（`coined_absent.txt`）。造語だけを `exclude_coined.jsonl` に書き、r6 の作成で `--exclude-terms` に渡す。**検査データのファイルそのものは `--exclude-terms` に渡さない**。
- 採点（W3-a の `PREREG.md` と同じ定義）: 正答 = `top` が空でなく gold と交わり `len(top) ≤ max(1, len(gold))`。誤決定 = `len(top)==1` かつ gold の外。**Q3 の分母**: 誤決定率 = `origin=="direct"` かつ誤決定 / typed の件数。分からない語で型を返す率 = `top != []`（直接・推定を問わない）/ unknown の件数。参考に direct の答えの中での誤決定の割合も出す。断片の語は材料にあるので生成の一覧に入りうる。モデルが型を返せば `estimated(generated)` になり「型を返す」に数える（一覧から手で除かない）。
- 凍結: `artifacts/w3-a3/FROZEN.json`（各ファイルの sha256・行数・凍結時刻 `frozen_at`、`PREREG.md` の sha256）。**凍結時刻 > この節の登録時刻**、かつ **凍結時刻 < 製品コードの最初の変更**。

### 12.12 受入基準（事前登録）
- **Q1** 分布の腕と格上げの規則が、検査データを書く前に docs に日時つきで登録されている。語の一覧が無い。
- **Q2** 生成は上限 1,500 回以内。成功した束の割合・所要時間・1 語あたりの呼び出し数を報告。
- **Q3** 動詞 300 語の凍結データで、`direct` の述語の型の **誤決定 ≤ 5%**、分からない語で型を返す ≤ 20%（目標の正答率は書かない。数だけ）。中間職の 100 語でも同じ条件。
- **Q4** W3-a の凍結データ L1〜L3 が悪化しない（W3-a2 の承認条件と同じ）。
- **Q5** 配置の作成が決定的（cache なしの 2 回の `content_sha256` が一致）。
- **Q6**（監査役が測る）隠しバンク B1 を `VERA_PLACEMENT` つきで流し、誤読 0・誤答 0 のまま `PLACEMENT_PREDICATE_UNIDENTIFIED` の件数が減る。**この基準は配置の側の変更では動かない見込みで、満たせないものとして報告する**: その理由を出すのは `origin/integ-w3b1:verantyx/semantic_read.py` の 760 行目だけで、英語の入力で、どの語も既知の動詞の閉じた一覧に無いときに、配置を一度も問い合わせずに足される（`_read_en`、758〜760 行）。日本語の経路にこの理由は無い。
- **Q7** 既存テストの失敗集合が基線（114 件）から増えない。

### 12.13 決めた順
登録（この節）→ 検査データの作成と凍結 → 既存 `frame` 腕の dev での判定（R5）→ 製品コード → 合成のテスト → 抽出の cache と述語の生成なしの配置（r6/base）→ 述語の一覧と生成 → dev の格子と設定の凍結 → 全量 r6（cache なし 2 回）→ 凍結データの測定 → 全体テストと文書。凍結データの測定のあとに規則・設定を変えない。

### 12.14 変更記録（登録のあとの変更はすべてここに日時・前後・理由を書く）
（登録時点では無し）
