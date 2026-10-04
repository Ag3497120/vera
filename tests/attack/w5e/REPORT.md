# W5-e 攻撃報告

## 1. 対象

- A-1: `docs/OBSERVATION.md` §W5-e A-1、H2（AGREE と TYPE_UNCHECKED の併存時は `INCOMPLETE_TYPING`）。
- A-2: `docs/ROUTING_FROM_TEXT.md` §W5-e A-2 第2ラウンド、H3（推定の主語を担当者に振らない）。
- A-3: `docs/BASIS_POLICY.md` §W5-e A-3、H4（human_confirmed の分類、document の本文照合）。
- A-4: `docs/COARSE_PLACEMENT.md` §14、H5、および §14.2 R1（確認済み枠の交わり、覆った `へ`）。
- B: `docs/READING_SOUNDNESS.md` §10E B-1/B-2、H6（並立・選言を役割値に畳まず棄権）。

## 2. 命中した攻撃

### B-1: コピュラの値「太郎と花子」を一つの role value として返す

- 観点: (a)。入力 `犯人は太郎と花子だ。`。
- 再現: `PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W5-e PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W5-e/test_attack_coordination_copula_and_tomo.py`。
- 実際の出力: `readable: true`、`clauses[0].roles == {"entity": "犯人", "value": "太郎と花子"}`、`unsupported == []`。詳細は `attack_run.txt` と失敗したテストの assertion 出力。
- 期待との差: 並立した名詞句が role の値になる文は棄権する約束だが、値を一つにまとめて読んだ。
- 該当箇所: `verantyx/semantic_reader.py:1451-1457` は助詞の後に名詞類が続き、その次が助詞の場合だけ表層マークを返す。コピュラ値の後はその条件を満たさず、`1461-1474` の門にも構文印が渡らない。対象の約束は `docs/READING_SOUNDNESS.md:2579-2591`。

### B-2: 「とも…とも」の companion を一つの値として返す

- 観点: (a)。入力 `太郎とも花子とも話した。`。
- 再現: 上と同じテストコマンド。
- 実際の出力: `readable: true`、`clauses[0].roles == {"companion": "太郎とも花子"}`、`unsupported == []`。
- 期待との差: 二つの名詞を含む並立の役割値を棄権せず、一つの companion 値に畳んだ。
- 該当箇所: `verantyx/semantic_reader.py:1452-1457`。`と` の直後の `も` は `_COORDINATION_RUN` に入らず、この形のマークが作られない。役割は `frame` 読みなので `1465-1469` の構文印にも当たらない。

この2件は同じ門の境界漏れだが、別の形態で実行してそれぞれ失敗を確認したため、命中数は2とした。テスト入力と期待は実行前に固定し、`frozen.sha256` に sha256 を記録した。

## 3. 外れた攻撃と、依頼された既知穴の再現

ここでは攻撃番号を入力群単位で数える。

### M-1: A-1 の証言の組合せと順序

- 試したもの: AGREE/DISAGREE/TYPE_UNCHECKED の3証言、DISAGREE＋TYPE_UNCHECKED だけ、全て TYPE_UNCHECKED、AGREE の TIE に TYPE_UNCHECKED を加えて文順を逆転。
- 結果: 追加した4境界テストは改訂版で `4 passed`（`a1_boundary_run_r2.txt`）。AGREE が残る混合では `INCOMPLETE_TYPING`、AGREE が無い混合・全未確認は `NO_TYPED_CANDIDATE`、TIE に勝者は出ず `ranks == []`。
- 再現: `PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W5-e PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -q attacks/W5-e/test_attack_a1_boundary_mixes.py`。

### M-2: A-2 の推定 P_*・非名詞型 MULTIPLE と r8 サ変主語

- 試したもの: 推定 `P_*` と、名詞型を含まない direct MULTIPLE。既存の W5-e 経路テストで各条件が棄権／通過の登録どおりであることを確認した。
- r8 では r7 に無かった direct `〜する` 型を70語確認した（対象例と出力は `a2_r8_suru_probe.txt`）。そのうち `報告する`・`報告するはテストをする。` など3文を実入口に通すと、全て `UNREAD / NO_SUPPORTED_CLAUSE` で止まり、担当者に振られなかった（`a2_r8_subject_probe.txt`）。
- 結果: 約束違反の route は再現しなかった。推定 P_* と MULTIPLE のテストは既存関連テスト内で通過。

### M-3: ほかの並立・選言表現

- 試したもの: `太郎と花子とが来た。`、`太郎や花子などが来た。`、`太郎または花子が本を買った。`、`太郎もしくは花子が本を買った。`、`太郎あるいは花子が本を買った。`。
- 結果: 全文が棄権し、単一の役割値は返らなかった。最初の2文には `COORDINATION_UNDETERMINED`、接続詞3文には `unrepresented source content` が付いた（実測は `coordination_boundary_probe.txt`）。接続詞3種は登録した閉じた助詞 `と・や・か` の外で、棄権自体は満たしているため命中には数えない。

### M-4: 句読点・英語・A-4 の枠

- `太郎と、花子が来た。` は `agent: 花子, companion: 太郎` と読めた。`Tom and Mary read the letter.` は既存の `EN_UNREAD:coordination: not representable` で棄権した（`coordination_boundary_probe.txt`）。
- `太郎と一緒に花子が来た。` は棄権した。これは `docs/READING_SOUNDNESS.md:2597-2599` に既知の過剰棄権として記載されており、新しい約束違反としては数えない。
- A-4/W3-b2 の関連テストは `28 passed`（`related_run_2.txt`）。`frame_unconfirmed` だけに `へ: [PLACE]` がある入力を reader に通すと、`predicate_frame` は `('confirmed', {})`、型確認は `PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:へ` を返した（`a4_reader_probe_retry.txt`）。reader は `frame_unconfirmed` を根拠にしていない。
- r7/r8 の共通4,788語を読み、同じ `frame_status` のまま `frame` が違う語は0だった（`a4_r7_r8_diff_probe.txt`）。`移す`・`通う` はこの r7/r8 間では ESTIMATED→CONFIRMED と状態も変わり、r8 の空の `frame` は裏づけの交わりに沿う（`a4_r7_r8_probe.txt`）。

### A-3 の自己申告は依頼どおり再現したが、事前登録済みの例外として数から除外

- 観点: (b)。`memory_sovereign + human_confirmed` に ID なし、store_id のみ、confirm_id のみ、空文字 ID を与えた。
- 実際の出力: 4通りすべて `HUMAN / ANSWER_HUMAN_BASIS / ANSWER`（`a3_policy_variants_probe.txt`）。これは構成した偽の出典での分類挙動であり、元の主張の証拠ではない。
- 該当箇所: `verantyx/basis_policy.py:193-198` は `family` と `origin` だけで `human` にする。`docs/BASIS_POLICY.md:1322` は ID を条件にしないと明記し、`:1369` で同じ入力を既知の穴としている。依頼に従い実測は記録するが、既に許容された挙動なので「文書に反する命中」には算入しない。

## 4. 数

- 命中: **2**（コピュラ値、`とも…とも`）。
- 外れ: **4群**（A-1 境界、A-2、その他の並立・選言、句読点/英語/A-4）。
- 文書に明記された既知穴の再現: **1群**（A-3、4 ID 形態）。既知の過剰棄権: `と一緒に` 1形。

## 5. 実行・受入・判断の記録

- 攻撃テストは `attack_run.txt` で **3 failed**。内訳は上記の B の2件と、既知穴を検出する A-3 テスト1件。A-3 は受入違反に数えていない。
- 関連する既存テスト: A-1/A-2/A-3/B は **125 passed**（`related_run_1.txt`）、A-4 は **28 passed**（`related_run_2.txt`）。全体テストは実行していない。
- A-1 の初版境界テストは、文順を変えた際の証拠 ID/順序まで同一と要求してしまい1件失敗した（`a1_boundary_run.txt`）。それは勝者選択の差ではないと判明したため、回答状態・候補集合・除外理由だけを比較する版を別ハッシュ `frozen_a1_r2.sha256` で凍結し直し、4件通過を確認した。旧版ハッシュは `frozen_a1.sha256` に残した。
- A-4 の最初の合成 reader probe は `Span` を `Role` の位置に渡したため `AttributeError` になった（`a4_reader_probe.txt`）。入力治具を `Role` に直して再実行した結果は `a4_reader_probe_retry.txt`。製品コードの失敗ではない。
- pytest の `tmp_path` が `/private/var/folders/.../pytest-*` に一時配置データを作成した。最初の2回の関連テストでは pytest cache provider も有効だった。いずれも攻撃結果の出力は `attacks/W5-e/` に保存し、一時物を削除していない。製品コードは変更していない。
