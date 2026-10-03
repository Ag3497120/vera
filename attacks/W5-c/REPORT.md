# W5-c 攻撃報告

## 1. 対象

`docs/BASIS_POLICY.md` の prereg-w5c-r3 §W5-c-r3-1（出所分類）・§W5-c-r3-2（確認記録による格上げ）、§10 J11（最後の確認記録）、§11(a)(c) と、今回の指示にある「人の出典は利用者の文書または明示的な人の origin のみ」「出所不明があれば棄権」「確認済みの文と現在の生成文が一致するときだけ格上げ」「確認 ID は宛先に束縛」を対象にした。

期待値はテスト実行前に [`PREREG.md`](PREREG.md) に記録し、`frozen_tests.sha256` にハッシュを保存した。合成データだけを使った。LLM・ネットワーク・隠し評価バンクは使っていない。

## 2. 命中した攻撃

### A1 — `family: document` が非空の文書引数だけで人の出典になる

- 観点: **(a)**。`apply_to_ask` に存在しない `memo.txt` を文書引数として渡し、`source: fabricated.txt`・利用者文書に無い本文・`family: document`・origin 欠落の合成出典を直接与えた。
- 再現コマンド: 下記の全攻撃テストコマンドで再現する。個別の入力は [`test_attack_classification_binding.py`](test_attack_classification_binding.py) にある。
- 実際の出力: [`reproduction_pytest_final2.txt`](reproduction_pytest_final2.txt) に記録。`basis: HUMAN`、`outcome: ANSWER_HUMAN_BASIS`、`verdict: ANSWER`、本文 `窓が光った。`。
- 期待との差: 渡した文書の実体も本文との一致も無いので人の根拠にならず棄権するはずだが、出典の family と `documents` が非空というだけで答えた。
- 該当箇所: [`basis_policy.py`](../../verantyx/basis_policy.py) は `mode == "round5" and bool(documents)` だけを `user_documents` にし（675–676 行）、その場合 `family == "document"` を無条件で `human` にする（176–177 行）。
- 既知性: 文書の §11(a) が直接呼び出しでのこの穴を明記している（[§11(a)](../../docs/BASIS_POLICY.md)）。今回の「利用者が渡した文書」という受入条件に対しても、文書との本文・ファイル照合は未実装。

### D1 — 確認済み文と現在の生成文が異なっても格上げされる

- 観点: **(d)**。旧文を実際の `ask → --confirm ID yes` 経路で確認・記録し、同じ問いに異なる生成文を与えた。新文は旧文から空白、句読点、または NFKC の差だけを持つ。
- 再現コマンド:

  ```bash
  PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W5-c/test_attack_*.py
  ```

- 実際の出力: [`reproduction_pytest_final2.txt`](reproduction_pytest_final2.txt) に記録。3 例すべて失敗テストとなり、実際の値は次のとおり。

  | 差分 | 確認済み文 | 現在の生成文 | 実際の結果 |
  |---|---|---|---|
  | 空白 | `窓が光った。` | `窓が 光った。` | `ANSWER_HUMAN_BASIS`、`ANSWER`。出力本文は旧文 `窓が光った。`、`confirmed_records_used: 1` |
  | 句読点 | `窓が光った。` | `窓が光った!` | `ANSWER_HUMAN_BASIS`、`ANSWER`。出力本文は旧文 `窓が光った。`、`confirmed_records_used: 1` |
  | NFKC | `コードはＡＢＣです。` | `コードはABCです。` | `ANSWER_HUMAN_BASIS`、`ANSWER`。出力本文は旧文 `コードはＡＢＣです。`、`confirmed_records_used: 1` |

- 期待との差: 今回の指示では完全一致しない文を格上げせず棄権するはずだが、保存済みの別文が人の根拠として出力された。
- 該当箇所: [`basis_policy.py`](../../verantyx/basis_policy.py) の `mine` は問い・はいの状態だけで記録を集め（696–698 行）、元の basis が `GENERATED` なら claim の一致検査なしで人へ格上げし（702–707 行）、その記録の claim を答えとして出す（729–734 行）。
- 既知性と指示間の差: 文書自身が §W5-c-r3-2 で照合を「今回は入れない」とし、§11(c) で同じ穴を明記している（[§W5-c-r3-2](../../docs/BASIS_POLICY.md)、[§11(c)](../../docs/BASIS_POLICY.md)）。従ってこれは新発見ではなく、今回の指示に明記された受入条件と現行文書・実装の間に残る既知の不一致を、正常な確認経路で実行確認したもの。

## 3. 外れた攻撃

再現テストのうち **14 件は通過**（同じ出力記録を参照）。攻撃仮説は成立しなかった。

- **(a) family の揺れ・欠落と偽の human origin**: `Document`・`documents`・family 欠落は `UNKNOWN_ORIGIN`、`user` は `request_text` で `HUMAN` にならない。`human`・`Human`・`user_confirmed` も `HUMAN` にならず未知値として扱われた。`document` でも文書引数なしでは `UNKNOWN_ORIGIN`。
- **(c) 同 root の別 store への確認 ID 再利用**: `store-a` で発行した ID を `store-b` に送ると `CONFIRM_TARGET_MISMATCH`、両方の台帳に書き込みなし。
- **(e) 同じ ID への連続 yes/no**: yes→no は棄権・`UNKNOWN_GENERATED_REJECTED_BY_USER`、no→yes は `ANSWER_HUMAN_BASIS`。最後の記録が有効になった。
- **(f) 出典順序・重複**: 3 出典の全順列と重複の組合せで `UNKNOWN_ORIGIN`・`ABSTAIN` が維持された。重複は件数に反映するが勝者の決定には使われなかった。

## 4. 数

**命中 2 件**（(a) の文書出典の自己申告、(d) の確認文不一致。後者は空白・句読点・NFKC の 3 入力で実行確認）。**外れ 14 件**。全 18 テストの結果は [`reproduction_pytest_final2.txt`](reproduction_pytest_final2.txt) に保存した。初回の直接イベント追記による再現記録は [`reproduction_direct_append_pytest.txt`](reproduction_direct_append_pytest.txt) に残した。
