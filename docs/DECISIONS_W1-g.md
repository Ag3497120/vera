# W1-g の決定 A・B・C

切り分け（`docs/FAILURE_TRIAGE_W1-f.md`）の「判断が要る」のうち 3 件を、監査役が原則から決めた。
オーナーが後で覆せるよう、決定として記録する。原則の語彙は切り分け §11 の P1〜P8 に従う。
数値は `artifacts/w1-g/` の出力ファイルを括弧で添える（このチケットで測ったものだけ）。

同じチケットで直した製品の不具合 B03・B04・B05 は、決定ではなく不具合の修正なので、この文書の末尾に
「付記」として差分の要点だけを書く（詳細は実装の報告）。

## 決定 A: 再実行できる証拠が無いときの検証の記録を FAIL にしない

### 内容
- 検証の記録の型に `UNVERIFIED`（「確かめられなかった」）を足す。`PASS`（確かめて合格）、`FAIL`（確かめて不合格）とは別の型。
- `ProjectFrame.record_verification` は `PASS` / `FAIL` / `UNVERIFIED` を受ける。ほかの検査（検証者と申告者の別、
  テンプレート、supersede）は同じに掛かる。拒否の文言は `verification result must be PASS, FAIL or UNVERIFIED`。
- 読み手が `UNVERIFIED` を有効な記録として読む。`ProjectFrame.verify_claim` は `UNVERIFIED` の記録を
  `ESCALATE`（`UNVERIFIED: independent verification could not be confirmed ...`、欠けているもの: re-runnable verifier evidence）
  で返す。「failed」とは言わず、完了にもならず、記録が無いものとして `ASK_VERIFIER` に戻ることもない。
- 検証役に返させる値（`_ask_verifier` の `result_schema`）は `PASS` / `FAIL` のまま。`UNVERIFIED` は検証役の判定ではなく、
  決定的な再実行の状態の記録。

### 根拠の原則
- P2「分からないことと偽であることを混ぜない」: 再実行できる証拠が無いことは、不合格の証拠ではない。
- P5「読み飛ばしたものを黙って捨てない」: `_valid_verification` が `UNVERIFIED` を知らないと、記録が黙って無視される。

### 変えたファイルと関数
- `verantyx/conductor.py`: モジュール定数 `_VERIFICATION_RESULTS`、`ProjectFrame.record_verification`（受理）、
  `ProjectFrame._valid_verification`（有効性）、`ProjectFrame.verify_claim`（`UNVERIFIED` の分岐を `FAIL` の分岐の直後に追加）。
- テスト（新規）: `tests/test_w1g_decision_a_unverified.py`。

### 覆す場合に戻す箇所
- `conductor.py`: `_VERIFICATION_RESULTS` を `{"PASS", "FAIL"}` に戻し、`record_verification` の拒否文言を戻し、
  `verify_claim` の `unverified = [...]` の分岐（4 行）を消す。影響を受けるテストは `tests/test_w1g_decision_a_unverified.py` の全体。

### 実装しなかった部分とその理由（生産側）
- `verantyx/verifier_agents.py` の `run_verifiers` が記録する値（現状は再実行できなかった場合も `FAIL`）を `UNVERIFIED` にする変更は、
  ツリーに入れていない（W2-b が同ファイルを変更中。チケットの指示）。差分を `artifacts/w1-g/decision_a/verifier_agents_record_result.diff` に残した
  （再実行器があり、検証役どうしが一致し、少なくとも 1 項目の再実行で観測値が期待と違ったときだけ `FAIL`。ほかは `UNVERIFIED`）。
- 切り分けの対象テスト n=106（`tests/attack/test_verifier_agents_fabrication.py::test_run_verifiers_records_references_with_their_verifier_identities`）は
  決定 A を入れても通らない。188 行（`result == ...`）は `UNVERIFIED` への 1 行差分（`test_n106_expectation.diff`）で通るが、
  190 行以降が旧い形の記録（`result`・`evidence_ref` のキー）を期待し、現行は `reported_result`・`opinion`・`items` のキーを持つ
  （`artifacts/w1-g/decision_a/n106_after_diffs.txt`）。これは決定 A ではなく期待値が古い側の問題（切り分けの順位 11）で、このチケットでは変えない。
  テストの期待値はツリーでは変えていない。

### 衝突の一覧
- `artifacts/w1-g/decision_a/conflicts.md`。生産側の差分を当てると、既存の 2 件が新しく落ちる（`artifacts/w1-g/decision_a/new_failures.txt`）:
  `tests/test_verifier_agents.py::test_passing_verdict_without_rerunnable_evidence_is_unverified`（127 行が `FAIL` を固定）、
  `tests/test_verifier_agents.py::test_unsafe_or_missing_artifact_cannot_complete_task[artifact:missing.json]`（263 行が `FAIL` を固定）。
  conductor 側（ツリーに入れた分）は verifier／conductor 系のテストで新しい失敗を出さない（全体テストの結果は実装の報告）。

### 許可パスの外に残った影響
- `verantyx/verifier_agents.py` は現状どおり再実行できない場合も `FAIL` を書く。決定 A の目的（「確かめられなかった」と「不合格」を分ける）は、
  生産側の差分が入るまでは記録の上では満たされない（読み手は `UNVERIFIED` を扱えるようになっただけ）。

---

## 決定 B: 有効でない supersede 事件を黙って落とさない

### 内容
- 置換記録が在るのに、その記録のポインタ（`supersedes`）が事件の対象を指さない supersede 事件を、型付きで保持し、件数を報告する。
- `verantyx.memory_merge.merge_report(left, right)`（公開 API。`__all__` に追加）が `MergeReport` を返す:
  `events`（`merge_logs` と同一の出力）、`supersedes`（`(old, new)` の昇順の `SupersedeStatus`: `status` は `OPERATIVE` / `PENDING` / `NONOPERATIVE`、
  `reason` は `REPLACEMENT_POINTER_MATCHES` / `RECORD_POINTER_ONLY` / `REPLACEMENT_NOT_PRESENT` / `REPLACEMENT_POINTER_ABSENT` / `REPLACEMENT_POINTER_MISMATCH`、
  `declared`）、`counts`（status ごと。0 件も出す）、`declared_events`・`retained_events`・`dropped_events`（出力を照合して数えたもの。固定値ではない）。
  「ポインタが無い」と「ポインタが別の記録を指す」は別の reason。
- `merge_logs` と `merge_report` は同じ経路（`_merge` → `_analyze`）で出力を作る。
- `Memory.supersede_accounting()`（公開メソッド）: 適用した件数、適用しなかった事件（`nonoperative`）、記録待ちの事件（`waiting_for_record`）を、
  理由の型つきで返す。`records` と `superseded` だけを持つ見かけの `Memory`（`Memory.__new__(Memory)`）でも例外にならない。
- 一度の merge の報告のうち、`declared`・OPERATIVE の reason・`declared_events` の件数は、merge を段階に分けたときに変わりうる
  （merge の出力は、置換記録のポインタから導いた事件を宣言された事件として書き出すので、次の merge で `declared=True` に見える）。
  関係（old, new）と status、`counts`、`dropped_events` は段階に依らない（`tests/test_w1g_decision_bc_supersede.py::test_status_of_each_relation_does_not_depend_on_merge_order`）。

### 根拠の原則
- P5「自動で棄却したものも数えて記録する」: 黙って落とさず、保持した件数・落とした件数を測って報告する。
- P2: 「ポインタが無い」「別の記録を指す」「記録がまだ来ていない」を別々の型で返す。

### 変えたファイルと関数
- `verantyx/memory_merge.py`: `SupersedeStatus`、`MergeReport`、`SUPERSEDE_STATUSES`、`_analyze`（旧 `_state` の本体。`_state` は薄い包み）、`_merge`、`merge_report`、`merge_logs`（`_merge` 経由）。
- `verantyx/memory_frame.py`: `Memory._apply`（supersede 事件の分類）、`Memory._settle_supersede`、`Memory.supersede_accounting`、`Memory._supersede_state`（`_supersede_log`・`_waiting` を最初に使うときに作る。`Memory.__init__` では作らない。第 2 ラウンドの修正: `Memory.__init__` を通らずに作られる子クラス `project_frame._ExchangeMemory`（公開関数 `decision_from_exchange` が `memory` 省略時に使う）が `write` で `AttributeError` になる回帰を、この関数で直した）。
- テスト（新規）: `tests/test_w1g_decision_bc_supersede.py`。

### 覆す場合に戻す箇所
- `merge_report`・`SupersedeStatus`・`MergeReport`・`_merge` を消し、`merge_logs` を `_state(_read_events(left) + _read_events(right))` の第 3 要素を返す形に戻す。
  `Memory.supersede_accounting`・`_supersede_state`・`_settle_supersede` を消す。影響を受けるテスト: `tests/test_w1g_decision_bc_supersede.py` の B の節。

### 実装しなかった部分とその理由（構造検査）
- 切り分けの対象テスト n=50〜52（`tests/attack/test_memory_merge_injection.py::test_instruction_payload_cannot_hide_a_dangling_supersession`、
  `::test_instruction_text_does_not_make_a_supersession_cycle_valid`、`tests/attack/test_memory_merge_limits.py::test_active_records_reject_dangling_supersession_reference`）は、
  決定 B の文言（型付きで保持し件数を報告）では通らない。3 件は有効でない事件も循環・宙に浮いた参照の `ValueError` にすることを期待しており、
  これは切り分け §8-2 の別の選択肢（構造検査をする）に当たる。監査役は §8-2 で「型付きで保持して件数を報告する」を選んだので、構造検査はツリーに入れていない。
- 変種（非有効な事件も循環検査と `active_records` の宙に浮いた参照の検査に入れ、退役はさせない）を `artifacts/w1-g/decision_b/structural_variant.diff` に残し、
  一時複写で測った（`artifacts/w1-g/decision_b/structural_variant.txt`）: n=50〜52 の 3 件が通り、memory・conductor・revalidate 系のテスト群で新しい失敗は 0 件
  （`structural_variant_new_failures.txt`）。オーナーが構造検査を選ぶなら、この差分を当てる。

### 許可パスの外に残った影響
- `verantyx/project_frame.py::_jsonl_active` と `verantyx/conduct_ask.py::_view_from_jsonl` は、ポインタを確かめずに、どの `supersede` 事件でも対象を退役させる。
  決定 C で有効でない事件が merge の出力に残るので、その出力をこれらに読ませると、`Memory` が退役させない記録が退役する。直していない（許可パス外）。

---

## 決定 C: supersede 事件は merge の出力に残す

### 内容
- `merge_logs` は、置換記録が在るがポインタが合わない（無い・別の記録を指す）事件を、`op: "supersede"` のまま、payload を変えずに出力に残す。
  `links` には入れない（`active_records`・`conflicts`・循環検査は従来どおり。退役させない）。
- `Memory` は supersede 事件を、置換記録が在り、そのポインタ（文字列、または list／tuple）が対象の id を含むときだけ適用する。
  置換記録がまだ無い事件は記録待ちとして持ち、記録の `write` を適用するときに照合する（事件ごとに 1 回。全体の走査し直しはしない）。
  ポインタの値が不正（空でない文字列以外の要素を含む）なときは例外にせず適用しない（理由 `REPLACEMENT_POINTER_INVALID` で数える）。
- `Memory.superseded` の意味（適用済みの事件だけ）と型（`dict[str, str]`）は変えない。`pending_supersede` の事件も `supersede` と同じ扱いにした
  （従来は `Memory` が黙って無視していた。記録が届いてポインタが合えば適用される）。

### 根拠の原則
- 「削除しない。退役は追記」: 有効でない事件も消さず、出力に残す。型は出力の事件ではなく `merge_report` の分類に持たせる（出力の形は n=48 が固定している）。
- P2: 「適用された」と「適用されなかった」を `superseded` と `supersede_accounting` で別に持つ。

### 変えたファイルと関数
- `verantyx/memory_merge.py`: `_analyze`（NONOPERATIVE の分岐）。
- `verantyx/memory_frame.py`: `Memory._apply`、`Memory._settle_supersede`、`Memory._supersede_state`（上の B の項を参照。`__init__` を通らない `Memory` でも `_apply` が動くようにした）。
- 対象テスト: n=48 `tests/attack/test_memory_merge_differential.py::test_canonical_order_and_exact_duplicate_removal`（通る）、相手の
  `tests/test_memory_merge.py::test_mismatched_supersede_stays_nonoperative_after_serialize_and_reopen`（通ったまま）。

### 覆す場合に戻す箇所
- `memory_merge._analyze`: `if old in pointers: ... else: ...` の else 側（NONOPERATIVE の分岐の `supersede_events.add`）を戻し、有効でない事件を出力に加えない。
  `memory_frame.Memory._apply`: `supersede` の分岐を `self.superseded[ev['id']] = ev['by']` に戻す。
  影響を受けるテスト: n=48（通らなくなる）、`tests/test_w1g_decision_bc_supersede.py` の C の節。

### 許可パスの外に残った影響
- 決定 B の節の `_jsonl_active`・`_view_from_jsonl` に加えて、`verantyx/conductor_run.py::_memory_events` は `memory.superseded`（適用済みの事件だけ）から事件を書き出すので、
  有効でない事件は書き出さない（`Memory` を経由する経路では、有効でない事件は出力に残らない）。直していない（許可パス外）。

---

## 付記: 不具合 B03・B04・B05（決定ではない）

- B03（`semantic_unknown_choice._JSONOptionResolver._prompt`）: 語は JSON 化済みなので `\` を倍化しない。`「」` と Cc/Cf/Zl/Zp だけを `\uXXXX` にする。
  切り分けの差分は `「」` だけで、`json.dumps(ensure_ascii=False)` が生で残す U+0085・U+007F が指示文に入る別の入力で同じ誤りが残るため、規則を広げた。
- B04（`memory_frame.Memory.ask` / `_witness_supports`）: 1 回の問いで `check_witness` を記録ごとに 1 回だけ呼び、その状態を STALE の除外と支持の判定に使う。
  file hash の形の規則は `_file_hash_shape_ok` に 1 つにまとめた。`git_commit` は形だけにしない（git が起動できないことを「支持あり」にしないため）。
  `RevalidatingMemory.ask`（`memory_revalidate.py`、許可パス外）の `text_in_file`・`git_commit` の 2 回読みは残る（`artifacts/w1-g/b04/readcount_after.txt`）。
- B05（`semantic_unknown.unknown_candidates`）: 作業量の語を `_source_words`（`runs()` の語 ＋ 空白・日本語の文字で区切った断片）にした。平仮名・和文の約物は語に数えない。
