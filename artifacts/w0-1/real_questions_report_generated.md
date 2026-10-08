# Real Agent Question Evaluation — 2026-10-02

## Method

The evaluator reads `$VERA_REAL_QUESTIONS`, classifies each question with `conductor.classify_question`, and runs the conductor against the compiled Vera frame. It also attempts to build a second, session-specific frame from only earlier rows in the same session and file order. Earlier human answers and option labels are passed through the typed frame writers; rejected entries are omitted. For accepted CHOICE, CONFIRM, or SCOPE answer rows, it attempts a question-specific policy. The current row and all later rows are excluded from its accumulated frame.

The closed-choice asker is a fake that always returns `None`; no model or network call is made. Scoring uses exact string equality. `WRONG` means the conductor returned an answer different from the recorded human answer; every non-ANSWER reply is counted as `ESCALATED`. The 72 known-answer rows are reported, with the 27 exact option-label answers shown separately.

Question text is not reproduced in this report. Row IDs refer to one-based input order. The accumulated-frame outcome is the primary leave-one-out result; Vera-only results are the baseline.

The typed frame writer rejected 2754 prior-record write attempts across per-row frames. These are repeated attempts to encode the same source rows for different target rows, not unique rejected rows. Rejected text was left out rather than normalized or forced into a record.

## Question-kind distribution

| Kind | Count | Share |
|---|---:|---:|
| ORDER | 7 | 5.4% |
| CHOICE | 78 | 60.0% |
| CONFIRM | 0 | 0.0% |
| SCOPE | 8 | 6.2% |
| STATUS | 0 | 0.0% |
| DESIGN_PREFERENCE | 1 | 0.8% |
| FEATURE_SELECTION | 0 | 0.0% |
| PERMISSION | 7 | 5.4% |
| REQUIREMENT_CLARIFICATION | 1 | 0.8% |
| PLAN_CONFIRMATION | 0 | 0.0% |
| RESOURCE_CHOICE | 0 | 0.0% |
| PRIORITY_CHOICE | 3 | 2.3% |
| DECISION_REQUEST | 0 | 0.0% |
| OTHER | 25 | 19.2% |

`OTHER` / unclassified rate: **25/130 (19.2%)**.

Ten concrete unclassified rows (question text omitted):

| Row | Session | Kind | Human answer recorded? |
|---|---|---|---|
| R006 | bdb06f7e | OTHER | yes |
| R009 | bdb06f7e | OTHER | yes |
| R012 | bdb06f7e | OTHER | no |
| R018 | 9d818891 | OTHER | no |
| R019 | 9d818891 | OTHER | yes |
| R020 | 9d818891 | OTHER | yes |
| R030 | 32c02fec | OTHER | no |
| R031 | 0910dc3f | OTHER | no |
| R036 | 0910dc3f | OTHER | yes |
| R044 | 0910dc3f | OTHER | yes |

## Exact-answer outcomes

| Population | Frame | Agreed | Wrong | Escalated |
|---|---|---:|---:|---:|
| 72 recorded human answers | Vera frame | 0 | 0 | 72 |
| 72 recorded human answers | Vera + prior same-session frame | 0 | 0 | 72 |
| 27 exact option-label answers | Vera frame | 0 | 0 | 27 |
| 27 exact option-label answers | Vera + prior same-session frame | 0 | 0 | 27 |

The row totals use the unnormalized answer strings as stored. `AGREED + WRONG + ESCALATED` equals the population size in each row.

## Worked examples

Examples below are calculated traces, not additional evaluation cases. Agreement and disagreement use the accumulated leave-one-out frame and only rows with a recorded human answer. Escalation examples may also use rows whose human answer is unknown.

### Agreed

Available: 0; shown: 0.

No rows in this category; an example cannot be supplied without inventing one.

### Disagreed (wrong answer)

Available: 0; shown: 0.

No rows in this category; an example cannot be supplied without inventing one.

### Escalated

Available: 130; shown: 10.

| Row | Kind | Earlier same-session answers | Human answer | Conductor reply | Trace |
|---|---|---:|---|---|---|
| R001 | CHOICE | 0 | macOSメニューバーから垂らす（推奨） | ESCALATE: POLICY | no active cited POLICY determines this choice |
| R002 | CHOICE | 1 | つけて、エージェントが探索を完遂できない可能性があるということを明示してそのまま続行するか選べるようにする | ESCALATE: POLICY | no active cited POLICY determines this choice |
| R003 | CHOICE | 0 | 設定でアクセスを付与する | ESCALATE: POLICY | no active cited POLICY determines this choice |
| R004 | PERMISSION | 1 | ローカル限定・絶対に公開しない（推奨） | ESCALATE: human | outside frame authority: outward publishing |
| R005 | CHOICE | 2 | unknown | ESCALATE: POLICY | no active cited POLICY determines this choice |
| R006 | OTHER | 2 | [User dismissed — do not proceed, wait for next instruction] | ESCALATE: typed frame record | question is outside the closed question set |
| R007 | CHOICE | 3 | [User dismissed — do not proceed, wait for next instruction] | ESCALATE: POLICY | no active cited POLICY determines this choice |
| R008 | CHOICE | 4 | jgenは使わずにvera-aのみを使う。llm系は触らない | ESCALATE: POLICY | no active cited POLICY determines this choice |
| R009 | OTHER | 5 | Vera-aをやると書いた通りそれ以外は一切やるつもりはない | ESCALATE: typed frame record | question is outside the closed question set |
| R010 | CHOICE | 6 | さっきと同じでvera-aのみに集中でそれ以外は一切やらない | ESCALATE: POLICY | no active cited POLICY determines this choice |

## Frame-growth estimate

On the 27 exact option-label rows, 27 accumulated-frame escalations were considered for a counterfactual addition of that row's recorded human choice. The simulation uses a typed DECISION, a POLICY only if its exact question condition passes the frame writer, and current option labels as question-sourced vocabulary for CHOICE. Added records are not part of the scored leave-one-out result; invalid records are not forced.

Correctly fixed in that simulation: **0**. The human choice and required records are listed below.

| Row | Kind | Human decision to record | Counterfactual result |
|---|---|---|---|
| — | — | No escalation in this set was fixed by the supported frame addition. | — |

Not fixed by that frame addition: **27** escalated exact-label rows. Rows classified OTHER, ORDER, or STATUS cannot be made answerable by a generic POLICY; supported policy rows can still fail because the typed writer rejects the question condition or answer, because option mapping remains unresolved, or because an existing record conflicts. This experiment did not alter those gates.


| Unfixed row | Kind | Why the counterfactual did not yield a correct answer |
|---|---|---|
| R001 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R003 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R004 | PERMISSION | this question kind has no generic POLICY answer path |
| R011 | CHOICE | the typed POLICY writer rejected the question condition or answer |
| R032 | CHOICE | the typed POLICY writer rejected the question condition or answer |
| R041 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R042 | PERMISSION | this question kind has no generic POLICY answer path |
| R049 | CHOICE | the typed POLICY writer rejected the question condition or answer |
| R051 | SCOPE | the typed DECISION writer rejected the recorded answer |
| R056 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R058 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R062 | SCOPE | the typed DECISION writer rejected the recorded answer |
| R074 | OTHER | this question kind has no generic POLICY answer path |
| R078 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R081 | ORDER | this question kind has no generic POLICY answer path |
| R082 | SCOPE | the typed DECISION writer rejected the recorded answer |
| R084 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R085 | CHOICE | the typed POLICY writer rejected the question condition or answer |
| R086 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R100 | CHOICE | the typed POLICY writer rejected the question condition or answer |
| R103 | CHOICE | the typed POLICY writer rejected the question condition or answer |
| R105 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R107 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R110 | CHOICE | the typed POLICY writer rejected the question condition or answer |
| R119 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R120 | PERMISSION | this question kind has no generic POLICY answer path |
| R127 | CHOICE | the typed POLICY writer rejected the question condition or answer |

## Limits

The accumulated frame is deliberately narrow: it uses earlier answers from the same session only, in source-file order. It does not merge decisions across project sessions, infer unstated policies, repair the classifier, or tune conductor behavior to this set. Frame growth is a counterfactual estimate for exact option-label answers, not a production update.
