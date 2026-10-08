# W2-h2 攻撃報告

## 1. 攻撃対象

- `docs/ROUTING_FROM_TEXT.md` §0 / J1（読めない単位があれば全件棄権）、§8 / J10（呼び名でない句をエージェントにしない）、§10（`MAPPED` 以外は門で止める）。
- 同 §3・§4 の追記処理、§18 D13（上書き）および §16 の既知の制限。
- 実装の約束: 人間が名指ししていない呼び名を作らない。追記の意味を読み違えて以前の宣言を捨てない。

## 2. 命中した攻撃

### W2H2-A01 — 普通名詞の主語を呼び名として登録して振る

- 観点: **(b)** 普通名詞の主語に振る。
- 入力: `attacks/W2-h2/attack_01_common_noun.md`（`The team reviews code.`）
- 再現コマンド:

  ```sh
  PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h2 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.cli route --explanation attacks/W2-h2/attack_01_common_noun.md --task '{"role":"review","kind":"review","size":"medium"}'
  ```

- 実際の出力（主要項目。完全な標準出力は `repro_01.out`）:

  ```json
  {"decision":"route","agent":"team","basis_kind":"explicit","evidence":["The team reviews code."],"reading":{"by_status":{"MAPPED":1}},"records":{"agents":[{"id":"team"}]}}
  ```

- 期待との差: `team` は `The team` の普通名詞句で、人間が名指ししたエージェント名ではない。読めない・名前と確定できないものとして棄権すべきところ、唯一の受け皿にして `team` へ振った。
- 該当箇所: `verantyx/routing_from_text.py:493-516` は英語の限定詞で始まる句と複数語名は止めるが、読解器が限定詞を落として返す一語の普通名詞は名前として通す。記録・規則にするのは同 `verantyx/routing_from_text.py:969-1003`。文書も §16 でこの既知の制限を認めている（`docs/ROUTING_FROM_TEXT.md:654`）。

### W2H2-A02 — `Addendum` を訂正扱いし、先行宣言を置き換える

- 観点: **(a)** 追記の意味を取り違え、先行する割り当てを落とす。
- 入力: `attacks/W2-h2/attack_02_addendum.md`（`Haru reviews code.` / `Addendum: Luna reviews code.`）
- 再現コマンド:

  ```sh
  PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h2 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.cli route --explanation attacks/W2-h2/attack_02_addendum.md --task '{"role":"review","kind":"review","size":"medium"}'
  ```

- 実際の出力（主要項目。完全な標準出力は `repro_02.out`）:

  ```json
  {"decision":"route","agent":"Luna","evidence":["Addendum: Luna reviews code."],"records":{"agents":[{"id":"Luna"}]},"relations":[{"id":"R001","names":["Haru"],"superseded_by":"R002"},{"id":"R002","names":["Luna"],"override":true}],"reading":{"auto_resolved":1}}
  ```

- 期待との差: `Addendum` は追加の宣言で、訂正・置換を述べていない。両方を保持して少なくとも Luna だけへ一意に振らないべきだが、Haru の宣言を `superseded_by` にし、根拠も Luna の文だけにして Luna へ振った。
- 該当箇所: `verantyx/routing_from_text.py:221-222` が `addendum` を上書き標識に含め、同 `:310-328` が標識を外して `override` にし、同 `:891-915` が同じ範囲・同種の古い関係を自動で supersede する。文書 §16 / D13 も「追記」が追加の意味なら同点が正解と既知の制限を記載（`docs/ROUTING_FROM_TEXT.md:653`）。

## 3. 外れた攻撃

- **W2H2-M01 否定の脱落:** `Haru does not review code.` は `MAPPED` の禁止関係になり、経路は `undecided / RECORD_REFUSED`。肯定の割り当てにはならなかった。
- **W2H2-M02 比較の向き:** `Luna is more suited to verification than Haru.` は `UNREAD`（`EN_UNREAD:infinitive complement` / 比較の標準が未対応）で門が止まった。
- **W2H2-M03 連結文書の矛盾:** `Haru reviews code.` に `Haru does not review code.` を続けると両単位 `CONTRADICTION`。別々の Haru/Luna が同じ role の受け皿を宣言した場合も `RECORD_REFUSED:DUPLICATE_FALLBACK`。いずれも誤振りなし。
- **W2H2-M04 task の形:** `running` の map / list / scalar はいずれも `ALL_EXCLUDED` に正規化。`already_used` の scalar / list も同じ正規化と決定。形式外の `already_used` 配列・負の `running` 数は CLI が終了コード 2、`BAD_TASK`。
- **W2H2-M05 系統関係:** `ハルとルナは同じ系列だ。` は明示どおり `same`。`ハルとルナは別会社だ。` は `AMBIGUOUS_RELATION` となり、`distinct` を記録しなかった。

## 4. 実行確認と数

失敗する攻撃テストを指定 Python で実行:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W2-h2 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider attacks/W2-h2/test_attack_routing_from_text.py -q
```

実行結果: `2 failed in 0.53s`。A01 は実際に `('route', 'team')`、A02 は `('route', 'Luna')` が安全側の期待値アサーションを破った。

**命中 2、外れ 5**
