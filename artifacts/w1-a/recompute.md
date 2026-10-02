## 型ごとの結果(出典: soundness_dev.json / soundness_after.json)

| 型 | 文数 | dev 正読 | dev 誤読 | dev 未対応 | dev 検査誤通過 | 修正後 正読 | 修正後 誤読 | うち上申済み | 修正後 未対応 | 修正後 棄権が正解 | 修正後 正読かつ全節検査PASS | 修正後 検査誤通過 | 正読が半数以上 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | True |
| E1 | 8 | 3 | 5 | 0 | 0 | 3 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| E2 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 9 | 0 | 0 | False |
| E3 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | False |
| E4 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | False |
| E5 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | False |
| E6 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | False |
| F0 | 6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | True |
| F1 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| F2 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| F3 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| F4 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| F5 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 6 | 0 | 0 | False |
| F6 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 6 | 0 | 0 | False |
| J1 | 17 | 0 | 16 | 1 | 15 | 13 | 1 | 1 | 3 | 0 | 13 | 1 | True |
| J2 | 18 | 17 | 1 | 0 | 1 | 17 | 0 | 0 | 1 | 0 | 17 | 0 | True |
| J3 | 15 | 1 | 8 | 6 | 9 | 9 | 0 | 0 | 6 | 6 | 9 | 0 | True |
| J4 | 15 | 4 | 11 | 0 | 11 | 13 | 0 | 0 | 2 | 0 | 13 | 0 | True |
| J5 | 17 | 1 | 14 | 2 | 14 | 11 | 0 | 0 | 6 | 0 | 11 | 0 | True |
| J6 | 16 | 10 | 5 | 1 | 5 | 15 | 0 | 0 | 1 | 0 | 15 | 0 | True |
| J7 | 16 | 0 | 16 | 0 | 16 | 9 | 0 | 0 | 7 | 0 | 9 | 0 | True |
| J8 | 17 | 14 | 3 | 0 | 0 | 14 | 0 | 0 | 3 | 0 | 14 | 0 | True |
| J9 | 18 | 16 | 2 | 0 | 2 | 18 | 0 | 0 | 0 | 0 | 0 | 0 | True |
| K1 | 10 | 0 | 3 | 7 | 2 | 8 | 0 | 0 | 2 | 0 | 8 | 0 | True |
| K2 | 7 | 0 | 2 | 5 | 2 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | False |
| K3 | 8 | 0 | 8 | 0 | 7 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | False |
| K4 | 6 | 0 | 1 | 5 | 1 | 5 | 0 | 0 | 1 | 0 | 5 | 0 | True |
| K5 | 5 | 0 | 5 | 0 | 5 | 1 | 0 | 0 | 4 | 0 | 1 | 0 | False |
| K6 | 7 | 6 | 1 | 0 | 1 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | True |
| L1 | 14 | 7 | 7 | 0 | 7 | 5 | 0 | 0 | 9 | 0 | 5 | 0 | False |
| L2 | 12 | 8 | 4 | 0 | 4 | 10 | 0 | 0 | 2 | 0 | 10 | 0 | True |
| L3 | 6 | 1 | 5 | 0 | 5 | 6 | 0 | 0 | 0 | 0 | 6 | 0 | True |
| T7 | 7 | 0 | 7 | 0 | 6 | 6 | 0 | 0 | 1 | 0 | 5 | 0 | True |
| 合計 | 326 | 102 | 197 | 27 | 113 | 184 | 1 | 1 | 141 | 84 | 141 | 1 | - |

harness 実行の木: dev = `/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/r3/dev` (not a git tree (archive of 075d486 expected for DEVTREE)), 修正後 = `/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S` (075d486105caa1c490e5a2a4f61b256921b111d3)
評価文の件数(ファイル別): {'table7.jsonl': 7, 'ja.jsonl': 149, 'ja_r2.jsonl': 43, 'ja_r3.jsonl': 32, 'en.jsonl': 57, 'en_r2.jsonl': 38}

## カバレッジ(出典: coverage_before.json / coverage_after.json / dropped.tsv / gained.tsv / changed.tsv)

| 指標 | 修正前(dev) | 修正後 |
|---|---|---|
| documents | 1500 | 1500 |
| sentences_approx | 3575 | 3575 |
| supported_sentences | 1365 | 1355 |
| supported_pct | 38.2 | 37.9 |
| only_unsupported_sentences | 1439 | 1431 |
| unread_spans | 772 | 790 |

- supported から外れた文(dropped.tsv): 49 件。分類(coverage_dropped_classified.tsv): {'WAS_WRONG': 49}
- dropped の分類理由欄の語から機械的に分けた内訳(recompute.py の `_kind`。目安であり、分類の正本は各行の理由): {'時間・場所・方角・結果・対象を参与者にした': 8, '先行する語を黙って落とした': 2, '語の途中・括弧・助詞をまたぐ役割句': 19, '役割 0 の空の節': 19, 'そのほか': 1}
- 新たに supported になった文(gained.tsv): 39 件。分類(coverage_gained_classified.tsv): {'CORRECT': 39}
- どちらも supported だが supported 節の構造が変わった文(changed.tsv): 78 件
- 検算: 修正前 1365 - 49 + 39 = 1355 (修正後 1355)

## 全テスト(出典: before_pytest.txt / after_pytest.txt)

- 作業前: `124 failed, 3684 passed, 28 skipped, 82 xfailed, 68 xpassed, 37 subtests passed in 28.70s`
- 作業後: `123 failed, 4598 passed, 28 skipped, 78 xfailed, 72 xpassed, 37 subtests passed in 25.35s`

## 凍結ハッシュ(出典: bank_freeze.sha256 = 第 1 ラウンドの 4 ファイル、bank_freeze_r2.sha256 = 第 2 ラウンドの 3 ファイル、bank_freeze_r3.sha256 = 第 3 ラウンドの 2 ファイル)と、いまの評価ファイルの sha256

| ファイル | 凍結時の sha256 | いまの sha256 | 一致 |
|---|---|---|---|
| a3.jsonl | `4e2d728ac017813d8f6f4ef26505d8394e7a7d8f0ad131487e02a3e67c559e58` | `4e2d728ac017813d8f6f4ef26505d8394e7a7d8f0ad131487e02a3e67c559e58` | 一致 |
| a3_r2.jsonl | `2672d566bd650b181617e89b77ce10ce44d3226169ec58589b10f8bb9d070394` | `2672d566bd650b181617e89b77ce10ce44d3226169ec58589b10f8bb9d070394` | 一致 |
| a3_r3.jsonl | `48e86f0a3d9a3b9c8597dd266a992999bc5580cf8cb625e7dad31d44beb29305` | `48e86f0a3d9a3b9c8597dd266a992999bc5580cf8cb625e7dad31d44beb29305` | 一致 |
| en.jsonl | `88fb349633b7d659db156afbf60ca48d4478692b0ad9c5f63f0506bb5bb76049` | `88fb349633b7d659db156afbf60ca48d4478692b0ad9c5f63f0506bb5bb76049` | 一致 |
| en_r2.jsonl | `a3f77278f73f2cc3d8502876baa5392d6e6febdace5ecfcd26c4bc1ae22cd8c8` | `a3f77278f73f2cc3d8502876baa5392d6e6febdace5ecfcd26c4bc1ae22cd8c8` | 一致 |
| ja.jsonl | `d4bff65f30857cee01ffa30a4c402fbcd87725085a213075b2178a51a3065c0e` | `d4bff65f30857cee01ffa30a4c402fbcd87725085a213075b2178a51a3065c0e` | 一致 |
| ja_r2.jsonl | `9df414efd8aa16a94af03cbe15e7e28037771543c4aed2969af7027bf105fea4` | `9df414efd8aa16a94af03cbe15e7e28037771543c4aed2969af7027bf105fea4` | 一致 |
| ja_r3.jsonl | `af6bb55eecf295a921d6e02b54e17e24f91a85eb8f1b60624f9a14cfa2b23f88` | `af6bb55eecf295a921d6e02b54e17e24f91a85eb8f1b60624f9a14cfa2b23f88` | 一致 |
| table7.jsonl | `4f8daab2c15ef1491610ae09326ece5d48d9e7dc18a5be89a39dfe3dbab1fa7f` | `4f8daab2c15ef1491610ae09326ece5d48d9e7dc18a5be89a39dfe3dbab1fa7f` | 一致 |

上申済みの既知の例外(harness.py の ESCALATED、id で列挙): J1-17 (end point of へ is read as recipient by a convention fixed in an existing test; escalated (docs/READING_SOUNDNESS.md))
