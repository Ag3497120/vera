# W5-a 攻撃第 2 波 報告

## 1. 攻撃対象

- `docs/READING_SOUNDNESS.md` §10A K62（動作主句なしの passive）、K63（`readable` と `unsupported`）、K64（`を` の patient と動作主証拠）。特に K64 の第 3 ラウンド規則。
- `docs/READING_CONVENTIONS.md` §9.2（比較の copula 代替読みだけが許す例外）。
- `docs/EVENT_CROSS.md` W5-a A1/A2（JSON の鍵順不変性）。
- `docs/CONDUCT_ASK.md` W5-a A-01、`docs/AGENT_ROUTING.md` §6/J27（候補ごとの `used_in` を含む証言再利用鍵）。
- 入力 fixture/gold は `PRE_REGISTRATION*.md` に日時つきで先に登録し、各テストファイルを最初の実行前に SHA-256 凍結した。hash は `FIXTURE*.sha256`。

## 2. 命中した攻撃

**H1 — K64 の意味上の正の人・組織証拠を落として棄権 (d: 過剰棄権)。命中 3 文。** 基点 `2732274^` は各文を agent/patient で読んだ。統合後は同じ各文を `AGENT_EVIDENCE_MISSING:<主語>` で棄権した。

| 文 | 基点の実際の読み | 統合後の実際の出力 |
|---|---|---|
| `尼僧が月報を発行した。` | `readable=true`, `発行する`, `agent=尼僧`, `patient=月報` | `readable=false`, `AGENT_EVIDENCE_MISSING:尼僧` |
| `複数の人物が会報を発行した。` | `readable=true`, `発行する`, `agent=複数の人物`, `patient=会報` | `readable=false`, `AGENT_EVIDENCE_MISSING:複数の人物` |
| `会社が試験機を公開した。` | `readable=true`, `公開する`, `agent=会社`, `patient=試験機` | `readable=false`, `AGENT_EVIDENCE_MISSING:会社` |

再現コマンド:

```sh
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q --basetemp=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w5a-wave2-r4 attacks/W5-a/test_attack_w5a_wave2_r4.py
```

実際の結果: `F [100%]`; `AssertionError: {'K64_positive_evidence_over_abstentions': [...]}` に上記 3 文それぞれの基点 clause と現行理由が出た。終了値 1、`1 failed`。テストは基点の checked-in `semantic_read.py` をこの clone の git からメモリ上で読み、gold と一致することを確認してから現行入口と比較する。

期待との差: 日本語では「尼僧」「複数の人物」「会社」は人・集団・組織を動作主とする読みが明白で、基点もその読みを返した。現行規則は人の証拠を閉じたクラスに限定し、これらをすべて証拠なしとして誤棄権する。該当箇所は [semantic_read.py](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W5-a/verantyx/semantic_read.py:466) の `not R._is_person_phrase(...)` と `_object_frame_known` 条件、棄権行 [semantic_read.py](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W5-a/verantyx/semantic_read.py:469)。契約の記述は [READING_SOUNDNESS.md](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W5-a/docs/READING_SOUNDNESS.md:900)。この報告は誤った agent/patient 出力ではなく、指定どおり「正の意味証拠があるのに棄権」の別勘定である。

## 3. 外れた攻撃

外れは攻撃軸/fixture 単位で **M=7**。各文・条件の出力を記録し、通らなかった反例を命中扱いにしていない。

1. **K62: 動作主句なしの日本語受身 20 文＋能動 20 文。** `test_ja_no_agent_passives_and_active_controls_do_not_gain_a_false_passive` は通過。受身形でも動作主句のない文に `readable=true` はなく、能動文で passive を返した出力もなかった。
2. **K62: 明示的な動作主と英語の能動/受身。** 読めた文に voice の誤分類はなかった。最初の日本語 by-phrase 10 文は、述語が入口で未対応のため 9 文が `UNCOVERED_PREDICATE`、1 文が `NO_SUPPORTED_CLAUSE`。別の既知述語セット 10 文では `選手がコーチに褒められた。` が `NO_SUPPORTED_CLAUSE` だったが、基点も同じ理由で unreadable なので W5-a 回帰ではない。英語受身 40 文のうち 5 文は `by her` を含み、`UNREPRESENTED_CONTENT:possessive determiner` で棄権した（`The fence was painted by her.` など）。これは誤った passive 出力ではなく、W5-a 変更前からある別の英語 over-abstention。
3. **K63: unsupported 不変条件。** 第 1 fixture の日本語100行・英語80行と追試12文で `readable=true` かつ例外外の unsupported は 0。比較の copula 例外は今も `readable=true` で `copula value is a predicate phrase` のみ。K63 関連テストは通過。
4. **K64: `を` の役割行列 40 文。** 人、動物、組織、乗り物、自然現象の目的語/経路文を試した。16 件の正の agent/patient gold は一致し、残り24件の明示した曖昧・経路 gold は棄権。誤った agent/patient 出力は 0。テスト通過。
5. **K62: 原因・手段を表す `によって` 12 文。** 読める passive に原因/手段名詞を agent とした結果は 0。テスト通過。未対応理由で読めなかった文はこの攻撃の命中にはしていない。
6. **event JSON の鍵順。** 各 Mapping の鍵を個別に逆順化し、トップレベルの 8! 順列も試した。直列化バイト列の差は 0。テスト通過。
7. **証言再利用鍵。** 実際に prompt に表示される候補ごとの文脈行を 1 行ずつ変える、追加/削除/並べ替える計 8 条件は再照会され、候補順だけの変更は同じ文脈で再利用された。差し替え行を候補 A の 4 行目に足す条件だけは cache hit したが、既定 `max_used_in=3` のためその行は prompt に表示されない。正しい再利用であり命中ではない。

## 4. 数と手順上の留意点

- **命中 N=3**, **外れ M=7**（外れは上記の攻撃軸単位）。命中はすべて (d) の K64 過剰棄権。K62 の誤 passive、K63 の不許可な同居、K64 の誤役割、K64 の経路誤読、LLM 鍵の取りこぼしは確認できなかった。
- 第 1 fixture は日本語 100 行中 91 文がユニーク、英語は 80/80 ユニーク。80 文以上の目標は満たしたが、テストの「日本語100行すべてユニーク」検査は失敗した。これは反例ではなく fixture 品質上の外れとして開示する。
- 第 1・第 2 fixture の一部のテスト失敗は、攻撃条件の誤設定（index で選ぶ fake provider、prompt 上限外の文脈行、未対応 predicate/possessive）によるもの。該当ケースは hit 数に含めず、上の misses に分類した。K64 の R3 試行は基点が読めない文で先に停止したので数えず、新しい R4 fixture で命中を再確認した。
- 全体テストは実行していない。対象の攻撃テストだけを実行。最初の実行だけ pytest の既定 temp 先を使い、その後は指示書の scratchpad 配下を `--basetemp` に指定した。pytest が `.pytest_cache/` を生成/更新した可能性があるため、削除せず残した。製品コードは変更していない。
