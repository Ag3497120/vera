# Real Agent Question Evaluation — 2026-10-02

## Method

The evaluator reads `$VERA_REAL_QUESTIONS`, classifies each question with `conductor.classify_question`, and runs the conductor against the compiled Vera frame. It also attempts to build a second, session-specific frame from only earlier rows in the same session and file order. Earlier human answers and option labels are passed through the typed frame writers; rejected entries are omitted. For accepted CHOICE, CONFIRM, or SCOPE answer rows, it attempts a question-specific policy. The current row and all later rows are excluded from its accumulated frame.

The closed-choice asker is a fake that always returns `None`; no model or network call is made. Scoring uses exact string equality. `WRONG` means the conductor returned an answer different from the recorded human answer; every non-ANSWER reply is counted as `ESCALATED`. The 72 known-answer rows are reported, with the 27 exact option-label answers shown separately.

Question text is not reproduced in this report. Row IDs refer to one-based input order. The accumulated-frame outcome is the primary leave-one-out result; Vera-only results are the baseline.

The typed frame writer rejected 2677 prior-record write attempts across per-row frames. These are repeated attempts to encode the same source rows for different target rows, not unique rejected rows. Rejected text was left out rather than normalized or forced into a record.

## Question-kind distribution

| Kind | Count | Share |
|---|---:|---:|
| ORDER | 10 | 7.7% |
| CHOICE | 18 | 13.8% |
| CONFIRM | 3 | 2.3% |
| SCOPE | 7 | 5.4% |
| STATUS | 0 | 0.0% |
| OTHER | 92 | 70.8% |

`OTHER` / unclassified rate: **92/130 (70.8%)**.

Ten concrete unclassified rows (question text omitted):

| Row | Session | Kind | Human answer recorded? |
|---|---|---|---|
| R001 | c4f2e02f | OTHER | yes |
| R003 | bdb06f7e | OTHER | yes |
| R004 | bdb06f7e | OTHER | yes |
| R005 | bdb06f7e | OTHER | no |
| R006 | bdb06f7e | OTHER | yes |
| R007 | bdb06f7e | OTHER | yes |
| R009 | bdb06f7e | OTHER | yes |
| R010 | bdb06f7e | OTHER | yes |
| R011 | bdb06f7e | OTHER | yes |
| R012 | bdb06f7e | OTHER | no |

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
| R001 | OTHER | 0 | macOSメニューバーから垂らす（推奨） | ESCALATE: typed frame record | question is outside the closed question set |
| R002 | CHOICE | 1 | つけて、エージェントが探索を完遂できない可能性があるということを明示してそのまま続行するか選べるようにする | ESCALATE: POLICY | no active cited POLICY determines this choice |
| R003 | OTHER | 0 | 設定でアクセスを付与する | ESCALATE: typed frame record | question is outside the closed question set |
| R004 | OTHER | 1 | ローカル限定・絶対に公開しない（推奨） | ESCALATE: human | outside frame authority: outward publishing |
| R005 | OTHER | 2 | unknown | ESCALATE: typed frame record | question is outside the closed question set |
| R006 | OTHER | 2 | [User dismissed — do not proceed, wait for next instruction] | ESCALATE: typed frame record | question is outside the closed question set |
| R007 | OTHER | 3 | [User dismissed — do not proceed, wait for next instruction] | ESCALATE: typed frame record | question is outside the closed question set |
| R008 | ORDER | 4 | jgenは使わずにvera-aのみを使う。llm系は触らない | ESCALATE: TASK state | predecessor or successor task state is missing |
| R009 | OTHER | 5 | Vera-aをやると書いた通りそれ以外は一切やるつもりはない | ESCALATE: typed frame record | question is outside the closed question set |
| R010 | OTHER | 6 | さっきと同じでvera-aのみに集中でそれ以外は一切やらない | ESCALATE: typed frame record | question is outside the closed question set |

## Frame-growth estimate

On the 27 exact option-label rows, 27 accumulated-frame escalations were considered for a counterfactual addition of that row's recorded human choice. The simulation uses a typed DECISION, a POLICY only if its exact question condition passes the frame writer, and current option labels as question-sourced vocabulary for CHOICE. Added records are not part of the scored leave-one-out result; invalid records are not forced.

Correctly fixed in that simulation: **0**. The human choice and required records are listed below.

| Row | Kind | Human decision to record | Counterfactual result |
|---|---|---|---|
| — | — | No escalation in this set was fixed by the supported frame addition. | — |

Not fixed by that frame addition: **27** escalated exact-label rows. Rows classified OTHER, ORDER, or STATUS cannot be made answerable by a generic POLICY; supported policy rows can still fail because the typed writer rejects the question condition or answer, because option mapping remains unresolved, or because an existing record conflicts. This experiment did not alter those gates.


| Unfixed row | Kind | Why the counterfactual did not yield a correct answer |
|---|---|---|
| R001 | OTHER | this question kind has no generic POLICY answer path |
| R003 | OTHER | this question kind has no generic POLICY answer path |
| R004 | OTHER | this question kind has no generic POLICY answer path |
| R011 | OTHER | this question kind has no generic POLICY answer path |
| R032 | OTHER | this question kind has no generic POLICY answer path |
| R041 | OTHER | this question kind has no generic POLICY answer path |
| R042 | OTHER | this question kind has no generic POLICY answer path |
| R049 | OTHER | this question kind has no generic POLICY answer path |
| R051 | SCOPE | the typed DECISION writer rejected the recorded answer |
| R056 | CHOICE | the typed DECISION writer rejected the recorded answer |
| R058 | SCOPE | the typed DECISION writer rejected the recorded answer |
| R062 | OTHER | this question kind has no generic POLICY answer path |
| R074 | OTHER | this question kind has no generic POLICY answer path |
| R078 | OTHER | this question kind has no generic POLICY answer path |
| R081 | ORDER | this question kind has no generic POLICY answer path |
| R082 | OTHER | this question kind has no generic POLICY answer path |
| R084 | OTHER | this question kind has no generic POLICY answer path |
| R085 | CHOICE | the typed POLICY writer rejected the question condition or answer |
| R086 | OTHER | this question kind has no generic POLICY answer path |
| R100 | OTHER | this question kind has no generic POLICY answer path |
| R103 | OTHER | this question kind has no generic POLICY answer path |
| R105 | OTHER | this question kind has no generic POLICY answer path |
| R107 | OTHER | this question kind has no generic POLICY answer path |
| R110 | OTHER | this question kind has no generic POLICY answer path |
| R119 | OTHER | this question kind has no generic POLICY answer path |
| R120 | OTHER | this question kind has no generic POLICY answer path |
| R127 | OTHER | this question kind has no generic POLICY answer path |

## Limits

The accumulated frame is deliberately narrow: it uses earlier answers from the same session only, in source-file order. It does not merge decisions across project sessions, infer unstated policies, repair the classifier, or tune conductor behavior to this set. Frame growth is a counterfactual estimate for exact option-label answers, not a production update.
