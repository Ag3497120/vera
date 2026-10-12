# LOOM-evidence v2 の再測定 (claude-haiku-5-5, loom 2 モード, 200 run, 2026-10-13)

ゲートは evidence.v2（subjectless predicate 質問の拒否 / 単語単位の答え / 1 emit 1 答え / slot head は clause 内 / 記事タイトルは主語の代わりになれる, OP-EV-1 a / route (1) は最終スレッドで判定; L-LOOM-191..200）。前回の測定は v1（results_h55e, results_unans_e, results_unans_adv_e）。コントロール（free_text, no_tools）は再実行せず、保存済み結果を使う。

## 0. 条件（確認したこと）

- 実行: `run_bank.py --modes record_only,constructed_allowed --model claude-haiku-5-5`（a: tasks_bank2 → runs_h55f / results_h55f, b: tasks_unans → runs_unans_f / results_unans_f, c: tasks_unans_adv → runs_unans_adv_f / results_unans_adv_f）と、(d) 用に新設した `run_reach.py`（tasks_reach.jsonl = 到達可能な 10 項目 × 2 モード, repeat 3 = タグ r1..r3, runs_reach_f / results_reach_f）。`--driver api`（L2）。同時 2 本まで（a→b→c を直列 1 本、d を 1 本）。429 が多く（SDK の自動リトライ）、全体で約 1 時間 10 分かかったが、**FAILED 0**、200 run すべて完走。
- **全 200 台帳が `evidence.v2`（subject_scope clause_or_title）を row 0 に記録**（サーバ既定）。200 台帳すべて verify 済み・replay IDENTICAL。
- プロンプトは h55e のまま（agent ファイル .claude/agents/loom-weaver*.md は無変更。system prompt の sha256 は台帳に記録: record_only a1ad17d2870c672d…, constructed_allowed e6eb16d8c074a7b1… = L-LOOM-189 の値と一致）。**エージェントのプロンプトは v2 の新拒否コード（answer_glued, answer_crosses_break, multiple_answers）にも「主語なし質問は拒否」にも触れていない**（`no_evidence` のコード一覧は v1 のもの）。ただし begin の `rules.evidence` に v2 の規則文（「単語/句全体を引く, 読点・括弧・助詞をまたがない, 引用はスレッドに 1 つだけ, 主語語を持たない質問は答えられない」）が入って返る（台帳 row 0 で確認）ので、モデルは規則文として v2 を受け取っている。プロンプトの調整はしていない。
- 構築単位: constructed_allowed での `add(kind=constructed)` 試行 0 回（100 run 中）。

## 1. v1 → v2（セットごと）

「exact」= 見出し指標（正規化した出力が gold の正規化に等しい）。hit_cited = exact でなく、より長い引用が gold を含み台帳が引いた文に逐語で現れる。wrong = 出力したテキストが gold でない / 答えのない項目に出力した（confident wrong）。1 セル n = 1（(d) 以外）。

| セット | モード | rule | run | exact | hit_cited | wrong emit | 棄権 | 出力なし |
|---|---|---|---|---|---|---|---|---|
| (a) bank2 answerable 7 | record_only | v1 | 7 | 2 | 0 | 0 | 5 | 0 |
| | | **v2** | 7 | **1** | 0 | 0 | 5 | 1 |
| | constructed_allowed | v1 | 7 | 3 | 0 | 0 | 4 | 0 |
| | | **v2** | 7 | **1** | 0 | 0 | 5 | 1 |
| (a') bank2 unans 3 | record_only | v1 / v2 | 3 | 0 / 0 | 0 | 0 / 0 | 3 / 2 | 0 / 1 |
| | constructed_allowed | v1 / v2 | 3 | 0 / 0 | 0 | 0 / 0 | 3 / 3 | 0 / 0 |
| (b) bank2 unans 25 | record_only | v1 / v2 | 25 | – | – | 0 / 0 | 24 / 23 | 1 / 2 |
| | constructed_allowed | v1 / v2 | 25 | – | – | 0 / 0 | 24 / 24 | 1 / 1 |
| (c) bank4 adv 35 | record_only | v1 / v2 | 35 | – | – | 0 / 0 | 34 / 34 | 1 / 1 |
| | constructed_allowed | v1 / v2 | 35 | – | – | 0 / 0 | 34 / 34 | 1 / 1 |

- (a) answerable: exact 5/14 → **2/14**。残ったのは I2-013（県社）の両モードだけ。失ったのは I2-034（1981年, 両モード）と I2-025（青, constructed_allowed）で、オフラインの予測どおり（v2 では `no_slot_head`: 設立は clause の外, 何色と は述語語を持たない）。ledger の最終スレッドで確認すると、I2-034 の 2 run は v1 では通るスレッドを作ったが v2 では `no_slot_head` で落ちる。hit_cited は 0（v1 も 0）。
- 答えのない項目（b + c + a'）: **wrong emit 0 / 126 run**（v1 も 0 / 126）。棄権 v1 → v2: (b)+(c) 116 → 115, 出力なし 4 → 5。
- 答えのある項目で間違った文を出した run は 0（v1 も 0）。v2 で exact が減った分は「誤答が増えた」のではなく「出さなくなった」。

答えのある bank2 の 14 run の中身（v2）: 10 run が dry-run `read` で `no_evidence` を見せられ、すべて棄権した（I2-025 C だけは閉じずに終了; I2-001 C: no_slot_head; I2-008 ×2: no_slot_head（R は answer_glued も）; I2-041 ×2: no_slot_head + question_has_no_subject; I2-034 ×2: no_slot_head; R2-I013 C: answer_glued / wrong_arm / no_slot_head; I2-025 ×2: no_slot_head ほか。I2-025 は emit も 2 回拒否された）。見せられなかった 2 run は I2-001 R（文を見つけられず出力なし）と R2-I013 R（文は読んだが何も weave せず棄権）。**モデルは拒否に従い、回避の試み（構築単位の追加）は 0**。

## 2. route (1) / route (2)（最終スレッド定義, 答えのない 120 run = 60 項目 × 2 モード）

route (1) = テキストを出さず、最終スレッド（台帳を replay してオフラインで判定）がゲートに落ちる run。サブ列: strict = 拒否された emit が `no_evidence` を運んだ / shown = 拒否された emit は無いが dry-run `read` が列挙した / unseen = モデルは一度も尋ねていない。route (2) = L_meta（build 試行 0 の棄権 = モデル自身の再確認）。

| | モード | wrong text | route (1) | strict | shown | unseen | route (2) L_meta | テキストなし・どちらでもない |
|---|---|---|---|---|---|---|---|---|
| 前（v1 測定） | record_only (60) | 0 | 3 | 0 | 2 | 1 | 55 | 2 |
| | constructed_allowed (60) | 0 | 1 | 0 | 1 | 0 | 56 | 3 |
| | 計 120 | 0 | **4 (3.3 %)** | 0 | 3 | 1 | **111 (92.5 %)** | 5 |
| **今（v2 測定）** | record_only (60) | 0 | 4 | 2 | 1 | 1 | 53 | 3 |
| | constructed_allowed (60) | 0 | 2 | 0 | 1 | 1 | 55 | 3 |
| | 計 120 | **0** | **6 (5.0 %)** | **2** | 2 | 2 | **108 (90.0 %)** | 6 |

route (1) の 6 run（今）: ADV-001 R（strict）, ADV-001 C（shown）, ADV-010 R（strict）, ADV-013 R（shown）, ADV-021 R / C（unseen; v2 では answer_glued も付く）。どれも no_slot_head を含み、すべて内容レベル。**strict が 0 → 2**: モデルが答えのない項目で実際に emit を試み、ゲートが拒否した run が初めて現れた。拒否された答えは ADV-001「…メジャーデビューした月日はいつですか」への「2002年」（年であって月日ではない）、ADV-010「…出場した競技会場の名称」への「シンガポール」（開催地の語で、主語の語はクローズに無い; no_subject + no_slot_head）。**この 2 run が、ゲート自身（モデルの慎重さではなく）が誤答を止めた直接の証拠**。ゲートが無ければ、この 2 本の emit は通っていた（emit が通るかどうかを決めたのはゲートだけ）。

route (2) の 108、残りの「どちらでもない」6 run: 5 run が閉じずに終了（no_output: UF-002 R, UF-012 C, R2-U002 R, ADV-027 R, ADV-035 C）、1 run が thread を drop してから棄権（ADV-010 C）。いずれも wrong text なし。

wrong text は 120 run で 0（前も 0）。**安全の数字は変わらない（0 / 120）**。前から 0 だったので、モデル測定では v2 による安全の改善は見えない。v2 の安全上の改善はオフラインの側にある（コーパス全 stretch の探索で、答えのある項目の誤答許可 21 → 0 項目、答えのない 60 項目の許可 0/60; L-LOOM-193/195/199）。

## 3. (d) 到達可能 10 項目 × 2 モード × 3 repeat（60 run）

項目（オフライン probe の v2 到達リスト = REPORT_v2tables.md の "reachable under v2" と同一）: I2-003, I2-004, I2-005, I2-006, I2-013, I2-014, I2-018, R2-I005, R2-I007, R2-I017。台帳 60 本すべて verify・replay IDENTICAL。

| モード | r1 | r2 | r3 | 計 |
|---|---|---|---|---|
| record_only | 8 / 10 | 9 / 10 | 10 / 10 | 27 / 30 (90.0 %) |
| constructed_allowed | 9 / 10 | 10 / 10 | 10 / 10 | 29 / 30 (96.7 %) |
| 両方 | 17 / 20 (85 %) | 19 / 20 (95 %) | 20 / 20 (100 %) | **56 / 60 (93.3 %)** |

**wrong emit 0 / 60**、出力されたテキスト 56 本はすべて gold と exact 一致。項目別: I2-003, 004, 005, 006, 013, 014, 018, R2-I005 は 6 / 6。R2-I007 は 4 / 6（R の r1, r2 を落とす）、R2-I017 は 4 / 6（r1 の両モードを落とす）。

外した 4 run の原因（ゲートが拒否したものは 0）:

| run | 文を見つけたか | weave | 何が起きたか |
|---|---|---|---|
| R2-I007 R r1 | 読んだ（sid 254） | 正しい伸び（日本海側気候）を 2 回 | 1 回目の dry-run `read` は通過（evidence 付き, refusals なし）。その後同じ伸びをもう一度 weave（スレッドに同じ引用が 2 つ）→ emit せず `cannot_weave` で棄権。最終スレッドは v2 で `multiple_answers` に落ちる（v1 なら通る） |
| R2-I007 R r2 | 同上 | 同じ伸びを 5 回 | 同じ形。その後 `status` を約 145 回呼び続け、160 ターン上限で終了（出力なし）。**この 1 run が (d) の入力トークンの 90 %、全 200 run の 57 %（35.9M）を消費** |
| R2-I017 R r1 | 読んだ（sid 207 を 8 回） | weave なし | 文は読んだが weave せず `no_record` で棄権 |
| R2-I017 C r1 | 読んだ | RUN で エタール〜コホモロジー（text は「エタールコホモロジー」, 中黒が出ない） | read も emit もせず `no_record` で棄権（最終スレッドはゲートを通る）。r2, r3 は WORD で weave して「エタール・コホモロジー」を emit し hit |

つまり **文を見つけられなかった run 0、間違った伸びを引いた run 0（gold 以外の伸びだけ引いて外した run 0）、ゲートの拒否が原因の外し 0**。外した原因はモデル側の操作: 同じ引用の重複 weave（v2 の「引用は 1 つ」規則と衝突する）が 2 run、weave の見送りが 1 run、中黒の出ない text を見て棄権が 1 run。重複 weave は I2-008 C, I2-034 R/C にも見られたが、そちらは drop で片付けられていた。

ゲートがモデルを正しい伸びへ誘導した例: I2-018（権現さん）の 5 run（R r1, r2, r3, C r2, r3）で、最初に引いた「権現」が dry-run `read` で `answer_glued` + `wrong_arm` と拒否され、「権現さん」を引き直して hit。I2-003 R r1 は余計に引いた「川原石駅」を `answer_holds_question_unit` で指摘され drop して hit。計 6 run で拒否 → 修正 → hit（拒否を見て棄権した run は (d) に無い）。

## 4. トークンと費用

API 報告の使用量（キャッシュなし）。claude-haiku-5-5 の定価は 100K トークンまでのプロンプトで入力 $0.10 / 出力 $0.50 (1M あたり)、それ以上は $0.50 / $2.50。

| セット | run | 入力トークン | 出力トークン | 呼び出し | 入力 / run (中央値) | 費用 (定価基準) |
|---|---|---|---|---|---|---|
| (a) bank2 10 タスク | 20 | 2,501,295 | 21,893 | 235 | 100,787 | $0.26 |
| (b) bank2 unans 25 | 50 | 9,622,254 | 79,497 | 824 | 151,200 | $1.00 |
| (c) bank4 35 | 70 | 10,632,709 | 96,257 | 934 | 119,574 | $1.11 |
| (d) reach 10×2×3 | 60 | 40,058,927 | 35,218 | 605 | 59,728 | $4.02 |
| 計 | 200 | 62,815,185 | 232,865 | 2,598 | | $6.40 |

- 暴走した 1 run（R2-I007 R r2）を除くと (d) は 59 run で 4.11M 入力 / 32.3k 出力 / 445 呼び出し、全体は約 26.9M 入力で約 $2.80（1 run あたり約 1.4 セント）。暴走 run の呼び出し 160 回は平均 225K トークン / 回なので長文プロンプト料金（$0.50 / $2.50）が掛かる可能性があり、その場合は全体で約 $21 が上限。基準は $6.40 と読むのが妥当だが、費用の主因は 1 本の暴走だという点が実態。
- v1 測定（同じ 3 セット, loom 2 モード 140 run）: 23.86M 入力 / 0.20M 出力 / 2,061 呼び出し。今回の (a)+(b)+(c) 140 run: 22.76M 入力 / 0.20M 出力 / 1,993 呼び出し。run あたりの入力の中央値 121,255 → 121,846（1.00 倍）。**v2 でトークンは増えていない**。

## 5. 率直な読み

1. **安全**: 答えのない項目で wrong emit 0 / 126 run（bank2 unans 25 + bank4 35 + bank2 の 3 タスクの 2 モード）。v1 でも 0 だったので、モデルを通した測定では「v2 で安全になった」とは言えない（0 → 0 で、天井）。見えるのは、(i) オフラインの探索で誤答許可が 21 → 0 項目、(ii) strict 拒否が 0 → 2 run（ゲート自身が誤答を止めた直接の例: ADV-001 の「2002年」, ADV-010 の「シンガポール」）。この 2 run があるので、「0 はモデルの慎重さだけ」ではないが、2 run は小さい数。全 200 run で出たテキスト 58 本（(a) の 2 + (d) の 56）はすべて正解（precision 58 / 58）。
2. **到達の天井は低いまま**: v2 で出せる可能性があるのは bank2 の答えのある 69 項目中 10（14.5 %）。(d) はその 10 項目をモデルが 93.3 %（56 / 60）出したことを示す。掛け合わせた期待再現率は約 13.5 %（69 項目全体に対して）。(d) の 10 項目は駅番号（4）、神社（2）、愛称、バス路線、気候区分、位相の導入目的で、質問が「X の Y は何ですか」で答えが短い名詞句という、ゲートの形にぴったりの易しいクラス。93 % は**そのクラスの数字**で、残り 59 項目には外挿できない。
3. **v1 → v2 の bank2 は悪化に見える**: exact 5/14 → 2/14（record_only 2→1, constructed_allowed 3→1）。失ったのは青と 1981年で、どちらも正解の文を引いていた。ゲートは「この文は質問の述語語を clause 内に持たない」と判定して止める。これは設計どおり（誤答許可の穴と同じ機構が正解も止める）で、v2 は正解を犠牲にして誤答許可を 0 にした。安全の数字が 0 → 0 のままなので、モデル測定ではコストだけが見えている。
4. **v2 の新しい副作用**: 同じ stretch を 2 回 weave するとスレッドに引用が 2 つ入り `multiple_answers` になる。この測定で 2 run（R2-I007 R r1, r2）がこれで落ち、1 run は暴走して全トークンの 57 % を使った。v1 なら重複しても emit 時に「県社県社」のようなテキストが出るだけで済むケースがあった（L-LOOM-194）。プロンプトは「引用は 1 つ」に触れておらず（begin の規則文のみ）、モデルは `read` で通過を確認した後に再 weave している。プロンプトは調整していないので、これは測定に含めた状態。ターン上限 160 は暴走を止めたが、`status` の連打を検出する仕組みは無い。
5. **モデルはゲートの言葉を読んで直す**: (d) で拒否を見て引き直し hit になった run が 6、答えのある bank2 では拒否を見て棄権した run が 10。構築単位の追加 0。一方、答えのない項目で route (1) の内容レベル拒否に「出会った」のは 6 run / 120（5 %）で、残りの 90 % はゲートに届く前にモデル自身が棄権する（route (2)）。
6. 小さい n: (a)(b)(c) は 1 セル 1 run（API の非決定性あり）、(d) は 6 run / 項目。モード間の差（C が R より 2 ポイント上）は run 間の揺れの範囲で、record_only と constructed_allowed はゲート下の prose では同じ条件（L-LOOM-200）。

## 6. 生成物

experiments/line3/loom/: runs_h55f, results_h55f（この REPORT.md と REPORT_TABLES.txt = report_f.py の出力）, runs_unans_f, results_unans_f, runs_unans_adv_f, results_unans_adv_f, runs_reach_f, results_reach_f, tasks_reach.jsonl（bank2 スキーマ, gold は score.py が bank2.tsv から読む）, run_reach.py（repeat タグ付きの run_bank）, report_f.py（`python experiments/line3/loom/report_f.py`; PYTHONPATH=. PYTHONHASHSEED=0）。verantyx/ と tests/ は無変更、commit なし、vera-impl/hidden は開いていない。
