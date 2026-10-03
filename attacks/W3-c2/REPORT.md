# W3-c2 攻撃報告

## 1. 対象

- `docs/OBSERVATION.md`「質問の観測（W3-c2）」: D9 一致、D11 出力状態、D12 証拠、D17 の WRONG=0。
- `docs/EVENT_CROSS.md`「穴の型」: wh 穴の受入型と direct 型の不一致除外。
- `verantyx/semantic_read.py` の `read_question`、`verantyx/observe.py` の質問観測・型フィルタ、CLI `observe --anchor-kind question --structure`。
- 事前登録・入力 SHA-256: [PREREG.md](PREREG.md)。10 文書・70 文・120 問を配置あり／なしの両方で実行した（[入力行数](results/input-counts.txt)、[配置なし結果](results/absent.summary.json)、[配置あり結果](results/configured.summary.json)）。

## 2. 命中

### A01 — 英語 who 穴が artifact を返す（観点 a, d, e）

**事前凍結した反例**: `EN08-01`。「Who did the girl write?」の正解は文書に人の書き先が書かれていないため `NONE`。`EN08-S01` は *The girl wrote a letter.*、`EN08-S02` は *The girl wrote a note.*。

再現コマンド:

```sh
env -u VERA_PLACEMENT PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.cli observe --anchor-text 'Who did the girl write?' --anchor-kind question --lang en --structure attacks/W3-c2/data/docs/EN08.jsonl --no-index
```

実出力（全 JSON は [cli-absent.json](results/cli-absent.json)）:

```text
answer.status = TIE
question = {wh: who, hole_role: patient, hole_type: [GROUP_ORG, PERSON]}
fillers = letter [EN08-S01], note [EN08-S02]
両候補の hole_type_check = NOT_CHECKED(NO_PLACEMENT)
```

期待は `NONE` だが、型が PERSON の問いに artifact 2 件が `TIE` で返り、D17 の CORRECT 条件を満たさない。指定された coarse placement 環境変数の有無で同じ出力だった（[CLI・配置あり](results/cli-configured.json)）。一方、同じ語を direct `ARTIFACT` とした明示的 `--placement` 対照は `TYPE_EXCLUDED_ALL`、両方 `HOLE_TYPE_DISAGREE` になった（[対照出力](results/cli-direct-types.json)）。このため「direct 型がある状態でも除外しない」とは数えず、配置なし経路で誤答が返ることを命中とした。

該当箇所: `verantyx/semantic_read.py:1168-1178` は wh 語を位置から穴にし、`Who did the girl write?` を `patient` として読む。`verantyx/observe.py:1252-1261` は配置なしを `NOT_CHECKED`、`verantyx/observe.py:1368-1374` は `DISAGREE` のときだけ通常候補から除外する。受入基準は `docs/OBSERVATION.md:359-360`。この限界自体は同文書 `:613` に既知の穴として記載されているが、D17 の WRONG=0 とは両立しない。

### A02 — 時の副詞が patient の候補面に混ざる（観点 a）

固定文書 `JA02-S06`「花子は毎日本を読んだ。」を含む `JA02` に、`JA02-01`「花子は何を読んだ？」を流すと、CLI は `TIE` として `新聞`・`本` に加えて `毎日本`（証拠 `JA02-S06`）を返した。該当する出力は [cli-time-adverb.json](results/cli-time-adverb.json)、構造文単体の reader 出力は `patient: 毎日本`。

```sh
env -u VERA_PLACEMENT PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.cli observe --anchor-text '花子は何を読んだ？' --anchor-kind question --lang ja --structure attacks/W3-c2/data/docs/JA02.jsonl --no-index
```

「毎日、本を読んだ」の `毎日` が目的語と一緒に一つの充填物になり、対象物の候補に加わっている。これは D9 の表層一致だけでは救えない構造読解の誤りである。**この質問に対する truth は初回の凍結 JSON に書いていないため、初回の自動 WRONG 数には含めていない**。凍結済みの文書・質問から実行後に見つけた独立の反例として命中に数えた。該当する値の引き渡し箇所は `verantyx/semantic_read.py:546`、穴の腕の候補化は `verantyx/observe.py:1368-1379`。

## 3. 外れた攻撃

- **同点崩し**: `JA01-01` の校長／先生、`EN09-01` の patient／student は両方 `TIE`。一方を選ぶ出力はなかった（`results/absent.jsonl`、`results/configured.jsonl`）。
- **否定・態・役割の入れ替え**: `JA01-05` は否定文の校長だけを返し、`JA01-02`・`JA04-02` は主語／相手を入れ替えた対応文の候補を返した。受身の `JA05-01/02` は文書中の受身文の候補を返した。肯定／否定や異なる役割を誤って一致させた出力はこの組では見つからなかった。
- **使役、助詞位置、数量、時の疑問、英語の was・stranded `to`**: 読めない形は `QUESTION_NOT_READ`、はい／いいえは `POLAR_QUESTION`、`which N` は配置なしで `HOLE_TYPE_UNDETERMINED` になった。これらから誤った `FILLED`/`TIE` は見つからなかった。英語の `does` 主語疑問は `girl` を返した。
- **direct 型の不一致**: `--placement attacks/W3-c2/data/direct-types.json` の明示 direct 型対照は、PERSON 穴から `letter` と `note` を除外した。型不一致の規則自体はこの対照で命中しなかった。
- **平叙文の既存経路**: 既存 reader の基点関数・定数 SHA-256 検査、否定・時制・態一致、英語の取り残し `to` の3つの関係テストは通過（[実測ログ](results/existing-related-tests.txt)、3 passed）。平叙文出力の変更を示す反例は得られなかった。

### 実行集計

凍結した4件の正解付き probe は `EN08-01` が WRONG、`EN08-04` は正答を読めず ABSTAINED、`JA01-01` と `JA01-05` は CORRECT。120問全体の配置なし・指定配置ありの両方で status は同一: `FILLED 34, TIE 10, NO_ATTESTED_CELL 12, TYPE_EXCLUDED_ALL 0, HOLE_TYPE_UNDETERMINED 7, QUESTION_NOT_READ 51, POLAR_QUESTION 6`。出力 JSONL は SHA-256 が一致（`e440450a86dcdeaa9f046141ef619a7f4c22ef8284b50fc83f8ad48a2cbc8747`）。数値の元ファイルは2つの `*.summary.json`。

W3-c2 の攻撃群で数えたものは **命中 2、外れ 5**。A02 は上記のとおり frozen truth の採点外。主な失敗テストは [pytest_attack.txt](results/pytest_attack.txt)（1 failed, 3 passed）。

## 4. 手順・限界

- 製品コード・既存テスト・期待値は変更していない。全体テスト、ネットワーク、commit/push は行っていない。
- 配置なし／ありの120問は `run_entry`（CLI が呼ぶ同じ entry）で完走し、A01 は CLI でも再現した。direct 対照も CLI で実行した。
- 既存の選択テストを最初に1回、存在しない node id で呼んで pytest collection が止まり、テストは走らなかった。その後、正しい node id で該当3テストを再実行して通過した。攻撃 pytest は意図した1失敗・3成功を確認した。
- 関連テストの再現コマンド: `env -u VERA_PLACEMENT PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest tests/test_question_cross.py::test_existing_functions_and_constants_are_byte_identical_to_the_base tests/test_question_cross_observe.py::test_polarity_tense_and_voice_must_be_the_same tests/test_question_cross_observe.py::test_en_a_stranded_to_question_never_returns_the_object_as_the_answer -q`。
- 初期に frozen truth を4問にしか付けていない。残る探索問のうち A02 は実出力から意味の誤りが明白と判断して別枠で報告したが、初回の自動スコアには含めていない。
- pytest が作業ツリー直下に `.pytest_cache/` を作成した（確認時刻 2026-10-03 22:19:42）。攻撃指示の「書くのは attacks/W3-c2 の下だけ」から逸脱した。削除禁止に従い、痕跡を消さず残した。製品コード・追跡対象ファイルの差分は `attacks/W3-c2/` のみ。
- 開始時の負荷確認は1分平均が8超だったため、試験を始める前に約6分待って再確認した。両配置の測定前にも `uptime` を確認し、1分平均8未満で実行した。
