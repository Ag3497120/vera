# T8 の手引き — 読解器の決着試験（オーナー向け）

この手引きは、人の確認（`vera confirm`）が読解器に何を足すかを、オーナーの実際の文で測る手順を書く。契約は凍結のまま（出力の型・棄権の型・出所の型・再読の門・同点は棄権・昇格の規則・形態素辞書の版）。設計と事前登録は `docs/COARSE_PLACEMENT.md` の 12.21。

**先に知っておくこと（隠さない）**
- 人の確認は、読解器が配置に問い合わせる語にだけ届く。問い合わせの出ない判断点（受け手の型・場所の型が決まらない文、述語が見つからない文）は、確認しても動かない。`suggest` はそれを `reachable=false`（`NOT_REACHABLE_BY_CONFIRMATION`）で出す。
- 分析の予備実験では、確認の増分は「確認した語が再び出た分」だった。一般化（確認していない語の文が読めること）は示せていない。この試験はそこを測る。
- 開発側の合成データ（`artifacts/w16-t8/data/`）は自作で、道具が動くことの確認にしか使えない。そこで通ったことは、実際の文で読めることの証拠にならない。

## 1. 150 文を書く

- 150 文のうち **半分（75 文）は今の書き方**（いつもの文体のまま。主語や助詞の省略、くだけた言い回しを直さない）、**半分（75 文）は統制した書き方** にする。
- 統制した書き方の約束:
  - 主語と目的語を省かない（「誰が・何を」を書く）。
  - 助詞を明示する（が・を・へ・に・で・から）。
  - 1 文に述語を 1 つだけ。
  - 文末は「〜した。」「〜する。」の言い切り。
- 統制した書き方で、いまの配置 r9 で読める例（`vera confirm suggest` で確かめた。出力は `artifacts/w16-t8/guide_examples_check.txt`）:
  - 田中が倉庫へ向かった。
  - 鈴木が荷物を倉庫へ運んだ。
  - 太郎が本を読んだ。
  - 整備士が書庫で本を書いた。
- 読めずに棄権し、確認で届く例: 「田中が整備室へ出向いた。」（`出向く` の型が基底に無い。`set 出向く P_MOVE` を書くと、次の `suggest` は未配置の `整備室` を名指しする）、「田中が学校へ出向いた。」（`set 出向く P_MOVE` のあと、`frame 出向く へ goal GROUP_ORG` を足すと読める）。
- 読めずに棄権し、確認では届かない例: 「ハルがミナに話した。」（読解器がミナの型を配置に問い合わせない）、「倉庫に着いたら連絡してください。」（読める節が無い）。
- 1 行 1 文で、UTF-8 のテキストファイルに保存する。`。` で文を切る（`vera confirm suggest` も同じ切り方）。

## 2. 確認の手順

配置（`--placement`、または環境変数 `VERA_PLACEMENT`）、確認を書く層（`--layer`）、台帳（`--ledger-file`）を決める。確認者の名前（`--by`）は必須で、理由（`--reason`）は任意。

1. **見る**: `vera confirm suggest --text 文のファイル --placement P [--layer L]`
   文ごとに読み、棄権した文の「確認すれば読めるかもしれない点」を 1 行 1 件の表で出す（列: sentence_id, text, status, op, word, particle, role, candidates, reason, reachable, why）。末尾の `#` の行に、読めた数・棄権した数・確認で届く候補のある文・届かない文、語ごとにふさいでいる文の数が出る。
   - `op=set`: その語の型を決める候補。`candidates` が空なら配置はその語を知らない（型を推測で埋めない。人が決める）。
   - `op=frame`: 述語の助詞と役割の枠が足りない候補。`role` の列は空（読解器の理由に役割が無いため）なので、役割（agent・goal など）は人が決めて `frame` に書く。`why` に `PREDICATE_TYPE_SET_FIRST` と出たら、先に述語の型を `set` で確認する。`reachable=false` の `frame`（`BASE_FRAME_1210_KEPT`・`BASE_ROLE_FRAME_INVALID`）は確認では動かないので書かない（下の「枠の確認の意味」）。
     **枠は「足す・検査する」もので、「制限する」ものではない**（下の「枠の確認の意味」）。
   - `op=none`（`reachable=false`）: 確認しても届かない判断点。
2. **書く**:
   - `vera confirm set <語> <TYPE> --by 名前 [--reason 理由] --layer L --ledger-file F --placement P`
   - `vera confirm frame <述語> <助詞> <役割> <TYPE…> --by 名前 --layer L --ledger-file F --placement P`（述語の型を先に確認していること。助詞は が・を・に・で・へ・と・から・まで・より、役割は agent・goal など）
3. **もう一度見る**: 読解器は最初の門で止まるので、1 回の `suggest` は最初のふさがりしか見えない。確認 → `suggest`（`--layer L` つき）を、新しい候補が出なくなるまで繰り返す。
4. **間違えたら**: `vera confirm undo <確認 id> --by 名前 --layer L --ledger-file F`（追記。確認の行は消えない）。`vera confirm list [--all]` で一覧（`--all` は取り消し済みも）。

### 枠の確認の意味（r3 の裁定で改めた。r9 で確かめた。`artifacts/w16-t8/t82f_set_only_vs_frame.tsv`、`artifacts/w16-t8/r3/`）

- **`set` は型だけを変える。基底の枠は残る（r3、監査役の裁定 2026-10-06 00:24）。** 基底がすでに確かめた 12.10 の枠（述語の助詞と型の枠。`frame_status=CONFIRMED`）と、役割枠は、`set` の後も基底のまま残る（答えの `decided_by` は `human:<id>` の後ろに `gen_frame` が付く。読解器がそれを要るため）。人が確かめたのは型だけで、枠ではないので、`set` だけでは「`が` を拒む」などの安全の門は消えない。例: `set 移動する P_MOVE` のあとも「田中が駅へ移動した。」は `PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:が` で棄権のまま（`t82f_set_only_vs_frame.tsv` の `set_only` の列）。以前（r2）はこれが読めるに変わっていた。
- **`frame` が変えるのは役割枠だけ。12.10 の枠は人の確認では変わらない。** 基底に確かめた 12.10 の枠が無い述語（例: `出向く`・`赴く`・`転勤する`。基底は estimated で枠なし）では、`set` だけだと「田中が学校へ出向いた。」は `PLACEMENT_TYPE_MISMATCH:P_MOVE:へ:GROUP_ORG` で棄権し、`frame 出向く へ goal GROUP_ORG` を足すと読める（`artifacts/w16-t8/r3/flow/` の `frame_reach` 5 文が全部読めた）。**基底が 12.10 の枠を持つ述語（例: `移動する`・`避難する`）では、枠の理由の棄権（`PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED` など）は人の確認では動かない。**
- **基底の役割枠が `CONFIRMED` の述語では `frame` も効かない（J15、直していない）。** 基底の役割枠の項目には `backed_by` があり、読解器は鍵が `role`・`types` ちょうどでない枠を拒む（`ROLE_FRAME_INVALID:ENTRY_KEYS`）。人の枠を重ねても基底の項目の `backed_by` は残る（人が確かめていない基底の項目を、人の確認を口実に読ませないため）ので、その述語では人の `frame` の行を書いても読解は変わらない（`移動する` が該当）。
- **`suggest` の `reachable=false` の読み方。** `why=BASE_FRAME_1210_KEPT`: 基底の 12.10 の枠が理由で、`vera confirm` では動かない。`why=BASE_ROLE_FRAME_INVALID:…(J15)`: 基底の役割枠を読解器が拒むので、`frame` を書いても読めない。どちらも確認の候補にしない（確認の行数を使わない）。`why=FILLER_TYPE_REFUSED:<型>` の `set` は、名詞の型を述語の都合で変える候補（たとえば GROUP_ORG の「学校」を PLACE に直す）で、`reachable=true` と出るが、名詞の型を変えるので **先に述語の `frame` を使えるかを見る**。
- **人の枠は、型の表がその型を挙げていない文（`PLACEMENT_TYPE_MISMATCH` で棄権する文）で読みを足す。宣言しなかった型・助詞は止めない。** へ の枠に GROUP_ORG だけを宣言しても、goal が PLACE の文は読める（`frame_not_restrictive`。r2 の測定、基底が枠を持たない述語の場合）。枠で「この述語の へ は組織だけ」と絞ることはできない（読解器の意味 K274 で、このチケットでは変えない）。確認した枠と違う読み（例: へ の goal が PLACE）が出ることがあり、オーナーの 150 文の試験ではこれを誤読として数えるかどうかを測定の前に決めておく。
- 枠を確認しても読めない文もある（名前が MULTIPLE のまま、など。suggest は `set <名前>` を名指しする）。

### 人の確認として効く行（r3、監査役の裁定）

人の確認として基底の上で効くのは、`vera confirm` が書いた行（確認 id が 16 桁の小文字 16 進で、`decided_by` が `["human:<確認 id>"]`）だけである。`tools/build_initial_layers.py combine` などで層を写すと、写された行は確認 id が `evidence.from_evidence` の中に包まれ確認の行の形でなくなるので、`layer_estimated`（表示するだけで、読解器は使わない）として扱われる。確認は写した層ではなく、`vera confirm` で書いた層をそのまま使う。

確認は、基底の配置が既に決めている語（DECIDED）にも **基底より上** で効く。その場合、答えに `decided_by: human:<確認 id>` が残り、基底の値は `axes.layer.overrode_base` に残る。確認した型と基底が違うときは人の確認を採る。同じ語に人が 2 つの型を確認すると同点なので棄権し、基底のままになる（`HUMAN_CONFLICT`）。

## 3. 確認は 50 行まで

- 数えるのは `vera confirm list`（取り消し済みを除く）の行数。`set` も `frame` も 1 行。50 行を超えて確認しない。
- 確認は「どの文がふさがっているか」の多い語から（`suggest` の末尾の `# blocks` の行が多い順）。

## 4. 試験の分割の作り方

- **train（確認に使う）**: 150 文のうち、確認する語を選ぶ側。確認する語は train の文からだけ選ぶ。
- **test（確認語と重ならない）**: train で確認した語（述語はその語幹も）を 1 つも含まない文。`measure.py` が確認語と test の文の重なりを調べ、重なりがあれば `TEST_OVERLAPS_CONFIRMED` と印をつける（印のついた傾きを一般化の証拠にしない）。
- **real（実際の文）**: 確認語の一覧を見ずに書いた実際の文。**これが決着の根拠になる**。
- それぞれ JSONL（1 行 1 文）: `{"id": "...", "text": "...", "expect": ...}`。`expect` は、読めるはずの文なら節の列 `[{"predicate": "移動する", "roles": {"agent": "田中", "goal": "整備室"}, "polarity": "+", "tense": "past", "voice": "active"}]`、読めてはならない文なら `"ABSTAIN"`、判断しない文なら `null`。**確認を始める前に `expect` を書き、sha256 を残す。**
- 確認の列 `confirmations.jsonl`（順序つき。1 行 = 確認 1 行）: `{"op": "set", "word": "...", "type": "...", "reason": "..."}` または `{"op": "frame", "predicate": "...", "particle": "...", "role": "...", "types": ["..."], "reason": "..."}`。

## 5. 測る

```
python tools/t8/measure.py --placement P --confirmations confirmations.jsonl \
  --train train.jsonl --test test.jsonl --real real.jsonl --out DIR [--steps 0,5,10,...,50] [--owner-minutes 分の書いたファイル]
```
- 確認の行数 k（0, 5, 10, …, 50）ごとに、新しい層と台帳を作り、確認の先頭 k 行を書いて、3 つの集合の全文を読む。確認の列の行数を超える k は走らない（`steps_run` に残る）。`--out` は新しいディレクトリにする。
- `curve.tsv` の列: `readable`（読めた文）、`newly_read`（k=0 で読めず今読める）、`lost`（k=0 で読めて今読めない）、`correct`（期待どおり）、`misread`（読めたが期待と違う、または `ABSTAIN` のはずが読めた）、`unjudged`（読めて `expect` が `null`）。末尾の `# slope` の行が集合ごとの傾き（式は 12.21.4: k に対する `newly_read` の最小二乗の傾き。単位は確認 1 行あたりの新しく読めた文の数）。
- `curve.json` に全数値、重なりの検査（`overlap`）、誤読の詳細（`misread_detail`）が入る。
- 所要: `owner_minutes` は人が記入する欄。

### オーナーが記入する欄（空欄のまま渡す。数値を足さない）

| 項目 | 記入 |
|---|---|
| 「傾きがほぼ 0」とみなす閾値（real の傾きが ___ 未満）。**測定の前に書く** | ＿＿＿＿ |
| 「直せない誤読」とみなす条件（誤読が ___ 件以上で、確認を足しても減らない） | ＿＿＿＿ |
| 150 文を書いた時間（分） | ＿＿＿＿ |
| 確認の作業時間（分） | ＿＿＿＿ |

## 6. 撤退条件

次のどちらかに当たったら、凍結の選択肢 **(A) に戻す**（この配線は残してよいが、決着試験としては打ち切る）:
- **実際の文（real）での傾きがほぼ 0**（閾値は上の欄にオーナーが測定前に書いた値）。test の傾きが 0 でも real の傾きが大きいとき、その増分は「確認した語が実際の文にも出た分」で、一般化の証拠ではない。
- **直せない誤読**（読めた文が期待と違い、確認を足しても・取り消しても直らない）。

## 7. 不変（K683）

層を使わないとき、または層に人の確認行が無いとき、読解と問い合わせの出力は基点と byte 一致する（開発側で確認済み）。`vera ledger confirm` → `promote` が書く既存の `layer_human` 行は確認 id を持たず、従来どおり基底を上書きしない（人の確認の優先は `vera confirm` が書いた行だけ）。人の確認の形をしているのに確認として裏づかない行（`human:` の腕や確認 id を持つが `vera confirm` の行でないもの）は `layer_estimated` として扱う（r3）。
