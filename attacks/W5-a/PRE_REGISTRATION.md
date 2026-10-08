# W5-a 攻撃波 2 事前登録

登録日時: 2026-10-03 09:36 UTC

## 対象

- `docs/READING_SOUNDNESS.md` §10A: K62（態の正の証拠）、K63（`unsupported` と `readable`）、K64（経路の `を` と動作主証拠）。
- `docs/READING_CONVENTIONS.md` §9.2: unsupported 節は読解を止める。唯一の例外は、unsupported 理由が `copula value is a predicate phrase` だけで、supported な比較節に答えられている copula の別読み。
- `docs/EVENT_CROSS.md` W5-a A1/A2: 入力 Mapping の鍵挿入順によらない JSON バイト列。
- `docs/CONDUCT_ASK.md` W5-a A-01 と `docs/AGENT_ROUTING.md` §6/J27: 語・候補・候補ごとの `used_in` 文脈が一致するときだけ証言を再利用する。

## 事前登録した検査式

1. **日英の文数**: 読解入口に通す自作文を日本語 100 文、英語 80 文用意する。全件の全文を fixture に固定し、重複文は文数に含めない。
2. **日本語の態 (K62)**: 受身形・動作主句なしの 20 文は、読める結果に `voice=passive` があれば命中。明示的な動作主句（`によって` または対象述語で動作主と決まる `に`）を持つ 20 文は、読める結果が `voice=passive` でなければ過剰棄権として別集計する。受身以外の能動文 20 文は、受身を出力したら命中。
3. **英語の態**: 明示的な能動主語を持つ能動 40 文と、受動態 40 文（by-phrase 有無を半数ずつ）の expected voice を固定する。読める結果の voice が手動 gold と異なれば命中、正しい passive が abstain したら過剰棄権として別に数える。
4. **unsupported 不変条件 (K63)**: すべての返却結果で `readable=true` かつ `unsupported` が非空なら、各 unsupported 節の理由が `['copula value is a predicate phrase']` と完全一致し、supported 節のうち少なくとも 1 節が比較である場合に限って許容する。それ以外の同居を命中とする。各言語 20 文以上に、通常文・比較・解釈不能な節を混ぜて調べる。
5. **日本語の `を` 役割 (K64)**: 人名/人の役割語、動物、組織名、乗り物、自然現象の主語に、経路動詞または目的語動詞を組み合わせた 40 文を固定する。`readable=true` のときは、手動 gold の agent/patient が同じ値・同じ役割で存在することを要求する。曖昧な経路/目的語または正の agent 証拠がない文を agent/patient として確定した場合、または手動 gold の明示的な agent/patient を捨てた場合を命中とする。語の追加や分類補正はしない。
6. **event JSON 鍵順**: 同じ内容の読解 Mapping で、トップレベル・節・役割・入れ子属性・relation・abstain の挿入順だけを個別に反転し、`json.dumps(build_crosses(x).to_dict(), ensure_ascii=False)` の UTF-8 バイト列が基準と一致するか調べる。一致しないと命中。
7. **証言再利用の鍵**: 同じ語・候補で `used_in` の一部だけ（各候補の各行の本文、1 行の追加/削除、複数行の順序）を変える場合は、再照会されることを要求する。同一文脈で候補順だけを変える場合は再照会されないことを要求する。変更後も cache hit なら命中。

## 検査後の分類

- 命中は、再現テストが assertion failure となり、実際の返却値または ask 数で約束違反を示したものだけ。
- 期待した性質を保った攻撃は外れとして記録する。
- K62 の過剰棄権は、正の動作主証拠があるのに unreadable となった文を別件数にし、誤った voice 出力の命中数と混ぜない。
- 期待一覧の SHA-256 は検査入力を初めて実装に通す前に保存し、その後は変更しない。
