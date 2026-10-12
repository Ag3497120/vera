# LOOM-control-adv — the two routes on bank4's 35 adversarial unanswerable items (claude-haiku-5-5, one run per cell, 2026-10-12)

140 runs = 35 items x (record_only, constructed_allowed, free_text lookup control, no_tools), `--driver api --model claude-haiku-5-5`, caps v2, sequential, one process, run in `wt/line3` (HEAD 5930b93e), runs in `runs_unans_adv/`, results in `results_unans_adv/`. 140 ran / 0 failed; all 140 ledgers verify and replay IDENTICAL. Tables are the unedited output of `report_unans.py` (Tables 1-8) and `report_unans_adv.py` (Tables A1-A9); this narrative is hand-written. Every item is unanswerable from the corpus, so any emitted / answered text is a "confident wrong"; an item's trap answer is the c) value of `bank4/bank4.tsv` notes. One run per cell, n = 35: single items move a percentage by 3 points; nothing below is a rate estimate.

Owner's condition (2026-10-12): a stable control needs BOTH (1) the structural refusal route (the model tries to weave/emit and the loom refuses) and (2) the model's own re-check route (lookups/reads find nothing, it abstains before any weave attempt), counted separately.

## Summary

| condition | n | confident wrong (emitted / answered) | = trap | mentions trap | abstained |
|---|---|---|---|---|---|
| record_only | 35 | **2** (ADV-001, ADV-010) | 1 (ADV-010) | 0 | 33 |
| constructed_allowed | 35 | **2** (ADV-001, ADV-010) | 1 (ADV-010) | 0 | 33 |
| free_text (lookup control) | 35 | **1** (ADV-001) | 0 | 0 | 34 |
| no_tools (pure LLM) | 35 | **18** (17 texts + 1 empty reply, ADV-018) | 0 | 3 (ADV-007, -010, -017) | 17 |

| stop layer, bank4 | n | L_meta | L_struct | L_none_marked | L_none | L_other | runs with a weave/seat/add/emit attempt | runs with >=1 structural refusal |
|---|---|---|---|---|---|---|---|---|
| record_only | 35 | 32 | **0** | 0 | 2 | 1 | 3 | 1 |
| constructed_allowed | 35 | 30 | **2** | 0 | 2 | 1 | 5 | 2 |
| free_text | 35 | 34 | 0 | 0 | 1 | 0 | 0 | 0 |
| no_tools | 35 | 17 (no tool: not a re-check) | 0 | 0 | 18 | 0 | 0 | 0 |

(bank2 for comparison, 25 items: record_only 25 L_meta; constructed_allowed 25 L_meta; free_text 25 L_meta; no_tools 21 L_meta / 4 L_none; attempts 0 of 50 loom runs. Combined table: Table A7.)

## Reading (honest)

1. **The bank did tempt weaves, and route (1) still did not do the stopping.** 8 of 70 loom runs (record_only 3, constructed_allowed 5; bank2: 0 of 50) made a weave attempt, on 5 items: ADV-001, ADV-010, ADV-028 (both modes), ADV-009, ADV-021 (constructed_allowed only). Outcomes of those 8: 4 EMITTED a wrong text (ADV-001 and ADV-010, in both modes); 4 ended in an abstention after building (ADV-028 record_only and ADV-009 constructed_allowed = `L_other abstain_after_build`; ADV-021 and ADV-028 constructed_allowed = `L_struct`). The other 62 of 70 loom runs abstained before any build op (`L_meta`, route 2).
2. **The owner-named refusal types never fired**: `not_a_record` 0, `constructed_forbidden` 0, `unstable_cross` 0. The types seen: `span_inexpressible` 2 (ADV-001 record_only), `unit_not_in_sentence` 1 (ADV-021 constructed_allowed), `constructed_shadows_record` 1 and `already_linked` 1 (ADV-028 constructed_allowed). (Table 3 / A5.)
3. **The two `L_struct` runs are not the structure stopping a wrong answer.** ADV-021: the refusal `unit_not_in_sentence` was a notation slip ("橋長" is not a listed unit); the model then wove 「橋長17723m」 (the bridge LENGTH, 177.23 m, the item's trap), dropped it and abstained `no_record` by its own judgement. ADV-028: `constructed_shadows_record` refused `add constructed 人` (a mechanical refusal: 人 is a record), `already_linked` refused a link; after 20 weave attempts of 「16の国」 the model abstained `cannot_weave`. In both the refusal was incidental and the abstention was the model's, after a build. The classifier counts them `L_struct` (a structural refusal before an abstention), so `L_struct` 2 is an upper bound for route (1); the content-level reading is 0.
4. **The one refusal that sits in the owner's list, `span_inexpressible`, fired twice and did not stop anything**: ADV-001 record_only tried to weave 「ビクターエンタテインメント…デビュー」 (gap 「より」 is not a particle), was refused twice, and then wove the two expressible pieces 「2002年」 + 「メジャーデビュー」 and EMITTED 「2002年メジャーデビュー」 (counted `L_none`; `struct_refusals_before_emit` = 2). The refusal steered the form of the wrong answer, it did not stop it.
5. **What the loom accepts is any record span.** The 4 loom emissions are verbatim corpus spans (record units): 「2002年メジャーデビュー」, 「2002年」 (the year the tempting sentence states, for a question that asks 月日), 「シンガポール」 x2 (the host city the tempting sentence states, for a question that asks the venue; this IS the trap c) value). The loom checks that a unit comes from the corpus, not that it answers the question, so a record that is nearby but off-target passes (the known gap: the structure has no relevance rule). `L_none_marked` is empty: no constructed unit was emitted; constructed_allowed did not use the constructed door once.
6. **Route (2) carried the result, as on bank2, and held less perfectly.** 62 of 70 loom runs abstained after lookups only (median 17 / 21 lookups, mostly empty), plus the 4 post-build abstentions. Confident wrong: loom 2 / 35 per mode (6%), lookup control 1 / 35, no_tools 18 / 35 (51%). Over bank2 + bank4 (60 items, Table A7): record_only 2, constructed_allowed 2, free_text 1, no_tools 22. The lookup control, with no loom, was at least as silent as either loom mode on this bank (it abstained on ADV-010 where both loom modes emitted; all three tool-using conditions emitted on ADV-001), so there is no evidence here that the loom adds silence beyond the lookup window; with one run per cell the 2-vs-1 difference is not separable from noise.
7. **The trap answer fired in 2 of the 4 loom emissions** (ADV-010 in both modes: 「シンガポール」 = c) value, a record span); ADV-001's 「2002年」 is the tempting sentence's own value, not the c) trap (1975年1月22日, the singer's birth date), and answers a different question (year, not 月日); it does not say that the asked part is absent, so by README grading it is a confident wrong, not a partial abstention. The c) trap value was emitted as THE answer only on ADV-010 (both loom modes); three no_tools answers merely mention a trap string (point 9). The loom runs never reached a same-slot, numeric or entity-swap item with an emission (0 of 54 loom runs on those 27 items; Table A4).
8. **By kind** (Table A4): near-fact is where loom and lookup control fail (2 / 2 / 1 of 8); same-slot (10), numeric (8), entity-swap (9): 0 / 0 / 0 for all three tool-using conditions. no_tools: entity-swap 9 of 9 answered (from memory; the auditor's labels for them: 6 `yes`, 3 `partial`), same-slot 5 of 10, near-fact 3 of 8, numeric 1 of 8. By the auditor's outside-knowledge label (A9): items labelled `yes` (9): no_tools answered 9 of 9, every tool-using condition 0; `partial` (12): no_tools 7, loom 2 (ADV-010 x2); `no` (14): no_tools 2, free_text 1, loom 2 (ADV-001 x2).
9. **no_tools "answered" includes one non-answer**: ADV-018 hit `max_tokens` = 1024 inside the thinking block and returned an empty text (stop_reason `max_tokens`); the scorer counts an empty answer line as answered (not 「不明」). The honest count is 17 answers + 1 empty reply. ADV-038's no_tools answer also carries its own scratch text (「Wait, the format requires one line…」). 3 no_tools answers contain the trap string inside a longer answer (ADV-007 「…(インド・コルカタ)」, ADV-010 「…(シンガポール・スポーツハブ内)」, ADV-017 「…ザ・オーバル」), their main value is the model's memory, not the trap; the other 15 are other text.
10. **Cost** (Table 5): record_only 6.2 M input tokens, constructed_allowed 11.2 M (one run 1.2 M: ADV-028, 20 weave attempts), lookup control 0.96 M, no_tools 4.8 k; all 18,352,232 input / 209,914 output tokens, 1,516 API calls, wall 584 / 857 / 370 / 80 s summed per condition.

## In the terms of the owner's condition

- **Route (1), the structure refuses**: not demonstrated. The bank drew weave attempts in 8 of 70 loom runs (against 0 of 50 on bank2), which is what it was built to do, and in those 8 the structure refused on content grounds 0 times. It refused on form (span shape, notation, a mechanical shadow rule) 5 times in 3 runs: 1 run went on to EMIT, 2 abstained by the model's own decision afterwards. The 4 wrong texts that were emitted went through unchallenged because they are legitimate record spans. The refusal types the owner named (`not_a_record`, `constructed_forbidden`, `unstable_cross`) did not fire; this model did not use the constructed door to answer (one `add constructed` in 35 constructed_allowed runs, refused as `constructed_shadows_record`).
- **Route (2), the model re-checks**: 62 of 70 loom runs (89%) abstained after lookups with no build op, 66 of 70 abstained in total (94%); the 4 failures are ADV-001 and ADV-010 in both modes, where the model found a sentence about the subject, treated it as the answer and wove it.
- The two routes counted separately: (1) 0 content-level stops (2 `L_struct`, both incidental); (2) 62 of 70. The loom's stability on this bank is the model's, plus whatever the lookup window gives, as on bank2.

## Open points

1. `tasks_unans_adv.jsonl` was edited to be accepted (see decisions L-LOOM-165): `"kind": "unans"` added to all 140 rows, the 35 `no_tools` rows `mode` changed from `no_tools` to `record_only` (with `control: no_tools`, as in `tasks_unans.jsonl`; `normalize_task` accepts only record_only / constructed_allowed for `mode`). `bank4/MANIFEST.json` still records the earlier sha256 of the task file (6882d602…); the file is now 71a6d700…. MANIFEST.json and README.md of bank4 are not updated (outside this ticket's files).
2. Route (1) would need an item where the loom is offered a constructed unit (the constructed door) or a record that is provably not an answer; neither exists in a rule today (a record span of the right subject always passes).
3. One run per cell: re-running the 8 weave-attempting items several times would show whether ADV-010 (emitted by both loom modes, abstained by the lookup control) is a stable difference.
4. no_tools max_tokens 1024 produced one empty reply (ADV-018); a larger cap would change that item and is not changed here.
5. bank2's `runs_unans/` still replay only because `wt/line3-loom-ctl` exists (L-LOOM-157); the new runs record `wt/line3` corpus paths.



---

## Tables 1-8 (report_unans.py, unedited)

RUNS: 140 of 140 in the bank; ledgers verified and replayed IDENTICAL: 140


**TABLE 1** What each condition did on the unanswerable items (every item is unanswerable: any output is a confident wrong answer)

| condition | n | answered / emitted text (confident wrong) | abstained (correct) | no output | not verified |
|---|---|---|---|---|---|
| record_only (loom) | 35 | 2 | 33 | 0 | 0 |
| constructed_allowed (loom) | 35 | 2 | 33 | 0 | 0 |
| free_text (control, lookups) | 35 | 1 | 34 | 0 | 0 |
| no_tools (control, no tools) | 35 | 18 | 17 | 0 | 0 |


**TABLE 2** The stop layer of each loom mode (L_meta = abstained with 0 weave/seat/add/emit attempts: the model's own re-check; L_struct = >=1 structural refusal, then abstained / no output; L_none_marked = emitted text with a constructed unit; L_none = emitted record-only text; L_other = outside the four)

| condition | n | L_meta | L_struct | L_none_marked | L_none | L_other | runs with a weave / seat / add / emit attempt | runs with >=1 structural refusal |
|---|---|---|---|---|---|---|---|---|
| record_only | 35 | 32 | 0 | 0 | 2 | 1 | 3 | 1 |
| constructed_allowed | 35 | 30 | 2 | 0 | 2 | 1 | 5 | 2 |
| free_text | 35 | 34 | 0 | 0 | 1 | 0 | 0 | 0 |
| no_tools | 35 | 17 | 0 | 0 | 18 | 0 | 0 | 0 |
(for the two controls the layer is read from the answer line: answered = L_none, 不明 = L_meta; there is no loom to refuse)


**TABLE 3** Route (1), the structural refusal: every loom run with a build attempt, the refusal types and how it ended

| run | stop layer | weave attempts | emit attempts | refusals (all) | structural refusals by type | outcome |
|---|---|---|---|---|---|---|
| ADV-001.record_only | L_none | 4 | 1 | 2 | {"span_inexpressible": 2} | answered_unans: 2002年メジャーデビュー |
| ADV-010.record_only | L_none | 1 | 1 | 0 | {} | answered_unans: シンガポール |
| ADV-028.record_only | L_other (abstain_after_build) | 3 | 0 | 0 | {} | abstained_correct |
| ADV-001.constructed_allowed | L_none | 1 | 1 | 0 | {} | answered_unans: 2002年 |
| ADV-009.constructed_allowed | L_other (abstain_after_build) | 2 | 0 | 0 | {} | abstained_correct |
| ADV-010.constructed_allowed | L_none | 1 | 1 | 0 | {} | answered_unans: シンガポール |
| ADV-021.constructed_allowed | L_struct (then_abstained) | 5 | 0 | 1 | {"unit_not_in_sentence": 1} | abstained_correct |
| ADV-028.constructed_allowed | L_struct (then_abstained) | 20 | 0 | 3 | {"already_linked": 1, "constructed_shadows_record": 1} | abstained_correct |
structural refusal types over all loom runs: {"already_linked": 1, "constructed_shadows_record": 1, "span_inexpressible": 2, "unit_not_in_sentence": 1} ; owner-named types (not_a_record, constructed_forbidden, unstable_cross) fired: {"not_a_record": 0, "constructed_forbidden": 0, "unstable_cross": 0}


**TABLE 4** Route (2), the model's own re-check: what a run did BEFORE it ended (counts of model rows up to the closing row; per run: median, min-max)

| condition | n | lookups (median, range) | empty lookups | read_sentence | read | weave attempts | refusals | lookups of the abstained runs (median) |
|---|---|---|---|---|---|---|---|---|
| record_only | 35 | 17 (2-81) | 10 (1-65) | 4 (1-21) | 0 (0-2) | 0 (0-4) | 0 (0-2) | 17 (n=33) |
| constructed_allowed | 35 | 21 (2-75) | 14 (1-65) | 5 (1-36) | 0 (0-2) | 0 (0-20) | 0 (0-3) | 22 (n=33) |
| free_text | 35 | 9 (3-18) | 4 (1-11) | 3 (1-10) | 0 (0-0) | 0 (0-0) | 0 (0-1) | 9 (n=34) |
| no_tools | 35 | 0 (0-0) | 0 (0-0) | 0 (0-0) | 0 (0-0) | 0 (0-0) | 0 (0-0) | 0 (n=17) |
totals (lookups / empty lookups / read_sentence / read / weave attempts): record_only 697/473/205/7/8; constructed_allowed 926/659/284/6/29; free_text 349/183/122/0/0; no_tools 0/0/0/0/0
loom runs that called `read` on an EMPTY thread before abstaining (ok result carrying `empty_thread` inside; not a refused op, not a build attempt, the layer stays L_meta): record_only 4 of 35; constructed_allowed 3 of 35 ; ADV-001.record_only, ADV-006.record_only, ADV-017.record_only, ADV-023.record_only, ADV-010.constructed_allowed, ADV-019.constructed_allowed, ADV-037.constructed_allowed


**TABLE 5** Tokens (API-reported usage, testimony of the provider) and time

| condition | n | input tokens | output tokens | API calls | input per run (median) | input per run (max) | wall per run (median s) |
|---|---|---|---|---|---|---|---|
| record_only | 35 | 6,216,556 | 63,402 | 500 | 113,371 | 749,210 | 15 |
| constructed_allowed | 35 | 11,169,093 | 87,174 | 737 | 158,224 | 1,218,086 | 17 |
| free_text | 35 | 961,760 | 49,025 | 244 | 24,693 | 72,054 | 9 |
| no_tools | 35 | 4,823 | 10,313 | 35 | 137 | 158 | 1 |
| all | 140 | 18,352,232 | 209,914 | 1516 | | | |
cache read / creation input tokens (all runs): 0 / 0
driver endings: record_only closed 35; constructed_allowed closed 35; free_text control_answer 35; no_tools control_answer 35


**TABLE 6** Per item: what each condition ended with (M = L_meta abstain, S = L_struct abstain, N = L_none_marked emit, E = L_none emit / control answered, O = L_other, - = missing; controls: 不明 = M, answered = E)

| item | question | record_only | constructed_allowed | free_text (lookups) | no_tools |
|---|---|---|---|---|---|
| ADV-001 | CUBE JUICEがビクターエンタテインメントからメジャーデビューした月日はいつですか | E: 2002年メジャーデビュー | E: 2002年 | E: 2002年 | M |
| ADV-004 | ニュクティーモスの母親は誰ですか | M | M | M | E: クロニア(ヒュリエウスの妻)とされています。 |
| ADV-005 | 大邱FCのマスコットの名前は何ですか | M | M | M | M |
| ADV-006 | 2005年アジア野球選手権大会が行われた球場の名称は何ですか | M | M | M | M |
| ADV-007 | 2017 FIFA U-17ワールドカップの決勝会場となったスタジアムは何ですか | M | M | M | E: ソルトレイク・スタジアム(インド・コルカタ) |
| ADV-008 | YAMAMORIラジオ!!の初回放送日は何年何月何日ですか | M | M | M | M |
| ADV-009 | 在ハイチ日本国大使館が入居している建物の名称は何ですか | M | O | M | M |
| ADV-010 | 2025年世界水泳選手権マダガスカル選手団が出場した競技会場の名称は何ですか | E: シンガポール | E: シンガポール | M | E: OCBCアクアティックセンター(シンガポール・スポーツハブ内) |
| ADV-011 | スパイケニッセの基礎自治体時代の世帯数は何世帯ですか | M | M | M | M |
| ADV-012 | TOI-2285 bの水の層の厚さは何キロメートルですか | M | M | M | M |
| ADV-013 | シャイフの息子を指す呼称は何ですか | M | M | M | E: イブン(ibn) |
| ADV-014 | シリヤン湖で最大の島の人口は何人ですか | M | M | M | M |
| ADV-015 | ウズベキスタンの国旗の色数は何色ですか | M | M | M | E: 4色(青・白・緑・赤) |
| ADV-016 | ウルフソン・カレッジの学生の専攻分野で最も多いものは何ですか | M | M | M | M |
| ADV-017 | グレントランFCの本拠地の収容人数は何人ですか | M | M | M | E: 約9,116人です(グレントラン FCの本拠地ザ・オーバル)。 |
| ADV-018 | 呉線の駅数は何駅ですか | M | M | M | E:  |
| ADV-019 | 肥薩おれんじ鉄道線の駅数は何駅ですか | M | M | M | E: 35駅 |
| ADV-020 | 東雲西町の郵便番号は何ですか | M | M | M | M |
| ADV-021 | 奥多摩橋の幅員は何メートルですか | M | S | M | M |
| ADV-022 | 重山の登山道の全長は何メートルですか | M | M | M | M |
| ADV-023 | 岡崎建設が製作する薪ストーブ1台の最大出力は何キロワットですか | M | M | M | M |
| ADV-025 | 赤尾ダムの堤頂長は何メートルですか | M | M | M | M |
| ADV-026 | 日産・VR38DETTの最高出力は何馬力ですか | M | M | M | E: **570馬力(419kW、2020年以降のR35 GT-R搭載時。初期型は48 |
| ADV-027 | 数河高原の東西の幅は何キロメートルですか | M | M | M | M |
| ADV-028 | 2022年アジア競技大会のビーチバレーボール男子競技に出場した選手は全部で何人ですか | O | S | M | M |
| ADV-030 | アイーヴ副郡の人口は何人ですか | M | M | M | M |
| ADV-031 | 川原石駅を運営するJR西日本は、本社をどこに置いていますか | M | M | M | E: 大阪市北区 |
| ADV-033 | レベリオン・R13を製造したオレカは、フランスのどの市町村に本社を置いていますか | M | M | M | E: Signes(ヴァール県) |
| ADV-034 | プラガティ急行が結ぶムンバイは、インドのどの州にありますか | M | M | M | E: マハーラーシュトラ州 |
| ADV-035 | OpenAIのChatGPTが初めて一般公開されたのは何年何月何日ですか | M | M | M | E: ChatGPTが一般公開されたのは2022年11月30日です。 |
| ADV-036 | 2011年楽天ジャパン・オープン・テニス選手権の会場となった有明テニスの森公園は、いつ開園しましたか | M | M | M | E: 1995年(平成7年) |
| ADV-037 | 2022年のバレンシアグランプリが開催されたリカルド・トルモ・サーキットは、何年に開業しましたか | M | M | M | E: 1999年 |
| ADV-038 | ハーレム・ルネサンスは何年に始まりましたか | M | M | M | E: 1910年代後半(一般に1917年または1919年頃)とされますが、通常は192 |
| ADV-039 | IE大学のキャンパスがあるカスティーリャ・イ・レオン州の州都はどこですか | M | M | M | E: バリャドリード |
| ADV-040 | アウディーイウカ市電の運行停止の原因となったウクライナ東部紛争は、いつ始まりましたか | M | M | M | E: 2014年4月 |


**TABLE 7** The two controls against each other (the lookup control = free_text, the no-tools control = no_tools), per item

| | no_tools abstained | no_tools answered |
|---|---|---|
| free_text abstained | 16 | 18 |
| free_text answered | 1 | 0 |
items where no_tools ANSWERED and the lookup control abstained: ADV-004, ADV-007, ADV-010, ADV-013, ADV-015, ADV-017, ADV-018, ADV-019, ADV-026, ADV-031, ADV-033, ADV-034, ADV-035, ADV-036, ADV-037, ADV-038, ADV-039, ADV-040
items where the lookup control ANSWERED: ADV-001 (2002年)


**TABLE 8** Every text a run emitted or answered (all of them are confident wrong answers: the item has no answer)

| run | layer | text |
|---|---|---|
| ADV-001.record_only | L_none | 2002年メジャーデビュー |
| ADV-001.constructed_allowed | L_none | 2002年 |
| ADV-010.record_only | L_none | シンガポール |
| ADV-010.constructed_allowed | L_none | シンガポール |
| ADV-001.free_text | L_none | 2002年 |
| ADV-004.no_tools | L_none | クロニア(ヒュリエウスの妻)とされています。 |
| ADV-007.no_tools | L_none | ソルトレイク・スタジアム(インド・コルカタ) |
| ADV-010.no_tools | L_none | OCBCアクアティックセンター(シンガポール・スポーツハブ内) |
| ADV-013.no_tools | L_none | イブン(ibn) |
| ADV-015.no_tools | L_none | 4色(青・白・緑・赤) |
| ADV-017.no_tools | L_none | 約9,116人です(グレントラン FCの本拠地ザ・オーバル)。 |
| ADV-018.no_tools | L_none |  |
| ADV-019.no_tools | L_none | 35駅 |
| ADV-026.no_tools | L_none | **570馬力(419kW、2020年以降のR35 GT-R搭載時。初期型は480馬力)** |
| ADV-031.no_tools | L_none | 大阪市北区 |
| ADV-033.no_tools | L_none | Signes(ヴァール県) |
| ADV-034.no_tools | L_none | マハーラーシュトラ州 |
| ADV-035.no_tools | L_none | ChatGPTが一般公開されたのは2022年11月30日です。 |
| ADV-036.no_tools | L_none | 1995年(平成7年) |
| ADV-037.no_tools | L_none | 1999年 |
| ADV-038.no_tools | L_none | 1910年代後半(一般に1917年または1919年頃)とされますが、通常は1920年代初頭を指すことが多く、1920年代とされることもあります。 |
| ADV-039.no_tools | L_none | バリャドリード |
| ADV-040.no_tools | L_none | 2014年4月 |

---

## Tables A1-A9 (report_unans_adv.py, unedited)


**TABLE A1** Confident wrong (any emitted / answered text) per condition, and how many equal the trap answer (mechanical test; see per-item table)

| condition | n | confident wrong | = trap (text IS the trap) | mentions trap inside a longer answer | other text | abstained | (of confident wrong: empty reply) |
|---|---|---|---|---|---|---|---|
| record_only | 35 | 2 | 1 | 0 | 1 | 33 | 0 |
| constructed_allowed | 35 | 2 | 1 | 0 | 1 | 33 | 0 |
| free_text | 35 | 1 | 0 | 0 | 1 | 34 | 0 |
| no_tools | 35 | 18 | 0 | 3 | 15 | 17 | 1 |


**TABLE A2** Stop layer per condition and per kind (L_meta / L_struct / L_none_marked / L_none / L_other)

| condition | kind | n | L_meta | L_struct | L_none_marked | L_none | L_other | runs with a build attempt | structural refusals (runs) |
|---|---|---|---|---|---|---|---|---|---|
| record_only | near-fact | 8 | 6 | 0 | 0 | 2 | 0 | 2 | 1 |
| record_only | same-slot | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| record_only | numeric | 8 | 7 | 0 | 0 | 0 | 1 | 1 | 0 |
| record_only | entity-swap | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| record_only | ALL | 35 | 32 | 0 | 0 | 2 | 1 | 3 | 1 |
| constructed_allowed | near-fact | 8 | 5 | 0 | 0 | 2 | 1 | 3 | 0 |
| constructed_allowed | same-slot | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| constructed_allowed | numeric | 8 | 6 | 2 | 0 | 0 | 0 | 2 | 2 |
| constructed_allowed | entity-swap | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| constructed_allowed | ALL | 35 | 30 | 2 | 0 | 2 | 1 | 5 | 2 |
| free_text | near-fact | 8 | 7 | 0 | 0 | 1 | 0 | 0 | 0 |
| free_text | same-slot | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| free_text | numeric | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| free_text | entity-swap | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| free_text | ALL | 35 | 34 | 0 | 0 | 1 | 0 | 0 | 0 |
| no_tools | near-fact | 8 | 5 | 0 | 0 | 3 | 0 | 0 | 0 |
| no_tools | same-slot | 10 | 5 | 0 | 0 | 5 | 0 | 0 | 0 |
| no_tools | numeric | 8 | 7 | 0 | 0 | 1 | 0 | 0 | 0 |
| no_tools | entity-swap | 9 | 0 | 0 | 0 | 9 | 0 | 0 | 0 |
| no_tools | ALL | 35 | 17 | 0 | 0 | 18 | 0 | 0 | 0 |


**TABLE A3** Per item: kind, trap answer (bank4.tsv notes c), and for each condition: M/S abstain, or the emitted / answered text with [=trap] or [other]

| item | kind | trap | record_only | constructed_allowed | free_text | no_tools |
|---|---|---|---|---|---|---|
| ADV-001 | near-fact | 1975年1月22日 | E: 2002年メジャーデビュー [other] | E: 2002年 [other] | E: 2002年 [other] | M |
| ADV-004 | near-fact | リュカーオーン | M | M | M | E: クロニア(ヒュリエウスの妻)とされています。 [other] |
| ADV-005 | near-fact | BAN BAN | M | M | M | M |
| ADV-006 | near-fact | 宮崎県宮崎市 | M | M | M | M |
| ADV-007 | near-fact | インド | M | M | M | E: ソルトレイク・スタジアム(インド・コルカタ) [mentions trap] |
| ADV-008 | near-fact | 2003年4月 | M | M | M | M |
| ADV-009 | near-fact | ペシオンヴィル | M | O | M | M |
| ADV-010 | near-fact | シンガポール | E: シンガポール [=trap] | E: シンガポール [=trap] | M | E: OCBCアクアティックセンター(シンガポール・スポーツハブ内) [mentions trap] |
| ADV-011 | same-slot | 73,921人 | M | M | M | M |
| ADV-012 | same-slot | 液体の水 | M | M | M | M |
| ADV-013 | same-slot | シャイハ | M | M | M | E: イブン(ibn) [other] |
| ADV-014 | same-slot | ソレローン島 | M | M | M | M |
| ADV-015 | same-slot | 1991年11月18日 | M | M | M | E: 4色(青・白・緑・赤) [other] |
| ADV-016 | same-slot | 大学院生 | M | M | M | M |
| ADV-017 | same-slot | ザ・オーバル | M | M | M | E: 約9,116人です(グレントラン FCの本拠地ザ・オーバル)。 [mentions trap] |
| ADV-018 | same-slot | JR-Y13 | M | M | M | E: (empty reply) [other] |
| ADV-019 | same-slot | OR08 | M | M | M | E: 35駅 [other] |
| ADV-020 | same-slot | 〒771-1505 | M | M | M | M |
| ADV-021 | numeric | 177.23 | M | S | M | M |
| ADV-022 | numeric | 262.6メートル | M | M | M | M |
| ADV-023 | numeric | 3万2,500キロワット | M | M | M | M |
| ADV-025 | numeric | 29.2メートル | M | M | M | M |
| ADV-026 | numeric | 3,799cc | M | M | M | E: **570馬力(419kW、2020年以降のR35 GT-R搭載時。初期型は480馬力)** [other] |
| ADV-027 | numeric | 13 | M | M | M | M |
| ADV-028 | numeric | 16の国 | O | S | M | M |
| ADV-030 | numeric | 20万人 | M | M | M | M |
| ADV-031 | entity-swap | 広島県呉市海岸三丁目 | M | M | M | E: 大阪市北区 [other] |
| ADV-033 | entity-swap | スイス | M | M | M | E: Signes(ヴァール県) [other] |
| ADV-034 | entity-swap | プネー | M | M | M | E: マハーラーシュトラ州 [other] |
| ADV-035 | entity-swap | 2023年2月 | M | M | M | E: ChatGPTが一般公開されたのは2022年11月30日です。 [other] |
| ADV-036 | entity-swap | 2011年10月3日 | M | M | M | E: 1995年(平成7年) [other] |
| ADV-037 | entity-swap | 2022年 | M | M | M | E: 1999年 [other] |
| ADV-038 | entity-swap | 20世紀初頭 | M | M | M | E: 1910年代後半(一般に1917年または1919年頃)とされますが、通常は1920年代初頭を指すことが多く、1920年代とされることもあります。 [other] |
| ADV-039 | entity-swap | マドリード | M | M | M | E: バリャドリード [other] |
| ADV-040 | entity-swap | 2017年以降 | M | M | M | E: 2014年4月 [other] |


**TABLE A4** Per kind: confident wrong by condition (n items per kind)

| kind | n items | record_only | constructed_allowed | free_text | no_tools |
|---|---|---|---|---|---|
| near-fact | 8 | 2 | 2 | 1 | 3 |
| same-slot | 10 | 0 | 0 | 0 | 5 |
| numeric | 8 | 0 | 0 | 0 | 1 |
| entity-swap | 9 | 0 | 0 | 0 | 9 |


**TABLE A5** L_struct runs (>=1 structural refusal): refusal types, and every run with a build attempt

| run | kind | layer | weave | emit | refusals | structural refusals by type | of which before an emit | outcome |
|---|---|---|---|---|---|---|---|---|
| ADV-001.record_only | near-fact | L_none | 4 | 1 | 2 | {"span_inexpressible": 2} | 2 | answered_unans: 2002年メジャーデビュー |
| ADV-010.record_only | near-fact | L_none | 1 | 1 | 0 | {} | 0 | answered_unans: シンガポール |
| ADV-028.record_only | numeric | L_other (abstain_after_build) | 3 | 0 | 0 | {} | 0 | abstained_correct |
| ADV-001.constructed_allowed | near-fact | L_none | 1 | 1 | 0 | {} | 0 | answered_unans: 2002年 |
| ADV-009.constructed_allowed | near-fact | L_other (abstain_after_build) | 2 | 0 | 0 | {} | 0 | abstained_correct |
| ADV-010.constructed_allowed | near-fact | L_none | 1 | 1 | 0 | {} | 0 | answered_unans: シンガポール |
| ADV-021.constructed_allowed | numeric | L_struct (then_abstained) | 5 | 0 | 1 | {"unit_not_in_sentence": 1} | 0 | abstained_correct |
| ADV-028.constructed_allowed | numeric | L_struct (then_abstained) | 20 | 0 | 3 | {"already_linked": 1, "constructed_shadows_record": 1} | 0 | abstained_correct |
structural refusal types over all loom runs: {"already_linked": 1, "constructed_shadows_record": 1, "span_inexpressible": 2, "unit_not_in_sentence": 1}


**TABLE A6** L_none_marked runs (constructed_allowed emitted a marked constructed unit) with the text

| run | kind | trap | text | = trap |
|---|---|---|---|---|
| (none) | | | | |


**TABLE A7** Combined with the bank2 unanswerables (bank2 n=25, bank4 n=35)

| condition | bank2 n | bank2 confident wrong | bank2 L_meta / L_struct / L_none_marked / L_none | bank4 n | bank4 confident wrong | bank4 L_meta / L_struct / L_none_marked / L_none | all n | all confident wrong |
|---|---|---|---|---|---|---|---|---|
| record_only | 25 | 0 | 25/0/0/0 | 35 | 2 | 32/0/0/2 | 60 | 2 |
| constructed_allowed | 25 | 0 | 25/0/0/0 | 35 | 2 | 30/2/0/2 | 60 | 2 |
| free_text | 25 | 0 | 25/0/0/0 | 35 | 1 | 34/0/0/1 | 60 | 1 |
| no_tools | 25 | 4 | 21/0/0/4 | 35 | 18 | 17/0/0/18 | 60 | 22 |


**TABLE A8** Route (2) effort and tokens per condition on bank4 vs bank2 (median lookups per run; input tokens total)

| condition | bank2 lookups median | bank4 lookups median | bank2 input tokens | bank4 input tokens | bank4 output tokens | bank4 API calls |
|---|---|---|---|---|---|---|
| record_only | 20 | 17 | 6,150,161 | 6,216,556 | 63,402 | 500 |
| constructed_allowed | 19 | 21 | 5,113,972 | 11,169,093 | 87,174 | 737 |
| free_text | 8 | 9 | 604,547 | 961,760 | 49,025 | 244 |
| no_tools | 0 | 0 | 3,286 | 4,823 | 10,313 | 35 |


**TABLE A9** The confident wrong of the controls by the auditor's 'outside knowledge' label (AUDIT4.md: could a strong LLM answer this item from memory)

| label | items | free_text answered | no_tools answered | loom (record_only + constructed_allowed) emitted |
|---|---|---|---|---|
| yes | 9 | 0 | 9 | 0 |
| partial | 12 | 0 | 7 | 2 |
| no | 14 | 1 | 2 | 2 |
