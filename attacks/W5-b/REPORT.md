# W5-b 攻撃第2波・報告

## 1. 対象

- `docs/CONDUCT_ASK.md` §16.1、§16.2 #1–#4、§16.4–§16.6: manifest 照合、属性の照合、依頼の承認要求。
- `docs/ROUTING_FROM_TEXT.md` D17・D20: 普通名詞の主語、追記の既定。
- `docs/OBSERVATION.md` §5: 合流要素が持つ座標の完全性。
- `docs/COARSE_PLACEMENT.md` §11.9: NFKC・かな変種。
- `tests/test_sovereign_w5b.py`: promote/release の競合と一意制約。

事前登録 `PREREG.md` の SHA-256 は `3bd91cd5c55949676e3600dec5a463a9b5a6ec9aabd2c0b67da8c2157c97dc39`。攻撃テストの実行版は `ATTACK.sha256` に固定。mapper はローカル scripted fake、配置データと観測データは constructed fixture。実 LLM/provider は起動していない。

正式再現コマンド:

```bash
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -s --basetemp=attacks/W5-b/pytest-temp-confined attacks/W5-b/test_attack_w5b_wave2.py
```

実出力: [`pytest-confined.log`](pytest-confined.log)、SHA-256 `20a62dbd5d1a1445a7262dfbbfcd3533b03bd313afb56992e20b7dcd981ef96a`。結果は **2 failed, 10 passed**。2件の失敗が以下の命中で、失敗したテスト入力は実行して確認済み。

## 2. 命中した攻撃

### R1 — (a) 配置なしの日本語普通名詞が agent として route される

- 入力: `チームがテストを書く。`。通常の `semantic_read` を使い、placement lookup は既定の `stub-no-placement/1`。
- 実出力 (`pytest-confined.log`):

```text
OBS R1 {"agent": "チーム", "agents": [{"adapter": "fake", "basis": {"kind": "declared_text", "line": null, "source": "attack.md", "witnesses": ["チームがテストを書く。"]}, "concurrency": null, "effort": null, "id": "チーム", "kinds": null, "lineage": null, "model": null, "note": null, "roles": null}], "common_noun_check": {"checked": 0, "flagged": 0, "introduced_by_naming": 0, "lookup": "stub-no-placement/1", "not_checked": 1}, "decision": "route", "reasons": [], "unit_status": "MAPPED"}
```

- 期待との差: 「普通名詞を呼び名にしない」なら未決定で route しない。実際には `not_checked: 1` と数えながら、その不明状態を止めず `チーム` を agent にした。
- コード: `verantyx/routing_from_text.py:920-936` は配置の direct 証言が無い場合 `None` を返し、`950-959` がその読みを止めずに残す。D17 の2種類の証言の外側は対象にならない。**この日本語・配置なしの穴自体は文書にも既記載** (`docs/ROUTING_FROM_TEXT.md:779-780`); 今回の出力で再実証した。

### R2 — (a) `やっぱりそのまま` の「そのまま」を無視し、追記を置換として扱う

- 入力: `実装はハルに任せる。` の後に `追記：やっぱりそのまま、実装はハルに任せる。`。置換判定だけを見るため、読み取り結果は scripted `constructed` input で固定。
- 実出力 (`pytest-confined.log`):

```text
OBS R2 {"additions_kept": 0, "auto_resolved": 1, "statuses": ["MAPPED", "MAPPED"], "superseded_by": ["R002", null]}
```

- 期待との差: `そのまま` は現状維持を述べる文脈だが、既存関係 `R001` が `R002` に supersede された。今回は同じ agent の反復なので route 先自体の差は出ないが、追記の扱い・自動解決の記録が誤る。
- コード: `verantyx/routing_from_text.py:862-875` は `やっぱり` を NFKC 後の部分文字列として見つけるだけで、`そのまま` による否定・維持を検査しない。supersede は `1002-1026`。

## 3. 外れた攻撃

各出力は `pytest-confined.log` にある。

| ID | 試したもの | 実出力と外れた理由 |
|---|---|---|
| M1 | 台帳 JSONL の行順を逆転、manifest は据え置き | `escalate / MAPPING_UNSETTLED / LEDGER_INTEGRITY`、answer `null`、replay `null`。鎖検査で再生しない。 |
| M2 | 末尾の `map_*` 行を重複追記、manifest は据え置き | 同じく `LEDGER_INTEGRITY`。重複 seq を再生しない。 |
| M3 | manifest 対象の末尾行を切り詰め | 同じく `LEDGER_INTEGRITY`。切り詰めても回答にしない。 |
| K1 | `ヒナタ丸`=`ARTIFACT`、`ひなた丸`=`GROUP_ORG`、両方 direct/DECIDED | 各綴りは自分の型を direct で返し、双方 `KANA_VARIANT_DIFFERS`。相手の型を借りない。 |
| S1 | 2 promote と3つ目のプロセスの release を同時開始、5反復 | 全5反復で `status=RELEASED`、`active=0`、`promotions=3`、`unique_ids=3`。release 後に active は残らない。 |
| O1 | 2座標を持つ合流要素から1座標を欠落 | `MISMATCH/COORDS_INCOMPLETE`。欠落を検出。 |
| A1a | `What’s the language of the invoice archive?` | `FRAME_SILENT/TERM_IN_WIDER_PHRASE`、`ESCALATE:ATTRIBUTE_NOT_IN_RECORD:language`、answer `null`。 |
| A1b | `Which language for the invoice archive?` | 同じく `ATTRIBUTE_NOT_IN_RECORD:language` で answer `null`。 |
| A2 | `Which billing-language should we use for the invoice archive?` | `ATTRIBUTE_NOT_IN_RECORD:billing-language` で answer `null`。複合語を既知語に縮めていない。 |
| Q1 | `ログを削除しないでください。` | `escalate/VOCAB_UNMAPPED/NO_ROLE`、answer `null`。期待した「削除する」という回答は出ず、承認・実行許可にもならない。 |
| Q2 | `もし可能なら、ログを削除してください。` | `escalate/HUMAN_APPROVAL_REQUIRED/BUILTIN_PROTECTED`、answer `null`。 |

いずれも受入上の誤答を実行確認できなかった。既存 `tests/` の削除・skip/xfail 化・期待値改変は今回の差分では発見せず、開始時の `git status` は空、最終時も未追跡の `attacks/W5-b/` だけだった。

## 4. 数と手順の記録

- 命中 **2**、外れ **11**（13個の入力プローブ。Q1/Q2 は1つの pytest ケースにまとめた）。
- 製品コード・既存テストは変更していない。全体テスト、ネットワーク、本物の LLM は使っていない。
- 最初の `pytest.log` は攻撃 harness が `ChoiceLedger` を直接生成して壊れた台帳を公開入口より先に開き、さらに agent 表示属性を誤指定したため、4失敗・8成功になった。この結果は採用せず、入力は維持して公開 `conduct_ask` 入口と正しいフィールドを使うよう harness を修正した。`pytest-rerun.log` は修正中の追加探索（台帳を再封印した行の入替・重複）で、事前登録外のため件数に含めない。正式な M1/M2 入力を再実行したものが `pytest-final.log` と `pytest-confined.log`。
- 初期3回の pytest は既定 `tmp_path` が OS の temporary directory を使った。削除はせず、最終の正式実行は `--basetemp=attacks/W5-b/pytest-temp-confined` で生成物を攻撃ディレクトリ内に置いた。この一時領域の場所は手順からの逸脱として記録する。
- R2 は scripted `constructed` reading で置換判定を隔離した結果であり、自然言語 reader がその文を同じように解析する証明ではない。R1 は既定 reader の実出力。
