# codex 生成コーパスの索引（P4 コーパス経路）

W1-c（第 1 ラウンド）と W1-c2（第 2 ラウンド）の成果。codex が生成したコーパスを Vera の検索経路
（`verantyx.ability_corpus.Corpus`）につなぐ。
この文書の数値の表はすべて `artifacts/w1-c/render_docs_numbers.py` が `artifacts/w1-c/` の出力から作った
ものを貼っている。表は `python artifacts/w1-c/render_docs_numbers.py --check` で再生成と一致するか確かめられる。
表の外の本文に、測定していない数値は書かない（本文の数値は種・上限・登録した問数などの構造定数だけ）。

第 2 ラウンドの追加: heldout と同じ本文の train 行を規則で除外する（§3）、コーパスの文を根拠にした回答の最上位に
`basis_origin` を付ける（§4）、commonsense 経路の trace に索引の状態を載せる（§4）、C5 を C5' として登録し直して実行する（§8）。

## 0. 監査役への申し送り（先に読む）

- **C5'(i) 会話経路: 不成立。** 会話供給（`round3._conversation_supply`）が使う社交の定型文のうち、完全一致の行が索引にあったのは
  「どういたしまして。」だけで（表 `conv_supply` の「規則で除外された train 行」と「索引に残った train 行」の合計）、他の定型文は規則を入れる前から一致する行が無い。この文は heldout にも同じ本文があり、heldout と同一本文の train 行を除外する規則（追補の C4 補足）で
  索引から全件除外された。その結果、8 種の定型文のどれも `Corpus.search(..., limit=60)` の窓に完全一致の行を持たず、
  会話群には「コーパス経路に届く質問」が無くなった（§8 の表 `conv_supply` と `c5r2_groups`）。
  検索の件数上限・正規化・検索語は変えていない。R1 と C5'(i) の衝突であり、実装役が解いてはいけないので型付きで報告する。
- commonsense 経路では、事実質問（例: `富士山の高さは？`）が無関係な生成文を根拠に `answer / ANSWER` になる。
  追補の決定 1 (a) のもとで `basis_origin: "generated"` は付くが、直していない（§11）。
- 選択肢 (b)「生成文だけを根拠にした回答を ANSWER にしない」は別チケット（オーナーの判断事項。§11）。

## 1. 使い方

索引の作成（入力と出力の場所は引数か環境変数で与える。ホームディレクトリは見ない）:

```
python tools/build_p4_corpus_index.py --root <codex コーパスの根> --out <索引の出力先> \
       [--manifest <manifest.json>] [--family <系列>]... [--jobs <並列数>]
```

- `--root` を省くと環境変数 `VERA_CODEX_CORPUS`、`--out` を省くと `VERA_P4_INDEX`。どちらも無ければ
  `UNKNOWN_CORPUS_ROOT_UNSET` / `UNKNOWN_INDEX_OUT_UNSET` を標準エラーに JSON で出して終了コード 2。
- 終了コード: 0 正常、2 場所の未指定、3 入力ファイルが欠けて作れなかった系列がある（`UNKNOWN_SOURCE_MISSING`）、
  または heldout ファイルが欠けて作れなかった系列がある（`UNKNOWN_HELDOUT_MISSING`）、または `HELDOUT` 表に載っていない
  heldout ファイルがコーパスにある（`heldout_unlisted`）、4 照合の恒等式が崩れたファイルがある。
- 索引の実体はリポジトリの外に置く（この作業では `/Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c`）。git には入れない。
- 検索側は `Corpus(root=None)`。`root` が無いときは **構築時に** 環境変数 `VERA_P4_INDEX`、無ければ `<ツリー>/build/p4` を使う。
  既定の入口（`python -m verantyx.cli ask ...` や `Vera().ask`）は索引の場所を設定しない限りコーパスを使わず、
  `UNKNOWN_NO_INDEX` が trace に出る（§8 の (iv)）。

検索の意味は従来のまま: `LIKE '%語句%'` の逐語（空白も文字）。AND 分割・OR・同義語・正規化はしない。
空語と 80 字を超える語は検索しない（下の `UNKNOWN_QUERY_NOT_SEARCHED`）。

### Corpus が返す状態（型）

`search` / `search_scene` / `neighbors` はどれも `list` の部分型を返す。`for`・`len`・`if not rows`・`[0]` は従来どおり使える。
`Corpus.status(系列)` は検索せずに索引の状態だけを返す。

| state | 型 | 意味 |
|---|---|---|
| `FOUND` | `CorpusHits` | 索引を検索し、1 件以上あった |
| `NO_MATCH` | `CorpusHits` | 索引を検索し、該当が無かった（索引の不在ではない） |
| `UNKNOWN_NO_INDEX` | `CorpusUnknown`（常に空） | 索引ディレクトリが無い、または `*.db` が 1 つも無い |
| `UNKNOWN_FAMILY_DB_MISSING` | `CorpusUnknown` | 他の DB は在るが、その系列の `<系列>.db` が無い |
| `UNKNOWN_INDEX_UNREADABLE` | `CorpusUnknown` | DB を開けない、または表が無い・壊れている |
| `UNKNOWN_INDEX_REBUILD_REQUIRED` | `CorpusUnknown` | `meta.format` が無い旧形式（出所の欄が無い） |
| `UNKNOWN_QUERY_NOT_SEARCHED` | `CorpusUnknown` | 検索語が空、または 80 字を超えるため検索していない |

`status()` は上のうち `UNKNOWN_*` か `INDEX_AVAILABLE` を返す。`FAMILIES` に無い名前は従来どおり `ValueError`（API の誤用）。

## 2. 系列と入力の対応表

索引化の対象は train 側だけ。系列ごとに別の DB（`<系列>.db`）で、系列をまたいで混ぜない。
1 入力行は、索引の 1 行か、理由つきで数えた読み飛ばし 1 件のどちらかになる。

| 系列（DB） | 入力ファイル（`--root` 相対） | 本文にする欄（順に改行で連結） | 必須の欄 |
|---|---|---|---|
| `pro`（単文） | `out/sentences.jsonl` | `text` | `text` |
| `code` | `code/items.jsonl`, `even/code/items.jsonl` | `text` | `text` |
| `conversation` | `conversation/utterances.jsonl`, `even/conversation/utterances.jsonl` | `text` | `text` |
| `general_qa` | `general_qa/train/records.jsonl` | `q_variants[*]`, `answer`, `why` | `q_variants`（空でない文字列の list）, `answer` |
| `code_qa` | `code_qa/train/records.jsonl` | `question`, `answer_text`, `code`, `usage` | `question`, `answer_text` |
| `figurative_commonsense` | `figurative_commonsense/train/records.jsonl` | kind 別: pun は `pun`,`mechanism` / haiku は `haiku`,`note` / simile_metaphor は `expression`,`plain_meaning`,`example` / cause_effect は `cause`,`effect`,`phrasings[*]` | pun は `pun` / haiku は `haiku` / simile_metaphor は `expression` / cause_effect は `cause`,`effect` |
| `narrative` | `narrative/train/records.jsonl` | story は `title`,`sentences[*].text` / poem は `title`,`lines[*]` | 本文にする欄と同じ |
| `paraphrase_entail` | `paraphrase_entail/train/records.jsonl` | pair は `s1`,`s2`,`reason` / who_did_what は `sentence`,`question`,`answer` | pair は `s1`,`s2` / who_did_what は `sentence`,`question`,`answer` |

- `code` と `even/code`、`conversation` と `even/conversation` は同じ系列の別 shard として同じ DB に入れる（`source_file` で区別する）。
  重複する本文は消さない（heldout と同じ本文の行だけは §3 の規則で除外する）。
- `general_qa` の kind は `fact`, `howto`, `advice`, `comparison`, `definition`, `needs_live_data`, `greeting` を対応表に持つ。
- 必須でない欄が空・欠落のときは本文から外すだけで読み飛ばしではない。その件数は manifest の `optional_absent` に数える。
- 検索対象の本文にならない欄（例: `lang`, `style`, `level`, `phenomenon`）は索引に入らない。
- `local` 系列は `FAMILIES` に残るが対応する入力が無い。実データの索引には `local.db` が無く、`local` を引くと
  `UNKNOWN_FAMILY_DB_MISSING` が返る。

### 単文を `pro` 系列にした判断

`out/sentences.jsonl` は全行の出所タグが `llm_authored:codex:pro-…` で始まる（下の表「出所タグの接頭辞」）。
そのため系列名は `pro` とした。これは中間職の判断で、`local`（別の出所）とは混ぜない。

<!-- BEGIN table:source_tags -->
出典: `artifacts/w1-c/manifest.json の files[].source_tag_prefixes`

| 入力ファイル | 出所タグの接頭辞(llm_authored:codex: 以降、-b 連番の前)と件数 |
|---|---|
| out/sentences.jsonl | pro: 1366290 |
| code/items.jsonl | pro-code: 1020920 |
| even/code/items.jsonl | pro-code: 384269 |
| conversation/utterances.jsonl | pro-conv: 1732912 |
| even/conversation/utterances.jsonl | pro-conv: 509952 |
| general_qa/train/records.jsonl | pro-general_qa: 317423 |
| code_qa/train/records.jsonl | pro-code_qa: 324639 |
| figurative_commonsense/train/records.jsonl | pro-figurative_commonsense: 238905 |
| narrative/train/records.jsonl | pro-narrative: 146598 |
| paraphrase_entail/train/records.jsonl | pro-paraphrase_entail: 379574 |
<!-- END table:source_tags -->

### 読み飛ばし理由の語彙

`blank_line` / `bad_json` / `bad_utf8` / `not_object` / `partial_final_line`（最後の行に改行が無い）/
`split_not_train:<値>`（`split` キーが在り `"train"` 以外）/ `family_mismatch:<値>` / `unmapped_kind:<値>` /
`missing_required:<kind>.<欄>` / `bad_field_type:<kind>.<欄>` / `empty_body` /
**`heldout_body_overlap`（第 2 ラウンドで追加。他の理由では索引に入るはずだった行の本文が、同系列の heldout の本文と同じ）**。
`bad_utf8` は指示書の語彙に無く、実装役が足した（壊れたバイト列を `bad_json` と混ぜないため）。
`split` キーが無い行は読み飛ばさず、`split_absent` として別に数える。出所タグが `llm_authored:codex:` で始まらない行は
`source_tag_unexpected` として数える（読み飛ばさない）。`split_absent` などの付帯の件数は、索引に入った行だけで数える。
理由別件数の表（`skipped`）には 0 件の理由を書かない。

### 系列の状態の語彙（manifest の `families{}`）

`BUILT` / `UNKNOWN_SOURCE_MISSING`（対応表の入力ファイルが無い）/
**`UNKNOWN_HELDOUT_MISSING`（第 2 ラウンドで追加。`HELDOUT` 表に載った heldout ファイルが無い。除外の根拠が読めないまま作らない）**。

## 3. heldout の扱い

### 索引に入れないこと（第 1 ラウンドから）

- 対応表（`SOURCES`）には train 側のファイルだけを列挙する。
- 読み込む直前に、パスの構成要素に `heldout` か `overlap_dropped` が含まれていたら `ExcludedPathError` で止める（`guard_path`。
  索引の入力に対するこの守りは第 2 ラウンドでもそのまま）。
- 行ごとに `split` キーを判定し、`"train"` 以外は読み飛ばす。
- 索引に入れなかった heldout / overlap_dropped の各ファイルは manifest の `excluded[]` に行数・sha256 つきで残す（下の表）。

<!-- BEGIN table:excluded -->
出典: `artifacts/w1-c/manifest.json の excluded[]`

| 索引に入れなかったファイル | 理由 | バイト数 | 行数 |
|---|---|---|---|
| code/heldout/items.jsonl | heldout | 38,579,300 | 73,642 |
| code/overlap_dropped/items.jsonl | overlap_dropped | 142,644 | 257 |
| code_qa/heldout/records.jsonl | heldout | 32,672,820 | 34,523 |
| code_qa/overlap_dropped/records.jsonl | overlap_dropped | 4,500,919 | 4,352 |
| conversation/heldout/utterances.jsonl | heldout | 71,035,680 | 159,676 |
| conversation/overlap_dropped/utterances.jsonl | overlap_dropped | 1,056,147 | 2,067 |
| even/code/heldout/items.jsonl | heldout | 22,379,722 | 42,674 |
| even/code/overlap_dropped/items.jsonl | overlap_dropped | 92,206 | 168 |
| even/conversation/heldout/utterances.jsonl | heldout | 27,078,227 | 59,609 |
| even/conversation/overlap_dropped/utterances.jsonl | overlap_dropped | 8,270,594 | 15,953 |
| figurative_commonsense/heldout/records.jsonl | heldout | 13,456,250 | 25,074 |
| figurative_commonsense/overlap_dropped/records.jsonl | overlap_dropped | 869,481 | 1,431 |
| general_qa/heldout/records.jsonl | heldout | 25,354,215 | 34,171 |
| general_qa/overlap_dropped/records.jsonl | overlap_dropped | 11,048,812 | 14,024 |
| narrative/heldout/records.jsonl | heldout | 11,482,734 | 18,193 |
| narrative/overlap_dropped/records.jsonl | overlap_dropped | 733,167 | 941 |
| paraphrase_entail/heldout/records.jsonl | heldout | 20,495,039 | 43,544 |
| paraphrase_entail/overlap_dropped/records.jsonl | overlap_dropped | 2,690,717 | 5,113 |
<!-- END table:excluded -->

### heldout と同じ本文の train 行を規則で除外する（第 2 ラウンド、追補の C4 補足）

heldout ファイルの本文を索引に入れないだけでは足りず、train 側に heldout と同じ本文の行があると、それが索引に入ってしまう。
そこで次の規則を builder に入れた。

1. `HELDOUT` 表（`SOURCES` の隣）に、系列ごとの heldout ファイルを **明示列挙** する。`pro` は heldout が無いので空（表のコメントに明記）。
2. `heldout_bodies(root, family)` が heldout ファイルを読み、**本文の sha256 の集合と報告だけを返す**（行・本文・レコードは返さない）。
   本文は索引と同じ `extract_body` で作る（同じ対応表を使うので hash が比べられる）。`classify_line` は使わない
   （heldout は全行 `split: "heldout"` で、全部 `split_not_train` になって集合が空になるため）。
   `guard_path` は索引入力の守りなので、この読み取りには通さない。索引に行を入れる経路から heldout のパスへ届く道は作っていない。
   本文を取り出せない行は理由別に数える（`unextractable`。`blank_line` / `partial_final_line` / `bad_utf8` / `bad_json` / `not_object` /
   `extract_body` の理由）。
3. `build_db(..., exclude_bodies=...)` は、`classify_line` が行を返したあとで `body_sha` が集合にあれば、その行を読み飛ばし理由
   `heldout_body_overlap` で数える。**判定順**: 既存の読み飛ばし理由が先。`heldout_body_overlap` は「他の理由では索引に入るはずだった行」だけ
   （例: 自分の `split` が `heldout` の行は `split_not_train:heldout` のまま）。**同系列だけ**で判定し、系列をまたいで消さない。
   旧 `build(path, output, family)` は集合を空のまま呼ぶので挙動は変わらない。
4. `main()` は、系列ごとに入力の欠落（`UNKNOWN_SOURCE_MISSING`）を先に見て、次に `HELDOUT` のファイル欠落を見る。
   後者があればその系列は作らず `UNKNOWN_HELDOUT_MISSING`、終了コード 3。さらにコーパスの根の下を走査して、パス構成要素に `heldout` を含む
   ファイルのうち `HELDOUT` のどの系列にも載っていないものを manifest の `heldout_unlisted` に出す（無ければ空配列を必ず書く）。
   1 件でもあれば終了コード 3（系列の作成は続ける）。
5. 子プロセス（`--jobs`）の中で集合を作るので、集合は親プロセスへ渡さない。

実データでの結果（表はすべて出力から作った）:

<!-- BEGIN table:heldout_files -->
出典: `artifacts/w1-c/manifest.json の families{}.heldout.files[]`

| 系列 | heldout ファイル(root 相対) | バイト数 | 行数 | sha256(先頭16桁) | 本文を取り出せなかった行(理由別) |
|---|---|---|---|---|---|
| code | code/heldout/items.jsonl | 38,579,300 | 73,642 | 75aa084034f5d0be | なし |
| code | even/code/heldout/items.jsonl | 22,379,722 | 42,674 | ca49d8fc5fb3171c | なし |
| conversation | conversation/heldout/utterances.jsonl | 71,035,680 | 159,676 | 2b2e2a2937aa4042 | なし |
| conversation | even/conversation/heldout/utterances.jsonl | 27,078,227 | 59,609 | 414d7896c8c84a09 | なし |
| general_qa | general_qa/heldout/records.jsonl | 25,354,215 | 34,171 | f941fa4f4dbd72a8 | なし |
| code_qa | code_qa/heldout/records.jsonl | 32,672,820 | 34,523 | 6f5fdf928ded3740 | なし |
| figurative_commonsense | figurative_commonsense/heldout/records.jsonl | 13,456,250 | 25,074 | f459ff1579f8cfc8 | なし |
| narrative | narrative/heldout/records.jsonl | 11,482,734 | 18,193 | ae736cbeaf665720 | なし |
| paraphrase_entail | paraphrase_entail/heldout/records.jsonl | 20,495,039 | 43,544 | 2deea92eeffdbbe3 | なし |
| pro | (heldout ファイルなし: HELDOUT 表が空) | — | — | — | — |
<!-- END table:heldout_files -->

<!-- BEGIN table:heldout_bodies -->
出典: `artifacts/w1-c/manifest.json の families{}.heldout`

| 系列 | 本文を取り出せた heldout 行 | 異なる本文(sha256)の数 | HELDOUT 表が空 |
|---|---|---|---|
| pro | 0 | 0 | True |
| code | 116,316 | 116,316 | False |
| conversation | 219,285 | 217,865 | False |
| general_qa | 34,171 | 34,171 | False |
| code_qa | 34,523 | 34,523 | False |
| figurative_commonsense | 25,074 | 25,074 | False |
| narrative | 18,193 | 18,193 | False |
| paraphrase_entail | 43,544 | 43,544 | False |
<!-- END table:heldout_bodies -->

<!-- BEGIN table:heldout_unlisted -->
出典: `artifacts/w1-c/manifest.json の heldout_unlisted`

| 項目 | 値 |
|---|---|
| HELDOUT 表に載っていない heldout ファイル(root 配下を走査) | 0 |
| その一覧 | なし |
| UNKNOWN_HELDOUT_MISSING の系列 | なし |
<!-- END table:heldout_unlisted -->

ファイルごとの除外件数と、規則を入れる前の索引（r1）との差:

<!-- BEGIN table:r1_r2 -->
出典: `artifacts/w1-c/manifest.json と manifest.r1.json の files[]`

| 入力ファイル | 行数 | r1 の索引行(規則なし) | r2 の索引行(規則あり) | r1 - r2 | r2 の heldout_body_overlap | r2 の他の読み飛ばし | r2 balanced | 行数・sha256 が r1 と同じ |
|---|---|---|---|---|---|---|---|---|
| out/sentences.jsonl | 1,366,290 | 1,366,290 | 1,366,290 | 0 | 0 | なし | True | True |
| code/items.jsonl | 1,020,930 | 1,020,930 | 1,020,920 | 10 | 10 | なし | True | True |
| even/code/items.jsonl | 384,279 | 384,279 | 384,269 | 10 | 10 | なし | True | True |
| conversation/utterances.jsonl | 1,751,373 | 1,751,373 | 1,732,912 | 18,461 | 18,461 | なし | True | True |
| even/conversation/utterances.jsonl | 514,199 | 514,199 | 509,952 | 4,247 | 4,247 | なし | True | True |
| general_qa/train/records.jsonl | 317,423 | 317,423 | 317,423 | 0 | 0 | なし | True | True |
| code_qa/train/records.jsonl | 324,639 | 324,639 | 324,639 | 0 | 0 | なし | True | True |
| figurative_commonsense/train/records.jsonl | 238,905 | 238,905 | 238,905 | 0 | 0 | なし | True | True |
| narrative/train/records.jsonl | 146,598 | 146,598 | 146,598 | 0 | 0 | なし | True | True |
| paraphrase_entail/train/records.jsonl | 379,580 | 379,580 | 379,574 | 6 | 6 | なし | True | True |
<!-- END table:r1_r2 -->

<!-- BEGIN table:r1_r2_timing -->
出典: `artifacts/w1-c/manifest.r1.json / build.r1.log と manifest.json / build.log`

|  | manifest の elapsed_seconds | /usr/bin/time の real(秒) | 開始 |
|---|---|---|---|
| r1(規則なし) | 75.976 | 76.02 | 2026-10-02T23:26:31+0900 |
| r2(規則あり) | 79.817 | 79.86 | 2026-10-03T00:15:27+0900 |
<!-- END table:r1_r2_timing -->

## 4. 出所と「生成物」の型

各索引行は `family`、`source_file`（root 相対）、`line`（1 始まりの物理行番号。`sed -n 'N p'` で取れる行）、
`sha`（レコードの sha）、`kind`、`fields`（本文に使った欄名）、`body_sha`、`origin`、`generator` を持つ。
行番号はバイナリで開いて `\n` だけで切って数える（`wc -l` と一致させるため）。

- `origin = "generated"`、`generator = "codex"`: **codex が生成した文であって、事実の証言ではない**。
  `Witness.cite()` は従来のキーを保ったまま `origin`, `generator`, `source_file`, `line` を足す。
- 戻り道は `source_file` + `line` を主にし、`sha` で照合する（レコードの `sha` は系列で桁が違い、一意の保証が無い）。

### 回答の最上位の出所種別 `basis_origin`（第 2 ラウンド、追補の決定 1）

- 規則（`ability_corpus.basis_origin(sources)` の 1 か所に定義）: 回答が引用する出典に `origin == "generated"` のものが 1 つでもあれば、
  回答の最上位に `basis_origin: "generated"` を付ける。1 つも無ければキー自体を付けない。値は文字列 `"generated"` だけ。
  `kind` / `verdict` / `text` / 既存のキーは変えない（追加のみ）。
- 付く場所: `abilities._reply()` の回答ありの分岐（commonsense・生成・理解・比喩・ユーモア・創作の各経路が共通で通る。出典は重複を除いた
  `sources`）と、`round3._conversation_supply` / `_code_supply` の戻り値。付かない場所: 棄権（出典が空）、`round3._social_frame` の定型回答、
  文書 QA、計算（skill）、一般知識の出典（`origin` を持たない）。
- 追補の決定 1 (a): `abilities.commonsense` の「〜例が複数あります」は、既存設計どおり **生成コーパス内の用例の報告であって事実の証言ではない**。
  `kind` / `verdict` と回答文は変えていない（既存テスト `tests/test_p4_abilities.py` の期待値は無変更）。
  「生成文だけを根拠にした回答を ANSWER にしない」（選択肢 (b)）はこのチケットでは行わない（§11）。
- `commonsense` 経路の trace に、先頭で `{"part": "ability_corpus.status", "ability": "commonsense", "family": <local|pro>, "index": <状態>}` を
  `local`、`pro` の順に 1 項目ずつ足した（commonsense が引く系列はこの 2 つ）。`verdict` キーは入れない（`_reply` の同点判定が trace の `verdict` を読むため）。
- 第 1 ラウンドから残した受け渡し: `abilities.generation` の trace 項目 `ability_corpus.search` に `index`、`round3` の会話供給・コード供給の trace に `index`。
  索引が `UNKNOWN_*` のときは会話供給の verdict 欄もその状態にする（`UNKNOWN_NO_STRICT_TURN` は索引が在って厳密一致が無かったときだけ）。
- 分岐・戻り値の既存キー・検索語・系列の選び方・回答文は変えていない。

### 既存コードの使い方（読んで確かめたこと）

`abilities.py` と `round3.py` はコーパスの文を「創作の材料」「社交の定型の裏づけ」「条件・性質の複数例の裏づけ」に使う。
W1-c ではこの使い方の意味を変えていない。コーパスを読むのは `Abilities` の各経路（`self.corpus`）と
`round3._conversation_supply` / `_code_supply` だけ。

## 5. 実データでの作成と照合（C1）

<!-- BEGIN table:files -->
出典: `artifacts/w1-c/manifest.json の files[]`

| 入力ファイル(root 相対) | 系列 | バイト数 | 行数 | sha256(先頭16桁) | 索引に入った行 | 読み飛ばし | split キー無し(索引行のうち) | 出所タグ想定外 |
|---|---|---|---|---|---|---|---|---|
| out/sentences.jsonl | pro | 304,983,990 | 1,366,290 | ecceb5343a782ec0 | 1,366,290 | なし | 1,366,290 | 0 |
| code/items.jsonl | code | 518,597,240 | 1,020,930 | feb260ef94df77de | 1,020,920 | heldout_body_overlap: 10 | 357,930 | 0 |
| even/code/items.jsonl | code | 199,871,186 | 384,279 | 40466f2bbb4bd0ac | 384,269 | heldout_body_overlap: 10 | 0 | 0 |
| conversation/utterances.jsonl | conversation | 760,707,818 | 1,751,373 | 5c591cbd9dff76c8 | 1,732,912 | heldout_body_overlap: 18461 | 316,897 | 0 |
| even/conversation/utterances.jsonl | conversation | 233,373,260 | 514,199 | e611efafc56f3eca | 509,952 | heldout_body_overlap: 4247 | 0 | 0 |
| general_qa/train/records.jsonl | general_qa | 234,192,716 | 317,423 | c7e85bd3441239be | 317,423 | なし | 0 | 0 |
| code_qa/train/records.jsonl | code_qa | 305,158,884 | 324,639 | 585ebfadf97f8528 | 324,639 | なし | 0 | 0 |
| figurative_commonsense/train/records.jsonl | figurative_commonsense | 127,829,754 | 238,905 | 1ce1851c92e9c9be | 238,905 | なし | 0 | 0 |
| narrative/train/records.jsonl | narrative | 92,963,878 | 146,598 | 4a2fbfb130fab93e | 146,598 | なし | 0 | 0 |
| paraphrase_entail/train/records.jsonl | paraphrase_entail | 176,935,921 | 379,580 | 76efded624774870 | 379,574 | heldout_body_overlap: 6 | 0 | 0 |
<!-- END table:files -->

<!-- BEGIN table:optional_absent -->
出典: `artifacts/w1-c/manifest.json の files[].optional_absent`

| 入力ファイル | 任意欄の欠落(索引行のうち、読み飛ばしではない) |
|---|---|
| general_qa/train/records.jsonl | fact.why: 4826, definition.why: 2112, greeting.why: 13258, needs_live_data.why: 28178, howto.why: 491, comparison.why: 248, advice.why: 270 |
| code_qa/train/records.jsonl | code_qa.usage: 8 |
<!-- END table:optional_absent -->

<!-- BEGIN table:families -->
出典: `artifacts/w1-c/manifest.json の families{}`

| 系列 | 状態 | 索引行数 | DB バイト数 | 系列ごとの所要秒 |
|---|---|---|---|---|
| pro | BUILT | 1,366,290 | 812,023,808 | 34.886 |
| code | BUILT | 1,405,189 | 1,443,852,288 | 78.586 |
| conversation | BUILT | 2,242,864 | 1,606,750,208 | 66.358 |
| general_qa | BUILT | 317,423 | 507,125,760 | 28.159 |
| code_qa | BUILT | 324,639 | 861,270,016 | 44.593 |
| figurative_commonsense | BUILT | 238,905 | 231,194,624 | 9.547 |
| narrative | BUILT | 146,598 | 181,018,624 | 9.048 |
| paraphrase_entail | BUILT | 379,574 | 340,123,648 | 12.55 |
<!-- END table:families -->

<!-- BEGIN table:timing -->
出典: `artifacts/w1-c/manifest.json と build.log(/usr/bin/time -l と終了コード)`

| 項目 | 値 |
|---|---|
| manifest の elapsed_seconds | 79.817 |
| /usr/bin/time の real(秒) | 79.86 |
| 終了コード | 0 |
| --jobs | 4 |
| git HEAD | 65f43dac02c8 |
| python | 3.11.14 |
| sqlite | 3.51.0 |
| 開始 | 2026-10-03T00:15:27+0900 |
| 終了 | 2026-10-03T00:16:47+0900 |
<!-- END table:timing -->

照合は builder の自己申告に頼らず、別のスクリプト `check_manifest.py` が入力ファイルを読み直して数え直した。
第 2 ラウンドでは heldout ファイル（`families{}.heldout.files[]`）の行数・sha256 も独立に数え直し、`excluded[]` の同じパスの値と比べている。

<!-- BEGIN table:check_manifest -->
出典: `artifacts/w1-c/check_manifest.json`

| 確認 | 結果 |
|---|---|
| 入力 10 ファイルの bytes / 行数 / sha256 の再計算が manifest と一致 | True |
| lines == indexed + 読み飛ばし(全ファイル) | True |
| wc -l / shasum による 2 ファイルの手計算が一致 | True |
| GROUP BY source_file が manifest の indexed と一致(8 DB) | True |
| heldout / overlap_dropped 由来の DB 行(8 DB の合計) | 0 |
| 無作為抽出した行の元行 sha 一致(系列あたり件数 / 全系列で一致) | 20 / True |
| 全体判定 all_ok | True |
<!-- END table:check_manifest -->

## 6. 検索の確認（C2）

語句は実行前に `c2_phrases.json` に固定した（乱数の種 `20261002`、選び方は同ファイルの `rule`）。第 2 ラウンドでもこのファイルは書き換えず、
`c2_select_phrases.py` は再実行していない（DB の行 id で選ぶため、索引を作り直すと別の語句が出て事前登録が壊れる）。
`c2_search.py` だけを、作り直した索引に対して再実行した。`Corpus.search` は公開 API のまま呼び、検索側を語句に合わせて変えていない。

**追補による C2 の改定**: 指定 8 語句のうち「Wi-Fiなし 携帯データ」と「脱水機の異音」は、監査報告の説明文を語句として写したもので、
生コーパスに存在しない。この 2 語句は **NO_MATCH であることの証拠つき報告で可** とする。残りの語句と自選語句の条件は変えない。
下の表で、この 2 語句の「満たした」が `False` なのは「FOUND の条件を満たさなかった」の意味で、NO_MATCH（索引は検索された）である。

<!-- BEGIN table:c2_ticket -->
出典: `artifacts/w1-c/c2_search.json の ticket[]`

| 語句 | 系列 | state | 件数(limit 1000) | 先頭ヒットの所在 | 元行の往復(sha・語句の包含) | 満たした |
|---|---|---|---|---|---|---|
| 冷えた頬をマフラー | pro | FOUND | 17 | out/sentences.jsonl:214792 | True | True |
| 湯気の中に青菜 | pro | FOUND | 1 | out/sentences.jsonl:113617 | True | True |
| 葉柄と葉身 | general_qa | FOUND | 3 | general_qa/train/records.jsonl:13569 | True | True |
| Wi-Fiなし 携帯データ | general_qa | NO_MATCH | 0 | — | — | False |
| strings.HasSuffix | code_qa | FOUND | 169 | code_qa/train/records.jsonl:171 | True | True |
| strings.HasSuffix | code | FOUND | 30 | code/items.jsonl:49896 | True | True |
| 重複部分文字列 | code_qa | FOUND | 1 | code_qa/train/records.jsonl:92858 | True | True |
| 重複部分文字列 | code | NO_MATCH | 0 | — | — | True |
| 脱水機の異音 | conversation | NO_MATCH | 0 | — | — | False |
| 改札を出て左 | conversation | FOUND | 436 | conversation/utterances.jsonl:2080 | True | True |
<!-- END table:c2_ticket -->

「Wi-Fiなし 携帯データ」と「脱水機の異音」は **索引には無く、生コーパスにも無い**。`NO_MATCH` として正直に返る
（索引の不在 `UNKNOWN_*` ではない）。再現手順（検索側は触らない）:

```
LC_ALL=C grep -rlF "携帯データ" <コーパスの根> --include='*.jsonl'      # 出力なし
python artifacts/w1-c/c2_search.py                                      # raw_corpus_absence_evidence に下の表
```

<!-- BEGIN table:c2_absence -->
出典: `artifacts/w1-c/c2_search.json の raw_corpus_absence_evidence`

| 確認(コーパスの全 *.jsonl を直接走査) | 結果 |
|---|---|
| 走査したファイル数 | 56 |
| 「携帯データ」を含む行 | 0 |
| 「Wi-Fiなし 携帯データ」を含む行 | 0 |
| 「脱水機」を含む行 | 22 |
| 「異音」を含む行 | 508 |
| 「脱水機の異音」を含む行 | 0 |
| 「脱水機」と「異音」が同一行にある行 | 0 |
| 同一 dialogue_id に両方がある dialogue 数(会話 6 ファイル合計) | 0 |
<!-- END table:c2_absence -->

自選語句（系列ごと）と陰性対照（heldout にだけ在って train に無い語句。`pro` は heldout が無いので対照なし）:

<!-- BEGIN table:c2_self -->
出典: `artifacts/w1-c/c2_search.json の self_chosen[] と negative_controls[]`

| 系列 | 自選語句 満たした件数 / 件数 | 陰性対照(heldout にだけ在る語句)の state |
|---|---|---|
| pro | 5 / 5 | UNKNOWN_NO_HELDOUT_FOR_FAMILY |
| code | 5 / 5 | NO_MATCH |
| conversation | 5 / 5 | NO_MATCH |
| general_qa | 5 / 5 | NO_MATCH |
| code_qa | 5 / 5 | NO_MATCH |
| figurative_commonsense | 5 / 5 | NO_MATCH |
| narrative | 5 / 5 | NO_MATCH |
| paraphrase_entail | 5 / 5 | NO_MATCH |
<!-- END table:c2_self -->

## 7. heldout が索引に無いことの確認（C4）

### 7.1 無作為抽出（`c4_heldout_check.py`、種 `20261002`、200 件）

heldout 全ファイルの行から一様に無作為抽出。本文は builder と同じ `extract_body` で作り、
(a) 同系列 DB に同じ本文があるか、(b) 欄の文字列が索引行に逐語で含まれるかを見た。
第 1 ラウンドの索引（r1、規則なし）と第 2 ラウンド（r2、規則あり）を並べる。

<!-- BEGIN table:c4_r1_r2 -->
出典: `artifacts/w1-c/c4_heldout_check.r1.json と c4_heldout_check.json`

| 項目 | r1(規則なし) | r2(規則あり) |
|---|---|---|
| seed | 20261002 | 20261002 |
| sampled | 200 | 200 |
| population | 491106 | 491106 |
| body_sha_hits | 6 | 0 |
| field_substring_hits | 26 | 23 |
| records_with_every_field_in_same_family | 6 | 3 |
<!-- END table:c4_r1_r2 -->

<!-- BEGIN table:c4 -->
出典: `artifacts/w1-c/c4_heldout_check.json`

| 項目 | 値 |
|---|---|
| 乱数の種 | 20261002 |
| 抽出件数 | 200 |
| 母集団(heldout 全ファイルの行数) | 491,106 |
| out/ に heldout があるか | False |
| 系列別の抽出件数 | pro: 0, code: 47, conversation: 88, general_qa: 15, code_qa: 12, figurative_commonsense: 8, narrative: 7, paraphrase_entail: 23 |
| 抽出できなかったレコード | なし |
| (a) 本文の sha が同系列 DB に在る件数 | 0 |
| (b) いずれかの欄の文字列が索引行に逐語で在るレコード数 | 23 |
| (b) うち全欄が同系列に在るレコード数 | 3 |
<!-- END table:c4 -->

r1 で (a) に該当した heldout レコード（規則を入れる前の観察）と、r2 で該当するもの:

<!-- BEGIN table:c4_body_hits -->
出典: `artifacts/w1-c/c4_heldout_check.json の body_sha_hit_records[] と c4_heldout_check.r1.json の body_sha_hit_records[](索引 r1 での該当)`

| 索引 | heldout の所在 | 系列 | 本文の文字数 | 同じ本文の索引行数 | 一致した索引行(先頭) |
|---|---|---|---|---|---|
| r1(heldout 除外の規則なし) | conversation/heldout/utterances.jsonl:109886 | conversation | 9 | 1 | conversation/utterances.jsonl:970946 |
| r1(heldout 除外の規則なし) | conversation/heldout/utterances.jsonl:125032 | conversation | 24 | 1 | conversation/utterances.jsonl:1593095 |
| r1(heldout 除外の規則なし) | conversation/heldout/utterances.jsonl:128739 | conversation | 11 | 1 | conversation/utterances.jsonl:1502324 |
| r1(heldout 除外の規則なし) | conversation/heldout/utterances.jsonl:132233 | conversation | 7 | 6 | conversation/utterances.jsonl:536058 |
| r1(heldout 除外の規則なし) | even/conversation/heldout/utterances.jsonl:16383 | conversation | 11 | 1 | conversation/utterances.jsonl:931596 |
| r1(heldout 除外の規則なし) | even/conversation/heldout/utterances.jsonl:31687 | conversation | 17 | 1 | conversation/utterances.jsonl:1438655 |
<!-- END table:c4_body_hits -->

(b) は「欄の文字列が、索引のどこかの行の本文の一部として含まれる」ことで、**本文全体の一致ではない**。r2 でも残る。
短い題名・短い答え・短い発話が別の行の中に現れるだけのもので、規則（本文全体の一致の除外）の対象ではない。
該当したレコード（全件。各欄の文字数つき）:

<!-- BEGIN table:c4_field_hits -->
出典: `artifacts/w1-c/c4_heldout_check.json の field_substring_hit_records[](欄の文字数つき)`

| heldout の所在 | kind | 索引行に逐語で在った欄(欄名:文字数) | 欄の総数 |
|---|---|---|---|
| conversation/heldout/utterances.jsonl:128739 | conversation | text:11 | 1 |
| conversation/heldout/utterances.jsonl:132233 | conversation | text:7 | 1 |
| even/conversation/heldout/utterances.jsonl:16383 | conversation | text:11 | 1 |
| general_qa/heldout/records.jsonl:1916 | greeting | q_variants:26 | 4 |
| general_qa/heldout/records.jsonl:30578 | howto | q_variants:29 | 5 |
| code_qa/heldout/records.jsonl:8074 | code_qa | code:112, usage:8 | 4 |
| code_qa/heldout/records.jsonl:15391 | code_qa | usage:21 | 4 |
| figurative_commonsense/heldout/records.jsonl:878 | cause_effect | effect:12 | 4 |
| figurative_commonsense/heldout/records.jsonl:18951 | cause_effect | cause:6 | 4 |
| figurative_commonsense/heldout/records.jsonl:19863 | simile_metaphor | expression:9 | 3 |
| narrative/heldout/records.jsonl:3897 | story | title:6 | 5 |
| narrative/heldout/records.jsonl:5855 | story | title:5 | 5 |
| narrative/heldout/records.jsonl:6343 | poem | title:4, lines:11 | 5 |
| narrative/heldout/records.jsonl:16885 | poem | title:2 | 5 |
| paraphrase_entail/heldout/records.jsonl:4763 | who_did_what | question:9, answer:2 | 3 |
| paraphrase_entail/heldout/records.jsonl:9218 | who_did_what | answer:2 | 3 |
| paraphrase_entail/heldout/records.jsonl:9734 | pair | s1:11 | 3 |
| paraphrase_entail/heldout/records.jsonl:11982 | who_did_what | answer:3 | 3 |
| paraphrase_entail/heldout/records.jsonl:19434 | who_did_what | answer:5 | 3 |
| paraphrase_entail/heldout/records.jsonl:19947 | who_did_what | answer:3 | 3 |
| paraphrase_entail/heldout/records.jsonl:20253 | who_did_what | answer:2 | 3 |
| paraphrase_entail/heldout/records.jsonl:21726 | who_did_what | question:8, answer:2 | 3 |
| paraphrase_entail/heldout/records.jsonl:34327 | pair | s1:24, s2:16 | 3 |
<!-- END table:c4_field_hits -->

### 7.2 heldout 全件（追補: 抜き取りではなく全件、`c4_heldout_full.py`）

- heldout ファイルの一覧は **コーパスを走査して** 作り、builder の `HELDOUT` と検算側の `_common.HELDOUT` の両方と集合として一致することを確かめた。
- heldout の全行を、builder と同じ `extract_body` で本文にして sha256 を取り、同系列の DB の `body_sha` と突き合わせた（(a)）。
  他系列の DB との一致は情報として数えた（(a')）。系列をまたいだ一致は規則の対象ではない。
- 独立の数え直し: train の各ファイルを `classify_line` で読み直し、規則なしなら索引に入る行のうち、本文が同系列の heldout の集合にあるものを数え、
  manifest の `heldout_body_overlap` とファイルごとに比べた。

<!-- BEGIN table:c4_full -->
出典: `artifacts/w1-c/c4_heldout_full.json の by_family[]`

| 系列 | heldout 行数 | 本文を取り出せた行 | 異なる本文数 | (a) 同系列 DB の同じ本文の行数 | (a') 他系列 DB の同じ本文の行数(合計) |
|---|---|---|---|---|---|
| pro | 0 | 0 | 0 | 0 | 0 |
| code | 116,316 | 116,316 | 116,316 | 0 | 0 |
| conversation | 219,285 | 219,285 | 217,865 | 0 | 1 |
| general_qa | 34,171 | 34,171 | 34,171 | 0 | 0 |
| code_qa | 34,523 | 34,523 | 34,523 | 0 | 0 |
| figurative_commonsense | 25,074 | 25,074 | 25,074 | 0 | 0 |
| narrative | 18,193 | 18,193 | 18,193 | 0 | 0 |
| paraphrase_entail | 43,544 | 43,544 | 43,544 | 0 | 0 |
<!-- END table:c4_full -->

<!-- BEGIN table:c4_full_other -->
出典: `artifacts/w1-c/c4_heldout_full.json の by_family[].other_family_examples[]`

| heldout の系列 | 同じ本文があった他系列 DB | その行 | 本文の先頭 |
|---|---|---|---|
| conversation | pro | out/sentences.jsonl:327747 | おやすみなさい。 |
<!-- END table:c4_full_other -->

<!-- BEGIN table:c4_full_rule -->
出典: `artifacts/w1-c/c4_heldout_full.json の rule_recount[]`

| 入力ファイル | 規則なしなら索引に入る行 | 同系列 heldout と本文が同じ行(数え直し) | manifest の heldout_body_overlap | 指示書の予測値 | 数え直し = manifest | manifest = 予測値 | 規則なし - 重なり = 索引行 |
|---|---|---|---|---|---|---|---|
| out/sentences.jsonl | 1,366,290 | 0 | 0 | 0 | True | True | True |
| code/items.jsonl | 1,020,930 | 10 | 10 | 10 | True | True | True |
| even/code/items.jsonl | 384,279 | 10 | 10 | 10 | True | True | True |
| conversation/utterances.jsonl | 1,751,373 | 18,461 | 18,461 | 18,461 | True | True | True |
| even/conversation/utterances.jsonl | 514,199 | 4,247 | 4,247 | 4,247 | True | True | True |
| general_qa/train/records.jsonl | 317,423 | 0 | 0 | 0 | True | True | True |
| code_qa/train/records.jsonl | 324,639 | 0 | 0 | 0 | True | True | True |
| figurative_commonsense/train/records.jsonl | 238,905 | 0 | 0 | 0 | True | True | True |
| narrative/train/records.jsonl | 146,598 | 0 | 0 | 0 | True | True | True |
| paraphrase_entail/train/records.jsonl | 379,580 | 6 | 6 | 6 | True | True | True |
<!-- END table:c4_full_rule -->

<!-- BEGIN table:c4_full_checks -->
出典: `artifacts/w1-c/c4_heldout_full.json`

| 確認 | 結果 |
|---|---|
| コーパスを走査して見つけた heldout ファイル数 | 9 |
| 走査結果 = builder の HELDOUT 表 | True |
| 走査結果 = 検算側 _common.HELDOUT | True |
| out/ に heldout があるか | False |
| 合格: 全系列で同系列 DB に同じ本文の行が 0 | True |
| 合格: 規則の数え直し = manifest(全ファイル) | True |
| 所要秒 | 41.375 |
<!-- END table:c4_full_checks -->

事実として: DB 行のうち `source_file` に heldout / overlap_dropped を含むものは 0（C1 の表）。heldout ファイルは索引の入力として読んでいない
（`heldout_bodies` が本文の hash だけを取り出す）。

## 8. 既定の入口からの利用（C5'）

追補の改定後の基準（C5'）: (i) 既定の入口からコーパス経路に実際に届く質問を実行前に登録する（commonsense・生成・会話の各経路で 3 問以上、
計 10 問以上。登録ファイルの時刻が結果より前）、(ii) 届いた回答はすべて最上位に `basis_origin: "generated"` を持つ、
(iii) 根拠がコーパスでない回答を 5 問以上流し、その型が付かないことを確かめる、(iv) 索引を設定しない既定状態では (i) の質問がどれもコーパスを使わず
「索引なし」が trace に現れる。

登録は `c5r2_probes.json`（実行前、コードを変える前に作成。候補は中間職が索引 r1 で「`origin: generated` の出典が付くか」だけを走査して指示書に載せたもの。
`basis_origin` の実装前なので (ii) の結果は知り得ない）。判定は `c5r2_entry_probe.py` が機械的に出す。入口は 3 つ:
`cli_default`（サブプロセス `python -m verantyx.cli ask`）、`api_legacy`（新しいサブプロセスで `Vera(mode="legacy").ask`）、
`api_legacy_docs`（同じく文書を読ませてから ask）。状態は 2 つ: `with_index`（`VERA_P4_INDEX` を実索引に）と `default`
（子プロセスの環境から `VERA_P4_INDEX` と `VERA_W1C_INDEX` を **取り除く**。存在しないディレクトリを指すのではない）。

<!-- BEGIN table:c5r2_registration -->
出典: `artifacts/w1-c/c5r2_entry_probe.json の summary.registration と summary.environment_check`

| 項目 | 値 |
|---|---|
| 登録ファイル | artifacts/w1-c/c5r2_probes.json |
| 登録ファイルの sha256 | 4bf772a42902927896670d1a1d134bb0c2e0b5424f7ca5215f630b242f54d1f5 |
| 登録ファイルの作成時刻 | 2026-10-03T00:12:43 |
| 登録ファイルの更新時刻 | 2026-10-03T00:12:43 |
| 実行開始時刻 | 2026-10-03T00:18:54 |
| 登録が実行開始より前 | True |
| 事後の追加登録ファイル | なし |
| 実行数(サブプロセス) | 127 |
| 全実行が JSON を返した | True |
| 作業ツリーに build/p4 が在る | False |
| 既定状態の子プロセス環境に VERA_P4_INDEX が在る | False |
| 既定状態の子プロセス環境に VERA_W1C_INDEX が在る | False |
<!-- END table:c5r2_registration -->

<!-- BEGIN table:c5r2_groups -->
出典: `artifacts/w1-c/c5r2_entry_probe.json の summary.by_group`

| 群 | 登録した質問数 | 到達(reached)した異なる質問数 | 到達した質問 |
|---|---|---|---|
| commonsense | 11 | 7 | 富士山の高さは？ / 鍋に水を入れて火にかけると、どうなりますか？ / ドアを開けると、どうなりますか？ / 電気を消すと、どうなりますか？ / コーヒーをこぼすと、どうなりますか？ / お湯を注ぐと、どうなりますか？ / カーテンを開けると、どうなりますか？ |
| generation | 15 | 11 | 湯気の中の朝の台所の様子を一文で描写してください。 / 海辺の様子を一文で描写してください。 / 台所の様子を一文で描写してください。 / 駅のホームの様子を一文で描写してください。 / 雨の日の窓の様子を一文で描写してください。 / 夜の街の様子を一文で描写してください。 / 公園の様子を一文で描写してください。 / 教室の様子を一文で描写してください。 / 森の様子を一文で描写してください。 / 川辺の様子を一文で描写してください。 / 商店街の様子を一文で描写してください。 |
| conversation | 4 | 0 | なし |
<!-- END table:c5r2_groups -->

<!-- BEGIN table:c5r2_judgement -->
出典: `artifacts/w1-c/c5r2_entry_probe.json の summary`

| 判定 | 結果 | 内訳 |
|---|---|---|
| (i) 各群 3 問以上・合計 10 問以上が到達 | False | 到達した異なる質問の合計 18 |
| (ii) 到達かつ回答の実行はすべて basis_origin が generated。全実行で「在る ⇔ generated 出典が在る」 | True | 不変条件の違反 0 / (ii) の違反 0 / 到達かつ回答なのに generated 出典が無い実行 0 |
| (iii) 根拠がコーパスでない回答 5 問以上で型が付かない | True | 満たした問 7 |
| (iv) 到達した各(質問, 入口)の既定状態でコーパス不使用・「索引なし」が trace に出る | True | 検査した(質問, 入口) 36 / 満たさなかった 0 |
<!-- END table:c5r2_judgement -->

### 8.1 会話経路: 不成立（前提の衝突）

**C5'(i) 会話経路: 不成立。R1 で唯一の供給文「どういたしまして。」が heldout と同一本文として全件除外されたため。**
表 `c5r2_groups` の会話群は、登録した問のうち到達した問が無い。社交の定型文ごとの数字は次の表（`c5r2_conversation_supply.py`）。
`Corpus.search(..., limit=60)`・`_norm` の完全一致・逐語 `LIKE` は変えていない。

<!-- BEGIN table:conv_supply -->
出典: `artifacts/w1-c/c5r2_conversation_supply.json の rows[]`

| 社交の定型文(round3._social_frame) | LIKE の件数 | _norm 完全一致の総数 | 先頭 60 件の窓の中の一致(Corpus.search limit=60) | 規則で除外された train 行 | 索引に残った train 行 | 供給に届く |
|---|---|---|---|---|---|---|
| こんにちは。 | 4,334 | 0 | 0 | 0 | 0 | False |
| どういたしまして。 | 7,862 | 4 | 0 | 110 | 4 | False |
| お話を聞きます。 | 3 | 0 | 0 | 0 | 0 | False |
| また、お話ししましょう。 | 0 | 0 | 0 | 0 | 0 | False |
| 気持ちを聞かせてください。 | 1 | 0 | 0 | 0 | 0 | False |
| おはようございます。 | 24,561 | 0 | 0 | 0 | 0 | False |
| こんばんは。 | 6,434 | 0 | 0 | 0 | 0 | False |
| はじめまして。 | 8 | 0 | 0 | 0 | 0 | False |
<!-- END table:conv_supply -->

登録した会話の問は、索引あり・なしの両方で、社交の定型枠から同じ文が返る（表 `c5r2_runs`。コーパス出典なし）。
合成データでは、会話索引に「どういたしまして。」の行があれば会話供給が `basis_origin: "generated"` を付けることを
`tests/test_corpus_index_basis.py`（B4）で確かめている。

### 8.2 実行ごとの結果

<!-- BEGIN table:c5r2_runs -->
出典: `artifacts/w1-c/c5r2_entry_probe.json の reached[] と runs[]`

| 群 | 入口 | 質問 | 索引あり: kind / verdict | generated 出典数 | basis_origin | 旗1: generated 出典が在る | 旗2: 既定状態と結果が違う | 到達 | 既定状態: kind / verdict | 既定状態の trace の索引の状態 | 既定状態の generated 出典数 | 既定状態の basis_origin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| commonsense | cli_default | 富士山の高さは？ | answer / ANSWER | 12 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | 富士山の高さは？ | answer / ANSWER | 12 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | 鍋に水を入れて火にかけると、どうなりますか？ | answer / ANSWER | 6 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | 鍋に水を入れて火にかけると、どうなりますか？ | answer / ANSWER | 6 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | 氷を日なたに置くと、どうなりますか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | 氷を日なたに置くと、どうなりますか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | ドアを開けると、どうなりますか？ | answer / ANSWER | 6 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | ドアを開けると、どうなりますか？ | answer / ANSWER | 6 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | 電気を消すと、どうなりますか？ | answer / ANSWER | 6 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | 電気を消すと、どうなりますか？ | answer / ANSWER | 6 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | コーヒーをこぼすと、どうなりますか？ | answer / ANSWER | 4 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | コーヒーをこぼすと、どうなりますか？ | answer / ANSWER | 4 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | お湯を注ぐと、どうなりますか？ | unknown / TIED_ABSTAIN | 0 | なし | False | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | お湯を注ぐと、どうなりますか？ | unknown / TIED_ABSTAIN | 0 | なし | False | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | カーテンを開けると、どうなりますか？ | answer / ANSWER | 6 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | カーテンを開けると、どうなりますか？ | answer / ANSWER | 6 | generated | True | True | True | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | 雨が降り出したら、何をするのがよいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | 雨が降り出したら、何をするのがよいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | 部屋が暗くなったら、何をするのがよいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | 部屋が暗くなったら、何をするのがよいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | cli_default | 水の沸点は何度ですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| commonsense | api_legacy | 水の沸点は何度ですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 湯気の中の朝の台所の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 湯気の中の朝の台所の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 海辺の様子を一文で描写してください。 | compose / CREATED | 4 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 海辺の様子を一文で描写してください。 | compose / CREATED | 4 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 台所の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 台所の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 駅のホームの様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 駅のホームの様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 雨の日の窓の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 雨の日の窓の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 冬の朝の様子を一文で描写してください。 | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 冬の朝の様子を一文で描写してください。 | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 夜の街の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 夜の街の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 公園の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 公園の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 教室の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 教室の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 森の様子を一文で描写してください。 | compose / CREATED | 4 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 森の様子を一文で描写してください。 | compose / CREATED | 4 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 川辺の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 川辺の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 商店街の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 商店街の様子を一文で描写してください。 | compose / CREATED | 2 | generated | True | True | True | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 雨上がりの公園の様子を一文で描写してください。 | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 雨上がりの公園の様子を一文で描写してください。 | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 夕暮れの商店街の様子を一文で描写してください。 | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 夕暮れの商店街の様子を一文で描写してください。 | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | cli_default | 冬の朝の駅の様子を一文で描写してください。 | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| generation | api_legacy | 冬の朝の駅の様子を一文で描写してください。 | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 0 | なし | False | False | False | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | UNKNOWN_NO_INDEX | 0 | なし |
| conversation | api_legacy | ありがとう。 | social / ANSWER | 0 | なし | False | False | False | social / ANSWER | UNKNOWN_NO_INDEX | 0 | なし |
| conversation | cli_default | ありがとう。 | social / None | 0 | なし | False | False | False | social / None | — | 0 | なし |
| conversation | api_legacy | ありがとうございます。 | social / ANSWER | 0 | なし | False | False | False | social / ANSWER | UNKNOWN_NO_INDEX | 0 | なし |
| conversation | cli_default | ありがとうございます。 | social / None | 0 | なし | False | False | False | social / None | — | 0 | なし |
| conversation | api_legacy | どうもありがとう。 | social / ANSWER | 0 | なし | False | False | False | social / ANSWER | UNKNOWN_NO_INDEX | 0 | なし |
| conversation | cli_default | どうもありがとう。 | social / None | 0 | なし | False | False | False | social / None | — | 0 | なし |
| conversation | api_legacy | ありがとうございました。 | social / ANSWER | 0 | なし | False | False | False | social / ANSWER | UNKNOWN_NO_INDEX | 0 | なし |
| conversation | cli_default | ありがとうございました。 | social / None | 0 | なし | False | False | False | social / None | — | 0 | なし |
<!-- END table:c5r2_runs -->

<!-- BEGIN table:c5r2_noncorpus -->
出典: `artifacts/w1-c/c5r2_entry_probe.json の summary.iii_rows`

| 入口 | 質問 | kind | ability | door | 回答した | generated 出典数 | basis_origin が在る | 満たした |
|---|---|---|---|---|---|---|---|---|
| cli_default | 3+4は？ | skill | — | skill | True | 0 | False | True |
| api_legacy | こんにちは。 | social | — | round3 | True | 0 | False | True |
| api_legacy | おはよう。 | social | — | round3 | True | 0 | False | True |
| api_legacy | 疲れた。 | social | — | round3 | True | 0 | False | True |
| api_legacy | ごめんなさい。 | social | — | round3 | True | 0 | False | True |
| api_legacy_docs | 議長は誰ですか？ | answer | — | document | True | 0 | False | True |
| api_legacy_docs | 会議は何曜日に開かれますか？ | answer | — | document | True | 0 | False | True |
<!-- END table:c5r2_noncorpus -->

- (ii): reached かつ answered の実行はすべて `basis_origin: "generated"` を持ち、全実行で「`basis_origin` が在る ⇔ generated 出典が在る」が成り立つ
  （表 `c5r2_judgement` の違反数）。
- (iii): 根拠がコーパスでない回答は `3+4は？`（skill）、社交の定型枠（`round3`）、文書 QA（`door: document`）で、いずれも `basis_origin` を持たない。
- (iv): 既定状態で commonsense・生成・会話の trace に `UNKNOWN_NO_INDEX` が現れる。commonsense は第 2 ラウンドで trace に索引の状態を載せたので、
  第 1 ラウンドでは出なかった `ability_corpus.status` が現れる。
- 観察（直していない）: `どうもありがとう。` は索引の有無によらず社交枠が `こんにちは。` を返す（表 `c5r2_runs`）。範囲外。

### 8.3 第 1 ラウンド・旧 C5・索引 r1 の記録（凍結。書き換えていない）

以下は第 1 ラウンドの記録で、索引 r1（heldout 除外の規則なし）と `basis_origin` 実装前のコードで取ったもの。`c5_probes.json`・`c5_entry_probe.py`・
`c5_entry_probe.json`・`c5_entry_probe.first_run.json` は第 2 ラウンドで再実行していない。「索引なし」は存在しないディレクトリを指す方式だった。

試験した入口: `python -m verantyx.cli ask <文>`（既定の chat の戸）、公開 API `verantyx.one.Vera(mode="legacy").ask`、
情報として `ask --mode round5`。

<!-- BEGIN table:c5_positive -->
出典: `artifacts/w1-c/c5_entry_probe.json の positive[]（第1ラウンド・旧 C5・索引 r1。凍結）`

| id | 入口 | 発話 | 索引あり: kind / verdict | 索引の状態(索引あり) | 索引の状態(索引なし) | 索引なしの結果 | 出所種別 generated の出典数(索引あり) | 判定 |
|---|---|---|---|---|---|---|---|---|
| P1 | cli_default | 湯気の中の朝の台所の様子を一文で描写してください。 | compose / CREATED | INDEX_AVAILABLE | UNKNOWN_NO_INDEX | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | 2 | True |
| P2 | api_legacy | ありがとう。 | social / ANSWER | INDEX_AVAILABLE | UNKNOWN_NO_INDEX | social / ANSWER | 3 | True |
| P3_info | cli_round5 | ありがとう。 | unknown / UNKNOWN_UNREAD | — | — | unknown / UNKNOWN_UNREAD | 0 | 情報のみ |
<!-- END table:c5_positive -->

反例探し。事前登録した質問（N 系）は `c5_probes.json` の `counterexample_search`、
最初の実行（`c5_entry_probe.first_run.json`）で、どの質問もコーパス経路に届かず索引の有無で結果が同じだったため、
手で試した 10 問を事後に追加した（A 系。事前登録ではない）。

<!-- BEGIN table:c5_counter -->
出典: `artifacts/w1-c/c5_entry_probe.json の counterexample_search[] と counterexample_search_added[]（第1ラウンド・旧 C5・索引 r1。凍結）`

| id | 登録 | 入口 | 質問 | 索引あり: kind / verdict | 回答した | generated 出典数 | 索引なしと同一結果 | 反例 |
|---|---|---|---|---|---|---|---|---|
| N1 | 事前登録 | cli_default | 『吾輩は猫である』の作者は誰ですか？ | answer / ANSWER | True | 0 | True | False |
| N1 | 事前登録 | api_legacy | 『吾輩は猫である』の作者は誰ですか？ | answer / ANSWER | True | 0 | True | False |
| N2 | 事前登録 | cli_default | あんずはどんな果物ですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| N2 | 事前登録 | api_legacy | あんずはどんな果物ですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| N3 | 事前登録 | cli_default | 『吾輩は猫である』の語り手は何ですか。 | answer / ANSWER | True | 0 | True | False |
| N3 | 事前登録 | api_legacy | 『吾輩は猫である』の語り手は何ですか。 | answer / ANSWER | True | 0 | True | False |
| N4 | 事前登録 | cli_default | 水切れした鉢植えに水を与えると、どうなりますか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| N4 | 事前登録 | api_legacy | 水切れした鉢植えに水を与えると、どうなりますか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| N5 | 事前登録 | cli_default | 猫は小さいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| N5 | 事前登録 | api_legacy | 猫は小さいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| N6 | 事前登録 | cli_default | 「彼女は花のようだった」とはどういう意味ですか？ | unknown / UNKNOWN_METAPHOR_NO_STRUCTURE | False | 0 | True | False |
| N6 | 事前登録 | api_legacy | 「彼女は花のようだった」とはどういう意味ですか？ | unknown / UNKNOWN_METAPHOR_NO_STRUCTURE | False | 0 | True | False |
| N7 | 事前登録 | cli_default | strings.HasSuffix は何をする関数ですか？ | unknown / UNKNOWN_CODE_SPEC | False | 0 | True | False |
| N7 | 事前登録 | api_legacy | strings.HasSuffix は何をする関数ですか？ | unknown / UNKNOWN_CODE_SPEC | False | 0 | True | False |
| N8 | 事前登録 | cli_default | あんこは何から作られますか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| N8 | 事前登録 | api_legacy | あんこは何から作られますか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| A1 | 事後に追加 | cli_default | 毛布を敷いてやると、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A1 | 事後に追加 | api_legacy | 毛布を敷いてやると、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A2 | 事後に追加 | cli_default | 水を与えると、どうなりますか？ | unknown / TIED_ABSTAIN | False | 0 | False | False |
| A2 | 事後に追加 | api_legacy | 水を与えると、どうなりますか？ | unknown / TIED_ABSTAIN | False | 0 | False | False |
| A3 | 事後に追加 | cli_default | 窓を開けると、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A3 | 事後に追加 | api_legacy | 窓を開けると、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A4 | 事後に追加 | cli_default | 傘を差すと、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A4 | 事後に追加 | api_legacy | 傘を差すと、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A5 | 事後に追加 | cli_default | 朝ごはんを食べると、どうなりますか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| A5 | 事後に追加 | api_legacy | 朝ごはんを食べると、どうなりますか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| A6 | 事後に追加 | cli_default | パンを焼くと、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A6 | 事後に追加 | api_legacy | パンを焼くと、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A7 | 事後に追加 | cli_default | 手を洗うと、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A7 | 事後に追加 | api_legacy | 手を洗うと、どうなりますか？ | answer / ANSWER | True | 6 | False | True |
| A8 | 事後に追加 | cli_default | 猫は小さいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| A8 | 事後に追加 | api_legacy | 猫は小さいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| A9 | 事後に追加 | cli_default | 犬は大きいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| A9 | 事後に追加 | api_legacy | 犬は大きいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| A10 | 事後に追加 | cli_default | 窓は明るいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
| A10 | 事後に追加 | api_legacy | 窓は明るいですか？ | unknown / UNKNOWN_COMMONSENSE_NO_STRUCTURE | False | 0 | True | False |
<!-- END table:c5_counter -->

<!-- BEGIN table:c5_summary -->
出典: `artifacts/w1-c/c5_entry_probe.json の summary（第1ラウンド・旧 C5・索引 r1。凍結）`

| 項目 | 値 |
|---|---|
| 実行数(質問 x 入口) | 36 |
| 反例(回答かつ generated 出典あり)の実行 | A1/cli_default, A1/api_legacy, A3/cli_default, A3/api_legacy, A4/cli_default, A4/api_legacy, A6/cli_default, A6/api_legacy, A7/cli_default, A7/api_legacy |
| うち事前登録の質問での反例 | なし |
| うち事後に追加した質問での反例 | A1/cli_default, A1/api_legacy, A3/cli_default, A3/api_legacy, A4/cli_default, A4/api_legacy, A6/cli_default, A6/api_legacy, A7/cli_default, A7/api_legacy |
| 索引の有無で結果が同一だった実行数 | 24 |
| コーパス経路が trace に現れた反例探しの実行数 | 0 |
<!-- END table:c5_summary -->

旧 C5 の「事実質問への回答の根拠としてコーパスの文が使われないこと」は、追補の決定 1 により C5' に置き換わった（A 系の反例は
`abilities._condition_examples` が生成文を出典に `answer` を返すもので、決定 1 (a) のもとでは `basis_origin: "generated"` が付けば可）。

## 9. 台帳の照合（`even/code` と `even/conversation`）

コーパス側は変更していない（読み取りのみ）。分かった事実だけを書く。原因は調べていない。第 2 ラウンドでは再実行していない
（コーパスだけを読むので出力は変わらない）。

<!-- BEGIN table:ledger -->
出典: `artifacts/w1-c/ledger_reconcile.json`

| ディレクトリ | 台帳の行数 | KEPT の kept 合計 | 台帳のバッチ接頭辞別行数 | items 系ファイルの行数(train+heldout+overlap_dropped) | 台帳にあり items に無いバッチ数 / その kept 合計 | items にあり台帳に無いバッチ数 | 両方に在るバッチ数 | 両方に在るバッチで kept と train+heldout 行数が違うバッチ数 |
|---|---|---|---|---|---|---|---|---|
| code | 7,599 | 1,094,572 | pro-code: 7599 | 1,094,829 | 1 / 0 | 0 | 7,199 | 0 |
| even/code | 7,577 | 1,074,560 | local-code: 4485, pro-code: 3092 | 427,121 | 4,569 / 647,607 | 0 | 2,992 | 0 |
| conversation | 20,135 | 1,911,049 | pro-conv: 20135 | 1,913,116 | 0 / 0 | 0 | 19,968 | 0 |
| even/conversation | 20,437 | 1,892,114 | local-conv: 14330, pro-conv: 6107 | 589,761 | 14,330 / 1,318,306 | 0 | 6,103 | 0 |
<!-- END table:ledger -->

<!-- BEGIN table:ledger_prefix -->
出典: `artifacts/w1-c/ledger_reconcile.json の ledger_batches_not_in_any_item_file.by_prefix`

| ディレクトリ | 台帳にあり items に無いバッチの接頭辞別数 | その台帳行の verdict 別 |
|---|---|---|
| code | pro-code: 1 | REJECTED: 3 |
| even/code | local-code: 4485, pro-code: 84 | KEPT: 4124, REJECTED: 447 |
| conversation | なし | なし |
| even/conversation | local-conv: 14330 | KEPT: 13865, REJECTED: 465 |
<!-- END table:ledger_prefix -->

- どのディレクトリでも、両方に在るバッチでは、台帳の `kept` と、items 系の train と heldout の行数の合計がバッチごとに一致した
  （表の最後の列が 0）。overlap_dropped の行は `kept` に入っていない。
- `even/code` と `even/conversation` の台帳には、バッチ名の接頭辞が `local-code` / `local-conv` の行があり、
  それらのバッチ名は train・heldout・overlap_dropped のどの items 系ファイルにも現れない。接頭辞 `pro-` のバッチは対応がつく。
- `code` と `conversation`（`even/` でない側）では、台帳にあり items に無いバッチの数は表のとおり。

## 10. テスト

<!-- BEGIN table:tests -->
出典: `artifacts/w1-c/tests_after_summary.txt / tests_after_failures.txt / baseline_failures.txt`

| 項目 | 値 |
|---|---|
| 全体テストの最終行 | 156 failed, 3684 passed, 26 skipped, 82 xfailed, 68 xpassed, 1 error, 37 subtests passed in 20.56s |
| ベースラインの失敗+エラー ID 数 | 157 |
| 変更後の失敗+エラー ID 数 | 157 |
| 変更後に新しく失敗した ID 数(ベースラインに無いもの) | 0 |
| ベースラインにあり変更後に無い ID 数 | 0 |
<!-- END table:tests -->

- 合成データの単体テスト（C6）:
  - `tests/test_corpus_index.py`（8 系列、heldout・overlap_dropped の除外、系列が混ざらないこと、読み飛ばし理由別件数の完全一致、
    型付き状態、旧 `build()` 互換、trace への受け渡し。第 1 ラウンドから無変更）。
  - `tests/test_corpus_index_heldout.py`（H 系: heldout と同じ本文の除外、系列をまたがないこと、抽出できない heldout 行の理由別件数、
    `UNKNOWN_HELDOUT_MISSING`、`heldout_unlisted`、判定順、`heldout_bodies` が hash だけを返すこと、旧 `build()` が heldout を見ないこと）。
  - `tests/test_corpus_index_basis.py`（B 系: commonsense・生成・理解・会話供給・コード供給の `basis_origin`、索引なしの commonsense の trace、
    `basis_origin()` の規則）。
- 実データ依存: `tests/test_corpus_index_real.py`。`VERA_CODEX_CORPUS` と実索引（`VERA_P4_INDEX` または `VERA_W1C_INDEX`）が
  無いときは、理由が「環境不足:」で始まる skip になる（実データ依存のテストは環境不足として分類される）。

## 11. 範囲外で見つけた不具合と判断事項（直していない）

どの再現も `artifacts/w1-c/oos_repro.py` が実行して `oos_repro.json` に残した出力（下の表）で、実行していない出力は書いていない。

<!-- BEGIN table:oos -->
出典: `artifacts/w1-c/oos_repro.json`

| 名前 | コマンド | kind / verdict | ability | basis_origin | 回答文 | trace の ability_corpus.*(part の末尾:family:index) |
|---|---|---|---|---|---|---|
| oos1_inflection | VERA_P4_INDEX=/Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1 python -m verantyx.cli ask "窓を開けると、どうなりますか？" | answer / ANSWER | commonsense | generated | 窓を開けると、入ってくった例が複数あります。 | status:local:UNKNOWN_FAMILY_DB_MISSING; status:pro:INDEX_AVAILABLE |
| oos2_scene_family_tie | env -u VERA_P4_INDEX PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1 python -m verantyx.cli ask "湯気の中の朝の台所の様子を一文で描写してください。" | unknown / UNKNOWN_GENERATION_NO_STRUCTURE | generation | なし | 分かりません。必要な根拠が足りません。 | search:local:UNKNOWN_NO_INDEX |
| oos2b_scene_family_tie_with_index | VERA_P4_INDEX=/Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1 python -m verantyx.cli ask "湯気の中の朝の台所の様子を一文で描写してください。" | compose / CREATED | generation | generated | 創作（出典の断片を再構成）: 炊きたてのご飯の湯気が朝の台所に立った。 | search:pro:INDEX_AVAILABLE |
| oos3_fact_question_answered_from_generated | VERA_P4_INDEX=/Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1 python -m verantyx.cli ask "富士山の高さは？" | answer / ANSWER | commonsense | generated | その条件に続く場面では、冷たい水が出た。 | status:local:UNKNOWN_FAMILY_DB_MISSING; status:pro:INDEX_AVAILABLE |
<!-- END table:oos -->

1. **回答文の活用の崩れ**: `窓を開けると、どうなりますか？` の回答が「入ってくった例が複数あります」になる（表の `oos1_inflection`）。
   再現: `env PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1 VERA_P4_INDEX=<索引> python -m verantyx.cli ask "窓を開けると、どうなりますか？"`。
2. **`abilities._scene_family` の同点処理**: 4 系列（`local`, `pro`, `code`, `conversation`）の支持の最大が同点のとき、先頭の最大を採る
   （同点は棄権の原則に反する）。索引を設定しない既定状態では 4 系列とも 0 で同点になり `local` を採る（表の `oos2_scene_family_tie`:
   trace の `ability_corpus.search` が `family: local`、`UNKNOWN_NO_INDEX`）。
   再現: `env -u VERA_P4_INDEX PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1 python -m verantyx.cli ask "湯気の中の朝の台所の様子を一文で描写してください。"`。
   索引ありでは同じ質問で `pro` が選ばれる（表の `oos2b_...`）。
3. **事実質問が無関係な生成文を根拠に ANSWER になる**: `富士山の高さは？` が commonsense の物語経路で `answer / ANSWER`
   「その条件に続く場面では、冷たい水が出た。」になる。出典は `pro` 系列の無関係な生成文で、`basis_origin: "generated"` は付く（決定 1 (a) のもとでは受入基準上は可）。
   再現: `env PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1 VERA_P4_INDEX=<索引> python -m verantyx.cli ask "富士山の高さは？"`（表の `oos3_...`）。
4. **オーナーの判断事項**: 「生成文だけを根拠にした回答を ANSWER にしない」（追補の選択肢 (b)）は別チケット。
5. **C2 の 2 語句**（「Wi-Fiなし 携帯データ」「脱水機の異音」）は、監査役の決定により NO_MATCH の証拠つき報告で可とした（§6）。
6. **社交枠の観察**: `どうもありがとう。` に `こんにちは。` が返る（§8.2）。直していない。
