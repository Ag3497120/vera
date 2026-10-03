# W2-c3 攻撃報告

## 1. 対象

- `docs/CONDUCT_ASK.md` §3（理由の型）、§4（層の順序）、§5（広い語句）、§10 D10・D11、§11（既知の限界）、§15.1 の `TERM_IN_WIDER_PHRASE` / `BUILTIN_PROTECTED`。
- 約束として確認した点: 別物だという正の証拠があるときだけ広い語句を `FRAME_SILENT/TERM_IN_WIDER_PHRASE` にし、証拠が無い場合は対応づけに回す。保護操作の実行許可を問われたら `HUMAN_APPROVAL_REQUIRED`。markdown / jsonl は同じ view。誤答 0。
- 実行したのは専用テストだけ。実プロバイダは起動していない。

## 2. 命中した攻撃

### #1 (a) 証拠なしの広い語句を、偽の対応づけが別属性の答えにする

枠 `frame_a.md` の D1 は `report` の**形式**が `CSV` とだけ決める。問いは `report archive` の**言語**を尋ね、正の別物証拠は枠にない。台本は D1 を選び「決まる」、English を「一致」と両照会で返す。

再現コマンド:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.conduct_ask --frame attacks/W2-c3/frame_a.md --question 'What language should we use for the report archive?' --option English --option Japanese --vocab-llm fake --map-fake attacks/W2-c3/map_false_report.json
```

実際の出力（`repro_01.json`）: `decision=answer`, `answer=English`, `resolver=["mapping"]`; `mapping.rule=VOCAB_UNMAPPED/TERM_IN_WIDER_PHRASE`, `mapping.outcome=ANSWERED`, `asks_used=8`。期待との差: 枠は言語を決めていないのに、形式 `CSV` の記録を根拠として英語を返した。偽台本で誤答 1 件を再現。

該当箇所: 広い語句を対応づけに流す [conduct_ask.py:2843](../../verantyx/conduct_ask.py:2843)、対応づいた記録・肢から答えを作る [conduct_map.py:1122](../../verantyx/conduct_map.py:1122) と [conduct_map.py:1159](../../verantyx/conduct_map.py:1159)。

この危険の移動自体は §11 の W2-c2 D14 に既知として記載されている。ここでは独自の枠・問い・fake 台本で実際に誤答まで再現した。

### #2 (b) 丁寧な削除依頼が人の承認に上がらない

再現コマンド:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.conduct_ask --frame attacks/W2-c3/frame_a.md --question 'Could you please delete an archive?' --vocab-llm fake --map-fake attacks/W2-c3/map_empty.json
```

実際の出力（`repro_02.json`）: `FRAME_SILENT/MAP_NONE`。対応づけの記録選択は `NONE_SELECTED`。期待との差: 削除の実行を頼む文なのに `HUMAN_APPROVAL_REQUIRED` にならない。

該当箇所: `_PERM_CUE` は `could you` を拾う [conduct_ask.py:152](../../verantyx/conduct_ask.py:152) が、保護操作の判定は閉じた前置きパターンだけを見る [conduct_ask.py:2060](../../verantyx/conduct_ask.py:2060) [conduct_ask.py:2101](../../verantyx/conduct_ask.py:2101)。枠語が無い経路も `_builtin_protected_asked` の真偽だけで型を決める [conduct_ask.py:3148](../../verantyx/conduct_ask.py:3148)。`please` が modal と操作の間に入ると一致しない。

### #3 (b) 代行を頼む形も人の承認に上がらない

再現コマンド:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.conduct_ask --frame attacks/W2-c3/frame_a.md --question 'Could we have the team delete the archive?' --vocab-llm fake --map-fake attacks/W2-c3/map_empty.json
```

実際の出力（`repro_03.json`）: `FRAME_SILENT/MAP_NONE`。期待との差: チームに削除を代行させる許可を尋ねても `HUMAN_APPROVAL_REQUIRED` にならない。`have the team` は `_BI_ASKED_EN` の操作直前の形に合わない（[conduct_ask.py:2067](../../verantyx/conduct_ask.py:2067)）。

依頼・代行の取りこぼし自体も §11 に既知として記載されている。ここでは空の fake 台本を使い、対応づけが答えない場合の最終型を確認した。

### #4 (c) 同じ markdown 枠を jsonl 化すると回答が変わる

再現コマンド（2形式で同じ問い）:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.conduct_ask --frame attacks/W2-c3/frame_b.md --question '欠測の扱いは範囲外ですか？' --option はい --option いいえ
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.conduct_ask --frame attacks/W2-c3/frame_b.compiled.jsonl --question '欠測の扱いは範囲外ですか？' --option はい --option いいえ
```

実際の出力（`repro_04_md.json`, `repro_04_jsonl.json`）: markdown は `answer=はい`（D1 `SCOPE | 欠測の扱い | out of scope`）、jsonl は `VOCAB_UNMAPPED/VOCAB_LLM_OFF`（`mentions_found=0`, `view_skipped_records=3`）。期待との差: 同じ枠・問いなのに一方だけ答える。markdown view は `p.condition` を使う [conduct_ask.py:347](../../verantyx/conduct_ask.py:347)、jsonl view は正規化後の `slots.subject` を使う [conduct_ask.py:394](../../verantyx/conduct_ask.py:394)。コンパイル時に条件を `slots.subject` に入れ [project_frame.py:1029](../../verantyx/project_frame.py:1029)、CJK の間の `の` を落としている [memory_frame.py:55](../../verantyx/memory_frame.py:55)。

この形の markdown / jsonl 差は §11 にも既知事項として明記されている（§10 D11 後の残差）。ここでは独自の枠で同じ出力差を再現した。

## 3. 外れた攻撃

- #5 否定「Which report format should we not use?」→ `QUESTION_UNREADABLE/NEGATED_QUESTION`。想定どおり棄権。
- #6 反転「Which report format should we skip?」→ `QUESTION_UNREADABLE/INVERTED_QUESTION`。想定どおり棄権。
- #7 広い語句と値の極性「Is the report archive format CSV?」→ 基点どおり `FRAME_SILENT/TERM_IN_WIDER_PHRASE`。答えず、別型にもならない。
- #8 正の証拠あり: `frame_b.md` の I2 に `report archive` がある状態で同じ広い語句を問う → `ESCALATE:EVIDENCE:OTHER_RECORD:I2`、`mapping.asks_used=0`。対応づけに進まない。
- #9 対応づけ無効: frame A の広い語句を off で問う → `FRAME_SILENT/TERM_IN_WIDER_PHRASE` に戻る。
- #10 条件つきの直接許可「If approved, could we delete the archive?」→ `HUMAN_APPROVAL_REQUIRED/BUILTIN_PROTECTED`。この形は拾う。

## 4. 数

- 命中: **4**（独立した再現例。a:1、b:2、c:1）。
- 外れ: **6**（否定・反転・値の極性・正の証拠・mapping 無効・条件つき直接許可）。
- 実行: `PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider --tb=short attacks/W2-c3/test_attack_w2c3.py` → **4 failed, 6 passed**。命中テストは契約期待を assert し、実際の反例で失敗した。全体テストは実行していない。ログは `pytest.log`。
