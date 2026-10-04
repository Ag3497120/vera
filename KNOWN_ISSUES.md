# 既知の制約と穴

この一覧は、チケットで指定された製品上の制約と、docs の読解・配置に関する既知の穴を要約しています。挙動の保証範囲を越えて答えを補うものではありません。

- 英語用の粗い配置はありません。粗い配置が必要な型の経路は、配置データが無い環境では利用できません。
- 副詞は読解対象にしません。副詞を含む文は、その情報を根拠にした質問には答えられない場合があります。
- 名詞句にかかる数量は読みません。数量が出来事の回数を表す形と、名詞句の数量を区別できない場合は棄権します。
- で・に・へ・から の句について、名詞や述語の型だけでは場所・手段・原因・行き先・受け手などの役割を確定できません。生成された述語の枠も役割の証拠にはならず、この経路で許可される読みの範囲は限定されています。
- 文末の相の形に続いて終助詞や連体形がある文は、助動詞の末尾条件に合わず棄権する場合があります。
- 文章の一部が規則に合わない場合、読み取れた断片だけで全体を代表させず、質問の答えを棄権することがあります。
- 同じ固定入力で round5 チャットを複数回実行したところ、返答に含まれる `source_event_sha256` が一致しませんでした。出力全体のバイト単位の安定性は確認できていません。
- `python -m verantyx.cli chat ... --` のように末尾へ単独の `--` を付けると CLI が引数エラーを返します。末尾の `--` を省く対話実行は確認しました。

## 公開 P2 テストの実行範囲

次の同期元候補は公開クローンにない配置ファイル・artifacts・開発 Git 履歴を必要とするため、P2 実行対象から除いています。テストの本文や期待値は変更していません。

- 実配置 r7/r8 が必要: `test_question_cross_w5d.py`、`test_routing_from_text_w5e.py`、`test_semantic_read_w3b4.py`、`test_semantic_read_w3b5.py`、`test_semantic_read_w5e.py`。
- 除外した `test_question_cross_w5d.py` の helper を import: `test_question_cross_w5e.py`。
- 同期しない artifacts を直接読む: `test_basis_policy_w5e.py`、`test_semantic_read_w1a5.py`、`test_semantic_read_w3b1_r4.py`。
- 公開クローンにない開発 Git のコミットを読む: `test_semantic_read_w3b1_i5.py`、`test_semantic_read_w3b1.py`、`test_semantic_read_w3b1_r3.py`、`test_semantic_read_w3b2.py`、`test_semantic_read_w3b3.py`、`test_semantic_read_w3b3_events.py`、`test_semantic_read_w3b3_m1r3.py`、`test_semantic_read_w3b3_r2.py`、`test_event_cross_entry.py`。`test_semantic_read_w3b1_r4.py` も過去コミットを参照します。

依存がコピー後に分かった `test_semantic_read_w3b1.py`、`test_semantic_read_w3b1_r3.py`、`test_semantic_read_w3b1_r4.py`、`test_event_cross_entry.py` はソースのまま保持していますが、上記の理由で実行していません。実行したモジュールと件数は実装報告に記録します。

監査値と測定範囲は [EVAL.md](EVAL.md)、関連する契約・測定記録は docs/READING_SOUNDNESS.md、docs/COARSE_PLACEMENT.md、docs/OBSERVATION.md を参照してください。

## 2026-10-04 の同期で公開側から外したテスト・落ちるテスト
- 開発ツリーの git 履歴（基点コミットの `git show`）に依存する検査は公開リポジトリでは成り立たないので外した: `test_event_cross_entry.py`、`test_semantic_read_w3b1.py`、`test_semantic_read_w3b1_r3.py`、`test_semantic_read_w3b1_r4.py`（開発ツリーでは通っている）。
- `test_contract_lower.py` の 9 件は `/opt/homebrew/bin/node` を固定パスで呼ぶため、node がそこに無い環境で落ちる（同期前から）。
- 開発ツリーの基線に含まれる既知の失敗 14 件（開発側の `baselines/dev_237a43b_failures.txt` と同じ）はそのまま。
