# W2-h 攻撃報告

## 1. 対象

- `docs/AGENT_ROUTING.md` §4 手順3（LLM 証言は残った候補について2回一致、過去決定の再利用を表示）、§6（決定と証言の台帳）、§8 J11（問い合わせ先）。
- 対象実装: `verantyx/agent_routing.py` の証言候補生成、`verantyx/llm_choice.py` のキーと再利用、`verantyx/conductor_run.py` の永続台帳接続。

## 2. 命中した攻撃

### A-01 — 候補説明を変更しても、古い LLM 証言が勝者になる

- 観点: **(a)** 実際の出力が現在の候補説明に対する証言と異なる。
- 再現: `PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W2-h/test_attack_routing_testimony_context_cache.py`
- 実際の出力: `actual agent_id='A', cached=True, provider_asks=2, current reasons favor B`。1回目に A を選んだ2回答が保存され、理由を B 優位に差し替えた2回目は追加照会なしで A が採用され、テストは `1 failed`。
- 期待との差: 証言候補には規則理由と agent の役割・種類・系統・model の要約が `used_in` として渡される。しかしキャッシュキーは質問語と候補 ID だけなので、その説明が変わった2回目も前の入力に対する証言を再利用する。テストの次の2つの provider 返答は B で一致するよう設定したが、そこには到達しない。
- コード: [`agent_routing.py`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h/verantyx/agent_routing.py:959) は理由と要約を候補に追加し、同ファイル 965 行で質問語を構成する。キーは [`llm_choice.py`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h/verantyx/llm_choice.py:373) で `word + candidate terms` のみ、同ファイル 790 行が一致時に旧決定を返す。conduct は [`conductor_run.py`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h/verantyx/conductor_run.py:2245) の永続 `routing_choice.jsonl` を使う。
- 再現テスト: [`test_attack_routing_testimony_context_cache.py`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h/attacks/W2-h/test_attack_routing_testimony_context_cache.py)。コマンドと出力: [`repro_context_cache.txt`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h/attacks/W2-h/repro_context_cache.txt)。

## 3. 外れた攻撃

- A-02（同点順序）: 行・agent の並べ替えで勝者が変わるケースを確認。該当順序試験は通り、再現できなかった。
- A-03（証言の不一致・失敗・無効回答）: 1回目/2回目の不一致、例外、拒否、候補外回答を確認。いずれも型付き `NONE` になり、決定は出なかった。
- A-04（名札と関係の矛盾）: `same` の推移閉包に `distinct` を加えた場合を確認。順序を変えても `LINEAGE_CONFLICT` で拒否された。
- A-05（role なし規則と独立条件）: verify 要求への暗黙の独立、明示 `independent_of=none` の waiver、role なし規則からの循環を確認。期待どおり適用・拒否され、別の循環や抜けは再現できなかった。
- A-06（未申告 concurrency）: 実行中 agent が無い場合は通り、`in_use` がある場合は `CONCURRENCY_UNDECLARED` で除外された。
- A-07（`essence()`）: 既存の名前変更・除外・異なる勝者の比較を確認。期待どおりで、反例を再現できなかった。
- A-08（DSL の ID / 系統名境界）: DSL で表せない ID・系統名を確認。`MALFORMED_ROW` になり、誤受理は再現できなかった。
- 上記の確認には関係する routing テストだけを指定して実行し、`19 passed`。

## 4. 数

命中 **1**、外れ **7**。
