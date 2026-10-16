# Meter v2 report (long stories, equal per-turn budget)

Stories: LS-D01. Repeats: [1]. Arms: A3 (structure (crosses)), A3f (flat table (no geometry)), A1v (log + grep, raw message appended by the harness (arms.v2 only)). Runs: 3.

Fewer than 3 repeats: a range is a single value, 'beats' is indicative only (OP-PUB-8 asks for ranges that do not overlap).

Every cell is `mean (min-max)` over repeats of the SUM over the stories of the set.

## Plants noticed at intake (structure notes and model reports, separately)

| metric | A3 | A3f | A1v |
|---|---|---|---|
| contradictions planted | 12 | 12 | 12 |
| contradictions: structure notes | 8 | 8 | 0 |
| contradictions: model reports | 4 | 6 | 12 |
| contradictions: either | 8 | 8 | 12 |
| reversals planted | 4 | 4 | 4 |
| reversals: structure notes | 4 | 4 | 0 |
| reversals: model reports | 4 | 4 | 1 |
| reversals: either | 4 | 4 | 1 |
| updates planted | 8 | 8 | 8 |
| updates: structure notes (UPDATE) | 8 | 8 | 0 |
| updates: model (supersede) | 0 | 0 | n/a |
| updates: either | 8 | 8 | 0 |
| false alarm: structure, list-trap pairs | 0 | 0 | 0 |
| false alarm: structure, unmatched (an unplanted conflict is possible) | 0 | 0 | 0 |
| false alarm: model report pairs matching no plant | 0 | 0 | 4 |

## Answers at the checkpoints

| metric | A3 | A3f | A1v |
|---|---|---|---|
| questions asked | 40 | 40 | 40 |
| right | 7 | 8 | 19 |
| over-broad | 0 | 0 | 0 |
| abstain | 21 | 18 | 3 |
| confident wrong | 4 | 6 | 10 |
| absent admitted (right) | 8 | 8 | 8 |
| false conflict claimed (inside confident wrong) | 2 | 3 | 0 |
| right per mille | 175 | 200 | 475 |
| present: asked | 12 | 12 | 12 |
| present: right | 3 | 3 | 12 |
| present: confident wrong | 1 | 0 | 0 |
| contested: asked | 12 | 12 | 12 |
| contested: right | 4 | 5 | 1 |
| contested: confident wrong | 2 | 3 | 10 |
| updated: asked | 8 | 8 | 8 |
| updated: right | 0 | 0 | 6 |
| updated: confident wrong | 1 | 3 | 0 |
| absent: asked | 8 | 8 | 8 |
| absent: admitted (right) | 8 | 8 | 8 |
| absent: confident wrong | 0 | 0 | 0 |

## Cost (tokens are estimates when the client is the stub)

| metric | A3 | A3f | A1v |
|---|---|---|---|
| input tokens | 4902830 | 4489373 | 3255123 |
| output tokens | 46529 | 41944 | 55243 |
| API calls (assistant turns) | 641 | 599 | 677 |
| tool calls | 819 | 746 | 689 |
| story turns | 160 | 160 | 160 |
| turns / episodes capped by the runaway cap | 0 | 0 | 0 |
| results cut by the budget | 88 | 63 | 100 |
| characters omitted by the budget | 41327 | 37221 | 29837 |

## P2 and P3 (OP-PUB-8, changed: revise until BOTH hold)

- **P2, the structure beats the log + search** (A3 vs A1): contradictions found (either) with ranges that do not overlap, right answers at least equal, confident wrong at most equal. Verdict: **not decidable (missing arm or data)**.
- **P3, the geometry beats the flat table** (A3 vs A3f): ranges that do not overlap on at least one of contradictions / reversals / updates / right answers, and not worse on the others. Verdict: **not met**.

## Pre-registered predictions P-PUB-1..4 (design 6.4; thresholds are this harness's operationalisation, frozen with the code)

| id | prediction | outcome |
|---|---|---|
| P-PUB-1 | Under the budget, A1's right answers fall well below the meter v1's 55/60 (916 per mille). Operationalised: A1 right_per_mille < 750. | not decidable |
| P-PUB-2 | A3 notices more contradictions than A1 (structure or model, 'any'). Confirmed iff min over repeats of A3 > max over repeats of A1 (ranges do not overlap). | not decidable |
| P-PUB-3 | A3 and A3f differ little on same-seat contradictions (|mean A3 - mean A3f| <= 1 plant per story-set) and A3 is higher on reversals + updates ('any'). | not confirmed |
| P-PUB-4 | A3's input tokens are about those of A1 or lower. Operationalised: mean A3 <= 1.25 x mean A1. | not decidable |

Asymmetry of A1 (see the module doc): its answer is a closed value scored by exact match, not a gate-passed quote.

## Arm version and who writes the memory

Arm version(s) in these runs: arms.v2. arms.v1 = the pilot's arms (the model writes its own words). arms.v2 = A3 / A3f writes must be VERBATIM WHOLE SENTENCES of the delivered message (a refused write stores nothing), declared topics must be pieces of the story's own words, A3 and A3f identically; A0 / A1 unchanged; A1v = A1 with the raw message appended to the log by the harness.

**A1's log is MODEL-WRITTEN** (the model chooses and words every line, at most 64 characters): its recall is bounded by what the model chose to write. A1v's log is the raw story (every sentence, appended automatically), so A1 vs A1v measures the cost of the model's own log writing.

Verbatim gate (writes accepted by the gate / refused as not verbatim / topics refused): A3 r01 149 / 8 / 0; A3f r01 98 / 3 / 0.

## Updated questions, one by one (class; abstain type)

| arm | repeat | question index | class | answer status |
|---|---|---|---|---|
| A3 | 1 | 7 認証端末の設置日は何日ですか？ | abstain | cannot_weave |
| A3 | 1 | 3 棚ラベルの確認作業はいつまでですか？ | abstain | cannot_weave |
| A3 | 1 | 13 本の庭開きの会場準備は何日ですか？ | abstain | no_record |
| A3 | 1 | 17 参加希望を送る期限は何日ですか？ | abstain | no_record |
| A3 | 1 | 27 展示写真の許可確認を終える日を教えてください？ | abstain | no_record |
| A3 | 1 | 23 新任向け研修は何分で組みますか？ | abstain | no_record |
| A3 | 1 | 33 増便分として用意する台車は何台ですか？ | confident_wrong | contested |
| A3 | 1 | 37 玄関照明の動作確認は何時に行いますか？ | abstain | no_record |
| A3f | 1 | 7 認証端末の設置日は何日ですか？ | confident_wrong | contested |
| A3f | 1 | 3 棚ラベルの確認作業はいつまでですか？ | confident_wrong | contested |
| A3f | 1 | 13 本の庭開きの会場準備は何日ですか？ | abstain | no_record |
| A3f | 1 | 17 参加希望を送る期限は何日ですか？ | abstain | no_record |
| A3f | 1 | 27 展示写真の許可確認を終える日を教えてください？ | abstain | no_record |
| A3f | 1 | 23 新任向け研修は何分で組みますか？ | abstain | no_record |
| A3f | 1 | 33 増便分として用意する台車は何台ですか？ | confident_wrong | contested |
| A3f | 1 | 37 玄関照明の動作確認は何時に行いますか？ | abstain | no_record |
| A1v | 1 | 7 認証端末の設置日は何日ですか？ | right | value |
| A1v | 1 | 3 棚ラベルの確認作業はいつまでですか？ | right | value |
| A1v | 1 | 13 本の庭開きの会場準備は何日ですか？ | abstain | none |
| A1v | 1 | 17 参加希望を送る期限は何日ですか？ | abstain | none |
| A1v | 1 | 27 展示写真の許可確認を終える日を教えてください？ | right | value |
| A1v | 1 | 23 新任向け研修は何分で組みますか？ | right | value |
| A1v | 1 | 33 増便分として用意する台車は何台ですか？ | right | value |
| A1v | 1 | 37 玄関照明の動作確認は何時に行いますか？ | right | value |
