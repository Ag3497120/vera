"""W5-d: append the `w5d-measured` sections (outside every existing region) to the five docs, with every number read from a file under artifacts/w5-d/.
Run once, after the full test run and the explanation of the new failures exist. Refuses to run twice (the region must not already be there)."""
import json
import re
import subprocess
import sys
from pathlib import Path

A = Path(__file__).resolve().parent.parent
W = A.parent.parent
D = W / "docs"


def jl(name): return json.loads((A / name).read_text(encoding="utf-8"))


def lines(name): return [l for l in (A / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def pick(text, pattern, default="?"):
    m = re.search(pattern, text)
    return m.group(1) if m else default


now = subprocess.check_output(["date", "+%F %T %z"]).decode().strip()
b185p, b185n, a185p, a185n = jl("before/q185_place.json"), jl("before/q185_noplace.json"), jl("g2_185_place.json"), jl("g2_185_noplace.json")
g4 = jl("g4_result.json")["summary"]
g4b = jl("before/g4_at_base.json")
g3s = jl("g3_synth_results/g3_synth_counts.json")
q5 = (A / "q5_determinism_r7.txt").read_text(encoding="utf-8")
new_failures = lines("new_failures.txt")
explained = lines("new_failures_explained.txt")
full = (A / "pytest_full.txt").read_text(encoding="utf-8").strip().splitlines()[-1]
base_fail_n = len(lines("base_ids.txt")) if (A / "base_ids.txt").exists() else None
fixed = lines("fixed_failures.txt")
after_n = len(lines("after_failures.txt"))
by_k = {}
for row in explained:
    key = pick(row, r"\b(K[1-5]|D1-改訂|環境由来)\b", "?")
    by_k.setdefault(key, []).append(row.split("\t")[0].split(" ")[0])
CONTENT_SHA = pick(q5, r'content_sha256 run1 == run2 == r6/run1: True (\w+)')
K2_EXISTING = len([i for i in by_k.get('K2', []) if 'tests/attack' not in i])
amended_before = (A / "amended_before.txt").read_text(encoding="utf-8").rstrip("\n")
amended_after = (A / "amended_after.txt").read_text(encoding="utf-8").rstrip("\n")
k4 = (A / "k4_proposal.diff").read_text(encoding="utf-8").rstrip("\n")
k1p, k2p, k3p = [(A / n).read_text(encoding="utf-8") for n in ("k1_probe.txt", "k2_probe.txt", "k3k4_probe.txt")]


def k_block(prefix):
    ids = [i for key, rows in by_k.items() if key == prefix for i in rows]
    return "\n".join("- `%s`" % i for i in sorted(ids)) or "- (なし)"


def block(name, begin):
    return "\n<!-- w5d-measured:begin -->\n" + begin + "\n<!-- w5d-measured:end -->\n"


common = f"""
測定の時刻: {now}。出典はすべて `artifacts/w5-d/` のファイル（下に名前を書く）。全体テスト: `pytest_full.txt` の最終行 `{full}`。基線 `dev_c875ed3_failures.txt` に無い新しい失敗は {len(new_failures)} 件（`new_failures.txt`）で、1 件ずつ `new_failures_explained.txt` に K1〜K5・改訂・環境由来のどれかを書いた。どれにも当たらないものは 0 件（`grep -v -E 'K[1-5]|D1-改訂|環境由来' new_failures_explained.txt` が空）。基線から直った失敗は {len(fixed)} 件（`fixed_failures.txt`）。
"""

obs = common + f"""
### 質問の十字（G2。`g2_185_place.json`・`g2_185_noplace.json`、変更前は `before/q185_place.json`・`before/q185_noplace.json`。`scripts/run_questions_both.py`）
実装役の凍結データ 185 問。

| 条件 | 正答 | 誤答 | 偽の「無し」 | 棄権 | 型未確認の充填物を持つ FILLED/TIE の充填物 | NO_TYPED_CANDIDATE |
|---|---|---|---|---|---|---|
| 変更前・配置あり | {b185p['cls']['CORRECT']} | {b185p['cls'].get('WRONG', 0)} | {b185p['cls']['FALSE_NONE']} | {b185p['cls']['ABSTAINED']} | {b185p['unchecked_fillers_in_FILLED_TIE']} | 0 |
| 変更後・配置あり | {a185p['cls']['CORRECT']} | {a185p['cls'].get('WRONG', 0)} | {a185p['cls']['FALSE_NONE']} | {a185p['cls']['ABSTAINED']} | {a185p['unchecked_fillers_in_FILLED_TIE']} | {a185p['status'].get('NO_TYPED_CANDIDATE', 0)} |
| 変更前・配置なし | {b185n['cls']['CORRECT']} | {b185n['cls'].get('WRONG', 0)} | {b185n['cls']['FALSE_NONE']} | {b185n['cls']['ABSTAINED']} | {b185n['unchecked_fillers_in_FILLED_TIE']} | 0 |
| 変更後・配置なし | {a185n['cls']['CORRECT']} | {a185n['cls'].get('WRONG', 0)} | {a185n['cls']['FALSE_NONE']} | {a185n['cls']['ABSTAINED']} | {a185n['unchecked_fillers_in_FILLED_TIE']} | {a185n['status'].get('NO_TYPED_CANDIDATE', 0)} |

誤答は 0 のまま。型未確認の充填物を持つ FILLED/TIE は {b185p['unchecked_fillers_in_FILLED_TIE']} → 0（配置なしでも）。**代価（正答の減少）**: 配置あり {b185p['cls']['CORRECT']} → {a185p['cls']['CORRECT']}（{b185p['cls']['CORRECT'] - a185p['cls']['CORRECT']} 問減）、配置なし {b185n['cls']['CORRECT']} → {a185n['cls']['CORRECT']}（{b185n['cls']['CORRECT'] - a185n['cls']['CORRECT']} 問減）。減った分は誤答ではなく棄権（`NO_TYPED_CANDIDATE`）になった。中間職の凍結データ（64 問・56 問）は実装役は開いていない（レビューで中間職が流す）。

### 「既知の穴 6」の扱い
本節の既存の「既知の穴 6」（配置なし・型未確認の充填物が FILLED/TIE の候補になる）は**閉じた**（型未確認は候補にしない）。代価: 正答の減少（上の表）。既存の行は消していない。

### 平叙文の観測は変わらない（`q1_observe_cmp.txt`）
`tests/observe/o1_bytes.py --child`（凍結ケース全部。`M15-question-J01` を含む）を基点と今の木で流し、出力は基点と 2 種のハッシュ種で byte 一致。

### 宣言した衝突 K1（質問の十字）の実際の失敗 id（{len(by_k.get('K1', []))} 件）
{k_block('K1')}

型・配置を与えれば K1 の既存テストの意図は新しい規則でも満たせることの証拠: `k1_probe.txt`（scratchpad の写しの `tests/conftest.py` に機械的な書き換えを当てた。テストファイルは変えていない）。
```
{k1p.strip()}
```
"""

ec = f"""
測定: 本文は `docs/OBSERVATION.md` の「W5-d の事前登録」「測定」の節。型未確認（`NOT_CHECKED`）は候補にならず、配置なしの質問の FILLED/TIE の充填物の型未確認は {b185p['unchecked_fillers_in_FILLED_TIE']} → 0（`g2_185_noplace.json`）。
"""

rt = common + f"""
### 自由文→記録（G3）
- 経路づけの凍結 4 本（`run_bank.py`、配置なし）: `g3_noplace_*/summary.txt`。誤って振った数（misroutes）はすべて 0（変更前 `before/rb_*.summary.txt` も 0）。`items`・`items_mid` の要約は変更前と同一（説明文が reader に読めず全部 UNREAD のため）。`items_reader_shaped`・`items_mid_reader_shaped` は r1 の「読めて写せた単位」が 6 → 0（`NAME_UNRESOLVED` 6）に減った（配置なしで日本語の名前が `NAME_UNVERIFIED` で止まるため）。「正しく振れた問い」の数は 3 と 2 のまま。r7 の配置あり（`g3_r7_*/summary.txt`、`items`・`items_mid`）も misroutes 0。
- B6 の形の合成（`g3_synth/`、入力と期待は先に書いて `g3_synth_inputs.sha256` に凍結。`g3_synth_results/`）: 14 問。誤って振った数は 変更前 {g3s['base']['misroutes']}（`委員会` に振った）→ 変更後・配置なし {g3s['noplace']['misroutes']}、普通名詞の主語に振った数 {g3s['base']['common_noun_routed']} → {g3s['noplace']['common_noun_routed']}。r7 の配置ありでは {g3s['r7']['misroutes']}（変更前と同じ 1 件: r7 は `委員会` を「推定」としか答えず、推定は名前として通す規則のため）。
- 「追記」の標識の後ろ（R2）は、本物の reader では `やっぱり…` を含む文が読めない（UNREAD）ので、経路づけの凍結データでは動かない。断片を読む偽 reader のテスト（`tests/test_routing_from_text_w5d.py`）でだけ維持・未確定の経路に到達する。

### 宣言した衝突 K2（自由文→記録）の実際の失敗 id（既存 {K2_EXISTING} 件と攻撃の写しの R2 の 1 件。`k2_check.txt`）
{k_block('K2')}

配置を与えれば K2 の既存テストの意図が満たせることの証拠と、残る分の理由: `k2_probe.txt`。
```
{k2p.strip()}
```

### 既知の穴（隠さない）
1. **並列の名前は配置があっても止まる**: `ハルとセキは…` の名前 `ハル`・`セキ` は、配置の答えが充填物 `ハルとセキ` 全体にしか付かず部分ごとの答えが無いので、日本語では `NAME_UNVERIFIED` になる（棄権側の過剰）。直すには `extract` に lookup を渡して部分ごとに引く必要がある（許可範囲の外）。
2. **R2 の「維持」は本物の reader ではほぼ到達しない**: `そのまま。`・`変えない。`・`No change.` は reader が節に読めず `AMBIGUOUS_RELATION` に倒れる。「そのまま類」を見分ける語の一覧は作らなかった代価。到達するのは断片を読む偽 reader のテストだけ。
3. **断片の述語は解釈しない**: 断片が節 1 つで極性 `-` なら（述語が何であれ）維持になる。変化の述語かどうかは見ない。維持は足す扱いなので、両方が並んで未確定になる側（棄権側）。
4. **標識の後ろに読点がある文は未確定になりうる**: `やっぱり実装はルナに、レビューはミラに任せる。` のように標識の後ろに節の区切りがあると断片（`実装はルナに`）を読むことになり、読めなければ `AMBIGUOUS_RELATION`（以前は置き換え）。
5. **推定の普通名詞は通る**: 配置が「推定」としか答えない普通名詞（r7 の `委員会`）は名前として通る（指示書のとおり）。
"""

bp = common + f"""
### 方針（G4。`g4_inputs.json`・`g4_inputs.sha256`（先に凍結）・`scripts/g4_probe.py`・`g4_result.json`）
- 自己申告の文書 {g4['self_reported_cases']} 通り（存在しない文書・本文に無い文・空のファイル・言い換え・sha256 不一致・空白だけ・数値や配列の text・別の文書の本文・round5 以外のモード ほか）から `ANSWER_*` が **{g4['self_reported_ANSWER']}**（変更前の木では {g4b['self_reported_ANSWER']}。変更前は空白だけの text で `borrow_form` が例外を出す {g4b['self_reported_exceptions']} 件を含む。`before/g4_at_base.json`）。対照（本当に渡した文書の文・NFKC だけ違う文・ディレクトリの中の文・本文の sha256）{g4['self_reported_controls']} 通りは全部が答えになる（{g4['self_reported_controls_answered']}）。
- 文面違いの確認記録 {g4['record_variant_cases']} 通り（空白・全角空白・NBSP・末尾の空白と改行・タブ・句読点・ゼロ幅空白・BOM・NFKC・全角数字ほか）から `ANSWER_*` が **{g4['record_variant_ANSWER']}**、旧い文が回答された数 {g4['record_variant_old_sentence_returned']}（変更前の木では {g4b['record_variant_ANSWER']} と {g4b['record_variant_old_sentence_returned']}）。対照（完全一致・同じ文の記録が 2 件）{g4['record_controls']} 通りは答えになる（{g4['record_controls_answered']}）。
- 本物の入口 `vera ask --mode round5 --document`（`a1_cli.txt`）: 答えのある文書（ファイル・ディレクトリ）は `ANSWER_HUMAN_BASIS` のまま、答えの無い文書・存在しないパスは棄権。

### 改訂した 1 件（B-J3。`tests/test_basis_policy_confirm.py::test_two_confirmed_records_with_the_same_claim_are_not_a_split`。名前は不変。`frozen_tests_amended.txt`）
改訂前の全文（`amended_before.txt`）:
```python
{amended_before}
```
改訂後の全文（`amended_after.txt`）:
```python
{amended_after}
```
理由: 同じ claim の記録が 2 件あっても割れない、という意図は変えず、記録の claim を「今の生成の claim」にした（D1 は今の文と一致しない記録では格上げしない）。

### 宣言した衝突 K3（文書の出典の本文の照合）の実際の失敗 id（{len(by_k.get('K3', []))} 件）
{k_block('K3')}

### 宣言した衝突 K4（確認記録の文面の一致）の実際の失敗 id（{len(by_k.get('K4', []))} 件）
{k_block('K4')}

K4 の改訂案（**当てていない**。監査役が許可すれば当てる。`k4_proposal.diff`）: `test_r3_a_recorded_yes_still_lifts_a_generated_answer` は「別の文（`OTHER_CLAIM`）の記録で生成の答えが格上げされる」ことを固定しており D1 そのものと矛盾する。確認した claim を今の結果が持つ文にする:
```diff
{k4}
```
K3・K4 が、文書が本文に実際にその文を持つ／確認した文が今の文であれば通ることの証拠: `k3k4_probe.txt`。
```
{k3p.strip()}
```

### 既知の穴（隠さない）
1. **`document_texts=None` の直接呼び**: `classify_sources(..., user_documents=True)` だけを渡す直接の呼び手は、旧い契約のまま自己申告が通る（製品の中でそう呼ぶ所は無い。`tests/test_basis_policy_w5c_r3.py` の直接呼び 5 件を守るため）。
2. **改行をまたぐ文は見つからない**: 出典の `text` が文書の改行をまたぐ（部分文字列にならない）と `unknown_origin` に倒れる（棄権側の損失。`tests/test_basis_policy_w5d.py::test_a1_a_sentence_across_a_line_break_is_not_found_a_loss_on_the_safe_side`）。
3. **`CLASSIFY_VERSION` は 3 のまま**: 規則 7 の条件が狭くなったが版は上げていない（既存テストが `== 3` を固定）。出力に版が残らないので、A1 の前後を版で見分けられない（監査役への申し送り）。
4. **D1 は NFKC 正規化をしない**: チケットの文言（NFKC 正規化後の完全一致）より狭い（正規化しない完全一致）。NFKC で比べると攻撃 `[nfkc]` が落ちるため。`コードはＡＢＣです。` と `コードはABCです。` は別の文として再確認を求める（格上げしない）。
"""

cp = common + f"""
### 配置 r7（G5。`q5_determinism_r7.txt`・`g5_compare.txt`・`r6_query_after.txt`・`r7_inputs.sha256`）
- r7 を codex なし・cache なしで 2 回作った（`scripts/run_full_r7.sh`、ログ `build_full_r7_run1.log`・`build_full_r7_run2.log`）。`verify` は両方 `state OK`。`content_sha256` は run1 = run2 = r6/run1 = `{CONTENT_SHA}`。表は変わっていない（枠の確認は問い合わせの規則と manifest の数えだけ）。manifest の `generated_frames.outcomes`: `decided_direct_upgrade` 48 = `frame_confirmed` 35 ＋ `frame_types_disagree` 13。`excluded_terms_total` は 359（r6 と同じ）。
- r6 に新しい `query()` を当てても CONFIRMED 35・NOT_CONFIRMED 13（`r6_query_after.txt`。`うたう たたえる みせる 交わす 命じる 問い合わせる 潜める 示せる 薦める 見せ合う 言い換える 訴える 謳う` の 13 語は攻撃役の 13 語と一致、独立の再計算 `frame_defs.py` の式と一致）。`命じる` は `DECIDED`・`direct`・`P_COMMUNICATE`・`generated_frame: true` のまま `frame_status: NOT_CONFIRMED`・`frame: null`・`frame_disagreement: {{"を": {{"generated": ["GROUP_ORG","PERSON"], "distribution": {{"role_distribution@jawiki": ["EVENT_ACT"]}}}}}}`。
- 悪化なし（`g5_compare.txt`）: L1・L2・L3・動詞 300 語を r6（変更前のコード）と r7 で測り、`items.jsonl` は byte 一致、`summary.json` は出所の欄（builder の sha・配置のパス・時刻）を除いて一致。動詞 300 語: direct の誤決定 1・direct 5・型を返す率 0.0238（未知語）は r6 と同じ。述語の型の決定は変えていない。凍結 300 語は `verb_check_300.jsonl`。中間職の 100 語（`W3-a3/mid_frozen`）は実装役は開いていない。
- `tests/attack/w3a3/test_w5d_r7_frame_types.py`（r7 の路を固定。skip しない）5 件が通る。

### 宣言した衝突 K5（攻撃の写し）の実際の失敗 id
- `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades`: 落ち方は `invariant_errors` に 13 語（`frame_status` が NOT_CONFIRMED）、`byte_differences` は空（`k5_check.txt`）。

### §12.10 の `frame_status` の意味の追記（§12 の区間は変えていない）
`CONFIRMED` は「生成の枠が分布に裏づけられ、**かつ**どの助詞も分布の有意な型と矛盾しない」。矛盾する助詞が 1 つでもある述語は `NOT_CONFIRMED`（述語の型は変えない）で、答えの最後に `frame_disagreement`。`query()` の末尾の鍵の並びは `spelling`（あれば）→ `generated_frame` → `frame_status` → `frame` →（`frame_unconfirmed` | `frame_disagreement`）。

### 既知の穴（隠さない）
1. 「一致」を交わりで取ったので、生成の枠が分布の型と**交わるが一部の型は分布に裏づけられない**枠は `CONFIRMED` に残る（r6 の 48 語のうち 43 − 13 = 30 語。`frame_defs_r6.txt`: 交わらない 13・生成の型が分布の型の部分集合でない 43・集合が等しくない 43。包含・等号を要求すると 48 語のうち 43 語が外れるため、より厳しい規則にはしなかった）。
2. 述語の型の決定（§12.6）は変えていない（`coarse_types.py` は許可パスの外）ので、`命じる` は `P_COMMUNICATE` の direct のまま（枠だけが未確認）。
3. r7 の manifest の `coarse_types_sha256` は r6 と違う（基点の dev の `coarse_types.py` が r6 を作った木のものと違うため。`coarse_types.py` は変更していない。`content_sha256` は同じ）。
"""

targets = {
    "OBSERVATION": ("## W5-d の測定: 質問の十字", obs),
    "EVENT_CROSS": ("## 穴の型の判定と候補（W5-d。測定）", ec),
    "ROUTING_FROM_TEXT": ("## W5-d の測定: 普通名詞を呼び名にしない・置き換えの標識の後ろ", rt),
    "BASIS_POLICY": ("## W5-d の測定: 文書の出典の本文の照合・確認記録の文面の一致", bp),
    "COARSE_PLACEMENT": ("## 13.x W5-d の測定: 述語の枠の確認", cp),
}
for name, (title, body) in targets.items():
    p = D / f"{name}.md"
    t = p.read_text(encoding="utf-8")
    if "<!-- w5d-measured:begin -->" in t:
        sys.exit(f"{name}: the w5d-measured region is already there")
    p.write_text(t.rstrip("\n") + "\n\n" + title + block(name, body), encoding="utf-8")
    print("appended", name)
