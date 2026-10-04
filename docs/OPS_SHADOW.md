# OPS_SHADOW: 試作中の Vera を開発運用に影運用で入れる (W8-shadow)

**影運用の間、Vera の出力で判断を 1 つも変えない。** 影運用のログ・集計はどの判断の入力にもしない。`verantyx/` とほかの道具はログを読まない。

## 事前登録 (2026-10-04 09:25:04 +0900)

この節はデータ・問い・宣言を書く前に書いた。以後は書き換えない。変更は文書末尾の「変更記録」に前後を追記する。

### 1. 段 0〜4 の定義

- 段 0: Vera を使わない（今の経路: 監査役と中間職）。
- 段 1（W8-shadow で実装）: 分業の影運用。チケットごとに `tools/ops/shadow_route.py` が `vera route` の結果を記録するだけ。
- 段 2（W8-shadow で実装）: 計画ソブリンと問いの影運用。`tools/ops/shadow_ask.py` が答え／棄権を記録するだけ。返答は従来どおり監査役。
- 段 3（未実装・定義だけ）: 昇格した種類（route か ask）について、Vera の出力を判断の **前に** 人へ提示する。決めるのは人で、採否を記録する。
- 段 4（未実装・定義だけ）: 昇格した種類について、Vera が `route`／`ANSWER`（証拠つき）を返したときだけその判断を持つ。`undecided`・棄権・道具の失敗は全部、今の経路（監査役・中間職）に落ちる。

### 2. 昇格の条件（事前登録）

- 種類ごと（route／ask）に、ログの追記順で、verdict の付いた非棄権の entry の連続が **N=30 以上**で、その連続の中に次が 0 件:
  - route の `disagree`、ask の `wrong`、`verdict_conflict`、`answer_untraced`、`unclassified_output`。
- 棄権（route の `undecided`/`not_called`、ask の `abstain`）と verdict 未記入は、連続に数えず、連続を途切れさせもしない。
- **N=30 は方針値であり、実測にもとづかない。**
- 昇格は監査役・オーナーが決める。`shadow_report.py` は条件の充足を表示するだけ。

### 3. 影運用の間は判断を変えない

- ログ・report はどの判断の入力にもしない。`verantyx/` とほかの道具はログを読まない（`tests/test_ops_shadow.py` の T-isolation が機械で確かめる部分）。
- 各道具の先頭にも同じ旨を書く。

### 4. 隠しバンクの中身を記録に入れない

- `/Users/motonisihikoudai/Projects/vera-impl/hidden` の下のパス（実パスで比べる）は全道具が `REFUSED_HIDDEN_PATH` で拒否する。
- 問い・決定の文書に隠しバンクの文を写さない。

### 5. ログの欄の定義（閉じた一覧）

追記のみの jsonl。既存の行は書き換えない・削除しない。

route の entry（1 job 1 行）:
`schema`(`vera.ops.shadow.route/1`), `type`(`entry`), `entry_id`, `ts`, `run_kind`(`operational|acceptance`), `ticket{path,sha256}`, `job`, `task`, `task_source`(`block|task_file|none`), `task_status`(`OK|TASK_NOT_DECLARED|TASK_DECLARATION_CONFLICT|TASK_DECLARATION_AMBIGUOUS|TASK_DECLARATION_INVALID|NO_EXPLANATION`), `explanation{path,sha256,parts[{path,sha256}]}`, `placement{path,content_sha256}`, `tree{git_head,verantyx_clean}`, `vera{called,rc,decision,agent,undecided_reason,abstention_type,decided_by,evidence}`, `raw{path,sha256}`, `shadow_class`, `verdict`(常に null で書く)。

ask の entry:
`schema`(`vera.ops.shadow.ask/1`), `type`(`entry`), `entry_id`, `ts`, `run_kind`, `question`, `asked_by`, `context`, `sovereign{root,store_id,events_used,state}`, `document{path,sha256,map_path}`, `placement`, `tree`, `vera{called,rc,verdict,values,sources[{text,source}],basis_outcome}`, `evidence_events`, `raw`, `shadow_class`, `verdict`(常に null で書く)。

verdict の行（追記）: `schema`, `type`(`verdict`), `ref`(entry_id), `verdict`, `by`, `ts`, `note`。

分類 `shadow_class`（閉じた一覧）:
- route: `route`（decision=route）／`undecided`（decision=undecided。理由と棄権の型は別の欄）／`not_called`（task_status が OK 以外）／`error`（rc≠0 か stdout が JSON でない）。
- ask: `answer`（verdict=ANSWER で証拠が全部引けた）／`answer_untraced`（ANSWER だが証拠が引けない・空）／`abstain`（verdict が ANSWER 以外で values が空。型は verdict の文字列そのまま。ソブリンが読めないときは `SOVEREIGN_<verdict>`）／`unclassified_output`（verdict が ANSWER 以外なのに values が空でない。棄権に数えない）／`error`。

verdict の値: route は `agree|disagree`、ask は `correct|wrong`。同じ entry に食い違う verdict があれば `verdict_conflict` と数え、解かない。人が entry の `verdict` 欄を手で書いた場合も読み、追記の verdict と食い違えば conflict。棄権の entry への verdict は受け、棄権のまま数え、`verdict_on_abstain` として別に数える。

---

# 実装の記録（事前登録のあとに書いた。事前登録の節は書き換えていない）

## 第 2 ラウンド（r2）の変更と測り直し

r1 のログ・集計・証拠は消さずに残してある。r1 の route の測定は、`ops/agents/*.md` と `routing_policy.md` の末尾に構成した「出所: …」の行が入った説明文で行った（その 6 行が `UNREAD_SPAN:uninterpreted colon scope` になり、22 単位になっていた）。r2 では出所を `ops/agents/SOURCES.json`（`*.md` の連結の対象外）に移し、本文の言い換えはしていない。

- r2 の測定ファイル: `ops/shadow/acceptance/route_log.r2.jsonl`（30 entry）、`ask_log.r2.jsonl`（20 entry）、`report.r2.json`、`evidence/s2_run.r2.txt`、`evidence/s3_run.r2.txt`、`evidence/ingest_r2.txt`。
- 数の読み替え: 上の「実測」の S2・S3 の数は r1 のもの。r2 も `report.r2.json` で同じ（route は `undecided` 30・`INCOMPLETE_READING` 30、ask は `abstain` 20・`UNKNOWN_UNREAD` 13・`UNKNOWN_UNSUPPORTED_EVIDENCE` 7、答え 0・誤答 0）。route の単位の数は 22 → 16 に変わった。ask の数・route の分類は同じ。テストは 27 → 33 件になり、全体テストの結果は下の「r2・r3 の S4」のとおり r1 と違う。
- ログの証拠のパス（`explanation.path`・`raw.path`・`document.path`・`map_path`）は、作業ツリーの下なら相対パス（統合後も辿れる）。r1 のログは絶対パスのまま。
- `plan_ingest.py`: 同じ文書に同じ `## ` 見出しが 2 つ以上あれば `DUPLICATE_SECTION:<見出し>` でその文書だけを `refused` にする（どちらも選ばない。ほかの文書は続ける）。
- `shadow_route.py`: 同じ job 名が重複する宣言は `TASK_DECLARATION_INVALID`。
- `content_write` は一時ファイルに書いて `os.replace` で置く（原子的）。

## 道具の使い方と出力

すべて標準ライブラリだけ（`verantyx.agent_routing` の値の一覧を import するのは `shadow_route.py` の宣言検査のみ）。ログは追記のみで、既存の行を読まず・書き換えず・削除しない。Python は `/Users/motonisihikoudai/vera-wiring/env/bin/python`、`PYTHONPATH=<ツリー>`、`PYTHONDONTWRITEBYTECODE=1`。

- 共通: 配置は `--placement`、なければ環境変数 `VERA_PLACEMENT`、なければ `build/coarse-W3a/full/r8/run2`。`manifest.json` の `content_sha256` が読めなければ rc=2 で何も書かない（`--no-placement` のときだけ配置なしで続ける）。子プロセス（`python -m verantyx.cli`）は `cwd=<ツリー>`・`PYTHONPATH=<ツリー>`、環境から `VERA_SOVEREIGN_ROOT`/`VERA_SOVEREIGN_STORE` を消し、`--confirm` は渡さない。`explanations/` `raw/` `docs/` は `--store-dir`（既定はログのあるディレクトリ）の下に内容アドレス（本文の sha256 先頭 16 桁）で書く。
- `tools/ops/shadow_route.py <ticket.md> [--task-file F] [--agents-dir D] [--policy P] [--log L] [--run-kind operational|acceptance]`: 課題は ```` ```shadow-task ```` の囲み（ちょうど 1 個）か `--task-file` の宣言だけから作る（D1）。説明文は `ops/agents/*.md`（名前順）と `ops/routing_policy.md` の本文を `"\n"` で連結しただけ。job ごとに `vera route` を 1 回呼び、1 job 1 行を追記。チケット本文は記録せずパスと sha256 だけ。記録できれば rc=0（`undecided` でも 0）、記録できないときだけ rc=2。
- `tools/ops/plan_ingest.py [--root R] [--decisions D] [--owner owner]`: `ops/decisions/*.md` の先頭メタ（HTML コメントの JSON 1 行）を外し、`## ` の節ごとに author（owner|auditor）を宣言した節だけを `vera sovereign append --kind decision` で追記する。同じ `(doc, section)` で本文が同じなら追記せず（`skipped_unchanged`）、違えば `corrects` つきで追記。メタが無い・author 未宣言の文書は `refused` に入れてほかは続ける。出力は 1 行 JSON（`INGESTED`）。
- `tools/ops/shadow_ask.py "<問い>" [--asked-by auditor|mid|implementer] [--context C] [--root R] [--log L]`: ソブリンの事件を `vera sovereign events` で読み、訂正されていないものの本文を空行 1 つで連結した文書を書き出して `vera ask --mode round5 --document` に通す。`ANSWER` のとき `sources[*].text` を事件の本文に引き、全部引ければ `answer`（`evidence_events` に事件の id）、引けなければ `answer_untraced`。ソブリンが読めない（`UNKNOWN_STORE`・registry の指すファイルが別・空など）ときは `ask` を呼ばず `abstain` とし、`vera.called=false`、`sovereign.state` にその型を残す（report は `SOVEREIGN_<state>` として数える）。
- `tools/ops/shadow_verdict.py --log L --ref <entry_id> --verdict agree|disagree|correct|wrong --by <誰> [--note …]`: 同じログに `type: verdict` の行を追記する（D4）。
- `tools/ops/shadow_report.py --route-log L1 --ask-log L2 [--n 30]`: 1 つの JSON を標準出力に出す。各分類の和が `total_entries` と合わなければ rc=2。

## 判断記録（D1〜D5。中間職の指示書の判断）

- **D1 課題は宣言から作る**: チケットの散文から `role/kind/size` を推すと語の一覧の規則になり、AGENTS.md の「語の一覧を足して直さない」に反する。宣言が無ければ `TASK_NOT_DECLARED`（`vera route` を呼ばない）、囲みと `--task-file` が食い違えば `TASK_DECLARATION_CONFLICT`、囲みが 2 個以上なら `TASK_DECLARATION_AMBIGUOUS`、値が `ROLES/TASK_KINDS/SIZES` の外なら `TASK_DECLARATION_INVALID`。
- **D2 計画ソブリンの sqlite はコミットしない**: registry がファイルの絶対パスを持ち、root を複製すると複製元のファイルを読み書きする（指示書 §0.1 の実測。`tests/test_ops_shadow.py::test_ingest_copied_root_is_refused_and_original_untouched` が再現して防ぐ）。`ops/plan_sovereign/.gitignore` と `README.md` を置いた。道具は registry の示す実パスが `<root>/stores/plan.sqlite` でなければ `PLAN_SOVEREIGN_PATH_ELSEWHERE` で止まる。
- **D3 本番と受入の記録を分ける**: 受入の走行は `ops/shadow/acceptance/` の下の別のログに `run_kind: "acceptance"` で書いた。本番のログ（`ops/shadow/route_log.jsonl` `ask_log.jsonl`）は作っていない。
- **D4 verdict は追記で付ける**: entry の行は `verdict: null` で書き、判定は verdict の行を追記する。同じ entry に食い違う verdict、または entry の手書きの `verdict` 欄と追記の食い違いは `verdict_conflict` と数え、解かない。
- **D5 昇格の N**: N=30 は方針値で、実測にもとづかない。route と ask は別々に数える。昇格の判断は監査役・オーナー。

実装者の追加の判断:
- `ops/agents/*.md` と `routing_policy.md` は、チケット「やること 1」と AGENTS.md の推奨構成の節に書かれたことだけを平らな日本語で書いた（出所は `ops/agents/SOURCES.json` に置いた。r1 は各ファイルの末尾に 1 行置いていた）。読解器が読める形への書き換えはしていない。
- 連続（streak）は「ログの追記順で、いまの末尾に続く連続」（最後に連続を切った entry より後の、verdict つき非棄権の数）で数える。過去に N を超える連続があっても、その後に連続を切るものがあれば昇格の条件は満たさない（事前登録の文言「連続」を保守側に読んだ）。`max_streak` も併記する。
- 事前登録は `error` の entry を連続に数えず切りもしないと読める。`error` は `by_class` と `verdicts.error_entries` に必ず出る。
- `unparseable_lines` が 1 行でもあれば昇格の条件は満たさない（`UNPARSEABLE_LINES`）。
- T-isolation は、指示書の「`shadow_` を参照する文字列」を、`verantyx/` に既にある無関係の `shadow_violations` が誤検知するため、道具名（`shadow_route` `shadow_ask` `shadow_report` `shadow_verdict` `plan_ingest`）・`route_log`・`ask_log`・`ops/shadow`・`tools/ops` で検査する。

## 実測（数値は測定出力のファイルから貼る）

- 読み込み元の確認: `ops/shadow/acceptance/evidence/env_check.txt`（作業ツリーの外の `verantyx*` は `[]`、HEAD は `89e3d2e`）。
- 指示書 §0.1 の実測の再確認: `vera route` は配置（r8/run2）を渡すと `Opusがレビューをやる。` で `route`・`Opus`、`Opus 5.5 の medium が書く。` のような版番号つきの文は `UNREAD`（`NO_SUPPORTED_CLAUSE`）。実物の `ops/agents`＋`routing_policy.md` は、r2（出所の行を外したあと）では 30 件の raw すべてが `16 of 16 units were not read and mapped` で `INCOMPLETE_READING`（`ops/shadow/acceptance/raw/` の各 json を `abstention.detail` で数えた。数えた出力は `evidence/r2_units.txt`）。r1 は 30 件すべて `22 of 22 units`（`evidence/r1_units.txt`）。差の 6 単位は r1 の説明文に混ざっていた構成した「出所」の行（`UNREAD_SPAN:uninterpreted colon scope`）。
- **S2**（10 件×一律 3 job、宣言は `ops/shadow/acceptance/tasks/`、凍結は `tasks/FROZEN.sha256`）: `ops/shadow/acceptance/route_log.jsonl` の entry 30 行、`evidence/s2_run.txt` に `FAIL` 0 行。`report.json` の route は `by_class` が `undecided` 30（`route` 0）、`by_undecided_reason` が `ABSTAINED` 30、`by_abstention_type` が `INCOMPLETE_READING` 30。**全 job が棄権で、ルート一致は 0**（一致数は報告のみ。verdict は付けていない）。
- **S3**（5 文書・7 節を `ops/plan_sovereign` に取り込み: `evidence/ingest_1.txt` が `appended 7`、`ingest_2.txt` が `appended 0, skipped_unchanged 7`。問い 20 件は `questions.jsonl`、凍結は `questions.FROZEN.json`、sha256 の一致は確認済み）: `report.json` の ask は `by_class` が `abstain` 20（`answer` 0・`answer_untraced` 0・`unclassified_output` 0・`error` 0）、`by_abstain_type` が `UNKNOWN_UNREAD` 13・`UNKNOWN_UNSUPPORTED_EVIDENCE` 7、`verdicts.wrong` 0。**答え（`answer`）は 0 件で、誤答 0 は「答えていないから」であって、答えの正しさの証拠ではない**。有答の問い 8 件も全部棄権だった（問いごとの対応は `ask_log.jsonl` と `questions.jsonl` の同じ順）。`answer` が無いので `shadow_verdict.py` は実行していない（`evidence/s3_verdict_cmd.txt`）。
- `basis_policy.md` に Markdown の表が入っているため、指示書 §0.1 のとおり文書全体が `UNKNOWN_UNSUPPORTED_EVIDENCE` になる見込みがあった。この測定では、表の有無を分けて測っていないので、7 件の `UNKNOWN_UNSUPPORTED_EVIDENCE` と表の関係は未確認。
- テスト（r1）: `tests/test_ops_shadow.py`（`evidence/test_ops_shadow.txt`）。全体テストと基線の比較は `evidence/pytest_full.txt`・`evidence/new_failures.txt`。r2・r3 の S4 は次の節。

### r2・r3 の S4（測定出力のファイル）

- r2: `evidence/test_ops_shadow.r2.txt` は 33 passed。全体テスト `evidence/pytest_full.r2.txt` は 116 failed。基線との差 `evidence/new_failures.r2.txt` は 1 件（`tests/test_gen_coarse_evidence.py::test_the_stop_signal_ends_the_run_with_an_interrupted_record`）。このテストは `time.sleep(0.1)` で待ちながら子プロセスへシグナルを送る時間依存の作りで、このチケットのファイルを参照しない。単独で 3 回流して通った（`evidence/stop_signal_rerun.r2.txt`）。中間職の全体テストの再走（r2 のレビュー）では 115 件・新規 0 件だった。
- r3: `evidence/test_ops_shadow.r3.txt` は 33 passed（M2 の修正後の `tests/test_ops_shadow.py`）。全体テスト `evidence/pytest_full.r3.txt` は 116 failed, 15191 passed, 38 skipped。基線との差 `evidence/new_failures.r3.txt` は r2 と同じ 1 件（`test_the_stop_signal_ends_the_run_with_an_interrupted_record`）で、消えた失敗は 0。単独再走は 3 回中 1 回失敗・2 回通過（`evidence/stop_signal_rerun.r3.txt`）で、このテストが基線の外で揺れることを再確認した（`tests/test_gen_coarse_evidence.py` に `ops`/`shadow` の参照はない。このチケットの変更ではない）。

## 既知の穴

1. 段 1・2 は、いまの説明文・記録では Vera がほとんど（この測定では全部）決めない。これは Vera 側の読解の限界の測定で、道具や文書を読解器に合わせて直す対象ではない（直すのは別チケット）。
2. 課題の宣言（S2 の一律 3 job）は、チケットの性質から推していない一律の暫定の宣言（10 件とも同じ中身。D1）で、チケットごとの実際の仕事の形を表していない。Vera の判断ではない。10 件の選び方も暫定（監査役が差し替える）。
3. 問い 20 件は自作（実装者が書いた）。自作で通ることは証拠にならない。誤答 0 は答え 0 件による。
4. `ops/decisions/` は写しなので、出所が後で変わったら `source_sha256` と食い違う（検出する道具は作っていない）。監査役の裁定（各 `tickets/*.md` の「監査役の判断」節）は写していない。「目的の順序」は出所が番号順の列で、優先順位の宣言は見つからない（メタの `note` に記録）。
5. `plan_ingest.py` は `ops/decisions/` から消えた文書・節を計画ソブリンから退役させない（削除しない原則。退役は追記が要るが、この版では作っていない）。
6. 「棄権の entry に付けた verdict」は数えるだけで、棄権が正しかったか（棄権すべき問いだったか）は測っていない。
7. `vera ask` の分類は最上位の `verdict`/`values`/`sources` だけを見る。`trace` の途中の別候補は読まない。`sources[*].text` が複数の事件に含まれるときは全部を `evidence_events` に列挙し、1 つに決めない。
8. ログへの追記は `flock` で直列化するが、別ホストからの同時書き込みは想定していない。
9. `shadow_ask.trace_sources` は `sources[].text` を書き出した本文の部分文字列として探す。読解器の raw では span から `**` や `` `code` `` が抜けることがあり、本当の答えが `answer_untraced` に落ちる恐れがある（保守側で、連続も切るので誤りの見逃しにはならない）。
10. 全体テストの結果は実行のたびに揺れうる。r1 は `evidence/pytest_full.txt` で失敗 115 件・基線との差 0 件（`evidence/new_failures.txt`）、r2 は `evidence/pytest_full.r2.txt` で失敗 116 件・新しい失敗 1 件（`evidence/new_failures.r2.txt`。時間依存の既存テストで、このチケットと無関係。単独再走は `evidence/stop_signal_rerun.r2.txt`）。`tests/test_ops_shadow.py` の失敗は 0。全体テストを流すと、既存の `tests/attack/w3a3/r6_48_queries.jsonl` が書き換わった（このチケットの変更ではない既存テストの副作用。復元した）。

## 監査役への申し送り

- S2 の 10 件を差し替える場合は `ops/shadow/acceptance/tasks/<チケット名>.json` と `route_log.jsonl` を別名で作り直す（既存のログは消さない）。
- verdict の付け方: `python tools/ops/shadow_verdict.py --log <ログ> --ref <entry_id> --verdict agree|disagree|correct|wrong --by <誰>`。
- 計画ソブリンの sqlite をコミットするかの裁定（既定はコミットしない。`ops/plan_sovereign/.gitignore` を外せばコミットできるが、registry の絶対パスの問題が残る）。
- 監査役の裁定を `ops/decisions/*.md` に足すときは、先頭メタに出所と節ごとの author を書く。

## 変更記録

（事前登録の節への変更はない。事前登録の節の末尾までの先頭 4960 バイト（`head -c 4960 docs/OPS_SHADOW.md | shasum -a 256`）の sha256 は `df410230f5d22c7f7092e4cf1f4f8d04a528a26a85aff05563295172b518cf45` で、`ops/shadow/acceptance/evidence/prereg_sha256.txt` の値と一致する。）

第 2 ラウンドで、事前登録の節より後ろの本文（実測・既知の穴・r2 の節）を直した。事前登録の節は変えていない（上の sha256 の照合）。
