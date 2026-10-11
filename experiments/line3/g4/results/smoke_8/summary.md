# G4 meter -- summary

Arms with records: A, B.  Per-arm tables: `meter_<arm>.<key>.md`.

## Step 8, per arm (present = intra2 whose article has entered; the headline row is present WITHOUT 未着; gold in a candidate beside it)

| arm | records at the step | present (all) | 未着 (primary flag) | 未着 (arm's own tiers) | denominator = present - 未着 | present-correct | correct / denominator | gold in a candidate | present confident wrong | absent | absent-correct | false presence | absent confident wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 6 | 3 | 1 | 1 | 2 | 0 | 0.0% | 0 | 0 | 3 | 0 | 3 | 0 |
| B | 6 | 3 | 1 | 3 | 2 | 0 | 0.0% | 0 | 2 | 3 | 0 | 3 | 0 |

## Events per arm (denominator without 未着; the primary flag of the arm)

| arm | flag | denominator | 現れる | 直入 / 後から / entry unmeasured | never (tags) | 残る (all later steps) | 壊れる | 置き換え | 単独誤答化 | 戻る |
|---|---|---|---|---|---|---|---|---|---|---|
| A | unarrived | 2 (未着 1 apart) | 0/2 | 0 / 0 / 0 | 未採択 2 | 0 of 0 | 0 | 0 | 0 | 0 |
| B | unarrived_3tier | 2 (未着 1 apart) | 0/2 | 0 / 0 / 0 | 未着 2 | 0 of 0 | 0 | 0 | 0 | 0 |

## Registered predictions

| id | prediction | value | status |
|---|---|---|---|
| P-1 | A: most 現れる are 直入 (more than half) and 後から <= 5 of 69 | 直入 0, 後から 0, entry unmeasured 0, of 0 appeared | not judged: arm A has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
| P-3 | A: among losses U > R > A, and 単独誤答化 <= 2 | tags {}; 単独誤答化 0 | not judged: arm A has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
| P-4 | A, C: unans absent-correct at 300 <= 5 of 25 for both, and >= 1 confident wrong on the absent row somewhere | A 0/0 abstain; single ANSWER on the absent row: True | not judged: no records of arm C |
| P-5 | B: present-correct at 300 <= 3 of 69 | 0 | not judged: arm B has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
| P-7 | stack: the closed share at 300 is higher with the foundation on than off | not computed by the meter | not judged: a structure fact (gate G-2 / stack ledgers), not a question |
| P-8 | A: 未着 at 300 is 5..25 of 69 | 0 | not judged: arm A has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
| P-9 | A: 未着 never returns once a gold unit exists | 0 returns | not judged: arm A has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
| P-10 | A: >= 75% of the appeared questions with a later step are 残る at every later step | 0 of 0 (-) | not judged: arm A has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
| P-11 | A: present-correct at 300 <= 20 of 69 | 0 | not judged: arm A has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
| P-12 | B: gold in a candidate at 300 <= A's, and no B-correct question that A lacks (a question with a one-character gold alternative aside) | A 0, B 0; B-only [] (of which one-character golds, left out: []) | not judged: arm A has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5); arm B has 66 of 66 scheduled steps incomplete (e.g. 1,2,3,5) |
