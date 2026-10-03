# W6-a 攻撃報告

## 1. 攻撃対象

対象は `docs/BASIS_POLICY.md` の事前登録 §§2–6、§8、既知の穴 §11 と `verantyx/basis_policy.py` の `classify_sources`・`apply_to_ask`・`AskPolicy.from_args`・確認保存境界。とくに「生成だけが根拠なら事実回答しない」（P2、§8）、「確認 id は同じ問い・同じ環境で再計算され、一致しなければ何も書かない」（§5）を確認した。

## 2. 命中した攻撃

### A1 — 出典の `origin` 欠落／`NULL` が生成文を HUMAN として回答

- 観点: (a), (c)
- 再現コマンド:

  ```bash
  PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W6-a PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -vv -p no:cacheprovider attacks/W6-a/test_attack_basis_policy.py
  ```

- 実際の出力: 合成 `local` 索引から得た生成文 `窓が光った。` の引用について、`origin` を索引上で `NULL` にするか引用 dict から省くと、`kind:"answer"`, `verdict:"ANSWER"`, `text:"窓が光った。"`, `basis_policy.basis:"HUMAN"`, `basis_policy.outcome:"ANSWER_HUMAN_BASIS"` が返った。参考欄 ON・人ありを含む3モード×全フラグ組合せの24試行で再現。出力全文は `pytest.txt`。
- 期待との差: 生成コーパス由来の根拠しかないため、`UNKNOWN_*` / `ABSTAIN` または確認要求になるべきだが、事実回答になった。
- コード: `verantyx/basis_policy.py:151-154` は `origin` が無い／`None` で `family != "user"` の出典を `human` に分類し、`verantyx/basis_policy.py:613-624` が `ANSWER_HUMAN_BASIS` で元の answer を保持する。文書の人間出典限定は `docs/BASIS_POLICY.md:13,168`。同じ欠落元の問題は既知の穴として `docs/BASIS_POLICY.md:218` にも記載されている。

### A2 — 表示された確認 id を別ソブリンへ再利用できる

- 観点: (c)
- 再現: 上記 pytest コマンド内の `test_confirmation_id_from_one_sovereign_cannot_be_replayed_into_another`。
- 実際の出力: `first` を宛先とする確認要求から得た id `730bf04d7f8c087d3c3128ce` を、確認時に環境変数の宛先だけ `second` に変えて `yes` と渡すと、`CONFIRMED_HUMAN_RECORD`, `store_id:"second"`, `wrote:1` が返り、`second:1` に `origin:"human_confirmed"` の事件が追記された。記録は `pytest.txt` にある。
- 期待との差: `first` の確認要求に対する id は `second` に書き込めず、宛先不一致として棄権し、台帳を変えないべき。
- コード: `verantyx/basis_policy.py:419-425` の id 入力は query・claim・生成出典の識別情報だけでソブリンを含まない。`verantyx/basis_policy.py:709-723` は現在の環境から読んだ `view` のソブリンへ追記し、確認要求を出したときの宛先と照合しない。文書は宛先を表示すると定め、同じ環境変数で再計算するとしている (`docs/BASIS_POLICY.md:143-148,224`)。

## 3. 外れた攻撃

- M1: `origin:""` は `non_evidence` と数えられ、`ABSTAIN`。回答にはならなかった。
- M2: `origin:"GENERATED"` も `non_evidence` と数えられ、`ABSTAIN`。大文字値から生成扱いを取り逃がして回答する形は再現しなかった。
- M3: `AskPolicy.from_args` に `FACTUAL` / `Factual` を渡すと `UNKNOWN_BAD_REQUEST_KIND`。未知・大文字の依頼種別が有効な表の行へ正規化される形は再現しなかった。
- M4: 改ざんした id と、別の問いへ持ち越した id は `UNKNOWN_CONFIRM_ID` で拒否され、台帳も空のままだった。
- M5: C の候補 `次郎が花子に資料を渡さなかった。` は極性差で借用されず、`次郎が花子に資料を5冊渡した。` も借用されなかった。`FORM_BORROWED` で新しい否定・数値が回答へ入る形は再現しなかった。
- 追加の対照確認: `related_pytest.txt` の限定実行は **516 passed**。origin が明示された生成だけの出典に対する kind/verdict・3モード・人/参考フラグの組合せ、human+generated の混在棄権、参考欄 ON 時のファイル非変更、壊れた確認引数を確認した。B のファイル sha256 不変は既存の P5 テストで通った。

## 4. 数

命中 **2件**（パラメータ化テストの失敗 **25件**）、外れ **5件**（8実行）。攻撃テスト全体は **25 failed, 8 passed**。追加対照テスト **516件成功**。数値の出力は `pytest.txt` と `related_pytest.txt`。

## 制約・判断記録

- 合成コーパスを使い、本物の LLM・ネットワーク・隠しバンクは使っていない。全体テストは実行していない。
- 攻撃は、CLI が全モードで共通利用する `apply_to_ask` 境界へ合成索引由来の結果を渡して確認した。実運用の外部索引全体や実ユーザー所有者間の UI 操作までは測っていない。
- `origin` の欠落は文書 §11 の既知の穴にすでに記載されているが、今回の受入約束に含まれる「生成コーパスだけなら ANSWER を出さない」と矛盾するため命中として数えた。
- 判断の事前記録と実行前ハッシュは `ATTACK_PLAN.md` と `frozen.sha256`。
