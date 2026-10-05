# `vera chat --mode round5`

## 事前登録（2026-10-04 09:05:32 JST）

対象は round5 の対話入口だけとする。実装前に次を固定する。

- `/` で始まる入力は `/doc`、`/docs`、`/gen`、`/route`、`/read`、`/json`、`/help`、`/quit` の閉じた集合として扱う。集合外は `UNKNOWN_COMMAND`。
- 質問は `cmd_ask` と同じ `Vera.ask` → `_round5_question_cross` → `basis_policy.apply_to_ask` を通す。同一引数の JSON dict は一致し、`basis_policy.outcome` も一致する。
- R2 の手元確認用に、次の4文をテスト専用の fixture として固定し、`VERA_PLACEMENT` に r8/run2 を設定する。期待は、地図の質問に先生を証拠付きで返す、兄の質問に妹を証拠付きで返す、荷物の行先は型付き棄権にする。
  1. `先生が生徒に地図を渡した。`
  2. `兄が妹を呼んだ。`
  3. `係が荷物を運んだ。`
  4. `妹が本を読んだ。`
- `/gen` の JSON は、同じ文書由来の `{id,text}` 構造・配置・方向・range を渡した `vera observe` の1行出力とバイト一致する。
- `/read` は `semantic_read.read` の結果を、`/route` は `cmd_route` の結果を使う。`--json` と `/json on` は質問の dict を出す。
- R4 は新規テストと既存テストを実行し、全体テストの失敗名を基線 `dev_0041606_failures.txt` と比較する。既存テストの期待は変更しない。

この指示書には「今朝の実演の4文」の原文またはファイルパスが含まれていない。上記は経路確認用の独立したテスト fixture であり、原文の実演を再現したとは扱わない。

検査データとテストを **2026-10-04 09:14:52 JST** に凍結した。`tests/test_chat_repl.py` の SHA-256 は `21551ba93558e849531ffc016e2b872d31637af9700cd05ef5193e2d4ec61a6a`。実装を通した後にこのファイルは変更しない。

**実装前の凍結訂正（2026-10-04 09:21:21 JST）**: 直す前の `vera ask` 記録では地図の質問は `Vera.ask` の時点で `ANSWER` となり、条件付き後段 `question_cross` を通らなかった。兄の質問は `UNKNOWN_UNREAD` から `question_cross=FILLED` へ進み `basis_policy` も適用された。このため R1 比較入力だけを兄の質問に切り替え、後段までの dict 一致を検査する。回答の期待値は変えない。訂正後の `tests/test_chat_repl.py` SHA-256 は `fce8a41c46ddbc6f3502bba91157ca2c1ab8f5703002d6f5fdd55fefe60a2df8`。この訂正は実装前であり、以後は変更しない。

**実装前の凍結確認（2026-10-04 09:23:58 JST）**: 既存 `vera ask` の地図回答の `text` は `agent: 先生`、証拠元は `demo.txt` の1行目だった。人向け表示も返却された `text` をそのまま示す期待に固定する。`tests/test_chat_repl.py` 最終 SHA-256 は `c8ed7349400673ae405d7e5771159b0ad26969d737cc3e5333b5b995201c7638`。以上を実装前の最終凍結とする。

## 追加事前登録（2026-10-04 10:42:21 JST、監査裁定反映）

前回レビューの verdict は `blocked`。未コミットの対話入口・テスト・文書を残した状態から再開した。前回の検査 fixture は監査役が提示した実演原文と異なるため、以下の受入 fixture に差し替える。これは前回の記録を消さずに追加する訂正であり、実装の結果を見て期待を変更するものではない。

- R1 は `vera ask --mode round5` と `vera chat --mode round5 --json` の結果を比較する。時間計測値 `ingest_ms` と `elapsed_ms` は値が呼出しごとに変わるため、辞書の全階層でこの2つの鍵だけを除外する。その他の鍵・値、特に `question_cross` と `basis_policy.outcome` は一致させる。`cmd_ask` は変更しない。
- R2 は次の文書を `VERA_PLACEMENT=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2` で読み込ませる。
  1. `先生が生徒に地図を渡した。`
  2. `校長が職員室で書類を確認した。`
  3. `母が弟に話した人を兄が呼んだ。`
  4. `係が荷物を倉庫に運んだ。`
- R2 の期待は、「誰が生徒に地図を渡した？」→ `ANSWER` 先生（1文目の証拠）、「兄は誰を呼んだ？」→ `ANSWER` 人（3文目の証拠）、「係は荷物をどこに運んだ？」→ `QUESTION_NOT_READ` 型の棄権、「校長はどこで書類を確認した？」→ 型の棄権。
- R3 の `/gen` は `vera chat --placement <json>` で指定された `tests/observe/data/placement.json` を `observe.run_entry` に渡す。同じ `{id,text}` 構造・配置・アンカー `先生が生徒に地図を渡した。`・方向 `FACE_SWAP:agent`・range `1` の `vera observe` と JSON 出力をバイト単位で比較する。環境変数 `VERA_PLACEMENT` の coarse 配置ディレクトリは observe の JSON 配置として流用しない。配置 JSON が無い場合は `NO_MOVE_LICENSED`（配置近傍なし）を利用者に表示し、観測結果自体も表示する。
- テストは上記の4文・期待、R1 の鍵除外、R3 の配置付き parity、および `/read`・`/doc`・未知コマンド・JSON 出力を実行前に固定する。次節で `tests/test_chat_repl.py` の SHA-256 を記録し、その後に期待値を変更しない。

追加 fixture と期待を **2026-10-04 10:48:33 JST** に凍結した。`tests/test_chat_repl.py` の SHA-256 は `7886d3516f18102c6e250c2c2d8ddd9efaadc0faecc771afe9e3eb3c3f4735d6`。実装後も内容を変更しない。

**直す前の記録（2026-10-04 10:49 JST）**: `PYTHONPATH=<worktree> PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider tests/test_chat_repl.py` は終了コード1、9 passed・4 failed。失敗は実演の兄の回答、校長の棄権、`chat --placement` 未対応、配置 JSON なしでの `NO_MOVE_LICENSED` 表示だった。生出力: [pre-fix.r1-chat-tests.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex/pre-fix.r1-chat-tests.log)。

## 使い方

```text
vera chat --mode round5 [--document PATH ...] [--request-kind KIND]
          [--human-present] [--show-generated-reference] [--placement JSON] [--json]
```

質問文を入力すると `vera ask --mode round5` と同じ経路を通る。`--document` は繰り返し指定でき、`/doc PATH` でもセッション中に追加できる。JSON 表示は起動時の `--json` または `/json on|off` で切り替える。

| 入力 | 呼ぶ入口 | 結果 |
|---|---|---|
| 質問文 | `Vera.ask` → `_round5_question_cross` → `basis_policy.apply_to_ask` | 判定、答え、根拠文書・行・文、`basis_policy.outcome` |
| `/doc PATH` | `Vera.load_documents` | 文書をこの対話に追加 |
| `/docs` | 読み込んだ `Vera` の文書 | 読み込んだ文書名を表示 |
| `/gen 文 [方向] [range]` | `observe.run_entry`（`--placement JSON` があれば渡す） | 実現文、主張型、座標を表示 |
| `/route 説明 PATH_OR_JSON` | `cmd_route` → `routing_from_text.emit` | `vera route` と同じJSON |
| `/read 文` | `semantic_read.read` | 文の読みと十字を表示 |
| `/json on|off`、`/help`、`/quit` | REPL | 表示切替、ヘルプ、終了 |

## 適用範囲と限界

この対話入口は既存経路のラッパーであり、読解規則や証拠の権限は増やさない。質問には `VERA_PLACEMENT` の粗い配置を使う。`/gen` は観測された構造の実現で、事実の回答ではない。observe の配置 JSON は `vera chat --placement PATH` で指定する。JSON が無い場合は `NO_MOVE_LICENSED` と表示して、移動を許可しない観測結果もそのまま示す。`VERA_PLACEMENT` の coarse 配置ディレクトリを observe JSON 配置として自動変換しない。読めない・証拠が無い・型が決まらない場合は、それぞれ既存経路の型付き結果を表示する。

## 実装ラウンドの実測

- `tests/test_chat_repl.py`: 13 collected、11 passed、2 failed。失敗は実演の兄の問いが `UNKNOWN_UNREAD`、校長の問いが `ANSWER` になったこと。最終出力: [final.r1-chat-tests.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex/final.r1-chat-tests.log)。
- R1 の辞書比較（`ingest_ms`・`elapsed_ms` を除外）は通過した。R3 の配置 JSON 付き `/gen` と `vera observe` のバイト一致も通過した。R3 の関係テスト出力は [related.r1-tests.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex/related.r1-tests.log)。
- 実演4問の CLI 出力では、地図の問いは先生を証拠付きで回答、兄の問いは `UNKNOWN_UNREAD`、荷物の行先は `UNKNOWN_UNREAD`（後段 `QUESTION_NOT_READ`）、校長の問いは職員室を回答した。出力: [r2-session.r1.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex/r2-session.r1.log)。
- 関係テスト 230 件中 228 passed、2 failed。ほかの質問十字・observe テストは通過した。出力: [related.r1-tests.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex/related.r1-tests.log)。基線に対する全体テスト失敗集合は、この作業者の環境では再測定していない。

以下はチケットで提示された隠しバンク測定値であり、この実装ラウンドでは再測定していない（出典: `review-impl/prompts/W7-chat_repl.prompt.md`）。

- B1: 11/296 誤読 0。
- B2: 0/286。
- B6: 誤ルート 0。
- B7: 誤答 0・方針到達 0。
- 質問の観測: 73/185 誤 0。

## R2 受入期待の訂正記録（2026-10-04 11:48:28 JST、監査役判断2）

前回レビューの必須指摘に対する処置を、テスト変更より先に登録する。監査役の判断2は前回の R2 期待に誤りがあったと認定し、「4問で誤った回答が0件、回答があれば証拠付き」を新しい受入条件とした。既存の質問の十字・回答方針・`cmd_ask` は変えず、既存経路の結果をこの条件に照らす。監査役指定の実演4文・4問は直前の事前登録に記録済みであり、以下はそのうち前回誤っていた2問の期待だけを訂正する。

| 問い | 固定する期待 | 判定の根拠 |
|---|---|---|
| `兄は誰を呼んだ？` | `UNKNOWN_UNREAD` の型付き棄権、方針 `ABSTAIN`。回答本文や証拠付き回答を要求しない | 監査役判断2はこの棄権を誤答でないと裁定。`cmd_ask` と chat の共有経路を維持する |
| `校長はどこで書類を確認した？` | `ANSWER`、`place: 職員室`、`demo.txt:2` の証拠文、方針 `ANSWER_HUMAN_BASIS` | 監査役判断2はこれを正しい回答と裁定 |

変更前後のテスト関数全文を先に凍結して記録する。テスト名は AGENTS.md の指示どおり維持する。変更前の全文:

```python
def test_round5_chat_answers_brother_question_with_source_and_line(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    code, dialogue = _chat(tmp_path, monkeypatch, capsys,
                           ["兄は誰を呼んだ？"], document=doc)
    assert code == 0
    assert "\nANSWER\n" in dialogue
    assert "答え: 人" in dialogue
    assert "demo.txt:3:" in dialogue
    assert "母が弟に話した人を兄が呼んだ。" in dialogue
    assert "basis_policy.outcome:" in dialogue


def test_round5_chat_keeps_other_unread_question_typed(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    query = "校長はどこで書類を確認した？"
    code, dialogue = _chat(tmp_path, monkeypatch, capsys, [query], document=doc, extra=("--json",))
    assert code == 0
    result = _json_in(dialogue)
    assert result["verdict"] != "ANSWER"
    assert isinstance(result.get("question_cross"), dict)
    assert "QUESTION_NOT_READ" in dialogue
```

訂正後に固定する全文:

```python
def test_round5_chat_answers_brother_question_with_source_and_line(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    query = "兄は誰を呼んだ？"
    code, dialogue = _chat(tmp_path, monkeypatch, capsys,
                           [query], document=doc, extra=("--json",))
    assert code == 0
    result = _json_in(dialogue)
    assert result["verdict"] == "UNKNOWN_UNREAD"
    assert isinstance(result.get("question_cross"), dict)
    assert result["basis_policy"]["outcome"] == "ABSTAIN"


def test_round5_chat_keeps_other_unread_question_typed(tmp_path, monkeypatch, capsys):
    doc = _document(tmp_path)
    monkeypatch.setenv("VERA_PLACEMENT", R8_PLACEMENT)
    query = "校長はどこで書類を確認した？"
    code, dialogue = _chat(tmp_path, monkeypatch, capsys, [query], document=doc)
    assert code == 0
    assert "\nANSWER\n" in dialogue
    assert "答え: place: 職員室" in dialogue
    assert "demo.txt:2: 校長が職員室で書類を確認した。" in dialogue
    assert "basis_policy.outcome: ANSWER_HUMAN_BASIS" in dialogue
```

訂正後にテスト全体を再凍結し、SHA-256 を追記する。実演以外の期待、プロダクト経路、他のテストには手を加えない。

テスト凍結（2026-10-04 11:50:58 JST）: `tests/test_chat_repl.py` SHA-256 は `df7366bee8c707860dd3866f5b1c3f5b06290ed769036fb18c9f4ff6d968088b`。以後このファイルの期待は変更しない。

期待訂正前の実測: `tests/test_chat_repl.py` は 13 件中 11 passed・2 failed。失敗は上記2問で、兄の問いには `UNKNOWN_UNREAD` / `ABSTAIN`、校長の問いには `ANSWER` が実際に表示された。パイプラインの `tee` が pytest の失敗終了コードを隠した最初の実行に続き、`set -o pipefail` 付きで再実行し、終了コード1を確認した。ログは [pre-correction.r2-chat-tests-pipefail.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex_r1/pre-correction.r2-chat-tests-pipefail.log)。

## 訂正後の受入確認（2026-10-04 11:54 JST）

- R1: 時間鍵 `ingest_ms`・`elapsed_ms` を全階層から除いた `cmd_ask` / chat の dict 比較、`question_cross` と `basis_policy.outcome` を含めて合格。R2 の live session でも後段経路が表示された。`cmd_ask`、`cmd_observe`、`cmd_route` の関数ソースは基点 HEAD とバイト一致を確認した。実行前後の `ask`・`observe`・`route` stdout 全体のバイト比較は未採取。
- R2: r8/run2 の実演4問を CLI に入力。先生の回答は1文目の根拠付き、兄の問いは型 `UNKNOWN_UNREAD` / `ABSTAIN` で棄権、係の行先も型付き棄権、校長の場所は `place: 職員室` と2文目の根拠付きで回答。4問で誤った確定回答はなかった。出力は [r2-live-session.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex_r1/r2-live-session.log)。
- R3: `/gen` と `vera observe` の JSON 1行バイト一致、配置 JSON 無しの `NO_MOVE_LICENSED` 表示を含む新規テスト合格。記録は [r2-chat-tests.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex_r1/r2-chat-tests.log)。
- R4: 新規 chat テスト 13/13、指定された質問十字・observe を含む関連テスト 230/230 合格。後者の出力は [r2-related-tests.log](/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W7-chat/codex_r1/r2-related-tests.log)。全体テストと基線失敗集合比較は監査役の担当として未実施。

既知の穴: 同じ実演文書に対し、`vera observe` は `人` を FILLED と観測した一方、質問の十字を通る「兄は誰を呼んだ？」は棄権する。監査役判断2に従いこのラウンドでは読解経路を変更しない。隠しバンクも実行していない。


## W10-f04: `vera read --holes` と `vera ledger`（docs/FUSION.md §6）
- `vera read --text 文 --placement DIR`（`--holes` なし）は `python -m verantyx.semantic_read` と 1 バイトも違わない。`--holes` を付けると、充填物の配置が理由で棄権した文に `holes_status`・`holes`（腕・助詞・語・許す型・役割・位置 `span`）・`partial`・`display`（穴を `Ｘ` で示した文）が付く。
- `vera serve --backend ollama|openai --model M [--api-base URL] [--fill --ledger-file F [--fill-model M] [--no-mask-user-text] [--fill-max-holes N]]`: `--fill` のときだけ候補の口が働き（既定は利用者の文を後段へ渡さない）、`vera.holes`・`vera.ledger_ids`・`testimony_fill` の腕が付く。候補は証言で、記録にも事実の根拠にもならない。
- 候補の不採用の理由（`vera.holes[i].reason`・台帳の `not_adopted` 行）に第 3 ラウンドで `GATE_A_HOLE_WORD_UNPLACED`（穴の語の配置が型を与えない）・`GATE_A_ROLE_SPLIT`（配置の型が 1 つの役割に落ちない。`gate_log` の `split_kind` が `TYPE_NOT_READ`／`ROLES_DIFFER`）・`GATE_B_REREAD_MISMATCH`（型注入の再読が戻らない）を足した（`docs/FUSION.md` §6.6）。1 穴の文は採用されない。
- `vera ledger list|show <id>|confirm <id> --ledger-file F`: 証言の台帳（追記のみ・ハッシュ連鎖）。`confirm` は人が呼ぶ（`store_id`・`confirm_id` を発行）。`promotable` の印までで、配置は変えない。

## W10-f05: `vera chat --layer`
`vera chat --layer <名前|パス>` は環境変数 `VERA_PLACEMENT_LAYER` を設定する（配置の層。docs/COARSE_PLACEMENT.md §12.19）。層が答えるのは基底が決めていない語だけで、`--layer` なし・変数が空のときの出力は変わらない。


## W3-e2: `/read` と `--strict-read`
`vera chat` の `/read <文>` は、既定で段 E2（仮定つきの読み）を使う: 前提（名前の型・造語の述語・未知の名詞の型）だけで止まった文は仮定を明示して読み、それ以外の文は従来の出力のまま。`--strict-read`（または `VERA_READ_MODE=strict`）で従来どおり strict だけで読む。`VERA_READ_MODE` が `strict`／`assume` 以外なら `BAD_READ_MODE`。
